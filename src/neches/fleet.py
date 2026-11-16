"""Builds the fleet: a list of fictional fiber devices (ONTs) wired to OLTs and PON ports."""

# date and timedelta: used to pick random install dates.
from datetime import date, timedelta

# numpy: the math library; Generator is its seeded random-number machine.
import numpy as np

from neches.config import GeneratorConfig

# Region names are fictional Texas-style labels. One region per OLT, cycling through the list.
REGIONS = ["Panhandle", "Gulf Coast", "Hill Country", "Piney Woods"]

# Made-up device models (not real products).
MODELS = ["NX-100", "NX-200", "NX-300"]

# Install dates are spread randomly between these two days.
INSTALL_START = date(2022, 1, 1)
INSTALL_END = date(2026, 6, 30)


def build_devices(cfg: GeneratorConfig, rng: np.random.Generator) -> list[dict]:
    """Return one dict per device. All randomness comes from `rng`, so the seed controls it."""
    n = cfg.n_devices
    span_days = (INSTALL_END - INSTALL_START).days

    # Draw all random numbers up front, in a fixed order, so the result never depends
    # on anything else. One random day-offset and one random model index per device.
    day_offsets = rng.integers(0, span_days + 1, size=n)
    model_indexes = rng.integers(0, len(MODELS), size=n)

    devices = []
    counter = 0  # running device number: 0, 1, 2, ...
    for olt in range(cfg.olts):  # loop over every OLT
        for port in range(1, cfg.ports_per_olt + 1):  # loop over its PON ports (1, 2, 3, ...)
            for _ in range(cfg.devices_per_port):  # loop over devices sharing this port
                install = INSTALL_START + timedelta(days=int(day_offsets[counter]))
                devices.append(
                    {
                        "device_id": f"ONT-{counter + 1:06d}",  # ONT-000001, ONT-000002, ...
                        "olt_id": f"OLT-{olt + 1:02d}",  # OLT-01, OLT-02, ...
                        "pon_port": port,
                        "region": REGIONS[olt % len(REGIONS)],
                        "model": MODELS[int(model_indexes[counter])],
                        "install_date": install.isoformat(),  # text like 2024-03-09
                    }
                )
                counter += 1
    return devices
