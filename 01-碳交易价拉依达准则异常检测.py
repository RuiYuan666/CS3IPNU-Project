import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.ensemble import IsolationForest
import warnings
warnings.filterwarnings("ignore")

# ===================== 【基础配置】 =====================
csv_path = "cea_2021_10col_final.csv"
window = 15
contamination = 0.05
# ======================================================

# 读取数据
df = pd.read_csv(csv_path)
print("你的 CSV 列名：")
print(df.columns.tolist())

# 精准映射你表格的原始列名
df = df.rename(columns={
    "日期": "date",
    "收盘价(元/吨)": "close",
    "日成交量(吨)": "volume",
    "日成交额(元)": "amount",
    "交易方式": "type"
})

# 日期清洗 + 空值过滤
df["date"] = pd.to_datetime(df["date"], errors="coerce")
df = df.sort_values("date").reset_index(drop=True)
df = df.dropna(subset=["date", "close", "volume", "type"])

# ===================== 异常检测公共函数 =====================
def detect(df_sub, title=""):
    df_sub = df_sub.sort_values("date").set_index("date")

    # 3σ 滚动异常检测
    df_sub["roll_mean"] = df_sub["close"].rolling(window=window).mean()
    df_sub["roll_std"] = df_sub["close"].rolling(window=window).std()
    df_sub["sigma_outlier"] = np.where(
        (abs(df_sub["close"] - df_sub["roll_mean"]) > 3 * df_sub["roll_std"]) & (df_sub["roll_std"].notna()), 1, 0
    )

    # 孤立森林 无监督异常检测
    df_sub["if_outlier"] = 0
    feat = ["close", "volume"]
    df_m = df_sub[feat].dropna()
    if len(df_m) > 10:
        model = IsolationForest(contamination=contamination, random_state=42)
        df_m["if_label"] = model.fit_predict(df_m)
        df_sub.loc[df_m.index, "if_outlier"] = (df_m["if_label"] == -1).astype(int)

    # 控制台打印结果
    print(f"\n===== {title} - 3σ 异常数据 =====")
    print(df_sub[df_sub["sigma_outlier"] == 1][["close", "volume"]])
    print(f"\n===== {title} - 孤立森林 异常数据 =====")
    print(df_sub[df_sub["if_outlier"] == 1][["close", "volume"]])
    return df_sub

# ===================== 三类场景分别计算 =====================
# 1. 仅挂牌交易
print("\n" + "="*80)
print("📊 情况1：挂牌交易")
df1 = df[df["type"].str.contains("挂牌", na=False)].copy()
df1 = df1.groupby("date").agg({"close": "last", "volume": "sum"}).reset_index()
df1_result = detect(df1, "挂牌交易")

# 2. 仅大宗交易
print("\n" + "="*80)
print("📊 情况2：大宗交易")
df2 = df[df["type"].str.contains("大宗", na=False)].copy()
df2 = df2.groupby("date").agg({"close": "last", "volume": "sum"}).reset_index()
df2_result = detect(df2, "大宗交易")

# 3. 全量日期合并
print("\n" + "="*80)
print("📊 情况3：全品类日期合并总量")
df3 = df.groupby("date").agg({"close": "last", "volume": "sum"}).reset_index()
df3_result = detect(df3, "全量合并交易")

# ===================== 绘图 + 自动保存图片 =====================
# 解决中文、负号乱码
plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False

plt.figure(figsize=(16, 9))

# 子图1：挂牌
plt.subplot(3, 1, 1)
plt.plot(df1_result.index, df1_result["close"], label="挂牌碳价", color="#2E86AB")
plt.scatter(df1_result[df1_result["sigma_outlier"]==1].index,
            df1_result[df1_result["sigma_outlier"]==1]["close"],
            c="red", s=60, label="3σ异常点")
plt.title("挂牌交易 - 碳价异常检测")
plt.legend()
plt.grid(alpha=0.3)

# 子图2：大宗
plt.subplot(3, 1, 2)
plt.plot(df2_result.index, df2_result["close"], label="大宗碳价", color="#A23B72")
plt.scatter(df2_result[df2_result["sigma_outlier"]==1].index,
            df2_result[df2_result["sigma_outlier"]==1]["close"],
            c="red", s=60, label="3σ异常点")
plt.title("大宗交易 - 碳价异常检测")
plt.legend()
plt.grid(alpha=0.3)

# 子图3：合并
plt.subplot(3, 1, 3)
plt.plot(df3_result.index, df3_result["close"], label="合并碳价", color="#F18F01")
plt.scatter(df3_result[df3_result["sigma_outlier"]==1].index,
            df3_result[df3_result["sigma_outlier"]==1]["close"],
            c="red", s=60, label="3σ异常点")
plt.title("全品类合并 - 碳价异常检测")
plt.legend()
plt.grid(alpha=0.3)

plt.tight_layout()

# 关键：保存图片到当前文件夹（高清300dpi）
plt.savefig("碳交易价拉依达准则异常检测结果图.png", dpi=300, bbox_inches="tight")
print("\n✅ 图片已保存至当前文件夹：碳交易异常检测结果图.png")

# 弹窗展示图片
plt.show()