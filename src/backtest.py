"""
Walk-forward backtest (plan Section 6).

    python src/backtest.py                       # all 4 real corridors from prices.db
    python src/backtest.py --commodity BEANS     # one real corridor
    python src/backtest.py --synthetic           # sanity check on data/fake_market.csv

On day t the model only sees: today's Dambulla wholesale price (the trader is buying
at it) and Colombo prices up to yesterday. It forecasts the Colombo price on the next
bulletin day, P^r_{t+1}. Results go to results/ (tracked in git).
"""
import argparse, json, os, sys, warnings
warnings.filterwarnings("ignore")
os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 4))   # silences a Windows CPU probe

import numpy as np, pandas as pd
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from walk_forward import walk_forward_splits
from cqr import fit_quantile_models
from aci import run_aci
from breakdown import detect_breakdowns
from decision import break_even, decide

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")
R, C, QUOTA = 0.003, 6.0, 100          # interest per trip, transport Rs/kg, kg bought
ALPHA, GAMMA = 0.10, 0.02
TEST_START = "2019-10-01"
COMMODITIES = ("BEANS", "CARROT", "TOMATO", "LEEKS")


def pinball(y, q, tau):
    d = y - q
    return np.mean(np.maximum(tau * d, (tau - 1) * d))


def load(commodity, synthetic):
    if synthetic:
        df = pd.read_csv(os.path.join(ROOT, "data", "fake_market.csv"), parse_dates=["date"])
        return df[["date", "wholesale", "retail"]]
    from build_real_features import build_corridor_dataset
    df = build_corridor_dataset(commodity=commodity)
    return df[["date", "wholesale", "retail", "retail_market"]]


