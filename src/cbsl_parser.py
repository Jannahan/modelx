"""
CBSL Daily Price Report parser.

    python src/cbsl_parser.py --workers 8

From each report it extracts
  1. today's wholesale and retail prices for our crops at Pettah, Dambulla and Narahenpita
     -> retail_prices table (source='CBSL') and data/history/cbsl_prices.csv
  2. the one-line supply reasons ("Price of Beans declined ... due to favourable supply
     from Welimada ...") -> data/history/cbsl_events.csv

The price table's column order changed over the years (2016 groups by market, 2019+ groups
by wholesale/retail, 2022+ adds Narahenpita), so numbers are matched to their headers by
x-position on the page, never by a fixed order.
"""
import argparse, os, re, sys
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRICES_CSV = os.path.join(ROOT, "data", "history", "cbsl_prices.csv")
EVENTS_CSV = os.path.join(ROOT, "data", "history", "cbsl_events.csv")

ITEMS = {"BEANS": ["beans"], "CARROT": ["carrot"], "TOMATO": ["tomato"], "LEEKS": ["leeks", "leek"],
         "GREEN_CHILLI": ["green chilli", "green chillies", "green chili"], "CABBAGE": ["cabbage"]}
MARKETS = {"pettah": "PETTAH", "dambulla": "DAMBULLA", "narahenpita": "NARAHENPITA"}
NUM = re.compile(r"^\d{1,3}(,\d{3})*(\.\d+)?$|^\d+(\.\d+)?$")
REASON = re.compile(r"((?:Wholesale |Retail )?[Pp]rices? of ([A-Z][A-Za-z ()\-]+?) (increased|declined|decreased|rose|dropped|fell|reduced)"
                    r"[^.]*?due to [^.]+\.)")


def _item(label):
    t = label.lower()
    for k, names in ITEMS.items():
        if any(t.startswith(n) for n in names):
            return k
    return None


def _is_cell(text):
    return bool(NUM.match(text)) or text.lower() in ("n.a.", "n.a", "-")


def parse_table(page, date):
    words = page.get_text("words")                       # x0, y0, x1, y1, text, ...
    # Data rows: a crop name on the left followed by at least four numbers on the same line.
    rows = []
    for w in words:
        if w[0] > 140 or not w[4][:1].isalpha():
            continue
        line = sorted([v for v in words if abs(v[1] - w[1]) < 3], key=lambda v: v[0])
        cells = [v for v in line if v[0] > w[2] and _is_cell(v[4])]
        label = " ".join(v[4] for v in line if v[2] <= (cells[0][0] if cells else 1e9) and not _is_cell(v[4]))
        if len(cells) >= 4 and _item(label.replace("Rs./Kg", "").replace("Rs./kg", "")):
            rows.append((w[1], label, cells))
    if not rows:
        return []
    first_y = min(r[0] for r in rows)
    head = [w for w in words if first_y - 120 < w[1] < first_y and (w[0] + w[2]) / 2 > 120]

    def nearest_line(keys):
        hits = [w for w in head if w[4].lower() in keys]
        if not hits:
            return []
        y = max(w[1] for w in hits)                      # the header line closest above the table
        return [((w[0] + w[2]) / 2, w[4].lower()) for w in hits if w[1] > y - 15]
    mk = [(x, MARKETS[k]) for x, k in nearest_line(MARKETS)]
    wr = nearest_line(("wholesale", "retail"))
    if not mk or not wr:
        return []
    out, seen_rows = [], set()
    for y, label, cells in sorted(rows):
        crop = _item(label)
        if round(y) in seen_rows:
            continue
        seen_rows.add(round(y))
        for k in range(0, len(cells) - 1, 2):             # (previous, today) pairs
            prev, today = cells[k], cells[k + 1]
            cx = (prev[0] + today[2]) / 2
            market = min(mk, key=lambda m: abs(m[0] - cx))[1]
            kind = "retail" if market == "NARAHENPITA" else min(wr, key=lambda m: abs(m[0] - cx))[1]
            val = today[4].replace(",", "")
            price = float(val) if NUM.match(today[4]) else None
            out.append({"date": date, "commodity": crop, "market": market, "type": kind, "price": price})
    return out


