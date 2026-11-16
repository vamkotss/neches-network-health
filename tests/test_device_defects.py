import numpy as np

from neches.config import GeneratorConfig
from neches.defects import plant_clock_skew, plant_silent_devices, plant_unit_change
from neches.fleet import build_devices
from neches.planting import plant_behaviors
from neches.records import build_records
from neches.telemetry import build_baseline


def make_records(seed=20261116):
    # Small 10-day fleet (20 devices), long enough to contain day 8 and a 36-hour silence.
    cfg = GeneratorConfig(olts=1, ports_per_olt=2, devices_per_port=10, days=10)
    rng = np.random.default_rng(seed)
    devices = build_devices(cfg, rng)
    data = build_baseline(cfg, rng)
    online, _ = plant_behaviors(cfg, devices, data, rng)
    return cfg, build_records(cfg, devices, data, online)


def test_clock_skew_hits_the_expected_number_of_devices():
    cfg, rec = make_records()
    _out, key = plant_clock_skew(rec, np.random.default_rng(5))
    assert len(key["device_id"]) == max(1, round(0.01 * cfg.n_devices))
    assert set(key["skew_minutes"].tolist()) == {37}


def test_skewed_devices_stamp_37_minutes_early():
    _, rec = make_records()
    out, key = plant_clock_skew(rec, np.random.default_rng(5))
    skewed = np.isin(rec["device_id"], key["device_id"])
    shift = (rec["event_time"] - out["event_time"]) / np.timedelta64(1, "m")
    assert (shift[skewed] == 37).all()
    assert (shift[~skewed] == 0).all()
    assert np.array_equal(out["arrival_time"], rec["arrival_time"])


def test_unit_change_hits_15_percent_of_devices():
    cfg, rec = make_records()
    _out, key = plant_unit_change(rec, cfg, np.random.default_rng(5))
    assert len(key["device_id"]) == round(0.15 * cfg.n_devices)


def test_unit_change_switches_power_to_milliwatts_from_day_8():
    cfg, rec = make_records()
    out, key = plant_unit_change(rec, cfg, np.random.default_rng(5))
    cutoff = np.datetime64("2026-11-08T00:00:00")
    changed = np.isin(rec["device_id"], key["device_id"]) & (rec["event_time"] >= cutoff)
    assert changed.any()
    assert set(out["firmware"][changed].tolist()) == {"2.5.0"}
    assert np.allclose(out["rx_power_dbm"][changed], 10 ** (rec["rx_power_dbm"][changed] / 10))
    assert np.allclose(out["tx_power_dbm"][changed], 10 ** (rec["tx_power_dbm"][changed] / 10))
    # Every other value in every column is untouched.
    for name in rec:
        assert np.array_equal(out[name][~changed], rec[name][~changed]), name


def test_silent_devices_are_6_to_36_hours():
    cfg, rec = make_records()
    _out, key = plant_silent_devices(rec, np.random.default_rng(5))
    assert len(key["device_id"]) == max(1, round(0.006 * cfg.n_devices))
    assert key["hours"].min() >= 6
    assert key["hours"].max() <= 36


def test_silent_devices_send_nothing_in_their_window():
    _, rec = make_records()
    out, key = plant_silent_devices(rec, np.random.default_rng(5))
    removed = 0
    for i in range(len(key["device_id"])):
        start, end = key["start"][i], key["end"][i]
        mine = rec["device_id"] == key["device_id"][i]
        inside = (rec["event_time"] >= start) & (rec["event_time"] < end)
        removed += int((mine & inside).sum())
        mine_out = out["device_id"] == key["device_id"][i]
        inside_out = (out["event_time"] >= start) & (out["event_time"] < end)
        assert not (mine_out & inside_out).any()
    assert len(out["device_id"]) == len(rec["device_id"]) - removed


def test_same_seed_gives_identical_device_defects():
    _, rec = make_records()
    _, key_a = plant_silent_devices(rec, np.random.default_rng(5))
    _, key_b = plant_silent_devices(rec, np.random.default_rng(5))
    assert np.array_equal(key_a["start"], key_b["start"])
