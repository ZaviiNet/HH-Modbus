"""Skyline / Duracell G3 inverter configuration.

Credit: iPeel/HA-Skyline (https://github.com/iPeel/HA-Skyline)
Skyline and Duracell G3 inverters communicate over local Modbus TCP.
The Duracell G3 is a rebrand of the Skyline inverter; it uses the same
register map with the exception that the DCDC software version register
is not populated on Duracell G3 units.
"""
from __future__ import annotations

from custom_components.hh_modbus_control.data.enums import InverterFeature, InverterType


class SkylineInverterConfig:
    def __init__(
        self,
        model: str,
        wattage: list[int],
        phases: int,
        has_dcdc_version: bool = True,
        features: list[InverterFeature] | None = None,
    ):
        if features is None:
            features = []
        self.model = model
        self.wattage = wattage
        self.phases = phases
        self.has_dcdc_version = has_dcdc_version
        self.type = InverterType.HYBRID
        self.features: list[InverterFeature] = [
            InverterFeature.PV,
            InverterFeature.BATTERY,
            InverterFeature.GRID,
        ] + list(features)
        self.wattage_chosen = max(wattage)


SKYLINE_INVERTERS = [
    SkylineInverterConfig(
        model="Skyline-3K",
        wattage=[3000],
        phases=1,
        has_dcdc_version=True,
    ),
    SkylineInverterConfig(
        model="Skyline-5K",
        wattage=[5000],
        phases=1,
        has_dcdc_version=True,
    ),
    SkylineInverterConfig(
        model="Skyline-6K",
        wattage=[6000],
        phases=3,
        has_dcdc_version=True,
    ),
    SkylineInverterConfig(
        model="Skyline-10K",
        wattage=[10000],
        phases=3,
        has_dcdc_version=True,
    ),
    # Duracell G3 models — same register map but DCDC version register absent
    SkylineInverterConfig(
        model="Duracell-G3-3K",
        wattage=[3000],
        phases=1,
        has_dcdc_version=False,
    ),
    SkylineInverterConfig(
        model="Duracell-G3-5K",
        wattage=[5000],
        phases=1,
        has_dcdc_version=False,
    ),
    SkylineInverterConfig(
        model="Duracell-G3-6K",
        wattage=[6000],
        phases=3,
        has_dcdc_version=False,
    ),
    SkylineInverterConfig(
        model="Duracell-G3-10K",
        wattage=[10000],
        phases=3,
        has_dcdc_version=False,
    ),
]
