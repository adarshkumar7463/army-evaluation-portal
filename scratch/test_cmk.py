import re

misspellings = {
    'cmk': 'cmk_sheet',
    'wpn': 'wpn_handling',
    'weapon handling': 'wpn_handling',
    'final exam': 'final_result',
    'final test': 'final_result',
}

q = "top ranker in CMK".lower().strip()
q = re.sub(r'\s+', ' ', q)

for mis, corr in misspellings.items():
    if not mis.isalnum():
        q = q.replace(mis, corr)
    q = re.sub(r'\b' + re.escape(mis) + r'\b', corr, q)

print(f"Processed query: {q}")

standard_tests = [
    'PPT', 'BPET', 'Firing', 'DST', 'MR_III', 'BFC', 'PDP', 'CMK_SHEET', 'WPN_HANDLING', 
    'FINAL_RESULT', 'CS_RESULT', 'CS_CLERK_RESULT', 'CS_ASSESSMENT', 'CLK_FINAL', 
    'CLK_WEEKLY_1', 'CLK_WEEKLY_2', 'CLK_INITIAL', 'OPEM_ASSESSMENT', 'DMV_ASSESSMENT', 
    'OTHER_ASSESSMENT', 'DMV_RESULT', 'OPEM_RESULT', 'OTHER_SCREEN_BOARD'
]

matched_tests = []
for test in standard_tests:
    test_norm = test.lower().replace("_", " ").replace("-", " ")
    q_norm = q.replace("_", " ").replace("-", " ")
    if re.search(r'\b' + re.escape(test_norm) + r'\b', q_norm):
        matched_tests.append(test)

print(f"Matched tests: {matched_tests}")
