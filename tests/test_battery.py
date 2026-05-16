import pathlib
import struct
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from senswar.exceptions import ProtocolError
from senswar.modules.battery import BatteryGaugeState, GAUGE_STATE_LENGTH


class BatteryGaugeStateTests(unittest.TestCase):
    def test_from_bytes_decodes_firmware_layout(self) -> None:
        payload = struct.pack("<hHhhHHHH", 234, 3790, -42, -160, 870, 220, 450, 180)

        state = BatteryGaugeState.from_bytes(payload)

        self.assertEqual(state.temperature_deci_c, 234)
        self.assertEqual(state.voltage_mv, 3790)
        self.assertEqual(state.average_current_ma, -42)
        self.assertEqual(state.average_power_mw, -160)
        self.assertEqual(state.state_of_charge_deci_percent, 870)
        self.assertEqual(state.nominal_available_capacity_mah, 220)
        self.assertEqual(state.full_battery_capacity_mah, 450)
        self.assertEqual(state.remaining_capacity_mah, 180)
        self.assertEqual(state.temperature_c, 23.4)
        self.assertEqual(state.state_of_charge_percent, 87.0)

    def test_from_bytes_rejects_wrong_length(self) -> None:
        with self.assertRaises(ProtocolError):
            BatteryGaugeState.from_bytes(bytes(GAUGE_STATE_LENGTH - 1))

    def test_zero_state_detects_firmware_fallback(self) -> None:
        state = BatteryGaugeState.from_bytes(bytes(GAUGE_STATE_LENGTH))

        self.assertTrue(state.is_zero_state)


if __name__ == "__main__":
    unittest.main()
