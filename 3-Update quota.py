import os
import re
import time
import shutil
import requests
import pandas as pd

# ====================== 配置 ======================
VERSION = "v2.2"

PROJECT    = r"Desktop"
IMG_DIR     = os.path.join(PROJECT, "data", "cneeex_images_v2")
OUT_DIR     = os.path.join(PROJECT, "data", "raw")
MERGED_CSV  = os.path.join(PROJECT, "data", "全国碳市场2026年Q1-Q2配额明细_异常检测.csv")

os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.cneeex.com/",
}

INDEX_URL = "https://www.cneeex.com/qgtpfqjy/mrgk/2026n/index.shtml"

# 配额名称标准化
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


# ====================== 步骤1：获取网站最新日期 ======================

def get_site_latest_date() -> str:
    """从CNEEEX索引页抓取最新文章日期，返回 YYYY-MM-DD"""
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
            print(f"  [!] 第{page}页获取失败: {e}")
            break

        links = re.findall(r'href="(/c/(2026-\d{2}-\d{2})/(\d+)\.shtml)"', text)
        if not links:
            break

        for url_path, date, sid in links:
            if date not in all_articles:
                all_articles[date] = "https://www.cneeex.com" + url_path

        time.sleep(0.3)

    if not all_articles:
        raise RuntimeError("无法从CNEEEX索引页获取任何文章")

    latest = max(sorted(all_articles.keys()))
    print(f"  网站最新日期: {latest} (共 {len(all_articles)} 篇文章)")
    return latest, all_articles


# ====================== 步骤2：获取CSV最新日期 ======================

def get_csv_latest_date() -> str:
    """读取合并CSV，返回最新日期字符串"""
    print(f"[步骤2] 检查本地CSV: {os.path.basename(MERGED_CSV)}")

    if not os.path.exists(MERGED_CSV):
        print("  文件不存在，最新日期视为空")
        return None

    df = pd.read_csv(MERGED_CSV, encoding="utf-8-sig")
    if df.empty:
        print("  CSV为空")
        return None

    latest = df["日期"].max()
    print(f"  CSV最新日期: {latest} ({len(df)} 条记录, {df['日期'].nunique()} 个交易日)")
    return latest


# ====================== 步骤3：发现需要更新的日期 ======================

def find_dates_to_fetch(site_latest: str, csv_latest: str, all_articles: dict) -> list:
    """返回需要抓取的日期列表（csv_latest之后的所有日期）"""
    print(f"[步骤3] 比较日期")

    if csv_latest is None:
        dates = sorted(all_articles.keys())
    else:
        dates = [d for d in sorted(all_articles.keys()) if d > csv_latest]

    if dates:
        print(f"  需要更新: {len(dates)} 个日期 -> {dates[0]} ~ {dates[-1]}")
    else:
        print(f"  数据已是最新，无需更新")
    return dates


# ====================== 步骤4：下载单日配图v2 ======================

def ensure_v2_image(date: str, article_url: str) -> str:
    """
    下载某日期的配图v2，返回本地路径。
    特殊: 04-20~04-24用alt2图（第3张upload图）
    """
    local = os.path.join(IMG_DIR, f"{date}_v2.png")

    # 跳过已存在的有效图片
    if os.path.exists(local) and os.path.getsize(local) > 40000:
        return local

    r = requests.get(article_url, headers=HEADERS, timeout=15)
    r.encoding = "utf-8"
    imgs = re.findall(r"upload/resources/image/(\d{4}/\d{2}/\d{2}/\d+\.png)", r.text)
    imgs = list(dict.fromkeys(imgs))

    if not imgs:
        raise RuntimeError(f"[{date}] 页面上未找到配图")

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


# ====================== 步骤5：OCR识别单张配图 ======================

def ocr_image(image_path: str) -> list:
    """
    调用MiniMax-Image-01 OCR解析配图v2
    返回: [{date, trade, quota, open, high, low, close, chg, vol, amt}, ...]
    """
    from image import image as img_tool

    prompt = (
        "识别这张全国碳市场各年度碳排放配额成交情况表格。\n"
        "输出格式（每行一条，不要输出小计行）：\n"
        "配额,交易类型,开盘价,最高价,最低价,收盘价,涨幅,日成交量,日成交额\n"
        "例: 碳排放配额25,挂牌协议交易,79.54,-,-,79.54,0.00,-,-\n"
        "涨幅填数字不带% (如0.00 / -0.89)；- 或空 表示无数据。"
    )

    result = img_tool(image=image_path, prompt=prompt)
    return parse_ocr_result(result)


