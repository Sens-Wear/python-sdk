from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from ..uuids import (
    PPG_GREEN_UUID,
    PPG_IR_UUID,
    PPG_PER_SAMPLE_IRQ_UUID,
    PPG_RED_UUID,
    PPG_SAMPLING_ENABLE_UUID,
)
from ._common import (
    DecodedCallback,
    GattClient,
    NotificationHandler,
    decode_bool,
    encode_bool,
    notification_handler,
    unpack_exact,
)

PPG_SAMPLE_FORMAT = "<QI"
PPG_SAMPLE_LENGTH = 12
PpgCallback = DecodedCallback["PpgSample"]


@dataclass(frozen=True)
class PpgSample:
    """One raw MAX30101 channel sample."""

    timestamp_ms: int
    value: int

    @classmethod
    def from_bytes(cls, payload: bytes | bytearray | memoryview) -> "PpgSample":
        timestamp_ms, value = unpack_exact(payload, PPG_SAMPLE_FORMAT, "PPG sample")
        return cls(int(timestamp_ms), int(value))

    @property
    def timestamp(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp_ms / 1000, tz=timezone.utc)


class PpgModule:
    """Read, configure, and subscribe to the three PPG channels."""

    _channels = {"red": PPG_RED_UUID, "ir": PPG_IR_UUID, "green": PPG_GREEN_UUID}

    def __init__(self, client: GattClient) -> None:
        self._client = client
        self._handlers: dict[str, NotificationHandler] = {}

    async def _read(self, channel: str) -> PpgSample:
        return PpgSample.from_bytes(
            await self._client.read_gatt_char(self._channels[channel])
        )

    async def read_red(self) -> PpgSample:
        return await self._read("red")

    async def read_ir(self) -> PpgSample:
        return await self._read("ir")

    async def read_green(self) -> PpgSample:
        return await self._read("green")

    async def _subscribe(self, channel: str, callback: PpgCallback) -> None:
        await self._unsubscribe(channel)
        handler = notification_handler(PpgSample.from_bytes, callback)
        self._handlers[channel] = handler
        await self._client.start_notify(self._channels[channel], handler)

    async def _unsubscribe(self, channel: str) -> None:
        if channel not in self._handlers:
            return
        await self._client.stop_notify(self._channels[channel])
        del self._handlers[channel]

    async def subscribe_red(self, callback: PpgCallback) -> None:
        await self._subscribe("red", callback)

    async def subscribe_ir(self, callback: PpgCallback) -> None:
        await self._subscribe("ir", callback)

    async def subscribe_green(self, callback: PpgCallback) -> None:
        await self._subscribe("green", callback)

    async def unsubscribe_red(self) -> None:
        await self._unsubscribe("red")

    async def unsubscribe_ir(self) -> None:
        await self._unsubscribe("ir")

    async def unsubscribe_green(self) -> None:
        await self._unsubscribe("green")

    async def unsubscribe_all(self) -> None:
        for channel in tuple(self._handlers):
            await self._unsubscribe(channel)

    async def sampling_enabled(self) -> bool:
        return decode_bool(
            await self._client.read_gatt_char(PPG_SAMPLING_ENABLE_UUID),
            "PPG sampling enable",
        )

    async def set_sampling_enabled(
        self, enabled: bool, *, response: bool = True
    ) -> None:
        await self._client.write_gatt_char(
            PPG_SAMPLING_ENABLE_UUID,
            encode_bool(enabled, "enabled"),
            response=response,
        )

    async def per_sample_irq_enabled(self) -> bool:
        return decode_bool(
            await self._client.read_gatt_char(PPG_PER_SAMPLE_IRQ_UUID),
            "PPG per-sample IRQ",
        )

    async def set_per_sample_irq_enabled(
        self, enabled: bool, *, response: bool = True
    ) -> None:
        await self._client.write_gatt_char(
            PPG_PER_SAMPLE_IRQ_UUID,
            encode_bool(enabled, "enabled"),
            response=response,
        )
