import pathlib
import struct
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from senswear.modules.imu import (
    ActivitySample,
    ActivityTransition,
    GestureSample,
    GyroscopeSample,
    ImuActivity,
    ImuGesture,
    ImuModule,
    LinearAccelerationSample,
    QuaternionSample,
)
from senswear.uuids import (
    IMU_DRAIN_PERIOD_UUID,
    IMU_GYROSCOPE_UUID,
    IMU_PHYSICAL_STREAMS_ENABLE_UUID,
    IMU_QUATERNION_UUID,
)


class FakeGattClient:
    def __init__(self):
        self.payloads = {}
        self.started = {}
        self.stopped = []
        self.writes = []

    async def read_gatt_char(self, uuid):
        return self.payloads[uuid]

    async def write_gatt_char(self, uuid, data, *, response=True):
        self.writes.append((uuid, data, response))

    async def start_notify(self, uuid, callback):
        self.started[uuid] = callback

    async def stop_notify(self, uuid):
        self.stopped.append(uuid)


class ImuPayloadTests(unittest.TestCase):
    def test_all_timestamped_firmware_layouts(self) -> None:
        timestamp = 1_720_000_000_123_456
        quat = QuaternionSample.from_bytes(
            struct.pack("<qhhhhH", timestamp, 8192, -1, 2, 16384, 3)
        )
        self.assertEqual(quat.timestamp_us, timestamp)
        self.assertEqual(quat.to_tuple(), (0.5, -1 / 16384, 2 / 16384, 1.0))

        accel = LinearAccelerationSample.from_bytes(
            struct.pack("<qhhh", timestamp, 4096, 0, -4096)
        )
        self.assertEqual(accel.to_tuple(), (1.0, 0.0, -1.0))
        self.assertEqual(
            GyroscopeSample.from_bytes(
                struct.pack("<qhhh", timestamp, 1, 2, 3)
            ).to_tuple(),
            (1, 2, 3),
        )

        gesture = GestureSample.from_bytes(struct.pack("<qBB", timestamp, 7, 4))
        self.assertEqual(gesture.gesture_type, ImuGesture.FLICK_IN)
        activity = ActivitySample.from_bytes(struct.pack("<qBBB", timestamp, 9, 2, 1))
        self.assertEqual(activity.activity_type, ImuActivity.RUNNING)
        self.assertEqual(activity.transition_type, ActivityTransition.STARTED)


class ImuModuleTests(unittest.IsolatedAsyncioTestCase):
    async def test_reads_subscribes_and_configures(self) -> None:
        client = FakeGattClient()
        timestamp = 123
        client.payloads[IMU_GYROSCOPE_UUID] = struct.pack("<qhhh", timestamp, 4, 5, 6)
        client.payloads[IMU_PHYSICAL_STREAMS_ENABLE_UUID] = b"\x01"
        client.payloads[IMU_DRAIN_PERIOD_UUID] = struct.pack("<I", 100)
        module = ImuModule(client)

        self.assertEqual(
            await module.read_gyroscope(), GyroscopeSample(timestamp, 4, 5, 6)
        )
        self.assertTrue(await module.physical_streams_enabled())
        self.assertEqual(await module.read_drain_period_ms(), 100)

        samples = []
        await module.subscribe_quaternion(samples.append)
        client.started[IMU_QUATERNION_UUID](
            None, bytearray(struct.pack("<qhhhhH", timestamp, 1, 2, 3, 4, 5))
        )
        self.assertEqual(samples, [QuaternionSample(timestamp, 1, 2, 3, 4, 5)])

        await module.set_physical_streams_enabled(False)
        await module.set_drain_period_ms(250)
        self.assertEqual(
            client.writes,
            [
                (IMU_PHYSICAL_STREAMS_ENABLE_UUID, b"\x00", True),
                (IMU_DRAIN_PERIOD_UUID, struct.pack("<I", 250), True),
            ],
        )


if __name__ == "__main__":
    unittest.main()
