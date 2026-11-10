import numpy as np, pandas as pd

rng = np.random.default_rng(7)
dates = pd.date_range("2019-01-01", "2026-10-31", freq="D")
n = len(dates)

# Dambulla wholesale: random walk, wilder in 2022
w = [150.0]
for d in dates[1:]:
    vol = 0.08 if d.year == 2022 else 0.03
    w.append(max(40, w[-1] * np.exp(rng.normal(0, vol))))
w = np.array(w)

# Known market breakdowns (lockdown + fuel standstill)
breaks = [("2020-03-20", "2020-05-10"), ("2022-06-15", "2022-07-20")]
broken = np.zeros(n, dtype=bool)
for a, b in breaks:
    broken |= (dates >= a) & (dates <= b)

# Colombo retail: normally follows yesterday's wholesale (Equation 6)
r = np.empty(n)
r[0] = 20 + 1.3 * w[0]
drift = 1.0
for t in range(1, n):
    if broken[t]:
        drift *= np.exp(rng.normal(0.01, 0.06))     # retail drifts away on its own
        r[t] = (20 + 1.3 * w[t - 1]) * drift
    else:
        drift = 1.0
        r[t] = (20 + 1.3 * w[t - 1]) * np.exp(rng.normal(0, 0.03))

pd.DataFrame({"date": dates, "wholesale": w, "retail": r,
              "true_breakdown": broken}).to_csv("data/fake_pair.csv", index=False)
print("Saved", n, "days |", broken.sum(), "breakdown days")
