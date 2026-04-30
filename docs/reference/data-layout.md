# `docs/reference/data-layout.md`

# Data Layout Reference

This document defines the canonical filesystem/data-lake layout for raw, normalized, feature, replay, backtest, report, model, and manifest data.

The layout is designed for long-running data capture and later reproducible research. It should remain stable across phases.

---

## Root Paths

The repo contains a local ignored `data/` directory only as a mount point or symlink placeholder.

Recommended runtime data root:

```text
/mnt/marketdata
```

Repo-local placeholder:

```text
./data
```

Do not commit real market data.

---

## Top-Level Data Layout

```text
/mnt/marketdata/
  raw/
  normalized/
  features/
  replay/
  backtests/
  reports/
  models/
  manifests/
  logs/
  tmp/
```

| Directory     | Purpose                                         |         Source of truth? |
| ------------- | ----------------------------------------------- | -----------------------: |
| `raw/`        | Raw source payloads wrapped with metadata       |                      yes |
| `normalized/` | Typed provider-specific normalized tables       |                       no |
| `features/`   | Derived indicator/microstructure/model features |                       no |
| `replay/`     | Replay-ready event bundles or state snapshots   |                       no |
| `backtests/`  | Backtest run outputs and simulated trades       |                       no |
| `reports/`    | Human-readable reports/plots                    |                       no |
| `models/`     | ML models/artifacts                             |                       no |
| `manifests/`  | Run metadata, file indexes, quality summaries   | supports reproducibility |
| `logs/`       | Runtime logs                                    |                       no |
| `tmp/`        | Temporary working files                         |                       no |

---

## Raw Data Layout

Raw data is the source of truth and should be append-only.

Canonical pattern:

```text
raw/<source>/<transport>/<source_symbol>/<stream>/date=YYYY-MM-DD/hour=HH/part-*.jsonl.zst
```

Path component note:

* The implemented path builder sanitizes components into filesystem-safe names.
* Current examples include `markPrice@1s -> markPrice_1s`, `depth@100ms -> depth_100ms`, and `BTC/USD -> BTC_USD` when a provider symbol contains a slash.

Examples:

```text
raw/pyth/sse/MULTI/price_stream/date=2026-04-30/hour=14/part-0000.jsonl.zst

raw/aster/ws/BTCUSDT/aggTrade/date=2026-04-30/hour=14/part-0000.jsonl.zst
raw/aster/ws/BTCUSDT/bookTicker/date=2026-04-30/hour=14/part-0000.jsonl.zst
raw/aster/ws/BTCUSDT/markPrice_1s/date=2026-04-30/hour=14/part-0000.jsonl.zst
raw/aster/ws/BTCUSDT/forceOrder/date=2026-04-30/hour=14/part-0000.jsonl.zst
raw/aster/ws/BTCUSDT/kline_1m/date=2026-04-30/hour=14/part-0000.jsonl.zst
raw/aster/ws/BTCUSDT/depth20_100ms/date=2026-04-30/hour=14/part-0000.jsonl.zst
raw/aster/ws/BTCUSDT/depth_100ms/date=2026-04-30/hour=14/part-0000.jsonl.zst

raw/aster/rest/BTCUSDT/depth_snapshot_1000/date=2026-04-30/hour=14/part-0000.jsonl.zst

raw/tradingview/webhook/ALL/alert/date=2026-04-30/hour=14/part-0000.jsonl.zst
```

### Raw File Format

Use:

```text
.jsonl.zst
```

Rules:

* One JSON object per line.
* Zstandard compression.
* Rotate hourly.
* Append-only.
* Do not mutate or rewrite raw files during normal operation.

### Raw File Rotation

Default rotation:

```text
hourly
```

Rationale:

* Easy retention management.
* Easy replay windows.
* Avoids giant files.
* Limits corruption scope.

### Raw Filename Policy

Acceptable simple form:

```text
part-0000.jsonl.zst
```

Current implemented default:

```text
part-<run_id>.jsonl.zst
```

Rationale:

* Avoids accidental overwrite across process restarts.
* Keeps a single run's files easy to identify during validation.

Never overwrite an existing raw file unless explicitly instructed.

---

## Normalized Data Layout

Canonical pattern:

```text
normalized/<table>/source=<source>/symbol=<canonical_symbol>/year=YYYY/month=MM/day=DD/*.parquet
```

Examples:

```text
normalized/pyth_prices/source=pyth/symbol=BTCUSD/year=2026/month=04/day=30/data.parquet
normalized/trades/source=aster/symbol=BTCUSD/year=2026/month=04/day=30/data.parquet
normalized/book_ticker/source=aster/symbol=BTCUSD/year=2026/month=04/day=30/data.parquet
normalized/mark_price/source=aster/symbol=BTCUSD/year=2026/month=04/day=30/data.parquet
normalized/liquidations/source=aster/symbol=BTCUSD/year=2026/month=04/day=30/data.parquet
normalized/l2_diff_depth/source=aster/symbol=BTCUSD/year=2026/month=04/day=30/data.parquet
normalized/tv_alerts/source=tradingview/year=2026/month=04/day=30/data.parquet
```

