"""
新股分析模块
支持 A股/港股 新股信息、打新统计、估值对比、申购建议
数据源：AKShare（同花顺/东方财富/巨潮）
"""
import pandas as pd
import numpy as np


def fetch_cn_ipo_list(limit: int = 20) -> pd.DataFrame:
    """获取A股近期新股列表"""
    try:
        import akshare as ak
        df = ak.stock_zh_a_new_em()
        cols = {
            '代码': '代码', '名称': '名称', '最新价': '最新价',
            '涨跌幅': '涨跌幅%', '市盈率-动态': '动态PE', '市净率': 'PB',
            '换手率': '换手率%'
        }
        df = df[[c for c in cols if c in df.columns]].rename(columns=cols)
        return df.head(limit)
    except Exception as e:
        return pd.DataFrame()


def fetch_cn_ipo_calendar(limit: int = 20) -> pd.DataFrame:
    """获取A股新股申购日历"""
    try:
        import akshare as ak
        df = ak.stock_ipo_ths()
        return df.head(limit)
    except Exception as e:
        return pd.DataFrame()


def fetch_cn_ipo_info(symbol: str) -> dict:
    """获取A股单只新股详细信息"""
    try:
        import akshare as ak
        df = ak.stock_ipo_info(stock=symbol)
        if df.empty:
            return {}
        info = {row['item']: row['value'] for _, row in df.iterrows()}
        return info
    except Exception as e:
        return {}


def fetch_hk_ipo_list(limit: int = 20) -> pd.DataFrame:
    """获取港股近期新股列表"""
    try:
        import akshare as ak
        df = ak.stock_ipo_hk_ths()
        return df.head(limit)
    except Exception as e:
        return pd.DataFrame()


def fetch_cn_new_stock_stats() -> dict:
    """A股打新统计：近期新股首日涨幅、破发率等"""
    try:
        import akshare as ak
        df = ak.stock_ipo_ths()
        if df.empty:
            return {}

        # 过滤有数据的行
        df_valid = df[df['首日最高涨幅'].notna() & (df['首日最高涨幅'] != '-')]
        if df_valid.empty:
            return {}

        try:
            df_valid = df_valid.copy()
            df_valid['首日涨幅_num'] = pd.to_numeric(
                df_valid['首日最高涨幅'].astype(str).str.replace('%', ''), errors='coerce'
            )
            df_valid = df_valid.dropna(subset=['首日涨幅_num'])

            avg_gain    = round(float(df_valid['首日涨幅_num'].mean()), 2)
            max_gain    = round(float(df_valid['首日涨幅_num'].max()), 2)
            break_count = int((df_valid['首日涨幅_num'] < 0).sum())
            total       = len(df_valid)
            break_rate  = round(break_count / total * 100, 1) if total > 0 else 0

            return {
                'avg_gain':   avg_gain,
                'max_gain':   max_gain,
                'break_rate': break_rate,
                'total':      total,
                'break_count': break_count,
            }
        except Exception:
            return {}
    except Exception:
        return {}


def ipo_valuation_signal(pe: float, industry_pe: float) -> str:
    """根据发行PE与行业PE对比给出估值信号"""
    if not pe or not industry_pe or industry_pe == 0:
        return "估值数据不足"
    ratio = pe / industry_pe
    if ratio < 0.7:
        return f"发行PE({pe:.1f})低于行业PE({industry_pe:.1f})的70%，估值偏低，打新吸引力较高"
    elif ratio < 1.0:
        return f"发行PE({pe:.1f})低于行业PE({industry_pe:.1f})，估值合理，可关注"
    elif ratio < 1.3:
        return f"发行PE({pe:.1f})略高于行业PE({industry_py:.1f})，估值偏高，需谨慎"
    else:
        return f"发行PE({pe:.1f})明显高于行业PE({industry_pe:.1f})，估值较贵，破发风险较高"


def ipo_advice(info: dict, stats: dict) -> list:
    """根据新股信息给出申购建议"""
    advice = []

    # 估值判断
    try:
        issue_pe = float(str(info.get('发行市盈率（按发行后总股本）', '') or '').replace('--', ''))
        industry_pe = float(str(info.get('行业市盈率', '') or '').replace('--', ''))
        if issue_pe and industry_pe:
            ratio = issue_pe / industry_pe
            if ratio < 0.8:
                advice.append(f"✅ 发行PE {issue_pe:.1f}x 低于行业PE {industry_pe:.1f}x，估值具有吸引力")
            elif ratio > 1.2:
                advice.append(f"⚠️ 发行PE {issue_pe:.1f}x 高于行业PE {industry_pe:.1f}x，估值偏贵")
            else:
                advice.append(f"📊 发行PE {issue_pe:.1f}x 与行业PE {industry_pe:.1f}x 相近，估值合理")
    except Exception:
        pass

    # 市场环境
    if stats:
        br = stats.get('break_rate', 0)
        ag = stats.get('avg_gain', 0)
        if br > 30:
            advice.append(f"⚠️ 近期新股破发率 {br}%，市场打新情绪偏冷，需谨慎")
        elif br < 10:
            advice.append(f"✅ 近期新股破发率仅 {br}%，打新市场较热")
        if ag > 20:
            advice.append(f"✅ 近期新股首日平均涨幅 {ag}%，打新收益可观")
        elif ag < 0:
            advice.append(f"⚠️ 近期新股首日平均涨幅为负（{ag}%），市场整体偏弱")

    if not advice:
        advice.append("📊 数据不足，建议结合行业景气度和公司基本面综合判断")

    advice.append("⚠️ 新股投资风险较高，请结合自身风险承受能力谨慎决策")
    return advice
