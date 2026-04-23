with open('app.py', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")
print(f"Line 489: {repr(lines[488].rstrip())}")
print(f"Line 490: {repr(lines[489].rstrip())}")
print(f"Line 491: {repr(lines[490].rstrip())}")

# 在第490行（index 489，空行）后插入
insert_pos = 490  # 0-indexed，即第491行前
lines.insert(insert_pos, '        wave_result = result.get("wave", {})\n')
lines.insert(insert_pos, '    if _ext_module == "\U0001f30a 波浪理论":\n')

print(f"\nAfter insert:")
for i in range(488, 498):
    print(f"  {i+1}: {repr(lines[i].rstrip())}")

with open('app.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

import ast
try:
    ast.parse(open('app.py', encoding='utf-8').read())
    print("syntax OK")
except SyntaxError as e:
    print(f"SyntaxError at line {e.lineno}: {e.msg}")
