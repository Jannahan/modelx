"""
Data-quality report for prices.db (Dataset Gathering Guide, Section 7 gates).

    python src/data_quality.py      ->  prints the report, writes results/data_quality.json

Gates:
  1. Spread logic      price_low <= price_high
  2. Extreme jump      |P_t - P_{t-1}| / P_{t-1} > 60%   (flagged for review, never auto-deleted)
  3. Missing trade     dashes stored as NULL, never 0, never forward-filled
  4. Coverage          which bulletins are missing, per year and per corridor
  5. Dual-source check HARTI vs CBSL prices on matching dates (guide: Pearson r >= 0.90)
"""
import json, os, sqlite3, sys
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from db import DB_PATH

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from history import CROPS, load_corridor
HIST = os.path.join(ROOT, "data", "history")


def main():
    conn = sqlite3.connect(DB_PATH)
    b_all = pd.read_sql_query("SELECT date, source, download_status, parse_status, error_message FROM bulletins", conn)
    b = b_all[b_all.source == "HARTI"].copy()
    cb = b_all[b_all.source == "CBSL"]
    p = pd.read_sql_query("SELECT * FROM wholesale_prices", conn)
    conn.close()

    b["year"] = b.date.str[:4]
    bulletins = (b.assign(listed=1,
                          downloaded=b.download_status.eq("DOWNLOADED"),
                          parsed=b.parse_status.eq("PARSED"),
                          not_on_server=b.error_message.fillna("").str.contains("404"),
                          empty_or_failed=b.parse_status.isin(["EMPTY", "FAILED"]))
                  .groupby("year")[["listed", "downloaded", "parsed", "not_on_server", "empty_or_failed"]]
                  .sum().astype(int))

    zero_prices = int((p.price_mid == 0).sum())
    inverted = int((p.price_low > p.price_high).sum())
    no_trade = float((p.is_traded == 0).mean())

    p = p.sort_values("date")
    tr = p[p.is_traded == 1]
    tr = tr.assign(prev=tr.groupby(["commodity_id", "market_id"]).price_mid.shift(1))
    jumps = tr[(tr.price_mid - tr.prev).abs() / tr.prev > 0.60]
    core = jumps[jumps.commodity_id.isin(CROPS) & jumps.market_id.isin(["DAMBULLA", "PELIYAGODA", "PETTAH"])]

    colombo_label = (p[p.market_id.isin(["PELIYAGODA", "PETTAH"]) & p.commodity_id.eq("BEANS")]
                     .assign(year=lambda d: d.date.str[:4])
                     .groupby(["year", "market_id"]).size().unstack(fill_value=0))

    corridors = {}
    for c in CROPS:
        d = load_corridor(c)
        if d.empty:
            continue
        d["year"] = d.date.dt.year
        corridors[c] = {"days": int(len(d)), "first": str(d.date.min().date()), "last": str(d.date.max().date()),
                        "days_per_year": d.groupby("year").size().to_dict(),
                        "max_gap_days": int(d.date.diff().dt.days.max())}

    # 5. HARTI vs CBSL on matching dates
    cross = {}
    cp = os.path.join(HIST, "cbsl_prices.csv")
    if os.path.exists(cp):
        cbsl = pd.read_csv(cp, parse_dates=["date"]).dropna(subset=["price"])
        for c in CROPS:
            h = load_corridor(c)
            for label, hcol, mkt in (("Dambulla wholesale", "wholesale", "DAMBULLA"),
                                     ("Colombo wholesale (HARTI) vs Pettah wholesale (CBSL)", "retail", "PETTAH")):
                s2 = cbsl[(cbsl.commodity == c) & (cbsl.market == mkt) & (cbsl.type == "wholesale")]
                m = h.merge(s2[["date", "price"]], on="date")
                if len(m) >= 30:
                    cross.setdefault(c, {})[label] = {"days": int(len(m)), "pearson_r": round(float(m[hcol].corr(m.price)), 3),
                                                      "median_abs_diff_pct": round(float(((m[hcol] - m.price).abs() / m.price).median() * 100), 1)}
    cbsl_counts = {"listed": int(len(cb)), "downloaded": int(cb.download_status.eq("DOWNLOADED").sum()),
                   "parsed": int(cb.parse_status.eq("PARSED").sum()),
                   "not_on_server": int(cb.error_message.fillna("").str.contains("404").sum()),
                   "first": cb.date.min(), "last": cb.date.max()}

    report = {
        "bulletins_by_year": bulletins.to_dict(orient="index"),
        "bulletins_total": bulletins.sum().to_dict(),
        "missing_bulletins_404": b[b.error_message.fillna("").str.contains("404")].date.sort_values().tolist(),
        "price_rows": int(len(p)),
        "gate1_inverted_low_high": inverted,
        "gate2_jumps_over_60pct_all": int(len(jumps)),
        "gate2_jumps_over_60pct_core_corridor": int(len(core)),
        "gate3_zero_prices": zero_prices,
        "gate3_share_no_trade_cells": round(no_trade, 4),
        "colombo_column_label_by_year": colombo_label.to_dict(orient="index"),
        "corridors": corridors,
        "cbsl": cbsl_counts,
        "cross_check": cross,
    }
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    core.to_csv(os.path.join(ROOT, "results", "flagged_jumps.csv"), index=False)
    with open(os.path.join(ROOT, "results", "data_quality.json"), "w") as f:
        json.dump(report, f, indent=2, default=int)

    print("Bulletins by year:\n", bulletins, "\n")
    print(f"Price rows: {len(p):,} | inverted low>high: {inverted} | zero prices: {zero_prices} "
          f"| no-trade cells: {no_trade:.1%}")
    print(f">60% day-on-day jumps: {len(jumps)} total, {len(core)} on the core corridor "
          "(listed in results/flagged_jumps.csv)")
    print("Colombo column label (Beans rows):\n", colombo_label, "\n")
    print("CBSL reports:", cbsl_counts)
    for c, v in cross.items():
        for k, x in v.items():
            print(f"  cross-check {c:<13} {k:<52} r={x['pearson_r']:.3f}  median diff {x['median_abs_diff_pct']}%  ({x['days']} days)")
    for c, v in corridors.items():
        print(f"{c:<7} {v['days']:>5} days  {v['first']} -> {v['last']}  longest gap {v['max_gap_days']} days")


if __name__ == "__main__":
    main()
