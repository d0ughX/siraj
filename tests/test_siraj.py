"""SIRAJ unit tests (stdlib unittest only). Run:
python3 -m unittest discover -s tests -v
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from siraj import config as config_mod
from siraj.fees import clears_hurdle, net_pnl_pct, round_trip_cost
from siraj.gateway import OrderIntent, check_intent
from siraj.ladder import DailyStop, WinLadder
from siraj.ledger import Ledger
from siraj.paper_engine import run
from siraj.regimes import classify, in_blackout
from siraj.sizing import position_size

RULES = config_mod.load_rules()


def intent(**kw):
    base = dict(pair="XBTUSDT", side="buy", units=0.01, price=100.0,
                stop=98.0, target=110.0, time_stop_bars=10,
                sleeve="intraday_trend", is_maker=True,
                expected_edge_pct=0.02, volume_24h_usd=5_000_000,
                spread_pct=0.0005, risk_amount=0.10)
    base.update(kw)
    return OrderIntent(**base)


class TestConfig(unittest.TestCase):
    def test_loads_and_weights_sum(self):
        self.assertEqual(RULES["version"], "0.1")
        self.assertIn("_sha256", RULES)
        self.assertEqual(len(RULES["_sha256"]), 64)

    def test_sleeve_weights(self):
        keys = ("intraday_trend", "cross_pair_momentum", "session_breakout")
        total = sum(RULES["sleeves"][k] for k in keys)
        self.assertAlmostEqual(total, 1.0)


class TestFees(unittest.TestCase):
    def test_tier1_round_trips(self):
        self.assertAlmostEqual(round_trip_cost(True, RULES), 0.008)
        self.assertAlmostEqual(round_trip_cost(False, RULES), 0.016)

    def test_hurdle(self):
        self.assertTrue(clears_hurdle(0.02, True, RULES))
        self.assertFalse(clears_hurdle(0.005, True, RULES))
        self.assertAlmostEqual(net_pnl_pct(0.05, True, RULES), 0.042)


class TestSizing(unittest.TestCase):
    def test_formula(self):
        size = position_size(10.0, 0.01, 2.0, 2.0, 100.0)
        self.assertAlmostEqual(size["risk_amount"], 0.10)
        self.assertAlmostEqual(size["units"], 0.025)


class TestLadder(unittest.TestCase):
    def test_ten_total_wins_step_up(self):
        ladder = WinLadder(RULES)
        for _ in range(10):
            ladder.record(True)
        self.assertEqual(ladder.tier, 1)

    def test_three_consecutive_losses_reset_window(self):
        ladder = WinLadder(RULES)
        for _ in range(9):
            ladder.record(True)
        for _ in range(3):
            ladder.record(False)
        self.assertEqual(ladder.wins_in_window, 0)
        self.assertEqual(ladder.tier, 0)

    def test_nine_wins_two_losses_then_win_steps_up(self):
        # Jonathan's worked example: 9 wins, 2 losses, 1 win = step-up.
        ladder = WinLadder(RULES)
        for _ in range(9):
            ladder.record(True)
        ladder.record(False)
        ladder.record(False)
        ladder.record(True)
        self.assertEqual(ladder.tier, 1)


class TestDailyStop(unittest.TestCase):
    def test_trip_and_owner_only_restart(self):
        stop = DailyStop(RULES)
        stop.add_pnl(-0.03)
        self.assertTrue(stop.tripped)
        self.assertFalse(stop.request_owner_restart(False))
        self.assertTrue(stop.tripped)
        self.assertTrue(stop.request_owner_restart(True))
        self.assertFalse(stop.tripped)


class TestGateway(unittest.TestCase):
    def test_valid_passes(self):
        ok, reasons = check_intent(intent(), RULES, 10.0, 0.0, False)
        self.assertTrue(ok, reasons)

    def test_taker_rejected_maker_first(self):
        ok, reasons = check_intent(intent(is_maker=False), RULES, 10.0, 0.0,
                                   False)
        self.assertFalse(ok)
        self.assertTrue(any("maker_first" in r for r in reasons))

    def test_bad_stop_and_low_reward_rejected(self):
        ok, _ = check_intent(intent(stop=101.0), RULES, 10.0, 0.0, False)
        self.assertFalse(ok)
        ok, _ = check_intent(intent(target=102.0), RULES, 10.0, 0.0, False)
        self.assertFalse(ok)  # reward:risk below 5:1

    def test_daily_stop_blocks(self):
        ok, reasons = check_intent(intent(), RULES, 10.0, 0.0, True)
        self.assertFalse(ok)
        self.assertTrue(any("daily stop" in r for r in reasons))


class TestLedger(unittest.TestCase):
    def test_chain_and_tamper(self):
        ledger = Ledger()
        ledger.append("fill", {"pnl_usd": 0.5})
        ledger.append("fill", {"pnl_usd": -0.1})
        self.assertEqual(ledger.replay(), 0.4)
        ok, _ = ledger.verify()
        self.assertTrue(ok)
        ledger.events[0]["payload"]["pnl_usd"] = 99.0
        ok, _ = ledger.verify()
        self.assertFalse(ok)


class TestRegimes(unittest.TestCase):
    def test_overlap_and_asia_and_weekend(self):
        self.assertEqual(classify(9, False, RULES)[0], "london_ny_overlap")
        self.assertEqual(classify(1, False, RULES)[1], 0.5)
        self.assertEqual(classify(10, True, RULES)[0], "weekend")

    def test_blackout(self):
        hit, _ = in_blackout(8, 30, RULES)
        self.assertTrue(hit)
        hit, _ = in_blackout(10, 30, RULES)
        self.assertFalse(hit)


class TestPaperEngine(unittest.TestCase):
    def test_fixture_run_verifies_ledger(self):
        path = os.path.join(os.path.dirname(__file__), "fixtures",
                            "sample_candles.json")
        with open(path) as fh:
            candles = json.load(fh)
        result = run(candles, RULES)
        self.assertTrue(result["ledger_ok"])
        self.assertGreater(result["equity_end"], result["equity_start"])


if __name__ == "__main__":
    unittest.main()
