"""
股票AI量化分析工具 (数据源: Alpaca 实时美股)
用法:
  python main.py AAPL              # 单股分析
  python main.py mag7              # 分析美股七姐妹
  python main.py AAPL MSFT NVDA    # 分析多只股票
"""
import sys
import os
sys.stdout.reconfigure(encoding="utf-8")

from data_fetcher import fetch_stock_data, fetch_latest_price
from indicators import add_indicators
from ai_analyzer import analyze
from visualizer import plot_analysis
from config import DEFAULT_PERIOD, DEFAULT_INTERVAL

MAG7 = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA"]
CHIPS = ["AMD", "INTC"]
MAG7_PLUS = MAG7 + CHIPS


def print_report(result: dict, symbol: str):
    print("\n" + "=" * 55)
    print(f"  {symbol} AI量化分析报告")
    print("=" * 55)
    print(f"  日期:       {result['latest_date']}")
    print(f"  最新收盘:   ${result['latest_close']}")
    print(f"  RSI:        {result['rsi']}")
    print(f"  MACD:       {result['macd']}")
    print(f"  MA5/20/60:  {result['ma5']} / {result['ma20']} / {result['ma60']}")
    print(f"  规则信号:   {result['rule_signal']}")
    print(f"  AI信号:     {result['ml_signal']}  (模型准确率 {result['ml_accuracy']}%)")
    print(f"  AI概率:     买入 {result['ml_proba'].get('买入', 0)}%  |  持有 {result['ml_proba'].get('持有', 0)}%  |  卖出 {result['ml_proba'].get('卖出', 0)}%")
    print("=" * 55)


def analyze_symbol(symbol: str, period: str, interval: str):
    try:
        df = fetch_stock_data(symbol, period, interval)
        df = add_indicators(df)
        result = analyze(df)
        result["symbol"] = symbol
        print_report(result, symbol)
        save_path = os.path.join(os.path.dirname(__file__), f"{symbol}_analysis.png")
        plot_analysis(result, symbol, save_path=save_path)
        return result
    except Exception as e:
        print(f"[ERROR] {symbol} 分析失败: {e}")
        return None


def print_summary(results: list):
    """打印多股票汇总对比表"""
    valid = [r for r in results if r]
    if len(valid) < 2:
        return
    print("\n" + "=" * 75)
    print(f"  {'股票':<8} {'收盘价':>10} {'RSI':>7} {'规则信号':>10} {'AI信号':>8} {'AI准确率':>9}")
    print("-" * 75)
    for r in valid:
        print(f"  {r['symbol']:<8} ${r['latest_close']:>9} {r['rsi']:>7} {r['rule_signal']:>10} {r['ml_signal']:>8} {r['ml_accuracy']:>8}%")
    print("=" * 75)
    print("[!] 本工具仅供学习研究，不构成投资建议！")
    print("=" * 75 + "\n")


def main():
    args = sys.argv[1:]
    period = DEFAULT_PERIOD
    interval = DEFAULT_INTERVAL

    if not args:
        symbol_input = input("请输入股票代码 (如 AAPL / mag7 / mag7+): ").strip()
        args = [symbol_input]

    # 解析关键字
    symbols = []
    for a in args:
        if a.lower() == "mag7":
            symbols.extend(MAG7)
        elif a.lower() in ("mag7+", "all"):
            symbols.extend(MAG7_PLUS)
        elif a.lower() == "chips":
            symbols.extend(CHIPS)
        else:
            symbols.append(a.upper())

    print(f"\n[*] 开始分析: {', '.join(symbols)}  周期={period}  间隔={interval}")
    print("[*] 请先确保 .env 文件中已填写 Alpaca API Key\n")

    results = []
    for symbol in symbols:
        result = analyze_symbol(symbol, period, interval)
        results.append(result)

    if len(symbols) > 1:
        print_summary(results)


if __name__ == "__main__":
    main()
