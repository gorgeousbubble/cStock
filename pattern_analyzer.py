"""
K线形态识别模块
识别经典K线形态：锤子线、吞没、十字星、头肩顶/底、双顶/底、趋势线等
"""
import numpy as np
import pandas as pd


# ── 单根K线形态 ───────────────────────────────────────────
def _body(row):   return abs(row["Close"] - row["Open"])
def _upper(row):  return row["High"] - max(row["Close"], row["Open"])
def _lower(row):  return min(row["Close"], row["Open"]) - row["Low"]
def _is_bull(row): return row["Close"] > row["Open"]
def _is_bear(row): return row["Close"] < row["Open"]


def detect_single_candles(df: pd.DataFrame) -> pd.DataFrame:
    """识别最近20根K线的单根形态"""
    results = []
    tail = df.tail(20).copy()
    for i, (idx, row) in enumerate(tail.iterrows()):
        body   = _body(row)
        upper  = _upper(row)
        lower  = _lower(row)
        total  = row["High"] - row["Low"]
        if total == 0:
            continue
        body_ratio  = body / total
        upper_ratio = upper / total
        lower_ratio = lower / total

        patterns = []

        # 锤子线（看涨反转）：下影线长，实体小，在下跌趋势末端
        if lower_ratio > 0.6 and body_ratio < 0.3 and upper_ratio < 0.1:
            patterns.append(("锤子线", "bullish", "下跌末端出现，看涨反转信号"))

        # 上吊线（看跌）：与锤子线形态相同但在上涨趋势末端
        if lower_ratio > 0.6 and body_ratio < 0.3 and upper_ratio < 0.1:
            if i > 3 and tail["Close"].iloc[max(0,i-3):i].mean() < row["Close"]:
                patterns[-1] = ("上吊线", "bearish", "上涨末端出现，看跌反转信号")

        # 射击之星（看跌）：上影线长，实体小
        if upper_ratio > 0.6 and body_ratio < 0.3 and lower_ratio < 0.1:
            patterns.append(("射击之星", "bearish", "上涨末端出现，看跌反转信号"))

        # 十字星（不确定）：实体极小
        if body_ratio < 0.05:
            patterns.append(("十字星", "neutral", "多空平衡，趋势可能反转"))

        # 长实体阳线（看涨）
        if _is_bull(row) and body_ratio > 0.7:
            patterns.append(("大阳线", "bullish", "强势上涨，多头主导"))

        # 长实体阴线（看跌）
        if _is_bear(row) and body_ratio > 0.7:
            patterns.append(("大阴线", "bearish", "强势下跌，空头主导"))

        for pat, signal, desc in patterns:
            results.append({
                "日期":   str(idx)[:10],
                "形态":   pat,
                "信号":   "🟢 看涨" if signal == "bullish" else ("🔴 看跌" if signal == "bearish" else "🟡 中性"),
                "收盘价": round(float(row["Close"]), 2),
                "说明":   desc,
            })

    return pd.DataFrame(results) if results else pd.DataFrame(
        columns=["日期", "形态", "信号", "收盘价", "说明"])


# ── 双根K线形态 ───────────────────────────────────────────
def detect_double_candles(df: pd.DataFrame) -> list:
    results = []
    tail = df.tail(30)
    for i in range(1, len(tail)):
        prev = tail.iloc[i-1]
        curr = tail.iloc[i]
        date = str(tail.index[i])[:10]

        prev_body = _body(prev)
        curr_body = _body(curr)

        # 看涨吞没：前阴后阳，阳线实体完全覆盖阴线
        if (_is_bear(prev) and _is_bull(curr) and
                curr["Open"] < prev["Close"] and curr["Close"] > prev["Open"]):
            results.append({"日期": date, "形态": "看涨吞没", "信号": "🟢 看涨",
                             "说明": "强烈看涨反转，阳线吞没前阴线"})

        # 看跌吞没：前阳后阴，阴线实体完全覆盖阳线
        if (_is_bull(prev) and _is_bear(curr) and
                curr["Open"] > prev["Close"] and curr["Close"] < prev["Open"]):
            results.append({"日期": date, "形态": "看跌吞没", "信号": "🔴 看跌",
                             "说明": "强烈看跌反转，阴线吞没前阳线"})

        # 孕线（看涨）：前大阴，后小阳包含在前阴实体内
        if (_is_bear(prev) and _is_bull(curr) and
                curr["Open"] > prev["Close"] and curr["Close"] < prev["Open"] and
                curr_body < prev_body * 0.5):
            results.append({"日期": date, "形态": "看涨孕线", "信号": "🟢 看涨",
                             "说明": "下跌趋势中出现，可能反转"})

        # 孕线（看跌）：前大阳，后小阴包含在前阳实体内
        if (_is_bull(prev) and _is_bear(curr) and
                curr["Open"] < prev["Close"] and curr["Close"] > prev["Open"] and
                curr_body < prev_body * 0.5):
            results.append({"日期": date, "形态": "看跌孕线", "信号": "🔴 看跌",
                             "说明": "上涨趋势中出现，可能反转"})

    return results