def run(commodity="BEANS", synthetic=False, verbose=True):
    df = load(commodity, synthetic).sort_values("date").reset_index(drop=True)
    w, r = df.wholesale, df.retail

    # ---------- 1. Features known at 06:00 on day t ----------
    X = pd.DataFrame({
        "r1_w": r.shift(1) / w,                 # yesterday's Colombo vs today's Dambulla
        "w1_w": w.shift(1) / w,                 # Dambulla change since last bulletin
        "r7_w": r.shift(7) / w,
        "vol_7d": np.log(r).diff().rolling(7).std().shift(1),
        "dow": df.date.dt.dayofweek,
        "gap_days": df.date.diff().dt.days,     # long gaps = holidays / closures
    })
    df["sell_price"] = r.shift(-1)              # P^r_{t+1}: what we forecast
    y_ratio = df.sell_price / w
    df["m_bar"] = (r - w.shift(1)).rolling(90, min_periods=30).mean().shift(1)
    df["breakdown"] = detect_breakdowns(df)["breakdown"].shift(1, fill_value=False)
    # "stale": the last bulletin is more than 4 days old -> RED (plan 3.5)
    df["stale"] = df.date.diff().dt.days > 4

    feat_ok = X.drop(columns="gap_days").notna().all(axis=1) & df.m_bar.notna()
    keep = feat_ok & (df.sell_price.notna() | (df.index == len(df) - 1))   # keep last row: "today"
    df, X, y_ratio = (d[keep].reset_index(drop=True) for d in (df, X, y_ratio))

    # ---------- 2. Walk-forward LightGBM quantiles + baselines ----------
    rows = []
    for train, cal, test in walk_forward_splits(df, test_start=TEST_START):
        tr = [i for i in train if not np.isnan(y_ratio[i])]
        models = fit_quantile_models(X.iloc[tr], y_ratio.iloc[tr])
        wt = df.wholesale.to_numpy()[test]
        p = {q: m.predict(X.iloc[test]) * wt for q, m in models.items()}
        # Naive baseline: 5th/95th pct of the last 90 days' ratio (tomorrow / today)
        hist = y_ratio.iloc[cal].dropna()
        nlo, nhi = np.quantile(hist, 0.05), np.quantile(hist, 0.95)
        for j, i in enumerate(test):
            rows.append({"i": i, "q_lo": p[0.05][j], "q_med": p[0.5][j], "q_hi": p[0.95][j],
                         "naive_lo": nlo * wt[j], "naive_hi": nhi * wt[j]})
    res = pd.DataFrame(rows).set_index("i").join(df)
    res["y"] = res.sell_price

    # ARIMA(1,1,1) baseline on log Colombo price, refit monthly, 90% interval
    res["arima_lo"], res["arima_hi"] = arima_intervals(df, res.index)

    # ---------- 3. Calibration: rolling CQR (gamma=0) vs ACI ----------
    res["cqr_lo"], res["cqr_hi"], _ = run_aci(res, alpha=ALPHA, gamma=0.0)
    res["L"], res["U"], res["alpha_t"] = run_aci(res, alpha=ALPHA, gamma=GAMMA)
    res = res.dropna(subset=["L"]).copy()

    # ---------- 4. Decision for every day ----------
    res["B"] = break_even(res.wholesale, R, C)
    out = [decide(L, M, U, B, mb, breakdown=bd, stale=st) for L, M, U, B, mb, bd, st in
           zip(res.L, res.q_med, res.U, res.B, res.m_bar, res.breakdown, res.stale)]
    res["signal"], res["reason"] = [o[0] for o in out], [o[1] for o in out]

    today = res.iloc[-1]
    ev = res[res.y.notna()].copy()             # evaluation days only

    # ---------- 5. Metrics ----------
    def cov(lo, hi):
        return float(((ev.y >= ev[lo]) & (ev.y <= ev[hi])).mean())
    def width(lo, hi):
        return float(((ev[hi] - ev[lo]) / ev.y).mean() * 100)
    ev["year"] = ev.date.dt.year
    intervals = {"Naive (90-day ratio)": ("naive_lo", "naive_hi"),
                 "ARIMA(1,1,1)": ("arima_lo", "arima_hi"),
                 "Raw LightGBM": ("q_lo", "q_hi"),
                 "Rolling CQR (gamma=0)": ("cqr_lo", "cqr_hi"),
                 f"CQR + ACI (gamma={GAMMA})": ("L", "U")}
    coverage = {k: {"coverage": cov(*v), "width_pct": width(*v)} for k, v in intervals.items()}
    by_year = {k: ev.assign(c=(ev.y >= ev[lo]) & (ev.y <= ev[hi])).groupby("year").c.mean().round(3).to_dict()
               for k, (lo, hi) in intervals.items()}

    profit_kg = ev.sell_price - ev.wholesale - C - R * ev.wholesale     # Equation (1)
    outlay_kg = ev.wholesale * (1 + R) + C
    spread_ok = (ev.retail.shift(1) - ev.wholesale.shift(1)) > C + R * ev.wholesale.shift(1)
    strategies = {
        "Always Trade": pd.Series(QUOTA, index=ev.index),
        "Yesterday's Spread": pd.Series(np.where(spread_ok, QUOTA, 0), index=ev.index),
        "Model Y": ev.signal.map({"GREEN": QUOTA, "AMBER": QUOTA / 2, "RED": 0}),
    }
    pnl_table = {}
    for name, kg in strategies.items():
        pnl = kg * profit_kg
        traded = kg > 0
        pnl_table[name] = {
            "total_pnl": float(pnl.sum()), "days_traded": int(traded.sum()),
            "losing_days": int((pnl < 0).sum()),
            "catastrophic": int((traded & (profit_kg < -0.30 * outlay_kg)).sum()),
            "catastrophic_rs": float(pnl[traded & (profit_kg < -0.30 * outlay_kg)].sum()),
            "worst_day": float(pnl.min()),
        }
    red = ev.signal == "RED"
    summary = {
        "commodity": "SYNTHETIC" if synthetic else commodity,
        "data": "synthetic (data/fake_market.csv)" if synthetic else "HARTI bulletins, Dambulla -> Colombo (Peliyagoda/Pettah)",
        "period": [str(ev.date.min().date()), str(ev.date.max().date())],
        "eval_days": int(len(ev)),
        "pinball": {str(t): float(pinball(ev.y, ev[c], t)) for t, c in
                    [(0.05, "q_lo"), (0.5, "q_med"), (0.95, "q_hi")]},
        "intervals": coverage, "coverage_by_year": by_year, "pnl": pnl_table,
        "signals": ev.signal.value_counts().to_dict(),
        "signals_by_year": pd.crosstab(ev.year, ev.signal).to_dict(orient="index"),
        "refusal_justification_rate": float((profit_kg[red] < 0).mean()) if red.any() else None,
        "base_loss_rate": float((profit_kg < 0).mean()),
        "params": {"r": R, "C": C, "quota_kg": QUOTA, "alpha": ALPHA, "gamma": GAMMA},
        "today": {"date": str(today.date.date()), "wholesale": float(today.wholesale),
                  "break_even": float(today.B), "L": float(today.L), "M": float(today.q_med),
                  "U": float(today.U), "signal": today.signal, "reason": today.reason,
                  "m_bar": float(today.m_bar), "stale": bool(today.stale),
                  "breakdown": bool(today.breakdown)},
    }

    os.makedirs(RESULTS, exist_ok=True)
    tag = summary["commodity"].lower()
    res.drop(columns=["i"], errors="ignore").to_csv(os.path.join(RESULTS, f"backtest_{tag}.csv"), index=False)
    with open(os.path.join(RESULTS, f"summary_{tag}.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)
    if verbose:
        print_summary(summary)
    return summary


def arima_intervals(df, idx, refit_every=30, window=365):
    from statsmodels.tsa.arima.model import ARIMA
    logr = np.log(df.retail.to_numpy())
    lo, hi = pd.Series(np.nan, index=idx), pd.Series(np.nan, index=idx)
    idx = list(idx)
    for k in range(0, len(idx), refit_every):
        block = idx[k:k + refit_every]
        start = block[0]
        try:
            fit = ARIMA(logr[max(0, start - window):start], order=(1, 1, 1)).fit()
            for i in block:
                # At 06:00 on day i only Colombo prices up to day i-1 are published,
                # so the target retail[i+1] is a 2-step-ahead forecast.
                f = fit.apply(logr[max(0, start - window):i]).get_forecast(2)
                ci = np.asarray(f.conf_int(alpha=0.10))[1]
                lo[i], hi[i] = np.exp(ci[0]), np.exp(ci[1])
        except Exception:
            pass
    return lo.to_numpy(), hi.to_numpy()


def print_summary(s):
    print(f"\n=== {s['commodity']}  {s['period'][0]} -> {s['period'][1]}  ({s['eval_days']} days) ===")
    print(f"{'Interval method':<26}{'Coverage':>10}{'Width % price':>15}")
    for k, v in s["intervals"].items():
        print(f"{k:<26}{v['coverage']:>10.3f}{v['width_pct']:>15.1f}")
    print(f"\n{'Strategy':<20}{'Total P&L':>14}{'Traded':>8}{'Losing':>8}{'Catastr.':>10}{'Worst day':>12}")
    for k, v in s["pnl"].items():
        print(f"{k:<20}{v['total_pnl']:>14,.0f}{v['days_traded']:>8}{v['losing_days']:>8}"
              f"{v['catastrophic']:>10}{v['worst_day']:>12,.0f}")
    print(f"Signals: {s['signals']} | refusal justification: {s['refusal_justification_rate']}"
          f" (base loss rate {s['base_loss_rate']:.3f})")
    print(f"Today ({s['today']['date']}): {s['today']['signal']} - {s['today']['reason']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--commodity", choices=COMMODITIES)
    ap.add_argument("--synthetic", action="store_true")
    a = ap.parse_args()
    if a.synthetic:
        run(synthetic=True)
    else:
        for c in ([a.commodity] if a.commodity else COMMODITIES):
            run(c)
