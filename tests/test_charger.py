import pathlib
import struct
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from senswar.exceptions import ProtocolError
from senswar.modules.charger import CHARGER_STATE_LENGTH, ChargerState


class ChargerStateTests(unittest.TestCase):
    def test_from_bytes_decodes_firmware_flags(self) -> None:
        flags = (1 << 5) | (1 << 6) | (1 << 10) | (1 << 17)
        payload = struct.pack("<I", flags)

        state = ChargerState.from_bytes(payload)

        self.assertEqual(state.flags, flags)
        self.assertTrue(state.power_good)
        self.assertTrue(state.charging)
        self.assertTrue(state.thermal_normal)
        self.assertTrue(state.battery_ocp_fault)
        self.assertTrue(state.has_fault)
        self.assertFalse(state.charged)
        self.assertFalse(state.thermal_system_fault)

    def test_from_bytes_rejects_wrong_length(self) -> None:
        with self.assertRaises(ProtocolError):
            ChargerState.from_bytes(bytes(CHARGER_STATE_LENGTH - 1))

    def test_zero_state_detects_firmware_fallback(self) -> None:
        state = ChargerState.from_bytes(bytes(CHARGER_STATE_LENGTH))

        self.assertTrue(state.is_zero_state)
        self.assertFalse(state.has_fault)


if __name__ == "__main__":
    unittest.main()
