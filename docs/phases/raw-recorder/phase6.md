# Phase 6 — TradingView Alert and Label Capture

## Overview

This phase adds structured alert capture so later analysis can align TradingView signal events with recorded market data.

The receiver should stay intentionally lightweight and preserve the raw alert payload rather than turning the webhook path into an analytics pipeline.

## Role In Sequence

This phase introduces the first inbound server-facing integration. It should build on the same recorder lifecycle and storage conventions already proven in earlier source phases.

## Objectives

* Accept TradingView webhook POSTs and record them as raw alert events.
* Preserve structured JSON payloads without inventing additional processing in the request path.
* Return quickly and safely under the operational constraints of webhook delivery.
* Keep webhook routing configurable and clearly separated from later notification or analysis systems.

## In Scope

* Webhook bind/host/path configuration.
* JSON and plain-text body handling appropriate for TradingView alerts.
* Raw alert-event wrapping and storage.
* Basic request validation, logging, and local smoke testing.

## Out Of Scope

* Home Assistant formatting or notification fan-out.
* TradingView script authoring.
* Alert outcome analysis.
* Public deployment hardening beyond what is needed for a safe initial receiver.

## Definitive Ending Spot

At the end of this phase, a test TradingView-compatible POST can be received and written as a valid raw alert event, with the request path remaining lightweight and operationally clear.

## Required Validation

* Confirm a valid JSON POST is stored with the expected alert envelope.
* Confirm plain-text requests are either preserved intentionally or rejected intentionally, with the behavior documented.
* Confirm the handler returns quickly enough for webhook delivery expectations.
* Confirm sample output contains required envelope fields and the preserved payload.

## Satisfactory Completion Criteria

* Alert capture is useful as a durable label stream for later joining and analysis.
* The webhook path is simple, bounded, and not overloaded with downstream behavior.
* Operational assumptions about deployment and timeout constraints are documented.

## Notes

* Current TradingView docs confirm that webhook alerts are sent as HTTP POST requests, use `application/json` only when the alert message is valid JSON, and otherwise use `text/plain`.
* Current TradingView docs also note that only ports 80 and 443 are accepted and that requests can be canceled if the remote server takes longer than about 3 seconds to process them.
* These constraints favor a minimal request path that validates, wraps, queues or writes quickly, and avoids long blocking work.

## Docs To Keep In Sync

* `docs/reference/providers/tradingview.md`
* `config/config.example.yaml`
* `docs/operations/change-log.md`
* `docs/operations/implementation-status.md`
