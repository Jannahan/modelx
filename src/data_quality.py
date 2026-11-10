"""
Data-quality report for prices.db (Dataset Gathering Guide, Section 7 gates).

    python src/data_quality.py      ->  prints the report, writes results/data_quality.json

Gates:
  1. Spread logic      price_low <= price_high
  2. Extreme jump      |P_t - P_{t-1}| / P_{t-1} > 60%   (flagged for review, never auto-deleted)
  3. Missing trade     dashes stored as NULL, never 0, never forward-filled
  4. Coverage          which bulletins are missing, per year and per corridor
"""
import json, os, sqlite3, sys
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from db import DB_PATH
from build_real_features import build_corridor_dataset

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CROPS = ("BEANS", "CARROT", "TOMATO", "LEEKS")


def main():
    conn = sqlite3.connect(DB_PATH)
    b = pd.read_sql_query("SELECT date, download_status, parse_status, error_message FROM bulletins", conn)
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
        d = build_corridor_dataset(commodity=c)
        if d.empty:
            continue
        d["year"] = d.date.dt.year
        corridors[c] = {"days": int(len(d)), "first": str(d.date.min().date()), "last": str(d.date.max().date()),
                        "days_per_year": d.groupby("year").size().to_dict(),
                        "max_gap_days": int(d.date.diff().dt.days.max())}

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
    for c, v in corridors.items():
        print(f"{c:<7} {v['days']:>5} days  {v['first']} -> {v['last']}  longest gap {v['max_gap_days']} days")


if __name__ == "__main__":
    main()
