# Aster Provider Reference

This document defines the Aster futures API integration used by this repository.

Aster is the primary perpetual-market market-data source for BTC and ETH research in this repo. Record Aster independently from Pyth oracle data and TradingView alert labels.

## Documentation State

This reference was updated against the current official Aster docs on 2026-04-30.

Primary sources used:

* Official Aster API Documentation at `docs.asterdex.com`
* Market data endpoint reference
* WebSocket stream reference
* Depth recovery guidance
* Current error and rate-limit guidance

---

## Role In The Project

Use Aster for:

* Aggregate trades and market trade flow.
* L1 book ticker.
* Mark price, index price, and funding context.
* Liquidation and force-order events.
* Reference klines.
* Partial depth and diff-depth streams.
* REST depth snapshots for later local order-book reconstruction.

Aster data is a market-data source, not a complete execution model. Later replay or execution simulation may also need exchange rules, fees, oracle logic, funding assumptions, and possibly private account streams if those are ever explicitly scoped.

---

## Base URLs And General Conventions

REST base URL:

```text
https://fapi.asterdex.com
```

WebSocket base URL:

```text
wss://fstream.asterdex.com
```

Current documented general conventions:

* All endpoints return JSON.
* All time and timestamp fields are represented in milliseconds.
* Data is returned oldest first when order is applicable.
* Market-data work should prefer WebSocket streams whenever possible to reduce rate-limit pressure.

---

## Symbols

Canonical-to-source mapping for the current repo target:

```yaml
BTCUSD:
  aster_symbol: BTCUSDT

ETHUSD:
  aster_symbol: ETHUSDT
```

Symbol naming notes:

* Store both canonical and source symbols in raw envelopes.
* All stream names, including symbols, must be lowercase.
* Use `btcusdt` and `ethusdt` in stream paths.

---

## Current Rate-Limit Guidance

The current official docs expose rate-limit information through `GET /fapi/v1/exchangeInfo`.

Current documented limits include:

```text
REQUEST_WEIGHT: 2400 per minute
ORDERS: 1200 per minute
```

Important implementation notes:

* Every response includes `X-MBX-USED-WEIGHT-*` headers for current IP usage.
* HTTP 429 indicates rate-limit violation.
* HTTP 418 indicates automated IP ban after repeated limit abuse.
* Aster explicitly recommends using WebSocket streams for live updates whenever possible.

Recorder implications:

* Use REST sparingly for snapshots and metadata.
* Do not poll market-data endpoints when a stream exists.
* Back off immediately after 429s.

---

## REST Endpoints Most Relevant To This Repo

The current official market-data docs use `/fapi/v1/...` routes for the endpoints relevant to recorder work.

Connectivity and clock:

```text
GET /fapi/v1/ping
GET /fapi/v1/time
GET /fapi/v1/exchangeInfo
```

Primary raw-recorder snapshot and validation endpoints:

```text
GET /fapi/v1/depth
GET /fapi/v1/premiumIndex
GET /fapi/v1/fundingRate
GET /fapi/v1/ticker/price
GET /fapi/v1/ticker/bookTicker
GET /fapi/v1/klines
GET /fapi/v1/indexPriceKlines
GET /fapi/v1/markPriceKlines
GET /fapi/v1/trades
GET /fapi/v1/historicalTrades
GET /fapi/v1/aggTrades
```

Depth snapshot endpoint for recorder work:

```text
GET /fapi/v1/depth?symbol=BTCUSDT&limit=1000
GET /fapi/v1/depth?symbol=ETHUSDT&limit=1000
```

Depth response fields documented today include:

```text
lastUpdateId
E
T
bids
asks
```

Implementation note:

* The previous draft referenced `/fapi/v3/...` market-data routes. The current official docs for recorder-relevant endpoints are centered on `/fapi/v1/...`, so this reference has been updated accordingly.

---

## WebSocket Access And Limits

Current documented WebSocket access modes:

```text
Raw stream:      /ws/<streamName>
Combined stream: /stream?streams=<stream1>/<stream2>/...
```

Combined stream wrapper:

```json
{"stream": "<streamName>", "data": <rawPayload>}
```

Current documented connection rules:

* A single connection is valid for 24 hours.
* The server sends a ping every 5 minutes.
* If no pong is received within 15 minutes, the connection is closed.
* Unsolicited pong frames are allowed.
* Connections are limited to 10 incoming messages per second.
* A single connection can subscribe to a maximum of 200 streams.

Recorder implications:

* Reconnect forever.
* Treat 24-hour disconnects as expected.
* Prefer a fixed combined-stream URL or a tightly controlled subscription pattern.
* Split connections if stream count or message volume requires it.

---

## v1 Stream Set For This Repo

Current initial target streams for both BTCUSDT and ETHUSDT:

```yaml
aster_streams:
  - aggTrade
  - bookTicker
  - markPrice@1s
  - forceOrder
  - kline_1m
  - kline_5m
  - kline_15m
  - depth20@100ms
  - depth@100ms
```

These should remain config-driven.

Recommended implementation split:

* Capture non-depth market streams first.
* Add snapshots and depth streams only after the general market-stream path is stable.

---

## Stream Details

### Aggregate Trades: `aggTrade`

Stream name:

```text
<symbol>@aggTrade
```

Current documented update speed:

```text
100ms
```

Important documented fields:

```text
e
E
s
a
p
q
f
l
T
m
```

Use for:

