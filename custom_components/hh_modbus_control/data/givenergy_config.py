"""GivEnergy inverter configuration.

Credit: cdpuk/givenergy-local (https://github.com/cdpuk/givenergy-local)
GivEnergy inverters communicate over Modbus TCP on port 8899.
Generation 3 inverters support standard Modbus TCP framing.
Generation 1/2 inverters use a proprietary framing layer and may not be
compatible with this integration without additional configuration.
"""
from __future__ import annotations

from custom_components.hh_modbus_control.data.enums import InverterFeature, InverterType


class GivEnergyInverterConfig:
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
            InverterFeature.BATTERY,
            InverterFeature.GRID,
        ] + list(features)
        self.wattage_chosen = max(wattage)


# Default Modbus TCP port for GivEnergy inverters
GIVENERGY_DEFAULT_PORT = 8899

GIVENERGY_INVERTERS = [
    GivEnergyInverterConfig(
        model="GivEnergy-Hybrid-1P",
        wattage=[3600, 5000, 6000],
        phases=1,
    ),
    GivEnergyInverterConfig(
        model="GivEnergy-Hybrid-3P",
        wattage=[6000, 8000, 10000],
        phases=3,
    ),
    GivEnergyInverterConfig(
        model="GivEnergy-AC-Coupled",
        wattage=[3600, 6000],
        phases=1,
    ),
]
