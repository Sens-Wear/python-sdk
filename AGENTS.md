# AGENTS.md

## Project overview

This is the Python 3.10+ SDK for SensWear devices. It uses `bleak` for transport and exposes
typed, asynchronous modules for battery, power, time, temperature, IMU, PPG, touch, LED, and
haptic services. The package uses a `src/` layout and Hatchling.

The firmware repository's Bluetooth implementations are the wire-protocol source of truth.
`README.md` is also the public protocol and application-developer guide; keep it precise.

## Repository map

- `src/senswear/client.py`: discovery, connection lifecycle, and low-level GATT operations.
- `src/senswear/uuids.py`: characteristic/service UUID registry.
- `src/senswear/modules/`: typed parsers, encoders, enums, and module APIs.
- `src/senswear/modules/_common.py`: shared binary/validation helpers.
- `src/senswear/__init__.py`: public package surface.
- `tests/`: protocol and client tests that run without physical BLE hardware.
- `examples/`: small executable usage examples.
- `dist/`: generated package output; regenerate rather than hand-edit.

## Setup and commands

Create and activate a virtual environment, then install development dependencies:

```sh
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Run all tests:

```sh
python -m pytest
```

Build distributions:

```sh
python -m build
```

Optional package validation:

```sh
python -m twine check dist/*
```

Use `python -m ...` so commands use the active interpreter. Do not publish to PyPI or connect to
physical hardware unless explicitly requested.

## Code conventions

- Use four spaces, type annotations, descriptive names, and standard Python naming.
- Public BLE APIs are `async`; do not hide blocking I/O inside them.
- Keep parsing/encoding pure and deterministic so it can be tested without a device.
- Accept `bytes`-like inputs consistently and reject incorrect lengths with `ProtocolError`.
- Validate application input before a GATT write; use `TypeError` for wrong kinds and
  `ValueError`/`RangeError`-equivalent validation consistent with nearby code.
- Preserve raw protocol values when useful, but expose documented unit conversions as explicit
  properties.
- Export new public classes/enums through `modules/__init__.py` and `senswear/__init__.py`.
- Maintain compatibility aliases only when they do not misrepresent the new firmware.

## Bluetooth protocol changes

Never infer a payload from an old SDK implementation. Inspect the matching firmware service
under the firmware repository's `src/bluetooth/`.

For every interface change, update:

1. `uuids.py` and characteristic-to-service mapping.
2. The typed module parser/encoder and exact length constants.
3. `SenswearClient` module exposure when adding a service.
4. Public exports.
5. Unit tests, including valid packets, boundary values, malformed lengths, and writes.
6. Examples and the README's API, units, enum meaning, GATT properties, and wire-layout tables.
7. Package version when the public contract changes.

Binary rules must be explicit: little-endian fields, signedness, packed padding, timestamp
epoch/unit, scaling, optional flags, and unknown sentinels. Preserve 64-bit integer timestamps
as Python integers.

Keep behavior aligned with the TypeScript SDK. Naming may be idiomatic per language, but UUIDs,
layouts, units, limits, and validation semantics must agree.

## Testing guidance

- Add focused tests in `tests/test_<module>.py`.
- Tests must not require a BLE adapter or device unless clearly marked as integration tests.
- Use fake clients for read/write/subscribe routing.
- Test notification parsing with the same payload parser used by reads.
- Test the endpoint registry when adding or removing characteristics.
- Run the full suite after changes to shared helpers, client lifecycle, UUIDs, or exports.

## Documentation

The README should tell an application developer what every field means, its unit/range, whether
it is raw or derived, and whether a characteristic is read/write/notify/indicate. Document
firmware rounding, startup defaults, configuration ordering, and known limitations. Do not
describe raw PPG as heart rate or SpO2, raw gyroscope values as physical units without a
declared scale, or accelerometer data as gravity-free when firmware includes gravity.

## Safety and repository hygiene

- Do not edit `dist/` directly or commit virtual environments/caches.
- Do not perform real BLE writes, LED/haptic activation, clock setting, or device configuration
  during unit tests.
- Preserve unrelated working-tree changes.
- Run `git diff --check` before handoff.

## Completion checklist

- `python -m pytest` passes.
- `python -m build` succeeds for packaging changes.
- New interfaces are exported, tested, exemplified, and documented.
- Protocol behavior matches firmware and the TypeScript SDK.
