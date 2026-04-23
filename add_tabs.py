import sys
sys.stdout.reconfigure(encoding='utf-8')

lines = open('app.py', encoding='utf-8').readlines()

# 找到波浪理论 subheader 行号（第400行）
# 找到 show_summary 函数定义行（show_detail 结束）
show_summary_line = None
for i, l in enumerate(lines):
    if 'def show_summary(results: list):' in l:
        show_summary_line = i
        break

print(f"show_summary at line {show_summary_line+1}")

# 找到波浪理论 subheader（第一个在 show_detail 里的大模块）
wave_line = None
for i, l in enumerate(lines):
    if i > 100 and i < show_summary_line and 'Elliott' in l and 'subheader' in l:
        wave_line = i
        break

print(f"wave subheader at line {wave_line+1}")

# 在波浪理论前插入 tabs 开始
# 在 show_summary 前插入 tabs 结束（不需要，tabs 自动管理）

# 策略：在波浪理论 subheader 前插入 tab 容器
# 把后续所有模块放进对应 tab
# 由于不能改缩进，用 st.container() 包裹每个 tab 内容

tab_insert = [
    '\n',
    '    st.divider()\n',
    '    # ── 扩展分析 Tabs ──────────────────────────────────────\n',
    '    _tab_names = ["🌊 波浪理论", "🕯️ K线形态", "📊 量价分析", "🧠 量化策略", "🏦 基本面", "🌐 宏观经济", "🏭 行业对比", "📰 新闻舆情", "📝 综合总结"]\n',
    '    _tabs = st.tabs(_tab_names)\n',
    '\n',
    '    # Tab 0: 波浪理论\n',
    '    with _tabs[0]:\n',
]

lines[wave_line:wave_line] = tab_insert
print(f"inserted tabs at line {wave_line+1}")

# 重新找各模块位置（行号已偏移）
open('app.py', 'w', encoding='utf-8').writelines(lines)

# 重新读取并找各模块
lines = open('app.py', encoding='utf-8').readlines()

# 找各模块并在前面加 with _tabs[N]:
module_markers = [
    ('K线形态识别', 1),
    ('量价分析', 2),
    ('量化策略分析', 3),
    ('基本面分析', 4),
    ('宏观经济环境', 5),
    ('行业横向对比', 6),
    ('新闻舆情分析', 7),
    ('综合分析总结', 8),
]

show_summary_line = None
for i, l in enumerate(lines):
    if 'def show_summary(results: list):' in l:
        show_summary_line = i
        break

offset = 0
for marker, tab_idx in module_markers:
    for i, l in enumerate(lines):
        if i > 100 and i < show_summary_line and marker in l and 'subheader' in l:
            # 找到前面的 st.divider()
            div_line = i
            for j in range(i-1, max(0, i-5), -1):
                if 'st.divider()' in lines[j]:
                    div_line = j
                    break
            # 在 divider 前插入 with _tabs[N]:
            insert = [f'    with _tabs[{tab_idx}]:\n']
            lines[div_line:div_line] = insert
            print(f"Tab {tab_idx} ({marker}) at line {div_line+1}")
            break

open('app.py', 'w', encoding='utf-8').writelines(lines)

import ast
ast.parse(open('app.py', encoding='utf-8').read())
print("syntax OK")
