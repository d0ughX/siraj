"""Pre-trade gateway. Every signal becomes a typed order intent and must
pass EVERY check before it may become an order. In the skeleton there is no
order-placement path at all: passing intents go to the paper engine's
simulated fills. A failed check is a rejection with a reason, logged.
"""
from dataclasses import dataclass, field


@dataclass
class OrderIntent:
    pair: str
    side: str            # "buy" or "sell"
    units: float
    price: float
    stop: float
    target: float
    time_stop_bars: int
    sleeve: str
    is_maker: bool = True
    expected_edge_pct: float = 0.0
    volume_24h_usd: float = 0.0
    spread_pct: float = 0.0
    risk_amount: float = 0.0


def check_intent(intent, rules, equity, open_risk, daily_stop_tripped):
    """Returns (ok, [reasons]). All reasons are returned, not just the first,
    so rejections are auditable."""
    reasons = []
    t = rules["trades"]
    dial = rules["dial"]

    if intent.side not in ("buy", "sell"):
        reasons.append("invalid side")
    if intent.units <= 0 or intent.price <= 0:
        reasons.append("non-positive units/price")
    if t["precise_only"]:
        if not intent.stop or not intent.target or not intent.time_stop_bars:
            reasons.append("precise_only: entry+stop+target+time_stop required")
    if intent.side == "buy" and intent.stop >= intent.price:
        reasons.append("stop must be below entry for a buy")
    if intent.side == "sell" and intent.stop <= intent.price:
        reasons.append("stop must be above entry for a sell")
    if intent.sleeve not in rules["sleeves"]:
        reasons.append("unknown sleeve")
    if t["volume_filter"]:
        if intent.volume_24h_usd < t["min_24h_volume_usd"]:
            reasons.append("volume below minimum")
        if intent.spread_pct > t["max_spread_pct"]:
            reasons.append("spread above maximum")
    if t["maker_first"] and not intent.is_maker:
        reasons.append("maker_first: taker intent rejected in skeleton")
    if intent.risk_amount > equity * dial["per_trade_risk_ceiling"]:
        reasons.append("per-trade risk above ceiling")
    if open_risk + intent.risk_amount > equity * dial["max_open_risk"]:
        reasons.append("portfolio heat cap exceeded")
    if daily_stop_tripped:
        reasons.append("daily stop tripped; owner restart required")
    # reward:risk sanity: target distance must reach the frozen multiple
    if intent.side == "buy" and intent.target > 0 and intent.stop > 0:
        reward = intent.target - intent.price
        risk = intent.price - intent.stop
        if risk > 0 and reward / risk < rules["trades"]["reward_to_risk_target"]:
            reasons.append("reward:risk below 5:1 target")
    if intent.side == "sell" and intent.target > 0 and intent.stop > 0:
        reward = intent.price - intent.target
        risk = intent.stop - intent.price
        if risk > 0 and reward / risk < rules["trades"]["reward_to_risk_target"]:
            reasons.append("reward:risk below 5:1 target")
    return (len(reasons) == 0, reasons)
