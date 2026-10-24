"""Kraken Pro fee model. Starting tier only in the skeleton; tier progress
is tracked by the engine and re-read from the frozen rules on version change.
Figures: Kraken Pro schedule from 2026-07-09. Re-verify on Kraken's own fee
page inside the account before modeling live capital.
"""


def round_trip_cost(is_maker, rules, stablecoin=False):
    fees = rules["fees"]
    if stablecoin:
        return 2 * fees["stablecoin_per_side"]
    per_side = fees["tier1_maker"] if is_maker else fees["tier1_taker"]
    return 2 * per_side


def clears_hurdle(expected_edge_pct, is_maker, rules, stablecoin=False):
    """expected_edge_pct is the gross edge of the idea, as a fraction
    (e.g. 0.02 = 2%). A trade earns size only if it clears its hurdle."""
    hurdle = (rules["fees"]["maker_round_trip_hurdle"] if is_maker
              else rules["fees"]["taker_round_trip_hurdle"])
    if stablecoin:
        hurdle = 2 * rules["fees"]["stablecoin_per_side"]
    return expected_edge_pct > hurdle


def net_pnl_pct(gross_pct, is_maker, rules, stablecoin=False):
    return gross_pct - round_trip_cost(is_maker, rules, stablecoin)
