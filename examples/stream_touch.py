import argparse
import asyncio

from senswear import (
    RawTouchSample,
    SenswearClient,
    TouchGesture,
    TouchGestureSample,
    TouchState,
)

TOUCH_STREAMS = ("state", "gesture", "raw")


async def run(
    device: str | None,
    timeout: float,
    duration: float,
    streams: list[str],
) -> None:
    async with SenswearClient(device, timeout=timeout) as client:
        event_counts = {stream: 0 for stream in streams}

        def on_state(sample: TouchState) -> None:
            event_counts["state"] += 1
            if sample.touched:
                message = f"touch timestamp_us={sample.timestamp_us} x={sample.x} y={sample.y}"
            else:
                message = f"release timestamp_us={sample.timestamp_us}"
            print(message, flush=True)

        def on_gesture(sample: TouchGestureSample) -> None:
            event_counts["gesture"] += 1
            gesture = sample.gesture_type
            name = gesture.name if isinstance(gesture, TouchGesture) else str(gesture)
            print(
                f"gesture timestamp_us={sample.timestamp_us} type={name} "
                f"raw_state=0x{sample.gesture_state:02x}",
                flush=True,
            )

        def on_raw(sample: RawTouchSample) -> None:
            event_counts["raw"] += 1
            print(
                f"raw timestamp_us={sample.timestamp_us} touched={sample.touched} "
                f"x={sample.x} y={sample.y} state=0x{sample.touch_state:02x}",
                flush=True,
            )

        subscribe = {
            "state": lambda: client.touch.subscribe_state(on_state),
            "gesture": lambda: client.touch.subscribe_gesture(on_gesture),
            "raw": lambda: client.touch.subscribe_raw(on_raw),
        }
        sampling_was_enabled = await client.touch.sampling_enabled()
        sampling_enabled_by_example = False

        try:
            for stream in streams:
                await subscribe[stream]()

            if not sampling_was_enabled:
                await client.touch.set_sampling_enabled(True)
                sampling_enabled_by_example = True

            print(
                f"Connected: {client.address or 'unknown'}; "
                f"streaming {', '.join(streams)}",
                flush=True,
            )
            await asyncio.sleep(duration)
        finally:
            try:
                if sampling_enabled_by_example:
                    await client.touch.set_sampling_enabled(False)
            finally:
                await client.touch.unsubscribe_all()

        counts = ", ".join(f"{name}={count}" for name, count in event_counts.items())
        print(f"Touch events received: {counts}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stream SensWear touch events over BLE."
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
        default=20.0,
        help="Stream duration in seconds.",
    )
    parser.add_argument(
        "--streams",
        nargs="+",
        choices=TOUCH_STREAMS,
        default=["state", "gesture"],
        help="Touch streams to enable (default: state gesture).",
    )
    args = parser.parse_args()
    asyncio.run(run(args.device, args.timeout, args.duration, args.streams))


if __name__ == "__main__":
    main()
