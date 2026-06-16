import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from senswear.exceptions import ProtocolError
from senswear.modules.led import LED_COLOR_LENGTH, LedColor, LedModule
from senswear.uuids import LED_COLOR_UUID


class LedColorTests(unittest.TestCase):
    def test_from_bytes_decodes_firmware_layout(self) -> None:
        color = LedColor.from_bytes(bytes([0x11, 0x22, 0x33, 0x44]))

        self.assertEqual(color.red, 0x11)
        self.assertEqual(color.green, 0x22)
        self.assertEqual(color.blue, 0x33)
        self.assertEqual(color.white, 0x44)
        self.assertEqual(color.to_int(), 0x44332211)
        self.assertEqual(color.to_bytes(), bytes([0x11, 0x22, 0x33, 0x44]))

    def test_from_hex_accepts_rgb_and_rgbw(self) -> None:
        self.assertEqual(LedColor.from_hex("#102030"), LedColor(0x10, 0x20, 0x30, 0))
        self.assertEqual(LedColor.from_hex("10203040"), LedColor(0x10, 0x20, 0x30, 0x40))

    def test_from_bytes_rejects_wrong_length(self) -> None:
        with self.assertRaises(ProtocolError):
            LedColor.from_bytes(bytes(LED_COLOR_LENGTH - 1))

    def test_channel_values_must_be_bytes(self) -> None:
        with self.assertRaises(ValueError):
            LedColor(256, 0, 0)


class FakeGattClient:
    def __init__(self) -> None:
        self.read_payload = bytes([1, 2, 3, 4])
        self.writes: list[tuple[str, bytes, bool]] = []

    async def read_gatt_char(self, characteristic_uuid: str) -> bytes:
        self.last_read_uuid = characteristic_uuid
        return self.read_payload

    async def write_gatt_char(self, characteristic_uuid: str, data: bytes, *, response: bool = True) -> None:
        self.writes.append((characteristic_uuid, data, response))


class LedModuleTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_returns_led_color(self) -> None:
        client = FakeGattClient()
        module = LedModule(client)

        color = await module.read()

        self.assertEqual(color, LedColor(1, 2, 3, 4))
        self.assertEqual(client.last_read_uuid, LED_COLOR_UUID)

    async def test_set_writes_color_payload(self) -> None:
        client = FakeGattClient()
        module = LedModule(client)

        await module.set_rgb(0x10, 0x20, 0x30, white=0x40, response=False)

        self.assertEqual(client.writes, [(LED_COLOR_UUID, bytes([0x10, 0x20, 0x30, 0x40]), False)])

    async def test_off_writes_zero_color(self) -> None:
        client = FakeGattClient()
        module = LedModule(client)

        await module.off()

        self.assertEqual(client.writes, [(LED_COLOR_UUID, bytes([0, 0, 0, 0]), True)])


if __name__ == "__main__":
    unittest.main()

