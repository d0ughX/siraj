"""Volatility sizing. Never sized by conviction: size comes from the formula
alone. size = (equity * per-trade risk) / (ATR * stop multiple).
"""


def position_size(equity, per_trade_risk, atr, stop_multiple, price):
    if atr <= 0 or stop_multiple <= 0 or price <= 0:
        raise ValueError("atr, stop_multiple and price must be positive")
    risk_amount = equity * per_trade_risk
    risk_per_unit = atr * stop_multiple
    units = risk_amount / risk_per_unit
    notional = units * price
    return {"units": units, "notional": notional, "risk_amount": risk_amount}


def apply_dial(equity, rules, level="moderately_aggressive"):
    dial = rules["dial"]["levels"][level]
    return {"target_vol_annual": dial["target_vol_annual"],
            "per_trade_risk": dial["per_trade_risk"],
            "max_open_risk": dial["max_open_risk"]}


def sleeve_risk_budget(total_risk, rules, sleeve):
    return total_risk * rules["sleeves"][sleeve]
