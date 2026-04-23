import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import pandas as pd

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False


def plot_analysis(result: dict, symbol: str, save_path: str = None):
    df = result["df"]
    fig = plt.figure(figsize=(16, 12))
    fig.suptitle(f"{symbol} AI量化分析报告  |  最新: {result['latest_close']}  |  规则信号: {result['rule_signal']}  |  AI信号: {result['ml_signal']} (准确率{result['ml_accuracy']}%)", fontsize=13, fontweight="bold")

    gs = gridspec.GridSpec(4, 2, figure=fig, hspace=0.45, wspace=0.3)

    # --- K线 + 均线 + 布林带 ---
    ax1 = fig.add_subplot(gs[0:2, 0])
    ax1.plot(df.index, df["Close"], label="收盘价", color="#1f77b4", linewidth=1.5)
    ax1.plot(df.index, df["MA5"], label="MA5", linestyle="--", linewidth=1)
    ax1.plot(df.index, df["MA20"], label="MA20", linestyle="--", linewidth=1)
    ax1.plot(df.index, df["MA60"], label="MA60", linestyle="--", linewidth=1)
    ax1.fill_between(df.index, df["BB_Upper"], df["BB_Lower"], alpha=0.1, color="gray", label="布林带")
    ax1.set_title("价格 & 均线 & 布林带")
    ax1.legend(fontsize=7)
    ax1.grid(alpha=0.3)

    # --- 成交量 ---
    ax2 = fig.add_subplot(gs[2, 0])
    colors = ["#d62728" if c >= o else "#2ca02c" for c, o in zip(df["Close"], df["Open"])]
    ax2.bar(df.index, df["Volume"], color=colors, alpha=0.7, width=1)
    ax2.plot(df.index, df["Vol_MA20"], color="orange", linewidth=1, label="Vol MA20")
    ax2.set_title("成交量")
    ax2.legend(fontsize=7)
    ax2.grid(alpha=0.3)

    # --- RSI ---
    ax3 = fig.add_subplot(gs[3, 0])
    ax3.plot(df.index, df["RSI"], color="purple", linewidth=1.2)
    ax3.axhline(70, color="red", linestyle="--", linewidth=0.8, label="超买70")
    ax3.axhline(30, color="green", linestyle="--", linewidth=0.8, label="超卖30")
    ax3.fill_between(df.index, df["RSI"], 70, where=(df["RSI"] >= 70), alpha=0.3, color="red")
    ax3.fill_between(df.index, df["RSI"], 30, where=(df["RSI"] <= 30), alpha=0.3, color="green")
    ax3.set_ylim(0, 100)
    ax3.set_title("RSI")
    ax3.legend(fontsize=7)
    ax3.grid(alpha=0.3)

    # --- MACD ---
    ax4 = fig.add_subplot(gs[0:2, 1])
    ax4.plot(df.index, df["MACD"], label="MACD", color="blue", linewidth=1.2)
    ax4.plot(df.index, df["MACD_Signal"], label="Signal", color="orange", linewidth=1.2)
    hist_colors = ["#d62728" if v >= 0 else "#2ca02c" for v in df["MACD_Hist"]]
    ax4.bar(df.index, df["MACD_Hist"], color=hist_colors, alpha=0.5, width=1, label="Hist")
    ax4.axhline(0, color="black", linewidth=0.5)
    ax4.set_title("MACD")
    ax4.legend(fontsize=7)
    ax4.grid(alpha=0.3)

    # --- AI 概率饼图 ---
    ax5 = fig.add_subplot(gs[2, 1])
    proba = result["ml_proba"]
    labels = list(proba.keys())
    sizes = list(proba.values())
    colors_pie = ["#2ca02c", "#aec7e8", "#d62728"]
    wedges, texts, autotexts = ax5.pie(sizes, labels=labels, autopct="%1.1f%%", colors=colors_pie, startangle=90)
    ax5.set_title(f"AI预测概率 (准确率 {result['ml_accuracy']}%)")

    # --- 特征重要性 ---
    ax6 = fig.add_subplot(gs[3, 1])
    fi = result["feature_importance"].head(8)
    ax6.barh(fi.index[::-1], fi.values[::-1], color="#1f77b4", alpha=0.8)
    ax6.set_title("特征重要性 (Top 8)")
    ax6.grid(alpha=0.3, axis="x")

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"[图表] 已保存至: {save_path}")
    else:
        plt.show()
    plt.close()
