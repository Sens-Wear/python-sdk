from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from ..uuids import POWER_BATTERY_LEVEL_STATUS_UUID
from ._common import (
    DecodedCallback,
    GattClient,
    NotificationHandler,
    notification_handler,
    unpack_exact,
)

BATTERY_LEVEL_STATUS_FORMAT = "<BHB"
BATTERY_LEVEL_STATUS_LENGTH = 4
ChargerStateCallback = DecodedCallback["BatteryLevelStatus"]


class PowerSourceState(IntEnum):
    NOT_CONNECTED = 0
    CONNECTED = 1
    UNKNOWN = 2
    RESERVED = 3


class ChargeState(IntEnum):
    UNKNOWN = 0
    CHARGING = 1
    DISCHARGING_ACTIVE = 2
    DISCHARGING_INACTIVE = 3


class ChargeLevel(IntEnum):
    UNKNOWN = 0
    GOOD = 1
    LOW = 2
    CRITICAL = 3


@dataclass(frozen=True)
class BatteryLevelStatus:
    """Battery Level Status (Bluetooth SIG characteristic 0x2BED)."""

    flags: int
    power_state: int
    battery_level: int

    @classmethod
    def from_bytes(
        cls, payload: bytes | bytearray | memoryview
    ) -> "BatteryLevelStatus":
        flags, power_state, battery_level = unpack_exact(
            payload, BATTERY_LEVEL_STATUS_FORMAT, "Battery level status"
        )
        return cls(int(flags), int(power_state), int(battery_level))

    @property
    def battery_present(self) -> bool:
        return bool(self.power_state & 0x1)

    @property
    def wired_power(self) -> PowerSourceState:
        return PowerSourceState((self.power_state >> 1) & 0x3)

    @property
    def wireless_power(self) -> PowerSourceState:
        return PowerSourceState((self.power_state >> 3) & 0x3)

    @property
    def charge_state(self) -> ChargeState:
        return ChargeState((self.power_state >> 5) & 0x3)

    @property
    def charge_level(self) -> ChargeLevel:
        return ChargeLevel((self.power_state >> 7) & 0x3)

    @property
    def charge_type(self) -> int:
        return (self.power_state >> 9) & 0x7

    @property
    def charging_fault_reason(self) -> int:
        return (self.power_state >> 12) & 0xF

    @property
    def power_good(self) -> bool:
        return self.wired_power == PowerSourceState.CONNECTED

    @property
    def charging(self) -> bool:
        return self.charge_state == ChargeState.CHARGING

    @property
    def charged(self) -> bool:
        return self.charge_state == ChargeState.DISCHARGING_INACTIVE

    @property
    def has_fault(self) -> bool:
        return self.charging_fault_reason != 0


ChargerState = BatteryLevelStatus


class PowerStatusModule:
    """Read and subscribe to the standard Battery Level Status characteristic."""

    characteristic_uuid = POWER_BATTERY_LEVEL_STATUS_UUID

    def __init__(self, client: GattClient) -> None:
        self._client = client
        self._notify_handler: NotificationHandler | None = None

    async def read(self) -> BatteryLevelStatus:
        payload = await self._client.read_gatt_char(self.characteristic_uuid)
        return BatteryLevelStatus.from_bytes(payload)

    async def subscribe(self, callback: ChargerStateCallback) -> None:
        if self._notify_handler is not None:
            await self.unsubscribe()
        self._notify_handler = notification_handler(
            BatteryLevelStatus.from_bytes, callback
        )
        await self._client.start_notify(self.characteristic_uuid, self._notify_handler)

    async def unsubscribe(self) -> None:
        if self._notify_handler is None:
            return
        await self._client.stop_notify(self.characteristic_uuid)
        self._notify_handler = None


ChargerModule = PowerStatusModule
