"""
Daily live run (proposal 5.3: "checks for new bulletins every morning at about 6:00 and again at 10:00").

    python src/daily_update.py

1. HARTI: download bulletins newer than data/history/harti_corridor.csv, parse, append.
2. CBSL: download reports newer than data/history/cbsl_prices.csv, parse prices and reasons.
3. Open-Meteo: refresh the last 14 days of rainfall.
4. Re-run the walk-forward forecasts (no ARIMA) -> results/live_<crop>.csv.
5. Rebuild ui/data/app-data.js for the web app.

Each step is independent: if HARTI or CBSL is down, the others still run and the app
shows the data's real age (and goes RED when it is too old), instead of failing.
Works without prices.db, so it runs on a fresh GitHub Actions machine.
"""
import os, re, sys, tempfile, traceback, urllib.request
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")
TMP = os.path.join(tempfile.gettempdir(), "modely_daily")


def step(name, fn):
    print(f"\n== {name}", flush=True)
    try:
        return fn()
    except Exception:
        traceback.print_exc()
        print(f"!! {name} failed; continuing with the other steps")


def update_harti():
    from harti_scraper import fetch_bulletin_index, download_bulletin
    from harti_parser import parse_harti_pdf
    from history import load_all, corridor_rows, append
    last = load_all().date.max()
    new = sorted({b["date"]: b for b in fetch_bulletin_index() if b["language"] == "EN" and b["date"] > last}.values(),
                 key=lambda b: b["date"])
    print(f"history ends {last}; {len(new)} newer HARTI bulletins listed")
    rows = []
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
            rows.append(got)
    if rows:
        print(f"added {append(pd.concat(rows))} rows to harti_corridor.csv")


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
    prices, events = [], []
    for d, url in sorted(links.items()):
        dest = os.path.join(TMP, "cbsl", f"cbsl_{d.replace('-', '_')}.pdf")
        ok, _, err = download_bulletin(url, dest)
        if ok:
            _, _, p, e, perr = parse_report((0, dest, d))
            prices += p; events += e
            print(f"  {d}: {len(p)} prices, {len(e)} reasons {perr or ''}")
    if prices or events:
        save(pd.DataFrame(prices), pd.DataFrame(events))


def update_weather():
    from datetime import date, timedelta
    import weather
    weather.save(weather.fetch(None, (date.today() - timedelta(days=2)).isoformat()))


def update_forecasts():
    from concurrent.futures import ProcessPoolExecutor
    from functools import partial
    import backtest
    from history import CROPS
    with ProcessPoolExecutor(max_workers=min(len(CROPS), os.cpu_count() or 2)) as pool:
        out = dict(zip(CROPS, pool.map(partial(backtest.forecast, with_arima=False), CROPS)))
    os.makedirs(RESULTS, exist_ok=True)
    for c, res in out.items():
        keep = ["date", "wholesale", "retail", "sell_price", "y", "q_lo", "q_med", "q_hi", "L", "U",
                "alpha_t", "m_bar", "stale", "bd_plan", "B"]
        res[[k for k in keep if k in res]].to_csv(os.path.join(RESULTS, f"live_{c.lower()}.csv"), index=False)
        t = res.iloc[-1]
        print(f"  {c:<13} {t.date.date()}  range Rs. {t.L:.0f}-{t.U:.0f}, median {t.q_med:.0f}")


if __name__ == "__main__":
    os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 2))
    step("HARTI bulletins", update_harti)
    step("CBSL reports", update_cbsl)
    step("Open-Meteo rainfall", update_weather)
    step("Forecasts", update_forecasts)
    import export_app_data
    step("Web app data", export_app_data.main)
