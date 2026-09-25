"""Typed writes obey the current firmware's advertised GATT properties."""

import pathlib
import sys
import unittest
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from senswear import SenswearClient
from senswear.modules.haptic import HapticModule
from senswear.modules.imu import ImuModule
from senswear.modules.led import LedModule
from senswear.modules.ppg import PpgModule
from senswear.modules.temperature import TemperatureModule
from senswear.modules.time import TimeModule
from senswear.modules.touch import TouchModule
from senswear.uuids import LED_COLOR_UUID, TOUCH_SAMPLING_ENABLE_UUID


class FakeGattClient:
    is_connected = True

    def __init__(self):
        self.writes = []

    async def write_gatt_char(self, uuid, data, *, response=True):
        self.writes.append((uuid, data, response))


class WritePropertiesTests(unittest.IsolatedAsyncioTestCase):
    async def test_write_only_endpoints_require_acknowledged_writes(self):
        client = FakeGattClient()
        operations = (
            (TouchModule(client).set_sampling_enabled, (True,)),
            (ImuModule(client).set_physical_streams_enabled, (True,)),
            (ImuModule(client).set_drain_period_ms, (100,)),
            (PpgModule(client).set_sampling_enabled, (True,)),
            (PpgModule(client).set_per_sample_irq_enabled, (True,)),
            (TemperatureModule(client).set_measurement_interval, (60,)),
            (TimeModule(client).set, (datetime(2026, 9, 25, tzinfo=timezone.utc),)),
            (HapticModule(client).play, ([(10, 100)],)),
            (HapticModule(client).vibrate, (10,)),
        )
        for operation, args in operations:
            with self.subTest(operation=operation.__qualname__):
                with self.assertRaises(ValueError):
                    await operation(*args, response=False)
                with self.assertRaises(TypeError):
                    await operation(*args, response=1)
                self.assertEqual(client.writes, [])

    async def test_led_and_low_level_transport_keep_unacknowledged_writes(self):
        client = FakeGattClient()
        await LedModule(client).set("#123456", response=False)
        transport = SenswearClient()
        transport._client = client
        await transport.write_gatt_char(TOUCH_SAMPLING_ENABLE_UUID, b"\x01", response=False)
        self.assertEqual(client.writes, [
            (LED_COLOR_UUID, b"\x56\x34\x12\x00", False),
            (TOUCH_SAMPLING_ENABLE_UUID, b"\x01", False),
        ])
