#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRC Carbon Market Data Incremental Sync Script
- Fetch the latest date from CRC website
- Compare with local CSV; download and append if website is newer
- Output saved in the same directory as this script
"""
import os, time, requests, csv
from bs4 import BeautifulSoup

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE   = os.path.join(SCRIPT_DIR, "CRC_Carbon_Market_v7.csv")
HEADERS    = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
BASE_URL   = "https://www.chinacrc.net.cn/list/101.html"

def fetch_page(page):
    url = f"{BASE_URL}?page={page}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.encoding = 'utf-8'
    return r.text

def clean_num(s):
    if not s or s.strip() in ('-', '—', ''):
        return 0.0
    return float(s.strip().replace(',', ''))

def parse_page(html):
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table')
    if not table:
        return []
    records = []
    for row in table.find_all('tr'):
        cols = row.find_all('td')
        if len(cols) != 11:
            continue
        try:
            records.append({
                'Date': cols[1].get_text(strip=True).replace('.', '-'),
                'Variety': cols[0].get_text(strip=True),
                'Close': clean_num(cols[2].get_text(strip=True)),
                'High': clean_num(cols[3].get_text(strip=True)),
                'Low': clean_num(cols[4].get_text(strip=True)),
                'ListedVol': clean_num(cols[5].get_text(strip=True)),
                'ListedAmt': clean_num(cols[6].get_text(strip=True)),
                'BlockVol': clean_num(cols[7].get_text(strip=True)),
                'BlockAmt': clean_num(cols[8].get_text(strip=True)),
                'TotalVol': clean_num(cols[9].get_text(strip=True)),
                'TotalAmt': clean_num(cols[10].get_text(strip=True)),
            })
        except:
            continue
    return records

def norm_date(s):
    """Normalize date to YYYY-MM-DD for comparison"""
    s = s.strip()
    if not s:
        return '0000-00-00'
    parts = s.split('-')
    return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"

def get_site_latest_date():
    """Fetch the latest data date from website (page 1, first row)"""
    recs = parse_page(fetch_page(1))
    if not recs:
        return None
    return max(r['Date'] for r in recs)

def get_csv_latest_date():
    """Fetch the latest data date from local CSV"""
    if not os.path.exists(CSV_FILE):
        return None
    with open(CSV_FILE, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = [row for row in reader if row.get('Date', '').strip()]
    if not rows:
        return None
    return max(norm_date(r['Date']) for r in rows)

def download_new_since(cutoff_date):
    """
    Download all records from website.
    Returns records newer than cutoff_date (and >= 2026-01-01).
    """
    all_records = []
    for page in range(1, 117):
        recs = parse_page(fetch_page(page))
        if not recs:
            break
        oldest = min(r['Date'] for r in recs)
        print(f"  Page {page}: {len(recs)} records (oldest: {oldest})")
        all_records.extend(recs)
        if oldest < '2026-01-01' and page > 1:
            break
        time.sleep(0.3)

    new_recs = [r for r in all_records
                if r['TotalVol'] > 0
                and norm_date(r['Date']) > norm_date(cutoff_date)
                and r['Date'] >= '2026-01-01']
    return new_recs

def wide_to_stacked(records):
    """Convert wide format to stacked format (one row per trade type)"""
    stacked = []
    base_keys = ['Date', 'Variety', 'Close', 'High', 'Low']
    for r in records:
        base = {k: r[k] for k in base_keys}
        if r['ListedVol'] > 0:
            stacked.append({**base, 'TradeType': 'Listed',
                'Volume': r['ListedVol'], 'Amount': r['ListedAmt']})
        if r['BlockVol'] > 0:
            stacked.append({**base, 'TradeType': 'Block',
                'Volume': r['BlockVol'], 'Amount': r['BlockAmt']})
    return stacked

def verify(records):
    """Verify: TotalVol == ListedVol + BlockVol"""
    ok = fail = 0
    for r in records:
        if abs(r['ListedVol'] + r['BlockVol'] - r['TotalVol']) < 1:
            ok += 1
        else:
            fail += 1
    return ok, fail

def main():
    print("=== CRC Carbon Market Incremental Sync ===\n")

    # Step 1: Get website latest date
    print("[Step 1] Fetching website latest date...")
    site_latest = get_site_latest_date()
    print(f"  Website latest: {site_latest}")

    # Step 2: Get local CSV latest date
    print("\n[Step 2] Fetching local CSV latest date...")
    csv_latest = get_csv_latest_date()
    print(f"  Local latest: {csv_latest}")

    # Step 3: Compare dates
    print("\n[Step 3] Comparing dates...")
    if csv_latest is None:
        print("  No local file, triggering full download from 2026-01-01")
        csv_latest = '2025-12-31'

    if norm_date(site_latest) <= norm_date(csv_latest):
        print(f"  Local is up-to-date ({csv_latest} >= website {site_latest}), no update needed")
        return

    print(f"  Website is newer, will download records after {csv_latest}...")

    # Step 4: Download new records
    print("\n[Step 4] Downloading new records...")
    new_wide = download_new_since(csv_latest)

    if not new_wide:
        print("  No new records found, website may have no new data")
        return

    ok, fail = verify(new_wide)
    print(f"  Downloaded {len(new_wide)} new records (verify: {ok} passed, {fail} failed)")

    # Step 5: Convert to stacked format
    new_stacked = wide_to_stacked(new_wide)
    print(f"  Stacked: {len(new_stacked)} records")

    # Step 6: Merge and write to local CSV
    print("\n[Step 5] Merging and writing local CSV...")

    existing = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            existing = [row for row in reader if row.get('Date', '').strip()]
        print(f"  Existing records: {len(existing)}")

    # Remove duplicates (same Date + TradeType)
    new_keys = {(r['Date'], r['TradeType']) for r in new_stacked}
    merged = [r for r in existing if (r['Date'], r['TradeType']) not in new_keys]
    merged.extend(new_stacked)
    merged.sort(key=lambda r: norm_date(r['Date']))

    cols = ['Date', 'Variety', 'TradeType', 'Close', 'High', 'Low', 'Volume', 'Amount']
    with open(CSV_FILE, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows(merged)

    print(f"  Saved: {CSV_FILE}")
    print(f"  Total: {len(merged)} records | {merged[0]['Date']} ~ {merged[-1]['Date']}")
    print(f"  Added: {len(new_stacked)} new records")

if __name__ == '__main__':
    main()
