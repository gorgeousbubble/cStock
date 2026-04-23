"""
综合目标价与操作策略分析模块
整合：技术面 + 基本面 + 量化 + 波浪 + 行业 + 宏观 + 情绪
"""
import numpy as np


def calc_valuation(result: dict, fd: dict = None) -> dict:
    """
    多方法估值分析：PE / PEG / DCF / PB / EV/EBITDA / 格雷厄姆公式
    返回各方法估值、综合公允价值、安全边际
    """
    price = float(result["latest_close"])
    extra = result["extra"]
    fc    = result["forecast"]

    methods   = {}   # {方法名: 估值价格}
    notes     = {}   # {方法名: 说明}
    available = 0

    def _safe(key):
        if not fd or fd.get("error"):
            return 0
        try:
            v = fd.get(key)
            return float(v) if v is not None and str(v) not in ("nan", "None", "", "N/A") else 0
        except Exception:
            return 0

    eps        = _safe("eps")
    pe         = _safe("pe")
    peg        = _safe("peg")
    roe        = _safe("roe")
    profit_yoy = _safe("profit_yoy")
    rev_yoy    = _safe("revenue_yoy")
    net_margin = _safe("net_margin")
    debt_ratio = _safe("debt_ratio")
    dcf_raw    = _safe("dcf_value")

    # ── 1. PE 估值法 ─────────────────────────────────────
    if eps > 0 and pe > 0:
        # 合理PE：成长股用PEG=1对应PE，价值股用行业均值简化
        g = max(profit_yoy, 5.0)  # 至少5%增速
        fair_pe_growth = min(g, 40)          # 成长PE上限40
        fair_pe_value  = 15.0                # 价值PE基准
        fair_pe = fair_pe_growth * 0.6 + fair_pe_value * 0.4
        pe_val  = round(fair_pe * eps, 2)
        methods["PE估值"] = pe_val
        notes["PE估值"]   = f"合理PE {round(fair_pe,1)}x × EPS ${eps} = ${pe_val}（当前PE {round(pe,1)}x）"
        available += 1

    # ── 2. PEG 估值法 ────────────────────────────────────
    if eps > 0 and profit_yoy > 0:
        # PEG=1 对应合理价：PE = 增速，目标价 = 增速 × EPS
        peg_pe  = min(profit_yoy, 50)  # PEG=1时的PE
        peg_val = round(peg_pe * eps, 2)
        methods["PEG估值"] = peg_val
        notes["PEG估值"]   = f"PEG=1 对应PE {round(peg_pe,1)}x × EPS ${eps} = ${peg_val}（净利增速 {round(profit_yoy,1)}%）"
        available += 1

    # ── 3. DCF 现金流折现 ────────────────────────────────
    if dcf_raw > 0:
        methods["DCF"] = dcf_raw
        g5 = min(profit_yoy / 100, 0.30) if profit_yoy > 0 else 0.08
        notes["DCF"] = f"5年增速 {round(g5*100,1)}%，折现率10%，终值PE=15，内在价值 ${dcf_raw}"
        available += 1
    elif eps > 0:
        # 自行计算简化DCF
        g5  = min(max(profit_yoy / 100, 0.05), 0.30) if profit_yoy > 0 else 0.08
        dcf_calc = round(eps * (1 + g5)**5 * 15 / (1.10**5), 2)
        methods["DCF"] = dcf_calc
        notes["DCF"] = f"5年增速 {round(g5*100,1)}%，折现率10%，终值PE=15，内在价值 ${dcf_calc}"
        available += 1

    # ── 4. 格雷厄姆公式 ─────────────────────────────────
    # V = EPS × (8.5 + 2g) × 4.4 / AAA债券收益率(用4.5%)
    if eps > 0:
        g_rate  = min(max(profit_yoy, 0), 25)
        graham  = round(eps * (8.5 + 2 * g_rate) * 4.4 / 4.5, 2)
        methods["格雷厄姆"] = graham
        notes["格雷厄姆"]   = f"V = EPS${eps} × (8.5 + 2×{round(g_rate,1)}%) × 4.4/4.5 = ${graham}"
        available += 1

    # ── 5. ROE-PB 估值法 ────────────────────────────────
    # 合理PB = ROE / 要求回报率(10%)，目标价 = 合理PB × 每股净资产
    # 用 price/pe*eps 反推每股净资产近似
    if roe > 0 and eps > 0 and pe > 0:
        bvps       = round(eps / (roe / 100), 2) if roe > 0 else None  # 每股净资产
        fair_pb    = round(roe / 10, 2)           # 合理PB = ROE/10%
        fair_pb    = min(fair_pb, 10)             # 上限10倍
        if bvps and bvps > 0:
            pb_val = round(fair_pb * bvps, 2)
            methods["ROE-PB"] = pb_val
            notes["ROE-PB"]   = f"合理PB {fair_pb}x × BVPS ${bvps} = ${pb_val}（ROE {round(roe,1)}%）"
            available += 1

    # ── 6. 技术面公允价值（支撑压力中枢）───────────────
    tech_fair = round((extra["support"] + extra["resistance"]) / 2, 2)
    methods["技术中枢"] = tech_fair
    notes["技术中枢"]   = f"60日支撑 ${extra['support']} ~ 压力 ${extra['resistance']} 中枢 ${tech_fair}"

    # ── 7. MC 概率加权公允价值 ──────────────────────────
    mc_fair = round(
        fc["mc_mean_final"] * 0.5 +
        fc["mc_bull"]       * 0.25 +
        fc["mc_bear"]       * 0.25, 2
    )
    methods["MC概率"] = mc_fair
    notes["MC概率"]   = f"均值${fc['mc_mean_final']}×50% + 乐观${fc['mc_bull']}×25% + 悲观${fc['mc_bear']}×25% = ${mc_fair}"

    # ── 综合公允价值（等权平均基本面方法）───────────────
    fundamental_methods = ["PE估值", "PEG估值", "DCF", "格雷厄姆", "ROE-PB"]
    fund_vals = [methods[m] for m in fundamental_methods if m in methods and methods[m] > 0]

    if fund_vals:
        fair_value = round(np.mean(fund_vals), 2)
    else:
        fair_value = round((tech_fair + mc_fair) / 2, 2)

    # 综合目标价（基本面60% + 技术30% + MC10%）
    w_fund = 0.60 if fund_vals else 0.0
    w_tech = 0.30 if fund_vals else 0.60
    w_mc   = 0.10 if fund_vals else 0.40
    综合目标 = round(
        fair_value  * w_fund +
        tech_fair   * w_tech +
        mc_fair     * w_mc, 2
    )

    # 安全边际
    margin_of_safety = round((fair_value / price - 1) * 100, 1) if fair_value > 0 else 0

    # 估值状态
    if margin_of_safety >= 20:   val_status, val_color = "明显低估", "🟢"
    elif margin_of_safety >= 5:  val_status, val_color = "略微低估", "🟩"
    elif margin_of_safety >= -5: val_status, val_color = "估值合理", "🟡"
    elif margin_of_safety >= -20:val_status, val_color = "略微高估", "🟠"
    else:                        val_status, val_color = "明显高估", "🔴"

    # ── 合理估值价格区间 ─────────────────────────────────
    # 强烈买入：公允价值打8折（20%安全边际）
    # 买入：公允价值打9折（10%安全边际）
    # 合理持有区间：公允价值 ±10%
    # 减仓：公允价值溢价20%
    # 强烈卖出：公允价值溢价35%
    strong_buy  = round(fair_value * 0.80, 2)
    buy_price   = round(fair_value * 0.90, 2)
    hold_low    = round(fair_value * 0.95, 2)
    hold_high   = round(fair_value * 1.10, 2)
    reduce_price= round(fair_value * 1.20, 2)
    strong_sell = round(fair_value * 1.35, 2)

    # 当前价所处区间
    if price <= strong_buy:
        price_zone, zone_color = "强烈买入区", "🟢"
    elif price <= buy_price:
        price_zone, zone_color = "买入区", "🟩"
    elif price <= hold_high:
        price_zone, zone_color = "合理持有区", "🟡"
    elif price <= reduce_price:
        price_zone, zone_color = "偏贵区", "🟠"
    elif price <= strong_sell:
        price_zone, zone_color = "减仓区", "🟥"
    else:
        price_zone, zone_color = "强烈卖出区", "🔴"

    price_zones = [
        {"区间": "🟢 强烈买入", "价格下限": "—",          "价格上限": f"${strong_buy}",   "说明": "公允价值8折，安全边际20%以上"},
        {"区间": "🟩 买入",     "价格下限": f"${strong_buy}","价格上限": f"${buy_price}",   "说明": "公允价值9折，安全边际10%"},
        {"区间": "🟡 合理持有", "价格下限": f"${hold_low}", "价格上限": f"${hold_high}",  "说明": "公允价值±10%区间内"},
        {"区间": "🟠 偏贵",     "价格下限": f"${hold_high}","价格上限": f"${reduce_price}","说明": "溢价10%~20%，谨慎追高"},
        {"区间": "🟥 减仓",     "价格下限": f"${reduce_price}","价格上限": f"${strong_sell}","说明": "溢价20%~35%，逐步减仓"},
        {"区间": "🔴 强烈卖出", "价格下限": f"${strong_sell}","价格上限": "—",             "说明": "溢价35%以上，严重高估"},
    ]

    # 各方法与当前价偏离
    deviations = {
        m: round((v / price - 1) * 100, 1)
        for m, v in methods.items()
    }

    # 估值建议
    val_advice = []
    if margin_of_safety >= 15:
        val_advice.append(f"综合公允价值 ${fair_value}，当前价存在 {margin_of_safety}% 安全边际，处于{price_zone}")
    elif margin_of_safety <= -15:
        val_advice.append(f"综合公允价值 ${fair_value}，当前价高于公允价值 {abs(margin_of_safety)}%，处于{price_zone}")
    else:
        val_advice.append(f"综合公允价值 ${fair_value}，当前价与公允价值接近，处于{price_zone}")

    if available == 0:
        val_advice.append("⚠️ 基本面数据不足，估值仅供参考，以技术面为主")

    above = sum(1 for v in methods.values() if v > price)
    below = sum(1 for v in methods.values() if v < price)
    total = len(methods)
    val_advice.append(f"{total} 种估值方法中，{above} 种高于当前价，{below} 种低于当前价")

    return {
        "methods":            methods,
        "notes":              notes,
        "deviations":         deviations,
        "fair_value":         fair_value,
        "综合目标":            综合目标,
        "margin_of_safety":   margin_of_safety,
        "val_status":         val_status,
        "val_color":          val_color,
        "val_advice":         val_advice,
        "available_methods":  available,
        "strong_buy":         strong_buy,
        "buy_price":          buy_price,
        "hold_low":           hold_low,
        "hold_high":          hold_high,
        "reduce_price":       reduce_price,
        "strong_sell":        strong_sell,
        "price_zone":         price_zone,
        "zone_color":         zone_color,
        "price_zones":        price_zones,
    }


