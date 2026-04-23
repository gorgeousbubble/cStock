"""
波浪理论自动识别模块 v3
核心改进：
1. 始终从最新价格往回识别，确保当前价格被纳入分析
2. 滑动窗口从最近极值点开始，优先识别最新结构
3. 严格 Elliott 三大规则验证
4. C浪结束后自动识别新推动浪
"""
import numpy as np
import pandas as pd
from scipy.signal import argrelextrema


# ── 极值点检测 ────────────────────────────────────────────
def find_pivots(close: pd.Series, order: int = 5) -> pd.DataFrame:
    arr      = close.values
    high_idx = argrelextrema(arr, np.greater_equal, order=order)[0]
    low_idx  = argrelextrema(arr, np.less_equal,    order=order)[0]

    pivots = []
    for i in high_idx:
        pivots.append({"idx": i, "date": close.index[i], "price": float(arr[i]), "type": "H"})
    for i in low_idx:
        pivots.append({"idx": i, "date": close.index[i], "price": float(arr[i]), "type": "L"})

    df = pd.DataFrame(pivots).sort_values("idx").reset_index(drop=True)

    # 合并相邻同类型，保留更极端的
    merged = []
    for _, row in df.iterrows():
        r = row.to_dict()
        if merged and merged[-1]["type"] == r["type"]:
            if r["type"] == "H" and r["price"] >= merged[-1]["price"]:
                merged[-1] = r
            elif r["type"] == "L" and r["price"] <= merged[-1]["price"]:
                merged[-1] = r
        else:
            merged.append(r)

    return pd.DataFrame(merged).reset_index(drop=True)


def _validate_impulse(prices: list) -> bool:
    """Elliott 三大规则"""
    if len(prices) < 6:
        return False
    w1 = prices[1] - prices[0]
    w3 = prices[3] - prices[2]
    w5 = prices[5] - prices[4]
    if prices[2] <= prices[0]:   return False  # 规则1: 2浪不破起点
    if w3 < w1 and w3 < w5:     return False  # 规则2: 3浪不是最短
    if prices[4] <= prices[1]:   return False  # 规则3: 4浪不进入1浪区间
    if w1 <= 0 or w3 <= 0 or w5 <= 0: return False
    return True


# ── 核心：从最新价格往回识别波浪 ─────────────────────────
def label_waves(pivots: pd.DataFrame, current_price: float = None) -> list:
    """
    从最近的极值点开始，向前滑动寻找最新的有效波浪结构。
    优先找包含最新价格附近节点的结构。
    """
    if len(pivots) < 4:
        return []

    pts = pivots.to_dict("records")

    # 如果有当前价格，在末尾追加一个"当前价"虚拟节点
    if current_price is not None:
        last = pts[-1]
        cur_type = "H" if current_price >= last["price"] else "L"
        # 只有当前价与最后极值点类型不同，或者差距超过1%才追加
        if cur_type != last["type"] or abs(current_price / last["price"] - 1) > 0.01:
            pts = pts + [{
                "idx":   last["idx"] + 1,
                "date":  pivots["date"].iloc[-1],  # 用最后日期占位
                "price": current_price,
                "type":  cur_type,
                "_virtual": True,
            }]

    best_waves = []
    best_start_idx = -1

    # 从最近的低点开始，向前滑动，找最新的有效5浪结构
    for start in range(len(pts) - 1, -1, -1):
        if pts[start]["type"] != "L":
            continue
        seg = pts[start:]
        if len(seg) < 4:
            continue

        types = [s["type"] for s in seg]

        # 尝试完整 5浪+ABC（9点）
        if len(seg) >= 9 and types[:6] == ["L","H","L","H","L","H"]:
            prices = [s["price"] for s in seg[:6]]
            if _validate_impulse(prices):
                candidate = [
                    {**seg[j], "wave": lbl, "phase": "impulse"}
                    for j, lbl in enumerate(["起点","①","②","③","④","⑤"])
                ]
                if types[5:9] == ["H","L","H","L"]:
                    for j, lbl in enumerate(["A","B","C"]):
                        candidate.append({**seg[6+j], "wave": lbl, "phase": "correction"})
                if start > best_start_idx:
                    best_waves, best_start_idx = candidate, start
                break  # 找到最新的完整结构就停

        # 尝试仅 5浪推动（6点）
        if len(seg) >= 6 and types[:6] == ["L","H","L","H","L","H"]:
            prices = [s["price"] for s in seg[:6]]
            if _validate_impulse(prices):
                candidate = [
                    {**seg[j], "wave": lbl, "phase": "impulse"}
                    for j, lbl in enumerate(["起点","①","②","③","④","⑤"])
                ]
                if start > best_start_idx:
                    best_waves, best_start_idx = candidate, start
                break

        # 尝试不完整推动浪（至少4点：起点①②③）
        if len(seg) >= 4 and types[:4] == ["L","H","L","H"]:
            prices = [s["price"] for s in seg[:4]]
            w1 = prices[1] - prices[0]
            w3 = prices[3] - prices[2]
            if w1 > 0 and w3 > 0 and prices[2] > prices[0]:
                candidate = [
                    {**seg[j], "wave": lbl, "phase": "impulse"}
                    for j, lbl in enumerate(["起点","①","②","③"])
                ]
                # 追加后续节点
                for j, pt in enumerate(seg[4:], 4):
                    remaining_labels = ["④","⑤","A","B","C"]
                    phases = ["impulse","impulse","correction","correction","correction"]
                    idx = j - 4
                    if idx < len(remaining_labels):
                        candidate.append({**pt, "wave": remaining_labels[idx], "phase": phases[idx]})
                if start > best_start_idx:
                    best_waves, best_start_idx = candidate, start
                break

    # 如果还是没找到，退化为最近2个极值点
    if not best_waves and len(pts) >= 2:
        last_low_idx = next((i for i in range(len(pts)-1, -1, -1) if pts[i]["type"] == "L"), 0)
        seg = pts[last_low_idx:]
        labels = ["起点","①","②","③","④","⑤","A","B","C"]
        phases = ["impulse"]*6 + ["correction"]*3
        for j, pt in enumerate(seg[:len(labels)]):
            best_waves.append({**pt, "wave": labels[j], "phase": phases[j]})

    return best_waves


