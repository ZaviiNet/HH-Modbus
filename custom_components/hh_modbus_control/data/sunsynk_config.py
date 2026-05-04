from __future__ import annotations

from custom_components.hh_modbus_control.data.enums import InverterFeature, InverterType


class SunsynkInverterConfig:
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
        self.features: list[InverterFeature] = [InverterFeature.PV, InverterFeature.BATTERY, InverterFeature.GRID] + list(features)
        self.wattage_chosen = max(wattage)


SUNSYNK_INVERTERS = [
    SunsynkInverterConfig(
        model="SUN-5K-SG01LP1",
        wattage=[5000],
        phases=1,
    ),
    SunsynkInverterConfig(
        model="SUN-8K-SG01LP1",
        wattage=[8000],
        phases=1,
    ),
    SunsynkInverterConfig(
        model="SUN-5K-SG01LP1-AU",
        wattage=[5000],
        phases=1,
    ),
    SunsynkInverterConfig(
        model="SUN-6K-OG01LP1",
        wattage=[6000],
        phases=1,
    ),
    SunsynkInverterConfig(
        model="DEYE-5K-SG01LP1",
        wattage=[5000],
        phases=1,
    ),
    SunsynkInverterConfig(
        model="DEYE-8K-SG01LP1",
        wattage=[8000],
        phases=1,
    ),
]
