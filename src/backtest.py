"""
Walk-forward backtest (plan Section 6) with honest threshold tuning.

    python src/backtest.py                       # all 4 real corridors from prices.db
    python src/backtest.py --commodity BEANS     # one real corridor
    python src/backtest.py --synthetic           # sanity check on data/fake_market.csv

Timeline (no look-ahead):
  * Forecasts are produced walk-forward from 2016-07 onward. On day t the model only
    sees today's Dambulla wholesale price (the trader is buying at it) and Colombo
    prices up to yesterday, and forecasts the Colombo price on the next bulletin day.
  * TUNE period 2016-07-01 .. 2019-12-31: the decision-rule thresholds (width factor
    beta, breakdown z-limit and correlation limit) are chosen here, once, shared by
    all four crops.
  * TEST period 2020-01-01 .. latest: reported with BOTH the original plan thresholds
    and the tuned thresholds. The test period is never used to pick anything.

Results go to results/ (tracked in git).
"""
import argparse, itertools, json, os, sys, warnings
warnings.filterwarnings("ignore")
os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 4))   # silences a Windows CPU probe

import numpy as np, pandas as pd
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from walk_forward import walk_forward_splits
from cqr import fit_quantile_models
from aci import run_aci
from breakdown import detect_breakdowns
from decision import break_even, decide
from history import CROPS, load_corridor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")
R, C, QUOTA = 0.003, 6.0, 100          # interest per trip, transport Rs/kg, kg bought
ALPHA, GAMMA = 0.10, 0.02
FORECAST_START = "2016-07-01"
TEST_START = "2020-01-01"
COMMODITIES = CROPS
SHOCKS = {"2020 COVID lockdown": "2020-03-20", "2022 fuel crisis": "2022-06-15"}
INTEREST_GRID = [0.0, 0.003, 0.01, 0.02, 0.03, 0.05, 0.10]

PLAN = {"beta": 3.0, "z_limit": 2.5, "corr_limit": 0.35}               # plan Section 3.4/3.5
GRID = {"beta": [3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 1e9],                   # 1e9 = width rule off
        "z_limit": [2.5, 3.0, 3.5, 4.0, 1e9],                           # 1e9 = residual rule off
        "corr_limit": [0.35, 0.2, 0.0, -2.0]}                            # -2 = correlation rule off


def pinball(y, q, tau):
    d = y - q
    return float(np.mean(np.maximum(tau * d, (tau - 1) * d)))


def load(commodity, synthetic):
    if synthetic:
        df = pd.read_csv(os.path.join(ROOT, "data", "fake_market.csv"), parse_dates=["date"])
        return df[["date", "wholesale", "retail"]]
    return load_corridor(commodity)[["date", "wholesale", "retail", "retail_market"]]


def bd_col(z, c):
    return f"bd_z{z:g}_c{c:g}"


