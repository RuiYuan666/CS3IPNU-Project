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
print("Your CSV column names：")
print(df.columns.tolist())

# Precisely map original column names of your table
df = df.rename(columns={
    "日期": "date",
    "收盘价(元/吨)": "close",
    "日成交量(吨)": "volume",
    "日成交额(元)": "amount",
    "交易方式": "type"
})

# Date cleaning + null value filtering
df["date"] = pd.to_datetime(df["date"], errors="coerce")
df = df.sort_values("date").reset_index(drop=True)
df = df.dropna(subset=["date", "close", "volume", "type"])

# ===================== Anomaly Detection Common Function =====================
def detect(df_sub, title=""):
    df_sub = df_sub.sort_values("date").set_index("date")

    # 3σ rolling anomaly detection
    df_sub["roll_mean"] = df_sub["close"].rolling(window=window).mean()
    df_sub["roll_std"] = df_sub["close"].rolling(window=window).std()
    df_sub["sigma_outlier"] = np.where(
        (abs(df_sub["close"] - df_sub["roll_mean"]) > 3 * df_sub["roll_std"]) & (df_sub["roll_std"].notna()), 1, 0
    )

    # Isolation Forest unsupervised anomaly detection
    df_sub["if_outlier"] = 0
    feat = ["close", "volume"]
    df_m = df_sub[feat].dropna()
    if len(df_m) > 10:
        model = IsolationForest(contamination=contamination, random_state=42)
        df_m["if_label"] = model.fit_predict(df_m)
        df_sub.loc[df_m.index, "if_outlier"] = (df_m["if_label"] == -1).astype(int)

    # Print results to console
    print(f"\n===== {title} - 3σ Anomaly Data =====")
    print(df_sub[df_sub["sigma_outlier"] == 1][["close", "volume"]])
    print(f"\n===== {title} - Isolation Forest Anomaly Data =====")
    print(df_sub[df_sub["if_outlier"] == 1][["close", "volume"]])
    return df_sub

# ===================== Calculate for Three Scenarios Separately =====================
# 1. Listing transactions only
print("\n" + "="*80)
print("📊 Scenario 1：Listing Transactions")
df1 = df[df["type"].str.contains("挂牌", na=False)].copy()
df1 = df1.groupby("date").agg({"close": "last", "volume": "sum"}).reset_index()
df1_result = detect(df1, "Listing Transactions")

# 2. Block transactions only
print("\n" + "="*80)
print("📊 Scenario 2：Block Transactions")
df2 = df[df["type"].str.contains("大宗", na=False)].copy()
df2 = df2.groupby("date").agg({"close": "last", "volume": "sum"}).reset_index()
df2_result = detect(df2, "Block Transactions")

# 3. Full date merge
print("\n" + "="*80)
print("📊 Scenario 3：Total Merged Volume of All Categories by Date")
df3 = df.groupby("date").agg({"close": "last", "volume": "sum"}).reset_index()
df3_result = detect(df3, "Full Merged Transactions")

# ===================== Plotting + Auto-save Image =====================
# Configure font for English display (remove Chinese font settings)
plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

plt.figure(figsize=(16, 9))

# Subplot 1：Listing Transactions
plt.subplot(3, 1, 1)
plt.plot(df1_result.index, df1_result["close"], label="Listing Carbon Price", color="#2E86AB")
plt.scatter(df1_result[df1_result["sigma_outlier"]==1].index,
            df1_result[df1_result["sigma_outlier"]==1]["close"],
            c="red", s=60, label="3σ Anomaly Points")
plt.title("Listing Transactions - Carbon Price Anomaly Detection")
plt.legend()
plt.grid(alpha=0.3)

# Subplot 2：Block Transactions
plt.subplot(3, 1, 2)
plt.plot(df2_result.index, df2_result["close"], label="Block Carbon Price", color="#A23B72")
plt.scatter(df2_result[df2_result["sigma_outlier"]==1].index,
            df2_result[df2_result["sigma_outlier"]==1]["close"],
            c="red", s=60, label="3σ Anomaly Points")
plt.title("Block Transactions - Carbon Price Anomaly Detection")
plt.legend()
plt.grid(alpha=0.3)

# Subplot 3：Merged Transactions
plt.subplot(3, 1, 3)
plt.plot(df3_result.index, df3_result["close"], label="Merged Carbon Price", color="#F18F01")
plt.scatter(df3_result[df3_result["sigma_outlier"]==1].index,
            df3_result[df3_result["sigma_outlier"]==1]["close"],
            c="red", s=60, label="3σ Anomaly Points")
plt.title("All Categories Merged - Carbon Price Anomaly Detection")
plt.legend()
plt.grid(alpha=0.3)

plt.tight_layout()

# Key: Save image to current folder (high resolution 300dpi)
plt.savefig("Carbon_Trading_Anomaly_Detection_Result.png", dpi=300, bbox_inches="tight")
print("\n✅ Image saved to current folder：Carbon_Trading_Anomaly_Detection_Result.png")

# Display image in popup window
plt.show()