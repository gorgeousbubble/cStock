import warnings
warnings.filterwarnings("ignore")
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression

FEATURE_COLS = ["RSI", "MACD", "MACD_Hist", "MA5", "MA20", "MA60", "BB_Upper", "BB_Lower", "Volume", "Vol_MA20"]


def _rule_signal(row) -> str:
    score = 0
    if row["RSI"] < 30:    score += 2
    elif row["RSI"] > 70:  score -= 2
    if row["MACD"] > row["MACD_Signal"] and row["MACD_Hist"] > 0:   score += 1
    elif row["MACD"] < row["MACD_Signal"] and row["MACD_Hist"] < 0: score -= 1
    if row["MA5"] > row["MA20"] > row["MA60"]:   score += 1
    elif row["MA5"] < row["MA20"] < row["MA60"]: score -= 1
    if row["Close"] < row["BB_Lower"]:  score += 1
    elif row["Close"] > row["BB_Upper"]: score -= 1
    if row["Volume"] > row["Vol_MA20"] * 1.5: score += 1
    if score >= 3:    return "强烈买入"
    elif score >= 1:  return "买入"
    elif score <= -3: return "强烈卖出"
    elif score <= -1: return "卖出"
    return "持有"


def _train_ml_model(df: pd.DataFrame):
    data = df.copy()
    data["future_return"] = data["Close"].shift(-5) / data["Close"] - 1
    data["label"] = 0
    data.loc[data["future_return"] > 0.02,  "label"] = 1
    data.loc[data["future_return"] < -0.02, "label"] = -1
    data = data.dropna()

    # 数据量不足时用规则信号代替
    if len(data) < 30:
        raise ValueError(f"数据量不足（仅{len(data)}条），至少需要 30 条有效数据，请选择更长的数据周期（如 3个月以上）")

    X = data[FEATURE_COLS]
    y = data["label"]
    scaler   = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    # 测试集至少保留 5 条
    test_size = max(5, int(len(X_scaled) * 0.2))
    split = len(X_scaled) - test_size
    X_train, X_test = X_scaled[:split], X_scaled[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]
    model = RandomForestClassifier(n_estimators=30, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)
    acc = round(model.score(X_test, y_test) * 100, 1) if len(X_test) > 0 else 0.0
    return model, scaler, acc


def _calc_extra(df: pd.DataFrame) -> dict:
    close  = df["Close"]
    latest = close.iloc[-1]

    daily_ret  = close.pct_change().dropna()
    volatility = round(float(daily_ret.rolling(20).std().iloc[-1] * np.sqrt(252) * 100), 1)

    roll_max         = close.cummax()
    drawdown         = (close - roll_max) / roll_max
    max_drawdown     = round(float(drawdown.min() * 100), 1)
    current_drawdown = round(float(drawdown.iloc[-1] * 100), 1)

    ret_5d  = round((latest / close.iloc[-6]  - 1) * 100, 2) if len(close) >= 6  else None
    ret_20d = round((latest / close.iloc[-21] - 1) * 100, 2) if len(close) >= 21 else None
    ret_60d = round((latest / close.iloc[-61] - 1) * 100, 2) if len(close) >= 61 else None

    window     = close.tail(60)
    support    = round(float(window.min()), 2)
    resistance = round(float(window.max()), 2)
    support_pct    = round((latest / support    - 1) * 100, 1)
    resistance_pct = round((resistance / latest - 1) * 100, 1)

    w52           = close.tail(252)
    high_52w      = round(float(w52.max()), 2)
    low_52w       = round(float(w52.min()), 2)
    pct_from_high = round((latest / high_52w - 1) * 100, 1)
    pct_from_low  = round((latest / low_52w  - 1) * 100, 1)

    vol_ratio = round(float(df["Volume"].tail(5).mean() / df["Vol_MA20"].iloc[-1]), 2)

    trend_score = 50
    ma5, ma20, ma60 = float(df["MA5"].iloc[-1]), float(df["MA20"].iloc[-1]), float(df["MA60"].iloc[-1])
    if latest > ma5:  trend_score += 10
    if latest > ma20: trend_score += 15
    if latest > ma60: trend_score += 15
    if ma5 > ma20:    trend_score += 5
    if ma20 > ma60:   trend_score += 5
    rsi = float(df["RSI"].iloc[-1])
    if rsi > 60:   trend_score += 5
    elif rsi < 40: trend_score -= 5
    trend_score = max(0, min(100, trend_score))

    return {
        "volatility": volatility, "max_drawdown": max_drawdown, "current_drawdown": current_drawdown,
        "ret_5d": ret_5d, "ret_20d": ret_20d, "ret_60d": ret_60d,
        "support": support, "resistance": resistance,
        "support_pct": support_pct, "resistance_pct": resistance_pct,
        "high_52w": high_52w, "low_52w": low_52w,
        "pct_from_high": pct_from_high, "pct_from_low": pct_from_low,
        "vol_ratio": vol_ratio, "trend_score": trend_score,
    }