# ------------------------------------------------------------------------------------------
# 1. Forecasts (expensive, run once per crop)
# ------------------------------------------------------------------------------------------
def forecast(commodity="BEANS", synthetic=False, use_weather=True, with_arima=True, use_extra=True):
    df = load(commodity, synthetic).sort_values("date").reset_index(drop=True)
    w, r = df.wholesale, df.retail

    X = pd.DataFrame({
        "r1_w": r.shift(1) / w,                 # yesterday's Colombo vs today's Dambulla
        "w1_w": w.shift(1) / w,                 # Dambulla change since last bulletin
        "r7_w": r.shift(7) / w,
        "vol_7d": np.log(r).diff().rolling(7).std().shift(1),
        "dow": df.date.dt.dayofweek,
        "gap_days": df.date.diff().dt.days,     # long gaps = holidays / closures
    })
    if use_extra:                               # proposal section 6: lags 2 and 14 as well
        X["r2_w"] = r.shift(2) / w
        X["r14_w"] = r.shift(14) / w
        X["w7_w"] = w.shift(7) / w
    if use_weather and not synthetic:           # rain in growing areas, ending yesterday
        from weather import rain_features
        X = pd.concat([X, rain_features(df.date)], axis=1)
    if use_extra and not synthetic:             # calendar (known ahead) + diesel and USD/LKR changes
        from macro import calendar_features, cost_features
        cal = calendar_features(df.date)
        cost = cost_features(df.date)
        X = pd.concat([X, cal, cost[["diesel_change_30d", "fx_change_30d"]]], axis=1)
        X["diesel_per_kg_price"] = cost["diesel"] / w      # fuel cost relative to the crop's price
    df["sell_price"] = r.shift(-1)              # P^r_{t+1}: what we forecast
    y_ratio = df.sell_price / w
    df["m_bar"] = (r - w.shift(1)).rolling(90, min_periods=30).mean().shift(1)
    df["stale"] = df.date.diff().dt.days > 4   # last bulletin > 4 days old -> RED
    # Breakdown flags for every threshold pair; yesterday's flag is what is known at 06:00
    for z, c in itertools.product(GRID["z_limit"], GRID["corr_limit"]):
        out = detect_breakdowns(df, z_limit=z, corr_limit=c)
        df[bd_col(z, c)] = out["breakdown"].shift(1, fill_value=False)

    feat_ok = X.drop(columns="gap_days").notna().all(axis=1) & df.m_bar.notna()
    df["bd_plan"] = df[bd_col(PLAN["z_limit"], PLAN["corr_limit"])]   # detector at plan settings
    keep = feat_ok & (df.sell_price.notna() | (df.index == len(df) - 1))   # keep last row: "today"
    df, X, y_ratio = (d[keep].reset_index(drop=True) for d in (df, X, y_ratio))

    rows = []
    # synthetic data only starts in 2019, so it needs a later first forecast day
    start = "2019-10-01" if synthetic else FORECAST_START
    for train, cal, test in walk_forward_splits(df, test_start=start):
        tr = [i for i in train if not np.isnan(y_ratio[i])]
        models = fit_quantile_models(X.iloc[tr], y_ratio.iloc[tr])
        wt = df.wholesale.to_numpy()[test]
        p = {q: m.predict(X.iloc[test]) * wt for q, m in models.items()}
        hist = y_ratio.iloc[cal].dropna()      # Naive: 5th/95th pct of last 90 days' ratio
        nlo, nhi = np.quantile(hist, 0.05), np.quantile(hist, 0.95)
        for j, i in enumerate(test):
            rows.append({"i": i, "q_lo": p[0.05][j], "q_med": p[0.5][j], "q_hi": p[0.95][j],
                         "naive_lo": nlo * wt[j], "naive_hi": nhi * wt[j]})
    res = pd.DataFrame(rows).set_index("i").join(df)
    res["y"] = res.sell_price
    res["arima_lo"], res["arima_hi"] = arima_intervals(df, res.index) if with_arima else (np.nan, np.nan)
    res["cqr_lo"], res["cqr_hi"], _ = run_aci(res, alpha=ALPHA, gamma=0.0)
    res["L"], res["U"], res["alpha_t"] = run_aci(res, alpha=ALPHA, gamma=GAMMA)
    res = res.dropna(subset=["L"]).reset_index(drop=True)
    res["B"] = break_even(res.wholesale, R, C)
    return res


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


# ------------------------------------------------------------------------------------------
# 2. Decisions (cheap, re-run per threshold set)
# ------------------------------------------------------------------------------------------
def apply_rule(res, beta, z_limit, corr_limit):
    bd = res[bd_col(z_limit, corr_limit)]
    out = [decide(L, M, U, B, mb, beta=beta, breakdown=b, stale=s) for L, M, U, B, mb, b, s in
           zip(res.L, res.q_med, res.U, res.B, res.m_bar, bd, res.stale)]
    return pd.Series([o[0] for o in out], index=res.index), pd.Series([o[1] for o in out], index=res.index), bd


def pnl_metrics(ev, signal, r=R):
    profit_kg = ev.sell_price - ev.wholesale - C - r * ev.wholesale     # Equation (1)
    outlay_kg = ev.wholesale * (1 + r) + C
    spread_ok = (ev.retail.shift(1) - ev.wholesale.shift(1)) > C + r * ev.wholesale.shift(1)
    strategies = {
        "Always Trade": pd.Series(QUOTA, index=ev.index),
        "Yesterday's Spread": pd.Series(np.where(spread_ok, QUOTA, 0), index=ev.index),
        "Model Y": signal.map({"GREEN": QUOTA, "AMBER": QUOTA / 2, "RED": 0}),
    }
    table = {}
    for name, kg in strategies.items():
        pnl = kg * profit_kg
        traded = kg > 0
        cat = traded & (profit_kg < -0.30 * outlay_kg)
        table[name] = {"total_pnl": float(pnl.sum()), "days_traded": int(traded.sum()),
                       "losing_days": int((pnl < 0).sum()), "catastrophic": int(cat.sum()),
                       "catastrophic_rs": float(pnl[cat].sum()), "worst_day": float(pnl.min())}
    red = signal == "RED"
    return table, {
        "signals": signal.value_counts().to_dict(),
        "refusal_justification_rate": float((profit_kg[red] < 0).mean()) if red.any() else None,
        "loss_rate_on_traded_days": float((profit_kg[~red] < 0).mean()) if (~red).any() else None,
        "base_loss_rate": float((profit_kg < 0).mean()),
    }


