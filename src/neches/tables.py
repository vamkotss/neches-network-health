"""Writes the small CSV tables: the device list and the ground-truth answer keys."""

import csv
from pathlib import Path

DEVICE_COLUMNS = ["device_id", "olt_id", "pon_port", "region", "model", "install_date"]
OUTAGE_COLUMNS = [
    "event_id",
    "scope",
    "device_id",
    "olt_id",
    "pon_port",
    "start",
    "end",
    "duration_minutes",
]
DEGRADATION_COLUMNS = ["event_id", "device_id", "start", "rate_db_per_day"]


def _write_csv(path: Path, columns: list[str], rows: list[dict]) -> Path:
    """Write rows to a CSV file with a header line. Missing values (None) become empty."""
    path.parent.mkdir(parents=True, exist_ok=True)  # create the folder if needed
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)  # one dict = one row
        writer.writeheader()  # the column names go first, even when there are no rows
        writer.writerows(rows)
    return path


def write_devices(devices: list[dict], out_dir) -> Path:
    """Write devices.csv: one row per device."""
    return _write_csv(Path(out_dir) / "devices.csv", DEVICE_COLUMNS, devices)


def write_ground_truth(truth: dict[str, list[dict]], out_dir) -> list[Path]:
    """Write the answer keys for outages and degradations. Returns the files written."""
    folder = Path(out_dir) / "ground_truth"
    return [
        _write_csv(folder / "outage_events.csv", OUTAGE_COLUMNS, truth["outage_events"]),
        _write_csv(
            folder / "degradation_events.csv", DEGRADATION_COLUMNS, truth["degradation_events"]
        ),
    ]
