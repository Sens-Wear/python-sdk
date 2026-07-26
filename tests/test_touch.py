import pathlib
import struct
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from senswear.modules.touch import (
    RawTouchSample,
    TouchGesture,
    TouchGestureSample,
    TouchState,
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


if __name__ == "__main__":
    unittest.main()
