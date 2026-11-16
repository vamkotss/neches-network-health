"""Runs the whole generator in the right order and writes every output file."""

import argparse
from dataclasses import replace
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


def config_for(scale: str, seed: int | None = None) -> GeneratorConfig:
    """Pick a run size by name (tiny, dev, or full), optionally with a different seed."""
    sizes = {
        "tiny": GeneratorConfig.tiny,
        "dev": GeneratorConfig.dev,
        "full": GeneratorConfig.full,
    }
    cfg = sizes[scale]()  # call the matching "settings card" builder
    return cfg if seed is None else replace(cfg, seed=seed)  # swap the seed if one was given


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point. Returns the exit code (0 = success)."""
    parser = argparse.ArgumentParser(description="Generate the Neches Network Health dataset.")
    parser.add_argument("--scale", choices=["tiny", "dev", "full"], default="dev", help="run size")
    parser.add_argument("--out", default="data", help="folder to write the files into")
    parser.add_argument("--seed", type=int, default=None, help="replace the default seed")
    args = parser.parse_args(argv)  # reads the options typed after the command
    summary = generate(config_for(args.scale, args.seed), args.out)
    print(
        f"Generated {summary['devices']} devices, {summary['rows']:,} rows, "
        f"{summary['files']} files in {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
