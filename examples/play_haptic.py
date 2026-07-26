import argparse
import asyncio

from senswear import HapticFrame, HapticPattern, SenswearClient


def is_unlikely_gatt_error(error: Exception) -> bool:
    return (
        type(error).__name__ == "BleakGATTProtocolError"
        and bool(error.args)
        and error.args[0] == 0x0E
    )


async def run(
    device: str | None,
    timeout: float,
    duration_ms: int,
    intensity: int,
    double_pulse: bool,
) -> None:
    async with SenswearClient(device, timeout=timeout) as client:
        if double_pulse:
            pattern = HapticPattern.from_frames(
                [
                    HapticFrame(duration_ms=duration_ms, intensity=intensity),
                    HapticFrame(duration_ms=duration_ms, intensity=0),
                    HapticFrame(duration_ms=duration_ms, intensity=intensity),
                ]
            )
        else:
            pattern = HapticPattern.from_frames(
                [HapticFrame(duration_ms=duration_ms, intensity=intensity)]
            )

        print(f"Connected: {client.address or 'unknown'}")
        try:
            await client.haptic.play(pattern)
        except Exception as error:
            if not is_unlikely_gatt_error(error):
                raise

            # Firmware also uses ATT 0x0E when a previous asynchronous RTP
            # pattern is still active. Give it time to finish and retry once.
            await asyncio.sleep(max(pattern.total_duration_ms / 1000.0, 0.5))
            try:
                await client.haptic.play(pattern)
            except Exception as retry_error:
                if not is_unlikely_gatt_error(retry_error):
                    raise
                raise RuntimeError(
                    "The firmware rejected a valid haptic pattern twice. Verify "
                    "that the haptic firmware preset is flashed and inspect the "
                    "device log for 'Haptic pattern rejected': -19 means the "
                    "DRV2605 is not ready, -16 means busy, and -5 means an I2C "
                    "failure."
                ) from retry_error
        print("Haptic pattern sent")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Play a SensWear haptic vibration pattern over BLE."
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
        "--duration", type=int, default=150, help="Frame duration in milliseconds."
    )
    parser.add_argument(
        "--intensity", type=int, default=255, help="Vibration intensity from 0 to 255."
    )
    parser.add_argument(
        "--double-pulse",
        action="store_true",
        help="Play two pulses separated by one off frame.",
    )
    args = parser.parse_args()
    asyncio.run(
        run(args.device, args.timeout, args.duration, args.intensity, args.double_pulse)
    )


if __name__ == "__main__":
    main()
