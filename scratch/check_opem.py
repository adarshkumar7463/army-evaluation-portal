import os
import sys
import django

sys.path.append(r'c:\Users\krada\Desktop\Evaluation-portal')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'army_portal.settings')
django.setup()

from evaluation.models import Agniveer, EvaluationSheet
from evaluation.result_helpers import build_tts_result_row

trainees = [447, 448, 511, 512, 525, 526]
for t_id in trainees:
    try:
        v = Agniveer.objects.get(pk=t_id)
        print(f"================= Trainee {v.pk} - {v.get_full_name()} ({v.trade}) =================")
        evals = EvaluationSheet.objects.filter(agniveer=v)
        for e in evals:
            print(f"  {e.test_type}: total={e.get_total_marks()}, max={e.get_max_marks()}, results={e.sub_event_results}")
        row = build_tts_result_row(v, list(evals))
        print("  TTS Row:", row)
    except Agniveer.DoesNotExist:
        pass
