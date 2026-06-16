# SensWear Python SDK

Python SDK for connecting to SensWear hardware over BLE.

This first SDK slice supports:

- Discovering and connecting to a SensWear device advertising as `Sens Wear ...`.
- Reading the custom power service battery gauge characteristic.
- Subscribing to battery gauge notifications.
- Reading the custom power service charger state characteristic.
- Subscribing to charger state notifications.
- Reading and writing the custom LED service color characteristic.
- Subscribing to custom IMU quaternion and acceleration notifications.
- Reading, configuring, and subscribing to custom temperature notifications.
- Writing custom haptic vibration patterns.

## Install for local development

```powershell
cd C:\Users\salamid1\Desktop\Projects\SenseWear\SDKs\Python
python -m pip install -e .
```

## Read the battery gauge

```python
import asyncio
from senswear import SenswearClient

async def main() -> None:
    async with SenswearClient() as device:
        state = await device.battery.read()
        print(f"Battery: {state.state_of_charge_percent:.1f}%")
        print(f"Voltage: {state.voltage_mv} mV")
        print(f"Temperature: {state.temperature_c:.1f} C")

asyncio.run(main())
```

To connect to a known BLE address or exact advertised name, pass it to the client:

```python
async with SenswearClient("Sens Wear (Regulator)") as device:
    state = await device.battery.read()
```

## Read the charger state

```python
import asyncio
from senswear import SenswearClient

async def main() -> None:
    async with SenswearClient() as device:
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
from senswear import LedColor, SenswearClient

async def main() -> None:
    async with SenswearClient() as device:
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
from senswear import SenswearClient

async def main() -> None:
    async with SenswearClient() as device:
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

## Read and stream temperature

```python
import asyncio
from senswear import SenswearClient

async def main() -> None:
    async with SenswearClient() as device:
        await device.temperature.set_sampling_rate_hz(2)

        latest = await device.temperature.read()
        print(f"Latest: {latest.temperature_c:.3f} C")

        def on_temperature(sample):
            print(f"Stream: {sample.temperature_c:.3f} C")

        await device.temperature.subscribe(on_temperature)
        await asyncio.sleep(10)
        await device.temperature.unsubscribe()

asyncio.run(main())
```

## Play haptic vibration

```python
import asyncio
from senswear import HapticFrame, HapticPattern, SenswearClient

async def main() -> None:
    async with SenswearClient() as device:
        await device.haptic.vibrate(duration_ms=150, intensity=255)

        pattern = HapticPattern.from_frames([
            HapticFrame(duration_ms=80, intensity=220),
            HapticFrame(duration_ms=60, intensity=0),
            HapticFrame(duration_ms=120, intensity=180),
        ])
        await device.haptic.play(pattern)

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

## Temperature fields

The SDK maps the firmware's `temperature_lbs_sample` payload. The temperature characteristic supports read and notify.

| SDK field | Unit |
| --- | --- |
| `temperature_mdeg_c` | millidegrees Celsius |

Convenience properties expose `temperature_c` and `temperature_f`.

Temperature UUIDs:

| Purpose | UUID |
| --- | --- |
| Service | `8e83a64b-319d-47c2-ba53-6185fae0007f` |
| Sampling rate write | `8e83a64c-319d-47c2-ba53-6185fae0007f` |
| Transfer interval write | `8e83a64d-319d-47c2-ba53-6185fae0007f` |
| Sample read/notify | `8e83a64e-319d-47c2-ba53-6185fae0007f` |

`set_sampling_rate_hz()` writes a nonzero little-endian `uint16`. `set_transfer_interval()` also writes a nonzero little-endian `uint16`; the current MAX30208 firmware accepts it over BLE but does not use it when scheduling samples.

## Haptic pattern fields

The SDK maps the firmware's write-only haptic pattern characteristic.

Haptic UUIDs:

| Purpose | UUID |
| --- | --- |
| Service | `daa05e91-f514-4a4e-8fc5-d1b80f25f24d` |
| Pattern write | `daa05e92-f514-4a4e-8fc5-d1b80f25f24d` |

Pattern payload layout:

| Field | Format |
| --- | --- |
| `version` | byte, currently `1` |
| `flags` | byte, reserved, send `0` |
| `frame_count` | little-endian `uint16`, 1 to 64 |
| frame `duration_ms` | little-endian `uint16`, nonzero |
| frame `intensity` | byte, 0 to 255 |

The actuator uses DRV2605 real-time playback. A frame with intensity `0` acts as an off/pause frame.

