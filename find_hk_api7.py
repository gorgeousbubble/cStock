from curl_cffi import requests as cr
import json

s = cr.Session(impersonate='chrome')

# 同花顺已知的个股新闻接口格式（A股用 600519 测试，找到后换 HK00700）
test_cases = [
    # 格式1: /tapp/news/push/stock/
    ('https://news.10jqka.com.cn/tapp/news/push/stock/', {'page':'1','pagesize':'3','code':'600519'}),
    # 格式2: 带 hexin-v header
    ('https://news.10jqka.com.cn/tapp/news/push/stock/', {'page':'1','pagesize':'3','code':'HK00700'}),
    # 格式3: 不同域名
    ('https://news.10jqka.com.cn/api/info/stock/HK00700/news/1/3', {}),
    # 格式4: 港股专用路径
    ('https://news.10jqka.com.cn/hkstock/news/HK00700/1/3', {}),
    ('https://news.10jqka.com.cn/hkstock/HK00700/news/1/3', {}),
    # 格式5: 带 market 参数
    ('https://news.10jqka.com.cn/tapp/news/push/stock/', {'page':'1','pagesize':'3','code':'00700','market':'hk'}),
    ('https://news.10jqka.com.cn/tapp/news/push/stock/', {'page':'1','pagesize':'3','code':'00700','market':'HK'}),
    # 格式6: 不同 code 格式
    ('https://news.10jqka.com.cn/tapp/news/push/stock/', {'page':'1','pagesize':'3','code':'0700'}),
    ('https://news.10jqka.com.cn/tapp/news/push/stock/', {'page':'1','pagesize':'3','code':'700'}),
    # 格式7: 带 hexin-v cookie（同花顺需要登录的接口）
]

for url, params in test_cases:
    try:
        r = s.get(url, params=params, timeout=8)
        try:
            d = r.json()
            items = d.get('data', {}).get('list', []) if isinstance(d.get('data'), dict) else []
            if items:
                first = items[0]
                stock_field = first.get('stocks', first.get('stock', first.get('stockList', '')))
                print(f"✅ {url[-40:]} params={params}")
                print(f"   count={len(items)}, title={first.get('title','')[:40]}")
                print(f"   stocks={stock_field}")
            else:
                print(f"❌ {url[-40:]} params={params} -> empty, code={d.get('code','')}")
        except:
            print(f"❌ {url[-40:]} params={params} -> status={r.status_code}, not JSON")
    except Exception as e:
        print(f"❌ {url[-40:]} ERROR: {str(e)[:50]}")
