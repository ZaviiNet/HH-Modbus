"""SolarEdge inverter configuration.

Credit: binsentsu/home-assistant-solaredge-modbus
        (https://github.com/binsentsu/home-assistant-solaredge-modbus)
SolarEdge inverters use Modbus TCP on port 1502 by default (slave address 1).
Registers follow the SunSpec standard (40000+ block).
StorEdge battery and meter registers are also supported.
"""
from __future__ import annotations

from custom_components.hh_modbus_control.data.enums import InverterFeature, InverterType


class SolarEdgeInverterConfig:
    def __init__(
        self,
        model: str,
        wattage: list[int],
        phases: int,
        features: list[InverterFeature] | None = None,
    ):
        if features is None:
            features = []
        self.model = model
        self.wattage = wattage
        self.phases = phases
        self.type = InverterType.HYBRID
        self.features: list[InverterFeature] = [
            InverterFeature.PV,
            InverterFeature.GRID,
        ] + list(features)
        self.wattage_chosen = max(wattage)


# Default Modbus TCP port for SolarEdge inverters
SOLAREDGE_DEFAULT_PORT = 1502

SOLAREDGE_INVERTERS = [
    SolarEdgeInverterConfig(
        model="SolarEdge-Single-Phase",
        wattage=[3000, 3680, 4000, 5000, 6000, 7000, 8000, 9000, 10000],
        phases=1,
    ),
    SolarEdgeInverterConfig(
        model="SolarEdge-Three-Phase",
        wattage=[10000, 12500, 15000, 17000, 20000, 25000, 27600, 33000],
        phases=3,
    ),
    SolarEdgeInverterConfig(
        model="SolarEdge-StorEdge",
        wattage=[3680, 5000, 6000, 7600, 10000],
        phases=1,
        features=[InverterFeature.BATTERY],
    ),
    SolarEdgeInverterConfig(
        model="SolarEdge-StorEdge-3P",
        wattage=[10000, 15000, 17000],
        phases=3,
        features=[InverterFeature.BATTERY],
    ),
]
