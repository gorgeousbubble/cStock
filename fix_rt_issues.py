lines = open('app.py', encoding='utf-8').readlines()

# 1. 在市场切换检测代码里加入清除 rt_history
for i, l in enumerate(lines):
    if 'keys_to_del = [k for k in st.session_state.keys()' in l:
        # 找到下面的 st.rerun() 行，在前面加清除 rt_history
        for j in range(i, i+5):
            if 'st.session_state.last_market = market' in lines[j] and j > i:
                indent = len(lines[j]) - len(lines[j].lstrip())
                sp = ' ' * indent
                lines.insert(j, sp + 'st.session_state.rt_history = {}\n')
                lines.insert(j+1, sp + 'st.session_state.rt_alerts = []\n')
                print(f"added rt_history clear at line {j+1}")
                break
        break

# 2. 修复实时报价卡片的货币符号
# 找到 page_realtime 里的 value=f"${q['price']}" 
in_rt = False
for i, l in enumerate(lines):
    if 'def page_realtime(' in l:
        in_rt = True
    elif in_rt and l.startswith('def ') and 'page_realtime' not in l:
        in_rt = False
    if in_rt and 'value=f"${q[\'price\']}"' in l:
        indent = len(l) - len(l.lstrip())
        sp = ' ' * indent
        # 在前面加货币符号定义
        lines.insert(i, sp + 'from market_data import detect_market as _dm_rt\n')
        lines.insert(i+1, sp + '_rt_cur = {"CN": "¥", "HK": "HK$", "US": "$"}.get(_dm_rt(q["symbol"]), "$")\n')
        # 更新 value 行
        lines[i+2] = lines[i+2].replace('value=f"${q[\'price\']}"', 'value=f"{_rt_cur}{q[\'price\']}"')
        print(f"fixed rt price currency at line {i+1}")
        break

open('app.py', 'w', encoding='utf-8').writelines(lines)
import ast; ast.parse(open('app.py', encoding='utf-8').read())
print("syntax OK")
