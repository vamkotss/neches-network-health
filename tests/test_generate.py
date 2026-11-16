import gzip
from dataclasses import replace
from pathlib import Path

from neches.config import GeneratorConfig
from neches.generate import generate


def all_files(root):
    # Every file under a folder, in a fixed order.
    return sorted(path for path in Path(root).rglob("*") if path.is_file())


def count_landing_rows(root):
    # Count JSON lines across every landing file.
    total = 0
    for path in Path(root).glob("landing/telemetry/dt=*/hour=*/batch_*.jsonl.gz"):
        with gzip.open(path, "rt") as handle:
            total += sum(1 for _ in handle)
    return total


def test_generate_writes_every_expected_output(tmp_path):
    generate(GeneratorConfig.tiny(), tmp_path)
    assert (tmp_path / "devices.csv").exists()
    for name in ("outage_events", "degradation_events", "planted_defects"):
        assert (tmp_path / "ground_truth" / f"{name}.csv").exists()
    assert list(tmp_path.glob("landing/telemetry/dt=*/hour=*/batch_0001.jsonl.gz"))


def test_summary_matches_what_was_written(tmp_path):
    summary = generate(GeneratorConfig.tiny(), tmp_path)
    assert summary["devices"] == 50
    assert summary["rows"] == count_landing_rows(tmp_path)
    assert summary["files"] == len(all_files(tmp_path))


def test_same_config_gives_identical_files(tmp_path):
    cfg = GeneratorConfig.tiny()
    generate(cfg, tmp_path / "a")
    generate(cfg, tmp_path / "b")
    files_a = all_files(tmp_path / "a")
    files_b = all_files(tmp_path / "b")
    names_a = [p.relative_to(tmp_path / "a") for p in files_a]
    names_b = [p.relative_to(tmp_path / "b") for p in files_b]
    assert names_a == names_b
    for first, second in zip(files_a, files_b):
        assert first.read_bytes() == second.read_bytes()


def test_different_seed_changes_the_data(tmp_path):
    cfg = GeneratorConfig.tiny()
    generate(cfg, tmp_path / "a")
    generate(replace(cfg, seed=7), tmp_path / "b")
    first = (tmp_path / "a" / "devices.csv").read_bytes()
    second = (tmp_path / "b" / "devices.csv").read_bytes()
    assert first != second


def test_answer_key_lists_all_five_defect_types(tmp_path):
    generate(GeneratorConfig.tiny(), tmp_path)
    text = (tmp_path / "ground_truth" / "planted_defects.csv").read_text()
    types = {line.split(",")[0] for line in text.splitlines()[1:]}
    assert types == {"late_arrival", "duplicate", "clock_skew", "unit_change", "silent_device"}
