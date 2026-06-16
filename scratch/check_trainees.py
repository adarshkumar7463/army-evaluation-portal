import os
import sys
import django

sys.path.append(r'c:\Users\krada\Desktop\Evaluation-portal')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'army_portal.settings')
django.setup()

from evaluation.models import Agniveer, EvaluationSheet
from evaluation.views import AgniveerReportCardView
from django.test import RequestFactory
from django.contrib.auth import get_user_model

v = Agniveer.objects.get(pk=444)
print(f"Evaluations in DB for {v.get_full_name()}:")
evals = EvaluationSheet.objects.filter(agniveer=v)
for e in evals:
    print(f"  {e.test_type} ({e.department}): total={e.get_total_marks()}, max={e.get_max_marks()}, category={e.category}")

print("\nRunning AgniveerReportCardView.get to see scoped evaluations:")
u = User = get_user_model().objects.filter(role='commander').first()
rf = RequestFactory()
req = rf.get(f'/evaluation/report-card/{v.pk}/')
req.user = u

context = {}
def mock_render(request, template, ctx):
    global context
    context = ctx
    return None

import evaluation.views
evaluation.views.render = mock_render

view = AgniveerReportCardView()
view.request = req
view.get(req, v.pk)

print(f"\nContext grand_total={context.get('grand_total')}, max_total={context.get('max_total')}")
print("Scoped evaluations in view context:")
for dept, data in context.get('dept_evaluations', {}).items():
    print(f"Dept {dept}:")
    for s in data.get('on_field', []):
        print(f"  on_field: {s.test_type} total={s.get_total_marks()}, max={s.get_max_marks()}")
    for s in data.get('trade', []):
        print(f"  trade: {s.test_type} total={s.get_total_marks()}, max={s.get_max_marks()}")
