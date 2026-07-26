# SensWear Python SDK

The SensWear Python SDK is an asynchronous Bluetooth Low Energy (BLE) client for
applications that communicate with the current SensWear firmware. It uses
[Bleak](https://github.com/hbldh/bleak) and supports Python 3.10 or newer.

The SDK provides typed Python objects for:

- battery level and charging state;
- UTC clock synchronization;
- body-temperature measurements;
- quaternion, acceleration, gyroscope, gesture, and activity data;
- red, infrared, and green PPG samples;
- touch position and gesture data;
- RGB LED control; and
- real-time haptic patterns.

This document describes both the high-level Python API and the data carried by
each Bluetooth characteristic. Application code should normally use the
high-level modules on `SenswearClient`; the wire-format sections are useful when
debugging or implementing a client in another language.

> **Hardware-dependent services**
>
> A firmware build can omit daughter boards or shields. The Python client always
> exposes all module properties, but a GATT operation fails if the connected
> firmware does not contain that service or its hardware is unavailable. An
> application intended for several SensWear hardware configurations should
> handle Bleak GATT errors and treat optional sensors as capabilities.

## Installation

Install the package and its Bleak dependency:

```powershell
python -m pip install senswear
```

For local SDK development:

```powershell
cd C:\Users\salamid1\Desktop\Projects\SenseWear\SDKs\Python
python -m pip install -e ".[dev]"
python -m pytest
```

## Programming model

All BLE operations are `async` methods and must run in an `asyncio` event loop.
Using the client as an asynchronous context manager is recommended because it
disconnects even if application code raises an exception:

```python
import asyncio

from senswear import SenswearClient


async def main() -> None:
    async with SenswearClient() as device:
        level = await device.battery.read()
        print(f"Connected to {device.address}; battery={level.percent}%")


asyncio.run(main())
```

The client exposes these modules:

| Property | Capability |
| --- | --- |
| `device.battery` | Battery percentage |
| `device.power` | External-power, charging, charge-level, and fault status |
| `device.charger` | Compatibility alias for `device.power` |
| `device.time` | Read or set the device's UTC clock |
| `device.temperature` | Body-temperature indications and measurement interval |
| `device.imu` | Motion, orientation, gestures, and activity |
| `device.ppg` | Raw red/IR/green optical samples |
| `device.touch` | Touch position, touch gestures, and raw touch state |
| `device.led` | RGB LED color |
| `device.haptic` | Real-time vibration patterns |

### Discovering and selecting a device

Without an argument, `SenswearClient` scans and connects to the first peripheral
whose advertised name begins with `Sens Wear`, `SensWear`, or `SenseWear`.

```python
devices = await SenswearClient.discover(timeout=5.0)
for item in devices:
    print(item.name, item.address, item.rssi)
```

`DiscoveredDevice` fields are:

| Field | Meaning |
| --- | --- |
| `name` | Advertised device name, or `None` if the platform did not provide it |
| `address` | MAC address on Linux/Windows or platform identifier on macOS |
| `rssi` | Received signal strength in dBm when supplied by the BLE platform |

Select a specific peripheral by exact advertised name, MAC address, or platform
identifier:

```python
async with SenswearClient("Sens Wear (OOB)", timeout=15.0) as device:
    ...
```

You can change automatic name matching:

```python
client = SenswearClient(name_prefixes=("My SensWear",))
```

Useful client properties and methods are:

| API | Meaning |
| --- | --- |
| `await SenswearClient.discover(...)` | Scan without connecting |
| `await client.connect()` | Resolve and connect to the requested peripheral |
| `await client.disconnect()` | Disconnect |
| `client.is_connected` | Whether the underlying Bleak client reports a connection |
| `client.address` | Connected platform address/identifier, if known |

`connect()` is idempotent while already connected. Calling a module operation
before connecting raises `NotConnectedError`.

### Reads, writes, and subscriptions

- A `read_*()` method returns the latest value cached by the firmware. A cached
  sensor value can be zero until the first hardware sample arrives.
- A `subscribe_*()` method enables GATT notifications or indications and
  decodes each payload into a typed object.
- Subscription callbacks can be ordinary functions or `async` functions.
- Subscribing again to the same stream first replaces the existing
  subscription.
- Always unsubscribe when a stream is no longer needed. `unsubscribe_all()` is
  available on multi-stream modules.

Example with a synchronous callback:

```python
def on_sample(sample) -> None:
    print(sample)

await device.ppg.subscribe_red(on_sample)
```

Example with an asynchronous callback:

```python
async def store_sample(sample) -> None:
    await database.insert(sample)

await device.ppg.subscribe_red(store_sample)
```

Async callbacks are scheduled as independent `asyncio` tasks. Keep callbacks
short or queue samples for a separate consumer; otherwise a high-rate stream can
create more pending work than the application can process.

Most write methods accept `response=True`. The default requests an acknowledged
GATT write, which is recommended for configuration and actuator commands.
`response=False` requests write-without-response when the characteristic and BLE
backend support it:

```python
await device.led.set("#ff0000", response=False)
```

## Common data conventions

### Timestamps

- IMU and touch samples use `timestamp_us`: signed 64-bit microseconds since the
  Unix epoch.
- PPG samples use `timestamp_ms`: unsigned 64-bit milliseconds since the Unix
  epoch.
- `sample.timestamp` converts either integer timestamp to a timezone-aware UTC
  `datetime`.
- Temperature and Current Time Service values are already exposed as
  timezone-aware UTC `datetime` objects.

Use the integer timestamp when preserving exact sensor timing or ordering. Use
the `datetime` convenience property for presentation and storage systems that
expect wall-clock time.

### Byte order

All multi-byte firmware fields are little-endian. The SDK performs the decoding;
high-level application code does not need to call `struct.unpack`.

### Validation and exceptions

The SDK validates local inputs before writing:

- wrong Python types raise `TypeError`;
- out-of-range values raise `ValueError`;
- malformed or unexpected firmware payloads raise `ProtocolError`;
- discovery failure raises `DeviceNotFoundError`;
- use before connection raises `NotConnectedError`; and
- missing Bleak installation raises `SenswearDependencyError`.

BLE transport and ATT/GATT failures are raised by Bleak. Catch the appropriate
Bleak exception when implementing reconnect or optional-service logic.

## Battery level

`device.battery` implements the Bluetooth SIG Battery Service Battery Level
characteristic.

### API

```python
level = await device.battery.read()
print(level.percent)

await device.battery.subscribe(lambda value: print(value.percent))
...
await device.battery.unsubscribe()
```

### `BatteryLevel`

| Field/property | Type | Unit | Meaning |
| --- | --- | --- | --- |
| `percent` | `int` | `%` | State of charge, constrained to 0 through 100 |
| `state_of_charge_percent` | `float` | `%` | Compatibility spelling for SDK 0.1 callers |

The firmware derives the percentage from the fuel gauge's state of charge in
tenths of a percent. It rounds to the nearest integer percent and clamps values
to 0–100. A notification is sent when the fuel-gauge stream updates.

The current standardized service intentionally does not expose the old SDK
fields for battery voltage, current, power, capacity, or temperature.

### Wire format

| Characteristic | UUID | Access | Payload |
| --- | --- | --- | --- |
| Battery Level | `00002a19-0000-1000-8000-00805f9b34fb` | Read, Notify | One unsigned byte, 0–100 percent |

## Power and charging status

`device.power` implements the Bluetooth SIG Battery Level Status
characteristic. `device.charger` is the same module retained as a compatibility
alias.

### API

```python
status = await device.power.read()

print(status.battery_level)
print(status.wired_power)
print(status.charge_state)
print(status.charge_level)
print(status.has_fault)

await device.power.subscribe(lambda value: print(value.charging))
...
await device.power.unsubscribe()
```

### `BatteryLevelStatus`

| Field/property | Type | Meaning |
| --- | --- | --- |
| `flags` | `int` | Raw Battery Level Status flags; firmware sets bit 1 because battery level is present |
| `power_state` | `int` | Raw 16-bit packed power-state field |
| `battery_level` | `int` | Battery percentage, 0–100 |
| `battery_present` | `bool` | A battery is present |
| `wired_power` | `PowerSourceState` | Wired input connection state |
| `wireless_power` | `PowerSourceState` | Wireless input connection state; current hardware reports not connected |
| `charge_state` | `ChargeState` | Charging/discharging state |
| `charge_level` | `ChargeLevel` | Good, low, critical, or unknown |
| `charge_type` | `int` | Raw three-bit charge-type value; current firmware reports 0/unknown |
| `charging_fault_reason` | `int` | Raw four-bit fault mask; current firmware uses bit 2 for “other fault” |
| `power_good` | `bool` | Convenience property: wired power is connected |
| `charging` | `bool` | Convenience property: charge state is charging |
| `charged` | `bool` | Convenience property: charge state is discharging-inactive/full |
| `has_fault` | `bool` | At least one charging-fault bit is set |

Enum values:

| Enum | Value | Meaning |
| --- | ---: | --- |
| `PowerSourceState.NOT_CONNECTED` | 0 | No source detected |
| `PowerSourceState.CONNECTED` | 1 | Source connected |
| `PowerSourceState.UNKNOWN` | 2 | State is not yet known |
| `PowerSourceState.RESERVED` | 3 | Reserved encoding |
| `ChargeState.UNKNOWN` | 0 | Charging state not known |
| `ChargeState.CHARGING` | 1 | Battery is charging |
| `ChargeState.DISCHARGING_ACTIVE` | 2 | Battery is powering the system |
| `ChargeState.DISCHARGING_INACTIVE` | 3 | Charge complete/inactive |
| `ChargeLevel.UNKNOWN` | 0 | Level classification not known |
| `ChargeLevel.GOOD` | 1 | More than 20% |
| `ChargeLevel.LOW` | 2 | 6–20% |
| `ChargeLevel.CRITICAL` | 3 | 0–5% |

Notifications are emitted when either the battery-gauge state or charger state
updates. An application may therefore receive a notification even when only one
field changed.

### Wire format

| Characteristic | UUID | Access | Payload |
| --- | --- | --- | --- |
| Battery Level Status | `00002bed-0000-1000-8000-00805f9b34fb` | Read, Notify | `<BHB`: flags, 16-bit power state, battery level |

`power_state` bit allocation:

| Bits | Meaning |
| --- | --- |
| 0 | Battery present |
| 1–2 | Wired power state |
| 3–4 | Wireless power state |
| 5–6 | Charge state |
| 7–8 | Charge-level classification |
| 9–11 | Charge type |
| 12–15 | Charging-fault reason |

## Device time and RTC synchronization

`device.time` implements the Bluetooth SIG Current Time Service. Firmware and
sensor timestamps depend on the device RTC, so applications should set the time
after provisioning or whenever the clock may be stale.

### API

```python
from datetime import datetime, timezone

await device.time.set(
    datetime.now(timezone.utc),
    adjust_reason=0x01,  # manual time update
)

current = await device.time.read()
print(current.value)

await device.time.subscribe(lambda value: print(value.value))
...
await device.time.unsubscribe()
```

The `datetime` passed to `set()` must be timezone-aware. It is converted to UTC
before transmission. Naive datetimes are rejected to prevent local time from
being written as UTC. The firmware RTC also rejects dates before
2020-01-01 00:00:00 UTC.

### `CurrentTime`

| Field | Type | Meaning |
| --- | --- | --- |
| `value` | UTC `datetime` | Whole-second UTC date and time |
| `day_of_week` | `int` | ISO day number: Monday=1 through Sunday=7 |
| `fractions256` | `int` | Fraction of a second in 1/256-second units; firmware currently reports/writes 0 |
| `adjust_reason` | `int` | Bit mask explaining why the time changed |

Adjust-reason bits:

| Bit | Hex | Meaning |
| ---: | ---: | --- |
| 0 | `0x01` | Manual time update |
| 1 | `0x02` | External reference time update |
| 2 | `0x04` | Time-zone change |
| 3 | `0x08` | Daylight-saving-time change |

The value written by `TimeModule.set()` updates the hardware RTC. If subscribed,
the firmware notifies the Current Time characteristic after a successful write.

### Local and reference information

```python
local = await device.time.read_local_information()
reference = await device.time.read_reference_information()
```

`LocalTimeInformation`:

| Field | Unit | Meaning |
| --- | --- | --- |
| `time_zone_quarter_hours` | 15-minute increments | UTC offset; `-128` means unknown |
| `dst_offset` | Bluetooth SIG DST code | `255` means unknown |

`ReferenceTimeInformation`:

| Field | Unit | Meaning |
| --- | --- | --- |
| `source` | Bluetooth SIG source code | `0` means unknown |
| `accuracy_eighths_second` | 1/8 second | `255` means unknown |
| `days_since_update` | days | `255` means unknown |
| `hours_since_update` | hours | `255` means unknown |

Current firmware leaves local-time and reference-time information unknown.
Application timestamps should therefore be interpreted as UTC.

### Wire format

| Characteristic | UUID | Access | Payload |
| --- | --- | --- | --- |
| Current Time | `00002a2b-0000-1000-8000-00805f9b34fb` | Read, Write, Notify | 10-byte Bluetooth Current Time value |
| Local Time Information | `00002a0f-0000-1000-8000-00805f9b34fb` | Read | `<bB>` |
| Reference Time Information | `00002a14-0000-1000-8000-00805f9b34fb` | Read | `<BBBB>` |

## Body temperature

`device.temperature` implements the Bluetooth SIG Health Thermometer Service
for the MAX30208 body-temperature sensor.

### Important behavior

Temperature Measurement is **indicate-only**. There is no
`device.temperature.read()` method. Subscribe and wait for a new measurement.
Indications are acknowledged at the GATT level and are lower-rate than IMU or
PPG notifications.

The firmware scheduler works in whole minutes:

- `set_measurement_interval(0)` disables scheduled measurements.
- `set_measurement_interval(seconds)` accepts `0` or a whole-minute multiple
  from 60 through 65,520 seconds.
- Raw BLE writes that are not whole-minute multiples are rounded **up** by the
  firmware, but the Python SDK rejects them so readback is predictable.
- `read_measurement_interval()` returns the applied interval in seconds.

The Bluetooth SIG characteristic uses seconds on the wire even though the
firmware scheduler operates in minutes. The maximum accepted value is 65,520
seconds because the next whole minute cannot fit in the characteristic's
unsigned 16-bit value.

### API

```python
async def on_temperature(sample) -> None:
    print(f"{sample.temperature_c:.2f} °C at {sample.timestamp}")


await device.temperature.set_measurement_interval(60)
print(await device.temperature.read_measurement_interval())
print(await device.temperature.read_temperature_type())

await device.temperature.subscribe(on_temperature)
...
await device.temperature.unsubscribe()
```

### `TemperatureMeasurement`

| Field/property | Type | Unit | Meaning |
| --- | --- | --- | --- |
| `temperature_c` | `float` | degrees Celsius | Decoded IEEE-11073 temperature |
| `temperature_f` | `float` | degrees Fahrenheit | Convenience conversion |
| `timestamp` | UTC `datetime` or `None` | UTC | Measurement time when the timestamp-present flag is set |
| `temperature_type` | `TemperatureType`, raw `int`, or `None` | — | Measurement location/type |
| `flags` | `int` | bit mask | Raw Health Thermometer flags |

Current firmware sends Celsius, includes a timestamp, and reports
`TemperatureType.BODY`.

`TemperatureType` values:

| Value | Enum | Meaning |
| ---: | --- | --- |
| 1 | `ARMPIT` | Armpit |
| 2 | `BODY` | General body measurement |
| 3 | `EAR` | Ear |
| 4 | `FINGER` | Finger |
| 5 | `GASTROINTESTINAL_TRACT` | Gastrointestinal tract |
| 6 | `MOUTH` | Mouth |
| 7 | `RECTUM` | Rectum |
| 8 | `TOE` | Toe |
| 9 | `TYMPANUM` | Tympanum |

The SDK aliases `TemperatureSample` to `TemperatureMeasurement` for
compatibility.

### Wire format

| Characteristic | UUID | Access | Meaning |
| --- | --- | --- | --- |
| Temperature Measurement | `00002a1c-0000-1000-8000-00805f9b34fb` | Indicate | Flags, IEEE-11073 FLOAT, optional timestamp, optional type |
| Temperature Type | `00002a1d-0000-1000-8000-00805f9b34fb` | Read | One-byte type code |
| Measurement Interval | `00002a21-0000-1000-8000-00805f9b34fb` | Read, Write, Indicate | Little-endian unsigned 16-bit seconds |

Temperature flags use bit 0 for Fahrenheit, bit 1 for timestamp present, and bit
2 for temperature type present. The SDK always exposes `temperature_c`
regardless of the on-wire unit.

## IMU

`device.imu` exposes BHI360 orientation, acceleration, angular velocity,
gesture, and activity data.

### Enabling high-rate physical streams

Quaternion, acceleration, and gyroscope streams are disabled initially and run
at 100 Hz when enabled:

```python
await device.imu.set_drain_period_ms(100)
await device.imu.set_physical_streams_enabled(True)

print(await device.imu.read_drain_period_ms())
print(await device.imu.physical_streams_enabled())
```

`drain_period_ms` is a nonzero unsigned 32-bit number controlling how often the
host drains the BHI360 FIFO. It is **not** the sensor sampling interval: the
three physical virtual sensors still produce data at 100 Hz. A shorter drain
period reduces delivery latency and produces smaller bursts, while a longer
period reduces host wakeups but increases latency and burst size.

Changing the drain period while physical streams are enabled restarts/applies
the FIFO timer immediately. Setting it while streams are disabled stores the
period for the next enable.

Gesture and activity-class sensors are low-rate/on-change streams and remain
available independently of the physical-stream enable switch.

### Reading and subscribing

```python
latest_q = await device.imu.read_quaternion()
latest_a = await device.imu.read_linear_acceleration()
latest_g = await device.imu.read_gyroscope()
latest_gesture = await device.imu.read_gesture()
latest_activity = await device.imu.read_activity()

await device.imu.subscribe_quaternion(on_quaternion)
await device.imu.subscribe_linear_acceleration(on_acceleration)
await device.imu.subscribe_gyroscope(on_gyroscope)
await device.imu.subscribe_gesture(on_gesture)
await device.imu.subscribe_activity(on_activity)

...
await device.imu.unsubscribe_all()
```

Each individual stream also has a matching `unsubscribe_*()` method.

### Quaternion data

`QuaternionSample` fields:

| Field/property | Type | Unit | Meaning |
| --- | --- | --- | --- |
| `timestamp_us` | `int` | µs since Unix epoch | Sensor sample time |
| `timestamp` | UTC `datetime` | UTC | Convenience conversion |
| `x`, `y`, `z`, `w` | `int` | signed Q14 | Raw quaternion components |
| `x_float`, `y_float`, `z_float`, `w_float` | `float` | unitless | Raw component divided by 16384 |
| `accuracy` | `int` | unsigned Q14 radians | Raw orientation accuracy |
| `accuracy_radians` | `float` | radians | `accuracy / 16384` |
| `accuracy_degrees` | `float` | degrees | Accuracy converted to degrees |

```python
def on_quaternion(sample) -> None:
    x, y, z, w = sample.to_tuple()  # normalized floats
    raw = sample.to_tuple(normalized=False)
```

The source is the BHI360 Game Rotation Vector wake-up virtual sensor. It does
not use a magnetometer, so yaw can drift over time even though short-term
orientation is smooth.

### Acceleration data

`LinearAccelerationSample` fields:

| Field/property | Type | Unit | Meaning |
| --- | --- | --- | --- |
| `timestamp_us` / `timestamp` | `int` / UTC `datetime` | µs / UTC | Sample time |
| `x`, `y`, `z` | `int` | signed raw value | Corrected accelerometer output |
| `x_g`, `y_g`, `z_g` | `float` | g | Raw value divided by 4096 |

`to_tuple()` returns scaled g values; `to_tuple(scaled=False)` returns raw
integers.

> **Current naming caveat:** the Python and BLE API call this “linear
> acceleration,” but the firmware currently configures the BHI360 `ACC_WU`
> corrected accelerometer stream. The values therefore include gravity. Do not
> treat the stream as gravity-removed acceleration without applying your own
> orientation/gravity compensation.

### Gyroscope data

`GyroscopeSample` contains `timestamp_us`, `timestamp`, and raw signed `x`, `y`,
and `z` values. `to_tuple()` returns the three raw integers.

The SDK deliberately does not apply a degrees-per-second scale because the
current BLE contract forwards BHI360 fixed-point values without publishing a
range/scale descriptor. Calibrate or convert only when the firmware's configured
gyroscope range is known by the application.

### Gesture data

`GestureSample` fields:

| Field/property | Meaning |
| --- | --- |
| `timestamp_us` / `timestamp` | Event time |
| `sensor_id` | BHI360 virtual-sensor ID that generated the event |
| `gesture` | Raw one-byte output from that virtual sensor |
| `gesture_type` | `ImuGesture` when recognized, otherwise the raw integer |

`ImuGesture` values:

| Value | Enum | Meaning |
| ---: | --- | --- |
| `0x00` | `NONE` | No decoded wrist gesture |
| `0x03` | `WRIST_SHAKE_JIGGLE` | Wrist shake/jiggle |
| `0x04` | `FLICK_IN` | Wrist flick inward |
| `0x05` | `FLICK_OUT` | Wrist flick outward |

Always inspect `sensor_id` before interpreting `gesture`. The same
characteristic also carries scalar events such as any-motion, no-motion, and
wrist-wear detection, for which the raw byte is a detection value rather than a
wrist-gesture enum. Relevant default sensor IDs include 142 (any-motion),
156 (wrist-gesture detector), 158 (wrist-wear), and 159 (no-motion).

### Activity data

`ActivitySample` fields:

| Field/property | Meaning |
| --- | --- |
| `timestamp_us` / `timestamp` | Transition time |
| `sensor_id` | BHI360 activity-recognition virtual-sensor ID; default wear activity is 154 |
| `activity` | Raw normalized activity code |
| `activity_type` | `ImuActivity` when recognized |
| `transition` | Raw transition code |
| `transition_type` | `ActivityTransition` when recognized |

Activity values:

| Value | Enum |
| ---: | --- |
| 0 | `STILL` |
| 1 | `WALKING` |
| 2 | `RUNNING` |
| 3 | `ON_BICYCLE` |
| 4 | `IN_VEHICLE` |
| 5 | `TILTING` |

Transition value 0/`ENDED` means the activity stopped; value 1/`STARTED` means
it began. One callback represents one activity transition, not a bit mask.

### IMU wire formats and UUIDs

| Characteristic | UUID | Access | Payload |
| --- | --- | --- | --- |
| Quaternion | `7d2b6c11-9d78-4f3c-a122-6d2c4e6d2a11` | Read, Notify | `<qhhhhH>`: timestamp µs, x, y, z, w, accuracy |
| Acceleration | `7d2b6c12-9d78-4f3c-a122-6d2c4e6d2a11` | Read, Notify | `<qhhh>`: timestamp µs, x, y, z |
| Gyroscope | `7d2b6c13-9d78-4f3c-a122-6d2c4e6d2a11` | Read, Notify | `<qhhh>`: timestamp µs, x, y, z |
| Gesture | `7d2b6c14-9d78-4f3c-a122-6d2c4e6d2a11` | Read, Notify | `<qBB>`: timestamp µs, sensor ID, value |
| Activity | `7d2b6c15-9d78-4f3c-a122-6d2c4e6d2a11` | Read, Notify | `<qBBB>`: timestamp µs, sensor ID, activity, transition |
| Physical streams enable | `7d2b6c21-9d78-4f3c-a122-6d2c4e6d2a11` | Read, Write | One byte: 0 or 1 |
| FIFO drain period | `7d2b6c22-9d78-4f3c-a122-6d2c4e6d2a11` | Read, Write | Little-endian unsigned 32-bit milliseconds, nonzero |

## PPG

`device.ppg` exposes raw optical samples from the MAX30101 in three channels:
red, infrared, and green.

> **Raw signal, not a physiological result:** `PpgSample.value` is a raw
> right-justified 18-bit ADC count. It is not heart rate, oxygen saturation, or
> a calibrated optical unit. Applications must perform filtering, artifact
> rejection, peak detection, and physiological estimation separately.

### Configuring acquisition

```python
# IRQ cadence may only be changed while sampling is stopped.
await device.ppg.set_sampling_enabled(False)
await device.ppg.set_per_sample_irq_enabled(False)
await device.ppg.set_sampling_enabled(True)

print(await device.ppg.sampling_enabled())
print(await device.ppg.per_sample_irq_enabled())
```

`per_sample_irq_enabled` selects how the MAX30101 wakes the firmware:

- `True`: interrupt for every new sample; lowest latency, most host wakeups.
- `False`: FIFO almost-full interrupt; samples arrive in bursts with fewer
  wakeups.

The firmware rejects an IRQ-cadence change while PPG sampling is active. Disable
sampling, change the setting, then re-enable sampling.

The current wrist-HR acquisition configuration uses all three LED channels,
hardware sampling at 3200 Hz with 16-sample FIFO averaging, giving an effective
200 samples/second per channel. The BLE API does not currently allow changing
sample rate, LED amplitude, pulse width, ADC range, or averaging.

The current OOB firmware normally starts PPG sampling during device bring-up
with batched/FIFO-almost-full IRQ cadence. Read `sampling_enabled()` instead of
assuming that acquisition starts disabled.

### Reading and subscribing

```python
red = await device.ppg.read_red()
infrared = await device.ppg.read_ir()
green = await device.ppg.read_green()

await device.ppg.subscribe_red(on_red)
await device.ppg.subscribe_ir(on_ir)
await device.ppg.subscribe_green(on_green)
...
await device.ppg.unsubscribe_all()
```

Every hardware sample updates all three cached characteristics. Subscribing to
all channels therefore produces three decoded callback events per sample time.
Match channels using `timestamp_ms`.

### `PpgSample`

| Field/property | Type | Unit | Meaning |
| --- | --- | --- | --- |
| `timestamp_ms` | `int` | ms since Unix epoch | Interpolated acquisition time |
| `timestamp` | UTC `datetime` | UTC | Convenience conversion |
| `value` | `int` | raw ADC counts | Right-justified 18-bit channel value, normally 0–262143 |

### Wire formats and UUIDs

| Characteristic | UUID | Access | Payload |
| --- | --- | --- | --- |
| Red | `029ca551-d022-4583-b483-91e9ea77034a` | Read, Notify | `<QI>` timestamp ms, value |
| Infrared | `029ca552-d022-4583-b483-91e9ea77034a` | Read, Notify | `<QI>` timestamp ms, value |
| Green | `029ca553-d022-4583-b483-91e9ea77034a` | Read, Notify | `<QI>` timestamp ms, value |
| Sampling enable | `029ca561-d022-4583-b483-91e9ea77034a` | Read, Write | One byte: 0 or 1 |
| Per-sample IRQ | `029ca562-d022-4583-b483-91e9ea77034a` | Read, Write | One byte: 0 or 1 |

## Touch

`device.touch` exposes touch presence/position and decoded gestures from the
MTCH6102 touch controller.

### Configuration

```python
await device.touch.set_sampling_enabled(True)
print(await device.touch.sampling_enabled())
```

Enabling sampling starts the controller and its event stream. Disabling it stops
sampling and powers down the touch supply. The setting uses a strict Python
`bool`.

### Touch position

```python
def on_touch(sample) -> None:
    if sample.touched:
        print(f"touch at x={sample.x}, y={sample.y}")
    else:
        print("released")


await device.touch.subscribe_state(on_touch)
```

`TouchState` fields:

| Field/property | Type | Meaning |
| --- | --- | --- |
| `timestamp_us` / `timestamp` | `int` / UTC `datetime` | Sample time |
| `touched` | `bool` | Whether a touch is present |
| `x`, `y` | `int` | Reconstructed unsigned 12-bit controller coordinates, 0–4095 |

When `touched` is false, firmware forces both coordinates to zero. Coordinates
are controller-space values; applications should calibrate, orient, and scale
them for their UI geometry.

### Touch gestures

`TouchGestureSample` fields:

| Field/property | Meaning |
| --- | --- |
| `timestamp_us` / `timestamp` | Gesture time |
| `gesture` | Normalized gesture number |
| `gesture_type` | `TouchGesture` when recognized, otherwise raw integer |
| `gesture_state` | Original MTCH6102 GESTURE_STATE register byte |

Normalized and raw gesture mappings:

| Normalized value | `TouchGesture` | Raw `gesture_state` |
| ---: | --- | ---: |
| 0 | `NONE` | `0x00` |
| 1 | `SINGLE_CLICK` | `0x10` |
| 2 | `CLICK_AND_HOLD` | `0x11` |
| 3 | `DOUBLE_CLICK` | `0x20` |
| 4 | `DOWN_SWIPE` | `0x31` |
| 5 | `DOWN_SWIPE_AND_HOLD` | `0x32` |
| 6 | `RIGHT_SWIPE` | `0x41` |
| 7 | `RIGHT_SWIPE_AND_HOLD` | `0x42` |
| 8 | `UP_SWIPE` | `0x51` |
| 9 | `UP_SWIPE_AND_HOLD` | `0x52` |
| 10 | `LEFT_SWIPE` | `0x61` |
| 11 | `LEFT_SWIPE_AND_HOLD` | `0x62` |

```python
await device.touch.subscribe_gesture(
    lambda sample: print(sample.gesture_type, hex(sample.gesture_state))
)
```

### Raw touch state

`RawTouchSample` adds `touch_state`, the original one-byte TOUCHSTATE register,
to the timestamp, presence, and coordinates. Use it for diagnostics or
controller-specific logic; ordinary applications should prefer `TouchState`.

```python
latest = await device.touch.read_raw()
await device.touch.subscribe_raw(on_raw_touch)
```

The raw characteristic mirrors a 16-byte aligned firmware structure. The SDK
removes the alignment padding and exposes only meaningful fields.

### Touch methods

| Stream | Read | Subscribe | Unsubscribe |
| --- | --- | --- | --- |
| Position/presence | `read_state()` | `subscribe_state(callback)` | `unsubscribe_state()` |
| Gesture | `read_gesture()` | `subscribe_gesture(callback)` | `unsubscribe_gesture()` |
| Raw state | `read_raw()` | `subscribe_raw(callback)` | `unsubscribe_raw()` |

`unsubscribe_all()` stops every active touch subscription.

### Wire formats and UUIDs

| Characteristic | UUID | Access | Payload |
| --- | --- | --- | --- |
| Touch state | `33a5eb42-0e13-424f-8b7a-942be0ee5cfc` | Read, Notify | `<q?HH>`: timestamp µs, touched, x, y |
| Touch gesture | `33a5eb43-0e13-424f-8b7a-942be0ee5cfc` | Read, Notify | `<qBB>`: timestamp µs, normalized gesture, raw gesture |
| Raw touch data | `33a5eb44-0e13-424f-8b7a-942be0ee5cfc` | Read, Notify | 16-byte aligned firmware touch message |
| Sampling enable | `33a5eb51-0e13-424f-8b7a-942be0ee5cfc` | Read, Write | One byte: 0 or 1 |

## RGB LED

`device.led` controls the three RGB channels. Each channel is an integer from 0
(off) to 255 (maximum command value).

### Accepted input forms

```python
from senswear import LedColor

await device.led.set(LedColor(red=255, green=128, blue=0))
await device.led.set("#ff8000")
await device.led.set("ff8000")
await device.led.set((255, 128, 0))
await device.led.set(0xFF8000)
await device.led.set_rgb(255, 128, 0)
await device.led.off()
```

Read back the firmware's cached command:

```python
color = await device.led.read()
print(color.red, color.green, color.blue)
print(color.to_hex())  # "#ff8000"
print(hex(color.to_int()))  # 0xff8000
```

`read()` reports the last successfully applied BLE color command, not a measured
optical output. Brightness and perceived color depend on LED hardware,
calibration, supply, and mechanics.

### `LedColor`

| Field | Range | Meaning |
| --- | --- | --- |
| `red` | 0–255 | Red channel command |
| `green` | 0–255 | Green channel command |
| `blue` | 0–255 | Blue channel command |

The firmware represents the color as the integer `0x00RRGGBB`. Because the
32-bit integer is sent little-endian, the four wire bytes are `BB GG RR 00`.

| Characteristic | UUID | Access | Payload |
| --- | --- | --- | --- |
| LED Color | `3c688943-4143-470d-a798-4629803a1983` | Read, Write, Write Without Response | Little-endian unsigned 32-bit `0x00RRGGBB` |

## Haptic actuator

`device.haptic` sends real-time playback patterns to the DRV2605 haptic
actuator.

### Single vibration

```python
await device.haptic.vibrate(duration_ms=150, intensity=255)
```

### Multi-frame pattern

```python
from senswear import HapticFrame, HapticPattern

pattern = HapticPattern.from_frames(
    [
        HapticFrame(duration_ms=80, intensity=220),
        HapticFrame(duration_ms=60, intensity=0),   # pause/off frame
        HapticFrame(duration_ms=120, intensity=180),
    ]
)

print(pattern.total_duration_ms)
await device.haptic.play(pattern)
```

`play()` also accepts an iterable of `(duration_ms, intensity)` tuples:

```python
await device.haptic.play([(80, 220), (60, 0), (120, 180)])
```

### Frame constraints

| Field | Range | Meaning |
| --- | --- | --- |
| `duration_ms` | 1–65535 ms | Time to hold the frame |
| `intensity` | 0–255 | DRV2605 RTP amplitude; 0 is off/pause |
| frames per pattern | 1–32 | Number of sequential frames |

`intensity` is an actuator command, not a calibrated force or acceleration.
Perceived strength depends on the actuator and mechanics. The total requested
duration is the sum of all frame durations.

The firmware accepts only one active real-time pattern. A new command sent while
a previous pattern is still playing is rejected by GATT. Wait at least
`pattern.total_duration_ms` before sending the next pattern, or handle the Bleak
write error and retry later.

### Wire format

| Characteristic | UUID | Access |
| --- | --- | --- |
| Haptic Pattern | `daa05e92-f514-4a4e-8fc5-d1b80f25f24d` | Write |

Packet structure:

| Offset | Type | Meaning |
| ---: | --- | --- |
| 0 | `uint8` | Version; must be 1 |
| 1 | `uint8` | Flags; must be 0 |
| 2 | little-endian `uint16` | Frame count, 1–32 |
| 4 | repeated frame | Frames follow immediately |

Each frame is three bytes: little-endian `uint16 duration_ms` followed by
`uint8 intensity`.

## Complete service and UUID index

Bluetooth SIG UUIDs are shown in their 16-bit form; custom UUIDs are shown in
full.

| Service | Service UUID | Client module |
| --- | --- | --- |
| Battery Service | `0x180F` | `battery`, `power` |
| Current Time Service | `0x1805` | `time` |
| Health Thermometer Service | `0x1809` | `temperature` |
| IMU data | `7d2b6c10-9d78-4f3c-a122-6d2c4e6d2a11` | `imu` |
| IMU configuration | `7d2b6c20-9d78-4f3c-a122-6d2c4e6d2a11` | `imu` |
| PPG data | `029ca54e-d022-4583-b483-91e9ea77034a` | `ppg` |
| PPG configuration | `029ca560-d022-4583-b483-91e9ea77034a` | `ppg` |
| Touch data | `33a5eb3f-0e13-424f-8b7a-942be0ee5cfc` | `touch` |
| Touch configuration | `33a5eb50-0e13-424f-8b7a-942be0ee5cfc` | `touch` |
| LED | `3c688942-4143-470d-a798-4629803a1983` | `led` |
| Haptic | `daa05e91-f514-4a4e-8fc5-d1b80f25f24d` | `haptic` |

UUID constants are available from `senswear.uuids` for applications that need
lower-level GATT access.

## Migration notes from SDK 0.1

The firmware moved several custom characteristics to Bluetooth SIG services and
added timestamps to sensor payloads. Existing applications should account for
these API changes:

- `device.battery.read()` now returns `BatteryLevel`, which contains percentage
  only. `BatteryGaugeState` remains an alias, but the former voltage/current/
  capacity fields no longer exist.
- `device.charger` is now an alias for `device.power` and returns
  `BatteryLevelStatus`, not the former raw BQ25180 flags object.
- Temperature is indication-only. Replace `temperature.read()`,
  `set_sampling_rate_hz()`, and `set_transfer_interval()` with
  `subscribe()`, `set_measurement_interval()`, and
  `read_measurement_interval()`.
- IMU data objects now begin with `timestamp_us`; gyroscope, gesture, activity,
  and runtime configuration methods are available.
- LED control is RGB rather than RGBW. The accepted integer is `0xRRGGBB`, and
  the on-wire 32-bit value is `0x00RRGGBB`.
- The maximum haptic pattern length is 32 frames.

## End-to-end streaming example

This example sets the RTC, configures the sensors, starts several streams, and
shuts them down cleanly:

```python
import asyncio
from datetime import datetime, timezone

from senswear import SenswearClient


async def main() -> None:
    async with SenswearClient() as device:
        await device.time.set(datetime.now(timezone.utc))

        await device.imu.set_drain_period_ms(100)
        await device.imu.set_physical_streams_enabled(True)

        # PPG IRQ cadence must be configured while sampling is stopped.
        await device.ppg.set_sampling_enabled(False)
        await device.ppg.set_per_sample_irq_enabled(False)
        await device.ppg.set_sampling_enabled(True)

        await device.touch.set_sampling_enabled(True)
        await device.temperature.set_measurement_interval(60)

        await device.imu.subscribe_quaternion(
            lambda sample: print("quat", sample.timestamp_us, sample.to_tuple())
        )
        await device.ppg.subscribe_red(
            lambda sample: print("red", sample.timestamp_ms, sample.value)
        )
        await device.touch.subscribe_gesture(
            lambda sample: print("touch gesture", sample.gesture_type)
        )
        await device.temperature.subscribe(
            lambda sample: print("temperature", sample.temperature_c)
        )

        try:
            await asyncio.sleep(30)
        finally:
            await device.imu.unsubscribe_all()
            await device.ppg.unsubscribe_all()
            await device.touch.unsubscribe_all()
            await device.temperature.unsubscribe()

            await device.imu.set_physical_streams_enabled(False)
            await device.ppg.set_sampling_enabled(False)
            await device.touch.set_sampling_enabled(False)


asyncio.run(main())
```

For production applications, add reconnect logic, bounded queues between BLE
callbacks and storage/processing tasks, and capability detection for optional
hardware services.
