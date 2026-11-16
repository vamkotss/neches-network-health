"""Turns the device-by-time tables into a flat list of rows (one row per reading sent)."""

import numpy as np

from neches.config import GeneratorConfig
from neches.telemetry import build_timestamps


def build_records(
    cfg: GeneratorConfig,
    devices: list[dict],
    data: dict[str, np.ndarray],
    online: np.ndarray,
) -> dict[str, np.ndarray]:
    """Return one column array per field. Each position across the arrays is one row."""
    ts = build_timestamps(cfg)  # the reading times
    # np.nonzero lists the (device, time) positions where the device was online.
    # Offline positions (outages) are skipped, so they leave real gaps.
    rows, cols = np.nonzero(online)
    ids = np.array([d["device_id"] for d in devices])  # device names, in table order

    records = {
        "device_id": ids[rows],  # which device sent this row
        "event_time": ts[cols],  # when the reading happened
        "arrival_time": ts[cols].copy(),  # when it reached us (same, until defects)
        "firmware": np.full(len(rows), "2.4.1"),  # software version (same for everyone)
    }
    # Copy each metric's value at every online (device, time) position.
    for name, table in data.items():
        records[name] = table[rows, cols]
    return records
