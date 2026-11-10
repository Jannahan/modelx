"""
Open-Meteo daily weather for the growing areas that supply the Dambulla -> Colombo route.

    python src/weather.py            # full history 2015-06 .. today (archive API + recent days)
    python src/weather.py --recent   # daily mode: last 14 days only

Writes data/history/weather_daily.csv (tracked in git, small) and the weather_daily table.
Stations follow the Dataset Gathering Guide (Section 3.3).
"""
import argparse, json, os, sys, time, urllib.parse, urllib.request
from datetime import date, timedelta
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, "data", "history", "weather_daily.csv")

STATIONS = {   # station_id: (name, lat, lon, crops it represents)
    "NUWARA_ELIYA": ("Nuwara Eliya", 6.9497, 80.7891, "Carrot, Leeks, Cabbage"),
    "WELIMADA":     ("Welimada", 6.9033, 80.9167, "Beans, Tomato"),
    "DAMBULLA":     ("Dambulla", 7.8742, 80.6511, "Hub logistics, low-country vegetables"),
    "BANDARAWELA":  ("Bandarawela", 6.8259, 80.9982, "Beans, Tomato, Cabbage"),
}
DAILY = "precipitation_sum,temperature_2m_max,temperature_2m_min"
ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
FORECAST = "https://api.open-meteo.com/v1/forecast"


def _get(url, params, retries=4):
    full = url + "?" + urllib.parse.urlencode(params)
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(full, headers={"User-Agent": "modelx-weather"}),
                                        timeout=60) as r:
                return json.loads(r.read())
        except Exception as e:
            if attempt == retries:
                raise
            time.sleep(3 * attempt)


def _frame(payload, station_id):
    d = payload["daily"]
    return pd.DataFrame({"date": d["time"], "station_id": station_id,
                         "rain_mm": d["precipitation_sum"],
                         "temp_max": d["temperature_2m_max"], "temp_min": d["temperature_2m_min"]})


def fetch(start, end, recent_days=14):
    frames = []
    for sid, (_, lat, lon, _) in STATIONS.items():
        common = {"latitude": lat, "longitude": lon, "daily": DAILY, "timezone": "Asia/Colombo"}
        if start:
            # The archive lags a few days behind; the forecast API's past_days covers the rest.
            frames.append(_frame(_get(ARCHIVE, {**common, "start_date": start, "end_date": end}), sid))
        frames.append(_frame(_get(FORECAST, {**common, "past_days": recent_days, "forecast_days": 1}), sid))
        time.sleep(0.5)
    df = pd.concat(frames).dropna(subset=["rain_mm"])
    # forecast-API rows come last, so keep the archive value when both exist
    return df.drop_duplicates(["date", "station_id"], keep="first").sort_values(["date", "station_id"])


def save(df):
    os.makedirs(os.path.dirname(CSV), exist_ok=True)
    if os.path.exists(CSV):
        old = pd.read_csv(CSV, dtype={"date": str})
        df = pd.concat([old, df]).drop_duplicates(["date", "station_id"], keep="first")
    df = df.sort_values(["date", "station_id"])
    df.to_csv(CSV, index=False)
    try:                                         # mirror into prices.db when it exists (local runs)
        from db import get_connection, DB_PATH
        if os.path.exists(DB_PATH):
            conn = get_connection()
            conn.execute("""CREATE TABLE IF NOT EXISTS weather_daily (date TEXT, station_id TEXT, rain_mm REAL,
                            temp_max REAL, temp_min REAL, PRIMARY KEY (date, station_id))""")
            conn.executemany("INSERT OR REPLACE INTO weather_daily VALUES (?,?,?,?,?)",
                             df[["date", "station_id", "rain_mm", "temp_max", "temp_min"]].itertuples(index=False))
            conn.commit(); conn.close()
    except Exception as e:
        print("prices.db mirror skipped:", e)
    return df


def rain_features(dates):
    """Rainfall known by 06:00 on each date: totals over the previous 3, 7 and 14 days
    (ending YESTERDAY), averaged over the up-country stations that grow the crops."""
    w = pd.read_csv(CSV, parse_dates=["date"])
    upc = w[w.station_id.isin(["NUWARA_ELIYA", "WELIMADA", "BANDARAWELA"])]
    daily = upc.groupby("date").rain_mm.mean().asfreq("D")
    out = pd.DataFrame(index=daily.index)
    for k in (3, 7, 14):
        out[f"rain_{k}d"] = daily.rolling(k, min_periods=k).sum().shift(1)   # ends yesterday
    return out.reindex(pd.to_datetime(dates)).reset_index(drop=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--recent", action="store_true")
    a = ap.parse_args()
    end = (date.today() - timedelta(days=2)).isoformat()
    df = fetch(None if a.recent else "2015-06-01", end)
    out = save(df)
    print(f"weather rows: {len(out):,}  {out.date.min()} -> {out.date.max()}  stations: {out.station_id.nunique()}")
