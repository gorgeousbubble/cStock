import sys
sys.stdout.reconfigure(encoding='utf-8')

src = open('app.py', encoding='utf-8').read()

# 把各分析模块的 st.subheader 改为 st.expander
# 这样不展开就不渲染内容，大幅减少初始渲染时间

# 注意：st.expander 内的内容需要缩进，但我们不改缩进
# 改用另一种方式：在 subheader 前加一个 expander 开关
# 用 st.session_state 记录展开状态

# 最简单可靠的方式：把各模块的 st.subheader 改为带折叠的标题
# 用 st.markdown + details/summary HTML 实现折叠

# 实际上最简单的是：把各模块改为 st.expander
# 但需要内容缩进，所以改用另一种方式：
# 在每个模块前加 if st.checkbox("显示xxx", value=True, key=f"show_xxx_{_uid}"):
# 这样用户可以选择显示/隐藏，且不影响缩进

replacements = [
    # 波浪理论
    ('    st.subheader("🌊 Elliott 波浪理论自动识别")',
     '    _show_wave = st.checkbox("🌊 Elliott 波浪理论", value=True, key=f"show_wave_{_uid}")\n    if _show_wave:'),
    # K线形态
    ('    st.subheader("🕯️ K线形态识别")',
     '    _show_pattern = st.checkbox("🕯️ K线形态识别", value=False, key=f"show_pattern_{_uid}")\n    if _show_pattern:'),
    # 量价分析
    ('    st.subheader("📊 量价分析")',
     '    _show_volume = st.checkbox("📊 量价分析", value=False, key=f"show_volume_{_uid}")\n    if _show_volume:'),
    # 量化策略
    ('    st.subheader("🧠 量化策略分析")',
     '    _show_quant = st.checkbox("🧠 量化策略分析", value=False, key=f"show_quant_{_uid}")\n    if _show_quant:'),
    # 基本面
    ('    st.subheader("🏦 基本面分析")',
     '    _show_fund = st.checkbox("🏦 基本面分析", value=False, key=f"show_fund_{_uid}")\n    if _show_fund:'),
    # 宏观经济
    ('    st.subheader("🌐 宏观经济环境")',
     '    _show_macro = st.checkbox("🌐 宏观经济环境", value=False, key=f"show_macro_{_uid}")\n    if _show_macro:'),
    # 行业对比
    ('    st.subheader("🏭 行业横向对比")',
     '    _show_industry = st.checkbox("🏭 行业横向对比", value=False, key=f"show_industry_{_uid}")\n    if _show_industry:'),
    # 新闻舆情
    ('    st.subheader("📰 新闻舆情分析")',
     '    _show_news = st.checkbox("📰 新闻舆情分析", value=False, key=f"show_news_{_uid}")\n    if _show_news:'),
    # 综合总结
    ('    st.subheader("📝 综合分析总结")',
     '    _show_summary = st.checkbox("📝 综合分析总结", value=True, key=f"show_summary_{_uid}")\n    if _show_summary:'),
]

fixed = 0
for old, new in replacements:
    if old in src:
        src = src.replace(old, new)
        fixed += 1
        print(f"Fixed: {old[:40]}")
    else:
        print(f"NOT FOUND: {old[:40]}")

open('app.py', 'w', encoding='utf-8').write(src)
import ast; ast.parse(src)
print(f"\nFixed {fixed} subheaders, syntax OK")
