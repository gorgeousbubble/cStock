import sys
sys.stdout.reconfigure(encoding='utf-8')

lines = open('app.py', encoding='utf-8').readlines()

# 找到 _peer_rows.append 那段，替换乱码 key
for i, l in enumerate(lines):
    if '_peer_rows.append({' in l and i > 1000:
        # 找到这个块的范围
        block_start = i
        block_end = i
        for j in range(i+1, i+20):
            if '})' in lines[j] or '})\n' in lines[j]:
                block_end = j
                break
        
        print(f"Found peer_rows block: lines {block_start+1} to {block_end+1}")
        for k in range(block_start, block_end+1):
            print(f"  {k+1}: {repr(lines[k].rstrip())}")
        
        # 替换整个块
        indent = '                '
        new_block = [
            indent + '_peer_rows.append({\n',
            indent + '    "股票": f"{_mark}{_p[\'名称\']}({_p[\'代码\']})",\n',
            indent + '    "最新价": _p["最新价"],\n',
            indent + '    "1月涨跌": _p["1月涨跌"],\n',
            indent + '    "3月涨跌": _p["3月涨跌"],\n',
            indent + '    "RSI": _p["RSI"],\n',
            indent + '    "波动率": _p["波动率"],\n',
            indent + '    "趋势评分": _p["趋势评分"],\n',
            indent + '})\n',
        ]
        lines[block_start:block_end+1] = new_block
        print("replaced!")
        break

# 同时修复 _ret_data 里的乱码 key
for i, l in enumerate(lines):
    if '_ret_data[_p[' in l and i > 1000:
        lines[i] = '                    _ret_data[_p["名称"]] = float(_p["1月涨跌"].replace("%","").replace("+",""))\n'
        print(f"fixed _ret_data at line {i+1}")
        break

# 修复 _mark 里的乱码 key
for i, l in enumerate(lines):
    if '_mark = ' in l and '頁倦輝念' in l and i > 1000:
        lines[i] = '                _mark = "[当前] " if _p["是否当前"] else ""\n'
        print(f"fixed _mark at line {i+1}")
        break

open('app.py', 'w', encoding='utf-8').writelines(lines)
import ast; ast.parse(open('app.py', encoding='utf-8').read())
print("syntax OK")