def tune(all_res):
    """Pick one shared threshold set that maximises Model Y's pooled P&L over the TUNE period."""
    scores = []
    for beta, z, c in itertools.product(GRID["beta"], GRID["z_limit"], GRID["corr_limit"]):
        total, cat = 0.0, 0
        for res in all_res.values():
            ev = res[(res.date < TEST_START) & res.y.notna()]
            sig, _, _ = apply_rule(ev, beta, z, c)
            t, _ = pnl_metrics(ev, sig)
            total += t["Model Y"]["total_pnl"]; cat += t["Model Y"]["catastrophic"]
        scores.append({"beta": beta, "z_limit": z, "corr_limit": c, "tune_pnl": total, "tune_catastrophic": cat})
    scores = pd.DataFrame(scores).sort_values(["tune_pnl", "tune_catastrophic"], ascending=[False, True])
    os.makedirs(RESULTS, exist_ok=True)
    scores.to_csv(os.path.join(RESULTS, "tuning_grid.csv"), index=False)
    best = scores.iloc[0]
    tuned = {"beta": float(best.beta), "z_limit": float(best.z_limit), "corr_limit": float(best.corr_limit)}
    with open(os.path.join(RESULTS, "thresholds.json"), "w") as f:
        json.dump({"tuned": tuned, "plan": PLAN, "tuned_on": [FORECAST_START, "2019-12-31"]}, f, indent=2)
    return tuned



def extra_measures(res, ev, tuned):
    """Proposal Table 4 measures beyond coverage and P&L."""
    out = {}
    # Point accuracy: median vs naive (last Colombo price known at 06:00) and seasonal naive
    naive = res.retail.shift(1).loc[ev.index]
    target_date = res.date.shift(-1)
    hist = res[["date", "retail"]].rename(columns={"date": "d7", "retail": "seasonal"})
    look = pd.DataFrame({"d7": (target_date - pd.Timedelta(days=7)).loc[ev.index]}).dropna()
    seas = pd.merge_asof(look.sort_values("d7"), hist.sort_values("d7"), on="d7").set_index(look.sort_values("d7").index)
    out["point_accuracy_mae"] = {
        "LightGBM median": float((ev.q_med - ev.y).abs().mean()),
        "Naive (last Colombo price)": float((naive - ev.y).abs().mean()),
        "Seasonal naive (same day last week)": float((seas.seasonal.reindex(ev.index) - ev.y).abs().mean()),
    }
    # Loss frequency and simulated profit at several interest rates
    rows = []
    for r in INTEREST_GRID:
        e = ev.assign(B=break_even(ev.wholesale, r, C))
        sig, _, _ = apply_rule(e, **tuned)
        t, x = pnl_metrics(e, sig, r=r)
        rows.append({"r": r, "always_loss_rate": x["base_loss_rate"],
                     "always_pnl": t["Always Trade"]["total_pnl"], "model_y_pnl": t["Model Y"]["total_pnl"],
                     "model_y_days": t["Model Y"]["days_traded"], "always_catastrophic": t["Always Trade"]["catastrophic"],
                     "model_y_catastrophic": t["Model Y"]["catastrophic"]})
    out["by_interest_rate"] = rows
    gross = float((ev.sell_price - ev.wholesale - C).mean())
    out["break_even_interest_rate"] = gross / float(ev.wholesale.mean()) if gross > 0 else 0.0
    # Refusal cost: what RED gives up
    sig = res.loc[ev.index, "signal_tuned"]
    profit = (ev.sell_price - ev.wholesale - C - R * ev.wholesale) * QUOTA
    red = sig == "RED"
    out["refusal_cost"] = {"red_days": int(red.sum()),
                           "red_days_profitable_share": float((profit[red] > 0).mean()) if red.any() else None,
                           "profit_forgone_rs": float(profit[red].clip(lower=0).sum()),
                           "losses_avoided_rs": float(-profit[red].clip(upper=0).sum())}
    # Breakdown warning before known shocks: full detector (residual + correlation, plan settings)
    # against rolling correlation alone (proposal Table 4)
    detectors = {"detector": "bd_plan", "correlation only": bd_col(1e9, PLAN["corr_limit"])}
    bw = {}
    for label, col in detectors.items():
        if col not in res:
            continue
        flags = res[col].astype(bool)
        base = float(flags.mean())
        warn = {}
        for name, d in SHOCKS.items():
            d = pd.Timestamp(d)
            pre = res[(res.date < d) & (res.date >= d - pd.Timedelta(days=30))]
            pf = flags[pre.index]
            # days of warning: length of the unbroken flagged run that is still on just before the shock
            run = 0
            for v in pf.iloc[::-1]:
                if not v:
                    break
                run += 1
            first = pre.date[pf].min() if pf.any() else None
            warn[name] = {"flag_rate_30d_before": float(pf.mean()) if len(pre) else None,
                          "lift_vs_usual": float(pf.mean() / base) if len(pre) and base > 0 else None,
                          "first_flag_days_before": int((d - first).days) if first is not None else None,
                          "flagged_bulletins_in_a_row_before": run}
        bw[label] = {"base_flag_rate": base, "shocks": warn}
    out["breakdown_warning"] = {**bw.get("detector", {}), "comparison": bw}
    # Recent honesty: share of the last 30 real prices inside their range
    last = ev.tail(30)
    out["recent_hit_rate_30d"] = float(((last.y >= last.L) & (last.y <= last.U)).mean())
    return out

