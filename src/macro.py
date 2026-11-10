"""
Cost drivers and calendar (proposal Table 2: "CBSL exchange rates; fuel price revisions"
and "Calendar: Poya days, festivals, market holidays").

    python src/macro.py            # refresh USD/LKR from CBSL (full history), report coverage

Files (tracked in git):
  data/history/usd_lkr.csv        CBSL daily indicative USD/LKR spot rate, 2015-06 onward
  data/history/diesel_cpc.csv     Ceylon Petroleum Corporation auto-diesel (LAD) price revisions,
                                  read from CPC's public "Historical fuel prices" archive
                                  (ceypetco.gov.lk/marketing-sales/historical-prices).
                                  CPC revises monthly at most; update this file when it does.

Calendar: Poya (full-moon) days are computed astronomically; Sri Lanka fixes the Poya holiday
by local observation, so roughly 1 in 10 may differ by one day. Fixed-date holidays are added.
"""
import os, re, sys, urllib.parse, urllib.request
from datetime import date, timedelta
import numpy as np, pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST = os.path.join(ROOT, "data", "history")
FX_CSV = os.path.join(HIST, "usd_lkr.csv")
DIESEL_CSV = os.path.join(HIST, "diesel_cpc.csv")
FX_URL = "https://www.cbsl.gov.lk/cbsl_custom/exrates/exrates_results_spot_mid.php"


# ---------------------------------------------------------------- exchange rate
def fetch_fx(start="2015-06-01", end=None):
    end = end or date.today().isoformat()
    body = urllib.parse.urlencode({
        "lookupPage": "lookup_daily_exchange_rates.php", "startRange": "2006-11-11", "rangeType": "dates",
        "txtStart": start, "txtEnd": end, "chk_cur[]": "USD~US Dollar", "submit_button": "Submit"}).encode()
    from harti_scraper import get_ssl_context
    req = urllib.request.Request(FX_URL, data=body, headers={
        "User-Agent": "Mozilla/5.0", "Referer": "https://www.cbsl.gov.lk/cbsl_custom/exrates/exrates_spot_mid.php"})
    with urllib.request.urlopen(req, context=get_ssl_context(), timeout=120) as r:
        html = r.read().decode("utf-8", errors="ignore")
    rows = re.findall(r"<td>\s*(20\d\d-\d\d-\d\d)\s*</td>\s*<td>\s*([\d.]+)\s*</td>", html)
    return pd.DataFrame(rows, columns=["date", "usd_lkr"]).astype({"usd_lkr": float})


def update_fx(full=False):
    old = pd.read_csv(FX_CSV, dtype={"date": str}) if os.path.exists(FX_CSV) else pd.DataFrame(columns=["date", "usd_lkr"])
    start = "2015-06-01" if full or old.empty else (pd.Timestamp(old.date.max()) - pd.Timedelta(days=10)).date().isoformat()
    new = fetch_fx(start)
    df = pd.concat([old, new]).drop_duplicates("date", keep="last").sort_values("date")
    os.makedirs(HIST, exist_ok=True)
    df.to_csv(FX_CSV, index=False)
    return df


# ---------------------------------------------------------------- calendar
def _full_moon_jde(k):
    """Julian Ephemeris Day of full moon number k (k = n + 0.5). Meeus, Astronomical Algorithms, ch. 49."""
    from math import sin, radians
    T = k / 1236.85
    jde = (2451550.09766 + 29.530588861 * k + 0.00015437 * T**2 - 0.000000150 * T**3 + 0.00000000073 * T**4)
    E = 1 - 0.002516 * T - 0.0000074 * T**2
    M = radians(2.5534 + 29.10535670 * k - 0.0000014 * T**2)
    Mp = radians(201.5643 + 385.81693528 * k + 0.0107582 * T**2)
    F = radians(160.7108 + 390.67050284 * k - 0.0016118 * T**2)
    Om = radians(124.7746 - 1.56375588 * k + 0.0020672 * T**2)
    corr = (-0.40614 * sin(Mp) + 0.17302 * E * sin(M) + 0.01614 * sin(2 * Mp) + 0.01043 * sin(2 * F)
            + 0.00734 * E * sin(Mp - M) - 0.00515 * E * sin(Mp + M) + 0.00209 * E * E * sin(2 * M)
            - 0.00111 * sin(Mp - 2 * F) - 0.00057 * sin(Mp + 2 * F) + 0.00056 * E * sin(2 * Mp + M)
            - 0.00042 * sin(3 * Mp) + 0.00042 * E * sin(M + 2 * F) + 0.00038 * E * sin(M - 2 * F)
            - 0.00024 * E * sin(2 * Mp - M) - 0.00017 * sin(Om))
    return jde + corr


