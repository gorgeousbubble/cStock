import warnings
warnings.filterwarnings("ignore")

import time
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime

from data_fetcher import fetch_stock_data, fetch_realtime_quotes
from indicators import add_indicators
from ai_analyzer import analyze, calc_position_sizing
from target_analyzer import calc_target_price, calc_valuation
from wave_analyzer import analyze_waves
from pattern_analyzer import analyze_patterns
from volume_analyzer import analyze_volume
from fundamental_analyzer import fetch_fundamentals
from quant_analyzer import analyze_quant
from news_analyzer import fetch_news, calc_sentiment_summary
from macro_analyzer import fetch_macro, macro_signal
from option_analyzer import fetch_option_data
from ipo_analyzer import fetch_cn_ipo_list, fetch_hk_ipo_list, fetch_cn_ipo_info, fetch_cn_new_stock_stats, fetch_cn_ipo_calendar, ipo_advice
from industry_analyzer import fetch_industry_comparison, calc_pair_trading, calc_correlation_matrix, get_industry_group
from watchlist import get_watchlist, add_symbol, remove_symbol, update_note, get_symbols

st.set_page_config(page_title="AI量化分析平台", page_icon="📈", layout="wide")

MAG7    = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA"]
CHIPS   = ["AMD", "INTC"]
CN_TOP  = ["600519", "000858", "601318", "000333", "600036"]
HK_TOP  = ["00700", "09988", "03690", "00941", "01299"]

US_PRESETS = {"七姐妹 (Mag7)": MAG7, "芯片股": CHIPS, "全部": MAG7 + CHIPS}
CN_PRESETS = {"核心资产": CN_TOP}
HK_PRESETS = {"蓝筹股": HK_TOP}
PRESETS    = {**US_PRESETS, **CN_PRESETS, **HK_PRESETS}  # 兼容旧代码
PERIOD_OPTIONS   = {"1个月": "1mo", "3个月": "3mo", "6个月": "6mo", "1年": "1y", "2年": "2y", "3年": "3y", "5年": "5y"}
INTERVAL_OPTIONS = {"日线": "1d", "小时线": "1h", "15分钟": "15m", "5分钟": "5m"}
SIGNAL_ICON = {"强烈买入": "🟢", "买入": "🟩", "持有": "🟡", "卖出": "🟥", "强烈卖出": "🔴"}


# ── 缓存 ──────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def load_analysis(symbol, period, interval):
    from concurrent.futures import ThreadPoolExecutor
    df = fetch_stock_data(symbol, period, interval)
    df = add_indicators(df)
    result = analyze(df)
    result["symbol"] = symbol
    period_order_map = {
        "1mo": 3, "3mo": 4, "6mo": 5, "1y": 7, "2y": 9, "3y": 12, "5y": 15
    }
    wave_order = period_order_map.get(period, 7)
    # 并行计算各分析模块
    with ThreadPoolExecutor(max_workers=4) as ex:
        f_wave    = ex.submit(analyze_waves,    df, wave_order)
        f_pattern = ex.submit(analyze_patterns, df)
        f_volume  = ex.submit(analyze_volume,   df)
        f_quant   = ex.submit(analyze_quant,    df)
        result["wave"]    = f_wave.result()
        result["pattern"] = f_pattern.result()
        result["volume"]  = f_volume.result()
        result["quant"]   = f_quant.result()
    return result


@st.cache_data(ttl=7200, show_spinner=False)
def load_fundamentals(symbol):
    return fetch_fundamentals(symbol)


@st.cache_data(ttl=900, show_spinner=False)
def load_news(symbol, limit=10):
    return fetch_news(symbol, limit)


@st.cache_data(ttl=3600, show_spinner=False)
def load_macro(market):
    return fetch_macro(market)


@st.cache_data(ttl=1800, show_spinner=False)
def load_industry(symbol, period):
    return fetch_industry_comparison(symbol, period)


@st.cache_data(ttl=600, show_spinner=False)
def load_option(symbol):
    return fetch_option_data(symbol, 45)


@st.cache_data(ttl=86400, show_spinner=False)
def load_ipo_cn():
    return fetch_cn_ipo_list(30), fetch_cn_new_stock_stats(), fetch_cn_ipo_calendar(20)


@st.cache_data(ttl=86400, show_spinner=False)
def load_ipo_hk():
    return fetch_hk_ipo_list(30)


@st.cache_data(ttl=3, show_spinner=False)
def load_realtime_quotes_cached(symbols_key: str, market: str):
    """实时报价缓存（2秒TTL，避免1秒刷新时重复请求）"""
    symbols = symbols_key.split(",")
    from market_data import fetch_cn_realtime, fetch_hk_realtime
    if market == "🇨🇳 A股":
        return fetch_cn_realtime(symbols)
    elif market == "🇭🇰 港股":
        return fetch_hk_realtime(symbols)
    else:
        return fetch_realtime_quotes(symbols)


@st.cache_data(ttl=120, show_spinner=False)
def load_kline_cached(symbol: str, interval: str):
    """分钟K线缓存（60秒TTL）"""
    df = fetch_stock_data(symbol, "5d", interval)
    return add_indicators(df)


# ── K线图 ─────────────────────────────────────────────────
def make_chart(result: dict, _cur: str = "$") -> go.Figure:
    df     = result["df"]
    symbol = result["symbol"]
    extra  = result["extra"]

    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        row_heights=[0.45, 0.2, 0.18, 0.17],
        vertical_spacing=0.03,
        subplot_titles=(f"{symbol} 价格 & 均线 & 布林带", "成交量", "RSI", "MACD"),
    )
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        name="K线", increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
    ), row=1, col=1)
    for ma, color in [("MA5", "#ff9800"), ("MA20", "#2196f3"), ("MA60", "#9c27b0")]:
        fig.add_trace(go.Scatter(x=df.index, y=df[ma], name=ma, line=dict(width=1, color=color)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_Upper"], name="BB上轨",
                             line=dict(width=1, color="gray", dash="dot"), showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_Lower"], name="BB下轨",
                             line=dict(width=1, color="gray", dash="dot"),
                             fill="tonexty", fillcolor="rgba(128,128,128,0.1)", showlegend=False), row=1, col=1)
    fig.add_hline(y=extra["support"],    line_dash="dot", line_color="#26a69a", line_width=1,
                  annotation_text=f"支撑 {_cur}{extra['support']}", annotation_position="left", row=1, col=1)
    fig.add_hline(y=extra["resistance"], line_dash="dot", line_color="#ef5350",  line_width=1,
                  annotation_text=f"压力 {_cur}{extra['resistance']}", annotation_position="left", row=1, col=1)
    colors = ["#26a69a" if c >= o else "#ef5350" for c, o in zip(df["Close"], df["Open"])]
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="成交量",
                         marker_color=colors, showlegend=False), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["Vol_MA20"], name="Vol MA20",
                             line=dict(width=1, color="orange"), showlegend=False), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], name="RSI",
                             line=dict(width=1.5, color="purple"), showlegend=False), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red",   line_width=1, row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", line_width=1, row=3, col=1)
    fig.add_hrect(y0=70, y1=100, fillcolor="red",   opacity=0.05, row=3, col=1)
    fig.add_hrect(y0=0,  y1=30,  fillcolor="green", opacity=0.05, row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD"],        name="MACD",
                             line=dict(width=1.5, color="#2196f3"), showlegend=False), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD_Signal"], name="Signal",
                             line=dict(width=1.5, color="#ff9800"), showlegend=False), row=4, col=1)
    hist_colors = ["#26a69a" if v >= 0 else "#ef5350" for v in df["MACD_Hist"]]
    fig.add_trace(go.Bar(x=df.index, y=df["MACD_Hist"], name="Hist",
                         marker_color=hist_colors, showlegend=False), row=4, col=1)
    fig.update_layout(height=780, template="plotly_dark", xaxis_rangeslider_visible=False,
                      margin=dict(l=0, r=0, t=40, b=0), legend=dict(orientation="h", y=1.02, x=0))
    return fig


