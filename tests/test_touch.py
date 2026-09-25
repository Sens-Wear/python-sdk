import pathlib
import struct
import sys
import unittest
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from senswear.modules.touch import (
    TOUCH_ELECTRODE_COUNT,
    TOUCH_ELECTRODE_PITCH,
    TOUCH_ELECTRODE_PITCH_MM,
    TOUCH_LENGTH_MM,
    TOUCH_POSITION_MAX,
    RawTouchSample,
    TouchGesture,
    TouchGestureSample,
    TouchModule,
    TouchState,
)
from senswear.exceptions import ProtocolError
from senswear.uuids import (
    TOUCH_GESTURE_UUID,
    TOUCH_RAW_DATA_UUID,
    TOUCH_SAMPLING_ENABLE_UUID,
    TOUCH_STATE_UUID,
)


class TouchTests(unittest.TestCase):
    def test_decodes_packed_touch_state(self) -> None:
        sample = TouchState.from_bytes(struct.pack("<q?HH", 123456, True, 400, 800))
        self.assertEqual(sample, TouchState(123456, True, 400, 800))

    def test_decodes_gesture(self) -> None:
        sample = TouchGestureSample.from_bytes(struct.pack("<qBB", 99, 3, 0xAA))
        self.assertEqual(sample.gesture_type, TouchGesture.DOUBLE_CLICK)
        self.assertEqual(sample.gesture_state, 0xAA)

    def test_decodes_aligned_raw_device_manager_struct(self) -> None:
        payload = struct.pack("<q?xHHB", 42, True, 10, 20, 0x7F) + b"\x00"
        self.assertEqual(
            RawTouchSample.from_bytes(payload), RawTouchSample(42, True, 10, 20, 0x7F)
        )

    def test_slider_geometry_at_every_pad_and_between_pads(self) -> None:
        self.assertEqual(TOUCH_ELECTRODE_COUNT, 15)
        self.assertEqual(TOUCH_ELECTRODE_PITCH, 64)
        self.assertEqual(TOUCH_ELECTRODE_PITCH_MM, 3)
        self.assertEqual(TOUCH_POSITION_MAX, 896)
        self.assertEqual(TOUCH_LENGTH_MM, 42)
        for pad in range(15):
            for sample in (
                TouchState(42, True, pad * 64, 0),
                RawTouchSample(42, True, pad * 64, 0, 0),
            ):
                with self.subTest(pad=pad, sample=type(sample)):
                    self.assertEqual(sample.position_normalized, pad / 14)
                    self.assertEqual(sample.position_mm, pad * 3)
        self.assertEqual(TouchState(0, True, 32, 0).position_mm, 1.5)

    def test_release_and_legacy_coordinates_have_no_slider_position(self) -> None:
        for touched, x, y in (
            (False, 0, 0), (False, 448, 0), (True, 897, 0),
            (True, 4095, 4095), (True, 448, 1),
        ):
            payload = struct.pack("<q?HH", 42, touched, x, y)
            sample = TouchState.from_bytes(payload)
            self.assertEqual((sample.x, sample.y), (x, y))
            self.assertIsNone(sample.position_normalized)
            self.assertIsNone(sample.position_mm)

    def test_raw_contact_uses_host_flag_not_native_tch_bit(self) -> None:
        for touched, native_state in ((True, 0), (False, 1)):
            # Padding bytes 9 and 15 are explicitly ignored, even if nonzero.
            payload = bytearray(struct.pack("<q?xHHB", 42, touched, 0, 0, native_state))
            payload[9] = 0xA5
            payload.append(0x5A)
            sample = RawTouchSample.from_bytes(payload)
            self.assertEqual(sample.touched, touched)
            self.assertEqual(sample.touch_state, native_state)
            self.assertEqual(sample.position_mm, 0.0 if touched else None)

    def test_bytes_like_inputs_preserve_exact_signed_timestamps(self) -> None:
        for timestamp in (-1, 9_007_199_254_740_993):
            for decoder, payload in (
                (TouchState, struct.pack("<q?HH", timestamp, True, 896, 0)),
                (TouchGestureSample, struct.pack("<qBB", timestamp, 6, 0x41)),
                (RawTouchSample, struct.pack("<q?xHHBx", timestamp, True, 896, 0, 0)),
            ):
                for container in (bytes, bytearray, memoryview):
                    self.assertEqual(
                        decoder.from_bytes(container(payload)).timestamp_us, timestamp
                    )

    def test_timestamp_convenience_for_all_touch_streams(self) -> None:
        for sample in (
            TouchState(1_000_000, True, 0, 0),
            TouchGestureSample(1_000_000, 6, 0x41),
            RawTouchSample(1_000_000, True, 0, 0, 0),
        ):
            self.assertEqual(sample.timestamp, datetime(1970, 1, 1, 0, 0, 1, tzinfo=timezone.utc))

    def test_host_gesture_codes_and_unknown_values(self) -> None:
        for normalized, encoded in ((1, 0x10), (2, 0x11), (3, 0x20),
                                    (6, 0x41), (7, 0x42), (10, 0x61), (11, 0x62)):
            sample = TouchGestureSample.from_bytes(struct.pack("<qBB", 42, normalized, encoded))
            self.assertEqual(sample.gesture_type, TouchGesture(normalized))
            self.assertEqual(sample.gesture_state, encoded)
        unknown = TouchGestureSample.from_bytes(struct.pack("<qBB", 42, 0xFE, 0xFF))
        self.assertEqual(unknown.gesture_type, 0xFE)
        self.assertEqual(unknown.gesture_state, 0xFF)

    def test_rejects_truncated_or_extra_bytes(self) -> None:
        for decoder, length in ((TouchState, 13), (TouchGestureSample, 10), (RawTouchSample, 16)):
            for bad_length in (0, length - 1, length + 1):
                with self.subTest(decoder=decoder, length=bad_length):
                    with self.assertRaises(ProtocolError):
                        decoder.from_bytes(bytes(bad_length))


