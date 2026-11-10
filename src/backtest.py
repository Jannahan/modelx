import warnings
warnings.filterwarnings("ignore")

import numpy as np, pandas as pd
from walk_forward import walk_forward_splits
from cqr import fit_quantile_models
from aci import run_aci
from breakdown import detect_breakdowns
from decision import break_even, decide

R, C, QUOTA = 0.003, 6.0, 100          # interest per trip, transport Rs/kg, kg bought

# ---------- 1. Load data and build features known at 06:00 on day t ----------
df = pd.read_csv("data/fake_market.csv", parse_dates=["date"])
w, r = df.wholesale, df.retail
# The trader knows today's wholesale price (they are buying at it),
# but only YESTERDAY's retail price.
X = pd.DataFrame({
    "r1_w": r.shift(1) / w,                     # yesterday's retail vs today's wholesale
    "w1_w": w.shift(1) / w,                     # wholesale change since yesterday
    "r7_w": r.shift(7) / w,
    "vol_7d": np.log(r).diff().rolling(7).std().shift(1),
})
df["sell_price"] = r.shift(-1)                   # P^r_{t+1}: what we're forecasting
y_ratio = df.sell_price / w                      # predict it relative to wholesale
df["m_bar"] = (r - w.shift(1)).rolling(90).mean().shift(1)   # past margins only
df["breakdown"] = detect_breakdowns(df)["breakdown"].shift(1, fill_value=False)  # yesterday's flag

keep = X.notna().all(axis=1) & df.sell_price.notna() & df.m_bar.notna()
df, X, y_ratio = df[keep].reset_index(drop=True), X[keep].reset_index(drop=True), y_ratio[keep].reset_index(drop=True)

# ---------- 2. Walk-forward quantile forecasts ----------
rows = []
for train, cal, test in walk_forward_splits(df, test_start="2019-10-01"):
    models = fit_quantile_models(X.iloc[train], y_ratio.iloc[train])
    wt = df.wholesale.to_numpy()[test]
    p = {q: m.predict(X.iloc[test]) * wt for q, m in models.items()}
    for j, i in enumerate(test):
        rows.append({"i": i, "q_lo": p[0.05][j], "q_med": p[0.5][j], "q_hi": p[0.95][j]})
res = pd.DataFrame(rows).set_index("i").join(df)
res["y"] = res.sell_price

# ---------- 3. ACI calibration ----------
res["L"], res["U"], _ = run_aci(res, gamma=0.02)
res = res.dropna(subset=["L"]).copy()

# ---------- 4. Decision for every day ----------
res["B"] = break_even(res.wholesale, R, C)
res["signal"] = [decide(L, M, U, B, mb, breakdown=bd)[0] for L, M, U, B, mb, bd in
                 zip(res.L, res.q_med, res.U, res.B, res.m_bar, res.breakdown)]

# ---------- 5. Trader P&L under each strategy ----------
profit_kg = res.sell_price - res.wholesale - C - R * res.wholesale    # Equation (1)
outlay_kg = res.wholesale * (1 + R) + C
spread_ok = (res.retail.shift(1) - res.wholesale.shift(1)) > C + R * res.wholesale.shift(1)
strategies = {
    "Always Trade":       pd.Series(QUOTA, index=res.index),
    "Yesterday's Spread": np.where(spread_ok, QUOTA, 0),
    "Model Y":            res.signal.map({"GREEN": QUOTA, "AMBER": QUOTA / 2, "RED": 0}),
}

print(f"Backtest {res.date.min().date()} -> {res.date.max().date()} ({len(res)} days)")
print(f"Interval coverage: {((res.y >= res.L) & (res.y <= res.U)).mean():.3f}\n")
print(f"{'Strategy':<20}{'Total P&L (Rs)':>16}{'Days traded':>13}{'Losing days':>13}"
      f"{'Catastrophic':>14}{'Worst day (Rs)':>16}")
for name, kg in strategies.items():
    kg = pd.Series(kg, index=res.index)
    pnl = kg * profit_kg
    traded = kg > 0
    catastrophic = traded & (profit_kg < -0.30 * outlay_kg)
    print(f"{name:<20}{pnl.sum():>16,.0f}{traded.sum():>13}{(pnl < 0).sum():>13}"
          f"{catastrophic.sum():>14}{pnl.min():>16,.0f}")

red = res.signal == "RED"
print(f"\nSignals: {res.signal.value_counts().to_dict()}")
print(f"Refusal justification rate (Red days that would have lost money): "
      f"{(profit_kg[red] < 0).mean():.3f}")
res["year"] = res.date.dt.year
print("\nSignals by year:")
print(pd.crosstab(res.year, res.signal))
res.to_csv("data/backtest_results.csv", index=False)