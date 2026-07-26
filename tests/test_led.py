import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from senswear.modules.led import LedColor, LedModule
from senswear.uuids import LED_COLOR_UUID


class FakeGattClient:
    def __init__(self):
        self.writes = []

    async def read_gatt_char(self, uuid):
        self.read_uuid = uuid
        return bytes([0x33, 0x22, 0x11, 0x00])

    async def write_gatt_char(self, uuid, data, *, response=True):
        self.writes.append((uuid, data, response))


class LedTests(unittest.IsolatedAsyncioTestCase):
    def test_wire_layout_is_little_endian_00rrggbb(self) -> None:
        color = LedColor(0x11, 0x22, 0x33)
        self.assertEqual(color.to_int(), 0x112233)
        self.assertEqual(color.to_bytes(), bytes([0x33, 0x22, 0x11, 0]))
        self.assertEqual(LedColor.from_bytes(color.to_bytes()), color)

    async def test_module_reads_and_writes_correct_layout(self) -> None:
        client = FakeGattClient()
        module = LedModule(client)
        self.assertEqual(await module.read(), LedColor(0x11, 0x22, 0x33))
        await module.set_rgb(1, 2, 3, response=False)
        self.assertEqual(client.writes, [(LED_COLOR_UUID, bytes([3, 2, 1, 0]), False)])


if __name__ == "__main__":
    unittest.main()
