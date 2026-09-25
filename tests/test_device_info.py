import pathlib
import struct
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from senswear import (
    DaughterBoard, DeviceCapabilities, DeviceFeature, DeviceInfo, DeviceInfoModule,
    ProtocolError, SenswearClient,
)
from senswear.modules.device_info import parse_firmware_version
from senswear import uuids


class FakeGattClient:
    def __init__(self):
        self.payloads = {
            uuids.FIRMWARE_REVISION_UUID: b"1.2.3-dev.4+abc123",
            uuids.DEVICE_CAPABILITIES_UUID: struct.pack("<BII", 1, 6, 219),
        }
        self.reads = []

    async def read_gatt_char(self, uuid):
        self.reads.append(uuid)
        return self.payloads[uuid]


class DeviceInfoTests(unittest.IsolatedAsyncioTestCase):
    def test_little_endian_and_unknown_bits_preserved(self):
        info = DeviceCapabilities.from_bytes(bytes([1, 6, 0, 0, 128, 219, 0, 0, 128]))
        self.assertEqual(info.protocol_version, 1)
        self.assertEqual(info.shield_mask, 0x80000006)
        self.assertEqual(info.feature_mask, 0x800000DB)
        self.assertEqual(info.shields, (DaughterBoard.PPG, DaughterBoard.TEMPERATURE))
        self.assertTrue(info.has_feature(DeviceFeature.PPG))
        self.assertTrue(info.has_feature(DeviceFeature.TEMPERATURE))
        self.assertFalse(info.has_feature(DeviceFeature.TOUCH))
        self.assertFalse(info.has_shield(DaughterBoard.HAPTIC))
        self.assertEqual(info.unknown_shield_mask, 0x80000000)
        self.assertEqual(info.unknown_feature_mask, 0x80000000)

    def test_base_and_all_shields(self):
        base = DeviceCapabilities.from_bytes(memoryview(struct.pack("<BII", 1, 0, 195)))
        self.assertEqual(base.shields, ())
        self.assertTrue(base.has_feature(DeviceFeature.IMU | DeviceFeature.LED))
        all_caps = DeviceCapabilities.from_bytes(bytearray(struct.pack("<BII", 1, 15, 255)))
        self.assertEqual(len(all_caps.shields), 4)
        for flag in DeviceFeature:
            self.assertTrue(all_caps.has_feature(flag))
        self.assertEqual(all_caps.unknown_feature_mask, 0)

    def test_rejects_malformed_lengths_and_schema(self):
        for length in (0, 1, 8, 10, 12):
            with self.subTest(length=length), self.assertRaises(ProtocolError):
                DeviceCapabilities.from_bytes(bytes(length))
        for schema in (0, 2, 255):
            with self.subTest(schema=schema), self.assertRaises(ProtocolError):
                DeviceCapabilities.from_bytes(struct.pack("<BII", schema, 0, 0))

    def test_revision_decode(self):
        self.assertEqual(parse_firmware_version(b"1.2.3-dev+abc"), "1.2.3-dev+abc")
        self.assertEqual(parse_firmware_version("1.2.3-β".encode()), "1.2.3-β")
        for payload in (b"", b" ", b"\xff", b"1.2.3\x00", b"\xc0\xaf"):
            with self.subTest(payload=payload), self.assertRaises(ProtocolError):
                parse_firmware_version(payload)

    async def test_module_routing_and_public_client(self):
        self.assertIsInstance(SenswearClient().device_info, DeviceInfoModule)
        client = FakeGattClient()
        module = DeviceInfoModule(client)
        info = await module.read()
        self.assertIsInstance(info, DeviceInfo)
        self.assertEqual(info.firmware_version, "1.2.3-dev.4+abc123")
        self.assertTrue(info.capabilities.has_shield(DaughterBoard.PPG))
        self.assertEqual(client.reads, [uuids.FIRMWARE_REVISION_UUID, uuids.DEVICE_CAPABILITIES_UUID])
        self.assertEqual(await module.read_firmware_version(), info.firmware_version)
        self.assertEqual(await module.read_capabilities(), info.capabilities)

    async def test_missing_or_bad_metadata_is_not_fabricated(self):
        client = FakeGattClient()
        client.payloads[uuids.DEVICE_CAPABILITIES_UUID] = b"\x02" + bytes(8)
        with self.assertRaises(ProtocolError):
            await DeviceInfoModule(client).read()
        del client.payloads[uuids.DEVICE_CAPABILITIES_UUID]
        with self.assertRaises(KeyError):
            await DeviceInfoModule(client).read_capabilities()

    def test_registry_covers_every_characteristic(self):
        for name, value in vars(uuids).items():
            if name.endswith("_UUID") and not name.endswith("_SERVICE_UUID"):
                self.assertIn(value, uuids.CHARACTERISTIC_SERVICE_UUIDS, name)
        self.assertEqual(
            uuids.service_uuid_for_characteristic(uuids.FIRMWARE_REVISION_UUID.upper()),
            uuids.DEVICE_INFORMATION_SERVICE_UUID,
        )
        self.assertEqual(
            uuids.service_uuid_for_characteristic(uuids.DEVICE_CAPABILITIES_UUID),
            uuids.DEVICE_CAPABILITIES_SERVICE_UUID,
        )
