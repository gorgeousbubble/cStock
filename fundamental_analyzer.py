"""
基本面分析模块 - 数据源：AKShare（东方财富）
支持美股 / A股 / 港股，完全免费无需注册
"""
import pandas as pd


def fetch_fundamentals(symbol: str) -> dict:
    from market_data import detect_market
    market = detect_market(symbol)
    try:
        if market == "US":
            return _fetch_us(symbol)
        elif market == "CN":
            return _fetch_cn(symbol)
        elif market == "HK":
            return _fetch_hk(symbol)
    except Exception as e:
        return {"error": str(e)}
    return {}


# ── 美股 ──────────────────────────────────────────────────
def _fetch_us(symbol: str) -> dict:
    import akshare as ak
    fin = ak.stock_financial_us_analysis_indicator_em(symbol=symbol, indicator="年报")
    if fin.empty:
        return {}
    row = fin.iloc[0]

    roe          = _s(row, "ROE_AVG")
    roa          = _s(row, "ROA")
    eps          = _s(row, "BASIC_EPS")
    gross_margin = _s(row, "GROSS_PROFIT_RATIO")
    net_margin   = _s(row, "NET_PROFIT_RATIO")
    debt_ratio   = _s(row, "DEBT_ASSET_RATIO")
    cur_ratio    = _s(row, "CURRENT_RATIO")
    revenue      = _s(row, "OPERATE_INCOME")
    net_profit   = _s(row, "PARENT_HOLDER_NETPROFIT")
    rev_yoy      = _s(row, "OPERATE_INCOME_YOY")
    profit_yoy   = _s(row, "PARENT_HOLDER_NETPROFIT_YOY")
    report_date  = str(row.get("REPORT_DATE", ""))[:10]

    income_trend = _us_income_trend(symbol)
    price        = _alpaca_price(symbol)

    pe  = round(float(price) / float(eps), 2) if price and eps and float(eps) > 0 else None
    peg = round(float(pe) / float(profit_yoy), 2) if pe and profit_yoy and float(profit_yoy) > 0 else None
    dcf = _dcf(eps, profit_yoy)

    return _build(symbol, report_date, price, pe, None, peg, eps, roe, roa,
                  gross_margin, net_margin, debt_ratio, cur_ratio,
                  revenue, net_profit, rev_yoy, profit_yoy, dcf, income_trend)


def _us_income_trend(symbol):
    try:
        import akshare as ak
        df = ak.stock_financial_us_report_em(stock=symbol, symbol="利润表", indicator="年报")
        result = []
        for _, r in df.head(4).iterrows():
            result.append({
                "年份": str(r.get("REPORT_DATE", ""))[:4],
                "营收(亿)": round(float(r.get("OPERATE_INCOME", 0) or 0) / 1e8, 2),
                "净利润(亿)": round(float(r.get("PARENT_HOLDER_NETPROFIT", 0) or 0) / 1e8, 2),
            })
        return result
    except Exception:
        return []


# ── A股 ──────────────────────────────────────────────────
def _fetch_cn(symbol: str) -> dict:
    import akshare as ak
    from datetime import datetime
    year = str(datetime.now().year - 1)
    fin  = ak.stock_financial_analysis_indicator(symbol=symbol, start_year=year)
    if fin.empty:
        return {}
    row = fin.iloc[-1]  # 最新一行

    def sc(key):  # safe get Chinese column
        try:
            v = row.get(key)
            return float(v) if v is not None and str(v) not in ("nan", "None", "") else None
        except Exception:
            return None

    roe          = sc("净资产收益率(%)")
    gross_margin = sc("销售毛利率(%)")
    net_margin   = sc("销售净利率(%)")
    debt_ratio   = sc("资产负巫t率(%)")
    report_date  = str(row.get("日期", ""))[:10]

    # 利润表趋势
    income_trend = _cn_income_trend(symbol)
    price        = _cn_price(symbol)

    # EPS 从利润表获取
    eps = None
    try:
        inc = ak.stock_financial_report_em(stock=symbol, symbol="利润表", indicator="年报")
        if not inc.empty:
            eps_raw = inc.iloc[0].get("BASIC_EPS")
            eps = float(eps_raw) if eps_raw else None
    except Exception:
        pass

    pe  = round(float(price) / float(eps), 2) if price and eps and float(eps) > 0 else None
    peg = None
    dcf = _dcf(eps, None)

    return _build(symbol, report_date, price, pe, None, peg, eps, roe, None,
                  gross_margin, net_margin, debt_ratio, None,
                  None, None, None, None, dcf, income_trend)


