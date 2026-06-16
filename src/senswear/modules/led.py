from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from typing import Protocol, TypeAlias

from ..exceptions import ProtocolError
from ..uuids import LED_COLOR_UUID

LED_COLOR_FORMAT = "<I"
LED_COLOR_LENGTH = struct.calcsize(LED_COLOR_FORMAT)
LedColorInput: TypeAlias = "LedColor | int | str | tuple[int, int, int] | tuple[int, int, int, int]"
_HEX_COLOR_RE = re.compile(r"^#?([0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


class _GattClient(Protocol):
    async def read_gatt_char(self, characteristic_uuid: str) -> bytes:
        ...

    async def write_gatt_char(
        self,
        characteristic_uuid: str,
        data: bytes,
        *,
        response: bool = True,
    ) -> None:
        ...


@dataclass(frozen=True)
class LedColor:
    """RGBW LED color matching the firmware's 4-byte color value."""

    red: int
    green: int
    blue: int
    white: int = 0

    def __post_init__(self) -> None:
        for name, value in self.to_dict().items():
            if not isinstance(value, int) or not 0 <= value <= 255:
                raise ValueError(f"{name} must be an integer between 0 and 255.")

    @classmethod
    def from_bytes(cls, payload: bytes | bytearray | memoryview) -> "LedColor":
        data = bytes(payload)
        if len(data) != LED_COLOR_LENGTH:
            raise ProtocolError(f"LED color payload must be {LED_COLOR_LENGTH} bytes, got {len(data)}.")
        return cls.from_int(struct.unpack(LED_COLOR_FORMAT, data)[0])

    @classmethod
    def from_int(cls, color: int) -> "LedColor":
        if not isinstance(color, int) or not 0 <= color <= 0xFFFFFFFF:
            raise ValueError("color must be an integer between 0x00000000 and 0xffffffff.")
        return cls(
            red=color & 0xFF,
            green=(color >> 8) & 0xFF,
            blue=(color >> 16) & 0xFF,
            white=(color >> 24) & 0xFF,
        )

    @classmethod
    def from_hex(cls, color: str) -> "LedColor":
        """Create a color from '#RRGGBB' or '#RRGGBBWW' text."""

        match = _HEX_COLOR_RE.fullmatch(color.strip())
        if match is None:
            raise ValueError("color must be '#RRGGBB' or '#RRGGBBWW'.")

        value = match.group(1)
        red = int(value[0:2], 16)
        green = int(value[2:4], 16)
        blue = int(value[4:6], 16)
        white = int(value[6:8], 16) if len(value) == 8 else 0
        return cls(red=red, green=green, blue=blue, white=white)

    @classmethod
    def coerce(cls, color: LedColorInput) -> "LedColor":
        if isinstance(color, cls):
            return color
        if isinstance(color, int):
            return cls.from_int(color)
        if isinstance(color, str):
            return cls.from_hex(color)
        if isinstance(color, tuple) and len(color) in (3, 4):
            return cls(*color)
        raise TypeError("color must be LedColor, int, '#RRGGBB', '#RRGGBBWW', or a 3/4-item tuple.")

    @property
    def is_off(self) -> bool:
        return self.to_int() == 0

    def to_int(self) -> int:
        return self.red | (self.green << 8) | (self.blue << 16) | (self.white << 24)

    def to_bytes(self) -> bytes:
        return struct.pack(LED_COLOR_FORMAT, self.to_int())

    def to_hex(self, *, include_white: bool = False) -> str:
        value = f"#{self.red:02x}{self.green:02x}{self.blue:02x}"
        if include_white:
            value += f"{self.white:02x}"
        return value

    def to_dict(self) -> dict[str, int]:
        return {
            "red": self.red,
            "green": self.green,
            "blue": self.blue,
            "white": self.white,
        }


class LedModule:
    """LED color controls for the SensWear LED service."""

    characteristic_uuid = LED_COLOR_UUID

    def __init__(self, client: _GattClient) -> None:
        self._client = client

    async def read(self) -> LedColor:
        """Read the current RGBW LED color cached by the firmware service."""

        payload = await self._client.read_gatt_char(self.characteristic_uuid)
        return LedColor.from_bytes(payload)

    async def set(self, color: LedColorInput, *, response: bool = True) -> None:
        """Set the LED color.

        A zero color turns the LEDs off in the current firmware bridge.
        """

        led_color = LedColor.coerce(color)
        await self._client.write_gatt_char(
            self.characteristic_uuid,
            led_color.to_bytes(),
            response=response,
        )

    async def set_rgb(self, red: int, green: int, blue: int, *, white: int = 0, response: bool = True) -> None:
        """Set the LED color from RGBW channel values."""

        await self.set(LedColor(red=red, green=green, blue=blue, white=white), response=response)

    async def off(self, *, response: bool = True) -> None:
        """Turn the LEDs off."""

        await self.set(LedColor(0, 0, 0, 0), response=response)

