import pandas as pd
import numpy as np
from config import RSI_PERIOD, MACD_FAST, MACD_SLOW, MACD_SIGNAL, BB_PERIOD, BB_STD, MA_PERIODS


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    data  = df.copy()
    close = data["Close"]
    n     = len(close)

    # 移动平均线 — 数据不足时用可用最大窗口
    for p in MA_PERIODS:
        actual_p = min(p, n)
        data[f"MA{p}"] = close.rolling(actual_p, min_periods=1).mean()

    # RSI
    rsi_p = min(RSI_PERIOD, n - 1)
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(rsi_p, min_periods=1).mean()
    loss  = (-delta.clip(upper=0)).rolling(rsi_p, min_periods=1).mean()
    data["RSI"] = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))
    data["RSI"] = data["RSI"].fillna(50)  # 数据不足时填充中性值

    # MACD
    ema_fast = close.ewm(span=min(MACD_FAST, n), adjust=False).mean()
    ema_slow = close.ewm(span=min(MACD_SLOW, n), adjust=False).mean()
    data["MACD"]        = ema_fast - ema_slow
    data["MACD_Signal"] = data["MACD"].ewm(span=min(MACD_SIGNAL, n), adjust=False).mean()
    data["MACD_Hist"]   = data["MACD"] - data["MACD_Signal"]

    # 布林带
    bb_p = min(BB_PERIOD, n)
    ma   = close.rolling(bb_p, min_periods=1).mean()
    std  = close.rolling(bb_p, min_periods=1).std().fillna(0)
    data["BB_Upper"] = ma + BB_STD * std
    data["BB_Lower"] = ma - BB_STD * std
    data["BB_Mid"]   = ma

    # 成交量均线
    data["Vol_MA20"] = data["Volume"].rolling(min(20, n), min_periods=1).mean()

    # 只删除真正无法计算的行（不再因MA60删掉所有数据）
    return data.dropna(subset=["MACD", "RSI", "BB_Upper"])
