import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.ensemble import IsolationForest
import warnings
warnings.filterwarnings("ignore")

# ===================== 【Basic Configuration】 =====================
csv_path = "cea_2021_10col_final.csv"
window = 15
contamination = 0.05
# ======================================================

# Read data
df = pd.read_csv(csv_path)
print("Your CSV column names:")
print(df.columns.tolist())

# Accurately map the original column names of your table
df = df.rename(columns={
    "日期": "date",
    "收盘价(元/吨)": "close",
    "日成交量(吨)": "volume",
    "日成交额(元)": "amount",
    "交易方式": "type"
})

# Date Cleaning + Null Value Filtering
df["date"] = pd.to_datetime(df["date"], errors="coerce")
df = df.sort_values("date").reset_index(drop=True)
df = df.dropna(subset=["date", "close", "volume", "type"])

# ===================== Public Function for Anomaly Detection =====================
def detect(df_sub, title=""):
    df_sub = df_sub.sort_values("date").set_index("date")

    # 3σ Scroll Anomaly Detection
    df_sub["roll_mean"] = df_sub["close"].rolling(window=window).mean()
    df_sub["roll_std"] = df_sub["close"].rolling(window=window).std()
    df_sub["sigma_outlier"] = np.where(
        (abs(df_sub["close"] - df_sub["roll_mean"]) > 3 * df_sub["roll_std"]) & (df_sub["roll_std"].notna()), 1, 0
    )

    # Isolation Forest Unsupervised Anomaly Detection
    df_sub["if_outlier"] = 0
    feat = ["close", "volume"]
    df_m = df_sub[feat].dropna()
    if len(df_m) > 10:
        model = IsolationForest(contamination=contamination, random_state=42)
        df_m["if_label"] = model.fit_predict(df_m)
        df_sub.loc[df_m.index, "if_outlier"] = (df_m["if_label"] == -1).astype(int)

    # Console print result
    print(f"\n===== {title} - 3σ Outlier Data =====")
    print(df_sub[df_sub["sigma_outlier"] == 1][["close", "volume"]])
    print(f"\n===== {title} - Isolation Forest Outlier Data =====")
    print(df_sub[df_sub["if_outlier"] == 1][["close", "volume"]])

    return df_sub

# ===================== Calculate separately for the three types of scenarios =====================
# 1. Listed for trading only
print("\n" + "="*80)
print("📊 Scenario 1: Listed Trading")
df1 = df[df["type"].str.contains("挂牌", na=False)].copy()
df1 = df1.groupby("date").agg({"close": "last", "volume": "sum"}).reset_index()
df1_result = detect(df1, "Listed Trading")

# 2. Only block trading
print("\n" + "="*80)
print("📊 Scenario 2: Block Trading")
df2 = df[df["type"].str.contains("大宗", na=False)].copy()
df2 = df2.groupby("date").agg({"close": "last", "volume": "sum"}).reset_index()
df2_result = detect(df2, "Block Trading")

# 3. Full Date Merge
print("\n" + "="*80)
print("📊 Scenario 3: Total Merged Trading (All Categories)")
df3 = df.groupby("date").agg({"close": "last", "volume": "sum"}).reset_index()
df3_result = detect(df3, "Total Merged Trading")

# ===================== Font Configuration (English) =====================
plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Helvetica"]
plt.rcParams["axes.unicode_minus"] = False

# ==================================================================================
# =================================== Figure 1：3σ Anomaly Detection ============================
# ==================================================================================
plt.figure(figsize=(16, 9))

plt.subplot(3, 1, 1)
plt.plot(df1_result.index, df1_result["close"], color="#2E86AB")
plt.scatter(df1_result[df1_result["sigma_outlier"]==1].index, df1_result[df1_result["sigma_outlier"]==1]["close"], c="red", s=70, label="3σ Outlier")
plt.title("Listed Trading - 3σ Outlier Detection")
plt.legend()
plt.grid(alpha=0.3)

plt.subplot(3, 1, 2)
plt.plot(df2_result.index, df2_result["close"], color="#A23B72")
plt.scatter(df2_result[df2_result["sigma_outlier"]==1].index, df2_result[df2_result["sigma_outlier"]==1]["close"], c="red", s=70, label="3σ Outlier")
plt.title("Block Trading - 3σ Outlier Detection")
plt.legend()
plt.grid(alpha=0.3)

plt.subplot(3, 1, 3)
plt.plot(df3_result.index, df3_result["close"], color="#F18F01")
plt.scatter(df3_result[df3_result["sigma_outlier"]==1].index, df3_result[df3_result["sigma_outlier"]==1]["close"], c="red", s=70, label="3σ Outlier")
plt.title("Total Merged Trading - 3σ Outlier Detection")
plt.legend()
plt.grid(alpha=0.3)

plt.tight_layout()
plt.savefig("【3σ Outlier Detection】.png", dpi=300, bbox_inches="tight")
print("\n✅ Saved: 3σ Outlier Detection.png")

# ==================================================================================
# =================================== Figure 2：Isolation Forest Anomaly Detection =======================
# ==================================================================================
plt.figure(figsize=(16, 9))

plt.subplot(3, 1, 1)
plt.plot(df1_result.index, df1_result["close"], color="#2E86AB")
plt.scatter(df1_result[df1_result["if_outlier"]==1].index, df1_result[df1_result["if_outlier"]==1]["close"], c="orange", s=90, marker="x", label="Isolation Forest Outlier")
plt.title("Listed Trading - Isolation Forest Outlier Detection")
plt.legend()
plt.grid(alpha=0.3)

plt.subplot(3, 1, 2)
plt.plot(df2_result.index, df2_result["close"], color="#A23B72")
plt.scatter(df2_result[df2_result["if_outlier"]==1].index, df2_result[df2_result["if_outlier"]==1]["close"], c="orange", s=90, marker="x", label="Isolation Forest Outlier")
plt.title("Block Trading - Isolation Forest Outlier Detection")
plt.legend()
plt.grid(alpha=0.3)

plt.subplot(3, 1, 3)
plt.plot(df3_result.index, df3_result["close"], color="#F18F01")
plt.scatter(df3_result[df3_result["if_outlier"]==1].index, df3_result[df3_result["if_outlier"]==1]["close"], c="orange", s=90, marker="x", label="Isolation Forest Outlier")
plt.title("Total Merged Trading - Isolation Forest Outlier Detection")
plt.legend()
plt.grid(alpha=0.3)

plt.tight_layout()
plt.savefig("【Isolation Forest Outlier Detection】.png", dpi=300, bbox_inches="tight")
print("✅ Saved: Isolation Forest Outlier Detection.png")

plt.show()