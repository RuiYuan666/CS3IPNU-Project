# Carbon Price Anomaly Detection

Detects anomalous trading days in China's National Carbon Market (全国碳市场) using the **3σ rule** and **Isolation Forest** algorithm, with data sourced via web scraping + OCR from the Shanghai Energy Exchange (CNEEEX).

---

## 📁 Project Structure

```
Result-e/
├── 01-carbon_price_3sigma_outlier_detection.py
│   └── Detects outliers per trading type using rolling 3σ rule on closing prices.
├── 02-carbon_price_3sigma_isolation_forest_outlier_detection.py
│   └── Combines rolling 3σ and Isolation Forest for dual-mechanism detection.
├── 03-update_quota_data.py
│   └── Incremental updater: checks CNEEEX daily articles → downloads quota images → OCR → appends to CSV.
├── 04-anomaly_detection.py
│   └── Generates 4 English charts (price trend, volume bar, daily range, volume heatmap) with detected anomalies highlighted.
│
├── National Carbon Market 2026 Mar-Apr Allowance Details.csv
│   └── Aggregated daily quota data (CEA25/24/23/22/21/19-20 × listing大宗协议) with anomaly labels.
├── cea_all_final.csv
│   └── Full CEA historical data (2021–present, 10 columns).
└── cea_2021_10col_final.csv
    └── CEA 2021 subset used by scripts 01 & 02.
```

---

## ⚙️ Core Methods

### 1. 3σ Rolling Anomaly Detection
For each trading type separately, compute a rolling mean and standard deviation of the closing price over a sliding window (default 15 days). Any day where `|close − μ| > 3σ` is flagged as an anomaly.

### 2. Isolation Forest
An unsupervised ensemble anomaly detector (n_estimators=128, contamination=0.05) applied to `{close, volume, amount}` features. Provides a second, feature-space-based anomaly score independent of the 3σ rule.

A trading day is only marked **anomalous** when flagged by **both** methods — this intersection strategy reduces false positives.

### 3. OCR-Based Data Pipeline (`03-update_quota_data.py`)
- Scrapes CNEEEX index pages for the latest trading-day articles.
- Extracts and deduplicates image URLs from article pages.
- Downloads PNG/JPEG images (>40 KB threshold filters out error pages).
- Runs OCR (MiniMax-Image-01) on quota-detail images to extract per-allowance-type price/volume data.
- Appends / updates rows in the merged CSV (UTF-8-BOM encoding).

---

## 📊 Data Schema (Merged CSV)

| Column | Description |
|--------|-------------|
| 日期 | Trading date |
| 配额类型 | Allowance type (CEA25 / CEA24 / CEA23 / CEA22 / CEA21 / CEA19-20) |
| 交易方式 | Trading method (挂牌协议 / 大宗协议) |
| 开盘价 | Opening price (元/吨) |
| 最高价 | Highest price (元/吨) |
| 最低价 | Lowest price (元/吨) |
| 收盘价 | Closing price (元/吨) |
| 涨幅 | Daily change (%) |
| 日成交量 | Daily volume (吨) |
| 日成交额 | Daily turnover (元) |

---

## 🚀 Usage

```bash
# 1. Update quota data (run periodically to keep CSV current)
python 03-update_quota_data.py

# 2. Detect anomalies on existing CSV
python 01-carbon_price_3sigma_outlier_detection.py
python 02-carbon_price_3sigma_isolation_forest_outlier_detection.py

# 3. Generate visualization charts
python 04-anomaly_detection.py
```

> **Note:** Scripts 01 & 02 read `cea_2021_10col_final.csv` (CEA 2021 historical data). Scripts 03 & 04 read the CNEEEX-sourced quota CSV.

---

## 🔑 Key Design Decisions

- **Dual-method intersection**: An anomaly must satisfy **both** 3σ and Isolation Forest to be flagged — this was chosen to minimize false positives in a thin, volatile market.
- **Per-trading-type 3σ**: The 3σ rule is applied **within each trading type** (挂牌 / 大宗), not across the full market, because price distributions differ significantly between mechanisms.
- **OCR over HTML**: Raw quota details only exist in article images, not HTML text. The pipeline prioritizes image OCR to ensure data completeness.
- **>40 KB download filter**: CNEEEX returns a small 403 error placeholder image on failures; a file-size gate prevents these from entering the pipeline.

---

## 📦 Dependencies

```
numpy
pandas
matplotlib
scikit-learn
requests
```

---

## 📝 License

MIT
