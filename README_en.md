# China Carbon Market — Data Collection & Anomaly Detection

## Project Overview

Automated data collection, cleaning, and anomaly detection for China's national carbon market (CEA), covering January–April 2026.

## Data Sources

| Source | Description |
|--------|-------------|
| **CNEEEX** (Shanghai Environment & Energy Exchange) | Daily market snapshots via image OCR (quota-level detail per allowance year) |
| **CRC** (China Carbon Emission Registry & Settlement) | Structured settlement tables with Listed/Block volume & price — directly parseable |

---

## Directory Structure

```
carbon-anomaly-detection/
├── README.md              # Chinese version
├── README_en.md           # This file
├── data/
│   ├── raw/               # Raw data & intermediate files
│   └── cneeex_images_v2/  # CNEEEX market snapshot images (PNG)
└── Result-e/
    ├── download_crc.py        # CRC full download script
    ├── sync_crc.py            # CRC incremental sync script
    ├── CRC_Carbon_Market_v7.csv  # Master dataset (English columns, stacked format)
    └── result/
        ├── 03-download_crc.py  # CRC download (Chinese version)
        ├── 04-sync_crc.py      # CRC sync (Chinese version)
        ├── 05-anomaly_detection.py  # Anomaly detection & visualization
        └── anomaly_detection_result.csv  # Detection results
```

---

## Core Data File

### CRC_Carbon_Market_v7.csv

Master dataset from CRC website, processed: download → clean → stacked format → verify.

| Column | Description |
|--------|-------------|
| `Date` | Trade date (YYYY-MM-DD) |
| `Variety` | Trading variety (CEA) |
| `TradeType` | Trade type (Listed / Block) |
| `Close` | Closing price (CNY/ton) |
| `High` | Highest price (CNY/ton) |
| `Low` | Lowest price (CNY/ton) |
| `Volume` | Trading volume (tons) |
| `Amount` | Trading amount (CNY) |

- **Rows**: 117 (stacked, one row per trade type per day)
- **Trading days**: 74
- **Date range**: 2026-01-05 ~ 2026-04-30

---

## Core Scripts

### download_crc.py

Full download script. Fetches all 116 pages from CRC, filters out zero-volume records, keeps only 2026 data and later, converts to stacked format.

```bash
python download_crc.py
```

Output: `CRC_Carbon_Market_v7.csv`

---

### sync_crc.py

Incremental sync script. Compares the website's latest date with the local CSV. If the website has newer data, it downloads and appends the new records.

```bash
python sync_crc.py
```

Features:
- Fetches website latest date vs local CSV latest date
- Normalized date string comparison (YYYY-MM-DD) to avoid lexical comparison pitfalls
- Deduplication before merging (Date + TradeType key)

---

### 05-anomaly_detection.py

Anomaly detection on CRC data, generates 4 analysis charts.

```bash
python 05-anomaly_detection.py
```

Output (saved in `Result-e/result/`):
- `anomaly_detection_result.csv` — Detection results
- `fig1_price_trend.png` — Price trend with 3σ bounds and anomaly markers
- `fig2_volume_trend.png` — Volume bar chart (anomaly days highlighted in red)
- `fig3_return_dist.png` — Daily return distribution histogram
- `fig4_iforest_scatter.png` — Isolation Forest scatter plot

**Detection methods**:
- **3-Sigma Rule**: Daily average price exceeds mean ± 3σ → anomaly
- **Isolation Forest**: Multi-dimensional feature (price, volume, return, amount) → anomaly
- **Combined**: Union of both methods

---

## Data Verification Rule

CRC data is automatically verified during download:

```
Daily Total Volume (tons) = Listed Volume (tons) + Block Volume (tons)
```

All 74 records pass this verification (74 passed, 0 failed).

---

## Requirements

```bash
pip install requests beautifulsoup4 pandas numpy scikit-learn matplotlib
```

---

## Workflow

```
CRC Website (116 pages)
        ↓
download_crc.py  ←── first run: full download
        ↓
CRC_Carbon_Market_v7.csv
        ↓
sync_crc.py  ←── daily run: incremental sync
        ↓
05-anomaly_detection.py  ←── analysis & charts
        ↓
anomaly_detection_result.csv + 4 PNG charts
```

---

## Changelog

| Version | Date | Description |
|---------|------|-------------|
| v1–v5 | 2026-05-03 | CRC download iterations (wide table → stacked → verification) |
| v6 | 2026-05-03 | Full download + English column names |
| v7 | 2026-05-03 | Incremental sync + anomaly detection charts |