# ── Fibonacci ─────────────────────────────────────────────
FIB_LEVELS = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.618]

def calc_fibonacci(start_price: float, end_price: float) -> list:
    diff = end_price - start_price
    return [{"ratio": r, "price": round(end_price - diff * r, 2)} for r in FIB_LEVELS]


def calc_fib_from_waves(waves: list) -> dict:
    if len(waves) < 2:
        return {}
    result   = {}
    wave_map = {w["wave"]: w for w in waves}

    if "起点" in wave_map and "⑤" in wave_map:
        result["整体推动浪"] = calc_fibonacci(wave_map["起点"]["price"], wave_map["⑤"]["price"])
    if "②" in wave_map and "③" in wave_map:
        result["第3浪"] = calc_fibonacci(wave_map["②"]["price"], wave_map["③"]["price"])
    if "⑤" in wave_map and "C" in wave_map:
        result["调整浪"] = calc_fibonacci(wave_map["⑤"]["price"], wave_map["C"]["price"])
    elif "⑤" in wave_map:
        last_price = waves[-1]["price"]
        result["调整浪(进行中)"] = calc_fibonacci(wave_map["⑤"]["price"], last_price)

    return result


# ── 当前浪位判断与详细建议 ────────────────────────────────
def get_wave_position(waves: list, current_price: float) -> dict:
    if not waves:
        return {"position": "无法识别", "description": "数据不足",
                "market_char": "", "advice": [], "entry": [], "risk": [],
                "fib_hints": [], "signal": "neutral", "trend": "unknown"}

    # 找到最后一个非虚拟节点作为当前浪位
    real_waves = [w for w in waves if not w.get("_virtual")]
    if not real_waves:
        real_waves = waves

    last_wave  = real_waves[-1]["wave"]
    last_price = real_waves[-1]["price"]
    trend      = "up" if current_price >= last_price else "down"
    wave_map   = {w["wave"]: w for w in real_waves}

    detail_map = {
        "起点": {
            "description": "可能处于第1浪启动阶段，趋势刚刚反转",
            "market_char": "市场情绪悲观，成交量开始温和放大，价格止跌企稳",
            "advice": ["可用总仓位的20%-30%小仓试多", "等待价格突破近期高点并放量确认后加仓", "此阶段风险较高，需严格控制仓位"],
            "entry": ["当前价格附近轻仓买入", "突破前高放量后追加仓位"],
            "risk": ["止损设在起点低点下方1%-2%", "若跌破起点则信号失效，立即止损"],
            "signal": "weak_buy",
        },
        "①": {
            "description": "第1浪结束，即将进入第2浪回调",
            "market_char": "第1浪上涨后市场获利了结，回调属正常现象，不必恐慌",
            "advice": ["暂时不追高，等待第2浪回调提供更好买点", "第2浪通常回撤第1浪的38.2%-61.8%，这是黄金买点", "已持仓者可持有，不建议此时加仓"],
            "entry": ["等待回调至Fib 38.2%开始分批建仓", "Fib 61.8%附近为最佳买入区间"],
            "risk": ["止损设在第1浪起点下方", "若回调超过78.6%则第1浪判断可能有误"],
            "signal": "wait",
        },
        "②": {
            "description": "第2浪回调中，这是整个推动浪中最佳买入时机",
            "market_char": "市场情绪再度悲观，主力借机洗盘吸筹，成交量萎缩",
            "advice": ["这是5浪推动中最佳买点，建议积极布局", "分2-3批建仓，总仓位可达50%-70%", "第3浪通常是最强最长的浪，潜在收益最大"],
            "entry": ["Fib 50%附近第一批建仓（30%仓位）", "Fib 61.8%附近第二批加仓（30%仓位）", "Fib 78.6%附近第三批加仓（10%仓位）"],
            "risk": ["止损设在第1浪起点下方1%", "若跌破起点则波浪计数有误，止损离场"],
            "signal": "buy",
        },
        "③": {
            "description": "第3浪结束（最强最长浪），即将进入第4浪回调",
            "market_char": "市场情绪极度乐观，成交量巨大，媒体大量报道",
            "advice": ["第3浪末端是减仓的好时机，建议止盈30%-50%仓位", "第4浪回调通常较浅（38.2%），可等待回调后再加仓", "注意：第4浪不会进入第1浪的价格区间"],
            "entry": ["等待第4浪回调至Fib 38.2%再加仓"],
            "risk": ["已持仓设置移动止盈保护利润", "若跌破第1浪高点则第3浪判断有误"],
            "signal": "partial_sell",
        },
        "④": {
            "description": "第4浪回调中，等待第5浪启动",
            "market_char": "市场震荡整理，成交量萎缩，情绪中性偏谨慎",
            "advice": ["第4浪回调通常较浅，是加仓机会", "可在Fib 38.2%附近加仓，但仓位不宜过重", "提前设好第5浪的止盈目标（通常等于第1浪长度）"],
            "entry": ["Fib 38.2%附近加仓（20%-30%仓位）", "确认企稳后买入"],
            "risk": ["止损设在第1浪高点下方", "若跌破第1浪高点则第4浪判断有误"],
            "signal": "buy",
        },
        "⑤": {
            "description": "第5浪可能结束，警惕ABC调整浪来临",
            "market_char": "市场情绪极度乐观，但成交量开始萎缩（顶背离），散户大量涌入",
            "advice": ["建议大幅减仓或清仓，锁定利润", "第5浪末端常见RSI顶背离，是重要卖出信号", "ABC调整浪通常回撤整个推动浪的38.2%-61.8%"],
            "entry": ["此阶段不建议买入", "等待ABC调整完成后再布局"],
            "risk": ["持仓者设置移动止损保护利润", "若出现RSI顶背离+成交量萎缩，加速减仓"],
            "signal": "sell",
        },
        "A": {
            "description": "ABC调整A浪，第一波下跌",
            "market_char": "市场开始下跌，多数人认为是正常回调，情绪尚未恐慌",
            "advice": ["建议观望，不要抄底", "A浪下跌通常较急，不是买入时机", "等待B浪反弹后再判断C浪目标位"],
            "entry": ["此阶段不建议买入", "等待B浪反弹确认后再做决策"],
            "risk": ["持仓者止损设在前高下方", "A浪跌幅通常为推动浪的38.2%-61.8%"],
            "signal": "wait",
        },
        "B": {
            "description": "ABC调整B浪反弹，这是假反弹",
            "market_char": "市场出现反弹，情绪短暂好转，但成交量不及前期高点",
            "advice": ["B浪反弹是卖出机会，不要追多", "B浪通常反弹A浪的38.2%-61.8%，不会创新高", "等待C浪下跌完成后再考虑买入"],
            "entry": ["此阶段不建议买入", "B浪高点是减仓/做空机会"],
            "risk": ["若B浪超过前高则波浪计数有误", "C浪通常等于A浪长度，提前计算目标位"],
            "signal": "sell",
        },
        "C": {
            "description": "ABC调整C浪，最后一跌，新一轮机会临近",
            "market_char": "市场情绪极度悲观，恐慌性抛售，成交量放大，媒体唱空",
            "advice": ["C浪末端是新一轮推动浪的最佳买入机会", "等待RSI超卖（<30）+ 成交量萎缩 + 价格企稳三重确认", "分批建仓，不要一次性全仓买入"],
            "entry": ["Fib 61.8%回撤位附近第一批建仓", "Fib 78.6%附近第二批加仓", "确认企稳（收阳线+放量）后第三批加仓"],
            "risk": ["止损设在C浪低点下方1%-2%", "若跌破前期重要支撑则重新评估"],
            "signal": "buy",
        },
    }

    info = detail_map.get(last_wave, {
        "description": "浪位不明确", "market_char": "",
        "advice": ["建议观望，等待信号明确"],
        "entry": [], "risk": [], "signal": "neutral",
    })

    # Fibonacci 具体价格提示
    fib_hints = []
    if last_wave in ("②", "④", "C") and "起点" in wave_map and "①" in wave_map:
        w_start = wave_map["起点"]["price"]
        w1_high = wave_map["①"]["price"]
        if w1_high > w_start:
            for ratio, label in [(0.382, "38.2%"), (0.618, "61.8%"), (0.786, "78.6%")]:
                price = round(w1_high - (w1_high - w_start) * ratio, 2)
                fib_hints.append(f"Fib {label} 支撑: ${price}")

    if last_wave == "⑤" and "起点" in wave_map and "⑤" in wave_map:
        w_start = wave_map["起点"]["price"]
        w5_high = wave_map["⑤"]["price"]
        for ratio, label in [(0.382, "38.2%"), (0.618, "61.8%")]:
            price = round(w5_high - (w5_high - w_start) * ratio, 2)
            fib_hints.append(f"调整目标 Fib {label}: ${price}")

    return {
        "position":    last_wave,
        "description": info["description"],
        "market_char": info.get("market_char", ""),
        "advice":      info["advice"],
        "entry":       info.get("entry", []),
        "risk":        info.get("risk", []),
        "fib_hints":   fib_hints,
        "signal":      info["signal"],
        "trend":       trend,
    }


