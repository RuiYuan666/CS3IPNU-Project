#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Anomaly Detection Charts - English Separate Figures
Generates 4 individual PNG files with English labels.
"""
import os, time, warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.ensemble import IsolationForest

VERSION = "v1.2-en"
PROJECT = r"C:\Users\linux365\.openclaw\workspace\carbon-anomaly-detection"
DATA_DIR = os.path.join(PROJECT, "data")
IMG_DIR = os.path.join(PROJECT, "data", "imgs")
os.makedirs(IMG_DIR, exist_ok=True)

plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

IFOREST_N = 128

def load_and_preprocess():
    csv_path = os.path.join(DATA_DIR, "全国碳市场2026年Q1-Q2配额明细_异常检测.csv")
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]
    df = df[df["日成交量（吨）"] > 0].copy()

    agg = df.groupby("日期").agg(
        开盘价=("开盘价（元/吨）", "first"),
        日最高价=("最高价（元/吨）", "max"),
        日最低价=("最低价（元/吨）", "min"),
        收盘价=("收盘价（元/吨）", "last"),
        日成交量=("日成交量（吨）", "sum"),
        日成交额=("日成交额（元）", "sum"),
    ).reset_index()
    agg = agg.sort_values("日期").reset_index(drop=True)
    agg["日均价"] = agg["日成交额"] / agg["日成交量"]
    agg.loc[agg["收盘价"] == 0, "收盘价"] = agg.loc[agg["收盘价"] == 0, "日均价"]
    agg["昨日收盘"] = agg["收盘价"].shift(1).fillna(agg["收盘价"].iloc[0])
    agg["涨幅"] = (agg["收盘价"] - agg["昨日收盘"]) / agg["昨日收盘"] * 100
    agg["涨幅"] = agg["涨幅"].clip(-50, 50)
    agg["日期_dt"] = pd.to_datetime(agg["日期"])
    print(f"[Data] {len(agg)} trading days ({agg['日期'].min()} ~ {agg['日期'].max()})")
    return agg

def detect_anomalies(df_raw):
    result = df_raw.copy()
    mu = result["日均价"].mean()
    sigma = result["日均价"].std()
    result["3σ_下界"] = mu - 3 * sigma
    result["3σ_上界"] = mu + 3 * sigma
    result["3σ_异常"] = (
        (result["日均价"] < mu - 3 * sigma) |
        (result["日均价"] > mu + 3 * sigma)
    )
    feat = result[["日均价", "日成交量", "涨幅", "日成交额"]].copy()
    for col in feat.columns:
        m, s = feat[col].mean(), feat[col].std()
        if s > 0:
            feat[col] = (feat[col] - m) / s
    clf = IsolationForest(n_estimators=IFOREST_N, contamination=0.1, random_state=42, n_jobs=-1)
    labels = clf.fit_predict(feat)
    scores = clf.decision_function(feat)
    result["IForest_异常"] = (labels == -1)
    result["IForest_得分"] = scores
    result["IForest_置信"] = 1 - (scores - scores.min()) / (scores.max() - scores.min() + 1e-9)
    result["综合异常"] = result["3σ_异常"] | result["IForest_异常"]
    result["异常等级"] = "Normal"
    result.loc[result["3σ_异常"] & result["IForest_异常"], "异常等级"] = "Severe Anomaly"
    result.loc[result["IForest_异常"] & ~result["3σ_异常"], "异常等级"] = "Mild Anomaly"
    print(f"[Detection] 3-sigma: {result['3σ_异常'].sum()}, IForest: {result['IForest_异常'].sum()}, Combined: {result['综合异常'].sum()}")
    return result

# ====================== Chart 1: Price Trend ======================
def plot_price(df: pd.DataFrame):
    anoms = df[df["综合异常"]]
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(df["日期_dt"], df["收盘价"], "b-", linewidth=1.8, label="Closing Price", zorder=2)
    ax.fill_between(df["日期_dt"], df["日最低价"], df["日最高价"],
                     alpha=0.15, color="blue", label="Daily Range")
    ax.axhline(df["3σ_上界"].iloc[0], color="green", linestyle="--",
                linewidth=1.5, alpha=0.8, label=f"3-sigma Upper: {df['3σ_上界'].iloc[0]:.1f}")
    ax.axhline(df["3σ_下界"].iloc[0], color="green", linestyle="--",
                linewidth=1.5, alpha=0.8, label=f"3-sigma Lower: {df['3σ_下界'].iloc[0]:.1f}")
    ax.scatter(anoms["日期_dt"], anoms["收盘价"], c="red", s=150,
                zorder=5, label=f"Anomalies ({len(anoms)})", edgecolors="darkred", linewidths=2)
    for _, r in anoms.iterrows():
        ax.annotate(r["日期"][5:], (r["日期_dt"], r["收盘价"]),
                     xytext=(0, 10), textcoords="offset points",
                     fontsize=9, color="red", ha="center", fontweight='bold')
    ax.set_title("Figure 1: CEA25 Closing Price Trend with Anomaly Detection\n(China Carbon Market, Mar-Apr 2026)", fontsize=13, fontweight='bold')
    ax.set_ylabel("Price (CNY/ton)", fontsize=11)
    ax.set_xlabel("Date", fontsize=11)
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.tick_params(axis='x', rotation=30)
    plt.tight_layout()
    ts = time.strftime("%Y%m%d")
    out_png = os.path.join(IMG_DIR, f"fig1_price_trend_en_{ts}.png")
    plt.savefig(out_png, dpi=150, bbox_inches="tight")
    print(f"[Saved] {out_png}")
    plt.close()

# ====================== Chart 2: Volume Trend ======================
def plot_volume(df: pd.DataFrame):
    anoms = df[df["综合异常"]]
    fig, ax = plt.subplots(figsize=(12, 5))
    bar_colors = ["crimson" if r else "steelblue" for r in df["综合异常"]]
    ax.bar(df["日期_dt"], df["日成交量"] / 1e4, color=bar_colors, alpha=0.75, width=0.8)
    ax.scatter(anoms["日期_dt"], anoms["日成交量"] / 1e4,
                 c="red", s=120, zorder=5, edgecolors="darkred", linewidths=2,
                 label=f"Anomaly Days ({len(anoms)})")
    ax.set_title("Figure 2: CEA25 Daily Trading Volume with Anomaly Detection\n(China Carbon Market, Mar-Apr 2026)", fontsize=13, fontweight='bold')
    ax.set_ylabel("Volume (10,000 tons)", fontsize=11)
    ax.set_xlabel("Date", fontsize=11)
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, alpha=0.3, axis='y')
    ax.tick_params(axis='x', rotation=30)
    for _, r in anoms.iterrows():
        ax.annotate(r["日期"][5:], (r["日期_dt"], r["日成交量"] / 1e4),
                     xytext=(0, 6), textcoords="offset points",
                     fontsize=8, color="red", ha="center")
    plt.tight_layout()
    ts = time.strftime("%Y%m%d")
    out_png = os.path.join(IMG_DIR, f"fig2_volume_trend_en_{ts}.png")
    plt.savefig(out_png, dpi=150, bbox_inches="tight")
    print(f"[Saved] {out_png}")
    plt.close()

# ====================== Chart 3: Return Distribution ======================
def plot_distribution(df: pd.DataFrame):
    anoms = df[df["综合异常"]]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(df["涨幅"], bins=20, color="steelblue", edgecolor="white", alpha=0.8, label="All Days")
    for _, r in anoms.iterrows():
        ax.axvline(r["涨幅"], color="red", linestyle="--", linewidth=1.5, alpha=0.9)
    ax.axvline(df["涨幅"].mean(), color="green", linewidth=2,
                label=f"Mean: {df['涨幅'].mean():.2f}%")
    ax.axvline(0, color="black", linewidth=1.2)
    ax.set_title("Figure 3: Daily Return Distribution\n(Red dashed = Anomaly Days)", fontsize=13, fontweight='bold')
    ax.set_xlabel("Daily Return (%)", fontsize=11)
    ax.set_ylabel("Frequency", fontsize=11)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    ts = time.strftime("%Y%m%d")
    out_png = os.path.join(IMG_DIR, f"fig3_return_dist_en_{ts}.png")
    plt.savefig(out_png, dpi=150, bbox_inches="tight")
    print(f"[Saved] {out_png}")
    plt.close()

# ====================== Chart 4: IForest Scatter ======================
def plot_iforest(df: pd.DataFrame):
    anoms = df[df["综合异常"]]
    normal = df[~df["综合异常"]]
    fig, ax = plt.subplots(figsize=(10, 6))
    sc = ax.scatter(normal["日均价"], normal["日成交量"] / 1e4,
                     c=normal["IForest_置信"], cmap="Blues",
                     s=70, alpha=0.7, edgecolors="lightblue", linewidths=0.5,
                     label="Normal Days")
    ax.scatter(anoms["日均价"], anoms["日成交量"] / 1e4,
               c="red", s=150, marker="X", label="Anomaly Days",
               edgecolors="darkred", linewidths=2)
    cbar = plt.colorbar(sc, ax=ax, label="IForest Confidence")
    cbar.ax.tick_params(labelsize=9)
    ax.set_title("Figure 4: Isolation Forest Anomaly Scatter Plot\n(Daily Avg Price vs Trading Volume)", fontsize=13, fontweight='bold')
    ax.set_xlabel("Daily Avg Price (CNY/ton)", fontsize=11)
    ax.set_ylabel("Daily Volume (10,000 tons)", fontsize=11)
    ax.legend(loc="upper right", fontsize=10)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    ts = time.strftime("%Y%m%d")
    out_png = os.path.join(IMG_DIR, f"fig4_iforest_scatter_en_{ts}.png")
    plt.savefig(out_png, dpi=150, bbox_inches="tight")
    print(f"[Saved] {out_png}")
    plt.close()

def main():
    print(f"=== Anomaly Detection Charts (English) {VERSION} ===\n")
    df = load_and_preprocess()
    df = detect_anomalies(df)
    plot_price(df)
    plot_volume(df)
    plot_distribution(df)
    plot_iforest(df)
    print("\n=== All charts generated ===")

if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    main()
