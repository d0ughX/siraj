# SIRAJ — Personal Trading Desk (skeleton, paper-only)

**Name:** SIRAJ (Arabic: a lamp, a light in the dark — guidance through noise).
**Status:** Code skeleton, version 0.1. PAPER ONLY. No live orders, no private API
calls, no keys. The paper engine simulates fills against market data; it never
places an order on any exchange.

## What this is

A deterministic rules engine for day trading crypto on Kraken Pro, hosted on
Render, built to blueprint v2 (`../blueprint-v2-2026-10-24.md`):

- Frozen rules in `rules/frozen-rules.yaml` (tag + hash before any scoring).
- One shared risk budget across three trading-only sleeves.
- A pre-trade gateway that every order intent must pass.
- An append-only, hash-chained event ledger (if it is not in the log, it did
  not happen).
- A daily stop that only the owner can restart.
- A win ladder: step up every 10 wins total; window restarts after 3
  consecutive losses.

## Disclaimer (baked in, non-negotiable)

This is a personal learning tool built by Jonathan for himself. It is not a
guarantee, not financial advice, not a fiduciary service. Jonathan is not a
banker and holds no stock licenses. Anyone who runs a copy risks losing money,
including all of it, on their own decision. No legal recourse is offered or
implied by sharing it.

## Layout

```
rules/frozen-rules.yaml   Frozen rule set (v0.1). Change = new version + re-validation.
siraj/config.py           Loads and validates the frozen rules.
siraj/fees.py             Kraken Pro fee model (Tier 1 starting point).
siraj/sizing.py           Volatility sizing + portfolio dial.
siraj/ladder.py           Win ladder + daily-stop state.
siraj/gateway.py          Pre-trade checks; typed order intents only.
siraj/ledger.py           Append-only hash-chained event ledger + replay.
siraj/regimes.py          Session/regime classification (IANA zones).
siraj/paper_engine.py     Paper engine: signals -> intents -> gateway -> simulated fills.
siraj/kraken_public.py    Public (unauthenticated) Kraken market-data client.
tests/test_siraj.py       Unit tests (stdlib unittest, no dependencies).
render.yaml               Render service definition (worker).
```

## Run the tests

```sh
python3 -m unittest discover -s tests -v
```

## Run the paper engine (fixture replay, no network)

```sh
python3 -m siraj.paper_engine --fixtures tests/fixtures/sample_candles.json
```

With live public market data (read-only, still simulated fills, still no orders):

```sh
python3 -m siraj.paper_engine --live-public --pairs XBTUSDT,ETHUSDT
```

## Deploying to Render (later step, needs owner's go-ahead)

1. Push this directory to a new, separate GitHub repository.
2. In Render, create a new Worker service from that repository (`render.yaml`
   already defines it).
3. Set NO secrets for the skeleton: the paper engine needs none. Live API keys
   are a separate, explicitly approved step and are always trade-only scope
   (never withdrawal) when that day comes.

## What is deliberately NOT in this skeleton

- No private Kraken API client, no order placement, no withdrawals.
- No margin trading (default OFF; conditional bar in the blueprint).
- No options, stocks, ETFs, or stock indices (Kraken spot is crypto-only).
- No model-driven decisions: no chat model decides, vetoes, resizes, re-times,
  or cancels any order. Models work in the research cage only.
- No self-modifying rules: "learning" is a logged monthly review that produces
  proposals, which must pass frozen validation + owner approval.
