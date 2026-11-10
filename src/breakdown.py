import numpy as np, pandas as pd

def detect_breakdowns(df, window=60, z_limit=2.5, corr_window=14, corr_limit=0.35,
                      min_clean=20):
    """Flag days where Dambulla -> Colombo price transmission breaks down."""
    w_lag = df["wholesale"].shift(1).to_numpy()      # P^w_{t-1}
    r = df["retail"].to_numpy()                      # P^r_t
    n = len(df)
    corr = pd.Series(w_lag).rolling(corr_window).corr(pd.Series(r)).to_numpy()

    z = np.full(n, np.nan)
    flag_resid = np.zeros(n, dtype=bool)
    clean = np.ones(n, dtype=bool)                   # days we trust for fitting
    for t in range(window + 1, n):
        idx = np.arange(t - window, t)               # only PAST days
        good = idx[clean[idx]]                       # NEW: skip broken days
        if len(good) >= min_clean:
            idx = good
        x, y = w_lag[idx], r[idx]
        b1, b0 = np.polyfit(x, y, 1)                 # Equation (6)
        sigma = np.std(y - (b0 + b1 * x), ddof=2)
        z[t] = abs(r[t] - (b0 + b1 * w_lag[t])) / sigma
        flag_resid[t] = z[t] > z_limit
        clean[t] = not (flag_resid[t] or corr[t] < corr_limit)

    out = df.copy()
    out["z_resid"], out["corr_14d"] = z, corr
    out["flag_resid"] = flag_resid
    out["flag_corr"] = out.corr_14d < corr_limit
    out["breakdown"] = out.flag_resid | out.flag_corr
    return out


if __name__ == "__main__":
    df = pd.read_csv("data/fake_pair.csv", parse_dates=["date"])
    out = detect_breakdowns(df).dropna(subset=["z_resid", "corr_14d"])
    truth, flag = out.true_breakdown, out.breakdown

    print("Detection rate (true breakdowns flagged):", round(flag[truth].mean(), 3))
    print("False alarm rate (normal days flagged):  ", round(flag[~truth].mean(), 3))
    for a, b in [("2020-03-20", "2020-05-10"), ("2022-06-15", "2022-07-20")]:
        first = out[(out.date >= a) & (out.date <= b) & out.breakdown].date.min()
        print(f"Breakdown starting {a}: first flagged on {first.date()} "
              f"({(first - pd.Timestamp(a)).days} days later)")
    out.to_csv("data/breakdown_results.csv", index=False)