def _cn_income_trend(symbol):
    try:
        import akshare as ak
        df = ak.stock_financial_report_em(stock=symbol, symbol="利润表", indicator="年报")
        result = []
        for _, r in df.head(4).iterrows():
            result.append({
                "年份": str(r.get("REPORT_DATE", ""))[:4],
                "营收(亿)": round(float(r.get("OPERATE_INCOME", 0) or 0) / 1e8, 2),
                "净利润(亿)": round(float(r.get("PARENT_HOLDER_NETPROFIT", 0) or 0) / 1e8, 2),
            })
        return result
    except Exception:
        return []


def _cn_price(symbol):
    try:
        from curl_cffi import requests as cr
        prefix = "sh" if symbol.startswith(("6", "5")) else "sz"
        s = cr.Session(impersonate="chrome")
        r = s.get(f"https://qt.gtimg.cn/q={prefix}{symbol}", timeout=8)
        parts = r.text.split("~")
        return round(float(parts[3]), 2) if len(parts) > 3 else None
    except Exception:
        return None


# ── 港股 ──────────────────────────────────────────────────
def _fetch_hk(symbol: str) -> dict:
    import akshare as ak
    sym5 = symbol.zfill(5)
    fin  = ak.stock_financial_hk_analysis_indicator_em(symbol=sym5, indicator="年报")
    if fin.empty:
        return {}
    row = fin.iloc[0]

    roe          = _s(row, "ROE_AVG")
    roa          = _s(row, "ROA")
    eps          = _s(row, "BASIC_EPS")
    gross_margin = _s(row, "GROSS_PROFIT_RATIO")
    net_margin   = _s(row, "NET_PROFIT_RATIO")
    debt_ratio   = _s(row, "DEBT_ASSET_RATIO")
    cur_ratio    = _s(row, "CURRENT_RATIO")
    revenue      = _s(row, "OPERATE_INCOME")
    net_profit   = _s(row, "PARENT_HOLDER_NETPROFIT")
    rev_yoy      = _s(row, "OPERATE_INCOME_YOY")
    profit_yoy   = _s(row, "PARENT_HOLDER_NETPROFIT_YOY")
    report_date  = str(row.get("REPORT_DATE", ""))[:10]

    income_trend = _hk_income_trend(sym5)
    price        = _hk_price(symbol)

    pe  = round(float(price) / float(eps), 2) if price and eps and float(eps) > 0 else None
    peg = round(float(pe) / float(profit_yoy), 2) if pe and profit_yoy and float(profit_yoy) > 0 else None
    dcf = _dcf(eps, profit_yoy)

    return _build(symbol, report_date, price, pe, None, peg, eps, roe, roa,
                  gross_margin, net_margin, debt_ratio, cur_ratio,
                  revenue, net_profit, rev_yoy, profit_yoy, dcf, income_trend)


def _hk_income_trend(sym5):
    try:
        import akshare as ak
        df = ak.stock_financial_hk_report_em(stock=sym5, symbol="利润表", indicator="年报")
        result = []
        for _, r in df.head(4).iterrows():
            result.append({
                "年份": str(r.get("REPORT_DATE", ""))[:4],
                "营收(亿)": round(float(r.get("OPERATE_INCOME", 0) or 0) / 1e8, 2),
                "净利润(亿)": round(float(r.get("PARENT_HOLDER_NETPROFIT", 0) or 0) / 1e8, 2),
            })
        return result
    except Exception:
        return []


