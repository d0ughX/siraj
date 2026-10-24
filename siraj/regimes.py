"""Session/regime classification. Crypto never closes, so the desk runs on
regimes, not on/off switches. Boundaries are computed from IANA zones at
runtime; the skeleton takes an hour (ET, 0-23) + weekday + weekend flag as
inputs so the logic is testable without a clock dependency.
"""


def classify(hour_et, is_weekend, rules):
    """Returns (regime, breakout_size_factor)."""
    s = rules["sessions"]
    if is_weekend:
        return "weekend", s["weekend_mode"]["size_factor"]
    if 8 <= hour_et < 12:
        return "london_ny_overlap", 1.0
    if 3 <= hour_et < 8:
        return "london", 1.0
    if 20 <= hour_et or hour_et < 3:
        return "asia", s["asia_breakout_size_factor"]
    return "new_york", 1.0


def in_blackout(hour_et, minute, rules):
    """Event blackout windows are frozen clock windows (ET)."""
    for blackout in rules["sessions"].get("event_blackouts_et", []):
        window = blackout.get("window", [])
        if len(window) != 2:
            continue
        start, end = window
        sh, sm = map(int, start.split(":"))
        eh, em = map(int, end.split(":"))
        now = hour_et * 60 + minute
        if sh * 60 + sm <= now < eh * 60 + em:
            return True, blackout.get("event", "event")
    return False, None
