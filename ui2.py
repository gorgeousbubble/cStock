import sys, re
sys.stdout.reconfigure(encoding='utf-8')

src = open('app.py', encoding='utf-8').read()

# ── 1. 全局 CSS 美化（只加一次）─────────────────────────
css = '''    st.markdown("""<style>
div[data-testid="metric-container"] {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px;
    padding: 10px 14px;
}
div[data-testid="stExpander"] {
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 10px;
    margin-bottom: 6px;
}
div[data-testid="stExpander"] summary p {
    font-size: 1.05rem !important;
    font-weight: 600 !important;
}
hr { border-color: rgba(255,255,255,0.08) !important; }
</style>""", unsafe_allow_html=True)
'''

if 'metric-container' not in src:
    src = src.replace(
        '    st.markdown(f"# {name}({sym})")\n',
        '    st.markdown(f"# {name}({sym})")\n' + css + '\n'
    )
    print("CSS inserted")

# ── 2. 把深度分析各模块用 st.expander 包裹 ───────────────
# 策略：在每个 st.subheader 前加 expander 开始，在下一个 st.subheader/st.divider 前结束
# 用 Tab 把内容分组：核心分析 | 技术形态 | 量化策略 | 基本面

# 找到 show_detail 里 st.divider() 后的第一个 st.subheader（综合分析建议那行）
# 在最后的波浪理论之前，把后续模块用 tabs 包裹

# 找到波浪理论 subheader 位置
wave_marker = '    st.subheader("🌊 Elliott 波浪理论自动识别")'
pattern_marker = '    st.subheader("🕯️ K线形态识别")'
volume_marker = '    st.subheader("📊 量价分析")'
quant_marker = '    st.subheader("🧠 量化策略分析")'
fund_marker = '    st.subheader("🏦 基本面分析")'

# 在波浪理论前插入 tab 开始
tab_start = '''
    st.divider()
    # ── 扩展分析 Tabs ──────────────────────────────────────
    _tab_wave, _tab_pattern, _tab_volume, _tab_quant, _tab_fund = st.tabs([
        "🌊 波浪理论", "🕯️ K线形态", "📊 量价分析", "🧠 量化策略", "🏦 基本面"
    ])
'''

# 替换各模块 subheader 为 tab with 块
replacements = [
    (wave_marker,    '\n    with _tab_wave:'),
    (pattern_marker, '\n    with _tab_pattern:'),
    (volume_marker,  '\n    with _tab_volume:'),
    (quant_marker,   '\n    with _tab_quant:'),
    (fund_marker,    '\n    with _tab_fund:'),
]

# 先插入 tab_start（在波浪理论 subheader 前）
if '_tab_wave' not in src:
    src = src.replace(
        '    st.divider()\n\n    # ── 波浪理论',
        tab_start + '\n    # ── 波浪理论'
    )
    # 如果上面没匹配到，尝试另一种格式
    if '_tab_wave' not in src:
        src = src.replace(
            '    st.divider()\n\n    st.subheader("🌊 Elliott',
            tab_start + '\n    st.subheader("🌊 Elliott'
        )
    print("tab_start inserted:", '_tab_wave' in src)

    for old, new in replacements:
        if old in src:
            src = src.replace(old, new)
            print(f"replaced: {old[:35]}")

# ── 3. 实时分析页面更新时间改为更美观 ────────────────────
src = src.replace(
    'st.info(f"🕐 最后更新：{now_str}　　⏱️ 下次刷新：{refresh_sec}秒后")',
    'st.markdown(f"**🕐 最后更新：** `{now_str}`　　**⏱️ 下次刷新：** `{refresh_sec}秒后`")'
)
# 如果还是旧格式
src = src.replace(
    'st.markdown(f"**最后更新：{now_str}**　　下次刷新：{refresh_sec}秒后")',
    'st.markdown(f"**🕐 最后更新：** `{now_str}`　　**⏱️ 下次刷新：** `{refresh_sec}秒后`")'
)

# ── 4. 侧边栏总资金标签简化 ──────────────────────────────
src = src.replace('st.number_input("💰 总资金 (USD)"', 'st.number_input("💰 总资金"')

open('app.py', 'w', encoding='utf-8').write(src)
import ast; ast.parse(src); print("syntax OK")
