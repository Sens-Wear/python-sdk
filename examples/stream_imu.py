import argparse
import asyncio

from senswear import LinearAccelerationSample, QuaternionSample, SenswearClient


async def run(device: str | None, timeout: float, duration: float) -> None:
    async with SenswearClient(device, timeout=timeout) as client:

        def on_quaternion(sample: QuaternionSample) -> None:
            x, y, z, w = sample.to_tuple()
            print(
                "quat "
                f"x={x:.4f} y={y:.4f} z={z:.4f} w={w:.4f} "
                f"acc={sample.accuracy_degrees:.2f}deg"
            )

        def on_acceleration(sample: LinearAccelerationSample) -> None:
            x, y, z = sample.to_tuple()
            print(f"accel x={x:.4f}g y={y:.4f}g z={z:.4f}g")

        await client.imu.set_physical_streams_enabled(True)
        await client.imu.subscribe_quaternion(on_quaternion)
        await client.imu.subscribe_linear_acceleration(on_acceleration)

        try:
            await asyncio.sleep(duration)
        finally:
            await client.imu.unsubscribe_all()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stream SensWear IMU notifications over BLE."
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
        "--duration", type=float, default=10.0, help="Stream duration in seconds."
    )
    args = parser.parse_args()
    asyncio.run(run(args.device, args.timeout, args.duration))


if __name__ == "__main__":
    main()
