import numpy as np, pandas as pd

def run_aci(res, alpha=0.10, gamma=0.02, window=90):
    q_lo, q_hi, y = res.q_lo.to_numpy(), res.q_hi.to_numpy(), res.y.to_numpy()
    scores = np.maximum(q_lo - y, y - q_hi)          # how badly each day missed
    n = len(res)
    lo, hi, alphas = np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)
    a = alpha
    for t in range(window, n):
        past = scores[t - window:t]                   # only PAST days
        level = np.clip((1 - a) * (1 + 1 / window), 0, 1)
        Q = np.quantile(past, level, method="higher")
        lo[t], hi[t], alphas[t] = q_lo[t] - Q, q_hi[t] + Q, a
        miss = 1 if (y[t] < lo[t] or y[t] > hi[t]) else 0
        a = a + gamma * (alpha - miss)                # Equation (5)
    return lo, hi, alphas


if __name__ == "__main__":
    res = pd.read_csv("data/cqr_results.csv")
    by_year, summary = {}, []
    for g in [0.0, 0.01, 0.02, 0.05]:
        lo, hi, _ = run_aci(res, gamma=g)
        ok = ~np.isnan(lo)
        cov = (res.y >= lo) & (res.y <= hi)
        width = (hi - lo) / res.y * 100
        by_year[f"γ={g}"] = cov[ok].groupby(res.year[ok]).mean()
        summary.append((g, cov[ok].mean(), np.nanmean(width)))

    print("Coverage by year:")
    print(pd.DataFrame(by_year).round(3))
    print("\nγ     coverage  avg width (% of price)")
    for g, c, w in summary:
        print(f"{g:<5} {c:.3f}     {w:.1f}%")

    lo, hi, alphas = run_aci(res, gamma=0.02)
    res["lo"], res["hi"], res["alpha_t"] = lo, hi, alphas
    res.dropna().to_csv("data/aci_results.csv", index=False)
    