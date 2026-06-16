from __future__ import annotations

import asyncio
import inspect
import struct
from dataclasses import dataclass
from typing import Awaitable, Callable, Protocol

from ..exceptions import ProtocolError
from ..uuids import (
    TEMPERATURE_SAMPLE_UUID,
    TEMPERATURE_SAMPLING_RATE_UUID,
    TEMPERATURE_TRANSFER_INTERVAL_UUID,
)

TEMPERATURE_SAMPLE_FORMAT = "<i"
TEMPERATURE_SAMPLE_LENGTH = struct.calcsize(TEMPERATURE_SAMPLE_FORMAT)
UINT16_FORMAT = "<H"
TemperatureCallback = Callable[["TemperatureSample"], None | Awaitable[None]]


class _GattClient(Protocol):
    async def read_gatt_char(self, characteristic_uuid: str) -> bytes:
        ...

    async def write_gatt_char(
        self,
        characteristic_uuid: str,
        data: bytes,
        *,
        response: bool = True,
    ) -> None:
        ...

    async def start_notify(self, characteristic_uuid: str, callback: Callable[[object, bytearray], None]) -> None:
        ...

    async def stop_notify(self, characteristic_uuid: str) -> None:
        ...


@dataclass(frozen=True)
class TemperatureSample:
    """Temperature sample reported by the firmware temperature service."""

    temperature_mdeg_c: int

    @classmethod
    def from_bytes(cls, payload: bytes | bytearray | memoryview) -> "TemperatureSample":
        data = bytes(payload)
        if len(data) != TEMPERATURE_SAMPLE_LENGTH:
            raise ProtocolError(
                f"Temperature payload must be {TEMPERATURE_SAMPLE_LENGTH} bytes, got {len(data)}."
            )
        return cls(temperature_mdeg_c=struct.unpack(TEMPERATURE_SAMPLE_FORMAT, data)[0])

    @property
    def temperature_c(self) -> float:
        return self.temperature_mdeg_c / 1000.0

    @property
    def temperature_f(self) -> float:
        return (self.temperature_c * 9.0 / 5.0) + 32.0

    def to_dict(self) -> dict[str, int | float]:
        return {
            "temperature_mdeg_c": self.temperature_mdeg_c,
            "temperature_c": self.temperature_c,
            "temperature_f": self.temperature_f,
        }


class TemperatureModule:
    """Temperature accessors for the Senswar temperature service."""

    sample_uuid = TEMPERATURE_SAMPLE_UUID
    sampling_rate_uuid = TEMPERATURE_SAMPLING_RATE_UUID
    transfer_interval_uuid = TEMPERATURE_TRANSFER_INTERVAL_UUID

    def __init__(self, client: _GattClient) -> None:
        self._client = client
        self._notify_handler: Callable[[object, bytearray], None] | None = None

    async def read(self) -> TemperatureSample:
        """Read the latest temperature sample cached by the firmware service."""

        payload = await self._client.read_gatt_char(self.sample_uuid)
        return TemperatureSample.from_bytes(payload)

    async def set_sampling_rate_hz(self, sampling_rate_hz: int, *, response: bool = True) -> None:
        """Set the firmware sampling rate in Hz."""

        payload = _pack_uint16_nonzero(sampling_rate_hz, "sampling_rate_hz")
        await self._client.write_gatt_char(self.sampling_rate_uuid, payload, response=response)

    async def set_transfer_interval(self, transfer_interval: int, *, response: bool = True) -> None:
        """Set the raw transfer interval characteristic value.

        The current MAX30208 firmware driver accepts this value through BLE but
        does not use it when scheduling samples.
        """

        payload = _pack_uint16_nonzero(transfer_interval, "transfer_interval")
        await self._client.write_gatt_char(self.transfer_interval_uuid, payload, response=response)

    async def subscribe(self, callback: TemperatureCallback) -> None:
        """Subscribe to temperature notifications."""

        if self._notify_handler is not None:
            await self.unsubscribe()

        def handle_notification(sender: object, data: bytearray) -> None:
            sample = TemperatureSample.from_bytes(data)
            result = callback(sample)
            if inspect.isawaitable(result):
                asyncio.create_task(result)

        self._notify_handler = handle_notification
        await self._client.start_notify(self.sample_uuid, handle_notification)

    async def unsubscribe(self) -> None:
        """Stop temperature notifications if subscribed."""

        if self._notify_handler is None:
            return
        await self._client.stop_notify(self.sample_uuid)
        self._notify_handler = None


def _pack_uint16_nonzero(value: int, name: str) -> bytes:
    if not isinstance(value, int) or not 1 <= value <= 0xFFFF:
        raise ValueError(f"{name} must be an integer between 1 and 65535.")
    return struct.pack(UINT16_FORMAT, value)
