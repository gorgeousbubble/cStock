"""
多市场数据获取模块
- 美股：Alpaca
- A股：AKShare 东方财富/腾讯财经
- 港股：AKShare 新浪财经
自动识别市场类型
"""
import pandas as pd
from datetime import datetime, timedelta

# 常用股票名称内置字典
STOCK_NAMES = {
    # A股
    "600519": "贵州茅台",  "000858": "五粮液",   "601318": "中国平安",
    "000333": "美的集团",  "600036": "招商銀行",  "000001": "平安銀行",
    "600000": "浦发銀行",  "601166": "兴业銀行",  "600276": "恒瑞医药",
    "000002": "万科A",      "600900": "长江电力",  "601398": "工商銀行",
    "601288": "农业銀行",  "601939": "建设銀行",  "601988": "中国銀行",
    "600028": "中国石化",  "601857": "中国石油",  "600048": "保利地产",
    "000568": "泸州老窖",  "002594": "比亚迪",    "300750": "宁德时代",
    # 港股
    "00700":  "腾讯控股",  "09988": "阿里巴巴-W", "03690": "美团-W",
    "00941":  "中国移动",  "01299": "友邦保险",  "00005": "汇丰銀行",
    "02318":  "中国平安",  "01398": "工商銀行",  "03988": "中国銀行",
    "00388":  "香港交所",  "02020": "安踏体育",  "09618": "京东集团",
    "09999":  "网易有道",  "06690": "海尔智家",  "01810": "小米集团",
    # 美股
    "AAPL":   "Apple",       "MSFT":  "Microsoft",  "NVDA":  "NVIDIA",
    "AMZN":   "Amazon",      "GOOGL": "Alphabet",   "META":  "Meta",
    "TSLA":   "Tesla",       "AMD":   "AMD",         "INTC":  "Intel",
}


def get_stock_name(symbol: str) -> str:
    """获取股票名称：先查内置字典，查不到再调腾讯财经接口"""
    name = STOCK_NAMES.get(symbol.upper())
    if name:
        return name
    # 字典没有时调腾讯财经实时接口
    try:
        from curl_cffi import requests as cr
        market = detect_market(symbol)
        if market == 'CN':
            prefix = 'sh' if symbol.startswith(('6', '5')) else 'sz'
            code = f'{prefix}{symbol}'
        elif market == 'HK':
            code = f'hk{symbol.zfill(5)}'
        else:
            code = f'us{symbol.lower()}'
        session = cr.Session(impersonate='chrome')
        resp = session.get(f'https://qt.gtimg.cn/q={code}', timeout=8)
        text = resp.text
        if '~' in text:
            parts = text.split('~')
            if len(parts) > 1 and parts[1].strip():
                return parts[1].strip()
    except Exception:
        pass
    return symbol


def detect_market(symbol: str) -> str:
    """
    自动识别市场类型
    - 纯数字6位 → A股 (600519, 000858)
    - 纯数字4-5位，以0开头 → 港股 (00700, 09988)
    - 其他 → 美股 (AAPL, TSLA)
    """
    s = symbol.strip().upper()
    if s.isdigit():
        if len(s) == 6:
            return "CN"   # A股
        elif len(s) in (4, 5):
            return "HK"   # 港股
    return "US"           # 美股


def _period_to_dates(period: str):
    """将周期字符串转为 start_date, end_date"""
    end   = datetime.now()
    mapping = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365,
               "2y": 730, "3y": 1095, "5y": 1825}
    days  = mapping.get(period, 365)
    start = end - timedelta(days=days)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


