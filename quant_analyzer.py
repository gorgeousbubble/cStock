"""
量化策略分析模块
均值回归 Z-Score、动量评分、夏普/索提诺比率、配对交易相关性
"""
import numpy as np
import pandas as pd


def calc_zscore(df: pd.DataFrame, window: int = 20) -> dict:
    """均值回归 Z-Score 分析"""
    close  = df["Close"]
    ma     = close.rolling(window).mean()
    std    = close.rolling(window).std()
    zscore = (close - ma) / std.replace(0, np.nan)

    latest_z = round(float(zscore.iloc[-1]), 2)

    if latest_z > 2:
        signal = "🔴 严重超买"
        advice = f"Z-Score={latest_z}，价格严重偏离均值上方，均值回归概率高，建议减仓"
    elif latest_z > 1:
        signal = "⚠️ 偏高"
        advice = f"Z-Score={latest_z}，价格偏离均值上方，注意回调风险"
    elif latest_z < -2:
        signal = "🟢 严重超卖"
        advice = f"Z-Score={latest_z}，价格严重偏离均值下方，均值回归反弹概率高，可考虑买入"
    elif latest_z < -1:
        signal = "💡 偏低"
        advice = f"Z-Score={latest_z}，价格偏离均值下方，存在反弹机会"
    else:
        signal = "⚪ 正常"
        advice = f"Z-Score={latest_z}，价格在均值附近，无明显偏离"

    return {
        "zscore":    zscore,
        "latest_z":  latest_z,
        "signal":    signal,
        "advice":    advice,
        "ma":        ma,
        "upper_2":   (ma + 2 * std),
        "lower_2":   (ma - 2 * std),
        "upper_1":   (ma + std),
        "lower_1":   (ma - std),
    }


def calc_momentum(df: pd.DataFrame) -> dict:
    """动量评分（多周期）"""
    close = df["Close"]
    latest = float(close.iloc[-1])

    periods = {"5日": 5, "20日": 20, "60日": 60, "120日": 120}
    scores  = {}
    total   = 0

    for label, p in periods.items():
        if len(close) > p:
            ret = round((latest / float(close.iloc[-p-1]) - 1) * 100, 2)
            scores[label] = ret
            total += (1 if ret > 0 else -1)

    # 动量评分 -4 到 +4
    if total >= 3:   momentum_signal = "🟢 强势动量"
    elif total >= 1: momentum_signal = "🟩 偏强"
    elif total <= -3: momentum_signal = "🔴 弱势动量"
    elif total <= -1: momentum_signal = "🟥 偏弱"
    else:            momentum_signal = "🟡 中性"

    # RSI 动量
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rsi   = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))
    rsi_latest = round(float(rsi.iloc[-1]), 1)

    return {
        "returns":  scores,
        "score":    total,
        "signal":   momentum_signal,
        "rsi":      rsi_latest,
    }


def calc_risk_metrics(df: pd.DataFrame, risk_free: float = 0.05) -> dict:
    """夏普比率、索提诺比率、最大回撤、卡玛比率"""
    close     = df["Close"]
    daily_ret = close.pct_change().dropna()
    n         = len(daily_ret)

    annual_ret  = float((close.iloc[-1] / close.iloc[0]) ** (252 / n) - 1)
    annual_vol  = float(daily_ret.std() * np.sqrt(252))
    sharpe      = round((annual_ret - risk_free) / annual_vol, 2) if annual_vol > 0 else 0

    # 索提诺比率（只考虑下行波动）
    downside    = daily_ret[daily_ret < 0]
    down_vol    = float(downside.std() * np.sqrt(252)) if len(downside) > 0 else 0
    sortino     = round((annual_ret - risk_free) / down_vol, 2) if down_vol > 0 else 0

    # 最大回撤
    roll_max    = close.cummax()
    drawdown    = (close - roll_max) / roll_max
    max_dd      = round(float(drawdown.min() * 100), 2)

    # 卡玛比率
    calmar      = round(annual_ret / abs(max_dd / 100), 2) if max_dd != 0 else 0

    # 胜率（日涨跌）
    win_rate    = round(float((daily_ret > 0).sum() / n * 100), 1)

    # 盈亏比
    avg_win  = float(daily_ret[daily_ret > 0].mean()) if len(daily_ret[daily_ret > 0]) > 0 else 0
    avg_loss = float(daily_ret[daily_ret < 0].mean()) if len(daily_ret[daily_ret < 0]) > 0 else 0
    profit_loss_ratio = round(abs(avg_win / avg_loss), 2) if avg_loss != 0 else 0

    def rate_sharpe(s):
        if s > 2:   return "优秀 🟢"
        elif s > 1: return "良好 🟩"
        elif s > 0: return "一般 🟡"
        else:       return "较差 🔴"

    return {
        "annual_ret":   round(annual_ret * 100, 2),
        "annual_vol":   round(annual_vol * 100, 2),
        "sharpe":       sharpe,
        "sortino":      sortino,
        "calmar":       calmar,
        "max_dd":       max_dd,
        "win_rate":     win_rate,
        "profit_loss":  profit_loss_ratio,
        "sharpe_rating": rate_sharpe(sharpe),
        "drawdown_series": drawdown,
    }


def calc_correlation(dfs: dict) -> pd.DataFrame:
    """多股票相关性矩阵"""
    if len(dfs) < 2:
        return pd.DataFrame()
    returns = {}
    for sym, df in dfs.items():
        returns[sym] = df["Close"].pct_change().dropna()
    ret_df = pd.DataFrame(returns).dropna()
    return ret_df.corr().round(3)


def find_pair_trade(dfs: dict) -> list:
    """配对交易机会识别（价差 Z-Score）"""
    results = []
    symbols = list(dfs.keys())
    if len(symbols) < 2:
        return results

    for i in range(len(symbols)):
        for j in range(i+1, len(symbols)):
            s1, s2 = symbols[i], symbols[j]
            try:
                c1 = dfs[s1]["Close"]
                c2 = dfs[s2]["Close"]
                # 对齐
                common = c1.index.intersection(c2.index)
                if len(common) < 60:
                    continue
                c1, c2 = c1[common], c2[common]
                spread = c1 / c2
                z = (spread.iloc[-1] - spread.rolling(60).mean().iloc[-1]) / spread.rolling(60).std().iloc[-1]
                z = round(float(z), 2)
                corr = round(float(c1.pct_change().corr(c2.pct_change())), 3)
                if abs(z) > 1.5 and corr > 0.5:
                    direction = f"做多{s1}做空{s2}" if z < 0 else f"做空{s1}做多{s2}"
                    results.append({
                        "配对": f"{s1}/{s2}",
                        "相关性": corr,
                        "价差Z-Score": z,
                        "信号": "🟢 做多价差" if z < -1.5 else "🔴 做空价差",
                        "操作": direction,
                        "说明": f"价差偏离{abs(z):.1f}个标准差，均值回归机会"
                    })
            except Exception:
                pass
    return results


def analyze_quant(df: pd.DataFrame, all_dfs: dict = None) -> dict:
    zscore   = calc_zscore(df)
    momentum = calc_momentum(df)
    risk     = calc_risk_metrics(df)
    corr     = calc_correlation(all_dfs) if all_dfs and len(all_dfs) >= 2 else pd.DataFrame()
    pairs    = find_pair_trade(all_dfs) if all_dfs and len(all_dfs) >= 2 else []

    return {
        "zscore":   zscore,
        "momentum": momentum,
        "risk":     risk,
        "corr":     corr,
        "pairs":    pairs,
    }
