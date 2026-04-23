"""
新闻舆情分析模块
- 美股：Alpaca News API
- A股/港股：AKShare + 腾讯财经
情绪分析：基于关键词的简单情绪打分
"""
import os
import pandas as pd
from datetime import datetime, timedelta


# ── 情绪关键词 ────────────────────────────────────────────
POSITIVE_WORDS = [
    "上涨", "涨", "突破", "新高", "增长", "盈利", "超预期", "利好", "买入",
    "推荐", "强烈推荐", "上调", "扩张", "增持", "回购", "分红", "创新",
    "beat", "surge", "rally", "gain", "profit", "growth", "upgrade",
    "buy", "outperform", "record", "high", "strong", "positive", "bullish"
]

NEGATIVE_WORDS = [
    "下跌", "跌", "下调", "亏损", "低于预期", "利空", "卖出", "减持",
    "风险", "警告", "诉讼", "罚款", "裁员", "下滑", "萎缩", "违规",
    "fall", "drop", "decline", "loss", "miss", "downgrade", "sell",
    "underperform", "risk", "warning", "lawsuit", "layoff", "bearish", "weak"
]


def _sentiment_score(text: str) -> tuple:
    """简单关键词情绪打分，返回 (score, label)"""
    if not text:
        return 0, "中性"
    text_lower = text.lower()
    pos = sum(1 for w in POSITIVE_WORDS if w in text_lower)
    neg = sum(1 for w in NEGATIVE_WORDS if w in text_lower)
    score = pos - neg
    if score >= 2:   return score, "积极"
    elif score == 1: return score, "偏积极"
    elif score == -1: return score, "偏消极"
    elif score <= -2: return score, "消极"
    return 0, "中性"


