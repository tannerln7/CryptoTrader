# TradingView Provider Reference

This document defines how TradingView alerts are handled in this repository.

TradingView is used as a signal and label source. It is not the source of market truth for replay or backtesting unless a later task explicitly changes that assumption.

## Documentation State

This reference was updated against the current official TradingView webhook docs on 2026-04-30.

Primary sources used:

* TradingView webhook configuration documentation
* TradingView webhook delivery guidance and constraints

---

## Role In The Project

TradingView alerts provide:

* Strategy and indicator signal labels.
* Event timestamps from the charting environment.
* Durable raw alert events that can later be joined with market data.
* Optional downstream notification payloads for other systems.

Examples used in this repo:

```text
Swing CHoCH Any
Supertrend Signal
RVOL Rising
```

---

## Official Webhook Behavior

TradingView webhook alerts are delivered as HTTP POST requests.

Current documented behavior:

* If the alert message is valid JSON, TradingView sends `Content-Type: application/json`.
* If the alert message is not valid JSON, TradingView sends `Content-Type: text/plain`.
* Webhooks are only available when TradingView two-factor authentication is enabled.

Recorder implication:

* Structured payloads intended for machine use should be valid JSON.
* The receiver should explicitly decide how to handle plain-text bodies instead of assuming JSON.

---

## Delivery Constraints That Matter For Implementation

Current documented TradingView constraints:

* Only ports `80` and `443` are accepted.
* Requests to other ports are rejected.
* If the remote server takes longer than about 3 seconds to process the request, the request is canceled.
* IPv6 is not currently supported for webhook delivery.
* Webhooks may occasionally fail to reach the destination and should be monitored in TradingView's alert log.

Current documented sender IPs for allowlisting:

```text
52.89.214.238
34.212.75.30
54.218.53.128
52.32.178.7
```

Implementation implications:

* The webhook path must return quickly.
* Do not do expensive processing in the request path.
* Local development usually needs a reverse proxy, tunnel, or later deployment path that exposes port 80 or 443.
* Optional source IP allowlisting can be considered for deployed receivers.

---

## Security Guidance

Current TradingView docs explicitly warn against putting secrets, credentials, or passwords into webhook bodies.

Repo guidance:

* Do not place API keys, secrets, or credentials inside TradingView alert payloads.
* Prefer structured, non-sensitive fields only.
* If authentication is needed later, use secure endpoint design rather than embedding secrets in the message body.

---

## Alert Message Guidelines

Use structured JSON for alerts intended for recorder ingestion.

Avoid:

* comments
* trailing commas
* smart quotes
* unescaped inner double quotes

Good:

```json
{
  "source": "tradingview",
  "event": "swing_choch",
  "alert_name": "Swing CHoCH Any",
  "symbol": "{{ticker}}",
  "interval": "{{interval}}",
  "close": "{{close}}"
}
```

Bad:

```json
{
  "alert_name": "Swing CHoCH Any", // invalid comment
  "close": "{{close}}",
}
```

Avoid long human-readable notification strings in the raw payload. Prefer structured fields and assemble presentation text later in downstream systems.

---

## Repo Payload Conventions

The fields below are repo conventions built on top of TradingView's generic alert message support. They are not a TradingView standard schema, but they are the preferred structured payload shape for this repo.

Common placeholders used here:

```text
{{ticker}}
{{exchange}}
{{interval}}
{{time}}
{{timenow}}
{{open}}
{{high}}
{{low}}
{{close}}
{{volume}}
```

Repo-specific plot placeholder usage examples:

```text
{{plot("Swing CHoCH Direction")}}
{{plot("Internal CHoCH Direction")}}
{{plot("CM MA 1")}}
{{plot("CM MA 1 Trend")}}
{{plot("CM MA 2")}}
{{plot("CM MA Cross")}}
{{plot("Supertrend Signal Direction")}}
{{plot("Supertrend Regime Direction")}}
{{plot("Supertrend Strength Percent")}}
```

