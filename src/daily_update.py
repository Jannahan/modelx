"""
Daily live run (proposal 5.3: "checks for new bulletins every morning at about 6:00 and again at 10:00").

    python src/daily_update.py

1. HARTI: download bulletins newer than the last HARTI day in data/history/harti_corridor.csv.
2. CBSL: download reports newer than data/history/cbsl_prices.csv; parse prices and reasons.
3. Fallback: if CBSL has a day HARTI has not published yet, fill that day from CBSL
   (scaled to HARTI's level, tagged "(CBSL)"); HARTI replaces it as soon as it appears.
4. Open-Meteo rainfall and CBSL USD/LKR for the last days.
5. Re-run the walk-forward forecasts (no ARIMA) -> results/live_<crop>.csv.
6. Market-risk index, then rebuild ui/data/app-data.js.

Every step is independent: if a source is down the others still run, and the app shows the
data's real age (red after 4 days). What happened is written to results/last_run.json, so a
run can be checked without access to the Actions log.
"""
import json, os, sys, tempfile, traceback
from datetime import datetime, timezone, timedelta
import numpy as np, pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")
TMP = os.path.join(tempfile.gettempdir(), "modely_daily")
SL = timezone(timedelta(hours=5, minutes=30))
REPORT = {"started": datetime.now(SL).strftime("%Y-%m-%d %H:%M"),
          "where": "GitHub Actions" if os.environ.get("GITHUB_ACTIONS") else "local run", "steps": {}}
CBSL_TAG = " (CBSL)"


def step(name, fn):
    print(f"\n== {name}", flush=True)
    try:
        info = fn() or {}
        REPORT["steps"][name] = {"ok": True, **info}
        return info
    except Exception as e:
        traceback.print_exc()
        REPORT["steps"][name] = {"ok": False, "error": f"{type(e).__name__}: {e}"[:300]}
        print(f"!! {name} failed; continuing with the other steps")


def last_harti_day():
    from history import load_all
    h = load_all()
    return h[~h.retail_market.astype(str).str.endswith(CBSL_TAG)].date.max()


def update_harti():
    from harti_scraper import fetch_bulletin_index, download_bulletin
    from harti_parser import parse_harti_pdf
    from history import corridor_rows, append
    last = last_harti_day()
    listed = fetch_bulletin_index()
    new = sorted({b["date"]: b for b in listed if b["language"] == "EN" and b["date"] > last}.values(),
                 key=lambda b: b["date"])
    print(f"HARTI history ends {last}; {len(new)} newer bulletins listed")
    rows, got_days = [], []
    for b in new:
        dest = os.path.join(TMP, "harti", f"harti_{b['date'].replace('-', '_')}.pdf")
        ok, size, err = download_bulletin(b["url"], dest)
        if not ok:
            print(f"  {b['date']}: download failed ({err})")
            continue
        recs = parse_harti_pdf(dest, b["date"])
        got = corridor_rows(recs) if recs else pd.DataFrame()
        print(f"  {b['date']}: {len(recs)} price cells, {len(got)} corridor rows")
        if len(got):
            rows.append(got); got_days.append(b["date"])
    if rows:
        print(f"added {append(pd.concat(rows))} rows to harti_corridor.csv")
    return {"listed": len(listed), "new_bulletins": got_days, "latest": max(got_days) if got_days else last}


def update_cbsl():
    from cbsl_scraper import fetch, LISTING, LINK_RE, BASE, report_date
    from harti_scraper import download_bulletin
    from cbsl_parser import parse_report, save, PRICES_CSV
    last = pd.read_csv(PRICES_CSV).date.max() if os.path.exists(PRICES_CSV) else "2000-01-01"
    links = {}
    for href in LINK_RE.findall(fetch(LISTING.format(0))):
        if "_s.pdf" in href.lower() or "_t.pdf" in href.lower():
            continue
        url = href if href.startswith("http") else BASE + href
        d = report_date(url)
        if d and d > last:
            links[d] = url
    print(f"CBSL history ends {last}; {len(links)} newer reports")
    prices, events, days = [], [], []
    for d, url in sorted(links.items()):
        dest = os.path.join(TMP, "cbsl", f"cbsl_{d.replace('-', '_')}.pdf")
        ok, _, err = download_bulletin(url, dest)
        if ok:
            _, _, p, e, perr = parse_report((0, dest, d))
            prices += p; events += e; days.append(d)
            print(f"  {d}: {len(p)} prices, {len(e)} reasons {perr or ''}")
    if prices or events:
        save(pd.DataFrame(prices), pd.DataFrame(events))
    return {"new_reports": days, "latest": max(days) if days else last}


