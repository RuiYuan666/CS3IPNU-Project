#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Download CRC National Carbon Market Trading Settlement Information
Source: https://www.chinacrc.net.cn/list/101.html (116 pages)

Column structure (11 columns, no header row):
  [0] Trading Variety
  [1] Date
  [2] Closing Price (CNY/ton)
  [3] Highest Price (CNY/ton)
  [4] Lowest Price (CNY/ton)
  [5] Listed Trading Volume (tons)
  [6] Listed Trading Amount (CNY)
  [7] Block Trading Volume (tons)
  [8] Block Trading Amount (CNY)
  [9] Daily Total Volume (tons)
  [10] Daily Total Amount (CNY)
"""
import os, time, requests, csv
from bs4 import BeautifulSoup

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR    = SCRIPT_DIR  # Save in the same directory as this script
OUT_FILE  = os.path.join(OUT_DIR, "CRC_Carbon_Market_v7.csv")

HEADERS   = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
BASE_URL  = "https://www.chinacrc.net.cn/list/101.html"

def fetch_page(page):
    url = f"{BASE_URL}?page={page}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.encoding = 'utf-8'
    return r.text

def clean_num(s):
    """Parse numeric string, return float; invalid returns 0.0"""
    if not s or s.strip() in ('-', '—', ''):
        return 0.0
    return float(s.strip().replace(',', ''))

def parse_page(html):
    """Parse CRC HTML table (no header row), return list of records"""
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
    parts = s.strip().split('-')
    return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    all_records = []

    print("=== CRC Carbon Market Data Download ===\n")
    for page in range(1, 117):
        print(f"Page {page}...", end=" ", flush=True)
        try:
            recs = parse_page(fetch_page(page))
            if not recs:
                print("No data, stopping"); break
            oldest = min(r['Date'] for r in recs)
            print(f"{len(recs)} records (oldest: {oldest})")
            all_records.extend(recs)
            if oldest < '2026-01-01' and page > 1:
                print("Crossed 2026-01-01, enough data")
                break
        except Exception as e:
            print(f"Failed: {e}"); break
        time.sleep(0.5)

    if not all_records:
        print("No data fetched!"); return

    # Filter: remove records with zero total volume
    before = len(all_records)
    all_records = [r for r in all_records if r['TotalVol'] > 0]
    print(f"Zero-volume filtered: {before} -> {len(all_records)}")

    # Filter: keep only 2026-01-01 and later
    before2 = len(all_records)
    all_records = [r for r in all_records if r['Date'] >= '2026-01-01']
    print(f"Pre-2026 filtered: {before2} -> {len(all_records)}")

    # Verify: TotalVol == ListedVol + BlockVol
    ok = fail = 0
    for r in all_records:
        if abs(r['ListedVol'] + r['BlockVol'] - r['TotalVol']) < 1:
            ok += 1
        else:
            fail += 1
    print(f"Verification: {ok} passed, {fail} failed")

    # Convert to stacked format (one row per trade type)
    stacked = []
    for r in all_records:
        base = {'Date': r['Date'], 'Variety': r['Variety'],
                'Close': r['Close'], 'High': r['High'], 'Low': r['Low']}
        if r['ListedVol'] > 0:
            stacked.append({**base, 'TradeType': 'Listed',
                'Volume': r['ListedVol'], 'Amount': r['ListedAmt']})
        if r['BlockVol'] > 0:
            stacked.append({**base, 'TradeType': 'Block',
                'Volume': r['BlockVol'], 'Amount': r['BlockAmt']})
    print(f"Stacked: {len(stacked)} records")
    all_records = stacked

    # Sort by date (normalized)
    all_records.sort(key=lambda r: norm_date(r['Date']))

    # Write CSV (UTF-8-BOM)
    cols = ['Date', 'Variety', 'TradeType', 'Close', 'High', 'Low', 'Volume', 'Amount']
    with open(OUT_FILE, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows(all_records)

    print(f"\nSaved: {OUT_FILE}")
    print(f"Total: {len(all_records)} records | {all_records[0]['Date']} ~ {all_records[-1]['Date']}")

if __name__ == '__main__':
    main()
