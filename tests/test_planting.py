import numpy as np

from neches.config import GeneratorConfig
from neches.fleet import build_devices
from neches.planting import plant_behaviors
from neches.telemetry import build_baseline, build_timestamps


def make(seed=20261116):
    # Tiny run: 50 devices, 1 day. Build fleet, healthy data, then plant problems.
    cfg = GeneratorConfig.tiny()
    rng = np.random.default_rng(seed)
    devices = build_devices(cfg, rng)
    data = build_baseline(cfg, rng)
    before = {name: values.copy() for name, values in data.items()}
    online, truth = plant_behaviors(cfg, devices, data, rng)
    return cfg, devices, before, data, online, truth


def index_of(devices):
    # Map device_id -> row number in the tables.
    return {d["device_id"]: i for i, d in enumerate(devices)}


def test_degradation_count_is_3_percent():
    cfg, _, _, _, _, truth = make()
    assert len(truth["degradation_events"]) == round(0.03 * cfg.n_devices)


def test_degraded_devices_lose_signal():
    _, devices, before, data, _, truth = make()
    rows = index_of(devices)
    for event in truth["degradation_events"]:
        i = rows[event["device_id"]]
        assert (data["rx_power_dbm"][i] - before["rx_power_dbm"][i]).min() < 0
        assert event["rate_db_per_day"] == 0.5


def test_other_devices_keep_their_signal():
    _, devices, before, data, _, truth = make()
    rows = index_of(devices)
    hit = {rows[e["device_id"]] for e in truth["degradation_events"]}
    for i in range(len(devices)):
        if i not in hit:
            assert np.array_equal(data["rx_power_dbm"][i], before["rx_power_dbm"][i])


def test_uncorrected_errors_only_go_up():
    _, _, before, data, _, _ = make()
    assert (data["fec_uncorrected"] >= before["fec_uncorrected"]).all()


def test_outage_counts():
    cfg, _, _, _, _, truth = make()
    single = [e for e in truth["outage_events"] if e["scope"] == "device"]
    shared = [e for e in truth["outage_events"] if e["scope"] == "pon_port"]
    assert len(single) == round(0.015 * cfg.n_devices)
    assert len(shared) == (cfg.olts * cfg.ports_per_olt) // 5


def test_outage_durations_are_in_range():
    _, _, _, _, _, truth = make()
    for e in truth["outage_events"]:
        low, high = (20, 180) if e["scope"] == "device" else (30, 240)
        assert low <= e["duration_minutes"] <= high


def test_online_mask_has_the_right_shape():
    cfg, _, _, _, online, _ = make()
    assert online.shape == (cfg.n_devices, cfg.readings_per_device)
    assert online.dtype == bool


def test_single_device_outage_takes_that_device_offline():
    cfg, devices, _, _, online, truth = make()
    rows = index_of(devices)
    ts = build_timestamps(cfg)
    for e in truth["outage_events"]:
        if e["scope"] != "device":
            continue
        start = int(np.searchsorted(ts, np.datetime64(e["start"])))
        length = e["duration_minutes"] // cfg.interval_minutes
        assert not online[rows[e["device_id"]], start : start + length].any()


def test_shared_outage_takes_whole_port_offline():
    cfg, devices, _, _, online, truth = make()
    ts = build_timestamps(cfg)
    for e in truth["outage_events"]:
        if e["scope"] != "pon_port":
            continue
        start = int(np.searchsorted(ts, np.datetime64(e["start"])))
        length = e["duration_minutes"] // cfg.interval_minutes
        members = [
            i
            for i, d in enumerate(devices)
            if d["olt_id"] == e["olt_id"] and d["pon_port"] == e["pon_port"]
        ]
        assert len(members) == cfg.devices_per_port
        assert not online[members, start : start + length].any()


def test_network_is_mostly_online():
    _, _, _, _, online, _ = make()
    assert online.mean() > 0.9


def test_same_seed_gives_identical_plants():
    _, _, _, data_a, online_a, truth_a = make(seed=7)
    _, _, _, data_b, online_b, truth_b = make(seed=7)
    assert truth_a == truth_b
    assert np.array_equal(online_a, online_b)
    assert np.array_equal(data_a["rx_power_dbm"], data_b["rx_power_dbm"])