When plot placeholders appear inside JSON strings, escape the inner quotes:

```json
"swing_choch_direction": "{{plot(\"Swing CHoCH Direction\")}}"
```

---

## Canonical Alert Payload Shape For This Repo

Use event-specific payloads, but keep the common envelope stable.

```json
{
  "source": "tradingview",
  "alert_name": "Swing CHoCH Any",
  "event": "swing_choch",
  "symbol": "{{ticker}}",
  "ticker": "{{ticker}}",
  "exchange": "{{exchange}}",
  "interval": "{{interval}}",
  "bar_time": "{{time}}",
  "fired_at": "{{timenow}}",
  "open": "{{open}}",
  "high": "{{high}}",
  "low": "{{low}}",
  "close": "{{close}}",
  "volume": "{{volume}}",
  "swing_choch_direction": "{{plot(\"Swing CHoCH Direction\")}}",
  "internal_choch_direction": "{{plot(\"Internal CHoCH Direction\")}}",
  "ma_1": "{{plot(\"CM MA 1\")}}",
  "ma_1_trend": "{{plot(\"CM MA 1 Trend\")}}",
  "ma_2": "{{plot(\"CM MA 2\")}}",
  "ma_cross": "{{plot(\"CM MA Cross\")}}",
  "supertrend_signal_direction": "{{plot(\"Supertrend Signal Direction\")}}",
  "supertrend_regime_direction": "{{plot(\"Supertrend Regime Direction\")}}",
  "supertrend_strength_percent": "{{plot(\"Supertrend Strength Percent\")}}"
}
```

Variant examples:

For Supertrend alerts:

```json
{
  "alert_name": "Supertrend Signal",
  "event": "supertrend_signal"
}
```

For RVOL alerts:

```json
{
  "alert_name": "RVOL Rising",
  "event": "rvol_rising"
}
```

---

## Direction Field Semantics

Use consistent numeric direction fields:

```text
1  = bullish / long / rising / above / cross up
-1 = bearish / short / falling / below / cross down
0  = neutral / none / no event
```

Known repo fields:

```text
swing_choch_direction
internal_choch_direction
ma_1_trend
ma_cross
supertrend_signal_direction
supertrend_regime_direction
supertrend_price_side
```

---

## Local Webhook Recorder Guidance

If the repo includes a local TradingView webhook receiver, prefer a simple endpoint such as:

```text
POST /webhook/tradingview
```

Expected behavior:

* Accept valid JSON payloads.
* Optionally preserve plain-text bodies explicitly if the project chooses to support them.
* Timestamp receive time immediately.
* Wrap the payload as `raw.alert_event.v1`.
* Write the raw record quickly.
* Return promptly to stay within TradingView's delivery window.

Suggested raw path:

```text
raw/tradingview/webhook/ALL/alert/date=YYYY-MM-DD/hour=HH/part-0000.jsonl.zst
```

---

## Raw Alert Wrapper

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
  "payload": {}
}
```

---

## Implementation Guidance

* Keep the webhook handler lightweight and bounded.
* Do not perform heavy downstream work before responding.
* Prefer JSON payloads for stable machine parsing.
* If local-only testing is needed, use a reverse proxy or tunnel that exposes a TradingView-compatible public port.
* If deployment later becomes public-facing, consider allowlisting the documented TradingView sender IPs.

---

## Validation Checklist

* Payload validates as JSON before it is pasted into TradingView.
* TradingView accepts the alert message without JSON warnings.
* The webhook receiver sees `application/json` when valid JSON is used.
* Raw alert events are written under the expected path.
* Alert fields are preserved under `payload`.
* The handler returns quickly enough for TradingView's delivery expectations.
* Any decision about plain-text bodies is documented and tested.

---

## Notes

TradingView is useful as a durable label and event stream, but it should remain separate from raw exchange and oracle market data. Join these sources later by timestamp when analysis or labeling logic actually needs them.