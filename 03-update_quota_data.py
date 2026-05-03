#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
National Carbon Market Quota Data Incremental Updater
=============================
Version: v2.2 (2026-04-29)
Author: Archer ⚡

Function:
  1. Check the date of the latest article on the CNEEEX index page
  2. Compare the latest date of the local CSV
  3. If there is any discrepancy, automatically download new matching images → OCR recognition → Append/Update CSV

Usage Method:
  python update_quota_data.py

Output:
  data/National Carbon Market 2026 Q1-Q2 Allowance Details_Anomaly Detection.csv (UTF-8-BOM Encoding)
"""

import os
import re
import time
import shutil
import requests
import pandas as pd

# ====================== Configuration ======================
VERSION = "v2.2"

PROJECT    = r"C:\Users\linux365\.openclaw\workspace\carbon-anomaly-detection"
IMG_DIR     = os.path.join(PROJECT, "data", "cneeex_images_v2")
OUT_DIR     = os.path.join(PROJECT, "data", "raw")
MERGED_CSV  = os.path.join(PROJECT, "data", "National Carbon Market 2026 Mar-Apr Allowance Details.csv")

os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.cneeex.com/",
}

INDEX_URL = "https://www.cneeex.com/qgtpfqjy/mrgk/2026n/index.shtml"

# Quota Name Standardization
QUOTA_MAP = {
    "碳排放配额25": "CEA25",
    "碳排放配额24": "CEA24",
    "碳排放配额23": "CEA23",
    "碳排放配额22": "CEA22",
    "碳排放配额21": "CEA21",
    "碳排放配额19-20": "CEA19-20",
    "CEA25": "CEA25", "CEA24": "CEA24", "CEA23": "CEA23",
    "CEA22": "CEA22", "CEA21": "CEA21", "CEA19-20": "CEA19-20",
}

# 04-20~04-24用alt2图（文章中第3张upload图）
ALT2_DATES = {"2026-04-20", "2026-04-21", "2026-04-22", "2026-04-23", "2026-04-24"}


# ====================== Step 1: Get the latest date of the website ======================

def get_site_latest_date() -> str:
    """Scrape the latest article date from the CNEEEX index page and return it. YYYY-MM-DD"""
    print(f"[步骤1] 检查CNEEEX索引页: {INDEX_URL}")

    session = requests.Session()
    all_articles = {}  # {date: url}

    for page in range(1, 10):
        url = INDEX_URL if page == 1 else f"{INDEX_URL.rstrip('index.shtml')}index_{page}.shtml"
        try:
            r = session.get(url, headers=HEADERS, timeout=15)
            r.encoding = "utf-8"
            text = r.text
        except Exception as e:
            print(f"  [!] the{page}page Acquisition failed: {e}")
            break

        links = re.findall(r'href="(/c/(2026-\d{2}-\d{2})/(\d+)\.shtml)"', text)
        if not links:
            break

        for url_path, date, sid in links:
            if date not in all_articles:
                all_articles[date] = "https://www.cneeex.com" + url_path

        time.sleep(0.3)

    if not all_articles:
        raise RuntimeError("Failed to retrieve any articles from the CNEEEX index page")

    latest = max(sorted(all_articles.keys()))
    print(f"  Latest website date: {latest} (Total {len(all_articles)} papers Article)")
    return latest, all_articles


# ====================== Step 2: Obtain the latest date of the CSV ======================

def get_csv_latest_date() -> str:
    """Read and merge CSV files, return the latest date string"""
    print(f"[Step 2] Check the local CSV: {os.path.basename(MERGED_CSV)}")

    if not os.path.exists(MERGED_CSV):
        print("  The file does not exist, and the latest date is regarded as empty.")
        return None

    df = pd.read_csv(MERGED_CSV, encoding="utf-8-sig")
    if df.empty:
        print("  CSV is empty")
        return None

    latest = df["日期"].max()
    print(f"  Latest CSV Date: {latest} ({len(df)} Record, {df['日期'].nunique()} Trading Day)")
    return latest


# ====================== Step 3: Identify the date that needs to be updated ======================

def find_dates_to_fetch(site_latest: str, csv_latest: str, all_articles: dict) -> list:
    """Return the list of dates to be crawled (all dates after csv_latest)"""
    print(f"[Step 3] Compare dates")

    if csv_latest is None:
        dates = sorted(all_articles.keys())
    else:
        dates = [d for d in sorted(all_articles.keys()) if d > csv_latest]

    if dates:
        print(f"  Need to be updated: {len(dates)} Date -> {dates[0]} ~ {dates[-1]}")
    else:
        print(f"  The data is already up to date and no update is required.")
    return dates


# ====================== Step 4: Download Daily Matching Imagesv2 ======================

def ensure_v2_image(date: str, article_url: str) -> str:
    """
    Download the version 2 illustrations for a specific date and return the local path.。
    Special: 04-20~04-24用alt2图（第3张upload图）
    """
    local = os.path.join(IMG_DIR, f"{date}_v2.png")

    # Skip existing valid images
    if os.path.exists(local) and os.path.getsize(local) > 40000:
        return local

    r = requests.get(article_url, headers=HEADERS, timeout=15)
    r.encoding = "utf-8"
    imgs = re.findall(r"upload/resources/image/(\d{4}/\d{2}/\d{2}/\d+\.png)", r.text)
    imgs = list(dict.fromkeys(imgs))

    if not imgs:
        raise RuntimeError(f"[{date}] No matching image found on the page")

    use_alt2 = date in ALT2_DATES
    if len(imgs) >= 3 and use_alt2:
        img_name = imgs[2]  # alt2: 第3张图
    else:
        img_name = imgs[1] if len(imgs) >= 2 else imgs[0]

    url = "https://www.cneeex.com/upload/resources/image/" + img_name
    r2 = requests.get(url, headers=HEADERS, timeout=15)
    with open(local, "wb") as f:
        f.write(r2.content)

    size = len(r2.content)
    print(f"  [{date}] 下载配图: {size:,} bytes {'(alt2)' if use_alt2 else ''}")
    return local


# ====================== Step 5: OCR recognition of a single matching image ======================

def ocr_image(image_path: str) -> list:
    """
    调用MiniMax-Image-01 OCR解析配图v2
    返回: [{date, trade, quota, open, high, low, close, chg, vol, amt}, ...]
    """
    from image import image as img_tool

    prompt = (
        "Identify the table showing the annual transaction status of carbon emission allowances in the national carbon market。\n"
        "Output format (one entry per line, do not output subtotal lines)：\n"
        "Quota, Transaction Type, Opening Price, Highest Price, Lowest Price, Closing Price, Increase Rate, Daily Trading Volume, Daily Turnover\n"
        "Example: Carbon emission allowance 25, listing agreement trading,79.54,-,-,79.54,0.00,-,-\n"
        "Fill in the increase percentage with numbers only, no extra characters.% (如0.00 / -0.89)；- Or empty, indicating no data。"
    )

    result = img_tool(image=image_path, prompt=prompt)
    return parse_ocr_result(result)


def parse_ocr_result(text: str) -> list:
    """Parse the OCR output text and return a list of records"""
    records = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line or len(line) < 5:
            continue
        if any(k in line for k in ["===", "标题", "表头", "说明", "注", "全国碳市场每", "小计"]):
            continue

        cells = [c.strip() for c in re.split(r"[,\t]+", line)]
        if len(cells) < 9:
            continue

        # 配额
        quota_raw = cells[0]
        quota = QUOTA_MAP.get(quota_raw, quota_raw)
        if quota not in ("CEA25", "CEA24", "CEA23", "CEA22", "CEA21", "CEA19-20"):
            continue

        # 交易类型
        trade_raw = cells[1] if len(cells) > 1 else ""
        if "挂牌" in trade_raw:
            trade = "挂牌协议"
        elif "大宗" in trade_raw:
            trade = "大宗协议"
        elif "单向" in trade_raw:
            trade = "单向竞价"
        else:
            continue

        # 数字解析
        def pnum(s):
            s = str(s).strip()
            if s in ("-", "", "N/A", "—"):
                return 0.0
            s = s.replace(",", "").replace("，", "")
            try:
                return float(s)
            except:
                return 0.0

        nums = []
        for c in cells[2:]:
            c = c.strip()
            if "%" in c:
                try:
                    nums.append(float(c.replace("%", "").replace(",", "")))
                except:
                    nums.append(0.0)
            elif c.replace(",", "").replace(".", "").replace("-", "").isdigit():
                nums.append(pnum(c))
            elif c in ("-", "—"):
                nums.append(0.0)

        if len(nums) >= 7:
            records.append({
                "quota": quota,
                "trade": trade,
                "open":  nums[0],
                "high":  nums[1],
                "low":   nums[2],
                "close": nums[3],
                "chg":   nums[4],
                "vol":   nums[5],
                "amt":   nums[6],
            })

    return records


# ====================== Step 6: Update CSV ======================

def update_csv(new_records: list):
    """Append/Update new records to the merged CSV"""
    if not new_records:
        return

    cols = [
        "日期", "交易类型", "各年度碳排放配额",
        "开盘价（元/吨）", "最高价（元/吨）", "最低价（元/吨）", "收盘价（元/吨）",
        "涨幅", "日成交量（吨）", "日成交额（元）",
    ]

    # Create a new record DataFrame
    new_df = pd.DataFrame(new_records, columns=cols)

    # Filter trading volume=0
    new_df = new_df[new_df["日成交量（吨）"] > 0].reset_index(drop=True)

    if new_df.empty:
        print("  No data is written after filtering new records with empty results.")
        return

    print(f"  Valid New Record: {len(new_df)} 条")

    # Read an existing CSV file or create an empty DataFrame
    if os.path.exists(MERGED_CSV):
        existing_df = pd.read_csv(MERGED_CSV, encoding="utf-8-sig")
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        combined_df = new_df

    # Deduplication (Retain one record for the same date, quota and transaction method)
    combined_df = combined_df.drop_duplicates(
        subset=["日期", "各年度碳排放配额", "交易类型"], keep="last"
    )
    combined_df = combined_df.sort_values(["日期", "各年度碳排放配额", "交易类型"]).reset_index(drop=True)

    # Save
    combined_df.to_csv(MERGED_CSV, index=False, encoding="utf-8-sig")
    print(f"  已保存: {MERGED_CSV}")
    print(f"  总记录: {len(combined_df)} 条, 交易日: {combined_df['日期'].nunique()} 天")


# ====================== Main Process ======================

def main():
    print(f"=== National Carbon Market Quota Data Incremental Updater {VERSION} ===\n")

    # Step 1: The latest date of the website
    site_latest, all_articles = get_site_latest_date()

    # Step 2: Latest date of CSV
    csv_latest = get_csv_latest_date()

    # Step 3: Identify the date to be captured
    dates_to_fetch = find_dates_to_fetch(site_latest, csv_latest, all_articles)

    if not dates_to_fetch:
        print("\nIt is already the latest version and no update is required.。")
        return

    # 步骤4+5: 下载 + OCR
    print(f"\n[Step 4+5] Start crawling {len(dates_to_fetch)} 个New data of the date..")
    all_new_records = []

    for date in dates_to_fetch:
        print(f"\nHandle: {date}")
        article_url = all_articles[date]

        try:
            img_path = ensure_v2_image(date, article_url)
        except Exception as e:
            print(f"  [!] Download failed: {e}")
            continue

        size = os.path.getsize(img_path)
        print(f"  Matching picture: {os.path.basename(img_path)} ({size:,} bytes)")

        try:
            records = ocr_image(img_path)
        except Exception as e:
            print(f"  [!] OCRFailure: {e}")
            records = []

        # 注入日期
        for rec in records:
            if rec["vol"] > 0:
                rec["date"] = date
                all_new_records.append(rec)

        valid = sum(1 for r in records if r["vol"] > 0)
        print(f"  -> {valid} valid records")
        time.sleep(1.5)

    # 步骤6: 更新CSV
    if all_new_records:
        print(f"\n[Step 6] Update CSV...")
        # 整理列名以匹配CSV格式
        formatted = []
        for rec in all_new_records:
            formatted.append({
                "日期":                  rec["date"],
                "交易类型":              rec["trade"],
                "各年度碳排放配额":       rec["quota"],
                "开盘价（元/吨）":        rec["open"],
                "最高价（元/吨）":        rec["high"],
                "最低价（元/吨）":        rec["low"],
                "收盘价（元/吨）":        rec["close"],
                "涨幅":                  rec["chg"],
                "日成交量（吨）":          rec["vol"],
                "日成交额（元）":          rec["amt"],
            })
        update_csv(formatted)
    else:
        print("\nNo new records retrieved, CSV not updated。")

    # 最终报告
    print("\n=== Completed ===")
    if os.path.exists(MERGED_CSV):
        df = pd.read_csv(MERGED_CSV, encoding="utf-8-sig")
        print(f"File: {MERGED_CSV}")
        print(f"Total Records: {len(df)} 条")
        print(f"Trading day: {df['日期'].nunique()} 天 ({df['日期'].min()} ~ {df['日期'].max()})")
        print(f"Quota Type: {df['Annual Carbon Emission Allowances'].unique()}")
        print(f"Transaction Type: {df['Transaction Type'].unique()}")


if __name__ == "__main__":
    main()