class FakeGattClient:
    def __init__(self):
        self.payloads = {
            TOUCH_STATE_UUID: struct.pack("<q?HH", 42, True, 448, 0),
            TOUCH_GESTURE_UUID: struct.pack("<qBB", 42, 6, 0x41),
            TOUCH_RAW_DATA_UUID: struct.pack("<q?xHHBx", 42, True, 448, 0, 0),
            TOUCH_SAMPLING_ENABLE_UUID: b"\x01",
        }
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
        del self.started[uuid]


class TouchModuleTests(unittest.IsolatedAsyncioTestCase):
    async def test_reads_and_notifications_use_same_packets(self) -> None:
        client = FakeGattClient()
        module = TouchModule(client)
        for name, uuid in (("state", TOUCH_STATE_UUID), ("gesture", TOUCH_GESTURE_UUID),
                           ("raw", TOUCH_RAW_DATA_UUID)):
            received = []
            expected = await getattr(module, f"read_{name}")()
            await getattr(module, f"subscribe_{name}")(received.append)
            client.started[uuid](None, bytearray(client.payloads[uuid]))
            self.assertEqual(received, [expected])
        await module.unsubscribe_all()
        self.assertEqual(
            set(client.stopped),
            {TOUCH_STATE_UUID, TOUCH_GESTURE_UUID, TOUCH_RAW_DATA_UUID},
        )
        await module.unsubscribe_all()
        self.assertEqual(len(client.stopped), 3)

    async def test_configuration_and_replacing_a_subscription(self) -> None:
        client = FakeGattClient()
        module = TouchModule(client)
        self.assertTrue(await module.sampling_enabled())
        await module.set_sampling_enabled(False)
        await module.set_sampling_enabled(True)
        self.assertEqual(client.writes, [(TOUCH_SAMPLING_ENABLE_UUID, b"\x00", True),
                                         (TOUCH_SAMPLING_ENABLE_UUID, b"\x01", True)])
        with self.assertRaises(TypeError):
            await module.set_sampling_enabled(1)
        client.payloads[TOUCH_SAMPLING_ENABLE_UUID] = b"\x02"
        with self.assertRaises(ProtocolError):
            await module.sampling_enabled()
        first, second = [], []
        await module.subscribe_state(first.append)
        await module.subscribe_state(second.append)
        client.started[TOUCH_STATE_UUID](None, bytearray(client.payloads[TOUCH_STATE_UUID]))
        self.assertEqual(first, [])
        self.assertEqual(len(second), 1)
        self.assertEqual(client.stopped, [TOUCH_STATE_UUID])


if __name__ == "__main__":
    unittest.main()