def _hk_price(symbol):
    try:
        from curl_cffi import requests as cr
        s = cr.Session(impersonate="chrome")
        r = s.get(f"https://qt.gtimg.cn/q=hk{symbol.zfill(5)}", timeout=8)
        parts = r.text.split("~")
        return round(float(parts[3]), 2) if len(parts) > 3 else None
    except Exception:
        return None


# ── 工具函数 ──────────────────────────────────────────────
def _alpaca_price(symbol):
    try:
        from data_fetcher import _get_client
        from alpaca.data.requests import StockLatestBarRequest
        bar = _get_client().get_stock_latest_bar(
            StockLatestBarRequest(symbol_or_symbols=symbol))[symbol]
        return round(float(bar.close), 2)
    except Exception:
        return None


def _dcf(eps, profit_yoy):
    try:
        if eps and float(eps) > 0 and profit_yoy and float(profit_yoy) > 0:
            g = min(float(profit_yoy) / 100, 0.30)
            return round(float(eps) * (1 + g) ** 5 * 15 / (1.10 ** 5), 2)
    except Exception:
        pass
    return None


def _build(symbol, report_date, price, pe, pb, peg, eps, roe, roa,
           gross_margin, net_margin, debt_ratio, cur_ratio,
           revenue, net_profit, rev_yoy, profit_yoy, dcf, income_trend):
    score, notes = 0, []
    if pe:
        if pe < 15:   score += 2; notes.append(f"PE {pe} 偏低，估值便宜")
        elif pe < 25: score += 1; notes.append(f"PE {pe} 合理")
        elif pe < 40: score -= 1; notes.append(f"PE {pe} 偏高")
        else:         score -= 2; notes.append(f"PE {pe} 很高，估值昂贵")
    if peg:
        if float(peg) < 1:   score += 1; notes.append(f"PEG {peg} < 1，成长性好")
        elif float(peg) > 2: score -= 1; notes.append(f"PEG {peg} > 2，成长溢价高")
    if roe and float(roe) > 20:
        score += 1; notes.append(f"ROE {round(float(roe),1)}% 优秀（>20%）")
    if debt_ratio and float(debt_ratio) > 80:
        score -= 1; notes.append(f"资产负债率 {round(float(debt_ratio),1)}% 偏高")
    if gross_margin and float(gross_margin) > 40:
        score += 1; notes.append(f"毛利率 {round(float(gross_margin),1)}% 优秀")
    if rev_yoy and float(rev_yoy) > 10:
        notes.append(f"营收同比增长 {round(float(rev_yoy),1)}%")

    if score >= 3:    val_rating = "低估 🟢"
    elif score >= 1:  val_rating = "合理 🟡"
    elif score >= -1: val_rating = "偏高 🟠"
    else:             val_rating = "高估 🔴"

    def r2(x): return round(float(x), 2) if x is not None else None
    return {
        "symbol": symbol, "report_date": report_date, "price": price,
        "pe": pe, "pb": pb, "peg": peg, "eps": r2(eps),
        "roe": r2(roe), "roa": r2(roa),
        "gross_margin": r2(gross_margin), "net_margin": r2(net_margin),
        "debt_ratio": r2(debt_ratio), "current_ratio": r2(cur_ratio),
        "revenue": r2(revenue), "net_profit": r2(net_profit),
        "revenue_yoy": r2(rev_yoy), "profit_yoy": r2(profit_yoy),
        "dcf_value": dcf, "val_rating": val_rating,
        "val_notes": notes, "income_trend": income_trend,
    }


def _s(row, key):
    try:
        v = row.get(key)
        return float(v) if v is not None and str(v) not in ("nan", "None", "") else None
    except Exception:
        return None
