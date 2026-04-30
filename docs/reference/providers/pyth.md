# Pyth Provider Reference

This document defines the Pyth integration used by this repository.

Pyth is the oracle and reference-price source for BTC/USD and ETH/USD. It should be recorded independently from Aster market data and TradingView alert labels.

## Documentation State

This reference was updated against the current public Pyth docs on 2026-04-30.

Primary sources used:

* Pyth Fetch Price Updates
* Pyth Rate Limits
* Pyth Hermes API Instances and Providers
* Pyth Historical Price Data (Benchmarks)

---

## Role In The Project

Use Pyth for:

* Oracle and reference price history.
* Pyth-vs-market divergence features.
* DEX oracle context.
* Later exact-window validation around trades or alerts.

Do not use Pyth alone as an executable fill model unless later execution logic explicitly supports that assumption.

---

## Hermes Access Model

Public Hermes endpoint:

```text
https://hermes.pyth.network
```

Important implementation note:

* Pyth documents the public Hermes endpoint as suitable for testing and development.
* For production-grade deployments, Pyth recommends using node providers for resilience and decentralization.

Current public/provider notes in the docs:

* Public Hermes: `https://hermes.pyth.network`
* Hermes Beta for selected testnet use cases: `https://hermes-beta.pyth.network`
* Production integrations are encouraged to use a node provider rather than depending solely on the public endpoint.

---

## Live Streaming Endpoint

Hermes live streaming endpoint:

```text
GET /v2/updates/price/stream?ids[]=<price_id>&ids[]=<price_id>
```

Example pattern:

```text
https://hermes.pyth.network/v2/updates/price/stream?ids[]=<BTC_ID>&ids[]=<ETH_ID>
```

Transport:

```text
Server-Sent Events (SSE)
```

Current documented behavior:

* The endpoint continuously streams updates for the requested feeds.
* The connection automatically closes after 24 hours.
* Clients should implement reconnection logic to maintain continuous updates.

Recorder implication:

* Treat reconnect as baseline behavior, not as optional hardening.
* Preserve raw event payloads as received.
* Reuse a managed HTTP client session rather than creating new sessions repeatedly.
* A bounded live capture run through the repo's `capture-pyth` command succeeded on 2026-04-30 against the public Hermes endpoint and produced valid raw files under the canonical Pyth path layout.

---

## REST Endpoints Most Relevant To This Repo

Latest updates:

```text
GET /v2/updates/price/latest
```

Live stream:

```text
GET /v2/updates/price/stream
```

Interactive API reference:

```text
https://hermes.pyth.network/docs/#/
```

Metadata discovery note:

* Pyth documents that available price feeds and IDs can be fetched via the Hermes metadata APIs.
* This is useful for config generation and feed verification.

---

## Feed IDs And Channel Notes

Current repo target feeds:

```yaml
BTCUSD:
  symbol: BTC/USD
  pyth_id: "0xe62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43"

ETHUSD:
  symbol: ETH/USD
  pyth_id: "0xff61491a931112ddf1bd8147cd1b641375f79f5825126d665480874634fd0ace"
```

Implementation notes:

* Store the configured ID with the `0x` prefix.
* Feed IDs can differ by channel, and Pyth explicitly notes that Stable and Beta channels can use different IDs.
* Re-verify configured IDs against the official feed list or Hermes metadata when creating the initial config scaffold.

---

## Rate Limits

Current official Hermes and Benchmarks rate limit:

```text
30 requests every 10 seconds per IP
```

Penalty behavior:

* Exceeding the limit results in HTTP 429 responses.
* The subsequent penalty window is documented as 60 seconds.

Recorder implications:

* Use one long-lived stream for live updates.
* Do not poll repeatedly for live data.
* Use Benchmarks selectively rather than as a bulk high-frequency backfill strategy.
* Use reconnect backoff after failures.

---

## Raw Stream Handling

Hermes SSE emits `data:` events containing price-update payloads.

Recorder behavior should be:

1. Preserve every `data:` payload as raw JSON.
2. Add local receive timestamps and connection metadata.
3. Optionally preserve non-data SSE lines as `raw.sse_line.v1` if they are useful for debugging transport behavior.
4. Avoid deep interpretation in the ingest path.

Suggested raw envelope:

```json
{
  "schema": "raw.market_event.v1",
  "source": "pyth",
  "transport": "sse",
  "stream": "price_stream",
  "canonical_symbol": "MULTI",
  "source_symbol": "MULTI",
  "ts_recv_ns": 1770000000000000000,
  "ts_recv_utc": "2026-04-30T14:00:00.123456Z",
  "monotonic_ns": 123456789000,
  "conn_id": "pyth-sse-20260430T140000Z-001",
  "seq": 1,
  "payload": {}
}
```

Symbol handling note:

* If a message can be safely attributed to a single configured feed, the recorder may set `canonical_symbol` and `source_symbol` to that feed.
* Otherwise, using `MULTI` at raw ingest is acceptable and normalization can split later.

---

## Payload Notes Useful For Later Normalization

Current Pyth examples show these fields inside price updates:

```text
id
price.price
price.conf
price.expo
price.publish_time
ema_price.price
ema_price.conf
ema_price.expo
ema_price.publish_time
metadata.slot
metadata.proof_available_time
metadata.prev_publish_time
binary.encoding
binary.data
```

Normalization implications:

```text
decoded_price = raw_price * 10^expo
decoded_conf  = raw_conf  * 10^expo
```

Keep decoded and raw values where practical.

---

## Historical Data Guidance

Pyth Benchmarks is suitable for historical lookups at specific timestamps and short intervals.

Current documented endpoints include:

```text
/v1/updates/price/{timestamp}
/v1/updates/price/{timestamp}/{interval}
```

Current documented constraint:

* The interval endpoint supports windows up to 60 seconds.

Recommended use in this repo:

* Use live Hermes recording as the durable forward-looking data source.
* Use Benchmarks for exact windows, audits, spot validation, and targeted historical recovery.
* Do not rely on Benchmarks as the sole mechanism for building large dense history.

---

## Implementation Guidance

* Prefer a single long-lived stream per recorder process unless there is a clear scaling reason to split.
* Treat disconnects and the 24-hour stream reset as expected behavior.
* Preserve payload fidelity and avoid "helpful" mutation in the raw layer.
* Keep feed IDs config-driven.
* If the public Hermes endpoint is used initially, document that choice as development-oriented.

---

## Validation Checklist

* SSE connection opens successfully.
* BTC/USD and ETH/USD updates are received.
* Raw `.jsonl.zst` files are written under canonical paths.
* Sample lines are valid JSON.
* `payload` preserves Hermes update content.
* Reconnect works after a forced disconnect or normal long-lived stream closure.
* No rate-limit issues appear under expected streaming usage.

---

## Notes

Pyth is valuable as an independent reference layer, but it should remain just that at ingest time: a separate oracle and reference stream that later phases can align with exchange and alert data by timestamp.