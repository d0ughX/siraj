"""Paper engine (skeleton). Flow, always in this order:

  candle -> signal (frozen rule sketch) -> typed intent -> gateway ->
  simulated fill at the candle close (maker fee applied) -> ledger event.

There is deliberately NO order-placement path. Simulated fills are not
evidence of live profitability; they are the paper record the research
qualification gates (blueprint v2 §9) will judge.
"""
import argparse
import json

from . import config as config_mod
from .fees import net_pnl_pct
from .gateway import OrderIntent, check_intent
from .ladder import DailyStop, WinLadder
from .ledger import Ledger
from .regimes import classify
from .sizing import apply_dial, position_size


def atr(candles, period=14):
    if len(candles) < 2:
        return 0.0
    trs = []
    prev_close = candles[0]["close"]
    for candle in candles[1:]:
        tr = max(candle["high"] - candle["low"],
                 abs(candle["high"] - prev_close),
                 abs(candle["low"] - prev_close))
        trs.append(tr)
        prev_close = candle["close"]
    window = trs[-period:]
    return sum(window) / len(window)


def run(candles, rules, equity_start=10.0):
    dial = apply_dial(equity_start, rules)
    ledger = Ledger()
    ladder = WinLadder(rules)
    stop = DailyStop(rules)
    equity = equity_start
    open_risk = 0.0
    ledger.append("engine_start", {"rules_version": rules["version"],
                                  "rules_sha256": rules["_sha256"],
                                  "equity_start": equity_start})
    for i, candle in enumerate(candles):
        if i < 3:
            continue
        window = candles[max(0, i - 20):i]
        a = atr(window)
        if a <= 0:
            continue
        # Skeleton signal (intraday trend sketch): close above the mean of
        # the last 3 closes, with a rising last close. Real sleeve signals
        # replace this function under frozen-rule versioning, never inline.
        closes = [c["close"] for c in candles[max(0, i - 3):i]]
        if not (candle["close"] > sum(closes) / len(closes)
                and candle["close"] > candles[i - 1]["close"]):
            continue
        regime, factor = classify(9, False, rules)  # skeleton: NY morning
        size = position_size(equity, dial["per_trade_risk"] * factor,
                             a, 2.0, candle["close"])
        price = candle["close"]
        stop_px = price - 2.0 * a
        target_px = price + 5.0 * (2.0 * a)  # 5:1 target multiple
        intent = OrderIntent(
            pair="XBTUSDT", side="buy", units=size["units"], price=price,
            stop=stop_px, target=target_px, time_stop_bars=10,
            sleeve="intraday_trend", is_maker=True,
            expected_edge_pct=0.02, volume_24h_usd=5_000_000,
            spread_pct=0.0005, risk_amount=size["risk_amount"])
        ok, reasons = check_intent(intent, rules, equity, open_risk,
                                   stop.tripped)
        ledger.append("intent", {"ok": ok, "reasons": reasons,
                                 "pair": intent.pair, "price": price})
        if not ok:
            continue
        # Simulated fill at close; outcome decided by the NEXT candle in the
        # fixture (hit target first in this skeleton's simple model).
        nxt = candles[i + 1] if i + 1 < len(candles) else candle
        if nxt["high"] >= target_px:
            gross = 5.0 * dial["per_trade_risk"]
            won = True
        elif nxt["low"] <= stop_px:
            gross = -1.0 * dial["per_trade_risk"]
            won = False
        else:
            continue  # still open at fixture end; no fill recorded
        net = net_pnl_pct(gross, True, rules)
        pnl_usd = equity * net
        equity += pnl_usd
        ladder.record(won)
        stop.add_pnl(net)
        ledger.append("fill", {"pair": intent.pair, "won": won,
                              "gross_pct": gross, "net_pct": net,
                              "pnl_usd": pnl_usd, "equity": equity})
    ledger.append("engine_end", {"equity_end": equity,
                                "ladder_tier": ladder.tier,
                                "daily_stop_tripped": stop.tripped})
    ok, bad_seq = ledger.verify()
    return {"equity_start": equity_start, "equity_end": equity,
            "ledger_events": len(ledger.events), "ledger_ok": ok,
            "bad_seq": bad_seq, "ledger_pnl": ledger.replay(),
            "ladder_tier": ladder.tier}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", default=None)
    parser.add_argument("--live-public", action="store_true")
    parser.add_argument("--pairs", default="XBTUSDT,ETHUSDT")
    args = parser.parse_args()
    rules = config_mod.load_rules()
    if args.live_public:
        from .kraken_public import get_ticker
        tickers = get_ticker([p for p in args.pairs.split(",") if p])
        print(json.dumps({"mode": "live_public_readonly",
                          "tickers": tickers}, indent=2))
        print("NOTE: live-public mode reads quotes only. No orders placed.")
        return
    if not args.fixtures:
        parser.error("--fixtures is required unless --live-public is set")
    with open(args.fixtures) as fh:
        candles = json.load(fh)
    print(json.dumps(run(candles, rules), indent=2))


if __name__ == "__main__":
    main()
