import argparse
import asyncio

from senswear import PpgSample, SenswearClient

PPG_CHANNELS = ("red", "ir", "green")


async def run(
    device: str | None,
    timeout: float,
    duration: float,
    channels: list[str],
) -> None:
    async with SenswearClient(device, timeout=timeout) as client:
        subscribe = {
            "red": client.ppg.subscribe_red,
            "ir": client.ppg.subscribe_ir,
            "green": client.ppg.subscribe_green,
        }
        sampling_was_enabled = await client.ppg.sampling_enabled()
        sample_counts = {channel: 0 for channel in channels}

        def sample_printer(channel: str):
            def print_sample(sample: PpgSample) -> None:
                sample_counts[channel] += 1
                print(
                    f"{channel} timestamp_ms={sample.timestamp_ms} "
                    f"value={sample.value}",
                    flush=True,
                )

            return print_sample

        try:
            for channel in channels:
                await subscribe[channel](sample_printer(channel))

            # Restart acquisition even when firmware reports it as enabled. This
            # synchronizes the manager state with the sensor after a stale or
            # interrupted acquisition and starts with CCC subscriptions active.
            if sampling_was_enabled:
                await client.ppg.set_sampling_enabled(False)
            await client.ppg.set_sampling_enabled(True)
            print(
                f"Connected: {client.address or 'unknown'}; "
                f"streaming {', '.join(channels)}",
                flush=True,
            )

            await asyncio.sleep(duration)
        finally:
            try:
                await client.ppg.set_sampling_enabled(False)
                if sampling_was_enabled:
                    await client.ppg.set_sampling_enabled(True)
            finally:
                await client.ppg.unsubscribe_all()

        if not any(sample_counts.values()):
            raise RuntimeError(
                "No PPG notifications received. Verify that the device is running "
                "the PPG firmware preset and inspect its MAX30101/PPG logs."
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stream raw SensWear PPG notifications over BLE."
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
        "--duration",
        type=float,
        default=10.0,
        help="Stream duration in seconds.",
    )
    parser.add_argument(
        "--channels",
        nargs="+",
        choices=PPG_CHANNELS,
        default=list(PPG_CHANNELS),
        help="PPG channels to stream (default: red ir green).",
    )
    args = parser.parse_args()
    asyncio.run(run(args.device, args.timeout, args.duration, args.channels))


if __name__ == "__main__":
    main()