# ── 多根K线形态（头肩顶/底、双顶/底）────────────────────
def detect_multi_candles(df: pd.DataFrame) -> list:
    results = []
    close = df["Close"].values
    high  = df["High"].values
    low   = df["Low"].values
    n     = len(close)
    if n < 30:
        return results

    # 双顶检测（最近60日）
    window = min(60, n)
    h = high[-window:]
    l = low[-window:]
    c = close[-window:]

    # 找两个相近的高点
    from scipy.signal import argrelextrema
    peaks = argrelextrema(h, np.greater, order=5)[0]
    if len(peaks) >= 2:
        p1, p2 = peaks[-2], peaks[-1]
        if abs(h[p1] - h[p2]) / h[p1] < 0.03:  # 两顶价格相差<3%
            neckline = min(c[p1:p2+1])
            if c[-1] < neckline:
                results.append({
                    "形态": "双顶（M顶）", "信号": "🔴 看跌",
                    "说明": f"颈线 ${round(neckline,2)} 已跌破，目标位 ${round(neckline-(h[p1]-neckline),2)}"
                })
            else:
                results.append({
                    "形态": "疑似双顶", "信号": "⚠️ 警惕",
                    "说明": f"两顶价格相近，颈线 ${round(neckline,2)} 尚未跌破，需观察"
                })

    # 双底检测
    troughs = argrelextrema(l, np.less, order=5)[0]
    if len(troughs) >= 2:
        t1, t2 = troughs[-2], troughs[-1]
        if abs(l[t1] - l[t2]) / l[t1] < 0.03:
            neckline = max(c[t1:t2+1])
            if c[-1] > neckline:
                results.append({
                    "形态": "双底（W底）", "信号": "🟢 看涨",
                    "说明": f"颈线 ${round(neckline,2)} 已突破，目标位 ${round(neckline+(neckline-l[t1]),2)}"
                })
            else:
                results.append({
                    "形态": "疑似双底", "信号": "💡 关注",
                    "说明": f"两底价格相近，颈线 ${round(neckline,2)} 尚未突破，需观察"
                })

    # 头肩顶检测
    if len(peaks) >= 3:
        ls, head, rs = peaks[-3], peaks[-2], peaks[-1]
        if (h[head] > h[ls] and h[head] > h[rs] and
                abs(h[ls] - h[rs]) / h[head] < 0.05):
            neckline = min(l[ls:rs+1])
            results.append({
                "形态": "头肩顶", "信号": "🔴 看跌",
                "说明": f"经典顶部反转形态，颈线 ${round(neckline,2)}，目标位 ${round(neckline-(h[head]-neckline),2)}"
            })

    # 头肩底检测
    if len(troughs) >= 3:
        ls, head, rs = troughs[-3], troughs[-2], troughs[-1]
        if (l[head] < l[ls] and l[head] < l[rs] and
                abs(l[ls] - l[rs]) / abs(l[head]) < 0.05):
            neckline = max(h[ls:rs+1])
            results.append({
                "形态": "头肩底", "信号": "🟢 看涨",
                "说明": f"经典底部反转形态，颈线 ${round(neckline,2)}，目标位 ${round(neckline+(neckline-l[head]),2)}"
            })

    return results


