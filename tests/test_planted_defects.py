import csv
from collections import Counter
from itertools import groupby

import numpy as np

from neches.config import GeneratorConfig
from neches.defects import (
    plant_clock_skew,
    plant_duplicates,
    plant_late_arrivals,
    plant_silent_devices,
    plant_unit_change,
)
from neches.fleet import build_devices
from neches.planting import plant_behaviors
from neches.records import build_records
from neches.tables import write_planted_defects
from neches.telemetry import build_baseline


def make_keys(seed=20261116):
    # Small 10-day fleet, long enough for every defect. Returns one answer key per defect.
    cfg = GeneratorConfig(olts=1, ports_per_olt=2, devices_per_port=10, days=10)
    rng = np.random.default_rng(seed)
    devices = build_devices(cfg, rng)
    data = build_baseline(cfg, rng)
    online, _ = plant_behaviors(cfg, devices, data, rng)
    rec = build_records(cfg, devices, data, online)
    return {
        "late_arrival": plant_late_arrivals(rec, np.random.default_rng(1))[1],
        "duplicate": plant_duplicates(rec, np.random.default_rng(2))[1],
        "clock_skew": plant_clock_skew(rec, np.random.default_rng(3))[1],
        "unit_change": plant_unit_change(rec, cfg, np.random.default_rng(4))[1],
        "silent_device": plant_silent_devices(rec, np.random.default_rng(5))[1],
    }


def read_csv(path):
    # Read a CSV file back: returns (column names, list of row dicts).
    with open(path, newline="") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames, list(reader)


def test_planted_defects_csv_has_the_expected_columns(tmp_path):
    names, _ = read_csv(write_planted_defects(make_keys(), tmp_path))
    assert names == ["defect_type", "device_id", "event_time", "detail"]


def test_one_row_per_planted_item(tmp_path):
    keys = make_keys()
    _, rows = read_csv(write_planted_defects(keys, tmp_path))
    assert len(rows) == sum(len(key["device_id"]) for key in keys.values())


def test_each_defect_type_has_the_right_count(tmp_path):
    keys = make_keys()
    _, rows = read_csv(write_planted_defects(keys, tmp_path))
    expected = {name: len(key["device_id"]) for name, key in keys.items()}
    assert Counter(row["defect_type"] for row in rows) == expected


def test_detail_text_describes_each_defect(tmp_path):
    _, rows = read_csv(write_planted_defects(make_keys(), tmp_path))
    by_type = {}
    for row in rows:
        by_type.setdefault(row["defect_type"], []).append(row)
    assert all(r["detail"].startswith("delay_minutes=") for r in by_type["late_arrival"])
    assert all(r["detail"] == "" for r in by_type["duplicate"])
    assert all(r["detail"] == "skew_minutes=37" for r in by_type["clock_skew"])
    assert all(r["detail"] == "firmware=2.5.0" for r in by_type["unit_change"])
    assert all("hours=" in r["detail"] for r in by_type["silent_device"])


def test_clock_skew_rows_have_no_event_time(tmp_path):
    _, rows = read_csv(write_planted_defects(make_keys(), tmp_path))
    skew = [r for r in rows if r["defect_type"] == "clock_skew"]
    assert skew
    assert all(r["event_time"] == "" for r in skew)


def test_defect_types_come_out_grouped_in_a_fixed_order(tmp_path):
    keys = make_keys()
    _, rows = read_csv(write_planted_defects(keys, tmp_path))
    order = [name for name, _ in groupby(r["defect_type"] for r in rows)]
    assert order == list(keys)


def test_no_defects_still_writes_a_header(tmp_path):
    names, rows = read_csv(write_planted_defects({}, tmp_path))
    assert names[0] == "defect_type"
    assert rows == []
