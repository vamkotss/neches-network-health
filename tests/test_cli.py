import pytest

from neches.generate import config_for, main


def test_config_for_picks_the_scale():
    assert config_for("tiny").n_devices == 50
    assert config_for("dev").n_devices == 500
    assert config_for("full").n_devices == 2000


def test_config_for_overrides_the_seed():
    assert config_for("tiny").seed == 20261116
    assert config_for("tiny", seed=7).seed == 7


def test_main_writes_files_and_reports(tmp_path, capsys):
    code = main(["--scale", "tiny", "--out", str(tmp_path)])
    assert code == 0
    assert "50 devices" in capsys.readouterr().out
    assert (tmp_path / "devices.csv").exists()


def test_main_rejects_an_unknown_scale(tmp_path):
    with pytest.raises(SystemExit):
        main(["--scale", "huge", "--out", str(tmp_path)])


def test_main_seed_changes_the_output(tmp_path):
    main(["--scale", "tiny", "--seed", "1", "--out", str(tmp_path / "a")])
    main(["--scale", "tiny", "--seed", "2", "--out", str(tmp_path / "b")])
    first = (tmp_path / "a" / "devices.csv").read_bytes()
    second = (tmp_path / "b" / "devices.csv").read_bytes()
    assert first != second
