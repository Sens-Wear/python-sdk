from __future__ import annotations

import struct
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum

from ..exceptions import ProtocolError
from ..uuids import (
    TEMPERATURE_MEASUREMENT_INTERVAL_UUID,
    TEMPERATURE_MEASUREMENT_UUID,
    TEMPERATURE_TYPE_UUID,
)
from ._common import (
    DecodedCallback,
    GattClient,
    NotificationHandler,
    notification_handler,
    require_write_response,
    unpack_exact,
)

TEMPERATURE_MEASUREMENT_FORMAT = "<BIHBBBBBB"
TEMPERATURE_MEASUREMENT_LENGTH = struct.calcsize(TEMPERATURE_MEASUREMENT_FORMAT)
TEMPERATURE_FLAG_FAHRENHEIT = 1 << 0
TEMPERATURE_FLAG_TIMESTAMP_PRESENT = 1 << 1
TEMPERATURE_FLAG_TYPE_PRESENT = 1 << 2
TEMPERATURE_INTERVAL_RESOLUTION_SECONDS = 60
TEMPERATURE_INTERVAL_MAX_SECONDS = (
    0xFFFF // TEMPERATURE_INTERVAL_RESOLUTION_SECONDS
) * TEMPERATURE_INTERVAL_RESOLUTION_SECONDS


class TemperatureType(IntEnum):
    ARMPIT = 1
    BODY = 2
    EAR = 3
    FINGER = 4
    GASTROINTESTINAL_TRACT = 5
    MOUTH = 6
    RECTUM = 7
    TOE = 8
    TYMPANUM = 9


@dataclass(frozen=True)
class TemperatureMeasurement:
    """Bluetooth Health Thermometer measurement emitted by the firmware."""

    temperature_c: float
    timestamp: datetime | None
    temperature_type: TemperatureType | int | None
    flags: int

    @classmethod
    def from_bytes(
        cls, payload: bytes | bytearray | memoryview
    ) -> "TemperatureMeasurement":
        data = bytes(payload)
        if len(data) < 5:
            raise ProtocolError(
                "Temperature measurement payload must be at least 5 bytes."
            )
        flags = data[0]
        offset = 5
        raw = struct.unpack_from("<I", data, 1)[0]
        value = _decode_ieee11073_float(raw)
        if flags & TEMPERATURE_FLAG_FAHRENHEIT:
            value = (value - 32.0) * 5.0 / 9.0

        timestamp = None
        if flags & TEMPERATURE_FLAG_TIMESTAMP_PRESENT:
            if len(data) < offset + 7:
                raise ProtocolError("Temperature timestamp is truncated.")
            year, month, day, hour, minute, second = struct.unpack_from(
                "<HBBBBB", data, offset
            )
            offset += 7
            try:
                timestamp = datetime(
                    year, month, day, hour, minute, second, tzinfo=timezone.utc
                )
            except ValueError as exc:
                raise ProtocolError(f"Invalid temperature timestamp: {exc}.") from exc

        temperature_type: TemperatureType | int | None = None
        if flags & TEMPERATURE_FLAG_TYPE_PRESENT:
            if len(data) < offset + 1:
                raise ProtocolError("Temperature type is missing.")
            raw_type = data[offset]
            offset += 1
            try:
                temperature_type = TemperatureType(raw_type)
            except ValueError:
                temperature_type = raw_type

        if len(data) != offset:
            raise ProtocolError(
                f"Temperature measurement has {len(data) - offset} unexpected trailing bytes."
            )
        return cls(value, timestamp, temperature_type, flags)

    @property
    def temperature_f(self) -> float:
        return self.temperature_c * 9.0 / 5.0 + 32.0


TemperatureSample = TemperatureMeasurement
TemperatureCallback = DecodedCallback[TemperatureMeasurement]


