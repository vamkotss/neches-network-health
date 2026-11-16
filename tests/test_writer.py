import gzip
import json
from datetime import datetime
from pathlib import Path

import numpy as np

from neches.config import GeneratorConfig
from neches.defects import plant_late_arrivals
from neches.fleet import build_devices
from neches.planting import plant_behaviors
from neches.records import build_records
from neches.telemetry import build_baseline
from neches.writer import write_landing

EXPECTED_KEYS = {
    "device_id",
    "event_time",
    "firmware",
    "rx_power_dbm",
    "tx_power_dbm",
    "fec_corrected",
    "fec_uncorrected",
    "bip_errors",
    "latency_ms",
    "packet_loss_pct",
    "temperature_c",
}


def make_records(seed=20261116):
    # Tiny run with late arrivals, so rows spread across many arrival hours.
    cfg = GeneratorConfig.tiny()
    rng = np.random.default_rng(seed)
    devices = build_devices(cfg, rng)
    data = build_baseline(cfg, rng)
    online, _ = plant_behaviors(cfg, devices, data, rng)
    rec = build_records(cfg, devices, data, online)
    rec, _ = plant_late_arrivals(rec, np.random.default_rng(5))
    return rec


def landing_files(out_dir):
    # Every landing file under the output folder, in a fixed order.
    return sorted(Path(out_dir).glob("landing/telemetry/dt=*/hour=*/batch_*.jsonl.gz"))


def read_rows(path):
    # Read one gzip JSONL file back into a list of dicts.
    with gzip.open(path, "rt") as handle:
        return [json.loads(line) for line in handle]


def file_hour(path):
    # .../dt=2026-11-01/hour=05/batch_0001.jsonl.gz  ->  "2026-11-01T05"
    day = path.parent.parent.name.split("=")[1]
    hour = path.parent.name.split("=")[1]
    return f"{day}T{hour}"


def test_every_row_is_written_once(tmp_path):
    rec = make_records()
    write_landing(rec, tmp_path)
    total = sum(len(read_rows(path)) for path in landing_files(tmp_path))
    assert total == len(rec["device_id"])


def test_files_are_named_by_arrival_hour(tmp_path):
    rec = make_records()
    write_landing(rec, tmp_path)
    arrival_hours = rec["arrival_time"].astype("datetime64[h]").astype(str)
    hours, counts = np.unique(arrival_hours, return_counts=True)
    expected = dict(zip(hours.tolist(), counts.tolist()))
    actual = {file_hour(path): len(read_rows(path)) for path in landing_files(tmp_path)}
    assert actual == expected


def test_rows_have_the_expected_fields(tmp_path):
    rec = make_records()
    write_landing(rec, tmp_path)
    for path in landing_files(tmp_path):
        for row in read_rows(path)[:50]:
            assert set(row) == EXPECTED_KEYS
            assert row["event_time"].endswith("Z")
            datetime.fromisoformat(row["event_time"])


def test_late_rows_sit_in_a_later_file_than_their_event_hour(tmp_path):
    rec = make_records()
    write_landing(rec, tmp_path)
    found_late = False
    for path in landing_files(tmp_path):
        for row in read_rows(path):
            event_hour = datetime.fromisoformat(row["event_time"]).strftime("%Y-%m-%dT%H")
            if event_hour != file_hour(path):
                found_late = True
    assert found_late


def test_same_records_write_identical_bytes(tmp_path):
    rec = make_records()
    write_landing(rec, tmp_path / "a")
    write_landing(rec, tmp_path / "b")
    files_a = landing_files(tmp_path / "a")
    files_b = landing_files(tmp_path / "b")
    assert [p.relative_to(tmp_path / "a") for p in files_a] == [
        p.relative_to(tmp_path / "b") for p in files_b
    ]
    for first, second in zip(files_a, files_b):
        assert first.read_bytes() == second.read_bytes()


def test_write_landing_returns_the_files_it_wrote(tmp_path):
    rec = make_records()
    written = write_landing(rec, tmp_path)
    assert sorted(written) == landing_files(tmp_path)
