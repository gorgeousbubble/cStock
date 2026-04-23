"""
宏观经济指标模块
数据源：AKShare（东方财富/财经日历）
支持：美股/A股/港股 对应的宏观指标
"""
import pandas as pd


def _safe_fetch(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception:
        return pd.DataFrame()


def fetch_macro_us() -> dict:
    """美股宏观指标：美联储利率、CPI、非农、GDP"""
    import akshare as ak
    result = {}

    # 美联储利率
    df = _safe_fetch(ak.macro_bank_usa_interest_rate)
    if not df.empty:
        latest = df.dropna(subset=['今值']).iloc[-1]
        result['fed_rate'] = {
            'name': '美联储利率',
            'value': float(latest['今值']),
            'prev':  float(latest['前值']) if pd.notna(latest['前值']) else None,
            'date':  str(latest['日期'])[:10],
            'unit':  '%',
        }

    # 美国CPI（用 macro_usa_cpi_monthly 或备用接口）
    for func_name in ['macro_usa_cpi_monthly', 'macro_usa_core_cpi_monthly']:
        try:
            func = getattr(ak, func_name)
            df = _safe_fetch(func)
            if not df.empty and '今值' in df.columns:
                latest = df.dropna(subset=['今值']).iloc[-1]
                result['us_cpi'] = {
                    'name': '美国CPI月率',
                    'value': float(latest['今值']),
                    'prev':  float(latest['前值']) if pd.notna(latest['前值']) else None,
                    'date':  str(latest['日期'])[:10],
                    'unit':  '%',
                }
                break
        except Exception:
            continue

    # 美国非农就业
    for func_name in ['macro_usa_non_farm', 'macro_usa_adp_employment']:
        try:
            func = getattr(ak, func_name)
            df = _safe_fetch(func)
            if not df.empty and '今值' in df.columns:
                latest = df.dropna(subset=['今值']).iloc[-1]
                result['non_farm'] = {
                    'name': '美国非农就业',
                    'value': float(latest['今值']),
                    'prev':  float(latest['前值']) if pd.notna(latest['前值']) else None,
                    'date':  str(latest['日期'])[:10],
                    'unit':  '万人',
                }
                break
        except Exception:
            continue

    # 美国GDP
    for func_name in ['macro_usa_gdp_monthly', 'macro_usa_gdp_annual']:
        try:
            func = getattr(ak, func_name)
            df = _safe_fetch(func)
            if not df.empty and '今值' in df.columns:
                latest = df.dropna(subset=['今值']).iloc[-1]
                result['us_gdp'] = {
                    'name': '美国GDP',
                    'value': float(latest['今值']),
                    'prev':  float(latest['前值']) if pd.notna(latest['前值']) else None,
                    'date':  str(latest['日期'])[:10],
                    'unit':  '%',
                }
                break
        except Exception:
            continue

    return result

def fetch_macro_cn() -> dict:
    """A股宏观指标：央行利率、CPI、PMI、GDP"""
    import akshare as ak
    result = {}

    # 中国央行利率
    df = _safe_fetch(ak.macro_bank_china_interest_rate)
    if not df.empty:
        latest = df.dropna(subset=['今值']).iloc[-1]
        result['cn_rate'] = {
            'name': '中国央行利率',
            'value': float(latest['今值']),
            'prev':  float(latest['前值']) if pd.notna(latest['前值']) else None,
            'date':  str(latest['日期'])[:10],
            'unit':  '%',
        }

    # 中国CPI
    df = _safe_fetch(ak.macro_china_cpi_monthly)
    if not df.empty:
        latest = df.dropna(subset=['今值']).iloc[-1]
        result['cn_cpi'] = {
            'name': '中国CPI月率',
            'value': float(latest['今值']),
            'prev':  float(latest['前值']) if pd.notna(latest['前值']) else None,
            'date':  str(latest['日期'])[:10],
            'unit':  '%',
        }

    # 中国PMI
    try:
        df = _safe_fetch(ak.macro_china_pmi_yearly)
        if not df.empty:
            latest = df.dropna(subset=['今值']).iloc[-1]
            result['cn_pmi'] = {
                'name': '中国PMI',
                'value': float(latest['今值']),
                'prev':  float(latest['前值']) if pd.notna(latest['前值']) else None,
                'date':  str(latest['日期'])[:10],
                'unit':  '',
            }
    except Exception:
        pass

    # 中国GDP
    try:
        df = _safe_fetch(ak.macro_china_gdp_yearly)
        if not df.empty:
            latest = df.dropna(subset=['今值']).iloc[-1]
            result['cn_gdp'] = {
                'name': '中国GDP年率',
                'value': float(latest['今值']),
                'prev':  float(latest['前值']) if pd.notna(latest['前值']) else None,
                'date':  str(latest['日期'])[:10],
                'unit':  '%',
            }
    except Exception:
        pass

    return result


def fetch_macro_hk() -> dict:
    """港股宏观指标：美联储利率 + 美国CPI（港元与美元挂钩）"""
    import akshare as ak
    result = {}

    # 美联储利率（港股与美元挂钩，直接影响港股）
    df = _safe_fetch(ak.macro_bank_usa_interest_rate)
    if not df.empty:
        latest = df.dropna(subset=['今值']).iloc[-1]
        result['fed_rate'] = {
            'name': '美联储利率',
            'value': float(latest['今值']),
            'prev':  float(latest['前值']) if pd.notna(latest['前值']) else None,
            'date':  str(latest['日期'])[:10],
            'unit':  '%',
        }
        # 香港最优惠利率（通常比美联储高约2.5%）
        result['hk_prime'] = {
            'name': '港最优惠利率(估)',
            'value': round(float(latest['今值']) + 2.5, 2),
            'prev':  None,
            'date':  str(latest['日期'])[:10],
            'unit':  '%',
        }

    # 美国CPI（影响港股通胀预期）
    df = _safe_fetch(ak.macro_usa_cpi_monthly)
    if not df.empty:
        latest = df.dropna(subset=['今值']).iloc[-1]
        result['us_cpi'] = {
            'name': '美国CPI月率',
            'value': float(latest['今值']),
            'prev':  float(latest['前值']) if pd.notna(latest['前值']) else None,
            'date':  str(latest['日期'])[:10],
            'unit':  '%',
        }

    return result

def fetch_macro(market: str) -> dict:
    """统一宏观指标获取入口"""
    try:
        if market == "🇺🇸 美股":
            return fetch_macro_us()
        elif market == "🇨🇳 A股":
            return fetch_macro_cn()
        elif market == "🇭🇰 港股":
            return fetch_macro_hk()
    except Exception:
        pass
    return {}


def macro_signal(data: dict) -> str:
    """根据宏观指标给出简单判断"""
    signals = []

    rate = data.get('fed_rate') or data.get('cn_rate')
    if rate:
        v = rate['value']
        p = rate.get('prev')
        if p and v < p:
            signals.append("央行降息，流动性宽松，利好股市")
        elif p and v > p:
            signals.append("央行加息，流动性收紧，注意风险")
        else:
            signals.append(f"利率维持 {v}%，货币政策稳定")

    cpi = data.get('us_cpi') or data.get('cn_cpi')
    if cpi:
        v = cpi['value']
        if v > 0.5:
            signals.append(f"CPI {v}% 偏高，通胀压力存在")
        elif v < -0.2:
            signals.append(f"CPI {v}% 为负，通缩风险需关注")
        else:
            signals.append(f"CPI {v}% 温和，通胀可控")

    pmi = data.get('cn_pmi')
    if pmi:
        v = pmi['value']
        if v > 50:
            signals.append(f"PMI {v} > 50，制造业扩张，经济向好")
        else:
            signals.append(f"PMI {v} < 50，制造业收缩，经济承压")

    return " | ".join(signals) if signals else "宏观数据暂无明显信号"