def fetch_us_news(symbol: str, limit: int = 15) -> list:
    """获取美股新闻：Alpaca News + Yahoo Finance RSS + Seeking Alpha"""
    results = []

    # ── 1. Alpaca News API ────────────────────────────────────
    try:
        from dotenv import load_dotenv
        from curl_cffi import requests as cr
        load_dotenv()
        key    = os.getenv("ALPACA_API_KEY", "")
        secret = os.getenv("ALPACA_SECRET_KEY", "")
        if key:
            session = cr.Session(impersonate="chrome")
            resp = session.get(
                "https://data.alpaca.markets/v1beta1/news",
                params={"symbols": symbol, "limit": limit, "sort": "desc"},
                headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret},
                timeout=10
            )
            if resp.status_code == 200:
                for n in resp.json().get("news", []):
                    title   = n.get("headline", "")
                    summary = n.get("summary", "")
                    score, label = _sentiment_score(title + " " + summary)
                    results.append({
                        "时间":  n.get("created_at", "")[:16].replace("T", " "),
                        "标题":  title,
                        "摘要":  summary[:150] + "..." if len(summary) > 150 else summary,
                        "来源":  n.get("author", "Alpaca News"),
                        "情绪":  label,
                        "得分":  score,
                        "链接":  n.get("url", ""),
                    })
    except Exception:
        pass

    # ── 2. Yahoo Finance RSS ───────────────────────────────
    try:
        from curl_cffi import requests as cr
        import xml.etree.ElementTree as ET
        session = cr.Session(impersonate="chrome")
        resp = session.get(
            f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US",
            timeout=10
        )
        if resp.status_code == 200:
            root = ET.fromstring(resp.text)
            for item in root.findall(".//item")[:8]:
                title   = item.findtext("title", "").strip()
                summary = item.findtext("description", "").strip()
                pub     = item.findtext("pubDate", "")[:16]
                url     = item.findtext("link", "")
                if not title:
                    continue
                score, label = _sentiment_score(title + " " + summary)
                results.append({
                    "时间":  pub,
                    "标题":  title,
                    "摘要":  summary[:150] + "..." if len(summary) > 150 else summary,
                    "来源":  "Yahoo Finance",
                    "情绪":  label,
                    "得分":  score,
                    "链接":  url,
                })
    except Exception:
        pass

    # ── 3. Finviz 新闻标题──────────────────────────────────
    try:
        from curl_cffi import requests as cr
        import re
        session = cr.Session(impersonate="chrome")
        resp = session.get(
            f"https://finviz.com/quote.ashx?t={symbol}",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        if resp.status_code == 200:
            matches = re.findall(
                r'class="news-link-left"[^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>([^<]{10,120})</a>.*?<td[^>]*>([^<]+)</td>',
                resp.text, re.DOTALL
            )
            for url, title, pub in matches[:6]:
                title = title.strip()
                score, label = _sentiment_score(title)
                results.append({
                    "时间":  pub.strip(),
                    "标题":  title,
                    "摘要":  "",
                    "来源":  "Finviz",
                    "情绪":  label,
                    "得分":  score,
                    "链接":  url,
                })
    except Exception:
        pass

    # 去重并按时间排序
    seen = set()
    unique = []
    for n in results:
        key = n["标题"][:30]
        if key not in seen:
            seen.add(key)
            unique.append(n)
    return unique[:limit]


def _fetch_ths_news(code: str, limit: int = 10) -> list:
    """东方财富个股公告（按股票代码精确过滤）"""
    try:
        from curl_cffi import requests as cr
        from market_data import detect_market
        session = cr.Session(impersonate="chrome")
        market  = detect_market(code)

        # 市场代码映射
        if market == "CN":
            prefix = "sh" if code.startswith(("6", "5")) else "sz"
            ann_type = "SHA" if prefix == "sh" else "SZA"
            stock_code = code
        elif market == "HK":
            ann_type = "HKA"
            stock_code = code.zfill(5)
        else:
            return []

        resp = session.get(
            "https://np-anotice-stock.eastmoney.com/api/security/ann",
            params={
                "sr": "-1", "page_size": str(limit), "page_index": "1",
                "ann_type": ann_type, "client_source": "web",
                "stock_list": stock_code
            },
            timeout=10
        )
        if resp.status_code != 200:
            return []

        items = resp.json().get("data", {}).get("list", [])
        results = []
        for n in items:
            title = n.get("title", "").strip()
            if not title:
                continue
            date  = n.get("notice_date", "")[:10]
            url   = f"https://data.eastmoney.com/notices/detail/{stock_code}/{n.get('art_code','')}.html"
            score, label = _sentiment_score(title)
            results.append({
                "时间":  date,
                "标题":  title,
                "摘要":  "",
                "来源":  "东方财富公告",
                "情绪":  label,
                "得分":  score,
                "链接":  url,
            })
        return results
    except Exception:
        return []


def fetch_cn_news(symbol: str, limit: int = 10) -> list:
    """获取A股公告和资讯（东方财富，按股票代码精确过滤）"""
    return _fetch_ths_news(symbol, limit)


def _fetch_cn_news_fallback(symbol: str, limit: int = 10) -> list:
    """A股新闻备用接口（新浪财经）"""
    try:
        from curl_cffi import requests as cr
        session = cr.Session(impersonate="chrome")
        prefix  = "sh" if symbol.startswith(("6", "5")) else "sz"
        resp = session.get(
            f"https://finance.sina.com.cn/realstock/company/{prefix}{symbol}/nc.shtml",
            timeout=10
        )
        import re
        titles = re.findall(r'<a[^>]*href="([^"]*)"[^>]*>([^<]{5,50})</a>', resp.text)
        results = []
        for url, title in titles[:limit]:
            if "http" not in url:
                continue
            score, label = _sentiment_score(title)
            results.append({
                "时间":  datetime.now().strftime("%Y-%m-%d"),
                "标题":  title.strip(),
                "摘要":  "",
                "来源":  "新浪财经",
                "情绪":  label,
                "得分":  score,
                "链接":  url,
            })
        return results
    except Exception:
        return []


def fetch_hk_news(symbol: str, limit: int = 10) -> list:
    """获取港股相关资讯（新浪财经港股频道 + 东方财富公告）"""
    results = []
    try:
        from curl_cffi import requests as cr
        from datetime import datetime
        session = cr.Session(impersonate="chrome")

        # 方案1：东方财富港股公告（按股票代码精确匹配）
        try:
            ann_resp = session.get(
                "https://np-anotice-stock.eastmoney.com/api/security/ann",
                params={
                    "sr": "-1", "page_size": str(limit // 2 + 1),
                    "page_index": "1", "ann_type": "A",
                    "client_source": "web", "stock_list": symbol.zfill(5)
                },
                timeout=8
            )
            ann_items = ann_resp.json().get("data", {}).get("list", [])
            for n in ann_items:
                title = n.get("title", "").strip()
                if not title:
                    continue
                date = n.get("notice_date", "")[:10]
                score, label = _sentiment_score(title)
                results.append({
                    "时间":  date,
                    "标题":  title,
                    "摘要":  "",
                    "来源":  "东方财富公告",
                    "情绪":  label,
                    "得分":  score,
                    "链接":  f"https://data.eastmoney.com/notices/detail/{symbol.zfill(5)}/{n.get('art_code','')}.html",
                })
        except Exception:
            pass

        # 方案2：新浪财经港股频道资讯（港股市场相关新闻）
        remaining = limit - len(results)
        if remaining > 0:
            resp = session.get(
                "https://feed.mix.sina.com.cn/api/roll/get",
                params={"pageid": "153", "lid": "2516",
                        "k": "港股", "num": str(remaining), "page": "1"},
                timeout=10
            )
            if resp.status_code == 200:
                items = resp.json().get("result", {}).get("data", [])
                for n in items[:remaining]:
                    title = n.get("title", "").strip()
                    if not title:
                        continue
                    url   = n.get("url", "")
                    src_  = n.get("media_name", "")
                    ctime = n.get("ctime", "")
                    try:
                        dt = datetime.fromtimestamp(int(ctime)).strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        dt = str(ctime)[:16]
                    score, label = _sentiment_score(title)
                    results.append({
                        "时间":  dt,
                        "标题":  title,
                        "摘要":  n.get("intro", "")[:120],
                        "来源":  src_ or "新浪财经港股",
                        "情绪":  label,
                        "得分":  score,
                        "链接":  url,
                    })

    except Exception:
        pass

    return results if results else _hk_fallback(symbol)


def fetch_news(symbol: str, limit: int = 10) -> list:
    """统一新闻获取入口"""
    from market_data import detect_market
    market = detect_market(symbol)
    if market == "US":
        return fetch_us_news(symbol, limit)
    elif market == "CN":
        return fetch_cn_news(symbol, limit)
    elif market == "HK":
        return fetch_hk_news(symbol, limit)
    return []


def calc_sentiment_summary(news_list: list) -> dict:
    """计算新闻情绪汇总"""
    if not news_list:
        return {"overall": "中性", "score": 0, "positive": 0, "negative": 0, "neutral": 0}

    scores  = [n["得分"] for n in news_list]
    avg     = sum(scores) / len(scores)
    pos_cnt = sum(1 for s in scores if s > 0)
    neg_cnt = sum(1 for s in scores if s < 0)
    neu_cnt = sum(1 for s in scores if s == 0)

    if avg >= 1:    overall = "积极 📈"
    elif avg >= 0.3: overall = "偏积极 🟢"
    elif avg <= -1:  overall = "消极 📉"
    elif avg <= -0.3: overall = "偏消极 🔴"
    else:            overall = "中性 ⚪"

    return {
        "overall":  overall,
        "score":    round(avg, 2),
        "positive": pos_cnt,
        "negative": neg_cnt,
        "neutral":  neu_cnt,
        "total":    len(news_list),
    }


def _hk_fallback(symbol: str) -> list:
    """港股新闻备用：返回港交所披露易链接"""
    try:
        sym_int = str(int(symbol))
    except Exception:
        sym_int = symbol
    return [{
        "时间":  "",
        "标题":  f"查看 {symbol} 在港交所披露易的所有公告",
        "摘要":  "点击链接可查看该股票在港交所披露易系统中的所有公告文件",
        "来源":  "港交所披露易",
        "情绪":  "中性",
        "得分":  0,
        "链接":  f"https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=zh&category=0&market=SEHK&searchType=1&stockId={sym_int}",
    }]
