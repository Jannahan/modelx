import os
import re
import fitz
import pandas as pd
from db import get_connection

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
    'PELIYAGODA': ['peliyagoda', 'manning'],
    'DAMBULLA': ['dambulla', 'ddec'],
    'KANDY': ['kandy'],
    'MEEGODA': ['meegoda'],
    'KEPPETIPOLA': ['keppetipola'],
    'NUWARA_ELIYA': ['nuwaraeliya', "n'eliya", 'nuwara eliya'],
    'BANDARAWELA': ['bandarawela'],
    'THAMBUTHTHEGAMA': ['thambuththegama', 'hambuththegam'],
    'VEYANGODA': ['veyangoda'],
    'NOROCHCHOLE': ['norochchole']
}

def resolve_commodity(text):
    if not text:
        return None
    t = text.lower()
    for comm_id, aliases in COMMODITY_ALIASES.items():
        for alias in aliases:
            if alias in t:
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

    # Parse header row for markets
    market_cols = {}
    for r_idx in range(min(4, len(target_table))):
        row = target_table[r_idx]
        for c_idx, cell in enumerate(row):
            mkt = resolve_market(cell)
            if mkt and c_idx not in market_cols:
                market_cols[c_idx] = mkt

    if not market_cols:
        return records

    # Parse commodity price rows
    for row in target_table:
        if not row or not row[0]:
            continue
        first_cell = str(row[0]).strip()
        comm_id = resolve_commodity(first_cell)
        if not comm_id:
            continue

        for c_idx, mkt_id in market_cols.items():
            if c_idx >= len(row):
                continue
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

def parse_and_store_bulletin(bulletin_id, pdf_path, date_str, conn):
    """Parse one bulletin and update prices.db."""
    cur = conn.cursor()
    try:
        records = parse_harti_pdf(pdf_path, date_str)
        if not records:
            cur.execute("""
                UPDATE bulletins 
                SET parse_status = 'EMPTY', num_rows = 0, error_message = 'No vegetable table identified', updated_at = CURRENT_TIMESTAMP
                WHERE bulletin_id = ?
            """, (bulletin_id,))
            conn.commit()
            return 0

        # Insert records into wholesale_prices
        for rec in records:
            cur.execute("""
                INSERT OR REPLACE INTO wholesale_prices 
                (date, commodity_id, market_id, price_low, price_high, price_mid, is_traded, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (rec['date'], rec['commodity_id'], rec['market_id'], 
                  rec['price_low'], rec['price_high'], rec['price_mid'], 
                  rec['is_traded'], rec['source']))

        cur.execute("""
            UPDATE bulletins 
            SET parse_status = 'PARSED', num_rows = ?, error_message = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE bulletin_id = ?
        """, (len(records), bulletin_id))
        conn.commit()
        return len(records)
    except Exception as e:
        cur.execute("""
            UPDATE bulletins 
            SET parse_status = 'FAILED', error_message = ?, updated_at = CURRENT_TIMESTAMP
            WHERE bulletin_id = ?
        """, (str(e), bulletin_id))
        conn.commit()
        return 0

def run_parser_batch(limit=None):
    """Parse all downloaded bulletins that are pending parsing."""
    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT bulletin_id, local_path, date 
        FROM bulletins 
        WHERE download_status = 'DOWNLOADED' AND parse_status != 'PARSED'
        ORDER BY date DESC
    """
    if limit:
        query += f" LIMIT {limit}"

    cur.execute(query)
    rows = cur.fetchall()
    print(f"Found {len(rows)} downloaded bulletins pending parsing.")

    total_records = 0
    parsed_files = 0
    for b_id, path, dt in rows:
        if not os.path.exists(path):
            continue
        n = parse_and_store_bulletin(b_id, path, dt, conn)
        total_records += n
        parsed_files += 1
        print(f"Parsed {dt}: {n} price observations stored.")

    conn.close()
    print(f"\nBatch parsing complete: {parsed_files} files parsed, {total_records} price rows stored.")

if __name__ == "__main__":
    run_parser_batch()
