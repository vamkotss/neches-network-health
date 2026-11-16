"""Healthy ("baseline") telemetry: what the network looks like before any problems are planted."""

import numpy as np

from neches.config import GeneratorConfig


def build_timestamps(cfg: GeneratorConfig) -> np.ndarray:
    """Return the reading times: start, start + 5 min, start + 10 min, ..."""
    # numpy dates have no timezone, so drop it (our start time is already UTC).
    start = np.datetime64(cfg.start.replace(tzinfo=None), "s")
    # The gap between two readings (5 minutes).
    step = np.timedelta64(cfg.interval_minutes, "m")
    # 0, 1, 2, ... 4031 steps after the start.
    return start + np.arange(cfg.readings_per_device) * step


def build_baseline(cfg: GeneratorConfig, rng: np.random.Generator) -> dict[str, np.ndarray]:
    """Return one table per metric. Rows = devices, columns = reading times."""
    n = cfg.n_devices  # number of rows
    t = cfg.readings_per_device  # number of columns
    shape = (n, t)  # the size of every table

    # Received light power: each device has its own typical level (like a house far from
    # or close to the box), clipped to a sane range, plus a little wobble per reading.
    device_rx = np.clip(rng.normal(-19, 1.5, size=(n, 1)), -24, -12)
    rx_power = device_rx + rng.normal(0, 0.3, size=shape)

    # Transmit power: close to 2.5 dBm with small variation.
    tx_power = rng.normal(2.5, 0.3, size=shape)

    # Error counters: Poisson is the standard shape for "how many rare events happened".
    fec_corrected = rng.poisson(20, size=shape)  # fixed errors: about 20 per reading
    fec_uncorrected = rng.poisson(0.01, size=shape)  # unfixed errors: almost always 0
    bip_errors = rng.poisson(2, size=shape)  # bit-parity errors: about 2 per reading

    # Delay: lognormal is always positive with a long tail; median is 8 ms.
    latency = rng.lognormal(mean=np.log(8), sigma=0.2, size=shape)

    # Packet loss percent: always positive, averages about 0.01.
    packet_loss = rng.exponential(0.01, size=shape)

    # Temperature: a daily wave between 35 and 55 C, shifted differently per device.
    minutes = np.arange(t) * cfg.interval_minutes  # minutes since the start
    angle = 2 * np.pi * minutes / (24 * 60)  # one full wave per day
    phase = rng.uniform(0, 2 * np.pi, size=(n, 1))  # each device starts at its own point
    temperature = 45 + 10 * np.sin(angle + phase) + rng.normal(0, 0.5, size=shape)

    return {
        "rx_power_dbm": rx_power,
        "tx_power_dbm": tx_power,
        "fec_corrected": fec_corrected,
        "fec_uncorrected": fec_uncorrected,
        "bip_errors": bip_errors,
        "latency_ms": latency,
        "packet_loss_pct": packet_loss,
        "temperature_c": temperature,
    }
