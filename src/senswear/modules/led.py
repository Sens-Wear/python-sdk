from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from typing import TypeAlias

from ..uuids import LED_COLOR_UUID
from ._common import GattClient, unpack_exact

LED_COLOR_FORMAT = "<I"
LED_COLOR_LENGTH = 4
LedColorInput: TypeAlias = "LedColor | int | str | tuple[int, int, int]"
_HEX_COLOR_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


@dataclass(frozen=True)
class LedColor:
    """RGB color encoded by the firmware as little-endian ``0x00RRGGBB``."""

    red: int
    green: int
    blue: int

    def __post_init__(self) -> None:
        for name, value in (
            ("red", self.red),
            ("green", self.green),
            ("blue", self.blue),
        ):
            if not isinstance(value, int) or not 0 <= value <= 255:
                raise ValueError(f"{name} must be an integer between 0 and 255.")

    @classmethod
    def from_bytes(cls, payload: bytes | bytearray | memoryview) -> "LedColor":
        (color,) = unpack_exact(payload, LED_COLOR_FORMAT, "LED color")
        return cls.from_int(int(color))

    @classmethod
    def from_int(cls, color: int) -> "LedColor":
        if not isinstance(color, int) or not 0 <= color <= 0xFFFFFF:
            raise ValueError("color must be an integer between 0x000000 and 0xffffff.")
        return cls((color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF)

    @classmethod
    def from_hex(cls, color: str) -> "LedColor":
        match = _HEX_COLOR_RE.fullmatch(color.strip())
        if match is None:
            raise ValueError("color must be '#RRGGBB'.")
        return cls.from_int(int(match.group(1), 16))

    @classmethod
    def coerce(cls, color: LedColorInput) -> "LedColor":
        if isinstance(color, cls):
            return color
        if isinstance(color, int):
            return cls.from_int(color)
        if isinstance(color, str):
            return cls.from_hex(color)
        if isinstance(color, tuple) and len(color) == 3:
            return cls(*color)
        raise TypeError("color must be LedColor, int, '#RRGGBB', or a 3-item tuple.")

    @property
    def is_off(self) -> bool:
        return self.to_int() == 0

    def to_int(self) -> int:
        return (self.red << 16) | (self.green << 8) | self.blue

    def to_bytes(self) -> bytes:
        return struct.pack(LED_COLOR_FORMAT, self.to_int())

    def to_hex(self) -> str:
        return f"#{self.red:02x}{self.green:02x}{self.blue:02x}"


class LedModule:
    characteristic_uuid = LED_COLOR_UUID

    def __init__(self, client: GattClient) -> None:
        self._client = client

    async def read(self) -> LedColor:
        return LedColor.from_bytes(
            await self._client.read_gatt_char(self.characteristic_uuid)
        )

    async def set(self, color: LedColorInput, *, response: bool = True) -> None:
        await self._client.write_gatt_char(
            self.characteristic_uuid,
            LedColor.coerce(color).to_bytes(),
            response=response,
        )

    async def set_rgb(
        self, red: int, green: int, blue: int, *, response: bool = True
    ) -> None:
        await self.set(LedColor(red, green, blue), response=response)

    async def off(self, *, response: bool = True) -> None:
        await self.set(LedColor(0, 0, 0), response=response)
