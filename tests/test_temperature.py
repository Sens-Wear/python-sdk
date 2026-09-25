import pathlib
import struct
import sys
import unittest
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from senswear.modules.temperature import (
    TEMPERATURE_INTERVAL_MAX_SECONDS,
    TemperatureMeasurement,
    TemperatureModule,
    TemperatureType,
)
from senswear.exceptions import ProtocolError
from senswear.uuids import (
    TEMPERATURE_MEASUREMENT_INTERVAL_UUID,
    TEMPERATURE_MEASUREMENT_UUID,
)


def firmware_measurement(mdeg_c: int) -> bytes:
    mantissa = int(mdeg_c / 10)
    ieee_float = (0xFE << 24) | (mantissa & 0xFFFFFF)
    return struct.pack("<BIHBBBBBB", 0x06, ieee_float, 2026, 7, 24, 13, 14, 15, 2)


class FakeGattClient:
    def __init__(self):
        self.started = {}
        self.writes = []
        self.stopped = []

    async def read_gatt_char(self, uuid):
        return struct.pack("<H", 60)

    async def write_gatt_char(self, uuid, data, *, response=True):
        self.writes.append((uuid, data, response))

    async def start_notify(self, uuid, callback):
        self.started[uuid] = callback

    async def stop_notify(self, uuid):
        self.stopped.append(uuid)
        del self.started[uuid]


class TemperatureTests(unittest.IsolatedAsyncioTestCase):
    def test_decodes_standard_hts_measurement(self) -> None:
        sample = TemperatureMeasurement.from_bytes(firmware_measurement(36_625))
        self.assertAlmostEqual(sample.temperature_c, 36.62)
        self.assertEqual(
            sample.timestamp, datetime(2026, 7, 24, 13, 14, 15, tzinfo=timezone.utc)
        )
        self.assertEqual(sample.temperature_type, TemperatureType.BODY)

    async def test_interval_uses_firmware_minute_granularity(self) -> None:
        client = FakeGattClient()
        module = TemperatureModule(client)
        self.assertEqual(await module.read_measurement_interval(), 60)
        await module.set_measurement_interval(120)
        self.assertEqual(
            client.writes,
            [(TEMPERATURE_MEASUREMENT_INTERVAL_UUID, b"\x78\x00", True)],
        )

    async def test_interval_accepts_disabled_and_largest_whole_minute(self) -> None:
        client = FakeGattClient()
        module = TemperatureModule(client)
        await module.set_measurement_interval(0)
        await module.set_measurement_interval(TEMPERATURE_INTERVAL_MAX_SECONDS)
        self.assertEqual(client.writes[0][1], b"\x00\x00")
        self.assertEqual(client.writes[1][1], b"\xf0\xff")

    async def test_interval_rejects_values_firmware_cannot_represent(self) -> None:
        module = TemperatureModule(FakeGattClient())
        for value in (True, 1, 59, 61, 65_521, 65_535):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    await module.set_measurement_interval(value)

    async def test_temperature_indications(self) -> None:
        client = FakeGattClient()
        module = TemperatureModule(client)
        samples = []
        await module.subscribe(samples.append)
        client.started[TEMPERATURE_MEASUREMENT_UUID](
            None, bytearray(firmware_measurement(-1250))
        )
        self.assertAlmostEqual(samples[0].temperature_c, -1.25)

    async def test_interval_indications_are_independent_and_replaced(self) -> None:
        client = FakeGattClient()
        module = TemperatureModule(client)
        samples, old_intervals, intervals = [], [], []
        await module.subscribe(samples.append)
        await module.subscribe_measurement_interval(old_intervals.append)
        await module.subscribe_measurement_interval(intervals.append)
        for seconds in (0, 60, 65520, 65535):
            client.started[TEMPERATURE_MEASUREMENT_INTERVAL_UUID](
                None, bytearray(struct.pack("<H", seconds))
            )
        self.assertEqual(intervals, [0, 60, 65520, 65535])
        self.assertEqual(old_intervals, [])
        self.assertEqual(samples, [])
        for payload in (b"", b"\x00", b"\x00\x00\x00"):
            with self.assertRaises(ProtocolError):
                client.started[TEMPERATURE_MEASUREMENT_INTERVAL_UUID](None, payload)
        await module.unsubscribe_measurement_interval()
        self.assertIn(TEMPERATURE_MEASUREMENT_UUID, client.started)
        await module.subscribe_measurement_interval(intervals.append)
        await module.unsubscribe()
        self.assertIn(TEMPERATURE_MEASUREMENT_INTERVAL_UUID, client.started)
        await module.unsubscribe_all()
        self.assertEqual(client.started, {})
        stopped = list(client.stopped)
        await module.unsubscribe_all()
        self.assertEqual(client.stopped, stopped)


if __name__ == "__main__":
    unittest.main()
