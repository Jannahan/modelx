import os
import re
import time
import urllib.parse
import urllib.request
import ssl
from datetime import datetime
from bs4 import BeautifulSoup
import pandas as pd
from db import get_connection, init_db

BASE_URL = "https://www.harti.gov.lk/"
DAILY_PRICE_URL = "https://www.harti.gov.lk/daily-price.php"
RAW_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw", "harti")

def get_ssl_context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def parse_date_from_string(text):
    """Extract standard YYYY-MM-DD from various filename and text patterns."""
    # Pattern 1: YYYY.MM.DD or YYYY-MM-DD or YYYY_MM_DD
    m1 = re.search(r'(20\d{2})[.\-_](\d{1,2})[.\-_](\d{1,2})', text)
    if m1:
        y, m, d = int(m1.group(1)), int(m1.group(2)), int(m1.group(3))
        if 1 <= m <= 12 and 1 <= d <= 31:
            return f"{y:04d}-{m:02d}-{d:02d}"

    # Pattern 2: DD-MM-YYYY or DD.MM.YYYY
    m2 = re.search(r'(\d{1,2})[.\-_](\d{1,2})[.\-_](20\d{2})', text)
    if m2:
        d, m, y = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
        if 1 <= m <= 12 and 1 <= d <= 31:
            return f"{y:04d}-{m:02d}-{d:02d}"

    return None

def fetch_bulletin_index():
    """Scrape the HARTI daily price archive page and return list of bulletin metadata."""
    print(f"Connecting to {DAILY_PRICE_URL} to fetch PDF bulletin index...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    req = urllib.request.Request(DAILY_PRICE_URL, headers=headers)
    ctx = get_ssl_context()
    
    with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a", href=True)

    bulletins = []
    for a in links:
        href = a["href"].strip()
        if not href.lower().endswith(".pdf"):
            continue

        text = a.text.strip()
        date_str = parse_date_from_string(href) or parse_date_from_string(text)
        if not date_str:
            continue

        # Determine language (we prioritize English 'EN')
        is_english = ("/eng/" in href.lower() or 
                      href.endswith("_E.pdf") or 
                      href.endswith("_e.pdf") or 
                      "english" in text.lower() or
                      "vegetable" in href.lower() or
                      "daily_" in href.lower())

        lang = "EN" if is_english else "SI"

        # Format full URL properly encoding special characters
        clean_rel = href.lstrip("./")
        parts = clean_rel.split("/")
        encoded_parts = [urllib.parse.quote(p) for p in parts]
        full_url = BASE_URL + "/".join(encoded_parts)

        bulletins.append({
            "date": date_str,
            "source": "HARTI",
            "language": lang,
            "url": full_url,
            "raw_rel_path": href
        })

    print(f"Found {len(bulletins)} total PDF bulletin links on HARTI archive.")
    return bulletins

def sync_bulletins_to_db(bulletins):
    """Insert newly discovered bulletin records into SQLite database."""
    conn = get_connection()
    cur = conn.cursor()
    new_count = 0
    for b in bulletins:
        # Check if already exists
        cur.execute("SELECT bulletin_id FROM bulletins WHERE url = ?", (b["url"],))
        row = cur.fetchone()
        if not row:
            cur.execute("""
                INSERT INTO bulletins (date, source, language, url, download_status, parse_status)
                VALUES (?, ?, ?, ?, 'PENDING', 'PENDING')
            """, (b["date"], b["source"], b["language"], b["url"]))
            new_count += 1
    conn.commit()
    conn.close()
    print(f"Synchronized index: {new_count} new bulletins added to SQLite.")

def download_bulletin(url, dest_path, retries=3, timeout=25):
    """Download single PDF with retries and exponential backoff."""
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 1000:
        return True, os.path.getsize(dest_path), None

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    ctx = get_ssl_context()

    last_err = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
                data = resp.read()
                if len(data) < 500:
                    raise ValueError(f"Downloaded file too small ({len(data)} bytes)")
                with open(dest_path, "wb") as f:
                    f.write(data)
                return True, len(data), None
        except Exception as e:
            last_err = str(e)
            time.sleep(attempt * 1.5)

    return False, 0, last_err

def run_download_batch(year=None, limit=None, delay=0.4, english_only=True):
    """Download pending bulletins from SQLite database."""
    conn = get_connection()
    cur = conn.cursor()

    query = "SELECT bulletin_id, date, url FROM bulletins WHERE download_status != 'DOWNLOADED'"
    params = []

    if english_only:
        query += " AND language = 'EN'"
    if year:
        query += " AND date LIKE ?"
        params.append(f"{year}-%")

    query += " ORDER BY date DESC"
    if limit:
        query += f" LIMIT {limit}"

    cur.execute(query, params)
    rows = cur.fetchall()
    print(f"Found {len(rows)} pending bulletins to download (year={year}, limit={limit}).")

    downloaded = 0
    failed = 0
    for b_id, dt, url in rows:
        y = dt[:4]
        filename = f"harti_{dt.replace('-', '_')}.pdf"
        dest = os.path.join(RAW_DIR, y, filename)

        success, size, err = download_bulletin(url, dest)
        if success:
            cur.execute("""
                UPDATE bulletins 
                SET download_status = 'DOWNLOADED', local_path = ?, file_size = ?, error_message = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE bulletin_id = ?
            """, (dest, size, b_id))
            downloaded += 1
            print(f"[{downloaded}/{len(rows)}] Downloaded {dt} ({size/1024:.1f} KB)")
        else:
            cur.execute("""
                UPDATE bulletins 
                SET download_status = 'FAILED', error_message = ?, updated_at = CURRENT_TIMESTAMP
                WHERE bulletin_id = ?
            """, (err, b_id))
            failed += 1
            print(f"FAILED {dt}: {err}")

        conn.commit()
        if delay > 0:
            time.sleep(delay)

    conn.close()
    print(f"Batch download finished: {downloaded} successful, {failed} failed.")

if __name__ == "__main__":
    init_db()
    # 1. Fetch index and sync to DB
    bulletins = fetch_bulletin_index()
    sync_bulletins_to_db(bulletins)

    # 2. Download sample 2026 bulletins to test parser
    print("\nDownloading sample batch for 2026...")
    run_download_batch(year="2026", limit=10, delay=0.5)
