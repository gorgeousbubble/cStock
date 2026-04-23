import sys
sys.stdout.reconfigure(encoding='utf-8')

lines = open('app.py', encoding='utf-8').readlines()

# 1. 加 import
for i, l in enumerate(lines):
    if 'from option_analyzer import' in l:
        lines.insert(i+1, 'from ipo_analyzer import fetch_cn_ipo_list, fetch_hk_ipo_list, fetch_cn_ipo_info, fetch_cn_new_stock_stats, fetch_cn_ipo_calendar, ipo_advice\n')
        print(f"added ipo import at line {i+2}")
        break

# 2. 加 load_ipo 缓存函数
for i, l in enumerate(lines):
    if 'def load_option(symbol):' in l:
        for j in range(i, i+5):
            if 'return fetch_option_data' in lines[j]:
                insert = [
                    '\n',
                    '\n@st.cache_data(ttl=3600, show_spinner=False)\n',
                    'def load_ipo_cn():\n',
                    '    return fetch_cn_ipo_list(30), fetch_cn_new_stock_stats(), fetch_cn_ipo_calendar(20)\n',
                    '\n',
                    '\n@st.cache_data(ttl=3600, show_spinner=False)\n',
                    'def load_ipo_hk():\n',
                    '    return fetch_hk_ipo_list(30)\n',
                ]
                lines[j+1:j+1] = insert
                print(f"added load_ipo at line {j+2}")
                break
        break

# 3. 在导航里加入新股分析
for i, l in enumerate(lines):
    if 'page = st.sidebar.radio' in l and '实时分析' in l and '深度分析' in l:
        lines[i] = lines[i].replace(
            '[\"⚡ 实时分析\", \"🔬 深度分析\"]',
            '[\"⚡ 实时分析\", \"🔬 深度分析\", \"🆕 新股分析\"]'
        )
        print(f"added IPO nav at line {i+1}")
        break

# 4. 在 main() 里加入新股分析页面路由
for i, l in enumerate(lines):
    if 'page_analysis(market)' in l and i > 1200:
        indent = len(l) - len(l.lstrip())
        sp = ' ' * indent
        lines.insert(i+1, sp + 'elif page == "🆕 新股分析":\n')
        lines.insert(i+2, sp + '    page_ipo(market)\n')
        print(f"added IPO route at line {i+2}")
        break

# 5. 在 main() 前加入 page_ipo 函数
for i, l in enumerate(lines):
    if 'def main():' in l and i > 1200:
        ipo_page = [
            '\n',
            '\n# ══════════════════════════════════════════════════════════\n',
            '# 新股分析页面\n',
            '# ══════════════════════════════════════════════════════════\n',
            'def page_ipo(market: str = "🇨🇳 A股"):\n',
            '    market_label = {"🇺🇸 美股": "美股", "🇨🇳 A股": "A股", "🇭🇰 港股": "港股"}.get(market, "A股")\n',
            '    st.header(f"🆕 {market_label} 新股分析")\n',
            '\n',
            '    if market == "🇺🇸 美股":\n',
            '        st.info("美股新股数据暂不支持，请切换到 A股 或 港股")\n',
            '        return\n',
            '\n',
            '    with st.spinner("正在获取新股数据..."):\n',
            '        if market == "🇨🇳 A股":\n',
            '            _ipo_list, _stats, _calendar = load_ipo_cn()\n',
            '        else:\n',
            '            _ipo_list = load_ipo_hk()\n',
            '            _stats, _calendar = {}, pd.DataFrame()\n',
            '\n',
            '    # ── 打新统计 ──────────────────────────────────────────\n',
            '    if _stats and market == "🇨🇳 A股":\n',
            '        st.subheader("📊 近期打新统计")\n',
            '        c1, c2, c3, c4 = st.columns(4)\n',
            '        c1.metric("统计新股数", f"{_stats.get(\'total\', 0)} 只")\n',
            '        c2.metric("平均首日涨幅", f"{_stats.get(\'avg_gain\', 0)}%")\n',
            '        c3.metric("最高首日涨幅", f"{_stats.get(\'max_gain\', 0)}%")\n',
            '        c4.metric("破发率", f"{_stats.get(\'break_rate\', 0)}%",\n',
            '                  delta="偏高" if _stats.get("break_rate", 0) > 20 else "正常",\n',
            '                  delta_color="inverse" if _stats.get("break_rate", 0) > 20 else "off")\n',
            '\n',
            '    # ── 新股申购日历 ──────────────────────────────────────\n',
            '    if market == "🇨🇳 A股" and not _calendar.empty:\n',
            '        st.subheader("📅 新股申购日历")\n',
            '        st.dataframe(_calendar, hide_index=True, use_container_width=True)\n',
            '\n',
            '    # ── 近期新股列表 ──────────────────────────────────────\n',
            '    st.subheader(f"📋 近期{market_label}新股列表")\n',
            '    if not _ipo_list.empty:\n',
            '        st.dataframe(_ipo_list, hide_index=True, use_container_width=True)\n',
            '    else:\n',
            '        st.info("暂无新股数据")\n',
            '\n',
            '    # ── 单只新股详情（仅A股）────────────────────────────\n',
            '    if market == "🇨🇳 A股":\n',
            '        st.divider()\n',
            '        st.subheader("🔍 单只新股详情查询")\n',
            '        _ipo_code = st.text_input("输入新股代码（如 688981）", key="ipo_code")\n',
            '        if _ipo_code:\n',
            '            with st.spinner(f"正在查询 {_ipo_code}..."):\n',
            '                _info = fetch_cn_ipo_info(_ipo_code)\n',
            '            if _info:\n',
            '                col_i1, col_i2 = st.columns(2)\n',
            '                with col_i1:\n',
            '                    st.markdown("**📄 发行信息**")\n',
            '                    for k, v in list(_info.items())[:8]:\n',
            '                        st.markdown(f"- **{k}**：{v}")\n',
            '                with col_i2:\n',
            '                    st.markdown("**📄 募资信息**")\n',
            '                    for k, v in list(_info.items())[8:]:\n',
            '                        st.markdown(f"- **{k}**：{v}")\n',
            '                st.divider()\n',
            '                st.markdown("**💡 申购建议**")\n',
            '                _advice = ipo_advice(_info, _stats)\n',
            '                for a in _advice:\n',
            '                    st.markdown(f"- {a}")\n',
            '            else:\n',
            '                st.warning(f"未找到 {_ipo_code} 的新股信息")\n',
            '\n',
        ]
        lines[i:i] = ipo_page
        print(f"added page_ipo at line {i+1}")
        break

open('app.py', 'w', encoding='utf-8').writelines(lines)
import ast; ast.parse(open('app.py', encoding='utf-8').read())
print("syntax OK")
