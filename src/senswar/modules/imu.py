from __future__ import annotations

import asyncio
import inspect
import math
import struct
from dataclasses import dataclass
from typing import Awaitable, Callable, Protocol

from ..exceptions import ProtocolError
from ..uuids import IMU_LINEAR_ACCELERATION_UUID, IMU_QUATERNION_UUID

QUATERNION_FORMAT = "<hhhhH"
QUATERNION_LENGTH = struct.calcsize(QUATERNION_FORMAT)
LINEAR_ACCELERATION_FORMAT = "<hhh"
LINEAR_ACCELERATION_LENGTH = struct.calcsize(LINEAR_ACCELERATION_FORMAT)
QUATERNION_SCALE = 16384.0
ACCELERATION_SCALE_G = 4096.0

QuaternionCallback = Callable[["QuaternionSample"], None | Awaitable[None]]
LinearAccelerationCallback = Callable[["LinearAccelerationSample"], None | Awaitable[None]]


class _GattClient(Protocol):
    async def start_notify(self, characteristic_uuid: str, callback: Callable[[object, bytearray], None]) -> None:
        ...

    async def stop_notify(self, characteristic_uuid: str) -> None:
        ...


@dataclass(frozen=True)
class QuaternionSample:
    """Quaternion sample from the firmware IMU service."""

    x: int
    y: int
    z: int
    w: int
    accuracy: int

    @classmethod
    def from_bytes(cls, payload: bytes | bytearray | memoryview) -> "QuaternionSample":
        data = bytes(payload)
        if len(data) != QUATERNION_LENGTH:
            raise ProtocolError(
                f"Quaternion payload must be {QUATERNION_LENGTH} bytes, got {len(data)}."
            )
        return cls(*struct.unpack(QUATERNION_FORMAT, data))

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
        return self.accuracy_radians * 180.0 / math.pi

    def to_tuple(self, *, normalized: bool = True) -> tuple[float, float, float, float] | tuple[int, int, int, int]:
        if normalized:
            return (self.x_float, self.y_float, self.z_float, self.w_float)
        return (self.x, self.y, self.z, self.w)

    def to_dict(self, *, normalized: bool = False) -> dict[str, float | int]:
        if normalized:
            return {
                "x": self.x_float,
                "y": self.y_float,
                "z": self.z_float,
                "w": self.w_float,
                "accuracy_radians": self.accuracy_radians,
                "accuracy_degrees": self.accuracy_degrees,
            }
        return {
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "w": self.w,
            "accuracy": self.accuracy,
        }


@dataclass(frozen=True)
class LinearAccelerationSample:
    """Linear acceleration sample from the firmware IMU service."""

    x: int
    y: int
    z: int

    @classmethod
    def from_bytes(cls, payload: bytes | bytearray | memoryview) -> "LinearAccelerationSample":
        data = bytes(payload)
        if len(data) != LINEAR_ACCELERATION_LENGTH:
            raise ProtocolError(
                "Linear acceleration payload must be "
                f"{LINEAR_ACCELERATION_LENGTH} bytes, got {len(data)}."
            )
        return cls(*struct.unpack(LINEAR_ACCELERATION_FORMAT, data))

    @property
    def x_g(self) -> float:
        return self.x / ACCELERATION_SCALE_G

    @property
    def y_g(self) -> float:
        return self.y / ACCELERATION_SCALE_G

    @property
    def z_g(self) -> float:
        return self.z / ACCELERATION_SCALE_G

    def to_tuple(self, *, scaled: bool = True) -> tuple[float, float, float] | tuple[int, int, int]:
        if scaled:
            return (self.x_g, self.y_g, self.z_g)
        return (self.x, self.y, self.z)

    def to_dict(self, *, scaled: bool = False) -> dict[str, float | int]:
        if scaled:
            return {
                "x_g": self.x_g,
                "y_g": self.y_g,
                "z_g": self.z_g,
            }
        return {
            "x": self.x,
            "y": self.y,
            "z": self.z,
        }


class ImuModule:
    """Notify-only IMU streams for the Senswar IMU service."""

    quaternion_uuid = IMU_QUATERNION_UUID
    linear_acceleration_uuid = IMU_LINEAR_ACCELERATION_UUID

    def __init__(self, client: _GattClient) -> None:
        self._client = client
        self._quaternion_notify_handler: Callable[[object, bytearray], None] | None = None
        self._linear_acceleration_notify_handler: Callable[[object, bytearray], None] | None = None

    async def subscribe_quaternion(self, callback: QuaternionCallback) -> None:
        """Subscribe to quaternion notifications."""

        if self._quaternion_notify_handler is not None:
            await self.unsubscribe_quaternion()

        def handle_notification(sender: object, data: bytearray) -> None:
            sample = QuaternionSample.from_bytes(data)
            result = callback(sample)
            if inspect.isawaitable(result):
                asyncio.create_task(result)

        self._quaternion_notify_handler = handle_notification
        await self._client.start_notify(self.quaternion_uuid, handle_notification)

    async def unsubscribe_quaternion(self) -> None:
        """Stop quaternion notifications if subscribed."""

        if self._quaternion_notify_handler is None:
            return
        await self._client.stop_notify(self.quaternion_uuid)
        self._quaternion_notify_handler = None

    async def subscribe_linear_acceleration(self, callback: LinearAccelerationCallback) -> None:
        """Subscribe to linear acceleration notifications."""

        if self._linear_acceleration_notify_handler is not None:
            await self.unsubscribe_linear_acceleration()

        def handle_notification(sender: object, data: bytearray) -> None:
            sample = LinearAccelerationSample.from_bytes(data)
            result = callback(sample)
            if inspect.isawaitable(result):
                asyncio.create_task(result)

        self._linear_acceleration_notify_handler = handle_notification
        await self._client.start_notify(self.linear_acceleration_uuid, handle_notification)

    async def unsubscribe_linear_acceleration(self) -> None:
        """Stop linear acceleration notifications if subscribed."""

        if self._linear_acceleration_notify_handler is None:
            return
        await self._client.stop_notify(self.linear_acceleration_uuid)
        self._linear_acceleration_notify_handler = None

    async def unsubscribe_all(self) -> None:
        """Stop every active IMU notification stream."""

        await self.unsubscribe_quaternion()
        await self.unsubscribe_linear_acceleration()
