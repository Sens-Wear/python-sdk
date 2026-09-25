from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any, ClassVar

from ..uuids import (
    IMU_ACTIVITY_UUID,
    IMU_DRAIN_PERIOD_UUID,
    IMU_GESTURE_UUID,
    IMU_GYROSCOPE_UUID,
    IMU_LINEAR_ACCELERATION_UUID,
    IMU_PHYSICAL_STREAMS_ENABLE_UUID,
    IMU_QUATERNION_UUID,
)
from ._common import (
    DecodedCallback,
    GattClient,
    NotificationHandler,
    decode_bool,
    encode_bool,
    notification_handler,
    require_write_response,
    unpack_exact,
)

QUATERNION_FORMAT = "<qhhhhH"
VECTOR_FORMAT = "<qhhh"
GESTURE_FORMAT = "<qBB"
ACTIVITY_FORMAT = "<qBBB"
QUATERNION_LENGTH = struct.calcsize(QUATERNION_FORMAT)
LINEAR_ACCELERATION_LENGTH = struct.calcsize(VECTOR_FORMAT)
GYROSCOPE_LENGTH = struct.calcsize(VECTOR_FORMAT)
GESTURE_LENGTH = struct.calcsize(GESTURE_FORMAT)
ACTIVITY_LENGTH = struct.calcsize(ACTIVITY_FORMAT)
QUATERNION_SCALE = 16384.0
ACCELERATION_SCALE_G = 4096.0


class ImuGesture(IntEnum):
    NONE = 0x00
    WRIST_SHAKE_JIGGLE = 0x03
    FLICK_IN = 0x04
    FLICK_OUT = 0x05


class ImuActivity(IntEnum):
    STILL = 0
    WALKING = 1
    RUNNING = 2
    ON_BICYCLE = 3
    IN_VEHICLE = 4
    TILTING = 5


class ActivityTransition(IntEnum):
    ENDED = 0
    STARTED = 1


@dataclass(frozen=True)
class TimestampedSample:
    timestamp_us: int
    _format: ClassVar[str]
    _label: ClassVar[str]

    @property
    def timestamp(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp_us / 1_000_000, tz=timezone.utc)

    @classmethod
    def from_bytes(cls, payload: bytes | bytearray | memoryview):
        return cls(*unpack_exact(payload, cls._format, cls._label))


@dataclass(frozen=True)
class QuaternionSample(TimestampedSample):
    x: int
    y: int
    z: int
    w: int
    accuracy: int
    _format = QUATERNION_FORMAT
    _label = "Quaternion"

    @property
    def x_float(self) -> float:
        return self.x / QUATERNION_SCALE

    @property
    def y_float(self) -> float:
        return self.y / QUATERNION_SCALE

    @property
    def z_float(self) -> float:
        return self.z / QUATERNION_SCALE

    @property
    def w_float(self) -> float:
        return self.w / QUATERNION_SCALE

    @property
    def accuracy_radians(self) -> float:
        return self.accuracy / QUATERNION_SCALE

    @property
    def accuracy_degrees(self) -> float:
        return math.degrees(self.accuracy_radians)

    def to_tuple(self, *, normalized: bool = True):
        if normalized:
            return (self.x_float, self.y_float, self.z_float, self.w_float)
        return (self.x, self.y, self.z, self.w)


@dataclass(frozen=True)
class LinearAccelerationSample(TimestampedSample):
    x: int
    y: int
    z: int
    _format = VECTOR_FORMAT
    _label = "Linear acceleration"

    @property
    def x_g(self) -> float:
        return self.x / ACCELERATION_SCALE_G

    @property
    def y_g(self) -> float:
        return self.y / ACCELERATION_SCALE_G

    @property
    def z_g(self) -> float:
        return self.z / ACCELERATION_SCALE_G

    def to_tuple(self, *, scaled: bool = True):
        return (self.x_g, self.y_g, self.z_g) if scaled else (self.x, self.y, self.z)


@dataclass(frozen=True)
class GyroscopeSample(TimestampedSample):
    x: int
    y: int
    z: int
    _format = VECTOR_FORMAT
    _label = "Gyroscope"

    def to_tuple(self) -> tuple[int, int, int]:
        return (self.x, self.y, self.z)


@dataclass(frozen=True)
class GestureSample(TimestampedSample):
    sensor_id: int
    gesture: int
    _format = GESTURE_FORMAT
    _label = "IMU gesture"

    @property
    def gesture_type(self) -> ImuGesture | int:
        try:
            return ImuGesture(self.gesture)
        except ValueError:
            return self.gesture


