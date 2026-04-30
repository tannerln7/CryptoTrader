# Schemas Reference

This document defines the canonical schemas used across the market-data and trading-research repository.

The schemas here are intentionally stable and explicit. They are designed to support raw recording, normalization, replay, backtesting, alert analysis, and future ML datasets without requiring brittle glue later.

## Schema Principles

1. **Raw records preserve source truth.** Raw events keep the provider payload intact under `payload`.
2. **Derived records preserve provenance.** Normalized, feature, and backtest tables should be traceable to source files/records or dataset versions.
3. **Timestamps are explicit.** Store source event time when provided, local receive time for live ingestion, and UTC everywhere.
4. **No silent unit ambiguity.** Prices, quantities, notional values, percentages, basis points, and timestamps must be named clearly.
5. **Schemas may evolve, but not silently.** Breaking changes require docs updates and migration notes.

---

## 1. Raw Event Envelope

All raw recorded events should use the same envelope shape regardless of provider.

```json
{
  "schema": "raw.market_event.v1",
  "source": "aster",
  "transport": "ws",
  "stream": "bookTicker",
  "stream_name": "btcusdt@bookTicker",
  "canonical_symbol": "BTCUSD",
  "source_symbol": "BTCUSDT",
  "ts_recv_ns": 1770000000000000000,
  "ts_recv_utc": "2026-04-30T14:00:00.123456Z",
  "monotonic_ns": 123456789000,
  "conn_id": "aster-ws-20260430T140000Z-001",
  "seq": 123456,
  "payload": {}
}
```

### Required Fields

| Field              |          Type | Required | Description                                                             |
| ------------------ | ------------: | -------: | ----------------------------------------------------------------------- |
| `schema`           |        string |      yes | Schema name/version. Example: `raw.market_event.v1`.                    |
| `source`           |        string |      yes | Provider/source. Example: `pyth`, `aster`, `tradingview`.               |
| `transport`        |        string |      yes | `ws`, `sse`, `rest`, `webhook`, or another explicit transport.          |
| `stream`           |        string |      yes | Logical stream name. Example: `aggTrade`, `bookTicker`, `price_stream`. |
| `stream_name`      |   string/null |       no | Exact provider stream name where applicable.                            |
| `canonical_symbol` |        string |      yes | Internal symbol, e.g. `BTCUSD`, `ETHUSD`, `MULTI`, `ALL`, `UNKNOWN`.    |
| `source_symbol`    |        string |      yes | Provider symbol, e.g. `BTCUSDT`, `ETHUSDT`, `BTCUSD`.                   |
| `ts_recv_ns`       |           int |      yes | Local wall-clock receive timestamp in Unix nanoseconds.                 |
| `ts_recv_utc`      |        string |      yes | Local receive timestamp in UTC ISO-8601 form.                           |
| `monotonic_ns`     |           int |      yes | Local monotonic timestamp for ordering/debugging.                       |
| `conn_id`          |        string |      yes | Unique source connection/run identifier.                                |
| `seq`              |           int |      yes | Local sequence number per connection/task, or `-1` when not applicable. |
| `payload`          | object/string |      yes | Original source payload preserved as faithfully as practical.           |

### Raw Schema Names

Use these schema names unless there is a specific reason to add a new one:

```text
raw.market_event.v1       # WebSocket/SSE market event
raw.rest_snapshot.v1      # REST snapshot or REST response captured as data
raw.alert_event.v1        # TradingView/user alert webhook event
raw.recorder_error.v1     # recorder/source/transport error event
raw.sse_line.v1           # optional non-data SSE line preservation
```

---

## 2. Raw REST Snapshot Schema

REST snapshots use the normal raw envelope with `schema = raw.rest_snapshot.v1`.

```json
{
  "schema": "raw.rest_snapshot.v1",
  "source": "aster",
  "transport": "rest",
  "stream": "depth_snapshot_1000",
  "canonical_symbol": "BTCUSD",
  "source_symbol": "BTCUSDT",
  "ts_recv_ns": 1770000000000000000,
  "ts_recv_utc": "2026-04-30T14:00:00.123456Z",
  "monotonic_ns": 123456789000,
  "conn_id": "aster-rest-depth",
  "seq": -1,
  "payload": {
    "status": 200,
    "request_ts_ns": 1770000000000000000,
    "url": "https://fapi.asterdex.com/fapi/v1/depth",
    "params": {"symbol": "BTCUSDT", "limit": 1000},
    "data": {}
  }
}
```

