import numpy as np, pandas as pd
import lightgbm as lgb
from walk_forward import walk_forward_splits

def make_features(df):
    X = pd.DataFrame({
        "lag1_ratio": df["lag_1"] / df["price"],
        "lag7_ratio": df["lag_7"] / df["price"],
        "roll_vol_7d": df["roll_vol_7d"],
    })
    y = df["target"] / df["price"]          # tomorrow relative to today
    return X, y

def fit_quantile_models(X, y, quantiles=(0.05, 0.5, 0.95)):
    models = {}
    for q in quantiles:
        m = lgb.LGBMRegressor(objective="quantile", alpha=q,
                              n_estimators=200, learning_rate=0.05, verbose=-1)
        m.fit(X, y)
        models[q] = m
    return models

def cqr_correction(q_lo, q_hi, y, alpha=0.10):
    scores = np.maximum(q_lo - y, y - q_hi)          # Equation (3)
    level = min(1.0, (1 - alpha) * (1 + 1 / len(scores)))
    return np.quantile(scores, level, method="higher")


if __name__ == "__main__":
    df = pd.read_csv("data/fake_prices.csv").reset_index(drop=True)
    X, y_ratio = make_features(df)
    price, y_true = df["price"].to_numpy(), df["target"].to_numpy()

    rows = []
    for train, cal, test in walk_forward_splits(df):
        models = fit_quantile_models(X.iloc[train], y_ratio.iloc[train])
        pred = lambda idx: {q: m.predict(X.iloc[idx]) * price[idx]
                            for q, m in models.items()}
        pc = pred(cal)
        Q = cqr_correction(pc[0.05], pc[0.95], y_true[cal])
        pt = pred(test)
        for j, i in enumerate(test):
            rows.append({"date": df.date[i], "y": y_true[i], "q_lo": pt[0.05][j],
                         "q_med": pt[0.5][j], "q_hi": pt[0.95][j], "Q": Q})

    res = pd.DataFrame(rows)
    res["lo"], res["hi"] = res.q_lo - res.Q, res.q_hi + res.Q   # Equation (4)
    res["raw_cov"] = (res.y >= res.q_lo) & (res.y <= res.q_hi)
    res["cqr_cov"] = (res.y >= res.lo) & (res.y <= res.hi)
    res["year"] = res.date.str[:4]

    print(res.groupby("year")[["raw_cov", "cqr_cov"]].mean().round(3))
    print("Overall raw:", round(res.raw_cov.mean(), 3),
          "| Overall CQR:", round(res.cqr_cov.mean(), 3))
    res.to_csv("data/cqr_results.csv", index=False)