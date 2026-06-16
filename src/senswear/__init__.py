"""Python SDK for SensWear hardware."""

from .client import DiscoveredDevice, SenswearClient
from .exceptions import (
    DeviceNotFoundError,
    NotConnectedError,
    ProtocolError,
    SenswearDependencyError,
    SenswearError,
)
from .modules.battery import BatteryGaugeState
from .modules.charger import ChargerState
from .modules.haptic import HapticFrame, HapticPattern
from .modules.imu import LinearAccelerationSample, QuaternionSample
from .modules.led import LedColor
from .modules.temperature import TemperatureSample

__all__ = [
    "BatteryGaugeState",
    "ChargerState",
    "DeviceNotFoundError",
    "DiscoveredDevice",
    "HapticFrame",
    "HapticPattern",
    "NotConnectedError",
    "ProtocolError",
    "LedColor",
    "LinearAccelerationSample",
    "QuaternionSample",
    "SenswearClient",
    "SenswearDependencyError",
    "SenswearError",
    "TemperatureSample",
]

__version__ = "0.1.1"

