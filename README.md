# Senswar Python SDK

Python SDK for connecting to Senswar/SensWear hardware over BLE.

This first SDK slice supports:

- Discovering and connecting to a Senswar device advertising as `Sens Wear ...`.
- Reading the custom power service battery gauge characteristic.
- Subscribing to battery gauge notifications.
- Reading the custom power service charger state characteristic.
- Subscribing to charger state notifications.
- Reading and writing the custom LED service color characteristic.
- Subscribing to custom IMU quaternion and acceleration notifications.

## Install for local development

```powershell
cd C:\Users\salamid1\Desktop\Projects\SenseWear\SDKs\Python
python -m pip install -e .
```

## Read the battery gauge

```python
import asyncio
from senswar import SenswarClient

async def main() -> None:
    async with SenswarClient() as device:
        state = await device.battery.read()
        print(f"Battery: {state.state_of_charge_percent:.1f}%")
        print(f"Voltage: {state.voltage_mv} mV")
        print(f"Temperature: {state.temperature_c:.1f} C")

asyncio.run(main())
```

To connect to a known BLE address or exact advertised name, pass it to the client:

```python
async with SenswarClient("Sens Wear (Regulator)") as device:
    state = await device.battery.read()
```

## Read the charger state

```python
import asyncio
from senswar import SenswarClient

async def main() -> None:
    async with SenswarClient() as device:
        state = await device.charger.read()
        print(f"Power good: {state.power_good}")
        print(f"Charging: {state.charging}")
        print(f"Charged: {state.charged}")
        print(f"Fault present: {state.has_fault}")

asyncio.run(main())
```

## Set the LED color

```python
import asyncio
from senswar import LedColor, SenswarClient

async def main() -> None:
    async with SenswarClient() as device:
        await device.led.set(LedColor(red=255, green=0, blue=0))
        current = await device.led.read()
        print(current.to_hex(include_white=True))

asyncio.run(main())
```

You can also use hex strings, tuples, or the raw firmware integer:

```python
await device.led.set("#00ff00")
await device.led.set((0, 0, 255, 0))
await device.led.set(0x000000ff)
await device.led.off()
```

## Stream the IMU

The IMU service is notify-only. Subscribing to either IMU characteristic enables firmware-side IMU streaming.

```python
import asyncio
from senswar import SenswarClient

async def main() -> None:
    async with SenswarClient() as device:
        def on_quaternion(sample):
            print(sample.to_tuple())

        def on_acceleration(sample):
            print(sample.to_tuple())

        await device.imu.subscribe_quaternion(on_quaternion)
        await device.imu.subscribe_linear_acceleration(on_acceleration)
        await asyncio.sleep(10)
        await device.imu.unsubscribe_all()

asyncio.run(main())
```

## Battery gauge fields

The SDK maps the firmware's `power_lbs_gauge_state` payload. The current firmware bridge forwards BQ27427 temperature and state-of-charge values in 0.1-unit resolution.

| SDK field | Unit |
| --- | --- |
| `temperature_deci_c` | 0.1 degrees Celsius |
| `voltage_mv` | millivolts |
| `average_current_ma` | milliamps |
| `average_power_mw` | milliwatts |
| `state_of_charge_deci_percent` | 0.1 percent |
| `nominal_available_capacity_mah` | mAh |
| `full_battery_capacity_mah` | mAh |
| `remaining_capacity_mah` | mAh |

Convenience properties expose `temperature_c` and `state_of_charge_percent`.

## Charger fields

The SDK maps the firmware's `power_lbs_charger_state` payload. It is a 32-bit flags value copied from the BQ25180 charger state bitfield.

| SDK property | Firmware bit |
| --- | --- |
| `button_pressed` | 0 |
| `wake1` | 1 |
| `wake2` | 2 |
| `shipment_mode` | 3 |
| `shutdown_mode` | 4 |
| `power_good` | 5 |
| `charging` | 6 |
| `charged` | 7 |
| `thermal_regulation` | 8 |
| `battery_uvlo` | 9 |
| `thermal_normal` | 10 |
| `thermal_warm_or_hot` | 11 |
| `thermal_warm` | 12 |
| `thermal_cool` | 13 |
| `safety_timer_fault` | 14 |
| `thermal_system_fault` | 15 |
| `battery_uvlo_fault` | 16 |
| `battery_ocp_fault` | 17 |

The `has_fault` convenience property is true when any charger fault bit is set.

## LED color fields

The SDK maps the firmware's `led_color_t` payload. The characteristic is a 4-byte little-endian RGBW value.

| SDK field | Firmware byte |
| --- | --- |
| `red` | 0 |
| `green` | 1 |
| `blue` | 2 |
| `white` | 3 |

The LED color characteristic UUID is `3c688943-4143-470d-a798-4629803a1983`. Writing `0x00000000` turns the LEDs off in the current firmware bridge.

## IMU fields

The SDK maps the firmware's `imu_lbs_quat` and `imu_lbs_lacc` notification payloads.

Quaternion notifications use UUID `7d2b6c11-9d78-4f3c-a122-6d2c4e6d2a11`.

| SDK field | Unit |
| --- | --- |
| `x` | raw signed Q14 |
| `y` | raw signed Q14 |
| `z` | raw signed Q14 |
| `w` | raw signed Q14 |
| `accuracy` | raw unsigned Q14 radians |

Convenience properties expose `x_float`, `y_float`, `z_float`, `w_float`, `accuracy_radians`, and `accuracy_degrees`.

Linear acceleration notifications use UUID `7d2b6c12-9d78-4f3c-a122-6d2c4e6d2a11`.

| SDK field | Unit |
| --- | --- |
| `x` | raw signed value |
| `y` | raw signed value |
| `z` | raw signed value |

Convenience properties expose `x_g`, `y_g`, and `z_g` using the BHI360 example scaling factor `value / 4096.0`. The current firmware labels this BLE stream `lacc`, but configures the BHI360 `BHY2_SENSOR_ID_ACC` virtual sensor.
