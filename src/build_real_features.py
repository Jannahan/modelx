import os
import sys
import sqlite3
import numpy as np
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from db import DB_PATH

# The HARTI bulletin's Colombo terminal column is headed "Pettah Market" up to 2021
# and "Peliyagoda Market" afterwards (labels alternate during 2021). "COLOMBO" joins
# them: Peliyagoda when that day lists it, otherwise Pettah.
COLOMBO = ("PELIYAGODA", "PETTAH")


def build_corridor_dataset(commodity="BEANS", origin="DAMBULLA", destination="COLOMBO", db_path=DB_PATH):
    """
    Extract wholesale prices for origin (e.g. Dambulla) and destination (Colombo terminal),
    align them chronologically, and generate modeling features with no future look-ahead.
    """
    dest_markets = COLOMBO if destination == "COLOMBO" else (destination,)
    markets = (origin,) + dest_markets
    conn = sqlite3.connect(db_path)

    query = f"""
        SELECT date, market_id, price_mid
        FROM wholesale_prices
        WHERE commodity_id = ? AND market_id IN ({",".join("?" * len(markets))}) AND is_traded = 1
        ORDER BY date ASC
    """
    df = pd.read_sql_query(query, conn, params=(commodity,) + markets)
    conn.close()

    if df.empty:
        print(f"No price observations found for {commodity} in {origin} -> {destination}.")
        return pd.DataFrame()

    pivoted = df.pivot(index="date", columns="market_id", values="price_mid").reset_index()
    pivoted.columns.name = None
    present = [m for m in dest_markets if m in pivoted.columns]

    if origin not in pivoted.columns or not present:
        print(f"Missing one of the markets in data. Columns found: {pivoted.columns.tolist()}")
        return pd.DataFrame()

    retail, source = pd.Series(np.nan, index=pivoted.index), pd.Series(None, index=pivoted.index, dtype=object)
    for m in present:                                  # first listed market wins
        take = retail.isna() & pivoted[m].notna()
        retail[take], source[take] = pivoted.loc[take, m], m
    pivoted = pivoted[["date", origin]].rename(columns={origin: "wholesale"})
    pivoted["retail"], pivoted["retail_market"] = retail, source
    pivoted["date"] = pd.to_datetime(pivoted["date"])
    pivoted = pivoted.sort_values("date").dropna(subset=["wholesale", "retail"]).reset_index(drop=True)

    # Build features known at 06:00 AM on day t
    # Trader buys at wholesale[t], retail is known up to retail[t-1]
    w, r = pivoted["wholesale"], pivoted["retail"]
    
    pivoted["lag_w1"] = w.shift(1)
    pivoted["lag_r1"] = r.shift(1)
    pivoted["lag_r7"] = r.shift(7)
    
    pivoted["spread_t"] = r.shift(1) - w
    pivoted["spread_ratio"] = r.shift(1) / w
    pivoted["roll_vol_7d"] = np.log(r).diff().rolling(7).std().shift(1)
    
    # Target: tomorrow's destination price (P^r_{t+1})
    pivoted["target"] = r.shift(-1)
    pivoted["target_ratio"] = pivoted["target"] / w
    pivoted["m_bar"] = (r.shift(1) - w.shift(1)).rolling(30, min_periods=5).mean()

    return pivoted

def export_all_commodities(commodities=('BEANS', 'CARROT', 'TOMATO', 'LEEKS'), output_dir="data"):
    os.makedirs(output_dir, exist_ok=True)
    summary = []
    for c in commodities:
        df = build_corridor_dataset(commodity=c)
        if not df.empty:
            out_csv = os.path.join(output_dir, f"real_{c.lower()}_dambulla_colombo.csv")
            df.to_csv(out_csv, index=False)
            summary.append({"commodity": c, "rows": len(df), "path": out_csv})
            print(f"Exported {c}: {len(df)} days to {out_csv}")
    return pd.DataFrame(summary)

if __name__ == "__main__":
    export_all_commodities()
