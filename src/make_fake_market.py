import numpy as np, pandas as pd

rng = np.random.default_rng(11)
dates = pd.date_range("2019-01-01", "2026-10-31", freq="D")
n = len(dates)

# Dambulla wholesale: wanders around Rs.150, much wilder in 2022
logw = [np.log(150)]
for d in dates[1:]:
    vol = 0.08 if d.year == 2022 else 0.03
    logw.append(logw[-1] + 0.02 * (np.log(150) - logw[-1]) + rng.normal(0, vol))
w = np.exp(logw)

# Market breakdowns: lockdown + fuel standstill
broken = np.zeros(n, dtype=bool)
for a, b in [("2020-03-20", "2020-05-10"), ("2022-06-15", "2022-07-20")]:
    broken |= (dates >= a) & (dates <= b)

# Colombo retail: about 15% above YESTERDAY's wholesale, noisier in 2022
r = np.empty(n)
r[0] = 1.15 * w[0]
drift = 1.0
for t in range(1, n):
    noise = 0.10 if dates[t].year == 2022 else 0.04
    if broken[t]:
        drift *= np.exp(rng.normal(0, 0.08))      # retail goes its own way
    else:
        drift = 1.0
    r[t] = 1.15 * w[t - 1] * drift * np.exp(rng.normal(0, noise))

pd.DataFrame({"date": dates, "wholesale": w, "retail": r,
              "true_breakdown": broken}).to_csv("data/fake_market.csv", index=False)
print("Saved", n, "days |", broken.sum(), "breakdown days")