def cbsl_fallback():
    """Fill days that CBSL has published but HARTI has not, scaled to HARTI's price level."""
    from history import load_all, append, CROPS, COLS
    from cbsl_parser import PRICES_CSV
    if not os.path.exists(PRICES_CSV):
        return {"filled": []}
    h = load_all()
    h_real = h[~h.retail_market.astype(str).str.endswith(CBSL_TAG)]
    last = h_real.date.max()
    cb = pd.read_csv(PRICES_CSV, dtype={"date": str}).dropna(subset=["price"])
    cb = cb[cb.type == "wholesale"]
    rows = []
    for crop in CROPS:
        c = cb[cb.commodity == crop].pivot_table(index="date", columns="market", values="price")
        if not {"DAMBULLA", "PETTAH"} <= set(c.columns):
            continue
        hc = h_real[h_real.commodity == crop].set_index("date")
        both = c.join(hc[["wholesale", "retail"]], how="inner").tail(60)
        if len(both) < 20:
            continue
        k_w = float((both.wholesale / both.DAMBULLA).median())     # HARTI level / CBSL level
        k_r = float((both.retail / both.PETTAH).median())
        for d, r in c[c.index > last].iterrows():
            if pd.notna(r.DAMBULLA) and pd.notna(r.PETTAH):
                rows.append([d, crop, r.DAMBULLA * k_w, np.nan, np.nan, r.PETTAH * k_r, np.nan, np.nan, "PETTAH" + CBSL_TAG])
    if rows:
        append(pd.DataFrame(rows, columns=COLS))
    filled = sorted({r[0] for r in rows})
    print(f"HARTI ends {last}; filled from CBSL: {filled or 'nothing needed'}")
    return {"filled": filled}


def update_weather():
    from datetime import date
    import weather
    df = weather.save(weather.fetch(None, (date.today() - timedelta(days=2)).isoformat()))
    return {"latest": str(df.date.max())}


def update_fx():
    import macro
    df = macro.update_fx()
    return {"latest": str(df.date.max()), "usd_lkr": float(df.usd_lkr.iloc[-1])}


def update_forecasts():
    from concurrent.futures import ProcessPoolExecutor
    from functools import partial
    import backtest
    from history import CROPS
    with ProcessPoolExecutor(max_workers=min(len(CROPS), os.cpu_count() or 2)) as pool:
        out = dict(zip(CROPS, pool.map(partial(backtest.forecast, with_arima=False), CROPS)))
    os.makedirs(RESULTS, exist_ok=True)
    info = {}
    for c, res in out.items():
        keep = ["date", "wholesale", "retail", "sell_price", "y", "q_lo", "q_med", "q_hi", "L", "U",
                "alpha_t", "m_bar", "stale", "bd_plan", "B"]
        res[[k for k in keep if k in res]].to_csv(os.path.join(RESULTS, f"live_{c.lower()}.csv"), index=False)
        t = res.iloc[-1]
        info[c] = str(t.date.date())
        print(f"  {c:<13} {t.date.date()}  range Rs. {t.L:.0f}-{t.U:.0f}, median {t.q_med:.0f}")
    return {"forecast_dates": info}


def update_risk_index():
    import risk_index
    r = risk_index.main()
    return {"today": r.get("today", {}).get("index")}


if __name__ == "__main__":
    os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 2))
    step("HARTI bulletins", update_harti)
    step("CBSL reports", update_cbsl)
    step("CBSL fallback", cbsl_fallback)
    step("Open-Meteo rainfall", update_weather)
    step("USD/LKR", update_fx)
    step("Forecasts", update_forecasts)
    step("Market-risk index", update_risk_index)
    REPORT["finished"] = datetime.now(SL).strftime("%Y-%m-%d %H:%M")
    REPORT["all_ok"] = all(s["ok"] for s in REPORT["steps"].values())
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "last_run.json"), "w") as f:
        json.dump(REPORT, f, indent=2)
    import export_app_data
    step("Web app data", export_app_data.main)
    REPORT["all_ok"] = all(s["ok"] for s in REPORT["steps"].values())
    with open(os.path.join(RESULTS, "last_run.json"), "w") as f:
        json.dump(REPORT, f, indent=2)
    export_app_data.main()          # once more so the app shows this run's report
    print("\nRun report:", json.dumps(REPORT, indent=1)[:2000])
