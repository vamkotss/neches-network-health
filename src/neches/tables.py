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


PLANTED_COLUMNS = ["defect_type", "device_id", "event_time", "detail"]
# For each defect: which answer-key field holds its time (None = affects a whole device).
TIME_FIELDS = {
    "late_arrival": "event_time",
    "duplicate": "event_time",
    "clock_skew": None,
    "unit_change": "change_time",
    "silent_device": "start",
}


def write_planted_defects(keys: dict[str, dict], out_dir) -> Path:
    """Write ground_truth/planted_defects.csv: one line per damaged row or device."""
    rows = []
    for defect_type, key in keys.items():  # one answer key per defect type
        time_field = TIME_FIELDS[defect_type]  # which field holds the time (or None)
        # Everything except the device and the time goes into the "detail" text.
        extras = [name for name in key if name not in ("device_id", time_field)]
        for i in range(len(key["device_id"])):  # one line per damaged item
            rows.append(
                {
                    "defect_type": defect_type,
                    "device_id": str(key["device_id"][i]),
                    "event_time": str(key[time_field][i]) if time_field else "",
                    "detail": ";".join(f"{name}={key[name][i]}" for name in extras),
                }
            )
    path = Path(out_dir) / "ground_truth" / "planted_defects.csv"
    return _write_csv(path, PLANTED_COLUMNS, rows)
