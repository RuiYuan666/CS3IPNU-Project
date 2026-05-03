# China Carbon Market — Data Collection & Anomaly Detection

## 项目概述 / Project Overview

本项目实现中国全国碳市场（CEA）数据的自动化采集、清洗与异常检测，覆盖 2026 年 1–4 月行情数据。

This project automates the collection, cleaning, and anomaly detection of China's national carbon market (CEA) trading data, covering January–April 2026.

---

## 数据来源 / Data Sources

| 来源 | 说明 |
|------|------|
| **CNEEEX**（上海环境能源交易所） | 每日行情文章配图，含各年度配额明细，需 OCR 识别 |
| **CRC**（中国碳排放权注册登记结算有限责任公司） | 结构化结算信息表格，含挂牌/大宗成交量与价格，直接解析 |

---

## 目录结构 / Directory Structure

```
carbon-anomaly-detection/
├── README.md
├── data/
│   ├── raw/                          # 原始数据（含各版本中间文件）
│   └── cneeex_images_v2/             # CNEEEX 行情配图（PNG）
├── Result-e/
│   ├── download_crc.py               # CRC 全量下载脚本
│   ├── sync_crc.py                   # CRC 增量同步脚本
│   ├── CRC_Carbon_Market_v7.csv      # CRC 主数据文件（英文列名，一级表）
│   └── result/
│       ├── 03-download_crc.py        # CRC 下载（中文版）
│       ├── 04-sync_crc.py            # CRC 同步（中文版）
│       ├── 05-anomaly_detection.py   # 异常检测可视化
│       └── anomaly_detection_result.csv  # 异常检测结果
```

---

## 核心数据文件 / Core Data File

### CRC_Carbon_Market_v7.csv

主数据文件，来自 CRC 网站，经下载→清洗→一级表展开→核实后生成。

| 列名 | 说明 |
|------|------|
| `Date` | 交易日期（YYYY-MM-DD） |
| `Variety` | 交易品种（CEA） |
| `TradeType` | 交易类型（Listed / Block） |
| `Close` | 收盘价（元/吨） |
| `High` | 最高价（元/吨） |
| `Low` | 最低价（元/吨） |
| `Volume` | 成交量（吨） |
| `Amount` | 成交额（元） |

- **记录数**：117 行（一级表展开后）
- **交易日**：74 天
- **日期范围**：2026-01-05 ~ 2026-04-30

---

## 核心脚本 / Core Scripts

### download_crc.py

全量下载脚本。从 CRC 网站下载全部 116 页数据，自动过滤无成交记录，仅保留 2026 年以后数据，转换为一级表格式。

```bash
python download_crc.py
```

输出：`CRC_Carbon_Market_v7.csv`

---

### sync_crc.py

增量同步脚本。对比网站最新日期与本地 CSV 日期，若网站更新则下载并追加新数据。

```bash
python sync_crc.py
```

功能：
- 获取网站最新日期 vs 本地最新日期
- 日期字符串统一规范化（YYYY-MM-DD）比较
- 去重合并写入同一 CSV 文件

---

### 05-anomaly_detection.py

基于 CRC 数据进行异常检测，生成 4 张分析图表。

```bash
python 05-anomaly_detection.py
```

输出：
- `anomaly_detection_result.csv` — 异常检测结果数据
- `fig1_price_trend.png` — 价格走势图（含 3σ 边界与异常标记）
- `fig2_volume_trend.png` — 成交量柱状图（异常日标红）
- `fig3_return_dist.png` — 收益率分布直方图
- `fig4_iforest_scatter.png` — Isolation Forest 散点图

**检测方法**：
- **3-Sigma 规则**：日均价超出均值±3σ 判定为异常
- **Isolation Forest**：多维特征标准化后隔离森林异常检测
- 两者并集为综合异常

---

## 数据核实规则 / Data Verification

CRC 数据在下载过程中自动验证：

```
当日总成交量（吨）= 挂牌成交量（吨）+ 大宗成交量（吨）
```

全部记录均通过此等式验证（74/74 通过，0 失败）。

---

## 依赖 / Requirements

```bash
pip install requests beautifulsoup4 pandas numpy scikit-learn matplotlib
```

---

## 更新日志 / Changelog

| 版本 | 日期 | 说明 |
|------|------|------|
| v1–v5 | 2026-05-03 | CRC 数据下载迭代（宽表→一级表→核实逻辑） |
| v6 | 2026-05-03 | 全量下载 + 英文列名 |
| v7 | 2026-05-03 | 增量同步脚本 + 异常检测图表 |
