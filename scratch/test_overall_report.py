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

# Trainee 526 (Vikas Sharma, OPEM) and Trainee 447 (DMV)
trainees = [526, 447]
u = get_user_model().objects.filter(role='commander').first()
rf = RequestFactory()

for t_id in trainees:
    v = Agniveer.objects.get(pk=t_id)
    print(f"================= Report Card for {v.get_full_name()} ({v.trade}) =================")
    
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
    
    print(f"Overall View: grand_total={context.get('grand_total')}, max_total={context.get('max_total')}, percentage={context.get('percentage')}%")
    for d, res in context.get('all_dept_results', {}).items():
        print(f"  Dept {d}: grand_total={res.get('grand_total')}, max_total={res.get('max_total')}, grading={res.get('grading')}")