def _generate_advice(result: dict) -> dict:
    rule, ml   = result["rule_signal"], result["ml_signal"]
    rsi, extra = result["rsi"], result["extra"]
    ts, vol, dd, vr = extra["trend_score"], extra["volatility"], extra["current_drawdown"], extra["vol_ratio"]

    points, risks, actions = [], [], []

    if ts >= 80:   points.append("价格站上MA5/MA20/MA60，多头排列强势")
    elif ts >= 65: points.append("短中期均线多头，趋势偏强")
    elif ts <= 35: risks.append("均线空头排列，趋势偏弱")

    if rsi > 75:   risks.append(f"RSI {rsi} 严重超买，短期回调风险较高")
    elif rsi > 65: risks.append(f"RSI {rsi} 偏高，注意超买风险")
    elif rsi < 25: points.append(f"RSI {rsi} 严重超卖，存在反弹机会")
    elif rsi < 35: points.append(f"RSI {rsi} 超卖区间，可关注企稳信号")

    if vr > 1.5:   points.append(f"近5日成交量是均量的 {vr}x，资金明显放大")
    elif vr < 0.7: risks.append(f"近5日成交量萎缩至均量的 {vr}x，上涨动能不足")

    if dd < -15:  risks.append(f"当前较高点回撤 {dd}%，处于深度调整中")
    elif dd < -8: risks.append(f"当前较高点回撤 {dd}%，注意止损")

    if vol > 60:   risks.append(f"年化波动率 {vol}%，属高波动股，仓位需控制")
    elif vol < 20: points.append(f"年化波动率 {vol}%，走势相对稳健")

    sp, rp = extra["support_pct"], extra["resistance_pct"]
    points.append(f"60日支撑位 ${extra['support']}（距当前 +{sp}%），压力位 ${extra['resistance']}（距当前 -{rp}%）")

    pfh = extra["pct_from_high"]
    if pfh > -5:    risks.append(f"股价接近52周高点（{pfh}%），上方空间有限")
    elif pfh < -30: points.append(f"股价距52周高点 {pfh}%，估值相对低位")

    both_buy  = rule in ("买入", "强烈买入") and ml == "买入"
    both_sell = rule in ("卖出", "强烈卖出") and ml == "卖出"
    if both_buy and ts >= 65 and rsi < 70:
        actions.append("规则与AI信号一致看多，趋势良好，可考虑逢低建仓或加仓")
        if vr > 1.2: actions.append("成交量配合放大，信号可信度较高")
    elif both_sell and ts <= 45:
        actions.append("规则与AI信号一致看空，趋势走弱，建议减仓或观望")
    elif rule != ml:
        actions.append("规则信号与AI信号分歧，建议等待方向明确后再操作")
    else:
        actions.append("当前信号中性，建议持仓观望，等待更明确的突破信号")

    if rsi > 70:  actions.append("RSI超买，即使看多也建议分批建仓，避免追高")
    if vol > 50:  actions.append(f"波动率较高（{vol}%），建议单笔仓位不超过总仓位的10%")

    score = 0
    if both_buy:   score += 2
    elif rule in ("买入", "强烈买入"): score += 1
    if ml == "买入": score += 1
    if ts >= 70:   score += 1
    if rsi < 65:   score += 1
    if vr > 1.2:   score += 1
    if both_sell:  score -= 3
    if rsi > 75:   score -= 2
    if dd < -15:   score -= 1

    if score >= 4:    rating, rating_color = "强烈推荐", "🟢"
    elif score >= 2:  rating, rating_color = "适度看多", "🟩"
    elif score <= -2: rating, rating_color = "建议回避", "🔴"
    elif score <= 0:  rating, rating_color = "谨慎观望", "🟡"
    else:             rating, rating_color = "中性持有", "⚪"

    return {"rating": rating, "rating_color": rating_color,
            "points": points, "risks": risks, "actions": actions}


