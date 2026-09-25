from __future__ import annotations

import asyncio
import inspect
import struct
from typing import Any, Awaitable, Callable, Protocol, TypeVar

from ..exceptions import ProtocolError

T = TypeVar("T")
DecodedCallback = Callable[[T], None | Awaitable[None]]
NotificationHandler = Callable[[object, bytearray], None]


class GattClient(Protocol):
    async def read_gatt_char(self, characteristic_uuid: str) -> bytes: ...

    async def write_gatt_char(
        self, characteristic_uuid: str, data: bytes, *, response: bool = True
    ) -> None: ...

    async def start_notify(
        self, characteristic_uuid: str, callback: NotificationHandler
    ) -> None: ...

    async def stop_notify(self, characteristic_uuid: str) -> None: ...


def unpack_exact(
    payload: bytes | bytearray | memoryview, fmt: str, label: str
) -> tuple[Any, ...]:
    data = bytes(payload)
    expected = struct.calcsize(fmt)
    if len(data) != expected:
        raise ProtocolError(
            f"{label} payload must be {expected} bytes, got {len(data)}."
        )
    return struct.unpack(fmt, data)


def decode_bool(payload: bytes | bytearray | memoryview, label: str) -> bool:
    (value,) = unpack_exact(payload, "<B", label)
    if value not in (0, 1):
        raise ProtocolError(f"{label} boolean must be 0 or 1, got {value}.")
    return bool(value)


def encode_bool(value: bool, name: str) -> bytes:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a bool.")
    return bytes((int(value),))


def require_write_response(response: bool) -> None:
    """Enforce firmware characteristics that advertise acknowledged Write only."""

    if not isinstance(response, bool):
        raise TypeError("response must be a bool.")
    if not response:
        raise ValueError("This characteristic requires response=True.")


def notification_handler(
    decoder: Callable[[bytes | bytearray | memoryview], T],
    callback: DecodedCallback[T],
) -> NotificationHandler:
    def handle(sender: object, data: bytearray) -> None:
        del sender
        result = callback(decoder(data))
        if inspect.isawaitable(result):
            asyncio.ensure_future(result)

    return handle
