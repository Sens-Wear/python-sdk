"""Print the connected firmware revision and compiled daughter-board support."""

import asyncio

from senswear import DeviceFeature, SenswearClient


async def main() -> None:
    async with SenswearClient() as device:
        info = await device.device_info.read()
        print("Firmware:", info.firmware_version)
        print("Firmware shields:", ", ".join(board.name for board in info.capabilities.shields) or "None")
        print("PPG supported:", info.capabilities.has_feature(DeviceFeature.PPG))


if __name__ == "__main__":
    asyncio.run(main())
