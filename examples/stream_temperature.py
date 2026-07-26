import argparse
import asyncio

from senswear import SenswearClient, TemperatureSample


def measurement_interval_minutes(value: str) -> int:
    minutes = int(value)
    if not 0 <= minutes <= 1092:
        raise argparse.ArgumentTypeError("must be between 0 and 1092 minutes")
    return minutes


async def run(
    device: str | None, timeout: float, duration: float, interval_minutes: int | None
) -> None:
    async with SenswearClient(device, timeout=timeout) as client:
        if interval_minutes is not None:
            await client.temperature.set_measurement_interval(interval_minutes * 60)

        def on_temperature(sample: TemperatureSample) -> None:
            print(f"temperature={sample.temperature_c:.3f} C")

        await client.temperature.subscribe(on_temperature)

        try:
            await asyncio.sleep(duration)
        finally:
            await client.temperature.unsubscribe()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stream SensWear temperature notifications over BLE."
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
    parser.add_argument(
        "--duration", type=float, default=70.0, help="Stream duration in seconds."
    )
    parser.add_argument(
        "--interval-minutes",
        type=measurement_interval_minutes,
        metavar="MINUTES",
        help="Optional measurement interval in whole minutes (0 disables).",
    )
    args = parser.parse_args()
    asyncio.run(
        run(args.device, args.timeout, args.duration, args.interval_minutes)
    )


if __name__ == "__main__":
    main()