def _predict_forecast(df: pd.DataFrame) -> dict:
    """多模型走势预测：GBR + Monte Carlo + ARIMA + 指数平滑 + 线性趋势"""
    close     = df["Close"].values
    latest    = float(close[-1])
    daily_ret = pd.Series(close).pct_change().dropna().values
    vol_daily = float(np.std(daily_ret[-20:]))
    n_days    = 30

    # ── 1. GradientBoosting 目标价预测 ──────────────────
    data = df.copy()
    for h in [5, 10, 20]:
        data[f"target_{h}"] = data["Close"].shift(-h)
    data     = data.dropna()
    X        = data[FEATURE_COLS].values
    scaler   = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    latest_x = scaler.transform(df[FEATURE_COLS].iloc[[-1]].values)
    split    = int(len(X_scaled) * 0.8)

    forecasts = {}
    for h, label in [(5, "5日"), (10, "10日"), (20, "20日")]:
        y     = data[f"target_{h}"].values
        model = GradientBoostingRegressor(n_estimators=30, max_depth=3, random_state=42)
        model.fit(X_scaled[:split], y[:split])
        pred  = float(model.predict(latest_x)[0])
        mae   = float(np.mean(np.abs(model.predict(X_scaled[split:]) - y[split:])))
        forecasts[label] = {
            "price":     round(pred, 2),
            "return":    round((pred / latest - 1) * 100, 2),
            "low":       round(pred - mae, 2),
            "high":      round(pred + mae, 2),
            "direction": "上涨" if pred > latest else "下跌",
        }

    # ── 2. 线性趋势外推 ──────────────────────────────────
    x_idx       = np.arange(len(close)).reshape(-1, 1)
    lr          = LinearRegression().fit(x_idx, close)
    future_idx  = np.arange(len(close), len(close) + n_days).reshape(-1, 1)
    trend_line  = lr.predict(future_idx)
    trend_slope = round(float(lr.coef_[0]), 4)

    # ── 3. Monte Carlo 模拟（1000条路径）────────────────
    np.random.seed(42)
    n_sim = 1000
    drift = float(np.mean(daily_ret[-60:]))
    sims  = np.zeros((n_sim, n_days))
    for i in range(n_sim):
        sims[i] = latest * np.cumprod(1 + np.random.normal(drift, vol_daily, n_days))

    # ── 4. ARIMA 预测 ────────────────────────────────────
    arima_pred = None
    try:
        from statsmodels.tsa.arima.model import ARIMA
        series = pd.Series(close[-120:])  # 用最近120日
        arima_model = ARIMA(series, order=(1, 1, 0)).fit(disp=False, maxiter=20)
        arima_forecast = arima_model.forecast(steps=n_days)
        arima_pred = [round(float(v), 2) for v in arima_forecast]
    except Exception:
        arima_pred = None

    # ── 5. 指数平滑（Holt-Winters）预测 ─────────────────
    ets_pred = None
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        series = pd.Series(close[-120:])
        ets_model = ExponentialSmoothing(series, trend="add", seasonal=None, damped_trend=True).fit()
        ets_forecast = ets_model.forecast(n_days)
        ets_pred = [round(float(v), 2) for v in ets_forecast]
    except Exception:
        ets_pred = None

    # ── 6. 模型综合预测（30日均值对比）─────────────────
    model_comparison = {}
    if arima_pred:
        model_comparison["ARIMA"] = {
            "price_30d": arima_pred[-1],
            "return_30d": round((arima_pred[-1] / latest - 1) * 100, 2),
            "series": arima_pred,
        }
    if ets_pred:
        model_comparison["指数平滑"] = {
            "price_30d": ets_pred[-1],
            "return_30d": round((ets_pred[-1] / latest - 1) * 100, 2),
            "series": ets_pred,
        }
    model_comparison["线性趋势"] = {
        "price_30d": round(float(trend_line[-1]), 2),
        "return_30d": round((float(trend_line[-1]) / latest - 1) * 100, 2),
        "series": [round(float(v), 2) for v in trend_line],
    }
    model_comparison["Monte Carlo"] = {
        "price_30d": round(float(np.mean(sims[:, -1])), 2),
        "return_30d": round((float(np.mean(sims[:, -1])) / latest - 1) * 100, 2),
        "series": [round(float(v), 2) for v in np.mean(sims, axis=0)],
    }

    return {
        "forecasts":        forecasts,
        "trend_slope":      trend_slope,
        "trend_dir":        "上升" if trend_slope > 0 else "下降",
        "trend_line":       trend_line.tolist(),
        "mc_days":          n_days,
        "mc_mean":          np.mean(sims, axis=0).tolist(),
        "mc_p10":           np.percentile(sims, 10, axis=0).tolist(),
        "mc_p25":           np.percentile(sims, 25, axis=0).tolist(),
        "mc_p75":           np.percentile(sims, 75, axis=0).tolist(),
        "mc_p90":           np.percentile(sims, 90, axis=0).tolist(),
        "mc_bull":          round(float(np.percentile(sims[:, -1], 90)), 2),
        "mc_bear":          round(float(np.percentile(sims[:, -1], 10)), 2),
        "mc_mean_final":    round(float(np.mean(sims[:, -1])), 2),
        "mc_prob_up":       round(float(np.mean(sims[:, -1] > latest) * 100), 1),
        "model_comparison": model_comparison,
    }


