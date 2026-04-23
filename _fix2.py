data = open('target_analyzer.py', 'rb').read().decode('utf-8')

# Find and fix the 综合目标 calculation block
old = '    # 综合目标价（基本面方法60% + 技术30% + MC10%）\n    w_fund = 0.60 if fund_vals else 0.0\n    w_tech = 0.30 if fund_vals else 0.60\n    w_mc   = 0.10 if fund_vals else 0.40\n    综合目标 = round(\n        fair_value  * w_fund +\n        tech_fair   * w_tech +\n        mc_fair     * w_mc, 2\n    )'

new = '    w_fund = 0.60 if fund_vals else 0.0\n    w_tech = 0.30 if fund_vals else 0.60\n    w_mc   = 0.10 if fund_vals else 0.40\n    综合目标 = round(\n        fair_value * w_fund +\n        tech_fair  * w_tech +\n        mc_fair    * w_mc, 2\n    )'

# Try CRLF version too
old_crlf = old.replace('\n', '\r\n')
new_crlf = new.replace('\n', '\r\n')

if old in data:
    data = data.replace(old, new, 1)
    print("Fixed LF version")
elif old_crlf in data:
    data = data.replace(old_crlf, new_crlf, 1)
    print("Fixed CRLF version")
else:
    # Just find the block by key phrase
    idx = data.find('综合目标 = round(')
    if idx >= 0:
        print(f"Found 综合目标 at {idx}")
        print(repr(data[idx-200:idx+100]))
    else:
        print("Not found, searching for w_fund")
        idx2 = data.find('w_fund = 0.60')
        print(f"w_fund at {idx2}")
        if idx2 >= 0:
            print(repr(data[idx2-50:idx2+200]))

open('target_analyzer.py', 'w', encoding='utf-8').write(data)
print("Done")
