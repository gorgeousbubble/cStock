lines = open('app.py', encoding='utf-8').readlines()

# 1. 在 page_realtime 里，quotes 获取后只保留当前 symbols 的数据
# 找到 quotes = fetch_... 那行
for i, l in enumerate(lines):
    if i > 950 and ('quotes = fetch_cn_realtime' in l or
                    'quotes = fetch_hk_realtime' in l or
                    'quotes = fetch_realtime_quotes' in l):
        # 找到 except 块结束后，插入过滤代码
        # 找到 return 后的第一个非空行
        for j in range(i+1, i+10):
            if 'return' in lines[j] and 'st.error' in lines[j-1]:
                indent = len(lines[j+1]) - len(lines[j+1].lstrip())
                sp = ' ' * indent
                # 在 return 后插入：过滤 quotes 只保留当前 symbols
                filter_code = [
                    '\n',
                    sp + '# 只保留当前 symbols 的报价，清除其他市场残留\n',
                    sp + 'quotes = [q for q in quotes if q.get("symbol") in symbols]\n',
                    sp + '# 货币符号\n',
                    sp + '_rt_cur = {"🇨🇳 A股": "¥", "🇭🇰 港股": "HK$"}.get(market, "$")\n',
                ]
                lines[j+1:j+1] = filter_code
                print(f"inserted filter at line {j+2}")
                break
        break

# 2. 修复报价卡片的货币符号 value=f"${q['price']}"
in_rt = False
for i, l in enumerate(lines):
    if 'def page_realtime(' in l:
        in_rt = True
    elif in_rt and l.startswith('def ') and 'page_realtime' not in l:
        in_rt = False
    if in_rt and "value=f\"${q['price']}\"" in l:
        lines[i] = l.replace("value=f\"${q['price']}\"", "value=f\"{_rt_cur}{q['price']}\"")
        print(f"fixed price currency at line {i+1}")
        break

open('app.py', 'w', encoding='utf-8').writelines(lines)
import ast; ast.parse(open('app.py', encoding='utf-8').read())
print("syntax OK")
