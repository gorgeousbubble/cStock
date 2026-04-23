"""
行业对比 & 配对交易模块
- 行业内股票横向对比（涨跌幅、RSI、趋势评分）
- 配对交易：价差 Z-Score 识别套利机会
- 相关性矩阵
"""
import pandas as pd
import numpy as np


# 预定义行业分组
INDUSTRY_GROUPS = {
    "美股科技": ["AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "INTC"],
    "美股电商": ["AMZN", "SHOP", "EBAY", "BABA"],
    "美股新能源": ["TSLA", "RIVN", "NIO", "XPEV"],
    "A股白酒":   ["600519", "000858", "000568", "002304"],
    "A股新能源":  ["300750", "002594", "601012", "600438"],
    "A股银行":   ["600036", "601318", "601166", "600000"],
    "港股科技":  ["00700", "09988", "03690", "09618"],
    "港股金融":  ["00005", "02318", "01398", "03988"],
}


def get_industry_group(symbol: str) -> str:
    """根据股票代码找所属行业组"""
    for group, symbols in INDUSTRY_GROUPS.items():
        if symbol.upper() in [s.upper() for s in symbols]:
            return group
    return None


def fetch_industry_comparison(symbol: str, period: str = "1y") -> dict:
    """获取同行业股票对比数据"""
    group_name = get_industry_group(symbol)
    if not group_name:
        return {"error": f"{symbol} 不在预定义行业组中", "group": None}

    peers = INDUSTRY_GROUPS[group_name]
    results = []

    for peer in peers:
        try:
            from data_fetcher import fetch_stock_data
            from indicators import add_indicators
            from market_data import get_display_name

            df = fetch_stock_data(peer, period, "1d")
            df = add_indicators(df)

            close  = df["Close"]
            latest = float(close.iloc[-1])
            ret_1m = round((latest / close.iloc[-22] - 1) * 100, 2) if len(close) >= 22 else None
            ret_3m = round((latest / close.iloc[-66] - 1) * 100, 2) if len(close) >= 66 else None
            rsi    = round(float(df["RSI"].iloc[-1]), 1)
            vol    = round(float(df["Close"].pct_change().dropna().rolling(20).std().iloc[-1] * np.sqrt(252) * 100), 1)

            # 趋势评分
            ma5, ma20, ma60 = float(df["MA5"].iloc[-1]), float(df["MA20"].iloc[-1]), float(df["MA60"].iloc[-1])
            ts = 50
            if latest > ma5:  ts += 10
            if latest > ma20: ts += 15
            if latest > ma60: ts += 15
            if ma5 > ma20:    ts += 5
            if ma20 > ma60:   ts += 5
            ts = max(0, min(100, ts))

            name = get_display_name(peer)
            results.append({
                "代码":     peer,
                "名称":     name,
                "最新价":   round(latest, 2),
                "1月涨跌":  f"{ret_1m:+.2f}%" if ret_1m else "N/A",
                "3月涨跌":  f"{ret_3m:+.2f}%" if ret_3m else "N/A",
                "RSI":      rsi,
                "波动率":   f"{vol}%",
                "趋势评分": ts,
                "是否当前": peer.upper() == symbol.upper(),
                "_ret_1m":  ret_1m or 0,
                "_close":   close,
            })
        except Exception:
            pass

    # 按1月涨跌排序
    results.sort(key=lambda x: x["_ret_1m"], reverse=True)

    return {
        "group":   group_name,
        "symbol":  symbol,
        "peers":   results,
        "count":   len(results),
    }


def calc_pair_trading(dfs: dict) -> list:
    """配对交易机会识别（价差 Z-Score）"""
    results = []
    symbols = list(dfs.keys())
    if len(symbols) < 2:
        return results

    for i in range(len(symbols)):
        for j in range(i + 1, len(symbols)):
            s1, s2 = symbols[i], symbols[j]
            try:
                c1 = dfs[s1]["Close"]
                c2 = dfs[s2]["Close"]
                common = c1.index.intersection(c2.index)
                if len(common) < 60:
                    continue
                c1, c2 = c1[common], c2[common]

                # 计算价差 Z-Score
                spread    = c1 / c2
                spread_ma = spread.rolling(60).mean()
                spread_std = spread.rolling(60).std()
                z = float((spread.iloc[-1] - spread_ma.iloc[-1]) / spread_std.iloc[-1])
                z = round(z, 2)

                # 相关性
                corr = round(float(c1.pct_change().corr(c2.pct_change())), 3)

                if abs(z) > 1.5 and corr > 0.5:
                    from market_data import get_display_name
                    n1 = get_display_name(s1)
                    n2 = get_display_name(s2)
                    direction = f"做多{n1}({s1}) 做空{n2}({s2})" if z < 0 else f"做空{n1}({s1}) 做多{n2}({s2})"
                    results.append({
                        "配对":       f"{n1}/{n2}",
                        "相关性":     corr,
                        "价差Z-Score": z,
                        "信号":       "🟢 做多价差" if z < -1.5 else "🔴 做空价差",
                        "操作建议":   direction,
                        "说明":       f"价差偏离 {abs(z):.1f} 个标准差，均值回归机会",
                    })
            except Exception:
                pass

    results.sort(key=lambda x: abs(x["价差Z-Score"]), reverse=True)
    return results


def calc_correlation_matrix(dfs: dict) -> pd.DataFrame:
    """计算多股票相关性矩阵"""
    if len(dfs) < 2:
        return pd.DataFrame()
    returns = {}
    for sym, df in dfs.items():
        try:
            from market_data import get_display_name
            name = get_display_name(sym)
            label = f"{name}({sym})" if name != sym else sym
            returns[label] = df["Close"].pct_change().dropna()
        except Exception:
            returns[sym] = df["Close"].pct_change().dropna()
    ret_df = pd.DataFrame(returns).dropna()
    return ret_df.corr().round(3)