def calc_target_price(result: dict, fd: dict = None, industry: dict = None) -> dict:
    """
    综合所有维度计算目标价区间与操作策略
    返回结构化的目标价、置信度、策略建议
    """
    price   = float(result["latest_close"])
    extra   = result["extra"]
    fc      = result["forecast"]
    advice  = result["advice"]
    rsi     = float(result["rsi"])
    ts      = extra["trend_score"]
    vol     = extra["volatility"] / 100
    support = extra["support"]
    resist  = extra["resistance"]

    targets = {}   # 各维度目标价
    weights = {}   # 各维度权重
    signals = []   # 信号汇总

    # ── 1. 技术面目标价 ──────────────────────────────────
    # 用 Monte Carlo 均值 + 压力位
    mc_mean  = fc["mc_mean_final"]
    mc_bull  = fc["mc_bull"]
    mc_bear  = fc["mc_bear"]
    fcs      = fc["forecasts"]
    pred_20d = fcs.get("20日", {}).get("price", price)

    tech_target = round((mc_mean * 0.5 + pred_20d * 0.3 + resist * 0.2), 2)
    targets["技术面"] = tech_target
    weights["技术面"] = 0.30

    tech_signal = "看多" if tech_target > price * 1.02 else ("看空" if tech_target < price * 0.98 else "中性")
    signals.append(f"技术面：{tech_signal}，MC均值 ${mc_mean}，20日预测 ${pred_20d}")

    # ── 2. 基本面目标价 ──────────────────────────────────
    fd_target = None
    if fd and not fd.get("error"):
        dcf   = fd.get("dcf_value")
        pe    = fd.get("pe")
        eps   = fd.get("eps")
        roe   = fd.get("roe")
        profit_yoy = fd.get("profit_yoy")

        # PE估值法：用行业合理PE * EPS
        pe_target = None
        if pe and eps and float(eps) > 0:
            # 合理PE：当前PE向历史均值回归（简化：取当前PE的0.85~1.15区间中值）
            fair_pe = float(pe) * 0.95 if float(pe) > 30 else float(pe) * 1.05
            pe_target = round(fair_pe * float(eps), 2)

        # DCF估值
        if dcf and pe_target:
            fd_target = round((dcf * 0.5 + pe_target * 0.5), 2)
        elif dcf:
            fd_target = dcf
        elif pe_target:
            fd_target = pe_target

        if fd_target:
            targets["基本面"] = fd_target
            weights["基本面"] = 0.30
            fd_signal = "低估" if fd_target > price * 1.05 else ("高估" if fd_target < price * 0.95 else "合理")
            signals.append(f"基本面：{fd_signal}，DCF ${dcf or 'N/A'}，PE估值 ${pe_target or 'N/A'}")
        else:
            weights["技术面"] += 0.15  # 基本面缺失，权重转移
    else:
        weights["技术面"] += 0.15

    # ── 3. 量化目标价 ────────────────────────────────────
    qt = result.get("quant", {})
    if qt:
        zs   = qt["zscore"]
        risk = qt["risk"]
        # Z-Score 均值回归目标：价格回归到 MA20
        ma20_target = float(zs["ma"].iloc[-1]) if hasattr(zs.get("ma", None), "iloc") else price
        sharpe = float(risk.get("sharpe", 0) or 0)

        # 夏普比率调整：高夏普给更高目标
        sharpe_adj = 1.0 + max(min(sharpe * 0.05, 0.15), -0.15)
        qt_target  = round(ma20_target * sharpe_adj, 2)
        targets["量化"] = qt_target
        weights["量化"] = 0.15
        qt_signal = "均值回归上行" if price < ma20_target else "均值回归下行"
        signals.append(f"量化：{qt_signal}，MA20目标 ${round(ma20_target,2)}，夏普 {risk.get('sharpe','N/A')}")

    # ── 4. 波浪理论目标价 ────────────────────────────────
    wave_result = result.get("wave", {})
    fib = wave_result.get("fib_levels", {})
    wave_target = None
    if fib:
        key = "整体推动浪" if "整体推动浪" in fib else (list(fib.keys())[0] if fib else None)
        if key:
            levels = fib[key]
            # 找最近的上方 Fib 位作为目标
            above = [lv["price"] for lv in levels if lv["price"] > price * 1.01]
            if above:
                wave_target = round(min(above), 2)
                targets["波浪"] = wave_target
                weights["波浪"] = 0.15
                signals.append(f"波浪：下一Fib目标 ${wave_target}")
            else:
                weights["技术面"] = weights.get("技术面", 0.30) + 0.075
                weights["量化"]   = weights.get("量化",   0.15) + 0.075
    else:
        weights["技术面"] = weights.get("技术面", 0.30) + 0.075
        weights["量化"]   = weights.get("量化",   0.15) + 0.075

    # ── 5. 行业对比目标价 ────────────────────────────────
    ind_target = None
    if industry and isinstance(industry, dict) and "peers" in industry:
        peers = industry["peers"]
        # 行业平均涨跌幅 → 推算目标价
        ret_list = []
        for p in peers:
            if not p.get("是否当前"):
                try:
                    ret_str = p.get("1月涨跌", "0%").replace("%", "").replace("+", "")
                    ret_list.append(float(ret_str))
                except Exception:
                    pass
        if ret_list:
            avg_peer_ret = np.mean(ret_list) / 100
            ind_target   = round(price * (1 + avg_peer_ret), 2)
            targets["行业"] = ind_target
            weights["行业"] = 0.10
            signals.append(f"行业：同行平均1月涨跌 {round(avg_peer_ret*100,1)}%，行业目标 ${ind_target}")

    # ── 6. 归一化权重 ────────────────────────────────────
    total_w = sum(weights.values())
    norm_w  = {k: v / total_w for k, v in weights.items()}

    # ── 7. 加权综合目标价 ────────────────────────────────
    weighted_target = sum(targets[k] * norm_w[k] for k in targets)
    weighted_target = round(weighted_target, 2)

    # ── 8. 目标价区间（±波动率调整）────────────────────
    vol_adj      = vol * np.sqrt(20 / 252)  # 20日波动
    target_low   = round(weighted_target * (1 - vol_adj * 1.5), 2)
    target_high  = round(weighted_target * (1 + vol_adj * 1.5), 2)
    target_return = round((weighted_target / price - 1) * 100, 2)

    # ── 9. 综合置信度评分 ────────────────────────────────
    confidence = 50
    # 多维度一致性加分
    above_price = sum(1 for v in targets.values() if v > price * 1.02)
    below_price = sum(1 for v in targets.values() if v < price * 0.98)
    n_targets   = len(targets)
    if n_targets > 0:
        if above_price / n_targets >= 0.7:   confidence += 20
        elif above_price / n_targets >= 0.5: confidence += 10
        elif below_price / n_targets >= 0.7: confidence -= 20
        elif below_price / n_targets >= 0.5: confidence -= 10

    if ts >= 75:   confidence += 10
    elif ts <= 35: confidence -= 10
    if 40 < rsi < 65: confidence += 5
    elif rsi > 75 or rsi < 25: confidence -= 5
    if n_targets >= 4: confidence += 5  # 维度越多越可信

    confidence = max(10, min(95, confidence))

    # ── 10. 操作策略 ─────────────────────────────────────
    strategy = _build_strategy(
        price, weighted_target, target_low, target_high,
        target_return, confidence, ts, rsi, vol,
        support, resist, extra, result, mc_bull, mc_bear, fd
    )

    return {
        "price":           price,
        "target":          weighted_target,
        "target_low":      target_low,
        "target_high":     target_high,
        "target_return":   target_return,
        "confidence":      confidence,
        "targets_by_dim":  targets,
        "weights":         norm_w,
        "signals":         signals,
        "strategy":        strategy,
        "mc_bull":         mc_bull,
        "mc_bear":         mc_bear,
    }


