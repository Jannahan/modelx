"""
CBSL Daily Price Report scraper (second price source in the proposal, Table 2).

    python src/cbsl_scraper.py                 # index every listing page, download all reports
    python src/cbsl_scraper.py --pages 2       # daily mode: only the newest listing pages

Listing:  https://www.cbsl.gov.lk/en/statistics/economic-indicators/price-report?page=N
Reports:  .../statistics/pricerpt/price_report_YYYYMMDD_e.pdf  (stored in data/raw/cbsl/YYYY/)
Status is tracked in the same `bulletins` table as HARTI, with source = 'CBSL'.
"""
import argparse, os, re, sys, time, urllib.request
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from db import get_connection, init_db
from harti_scraper import download_bulletin, get_ssl_context

BASE = "https://www.cbsl.gov.lk"
LISTING = BASE + "/en/statistics/economic-indicators/price-report?page={}"
RAW_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw", "cbsl")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
LINK_RE = re.compile(r'href="([^"]*/statistics/pricerpt/[^"]+\.pdf)"', re.I)


def fetch(url, retries=4, timeout=40):
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, context=get_ssl_context(), timeout=timeout) as r:
                return r.read().decode("utf-8", errors="ignore")
        except Exception:
            time.sleep(2 * attempt)
    return ""


def report_date(url):
    m = re.search(r"(20\d{2})(\d{2})(\d{2})", url)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def last_page():
    html = fetch(LISTING.format(0))
    pages = [int(p) for p in re.findall(r"price-report\?page=(\d+)", html)]
    return max(pages) if pages else 0


def index_listing(max_pages=None, delay=0.5):
    """Collect English report links from the listing pages into the bulletins table."""
    n_pages = (max_pages - 1) if max_pages else last_page()
    conn = get_connection()
    cur = conn.cursor()
    found = new = 0
    for page in range(0, n_pages + 1):
        html = ""
        for _ in range(3):                      # some pages come back empty: retry
            html = fetch(LISTING.format(page))
            if LINK_RE.search(html):
                break
            time.sleep(3)
        links = sorted(set(LINK_RE.findall(html)))
        for href in links:
            if "_s.pdf" in href.lower() or "_t.pdf" in href.lower():
                continue                        # Sinhala / Tamil editions
            url = href if href.startswith("http") else BASE + href
            dt = report_date(url)
            if not dt:
                continue
            found += 1
            cur.execute("SELECT 1 FROM bulletins WHERE url = ?", (url,))
            if not cur.fetchone():
                cur.execute("""INSERT INTO bulletins (date, source, language, url, download_status, parse_status)
                               VALUES (?, 'CBSL', 'EN', ?, 'PENDING', 'PENDING')""", (dt, url))
                new += 1
        conn.commit()
        print(f"page {page}/{n_pages}: {len(links)} links", flush=True)
        time.sleep(delay)
    conn.close()
    print(f"Indexed {found} CBSL report links ({new} new).")


def download_pending(limit=None, delay=0.4):
    conn = get_connection()
    cur = conn.cursor()
    q = """SELECT bulletin_id, date, url FROM bulletins
           WHERE source = 'CBSL' AND download_status != 'DOWNLOADED'
             AND (error_message IS NULL OR error_message NOT LIKE '%404%')
           ORDER BY date DESC"""
    rows = cur.execute(q + (f" LIMIT {int(limit)}" if limit else "")).fetchall()
    print(f"{len(rows)} CBSL reports to download.")
    ok = bad = 0
    for b_id, dt, url in rows:
        dest = os.path.join(RAW_DIR, dt[:4], f"cbsl_{dt.replace('-', '_')}.pdf")
        success, size, err = download_bulletin(url, dest)
        if success:
            cur.execute("""UPDATE bulletins SET download_status='DOWNLOADED', local_path=?, file_size=?,
                           error_message=NULL, updated_at=CURRENT_TIMESTAMP WHERE bulletin_id=?""", (dest, size, b_id))
            ok += 1
        else:
            cur.execute("""UPDATE bulletins SET download_status='FAILED', error_message=?,
                           updated_at=CURRENT_TIMESTAMP WHERE bulletin_id=?""", (err, b_id))
            bad += 1
            print(f"FAILED {dt}: {err}", flush=True)
        conn.commit()
        if (ok + bad) % 100 == 0:
            print(f"[{ok + bad}/{len(rows)}] {ok} ok, {bad} failed", flush=True)
        time.sleep(delay)
    conn.close()
    print(f"CBSL download finished: {ok} ok, {bad} failed.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=None, help="only index the newest N listing pages")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    init_db()
    index_listing(max_pages=a.pages)
    download_pending(limit=a.limit)
