"""Sigenergy inverter configuration.

Credit: TypQxQ/Sigenergy-Local-Modbus (https://github.com/TypQxQ/Sigenergy-Local-Modbus)
Sigenergy ESS communicates over local Modbus TCP.
Plant-level registers start at 30000; inverter-level at 32000; battery at 35000.
"""
from __future__ import annotations

from custom_components.hh_modbus_control.data.enums import InverterFeature, InverterType


class SigenergyInverterConfig:
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


SIGENERGY_INVERTERS = [
    SigenergyInverterConfig(
        model="Sigenergy-5K",
        wattage=[5000],
        phases=1,
    ),
    SigenergyInverterConfig(
        model="Sigenergy-8K",
        wattage=[8000],
        phases=1,
    ),
    SigenergyInverterConfig(
        model="Sigenergy-10K",
        wattage=[10000],
        phases=3,
    ),
    SigenergyInverterConfig(
        model="Sigenergy-15K",
        wattage=[15000],
        phases=3,
    ),
    SigenergyInverterConfig(
        model="Sigenergy-20K",
        wattage=[20000],
        phases=3,
    ),
]