def parse_events(doc, date):
    text = " ".join(doc[i].get_text() for i in range(min(2, len(doc))))
    text = re.sub(r"\s+", " ", text)
    out = []
    for sent, item, direction in [(m.group(1), m.group(2), m.group(3)) for m in REASON.finditer(text)]:
        crop = _item(item.strip())
        if crop:
            up = direction in ("increased", "rose")
            out.append({"date": date, "commodity": crop, "direction": "up" if up else "down",
                        "text": sent.strip()})
    return out


def parse_report(job):
    b_id, path, date = job
    import fitz
    try:
        doc = fitz.open(path)
        prices = []
        for p in doc:
            prices = parse_table(p, date)
            if prices:
                break
        # one row per (commodity, market, type); keep the first (main variety)
        seen, uniq = set(), []
        for r in prices:
            key = (r["commodity"], r["market"], r["type"])
            if key not in seen:
                seen.add(key); uniq.append(r)
        return b_id, date, uniq, parse_events(doc, date), None
    except Exception as e:
        return b_id, date, [], [], f"{type(e).__name__}: {e}"


def run(workers=8):
    from db import get_connection
    conn = get_connection()
    cur = conn.cursor()
    jobs = [r for r in cur.execute("""SELECT bulletin_id, local_path, date FROM bulletins
                                      WHERE source='CBSL' AND download_status='DOWNLOADED'""").fetchall()
            if r[1] and os.path.exists(r[1])]
    print(f"Parsing {len(jobs)} CBSL reports with {workers} workers")
    from concurrent.futures import ProcessPoolExecutor
    prices, events = [], []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for k, (b_id, date, p, e, err) in enumerate(pool.map(parse_report, jobs, chunksize=8), 1):
            status = "FAILED" if err else ("PARSED" if p else "EMPTY")
            cur.execute("UPDATE bulletins SET parse_status=?, num_rows=?, error_message=? WHERE bulletin_id=?",
                        (status, len(p), err, b_id))
            cur.execute("DELETE FROM retail_prices WHERE date=? AND source='CBSL'", (date,))
            for r in p:
                if r["type"] == "retail":
                    cur.execute("""INSERT OR REPLACE INTO retail_prices (date, commodity_id, market_id, price_mid,
                                   is_traded, source) VALUES (?,?,?,?,?, 'CBSL')""",
                                (r["date"], r["commodity"], r["market"], r["price"], int(r["price"] is not None)))
            prices += p; events += e
            if k % 250 == 0:
                conn.commit(); print(f"[{k}/{len(jobs)}]", flush=True)
    conn.commit(); conn.close()
    save(pd.DataFrame(prices), pd.DataFrame(events))


def save(prices, events):
    os.makedirs(os.path.dirname(PRICES_CSV), exist_ok=True)
    for df, path, key in ((prices, PRICES_CSV, ["date", "commodity", "market", "type"]),
                          (events, EVENTS_CSV, ["date", "commodity", "text"])):
        if df.empty:
            continue
        if os.path.exists(path):
            df = pd.concat([pd.read_csv(path, dtype={"date": str}), df])
        df.drop_duplicates(key, keep="last").sort_values(key).to_csv(path, index=False)
    p = pd.read_csv(PRICES_CSV) if os.path.exists(PRICES_CSV) else pd.DataFrame()
    e = pd.read_csv(EVENTS_CSV) if os.path.exists(EVENTS_CSV) else pd.DataFrame()
    if len(p):
        print(f"CBSL prices: {len(p):,} rows, {p.date.nunique():,} days ({p.date.min()} -> {p.date.max()})")
        print(p.groupby(["market", "type"]).price.count())
    if len(e):
        print(f"CBSL supply reasons: {len(e):,} sentences for our crops")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    run(ap.parse_args().workers)
