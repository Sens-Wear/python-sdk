import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from senswear import SenswearClient


class ClientSurfaceTests(unittest.TestCase):
    def test_exposes_every_current_firmware_service(self) -> None:
        client = SenswearClient()
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
