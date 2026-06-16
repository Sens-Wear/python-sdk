import argparse
import asyncio

from senswear import SenswearClient


async def run(device: str | None, timeout: float) -> None:
    async with SenswearClient(device, timeout=timeout) as client:
        state = await client.charger.read()
        print(f"Connected: {client.address or 'unknown'}")
        print(f"Raw flags: 0x{state.flags:08x}")
        print(f"Power good: {state.power_good}")
        print(f"Charging: {state.charging}")
        print(f"Charged: {state.charged}")
        print(f"Thermal normal: {state.thermal_normal}")
        print(f"Fault present: {state.has_fault}")
        print(f"Safety timer fault: {state.safety_timer_fault}")
        print(f"Thermal system fault: {state.thermal_system_fault}")
        print(f"Battery UVLO fault: {state.battery_uvlo_fault}")
        print(f"Battery OCP fault: {state.battery_ocp_fault}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Read the SensWear charger state over BLE.")
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

