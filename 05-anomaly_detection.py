#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Anomaly Detection Charts for CRC Carbon Market Data
Data source: CRC_Carbon_Market_v7.csv (from sync_crc.py)
Output: same directory as this script
"""
import os, time, warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.ensemble import IsolationForest

VERSION = "v2.0-en"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE  = os.path.normpath(os.path.join(SCRIPT_DIR, os.pardir, "CRC_Carbon_Market_v7.csv"))

plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

IFOREST_N = 128

def norm_date(s):
    """Normalize date to YYYY-MM-DD"""
    parts = s.strip().split('-')
    return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"

def load_and_preprocess():
    """Load CRC data and aggregate to daily OHLCV"""
    df = pd.read_csv(DATA_FILE, encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]

    # Aggregate by Date: price fields are same across TradeTypes, Volume/Amount sum
    agg = df.groupby("Date").agg(
        Open   = ("Close", "first"),   # proxy: previous day Close (filled below)
        High   = ("High", "max"),
        Low    = ("Low", "min"),
        Close  = ("Close", "last"),
        Volume = ("Volume", "sum"),
        Amount = ("Amount", "sum"),
    ).reset_index()

    agg = agg.sort_values("Date").reset_index(drop=True)

    # Open = previous day Close (CRC has no explicit open price)
    agg["Open"] = agg["Close"].shift(1).fillna(agg["Close"].iloc[0])

    # Daily average price
    agg["DailyAvg"] = agg["Amount"] / agg["Volume"]

    # Return: (Close - Open) / Open * 100
    agg["Return"] = (agg["Close"] - agg["Open"]) / agg["Open"] * 100
    agg["Return"] = agg["Return"].clip(-50, 50)

    agg["Date_dt"] = pd.to_datetime(agg["Date"])
    print(f"[Data] {len(agg)} trading days ({agg['Date'].min()} ~ {agg['Date'].max()})")
    return agg

def detect_anomalies(agg):
    """3-sigma + IsolationForest anomaly detection"""
    result = agg.copy()
    mu    = result["DailyAvg"].mean()
    sigma = result["DailyAvg"].std()
    result["Sigma3_Lower"] = mu - 3 * sigma
    result["Sigma3_Upper"] = mu + 3 * sigma
    result["Sigma3_Anomaly"] = (
        (result["DailyAvg"] < mu - 3 * sigma) |
        (result["DailyAvg"] > mu + 3 * sigma)
    )

    feat = result[["DailyAvg", "Volume", "Return", "Amount"]].copy()
    for col in feat.columns:
        m, s = feat[col].mean(), feat[col].std()
        if s > 0:
            feat[col] = (feat[col] - m) / s

    clf = IsolationForest(n_estimators=IFOREST_N, contamination=0.1, random_state=42, n_jobs=-1)
    labels = clf.fit_predict(feat)
    scores = clf.decision_function(feat)
    result["IForest_Label"] = (labels == -1).astype(int)
    result["IForest_Score"] = scores
    result["IForest_Conf"] = 1 - (scores - scores.min()) / (scores.max() - scores.min() + 1e-9)

    result["Combined_Anomaly"] = result["Sigma3_Anomaly"] | (result["IForest_Label"] == -1)
    result["AnomalyLevel"] = "Normal"
    result.loc[result["Sigma3_Anomaly"] & (result["IForest_Label"] == -1), "AnomalyLevel"] = "Severe"
    result.loc[(result["IForest_Label"] == -1) & ~result["Sigma3_Anomaly"], "AnomalyLevel"] = "Mild"

    n_sigma = result["Sigma3_Anomaly"].sum()
    n_iforest = (result["IForest_Label"] == -1).sum()
    n_combined = result["Combined_Anomaly"].sum()
    print(f"[Detection] 3-sigma: {n_sigma}, IForest: {n_iforest}, Combined: {n_combined}")
    return result

# ====================== Chart 1: Price Trend ======================
def plot_price(df: pd.DataFrame):
    anoms = df[df["Combined_Anomaly"]]
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(df["Date_dt"], df["Close"], "b-", linewidth=1.8, label="Closing Price", zorder=2)
    ax.fill_between(df["Date_dt"], df["Low"], df["High"],
                    alpha=0.15, color="blue", label="Daily Range")
    ax.axhline(df["Sigma3_Upper"].iloc[0], color="green", linestyle="--",
                linewidth=1.5, alpha=0.8,
                label=f"3-sigma Upper: {df['Sigma3_Upper'].iloc[0]:.2f}")
    ax.axhline(df["Sigma3_Lower"].iloc[0], color="green", linestyle="--",
                linewidth=1.5, alpha=0.8,
                label=f"3-sigma Lower: {df['Sigma3_Lower'].iloc[0]:.2f}")
    ax.scatter(anoms["Date_dt"], anoms["Close"], c="red", s=150,
                zorder=5, label=f"Anomalies ({len(anoms)})",
                edgecolors="darkred", linewidths=2)
    for _, r in anoms.iterrows():
        ax.annotate(r["Date"][5:], (r["Date_dt"], r["Close"]),
                     xytext=(0, 10), textcoords="offset points",
                     fontsize=9, color="red", ha="center", fontweight='bold')
    ax.set_title("Chart 1: CEA Daily Closing Price with Anomaly Detection\n(CRC Carbon Market, 2026)", fontsize=13, fontweight='bold')
    ax.set_ylabel("Price (CNY/ton)", fontsize=11)
    ax.set_xlabel("Date", fontsize=11)
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.tick_params(axis='x', rotation=30)
    plt.tight_layout()
    out_png = os.path.join(SCRIPT_DIR, "fig1_price_trend.png")
    plt.savefig(out_png, dpi=150, bbox_inches="tight")
    print(f"[Saved] {out_png}")
    plt.close()

# ====================== Chart 2: Volume Trend ======================
def plot_volume(df: pd.DataFrame):
    anoms = df[df["Combined_Anomaly"]]
    fig, ax = plt.subplots(figsize=(12, 5))
    bar_colors = ["crimson" if r else "steelblue" for r in df["Combined_Anomaly"]]
    ax.bar(df["Date_dt"], df["Volume"] / 1e4, color=bar_colors, alpha=0.75, width=0.8)
    ax.scatter(anoms["Date_dt"], anoms["Volume"] / 1e4,
                c="red", s=120, zorder=5, edgecolors="darkred", linewidths=2,
                label=f"Anomaly Days ({len(anoms)})")
    for _, r in anoms.iterrows():
        ax.annotate(r["Date"][5:], (r["Date_dt"], r["Volume"] / 1e4),
                     xytext=(0, 6), textcoords="offset points",
                     fontsize=8, color="red", ha="center")
    ax.set_title("Chart 2: CEA Daily Trading Volume with Anomaly Detection\n(CRC Carbon Market, 2026)", fontsize=13, fontweight='bold')
    ax.set_ylabel("Volume (10,000 tons)", fontsize=11)
    ax.set_xlabel("Date", fontsize=11)
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, alpha=0.3, axis='y')
    ax.tick_params(axis='x', rotation=30)
    plt.tight_layout()
    out_png = os.path.join(SCRIPT_DIR, "fig2_volume_trend.png")
    plt.savefig(out_png, dpi=150, bbox_inches="tight")
    print(f"[Saved] {out_png}")
    plt.close()

# ====================== Chart 3: Return Distribution ======================
def plot_distribution(df: pd.DataFrame):
    anoms = df[df["Combined_Anomaly"]]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(df["Return"], bins=20, color="steelblue", edgecolor="white", alpha=0.8, label="All Days")
    for _, r in anoms.iterrows():
        ax.axvline(r["Return"], color="red", linestyle="--", linewidth=1.5, alpha=0.9)
    ax.axvline(df["Return"].mean(), color="green", linewidth=2,
                label=f"Mean: {df['Return'].mean():.2f}%")
    ax.axvline(0, color="black", linewidth=1.2)
    ax.set_title("Chart 3: Daily Return Distribution\n(Red dashed = Anomaly Days)", fontsize=13, fontweight='bold')
    ax.set_xlabel("Daily Return (%)", fontsize=11)
    ax.set_ylabel("Frequency", fontsize=11)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    out_png = os.path.join(SCRIPT_DIR, "fig3_return_dist.png")
    plt.savefig(out_png, dpi=150, bbox_inches="tight")
    print(f"[Saved] {out_png}")
    plt.close()

# ====================== Chart 4: IForest Scatter ======================
def plot_iforest(df: pd.DataFrame):
    anoms = df[df["Combined_Anomaly"]]
    normal = df[~df["Combined_Anomaly"]]
    fig, ax = plt.subplots(figsize=(10, 6))
    sc = ax.scatter(normal["DailyAvg"], normal["Volume"] / 1e4,
                     c=normal["IForest_Conf"], cmap="Blues",
                     s=70, alpha=0.7, edgecolors="lightblue", linewidths=0.5,
                     label="Normal Days")
    ax.scatter(anoms["DailyAvg"], anoms["Volume"] / 1e4,
               c="red", s=150, marker="X", label="Anomaly Days",
               edgecolors="darkred", linewidths=2)
    cbar = plt.colorbar(sc, ax=ax, label="IForest Confidence")
    cbar.ax.tick_params(labelsize=9)
    ax.set_title("Chart 4: Isolation Forest Anomaly Scatter\n(Daily Avg Price vs Volume)", fontsize=13, fontweight='bold')
    ax.set_xlabel("Daily Avg Price (CNY/ton)", fontsize=11)
    ax.set_ylabel("Daily Volume (10,000 tons)", fontsize=11)
    ax.legend(loc="upper right", fontsize=10)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    out_png = os.path.join(SCRIPT_DIR, "fig4_iforest_scatter.png")
    plt.savefig(out_png, dpi=150, bbox_inches="tight")
    print(f"[Saved] {out_png}")
    plt.close()

def main():
    print(f"=== Anomaly Detection Charts {VERSION} ===\n")
    print(f"Data source: {DATA_FILE}\n")

    agg = load_and_preprocess()
    result = detect_anomalies(agg)

    # Save anomaly detection result CSV to script directory
    out_cols = ["Date", "Open", "High", "Low", "Close", "Volume", "Amount",
                "DailyAvg", "Return", "Sigma3_Upper", "Sigma3_Lower",
                "Sigma3_Anomaly", "IForest_Label", "IForest_Conf",
                "Combined_Anomaly", "AnomalyLevel"]
    out_csv = os.path.join(SCRIPT_DIR, "anomaly_detection_result.csv")
    result[out_cols].to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"[Saved] {out_csv}")

    plot_price(result)
    plot_volume(result)
    plot_distribution(result)
    plot_iforest(result)
    print("\n=== All charts generated ===")

if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    main()