def _build_strategy(price, target, t_low, t_high, t_ret, conf,
                    ts, rsi, vol, support, resist, extra,
                    result, mc_bull, mc_bear, fd) -> dict:
    """根据综合评估生成操作策略"""

    # 方向判断
    if t_ret >= 8 and conf >= 60 and ts >= 60:
        direction = "积极做多"
        dir_color = "🟢"
    elif t_ret >= 3 and conf >= 50:
        direction = "温和做多"
        dir_color = "🟩"
    elif t_ret <= -8 and conf >= 60 and ts <= 40:
        direction = "积极做空/减仓"
        dir_color = "🔴"
    elif t_ret <= -3:
        direction = "谨慎减仓"
        dir_color = "🟥"
    else:
        direction = "观望持有"
        dir_color = "🟡"

    # 仓位建议
    base_pos = 0.10
    if conf >= 75:   base_pos = 0.20
    elif conf >= 60: base_pos = 0.15
    elif conf < 40:  base_pos = 0.05

    vol_factor = min(0.20 / max(vol, 0.10), 1.5)
    pos_pct    = round(min(base_pos * vol_factor, 0.30) * 100, 1)

    # 止损位
    atr = result.get("quant", {}).get("risk", {})
    stop = round(max(support * 0.99, price * 0.93), 2)
    stop_pct = round((stop / price - 1) * 100, 2)

    # 分批建仓价
    entry_plan = [
        {"批次": "第1批（立即）", "价格": price,
         "比例": f"{round(pos_pct*0.4,1)}%", "条件": "当前价位，信号确认后入场"},
        {"批次": "第2批（回调）", "价格": round(price * 0.97, 2),
         "比例": f"{round(pos_pct*0.35,1)}%", "条件": f"回调至 ${round(price*0.97,2)} 附近"},
        {"批次": "第3批（支撑）", "价格": round(support * 1.01, 2),
         "比例": f"{round(pos_pct*0.25,1)}%", "条件": f"回调至支撑位 ${round(support*1.01,2)} 附近"},
    ]

    # 止盈计划
    risk_amt = price - stop
    tp_plan = [
        {"目标": "TP1（保守）", "价格": round(price + risk_amt * 1.5, 2),
         "涨幅": f"+{round(risk_amt*1.5/price*100,1)}%", "操作": "减仓 1/3"},
        {"目标": "TP2（目标价）", "价格": target,
         "涨幅": f"{t_ret:+.1f}%", "操作": "减仓 1/3"},
        {"目标": "TP3（乐观）",  "价格": round(min(mc_bull, resist), 2),
         "涨幅": f"+{round((min(mc_bull,resist)/price-1)*100,1)}%", "操作": "剩余仓位清仓"},
    ]

    # 关键风险
    risks = []
    if rsi > 70:   risks.append(f"RSI {rsi} 超买，短期回调风险")
    if vol > 0.5:  risks.append(f"年化波动率 {round(vol*100,1)}% 较高，仓位需控制")
    if extra.get("pct_from_high", 0) > -5: risks.append("股价接近52周高点，上方空间有限")
    if extra.get("current_drawdown", 0) < -15: risks.append(f"当前回撤 {extra['current_drawdown']}%，趋势偏弱")
    if fd and fd.get("pe") and float(fd["pe"] or 0) > 40: risks.append(f"PE {fd['pe']} 估值偏高")
    if not risks: risks.append("当前无明显风险信号")

    # 催化剂
    catalysts = []
    if ts >= 70:   catalysts.append("均线多头排列，趋势强势")
    if rsi < 40:   catalysts.append("RSI 超卖，存在反弹机会")
    if extra.get("vol_ratio", 1) > 1.5: catalysts.append("近期成交量放大，资金关注度提升")
    if fd and fd.get("roe") and float(fd["roe"] or 0) > 20: catalysts.append(f"ROE {fd['roe']}% 盈利能力强")
    if fd and fd.get("revenue_yoy") and float(fd["revenue_yoy"] or 0) > 10:
        catalysts.append(f"营收同比增长 {fd['revenue_yoy']}%，基本面向好")
    if not catalysts: catalysts.append("等待更明确的催化剂信号")

    return {
        "direction":   direction,
        "dir_color":   dir_color,
        "pos_pct":     pos_pct,
        "stop":        stop,
        "stop_pct":    stop_pct,
        "entry_plan":  entry_plan,
        "tp_plan":     tp_plan,
        "risks":       risks,
        "catalysts":   catalysts,
        "horizon":     "20-30个交易日",
    }
