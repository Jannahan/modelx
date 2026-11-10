import os
import re
import fitz
import pandas as pd
from db import get_connection

# Row labels that contain a commodity keyword but are a DIFFERENT product.
# e.g. "Long Beans" and "Dambala (Wing Beans)" must never be read as BEANS.
COMMODITY_EXCLUDES = {
    'BEANS': ['long', 'wing', 'dambala', 'soya'],
}

COMMODITY_ALIASES = {
    'BEANS': ['bean', 'bochi'],
    'CARROT': ['carrot'],
    'TOMATO': ['tomato'],
    'LEEKS': ['leek'],
    'CABBAGE': ['cabbage'],
    'BEET_ROOT': ['beet'],
    'KNOLKHOL': ['knol'],
    'RADDISH': ['radish', 'raddish'],
    'GREEN_CHILLI': ['green chill', 'green chili'],
    'BIG_ONION': ['big onion', 'b.onion', 'b-onion'],
    'POTATO': ['potato'],
    'BRINJAL': ['brinjal'],
    'PUMPKIN': ['pumpkin'],
    'SNAKE_GOURD': ['snake gourd'],
    'BITTER_GOURD': ['bitter gourd']
}

MARKET_ALIASES = {
    # Pre-2021 bulletins list the Colombo terminal as "Pettah Market"; after the
    # Manning Market moved it is listed as "Peliyagoda Market".
    'PELIYAGODA': ['peliyagoda', 'manning'],
    'PETTAH': ['pettah', 'petha'],   # "Petha Market" typo seen in Aug 2021
    'DAMBULLA': ['dambulla', 'ddec'],
    'KANDY': ['kandy'],
    'MEEGODA': ['meegoda', 'megoda'],
    'KEPPETIPOLA': ['petipola'],          # "Keppetipola", "Kappetipola", "mKappetipola"
    'NUWARA_ELIYA': ['nuwaraeliya', "n'eliya", 'nuwara eliya'],
    'BANDARAWELA': ['bandarawela'],
    'THAMBUTHTHEGAMA': ['mbuththeg'],     # "Thambuththegama", "hambuththegam", "ambuththega"
    'VEYANGODA': ['veyangod'],
    'NOROCHCHOLE': ['norochchole']
}

def resolve_commodity(text):
    if not text:
        return None
    t = str(text).lower()
    for comm_id, aliases in COMMODITY_ALIASES.items():
        for alias in aliases:
            if alias in t:
                if any(x in t for x in COMMODITY_EXCLUDES.get(comm_id, [])):
                    return None
                return comm_id
    return None

def resolve_market(text):
    if not text:
        return None
    t = text.lower()
    for mkt_id, aliases in MARKET_ALIASES.items():
        for alias in aliases:
            if alias in t:
                return mkt_id
    return None

def parse_price_range(cell_text):
    """
    Parse price range e.g. '500 - 600' -> (500.0, 600.0, 550.0, True).
    If dash or empty -> (None, None, None, False).
    """
    if not cell_text:
        return None, None, None, False

    clean = cell_text.strip()
    if clean in ['-', '--', 'N/A', 'n/a', 'N.A.', '', '.']:
        return None, None, None, False

    nums = re.findall(r'[\d\.]+', clean)
    valid_nums = []
    for n in nums:
        try:
            val = float(n)
            # Basic sanity filter for rupee vegetable price per kg
            if 5.0 <= val <= 8000.0:
                valid_nums.append(val)
        except ValueError:
            continue

    if len(valid_nums) >= 2:
        lo, hi = min(valid_nums[0], valid_nums[1]), max(valid_nums[0], valid_nums[1])
        mid = (lo + hi) / 2.0
        return lo, hi, mid, True
    elif len(valid_nums) == 1:
        val = valid_nums[0]
        return val, val, val, True

    return None, None, None, False

