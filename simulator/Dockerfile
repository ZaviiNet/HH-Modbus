# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Inverter Modbus TCP Simulator — Docker image
#
# Build context must be the **repository root** (one level above simulator/):
#
#   docker build -f simulator/Dockerfile -t hh-modbus-simulator .
#
# Or use docker-compose (recommended):
#
#   cd simulator && docker-compose up
# ---------------------------------------------------------------------------
FROM python:3.12-slim

LABEL org.opencontainers.image.title="HH Modbus Inverter Simulator"
LABEL org.opencontainers.image.description="Modbus TCP simulator for the hh_modbus_control Home Assistant integration"
LABEL org.opencontainers.image.source="https://github.com/ZaviiNet/HH-Modbus"

WORKDIR /app

# Install only the Python runtime packages needed by the simulator.
# We intentionally avoid installing the full homeassistant package here —
# the simulator mocks all HA imports at runtime.
RUN pip install --no-cache-dir "pymodbus>=3.11.1" "aiohttp>=3.9"

# Copy the sensor definitions and the simulator itself.
COPY custom_components/ custom_components/
COPY simulator/inverter_simulator.py simulator/inverter_simulator.py

# Modbus TCP port (overridden by MODBUS_PORT env var or docker-compose)
EXPOSE 5020
# Web UI port
EXPOSE 8080

# Environment variable defaults (all overridable at run time)
ENV BRAND=solis \
    MODBUS_PORT=5020 \
    SLAVE=1 \
    WEB_UI_PORT=8080 \
    LOG_LEVEL=WARNING

# Use shell form so environment variable substitution works
CMD python simulator/inverter_simulator.py \
        --brand      "${BRAND}" \
        --port       "${MODBUS_PORT}" \
        --slave      "${SLAVE}" \
        --web-ui-port "${WEB_UI_PORT}" \
        --log-level  "${LOG_LEVEL}"
