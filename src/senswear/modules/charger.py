from __future__ import annotations

import asyncio
import inspect
import struct
from dataclasses import dataclass
from typing import Awaitable, Callable, Protocol

from ..exceptions import ProtocolError
from ..uuids import POWER_CHARGER_STATE_UUID

CHARGER_STATE_FORMAT = "<I"
CHARGER_STATE_LENGTH = struct.calcsize(CHARGER_STATE_FORMAT)
ChargerStateCallback = Callable[["ChargerState"], None | Awaitable[None]]


class _GattClient(Protocol):
    async def read_gatt_char(self, characteristic_uuid: str) -> bytes:
        ...

    async def start_notify(self, characteristic_uuid: str, callback: Callable[[object, bytearray], None]) -> None:
        ...

    async def stop_notify(self, characteristic_uuid: str) -> None:
        ...


@dataclass(frozen=True)
class ChargerState:
    """BQ25180 charger state reported by the firmware power BLE service."""

    flags: int

    @classmethod
    def from_bytes(cls, payload: bytes | bytearray | memoryview) -> "ChargerState":
        data = bytes(payload)
        if len(data) != CHARGER_STATE_LENGTH:
            raise ProtocolError(
                f"Charger payload must be {CHARGER_STATE_LENGTH} bytes, got {len(data)}."
            )
        return cls(flags=struct.unpack(CHARGER_STATE_FORMAT, data)[0])

    @property
    def button_pressed(self) -> bool:
        return self._bit(0)

    @property
    def wake1(self) -> bool:
        return self._bit(1)

    @property
    def wake2(self) -> bool:
        return self._bit(2)

    @property
    def shipment_mode(self) -> bool:
        return self._bit(3)

    @property
    def shutdown_mode(self) -> bool:
        return self._bit(4)

    @property
    def power_good(self) -> bool:
        return self._bit(5)

    @property
    def charging(self) -> bool:
        return self._bit(6)

    @property
    def charged(self) -> bool:
        return self._bit(7)

    @property
    def thermal_regulation(self) -> bool:
        return self._bit(8)

    @property
    def battery_uvlo(self) -> bool:
        return self._bit(9)

    @property
    def thermal_normal(self) -> bool:
        return self._bit(10)

    @property
    def thermal_warm_or_hot(self) -> bool:
        return self._bit(11)

    @property
    def thermal_warm(self) -> bool:
        return self._bit(12)

    @property
    def thermal_cool(self) -> bool:
        return self._bit(13)

    @property
    def safety_timer_fault(self) -> bool:
        return self._bit(14)

    @property
    def thermal_system_fault(self) -> bool:
        return self._bit(15)

    @property
    def battery_uvlo_fault(self) -> bool:
        return self._bit(16)

    @property
    def battery_ocp_fault(self) -> bool:
        return self._bit(17)

    @property
    def has_fault(self) -> bool:
        return (
            self.safety_timer_fault
            or self.thermal_system_fault
            or self.battery_uvlo_fault
            or self.battery_ocp_fault
        )

    @property
    def is_zero_state(self) -> bool:
        """Return True when the firmware reports its all-zero charger fallback."""

        return self.flags == 0

    def to_dict(self) -> dict[str, bool | int]:
        return {
            "flags": self.flags,
            "button_pressed": self.button_pressed,
            "wake1": self.wake1,
            "wake2": self.wake2,
            "shipment_mode": self.shipment_mode,
            "shutdown_mode": self.shutdown_mode,
            "power_good": self.power_good,
            "charging": self.charging,
            "charged": self.charged,
            "thermal_regulation": self.thermal_regulation,
            "battery_uvlo": self.battery_uvlo,
            "thermal_normal": self.thermal_normal,
            "thermal_warm_or_hot": self.thermal_warm_or_hot,
            "thermal_warm": self.thermal_warm,
            "thermal_cool": self.thermal_cool,
            "safety_timer_fault": self.safety_timer_fault,
            "thermal_system_fault": self.thermal_system_fault,
            "battery_uvlo_fault": self.battery_uvlo_fault,
            "battery_ocp_fault": self.battery_ocp_fault,
            "has_fault": self.has_fault,
        }

    def _bit(self, bit: int) -> bool:
        return bool(self.flags & (1 << bit))


class ChargerModule:
    """Charger accessors for the SensWear power service."""

    characteristic_uuid = POWER_CHARGER_STATE_UUID

    def __init__(self, client: _GattClient) -> None:
        self._client = client
        self._notify_handler: Callable[[object, bytearray], None] | None = None

    async def read(self) -> ChargerState:
        """Read the current charger state."""

        payload = await self._client.read_gatt_char(self.characteristic_uuid)
        return ChargerState.from_bytes(payload)

    async def subscribe(self, callback: ChargerStateCallback) -> None:
        """Subscribe to charger state notifications."""

        if self._notify_handler is not None:
            await self.unsubscribe()

        def handle_notification(sender: object, data: bytearray) -> None:
            state = ChargerState.from_bytes(data)
            result = callback(state)
            if inspect.isawaitable(result):
                asyncio.create_task(result)

        self._notify_handler = handle_notification
        await self._client.start_notify(self.characteristic_uuid, handle_notification)

    async def unsubscribe(self) -> None:
        """Stop charger state notifications if subscribed."""

        if self._notify_handler is None:
            return
        await self._client.stop_notify(self.characteristic_uuid)
        self._notify_handler = None