def parse_harti_pdf(pdf_path, date_str):
    """
    Extract wholesale vegetable price tables from a HARTI daily bulletin.
    Returns list of dicts: [{date, commodity_id, market_id, low, high, mid, traded}]
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(pdf_path)
    records = []

    # Search for the wholesale table across pages (typically Page 2 or 1)
    target_table = None
    for pno in range(min(4, len(doc))):
        page = doc[pno]
        tab_finder = page.find_tables()
        for tab in tab_finder:
            data = tab.extract()
            if not data or len(data) < 10:
                continue
            # Look for keywords in rows
            flat_text = " ".join([str(c) for r in data[:5] for c in r if c]).lower()
            if 'peliyagoda' in flat_text or 'dambulla' in flat_text or 'beans' in flat_text:
                target_table = data
                break
        if target_table:
            break

    if not target_table:
        return records

    # Which column holds the item name? Layout A: column 0.
    # Layout B (some 2022 bulletins): column 0 is a row number, column 1 the item.
    name_col = 0
    for row in target_table[:8]:
        if len(row) > 1 and resolve_commodity(row[1]) and not resolve_commodity(row[0]):
            name_col = 1
            break

    # Header rows = everything before the first commodity row
    header_end = len(target_table)
    for r_idx, row in enumerate(target_table):
        if row and len(row) > name_col and resolve_commodity(row[name_col]):
            header_end = r_idx
            break
    header_rows = target_table[:min(header_end, 6)]

    market_cols = {}
    for row in header_rows:
        for c_idx, cell in enumerate(row):
            if c_idx <= name_col:
                continue
            mkt = resolve_market(cell)
            if mkt and c_idx not in market_cols and mkt not in market_cols.values():
                market_cols[c_idx] = mkt

    if not market_cols:
        return records

    # Layout B splits each market into separate "Min" and "Max" columns.
    minmax = any(
        any(str(c or '').strip().lower() == 'min' for c in row) for row in header_rows
    )

    # Parse commodity price rows. Only the FIRST row per commodity is kept:
    # it is the main variety (e.g. "Cabbage (N'Eliya)" before "Cabbage (Kandy)").
    seen = set()
    for row in target_table[header_end:]:
        if not row or len(row) <= name_col or not row[name_col]:
            continue
        comm_id = resolve_commodity(str(row[name_col]).strip())
        if not comm_id or comm_id in seen:
            continue
        seen.add(comm_id)

        for c_idx, mkt_id in market_cols.items():
            if c_idx >= len(row):
                continue
            if minmax:
                lo_txt = str(row[c_idx] or '').strip()
                hi_txt = str(row[c_idx + 1] or '').strip() if c_idx + 1 < len(row) else ''
                cell_val = f"{lo_txt} - {hi_txt}" if lo_txt and hi_txt else (lo_txt or hi_txt)
            else:
                cell_val = row[c_idx]
            lo, hi, mid, traded = parse_price_range(cell_val)
            records.append({
                'date': date_str,
                'commodity_id': comm_id,
                'market_id': mkt_id,
                'price_low': lo,
                'price_high': hi,
                'price_mid': mid,
                'is_traded': 1 if traded else 0,
                'source': 'HARTI'
            })

    return records

def store_bulletin_records(bulletin_id, date_str, records, conn, error=None):
    """Write one bulletin's parsed rows (or its failure) to prices.db."""
    cur = conn.cursor()
    if error is not None:
        cur.execute("""
            UPDATE bulletins
            SET parse_status = 'FAILED', error_message = ?, updated_at = CURRENT_TIMESTAMP
            WHERE bulletin_id = ?
        """, (error, bulletin_id))
        conn.commit()
        return 0
    if not records:
        cur.execute("""
            UPDATE bulletins
            SET parse_status = 'EMPTY', num_rows = 0, error_message = 'No vegetable table identified', updated_at = CURRENT_TIMESTAMP
            WHERE bulletin_id = ?
        """, (bulletin_id,))
        conn.commit()
        return 0

    # Replace any rows from an earlier parse of this date
    cur.execute("DELETE FROM wholesale_prices WHERE date = ? AND source = 'HARTI'", (date_str,))
    cur.executemany("""
        INSERT OR REPLACE INTO wholesale_prices
        (date, commodity_id, market_id, price_low, price_high, price_mid, is_traded, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, [(r['date'], r['commodity_id'], r['market_id'], r['price_low'], r['price_high'],
           r['price_mid'], r['is_traded'], r['source']) for r in records])
    cur.execute("""
        UPDATE bulletins
        SET parse_status = 'PARSED', num_rows = ?, error_message = NULL, updated_at = CURRENT_TIMESTAMP
        WHERE bulletin_id = ?
    """, (len(records), bulletin_id))
    conn.commit()
    return len(records)


def _parse_job(job):
    """Worker-process entry point: parse one PDF, never raise."""
    b_id, path, dt = job
    try:
        return b_id, dt, parse_harti_pdf(path, dt), None
    except Exception as e:
        return b_id, dt, [], f"{type(e).__name__}: {e}"


def parse_and_store_bulletin(bulletin_id, pdf_path, date_str, conn):
    """Parse one bulletin and update prices.db."""
    _, _, records, err = _parse_job((bulletin_id, pdf_path, date_str))
    return store_bulletin_records(bulletin_id, date_str, records, conn, err)


def run_parser_batch(limit=None, workers=1, reparse=False):
    """Parse downloaded bulletins. reparse=True also redoes ones already PARSED."""
    conn = get_connection()
    cur = conn.cursor()

    query = "SELECT bulletin_id, local_path, date FROM bulletins WHERE download_status = 'DOWNLOADED'"
    if not reparse:
        query += " AND parse_status != 'PARSED'"
    query += " ORDER BY date DESC"
    if limit:
        query += f" LIMIT {int(limit)}"

    rows = [r for r in cur.execute(query).fetchall() if r[1] and os.path.exists(r[1])]
    print(f"Found {len(rows)} downloaded bulletins to parse (workers={workers}).")

    total_records = 0
    if workers > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = pool.map(_parse_job, rows, chunksize=4)
            for k, (b_id, dt, records, err) in enumerate(results, 1):
                total_records += store_bulletin_records(b_id, dt, records, conn, err)
                if k % 100 == 0 or err:
                    print(f"[{k}/{len(rows)}] {dt}: {len(records)} rows" + (f" FAILED {err}" if err else ""), flush=True)
    else:
        for b_id, path, dt in rows:
            n = parse_and_store_bulletin(b_id, path, dt, conn)
            total_records += n
            print(f"Parsed {dt}: {n} price observations stored.")

    conn.close()
    print(f"\nBatch parsing complete: {len(rows)} files processed, {total_records} price rows stored.")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Parse downloaded HARTI bulletins into prices.db")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--reparse", action="store_true", help="also re-parse bulletins already PARSED")
    a = ap.parse_args()
    run_parser_batch(limit=a.limit, workers=a.workers, reparse=a.reparse)
