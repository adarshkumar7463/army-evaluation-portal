import os
for root, dirs, files in os.walk(r'c:\Users\krada\Desktop\Evaluation-portal'):
    if 'venv' in root:
        continue
    for file in files:
        if file.endswith('.html'):
            print(os.path.join(root, file))
