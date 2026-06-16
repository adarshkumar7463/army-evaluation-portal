with open(r'C:\Users\krada\Desktop\Evaluation-portal\reports\views.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines, 1):
    if 'get_total_marks' in line:
        print(f"Line {i}: {line.strip()}")
    elif 'get_max_marks' in line:
        print(f"Line {i}: {line.strip()}")