# ------------------------------------------------------------------------------------------
# 3. Report
# ------------------------------------------------------------------------------------------
def summarise(res, name, tuned, synthetic=False):
    ev = res[(res.date >= TEST_START) & res.y.notna()].copy()
    ev["year"] = ev.date.dt.year

    def cov(lo, hi):
        return float(((ev.y >= ev[lo]) & (ev.y <= ev[hi])).mean())
    def width(lo, hi):
        return float(((ev[hi] - ev[lo]) / ev.y).mean() * 100)
    intervals = {"Naive (90-day ratio)": ("naive_lo", "naive_hi"),
                 "ARIMA(1,1,1)": ("arima_lo", "arima_hi"),
                 "Raw LightGBM": ("q_lo", "q_hi"),
                 "Rolling CQR (gamma=0)": ("cqr_lo", "cqr_hi"),
                 f"CQR + ACI (gamma={GAMMA})": ("L", "U")}

    rules = {"plan": PLAN, "tuned": tuned}
    decisions = {}
    for k, p in rules.items():
        sig, reason, bd = apply_rule(ev, **p)
        table, extra = pnl_metrics(ev, sig)
        decisions[k] = {"thresholds": p, "pnl": table, **extra,
                        "breakdown_rate": float(bd.mean()),
                        "red_reasons": reason[sig == "RED"].value_counts().to_dict(),
                        "signals_by_year": pd.crosstab(ev.year, sig).to_dict(orient="index")}
        res.loc[ev.index, f"signal_{k}"] = sig
        res.loc[ev.index, f"reason_{k}"] = reason

    extras = extra_measures(res, ev, tuned)

    # "today" = the last bulletin row, decided with the tuned thresholds
    today = res.iloc[-1]
    t_sig, t_reason, t_bd = apply_rule(res.iloc[[-1]], **tuned)
    summary = {
        "commodity": name,
        "data": "synthetic (data/fake_market.csv)" if synthetic else
                "HARTI bulletins, Dambulla -> Colombo (Pettah to 2021, Peliyagoda after)",
        "tune_period": [str(res.date.min().date()), "2019-12-31"],
        "period": [str(ev.date.min().date()), str(ev.date.max().date())],
        "eval_days": int(len(ev)),
        "pinball": {str(t): pinball(ev.y, ev[c], t) for t, c in
                    [(0.05, "q_lo"), (0.5, "q_med"), (0.95, "q_hi")]},
        "intervals": {k: {"coverage": cov(*v), "width_pct": width(*v)} for k, v in intervals.items()},
        "coverage_by_year": {k: ev.assign(c=(ev.y >= ev[lo]) & (ev.y <= ev[hi])).groupby("year").c.mean()
                             .round(3).to_dict() for k, (lo, hi) in intervals.items()},
        "decision": decisions,
        **extras,
        # kept at top level for the dashboard: tuned rule
        "pnl": decisions["tuned"]["pnl"], "signals": decisions["tuned"]["signals"],
        "signals_by_year": decisions["tuned"]["signals_by_year"],
        "refusal_justification_rate": decisions["tuned"]["refusal_justification_rate"],
        "base_loss_rate": decisions["tuned"]["base_loss_rate"],
        "params": {"r": R, "C": C, "quota_kg": QUOTA, "alpha": ALPHA, "gamma": GAMMA, **tuned},
        "today": {"date": str(today.date.date()), "wholesale": float(today.wholesale),
                  "break_even": float(today.B), "L": float(today.L), "M": float(today.q_med),
                  "U": float(today.U), "signal": t_sig.iloc[0], "reason": t_reason.iloc[0],
                  "m_bar": float(today.m_bar), "stale": bool(today.stale),
                  "breakdown": bool(t_bd.iloc[0]), "breakdown_advisory": bool(today.bd_plan),
                  "beta": tuned["beta"]},
    }
    tag = name.lower()
    keep_cols = [c for c in res.columns if not c.startswith("bd_") or c == "bd_plan"]
    res[keep_cols].to_csv(os.path.join(RESULTS, f"backtest_{tag}.csv"), index=False)
    with open(os.path.join(RESULTS, f"summary_{tag}.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)
    return summary


def print_summary(s):
    print(f"\n=== {s['commodity']}  test {s['period'][0]} -> {s['period'][1]}  ({s['eval_days']} days) ===")
    print(f"{'Interval method':<26}{'Coverage':>10}{'Width % price':>15}")
    for k, v in s["intervals"].items():
        print(f"{k:<26}{v['coverage']:>10.3f}{v['width_pct']:>15.1f}")
    for k, d in s["decision"].items():
        print(f"\n[{k} thresholds {d['thresholds']}]  breakdown flagged on {d['breakdown_rate']:.0%} of days")
        print(f"{'Strategy':<20}{'Total P&L':>14}{'Traded':>8}{'Losing':>8}{'Catastr.':>10}{'Worst day':>12}")
        for name, v in d["pnl"].items():
            print(f"{name:<20}{v['total_pnl']:>14,.0f}{v['days_traded']:>8}{v['losing_days']:>8}"
                  f"{v['catastrophic']:>10}{v['worst_day']:>12,.0f}")
        rj = d["refusal_justification_rate"]
        print(f"Signals {d['signals']} | RED days that lose: {rj if rj is None else round(rj, 3)}"
              f" | base loss rate {d['base_loss_rate']:.3f}")
    print(f"Today ({s['today']['date']}): {s['today']['signal']} - {s['today']['reason']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--commodity", choices=COMMODITIES)
    ap.add_argument("--synthetic", action="store_true")
    a = ap.parse_args()
    os.makedirs(RESULTS, exist_ok=True)
    if a.synthetic:
        res = forecast(synthetic=True)
        print_summary(summarise(res, "SYNTHETIC", PLAN, synthetic=True))
    else:
        crops = [a.commodity] if a.commodity else list(COMMODITIES)
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=len(crops)) as pool:
            all_res = dict(zip(crops, pool.map(forecast, crops)))
        tuned = tune(all_res)
        print(f"Tuned on {FORECAST_START}..2019-12-31 (all crops pooled): {tuned}  | plan: {PLAN}")
        summaries = {}
        for c in crops:
            summaries[c] = summarise(all_res[c], c, tuned)
            print_summary(summaries[c])

        # Feature ablation: drop the rainfall features, or drop the calendar / diesel / FX / extra lags
        from functools import partial
        with ProcessPoolExecutor(max_workers=len(crops)) as pool:
            no_w = dict(zip(crops, pool.map(partial(forecast, use_weather=False, with_arima=False), crops)))
            no_x = dict(zip(crops, pool.map(partial(forecast, use_extra=False, with_arima=False), crops)))
        ab = {}
        for c in crops:
            rows = {}
            for label, res in (("all features", all_res[c]), ("without rainfall", no_w[c]),
                               ("without calendar, fuel, FX, lags 2/14", no_x[c])):
                ev = res[(res.date >= TEST_START) & res.y.notna()]
                rows[label] = {"coverage": float(((ev.y >= ev.L) & (ev.y <= ev.U)).mean()),
                               "width_pct": float(((ev.U - ev.L) / ev.y).mean() * 100),
                               "pinball_median": pinball(ev.y, ev.q_med, 0.5),
                               "mae_median": float((ev.q_med - ev.y).abs().mean()),
                               "raw_coverage": float(((ev.y >= ev.q_lo) & (ev.y <= ev.q_hi)).mean())}
            ab[c] = rows
        with open(os.path.join(RESULTS, "ablation_features.json"), "w") as f:
            json.dump(ab, f, indent=2)
        old = os.path.join(RESULTS, "ablation_weather.json")
        if os.path.exists(old):
            os.remove(old)
        print("\nFeature ablation (test period): width % | median error Rs. | coverage")
        for c, rows in ab.items():
            print(c, " | ".join(f"{k}: {v['width_pct']:.1f}% / {v['mae_median']:.1f} / {v['coverage']:.3f}" for k, v in rows.items()))
