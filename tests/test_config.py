from neches.config import GeneratorConfig


def test_dev_scale_defaults():
    cfg = GeneratorConfig.dev()
    assert cfg.n_devices == 500
    assert cfg.readings_per_device == 4032


def test_full_scale():
    assert GeneratorConfig.full().n_devices == 2000


def test_tiny_scale_is_small():
    cfg = GeneratorConfig.tiny()
    assert cfg.n_devices == 50
    assert cfg.days == 1