@dataclass(frozen=True)
class ActivitySample(TimestampedSample):
    sensor_id: int
    activity: int
    transition: int
    _format = ACTIVITY_FORMAT
    _label = "IMU activity"

    @property
    def activity_type(self) -> ImuActivity | int:
        try:
            return ImuActivity(self.activity)
        except ValueError:
            return self.activity

    @property
    def transition_type(self) -> ActivityTransition | int:
        try:
            return ActivityTransition(self.transition)
        except ValueError:
            return self.transition


QuaternionCallback = DecodedCallback[QuaternionSample]
LinearAccelerationCallback = DecodedCallback[LinearAccelerationSample]
GyroscopeCallback = DecodedCallback[GyroscopeSample]
GestureCallback = DecodedCallback[GestureSample]
ActivityCallback = DecodedCallback[ActivitySample]


class ImuModule:
    """Read, configure, and subscribe to all current IMU characteristics."""

    _streams: dict[str, tuple[str, Any]] = {
        "quaternion": (IMU_QUATERNION_UUID, QuaternionSample),
        "linear_acceleration": (IMU_LINEAR_ACCELERATION_UUID, LinearAccelerationSample),
        "gyroscope": (IMU_GYROSCOPE_UUID, GyroscopeSample),
        "gesture": (IMU_GESTURE_UUID, GestureSample),
        "activity": (IMU_ACTIVITY_UUID, ActivitySample),
    }

    def __init__(self, client: GattClient) -> None:
        self._client = client
        self._handlers: dict[str, NotificationHandler] = {}

    async def _read(self, name: str):
        uuid, decoder = self._streams[name]
        return decoder.from_bytes(await self._client.read_gatt_char(uuid))

    async def read_quaternion(self) -> QuaternionSample:
        return await self._read("quaternion")

    async def read_linear_acceleration(self) -> LinearAccelerationSample:
        return await self._read("linear_acceleration")

    async def read_gyroscope(self) -> GyroscopeSample:
        return await self._read("gyroscope")

    async def read_gesture(self) -> GestureSample:
        return await self._read("gesture")

    async def read_activity(self) -> ActivitySample:
        return await self._read("activity")

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

    async def subscribe_quaternion(self, callback: QuaternionCallback) -> None:
        await self._subscribe("quaternion", callback)

    async def unsubscribe_quaternion(self) -> None:
        await self._unsubscribe("quaternion")

    async def subscribe_linear_acceleration(
        self, callback: LinearAccelerationCallback
    ) -> None:
        await self._subscribe("linear_acceleration", callback)

    async def unsubscribe_linear_acceleration(self) -> None:
        await self._unsubscribe("linear_acceleration")

    async def subscribe_gyroscope(self, callback: GyroscopeCallback) -> None:
        await self._subscribe("gyroscope", callback)

    async def unsubscribe_gyroscope(self) -> None:
        await self._unsubscribe("gyroscope")

    async def subscribe_gesture(self, callback: GestureCallback) -> None:
        await self._subscribe("gesture", callback)

    async def unsubscribe_gesture(self) -> None:
        await self._unsubscribe("gesture")

    async def subscribe_activity(self, callback: ActivityCallback) -> None:
        await self._subscribe("activity", callback)

    async def unsubscribe_activity(self) -> None:
        await self._unsubscribe("activity")

    async def unsubscribe_all(self) -> None:
        for name in tuple(self._handlers):
            await self._unsubscribe(name)

    async def physical_streams_enabled(self) -> bool:
        payload = await self._client.read_gatt_char(IMU_PHYSICAL_STREAMS_ENABLE_UUID)
        return decode_bool(payload, "IMU physical-stream enable")

    async def set_physical_streams_enabled(
        self, enabled: bool, *, response: bool = True
    ) -> None:
        require_write_response(response)
        await self._client.write_gatt_char(
            IMU_PHYSICAL_STREAMS_ENABLE_UUID,
            encode_bool(enabled, "enabled"),
            response=response,
        )

    async def read_drain_period_ms(self) -> int:
        (period,) = unpack_exact(
            await self._client.read_gatt_char(IMU_DRAIN_PERIOD_UUID),
            "<I",
            "IMU drain period",
        )
        return int(period)

    async def set_drain_period_ms(
        self, period_ms: int, *, response: bool = True
    ) -> None:
        require_write_response(response)
        if not isinstance(period_ms, int) or not 1 <= period_ms <= 0xFFFFFFFF:
            raise ValueError("period_ms must be an integer between 1 and 4294967295.")
        await self._client.write_gatt_char(
            IMU_DRAIN_PERIOD_UUID, struct.pack("<I", period_ms), response=response
        )
