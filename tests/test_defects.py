from collections import Counter

import numpy as np

from neches.config import GeneratorConfig
from neches.defects import plant_duplicates, plant_late_arrivals
from neches.fleet import build_devices
from neches.planting import plant_behaviors
from neches.records import build_records
from neches.telemetry import build_baseline


def make_records(seed=20261116):
    # Tiny run: fleet, healthy data, planted outages, flattened into rows.
    cfg = GeneratorConfig.tiny()
    rng = np.random.default_rng(seed)
    devices = build_devices(cfg, rng)
    data = build_baseline(cfg, rng)
    online, _ = plant_behaviors(cfg, devices, data, rng)
    return build_records(cfg, devices, data, online)


def test_late_arrivals_hit_4_percent_of_rows():
    rec = make_records()
    out, key = plant_late_arrivals(rec, np.random.default_rng(5))
    n_late = round(0.04 * len(rec["device_id"]))
    assert len(key["device_id"]) == n_late
    assert (out["arrival_time"] != out["event_time"]).sum() == n_late


def test_late_delays_are_between_1_and_6_hours():
    rec = make_records()
    out, key = plant_late_arrivals(rec, np.random.default_rng(5))
    delay = (out["arrival_time"] - out["event_time"]) / np.timedelta64(1, "m")
    late = delay[delay > 0]
    assert late.min() >= 60
    assert late.max() <= 360
    assert sorted(late.tolist()) == sorted(key["delay_minutes"].tolist())


def test_late_arrivals_leave_event_times_and_input_alone():
    rec = make_records()
    out, _ = plant_late_arrivals(rec, np.random.default_rng(5))
    assert np.array_equal(out["event_time"], rec["event_time"])
    assert np.array_equal(rec["arrival_time"], rec["event_time"])


def test_duplicates_add_1_point_5_percent_more_rows():
    rec = make_records()
    out, key = plant_duplicates(rec, np.random.default_rng(5))
    n_dup = round(0.015 * len(rec["device_id"]))
    assert len(out["device_id"]) == len(rec["device_id"]) + n_dup
    assert len(key["device_id"]) == n_dup
    assert len({len(values) for values in out.values()}) == 1


def test_duplicates_are_exact_second_copies():
    rec = make_records()
    out, key = plant_duplicates(rec, np.random.default_rng(5))
    seen = Counter(zip(out["device_id"].tolist(), out["event_time"].astype(str).tolist()))
    assert set(seen.values()) == {1, 2}
    twice = {pair for pair, count in seen.items() if count == 2}
    expected = set(zip(key["device_id"].tolist(), key["event_time"].astype(str).tolist()))
    assert twice == expected


def test_same_seed_gives_identical_defects():
    out_a, key_a = plant_late_arrivals(make_records(), np.random.default_rng(5))
    out_b, key_b = plant_late_arrivals(make_records(), np.random.default_rng(5))
    assert np.array_equal(out_a["arrival_time"], out_b["arrival_time"])
    assert np.array_equal(key_a["delay_minutes"], key_b["delay_minutes"])
