"""
Build ui/data/app-data.js, the only data file the web app reads.

    python src/export_app_data.py

Inputs (all tracked in git, so the daily GitHub Actions run can rebuild it):
  results/summary_<crop>.json   backtest results (2020-2026 test)
  results/live_<crop>.csv       newest forecasts from the daily run (falls back to backtest_<crop>.csv)
  results/thresholds.json, results/data_quality.json, results/ablation_weather.json
  data/history/*.csv            HARTI corridor, CBSL prices and reasons, Open-Meteo weather
"""
import json, os, sys
from datetime import datetime, timezone, timedelta
import numpy as np, pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from history import CROPS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
HIST = os.path.join(ROOT, "data", "history")
OUT = os.path.join(ROOT, "ui", "data", "app-data.js")
NAMES = {"BEANS": "Beans", "CARROT": "Carrot", "TOMATO": "Tomato", "LEEKS": "Leeks", "GREEN_CHILLI": "Green chilli"}
COLOMBO_NAME = {"PELIYAGODA": "Peliyagoda", "PETTAH": "Pettah", "PETTAH (CBSL)": "Pettah"}
SL = timezone(timedelta(hours=5, minutes=30))


def _read_json(name, default=None):
    p = os.path.join(RES, name)
    return json.load(open(p)) if os.path.exists(p) else default


def _r(x, n=1):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), n)


def monthly(series, how="mean"):
    s = series.dropna()
    if s.empty:
        return []
    m = getattr(s.resample("MS"), how)()
    return [[d.strftime("%Y-%m"), _r(v, 3)] for d, v in m.items() if not np.isnan(v)]


def crop_block(crop, thresholds):
    summ = _read_json(f"summary_{crop.lower()}.json")
    if summ is None:
        return None
    live = os.path.join(RES, f"live_{crop.lower()}.csv")
    bt_path = os.path.join(RES, f"backtest_{crop.lower()}.csv")
    bt = pd.read_csv(bt_path, parse_dates=["date"])
    src = bt
    if os.path.exists(live):
        lv = pd.read_csv(live, parse_dates=["date"])
        if lv.date.max() >= bt.date.max():
            src = lv
    hist = pd.read_csv(os.path.join(HIST, "harti_corridor.csv"), parse_dates=["date"])
    hist = hist[hist.commodity == crop].sort_values("date")

    t = src.iloc[-1]
    ev = src[src.y.notna()]
    last30 = ev.tail(30)
    hits = int(((last30.y >= last30.L) & (last30.y <= last30.U)).sum())

    # last 14 bulletin days: real prices and the range that had been forecast for each
    rng = src.assign(target_date=src.date.shift(-1))[["target_date", "L", "U"]].dropna()
    recent = hist.tail(14).merge(rng, left_on="date", right_on="target_date", how="left")
    recent_rows = [{"date": d.strftime("%Y-%m-%d"), "dambulla": _r(w, 0), "colombo": _r(c, 0),
                    "lo": _r(lo, 0), "hi": _r(hi, 0)}
                   for d, w, c, lo, hi in zip(recent.date, recent.wholesale, recent.retail, recent.L, recent.U)]

    # analyst series: rolling 90-day coverage (monthly), breakdown flags per month
    s = bt.set_index("date")
    evb = s[s.y.notna() & (s.index >= "2020-01-01")]
    inside = ((evb.y >= evb.L) & (evb.y <= evb.U)).astype(float)
    raw_inside = ((evb.y >= evb.q_lo) & (evb.y <= evb.q_hi)).astype(float)
    cal = {"aci": monthly(inside.rolling(90, min_periods=60).mean(), "last"),
           "raw": monthly(raw_inside.rolling(90, min_periods=60).mean(), "last")}
    bd = monthly(s.bd_plan.astype(float), "mean") if "bd_plan" in s else []

    return {
        "id": crop, "name": NAMES[crop],
        "colombo_market": COLOMBO_NAME.get(str(hist.retail_market.iloc[-1]), "Colombo"),
        "today": {"date": t.date.strftime("%Y-%m-%d"), "dambulla": _r(t.wholesale, 0),
                  "source": "CBSL" if str(hist.retail_market.iloc[-1]).endswith("(CBSL)") else "HARTI",
                  "L": _r(t.L, 0), "M": _r(t.q_med, 0), "U": _r(t.U, 0), "m_bar": _r(t.m_bar, 1),
                  "alpha_t": _r(t.alpha_t, 3), "gap_days": int(src.date.diff().dt.days.iloc[-1]),
                  "breakdown_advisory": bool(t.get("bd_plan", False))},
        "recent": recent_rows,
        "hits_30": [hits, int(len(last30))],
        "backtest": {
            "period": summ["period"], "days": summ["eval_days"],
            "coverage": {k: _r(v["coverage"], 3) for k, v in summ["intervals"].items()},
            "width_pct": {k: _r(v["width_pct"], 1) for k, v in summ["intervals"].items()},
            "coverage_by_year": summ["coverage_by_year"],
            "pnl": summ["pnl"], "pnl_plan": summ["decision"]["plan"]["pnl"],
            "signals": summ["signals"],
            "red_days_lose": _r(summ["refusal_justification_rate"], 3),
            "base_loss_rate": _r(summ["base_loss_rate"], 3),
            "by_interest_rate": summ.get("by_interest_rate", []),
            "break_even_interest_rate": _r(summ.get("break_even_interest_rate"), 4),
            "refusal_cost": summ.get("refusal_cost"),
            "mae": summ.get("point_accuracy_mae"),
            "breakdown_warning": summ.get("breakdown_warning"),
        },
        "calibration_monthly": cal,
        "breakdown_monthly": bd,
    }