class TemperatureModule:
    """Bluetooth SIG Health Thermometer Service accessors."""

    measurement_uuid = TEMPERATURE_MEASUREMENT_UUID

    def __init__(self, client: GattClient) -> None:
        self._client = client
        self._notify_handler: NotificationHandler | None = None
        self._interval_handler: NotificationHandler | None = None

    async def read_temperature_type(self) -> TemperatureType | int:
        (raw_type,) = unpack_exact(
            await self._client.read_gatt_char(TEMPERATURE_TYPE_UUID),
            "<B",
            "Temperature type",
        )
        try:
            return TemperatureType(raw_type)
        except ValueError:
            return int(raw_type)

    async def read_measurement_interval(self) -> int:
        """Read the applied measurement interval in seconds."""

        return _decode_measurement_interval(
            await self._client.read_gatt_char(TEMPERATURE_MEASUREMENT_INTERVAL_UUID)
        )

    async def set_measurement_interval(
        self, interval_seconds: int, *, response: bool = True
    ) -> None:
        """Set the interval using the firmware's whole-minute resolution."""

        require_write_response(response)
        if (
            not isinstance(interval_seconds, int)
            or isinstance(interval_seconds, bool)
            or not 0 <= interval_seconds <= TEMPERATURE_INTERVAL_MAX_SECONDS
        ):
            raise ValueError(
                "interval_seconds must be an integer between 0 and 65520."
            )
        if interval_seconds % TEMPERATURE_INTERVAL_RESOLUTION_SECONDS != 0:
            raise ValueError(
                "interval_seconds must be 0 or a whole-minute multiple of 60."
            )
        await self._client.write_gatt_char(
            TEMPERATURE_MEASUREMENT_INTERVAL_UUID,
            struct.pack("<H", interval_seconds),
            response=response,
        )

    async def subscribe(self, callback: TemperatureCallback) -> None:
        """Subscribe to indications from the Temperature Measurement characteristic."""

        if self._notify_handler is not None:
            await self.unsubscribe()
        self._notify_handler = notification_handler(
            TemperatureMeasurement.from_bytes, callback
        )
        await self._client.start_notify(self.measurement_uuid, self._notify_handler)

    async def unsubscribe(self) -> None:
        if self._notify_handler is None:
            return
        await self._client.stop_notify(self.measurement_uuid)
        self._notify_handler = None

    async def subscribe_measurement_interval(
        self, callback: DecodedCallback[int]
    ) -> None:
        """Subscribe to applied interval changes, in seconds (zero disables)."""

        await self.unsubscribe_measurement_interval()
        handler = notification_handler(_decode_measurement_interval, callback)
        await self._client.start_notify(TEMPERATURE_MEASUREMENT_INTERVAL_UUID, handler)
        self._interval_handler = handler

    async def unsubscribe_measurement_interval(self) -> None:
        """Stop interval indications without changing measurement indications."""

        if self._interval_handler is None:
            return
        await self._client.stop_notify(TEMPERATURE_MEASUREMENT_INTERVAL_UUID)
        self._interval_handler = None

    async def unsubscribe_all(self) -> None:
        """Stop both temperature measurement and interval indications."""

        await self.unsubscribe()
        await self.unsubscribe_measurement_interval()


def _decode_measurement_interval(payload: bytes | bytearray | memoryview) -> int:
    (interval,) = unpack_exact(payload, "<H", "Temperature measurement interval")
    return int(interval)


def _decode_ieee11073_float(raw: int) -> float:
    mantissa = raw & 0xFFFFFF
    exponent = (raw >> 24) & 0xFF
    if mantissa in {0x007FFFFE, 0x00800002, 0x007FFFFF, 0x00800000, 0x00800001}:
        raise ProtocolError(
            f"Unsupported IEEE-11073 special temperature value 0x{raw:08x}."
        )
    if mantissa & 0x800000:
        mantissa -= 1 << 24
    if exponent & 0x80:
        exponent -= 1 << 8
    return float(mantissa * (10**exponent))
