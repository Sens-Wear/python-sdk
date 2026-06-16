from __future__ import annotations

import asyncio
import inspect
import struct
from dataclasses import dataclass
from typing import Awaitable, Callable, Protocol

from ..exceptions import ProtocolError
from ..uuids import POWER_GAUGE_STATE_UUID

GAUGE_STATE_FORMAT = "<hHhhHHHH"
GAUGE_STATE_LENGTH = struct.calcsize(GAUGE_STATE_FORMAT)
BatteryGaugeCallback = Callable[["BatteryGaugeState"], None | Awaitable[None]]


class _GattClient(Protocol):
    async def read_gatt_char(self, characteristic_uuid: str) -> bytes:
        ...

    async def start_notify(self, characteristic_uuid: str, callback: Callable[[object, bytearray], None]) -> None:
        ...

    async def stop_notify(self, characteristic_uuid: str) -> None:
        ...


@dataclass(frozen=True)
class BatteryGaugeState:
    """Battery gauge state reported by the firmware power BLE service."""

    temperature_deci_c: int
    voltage_mv: int
    average_current_ma: int
    average_power_mw: int
    state_of_charge_deci_percent: int
    nominal_available_capacity_mah: int
    full_battery_capacity_mah: int
    remaining_capacity_mah: int

    @classmethod
    def from_bytes(cls, payload: bytes | bytearray | memoryview) -> "BatteryGaugeState":
        data = bytes(payload)
        if len(data) != GAUGE_STATE_LENGTH:
            raise ProtocolError(
                f"Battery gauge payload must be {GAUGE_STATE_LENGTH} bytes, got {len(data)}."
            )
        return cls(*struct.unpack(GAUGE_STATE_FORMAT, data))

    @property
    def temperature_c(self) -> float:
        """Battery temperature in degrees Celsius."""

        return self.temperature_deci_c / 10.0

    @property
    def state_of_charge_percent(self) -> float:
        """Battery state of charge in percent."""

        return self.state_of_charge_deci_percent / 10.0

    @property
    def is_zero_state(self) -> bool:
        """Return True when the firmware reports its all-zero gauge fallback."""

        return all(value == 0 for value in self.to_dict().values())

    def to_dict(self) -> dict[str, int]:
        """Return the raw firmware fields as a dictionary."""

        return {
            "temperature_deci_c": self.temperature_deci_c,
            "voltage_mv": self.voltage_mv,
            "average_current_ma": self.average_current_ma,
            "average_power_mw": self.average_power_mw,
            "state_of_charge_deci_percent": self.state_of_charge_deci_percent,
            "nominal_available_capacity_mah": self.nominal_available_capacity_mah,
            "full_battery_capacity_mah": self.full_battery_capacity_mah,
            "remaining_capacity_mah": self.remaining_capacity_mah,
        }


class BatteryGaugeModule:
    """Battery gauge accessors for the SensWear power service."""

    characteristic_uuid = POWER_GAUGE_STATE_UUID

    def __init__(self, client: _GattClient) -> None:
        self._client = client
        self._notify_handler: Callable[[object, bytearray], None] | None = None

    async def read(self) -> BatteryGaugeState:
        """Read the current battery gauge state."""

        payload = await self._client.read_gatt_char(self.characteristic_uuid)
        return BatteryGaugeState.from_bytes(payload)

    async def subscribe(self, callback: BatteryGaugeCallback) -> None:
        """Subscribe to battery gauge notifications.

        The callback can be a normal function or an async function. The firmware
        sends notifications when the gauge state changes while notification is
        enabled.
        """

        if self._notify_handler is not None:
            await self.unsubscribe()

        def handle_notification(sender: object, data: bytearray) -> None:
            state = BatteryGaugeState.from_bytes(data)
            result = callback(state)
            if inspect.isawaitable(result):
                asyncio.create_task(result)

        self._notify_handler = handle_notification
        await self._client.start_notify(self.characteristic_uuid, handle_notification)

    async def unsubscribe(self) -> None:
        """Stop battery gauge notifications if subscribed."""

        if self._notify_handler is None:
            return
        await self._client.stop_notify(self.characteristic_uuid)
        self._notify_handler = None

