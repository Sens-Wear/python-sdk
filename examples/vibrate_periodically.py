import argparse
import asyncio

from senswear import SenswearClient

VIBRATION_DURATION_MS = 300
VIBRATION_INTENSITY = 60
INTERVAL_SECONDS = 5.0
RUN_DURATION_SECONDS = 125.0
PULSE_COUNT = int(RUN_DURATION_SECONDS / INTERVAL_SECONDS)


async def run(device: str | None, timeout: float) -> None:
    async with SenswearClient(device, timeout=timeout) as client:
        print(f"Connected: {client.address or 'unknown'}", flush=True)

        loop = asyncio.get_running_loop()
        started_at = loop.time()

        for pulse_index in range(PULSE_COUNT):
            scheduled_at = started_at + pulse_index * INTERVAL_SECONDS
            await asyncio.sleep(max(0.0, scheduled_at - loop.time()))

            await client.haptic.vibrate(
                duration_ms=VIBRATION_DURATION_MS,
                intensity=VIBRATION_INTENSITY,
            )
            print(f"Vibration {pulse_index + 1}/{PULSE_COUNT}", flush=True)

        # Keep the connection open for the complete 125-second schedule.
        await asyncio.sleep(max(0.0, started_at + RUN_DURATION_SECONDS - loop.time()))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Vibrate a SensWear device for 300 ms at maximum amplitude every "
            "5 seconds for 125 seconds."
        )
    )
    parser.add_argument(
        "device",
        nargs="?",
        help="Optional BLE address/platform identifier or exact advertised name.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="BLE scan/connect timeout in seconds.",
    )
    args = parser.parse_args()
    asyncio.run(run(args.device, args.timeout))


if __name__ == "__main__":
    main()
