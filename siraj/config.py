"""Load and validate the frozen rule set. No rule value may be overridden
at runtime: a change means a new file version + re-validation + owner approval.

A small purpose-built parser (no dependencies): it handles nested mappings,
flow mappings ``{k: v, ...}``, flow lists ``[a, b]``, lists of flow mappings,
scalars, and ``#`` comments. Anything else raises instead of guessing.
"""
import hashlib
import os

REQUIRED_TOP = ("version", "dial", "sleeves", "fees", "trades",
                 "win_ladder", "daily_stop", "kill_switches")


def _strip_comment(line):
    # Comments start at " #" outside quotes; frozen-rules.yaml has no quoted
    # '#' characters, so a simple split is safe here.
    if " #" in line:
        return line.split(" #", 1)[0].rstrip()
    return line.rstrip()


def _split_top_level(text, sep=","):
    parts, depth, cur, quote = [], 0, "", None
    for ch in text:
        if quote:
            cur += ch
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            cur += ch
        elif ch in "[{":
            depth += 1
            cur += ch
        elif ch in "]}":
            depth -= 1
            cur += ch
        elif ch == sep and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur)
    return parts


def _parse_value(text):
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        out = {}
        for part in _split_top_level(text[1:-1]):
            k, _, v = part.partition(":")
            out[k.strip()] = _parse_value(v)
        return out
    if text.startswith("[") and text.endswith("]"):
        return [_parse_value(p) for p in _split_top_level(text[1:-1])]
    if text in ("true", "false"):
        return text == "true"
    if (text.startswith('"') and text.endswith('"')) or \
       (text.startswith("'") and text.endswith("'")):
        return text[1:-1]
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    return text


def parse_simple_yaml(path):
    with open(path) as fh:
        raw_lines = fh.readlines()
    # (indent, text) pairs, comments/blank lines removed
    lines = []
    for raw in raw_lines:
        if raw.strip().startswith("#"):
            continue
        stripped = _strip_comment(raw)
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip())
        lines.append((indent, stripped.strip()))

    def parse_block(i, indent):
        """Parse a mapping block starting at lines[i] with given indent.
        Returns (mapping, next_index)."""
        mapping = {}
        while i < len(lines):
            ind, text = lines[i]
            if ind < indent:
                break
            if ind > indent:
                raise ValueError("unexpected indent: %r" % text)
            if text.startswith("- "):
                break
            if ":" not in text:
                raise ValueError("unsupported line: %r" % text)
            key, _, value = text.partition(":")
            key, value = key.strip(), value.strip()
            if value == "":
                # Nested block follows: mapping or list?
                if i + 1 < len(lines) and lines[i + 1][0] > indent:
                    nxt_ind, nxt_text = lines[i + 1]
                    if nxt_text.startswith("- "):
                        lst, i = parse_list(i + 1, nxt_ind)
                        mapping[key] = lst
                    else:
                        sub, i = parse_block(i + 1, nxt_ind)
                        mapping[key] = sub
                else:
                    mapping[key] = {}
                    i += 1
            else:
                mapping[key] = _parse_value(value)
                i += 1
        return mapping, i

    def parse_list(i, indent):
        lst = []
        while i < len(lines):
            ind, text = lines[i]
            if ind < indent or not text.startswith("- "):
                break
            body = text[2:].strip()
            if body.startswith("{"):
                lst.append(_parse_value(body))
                i += 1
            else:
                # "- key: value" form: treat as one-key mapping (not used by
                # frozen-rules.yaml, but kept for completeness).
                k, _, v = body.partition(":")
                lst.append({k.strip(): _parse_value(v)} if v.strip() else {})
                i += 1
        return lst, i

    if not lines:
        return {}
    result, _ = parse_block(0, lines[0][0])
    return result


def load_rules(path=None):
    path = path or os.path.join(os.path.dirname(__file__), "..",
                                "rules", "frozen-rules.yaml")
    path = os.path.normpath(path)
    with open(path, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()
    rules = parse_simple_yaml(path)
    for key in REQUIRED_TOP:
        if key not in rules:
            raise ValueError("frozen rules missing section: %s" % key)
    sleeve_keys = ("intraday_trend", "cross_pair_momentum", "session_breakout")
    total = sum(rules["sleeves"][k] for k in sleeve_keys)
    if abs(total - 1.0) > 1e-9:
        raise ValueError("sleeve risk weights must sum to 1.0, got %s" % total)
    if rules["dial"]["per_trade_risk"] > rules["dial"]["per_trade_risk_ceiling"]:
        raise ValueError("per-trade risk exceeds ceiling")
    rules["_sha256"] = digest
    rules["_path"] = path
    return rules
