"""Guard against relying on private Home Assistant helpers that move or disappear.

``homeassistant.helpers.template.is_number`` was removed from the template helper
namespace in recent Home Assistant releases, which made the integration fail to load
its config flow:

    Error occurred loading flow for integration hh_modbus_control: cannot import name
    'is_number' from 'homeassistant.helpers.template'

Both integrations now ship a local ``is_number`` in their own helpers module.

The import check runs in a subprocess so that it can hide ``is_number`` from Home
Assistant's template module without touching the pytest process (re-importing
``sys.modules`` entries in-process leaks module duplicates into unrelated tests).
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

MODULES = [
    "custom_components.hh_modbus_control.helpers",
    "custom_components.hh_modbus_control.modbus_controller",
    "custom_components.hh_modbus_control.sensors.solis_number_sensor",
    "custom_components.solis_modbus.helpers",
    "custom_components.solis_modbus.modbus_controller",
    "custom_components.solis_modbus.sensors.solis_number_sensor",
]

_IMPORT_PROBE = """
import importlib
import sys

sys.path.insert(0, {root!r})

import homeassistant.helpers.template as ha_template

# Simulate a Home Assistant version where this private helper no longer exists.
if hasattr(ha_template, "is_number"):
    del ha_template.is_number

importlib.import_module({module!r})
print("imported-ok")
"""


@pytest.mark.parametrize("module_name", MODULES)
def test_module_imports_without_ha_template_is_number(module_name):
    """Each integration module must import with the removed HA helper hidden."""
    probe = _IMPORT_PROBE.format(root=str(REPO_ROOT), module=module_name)
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        cwd=REPO_ROOT,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"{module_name} failed to import:\n{result.stderr}"
    assert "imported-ok" in result.stdout


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (42, True),
        (42.5, True),
        ("33000", True),
        ("-3.5", True),
        ("1e3", True),
        (True, True),
        (None, False),
        ("", False),
        ("abc", False),
        ("12abc", False),
        (float("nan"), False),
        (float("inf"), False),
        ([1], False),
    ],
)
def test_local_is_number_matches_ha_semantics(value, expected):
    """The local helper keeps the old float + isfinite behaviour."""
    from custom_components.hh_modbus_control.helpers import is_number as hh_is_number
    from custom_components.solis_modbus.helpers import is_number as solis_is_number

    assert hh_is_number(value) is expected
    assert solis_is_number(value) is expected