def calc_position_sizing(result: dict, total_capital: float = 100000) -> dict:
    """仓位控制与买入价格建议：Kelly公式 + ATR止损 + 信号强度加权"""
    extra   = result["extra"]
    close   = float(result["latest_close"])
    vol     = extra["volatility"] / 100
    support = extra["support"]
    resist  = extra["resistance"]
    rsi     = result["rsi"]
    rule    = result["rule_signal"]
    ml      = result["ml_signal"]
    ts      = extra["trend_score"]
    df      = result["df"]

    high, low, prev_close = df["High"], df["Low"], df["Close"].shift(1)
    tr  = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = round(float(tr.rolling(14).mean().iloc[-1]), 2)

    entry1 = round(close, 2)
    entry2 = round(float(result["ma20"]), 2)
    fib618 = round(resist - (resist - support) * 0.618, 2)
    entry3 = round(min(support + atr * 0.5, fib618), 2)

    stop_loss = max(round(entry1 - atr * 2, 2), round(support * 0.99, 2))
    stop_pct  = round((stop_loss / entry1 - 1) * 100, 2)

    risk_amt = entry1 - stop_loss
    tp1 = round(entry1 + risk_amt * 1.5, 2)
    tp2 = round(entry1 + risk_amt * 2.5, 2)
    tp3 = round(min(resist, entry1 + risk_amt * 4), 2)
    tp1_pct  = round((tp1 / entry1 - 1) * 100, 2)
    tp2_pct  = round((tp2 / entry1 - 1) * 100, 2)
    tp3_pct  = round((tp3 / entry1 - 1) * 100, 2)
    rr_ratio = round(abs(tp2_pct / stop_pct), 2) if stop_pct != 0 else 0

    win_rate   = result["ml_proba"].get("买入", 33) / 100
    kelly      = max(0.0, min(win_rate - (1 - win_rate) / 2.0, 0.25))
    half_kelly = round(kelly * 0.5, 3)

    signal_score = 0
    if rule in ("买入", "强烈买入"): signal_score += 2
    if ml == "买入":                 signal_score += 2
    if ts >= 70:                     signal_score += 1
    if rsi < 60:                     signal_score += 1
    if extra["vol_ratio"] > 1.2:     signal_score += 1

    base_pct  = round(min(0.05 + signal_score * 0.03, 0.30), 2)
    vol_adj   = round(0.20 / max(vol, 0.10), 2)
    final_pct = round(min(base_pct * vol_adj, 0.30), 2)

    batches = [
        {"batch": "第1批", "price": entry1, "pct": round(final_pct * 0.4, 3),
         "amount": round(total_capital * final_pct * 0.4, 0),
         "shares": int(total_capital * final_pct * 0.4 / entry1),
         "condition": "当前价格市价买入"},
        {"batch": "第2批", "price": entry2, "pct": round(final_pct * 0.35, 3),
         "amount": round(total_capital * final_pct * 0.35, 0),
         "shares": int(total_capital * final_pct * 0.35 / entry2),
         "condition": f"回调至 MA20 (${entry2}) 附近买入"},
        {"batch": "第3批", "price": entry3, "pct": round(final_pct * 0.25, 3),
         "amount": round(total_capital * final_pct * 0.25, 0),
         "shares": int(total_capital * final_pct * 0.25 / entry3),
         "condition": f"回调至 Fib61.8% / 支撑位 (${entry3}) 买入"},
    ]

    return {
        "entry1": entry1, "entry2": entry2, "entry3": entry3,
        "stop_loss": stop_loss, "stop_pct": stop_pct, "atr": atr,
        "tp1": tp1, "tp1_pct": tp1_pct,
        "tp2": tp2, "tp2_pct": tp2_pct,
        "tp3": tp3, "tp3_pct": tp3_pct,
        "rr_ratio": rr_ratio,
        "kelly": round(kelly * 100, 1),
        "half_kelly": round(half_kelly * 100, 1),
        "final_pct": round(final_pct * 100, 1),
        "signal_score": signal_score,
        "batches": batches,
        "total_capital": total_capital,
    }


