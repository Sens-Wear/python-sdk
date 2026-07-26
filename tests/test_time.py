import pathlib
import struct
import sys
import unittest
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from senswear.modules.time import (
    CurrentTime,
    LocalTimeInformation,
    ReferenceTimeInformation,
    TimeModule,
)
from senswear.uuids import CURRENT_TIME_UUID


class FakeGattClient:
    def __init__(self):
        self.writes = []

    async def read_gatt_char(self, uuid):
        return struct.pack("<HBBBBBBBB", 2026, 7, 24, 10, 11, 12, 5, 0, 0)

    async def write_gatt_char(self, uuid, data, *, response=True):
        self.writes.append((uuid, data, response))


class TimeTests(unittest.IsolatedAsyncioTestCase):
    def test_decodes_all_standard_time_payloads(self) -> None:
        payload = struct.pack("<HBBBBBBBB", 2026, 7, 24, 10, 11, 12, 5, 128, 1)
        current = CurrentTime.from_bytes(payload)
        self.assertEqual(
            current.value, datetime(2026, 7, 24, 10, 11, 12, tzinfo=timezone.utc)
        )
        self.assertEqual(current.fractions256, 128)
        self.assertEqual(
            LocalTimeInformation.from_bytes(struct.pack("<bB", -8, 0)),
            LocalTimeInformation(-8, 0),
        )
        self.assertEqual(
            ReferenceTimeInformation.from_bytes(bytes([0, 255, 255, 255])),
            ReferenceTimeInformation(0, 255, 255, 255),
        )

    async def test_set_converts_to_utc_wire_value(self) -> None:
        client = FakeGattClient()
        module = TimeModule(client)
        local = datetime(2026, 7, 24, 13, 0, tzinfo=timezone(timedelta(hours=3)))
        await module.set(local, adjust_reason=1, response=False)
        self.assertEqual(
            client.writes,
            [
                (
                    CURRENT_TIME_UUID,
                    struct.pack("<HBBBBBBBB", 2026, 7, 24, 10, 0, 0, 5, 0, 1),
                    False,
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
