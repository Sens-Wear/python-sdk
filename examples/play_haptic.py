import argparse
import asyncio

from senswar import HapticFrame, HapticPattern, SenswarClient


async def run(
    device: str | None,
    timeout: float,
    duration_ms: int,
    intensity: int,
    double_pulse: bool,
) -> None:
    async with SenswarClient(device, timeout=timeout) as client:
        if double_pulse:
            pattern = HapticPattern.from_frames(
                [
                    HapticFrame(duration_ms=duration_ms, intensity=intensity),
                    HapticFrame(duration_ms=duration_ms, intensity=0),
                    HapticFrame(duration_ms=duration_ms, intensity=intensity),
                ]
            )
            await client.haptic.play(pattern)
        else:
            await client.haptic.vibrate(duration_ms=duration_ms, intensity=intensity)

        print(f"Connected: {client.address or 'unknown'}")
        print("Haptic pattern sent")


def main() -> None:
    parser = argparse.ArgumentParser(description="Play a Senswar haptic vibration pattern over BLE.")
    parser.add_argument(
        "device",
        nargs="?",
        help="Optional BLE address/platform identifier or exact advertised name.",
    )
    parser.add_argument("--timeout", type=float, default=10.0, help="BLE scan/connect timeout in seconds.")
    parser.add_argument("--duration", type=int, default=150, help="Frame duration in milliseconds.")
    parser.add_argument("--intensity", type=int, default=255, help="Vibration intensity from 0 to 255.")
    parser.add_argument("--double-pulse", action="store_true", help="Play two pulses separated by one off frame.")
    args = parser.parse_args()
    asyncio.run(run(args.device, args.timeout, args.duration, args.intensity, args.double_pulse))


if __name__ == "__main__":
    main()