* Taker flow.
* Trade intensity.
* Later custom bar building.

### Book Ticker: `bookTicker`

Stream name:

```text
<symbol>@bookTicker
```

Current documented update speed:

```text
real-time
```

Important documented fields:

```text
e
u
E
T
s
b
B
a
A
```

Use for:

* Best bid and ask.
* Spread and mid.
* L1 liquidity changes.

### Mark Price: `markPrice@1s`

Stream names:

```text
<symbol>@markPrice
<symbol>@markPrice@1s
```

Current documented update speeds:

```text
3000ms or 1000ms
```

Important documented fields:

```text
e
E
s
p
i
P
r
T
```

Use for:

* Mark price.
* Index price.
* Funding rate.
* Next funding timestamp.

### Liquidations: `forceOrder`

Stream name:

```text
<symbol>@forceOrder
```

Current documented behavior:

* Only the latest liquidation order within a 1000ms interval is pushed.
* No event is pushed if no liquidation occurs in the interval.

Important documented nested order fields include:

```text
o.s
o.S
o.o
o.f
o.q
o.p
o.ap
o.X
o.l
o.z
o.T
```

### Reference Klines: `kline_<interval>`

Stream name:

```text
<symbol>@kline_<interval>
```

Current documented update speed:

```text
250ms if existing
```

Supported intervals in current docs include:

```text
1m 3m 5m 15m 30m 1h 2h 4h 6h 8h 12h 1d 3d 1w 1M
```

Repo guidance:

* Capture only the intervals you actually plan to reference.
* Derive other bars later from trades if needed.

### Partial Depth

Current documented stream names:

```text
<symbol>@depth<levels>
<symbol>@depth<levels>@500ms
<symbol>@depth<levels>@100ms
```

Valid documented `<levels>` values:

```text
5, 10, 20
```

Current documented update speeds:

```text
250ms, 500ms, or 100ms
```

### Diff Depth

Current documented stream names:

```text
<symbol>@depth
<symbol>@depth@500ms
<symbol>@depth@100ms
```

Current documented fields:

```text
e
E
T
s
U
u
pu
b
a
```

Current documented update speeds:

```text
250ms, 500ms, 100ms
```

---

## Snapshot And Depth Recovery Guidance

Current official local-order-book guidance is explicit and is important even if the recorder does not reconstruct books yet.

Documented recovery outline:

1. Open the depth stream and buffer events.
2. Fetch a REST depth snapshot.
3. Drop buffered events where `u < lastUpdateId` from the snapshot.
4. The first processed event must satisfy `U <= lastUpdateId <= u`.
5. For subsequent events, `pu` must equal the previous event's `u`.
6. If continuity fails, restart from a new snapshot.
7. Quantities in depth events are absolute quantities for price levels.
8. Quantity `0` means remove the price level.

Recorder implications:

* Preserve `lastUpdateId`, `U`, `u`, `pu`, bids, asks, and both source and local timestamps.
* Keep reconstruction out of the ingest path unless explicitly scoped later.
* Validate depth stream names and behavior in practice before declaring the phase stable.

---

## Authenticated And Private Endpoints

Authenticated endpoints exist and use HMAC SHA256 signatures, timestamp checks, and `recvWindow` handling.

Current repo guidance:

* Private endpoints and user streams are out of current raw-recorder scope unless the user explicitly expands scope.
* Do not add live-trading or private-account behavior into the recorder by default.

Useful future notes from current docs:

* Signed endpoints require `timestamp` and `signature`.
* Aster documents `recvWindow` timing behavior and HMAC SHA256 signing.
* User data streams use a `listenKey` that expires after 60 minutes unless kept alive.

---

## Error And Operational Notes Useful During Implementation

Current documented behaviors worth preserving in future implementation notes:

* HTTP 503 can mean execution status is unknown on signed endpoints; do not automatically treat it as a simple failure for private trading actions.
* `exchangeInfo` is the current runtime truth for rate limits and symbol filters.
* `pricePrecision` and `quantityPrecision` in `exchangeInfo` should not be treated as `tickSize` and `stepSize`; use filters instead.
* Repeatedly ignoring 429s can lead to 418 auto-bans.

These are mostly out-of-scope for the initial recorder, but they are useful future reference and worth keeping here.

---

## Implementation Guidance

* Prefer WebSockets for live market data and REST for snapshots and metadata.
* Keep stream names config-driven and lowercase.
* Preserve raw combined-stream wrappers where useful for debugging stream routing.
* Split the work into non-depth capture first, depth/snapshot capture second.
* Keep snapshot cadence configurable.
* Update this file whenever observed live behavior differs from the current official docs.

---

## Validation Checklist

* `GET /fapi/v1/ping` works.
* `GET /fapi/v1/time` works.
* `GET /fapi/v1/exchangeInfo` works.
* `GET /fapi/v1/depth?symbol=<symbol>&limit=1000` works.
* The selected WebSocket stream set connects successfully.
* Combined or raw stream routing matches the configured mode.
* Raw files are written under canonical paths.
* Sample files decompress and contain valid JSON lines.
* Required envelope fields exist.
* Depth sequence fields needed for later reconstruction are preserved.
* Reconnect behavior works after forced disconnect or expected 24-hour close.

---

## Notes

Aster is the main live market-data source for this repo, so it is worth keeping this reference operationally precise. When the live behavior differs from prior assumptions, update this file immediately rather than leaving future implementation phases to rediscover the mismatch.