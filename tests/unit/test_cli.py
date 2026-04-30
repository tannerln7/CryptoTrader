from __future__ import annotations

from pathlib import Path

from market_recorder.cli import main
from market_recorder.storage import validate_raw_file


def test_cli_validate_config_reports_loaded_paths(capsys) -> None:
    exit_code = main(["validate-config"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Configuration valid:" in captured.out
    assert "Enabled sources: pyth, aster" in captured.out


def test_cli_reports_invalid_config_to_stderr(tmp_path: Path, capsys) -> None:
    sources_path = tmp_path / "sources.yaml"
    sources_path.write_text(
        """
pyth:
  enabled: false
  provider: hermes
  http_base_url: https://hermes.pyth.network
  feeds: []
aster:
  enabled: false
  rest_base_url: https://fapi.asterdex.com
  ws_base_url: wss://fstream.asterdex.com
  symbols: []
  streams: []
tradingview:
  enabled: false
  webhook:
    bind_host: 127.0.0.1
    bind_port: 8000
    path: webhook/tradingview
""".strip(),
        encoding="utf-8",
    )

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
runtime:
  environment: development
  timezone: UTC
  data_root: ./data
  sources_config: {sources_path}
logging:
  level: INFO
  structured: false
storage:
  format: jsonl.zst
  rotation: hourly
  compression_level: 3
validation:
  enable_sample_checks: true
""".strip(),
        encoding="utf-8",
    )

    exit_code = main(["validate-config", "--config", str(config_path)])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "Configuration error:" in captured.err


def test_cli_write_sample_creates_valid_raw_file(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
runtime:
  environment: development
  timezone: UTC
  data_root: {tmp_path / 'data'}
  sources_config: {Path('config/sources.example.yaml').resolve()}
logging:
  level: INFO
  structured: false
storage:
  format: jsonl.zst
  rotation: hourly
  compression_level: 3
validation:
  enable_sample_checks: true
""".strip(),
        encoding="utf-8",
    )

    exit_code = main(["write-sample", "--config", str(config_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Sample raw file:" in captured.out

    raw_path = Path(captured.out.splitlines()[0].split(": ", 1)[1])
    summary = validate_raw_file(raw_path)
    assert summary.record_count == 2