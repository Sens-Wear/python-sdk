import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from senswear import SenswearClient
import senswear


class ClientSurfaceTests(unittest.TestCase):
    def test_exports_current_slider_geometry(self) -> None:
        for name, value in (
            ("TOUCH_ELECTRODE_COUNT", 15),
            ("TOUCH_ELECTRODE_PITCH", 64),
            ("TOUCH_ELECTRODE_PITCH_MM", 3),
            ("TOUCH_POSITION_MAX", 896),
            ("TOUCH_LENGTH_MM", 42),
        ):
            self.assertEqual(getattr(senswear, name), value)
            self.assertIn(name, senswear.__all__)

    def test_exposes_every_current_firmware_service(self) -> None:
        client = SenswearClient()
        self.assertEqual(client.name_prefixes, ("Sens Wear", "SensWear"))
        for name in (
            "battery",
            "power",
            "charger",
            "haptic",
            "imu",
            "led",
            "ppg",
            "temperature",
            "time",
            "touch",
        ):
            self.assertTrue(hasattr(client, name), name)
        self.assertIs(client.charger, client.power)


if __name__ == "__main__":
    unittest.main()