def fetch_cn_stock(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """获取A股历史K线，优先东方财富，备用腾讯财经"""
    import akshare as ak
    start, end = _period_to_dates(period)

    # 尝试东方财富
    try:
        df = ak.stock_zh_a_hist(
            symbol=symbol, period="daily",
            start_date=start, end_date=end, adjust="qfq"
        )
        df = df.rename(columns={
            "日期": "Date", "开盘": "Open", "收盘": "Close",
            "最高": "High", "最低": "Low", "成交量": "Volume"
        })
    except Exception:
        # 备用腾讯财经
        prefix = "sh" if symbol.startswith(("6", "5")) else "sz"
        df = ak.stock_zh_a_hist_tx(
            symbol=f"{prefix}{symbol}",
            start_date=start.replace("-", ""),
            end_date=end.replace("-", "")
        )
        df = df.rename(columns={
            "date": "Date", "open": "Open", "close": "Close",
            "high": "High", "low": "Low", "amount": "Volume"
        })

    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date")
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna().astype(float)
    print(f"[OK] A股 {symbol} 数据：{len(df)} 条 ({df.index[0].date()} ~ {df.index[-1].date()})")
    return df


def fetch_hk_stock(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """获取港股历史K线（新浪财经），含空数据检查"""
    import akshare as ak
    sym = symbol.zfill(5)

    df = ak.stock_hk_daily(symbol=sym, adjust="qfq")
    if df is None or df.empty:
        raise ValueError(f"无法获取港股 {symbol} 数据，请检查代码是否正确")

    df = df.rename(columns={
        "date": "Date", "open": "Open", "high": "High",
        "low": "Low", "close": "Close", "volume": "Volume"
    })
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date")
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna().astype(float)

    days_map = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365,
                "2y": 730, "3y": 1095, "5y": 1825}
    days   = days_map.get(period, 365)
    cutoff = datetime.now() - timedelta(days=days)
    df = df[df.index >= cutoff]

    if df.empty:
        raise ValueError(f"港股 {symbol} 在所选周期内无数据，请尝试更长周期")

    print(f"[OK] 港股 {symbol} 数据：{len(df)} 条 ({df.index[0].date()} ~ {df.index[-1].date()})")
    return df


def fetch_cn_realtime(symbols: list) -> list:
    """A股实时行情 - 用腾讯财经单股接口，速度快"""
    from curl_cffi import requests as cr
    session = cr.Session(impersonate="chrome")
    results = []
    for sym in symbols:
        try:
            prefix = "sh" if sym.startswith(("6", "5")) else "sz"
            resp = session.get(f"https://qt.gtimg.cn/q={prefix}{sym}", timeout=8)
            text = resp.text
            if "~" not in text:
                results.append({"symbol": sym, "price": None, "error": "数据获取失败"})
                continue
            parts = text.split("~")
            # 格式: v_sh600519="1~贵州茅台~600519~当前价~昨收~今开~成交量~外盘~内盘~买一~..."
            name     = parts[1] if len(parts) > 1 else sym
            price    = float(parts[3]) if len(parts) > 3 and parts[3] else None
            prev     = float(parts[4]) if len(parts) > 4 and parts[4] else None
            chg_pct  = round((price / prev - 1) * 100, 2) if price and prev else None
            chg_amt  = round(price - prev, 2) if price and prev else None
            volume   = int(float(parts[6]) * 100) if len(parts) > 6 and parts[6] else 0
            results.append({
                "symbol":    sym,
                "name":      name,
                "price":     price,
                "chg_pct":   chg_pct,
                "chg_amt":   chg_amt,
                "volume":    volume,
                "bid":       price,
                "ask":       price,
                "timestamp": datetime.now().strftime("%H:%M:%S"),
            })
        except Exception as e:
            results.append({"symbol": sym, "price": None, "error": str(e)})
    return results


def fetch_hk_realtime(symbols: list) -> list:
    """港股实时行情 - 用腾讯财经接口，速度快"""
    from curl_cffi import requests as cr
    session = cr.Session(impersonate="chrome")
    results = []
    for sym in symbols:
        try:
            code = f"hk{sym.zfill(5)}"
            resp = session.get(f"https://qt.gtimg.cn/q={code}", timeout=8)
            text = resp.text
            if "~" not in text:
                results.append({"symbol": sym, "price": None, "error": "数据获取失败"})
                continue
            parts = text.split("~")
            name    = parts[1] if len(parts) > 1 else sym
            price   = float(parts[3]) if len(parts) > 3 and parts[3] else None
            prev    = float(parts[4]) if len(parts) > 4 and parts[4] else None
            chg_pct = round((price / prev - 1) * 100, 2) if price and prev else None
            chg_amt = round(price - prev, 2) if price and prev else None
            volume  = int(float(parts[6])) if len(parts) > 6 and parts[6] else 0
            results.append({
                "symbol":    sym,
                "name":      name,
                "price":     price,
                "chg_pct":   chg_pct,
                "chg_amt":   chg_amt,
                "volume":    volume,
                "bid":       price,
                "ask":       price,
                "timestamp": __import__("datetime").datetime.now().strftime("%H:%M:%S HKT"),
            })
        except Exception as e:
            results.append({"symbol": sym, "price": None, "error": str(e)})
    return results


_NAME_CACHE: dict = {}


def get_display_name(symbol: str) -> str:
    """带缓存的股票名称查询，失败时返回代码本身"""
    if symbol not in _NAME_CACHE:
        _NAME_CACHE[symbol] = get_stock_name(symbol)
    return _NAME_CACHE[symbol]
