from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Iterable, Protocol, TypeAlias

from ..exceptions import ProtocolError
from ..uuids import HAPTIC_PATTERN_UUID

HAPTIC_PATTERN_VERSION = 1
HAPTIC_PATTERN_FLAGS = 0
HAPTIC_MAX_FRAMES = 64
HAPTIC_PATTERN_HEADER_FORMAT = "<BBH"
HAPTIC_FRAME_FORMAT = "<HB"
HAPTIC_PATTERN_HEADER_LENGTH = struct.calcsize(HAPTIC_PATTERN_HEADER_FORMAT)
HAPTIC_FRAME_LENGTH = struct.calcsize(HAPTIC_FRAME_FORMAT)

HapticFrameInput: TypeAlias = "HapticFrame | tuple[int, int]"
HapticPatternInput: TypeAlias = "HapticPattern | Iterable[HapticFrameInput]"


class _GattClient(Protocol):
    async def write_gatt_char(
        self,
        characteristic_uuid: str,
        data: bytes,
        *,
        response: bool = True,
    ) -> None:
        ...


@dataclass(frozen=True)
class HapticFrame:
    """One haptic actuator frame."""

    duration_ms: int
    intensity: int

    def __post_init__(self) -> None:
        if not isinstance(self.duration_ms, int) or not 1 <= self.duration_ms <= 0xFFFF:
            raise ValueError("duration_ms must be an integer between 1 and 65535.")
        if not isinstance(self.intensity, int) or not 0 <= self.intensity <= 0xFF:
            raise ValueError("intensity must be an integer between 0 and 255.")

    @classmethod
    def coerce(cls, frame: HapticFrameInput) -> "HapticFrame":
        if isinstance(frame, cls):
            return frame
        if isinstance(frame, tuple) and len(frame) == 2:
            return cls(duration_ms=frame[0], intensity=frame[1])
        raise TypeError("frame must be HapticFrame or a (duration_ms, intensity) tuple.")

    @classmethod
    def from_bytes(cls, payload: bytes | bytearray | memoryview) -> "HapticFrame":
        data = bytes(payload)
        if len(data) != HAPTIC_FRAME_LENGTH:
            raise ProtocolError(f"Haptic frame payload must be {HAPTIC_FRAME_LENGTH} bytes, got {len(data)}.")
        return cls(*struct.unpack(HAPTIC_FRAME_FORMAT, data))

    def to_bytes(self) -> bytes:
        return struct.pack(HAPTIC_FRAME_FORMAT, self.duration_ms, self.intensity)

    def to_dict(self) -> dict[str, int]:
        return {
            "duration_ms": self.duration_ms,
            "intensity": self.intensity,
        }


@dataclass(frozen=True)
class HapticPattern:
    """Versioned BLE haptic pattern payload."""

    frames: tuple[HapticFrame, ...]

    def __post_init__(self) -> None:
        if not 1 <= len(self.frames) <= HAPTIC_MAX_FRAMES:
            raise ValueError(f"haptic patterns must contain 1 to {HAPTIC_MAX_FRAMES} frames.")

    @classmethod
    def from_frames(cls, frames: Iterable[HapticFrameInput]) -> "HapticPattern":
        return cls(tuple(HapticFrame.coerce(frame) for frame in frames))

    @classmethod
    def from_bytes(cls, payload: bytes | bytearray | memoryview) -> "HapticPattern":
        data = bytes(payload)
        if len(data) < HAPTIC_PATTERN_HEADER_LENGTH:
            raise ProtocolError(
                f"Haptic pattern payload must be at least {HAPTIC_PATTERN_HEADER_LENGTH} bytes."
            )

        version, flags, frame_count = struct.unpack(
            HAPTIC_PATTERN_HEADER_FORMAT,
            data[:HAPTIC_PATTERN_HEADER_LENGTH],
        )
        if version != HAPTIC_PATTERN_VERSION:
            raise ProtocolError(f"Unsupported haptic pattern version {version}.")
        if flags != HAPTIC_PATTERN_FLAGS:
            raise ProtocolError(f"Unsupported haptic pattern flags {flags}.")
        if frame_count == 0 or frame_count > HAPTIC_MAX_FRAMES:
            raise ProtocolError(f"Haptic pattern frame count must be 1 to {HAPTIC_MAX_FRAMES}.")

        expected_len = HAPTIC_PATTERN_HEADER_LENGTH + (frame_count * HAPTIC_FRAME_LENGTH)
        if len(data) != expected_len:
            raise ProtocolError(f"Haptic pattern payload must be {expected_len} bytes, got {len(data)}.")

        frames = []
        for index in range(frame_count):
            offset = HAPTIC_PATTERN_HEADER_LENGTH + (index * HAPTIC_FRAME_LENGTH)
            frames.append(HapticFrame.from_bytes(data[offset : offset + HAPTIC_FRAME_LENGTH]))

        return cls(tuple(frames))

    @property
    def total_duration_ms(self) -> int:
        return sum(frame.duration_ms for frame in self.frames)

    def to_bytes(self) -> bytes:
        header = struct.pack(
            HAPTIC_PATTERN_HEADER_FORMAT,
            HAPTIC_PATTERN_VERSION,
            HAPTIC_PATTERN_FLAGS,
            len(self.frames),
        )
        return header + b"".join(frame.to_bytes() for frame in self.frames)

    def to_dict(self) -> dict[str, object]:
        return {
            "version": HAPTIC_PATTERN_VERSION,
            "flags": HAPTIC_PATTERN_FLAGS,
            "frame_count": len(self.frames),
            "total_duration_ms": self.total_duration_ms,
            "frames": [frame.to_dict() for frame in self.frames],
        }


class HapticModule:
    """Haptic actuator controls for the SensWear haptic service."""

    pattern_uuid = HAPTIC_PATTERN_UUID

    def __init__(self, client: _GattClient) -> None:
        self._client = client

    async def play(self, pattern: HapticPatternInput, *, response: bool = True) -> None:
        """Play a haptic pattern."""

        haptic_pattern = _coerce_pattern(pattern)
        await self._client.write_gatt_char(
            self.pattern_uuid,
            haptic_pattern.to_bytes(),
            response=response,
        )

    async def vibrate(self, duration_ms: int, intensity: int = 255, *, response: bool = True) -> None:
        """Play one constant-intensity vibration frame."""

        await self.play(HapticPattern((HapticFrame(duration_ms, intensity),)), response=response)


def _coerce_pattern(pattern: HapticPatternInput) -> HapticPattern:
    if isinstance(pattern, HapticPattern):
        return pattern
    return HapticPattern.from_frames(pattern)