# ── 主入口 ────────────────────────────────────────────────
def analyze_waves(df: pd.DataFrame, order: int = None) -> dict:
    close         = df["Close"]
    current_price = float(close.iloc[-1])
    n             = len(close)

    # 根据数据量自动选择 order
    if order is None:
        if n < 100:   order = 3
        elif n < 200: order = 5
        elif n < 400: order = 7
        else:         order = 10

    # 多 order 尝试，选择识别到最完整结构的结果
    orders_to_try = sorted(set([order, max(3, order-2), order+2]), reverse=True)
    best_waves    = []
    best_pivots   = pd.DataFrame()
    best_order    = order

    for o in orders_to_try:
        pivots = find_pivots(close, order=o)
        waves  = label_waves(pivots, current_price=current_price)
        wave_labels = [w["wave"] for w in waves if not w.get("_virtual")]

        has_5  = "⑤" in wave_labels
        has_3  = "③" in wave_labels
        prev_5 = "⑤" in [w["wave"] for w in best_waves if not w.get("_virtual")]
        prev_3 = "③" in [w["wave"] for w in best_waves if not w.get("_virtual")]

        # 优先：有完整5浪 > 有3浪 > 节点更多
        if (has_5 and not prev_5) or \
           (has_5 == prev_5 and has_3 and not prev_3) or \
           (has_5 == prev_5 and has_3 == prev_3 and len(waves) > len(best_waves)):
            best_waves, best_pivots, best_order = waves, pivots, o

    if not best_waves:
        best_pivots = find_pivots(close, order=order)
        best_waves  = label_waves(best_pivots, current_price=current_price)

    # C浪结束后自动识别新推动浪
    real_waves  = [w for w in best_waves if not w.get("_virtual")]
    wave_labels = [w["wave"] for w in real_waves]
    if "C" in wave_labels:
        c_wave = next(w for w in real_waves if w["wave"] == "C")
        if current_price > c_wave["price"] * 1.08:
            c_idx      = c_wave["idx"]
            new_close  = close.iloc[c_idx:]
            if len(new_close) >= 10:
                new_order  = max(3, best_order - 2)
                new_pivots = find_pivots(new_close, order=new_order)
                new_waves  = label_waves(new_pivots, current_price=current_price)
                if len([w for w in new_waves if not w.get("_virtual")]) >= 2:
                    best_waves  = new_waves
                    best_pivots = new_pivots

    fib = calc_fib_from_waves([w for w in best_waves if not w.get("_virtual")])
    pos = get_wave_position(best_waves, current_price)

    return {
        "pivots":     best_pivots,
        "waves":      [w for w in best_waves if not w.get("_virtual")],
        "fib_levels": fib,
        "position":   pos,
        "close":      close,
        "order_used": best_order,
    }
