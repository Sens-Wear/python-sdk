import argparse
import asyncio

from senswar import SenswarClient, TemperatureSample


async def run(device: str | None, timeout: float, duration: float, sampling_rate_hz: int | None) -> None:
    async with SenswarClient(device, timeout=timeout) as client:
        if sampling_rate_hz is not None:
            await client.temperature.set_sampling_rate_hz(sampling_rate_hz)

        def on_temperature(sample: TemperatureSample) -> None:
            print(f"temperature={sample.temperature_c:.3f} C")

        await client.temperature.subscribe(on_temperature)

        try:
            await asyncio.sleep(duration)
        finally:
            await client.temperature.unsubscribe()


def main() -> None:
    parser = argparse.ArgumentParser(description="Stream Senswar temperature notifications over BLE.")
    parser.add_argument(
        "device",
        nargs="?",
        help="Optional BLE address/platform identifier or exact advertised name.",
    )
    parser.add_argument("--timeout", type=float, default=10.0, help="BLE scan/connect timeout in seconds.")
    parser.add_argument("--duration", type=float, default=10.0, help="Stream duration in seconds.")
    parser.add_argument("--sampling-rate", type=int, help="Optional temperature sampling rate in Hz.")
    args = parser.parse_args()
    asyncio.run(run(args.device, args.timeout, args.duration, args.sampling_rate))


if __name__ == "__main__":
    main()