def generate_summary(result: dict, news: list = None, val: dict = None, fd: dict = None) -> dict:
    """系统性综合分析总结，整合技术/基本面/估值/新闻/预测"""
    sym     = result.get("symbol", "")
    name    = result.get("name", sym)
    price   = result["latest_close"]
    date    = result["latest_date"]
    extra   = result["extra"]
    advice  = result["advice"]
    fc      = result["forecast"]
    rsi     = result["rsi"]
    rule    = result["rule_signal"]
    ml      = result["ml_signal"]
    ml_acc  = result["ml_accuracy"]
    ts      = extra["trend_score"]
    vol     = extra["volatility"]
    dd      = extra["current_drawdown"]
    ret_5d  = extra.get("ret_5d") or 0
    ret_20d = extra.get("ret_20d") or 0
    ret_60d = extra.get("ret_60d") or 0
    mc_prob = fc["mc_prob_up"]
    mc_bull = fc["mc_bull"]
    mc_bear = fc["mc_bear"]
    fcs     = fc["forecasts"]
    rating  = advice["rating"]
    rating_color = advice["rating_color"]
    both_buy  = rule in ("买入", "强烈买入") and ml == "买入"
    both_sell = rule in ("卖出", "强烈卖出") and ml == "卖出"

    # ── 一、走势分析 ──────────────────────────────────────────
    if ts >= 80:   trend_desc = "均线多头排列，价格展现强势上升趋势"
    elif ts >= 65: trend_desc = "短中期均线向上，趋势偏强"
    elif ts >= 50: trend_desc = "趋势中性，多空力量均衡"
    elif ts >= 35: trend_desc = "趋势偏弱，均线向下压制"
    else:          trend_desc = "空头排列，价格处于下降趋势"

    ma5  = result["ma5"]
    ma20 = result["ma20"]
    ma60 = result["ma60"]
    ma_status = []
    if price > ma5:  ma_status.append(f"MA5(${ma5})上方")
    else:            ma_status.append(f"MA5(${ma5})下方")
    if price > ma20: ma_status.append(f"MA20(${ma20})上方")
    else:            ma_status.append(f"MA20(${ma20})下方")
    if price > ma60: ma_status.append(f"MA60(${ma60})上方")
    else:            ma_status.append(f"MA60(${ma60})下方")

    if rsi > 75:   rsi_desc = f"RSI={rsi}，严重超买，短期回调风险高"
    elif rsi > 65: rsi_desc = f"RSI={rsi}，偏高注意超买风险"
    elif rsi < 25: rsi_desc = f"RSI={rsi}，严重超卖，具备反弹条件"
    elif rsi < 35: rsi_desc = f"RSI={rsi}，超卖区间，可关注企稳信号"
    else:          rsi_desc = f"RSI={rsi}，处于正常区间"

    vr = extra.get("vol_ratio", 1)
    vol_desc = f"近5日成交量是均量的{vr}x，" + ("资金明显放大" if vr > 1.5 else ("缩量明显" if vr < 0.7 else "成交量正常"))

    # ── 二、基本面分析 ───────────────────────────────────────
    fd_desc = "基本面数据暂无。"
    if fd and not fd.get("error"):
        pe  = fd.get("pe")
        roe = fd.get("roe")
        rev_yoy = fd.get("revenue_yoy")
        profit_yoy = fd.get("profit_yoy")
        gm  = fd.get("gross_margin")
        parts = []
        if pe:         parts.append(f"PE {pe}x")
        if roe:        parts.append(f"ROE {roe}%")
        if gm:         parts.append(f"毛利率 {gm}%")
        if rev_yoy:    parts.append(f"营收同比 {rev_yoy:+.1f}%")
        if profit_yoy: parts.append(f"净利同比 {profit_yoy:+.1f}%")
        fd_desc = "、".join(parts) + "。" if parts else "基本面数据暂无。"

    # ── 三、估值分析 ─────────────────────────────────────────
    val_desc = ""
    if val and not val.get("error"):
        fv  = val.get("fair_value", 0)
        mos = val.get("margin_of_safety", 0)
        vs  = val.get("val_status", "")
        vc  = val.get("val_color", "")
        buy_p  = val.get("buy_price", 0)
        sell_p = val.get("reduce_price", 0)
        val_desc = (f"综合公允价值 ${fv}，安全边际 {mos:+.1f}%，估值状态：{vc}{vs}。"
                   f"合理买入区间 ${buy_p}~${round(fv*1.05,2)}，减仓价位 ${sell_p}。")

    # ── 四、新闻情绪分析 ──────────────────────────────────────
    news_desc = "新闻数据暂无。"
    news_signal = "neutral"
    if news:
        from news_analyzer import calc_sentiment_summary
        sent = calc_sentiment_summary(news)
        pos_titles = [n["标题"] for n in news if n.get("得分", 0) > 0][:3]
        neg_titles = [n["标题"] for n in news if n.get("得分", 0) < 0][:2]
        news_desc = (f"共收集 {sent['total']} 条新闻，整体情绪 {sent['overall']}（积极 {sent['positive']} 条，消极 {sent['negative']} 条）。")
        if pos_titles:
            news_desc += f"主要积极信息：{'、'.join(pos_titles[:2])}。"
        if neg_titles:
            news_desc += f"主要风险信息：{'\u3001'.join(neg_titles[:1])}。"
        if sent["score"] >= 0.5:   news_signal = "positive"
        elif sent["score"] <= -0.5: news_signal = "negative"

    # ── 五、预测展望 ──────────────────────────────────────────
    pred_5d  = fcs.get("5日",  {}).get("price", price)
    pred_20d = fcs.get("20日", {}).get("price", price)
    pred_5d_ret  = fcs.get("5日",  {}).get("return", 0)
    pred_20d_ret = fcs.get("20日", {}).get("return", 0)
    mc_models = fc.get("model_comparison", {})
    model_consensus = sum(1 for m in mc_models.values() if m.get("return_30d", 0) > 0)
    model_total = len(mc_models)

    # ── 六、风险评估 ──────────────────────────────────────────
    risk_items = []
    if vol > 50:   risk_items.append(f"高波动率（{vol}%）")
    if dd < -15:   risk_items.append(f"深度回撤（{dd}%）")
    if rsi > 70:   risk_items.append("超买风险")
    if extra.get("pct_from_high", 0) > -5: risk_items.append("接近52周高点")
    if fd and fd.get("pe") and float(fd["pe"] or 0) > 40: risk_items.append(f"PE高估({fd['pe']}x)")
    if news_signal == "negative": risk_items.append("新闻情绪偏消极")

    # ── 七、综合评分 ──────────────────────────────────────────
    bull_factors, bear_factors = [], []
    if ts >= 65:          bull_factors.append("技术趋势向上")
    if both_buy:          bull_factors.append("规则+AI信号共振")
    if mc_prob > 55:      bull_factors.append(f"MC上涨概率{mc_prob}%")
    if model_consensus >= max(model_total-1, 1): bull_factors.append("多模型预测一致向上")
    if news_signal == "positive": bull_factors.append("新闻情绪积极")
    if val and val.get("margin_of_safety", 0) > 10: bull_factors.append("估值具备安全边际")
    if fd and fd.get("revenue_yoy") and float(fd["revenue_yoy"] or 0) > 10: bull_factors.append("营收高增长")

    if ts <= 40:          bear_factors.append("技术趋势向下")
    if both_sell:         bear_factors.append("规则+AI信号共振看空")
    if mc_prob < 45:      bear_factors.append(f"MC上涨概率仅{mc_prob}%")
    if rsi > 75:          bear_factors.append("RSI严重超买")
    if dd < -15:          bear_factors.append("深度回撤")
    if val and val.get("margin_of_safety", 0) < -20: bear_factors.append("估值明显高估")

    # ── 八、未来走势判断 ───────────────────────────────────────
    bull_score = len(bull_factors)
    bear_score = len(bear_factors)
    if bull_score >= 4 and bear_score <= 1:
        outlook = "明确向上"; outlook_color = "🟢"
    elif bull_score >= 3 and bull_score > bear_score:
        outlook = "偏多"; outlook_color = "🟩"
    elif bear_score >= 4 and bull_score <= 1:
        outlook = "明确向下"; outlook_color = "🔴"
    elif bear_score >= 3 and bear_score > bull_score:
        outlook = "偏空"; outlook_color = "🟥"
    else:
        outlook = "中性震荡"; outlook_color = "🟡"

    # ── 组装系统性总结文本 ─────────────────────────────────
    summary_text = f"""
**{name}({sym})** 截至 {date}，收盘价 **${price}**。

---

**一、技术面分析**
趋势评分 {ts}/100，{trend_desc}。当前价格处于 {'、'.join(ma_status)}。{rsi_desc}。{vol_desc}。近5日涨跌 {ret_5d:+.2f}%，近20日 {ret_20d:+.2f}%，近60日 {ret_60d:+.2f}%。支撑位 ${extra['support']}，压力位 ${extra['resistance']}。

**二、信号判断**
规则信号《{rule}》，AI信号《{ml}》（模型准确率 {ml_acc}%）。{'**信号一致，可信度高。**' if both_buy or both_sell else '信号存在分歧，建议等待方向明确。'}

**三、基本面与估值**
{fd_desc}{val_desc}

**四、新闻与市场情绪**
{news_desc}

**五、预测展望**
GBR模型预测：5日目标价 ${pred_5d}({pred_5d_ret:+.2f}%)，20日目标价 ${pred_20d}({pred_20d_ret:+.2f}%)。Monte Carlo模拟30日上涨概率 {mc_prob}%，乐观目标 ${mc_bull}，悲观目标 ${mc_bear}。{model_total}种模型中 {model_consensus} 种预测30日上涨。

**六、多空因素对比**
✅ 做多因素：{'、'.join(bull_factors) if bull_factors else '暂无明显做多信号'}
❌ 做空因素：{'、'.join(bear_factors) if bear_factors else '暂无明显做空信号'}

**七、风险提示**
{'、'.join(risk_items) if risk_items else '暂无明显风险信号'}。建议仓位控制在合理范围内，严格执行止损纪律。

**八、未来走势判断**
{outlook_color} **{outlook}**。综合评级：{rating_color} **{rating}**。{advice['actions'][0] if advice['actions'] else ''}
    """.strip()

    return {
        "text":         summary_text,
        "rating":       rating,
        "rating_color": rating_color,
        "trend_score":  ts,
        "signal":       "buy" if both_buy else ("sell" if both_sell else "neutral"),
        "mc_prob_up":   mc_prob,
        "risk_items":   risk_items,
        "outlook":      outlook,
        "outlook_color": outlook_color,
        "bull_factors": bull_factors,
        "bear_factors": bear_factors,
    }


