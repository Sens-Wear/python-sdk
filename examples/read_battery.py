import argparse
import asyncio

from senswar import SenswarClient


async def run(device: str | None, timeout: float) -> None:
    async with SenswarClient(device, timeout=timeout) as client:
        state = await client.battery.read()
        print(f"Connected: {client.address or 'unknown'}")
        print(f"State of charge: {state.state_of_charge_percent:.1f}%")
        print(f"Voltage: {state.voltage_mv} mV")
        print(f"Average current: {state.average_current_ma} mA")
        print(f"Average power: {state.average_power_mw} mW")
        print(f"Temperature: {state.temperature_c:.2f} C")
        print(f"Remaining capacity: {state.remaining_capacity_mah} mAh")
        print(f"Full capacity: {state.full_battery_capacity_mah} mAh")


def main() -> None:
    parser = argparse.ArgumentParser(description="Read the Senswar battery gauge over BLE.")
    parser.add_argument(
        "device",
        nargs="?",
        help="Optional BLE address/platform identifier or exact advertised name.",
    )
    parser.add_argument("--timeout", type=float, default=10.0, help="BLE scan/connect timeout in seconds.")
    args = parser.parse_args()
    asyncio.run(run(args.device, args.timeout))


if __name__ == "__main__":
    main()
