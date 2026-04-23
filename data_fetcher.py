import os
import hashlib
import pandas as pd
from datetime import datetime, timedelta

# 本地磁盘缓存目录
_CACHE_DIR = os.path.join(os.path.dirname(__file__), '.data_cache')
os.makedirs(_CACHE_DIR, exist_ok=True)

def _cache_key(symbol: str, period: str, interval: str) -> str:
    return hashlib.md5(f"{symbol}_{period}_{interval}".encode()).hexdigest()[:12]

def _cache_path(symbol: str, period: str, interval: str) -> str:
    key = _cache_key(symbol, period, interval)
    return os.path.join(_CACHE_DIR, f"{symbol}_{period}_{interval}_{key}.pkl")

def _cache_valid(path: str, max_age_seconds: int = 300) -> bool:
    """缓存是否有效（默认5分钟）"""
    if not os.path.exists(path):
        return False
    age = datetime.now().timestamp() - os.path.getmtime(path)
    return age < max_age_seconds

def _load_cache(path: str) -> pd.DataFrame:
    try:
        import pickle
        with open(path, 'rb') as f:
            return pickle.load(f)
    except Exception:
        return None

def _save_cache(df: pd.DataFrame, path: str):
    try:
        import pickle
        with open(path, 'wb') as f:
            pickle.dump(df, f, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception:
        pass
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest, StockLatestBarRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

load_dotenv()

_client = None

def _get_client() -> StockHistoricalDataClient:
    global _client
    if _client is None:
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")
        if not api_key or "你的" in api_key:
            raise ValueError("请先在 .env 文件中填写 ALPACA_API_KEY 和 ALPACA_SECRET_KEY")
        _client = StockHistoricalDataClient(api_key, secret_key)
    return _client


def _parse_timeframe(interval: str) -> TimeFrame:
    mapping = {
        "1d": TimeFrame.Day,
        "1h": TimeFrame.Hour,
        "30m": TimeFrame(30, TimeFrameUnit.Minute),
        "15m": TimeFrame(15, TimeFrameUnit.Minute),
        "5m":  TimeFrame(5,  TimeFrameUnit.Minute),
    }
    if interval not in mapping:
        raise ValueError(f"不支持的间隔 {interval}，可选: {list(mapping.keys())}")
    return mapping[interval]


def _parse_period(period: str) -> datetime:
    """将 '1y'/'6mo'/'3mo'/'1mo' 转为起始时间"""
    now = datetime.now(ZoneInfo("America/New_York"))
    mapping = {"1y": 365, "2y": 730, "3y": 1095, "5y": 1825, "6mo": 180, "3mo": 90, "1mo": 30, "5d": 5}
    days = mapping.get(period)
    if days is None:
        raise ValueError(f"不支持的周期 {period}，可选: {list(mapping.keys())}")
    return now - timedelta(days=days)


def fetch_stock_data(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """统一入口：自动识别市场，美股用Alpaca，A股/港股用AKShare，带本地磁盘缓存"""
    from market_data import detect_market, fetch_cn_stock, fetch_hk_stock
    market = detect_market(symbol)

    # 日线数据缓存时间：交易日内5分钟，非交易时间24小时
    _now = datetime.now()
    _is_trading = _now.weekday() < 5 and 9 <= _now.hour <= 16
    _cache_ttl = 300 if _is_trading else 86400  # 5分钟 or 24小时

    # 分钟线不缓存（实时性要求高）
    _use_cache = interval == "1d"

    if _use_cache:
        _cpath = _cache_path(symbol, period, interval)
        if _cache_valid(_cpath, _cache_ttl):
            _cached = _load_cache(_cpath)
            if _cached is not None and not _cached.empty:
                print(f"[CACHE] {symbol} {period} {interval}")
                return _cached

    if market == "CN":
        df = fetch_cn_stock(symbol, period, interval)
        if _use_cache: _save_cache(df, _cache_path(symbol, period, interval))
        return df
    elif market == "HK":
        df = fetch_hk_stock(symbol, period, interval)
        if _use_cache: _save_cache(df, _cache_path(symbol, period, interval))
        return df
    # 美股原逻辑
    client = _get_client()
    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=_parse_timeframe(interval),
        start=_parse_period(period),
        feed="iex",  # 免费实时数据源
    )
    bars = client.get_stock_bars(request)
    df = bars.df

    # 多股票时 df 有 MultiIndex，单股票时取对应层
    if isinstance(df.index, pd.MultiIndex):
        df = df.xs(symbol, level="symbol")

    df.index = pd.to_datetime(df.index).tz_localize(None)
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                             "close": "Close", "volume": "Volume"})
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    print(f"[OK] 已获取 {symbol} 数据：{len(df)} 条记录 ({df.index[0].date()} ~ {df.index[-1].date()})")
    if _use_cache: _save_cache(df, _cache_path(symbol, period, interval))
    return df


def fetch_latest_price(symbol: str) -> dict:
    """获取单只股票最新实时报价"""
    client = _get_client()
    quote = client.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=symbol))[symbol]
    bar   = client.get_stock_latest_bar(StockLatestBarRequest(symbol_or_symbols=symbol))[symbol]
    mid   = round((float(quote.bid_price) + float(quote.ask_price)) / 2, 2)
    prev_close = float(bar.close)
    return {
        "symbol":     symbol,
        "bid":        float(quote.bid_price),
        "ask":        float(quote.ask_price),
        "mid":        mid,
        "prev_close": prev_close,
    }


def fetch_realtime_quotes(symbols: list) -> list:
    """批量获取实时报价 + 当日涨跌幅"""
    client  = _get_client()
    quotes  = client.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=symbols))
    bars    = client.get_stock_latest_bar(StockLatestBarRequest(symbol_or_symbols=symbols))

    # 取昨日收盘：用最近2日日线
    prev_closes = {}
    try:
        hist_req = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=TimeFrame.Day,
            start=datetime.now(ZoneInfo("America/New_York")) - timedelta(days=5),
            feed="iex",
        )
        hist = client.get_stock_bars(hist_req).df
        for sym in symbols:
            try:
                sym_df = hist.xs(sym, level="symbol") if isinstance(hist.index, pd.MultiIndex) else hist
                prev_closes[sym] = float(sym_df["close"].iloc[-2]) if len(sym_df) >= 2 else float(sym_df["close"].iloc[-1])
            except Exception:
                prev_closes[sym] = None
    except Exception:
        prev_closes = {s: None for s in symbols}

    results = []
    for sym in symbols:
        try:
            q   = quotes[sym]
            b   = bars[sym]
            bid = float(q.bid_price)
            ask = float(q.ask_price)
            # ask=0 时用 bid 或 bar close 作为价格
            if ask > 0 and bid > 0:
                mid = round((bid + ask) / 2, 2)
            elif bid > 0:
                mid = bid
            else:
                mid = round(float(b.close), 2)
            prev = prev_closes.get(sym)
            chg_pct = round((mid / prev - 1) * 100, 2) if prev else None
            chg_amt = round(mid - prev, 2)              if prev else None
            results.append({
                "symbol":   sym,
                "price":    mid,
                "bid":      float(q.bid_price),
                "ask":      float(q.ask_price),
                "volume":   int(b.volume),
                "prev_close": prev,
                "chg_amt":  chg_amt,
                "chg_pct":  chg_pct,
                "timestamp": datetime.now(ZoneInfo("America/New_York")).strftime("%H:%M:%S ET"),
            })
        except Exception as e:
            results.append({"symbol": sym, "price": None, "error": str(e)})
    return results
