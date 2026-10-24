"""Public (unauthenticated) Kraken market-data client. Read-only by design:
it never touches private endpoints, never signs a request, never places an
order. Used by the paper engine's --live-public mode only.
"""
import json
import urllib.request

BASE = "https://api.kraken.com/0/public"


def get_ticker(pairs):
    url = BASE + "/Ticker?pair=" + ",".join(pairs)
    with urllib.request.urlopen(url, timeout=15) as resp:
        data = json.load(resp)
    if data.get("error"):
        raise RuntimeError("Kraken public API error: %s" % data["error"])
    out = {}
    for pair, quote in data["result"].items():
        out[pair] = {
            "last": float(quote["c"][0]),
            "bid": float(quote["b"][0]),
            "ask": float(quote["a"][0]),
            "volume_24h": float(quote["v"][1]),
        }
    return out
