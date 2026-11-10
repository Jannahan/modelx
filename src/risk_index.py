"""
Market-risk index for lenders, cooperatives and NGOs (proposal section 2, secondary user:
"an aggregate market-risk index to time lending or relief").

    python src/risk_index.py      -> results/risk_index.json

For a typical borrower (0.3% interest per trip, Rs. 6/kg transport) the index is the average,
over the five crops, of the chance that tomorrow's Colombo price falls below break-even,
read from each crop's calibrated range (5th, 50th, 95th percentile), on a 0-100 scale.

Validation (2020-2026 test period): days are ranked by index into five equal groups; if the
index means anything, the share of crop-trades that really lost money should rise with it.
"""
import json, os, sys
import numpy as np, pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from history import CROPS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
R, C = 0.003, 6.0


def chance_below(L, M, U, B):
    """Piecewise-linear CDF through (L, 5%), (M, 50%), (U, 95%); same as the web app."""
    p = np.where(B <= M, 0.05 + 0.45 * (B - L) / (M - L), 0.5 + 0.45 * (B - M) / (U - M))
    p = np.where(B <= L, 0.025, p)
    p = np.where(B >= U, 0.975, p)
    return np.clip(p, 0, 1)


def crop_frame(crop):
    bt = pd.read_csv(os.path.join(RES, f"backtest_{crop.lower()}.csv"), parse_dates=["date"])
    live_p = os.path.join(RES, f"live_{crop.lower()}.csv")
    if os.path.exists(live_p):                         # newest days from the daily run
        live = pd.read_csv(live_p, parse_dates=["date"])
        bt = pd.concat([bt, live[live.date > bt.date.max()]], ignore_index=True)
    B = bt.wholesale * (1 + R) + C
    out = pd.DataFrame({"date": bt.date, "p_below": chance_below(bt.L, bt.q_med, bt.U, B)})
    profit = bt.sell_price - B
    out["lost"] = np.where(profit.notna(), (profit < 0).astype(float), np.nan)
    return out.set_index("date")


def main():
    frames = {c: crop_frame(c) for c in CROPS if os.path.exists(os.path.join(RES, f"backtest_{c.lower()}.csv"))}
    p = pd.DataFrame({c: f.p_below for c, f in frames.items()})
    lost = pd.DataFrame({c: f.lost for c, f in frames.items()})
    idx = (p.mean(axis=1, skipna=True) * 100).dropna()
    test = idx[idx.index >= "2020-01-01"]

    # validation: realised loss share across crops on each day, by index quintile
    real = lost.mean(axis=1, skipna=True).reindex(test.index)
    ok = real.notna()
    q = pd.qcut(test[ok], 5, labels=False)
    quint = [{"group": int(g) + 1, "index_from": round(float(test[ok][q == g].min()), 1),
              "index_to": round(float(test[ok][q == g].max()), 1),
              "share_of_trades_that_lost": round(float(real[ok][q == g].mean()), 3), "days": int((q == g).sum())}
             for g in range(5)]
    corr = float(np.corrcoef(test[ok], real[ok])[0, 1])

    today_date = idx.index.max()
    today = float(idx.loc[today_date])
    pct_rank = float((test < today).mean())
    level = "High" if pct_rank >= 0.8 else "Elevated" if pct_rank >= 0.6 else "Normal" if pct_rank >= 0.2 else "Low"
    monthly = test.resample("MS").mean().dropna()
    out = {
        "method": "Average over crops of P(tomorrow's Colombo price < break-even at 0.3%/trip, Rs. 6/kg), 0-100",
        "today": {"date": str(today_date.date()), "index": round(today, 1), "level": level,
                  "higher_than_share_of_days": round(pct_rank, 3),
                  "crops": {c: round(float(p.loc[today_date, c]) * 100, 1) for c in p.columns if pd.notna(p.loc[today_date, c])}},
        "monthly": [[d.strftime("%Y-%m"), round(float(v), 1)] for d, v in monthly.items()],
        "last_90_days": [[d.strftime("%Y-%m-%d"), round(float(v), 1)] for d, v in idx.tail(90).items()],
        "validation": {"quintiles": quint, "correlation_with_share_lost": round(corr, 3), "days": int(ok.sum())},
    }
    with open(os.path.join(RES, "risk_index.json"), "w") as f:
        json.dump(out, f, indent=2)
    print(f"Risk index today ({out['today']['date']}): {today:.1f} ({level}, higher than {pct_rank:.0%} of days since 2020)")
    for g in quint:
        print(f"  group {g['group']}: index {g['index_from']}-{g['index_to']}  ->  {g['share_of_trades_that_lost']:.1%} of trades lost ({g['days']} days)")
    print(f"  correlation with the share of trades that lost: {corr:.2f}")
    return out


if __name__ == "__main__":
    main()
