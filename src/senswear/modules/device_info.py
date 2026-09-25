"""Read-only firmware identity and build capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntFlag

from ..exceptions import ProtocolError
from ..uuids import DEVICE_CAPABILITIES_UUID, FIRMWARE_REVISION_UUID
from ._common import GattClient, unpack_exact

DEVICE_CAPABILITIES_LENGTH = 9
DEVICE_CAPABILITIES_PROTOCOL_VERSION = 1


class DaughterBoard(IntFlag):
    HAPTIC = 1
    PPG = 2
    TEMPERATURE = 4
    TOUCH = 8


class DeviceFeature(IntFlag):
    IMU = 1
    LED = 2
    HAPTIC = 4
    PPG = 8
    TEMPERATURE = 16
    TOUCH = 32
    BATTERY = 64
    TIME = 128


@dataclass(frozen=True)
class DeviceCapabilities:
    """Compiled shields/features, not a physical attachment or health check."""

    protocol_version: int
    shield_mask: int
    feature_mask: int

    def __post_init__(self) -> None:
        if self.protocol_version != DEVICE_CAPABILITIES_PROTOCOL_VERSION:
            raise ProtocolError(f"Unsupported capabilities schema {self.protocol_version}.")
        for label, value in (("shield_mask", self.shield_mask), ("feature_mask", self.feature_mask)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{label} must be an integer.")
            if not 0 <= value <= 0xFFFFFFFF:
                raise ValueError(f"{label} must fit in an unsigned 32-bit integer.")

    @classmethod
    def from_bytes(cls, payload: bytes | bytearray | memoryview) -> DeviceCapabilities:
        return cls(*unpack_exact(payload, "<BII", "Device Capabilities"))

    def has_shield(self, shield: DaughterBoard) -> bool:
        return bool(shield) and (self.shield_mask & int(shield)) == int(shield)

    def has_feature(self, feature: DeviceFeature) -> bool:
        return bool(feature) and (self.feature_mask & int(feature)) == int(feature)

    @property
    def shields(self) -> tuple[DaughterBoard, ...]:
        return tuple(shield for shield in DaughterBoard if self.has_shield(shield))

    @property
    def unknown_shield_mask(self) -> int:
        return self.shield_mask & ~0x0F

    @property
    def unknown_feature_mask(self) -> int:
        return self.feature_mask & ~0xFF


def parse_firmware_version(payload: bytes | bytearray | memoryview) -> str:
    """Decode the DIS UTF-8 revision without inventing a fallback version."""
    try:
        value = bytes(payload).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProtocolError("Firmware Revision must be valid UTF-8.") from exc
    if not value.strip() or "\x00" in value:
        raise ProtocolError("Firmware Revision must be a nonempty string without NUL bytes.")
    return value


@dataclass(frozen=True)
class DeviceInfo:
    firmware_version: str
    capabilities: DeviceCapabilities


class DeviceInfoModule:
    def __init__(self, client: GattClient) -> None:
        self._client = client

    async def read_firmware_version(self) -> str:
        return parse_firmware_version(await self._client.read_gatt_char(FIRMWARE_REVISION_UUID))

    async def read_capabilities(self) -> DeviceCapabilities:
        return DeviceCapabilities.from_bytes(
            await self._client.read_gatt_char(DEVICE_CAPABILITIES_UUID)
        )

    async def read(self) -> DeviceInfo:
        return DeviceInfo(await self.read_firmware_version(), await self.read_capabilities())
