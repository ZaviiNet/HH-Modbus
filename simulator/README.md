# Inverter Modbus TCP Simulator

A standalone Python tool that simulates any inverter brand supported by **hh_modbus_control**. It starts a Modbus TCP server and responds to register reads with realistic default values, allowing the Home Assistant integration to be tested without physical hardware.

## Supported Brands

| Brand | Default Port | Notes |
|-------|-------------|-------|
| `solis` | 502 | Hybrid and string inverters (471 holding registers) |
| `sunsynk` | 502 | Sun-Synk single-phase hybrid |
| `deye` | 502 | Deye (same register map as Sun-Synk) |
| `givenergy` | 8899 | GivEnergy (input + holding registers) |
| `sigenergy` | 502 | Sigenergy ESS plant-level registers |
| `solaredge` | 1502 | SolarEdge SunSpec Modbus |
| `skyline` | 502 | Skyline hybrid inverter |
| `duracell` | 502 | Duracell G3 (rebranded Skyline) |

## Requirements

- Python 3.12+
- `pymodbus` ≥ 3.11 (already a project dependency)

The simulator has **no additional dependencies** beyond what the project already requires.

Install dependencies from the repository root before running:

```bash
uv sync
```

## Usage

Run from the repository root:

```bash
# Simulate a Solis inverter on the default port (502)
# Note: port 502 requires root/administrator privileges on most systems.
sudo -E uv run python simulator/inverter_simulator.py --brand solis

# Use a non-privileged port for testing
uv run python simulator/inverter_simulator.py --brand solis --port 5020

# Simulate a GivEnergy inverter on its default port (8899)
uv run python simulator/inverter_simulator.py --brand givenergy

# Simulate a SolarEdge inverter on port 1502
uv run python simulator/inverter_simulator.py --brand solaredge

# Bind to a specific IP, custom slave address, with verbose output
uv run python simulator/inverter_simulator.py --brand sunsynk --host 192.168.1.50 --port 5020 --slave 2 --verbose
```

### All Options

```
usage: inverter_simulator.py [-h] --brand BRAND [--host HOST] [--port PORT]
                              [--slave SLAVE] [--verbose] [--log-level {DEBUG,INFO,WARNING,ERROR}]

  --brand BRAND   Inverter brand to simulate.
                  Choices: deye, duracell, givenergy, sigenergy, solaredge, solis, skyline, sunsynk
  --host HOST     IP address to listen on (default: 0.0.0.0)
  --port PORT     Modbus TCP port (default: brand-specific, e.g. 8899 for GivEnergy)
  --slave SLAVE   Modbus slave / device ID to answer on (default: 1)
  --verbose       Print all populated register addresses and values on startup
  --log-level     Logging verbosity (default: WARNING)
```

## Simulated Values

The simulator populates registers with realistic default values based on each sensor's unit and device class:

| Sensor Type | Simulated Value |
|-------------|----------------|
| Grid Voltage | 230.0 V |
| PV / DC Voltage | 380.0 V |
| Battery Voltage | 52.0 V |
| Current | 10.0 A |
| Power | 3 000 W |
| Frequency | 50.0 Hz |
| Temperature | 25.0 °C |
| Battery SOC | 75 % |
| Energy | 500 kWh |
| Time | 12 (hours / minutes / seconds) |
| Status / version | 1 |
| Serial / model strings | `SIMULATOR-HH` (ASCII-encoded) |

## Connecting the Home Assistant Integration

1. Start the simulator on your machine (or a Docker container):

   ```bash
   uv run python simulator/inverter_simulator.py --brand solis --port 5020
   ```

2. In Home Assistant, add the **HH Modbus Control** integration:
   - **Host**: the IP address of the machine running the simulator
   - **Port**: the port you specified (e.g. `5020`)
   - **Brand**: matching brand (e.g. `Solis`)
   - **Slave**: `1` (or whatever you passed to `--slave`)
   - **Serial**: any string (e.g. `SIM00001`)

3. The integration will poll the simulator and populate sensor states with the simulated values.

## How It Works

The script:

1. Mocks the `homeassistant` Python package so the sensor definition files can be imported without a running Home Assistant instance.
2. Imports all sensor group definitions from `custom_components/hh_modbus_control/sensor_data/`.
3. Walks every sensor entity, computes a realistic raw register value from the sensor's unit, device class, and scaling multiplier.
4. Builds contiguous `SimData` blocks and serves them via a `pymodbus` Modbus TCP server.

Stopping the simulator (Ctrl+C) is clean — the server shuts down gracefully.
