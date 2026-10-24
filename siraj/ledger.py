"""Append-only, hash-chained event ledger.

Each event carries the sha256 of the previous event, so any edit, deletion,
or reordering breaks the chain and is detectable on replay. If it is not in
the log, it did not happen.
"""
import hashlib
import json


def _canonical(event):
    return json.dumps(event, sort_keys=True, separators=(",", ":")).encode()


class Ledger:
    def __init__(self):
        self.events = []
        self.prev_hash = "0" * 64

    def append(self, kind, payload):
        event = {"seq": len(self.events), "kind": kind,
                 "prev_hash": self.prev_hash, "payload": payload}
        event["hash"] = hashlib.sha256(_canonical(event)).hexdigest()
        self.prev_hash = event["hash"]
        self.events.append(event)
        return event

    def verify(self):
        prev = "0" * 64
        for event in self.events:
            if event["prev_hash"] != prev:
                return False, event["seq"]
            check = dict(event)
            claimed = check.pop("hash")
            if hashlib.sha256(_canonical(check)).hexdigest() != claimed:
                return False, event["seq"]
            prev = claimed
        return True, None

    def replay(self):
        """Rebuild paper P&L from fill events only. Returns net P&L in USD."""
        pnl = 0.0
        for event in self.events:
            if event["kind"] == "fill":
                pnl += event["payload"].get("pnl_usd", 0.0)
        return pnl
