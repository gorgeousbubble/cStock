lines = open('app.py', encoding='utf-8').readlines()

for i, l in enumerate(lines):

    # 1. 汇总表 "股票": r["symbol"]
    if '"股票": r["symbol"]' in l:
        lines[i] = l.replace(
            '"股票": r["symbol"]',
            '"股票": f\"{r.get(\'name\', r[\'symbol\'])}({r[\'symbol\']})\""'
        )
        print(f"fixed summary table at line {i+1}")

    # 2. 实时报价卡片 - 预警高亮
    if 'st.warning(f"**{color} {q[\'symbol\']}**' in l:
        lines[i] = l.replace(
            'st.warning(f"**{color} {q[\'symbol\']}**  ⚠️ 预警")',
            'st.warning(f"**{color} {q.get(\'name\', q[\'symbol\'])}({q[\'symbol\']})** ⚠️ 预警")'
        )
        print(f"fixed warning card at line {i+1}")

    # 3. 实时报价卡片 - 正常显示
    if 'st.markdown(f"**{color} {q[\'symbol\']}**")' in l:
        lines[i] = l.replace(
            'st.markdown(f"**{color} {q[\'symbol\']}**")',
            'st.markdown(f"**{color} {q.get(\'name\', q[\'symbol\'])}({q[\'symbol\']})**")'
        )
        print(f"fixed normal card at line {i+1}")

    # 4. 技术指标扫描表 "股票": q["symbol"]
    if '"股票": q["symbol"]' in l:
        lines[i] = l.replace(
            '"股票": q["symbol"]',
            '"股票": f\"{q.get(\'name\', q[\'symbol\'])}({q[\'symbol\']})\""'
        )
        print(f"fixed scan table at line {i+1}")

open('app.py', 'w', encoding='utf-8').writelines(lines)
import ast; ast.parse(open('app.py', encoding='utf-8').read())
print("syntax OK")
