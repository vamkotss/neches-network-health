"""Planted data defects. Each function returns the damaged rows plus an answer key."""

import numpy as np

LATE_SHARE = 0.04  # 4% of rows arrive late
LATE_MINUTES = (60, 360)  # late by 1 to 6 hours
DUPLICATE_SHARE = 0.015  # 1.5% of rows are sent twice


def plant_late_arrivals(
    records: dict[str, np.ndarray], rng: np.random.Generator
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Make some rows arrive hours after they happened. Only arrival_time changes."""
    out = {name: values.copy() for name, values in records.items()}  # never touch the input
    n_rows = len(out["device_id"])  # how many rows there are
    n_late = round(LATE_SHARE * n_rows)  # how many rows to delay
    # Pick which rows are late (sorted so the answer key reads in order).
    rows = np.sort(rng.choice(n_rows, size=n_late, replace=False))
    # Delay in whole 5-minute steps, from 60 up to 360 minutes.
    steps = rng.integers(LATE_MINUTES[0] // 5, LATE_MINUTES[1] // 5 + 1, size=n_late)
    delay = 5 * steps  # minutes late, one number per late row
    # New arrival time = when it happened + the delay.
    out["arrival_time"][rows] = out["event_time"][rows] + delay.astype("timedelta64[m]")
    key = {
        "device_id": out["device_id"][rows],  # which device sent the late row
        "event_time": out["event_time"][rows],  # when the reading really happened
        "delay_minutes": delay,  # how late it arrived
    }
    return out, key


def plant_duplicates(
    records: dict[str, np.ndarray], rng: np.random.Generator
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Send some rows twice. The extra copies are exact and are added at the end."""
    n_rows = len(records["device_id"])  # how many rows there are
    n_dup = round(DUPLICATE_SHARE * n_rows)  # how many rows to repeat
    # Pick which rows get repeated (sorted so the answer key reads in order).
    rows = np.sort(rng.choice(n_rows, size=n_dup, replace=False))
    # For every column: the original values, then the chosen rows again.
    out = {name: np.concatenate([values, values[rows]]) for name, values in records.items()}
    key = {
        "device_id": records["device_id"][rows].copy(),  # which device's row was repeated
        "event_time": records["event_time"][rows].copy(),  # which reading was repeated
    }
    return out, key
