import pathlib
import struct
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from senswear.exceptions import ProtocolError
from senswear.modules.temperature import TEMPERATURE_SAMPLE_LENGTH, TemperatureModule, TemperatureSample
from senswear.uuids import (
    TEMPERATURE_SAMPLE_UUID,
    TEMPERATURE_SAMPLING_RATE_UUID,
    TEMPERATURE_TRANSFER_INTERVAL_UUID,
)


class TemperatureSampleTests(unittest.TestCase):
    def test_from_bytes_decodes_firmware_layout(self) -> None:
        sample = TemperatureSample.from_bytes(struct.pack("<i", 36_625))

        self.assertEqual(sample.temperature_mdeg_c, 36_625)
        self.assertEqual(sample.temperature_c, 36.625)
        self.assertAlmostEqual(sample.temperature_f, 97.925)

    def test_from_bytes_decodes_negative_temperature(self) -> None:
        sample = TemperatureSample.from_bytes(struct.pack("<i", -1250))

        self.assertEqual(sample.temperature_c, -1.25)

    def test_from_bytes_rejects_wrong_length(self) -> None:
        with self.assertRaises(ProtocolError):
            TemperatureSample.from_bytes(bytes(TEMPERATURE_SAMPLE_LENGTH - 1))


class FakeGattClient:
    def __init__(self) -> None:
        self.read_payload = struct.pack("<i", 25_000)
        self.writes: list[tuple[str, bytes, bool]] = []
        self.started: dict[str, object] = {}
        self.stopped: list[str] = []

    async def read_gatt_char(self, characteristic_uuid: str) -> bytes:
        self.last_read_uuid = characteristic_uuid
        return self.read_payload

    async def write_gatt_char(self, characteristic_uuid: str, data: bytes, *, response: bool = True) -> None:
        self.writes.append((characteristic_uuid, data, response))

    async def start_notify(self, characteristic_uuid: str, callback: object) -> None:
        self.started[characteristic_uuid] = callback

    async def stop_notify(self, characteristic_uuid: str) -> None:
        self.stopped.append(characteristic_uuid)


class TemperatureModuleTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_returns_temperature_sample(self) -> None:
        client = FakeGattClient()
        module = TemperatureModule(client)

        sample = await module.read()

        self.assertEqual(sample.temperature_c, 25.0)
        self.assertEqual(client.last_read_uuid, TEMPERATURE_SAMPLE_UUID)

    async def test_set_sampling_rate_writes_uint16(self) -> None:
        client = FakeGattClient()
        module = TemperatureModule(client)

        await module.set_sampling_rate_hz(10, response=False)

        self.assertEqual(client.writes, [(TEMPERATURE_SAMPLING_RATE_UUID, struct.pack("<H", 10), False)])

    async def test_set_transfer_interval_writes_uint16(self) -> None:
        client = FakeGattClient()
        module = TemperatureModule(client)

        await module.set_transfer_interval(2)

        self.assertEqual(client.writes, [(TEMPERATURE_TRANSFER_INTERVAL_UUID, struct.pack("<H", 2), True)])

    async def test_zero_sampling_rate_is_rejected(self) -> None:
        module = TemperatureModule(FakeGattClient())

        with self.assertRaises(ValueError):
            await module.set_sampling_rate_hz(0)

    async def test_subscribe_decodes_notifications(self) -> None:
        client = FakeGattClient()
        module = TemperatureModule(client)
        samples: list[TemperatureSample] = []

        await module.subscribe(samples.append)
        callback = client.started[TEMPERATURE_SAMPLE_UUID]
        callback(None, bytearray(struct.pack("<i", 30_500)))

        self.assertEqual(samples, [TemperatureSample(30_500)])

        await module.unsubscribe()

        self.assertEqual(client.stopped, [TEMPERATURE_SAMPLE_UUID])


if __name__ == "__main__":
    unittest.main()

