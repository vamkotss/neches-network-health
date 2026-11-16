"""Planted data defects. Each function returns the damaged rows plus an answer key."""

import numpy as np

from neches.config import GeneratorConfig

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


SKEW_SHARE = 0.01  # 1% of devices have a wrong clock
SKEW_MINUTES = 37  # their clocks run this many minutes behind
UNIT_CHANGE_SHARE = 0.15  # 15% of devices get the firmware upgrade
UNIT_CHANGE_DAY = 7  # the upgrade lands after 7 full days (start of day 8)
SILENT_SHARE = 0.006  # 0.6% of devices go quiet
SILENT_HOURS = (6, 36)  # for 6 to 36 hours


def _pick_devices(records: dict[str, np.ndarray], share: float, rng: np.random.Generator):
    """Pick a share of the devices at random (always at least one). Returns sorted ids."""
    ids = np.unique(records["device_id"])  # every device name once, sorted
    count = max(1, round(share * len(ids)))  # how many devices to pick
    return np.sort(rng.choice(ids, size=count, replace=False))


def plant_clock_skew(
    records: dict[str, np.ndarray], rng: np.random.Generator
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Some devices stamp every reading 37 minutes too early. Arrival time stays true."""
    out = {name: values.copy() for name, values in records.items()}  # never touch the input
    chosen = _pick_devices(out, SKEW_SHARE, rng)  # the devices with a bad clock
    rows = np.isin(out["device_id"], chosen)  # True for every row from those devices
    out["event_time"][rows] = out["event_time"][rows] - np.timedelta64(SKEW_MINUTES, "m")
    key = {
        "device_id": chosen,  # which devices have the wrong clock
        "skew_minutes": np.full(len(chosen), SKEW_MINUTES),  # how far behind they run
    }
    return out, key


def plant_unit_change(
    records: dict[str, np.ndarray], cfg: GeneratorConfig, rng: np.random.Generator
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """After a firmware upgrade, some devices report power in milliwatts instead of dBm."""
    out = {name: values.copy() for name, values in records.items()}  # never touch the input
    chosen = _pick_devices(out, UNIT_CHANGE_SHARE, rng)  # the devices that upgrade
    # The upgrade moment: the start date plus 7 full days (so day 8 begins).
    start = np.datetime64(cfg.start.replace(tzinfo=None), "s")
    cutoff = start + np.timedelta64(UNIT_CHANGE_DAY, "D")
    # Only rows from chosen devices at or after the upgrade moment change.
    rows = np.isin(out["device_id"], chosen) & (out["event_time"] >= cutoff)
    out["firmware"][rows] = "2.5.0"  # new software version
    for name in ("rx_power_dbm", "tx_power_dbm"):
        # dBm to milliwatts: mW = 10 ** (dBm / 10). The numbers look small but plausible.
        out[name][rows] = 10 ** (out[name][rows] / 10)
    key = {
        "device_id": chosen,  # which devices changed units
        "change_time": np.full(len(chosen), cutoff),  # when it happened
        "firmware": np.full(len(chosen), "2.5.0"),  # the new version
    }
    return out, key


def plant_silent_devices(
    records: dict[str, np.ndarray], rng: np.random.Generator
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Some devices send nothing for 6 to 36 hours, with no outage record anywhere."""
    chosen = _pick_devices(records, SILENT_SHARE, rng)  # the devices that go quiet
    first = records["event_time"].min()  # the first moment in the data
    span = int((records["event_time"].max() - first) / np.timedelta64(1, "m"))  # minutes
    keep = np.ones(len(records["device_id"]), dtype=bool)  # True = keep the row
    starts, ends, hours = [], [], []  # answer key pieces
    for device in chosen:
        low, high = SILENT_HOURS
        # Length in whole 5-minute steps, from 6 hours up to 36 hours.
        minutes = 5 * int(rng.integers(low * 12, high * 12 + 1))
        minutes = min(minutes, span)  # never longer than the data itself
        # Random start so the silence fits inside the data window.
        offset = 5 * int(rng.integers(0, (span - minutes) // 5 + 1))
        start = first + np.timedelta64(offset, "m")
        end = start + np.timedelta64(minutes, "m")
        inside = (records["event_time"] >= start) & (records["event_time"] < end)
        keep &= ~((records["device_id"] == device) & inside)  # drop that device's rows
        starts.append(start)
        ends.append(end)
        hours.append(minutes / 60)
    out = {name: values[keep] for name, values in records.items()}
    key = {
        "device_id": chosen,  # which devices went quiet
        "start": np.array(starts),  # when the silence began
        "end": np.array(ends),  # when it ended
        "hours": np.array(hours),  # how long it lasted
    }
    return out, key
