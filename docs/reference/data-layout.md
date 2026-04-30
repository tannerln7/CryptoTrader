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

Current operational manifest paths:

```text
manifests/runtime/health-<run_id>.json
```

Use runtime manifests for lightweight service-health state and operator-facing summaries that should not be mixed into raw event files.

---

## Raw Data Layout

Raw data is the source of truth and should be append-only.

Canonical pattern:

```text
raw/<source>/<transport>/<source_symbol>/<stream>/date=YYYY-MM-DD/hour=HH/part-*.jsonl.zst*
```

Path component note:

* The implemented path builder sanitizes components into filesystem-safe names.
* Current examples include `markPrice@1s -> markPrice_1s`, `depth@100ms -> depth_100ms`, and `BTC/USD -> BTC_USD` when a provider symbol contains a slash.

Examples:

```text
raw/pyth/sse/MULTI/price_stream/date=2026-04-30/hour=14/part-20260430T140000Z-recorder-abc123.jsonl.zst.open
raw/pyth/sse/MULTI/price_stream/date=2026-04-30/hour=14/part-20260430T140000Z-20260430T150000123456Z-recorder-abc123.jsonl.zst

raw/aster/ws/BTCUSDT/aggTrade/date=2026-04-30/hour=14/part-20260430T140000Z-recorder-abc123.jsonl.zst.open
raw/aster/ws/BTCUSDT/bookTicker/date=2026-04-30/hour=14/part-20260430T140000Z-20260430T150000Z-recorder-abc123.jsonl.zst
raw/aster/ws/BTCUSDT/markPrice_1s/date=2026-04-30/hour=12/part-20260430T120000Z-20260430T180000Z-recorder-abc123.jsonl.zst
raw/aster/ws/BTCUSDT/forceOrder/date=2026-04-30/hour=00/part-20260430T000000Z-recorder-abc123.jsonl.zst.open
raw/aster/ws/BTCUSDT/kline_1m/date=2026-04-30/hour=12/part-20260430T120000Z-recorder-abc123.jsonl.zst.open
raw/aster/ws/BTCUSDT/kline_5m/date=2026-04-30/hour=12/part-20260430T120000Z-recorder-abc123.jsonl.zst.open
raw/aster/ws/BTCUSDT/kline_15m/date=2026-04-30/hour=12/part-20260430T120000Z-recorder-abc123.jsonl.zst.open
raw/aster/ws/BTCUSDT/depth20_100ms/date=2026-04-30/hour=14/part-20260430T140000Z-recorder-abc123.jsonl.zst.open
raw/aster/ws/BTCUSDT/depth_100ms/date=2026-04-30/hour=14/part-20260430T140000Z-recorder-abc123.jsonl.zst.open

raw/aster/rest/BTCUSDT/depth_snapshot_1000/date=2026-04-30/hour=00/part-20260430T000000Z-recorder-abc123.jsonl.zst.open

raw/tradingview/webhook/ALL/alert/date=2026-04-30/hour=00/part-20260430T000000Z-recorder-abc123.jsonl.zst.open
```

### Raw File Format

Use:

```text
.jsonl.zst.open   # active writer-owned segment
.jsonl.zst        # sealed segment safe for validation and user reads
```

Treat sealed `.jsonl.zst` files as the default validation and read target. Active `.jsonl.zst.open` files are incomplete until they are sealed.

Rules:

* One JSON object per line.
* Zstandard compression.
* Writers own active `.jsonl.zst.open` segments and never write directly to final-looking sealed files.
* Active `.jsonl.zst.open` segments remain service-private while open; sealed `.jsonl.zst` files may be group-readable but are not group-writable.
* Sealing closes the zstd frame and atomically renames the active path to a sealed `.jsonl.zst` path.
* Validators and user-facing inspection commands should treat sealed `.jsonl.zst` files as authoritative by default and skip or refuse active `.jsonl.zst.open` files.
* Append-only.
* Do not mutate or rewrite raw files during normal operation.

### Raw File Rotation

Rotation is now policy-driven per stream route.

```text
default rotation policy
named rotation classes
per-source/per-stream class mapping
age-based rotation
size-based rotation
reserved manual checkpoint/seal constraints
```

Current implementation:

* Each route keeps its own independent segment series under the same per-stream directory layout as before.
* `segment_start_utc` is the route-local bucket start used for directory partitioning and the active filename.
* `segment_end_utc` is the actual seal time used in the sealed filename.
* `first_record_ts_recv_utc` and `last_record_ts_recv_utc` are the first and last raw envelope receive timestamps written into the segment.
* Age rotation is enforced by the configured `max_age_seconds` bucket for that route.
* Size rotation is enforced by flushed compressed bytes in the active segment when `max_bytes` is configured.
* Size rotation seals the segment after the record that crosses the limit; the next record opens a new active segment.

Rationale:

* Easy retention management.
* Per-stream routes remain isolated and predictable.
* Active and sealed states are unambiguous to writers and readers.
* Larger retention windows are possible for lower-frequency routes without creating many tiny files.
* Size caps limit segment growth on high-frequency routes.

### Raw Filename Policy

Active filename form:

```text
part-<segment_start_utc>-<run_id>.jsonl.zst.open
```

Sealed filename form:

```text
part-<segment_start_utc>-<segment_end_utc>-<run_id>.jsonl.zst
```

Notes:

* `segment_start_utc` is compact UTC and is usually bucket-aligned, for example `20260430T140000Z`.
* `segment_end_utc` uses compact UTC and may include subsecond digits when the actual seal time is not second-aligned, for example `20260430T150000123456Z`.
* Run IDs remain part of the filename to prevent accidental overwrite across process restarts.
* The per-stream directory layout does not change. This refactor only changes the segment filename and lifecycle within each existing route directory.

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

## Replay Layout

Replay data should be generated from raw/normalized data and should be reproducible.

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