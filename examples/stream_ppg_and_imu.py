import argparse
import asyncio

from senswear import (
    GyroscopeSample,
    LinearAccelerationSample,
    PpgSample,
    QuaternionSample,
    SenswearClient,
)

async def run(device: str | None, timeout: float, duration: float) -> None:
    async with SenswearClient(device, timeout=timeout) as client:
        ppg_was_enabled = await client.ppg.sampling_enabled()
        imu_was_enabled = await client.imu.physical_streams_enabled()

        def ppg_printer(channel: str):
            def print_sample(sample: PpgSample) -> None:
                print(
                    f"ppg {channel} timestamp_ms={sample.timestamp_ms} "
                    f"value={sample.value}",
                    flush=True,
                )

            return print_sample

        def on_quaternion(sample: QuaternionSample) -> None:
            x, y, z, w = sample.to_tuple()
            print(
                f"imu quat timestamp_us={sample.timestamp_us} "
                f"x={x:.4f} y={y:.4f} z={z:.4f} w={w:.4f} "
                f"accuracy={sample.accuracy_degrees:.2f}deg",
                flush=True,
            )

        def on_acceleration(sample: LinearAccelerationSample) -> None:
            x, y, z = sample.to_tuple()
            print(
                f"imu accel timestamp_us={sample.timestamp_us} "
                f"x={x:.4f}g y={y:.4f}g z={z:.4f}g",
                flush=True,
            )

        def on_gyroscope(sample: GyroscopeSample) -> None:
            x, y, z = sample.to_tuple()
            print(
                f"imu gyro timestamp_us={sample.timestamp_us} "
                f"x={x} y={y} z={z}",
                flush=True,
            )

        try:
            ppg_subscriptions = {
                "red": client.ppg.subscribe_red,
                "ir": client.ppg.subscribe_ir,
                "green": client.ppg.subscribe_green,
            }
            for channel, subscribe in ppg_subscriptions.items():
                await subscribe(ppg_printer(channel))
            await client.imu.subscribe_quaternion(on_quaternion)
            await client.imu.subscribe_linear_acceleration(on_acceleration)
            await client.imu.subscribe_gyroscope(on_gyroscope)

            # Restart PPG acquisition after subscribing so the firmware and
            # sensor begin from a synchronized state without losing samples.
            if ppg_was_enabled:
                await client.ppg.set_sampling_enabled(False)
            await client.ppg.set_sampling_enabled(True)
            if not imu_was_enabled:
                await client.imu.set_physical_streams_enabled(True)

            print(
                f"Connected: {client.address or 'unknown'}; "
                "streaming PPG and IMU",
                flush=True,
            )
            await asyncio.sleep(duration)
        finally:
            try:
                await client.ppg.set_sampling_enabled(False)
                if not imu_was_enabled:
                    await client.imu.set_physical_streams_enabled(False)
            finally:
                await client.ppg.unsubscribe_all()
                await client.imu.unsubscribe_all()
                if ppg_was_enabled:
                    await client.ppg.set_sampling_enabled(True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stream SensWear PPG and IMU notifications over BLE."
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
        "--duration", type=float, default=125.0, help="Stream duration in seconds."
    )
    args = parser.parse_args()
    asyncio.run(run(args.device, args.timeout, args.duration))


if __name__ == "__main__":
    main()
