import pathlib
import struct
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from senswear.exceptions import ProtocolError
from senswear.modules.haptic import (
    HAPTIC_MAX_FRAMES,
    HAPTIC_PATTERN_VERSION,
    HapticFrame,
    HapticModule,
    HapticPattern,
)
from senswear.uuids import HAPTIC_PATTERN_UUID


class HapticFrameTests(unittest.TestCase):
    def test_frame_encodes_firmware_layout(self) -> None:
        frame = HapticFrame(duration_ms=120, intensity=200)

        self.assertEqual(frame.to_bytes(), struct.pack("<HB", 120, 200))
        self.assertEqual(HapticFrame.from_bytes(frame.to_bytes()), frame)

    def test_frame_rejects_invalid_values(self) -> None:
        with self.assertRaises(ValueError):
            HapticFrame(0, 200)

        with self.assertRaises(ValueError):
            HapticFrame(100, 256)

    def test_frame_rejects_wrong_payload_length(self) -> None:
        with self.assertRaises(ProtocolError):
            HapticFrame.from_bytes(b"\x01\x02")


class HapticPatternTests(unittest.TestCase):
    def test_pattern_encodes_firmware_layout(self) -> None:
        pattern = HapticPattern.from_frames([(100, 255), HapticFrame(50, 0)])

        payload = pattern.to_bytes()

        self.assertEqual(payload, bytes([HAPTIC_PATTERN_VERSION, 0, 2, 0, 100, 0, 255, 50, 0, 0]))
        self.assertEqual(pattern.total_duration_ms, 150)
        self.assertEqual(HapticPattern.from_bytes(payload), pattern)

    def test_pattern_rejects_empty_frames(self) -> None:
        with self.assertRaises(ValueError):
            HapticPattern.from_frames([])

    def test_pattern_rejects_too_many_frames(self) -> None:
        frames = [HapticFrame(1, 1)] * (HAPTIC_MAX_FRAMES + 1)

        with self.assertRaises(ValueError):
            HapticPattern.from_frames(frames)

    def test_pattern_rejects_unsupported_version(self) -> None:
        with self.assertRaises(ProtocolError):
            HapticPattern.from_bytes(bytes([2, 0, 1, 0, 10, 0, 1]))

    def test_pattern_rejects_bad_length(self) -> None:
        with self.assertRaises(ProtocolError):
            HapticPattern.from_bytes(bytes([1, 0, 2, 0, 10, 0, 1]))


class FakeGattClient:
    def __init__(self) -> None:
        self.writes: list[tuple[str, bytes, bool]] = []

    async def write_gatt_char(self, characteristic_uuid: str, data: bytes, *, response: bool = True) -> None:
        self.writes.append((characteristic_uuid, data, response))


class HapticModuleTests(unittest.IsolatedAsyncioTestCase):
    async def test_play_writes_pattern_payload(self) -> None:
        client = FakeGattClient()
        module = HapticModule(client)

        await module.play([(25, 100), (25, 0)], response=False)

        self.assertEqual(
            client.writes,
            [(HAPTIC_PATTERN_UUID, bytes([1, 0, 2, 0, 25, 0, 100, 25, 0, 0]), False)],
        )

    async def test_vibrate_writes_single_frame_pattern(self) -> None:
        client = FakeGattClient()
        module = HapticModule(client)

        await module.vibrate(75, intensity=180)

        self.assertEqual(client.writes, [(HAPTIC_PATTERN_UUID, bytes([1, 0, 1, 0, 75, 0, 180]), True)])


if __name__ == "__main__":
    unittest.main()