def poya_days(start="2014-01-01", end="2027-12-31"):
    """Full-moon dates in Sri Lanka time (UTC+5:30), accurate to minutes."""
    t0, t1 = pd.Timestamp(start), pd.Timestamp(end)
    k = np.floor((t0.year + (t0.dayofyear / 365.25) - 2000) * 12.3685) - 1
    out = []
    while True:
        jde = _full_moon_jde(k + 0.5)
        utc = pd.Timestamp("2000-01-01 12:00") + pd.Timedelta(days=jde - 2451545.0) - pd.Timedelta(seconds=69)
        local = (utc + pd.Timedelta(hours=5, minutes=30)).normalize()
        if local > t1:
            break
        if local >= t0:
            out.append(local)
        k += 1
    return pd.Series(out)


FIXED = ["02-04", "04-13", "04-14", "05-01", "12-25"]   # Independence, Sinhala & Tamil New Year, May Day, Christmas


def calendar_features(dates):
    """Features known in advance for each bulletin date t (the sale happens on the next market day)."""
    d = pd.to_datetime(pd.Series(dates)).reset_index(drop=True)
    poya = poya_days(str(d.min().year - 1) + "-01-01", str(d.max().year + 1) + "-12-31")
    pv = poya.values
    nxt = np.searchsorted(pv, d.values)                      # first poya on/after t
    days_to_poya = (pv[np.minimum(nxt, len(pv) - 1)] - d.values) / np.timedelta64(1, "D")
    md = d.dt.strftime("%m-%d")
    holiday_next = d.apply(lambda x: any((x + pd.Timedelta(days=k)).strftime("%m-%d") in FIXED for k in (1, 2)))
    return pd.DataFrame({
        "days_to_poya": days_to_poya.astype(float),
        "poya_tomorrow": (days_to_poya <= 1).astype(int),
        "holiday_next_2d": holiday_next.astype(int),
        "new_year_season": md.between("04-05", "04-20").astype(int),
        "december_season": md.between("12-15", "12-31").astype(int),
        "month": d.dt.month,
    })


# ---------------------------------------------------------------- cost drivers as features
def cost_features(dates):
    """Diesel price and USD/LKR known on each date (last published value, never a future one)."""
    d = pd.DataFrame({"date": pd.to_datetime(pd.Series(dates)).reset_index(drop=True)})
    d["_i"] = range(len(d))
    out = d.sort_values("date")
    if os.path.exists(DIESEL_CSV):
        dz = pd.read_csv(DIESEL_CSV, parse_dates=["date"]).sort_values("date")
        out = pd.merge_asof(out, dz, on="date", direction="backward")
        out["diesel_change_30d"] = np.nan
        prev = pd.merge_asof(out[["date"]].assign(date=out.date - pd.Timedelta(days=30)), dz, on="date", direction="backward")
        out["diesel_change_30d"] = out.auto_diesel_rs_per_litre.values / prev.auto_diesel_rs_per_litre.values - 1
    if os.path.exists(FX_CSV):
        fx = pd.read_csv(FX_CSV, parse_dates=["date"]).sort_values("date")
        # the CBSL rate for day t is published during day t, so at 06:00 only t-1 is known
        fx["date"] = fx.date + pd.Timedelta(days=1)
        out = pd.merge_asof(out, fx, on="date", direction="backward")
        prev = pd.merge_asof(out[["date"]].assign(date=out.date - pd.Timedelta(days=30)), fx, on="date", direction="backward")
        out["fx_change_30d"] = out.usd_lkr.values / prev.usd_lkr.values - 1
    out = out.sort_values("_i").drop(columns=["date", "_i"]).reset_index(drop=True)
    return out.rename(columns={"auto_diesel_rs_per_litre": "diesel"})


if __name__ == "__main__":
    fx = update_fx(full=True)
    print(f"USD/LKR: {len(fx):,} days {fx.date.min()} -> {fx.date.max()}  (last {fx.usd_lkr.iloc[-1]:.2f})")
    dz = pd.read_csv(DIESEL_CSV)
    print(f"Diesel revisions: {len(dz)} from {dz.date.min()} to {dz.date.max()} (now Rs. {dz.iloc[-1, 1]})")
    p = poya_days("2026-01-01", "2026-12-31")
    print("Poya 2026 (computed):", ", ".join(x.strftime("%d %b") for x in p))
