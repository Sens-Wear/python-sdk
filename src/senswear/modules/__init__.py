"""High-level SensWear hardware modules."""

from .battery import BatteryGaugeModule, BatteryGaugeState
from .charger import ChargerModule, ChargerState
from .haptic import HapticFrame, HapticModule, HapticPattern
from .imu import ImuModule, LinearAccelerationSample, QuaternionSample
from .led import LedColor, LedModule
from .temperature import TemperatureModule, TemperatureSample

__all__ = [
    "BatteryGaugeModule",
    "BatteryGaugeState",
    "ChargerModule",
    "ChargerState",
    "HapticFrame",
    "HapticModule",
    "HapticPattern",
    "ImuModule",
    "LedColor",
    "LedModule",
    "LinearAccelerationSample",
    "QuaternionSample",
    "TemperatureModule",
    "TemperatureSample",
]

