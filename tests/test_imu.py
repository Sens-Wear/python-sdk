import math
import pathlib
import struct
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from senswar.exceptions import ProtocolError
from senswar.modules.imu import (
    LINEAR_ACCELERATION_LENGTH,
    QUATERNION_LENGTH,
    ImuModule,
    LinearAccelerationSample,
    QuaternionSample,
)
from senswar.uuids import IMU_LINEAR_ACCELERATION_UUID, IMU_QUATERNION_UUID


class QuaternionSampleTests(unittest.TestCase):
    def test_from_bytes_decodes_firmware_layout(self) -> None:
        payload = struct.pack("<hhhhH", 8192, -8192, 0, 16384, 1024)

        sample = QuaternionSample.from_bytes(payload)

        self.assertEqual(sample.x, 8192)
        self.assertEqual(sample.y, -8192)
        self.assertEqual(sample.z, 0)
        self.assertEqual(sample.w, 16384)
        self.assertEqual(sample.accuracy, 1024)
        self.assertEqual(sample.to_tuple(), (0.5, -0.5, 0.0, 1.0))
        self.assertEqual(sample.to_tuple(normalized=False), (8192, -8192, 0, 16384))
        self.assertAlmostEqual(sample.accuracy_radians, 0.0625)
        self.assertAlmostEqual(sample.accuracy_degrees, 0.0625 * 180.0 / math.pi)

    def test_from_bytes_rejects_wrong_length(self) -> None:
        with self.assertRaises(ProtocolError):
            QuaternionSample.from_bytes(bytes(QUATERNION_LENGTH - 1))


class LinearAccelerationSampleTests(unittest.TestCase):
    def test_from_bytes_decodes_firmware_layout(self) -> None:
        payload = struct.pack("<hhh", 4096, -2048, 1024)

        sample = LinearAccelerationSample.from_bytes(payload)

        self.assertEqual(sample.x, 4096)
        self.assertEqual(sample.y, -2048)
        self.assertEqual(sample.z, 1024)
        self.assertEqual(sample.to_tuple(), (1.0, -0.5, 0.25))
        self.assertEqual(sample.to_tuple(scaled=False), (4096, -2048, 1024))

    def test_from_bytes_rejects_wrong_length(self) -> None:
        with self.assertRaises(ProtocolError):
            LinearAccelerationSample.from_bytes(bytes(LINEAR_ACCELERATION_LENGTH - 1))


class FakeGattClient:
    def __init__(self) -> None:
        self.started: dict[str, object] = {}
        self.stopped: list[str] = []

    async def start_notify(self, characteristic_uuid: str, callback: object) -> None:
        self.started[characteristic_uuid] = callback

    async def stop_notify(self, characteristic_uuid: str) -> None:
        self.stopped.append(characteristic_uuid)


class ImuModuleTests(unittest.IsolatedAsyncioTestCase):
    async def test_subscribe_quaternion_decodes_notifications(self) -> None:
        client = FakeGattClient()
        module = ImuModule(client)
        samples: list[QuaternionSample] = []

        await module.subscribe_quaternion(samples.append)
        callback = client.started[IMU_QUATERNION_UUID]
        callback(None, bytearray(struct.pack("<hhhhH", 1, 2, 3, 4, 5)))

        self.assertEqual(samples, [QuaternionSample(1, 2, 3, 4, 5)])

        await module.unsubscribe_quaternion()

        self.assertEqual(client.stopped, [IMU_QUATERNION_UUID])

    async def test_subscribe_linear_acceleration_decodes_notifications(self) -> None:
        client = FakeGattClient()
        module = ImuModule(client)
        samples: list[LinearAccelerationSample] = []

        await module.subscribe_linear_acceleration(samples.append)
        callback = client.started[IMU_LINEAR_ACCELERATION_UUID]
        callback(None, bytearray(struct.pack("<hhh", 10, 20, 30)))

        self.assertEqual(samples, [LinearAccelerationSample(10, 20, 30)])

        await module.unsubscribe_linear_acceleration()

        self.assertEqual(client.stopped, [IMU_LINEAR_ACCELERATION_UUID])


if __name__ == "__main__":
    unittest.main()
