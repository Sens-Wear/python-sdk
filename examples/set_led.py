import argparse
import asyncio

from senswear import LedColor, SenswearClient


async def run(device: str | None, color: str, timeout: float, no_response: bool) -> None:
    async with SenswearClient(device, timeout=timeout) as client:
        led_color = LedColor.from_hex(color)
        await client.led.set(led_color, response=not no_response)
        current = await client.led.read()
        print(f"Connected: {client.address or 'unknown'}")
        print(f"LED color: {current.to_hex(include_white=True)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Set the SensWear LED color over BLE.")
    parser.add_argument("color", help="LED color as #RRGGBB or #RRGGBBWW.")
    parser.add_argument(
        "device",
        nargs="?",
        help="Optional BLE address/platform identifier or exact advertised name.",
    )
    parser.add_argument("--timeout", type=float, default=10.0, help="BLE scan/connect timeout in seconds.")
    parser.add_argument(
        "--no-response",
        action="store_true",
        help="Use BLE write-without-response instead of the default acknowledged write.",
    )
    args = parser.parse_args()
    asyncio.run(run(args.device, args.color, args.timeout, args.no_response))


if __name__ == "__main__":
    main()

