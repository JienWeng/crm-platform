#!/usr/bin/env python3
"""Recompute the billing forecast across all Funnels (Twenty has no formula fields).

For every Funnel it sets, from the editable FunnelStage config:
    winRate          = config[stage].winRate
    includeInForecast= config[stage].includeInForecast   (the threshold gate)
    forecastAmount   = amount * winRate%   if includeInForecast else 0

Then it prints the weighted billing forecast (sum of forecastAmount — only 4a + closed
contribute) and the funnel-shaped breakdown by stage (count + amount per stage).

Run after changing win-rates/thresholds in the UI, after import, or on a cron.
Idempotent: only PATCHes funnels whose computed values changed.

Usage:
  TWENTY_API_URL=... TWENTY_API_KEY=... python3 funnel_forecast.py preview   # report only
  TWENTY_API_URL=... TWENTY_API_KEY=... python3 funnel_forecast.py apply     # write + report
"""
import os, sys, json, urllib.request, urllib.error

API_URL = os.environ.get("TWENTY_API_URL", "").rstrip("/")
API_KEY = os.environ.get("TWENTY_API_KEY", "")

# Fallback defaults if the FunnelStage config object is empty/missing.
DEFAULTS = {  # stageValue -> (winRate, includeInForecast)
    "S0E": (0, False), "S1D": (25, False), "S2C": (50, False),
    "S3B": (75, False), "S4A": (90, True), "CLOSED": (100, True),
}
LABELS = {"S0E": "0e", "S1D": "1d", "S2C": "2c", "S3B": "3b", "S4A": "4a", "CLOSED": "closed"}
ORDER = ["S0E", "S1D", "S2C", "S3B", "S4A", "CLOSED"]


def rest(method, path, body=None):
    if not API_URL or not API_KEY:
        sys.exit("Set TWENTY_API_URL and TWENTY_API_KEY.")
    req = urllib.request.Request(
        API_URL + path, method=method,
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        data=json.dumps(body).encode() if body else None)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or "{}")


def list_all(obj):
    out, cursor = [], None
    while True:
        path = f"/rest/{obj}?limit=200" + (f"&starting_after={cursor}" if cursor else "")
        st, d = rest("GET", path)
        if st != 200:
            break
        page = d.get("data", {}).get(obj, [])
        out += page
        info = d.get("pageInfo", {}) or {}
        if not info.get("hasNextPage") or not page:
            break
        cursor = info.get("endCursor")
    return out


def load_config():
    cfg = {}
    for r in list_all("funnelStages"):
        v = r.get("stageValue")
        if v:
            cfg[v] = (r.get("winRate") or 0, bool(r.get("includeInForecast")))
    if not cfg:
        print("  (FunnelStage config empty — using built-in defaults)")
        cfg = dict(DEFAULTS)
    return cfg


def micros(amount_field):
    if isinstance(amount_field, dict):
        return amount_field.get("amountMicros") or 0
    return 0


def run(apply_changes):
    cfg = load_config()
    funnels = list_all("funnels")
    by_stage = {v: {"count": 0, "amount": 0, "forecast": 0} for v in ORDER}
    changed = 0

    for f in funnels:
        stage = f.get("stage")
        wr, inc = cfg.get(stage, DEFAULTS.get(stage, (0, False)))
        amt = micros(f.get("amount"))
        fc = int(round(amt * wr / 100)) if inc else 0

        cur = f.get("forecastAmount") or {}
        cur_fc = micros(cur)
        needs = (f.get("winRate") != wr or
                 bool(f.get("includeInForecast")) != inc or
                 cur_fc != fc)
        if needs and apply_changes:
            ccode = (f.get("amount") or {}).get("currencyCode", "MYR")
            st, _ = rest("PATCH", f"/rest/funnels/{f['id']}", {
                "winRate": wr,
                "includeInForecast": inc,
                "forecastAmount": {"amountMicros": fc, "currencyCode": ccode},
            })
            if st in (200, 201):
                changed += 1

        b = by_stage.setdefault(stage, {"count": 0, "amount": 0, "forecast": 0})
        b["count"] += 1
        b["amount"] += amt
        b["forecast"] += fc

    # ── Report: funnel-shaped breakdown (wide top -> narrow bottom) ─────────────
    print(f"\n{'STAGE':<8}{'COUNT':>7}{'PIPELINE':>18}{'WEIGHTED FORECAST':>22}")
    print("-" * 55)
    total_fc = 0
    for v in ORDER:
        b = by_stage.get(v, {"count": 0, "amount": 0, "forecast": 0})
        wr, inc = cfg.get(v, DEFAULTS.get(v, (0, False)))
        tag = f"  <- forecast ({wr}%)" if inc else ""
        bar = "#" * min(40, b["count"])
        print(f"{LABELS.get(v, v):<8}{b['count']:>7}{b['amount']/1e6:>18,.0f}"
              f"{b['forecast']/1e6:>22,.0f}{tag}")
        if bar:
            print(f"        {bar}")
        total_fc += b["forecast"]
    print("-" * 55)
    print(f"BILLING FORECAST (4a + closed, weighted): {total_fc/1e6:,.0f}")
    if apply_changes:
        print(f"funnels updated: {changed}")
    else:
        print("(preview — no writes; run `apply` to persist winRate/forecastAmount)")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "preview"
    run(apply_changes=(cmd == "apply"))
