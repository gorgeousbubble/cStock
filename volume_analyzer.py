"""
量价分析模块
OBV、VWAP、成交量背离、筹码分布、资金流向
"""
import numpy as np
import pandas as pd


def calc_obv(df: pd.DataFrame) -> pd.Series:
    """On-Balance Volume"""
    obv = [0]
    for i in range(1, len(df)):
        if df["Close"].iloc[i] > df["Close"].iloc[i-1]:
            obv.append(obv[-1] + df["Volume"].iloc[i])
        elif df["Close"].iloc[i] < df["Close"].iloc[i-1]:
            obv.append(obv[-1] - df["Volume"].iloc[i])
        else:
            obv.append(obv[-1])
    return pd.Series(obv, index=df.index)


def calc_vwap(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """成交量加权均价（滚动窗口）"""
    typical = (df["High"] + df["Low"] + df["Close"]) / 3
    vwap = (typical * df["Volume"]).rolling(window).sum() / df["Volume"].rolling(window).sum()
    return vwap


def calc_mfi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """资金流量指标 Money Flow Index"""
    typical = (df["High"] + df["Low"] + df["Close"]) / 3
    raw_mf  = typical * df["Volume"]
    pos_mf  = raw_mf.where(typical > typical.shift(1), 0)
    neg_mf  = raw_mf.where(typical < typical.shift(1), 0)
    mfr     = pos_mf.rolling(period).sum() / neg_mf.rolling(period).sum().replace(0, np.nan)
    return 100 - (100 / (1 + mfr))


def detect_volume_divergence(df: pd.DataFrame) -> list:
    """量价背离检测"""
    signals = []
    close  = df["Close"]
    volume = df["Volume"]
    n      = len(df)
    if n < 20:
        return signals

    # 近20日价格和成交量趋势
    price_trend  = close.iloc[-1] - close.iloc[-20]
    volume_trend = volume.iloc[-5:].mean() - volume.iloc[-20:-5].mean()

    # 顶背离：价格创新高但成交量萎缩
    if close.iloc[-1] >= close.iloc[-20:].max() * 0.99 and volume_trend < 0:
        signals.append({
            "类型": "顶背离",
            "信号": "🔴 看跌",
            "说明": "价格创近期新高但成交量萎缩，上涨动能不足，警惕回调"
        })

    # 底背离：价格创新低但成交量萎缩
    if close.iloc[-1] <= close.iloc[-20:].min() * 1.01 and volume_trend < 0:
        signals.append({
            "类型": "底背离",
            "信号": "🟢 看涨",
            "说明": "价格创近期新低但成交量萎缩，下跌动能减弱，可能反转"
        })

    # 放量上涨
    vol_ratio = volume.iloc[-1] / volume.iloc[-20:].mean()
    if vol_ratio > 2.0 and close.iloc[-1] > close.iloc[-2]:
        signals.append({
            "类型": "放量上涨",
            "信号": "🟢 看涨",
            "说明": f"成交量是均量的 {vol_ratio:.1f}x，资金大量涌入，强势信号"
        })

    # 放量下跌
    if vol_ratio > 2.0 and close.iloc[-1] < close.iloc[-2]:
        signals.append({
            "类型": "放量下跌",
            "信号": "🔴 看跌",
            "说明": f"成交量是均量的 {vol_ratio:.1f}x，资金大量出逃，恐慌信号"
        })

    # 缩量上涨（弱势）
    if vol_ratio < 0.5 and close.iloc[-1] > close.iloc[-5:].mean():
        signals.append({
            "类型": "缩量上涨",
            "信号": "⚠️ 警惕",
            "说明": "价格上涨但成交量萎缩，上涨缺乏支撑，可信度低"
        })

    return signals


def calc_chip_distribution(df: pd.DataFrame, bins: int = 20) -> dict:
    """
    筹码分布（成交量在价格上的分布）
    模拟历史成交量在各价格区间的累积
    """
    close  = df["Close"].values
    volume = df["Volume"].values
    n      = len(close)

    price_min = float(np.min(close))
    price_max = float(np.max(close))
    price_bins = np.linspace(price_min, price_max, bins + 1)
    chip_dist  = np.zeros(bins)

    # 衰减因子：越近期的成交量权重越高
    decay = np.exp(-np.arange(n)[::-1] / (n * 0.3))

    for i in range(n):
        bin_idx = min(int((close[i] - price_min) / (price_max - price_min + 1e-9) * bins), bins - 1)
        chip_dist[bin_idx] += volume[i] * decay[i]

    chip_dist = chip_dist / chip_dist.sum() * 100  # 归一化为百分比

    # 找筹码峰（成本密集区）
    peak_idx = int(np.argmax(chip_dist))
    peak_price = round(float((price_bins[peak_idx] + price_bins[peak_idx+1]) / 2), 2)

    current = float(close[-1])
    # 套牢盘比例（持仓成本高于当前价的筹码）
    trapped_pct = round(float(chip_dist[peak_idx+1:].sum()), 1) if peak_idx < bins-1 else 0
    profit_pct  = round(float(chip_dist[:peak_idx+1].sum()), 1)

    return {
        "bins":        bins,
        "price_bins":  [(round(float(price_bins[i]),2), round(float(price_bins[i+1]),2)) for i in range(bins)],
        "chip_dist":   chip_dist.tolist(),
        "peak_price":  peak_price,
        "trapped_pct": trapped_pct,
        "profit_pct":  profit_pct,
        "current":     current,
        "signal":      "bullish" if profit_pct > 60 else ("bearish" if trapped_pct > 60 else "neutral"),
    }


def analyze_volume(df: pd.DataFrame) -> dict:
    obv  = calc_obv(df)
    vwap = calc_vwap(df)
    mfi  = calc_mfi(df)

    latest_obv  = float(obv.iloc[-1])
    latest_vwap = round(float(vwap.iloc[-1]), 2)
    latest_mfi  = round(float(mfi.iloc[-1]), 1)
    latest_price = float(df["Close"].iloc[-1])

    # OBV 趋势
    obv_trend = "上升" if obv.iloc[-1] > obv.iloc[-20] else "下降"
    obv_signal = "bullish" if obv_trend == "上升" else "bearish"

    # VWAP 信号
    vwap_signal = "bullish" if latest_price > latest_vwap else "bearish"
    vwap_pct    = round((latest_price / latest_vwap - 1) * 100, 2)

    # MFI 信号
    mfi_signal = "超买" if latest_mfi > 80 else ("超卖" if latest_mfi < 20 else "正常")

    return {
        "obv":              obv,
        "vwap":             vwap,
        "mfi":              mfi,
        "latest_vwap":      latest_vwap,
        "vwap_pct":         vwap_pct,
        "vwap_signal":      vwap_signal,
        "latest_mfi":       latest_mfi,
        "mfi_signal":       mfi_signal,
        "obv_trend":        obv_trend,
        "obv_signal":       obv_signal,
        "divergence":       detect_volume_divergence(df),
        "chip":             calc_chip_distribution(df),
    }