Recommended `payload` fields:

| Field           | Description                              |
| --------------- | ---------------------------------------- |
| `status`        | HTTP status code.                        |
| `request_ts_ns` | Local timestamp before request was sent. |
| `url`           | Request URL without secrets.             |
| `params`        | Query params without secrets.            |
| `data`          | Exact decoded provider response.         |

---

## 3. Raw Alert Event Schema

TradingView and other alert webhooks should be wrapped as `raw.alert_event.v1`.

```json
{
  "schema": "raw.alert_event.v1",
  "source": "tradingview",
  "transport": "webhook",
  "stream": "alert",
  "canonical_symbol": "BTCUSD",
  "source_symbol": "BTCUSD",
  "ts_recv_ns": 1770000000000000000,
  "ts_recv_utc": "2026-04-30T14:00:00.123456Z",
  "monotonic_ns": 123456789000,
  "conn_id": "tradingview-webhook",
  "seq": -1,
  "payload": {
    "event": "swing_choch",
    "alert_name": "Swing CHoCH Any"
  }
}
```

The webhook receiver should return quickly and avoid expensive processing in the request path.

---

## 4. Normalized Tables

Normalized tables are derived from raw files. They should not be the only copy of data.

All normalized tables should include provenance fields where practical:

```text
raw_file
raw_line_number
source
symbol
```

If line numbers are expensive to maintain, use `raw_file` plus `source_sequence` or another stable locator.

---

## 4.1 `pyth_prices`

Historical/live Pyth price feed updates.

| Column            |            Type | Description                           |
| ----------------- | --------------: | ------------------------------------- |
| `ts_event`        |       timestamp | Pyth publish/event time if available. |
| `ts_recv`         |       timestamp | Local receive time.                   |
| `symbol`          |          string | Canonical symbol, e.g. `BTCUSD`.      |
| `price`           |   decimal/float | Decoded price.                        |
| `conf`            |   decimal/float | Decoded confidence interval.          |
| `expo`            |             int | Pyth exponent from raw payload.       |
| `publish_time`    |   timestamp/int | Pyth publish time.                    |
| `price_raw`       | string/int/null | Raw integer price if present.         |
| `conf_raw`        | string/int/null | Raw integer confidence if present.    |
| `source`          |          string | `pyth`.                               |
| `raw_file`        |          string | Source raw file path.                 |
| `raw_line_number` |        int/null | Line number or stable locator.        |

---

## 4.2 `trades`

Trade or aggregate trade stream normalized rows.

| Column            |               Type | Description                                                   |
| ----------------- | -----------------: | ------------------------------------------------------------- |
| `ts_event`        |          timestamp | Source event/trade time.                                      |
| `ts_recv`         |          timestamp | Local receive time.                                           |
| `source`          |             string | Provider, e.g. `aster`.                                       |
| `symbol`          |             string | Canonical symbol.                                             |
| `source_symbol`   |             string | Provider symbol.                                              |
| `trade_id`        |    string/int/null | Trade ID if raw trades are available.                         |
| `agg_trade_id`    |    string/int/null | Aggregate trade ID if applicable.                             |
| `first_trade_id`  |    string/int/null | First trade ID in aggregate.                                  |
| `last_trade_id`   |    string/int/null | Last trade ID in aggregate.                                   |
| `price`           |      decimal/float | Trade price.                                                  |
| `qty`             |      decimal/float | Base quantity.                                                |
| `quote_qty`       | decimal/float/null | Quote quantity, if available or computed.                     |
| `is_buyer_maker`  |          bool/null | Source maker-side flag.                                       |
| `side_inferred`   |        string/null | Optional normalized side inference: `buy`, `sell`, `unknown`. |
| `raw_file`        |             string | Source raw file path.                                         |
| `raw_line_number` |           int/null | Source record locator.                                        |

---

## 4.3 `book_ticker`

L1/top-of-book updates.

