import os
import sys
import django

# Add project root to python path
sys.path.append(r'c:\Users\krada\Desktop\Evaluation-portal')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'army_portal.settings')
django.setup()

from evaluation.models import Agniveer, EvaluationSheet
from evaluation.result_helpers import build_department_result_row, is_sheet_evaluated

def verify():
    print("=== VERIFYING TRAINEE TOTALS & PASS STATUS ===")
    
    # Get trainees with evaluations
    trainees = Agniveer.objects.filter(evaluations__isnull=False).distinct()
    
    for t in trainees[:15]:
        evaluations = list(EvaluationSheet.objects.filter(agniveer=t).prefetch_related('marks'))
        
        # Calculate manually via helper
        total_helper = 0.0
        max_helper = 0.0
        depts_eval = []
        for d in ['A', 'B', 'C', 'D']:
            d_sheets = [s for s in evaluations if s.department == d]
            if d_sheets and any(is_sheet_evaluated(s) for s in d_sheets):
                d_row = build_department_result_row(t, d_sheets, d)
                total_helper += float(d_row.get('grand_total', 0.0) or 0.0)
                max_helper += float(d_row.get('max_total') or (120 if d == 'A' else 40))
                depts_eval.append(d)
                
        model_total = t.get_total_score()
        model_pass = t.get_pass_status()
        
        pct_helper = (total_helper / max_helper * 100) if max_helper > 0 else 0
        passing_threshold = 40 if depts_eval == ['A'] else 50
        expected_pass = 'Pass' if pct_helper >= passing_threshold else 'Fail'
        if max_helper == 0:
            expected_pass = 'Pending'
            
        print(f"Trainee ID {t.pk}: {t.get_full_name()} ({t.trade})")
        print(f"  Evaluated Depts: {depts_eval}")
        print(f"  Helper Score: {total_helper:.2f} / {max_helper:.2f} ({pct_helper:.1f}%) -> {expected_pass}")
        print(f"  Model Score: {model_total:.2f} -> {model_pass}")
        
        # Asset equality
        assert abs(model_total - total_helper) < 1e-5, f"Mismatch in total score! {model_total} vs {total_helper}"
        assert model_pass == expected_pass, f"Mismatch in pass status! {model_pass} vs {expected_pass}"
        print("  => OK")
        
    print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    verify()
