"""
Committed price history: data/history/harti_corridor.csv  (tracked in git, ~2 MB)

One row per (date, commodity): Dambulla wholesale and Colombo terminal wholesale
(Peliyagoda when listed that day, otherwise Pettah). This is the single input the model,
the daily GitHub Actions run and the web app share, so none of them needs prices.db.

    python src/history.py        # rebuild the CSV from prices.db (after a local parse)
"""
import os, sqlite3, sys
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_CSV = os.path.join(ROOT, "data", "history", "harti_corridor.csv")
CROPS = ("BEANS", "CARROT", "TOMATO", "LEEKS", "GREEN_CHILLI")
ORIGIN, COLOMBO = "DAMBULLA", ("PELIYAGODA", "PETTAH")      # first listed Colombo market wins
COLS = ["date", "commodity", "wholesale", "wholesale_low", "wholesale_high",
        "retail", "retail_low", "retail_high", "retail_market"]


def corridor_rows(records):
    """Turn parsed wholesale_prices rows (dicts or a DataFrame) into corridor rows."""
    p = pd.DataFrame(records)
    p = p[(p.is_traded == 1) & p.commodity_id.isin(CROPS) & p.market_id.isin((ORIGIN,) + COLOMBO)]
    out = []
    for (dt, crop), g in p.groupby(["date", "commodity_id"]):
        by = {r.market_id: r for r in g.itertuples()}
        dest = next((m for m in COLOMBO if m in by), None)
        if ORIGIN not in by or dest is None:
            continue
        w, r = by[ORIGIN], by[dest]
        out.append([dt, crop, w.price_mid, w.price_low, w.price_high, r.price_mid, r.price_low, r.price_high, dest])
    return pd.DataFrame(out, columns=COLS)


def export_from_db():
    from db import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    p = pd.read_sql_query("SELECT * FROM wholesale_prices WHERE source = 'HARTI'", conn)
    conn.close()
    df = corridor_rows(p).sort_values(["commodity", "date"])
    os.makedirs(os.path.dirname(HISTORY_CSV), exist_ok=True)
    df.to_csv(HISTORY_CSV, index=False)
    print(f"Wrote {len(df):,} rows to {HISTORY_CSV}")
    print(df.groupby("commodity").date.agg(["count", "min", "max"]))
    return df


def append(new_rows):
    """Add corridor rows for new bulletin dates (daily run). Returns the number of new rows."""
    old = load_all()
    df = pd.concat([old, new_rows]).drop_duplicates(["date", "commodity"], keep="last")
    df.sort_values(["commodity", "date"]).to_csv(HISTORY_CSV, index=False)
    return len(df) - len(old)


def load_all():
    return pd.read_csv(HISTORY_CSV, dtype={"date": str})


def load_corridor(commodity):
    df = load_all()
    df = df[df.commodity == commodity].copy()
    df["date"] = pd.to_datetime(df.date)
    return df.sort_values("date").reset_index(drop=True)


if __name__ == "__main__":
    export_from_db()
