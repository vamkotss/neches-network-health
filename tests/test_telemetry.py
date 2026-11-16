import numpy as np

from neches.config import GeneratorConfig
from neches.telemetry import build_baseline, build_timestamps

# Every metric the baseline must produce (names match docs/generator-spec.md).
METRICS = [
    "rx_power_dbm",
    "tx_power_dbm",
    "fec_corrected",
    "fec_uncorrected",
    "bip_errors",
    "latency_ms",
    "packet_loss_pct",
    "temperature_c",
]


def make(seed=20261116):
    # Use the tiny run (50 devices, 1 day) so tests stay fast.
    cfg = GeneratorConfig.tiny()
    return cfg, build_baseline(cfg, np.random.default_rng(seed))


def test_timestamps_start_and_spacing():
    cfg = GeneratorConfig.tiny()
    ts = build_timestamps(cfg)
    assert len(ts) == cfg.readings_per_device
    assert ts[0] == np.datetime64("2026-11-01T00:00:00")
    # Every gap between neighbors is exactly 5 minutes.
    assert (np.diff(ts) == np.timedelta64(5, "m")).all()


def test_every_metric_has_the_right_shape():
    cfg, data = make()
    assert set(data) == set(METRICS)
    for name in METRICS:
        assert data[name].shape == (cfg.n_devices, cfg.readings_per_device), name


def test_rx_power_is_in_a_plausible_range():
    _, data = make()
    assert data["rx_power_dbm"].min() > -26
    assert data["rx_power_dbm"].max() < -10


def test_counters_are_never_negative():
    _, data = make()
    for name in ["fec_corrected", "fec_uncorrected", "bip_errors"]:
        assert data[name].min() >= 0, name


def test_fec_corrected_averages_near_20():
    _, data = make()
    assert 19 < data["fec_corrected"].mean() < 21


def test_latency_and_packet_loss_are_not_negative():
    _, data = make()
    assert data["latency_ms"].min() > 0
    assert data["packet_loss_pct"].min() >= 0


def test_temperature_stays_between_30_and_60():
    _, data = make()
    assert data["temperature_c"].min() > 30
    assert data["temperature_c"].max() < 60


def test_same_seed_gives_identical_numbers():
    _, first = make(seed=1)
    _, second = make(seed=1)
    for name in METRICS:
        assert np.array_equal(first[name], second[name]), name


def test_different_seed_gives_different_numbers():
    _, first = make(seed=1)
    _, second = make(seed=2)
    assert not np.array_equal(first["rx_power_dbm"], second["rx_power_dbm"])