| Column            |            Type | Description                                 |
| ----------------- | --------------: | ------------------------------------------- |
| `ts_event`        |       timestamp | Source event/transaction time if available. |
| `ts_recv`         |       timestamp | Local receive time.                         |
| `source`          |          string | Provider.                                   |
| `symbol`          |          string | Canonical symbol.                           |
| `source_symbol`   |          string | Provider symbol.                            |
| `update_id`       | int/string/null | Provider update ID.                         |
| `bid_price`       |   decimal/float | Best bid price.                             |
| `bid_qty`         |   decimal/float | Best bid size.                              |
| `ask_price`       |   decimal/float | Best ask price.                             |
| `ask_qty`         |   decimal/float | Best ask size.                              |
| `mid`             |   decimal/float | `(bid_price + ask_price) / 2`.              |
| `spread`          |   decimal/float | `ask_price - bid_price`.                    |
| `spread_bps`      |   decimal/float | Spread in basis points relative to mid.     |
| `raw_file`        |          string | Source raw file path.                       |
| `raw_line_number` |        int/null | Source record locator.                      |

---

## 4.4 `mark_price`

Perpetual mark/index/funding data.

| Column                   |               Type | Description                          |
| ------------------------ | -----------------: | ------------------------------------ |
| `ts_event`               |          timestamp | Source event time.                   |
| `ts_recv`                |          timestamp | Local receive time.                  |
| `source`                 |             string | Provider.                            |
| `symbol`                 |             string | Canonical symbol.                    |
| `source_symbol`          |             string | Provider symbol.                     |
| `mark_price`             |      decimal/float | Mark price.                          |
| `index_price`            | decimal/float/null | Index price.                         |
| `estimated_settle_price` | decimal/float/null | Estimated settle price if available. |
| `funding_rate`           | decimal/float/null | Current funding rate.                |
| `next_funding_time`      | timestamp/int/null | Next funding timestamp.              |
| `raw_file`               |             string | Source raw file path.                |
| `raw_line_number`        |           int/null | Source record locator.               |

---

## 4.5 `liquidations`

Forced-order/liquidation stream events.

| Column            |               Type | Description                         |
| ----------------- | -----------------: | ----------------------------------- |
| `ts_event`        |          timestamp | Source event/trade time.            |
| `ts_recv`         |          timestamp | Local receive time.                 |
| `source`          |             string | Provider.                           |
| `symbol`          |             string | Canonical symbol.                   |
| `source_symbol`   |             string | Provider symbol.                    |
| `side`            |        string/null | Buy/sell side as source reports it. |
| `order_type`      |        string/null | Source order type.                  |
| `price`           | decimal/float/null | Order price.                        |
| `avg_price`       | decimal/float/null | Average fill price if available.    |
| `qty`             | decimal/float/null | Original quantity.                  |
| `filled_qty`      | decimal/float/null | Filled quantity.                    |
| `status`          |        string/null | Source status.                      |
| `notional`        | decimal/float/null | Computed notional if possible.      |
| `raw_file`        |             string | Source raw file path.               |
| `raw_line_number` |           int/null | Source record locator.              |

---

## 4.6 `l2_diff_depth`

Full diff-depth L2 deltas. This table is for later reconstruction, not necessarily direct strategy use.

| Column                 |        Type | Description                                |
| ---------------------- | ----------: | ------------------------------------------ |
| `ts_event`             |   timestamp | Source event time.                         |
| `ts_recv`              |   timestamp | Local receive time.                        |
| `source`               |      string | Provider.                                  |
| `symbol`               |      string | Canonical symbol.                          |
| `source_symbol`        |      string | Provider symbol.                           |
| `first_update_id`      |    int/null | First update ID in event, often `U`.       |
| `final_update_id`      |    int/null | Final update ID in event, often `u`.       |
| `prev_final_update_id` |    int/null | Previous final update ID, often `pu`.      |
| `bids_changed`         | list/struct | Changed bid levels as source reports them. |
| `asks_changed`         | list/struct | Changed ask levels as source reports them. |
| `raw_file`             |      string | Source raw file path.                      |
| `raw_line_number`      |    int/null | Source record locator.                     |

---

## 4.7 `l2_partial_depth`

Partial top-N L2 updates/snapshots.

