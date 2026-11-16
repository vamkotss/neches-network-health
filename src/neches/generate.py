"""Runs the whole generator in the right order and writes every output file."""

from pathlib import Path

import numpy as np

from neches.config import GeneratorConfig
from neches.defects import (
    plant_clock_skew,
    plant_duplicates,
    plant_late_arrivals,
    plant_silent_devices,
    plant_unit_change,
)
from neches.fleet import build_devices
from neches.planting import plant_behaviors
from neches.records import build_records
from neches.tables import write_devices, write_ground_truth, write_planted_defects
from neches.telemetry import build_baseline
from neches.writer import write_landing


def generate(cfg: GeneratorConfig, out_dir) -> dict[str, int]:
    """Generate the full synthetic dataset into out_dir. Returns a small summary."""
    out_dir = Path(out_dir)
    rng = np.random.default_rng(cfg.seed)  # drives the network: fleet, readings, outages
    defect_rng = np.random.default_rng([cfg.seed, 1])  # a separate stream for data defects

    # 1. The network: devices, healthy readings, then planted outages and degradations.
    devices = build_devices(cfg, rng)
    data = build_baseline(cfg, rng)
    online, truth = plant_behaviors(cfg, devices, data, rng)

    # 2. Flatten into rows, then damage the data. Clock skew goes last so that every
    # answer key records the true event times.
    records = build_records(cfg, devices, data, online)
    records, silent = plant_silent_devices(records, defect_rng)
    records, unit = plant_unit_change(records, cfg, defect_rng)
    records, late = plant_late_arrivals(records, defect_rng)
    records, duplicate = plant_duplicates(records, defect_rng)
    records, skew = plant_clock_skew(records, defect_rng)
    keys = {
        "late_arrival": late,
        "duplicate": duplicate,
        "clock_skew": skew,
        "unit_change": unit,
        "silent_device": silent,
    }

    # 3. Write every output file and count them.
    files = write_landing(records, out_dir)  # the gzip JSONL batches
    files.append(write_devices(devices, out_dir))  # devices.csv
    files.extend(write_ground_truth(truth, out_dir))  # outage and degradation answer keys
    files.append(write_planted_defects(keys, out_dir))  # data-defect answer key
    return {"devices": len(devices), "rows": len(records["device_id"]), "files": len(files)}
