import pandas as pd

def walk_forward_splits(df, test_start="2020-01-01", cal_days=90, retrain_every=30):
    """Yield (train_idx, cal_idx, test_idx). Never uses future data."""
    dates = pd.to_datetime(df["date"]).reset_index(drop=True)
    first = int(dates.searchsorted(pd.Timestamp(test_start)))
    for start in range(first, len(df), retrain_every):
        end = min(start + retrain_every, len(df))
        cal_start = start - cal_days
        train_idx = list(range(0, cal_start))
        cal_idx = list(range(cal_start, start))
        test_idx = list(range(start, end))
        # Safety check: everything used must come BEFORE the test days
        assert max(train_idx) < min(cal_idx) < min(test_idx)
        yield train_idx, cal_idx, test_idx


if __name__ == "__main__":
    df = pd.read_csv("data/fake_prices.csv").reset_index(drop=True)
    splits = list(walk_forward_splits(df))
    print("Number of splits:", len(splits))
    for train, cal, test in splits[:3]:
        print(f"Train: {df.date[train[0]]} → {df.date[train[-1]]} | "
              f"Cal: {df.date[cal[0]]} → {df.date[cal[-1]]} | "
              f"Test: {df.date[test[0]]} → {df.date[test[-1]]}")