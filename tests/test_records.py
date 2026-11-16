import numpy as np

from neches.config import GeneratorConfig
from neches.fleet import build_devices
from neches.planting import plant_behaviors
from neches.records import build_records
from neches.telemetry import build_baseline, build_timestamps


def make(seed=20261116):
    # Tiny run: fleet, healthy data, planted outages, then flatten into rows.
    cfg = GeneratorConfig.tiny()
    rng = np.random.default_rng(seed)
    devices = build_devices(cfg, rng)
    data = build_baseline(cfg, rng)
    online, _ = plant_behaviors(cfg, devices, data, rng)
    return cfg, devices, data, online, build_records(cfg, devices, data, online)


def test_one_row_per_online_reading():
    _, _, _, online, rec = make()
    assert len(rec["device_id"]) == online.sum()


def test_all_columns_have_the_same_length():
    _, _, _, _, rec = make()
    assert len({len(values) for values in rec.values()}) == 1


def test_rows_per_device_match_the_online_table():
    _, devices, _, online, rec = make()
    ids, counts = np.unique(rec["device_id"], return_counts=True)
    expected = {d["device_id"]: int(online[i].sum()) for i, d in enumerate(devices)}
    assert dict(zip(ids.tolist(), counts.tolist())) == expected


def test_values_land_on_the_right_device_and_time():
    cfg, _, data, _, rec = make()
    ts = build_timestamps(cfg)
    for k in (0, 5, 777, len(rec["device_id"]) - 1):
        device_row = int(rec["device_id"][k].split("-")[1]) - 1
        time_col = int(np.searchsorted(ts, rec["event_time"][k]))
        assert rec["rx_power_dbm"][k] == data["rx_power_dbm"][device_row, time_col]
        assert rec["fec_corrected"][k] == data["fec_corrected"][device_row, time_col]


def test_arrival_starts_equal_to_event_time():
    _, _, _, _, rec = make()
    assert np.array_equal(rec["arrival_time"], rec["event_time"])


def test_firmware_starts_at_2_4_1():
    _, _, _, _, rec = make()
    assert set(rec["firmware"].tolist()) == {"2.4.1"}
