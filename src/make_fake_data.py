import numpy as np, pandas as pd

rng = np.random.default_rng(42)
dates = pd.date_range("2019-01-01", "2026-10-31", freq="D")
price = [200.0]
for d in dates[1:]:
    vol = 0.08 if d.year == 2022 else 0.03   # 2022 = crisis shock
    price.append(max(50, price[-1] * np.exp(rng.normal(0, vol))))

df = pd.DataFrame({"date": dates, "price": price})
df["lag_1"] = df.price.shift(1)
df["lag_7"] = df.price.shift(7)
df["roll_vol_7d"] = df.price.pct_change().rolling(7).std().shift(1)
df["target"] = df.price.shift(-1)          # tomorrow's price
df = df.dropna()
df.to_csv("data/fake_prices.csv", index=False)
print(df.head()); print("Rows:", len(df))