Preferred format:

```text
Parquet
```

Partition by symbol and date for efficient scans.

---

## Feature Data Layout

Canonical pattern:

```text
features/<feature_family>/symbol=<canonical_symbol>/timeframe=<tf>/version=<version>/year=YYYY/month=MM/day=DD/*.parquet
```

Examples:

```text
features/bars/symbol=BTCUSD/timeframe=1s/version=v1/year=2026/month=04/day=30/data.parquet
features/bars/symbol=BTCUSD/timeframe=1m/version=v1/year=2026/month=04/day=30/data.parquet
features/microstructure/symbol=BTCUSD/timeframe=1s/version=v1/year=2026/month=04/day=30/data.parquet
features/indicators/symbol=BTCUSD/timeframe=5m/version=v1/year=2026/month=04/day=30/data.parquet
features/labels/symbol=BTCUSD/timeframe=5m/version=v1/year=2026/month=04/day=30/data.parquet
```

Feature outputs must include enough metadata to identify source dataset version and feature configuration.

---

## Replay Layout

Replay data should be generated from raw/normalized data and should be reproducible.

Examples:

```text
replay/event_streams/source_set=aster_pyth/symbol=BTCUSD/date=2026-04-30/*.parquet
replay/orderbook_checkpoints/source=aster/symbol=BTCUSD/date=2026-04-30/hour=14/*.parquet
replay/windows/event_id=<event_id>/*.parquet
```

Use replay bundles for deterministic “as if live” simulations.

---

## Backtest Layout

Backtest runs should be stored under a unique run ID.

```text
backtests/run_id=<run_id>/
  config.yaml
  metadata.json
  metrics.json
  trades.parquet
  equity_curve.parquet
  events.parquet
  report.md
```

`metadata.json` should include:

```text
git commit
strategy version
source dataset versions
feature versions
symbols
time range
fee/slippage/fill assumptions
created_at
```

---

## Reports Layout

```text
reports/
  daily-data-quality/date=YYYY-MM-DD/report.md
  backtests/run_id=<run_id>/report.md
  notebooks-exported/<name>.html
```

Reports are derived artifacts and should be reproducible from data and code when practical.

---

## Manifests Layout

Manifests track runs, data quality, gaps, source changes, and generated artifacts.

```text
manifests/
  recorder_runs.parquet
  raw_file_index.parquet
  stream_gaps.parquet
  data_quality_daily.parquet
  normalization_runs.parquet
  feature_runs.parquet
  backtest_runs.parquet
```

Recommended manifest records:

```text
run_id
source
stream
symbol
start_time
end_time
file_path
record_count
byte_count
status
error_count
created_at
config_hash
git_commit
```

---

## Logs Layout

```text
logs/
  recorder/date=YYYY-MM-DD/*.log
  normalizer/date=YYYY-MM-DD/*.log
  backtest/date=YYYY-MM-DD/*.log
```

Do not log secrets.

---

## Local Repo `data/` Directory

The repo may contain:

```text
data/.gitkeep
```

The actual contents of `data/` should be ignored by Git. Use it as a symlink or mount point only.

Suggested `.gitignore` entries:

```gitignore
data/*
!data/.gitkeep
.env
.env.*
!.env.example
```

---

## Retention Policy

No destructive retention policy should be implemented until explicitly requested.

Future likely tiers:

```text
Forever:
  Pyth, trades/aggTrades, L1/bookTicker, mark/funding, alerts, own fills.

Rolling:
  Raw L2 depth streams.

Permanent event windows:
  L2 excerpts around alerts/trades/high-volatility events.

Forever derived:
  Compact L2 features such as spread, depth, imbalance, and slippage estimates.
```

Until a retention policy exists, do not delete raw data automatically.

---

## Validation Commands

List raw files:

```bash
find /mnt/marketdata/raw -type f | head -n 50
```

Check disk usage:

```bash
du -h --max-depth=4 /mnt/marketdata/raw | sort -h | tail -n 30
```

Inspect a compressed raw file:

```bash
zstdcat /mnt/marketdata/raw/aster/ws/BTCUSDT/bookTicker/date=*/hour=*/part-0000.jsonl.zst | head -n 3
```

Validate sampled JSON lines:

```bash
zstdcat FILE.jsonl.zst | head -n 100 | python -m json.tool >/dev/null
```

For large files, use a purpose-built validator rather than piping entire files through `json.tool`.

---