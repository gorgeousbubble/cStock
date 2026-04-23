"""
期权分析模块（仅美股）
数据源：Alpaca Options API
分析：Put/Call比率、隐含波动率、最大痛点、期权链
"""
import os
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()


def _parse_symbol(symbol: str) -> dict:
    """解析期权代码：AAPL260415C00185000"""
    m = re.match(r'([A-Z]+)(\d{6})([CP])(\d+)', symbol)
    if not m:
        return {}
    ticker, exp, opt_type, strike = m.groups()
    return {
        'ticker':    ticker,
        'expiry':    f"20{exp[:2]}-{exp[2:4]}-{exp[4:6]}",
        'type':      'Call' if opt_type == 'C' else 'Put',
        'strike':    round(int(strike) / 1000, 2),
    }


def fetch_option_data(symbol: str, days_ahead: int = 45) -> dict:
    """获取期权链数据并分析"""
    try:
        from alpaca.data.historical import OptionHistoricalDataClient
        from alpaca.data.requests import OptionChainRequest

        client = OptionHistoricalDataClient(
            os.getenv('ALPACA_API_KEY'), os.getenv('ALPACA_SECRET_KEY')
        )
        req = OptionChainRequest(
            underlying_symbol=symbol,
            expiration_date_gte=datetime.now().strftime('%Y-%m-%d'),
            expiration_date_lte=(datetime.now() + timedelta(days=days_ahead)).strftime('%Y-%m-%d'),
        )
        chain = client.get_option_chain(req)
        if not chain:
            return {}

        calls, puts = [], []
        total_call_oi = 0
        total_put_oi  = 0

        for opt_sym, opt_data in chain.items():
            info = _parse_symbol(opt_sym)
            if not info:
                continue
            # opt_data 可能是 OptionsSnapshot 对象或 dict
            if hasattr(opt_data, '__dict__'):
                opt_dict = opt_data.__dict__
            elif isinstance(opt_data, dict):
                opt_dict = opt_data
            else:
                opt_dict = {}
            quote  = opt_dict.get('latest_quote') or {}
            if hasattr(quote, '__dict__'):
                quote = quote.__dict__
            bid    = float(getattr(quote, 'bid_price', None) or quote.get('bid_price') or 0)
            ask    = float(getattr(quote, 'ask_price', None) or quote.get('ask_price') or 0)
            mid    = round((bid + ask) / 2, 2) if bid and ask else 0
            iv     = opt_dict.get('implied_volatility')
            greeks = opt_dict.get('greeks') or {}
            if hasattr(greeks, '__dict__'):
                greeks = greeks.__dict__

            row = {
                'symbol':  opt_sym,
                'expiry':  info['expiry'],
                'type':    info['type'],
                'strike':  info['strike'],
                'bid':     bid,
                'ask':     ask,
                'mid':     mid,
                'iv':      round(float(iv) * 100, 1) if iv else None,
                'delta':   round(float(greeks.get('delta') or 0), 3),
                'gamma':   round(float(greeks.get('gamma') or 0), 4),
                'theta':   round(float(greeks.get('theta') or 0), 4),
                'vega':    round(float(greeks.get('vega') or 0), 4),
            }
            if info['type'] == 'Call':
                calls.append(row)
                total_call_oi += 1
            else:
                puts.append(row)
                total_put_oi += 1

        # Put/Call 比率
        pc_ratio = round(total_put_oi / total_call_oi, 2) if total_call_oi > 0 else None

        # 按到期日分组
        expiries = sorted(set(r['expiry'] for r in calls + puts))

        # 最近到期日的期权链（用于展示）
        nearest_expiry = expiries[0] if expiries else None
        near_calls = sorted([r for r in calls if r['expiry'] == nearest_expiry], key=lambda x: x['strike'])
        near_puts  = sorted([r for r in puts  if r['expiry'] == nearest_expiry], key=lambda x: x['strike'])

        # 最大痛点（Max Pain）：所有行权价中，期权买方损失最大的价格
        max_pain = _calc_max_pain(calls, puts)

        # 平均隐含波动率
        all_ivs = [r['iv'] for r in calls + puts if r['iv']]
        avg_iv  = round(sum(all_ivs) / len(all_ivs), 1) if all_ivs else None

        return {
            'symbol':         symbol,
            'total_calls':    total_call_oi,
            'total_puts':     total_put_oi,
            'pc_ratio':       pc_ratio,
            'avg_iv':         avg_iv,
            'max_pain':       max_pain,
            'expiries':       expiries[:5],
            'nearest_expiry': nearest_expiry,
            'near_calls':     near_calls[:10],
            'near_puts':      near_puts[:10],
            'signal':         _option_signal(pc_ratio, avg_iv),
        }
    except Exception as e:
        return {'error': str(e)}


def _calc_max_pain(calls: list, puts: list) -> float:
    """计算最大痛点价格"""
    try:
        strikes = sorted(set(r['strike'] for r in calls + puts))
        if not strikes:
            return None
        min_pain = float('inf')
        max_pain_price = strikes[0]
        for test_price in strikes:
            pain = 0
            for c in calls:
                if test_price > c['strike']:
                    pain += (test_price - c['strike']) * c['mid']
            for p in puts:
                if test_price < p['strike']:
                    pain += (p['strike'] - test_price) * p['mid']
            if pain < min_pain:
                min_pain = pain
                max_pain_price = test_price
        return max_pain_price
    except Exception:
        return None


def _option_signal(pc_ratio: float, avg_iv: float) -> str:
    """根据期权数据给出信号"""
    signals = []
    if pc_ratio:
        if pc_ratio > 1.2:
            signals.append(f"Put/Call={pc_ratio}，市场偏悲观，可能超卖")
        elif pc_ratio < 0.7:
            signals.append(f"Put/Call={pc_ratio}，市场偏乐观，注意过热")
        else:
            signals.append(f"Put/Call={pc_ratio}，市场情绪中性")
    if avg_iv:
        if avg_iv > 40:
            signals.append(f"隐含波动率{avg_iv}%偏高，市场预期大幅波动")
        elif avg_iv < 20:
            signals.append(f"隐含波动率{avg_iv}%偏低，市场预期平稳")
        else:
            signals.append(f"隐含波动率{avg_iv}%正常")
    return " | ".join(signals) if signals else "期权数据信号中性"
