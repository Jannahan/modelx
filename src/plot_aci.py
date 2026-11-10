import os
import pandas as pd
import matplotlib.pyplot as plt

res = pd.read_csv("data/aci_results.csv", parse_dates=["date"])
w = res[(res.date >= "2021-07-01") & (res.date <= "2023-06-30")]
miss = (w.y < w.lo) | (w.y > w.hi)

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True,
                               gridspec_kw={"height_ratios": [3, 1]})

ax1.axvspan(pd.Timestamp("2022-01-01"), pd.Timestamp("2022-12-31"),
            color="orange", alpha=0.1, label="2022 crisis")
ax1.fill_between(w.date, w.lo, w.hi, alpha=0.3, label="90% ACI interval")
ax1.plot(w.date, w.y, color="black", lw=0.8, label="Actual price")
ax1.scatter(w.date[miss], w.y[miss], color="red", s=12, zorder=3, label="Miss")
ax1.set_ylabel("Price (Rs./kg)")
ax1.set_title("ACI intervals adapting through the 2022 shock (synthetic data)")
ax1.legend(loc="upper left")

ax2.plot(w.date, w.alpha_t, color="purple")
ax2.axhline(0.10, ls="--", color="grey", label="target α = 0.10")
ax2.set_ylabel("α_t")
ax2.legend(loc="upper left")

plt.tight_layout()
os.makedirs("figures", exist_ok=True)
plt.savefig("figures/aci_2022.png", dpi=150)
plt.show()