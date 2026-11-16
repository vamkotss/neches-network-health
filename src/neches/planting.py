"""Plants known problems into healthy data and records an answer key for each one."""

import numpy as np

from neches.config import GeneratorConfig
from neches.telemetry import build_timestamps

DEGRADATION_DB_PER_DAY = 0.5  # affected devices lose this much signal per day
DEGRADED_SHARE = 0.03  # 3% of devices slowly degrade
OUTAGE_SHARE = 0.015  # 1.5% of devices have a single-device outage
PORTS_PER_SHARED_OUTAGE = 5  # one shared-fiber outage per 5 PON ports
DEVICE_OUTAGE_MINUTES = (20, 180)  # shortest and longest single-device outage
PORT_OUTAGE_MINUTES = (30, 240)  # shortest and longest shared-fiber outage


def _pick_outage(cfg: GeneratorConfig, rng: np.random.Generator, bounds: tuple[int, int]):
    """Pick a random outage. Returns (first reading number, readings lost, minutes lost)."""
    step = cfg.interval_minutes  # minutes between readings (5)
    low, high = bounds
    # Duration is a whole number of 5-minute steps, so it lines up with the readings.
    minutes = step * int(rng.integers(low // step, high // step + 1))
    length = minutes // step  # how many readings go missing
    # Latest possible start so the outage still fits inside the data window.
    start = int(rng.integers(0, cfg.readings_per_device - length + 1))
    return start, length, minutes


def plant_behaviors(
    cfg: GeneratorConfig,
    devices: list[dict],
    data: dict[str, np.ndarray],
    rng: np.random.Generator,
) -> tuple[np.ndarray, dict[str, list[dict]]]:
    """Plant degradations and outages. Returns (online table, answer key).

    Degradations edit `data` in place. Outages only mark readings as missing in the
    `online` table (False = the device sent nothing at that time).
    """
    n = cfg.n_devices  # number of devices
    t = cfg.readings_per_device  # readings per device
    per_day = 24 * 60 // cfg.interval_minutes  # readings in one day (288)
    ts = build_timestamps(cfg)  # the reading times
    online = np.ones((n, t), dtype=bool)  # start with every device online
    degradations = []  # answer key: slow degradations
    outages = []  # answer key: outages

    # --- 1. Slow degradation: signal sags a little more every day, errors creep up ---
    n_degraded = round(DEGRADED_SHARE * n)
    rows = sorted(int(r) for r in rng.choice(n, size=n_degraded, replace=False))
    for k, row in enumerate(rows, start=1):
        start = int(rng.integers(0, t // 2))  # degradation begins in the first half
        # Days since the problem began (0 before it starts).
        days = np.maximum(np.arange(t) - start, 0) / per_day
        data["rx_power_dbm"][row] -= DEGRADATION_DB_PER_DAY * days  # signal drops
        data["fec_uncorrected"][row] += rng.poisson(0.5 * days)  # unfixed errors rise
        degradations.append(
            {
                "event_id": f"DEG-{k:04d}",
                "device_id": devices[row]["device_id"],
                "start": str(ts[start]),
                "rate_db_per_day": DEGRADATION_DB_PER_DAY,
            }
        )

    # --- 2. Single-device outages: one device goes dark for a while ---
    n_single = round(OUTAGE_SHARE * n)
    rows = sorted(int(r) for r in rng.choice(n, size=n_single, replace=False))
    for row in rows:
        start, length, minutes = _pick_outage(cfg, rng, DEVICE_OUTAGE_MINUTES)
        online[row, start : start + length] = False  # no readings in this window
        outages.append(
            {
                "event_id": f"OUT-{len(outages) + 1:04d}",
                "scope": "device",
                "device_id": devices[row]["device_id"],
                "olt_id": devices[row]["olt_id"],
                "pon_port": devices[row]["pon_port"],
                "start": str(ts[start]),
                "end": str(ts[start] + np.timedelta64(minutes, "m")),
                "duration_minutes": minutes,
            }
        )

    # --- 3. Shared-fiber outages: every device on one PON port goes dark together ---
    ports = list(dict.fromkeys((d["olt_id"], d["pon_port"]) for d in devices))
    n_shared = len(ports) // PORTS_PER_SHARED_OUTAGE
    chosen = sorted(int(p) for p in rng.choice(len(ports), size=n_shared, replace=False))
    for index in chosen:
        olt_id, pon_port = ports[index]
        members = [
            i for i, d in enumerate(devices) if d["olt_id"] == olt_id and d["pon_port"] == pon_port
        ]
        start, length, minutes = _pick_outage(cfg, rng, PORT_OUTAGE_MINUTES)
        online[members, start : start + length] = False  # the whole port is silent
        outages.append(
            {
                "event_id": f"OUT-{len(outages) + 1:04d}",
                "scope": "pon_port",
                "device_id": None,
                "olt_id": olt_id,
                "pon_port": pon_port,
                "start": str(ts[start]),
                "end": str(ts[start] + np.timedelta64(minutes, "m")),
                "duration_minutes": minutes,
            }
        )

    return online, {"degradation_events": degradations, "outage_events": outages}