# ── 趋势线 ────────────────────────────────────────────────
def detect_trendlines(df: pd.DataFrame) -> dict:
    """自动识别上升/下降趋势线"""
    close = df["Close"].values
    n     = len(close)
    x     = np.arange(n)

    # 用最近60日做线性回归趋势线
    window = min(60, n)
    x_w = x[-window:].reshape(-1, 1)
    y_w = close[-window:]

    from sklearn.linear_model import LinearRegression
    lr = LinearRegression().fit(x_w, y_w)
    slope     = float(lr.coef_[0])
    intercept = float(lr.intercept_)
    trend_prices = lr.predict(x_w)

    # 计算R²判断趋势强度
    ss_res = np.sum((y_w - trend_prices) ** 2)
    ss_tot = np.sum((y_w - np.mean(y_w)) ** 2)
    r2 = round(1 - ss_res / ss_tot, 3) if ss_tot > 0 else 0

    direction = "上升" if slope > 0 else "下降"
    strength  = "强" if abs(r2) > 0.7 else ("中" if abs(r2) > 0.4 else "弱")

    # 趋势线当前值和未来5日预测
    current_trend = round(float(trend_prices[-1]), 2)
    future_trend  = round(float(lr.predict([[n + 4]])[0]), 2)

    return {
        "direction":     direction,
        "slope":         round(slope, 4),
        "r2":            r2,
        "strength":      strength,
        "current_trend": current_trend,
        "future_5d":     future_trend,
        "trend_prices":  trend_prices.tolist(),
        "dates":         df.index[-window:].tolist(),
        "signal":        "bullish" if slope > 0 and r2 > 0.4 else ("bearish" if slope < 0 and r2 > 0.4 else "neutral"),
    }


# ── 葛兰碧八大法则 ────────────────────────────────────────
def granville_signals(df: pd.DataFrame) -> list:
    """葛兰碧八大法则信号检测"""
    signals = []
    if len(df) < 22:
        return signals

    close = df["Close"]
    ma200 = close.rolling(200).mean() if len(df) >= 200 else close.rolling(len(df)).mean()
    ma20  = close.rolling(20).mean()

    latest     = float(close.iloc[-1])
    prev       = float(close.iloc[-2])
    ma_latest  = float(ma20.iloc[-1])
    ma_prev    = float(ma20.iloc[-2])
    ma_prev2   = float(ma20.iloc[-3]) if len(df) >= 3 else ma_prev

    # 法则1：均线由下转上，价格上穿均线 → 买入
    if ma_prev <= ma_prev2 and ma_latest > ma_prev and latest > ma_latest and prev < ma_prev:
        signals.append({"法则": "法则①", "信号": "🟢 买入", "说明": "均线由跌转涨，价格上穿MA20，强烈买入信号"})

    # 法则2：均线向上，价格回调至均线附近 → 买入
    if ma_latest > ma_prev and abs(latest - ma_latest) / ma_latest < 0.02:
        signals.append({"法则": "法则②", "信号": "🟢 买入", "说明": "均线向上，价格回踩MA20，逢低买入机会"})

    # 法则3：均线向上，价格跌破均线后迅速收回 → 买入
    if ma_latest > ma_prev and prev < ma_prev and latest > ma_latest:
        signals.append({"法则": "法则③", "信号": "🟢 买入", "说明": "价格短暂跌破MA20后收回，假跌破，买入信号"})

    # 法则4：均线向下，价格大幅偏离均线 → 超跌买入
    if ma_latest < ma_prev and (ma_latest - latest) / ma_latest > 0.05:
        signals.append({"法则": "法则④", "信号": "💡 超跌买入", "说明": "价格严重偏离均线下方，超跌反弹机会"})

    # 法则5：均线由上转下，价格下穿均线 → 卖出
    if ma_prev >= ma_prev2 and ma_latest < ma_prev and latest < ma_latest and prev > ma_prev:
        signals.append({"法则": "法则⑤", "信号": "🔴 卖出", "说明": "均线由涨转跌，价格下穿MA20，强烈卖出信号"})

    # 法则6：均线向下，价格反弹至均线附近 → 卖出
    if ma_latest < ma_prev and abs(latest - ma_latest) / ma_latest < 0.02 and latest > ma_latest:
        signals.append({"法则": "法则⑥", "信号": "🔴 卖出", "说明": "均线向下，价格反弹至MA20，逢高卖出机会"})

    # 法则7：均线向下，价格上穿均线后迅速跌回 → 卖出
    if ma_latest < ma_prev and prev > ma_prev and latest < ma_latest:
        signals.append({"法则": "法则⑦", "信号": "🔴 卖出", "说明": "价格短暂突破MA20后跌回，假突破，卖出信号"})

    # 法则8：均线向上，价格大幅偏离均线上方 → 超买卖出
    if ma_latest > ma_prev and (latest - ma_latest) / ma_latest > 0.08:
        signals.append({"法则": "法则⑧", "信号": "⚠️ 超买卖出", "说明": "价格严重偏离均线上方，超买回调风险"})

    return signals


# ── 主入口 ────────────────────────────────────────────────
def analyze_patterns(df: pd.DataFrame) -> dict:
    return {
        "single_candles": detect_single_candles(df),
        "double_candles": detect_double_candles(df),
        "multi_patterns": detect_multi_candles(df),
        "trendline":      detect_trendlines(df),
        "granville":      granville_signals(df),
    }