def parse_ocr_result(text: str) -> list:
    """解析OCR输出文本，返回记录列表"""
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


# ====================== 步骤6：更新CSV ======================

def update_csv(new_records: list):
    """将新记录追加/更新到合并CSV"""
    if not new_records:
        return

    cols = [
        "日期", "交易类型", "各年度碳排放配额",
        "开盘价（元/吨）", "最高价（元/吨）", "最低价（元/吨）", "收盘价（元/吨）",
        "涨幅", "日成交量（吨）", "日成交额（元）",
    ]

    # 构建新记录DataFrame
    new_df = pd.DataFrame(new_records, columns=cols)

    # 过滤成交量=0
    new_df = new_df[new_df["日成交量（吨）"] > 0].reset_index(drop=True)

    if new_df.empty:
        print("  新记录过滤后为空，无数据写入")
        return

    print(f"  有效新记录: {len(new_df)} 条")

    # 读取现有CSV或创建空DataFrame
    if os.path.exists(MERGED_CSV):
        existing_df = pd.read_csv(MERGED_CSV, encoding="utf-8-sig")
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        combined_df = new_df

    # 去重（同日期+配额+交易方式保留一条）
    combined_df = combined_df.drop_duplicates(
        subset=["日期", "各年度碳排放配额", "交易类型"], keep="last"
    )
    combined_df = combined_df.sort_values(["日期", "各年度碳排放配额", "交易类型"]).reset_index(drop=True)

    # 保存
    combined_df.to_csv(MERGED_CSV, index=False, encoding="utf-8-sig")
    print(f"  已保存: {MERGED_CSV}")
    print(f"  总记录: {len(combined_df)} 条, 交易日: {combined_df['日期'].nunique()} 天")


# ====================== 主流程 ======================

def main():
    print(f"=== 全国碳市场配额数据增量更新器 {VERSION} ===\n")

    # 步骤1: 网站最新日期
    site_latest, all_articles = get_site_latest_date()

    # 步骤2: CSV最新日期
    csv_latest = get_csv_latest_date()

    # 步骤3: 发现需要抓取的日期
    dates_to_fetch = find_dates_to_fetch(site_latest, csv_latest, all_articles)

    if not dates_to_fetch:
        print("\n数据已是最新，无需更新。")
        return

    # 步骤4+5: 下载 + OCR
    print(f"\n[步骤4+5] 开始抓取 {len(dates_to_fetch)} 个日期的新数据...")
    all_new_records = []

    for date in dates_to_fetch:
        print(f"\n处理: {date}")
        article_url = all_articles[date]

        try:
            img_path = ensure_v2_image(date, article_url)
        except Exception as e:
            print(f"  [!] 下载失败: {e}")
            continue

        size = os.path.getsize(img_path)
        print(f"  配图: {os.path.basename(img_path)} ({size:,} bytes)")

        try:
            records = ocr_image(img_path)
        except Exception as e:
            print(f"  [!] OCR失败: {e}")
            records = []

        # 注入日期
        for rec in records:
            if rec["vol"] > 0:
                rec["date"] = date
                all_new_records.append(rec)

        valid = sum(1 for r in records if r["vol"] > 0)
        print(f"  -> {valid} 条有效记录")
        time.sleep(1.5)

    # 步骤6: 更新CSV
    if all_new_records:
        print(f"\n[步骤6] 更新CSV...")
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
        print("\n未获取到任何新记录，CSV未更新。")

    # 最终报告
    print("\n=== 完成 ===")
    if os.path.exists(MERGED_CSV):
        df = pd.read_csv(MERGED_CSV, encoding="utf-8-sig")
        print(f"文件: {MERGED_CSV}")
        print(f"总记录: {len(df)} 条")
        print(f"交易日: {df['日期'].nunique()} 天 ({df['日期'].min()} ~ {df['日期'].max()})")
        print(f"配额类型: {df['各年度碳排放配额'].unique()}")
        print(f"交易类型: {df['交易类型'].unique()}")


if __name__ == "__main__":
    main()