# ── 单股详情 ──────────────────────────────────────────────
def show_detail(result: dict, total_capital: float = 100000, _uid: str = "", modules: list = None):
    if modules is None: modules = ["核心", "预测", "仓位", "波浪", "K线", "量价", "量化", "基本面", "宏观", "行业", "新闻", "总结"]
    def _should_show(m): return m in modules
    # ── 安全初始化所有可能用到的变量 ──────────────────
    wave_result = result.get("wave", {})
    _sym_news   = result.get("symbol", "")

    sym  = result.get("symbol", "")
    name = result.get("name", sym)
    st.markdown(f"# {name}({sym})")
    st.markdown("""<style>
div[data-testid="metric-container"] {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px;
    padding: 10px 14px;
}
div[data-testid="stExpander"] {
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 10px;
    margin-bottom: 6px;
}
div[data-testid="stExpander"] summary p {
    font-size: 1.05rem !important;
    font-weight: 600 !important;
}
hr { border-color: rgba(255,255,255,0.08) !important; }
</style>""", unsafe_allow_html=True)



    from market_data import detect_market as _dm
    _mkt = _dm(sym)
    _cur = {"CN": "¥", "HK": "HK$", "US": "$"}.get(_mkt, "$")
    st.divider()

    extra  = result["extra"]
    advice = result["advice"]

    st.markdown(
        f"### {advice['rating_color']} 综合评级：**{advice['rating']}**　　"
        f"趋势评分：**{extra['trend_score']}/100**　　日期：{result['latest_date']}"
    )
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("最新收盘",   f"{_cur}{result['latest_close']}")
    c2.metric("RSI",        result["rsi"],
              delta="⚠️超买" if result["rsi"] > 70 else ("💡超卖" if result["rsi"] < 30 else "正常"))
    c3.metric("规则信号",   f"{SIGNAL_ICON.get(result['rule_signal'],'')} {result['rule_signal']}")
    c4.metric("AI信号",     result["ml_signal"])
    c5.metric("AI准确率",   f"{result['ml_accuracy']}%")
    c6.metric("年化波动率", f"{extra['volatility']}%")

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("5日涨跌",   f"{extra['ret_5d']}%",  delta=extra["ret_5d"])
    c2.metric("20日涨跌",  f"{extra['ret_20d']}%", delta=extra["ret_20d"])
    c3.metric("60日涨跌",  f"{extra['ret_60d']}%", delta=extra["ret_60d"])
    c4.metric("当前回撤",  f"{extra['current_drawdown']}%", delta=extra["current_drawdown"], delta_color="inverse")
    c5.metric("最大回撤",  f"{extra['max_drawdown']}%", delta_color="off")
    c6.metric("成交量比",  f"{extra['vol_ratio']}x",
              delta="放量" if extra["vol_ratio"] > 1.2 else ("缩量" if extra["vol_ratio"] < 0.8 else "正常"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("60日支撑位", f"{_cur}{extra['support']}",    delta=f"距当前 +{extra['support_pct']}%",    delta_color="off")
    c2.metric("60日压力位", f"{_cur}{extra['resistance']}", delta=f"距当前 -{extra['resistance_pct']}%", delta_color="off")
    c3.metric("52周最高",   f"{_cur}{extra['high_52w']}",   delta=f"{extra['pct_from_high']}%",          delta_color="inverse")
    c4.metric("52周最低",   f"{_cur}{extra['low_52w']}",    delta=f"+{extra['pct_from_low']}%",          delta_color="off")

    st.divider()
    st.plotly_chart(make_chart(result, _cur), use_container_width=True, key=f"chart_{_uid}_1")
    st.divider()

    # ── 综合目标价与操作策略 ──────────────────────────────
    st.subheader("🎯 综合目标价与操作策略")
    with st.spinner("正在综合所有维度计算目标价..."):
        try:
            _fd  = load_fundamentals(sym)
            _fd_clean = _fd if (_fd and not _fd.get("error")) else None
            _ind = load_industry(sym, "3mo")
            _tp  = calc_target_price(result, _fd_clean, _ind)
        except Exception as _tpe:
            _tp = None
            st.warning(f"目标价计算失败: {_tpe}")

    if _tp:
        _st = _tp["strategy"]
        # 顶部核心指标
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("综合目标价", f"{_cur}{_tp['target']}",
                  delta=f"{_tp['target_return']:+.2f}%",
                  delta_color="normal")
        c2.metric("目标价区间", f"{_cur}{_tp['target_low']} ~ {_cur}{_tp['target_high']}")
        c3.metric("置信度", f"{_tp['confidence']}%",
                  delta="高" if _tp['confidence']>=65 else ("低" if _tp['confidence']<45 else "中"),
                  delta_color="off")
        c4.metric("操作方向", f"{_st['dir_color']} {_st['direction']}")
        c5.metric("建议仓位", f"{_st['pos_pct']}%",
                  delta=f"止损 {_cur}{_st['stop']} ({_st['stop_pct']}%)",
                  delta_color="off")

        col_tp1, col_tp2 = st.columns(2)

        with col_tp1:
            # 各维度目标价对比图
            st.markdown("**📊 各维度目标价对比**")
            import plotly.graph_objects as go
            dims   = list(_tp["targets_by_dim"].keys())
            vals   = list(_tp["targets_by_dim"].values())
            wts    = [round(_tp["weights"].get(d, 0)*100, 1) for d in dims]
            d_colors = ["#26a69a" if v > _tp["price"] else "#ef5350" for v in vals]
            fig_tp = go.Figure()
            fig_tp.add_trace(go.Bar(
                x=dims, y=vals, marker_color=d_colors,
                text=[f"{_cur}{v}<br>权重{w}%" for v, w in zip(vals, wts)],
                textposition="outside"
            ))
            fig_tp.add_hline(y=_tp["price"], line_dash="dash", line_color="white",
                             line_width=2, annotation_text=f"当前 {_cur}{_tp['price']}")
            fig_tp.add_hline(y=_tp["target"], line_dash="dot", line_color="#ff9800",
                             line_width=2, annotation_text=f"综合目标 {_cur}{_tp['target']}")
            fig_tp.update_layout(height=300, template="plotly_dark",
                                 margin=dict(l=0,r=0,t=30,b=0), yaxis_title="价格")
            st.plotly_chart(fig_tp, use_container_width=True, key=f"chart_{_uid}_tp1")

            # 分批建仓计划
            st.markdown("**🟢 分批建仓计划**")
            st.dataframe(pd.DataFrame(_st["entry_plan"]), hide_index=True, use_container_width=True)

        with col_tp2:
            # 止盈计划
            st.markdown("**🎯 止盈目标计划**")
            st.dataframe(pd.DataFrame(_st["tp_plan"]), hide_index=True, use_container_width=True)

            # 催化剂 & 风险
            st.markdown("**✅ 做多催化剂**")
            for c in _st["catalysts"]: st.markdown(f"- {c}")
            st.markdown("**⚠️ 主要风险**")
            for r in _st["risks"]:     st.markdown(f"- {r}")

        # 各维度信号汇总
        with st.expander("📋 各维度分析信号详情", expanded=False):
            for sig in _tp["signals"]:
                st.markdown(f"- {sig}")
            st.caption(f"投资期限：{_st['horizon']}　置信度：{_tp['confidence']}%　⚠️ 仅供参考，不构成投资建议")

    st.divider()

    # ── 估值分析 ──────────────────────────────────────────
    st.subheader("💰 多维度估值分析")
    try:
        _fd2 = load_fundamentals(sym)
        _fd2_clean = _fd2 if (_fd2 and not _fd2.get("error")) else None
        _val = calc_valuation(result, _fd2_clean)
    except Exception as _ve:
        _val = None
        st.warning(f"估值计算失败: {_ve}")

    if _val:
        # 核心指标
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("综合公允价值", f"{_cur}{_val['fair_value']}",
                  delta=f"安全边际 {_val['margin_of_safety']:+.1f}%", delta_color="normal")
        c2.metric("估值状态", f"{_val['val_color']} {_val['val_status']}")
        c3.metric("当前所处区间", f"{_val['zone_color']} {_val['price_zone']}")
        c4.metric("合理买入价", f"{_cur}{_val['buy_price']} ~ {_cur}{_val['hold_high']}")
        c5.metric("强烈买入价", f"≤ {_cur}{_val['strong_buy']}",
                  delta=f"减仓价 ≥ {_cur}{_val['reduce_price']}", delta_color="off")

        col_v1, col_v2 = st.columns([3, 2])

        with col_v1:
            st.markdown("**📊 各估值方法对比**")
            _m_names = list(_val["methods"].keys())
            _m_vals  = list(_val["methods"].values())
            _m_devs  = [_val["deviations"][m] for m in _m_names]
            _cur_price = result["latest_close"]
            _m_colors = ["#26a69a" if v > _cur_price else "#ef5350" for v in _m_vals]
            fig_val = go.Figure()
            fig_val.add_trace(go.Bar(
                x=_m_names, y=_m_vals, marker_color=_m_colors,
                text=[f"{_cur}{v}<br>{d:+.1f}%" for v, d in zip(_m_vals, _m_devs)],
                textposition="outside"
            ))
            fig_val.add_hline(y=result["latest_close"], line_dash="dash", line_color="white",
                              line_width=2, annotation_text=f"当前 {_cur}{result['latest_close']}")
            fig_val.add_hline(y=_val["fair_value"], line_dash="dot", line_color="#ff9800",
                              line_width=2, annotation_text=f"公允 {_cur}{_val['fair_value']}")
            fig_val.update_layout(height=320, template="plotly_dark",
                                  margin=dict(l=0, r=0, t=30, b=0), yaxis_title="价格")
            st.plotly_chart(fig_val, use_container_width=True, key=f"chart_{_uid}_val1")

        with col_v2:
            st.markdown("**📋 估值方法明细**")
            _val_rows = [
                {"方法": m, "估值": f"{_cur}{v}",
                 "偏离": f"{_val['deviations'][m]:+.1f}%",
                 "说明": _val["notes"].get(m, "")}
                for m, v in _val["methods"].items()
            ]
            st.dataframe(pd.DataFrame(_val_rows), hide_index=True, use_container_width=True)

            st.divider()
            st.markdown("**💡 估值结论**")
            for a in _val["val_advice"]:
                st.markdown(f"- {a}")
            st.caption("⚠️ 估值基于公开财务数据，仅供参考，不构成投资建议")

        # 合理价格区间表
        st.markdown(f"**🎯 当前价格所处区间：{_val['zone_color']} {_val['price_zone']}**")
        col_z1, col_z2 = st.columns([1, 2])
        with col_z1:
            st.dataframe(pd.DataFrame(_val["price_zones"]), hide_index=True, use_container_width=True)
            st.caption("基于综合公允价值计算，仅供参考")
        with col_z2:
            # 价格区间可视化
            _zones_y = [
                _val["strong_buy"], _val["buy_price"],
                _val["hold_low"],   _val["hold_high"],
                _val["reduce_price"], _val["strong_sell"]
            ]
            _zone_labels = [
                f"强烈买入 {_cur}{_val['strong_buy']}",
                f"买入 {_cur}{_val['buy_price']}",
                f"合理持有下限 {_cur}{_val['hold_low']}",
                f"合理持有上限 {_cur}{_val['hold_high']}",
                f"减仓 {_cur}{_val['reduce_price']}",
                f"强烈卖出 {_cur}{_val['strong_sell']}",
            ]
            _zone_colors = ["#1b5e20","#388e3c","#f9a825","#f57f17","#e64a19","#b71c1c"]
            fig_zone = go.Figure()
            for i in range(len(_zones_y) - 1):
                fig_zone.add_hrect(
                    y0=_zones_y[i], y1=_zones_y[i+1],
                    fillcolor=_zone_colors[i], opacity=0.25,
                    annotation_text=_zone_labels[i],
                    annotation_position="right"
                )
            fig_zone.add_hline(y=result["latest_close"], line_dash="solid",
                               line_color="white", line_width=3,
                               annotation_text=f"当前 {_cur}{result['latest_close']}",
                               annotation_position="left")
            fig_zone.add_hline(y=_val["fair_value"], line_dash="dot",
                               line_color="#ff9800", line_width=2,
                               annotation_text=f"公允 {_cur}{_val['fair_value']}")
            fig_zone.update_layout(
                height=320, template="plotly_dark",
                margin=dict(l=0, r=160, t=10, b=0),
                yaxis=dict(title="价格",
                           range=[_val["strong_buy"]*0.9, _val["strong_sell"]*1.05]),
                xaxis=dict(visible=False),
            )
            st.plotly_chart(fig_zone, use_container_width=True, key=f"chart_{_uid}_val2")

        st.divider()
        st.markdown("**💡 估值结论**")
        for a in _val["val_advice"]:
            st.markdown(f"- {a}")
        st.caption("⚠️ 估值基于公开财务数据，仅供参考，不构成投资建议")

    st.divider()

    col_adv, col_charts = st.columns([1, 1])
    with col_adv:
        st.subheader("📋 综合分析建议")
        if advice["points"]:
            st.markdown("**✅ 利多因素**")
            for p in advice["points"]: st.markdown(f"- {p}")
        if advice["risks"]:
            st.markdown("**⚠️ 风险提示**")
            for r in advice["risks"]:  st.markdown(f"- {r}")
        st.markdown("**💡 操作建议**")
        for a in advice["actions"]:    st.markdown(f"- {a}")
        st.divider()
        st.markdown("**📐 均线状态**")
        price = result["latest_close"]
        for ma_name, ma_val in [("MA5", result["ma5"]), ("MA20", result["ma20"]), ("MA60", result["ma60"])]:
            diff = round((price / ma_val - 1) * 100, 1)
            icon = "🟢" if price > ma_val else "🔴"
            st.markdown(f"- {icon} {ma_name}: ${ma_val}　（{'+' if diff>0 else ''}{diff}%）")

    with col_charts:
        st.subheader("🤖 AI 预测概率")
        proba = result["ml_proba"]
        fig_pie = go.Figure(go.Pie(
            labels=list(proba.keys()), values=list(proba.values()), hole=0.4,
            marker_colors=["#26a69a", "#aaaaaa", "#ef5350"],
        ))
        fig_pie.update_layout(height=260, template="plotly_dark", margin=dict(l=0,r=0,t=10,b=0),
                              showlegend=True, legend=dict(orientation="h"))
        st.plotly_chart(fig_pie, use_container_width=True, key=f"chart_{_uid}_2")

        st.subheader("🔍 特征重要性 Top 8")
        fi = result["feature_importance"].head(8)
        fig_fi = go.Figure(go.Bar(x=fi.values[::-1], y=fi.index[::-1], orientation="h", marker_color="#2196f3"))
        fig_fi.update_layout(height=260, template="plotly_dark", margin=dict(l=0,r=0,t=10,b=0))
        st.plotly_chart(fig_fi, use_container_width=True, key=f"chart_{_uid}_3")

    # ── 累计收益率 ────────────────────────────────────────
    st.subheader("📈 累计收益率走势")
    df = result["df"]
    ret = (df["Close"] / df["Close"].iloc[0] - 1) * 100
    color = "#26a69a" if ret.iloc[-1] >= 0 else "#ef5350"
    fig_ret = go.Figure(go.Scatter(x=df.index, y=ret, fill="tozeroy",
                                   fillcolor="rgba(38,166,154,0.15)" if ret.iloc[-1] >= 0 else "rgba(239,83,80,0.15)",
                                   line=dict(color=color, width=2), name="累计收益率"))
    fig_ret.add_hline(y=0, line_dash="dash", line_color="gray", line_width=1)
    fig_ret.update_layout(height=250, template="plotly_dark", margin=dict(l=0,r=0,t=10,b=0), yaxis_title="收益率(%)")
    st.plotly_chart(fig_ret, use_container_width=True, key=f"chart_{_uid}_4")

    st.divider()

    # ── 走势预测 ──────────────────────────────────────────
    st.subheader("🔮 AI 走势预测")
    fc   = result["forecast"]
    fcs  = fc["forecasts"]
    latest_price = result["latest_close"]

    # 预测目标价卡片
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("趋势方向", f"{fc['trend_dir']} ({fc['trend_slope']:+.2f}/日)",
              delta="上升" if fc["trend_slope"] > 0 else "下降", delta_color="normal")
    for col, label in zip([c2, c3, c4], ["5日", "10日", "20日"]):
        f = fcs[label]
        col.metric(
            f"预测目标价 ({label})",
            f"${f['price']}",
            delta=f"{f['return']:+.2f}%  ({f['direction']})",
            delta_color="normal",
        )

    col_mc, col_tbl = st.columns([2, 1])

    with col_mc:
        st.markdown("**Monte Carlo 30日价格路径模拟（1000条）**")
        import numpy as np
        future_dates = pd.date_range(start=df.index[-1], periods=fc["mc_days"] + 1, freq="B")[1:]

        fig_mc = go.Figure()
        # 历史价格（最近60日）
        hist_tail = df["Close"].tail(60)
        fig_mc.add_trace(go.Scatter(
            x=hist_tail.index, y=hist_tail.values,
            name="历史价格", line=dict(color="#aaaaaa", width=1.5)
        ))
        # 90% 置信区间
        fig_mc.add_trace(go.Scatter(
            x=list(future_dates) + list(future_dates[::-1]),
            y=fc["mc_p90"] + fc["mc_p10"][::-1],
            fill="toself", fillcolor="rgba(33,150,243,0.08)",
            line=dict(color="rgba(0,0,0,0)"), name="90% 区间", showlegend=True
        ))
        # 50% 置信区间
        fig_mc.add_trace(go.Scatter(
            x=list(future_dates) + list(future_dates[::-1]),
            y=fc["mc_p75"] + fc["mc_p25"][::-1],
            fill="toself", fillcolor="rgba(33,150,243,0.18)",
            line=dict(color="rgba(0,0,0,0)"), name="50% 区间", showlegend=True
        ))
        # 均值路径
        fig_mc.add_trace(go.Scatter(
            x=future_dates, y=fc["mc_mean"],
            name="预测均值", line=dict(color="#2196f3", width=2, dash="dash")
        ))
        # 乐观/悲观
        fig_mc.add_trace(go.Scatter(
            x=future_dates, y=fc["mc_p90"],
            name=f"乐观 ${fc['mc_bull']}", line=dict(color="#26a69a", width=1, dash="dot")
        ))
        fig_mc.add_trace(go.Scatter(
            x=future_dates, y=fc["mc_p10"],
            name=f"悲观 ${fc['mc_bear']}", line=dict(color="#ef5350", width=1, dash="dot")
        ))
        # 当前价水平线
        fig_mc.add_hline(y=latest_price, line_dash="dash", line_color="white",
                         line_width=1, annotation_text=f"当前 {_cur}{latest_price}")
        fig_mc.update_layout(
            height=380, template="plotly_dark",
            margin=dict(l=0, r=0, t=10, b=0),
            yaxis_title="价格 ($)",
            legend=dict(orientation="h", y=1.08)
        )
        st.plotly_chart(fig_mc, use_container_width=True, key=f"chart_{_uid}_5")

    with col_tbl:
        st.markdown("**预测摘要**")
        st.metric("30日上涨概率", f"{fc['mc_prob_up']}%",
                  delta="偏多" if fc["mc_prob_up"] > 55 else ("偏空" if fc["mc_prob_up"] < 45 else "中性"))
        st.metric("预测均值（30日）", f"${fc['mc_mean_final']}",
                  delta=f"{round((fc['mc_mean_final']/latest_price-1)*100,2):+.2f}%")
        st.metric("乐观目标（90%）", f"${fc['mc_bull']}",
                  delta=f"{round((fc['mc_bull']/latest_price-1)*100,2):+.2f}%")
        st.metric("悲观目标（10%）", f"${fc['mc_bear']}",
                  delta=f"{round((fc['mc_bear']/latest_price-1)*100,2):+.2f}%", delta_color="inverse")
        st.divider()
        st.markdown("**ML 目标价区间**")
        for label in ["5日", "10日", "20日"]:
            f = fcs[label]
            icon = "🟢" if f["direction"] == "上涨" else "🔴"
            st.markdown(f"{icon} **{label}**: ${f['price']}　`${f['low']} ~ ${f['high']}`")
        st.caption("区间为模型误差范围，仅供参考")
        st.caption("⚠️ 预测不代表实际走势，不构成投资建议")

    # ── 多模型对比图 ────────────────────────────────────
    mc = fc.get("model_comparison", {})
    if mc:
        st.markdown("**📊 多模型预测对比（30日）**")
        model_colors = {"ARIMA": "#ff9800", "指数平滑": "#9c27b0",
                        "线性趋势": "#4caf50", "Monte Carlo": "#2196f3"}
        fig_cmp = go.Figure()
        hist_tail = df["Close"].tail(30)
        fig_cmp.add_trace(go.Scatter(
            x=hist_tail.index, y=hist_tail.values,
            name="历史价格", line=dict(color="#aaaaaa", width=2)
        ))
        for model_name, mdata in mc.items():
            color = model_colors.get(model_name, "white")
            fig_cmp.add_trace(go.Scatter(
                x=future_dates, y=mdata["series"],
                name=f"{model_name} ${mdata['price_30d']} ({mdata['return_30d']:+.1f}%)",
                line=dict(color=color, width=2, dash="dash")
            ))
        fig_cmp.add_hline(y=latest_price, line_dash="dot", line_color="white", line_width=1)
        fig_cmp.update_layout(
            height=320, template="plotly_dark",
            margin=dict(l=0, r=0, t=10, b=0),
            yaxis_title="价格 ($)",
            legend=dict(orientation="h", y=1.1)
        )
        st.plotly_chart(fig_cmp, use_container_width=True, key=f"chart_{_uid}_6")

        # 模型对比表
        cmp_rows = []
        for model_name, mdata in mc.items():
            cmp_rows.append({
                "模型": model_name,
                "30日目标价": f"${mdata['price_30d']}",
                "预测涨跌": f"{mdata['return_30d']:+.2f}%",
                "方向": "🟢 上涨" if mdata['return_30d'] > 0 else "🔴 下跌"
            })
        st.dataframe(pd.DataFrame(cmp_rows), hide_index=True, use_container_width=True)

    st.divider()

    # ── 仓位控制与买入建议 ────────────────────────────────
    st.subheader("💹 买入价格与仓位控制")
    ps = calc_position_sizing(result, total_capital)

    # 核心指标卡片
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("ATR (14日)",    f"${ps['atr']}")
    c2.metric("止损价",       f"${ps['stop_loss']}",  delta=f"{ps['stop_pct']}%", delta_color="inverse")
    c3.metric("盈亏比 (R:R)",  f"{ps['rr_ratio']}:1")
    c4.metric("Kelly 仓位",   f"{ps['kelly']}%",      delta=f"Half-Kelly {ps['half_kelly']}%", delta_color="off")
    c5.metric("建议仓位比例",  f"{ps['final_pct']}%",
              delta=f"{_cur}{round(total_capital * ps['final_pct'] / 100):,.0f}", delta_color="off")

    col_entry, col_tp = st.columns(2)

    with col_entry:
        st.markdown("**🟢 分批建仓计划**")
        batch_rows = []
        for b in ps["batches"]:
            batch_rows.append({
                "批次":   b["batch"],
                "买入价": f"{_cur}{b['price']}",
                "仓位比": f"{round(b['pct']*100, 1)}%",
                "金额":   f"{_cur}{b['amount']:,.0f}",
                "股数":   f"{b['shares']} 股",
                "条件":   b["condition"],
            })
        st.dataframe(pd.DataFrame(batch_rows), hide_index=True, use_container_width=True)

        st.markdown("**🔴 止损设置**")
        st.markdown(
            f"- 止损价：**{_cur}{ps['stop_loss']}**（下跌 {ps['stop_pct']}%）"
            f"\n- ATR止损：当前价 - 2×ATR = {_cur}{round(result['latest_close'] - ps['atr']*2, 2)}"
            f"\n- 支撑位止损：{_cur}{ps['stop_loss']}（支撑位下方1%）"
        )

    with col_tp:
        st.markdown("**🎯 止盈目标**")
        tp_rows = [
            {"目标": "TP1 (1.5R)", "价格": f"{_cur}{ps['tp1']}", "涨幅": f"+{ps['tp1_pct']}%",
             "建议": "减仓30-40%仓位"},
            {"目标": "TP2 (2.5R)", "价格": f"{_cur}{ps['tp2']}", "涨幅": f"+{ps['tp2_pct']}%",
             "建议": "减仓30-40%仓位"},
            {"目标": "TP3 (压力位)", "价格": f"{_cur}{ps['tp3']}", "涨幅": f"+{ps['tp3_pct']}%",
             "建议": "剩余仓位清仓"},
        ]
        st.dataframe(pd.DataFrame(tp_rows), hide_index=True, use_container_width=True)

        # 盈亏比可视化
        fig_rr = go.Figure()
        prices_rr = [ps["stop_loss"], result["latest_close"], ps["tp1"], ps["tp2"], ps["tp3"]]
        labels_rr = [f"止损 {_cur}{ps['stop_loss']}", f"当前 {_cur}{result['latest_close']}",
                     f"TP1 {_cur}{ps['tp1']}", f"TP2 {_cur}{ps['tp2']}", f"TP3 {_cur}{ps['tp3']}"]
        colors_rr = ["#ef5350", "#ffffff", "#66bb6a", "#26a69a", "#00897b"]
        fig_rr.add_trace(go.Bar(
            x=labels_rr, y=prices_rr,
            marker_color=colors_rr, showlegend=False,
        ))
        fig_rr.add_hline(y=result["latest_close"], line_dash="dash", line_color="white", line_width=1)
        fig_rr.update_layout(height=220, template="plotly_dark",
                             margin=dict(l=0, r=0, t=10, b=0), yaxis_title="价格 ($)")
        st.plotly_chart(fig_rr, use_container_width=True, key=f"chart_{_uid}_7")

        st.markdown(
            f"**💡 仓位逻辑**"
            f"\n- 信号强度得分：{ps['signal_score']}/7"
            f"\n- 分配资金：${total_capital:,.0f}"
            f"\n- 建议投入：{_cur}{round(total_capital * ps['final_pct'] / 100):,.0f} ({ps['final_pct']}%)"
            f"\n- 最大亏损：{_cur}{round(total_capital * ps['final_pct'] / 100 * abs(ps['stop_pct']) / 100):,.0f}"
        )
        st.caption("⚠️ 仓位建议基于 Kelly 公式 + ATR，仅供参考，不构成投资建议")


    st.divider()





    # ── 波浪理论 ──────────────────────────────────────────


    st.divider()
    # ── 扩展分析 ──────────────────────────────────────
    st.success("核心分析已在上方显示完毕，展开下方查看更多详细分析。")
    with st.expander("🔬 扩展分析（点击展开）", expanded=False):
        st.divider()

        wave_result = result.get("wave", {})
        waves  = wave_result.get("waves", [])
        pivots = wave_result.get("pivots", pd.DataFrame())
        pos    = wave_result.get("position", {})
        fib    = wave_result.get("fib_levels", {})
        close  = wave_result.get("close", result["df"]["Close"])

        # 波浪位信息卡
        signal_color_map = {
            "buy": "🟢", "weak_buy": "🟩", "sell": "🔴",
            "partial_sell": "🟥", "wait": "🟡", "neutral": "⚪"
        }
        sig_icon = signal_color_map.get(pos.get("signal", "neutral"), "⚪")
        order_used = wave_result.get("order_used", "?")
        data_range = f"{str(close.index[0])[:10]} ~ {str(close.index[-1])[:10]}" if len(close) > 0 else ""
        c1, c2, c3 = st.columns(3)
        c1.metric("当前浪位", f"{sig_icon} 第 {pos.get('position', 'N/A')} 浪",
                  delta=f"数据 {data_range} | order={order_used}", delta_color="off")
        c2.markdown(f"**浪位描述**\n\n{pos.get('description', '')}")
        c3.markdown(f"**🌊 市场特征**\n\n{pos.get('market_char', '')}")

        col_wave, col_fib = st.columns([2, 1])

        with col_wave:
            st.markdown("**K线 + 波浪标注图**")
            fig_wave = go.Figure()

            # K线（最近120日）
            df_tail = result["df"].tail(120)
            fig_wave.add_trace(go.Candlestick(
                x=df_tail.index, open=df_tail["Open"], high=df_tail["High"],
                low=df_tail["Low"], close=df_tail["Close"],
                name="K线", increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
                showlegend=False,
            ))

            # 波浪连线
            if waves:
                wave_dates  = [w["date"]  for w in waves]
                wave_prices = [w["price"] for w in waves]
                fig_wave.add_trace(go.Scatter(
                    x=wave_dates, y=wave_prices,
                    mode="lines", name="波浪连线",
                    line=dict(color="#ff9800", width=2, dash="dot"),
                    showlegend=True,
                ))
                # 波浪标注
                impulse_colors    = {"起点": "#aaaaaa", "①": "#26a69a", "②": "#ef5350",
                                      "③": "#26a69a", "④": "#ef5350", "⑤": "#26a69a"}
                correction_colors = {"A": "#ff5722", "B": "#9c27b0", "C": "#ff5722"}
                for w in waves:
                    color = impulse_colors.get(w["wave"], correction_colors.get(w["wave"], "white"))
                    fig_wave.add_annotation(
                        x=w["date"], y=w["price"],
                        text=f"<b>{w['wave']}</b>",
                        showarrow=True, arrowhead=2, arrowsize=1,
                        arrowcolor=color, font=dict(size=13, color=color),
                        ax=0, ay=-30 if w["type"] == "H" else 30,
                    )

            # Fibonacci 水平线（只画整体推动浪）
            fib_colors = {
                0.0: "#ffffff", 0.236: "#26a69a", 0.382: "#4caf50",
                0.5: "#ff9800",  0.618: "#f44336", 0.786: "#9c27b0", 1.0: "#ffffff"
            }
            key = "整体推动浪" if "整体推动浪" in fib else list(fib.keys())[0] if fib else None
            if key:
                for level in fib[key]:
                    if level["ratio"] in fib_colors:
                        fig_wave.add_hline(
                            y=level["price"],
                            line_dash="dot", line_width=1,
                            line_color=fib_colors[level["ratio"]],
                            annotation_text=f"Fib {level['ratio']} (${level['price']})",
                            annotation_position="right",
                        )

            fig_wave.update_layout(
                height=500, template="plotly_dark",
                xaxis_rangeslider_visible=False,
                margin=dict(l=0, r=80, t=10, b=0),
            )
            st.plotly_chart(fig_wave, use_container_width=True, key=f"chart_{_uid}_8")

        with col_fib:
            st.markdown("**Fibonacci 水平**")
            for fib_name, levels in fib.items():
                with st.expander(fib_name, expanded=(fib_name == "整体推动浪")):
                    rows = []
                    current = float(close.iloc[-1])
                    for lv in levels:
                        dist = round((lv["price"] / current - 1) * 100, 1)
                        rows.append({
                            "Fib": f"{lv['ratio']:.3f}",
                            "价格": f"${lv['price']}",
                            "距当前": f"{dist:+.1f}%"
                        })
                    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

            st.divider()
            st.markdown("**波浪节点列表**")
            if waves:
                wave_rows = [{"浪": w["wave"], "日期": str(w["date"])[:10],
                              "价格": f"${round(w['price'],2)}",
                              "类型": "高点" if w["type"]=="H" else "低点"} for w in waves]
                st.dataframe(pd.DataFrame(wave_rows), hide_index=True, use_container_width=True)

            st.divider()
            st.markdown("**💡 操作建议**")
            for a in pos.get("advice", []):
                st.markdown(f"- {a}")

            entry_list = pos.get("entry", [])
            if entry_list:
                st.markdown("**🟢 入场时机**")
                for e in entry_list:
                    st.markdown(f"- {e}")

            risk_list = pos.get("risk", [])
            if risk_list:
                st.markdown("**🔴 风险提示**")
                for r in risk_list:
                    st.markdown(f"- {r}")

            fib_hints = pos.get("fib_hints", [])
            if fib_hints:
                st.markdown("**📐 Fibonacci 关键价位**")
                for f in fib_hints:
                    st.markdown(f"- {f}")


        # ── K线形态识别 ────────────────────────────────────────

        pat = result.get("pattern", {})

        # 趋势线指标卡
        tl = pat.get("trendline", {})
        if tl:
            tl_icon = "🟢" if tl["signal"] == "bullish" else ("🔴" if tl["signal"] == "bearish" else "🟡")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("趋势方向", f"{tl_icon} {tl['direction']}趋势")
            c2.metric("趋势强度", f"{tl['strength']} (R²={tl['r2']})",
                      delta=f"斜率 {tl['slope']:+.3f}/日", delta_color="off")
            c3.metric("趋势线当前价", f"${tl['current_trend']}")
            c4.metric("趋势线5日预测", f"${tl['future_5d']}")

        col_pat1, col_pat2 = st.columns(2)

        with col_pat1:
            # 单根K线形态
            single = pat.get("single_candles", pd.DataFrame())
            st.markdown("**🕯️ 单根K线形态（近20日）**")
            if not single.empty:
                st.dataframe(single, hide_index=True, use_container_width=True)
            else:
                st.caption("近20日内未识别到明显单根形态")

            # 双根K线形态
            double = pat.get("double_candles", [])
            st.markdown("**🔄 双根K线形态**")
            if double:
                st.dataframe(pd.DataFrame(double), hide_index=True, use_container_width=True)
            else:
                st.caption("近30日内未识别到吃线/孕线形态")

        with col_pat2:
            # 多根K线形态（头肩顶/底、双顶/底）
            multi = pat.get("multi_patterns", [])
            st.markdown("**🏛️ 大形态识别（头肩顶/底、双顶/底）**")
            if multi:
                st.dataframe(pd.DataFrame(multi), hide_index=True, use_container_width=True)
            else:
                st.caption("未识别到头肩顶/底、双顶/底形态")

            # 葛兰比八大法则
            granville = pat.get("granville", [])
            st.markdown("**📊 葛兰比八大法则**")
            if granville:
                st.dataframe(pd.DataFrame(granville), hide_index=True, use_container_width=True)
            else:
                st.caption("当前无葛兰比信号触发")


        # ── 量价分析 ──────────────────────────────────────────

        vol_result = result.get("volume", {})
        if vol_result:
            obv   = vol_result["obv"]
            vwap  = vol_result["vwap"]
            mfi   = vol_result["mfi"]
            chip  = vol_result["chip"]
            df_v  = result["df"]

            # 指标卡片
            c1, c2, c3, c4 = st.columns(4)
            vwap_icon = "🟢" if vol_result["vwap_signal"] == "bullish" else "🔴"
            obv_icon  = "🟢" if vol_result["obv_signal"]  == "bullish" else "🔴"
            mfi_icon  = "🔴" if vol_result["mfi_signal"] == "超买" else ("🟢" if vol_result["mfi_signal"] == "超卖" else "⚪")
            chip_icon = "🟢" if chip["signal"] == "bullish" else ("🔴" if chip["signal"] == "bearish" else "🟡")
            c1.metric("VWAP", f"${vol_result['latest_vwap']}",
                      delta=f"{vwap_icon} 价格偏离 {vol_result['vwap_pct']:+.2f}%", delta_color="off")
            c2.metric("MFI 资金流量", vol_result["latest_mfi"],
                      delta=f"{mfi_icon} {vol_result['mfi_signal']}", delta_color="off")
            c3.metric("OBV 趋势", f"{obv_icon} {vol_result['obv_trend']}")
            c4.metric("筹码峰价格", f"${chip['peak_price']}",
                      delta=f"{chip_icon} 获利盘 {chip['profit_pct']}%", delta_color="off")

            col_v1, col_v2 = st.columns(2)

            with col_v1:
                # OBV + 价格双轴图
                st.markdown("**OBV 能量潮 + 价格**")
                fig_obv = go.Figure()
                fig_obv.add_trace(go.Scatter(
                    x=df_v.index, y=df_v["Close"],
                    name="收盘价", line=dict(color="#aaaaaa", width=1.5), yaxis="y1"
                ))
                fig_obv.add_trace(go.Scatter(
                    x=obv.index, y=obv.values,
                    name="OBV", line=dict(color="#2196f3", width=1.5), yaxis="y2"
                ))
                fig_obv.update_layout(
                    height=280, template="plotly_dark",
                    margin=dict(l=0, r=0, t=10, b=0),
                    yaxis=dict(title="价格", side="left"),
                    yaxis2=dict(title="OBV", side="right", overlaying="y"),
                    legend=dict(orientation="h", y=1.1),
                )
                st.plotly_chart(fig_obv, use_container_width=True, key=f"chart_{_uid}_9")

                # VWAP 图
                st.markdown("**VWAP 成交量加权均价**")
                fig_vwap = go.Figure()
                fig_vwap.add_trace(go.Scatter(
                    x=df_v.index, y=df_v["Close"],
                    name="收盘价", line=dict(color="#aaaaaa", width=1.5)
                ))
                fig_vwap.add_trace(go.Scatter(
                    x=vwap.index, y=vwap.values,
                    name="VWAP(20)", line=dict(color="#ff9800", width=2, dash="dash")
                ))
                fig_vwap.add_hline(y=vol_result["latest_vwap"], line_dash="dot",
                                   line_color="#ff9800", line_width=1)
                fig_vwap.update_layout(
                    height=250, template="plotly_dark",
                    margin=dict(l=0, r=0, t=10, b=0),
                    legend=dict(orientation="h", y=1.1),
                )
                st.plotly_chart(fig_vwap, use_container_width=True, key=f"chart_{_uid}_10")

            with col_v2:
                # MFI 图
                st.markdown("**MFI 资金流量指标**")
                fig_mfi = go.Figure()
                fig_mfi.add_trace(go.Scatter(
                    x=mfi.index, y=mfi.values,
                    name="MFI", line=dict(color="#9c27b0", width=1.5),
                    fill="tozeroy", fillcolor="rgba(156,39,176,0.1)"
                ))
                fig_mfi.add_hline(y=80, line_dash="dash", line_color="red",   line_width=1,
                                  annotation_text="超买 80")
                fig_mfi.add_hline(y=20, line_dash="dash", line_color="green", line_width=1,
                                  annotation_text="超卖 20")
                fig_mfi.add_hrect(y0=80, y1=100, fillcolor="red",   opacity=0.05)
                fig_mfi.add_hrect(y0=0,  y1=20,  fillcolor="green", opacity=0.05)
                fig_mfi.update_layout(
                    height=250, template="plotly_dark",
                    margin=dict(l=0, r=0, t=10, b=0),
                    yaxis=dict(range=[0, 100]),
                )
                st.plotly_chart(fig_mfi, use_container_width=True, key=f"chart_{_uid}_11")

                # 筹码分布图
                st.markdown("**📊 筹码分布（成本密集区）**")
                bins   = chip["bins"]
                prices = [(chip["price_bins"][i][0] + chip["price_bins"][i][1]) / 2 for i in range(bins)]
                dist   = chip["chip_dist"]
                cur    = chip["current"]
                bar_colors = ["#ef5350" if prices[i] > cur else "#26a69a" for i in range(bins)]
                fig_chip = go.Figure(go.Bar(
                    x=dist, y=prices,
                    orientation="h",
                    marker_color=bar_colors,
                    name="筹码分布",
                ))
                fig_chip.add_hline(y=cur, line_dash="dash", line_color="white", line_width=2,
                                   annotation_text=f"当前 ${cur}")
                fig_chip.add_hline(y=chip["peak_price"], line_dash="dot", line_color="#ff9800",
                                   line_width=1, annotation_text=f"筹码峰 ${chip['peak_price']}")
                fig_chip.update_layout(
                    height=280, template="plotly_dark",
                    margin=dict(l=0, r=0, t=10, b=0),
                    xaxis_title="筹码占比(%)",
                    yaxis_title="价格 ($)",
                )
                st.plotly_chart(fig_chip, use_container_width=True, key=f"chart_{_uid}_12")

            # 量价背离信号
            divergence = vol_result.get("divergence", [])
            if divergence:
                st.markdown("**⚠️ 量价背离信号**")
                st.dataframe(pd.DataFrame(divergence), hide_index=True, use_container_width=True)


        # ── 量化策略分析 ────────────────────────────────────────

        qt = result.get("quant", {})
        if qt:
            zs   = qt["zscore"]
            mom  = qt["momentum"]
            risk = qt["risk"]

            # ─ 指标卡片 ─
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Z-Score", zs["latest_z"], delta=zs["signal"], delta_color="off")
            c2.metric("动量信号", mom["signal"])
            c3.metric("夏普比率", risk["sharpe"], delta=risk["sharpe_rating"], delta_color="off")
            c4.metric("索提诺比率", risk["sortino"])
            c5.metric("年化收益", f"{risk['annual_ret']}%",
                      delta=f"波动率 {risk['annual_vol']}%", delta_color="off")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("胜率", f"{risk['win_rate']}%")
            c2.metric("盈亏比", f"{risk['profit_loss']}:1")
            c3.metric("卡玛比率", risk["calmar"])
            c4.metric("最大回撤", f"{risk['max_dd']}%", delta_color="off")

            col_q1, col_q2 = st.columns(2)

            with col_q1:
                # Z-Score 均值回归图
                st.markdown("**📉 Z-Score 均值回归**")
                df_q  = result["df"]
                fig_z = go.Figure()
                fig_z.add_trace(go.Scatter(
                    x=df_q.index, y=df_q["Close"],
                    name="收盘价", line=dict(color="#aaaaaa", width=1.5)
                ))
                fig_z.add_trace(go.Scatter(
                    x=zs["ma"].index, y=zs["ma"].values,
                    name="MA20", line=dict(color="#2196f3", width=1.5)
                ))
                fig_z.add_trace(go.Scatter(
                    x=zs["upper_2"].index, y=zs["upper_2"].values,
                    name="+2σ", line=dict(color="#ef5350", width=1, dash="dot"),
                    fill=None
                ))
                fig_z.add_trace(go.Scatter(
                    x=zs["lower_2"].index, y=zs["lower_2"].values,
                    name="-2σ", line=dict(color="#26a69a", width=1, dash="dot"),
                    fill="tonexty", fillcolor="rgba(33,150,243,0.05)"
                ))
                fig_z.add_trace(go.Scatter(
                    x=zs["upper_1"].index, y=zs["upper_1"].values,
                    name="+1σ", line=dict(color="#ef5350", width=1, dash="dash"), showlegend=False
                ))
                fig_z.add_trace(go.Scatter(
                    x=zs["lower_1"].index, y=zs["lower_1"].values,
                    name="-1σ", line=dict(color="#26a69a", width=1, dash="dash"), showlegend=False
                ))
                fig_z.update_layout(
                    height=300, template="plotly_dark",
                    margin=dict(l=0, r=0, t=10, b=0),
                    legend=dict(orientation="h", y=1.1)
                )
                st.plotly_chart(fig_z, use_container_width=True, key=f"chart_{_uid}_13")
                st.caption(f"当前 Z-Score: **{zs['latest_z']}**　{zs['advice']}")

                # 回撤走势图
                st.markdown("**📉 回撤走势**")
                dd = risk["drawdown_series"]
                fig_dd = go.Figure(go.Scatter(
                    x=dd.index, y=dd.values * 100,
                    fill="tozeroy", fillcolor="rgba(239,83,80,0.2)",
                    line=dict(color="#ef5350", width=1.5), name="回撤"
                ))
                fig_dd.add_hline(y=0, line_dash="dash", line_color="gray", line_width=1)
                fig_dd.update_layout(
                    height=220, template="plotly_dark",
                    margin=dict(l=0, r=0, t=10, b=0),
                    yaxis_title="回撤(%)"
                )
                st.plotly_chart(fig_dd, use_container_width=True, key=f"chart_{_uid}_14")

            with col_q2:
                # 动量多周期收益柱状图
                st.markdown("**🚀 多周期动量收益**")
                ret_data = mom["returns"]
                if ret_data:
                    labels = list(ret_data.keys())
                    values = list(ret_data.values())
                    bar_colors = ["#26a69a" if v >= 0 else "#ef5350" for v in values]
                    fig_mom = go.Figure(go.Bar(
                        x=labels, y=values,
                        marker_color=bar_colors, text=[f"{v:+.1f}%" for v in values],
                        textposition="outside"
                    ))
                    fig_mom.add_hline(y=0, line_dash="dash", line_color="gray", line_width=1)
                    fig_mom.update_layout(
                        height=260, template="plotly_dark",
                        margin=dict(l=0, r=0, t=30, b=0),
                        yaxis_title="收益率(%)"
                    )
                    st.plotly_chart(fig_mom, use_container_width=True, key=f"chart_{_uid}_15")
                    st.caption(f"动量评分: {mom['score']:+d}/4　{mom['signal']}")

                # 风险指标表
                st.markdown("**🛡️ 风险指标**")
                risk_rows = [
                    {"指标": "年化收益",   "数值": f"{risk['annual_ret']}%"},
                    {"指标": "年化波动率", "数值": f"{risk['annual_vol']}%"},
                    {"指标": "夏普比率",   "数值": f"{risk['sharpe']} ({risk['sharpe_rating']})" },
                    {"指标": "索提诺比率", "数值": str(risk["sortino"])},
                    {"指标": "卡玛比率",   "数值": str(risk["calmar"])},
                    {"指标": "最大回撤",   "数值": f"{risk['max_dd']}%"},
                    {"指标": "日胜率",     "数值": f"{risk['win_rate']}%"},
                    {"指标": "盈亏比",     "数值": f"{risk['profit_loss']}:1"},
                ]
                st.dataframe(pd.DataFrame(risk_rows), hide_index=True, use_container_width=True)


        # ── 基本面分析 ────────────────────────────────────────

        sym = result["symbol"]
        fd = load_fundamentals(sym)

        if not fd or fd.get("error"):
            st.warning("基本面数据暂时无法获取，请稍后重试")
        else:
            # 估值评级卡片
            c1, c2, c3, c4, c5, c6 = st.columns(6)
            c1.metric("PE 市盈率",   str(fd.get("pe") or "N/A"))
            c2.metric("PEG",          str(fd.get("peg") or "N/A"))
            c3.metric("EPS",          f"${fd.get('eps') or 'N/A'}")
            c4.metric("ROE",          f"{fd.get('roe') or 'N/A'}%")
            c5.metric("ROA",          f"{fd.get('roa') or 'N/A'}%")
            c6.metric("估值评级",     fd.get("val_rating", "N/A"))

            c1, c2, c3, c4, c5, c6 = st.columns(6)
            c1.metric("毛利率",     f"{fd.get('gross_margin') or 'N/A'}%")
            c2.metric("净利率",     f"{fd.get('net_margin') or 'N/A'}%")
            c3.metric("资产负债率", f"{fd.get('debt_ratio') or 'N/A'}%")
            c4.metric("流动比率",   str(fd.get("current_ratio") or "N/A"))
            c5.metric("营收同比",   f"{fd.get('revenue_yoy') or 'N/A'}%")
            c6.metric("净利同比",   f"{fd.get('profit_yoy') or 'N/A'}%")

            col_f1, col_f2 = st.columns(2)

            with col_f1:
                # 营收/净利趋势图
                trend = fd.get("income_trend", [])
                if trend:
                    st.markdown("**📈 营收 & 净利润趋势（年报）**")
                    trend_df = pd.DataFrame(trend)
                    fig_inc = go.Figure()
                    fig_inc.add_trace(go.Bar(
                        x=trend_df["年份"], y=trend_df["营收(亿)"],
                        name="营收(亿)", marker_color="#2196f3"
                    ))
                    fig_inc.add_trace(go.Bar(
                        x=trend_df["年份"], y=trend_df["净利润(亿)"],
                        name="净利润(亿)", marker_color="#26a69a"
                    ))
                    fig_inc.update_layout(
                        height=280, template="plotly_dark", barmode="group",
                        margin=dict(l=0, r=0, t=10, b=0),
                        yaxis_title="金额(亿美元)",
                        legend=dict(orientation="h", y=1.1)
                    )
                    st.plotly_chart(fig_inc, use_container_width=True, key=f"chart_{_uid}_16")

                # 估值评级说明
                notes = fd.get("val_notes", [])
                if notes:
                    st.markdown("**📝 估值分析**")
                    for n in notes:
                        st.markdown(f"- {n}")
                if fd.get("dcf_value"):
                    cur = fd.get("price") or result["latest_close"]
                    dcf = fd["dcf_value"]
                    diff = round((dcf / cur - 1) * 100, 1) if cur else 0
                    icon = "🟢" if diff > 0 else "🔴"
                    st.markdown(f"**DCF 简化估值**: ${dcf}（{icon} 相对当前价 {diff:+.1f}%）")
                    st.caption("基于未来 5 年盈利增长 + 折现率 10% + 终值 PE=15，仅供参考")

            with col_f2:
                # 财务指标雷达图
                st.markdown("**📊 财务健康度雷达图**")
                categories = ["毛利率", "净利率", "ROE", "ROA", "流动比率x10", "负债率(100-x)"]
                gm  = min(fd.get("gross_margin") or 0, 100)
                nm  = min(fd.get("net_margin")   or 0, 100)
                roe_v = min(fd.get("roe")        or 0, 100)
                roa_v = min(fd.get("roa")        or 0, 100)
                cr  = min((fd.get("current_ratio") or 0) * 10, 100)
                dr  = max(100 - (fd.get("debt_ratio") or 0), 0)
                values = [gm, nm, roe_v, roa_v, cr, dr]
                fig_radar = go.Figure(go.Scatterpolar(
                    r=values + [values[0]],
                    theta=categories + [categories[0]],
                    fill="toself", fillcolor="rgba(33,150,243,0.2)",
                    line=dict(color="#2196f3", width=2),
                    name=sym
                ))
                fig_radar.update_layout(
                    height=300, template="plotly_dark",
                    polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                    margin=dict(l=20, r=20, t=20, b=20),
                    showlegend=False
                )
                st.plotly_chart(fig_radar, use_container_width=True, key=f"chart_{_uid}_17")

                # 详细数据表
                st.markdown("**📊 详细财务数据**")
                fd_rows = [
                    {"指标": "PE 市盈率",    "数值": str(fd.get("pe") or "N/A"),    "说明": "<15低估 >40高估"},
                    {"指标": "PEG",           "数值": str(fd.get("peg") or "N/A"),   "说明": "<1成长性好"},
                    {"指标": "EPS",           "数值": f"${fd.get('eps') or 'N/A'}",  "说明": "每股收益"},
                    {"指标": "ROE",           "数值": f"{fd.get('roe') or 'N/A'}%",  "说明": ">20%优秀"},
                    {"指标": "ROA",           "数值": f"{fd.get('roa') or 'N/A'}%",  "说明": ">10%优秀"},
                    {"指标": "毛利率",      "数值": f"{fd.get('gross_margin') or 'N/A'}%", "说明": ">40%优秀"},
                    {"指标": "净利率",      "数值": f"{fd.get('net_margin') or 'N/A'}%",   "说明": ">20%优秀"},
                    {"指标": "资产负债率",  "数值": f"{fd.get('debt_ratio') or 'N/A'}%",  "说明": "<60%健康"},
                    {"指标": "流动比率",    "数值": str(fd.get("current_ratio") or "N/A"), "说明": ">1.5健康"},
                    {"指标": "DCF估值",     "数值": f"${fd.get('dcf_value') or 'N/A'}",  "说明": "简化现金流折现"},
                ]
                st.dataframe(pd.DataFrame(fd_rows), hide_index=True, use_container_width=True)


        # ── 汇总表 ────────────────────────────────────────────────


    

        # ── 宏观经济指标 ──────────────────────────────────────
        # MODULE: 宏观
        st.subheader("🌐 宏观经济环境")
        _market_for_macro = {"CN": "🇨🇳 A股", "HK": "🇭🇰 港股", "US": "🇺🇸 美股"}.get(_mkt, "🇺🇸 美股")
        _macro = load_macro(_market_for_macro)
        if _macro:
            _macro_cols = st.columns(min(len(_macro), 4))
            for _mi, (_mk, _mv) in enumerate(_macro.items()):
                _col = _macro_cols[_mi % len(_macro_cols)]
                _prev = _mv.get("prev")
                _delta = round(_mv["value"] - _prev, 3) if _prev is not None else None
                _col.metric(
                    f"{_mv['name']} ({_mv['date']})",
                    f"{_mv['value']}{_mv['unit']}",
                    delta=f"{_delta:+.3f}{_mv['unit']}" if _delta is not None else None,
                )
            st.caption(f"宏观信号：{macro_signal(_macro)}")
        else:
            st.info("宏观数据暂时无法获取")


        # ── 行业对比 ──────────────────────────────────────────
        # MODULE: 行业
        st.subheader("🏭 行业横向对比")
        from industry_analyzer import get_industry_group as _get_group
        _group = _get_group(sym)
        _industry = None
        if _group:
            with st.spinner(f"正在获取 {_group} 行业数据..."):
                _industry = load_industry(sym, "3mo")
            if _industry and isinstance(_industry, dict) and "peers" in _industry:
                st.markdown(f"**所属行业：{_industry['group']}**　共 {_industry['count']} 只股票")
                _peer_rows = []
                for _p in _industry["peers"]:
                    _mark = "[当前] " if _p["是否当前"] else ""
                    _peer_rows.append({
                        "股票": f"{_mark}{_p['名称']}({_p['代码']})",
                        "最新价": _p["最新价"],
                        "1月涨跌": _p["1月涨跌"],
                        "3月涨跌": _p["3月涨跌"],
                        "RSI": _p["RSI"],
                        "波动率": _p["波动率"],
                        "趋势评分": _p["趋势评分"],
                    })
                st.dataframe(pd.DataFrame(_peer_rows), hide_index=True, use_container_width=True)
                _ret_data = {}
                for _p in _industry["peers"]:
                    try:
                        _ret_data[_p["名称"]] = float(_p["1月涨跌"].replace("%","").replace("+",""))
                    except Exception:
                        pass
                if _ret_data:
                    _ret_colors = ["#26a69a" if v >= 0 else "#ef5350" for v in _ret_data.values()]
                    _fig_ind = go.Figure(go.Bar(
                        x=list(_ret_data.keys()), y=list(_ret_data.values()),
                        marker_color=_ret_colors,
                        text=[f"{v:+.1f}%" for v in _ret_data.values()],
                        textposition="outside"
                    ))
                    _fig_ind.add_hline(y=0, line_dash="dash", line_color="gray", line_width=1)
                    _fig_ind.update_layout(
                        height=300, template="plotly_dark",
                        margin=dict(l=0, r=0, t=10, b=0),
                        yaxis_title="1月涨跌(%)"
                    )
                    st.plotly_chart(_fig_ind, use_container_width=True, key=f"chart_{_uid}_industry")
        else:
            st.info(f"{sym} 暂未加入行业对比组，可在 industry_analyzer.py 中添加")

        # ── 期权分析（仅美股）──────────────────────────────
        if _mkt == "US":
            st.divider()
            st.subheader("📊 期权市场分析")
            with st.spinner(f"正在获取 {sym} 期权数据..."):
                _opt = load_option(sym)
            if _opt and not _opt.get("error"):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Put/Call 比率", _opt.get("pc_ratio", "N/A"),
                          delta="偏悲观" if (_opt.get("pc_ratio") or 0) > 1.2 else ("偏乐观" if (_opt.get("pc_ratio") or 1) < 0.7 else "中性"),
                          delta_color="off")
                c2.metric("平均隐含波动率", f"{_opt.get('avg_iv', 'N/A')}%")
                c3.metric("最大痛点", f"${_opt.get('max_pain', 'N/A')}")
                c4.metric("到期日数量", len(_opt.get("expiries", [])))
                st.caption(f"期权信号：{_opt.get('signal', '')}")

                # 期权链表格
                _near_exp = _opt.get("nearest_expiry", "")
                if _near_exp:
                    st.markdown(f"**最近到期日 {_near_exp} 期权链（前10档）**")
                    col_c, col_p = st.columns(2)
                    with col_c:
                        st.markdown("**Call 期权**")
                        _call_rows = [{"行权价": r["strike"], "中间价": r["mid"],
                                       "买价": r["bid"], "卖价": r["ask"],
                                       "IV%": r["iv"], "Delta": r["delta"]}
                                      for r in _opt.get("near_calls", [])]
                        if _call_rows:
                            st.dataframe(pd.DataFrame(_call_rows), hide_index=True, use_container_width=True)
                    with col_p:
                        st.markdown("**Put 期权**")
                        _put_rows = [{"行权价": r["strike"], "中间价": r["mid"],
                                      "买价": r["bid"], "卖价": r["ask"],
                                      "IV%": r["iv"], "Delta": r["delta"]}
                                     for r in _opt.get("near_puts", [])]
                        if _put_rows:
                            st.dataframe(pd.DataFrame(_put_rows), hide_index=True, use_container_width=True)
            elif _opt.get("error"):
                st.warning(f"期权数据获取失败: {_opt['error']}")

        # ── 新闻舆情 ──────────────────────────────────────────
        # MODULE: 新闻
        st.subheader("📰 新闻舆情分析")
        _sym_news = result.get("symbol", "")
        with st.spinner(f"正在获取 {_sym_news} 最新新闻..."):
            _news = load_news(_sym_news, 10)
        _sent = calc_sentiment_summary(_news)
        if _news:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("整体情绪", _sent["overall"])
            c2.metric("积极新闻", f"{_sent['positive']}条")
            c3.metric("消极新闻", f"{_sent['negative']}条")
            c4.metric("情绪得分", _sent["score"])
            st.divider()
            for _n in _news:
                _sent_icon = {"积极": "🟢", "偏积极": "🟩", "消极": "🔴", "偏消极": "🟥"}.get(_n["情绪"], "⚪")
                _title = _n["标题"]
                _url   = _n.get("链接", "")
                _time  = _n.get("时间", "")
                _src   = _n.get("来源", "")
                _sum   = _n.get("摘要", "")
                if _url:
                    st.markdown(f"{_sent_icon} **[{_title}]({_url})**")
                else:
                    st.markdown(f"{_sent_icon} **{_title}**")
                st.caption(f"{_time}　{_src}　{_n['情绪']}")
                if _sum:
                    st.markdown(f"> {_sum}")
        else:
            st.info("暂无相关新闻数据")
    
        # ── 综合总结 ──────────────────────────────────────────
        # MODULE: 总结
        st.subheader("📝 系统性综合分析总结")
        try:
            from ai_analyzer import generate_summary
            _news_for_sum = load_news(_sym_news, 15)
            _fd_for_sum   = load_fundamentals(sym)
            _val_for_sum  = None
            try:
                _val_for_sum = calc_valuation(result, _fd_for_sum if _fd_for_sum and not _fd_for_sum.get("error") else None)
            except Exception:
                pass
            _summary = generate_summary(
                result,
                news=_news_for_sum,
                val=_val_for_sum,
                fd=_fd_for_sum if _fd_for_sum and not _fd_for_sum.get("error") else None
            )
            _sig_color = {"buy": "#26a69a", "sell": "#ef5350", "neutral": "#ff9800"}.get(_summary["signal"], "#aaaaaa")
            st.markdown(f"""
        <div style="background:rgba(255,255,255,0.04);border-left:4px solid {_sig_color};border-radius:8px;padding:20px 24px;line-height:1.8;">

        {_summary["text"]}

        </div>
        """, unsafe_allow_html=True)
            st.caption("⚠️ 以上总结由AI自动生成，仅供参考，不构成投资建议。投资有风险，入市需谨慎。")
        except Exception as _e:
            st.warning(f"总结生成失败: {_e}")

def _render_watchlist_sidebar(market: str):
    """侧边栏自选股管理组件，返回 (watchlist, mkt_key)"""
    _mkt_key = {"\U0001f1fa\U0001f1f8 美股": "US", "\U0001f1e8\U0001f1f3 A股": "CN", "\U0001f1ed\U0001f1f0 港股": "HK"}.get(market, "US")
    _placeholder = {"US": "AAPL", "CN": "600519", "HK": "00700"}.get(_mkt_key, "AAPL")

    st.divider()
    st.subheader("⭐ 自选股")

    with st.expander("➕ 添加自选股", expanded=False):
        _new_sym  = st.text_input("股票代码", placeholder=_placeholder, key=f"wl_add_sym_{_mkt_key}").strip().upper()
        _new_note = st.text_input("备注（可空）", placeholder="如：长期持有", key=f"wl_add_note_{_mkt_key}")
        if st.button("保存到自选", key=f"wl_add_btn_{_mkt_key}", use_container_width=True):
            if _new_sym:
                try:
                    from market_data import get_display_name
                    _name = get_display_name(_new_sym)
                except Exception:
                    _name = _new_sym
                ok = add_symbol(_mkt_key, _new_sym, _name, _new_note)
                if ok:
                    st.success(f"已添加 {_new_sym}")
                    st.rerun()
                else:
                    st.warning(f"{_new_sym} 已在自选列表中")
            else:
                st.warning("请输入股票代码")

    _wl = get_watchlist(_mkt_key)
    if _wl:
        st.caption(f"共 {len(_wl)} 只自选股")
        for _w in _wl:
            _c1, _c2 = st.columns([5, 1])
            _label = f"{_w['name']}({_w['symbol']})" if _w['name'] and _w['name'] != _w['symbol'] else _w['symbol']
            if _w['note']:
                _label += f"  ·  {_w['note']}"
            _c1.markdown(f"<small>{_label}</small>", unsafe_allow_html=True)
            if _c2.button("✕", key=f"wl_del_{_mkt_key}_{_w['symbol']}", help=f"删除 {_w['symbol']}"):
                remove_symbol(_mkt_key, _w['symbol'])
                st.rerun()
    else:
        st.caption("暂无自选股，点击上方添加")

    return _wl, _mkt_key


def show_summary(results: list):
    rows = []
    for r in [x for x in results if x]:
        e, a = r["extra"], r["advice"]
        rows.append({
            "股票": f"{r.get('name', r['symbol'])}({r['symbol']})", "收盘价": f"${r['latest_close']}",
            "5日": f"{e['ret_5d']}%", "20日": f"{e['ret_20d']}%",
            "RSI": r["rsi"], "波动率": f"{e['volatility']}%",
            "规则信号": f"{SIGNAL_ICON.get(r['rule_signal'],'')} {r['rule_signal']}",
            "AI信号": r["ml_signal"], "买入概率": f"{r['ml_proba'].get('买入',0)}%",
            "趋势评分": e["trend_score"], "综合评级": f"{a['rating_color']} {a['rating']}",
            "当前回撤": f"{e['current_drawdown']}%",
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════
# 实时监控页面
# ══════════════════════════════════════════════════════════
def page_realtime(market: str = "🇺🇸 美股"):
    market_label = {"🇺🇸 美股": "美股", "🇨🇳 A股": "A股", "🇭🇰 港股": "港股"}.get(market, "美股")
    st.header(f"⚡ {market_label} 实时行情分析")

    with st.sidebar:
        st.subheader("实时监控设置")
        _rt_presets = {"🇺🇸 美股": US_PRESETS, "🇨🇳 A股": CN_PRESETS, "🇭🇰 港股": HK_PRESETS}.get(market, US_PRESETS)
        _rt_default = {"🇺🇸 美股": "AAPL, NVDA, TSLA", "🇨🇳 A股": "600519, 000858", "🇭🇰 港股": "00700, 09988"}.get(market, "AAPL")
        preset = st.selectbox("监控股票组", ["自定义"] + list(_rt_presets.keys()), key=f"rt_preset_{market}")
        if preset == "自定义":
            # 强制设置当前市场的默认值
            _rt_key = f"rt_custom_{market}"
            if _rt_key not in st.session_state or st.session_state.get("_rt_last_market") != market:
                st.session_state[_rt_key] = _rt_default
                st.session_state["_rt_last_market"] = market
            custom  = st.text_input("股票代码（逗号分隔）", key=f"rt_custom_{market}")
            symbols = [s.strip().upper() for s in custom.split(",") if s.strip()]
        else:
            symbols = _rt_presets[preset]

        refresh_sec = st.selectbox("自动刷新间隔", [1, 3, 5, 10, 30, 60, 120], index=3, key=f"rt_refresh_{market}")
        st.divider()

        st.subheader("🔔 价格预警设置")
        alert_pct = st.slider("涨跌幅预警阈值 (%)", 1.0, 10.0, 3.0, 0.5, key=f"rt_alert_{market}")
        alert_rsi_high = st.slider("RSI 超买预警", 60, 90, 75, key=f"rt_rsi_high_{market}")
        alert_rsi_low  = st.slider("RSI 超卖预警", 10, 40, 25, key=f"rt_rsi_low_{market}")

        # 分析设置
        st.divider()
        st.subheader("K线分析设置")
        period   = PERIOD_OPTIONS[st.selectbox("数据周期", list(PERIOD_OPTIONS.keys()), index=3, key=f"rt_period_{market}")]
        interval = INTERVAL_OPTIONS[st.selectbox("K线间隔", list(INTERVAL_OPTIONS.keys()), key=f"rt_interval_{market}")]
        run_analysis = st.button("🔍 深度分析选中股票", type="primary", use_container_width=True, key=f"rt_run_{market}")
        st.caption("⚠️ 本工具仅供学习研究，不构成投资建议。")
        _wl_rt, _mkt_key_rt = _render_watchlist_sidebar(market)
        # 自选股快捷选择
        if _wl_rt:
            _wl_syms = [w["symbol"] for w in _wl_rt]
            if st.button("⭐ 一键加载自选股", key=f"rt_load_wl_{market}", use_container_width=True):
                st.session_state[f"rt_custom_{market}"] = ", ".join(_wl_syms)
                st.rerun()

    # 初始化 session state
    if "rt_history" not in st.session_state:
        st.session_state.rt_history = {s: [] for s in (MAG7 + CHIPS + CN_TOP + HK_TOP)}
        # 清除不属于当前 symbols 的历史数据
        for _old_sym in list(st.session_state.rt_history.keys()):
            if _old_sym not in symbols:
                del st.session_state.rt_history[_old_sym]
    if "rt_alerts" not in st.session_state:
        st.session_state.rt_alerts = []

    # ── 拉取实时报价 ──────────────────────────────────────
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with st.spinner("正在获取实时行情..."):
        try:
            _sym_key = ",".join(sorted(symbols))
            quotes = load_realtime_quotes_cached(_sym_key, market)
            quotes = [q for q in quotes if q.get("symbol") in [s.upper() for s in symbols]]
        except Exception as e:
            st.error(f"获取行情失败: {e}")
            return

    # 只保留当前 symbols 的报价，清除其他市场残留
    quotes = [q for q in quotes if q.get("symbol") in symbols]
    st.session_state["rt_quotes"] = quotes
    # 补充股票名称
    try:
        from market_data import get_display_name as _gdn_rt
        for _q in quotes:
            if not _q.get("name") or _q.get("name") == _q.get("symbol"):
                _q["name"] = _gdn_rt(_q["symbol"])
    except Exception:
        pass
    # 货币符号
    _rt_cur = {"🇨🇳 A股": "¥", "🇭🇰 港股": "HK$"}.get(market, "$")

    # ── 检查预警 ─────────────────────────────────────────
    new_alerts = []
    for q in quotes:
        if not q.get("price"):
            continue
        sym = q["symbol"]
        pct = q.get("chg_pct")
        # 更新价格历史
        if sym not in st.session_state.rt_history:
            st.session_state.rt_history[sym] = []
        st.session_state.rt_history[sym].append({"time": now_str, "price": q["price"]})
        if len(st.session_state.rt_history[sym]) > 200:
            st.session_state.rt_history[sym] = st.session_state.rt_history[sym][-200:]
        # 涨跌幅预警
        if pct is not None and abs(pct) >= alert_pct:
            direction = "📈 大涨" if pct > 0 else "📉 大跌"
            new_alerts.append(f"🔔 {sym} {direction} {pct:+.2f}%  （当前 ${q['price']}）  [{q['timestamp']}]")

    if new_alerts:
        st.session_state.rt_alerts = new_alerts + st.session_state.rt_alerts
        st.session_state.rt_alerts = st.session_state.rt_alerts[:50]

    # ── 预警通知栏 ────────────────────────────────────────
    if st.session_state.rt_alerts:
        with st.expander(f"🔔 价格预警 ({len(st.session_state.rt_alerts)} 条)", expanded=len(new_alerts) > 0):
            for alert in st.session_state.rt_alerts[:10]:
                color = "🔴" if "大跌" in alert else "🟢"
                st.markdown(f"{color} {alert}")
            if st.button("清空预警", key="clear_alerts"):
                st.session_state.rt_alerts = []

    # ── 实时报价卡片 ──────────────────────────────────────
    st.markdown(f"**🕐 最后更新：** `{now_str}`　　**⏱️ 下次刷新：** `{refresh_sec}秒后`")
    st.divider()

    # ── C. 顶部滚动行情条 ────────────────────────────────
    if quotes:
        ticker_parts = []
        for q in quotes:
            name = q.get("name", q["symbol"])
            price = q.get("price", 0)
            pct = q.get("chg_pct", 0) or 0
            color = "#26a69a" if pct >= 0 else "#ef5350"
            arrow = "▲" if pct >= 0 else "▼"
            ticker_parts.append(
                f'<span style="margin:0 20px;color:{color}">'
                f'<b>{name}</b> {_rt_cur}{price} '
                f'<span>{arrow}{abs(pct):.2f}%</span></span>'
            )
        ticker_html = " &nbsp;|&nbsp; ".join(ticker_parts)
        st.markdown(f"""
<div style="background:rgba(255,255,255,0.05);border-radius:8px;padding:10px 16px;
            overflow:hidden;white-space:nowrap;font-size:0.95rem;">
  <marquee behavior="scroll" direction="left" scrollamount="4">
    {ticker_html}
  </marquee>
</div>
""", unsafe_allow_html=True)
        st.divider()

    # ── B. 价格看板（大字体）────────────────────────────
    st.subheader("📺 实时价格看板")
    if quotes:
        board_cols = st.columns(min(len(quotes), 4))
        for i, q in enumerate(quotes):
            col = board_cols[i % len(board_cols)]
            if not q.get("price"):
                continue
            name  = q.get("name", q["symbol"])
            price = q["price"]
            pct   = q.get("chg_pct", 0) or 0
            amt   = q.get("chg_amt", 0) or 0
            color = "#26a69a" if pct >= 0 else "#ef5350"
            arrow = "▲" if pct >= 0 else "▼"
            col.markdown(f"""
<div style="background:rgba(255,255,255,0.04);border:1px solid {color}40;
            border-radius:12px;padding:16px;text-align:center;">
  <div style="font-size:0.85rem;color:#aaa;margin-bottom:4px">{name}({q["symbol"]})</div>
  <div style="font-size:2rem;font-weight:700;color:{color}">{_rt_cur}{price}</div>
  <div style="font-size:1rem;color:{color}">{arrow} {abs(pct):.2f}% ({_rt_cur}{abs(amt):.2f})</div>
  <div style="font-size:0.75rem;color:#666;margin-top:4px">{q.get("timestamp","")}</div>
</div>
""", unsafe_allow_html=True)
    st.divider()

    # ── A. 悬浮价格窗口（固定在右侧）────────────────────
    if quotes:
        float_items = []
        for q in quotes:
            if not q.get("price"):
                continue
            name  = q.get("name", q["symbol"])[:4]
            price = q["price"]
            pct   = q.get("chg_pct", 0) or 0
            color = "#26a69a" if pct >= 0 else "#ef5350"
            float_items.append(
                f'<div style="margin:4px 0;font-size:0.8rem">'
                f'<span style="color:#ccc">{name}</span> '
                f'<span style="color:{color};font-weight:600">{_rt_cur}{price}</span> '
                f'<span style="color:{color}">{pct:+.1f}%</span></div>'
            )
        float_html = "".join(float_items)
        st.markdown(f"""
<div style="position:fixed;right:16px;top:80px;z-index:999;
            background:rgba(20,20,30,0.92);border:1px solid rgba(255,255,255,0.15);
            border-radius:10px;padding:12px 16px;min-width:160px;
            backdrop-filter:blur(8px);box-shadow:0 4px 20px rgba(0,0,0,0.4);">
  <div style="font-size:0.75rem;color:#888;margin-bottom:6px;font-weight:600">
    ⚡ 实时行情
  </div>
  {float_html}
  <div style="font-size:0.65rem;color:#555;margin-top:6px">{now_str[11:19]}</div>
</div>
""", unsafe_allow_html=True)

    # ── D. 实时K线（当天分钟级）────────────────────────
    st.subheader("📈 实时K线图（当日分钟线）")
    _kline_sym = st.selectbox(
        "选择股票", symbols,
        format_func=lambda s: f"{next((q.get('name',s) for q in quotes if q.get('symbol')==s), s)}({s})",
        key=f"rt_kline_sym_{market}"
    )
    _kline_interval = st.radio(
        "K线周期", ["5m", "15m", "1h"],
        horizontal=True, key=f"rt_kline_interval_{market}"
    )
    try:
        with st.spinner(f"正在获取 {_kline_sym} {_kline_interval} K线..."):
            _kline_df = load_kline_cached(_kline_sym, _kline_interval)

        fig_kline = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            row_heights=[0.7, 0.3], vertical_spacing=0.03,
        )
        # K线
        fig_kline.add_trace(go.Candlestick(
            x=_kline_df.index, open=_kline_df["Open"],
            high=_kline_df["High"], low=_kline_df["Low"], close=_kline_df["Close"],
            name="K线", increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
        ), row=1, col=1)
        # MA
        for ma, color in [("MA5", "#ff9800"), ("MA20", "#2196f3")]:
            fig_kline.add_trace(go.Scatter(
                x=_kline_df.index, y=_kline_df[ma], name=ma,
                line=dict(width=1, color=color)
            ), row=1, col=1)
        # 成交量
        vol_colors = ["#26a69a" if c >= o else "#ef5350"
                      for c, o in zip(_kline_df["Close"], _kline_df["Open"])]
        fig_kline.add_trace(go.Bar(
            x=_kline_df.index, y=_kline_df["Volume"],
            marker_color=vol_colors, name="成交量", showlegend=False
        ), row=2, col=1)
        # 最新价水平线
        latest_close = float(_kline_df["Close"].iloc[-1])
        fig_kline.add_hline(
            y=latest_close, line_dash="dash", line_color="white", line_width=1,
            annotation_text=f"最新 {_rt_cur}{latest_close:.2f}", row=1, col=1
        )
        fig_kline.update_layout(
            height=500, template="plotly_dark",
            xaxis_rangeslider_visible=False,
            margin=dict(l=0, r=0, t=30, b=0),
            title=f"{_kline_sym} {_kline_interval} K线  |  最新: {_rt_cur}{latest_close:.2f}",
            legend=dict(orientation="h", y=1.05),
        )
        st.plotly_chart(fig_kline, use_container_width=True, key=f"rt_kline_{market}_{_kline_sym}")
    except Exception as _ke:
        st.warning(f"K线数据获取失败: {_ke}")

    st.divider()

    # 最终过滤：确保只显示当前 symbols 的报价
    quotes = [q for q in quotes if q.get("symbol", "").upper() in [s.upper() for s in symbols]]
    cols = st.columns(min(len(quotes), 4))
    for i, q in enumerate(quotes):
        col = cols[i % len(cols)]
        if not q.get("price"):
            col.error(f"{q['symbol']}: 获取失败")
            continue
        pct  = q.get("chg_pct", 0) or 0
        amt  = q.get("chg_amt", 0) or 0
        color = "🟢" if pct > 0 else ("🔴" if pct < 0 else "⚪")
        # 预警高亮
        is_alert = abs(pct) >= alert_pct
        with col:
            if is_alert:
                st.warning(f"**{color} {q.get('name', q['symbol'])}({q['symbol']})** ⚠️ 预警")
            else:
                st.markdown(f"**{color} {q.get('name', q['symbol'])}({q['symbol']})**")
            st.metric(
                label=f"Bid {q['bid']} / Ask {q['ask']}",
                value=f"{_rt_cur}{q['price']}",
                delta=f"{amt:+.2f} ({pct:+.2f}%)" if pct is not None else "N/A",
            )
            vol_m = q.get("volume", 0) / 1_000_000
            st.caption(f"成交量: {vol_m:.2f}M　{q.get('timestamp','')}")

    # ── 实时价格走势图（多股对比）────────────────────────
    st.divider()
    st.subheader("📊 实时价格走势（本次会话）")
    fig_live = go.Figure()
    has_data = False
    for sym in symbols:
        hist = st.session_state.rt_history.get(sym, [])
        if len(hist) >= 2:
            has_data = True
            times  = [h["time"]  for h in hist]
            prices = [h["price"] for h in hist]
            # 归一化为百分比变化
            base = prices[0]
            pcts = [round((p / base - 1) * 100, 3) for p in prices]
            fig_live.add_trace(go.Scatter(x=times, y=pcts, name=sym, mode="lines+markers",
                                          marker=dict(size=4), line=dict(width=2)))
    if has_data:
        fig_live.add_hline(y=0, line_dash="dash", line_color="gray", line_width=1)
        fig_live.update_layout(height=300, template="plotly_dark", yaxis_title="相对涨跌(%)",
                               margin=dict(l=0,r=0,t=10,b=0), legend=dict(orientation="h"))
        st.plotly_chart(fig_live, use_container_width=True)
    else:
        st.info("数据积累中，刷新几次后将显示走势图...")

    # ── RSI 实时预警状态 ──────────────────────────────────
    st.divider()
    st.subheader("📡 技术指标快速扫描")
    with st.spinner("正在计算技术指标..."):
        scan_rows = []
        for q in quotes:
            if not q.get("price"):
                continue
            try:
                df = fetch_stock_data(q["symbol"], "3mo", "1d")
                df = add_indicators(df)
                latest = df.iloc[-1]
                rsi  = round(float(latest["RSI"]), 1)
                macd = round(float(latest["MACD"]), 3)
                macd_hist = round(float(latest["MACD_Hist"]), 3)
                rsi_status = "🔴 超买" if rsi > alert_rsi_high else ("🟢 超卖" if rsi < alert_rsi_low else "⚪ 正常")
                macd_status = "金叉↑" if macd_hist > 0 else "死叉↓"
                scan_rows.append({
                    "股票": f"{q.get('name', q['symbol'])}({q['symbol']})", "实时价": f"${q['price']}",
                    "涨跌幅": f"{q.get('chg_pct',0):+.2f}%",
                    "RSI": rsi, "RSI状态": rsi_status,
                    "MACD": macd, "MACD状态": macd_status,
                    "MA5": round(float(latest["MA5"]), 2),
                    "MA20": round(float(latest["MA20"]), 2),
                    "价格vs MA20": f"{round((q['price']/float(latest['MA20'])-1)*100,1)}%",
                })
            except Exception:
                pass

    if scan_rows:
        st.dataframe(pd.DataFrame(scan_rows), use_container_width=True, hide_index=True)

    # ── 深度分析 ──────────────────────────────────────────
    if run_analysis:
        st.divider()
        st.subheader("🔬 深度 AI 分析")
        results = []
        prog = st.progress(0)
        for i, sym in enumerate(symbols):
            prog.progress((i+1)/len(symbols), text=f"分析 {sym}...")
            try:
                results.append(load_analysis(sym, period, interval))
                if results and results[-1]:
                    try:
                        from market_data import get_display_name as _gdn
                        results[-1]["name"] = _gdn(sym)
                    except Exception:
                        results[-1]["name"] = sym
            except Exception as e:
                st.error(f"{sym} 失败: {e}")
                results.append(None)
        prog.empty()

        if len(symbols) > 1:
            show_summary(results)
            st.divider()
            tabs = st.tabs([f"{r.get('name', r['symbol'])}({r['symbol']})" if r else 'ERR' for r in results])
            for tab, r in zip(tabs, results):
                with tab:
                    if r: show_detail(r, _uid=r.get('symbol',''))
        elif results[0]:
            show_detail(results[0], _uid=results[0].get('symbol',''))

    # ── 自动刷新 ──────────────────────────────────────────
    time.sleep(refresh_sec)
    st.rerun()


# ══════════════════════════════════════════════════════════
# 深度分析页面
# ══════════════════════════════════════════════════════════
def page_analysis(market: str = "🇺🇸 美股"):
    market_label = {"🇺🇸 美股": "美股", "🇨🇳 A股": "A股", "🇭🇰 港股": "港股"}.get(market, "美股")
    st.header(f"🔬 {market_label} 深度 AI 分析")

    with st.sidebar:
        st.subheader("分析设置")
        _mkt_presets = {"🇺🇸 美股": US_PRESETS, "🇨🇳 A股": CN_PRESETS, "🇭🇰 港股": HK_PRESETS}.get(market, US_PRESETS)
        _mkt_default = {"🇺🇸 美股": "AAPL, NVDA", "🇨🇳 A股": "600519, 000858", "🇭🇰 港股": "00700, 09988"}.get(market, "AAPL")
        preset = st.selectbox("快捷选股", ["自定义"] + list(_mkt_presets.keys()), key="an_preset")
        if preset == "自定义":
            _an_key = "an_custom"
            if _an_key not in st.session_state or st.session_state.get("_an_last_market") != market:
                st.session_state[_an_key] = _mkt_default
                st.session_state["_an_last_market"] = market
            custom  = st.text_input("股票代码（逗号分隔）", key="an_custom")
            symbols = [s.strip().upper() for s in custom.split(",") if s.strip()]
        else:
            symbols = _mkt_presets[preset]
            st.info(f"已选: {', '.join(symbols)}")
        period   = PERIOD_OPTIONS[st.selectbox("数据周期", list(PERIOD_OPTIONS.keys()), index=3, key="an_period")]
        interval = INTERVAL_OPTIONS[st.selectbox("K线间隔", list(INTERVAL_OPTIONS.keys()), key="an_interval")]
        st.divider()
        total_capital = st.number_input("💰 总资金", min_value=1000, max_value=10_000_000,
                                        value=100000, step=1000, key="an_capital")
        st.markdown("📊 **各股仓位比例 (%)**")
        alloc = {}
        try:
            from market_data import get_display_name as _gdn2
            _snames = {s: _gdn2(s) for s in symbols}
        except Exception:
            _snames = {s: s for s in symbols}
        for sym in symbols:
            _n = _snames.get(sym, sym)
            _lbl = f"{_n}({sym})" if _n != sym else sym
            alloc[sym] = st.slider(_lbl, 0, 100, 10, 1, key=f"alloc_{sym}")
        total_alloc = sum(alloc.values())
        if total_alloc > 0:
            st.caption(f"已分配总仓位: {total_alloc}%")
            if total_alloc > 100:
                st.warning("仓位合计超过 100%，请调整")
        st.divider()
        st.markdown("**📦 显示模块**")
        _modules = st.multiselect(
            "选择要显示的分析模块",
            ["核心", "预测", "仓位", "波浪", "K线", "量价", "量化", "基本面", "宏观", "行业", "新闻", "总结"],
            default=["核心", "预测", "仓位", "波浪"],
            key="an_modules"
        )
        run = st.button("🚀 开始分析", type="primary", use_container_width=True, key="an_run")
        st.caption("⚠️ 本工具仅供学习研究，不构成投资建议。")
        _wl_an, _mkt_key_an = _render_watchlist_sidebar(market)
        if _wl_an:
            _wl_syms_an = [w["symbol"] for w in _wl_an]
            if st.button("⭐ 一键加载自选股", key=f"an_load_wl_{market}", use_container_width=True):
                st.session_state["an_custom"] = ", ".join(_wl_syms_an)
                st.rerun()

    if not run:
        st.info("👈 在左侧选择股票和参数，点击「开始分析」")
        return

    results = []
    prog = st.progress(0, text="正在获取数据...")
    for i, sym in enumerate(symbols):
        prog.progress((i+1)/len(symbols), text=f"正在分析 {sym} ({i+1}/{len(symbols)})...")
        try:
            results.append(load_analysis(sym, period, interval))
            if results and results[-1]:
                try:
                    from market_data import get_display_name as _gdn
                    results[-1]["name"] = _gdn(sym)
                except Exception:
                    results[-1]["name"] = sym
        except Exception as e:
            st.error(f"{sym} 获取失败: {e}")
            results.append(None)
    prog.empty()

    if len(symbols) > 1:
        st.subheader("📊 多股票汇总对比")
        show_summary(results)
        st.divider()
        tabs = st.tabs([f"{r.get('name', r['symbol'])}({r['symbol']})" if r else 'ERR' for r in results])
        for tab, r in zip(tabs, results):
            with tab:
                if r:
                    sym_capital = round(total_capital * alloc.get(r["symbol"], 10) / 100)
                    try:
                        show_detail(r, sym_capital, _uid=r.get('symbol',''), modules=_modules)
                    except Exception as _e:
                        import traceback
                        st.error(f"show_detail error: {_e}")
                        st.code(traceback.format_exc())
                else: st.error("数据获取失败")
    elif results[0]:
        sym_capital = round(total_capital * alloc.get(symbols[0], 10) / 100)
        show_detail(results[0], sym_capital, _uid=results[0].get('symbol',''), modules=_modules)


# ══════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════
# 新股分析页面
# ══════════════════════════════════════════════════════════
def page_ipo(market: str = "🇨🇳 A股"):
    market_label = {"🇺🇸 美股": "美股", "🇨🇳 A股": "A股", "🇭🇰 港股": "港股"}.get(market, "A股")
    st.header(f"🌱 {market_label} 新股分析")

    if market == "🇺🇸 美股":
        st.info("美股新股数据暂不支持，请切换到 A股 或 港股")
        return

    with st.spinner("正在获取新股数据..."):
        if market == "🇨🇳 A股":
            _ipo_list, _stats, _calendar = load_ipo_cn()
        else:
            _ipo_list = load_ipo_hk()
            _stats, _calendar = {}, pd.DataFrame()

    # ── 打新统计 ──────────────────────────────────────────
    if _stats and market == "🇨🇳 A股":
        st.subheader("📊 近期打新统计")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("统计新股数", f"{_stats.get('total', 0)} 只")
        c2.metric("平均首日涨幅", f"{_stats.get('avg_gain', 0)}%")
        c3.metric("最高首日涨幅", f"{_stats.get('max_gain', 0)}%")
        c4.metric("破发率", f"{_stats.get('break_rate', 0)}%",
                  delta="偏高" if _stats.get("break_rate", 0) > 20 else "正常",
                  delta_color="inverse" if _stats.get("break_rate", 0) > 20 else "off")

    # ── 新股申购日历 ──────────────────────────────────────
    if market == "🇨🇳 A股" and not _calendar.empty:
        st.subheader("📅 新股申购日历")
        st.dataframe(_calendar, hide_index=True, use_container_width=True)

    # ── 近期新股列表 ──────────────────────────────────────
    st.subheader(f"📋 近期{market_label}新股列表")
    if not _ipo_list.empty:
        st.dataframe(_ipo_list, hide_index=True, use_container_width=True)
    else:
        st.info("暂无新股数据")

    # ── 单只新股详情（仅A股）────────────────────────────
    if market == "🇨🇳 A股":
        st.divider()
        st.subheader("🔍 单只新股详情查询")
        _ipo_code = st.text_input("输入新股代码（如 688981）", key="ipo_code")
        if _ipo_code:
            with st.spinner(f"正在查询 {_ipo_code}..."):
                _info = fetch_cn_ipo_info(_ipo_code)
            if _info:
                col_i1, col_i2 = st.columns(2)
                with col_i1:
                    st.markdown("**📄 发行信息**")
                    for k, v in list(_info.items())[:8]:
                        st.markdown(f"- **{k}**：{v}")
                with col_i2:
                    st.markdown("**📄 募资信息**")
                    for k, v in list(_info.items())[8:]:
                        st.markdown(f"- **{k}**：{v}")
                st.divider()
                st.markdown("**💡 申购建议**")
                _advice = ipo_advice(_info, _stats)
                for a in _advice:
                    st.markdown(f"- {a}")
            else:
                st.warning(f"未找到 {_ipo_code} 的新股信息")

def main():
    st.title("📈 AI 量化分析平台")

    market = st.sidebar.radio("🌍 市场选择", ["🇺🇸 美股", "🇨🇳 A股", "🇭🇰 港股"], horizontal=True)
    # 市场切换时清除旧的 session state
    if "last_market" not in st.session_state:
        st.session_state.last_market = market
    elif st.session_state.last_market != market:
        # 清除所有 rt_ 和 an_ 开头的 session state
        keys_to_del = [k for k in st.session_state.keys() if k.startswith(("rt_", "an_", "alloc_"))]
        for k in keys_to_del:
            del st.session_state[k]
        st.session_state.rt_history = {}
        if "rt_quotes" in st.session_state: del st.session_state["rt_quotes"]
        st.session_state.rt_alerts = []
        st.session_state.last_market = market
        st.rerun()
    data_src = "Alpaca" if market == "🇺🇸 美股" else "AKShare"
    st.caption(f"数据源: {data_src} 实时行情 | 本工具仅供学习研究，不构成投资建议")

    st.sidebar.divider()
    page = st.sidebar.radio("📌 功能导航", ["⚡ 实时分析", "🔬 深度分析", "🌱 新股分析"], label_visibility="collapsed")

    if page == "⚡ 实时分析":
        page_realtime(market)
    elif page == "🔬 深度分析":
        page_analysis(market)
    elif page == "🌱 新股分析":
        page_ipo(market)

if __name__ == "__main__":
    main()
