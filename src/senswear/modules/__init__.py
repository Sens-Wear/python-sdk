"""High-level SensWear hardware modules."""

from .battery import BatteryGaugeModule, BatteryGaugeState, BatteryLevel, BatteryModule
from .charger import (
    BatteryLevelStatus,
    ChargeLevel,
    ChargeState,
    ChargerModule,
    ChargerState,
    PowerSourceState,
    PowerStatusModule,
)
from .haptic import HapticFrame, HapticModule, HapticPattern
from .imu import (
    ActivitySample,
    ActivityTransition,
    GestureSample,
    GyroscopeSample,
    ImuActivity,
    ImuGesture,
    ImuModule,
    LinearAccelerationSample,
    QuaternionSample,
)
from .led import LedColor, LedModule
from .ppg import PpgModule, PpgSample
from .temperature import (
    TemperatureMeasurement,
    TemperatureModule,
    TemperatureSample,
    TemperatureType,
)
from .time import (
    CurrentTime,
    LocalTimeInformation,
    ReferenceTimeInformation,
    TimeModule,
)
from .touch import (
    RawTouchSample,
    TouchGesture,
    TouchGestureSample,
    TouchModule,
    TouchState,
)

__all__ = [
    "ActivitySample",
    "ActivityTransition",
    "BatteryGaugeModule",
    "BatteryGaugeState",
    "BatteryLevel",
    "BatteryLevelStatus",
    "BatteryModule",
    "ChargeLevel",
    "ChargeState",
    "ChargerModule",
    "ChargerState",
    "CurrentTime",
    "GestureSample",
    "GyroscopeSample",
    "HapticFrame",
    "HapticModule",
    "HapticPattern",
    "ImuActivity",
    "ImuGesture",
    "ImuModule",
    "LedColor",
    "LedModule",
    "LinearAccelerationSample",
    "LocalTimeInformation",
    "PowerSourceState",
    "PowerStatusModule",
    "PpgModule",
    "PpgSample",
    "QuaternionSample",
    "RawTouchSample",
    "ReferenceTimeInformation",
    "TemperatureMeasurement",
    "TemperatureModule",
    "TemperatureSample",
    "TemperatureType",
    "TimeModule",
    "TouchGesture",
    "TouchGestureSample",
    "TouchModule",
    "TouchState",
]
