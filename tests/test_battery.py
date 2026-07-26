import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from senswear.exceptions import ProtocolError
from senswear.modules.battery import BatteryLevel, BatteryModule
from senswear.uuids import POWER_BATTERY_LEVEL_UUID


class FakeGattClient:
    def __init__(self) -> None:
        self.started = {}
        self.stopped = []

    async def read_gatt_char(self, uuid):
        self.read_uuid = uuid
        return b"\x57"

    async def start_notify(self, uuid, callback):
        self.started[uuid] = callback

    async def stop_notify(self, uuid):
        self.stopped.append(uuid)


class BatteryTests(unittest.IsolatedAsyncioTestCase):
    def test_decodes_standard_battery_level(self) -> None:
        self.assertEqual(BatteryLevel.from_bytes(b"\x64").percent, 100)
        with self.assertRaises(ProtocolError):
            BatteryLevel.from_bytes(b"\x01\x02")

    async def test_read_and_subscribe(self) -> None:
        client = FakeGattClient()
        module = BatteryModule(client)
        self.assertEqual((await module.read()).percent, 87)
        samples = []
        await module.subscribe(samples.append)
        client.started[POWER_BATTERY_LEVEL_UUID](None, bytearray(b"\x2a"))
        self.assertEqual(samples, [BatteryLevel(42)])
        await module.unsubscribe()
        self.assertEqual(client.stopped, [POWER_BATTERY_LEVEL_UUID])


if __name__ == "__main__":
    unittest.main()
