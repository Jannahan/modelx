import warnings
warnings.filterwarnings("ignore")            # hides harmless feature-name warnings

import numpy as np, pandas as pd
from mapie.regression import ConformalizedQuantileRegressor
from walk_forward import walk_forward_splits
from cqr import make_features, fit_quantile_models, cqr_correction

df = pd.read_csv("data/fake_prices.csv").reset_index(drop=True)
X, y = make_features(df)

max_diff, n_checked = 0.0, 0
for train, cal, test in list(walk_forward_splits(df))[::10]:   # every 10th split
    models = fit_quantile_models(X.iloc[train], y.iloc[train])

    # --- Your engine ---
    Q = cqr_correction(models[0.05].predict(X.iloc[cal]),
                       models[0.95].predict(X.iloc[cal]),
                       y.iloc[cal].to_numpy())
    my_lo = models[0.05].predict(X.iloc[test]) - Q
    my_hi = models[0.95].predict(X.iloc[test]) + Q

    # --- MAPIE, given the SAME trained models (order: lower, upper, median) ---
    mapie = ConformalizedQuantileRegressor(
        [models[0.05], models[0.95], models[0.5]],
        confidence_level=0.90, prefit=True)
    mapie.conformalize(X.iloc[cal], y.iloc[cal])
    _, bounds = mapie.predict_interval(X.iloc[test], symmetric_correction=True)
    m_lo, m_hi = bounds[:, 0, 0], bounds[:, 1, 0]

    max_diff = max(max_diff, np.abs(my_lo - m_lo).max(), np.abs(my_hi - m_hi).max())
    n_checked += len(test)

print(f"Checked {n_checked} test days")
print(f"Largest difference vs MAPIE: {max_diff:.2e}")
print("PASS ✅" if max_diff < 1e-6 else "MISMATCH ❌")