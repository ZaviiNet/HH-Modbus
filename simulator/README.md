# Inverter Modbus TCP Simulator

A standalone Python tool that simulates any inverter brand supported by **hh_modbus_control**. It starts a Modbus TCP server and responds to register reads with realistic default values, allowing the Home Assistant integration to be tested without physical hardware.

An optional **Web UI** lets you view and change simulated register values live in your browser — handy for testing how the integration reacts to different inverter states.

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

---

## Quick Start with Docker (recommended)

Docker is the easiest way to run the simulator — no Python installation required on your host.

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)

### Run

```bash
# From the simulator/ directory:
cd simulator

# Start the default Solis simulator (Modbus on :5020, Web UI on :8080)
docker-compose up

# Simulate a different brand
BRAND=givenergy docker-compose up

# Custom ports
BRAND=sunsynk MODBUS_PORT=5021 WEB_UI_PORT=8081 docker-compose up
```

The simulator is ready when you see:

```
🔌  Modbus TCP simulator ready
    Brand  : solis
    Address: 0.0.0.0:5020  (slave=1)
    HR populated: 471 registers
    Web UI : http://0.0.0.0:8080
```

Open **http://localhost:8080** in your browser to access the Web UI.

### Docker Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BRAND` | `solis` | Inverter brand to simulate |
| `MODBUS_PORT` | `5020` | Modbus TCP port |
| `SLAVE` | `1` | Modbus slave / device ID |
| `WEB_UI_PORT` | `8080` | Web UI HTTP port |
| `LOG_LEVEL` | `WARNING` | Python logging level |

### Build the image manually

```bash
# From the repository root:
docker build -f simulator/Dockerfile -t hh-modbus-simulator .
docker run --rm -p 5020:5020 -p 8080:8080 \
    -e BRAND=solis hh-modbus-simulator
```

---

## Running without Docker

### Requirements

- Python 3.12+
- `pymodbus` ≥ 3.11 (already a project dependency)
- `aiohttp` ≥ 3.9 — **only required when using the Web UI**

Install dependencies from the repository root before running:

```bash
uv sync
# For the Web UI also install aiohttp:
pip install aiohttp   # or: uv add aiohttp
```

### Usage

Run from the repository root:

```bash
# Simulate a Solis inverter on a non-privileged port
uv run python simulator/inverter_simulator.py --brand solis --port 5020

# Same, but with the Web UI enabled
uv run python simulator/inverter_simulator.py --brand solis --port 5020 --web-ui-port 8080

# Simulate a GivEnergy inverter (default port 8899)
uv run python simulator/inverter_simulator.py --brand givenergy

# Bind to a specific IP, custom slave address, with verbose register output
uv run python simulator/inverter_simulator.py \
    --brand sunsynk --host 192.168.1.50 --port 5020 --slave 2 --verbose
```

### All Options

```
usage: inverter_simulator.py [-h] --brand BRAND [--host HOST] [--port PORT]
                              [--slave SLAVE] [--verbose]
                              [--log-level {DEBUG,INFO,WARNING,ERROR}]
                              [--web-ui-port PORT]

  --brand BRAND        Inverter brand to simulate.
                       Choices: deye, duracell, givenergy, sigenergy, solaredge, solis, skyline, sunsynk
  --host HOST          IP address to listen on (default: 0.0.0.0)
  --port PORT          Modbus TCP port (default: brand-specific, e.g. 8899 for GivEnergy)
  --slave SLAVE        Modbus slave / device ID to answer on (default: 1)
  --verbose            Print all populated register addresses and values on startup
  --log-level LEVEL    Logging verbosity (default: WARNING)
  --web-ui-port PORT   Enable the Web UI on this HTTP port (e.g. 8080). Disabled by default.
```

---

## Web UI

When `--web-ui-port` is supplied (or `WEB_UI_PORT` is set in Docker), the simulator also starts a small HTTP server. Open the URL printed on startup in your browser:

```
http://localhost:8080
```

The Web UI shows every sensor group as a collapsible table.  
You can **edit any numeric register value** inline — changes take effect immediately on the live Modbus server, so the next poll from Home Assistant (or any Modbus client) will return the new value.

### Features

- **Search / filter** sensors by name
- **Collapsible groups** — each sensor group folds independently
- **Live editing** — type a new display value and press Enter (or wait for the debounce); the register is updated instantly
- **Hidden registers** — hidden/reserve registers are filtered out by default; toggle *"Show hidden / reserve registers"* to reveal them
- **Visual feedback** — the edited field flashes green on success or red on error, and a toast notification confirms each update

---

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

---

## Connecting the Home Assistant Integration

1. Start the simulator (Docker or directly):

   ```bash
   # Docker
   cd simulator && docker-compose up

   # or directly
   uv run python simulator/inverter_simulator.py --brand solis --port 5020
   ```

2. In Home Assistant, add the **HH Modbus Control** integration:
   - **Host**: the IP address of the machine running the simulator
   - **Port**: the port you specified (e.g. `5020`)
   - **Brand**: matching brand (e.g. `Solis`)
   - **Slave**: `1` (or whatever you passed to `--slave`)
   - **Serial**: any string (e.g. `SIM00001`)

3. The integration will poll the simulator and populate sensor states with the simulated values.

4. Use the Web UI at **http://localhost:8080** to change values and observe the integration react in real time.

---

## How It Works

The script:

1. Mocks the `homeassistant` Python package so the sensor definition files can be imported without a running Home Assistant instance.
2. Imports all sensor group definitions from `custom_components/hh_modbus_control/sensor_data/`.
3. Walks every sensor entity, computes a realistic raw register value from the sensor's unit, device class, and scaling multiplier.
4. Builds contiguous `SimData` blocks and serves them via a `pymodbus` Modbus TCP server.
5. Optionally starts an `aiohttp` HTTP server (the Web UI) that allows live register updates via a browser.

Stopping the simulator (Ctrl+C) is clean — both servers shut down gracefully.