def cbsl_notes():
    out = {}
    ev_p = os.path.join(HIST, "cbsl_events.csv")
    pr_p = os.path.join(HIST, "cbsl_prices.csv")
    if os.path.exists(ev_p):
        ev = pd.read_csv(ev_p).sort_values("date")
        for crop, g in ev.groupby("commodity"):
            r = g.iloc[-1]
            out.setdefault(crop, {})["reason"] = {"date": r.date, "direction": r.direction, "text": r.text}
    if os.path.exists(pr_p):
        pr = pd.read_csv(pr_p).dropna(subset=["price"]).sort_values("date")
        for crop, g in pr.groupby("commodity"):
            last = g[g.date == g.date.max()]
            out.setdefault(crop, {})["prices"] = {
                "date": last.date.iloc[0],
                "rows": [{"market": m.title(), "type": k, "price": _r(p, 0)}
                         for m, k, p in zip(last.market, last.type, last.price)]}
    return out


def weather_now():
    p = os.path.join(HIST, "weather_daily.csv")
    if not os.path.exists(p):
        return None
    w = pd.read_csv(p, parse_dates=["date"])
    upc = w[w.station_id.isin(["NUWARA_ELIYA", "WELIMADA", "BANDARAWELA"])]
    d = upc.groupby("date").rain_mm.mean()
    today = pd.Timestamp(datetime.now(SL).date())
    d = d[d.index < today]
    last7 = d.tail(7)
    clim = d[d.index.month == today.month].rolling(7).sum().mean()
    daily7 = [[i.strftime("%Y-%m-%d"), _r(v, 1)] for i, v in last7.items()]
    temps = {}
    for sid in ("NUWARA_ELIYA", "DAMBULLA"):
        s = w[(w.station_id == sid) & (w.date < today)].sort_values("date").tail(1)
        if len(s):
            temps[sid] = {"max": _r(s.temp_max.iloc[0], 0), "min": _r(s.temp_min.iloc[0], 0)}
    return {"through": last7.index.max().strftime("%Y-%m-%d"), "rain_7d_mm": _r(last7.sum(), 0),
            "typical_7d_mm": _r(clim, 0), "daily": daily7, "temps": temps}


def main():
    th = _read_json("thresholds.json", {"tuned": {"beta": 1e9, "z_limit": 1e9, "corr_limit": -2}})
    crops = [b for b in (crop_block(c, th) for c in CROPS) if b]
    notes = cbsl_notes()
    for b in crops:
        b["cbsl"] = notes.get(b["id"])
    dq = _read_json("data_quality.json", {})
    data = {
        "generated_at": datetime.now(SL).strftime("%Y-%m-%dT%H:%M+05:30"),
        "bulletin_date": max(b["today"]["date"] for b in crops),
        "defaults": {"r_pct": 0.3, "C": 6.0, "quota": 100},
        "rule": {"beta": th["tuned"]["beta"], "stale_after_days": 4, "alpha": 0.10},
        "weather": weather_now(),
        "crops": crops,
        "ablation": _read_json("ablation_features.json") or _read_json("ablation_weather.json"),
        "risk_index": _read_json("risk_index.json"),
        "last_run": _read_json("last_run.json"),
        "data_quality": {"bulletins": dq.get("bulletins_total"), "price_rows": dq.get("price_rows"),
                         "missing_404": len(dq.get("missing_bulletins_404", [])),
                         "jumps_flagged": dq.get("gate2_jumps_over_60pct_core_corridor"),
                         "cbsl": dq.get("cbsl"), "cross_check": dq.get("cross_check")},
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("// Generated by src/export_app_data.py. Do not edit by hand.\n")
        f.write("window.MODEL_Y = " + json.dumps(data, separators=(",", ":"), default=str) + ";\n")
    print(f"Wrote {OUT} ({os.path.getsize(OUT) / 1024:.0f} KB) for {len(crops)} crops, bulletin {data['bulletin_date']}")


if __name__ == "__main__":
    main()
