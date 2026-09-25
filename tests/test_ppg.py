import pathlib
import struct
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from senswear.modules.ppg import PpgModule, PpgSample
from senswear.uuids import (
    PPG_PER_SAMPLE_IRQ_UUID,
    PPG_RED_UUID,
    PPG_SAMPLING_ENABLE_UUID,
)


class FakeGattClient:
    def __init__(self):
        self.payloads = {
            PPG_RED_UUID: struct.pack("<QI", 1_720_000_000_123, 0x3FFFF),
            PPG_SAMPLING_ENABLE_UUID: b"\x01",
        }
        self.writes = []
        self.started = {}

    async def read_gatt_char(self, uuid):
        return self.payloads[uuid]

    async def write_gatt_char(self, uuid, data, *, response=True):
        self.writes.append((uuid, data, response))

    async def start_notify(self, uuid, callback):
        self.started[uuid] = callback

    async def stop_notify(self, uuid):
        pass


class PpgTests(unittest.IsolatedAsyncioTestCase):
    async def test_reads_and_configures_firmware_ppg(self) -> None:
        client = FakeGattClient()
        module = PpgModule(client)
        self.assertEqual(await module.read_red(), PpgSample(1_720_000_000_123, 0x3FFFF))
        self.assertTrue(await module.sampling_enabled())
        await module.set_sampling_enabled(False)
        await module.set_per_sample_irq_enabled(True)
        self.assertEqual(
            client.writes,
            [
                (PPG_SAMPLING_ENABLE_UUID, b"\x00", True),
                (PPG_PER_SAMPLE_IRQ_UUID, b"\x01", True),
            ],
        )

    async def test_notification_decodes_timestamp_value_pair(self) -> None:
        client = FakeGattClient()
        samples = []
        module = PpgModule(client)
        await module.subscribe_red(samples.append)
        client.started[PPG_RED_UUID](None, bytearray(struct.pack("<QI", 123, 456)))
        self.assertEqual(samples, [PpgSample(123, 456)])


if __name__ == "__main__":
    unittest.main()
