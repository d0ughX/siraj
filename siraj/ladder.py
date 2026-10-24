"""Win ladder + daily stop state.

Win ladder (frozen rule): step up one risk tier every 10 wins TOTAL.
The counting window restarts after 3 CONSECUTIVE losses (win count -> 0).
A week closing negative steps the tier back down one notch.
Tiers never exceed the dial's per-trade maximum.

Daily stop: once tripped, only the owner can restart. The engine exposes
`request_owner_restart()` as the single, auditable restart path; there is
no automatic or next-morning resume.
"""


class WinLadder:
    def __init__(self, rules):
        wl = rules["win_ladder"]
        self.wins_to_step = wl["wins_to_step_up"]
        self.reset_losses = wl["consecutive_losses_to_reset"]
        self.tier = 0
        self.wins_in_window = 0
        self.consec_losses = 0
        self.max_tier = 4  # tier cap; dial cap still applies on top

    def record(self, won):
        if won:
            self.consec_losses = 0
            self.wins_in_window += 1
            if self.wins_in_window >= self.wins_to_step:
                self.tier = min(self.tier + 1, self.max_tier)
                self.wins_in_window = 0
        else:
            self.consec_losses += 1
            if self.consec_losses >= self.reset_losses:
                self.wins_in_window = 0
                self.consec_losses = 0

    def week_closed_negative(self):
        self.tier = max(self.tier - 1, 0)

    def tier_risk_multiplier(self):
        # Tier 0 = baseline; each tier adds 25% to baseline risk, capped by
        # the dial ceiling in the gateway (never by this class alone).
        return 1.0 + 0.25 * self.tier


class DailyStop:
    def __init__(self, rules):
        self.cap = rules["daily_stop"]["daily_loss_cap_pct"]
        self.tripped = False
        self.day_pnl = 0.0
        self.restart_count = 0

    def add_pnl(self, pnl_fraction_of_equity):
        self.day_pnl += pnl_fraction_of_equity
        if self.day_pnl <= -self.cap:
            self.tripped = True

    def new_day(self):
        # A new calendar day does NOT clear a trip: only the owner restarts.
        # new_day only resets the P&L accumulator for reporting.
        self.day_pnl = 0.0

    def request_owner_restart(self, owner_approved):
        if not owner_approved:
            return False
        self.tripped = False
        self.restart_count += 1
        return True
