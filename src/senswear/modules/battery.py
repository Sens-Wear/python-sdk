from __future__ import annotations

from dataclasses import dataclass

from ..uuids import POWER_BATTERY_LEVEL_UUID
from ._common import (
    DecodedCallback,
    GattClient,
    NotificationHandler,
    notification_handler,
    unpack_exact,
)

BATTERY_LEVEL_FORMAT = "<B"
BATTERY_LEVEL_LENGTH = 1
BatteryLevelCallback = DecodedCallback["BatteryLevel"]


@dataclass(frozen=True)
class BatteryLevel:
    """Bluetooth SIG Battery Level value, in percent."""

    percent: int

    def __post_init__(self) -> None:
        if not 0 <= self.percent <= 100:
            raise ValueError("percent must be between 0 and 100.")

    @classmethod
    def from_bytes(cls, payload: bytes | bytearray | memoryview) -> "BatteryLevel":
        (percent,) = unpack_exact(payload, BATTERY_LEVEL_FORMAT, "Battery level")
        return cls(percent=int(percent))

    @property
    def state_of_charge_percent(self) -> float:
        """Compatibility spelling used by SDK 0.1."""

        return float(self.percent)


# Compatibility names for callers that imported the 0.1 classes.
BatteryGaugeState = BatteryLevel


class BatteryModule:
    """Read and subscribe to the standard Battery Level characteristic."""

    characteristic_uuid = POWER_BATTERY_LEVEL_UUID

    def __init__(self, client: GattClient) -> None:
        self._client = client
        self._notify_handler: NotificationHandler | None = None

    async def read(self) -> BatteryLevel:
        return BatteryLevel.from_bytes(
            await self._client.read_gatt_char(self.characteristic_uuid)
        )

    async def subscribe(self, callback: BatteryLevelCallback) -> None:
        if self._notify_handler is not None:
            await self.unsubscribe()
        self._notify_handler = notification_handler(BatteryLevel.from_bytes, callback)
        await self._client.start_notify(self.characteristic_uuid, self._notify_handler)

    async def unsubscribe(self) -> None:
        if self._notify_handler is None:
            return
        await self._client.stop_notify(self.characteristic_uuid)
        self._notify_handler = None


BatteryGaugeModule = BatteryModule
