import csv

import numpy as np

from neches.config import GeneratorConfig
from neches.fleet import build_devices
from neches.planting import plant_behaviors
from neches.tables import write_devices, write_ground_truth
from neches.telemetry import build_baseline


def make(seed=20261116):
    # Tiny run: fleet plus the answer key of planted outages and degradations.
    cfg = GeneratorConfig.tiny()
    rng = np.random.default_rng(seed)
    devices = build_devices(cfg, rng)
    data = build_baseline(cfg, rng)
    _, truth = plant_behaviors(cfg, devices, data, rng)
    return cfg, devices, truth


def read_csv(path):
    # Read a CSV file back: returns (column names, list of row dicts).
    with open(path, newline="") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames, list(reader)


def test_devices_csv_has_one_row_per_device(tmp_path):
    cfg, devices, _ = make()
    path = write_devices(devices, tmp_path)
    names, rows = read_csv(path)
    assert names == ["device_id", "olt_id", "pon_port", "region", "model", "install_date"]
    assert len(rows) == cfg.n_devices


def test_devices_csv_round_trips(tmp_path):
    _, devices, _ = make()
    _, rows = read_csv(write_devices(devices, tmp_path))
    assert rows == [{key: str(value) for key, value in d.items()} for d in devices]


def test_outage_events_csv_matches_the_answer_key(tmp_path):
    _, _, truth = make()
    write_ground_truth(truth, tmp_path)
    names, rows = read_csv(tmp_path / "ground_truth" / "outage_events.csv")
    assert names == [
        "event_id",
        "scope",
        "device_id",
        "olt_id",
        "pon_port",
        "start",
        "end",
        "duration_minutes",
    ]
    expected = [e["event_id"] for e in truth["outage_events"]]
    assert [row["event_id"] for row in rows] == expected
    shared = [row for row in rows if row["scope"] == "pon_port"]
    assert shared
    assert all(row["device_id"] == "" for row in shared)


def test_degradation_events_csv_matches_the_answer_key(tmp_path):
    _, _, truth = make()
    write_ground_truth(truth, tmp_path)
    names, rows = read_csv(tmp_path / "ground_truth" / "degradation_events.csv")
    assert names == ["event_id", "device_id", "start", "rate_db_per_day"]
    expected = [e["device_id"] for e in truth["degradation_events"]]
    assert [row["device_id"] for row in rows] == expected


def test_write_ground_truth_returns_the_files_it_wrote(tmp_path):
    _, _, truth = make()
    written = write_ground_truth(truth, tmp_path)
    assert sorted(p.name for p in written) == ["degradation_events.csv", "outage_events.csv"]
    assert all(p.exists() for p in written)


def test_empty_answer_key_still_writes_headers(tmp_path):
    write_ground_truth({"degradation_events": [], "outage_events": []}, tmp_path)
    names, rows = read_csv(tmp_path / "ground_truth" / "outage_events.csv")
    assert names[0] == "event_id"
    assert rows == []
