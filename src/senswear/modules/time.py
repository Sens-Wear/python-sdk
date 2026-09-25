from __future__ import annotations

import struct
from dataclasses import dataclass
from datetime import datetime, timezone

from ..exceptions import ProtocolError
from ..uuids import (
    CURRENT_TIME_UUID,
    LOCAL_TIME_INFORMATION_UUID,
    REFERENCE_TIME_INFORMATION_UUID,
)
from ._common import (
    DecodedCallback,
    GattClient,
    NotificationHandler,
    notification_handler,
    require_write_response,
    unpack_exact,
)

CURRENT_TIME_FORMAT = "<HBBBBBBBB"
LOCAL_TIME_FORMAT = "<bB"
REFERENCE_TIME_FORMAT = "<BBBB"
CURRENT_TIME_LENGTH = 10


@dataclass(frozen=True)
class CurrentTime:
    value: datetime
    day_of_week: int
    fractions256: int
    adjust_reason: int

    @classmethod
    def from_bytes(cls, payload: bytes | bytearray | memoryview) -> "CurrentTime":
        year, month, day, hour, minute, second, day_of_week, fractions, reason = (
            unpack_exact(payload, CURRENT_TIME_FORMAT, "Current time")
        )
        try:
            value = datetime(
                year, month, day, hour, minute, second, tzinfo=timezone.utc
            )
        except ValueError as exc:
            raise ProtocolError(f"Invalid Current Time value: {exc}.") from exc
        return cls(value, int(day_of_week), int(fractions), int(reason))

    def to_bytes(self) -> bytes:
        value = _as_utc(self.value)
        day_of_week = value.isoweekday()
        return struct.pack(
            CURRENT_TIME_FORMAT,
            value.year,
            value.month,
            value.day,
            value.hour,
            value.minute,
            value.second,
            day_of_week,
            self.fractions256,
            self.adjust_reason,
        )


@dataclass(frozen=True)
class LocalTimeInformation:
    time_zone_quarter_hours: int
    dst_offset: int

    @classmethod
    def from_bytes(
        cls, payload: bytes | bytearray | memoryview
    ) -> "LocalTimeInformation":
        return cls(*unpack_exact(payload, LOCAL_TIME_FORMAT, "Local time information"))


@dataclass(frozen=True)
class ReferenceTimeInformation:
    source: int
    accuracy_eighths_second: int
    days_since_update: int
    hours_since_update: int

    @classmethod
    def from_bytes(
        cls, payload: bytes | bytearray | memoryview
    ) -> "ReferenceTimeInformation":
        return cls(
            *unpack_exact(payload, REFERENCE_TIME_FORMAT, "Reference time information")
        )


class TimeModule:
    def __init__(self, client: GattClient) -> None:
        self._client = client
        self._notify_handler: NotificationHandler | None = None

    async def read(self) -> CurrentTime:
        return CurrentTime.from_bytes(
            await self._client.read_gatt_char(CURRENT_TIME_UUID)
        )

    async def set(
        self, value: datetime, *, adjust_reason: int = 0, response: bool = True
    ) -> None:
        require_write_response(response)
        if not isinstance(adjust_reason, int) or not 0 <= adjust_reason <= 0xFF:
            raise ValueError("adjust_reason must be an integer between 0 and 255.")
        current = CurrentTime(_as_utc(value), 0, 0, adjust_reason)
        await self._client.write_gatt_char(
            CURRENT_TIME_UUID, current.to_bytes(), response=response
        )

    async def read_local_information(self) -> LocalTimeInformation:
        return LocalTimeInformation.from_bytes(
            await self._client.read_gatt_char(LOCAL_TIME_INFORMATION_UUID)
        )

    async def read_reference_information(self) -> ReferenceTimeInformation:
        return ReferenceTimeInformation.from_bytes(
            await self._client.read_gatt_char(REFERENCE_TIME_INFORMATION_UUID)
        )

    async def subscribe(self, callback: DecodedCallback[CurrentTime]) -> None:
        if self._notify_handler is not None:
            await self.unsubscribe()
        self._notify_handler = notification_handler(CurrentTime.from_bytes, callback)
        await self._client.start_notify(CURRENT_TIME_UUID, self._notify_handler)

    async def unsubscribe(self) -> None:
        if self._notify_handler is None:
            return
        await self._client.stop_notify(CURRENT_TIME_UUID)
        self._notify_handler = None


def _as_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError("value must be a datetime.")
    if value.tzinfo is None:
        raise ValueError("value must be timezone-aware.")
    return value.astimezone(timezone.utc)
