from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any

from ..exceptions import ProtocolError
from ..uuids import (
    TOUCH_GESTURE_UUID,
    TOUCH_RAW_DATA_UUID,
    TOUCH_SAMPLING_ENABLE_UUID,
    TOUCH_STATE_UUID,
)
from ._common import (
    DecodedCallback,
    GattClient,
    NotificationHandler,
    decode_bool,
    encode_bool,
    notification_handler,
    unpack_exact,
)

TOUCH_STATE_FORMAT = "<q?HH"
TOUCH_GESTURE_FORMAT = "<qBB"
# This characteristic deliberately mirrors the aligned C touch_msg_t ABI.
TOUCH_RAW_DATA_FORMAT = "<q?xHHB"
TOUCH_STATE_LENGTH = 13
TOUCH_GESTURE_LENGTH = 10
TOUCH_RAW_DATA_LENGTH = 16


class TouchGesture(IntEnum):
    NONE = 0
    SINGLE_CLICK = 1
    CLICK_AND_HOLD = 2
    DOUBLE_CLICK = 3
    DOWN_SWIPE = 4
    DOWN_SWIPE_AND_HOLD = 5
    RIGHT_SWIPE = 6
    RIGHT_SWIPE_AND_HOLD = 7
    UP_SWIPE = 8
    UP_SWIPE_AND_HOLD = 9
    LEFT_SWIPE = 10
    LEFT_SWIPE_AND_HOLD = 11


@dataclass(frozen=True)
class TouchState:
    timestamp_us: int
    touched: bool
    x: int
    y: int

    @classmethod
    def from_bytes(cls, payload: bytes | bytearray | memoryview) -> "TouchState":
        return cls(*unpack_exact(payload, TOUCH_STATE_FORMAT, "Touch state"))

    @property
    def timestamp(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp_us / 1_000_000, tz=timezone.utc)


@dataclass(frozen=True)
class TouchGestureSample:
    timestamp_us: int
    gesture: int
    gesture_state: int

    @classmethod
    def from_bytes(
        cls, payload: bytes | bytearray | memoryview
    ) -> "TouchGestureSample":
        return cls(*unpack_exact(payload, TOUCH_GESTURE_FORMAT, "Touch gesture"))

    @property
    def gesture_type(self) -> TouchGesture | int:
        try:
            return TouchGesture(self.gesture)
        except ValueError:
            return self.gesture


@dataclass(frozen=True)
class RawTouchSample:
    timestamp_us: int
    touched: bool
    x: int
    y: int
    touch_state: int

    @classmethod
    def from_bytes(cls, payload: bytes | bytearray | memoryview) -> "RawTouchSample":
        data = bytes(payload)
        # The C struct has one trailing alignment byte (16-byte sizeof); struct
        # ignores it because it carries no protocol information.
        if len(data) != TOUCH_RAW_DATA_LENGTH:
            raise ProtocolError(
                f"Raw touch payload must be {TOUCH_RAW_DATA_LENGTH} bytes, got {len(data)}."
            )
        return cls(*unpack_exact(data[:15], TOUCH_RAW_DATA_FORMAT, "Raw touch"))


class TouchModule:
    _streams: dict[str, tuple[str, Any]] = {
        "state": (TOUCH_STATE_UUID, TouchState),
        "gesture": (TOUCH_GESTURE_UUID, TouchGestureSample),
        "raw": (TOUCH_RAW_DATA_UUID, RawTouchSample),
    }

    def __init__(self, client: GattClient) -> None:
        self._client = client
        self._handlers: dict[str, NotificationHandler] = {}

    async def _read(self, name: str):
        uuid, decoder = self._streams[name]
        return decoder.from_bytes(await self._client.read_gatt_char(uuid))

    async def read_state(self) -> TouchState:
        return await self._read("state")

    async def read_gesture(self) -> TouchGestureSample:
        return await self._read("gesture")

    async def read_raw(self) -> RawTouchSample:
        return await self._read("raw")

    async def _subscribe(self, name: str, callback: DecodedCallback) -> None:
        await self._unsubscribe(name)
        uuid, decoder = self._streams[name]
        handler = notification_handler(decoder.from_bytes, callback)
        self._handlers[name] = handler
        await self._client.start_notify(uuid, handler)

    async def _unsubscribe(self, name: str) -> None:
        if name not in self._handlers:
            return
        await self._client.stop_notify(self._streams[name][0])
        del self._handlers[name]

    async def subscribe_state(self, callback: DecodedCallback[TouchState]) -> None:
        await self._subscribe("state", callback)

    async def subscribe_gesture(
        self, callback: DecodedCallback[TouchGestureSample]
    ) -> None:
        await self._subscribe("gesture", callback)

    async def subscribe_raw(self, callback: DecodedCallback[RawTouchSample]) -> None:
        await self._subscribe("raw", callback)

    async def unsubscribe_state(self) -> None:
        await self._unsubscribe("state")

    async def unsubscribe_gesture(self) -> None:
        await self._unsubscribe("gesture")

    async def unsubscribe_raw(self) -> None:
        await self._unsubscribe("raw")

    async def unsubscribe_all(self) -> None:
        for name in tuple(self._handlers):
            await self._unsubscribe(name)

    async def sampling_enabled(self) -> bool:
        return decode_bool(
            await self._client.read_gatt_char(TOUCH_SAMPLING_ENABLE_UUID),
            "Touch sampling enable",
        )

    async def set_sampling_enabled(
        self, enabled: bool, *, response: bool = True
    ) -> None:
        await self._client.write_gatt_char(
            TOUCH_SAMPLING_ENABLE_UUID,
            encode_bool(enabled, "enabled"),
            response=response,
        )
