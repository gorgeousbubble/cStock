import sys
sys.stdout.reconfigure(encoding='utf-8')

src = open('app.py', encoding='utf-8').read()

# ── 1. 各分析模块改为可折叠 expander ─────────────────────
modules = [
    ('    st.subheader("🕯️ K线形态识别")',          '    with st.expander("🕯️ K线形态识别", expanded=False):'),
    ('    st.subheader("📊 量价分析")',               '    with st.expander("📊 量价分析", expanded=False):'),
    ('    st.subheader("🧠 量化策略分析")',            '    with st.expander("🧠 量化策略分析", expanded=False):'),
    ('    st.subheader("🏦 基本面分析")',              '    with st.expander("🏦 基本面分析", expanded=False):'),
    ('    st.subheader("🌊 Elliott 波浪理论自动识别")', '    with st.expander("🌊 Elliott 波浪理论自动识别", expanded=False):'),
    ('    st.subheader("🔮 AI 走势预测")',             '    with st.expander("🔮 AI 走势预测", expanded=True):'),
    ('    st.subheader("💹 买入价格与仓位控制")',       '    with st.expander("💹 买入价格与仓位控制", expanded=True):'),
    ('    st.subheader("📈 累计收益率走势")',           '    with st.expander("📈 累计收益率走势", expanded=False):'),
]

fixed = 0
for old, new in modules:
    if old in src:
        src = src.replace(old, new)
        fixed += 1

print(f"replaced {fixed} subheaders with expanders")

# ── 2. 全局 CSS 美化 ──────────────────────────────────────
css_code = '''
    # 全局CSS美化
    st.markdown("""
<style>
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
div[data-testid="stExpander"] summary {
    font-size: 1.05rem;
    font-weight: 600;
}
hr { border-color: rgba(255,255,255,0.08) !important; }
section[data-testid="stSidebar"] > div {
    background: rgba(10,10,20,0.98);
}
</style>
""", unsafe_allow_html=True)
'''

# 在 show_detail 里 st.divider() 后插入 CSS（只插一次）
if '全局CSS美化' not in src:
    src = src.replace(
        '    st.markdown(f"# {name}({sym})")\n',
        '    st.markdown(f"# {name}({sym})")\n' + css_code + '\n'
    )
    print("inserted CSS")

# ── 3. 侧边栏总资金标签改为更简洁 ────────────────────────
src = src.replace(
    'st.number_input("💰 总资金 (USD)"',
    'st.number_input("💰 总资金"'
)

# ── 4. 实时分析页面标题优化 ──────────────────────────────
src = src.replace(
    'st.markdown(f"**最后更新：{now_str}**　　下次刷新：{refresh_sec}秒后")',
    'st.info(f"🕐 最后更新：{now_str}　　⏱️ 下次刷新：{refresh_sec}秒后")'
)

open('app.py', 'w', encoding='utf-8').write(src)

import ast
ast.parse(src)
print("syntax OK")
