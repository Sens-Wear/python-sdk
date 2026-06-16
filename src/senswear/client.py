from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from .exceptions import DeviceNotFoundError, NotConnectedError, SenswearDependencyError
from .modules.battery import BatteryGaugeModule
from .modules.charger import ChargerModule
from .modules.haptic import HapticModule
from .modules.imu import ImuModule
from .modules.led import LedModule
from .modules.temperature import TemperatureModule

DEFAULT_NAME_PREFIXES = ("Sens Wear", "SensWear", "SenseWear")
NotifyCallback = Callable[[object, bytearray], None]


@dataclass(frozen=True)
class DiscoveredDevice:
    """A BLE peripheral discovered by the SDK scanner."""

    address: str
    name: str | None
    rssi: int | None = None


class SenswearClient:
    """Async BLE client for SensWear hardware.

    Parameters
    ----------
    address_or_name:
        Optional BLE address, platform identifier, or exact advertised name.
        When omitted, the client connects to the first device with a known
        SensWear advertised name prefix.
    timeout:
        BLE scan/connect timeout in seconds.
    name_prefixes:
        Advertised name prefixes used for automatic discovery.
    """

    def __init__(
        self,
        address_or_name: str | None = None,
        *,
        timeout: float = 10.0,
        name_prefixes: Iterable[str] = DEFAULT_NAME_PREFIXES,
    ) -> None:
        self.address_or_name = address_or_name
        self.timeout = timeout
        self.name_prefixes = tuple(name_prefixes)
        self._client: Any | None = None
        self._device: Any | None = None
        self.battery = BatteryGaugeModule(self)
        self.charger = ChargerModule(self)
        self.haptic = HapticModule(self)
        self.imu = ImuModule(self)
        self.led = LedModule(self)
        self.temperature = TemperatureModule(self)

    async def __aenter__(self) -> "SenswearClient":
        return await self.connect()

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.disconnect()

    @classmethod
    async def discover(
        cls,
        *,
        timeout: float = 5.0,
        name_prefixes: Iterable[str] = DEFAULT_NAME_PREFIXES,
    ) -> list[DiscoveredDevice]:
        """Scan for SensWear-like BLE peripherals."""

        _, BleakScanner = _load_bleak()
        prefixes = tuple(name_prefixes)
        devices = await BleakScanner.discover(timeout=timeout)
        discovered: list[DiscoveredDevice] = []

        for device in devices:
            name = getattr(device, "name", None)
            if prefixes and not _name_matches_prefix(name, prefixes):
                continue
            discovered.append(
                DiscoveredDevice(
                    address=str(getattr(device, "address", "")),
                    name=name,
                    rssi=getattr(device, "rssi", None),
                )
            )

        return discovered

    @property
    def is_connected(self) -> bool:
        """Return True when the underlying BLE client is connected."""

        return _client_is_connected(self._client)

    @property
    def address(self) -> str | None:
        """Return the connected BLE address or platform identifier when known."""

        if self._client is not None:
            address = getattr(self._client, "address", None)
            if address:
                return str(address)
        if self._device is not None:
            address = getattr(self._device, "address", None)
            if address:
                return str(address)
        return None

    async def connect(self) -> "SenswearClient":
        """Connect to a SensWear BLE peripheral."""

        if self.is_connected:
            return self

        BleakClient, _ = _load_bleak()
        self._device = await self._resolve_device()
        self._client = BleakClient(self._device, timeout=self.timeout)
        await self._client.connect()
        return self

    async def disconnect(self) -> None:
        """Disconnect from the current BLE peripheral."""

        if self._client is not None:
            await self._client.disconnect()
        self._client = None
        self._device = None

    async def read_gatt_char(self, characteristic_uuid: str) -> bytes:
        """Read a GATT characteristic from the connected device."""

        client = self._require_client()
        return bytes(await client.read_gatt_char(characteristic_uuid))

    async def write_gatt_char(
        self,
        characteristic_uuid: str,
        data: bytes,
        *,
        response: bool = True,
    ) -> None:
        """Write a GATT characteristic on the connected device."""

        client = self._require_client()
        await client.write_gatt_char(characteristic_uuid, data, response=response)

    async def start_notify(self, characteristic_uuid: str, callback: NotifyCallback) -> None:
        """Subscribe to notifications for a GATT characteristic."""

        client = self._require_client()
        await client.start_notify(characteristic_uuid, callback)

    async def stop_notify(self, characteristic_uuid: str) -> None:
        """Stop notifications for a GATT characteristic."""

        client = self._require_client()
        await client.stop_notify(characteristic_uuid)

    async def _resolve_device(self) -> object:
        _, BleakScanner = _load_bleak()
        devices = await BleakScanner.discover(timeout=self.timeout)

        if self.address_or_name is None:
            for device in devices:
                if _name_matches_prefix(getattr(device, "name", None), self.name_prefixes):
                    return device
            raise DeviceNotFoundError(
                "No SensWear device was found. Make sure the device is powered, "
                "advertising, and close enough to the host."
            )

        target = self.address_or_name.strip()
        for device in devices:
            if _device_matches_target(device, target):
                return device

        if _looks_like_ble_identifier(target):
            return target

        raise DeviceNotFoundError(f"No BLE device named {target!r} was found.")

    def _require_client(self) -> Any:
        if not self.is_connected or self._client is None:
            raise NotConnectedError("Connect to a SensWear device before using GATT operations.")
        return self._client


def _load_bleak() -> tuple[type[Any], type[Any]]:
    try:
        from bleak import BleakClient, BleakScanner
    except ImportError as exc:
        raise SenswearDependencyError(
            "The SensWear SDK needs the 'bleak' package for BLE access. "
            "Install it with 'python -m pip install senswear' or "
            "'python -m pip install bleak'."
        ) from exc
    return BleakClient, BleakScanner


def _client_is_connected(client: Any | None) -> bool:
    if client is None:
        return False
    connected = getattr(client, "is_connected", False)
    if callable(connected):
        connected = connected()
    return bool(connected)


def _name_matches_prefix(name: str | None, prefixes: Iterable[str]) -> bool:
    return bool(name) and str(name).startswith(tuple(prefixes))


def _device_matches_target(device: object, target: str) -> bool:
    address = str(getattr(device, "address", ""))
    name = getattr(device, "name", None)
    return address.lower() == target.lower() or (name is not None and str(name) == target)


def _looks_like_ble_identifier(value: str) -> bool:
    # BLE addresses on Windows/Linux and CoreBluetooth UUIDs on macOS both use separators.
    return ":" in value or "-" in value