def analyze(df: pd.DataFrame) -> dict:
    df["rule_signal"] = df.apply(_rule_signal, axis=1)
    latest = df.iloc[-1]

    model, scaler, accuracy = _train_ml_model(df)
    latest_features = latest[FEATURE_COLS].values.reshape(1, -1)
    ml_pred  = model.predict(scaler.transform(latest_features))[0]
    ml_proba = model.predict_proba(scaler.transform(latest_features))[0]
    label_map = {-1: "卖出", 0: "持有", 1: "买入"}

    importance = pd.Series(model.feature_importances_, index=FEATURE_COLS).sort_values(ascending=False)
    extra    = _calc_extra(df)
    forecast = _predict_forecast(df)

    result = {
        "symbol":       "",
        "latest_date":  df.index[-1].strftime("%Y-%m-%d"),
        "latest_close": round(float(latest["Close"]), 2),
        "rule_signal":  latest["rule_signal"],
        "ml_signal":    label_map[ml_pred],
        "ml_accuracy":  accuracy,
        "ml_proba":     {label_map[c]: round(float(p) * 100, 1) for c, p in zip(model.classes_, ml_proba)},
        "rsi":          round(float(latest["RSI"]), 1),
        "macd":         round(float(latest["MACD"]), 4),
        "ma5":          round(float(latest["MA5"]), 2),
        "ma20":         round(float(latest["MA20"]), 2),
        "ma60":         round(float(latest["MA60"]), 2),
        "feature_importance": importance,
        "extra":        extra,
        "forecast":     forecast,
        "df":           df,
    }
    result["advice"] = _generate_advice(result)
    return result
