import pathlib
import struct
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from senswear.modules.charger import (
    BatteryLevelStatus,
    ChargeLevel,
    ChargeState,
    PowerSourceState,
)


class BatteryLevelStatusTests(unittest.TestCase):
    def test_decodes_firmware_power_state_bits(self) -> None:
        power_state = 1 | (1 << 1) | (1 << 5) | (2 << 7) | (4 << 12)
        status = BatteryLevelStatus.from_bytes(struct.pack("<BHB", 2, power_state, 18))
        self.assertTrue(status.battery_present)
        self.assertEqual(status.wired_power, PowerSourceState.CONNECTED)
        self.assertEqual(status.charge_state, ChargeState.CHARGING)
        self.assertEqual(status.charge_level, ChargeLevel.LOW)
        self.assertEqual(status.battery_level, 18)
        self.assertTrue(status.power_good)
        self.assertTrue(status.charging)
        self.assertTrue(status.has_fault)

    def test_charged_maps_inactive_discharge(self) -> None:
        status = BatteryLevelStatus(2, 3 << 5, 100)
        self.assertTrue(status.charged)


if __name__ == "__main__":
    unittest.main()
