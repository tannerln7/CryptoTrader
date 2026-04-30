from market_recorder import __version__
from market_recorder.cli import main
from market_recorder.config import DEFAULT_CONFIG_PATH, DEFAULT_SOURCES_PATH
from market_recorder.timeutil import utc_now_iso


def test_version_is_exposed() -> None:
    assert __version__ == "0.1.0"


def test_default_config_paths_point_to_examples() -> None:
    assert DEFAULT_CONFIG_PATH.name == "config.example.yaml"
    assert DEFAULT_SOURCES_PATH.name == "sources.example.yaml"


def test_utc_now_iso_ends_with_z() -> None:
    assert utc_now_iso().endswith("Z")


def test_cli_version_flag(capsys) -> None:
    exit_code = main(["--version"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "0.1.0"