| Column            |        Type | Description                          |
| ----------------- | ----------: | ------------------------------------ |
| `ts_event`        |   timestamp | Source event time.                   |
| `ts_recv`         |   timestamp | Local receive time.                  |
| `source`          |      string | Provider.                            |
| `symbol`          |      string | Canonical symbol.                    |
| `source_symbol`   |      string | Provider symbol.                     |
| `levels`          |         int | Number of levels requested/provided. |
| `bids`            | list/struct | Bid levels.                          |
| `asks`            | list/struct | Ask levels.                          |
| `raw_file`        |      string | Source raw file path.                |
| `raw_line_number` |    int/null | Source record locator.               |

---

## 4.8 `tv_alerts`

TradingView/user alert events.

| Column                        |                  Type | Description                                                          |
| ----------------------------- | --------------------: | -------------------------------------------------------------------- |
| `ts_recv`                     |             timestamp | Local receive timestamp.                                             |
| `source`                      |                string | `tradingview` or other alert source.                                 |
| `event`                       |                string | Alert event, e.g. `swing_choch`, `supertrend_signal`, `rvol_rising`. |
| `alert_name`                  |                string | Alert display name.                                                  |
| `symbol`                      |                string | Alert symbol.                                                        |
| `ticker`                      |           string/null | Ticker from alert payload.                                           |
| `exchange`                    |           string/null | Exchange from alert payload.                                         |
| `interval`                    |           string/null | TradingView interval.                                                |
| `bar_time`                    | timestamp/string/null | Alert bar time.                                                      |
| `fired_at`                    | timestamp/string/null | TradingView fired timestamp.                                         |
| `open`                        |    decimal/float/null | OHLC open.                                                           |
| `high`                        |    decimal/float/null | OHLC high.                                                           |
| `low`                         |    decimal/float/null | OHLC low.                                                            |
| `close`                       |    decimal/float/null | OHLC close.                                                          |
| `volume`                      |    decimal/float/null | Volume.                                                              |
| `swing_choch_direction`       |              int/null | `1` bullish, `-1` bearish, `0` none.                                 |
| `internal_choch_direction`    |              int/null | `1` bullish, `-1` bearish, `0` none.                                 |
| `ma_1`                        |    decimal/float/null | MA value from alert payload.                                         |
| `ma_1_trend`                  |              int/null | `1` rising, `-1` falling, `0` neutral.                               |
| `ma_2`                        |    decimal/float/null | Optional second MA.                                                  |
| `ma_cross`                    |              int/null | `1` cross up, `-1` cross down, `0` none.                             |
| `supertrend_signal_direction` |              int/null | `1` long, `-1` short, `0` none.                                      |
| `supertrend_regime_direction` |              int/null | `1` bull, `-1` bear, `0` neutral.                                    |
| `supertrend_strength_percent` |    decimal/float/null | Supertrend strength percent.                                         |
| `raw_json`                    |         object/string | Original alert payload.                                              |
| `raw_file`                    |                string | Source raw file path.                                                |
| `raw_line_number`             |              int/null | Source record locator.                                               |

---

## 5. Feature Table Guidelines

Feature tables should use partitioned Parquet later. Suggested metadata columns:

```text
symbol
timeframe
ts_start
ts_end
feature_version
source_dataset_version
config_hash
created_at
```

Feature-specific columns should be explicitly named with units:

```text
spread_bps
range_pct
body_pct
rvol_ratio
funding_rate
pyth_vs_mark_bps
bid_depth_10bps
ask_depth_10bps
imbalance_10bps
```

---

## 6. Backtest Result Guidelines

Backtest results should include:

```text
run_id
strategy_name
strategy_version
code_version / git_commit
config_hash
source_dataset_version
symbol
start_time
end_time
fees_model
slippage_model
fill_model
initial_balance
metrics
trades_path
created_at
```

Individual simulated trades should include:

```text
run_id
trade_id
symbol
direction
entry_time
entry_price
exit_time
exit_price
stop_loss
tp1
tp2
tp3
size
leverage
fees
funding
pnl
pnl_pct
r_multiple
max_favorable_excursion
max_adverse_excursion
exit_reason
```

---

## 7. Schema Evolution Rules

* Additive changes are preferred.
* Breaking changes need a new schema version or migration note.
* Update this file and `docs/agent-guidebook.md` when durable schema assumptions change.
* Keep raw schemas stable and conservative.

---

