import numpy as np

from neches.config import GeneratorConfig
from neches.fleet import build_devices


def make(seed=20261116):
    cfg = GeneratorConfig.dev()
    return cfg, build_devices(cfg, np.random.default_rng(seed))


def test_device_count_matches_config():
    cfg, devices = make()
    assert len(devices) == cfg.n_devices


def test_device_ids_are_unique():
    _, devices = make()
    ids = [d["device_id"] for d in devices]
    assert len(ids) == len(set(ids))


def test_every_pon_port_has_20_devices():
    _, devices = make()
    counts = {}
    for d in devices:
        key = (d["olt_id"], d["pon_port"])
        counts[key] = counts.get(key, 0) + 1
    assert set(counts.values()) == {20}


def test_same_seed_gives_identical_fleet():
    _, first = make(seed=1)
    _, second = make(seed=1)
    assert first == second


def test_different_seed_changes_the_fleet():
    _, first = make(seed=1)
    _, second = make(seed=2)
    assert first != second
