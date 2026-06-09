"""
Evaluation App - Views
Complete evaluation workflow with marks entry and locking
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView, DetailView
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.http import JsonResponse, HttpResponseForbidden
from django.urls import reverse_lazy
from datetime import date

from .models import EvaluationSheet, Marks
from .result_helpers import build_department_result_row
from .forms import EvaluationSheetForm, MarksForm, EvaluationFilterForm, AgniveerEvaluationForm, SubEventEvaluationForm
from departments.models import Agniveer
from accounts.mixins import AnyStaffMixin, CommanderOrDeptMixin, TrainerMixin
from logs.utils import log_action


CLERK_TRADES = ['CLK', 'CLERK', 'Clerk', 'CLK_SD', 'CLK_IM']


class EvaluationListView(AnyStaffMixin, ListView):
    model = EvaluationSheet
    template_name = 'evaluation/evaluation_list.html'
    context_object_name = 'evaluations'
    paginate_by = 20

    def get(self, request, *args, **kwargs):
        if request.user.is_trainer:
            return redirect('core:dashboard')
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        queryset = EvaluationSheet.objects.select_related(
            'agniveer', 'created_by'
        ).prefetch_related('marks')

        if user.is_department:
            queryset = queryset.filter(department=user.get_department_code())

        # Filters
        dept = self.request.GET.get('department')
        category = self.request.GET.get('category')
        test_type = self.request.GET.get('test_type')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        search = self.request.GET.get('search')
        locked = self.request.GET.get('locked')

        if dept and (user.is_commander or user.is_g_head):
            queryset = queryset.filter(department=dept)
        if category:
            queryset = queryset.filter(category=category)
        if test_type:
            queryset = queryset.filter(test_type=test_type)
        if date_from:
            queryset = queryset.filter(evaluation_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(evaluation_date__lte=date_to)
        if search:
            queryset = queryset.filter(
                Q(agniveer__enrollment_number__icontains=search) |
                Q(agniveer__first_name__icontains=search) |
                Q(agniveer__last_name__icontains=search)
            )
        if locked == '1':
            queryset = queryset.filter(is_locked=True)
        elif locked == '0':
            queryset = queryset.filter(is_locked=False)

        return queryset.order_by('-evaluation_date')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = EvaluationFilterForm(self.request.GET)
        ctx['category_choices'] = EvaluationSheet.CATEGORY_CHOICES
        ctx['test_type_choices'] = EvaluationSheet.TEST_TYPE_CHOICES
        
        # Group evaluations by department
        from collections import defaultdict
        dept_evaluations = defaultdict(list)
        for ev in ctx['evaluations']:
            dept_evaluations[ev.department].append(ev)
        
        # Sort departments
        ctx['grouped_evaluations'] = {dept: dept_evaluations[dept] 
                                    for dept in sorted(dept_evaluations.keys())}
        ctx['all_departments'] = ['A', 'B', 'C', 'D']
        
        return ctx


class EvaluationCreateView(TrainerMixin, View):
    def get(self, request):
        messages.warning(request, "Evaluation creation is managed from each Agniveer profile. Please select an Agniveer and evaluate from their detail page.")
        return redirect('departments:agniveer_list')

    def post(self, request):
        return self.get(request)


class EvaluationDetailView(AnyStaffMixin, DetailView):
    model = EvaluationSheet
    template_name = 'evaluation/evaluation_detail.html'
    context_object_name = 'sheet'

    def get(self, request, *args, **kwargs):
        if request.user.is_trainer:
            sheet = self.get_object()
            return redirect('evaluation:marks_entry', pk=sheet.pk)
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_department:
            queryset = queryset.filter(department=user.get_department_code())
        return queryset

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        sheet = self.object
        ctx['nco_marks'] = sheet.marks.filter(evaluator_type='nco').first()
        ctx['jco_marks'] = sheet.marks.filter(evaluator_type='jco').first()
        ctx['officer_marks'] = sheet.marks.filter(evaluator_type='officer').first()
        ctx['total_marks'] = sheet.get_total_marks()
        ctx['percentage'] = sheet.get_percentage()
        ctx['is_pass'] = sheet.is_pass()
        return ctx


class AgniveerEvaluateView(AnyStaffMixin, View):
    template_name = 'evaluation/agniveer_evaluate.html'

    def get_evaluator_type(self, user):
        if user.is_nco: return 'nco'
        elif user.is_jco: return 'jco'
        elif user.is_officer: return 'officer'
        return 'admin'

    def get(self, request, pk):
        from django.urls import reverse
        return redirect(reverse('departments:agniveer_detail', args=[pk]))

    def post(self, request, pk):
        agniveer = get_object_or_404(Agniveer, pk=pk)
        department = request.user.get_department_code()
        active_test = request.POST.get('active_test')
        
        from .constants import get_dept_config
        config = get_dept_config(department, request.user)
        test_config = config.get('test_config', {}).get(active_test, {})
        sub_events = test_config.get('sub_events', config.get('sub_events', {}).get(active_test, []))
        columns = test_config.get('columns', [])
        
        # Construct results
        results = {}
        total_for_best = 0
        
        # ─── DMV Specific Calculations ───
        if active_test == 'DMV_RESULT':
            prac_sheet = EvaluationSheet.objects.filter(agniveer=agniveer, test_type='DMV_PRACTICAL', department='B').first()
            drive_sheet = EvaluationSheet.objects.filter(agniveer=agniveer, test_type='DMV_DRIVING', department='B').first()
            
            prac_total = prac_sheet.get_total_marks() if prac_sheet else 0
            drive_total = drive_sheet.get_total_marks() if drive_sheet else 0
            
            try:
                online_val = int(request.POST.get('Online Test (100)', 0))
            except (ValueError, TypeError):
                online_val = 0
                
            total_200 = online_val + prac_total + drive_total
            percentage = (total_200 / 200 * 100) if total_200 else 0
            
            # Grading Logic: A(70%+), B(60-70%), C(<60%)
            if percentage >= 70: grading = 'A'
            elif percentage >= 60: grading = 'B'
            else: grading = 'C'
            
            converted_40 = (total_200 / 200 * 40) if total_200 else 0
            
            results = {
                'Online Test (100)': online_val,
                'Practical Test (50)': prac_total,
                'Driving Test (50)': drive_total,
                'Total (200)': total_200,
                '% Age': round(percentage, 2),
                'Grading': grading,
                'Convert 40 Marks': round(converted_40, 2)
            }
            total_for_best = round(converted_40)
            evaluator_type = 'admin'

        # ─── OPEM Specific Calculations ───
        elif active_test == 'OPEM_RESULT':
            prac_sheet = EvaluationSheet.objects.filter(agniveer=agniveer, test_type='OPEM_PRACTICAL', department='B').first()
            maint_sheet = EvaluationSheet.objects.filter(agniveer=agniveer, test_type='OPEM_MAINTENANCE', department='B').first()
            
            prac_total = prac_sheet.get_total_marks() if prac_sheet else 0
            maint_total = maint_sheet.get_total_marks() if maint_sheet else 0
            
            try:
                written_val = int(request.POST.get('Written Test (100)', 0))
            except (ValueError, TypeError):
                written_val = 0
                
            total_200 = written_val + prac_total + maint_total
            percentage = (total_200 / 200 * 100) if total_200 else 0
            
            # Grading Logic: A(70%+), B(60-70%), C(<60%)
            if percentage >= 70: grading = 'A'
            elif percentage >= 60: grading = 'B'
            else: grading = 'C'
            
            converted_40 = (total_200 / 200 * 40) if total_200 else 0
            
            results = {
                'Written Test (100)': written_val,
                'Practical Test (50)': prac_total,
                'Maintenance Test (50)': maint_total,
                'Total (200)': total_200,
                '% Age': round(percentage, 2),
                'Grading': grading,
                'Convert 40 Marks': round(converted_40, 2)
            }
            total_for_best = round(converted_40)
            evaluator_type = 'admin'

        # ─── OPEM/DMV Practical & Maintenance/Driving Calculations ───
        elif active_test in ('OPEM_PRACTICAL', 'DMV_PRACTICAL', 'OPEM_MAINTENANCE', 'DMV_DRIVING'):
            results = {'Marks': {}}
            total_marks = 0.0
            for sub in sub_events:
                val = request.POST.get(sub)
                try:
                    val_float = float(val) if val else 0.0
                except (ValueError, TypeError):
                    val_float = 0.0
                
                max_limit = config.get('max_marks', {}).get(active_test, {}).get(sub, 999)
                if val_float > max_limit:
                    val_float = max_limit
                results['Marks'][sub] = val_float
                total_marks += val_float
            
            results['Marks']['Total'] = round(total_marks, 2)
            results['Marks']['Percentage'] = round((total_marks / 50.0) * 100.0, 2)
            results['Marks']['Result'] = 'Pass' if total_marks >= 25.0 else 'Fail'
            
            total_for_best = round(total_marks)
            evaluator_type = 'admin'

        # ─── OPEM/DMV Final Assessment Specific Calculations ───
        elif active_test in ('OPEM_ASSESSMENT', 'DMV_ASSESSMENT'):
            results = {'Marks': {}}
            total_average = 0.0
            for event in sub_events:
                results['Marks'][event] = {}
                filled_weeks = []
                for week in range(1, 9):
                    val = request.POST.get(f"week_{week}_{event}")
                    try:
                        val_float = float(val) if val else None
                    except (ValueError, TypeError):
                        val_float = None
                    
                    results['Marks'][event][f"week_{week}"] = val_float
                    if val_float is not None:
                        filled_weeks.append(val_float)
                
                # Calculate week 9 as average of filled weeks
                if filled_weeks:
                    avg_val = round(sum(filled_weeks) / len(filled_weeks), 2)
                else:
                    avg_val = 0.0
                results['Marks'][event]['week_9'] = avg_val
                total_average += avg_val
            
            percentage = (total_average / 71.0 * 100.0) if total_average else 0.0
            is_pass_status = 'Pass' if percentage >= 40 else 'Fail'
            
            results['Marks']['Total'] = round(total_average, 2)
            results['Marks']['Percentage'] = round(percentage, 2)
            results['Marks']['Result'] = is_pass_status
            
            total_for_best = round(total_average)
            evaluator_type = 'admin'

        # ─── OTHER Trades Specific Calculations ───
        elif active_test == 'OTHER_ASSESSMENT':
            total_marks = 0
            for sub in sub_events:
                val = request.POST.get(sub)
                if val:
                    try:
                        total_marks += int(val)
                    except (ValueError, TypeError):
                        pass
            
            # Convert 74 marks total to 40 scale
            total_for_best = round((total_marks / 74 * 40)) if total_marks else 0
            evaluator_type = 'admin'

        elif department == 'C' and active_test == 'CS_RESULT':
            max_config = config.get('max_marks', {}).get(active_test, {})
            readonly_events = set(config.get('readonly_events', {}).get(active_test, []))
            mark_events = [event for event in sub_events if event not in readonly_events]

            results = {'Marks': {}}
            for event in mark_events:
                raw_value = request.POST.get(event)
                try:
                    value = float(raw_value) if raw_value else 0
                except (ValueError, TypeError):
                    value = 0

                max_limit = max_config.get(event, 600)
                if value > max_limit:
                    messages.warning(request, f"Value {value} for {event} exceeds max marks {max_limit}. Capped at limit.")
                    value = max_limit
                if value < 0:
                    value = 0
                results['Marks'][event] = value

            toet_total = results['Marks'].get('TOET-I (25)', 0) + results['Marks'].get('TOET-II (25)', 0)
            toet_25 = (toet_total / 50) * 25 if toet_total else 0
            fe_total = results['Marks'].get('FE Online Exam (50)', 0) + results['Marks'].get('FE Prac (20)', 0)
            br_total = results['Marks'].get('BR Online Exam (40)', 0) + results['Marks'].get('BR Prac (25)', 0)
            total_160 = toet_25 + fe_total + br_total
            converted_40 = (total_160 / 160) * 40 if total_160 else 0

            results['Marks']['TOTAL TOET (50)'] = min(toet_total, max_config.get('TOTAL TOET (50)', 50))
            results['Marks']['25% OF TOET (25)'] = round(min(toet_25, max_config.get('25% OF TOET (25)', 25)), 2)
            results['Marks']['FE Total (70)'] = min(fe_total, max_config.get('FE Total (70)', 70))
            results['Marks']['BR Total (65)'] = min(br_total, max_config.get('BR Total (65)', 65))
            results['Marks']['TOTAL (160)'] = round(min(total_160, max_config.get('TOTAL (160)', 160)), 2)
            results['Marks']['CONVERTED TO 40'] = round(min(converted_40, max_config.get('CONVERTED TO 40', 40)), 2)
            total_for_best = round(results['Marks']['CONVERTED TO 40'])
            evaluator_type = 'admin'

        elif department == 'C' and active_test == 'CS_CLERK_RESULT':
            max_config = config.get('max_marks', {}).get(active_test, {})
            results = {'Marks': {}}

            for event in ['PL', 'EN']:
                results['Marks'][event] = (request.POST.get(event) or '').strip()

            online = 0
            tprac = 0
            for event in ['Online (20)', 'TPrac (20)']:
                raw_value = request.POST.get(event)
                try:
                    value = float(raw_value) if raw_value else 0
                except (ValueError, TypeError):
                    value = 0

                max_limit = max_config.get(event, 20)
                if value > max_limit:
                    messages.warning(request, f"Value {value} for {event} exceeds max marks {max_limit}. Capped at limit.")
                    value = max_limit
                if value < 0:
                    value = 0
                results['Marks'][event] = value
                if event == 'Online (20)':
                    online = value
                else:
                    tprac = value

            total_40 = min(online + tprac, max_config.get('Total (40)', 40))
            results['Marks']['Total (40)'] = round(total_40, 2)
            results['Marks']['Percentage'] = round((total_40 / 40) * 100, 2) if total_40 else 0
            results['Marks']['Result'] = 'Pass' if total_40 >= 20 else 'Fail'
            total_for_best = round(total_40)
            evaluator_type = 'admin'

        elif department == 'C' and active_test == 'CS_ASSESSMENT':
            max_config = config.get('max_marks', {}).get(active_test, {})
            results = {'Marks': {}}
            raw_total = 0

            for event in sub_events:
                raw_value = request.POST.get(event)
                try:
                    value = float(raw_value) if raw_value else 0
                except (ValueError, TypeError):
                    value = 0

                max_limit = max_config.get(event, 999)
                if value > max_limit:
                    messages.warning(request, f"Value {value} for {event} exceeds max marks {max_limit}. Capped at limit.")
                    value = max_limit
                if value < 0:
                    value = 0
                results['Marks'][event] = value
                raw_total += value

            converted_40 = round((raw_total / 74) * 40, 2) if raw_total else 0
            percentage = round((raw_total / 74) * 100, 2) if raw_total else 0
            if percentage >= 80:
                grading = 'A'
            elif percentage >= 60:
                grading = 'B'
            elif percentage >= 46:
                grading = 'C'
            else:
                grading = 'D'

            results['Marks']['Raw Total (74)'] = round(raw_total, 2)
            results['Marks']['Total (40)'] = min(converted_40, max_config.get('Total (40)', 40))
            results['Marks']['Percentage'] = percentage
            results['Marks']['Result'] = 'Pass' if percentage >= 50 else 'Fail'
            results['Marks']['Grading'] = grading
            total_for_best = round(results['Marks']['Total (40)'])
            evaluator_type = 'admin'

        elif department == 'D' and active_test.startswith('CLK_'):
            max_config = config.get('max_marks', {}).get(active_test, {})
            readonly_events = set(config.get('readonly_events', {}).get(active_test, []))
            mark_events = [event for event in sub_events if event not in readonly_events]

            results = {'Marks': {}}
            for event in mark_events:
                raw_value = request.POST.get(event)
                try:
                    value = float(raw_value) if raw_value else 0
                except (ValueError, TypeError):
                    value = 0

                max_limit = max_config.get(event, 999)
                if event == 'Typing 20 WPM':
                    max_limit = max_config.get(event, 200)
                if value > max_limit:
                    messages.warning(request, f"Value {value} for {event} exceeds max marks {max_limit}. Capped at limit.")
                    value = max_limit
                if value < 0:
                    value = 0
                results['Marks'][event] = value

            if active_test == 'CLK_INITIAL':
                academic = results['Marks'].get('Academic Written (100)', 0)
                computer = results['Marks'].get('Computer Project Work (25)', 0)
                
                academic_conv = round(academic * 0.40, 2)
                computer_conv = round(computer * 0.40, 2)
                
                results['Marks']['Academic Converted (40)'] = academic_conv
                results['Marks']['Computer Converted (10)'] = computer_conv
                
                marks_obtained = academic_conv + computer_conv
                max_total = 50
                score_event = 'Marks Obtained (50)'
                
                percentage = ((academic + computer) / 125) * 100 if (academic + computer) else 0
                is_pass_status = 'Pass' if (academic >= 40 and computer >= 10) else 'Fail'

            elif active_test == 'CLK_WEEKLY_1':
                tech = results['Marks'].get('Tech Written (50)', 0)
                academic = results['Marks'].get('Academic Written (50)', 0)
                comp_obj = results['Marks'].get('Computer Obj (25)', 0)
                comp_prac = results['Marks'].get('Computer Prac (25)', 0)
                typing = results['Marks'].get('Typing 20 WPM', 0)
                
                comp_total = comp_obj + comp_prac
                results['Marks']['Computer Total (50)'] = comp_total
                
                tech_conv = round(tech * 0.40, 2)
                academic_conv = round(academic * 0.40, 2)
                comp_total_conv = round(comp_total * 0.40, 2)
                
                results['Marks']['Tech Converted (20)'] = tech_conv
                results['Marks']['Academic Converted (20)'] = academic_conv
                results['Marks']['Computer Total Converted (20)'] = comp_total_conv
                
                raw_total = tech + academic + comp_total
                marks_obtained = round(raw_total * 0.46, 2)
                max_total = 69
                score_event = 'Marks Obtained (69)'
                
                percentage = (raw_total / 150) * 100 if raw_total else 0
                is_pass_status = 'Pass' if (tech >= 20 and academic >= 20 and comp_total >= 20 and typing >= 70) else 'Fail'

            elif active_test == 'CLK_WEEKLY_2':
                tech_online = results['Marks'].get('Tech Online (115)', 0)
                tech_proj = results['Marks'].get('Tech Proj HRMS (25)', 0)
                academic = results['Marks'].get('Academic Online (85)', 0)
                comp_online = results['Marks'].get('Computer Online (25)', 0)
                comp_prac = results['Marks'].get('Computer Prac (25)', 0)
                typing = results['Marks'].get('Typing 20 WPM', 0)
                
                comp_total = comp_online + comp_prac
                results['Marks']['Computer Total (50)'] = comp_total
                
                tech_online_conv = round(tech_online * 0.40, 2)
                tech_proj_conv = round(tech_proj * 0.40, 2)
                academic_conv = round(academic * 0.40, 2)
                comp_online_conv = round(comp_online * 0.40, 2)
                comp_prac_conv = round(comp_prac * 0.40, 2)
                comp_total_conv = round(comp_total * 0.40, 2)
                
                results['Marks']['Tech Online Converted (46)'] = tech_online_conv
                results['Marks']['Tech Proj Converted (10)'] = tech_proj_conv
                results['Marks']['Academic Converted (34)'] = academic_conv
                results['Marks']['Computer Online Converted (10)'] = comp_online_conv
                results['Marks']['Computer Prac Converted (10)'] = comp_prac_conv
                results['Marks']['Computer Total Converted (20)'] = comp_total_conv
                
                raw_total = tech_online + tech_proj + academic + comp_total
                marks_obtained = round(raw_total * 0.46, 2)
                max_total = 126.50
                score_event = 'Marks Obtained (126.50)'
                
                percentage = (raw_total / 275) * 100 if raw_total else 0
                is_pass_status = 'Pass' if (tech_online >= 46 and tech_proj >= 10 and academic >= 34 and comp_total >= 20 and typing >= 70) else 'Fail'

            else: # CLK_FINAL
                tech_online = results['Marks'].get('Tech Online (115)', 0)
                tech_proj = results['Marks'].get('Tech Proj HRMS (25)', 0)
                academic = results['Marks'].get('Academic Online (85)', 0)
                comp_online = results['Marks'].get('Computer Online (25)', 0)
                comp_prac = results['Marks'].get('Computer Prac (25)', 0)
                extempore = results['Marks'].get('Extempore (25)', 0)
                typing = results['Marks'].get('Typing 20 WPM', 0)
                
                comp_total = comp_online + comp_prac
                results['Marks']['Computer Total (50)'] = comp_total
                
                tech_online_conv = round(tech_online * 0.40, 2)
                tech_proj_conv = round(tech_proj * 0.40, 2)
                academic_conv = round(academic * 0.40, 2)
                comp_online_conv = round(comp_online * 0.40, 2)
                comp_prac_conv = round(comp_prac * 0.40, 2)
                comp_total_conv = round(comp_total * 0.40, 2)
                extempore_conv = round(extempore * 0.40, 2)
                
                results['Marks']['Tech Online Converted (46)'] = tech_online_conv
                results['Marks']['Tech Proj Converted (10)'] = tech_proj_conv
                results['Marks']['Academic Converted (34)'] = academic_conv
                results['Marks']['Computer Online Converted (10)'] = comp_online_conv
                results['Marks']['Computer Prac Converted (10)'] = comp_prac_conv
                results['Marks']['Computer Total Converted (20)'] = comp_total_conv
                results['Marks']['Extempore Converted (10)'] = extempore_conv
                
                raw_total = tech_online + tech_proj + academic + comp_total + extempore
                marks_obtained = round(raw_total * 0.40, 2)
                max_total = 120.00
                score_event = 'Marks Obtained (120.00)'
                
                percentage = (raw_total / 300) * 100 if raw_total else 0
                is_pass_status = 'Pass' if (tech_online >= 46 and tech_proj >= 10 and academic >= 34 and comp_total >= 20 and extempore >= 10 and typing >= 70) else 'Fail'

            if percentage >= 80:
                grading = 'A'
            elif percentage >= 60:
                grading = 'B'
            elif percentage >= 46:
                grading = 'C'
            else:
                grading = 'D'

            results['Marks'][score_event] = min(marks_obtained, max_total)
            results['Marks']['Percentage'] = round(percentage, 2)
            results['Marks']['Result'] = is_pass_status
            results['Marks']['Grading'] = grading
            results['Marks']['Pass/Fail'] = is_pass_status

            total_for_best = round(marks_obtained)
            evaluator_type = 'admin'
        
        # ─── Battalion Screening Calculations ───
        elif department == 'A' and active_test == 'BN_SCREENING':
            max_config = config.get('max_marks', {}).get(active_test, {})
            readonly_events = set(config.get('readonly_events', {}).get(active_test, []))
            mark_events = [event for event in sub_events if event not in readonly_events]

            results = {'Marks': {}}
            for event in mark_events:
                raw_value = request.POST.get(event)
                try:
                    value = float(raw_value) if raw_value else 0
                except (ValueError, TypeError):
                    value = 0

                max_limit = max_config.get(event, 999)
                if value > max_limit:
                    messages.warning(request, f"Value {value} for {event} exceeds max marks {max_limit}. Capped at limit.")
                    value = max_limit
                if value < 0:
                    value = 0
                results['Marks'][event] = value

            cmk = results['Marks'].get('COMMN MIL KNOWLEDGE (20)', 0)
            wpn = results['Marks'].get('WPN & EQPT HANDLING (20)', 0)
            ces = results['Marks'].get('BASIC TAC (40)', 0)
            ppt = results['Marks'].get('PPT (10)', 0)
            fire = results['Marks'].get('FIRE (10)', 0)
            drill = results['Marks'].get('DRILL (20)', 0)
            bpet = results['Marks'].get('BPET (10)', 0)

            out_cmk = cmk
            out_ces = ces
            out_btt = round(ppt + drill + bpet, 2)
            out_wpn = round(wpn + fire, 2)

            total_120 = out_cmk + out_ces + out_btt + out_wpn
            round_figure = round(total_120)

            results['Marks']['COMMON MIL KNOWLEDGE (20)'] = out_cmk
            results['Marks']['BASIC TACTICE (CES) (40)'] = out_ces
            results['Marks']['TRADE PROFICIENCY (BTT) (40)'] = out_btt
            results['Marks']['WPN & EQPT HANDLING (20)'] = out_wpn
            results['Marks']['TOTAL (120)'] = round(total_120, 2)
            results['Marks']['ROUND FIGURE(120)'] = round_figure

            total_for_best = round_figure
            evaluator_type = 'admin'

        elif department == 'A':
            for col in columns:
                results[col] = {}
                col_total = 0
                for event in sub_events:
                    val = request.POST.get(f"{col}_{event}")
                    if val:
                        try:
                            val = int(val)
                            results[col][event] = val
                            col_total += val
                        except ValueError:
                            results[col][event] = None
                    else:
                        results[col][event] = None
                results[col]['TOTAL POINT'] = col_total
                
                # Firing test conversion (out of 56, converted to 100)
                if active_test == 'Firing':
                    converted = round((col_total / 56) * 100) if col_total else 0
                    results[col]['CONVERTED 100 MKS'] = converted
                    if converted > total_for_best:
                        total_for_best = converted
                # DST max attempt calculation
                elif active_test == 'DST':
                    if col_total > total_for_best:
                        total_for_best = col_total
                # BFC max attempt calculation
                elif active_test == 'BFC':
                    if col_total > total_for_best:
                        total_for_best = col_total
                # PPT/BPET max attempt calculation (Event Wise Best total)
                else:
                    if 'Best' in col: 
                        total_for_best = col_total
            
            # Fallback for simple single-column tests (e.g. MR_III, PDP, FC_All) without columns defined
            if not columns:
                results['Marks'] = {}
                for event in sub_events:
                    val = request.POST.get(event)
                    if val:
                        try:
                            results['Marks'][event] = int(val)
                        except ValueError:
                            results['Marks'][event] = None
                    else:
                        results['Marks'][event] = None
                
                if active_test == 'MR_III':
                    col_total = sum(filter(None, results['Marks'].values()))
                    converted = round((col_total / 150) * 100) if col_total else 0
                    results['Marks']['CONVERTED 100 MKS'] = converted
                    total_for_best = converted
                elif active_test == 'FC_All':
                    prac_total = sum(filter(None, [results['Marks'].get('TGT IDEN'), results['Marks'].get('JUDGING DIST'), results['Marks'].get('OBSN TRG')]))
                    results['Marks']['FC Practical Total'] = prac_total
                    
                    attempt1 = results['Marks'].get('FC Online 1st Attempt') or 0
                    attempt2 = results['Marks'].get('FC Online 2nd Attempt') or 0
                    best_online = max(attempt1, attempt2)
                    results['Marks']['FC Online Best Attempt'] = best_online
                    
                    camp_trg = results['Marks'].get('CAMP TRG') or 0
                    
                    total_for_best = prac_total + best_online + camp_trg
                else:
                    total_for_best = sum(filter(None, results['Marks'].values()))
                
            evaluator_type = 'admin'
        else:
            evaluator_type = self.get_evaluator_type(request.user)
            # Legacy NCO/JCO/Officer logic fallback
            results = {}
            for event in sub_events:
                val = request.POST.get(event)
                try:
                    val_int = int(val) if val else 0
                    # Max marks validation for DMV
                    if active_test.startswith('DMV_'):
                        max_limit = config.get('max_marks', {}).get(active_test, {}).get(event, 999)
                        if val_int > max_limit:
                            messages.warning(request, f"Value {val_int} for {event} exceeds max marks {max_limit}. Capped at limit.")
                            val_int = max_limit
                    results[event] = val_int
                except ValueError:
                    results[event] = 0
            total_for_best = sum(filter(None, results.values()))
            
        remarks = request.POST.get('remarks', '')

        # Get/Create Sheet
        category = config['test_to_category'].get(active_test, 'assessment')
        sheet, created = EvaluationSheet.objects.get_or_create(
            agniveer=agniveer,
            department=department,
            test_type=active_test,
            defaults={
                'category': category,
                'evaluation_date': date.today(),
                'created_by': request.user,
            }
        )

        if sheet.is_locked:
            messages.error(request, "This sheet is locked.")
            from django.urls import reverse
            return redirect(reverse('departments:agniveer_detail', args=[pk]) + f"?test={active_test}")

        # Update JSONField
        if (department == 'A' or 
            active_test in ('DMV_RESULT', 'OPEM_RESULT', 'OPEM_ASSESSMENT', 'DMV_ASSESSMENT', 
                            'OPEM_PRACTICAL', 'DMV_PRACTICAL', 'OPEM_MAINTENANCE', 'DMV_DRIVING') or 
            (department == 'C' and active_test in ('CS_RESULT', 'CS_CLERK_RESULT', 'CS_ASSESSMENT')) or 
            (department == 'D' and active_test.startswith('CLK_'))):
            sheet.sub_event_results = results
        else:
            if not sheet.sub_event_results:
                sheet.sub_event_results = {}
            sheet.sub_event_results[evaluator_type] = results
        sheet.remarks = remarks
        sheet.save()

        # Update/Create Marks
        Marks.objects.update_or_create(
            evaluation_sheet=sheet,
            evaluator_type=evaluator_type,
            defaults={
                'evaluator': request.user,
                'marks': total_for_best,
                'remarks': remarks,
            }
        )

        from django.urls import reverse
        messages.success(request, f"Evaluation for {active_test} saved successfully. Total: {total_for_best}")
        return redirect(reverse('departments:agniveer_detail', args=[pk]) + f"?test={active_test}")


class MarksEntryView(TrainerMixin, View):
    template_name = 'evaluation/marks_entry.html'

    def get_evaluator_type(self, user):
        if user.is_nco:
            return 'nco'
        elif user.is_jco:
            return 'jco'
        elif user.is_officer:
            return 'officer'
        return None

    def get(self, request, pk):
        sheet = get_object_or_404(EvaluationSheet, pk=pk)

        if not request.user.is_trainer:
            messages.error(request, "Only trainers can enter evaluation marks.")
            return redirect('core:dashboard')

        # Trainers CAN edit even if locked
        evaluator_type = self.get_evaluator_type(request.user)
        existing = sheet.marks.filter(evaluator_type=evaluator_type).first()
        form = MarksForm(instance=existing) if existing else MarksForm()

        # Get all marks for this sheet
        nco_marks = sheet.marks.filter(evaluator_type='nco').first()
        jco_marks = sheet.marks.filter(evaluator_type='jco').first()
        officer_marks = sheet.marks.filter(evaluator_type='officer').first()

        # Calculate total marks across all test types for this agniveer in this department
        all_sheets = EvaluationSheet.objects.filter(agniveer=sheet.agniveer, department=sheet.department)
        total_all_marks = sum(s.get_total_marks() for s in all_sheets)
        
        from .constants import get_dept_total_marks
        max_marks = get_dept_total_marks(sheet.department)

        return render(request, self.template_name, {
            'sheet': sheet,
            'form': form,
            'evaluator_type': evaluator_type,
            'existing': existing,
            'nco_marks': nco_marks,
            'jco_marks': jco_marks,
            'officer_marks': officer_marks,
            'total': sheet.get_total_marks(),
            'total_all_marks': total_all_marks,
            'max_marks': max_marks,
            'can_admin_enter': False,
        })

    def post(self, request, pk):
        sheet = get_object_or_404(EvaluationSheet, pk=pk)

        if not request.user.is_trainer:
            messages.error(request, "Only trainers can enter evaluation marks.")
            return redirect('core:dashboard')

        # Trainers CAN edit locked sheets
        evaluator_type = self.get_evaluator_type(request.user)
        if not evaluator_type:
            messages.error(request, "Invalid evaluator type.")
            return redirect('evaluation:marks_entry', pk=pk)

        try:
            marks_value = int(request.POST.get('marks', 0))
            if marks_value < 0 or marks_value > 20:
                raise ValueError
        except (ValueError, TypeError):
            messages.error(request, "Invalid marks value. Must be between 0 and 20.")
            return redirect('evaluation:marks_entry', pk=pk)

        remarks = request.POST.get('remarks', '')

        marks_obj, created = Marks.objects.update_or_create(
            evaluation_sheet=sheet,
            evaluator_type=evaluator_type,
            defaults={
                'evaluator': request.user,
                'marks': marks_value,
                'remarks': remarks,
            }
        )

        # AUTO-LOCK: Check if all 3 evaluators have submitted marks
        all_marks_submitted = (
            sheet.marks.filter(evaluator_type='nco').exists() and
            sheet.marks.filter(evaluator_type='jco').exists() and
            sheet.marks.filter(evaluator_type='officer').exists()
        )
        
        if all_marks_submitted and not sheet.is_locked:
            sheet.is_locked = True
            sheet.locked_by = request.user
            sheet.locked_at = timezone.now()
            sheet.save()
            messages.info(request, "✓ All evaluators have submitted marks. Sheet auto-locked.")

        action_word = "submitted" if created else "updated"
        log_action(
            request.user, 'EVALUATE',
            f'{evaluator_type.upper()} marks {action_word} for {sheet.agniveer}: {marks_value}/20',
            request
        )
        messages.success(request, f"Marks {action_word} successfully: {marks_value}/20")
        return redirect('evaluation:marks_entry', pk=pk)


class LockSheetView(AnyStaffMixin, View):
    def post(self, request, pk):
        sheet = get_object_or_404(EvaluationSheet, pk=pk)
        
        # Allow trainers, department heads, g_head, and commander to lock
        if not (request.user.is_trainer or request.user.is_commander or request.user.is_g_head or request.user.is_department):
            messages.error(request, "You don't have permission to lock evaluation sheets.")
            return redirect('evaluation:marks_entry', pk=pk)

        if sheet.is_locked:
            messages.warning(request, "This evaluation sheet is already locked.")
            return redirect('evaluation:marks_entry', pk=pk)

        # Check if all marks are entered (at least one evaluator has marks)
        has_marks = sheet.marks.exists()
        if not has_marks:
            messages.error(request, "At least one evaluator must enter marks before locking.")
            return redirect('evaluation:marks_entry', pk=pk)

        sheet.is_locked = True
        sheet.locked_by = request.user
        sheet.locked_at = timezone.now()
        sheet.save(update_fields=['is_locked', 'locked_by', 'locked_at'])

        log_action(request.user, 'LOCK', f'Locked evaluation sheet #{sheet.pk} for {sheet.agniveer}', request)
        messages.success(request, f"✓ Evaluation sheet locked. Total: {sheet.get_total_marks()}/60")
        return redirect('evaluation:marks_entry', pk=pk)


class UnlockSheetView(AnyStaffMixin, View):
    def post(self, request, pk):
        sheet = get_object_or_404(EvaluationSheet, pk=pk)
        
        # Only department heads, g_head, and commander can unlock
        if not (request.user.is_commander or request.user.is_g_head or request.user.is_department):
            messages.error(request, "Only Department Heads and above can unlock evaluation sheets.")
            return redirect('evaluation:marks_entry', pk=pk)

        if not sheet.is_locked:
            messages.warning(request, "This evaluation sheet is not locked.")
            return redirect('evaluation:marks_entry', pk=pk)

        sheet.is_locked = False
        sheet.locked_by = None
        sheet.locked_at = None
        sheet.save(update_fields=['is_locked', 'locked_by', 'locked_at'])

        log_action(request.user, 'UNLOCK', f'Unlocked evaluation sheet #{sheet.pk} for {sheet.agniveer}', request)
        messages.success(request, "✓ Evaluation sheet unlocked.")
        return redirect('evaluation:marks_entry', pk=pk)


class AgniveerReportCardView(AnyStaffMixin, View):
    template_name = 'evaluation/report_card.html'

    def _scope_evaluations_for_department_user(self, evaluations, user, agniveer, user_dept):
        evaluations = evaluations.filter(department=user_dept)

        if user_dept == 'A':
            if user.battalion_unit and agniveer.bn_desp != user.battalion_unit:
                return None
            if not user.battalion_unit:
                battalion_units = [choice[0] for choice in user.BATTALION_CHOICES]
                if agniveer.bn_desp not in battalion_units:
                    return None
                evaluations = evaluations.filter(agniveer__bn_desp__in=battalion_units)
            else:
                evaluations = evaluations.filter(agniveer__bn_desp=user.battalion_unit)

        elif user_dept == 'B' and user.tts_trade:
            if user.tts_trade == 'DMV':
                if agniveer.trade != 'DMV':
                    return None
                evaluations = evaluations.filter(agniveer__trade='DMV')
            elif user.tts_trade == 'OPEM':
                if agniveer.trade != 'OPEM':
                    return None
                evaluations = evaluations.filter(agniveer__trade='OPEM')
            elif user.tts_trade == 'OTHER':
                if agniveer.trade in ['DMV', 'OPEM']:
                    return None
                evaluations = evaluations.exclude(agniveer__trade__in=['DMV', 'OPEM'])

        elif user_dept == 'D':
            if agniveer.trade not in CLERK_TRADES:
                return None
            evaluations = evaluations.filter(agniveer__trade__in=CLERK_TRADES)

        return evaluations

    def get(self, request, pk):
        agniveer = get_object_or_404(Agniveer, pk=pk)
        
        # Check permissions
        if request.user.is_trainer:
            messages.error(request, "You don't have permission to view report cards.")
            return redirect('core:dashboard')
        
        # Get evaluations
        evaluations = EvaluationSheet.objects.filter(
            agniveer=agniveer
        ).prefetch_related('marks').order_by('department', 'category', 'test_type')
        
        # Determine filtering based on role and optional query parameter
        target_dept = request.GET.get('dept')
        is_department_view = False
        user_dept = None
        battalion_result_row = None

        if request.user.is_department:
            user_dept = request.user.get_department_code()
            evaluations = self._scope_evaluations_for_department_user(evaluations, request.user, agniveer, user_dept)
            if evaluations is None:
                return HttpResponseForbidden("You don't have permission to view this report card.")
            is_department_view = True
            departments_to_show = [user_dept]
        elif target_dept and target_dept in ['A', 'B', 'C', 'D'] and (request.user.is_commander or request.user.is_g_head):
            # Privileged users can optionally filter by department
            evaluations = evaluations.filter(department=target_dept)
            is_department_view = True
            departments_to_show = [target_dept]
            user_dept = target_dept
        else:
            # Commanders/G-Heads see everything by default
            is_department_view = False
            departments_to_show = ['A', 'B', 'C', 'D']

        # Group by department
        dept_evaluations = {}
        from .constants import get_dept_total_marks, get_overall_total_marks
        
        for dept in departments_to_show:
            dept_evals = evaluations.filter(department=dept)
            if dept_evals.exists():
                dept_evaluations[dept] = {
                    'on_field': dept_evals.filter(category='on_field'),
                    'trade': dept_evals.filter(category='trade'),
                    'total_marks': sum(e.get_total_marks() for e in dept_evals),
                    'max_marks': sum(e.get_max_marks() for e in dept_evals),
                    'total_locked': sum(e.get_total_marks() for e in dept_evals if e.is_locked),
                    'max_total': sum(e.get_max_marks() for e in dept_evals if e.is_locked),
                }

        # Prepare chart data
        chart_data = {
            'departments': [],
            'on_field_totals': [],
            'trade_totals': [],
            'overall_totals': []
        }
        
        for dept in departments_to_show:
            if dept in dept_evaluations:
                data = dept_evaluations[dept]
                chart_data['departments'].append({'A': 'Battalion', 'B': 'TTS', 'C': 'CS', 'D': 'Clerk'}.get(dept, dept))
                on_field_total = sum(e.get_total_marks() for e in data['on_field'])
                trade_total = sum(e.get_total_marks() for e in data['trade'])
                chart_data['on_field_totals'].append(on_field_total)
                chart_data['trade_totals'].append(trade_total)
                chart_data['overall_totals'].append(on_field_total + trade_total)
            else:
                chart_data['departments'].append({'A': 'Battalion', 'B': 'TTS', 'C': 'CS', 'D': 'Clerk'}.get(dept, dept))
                chart_data['on_field_totals'].append(0)
                chart_data['trade_totals'].append(0)
                chart_data['overall_totals'].append(0)

        department_result_row = None
        tts_result_row = None
        if is_department_view:
            department_result_row = build_department_result_row(agniveer, list(evaluations), user_dept)
            grand_total = department_result_row['grand_total']
            max_total = department_result_row.get('max_total') or 40
            percentage = department_result_row['percentage']
            overall_pass = department_result_row['is_pass']
            if user_dept == 'B':
                tts_result_row = department_result_row
            elif user_dept == 'A':
                battalion_result_row = department_result_row
        else:
            grand_total = sum(e.get_total_marks() for e in evaluations)
            max_total = sum(e.get_max_marks() for e in evaluations)
            percentage = round((grand_total / max_total * 100), 2) if max_total else 0
            overall_pass = percentage >= 50

        return render(request, self.template_name, {
            'agniveer': agniveer,
            'dept_evaluations': dept_evaluations,
            'department_result_row': department_result_row,
            'tts_result_row': tts_result_row,
            'battalion_result_row': battalion_result_row,
            'chart_data': chart_data,
            'grand_total': grand_total,
            'max_total': max_total,
            'percentage': percentage,
            'overall_pass': overall_pass,
            'is_department_view': is_department_view,
            'user_department': user_dept if is_department_view else None,
            'user_department_name': {'A': 'Battalion', 'B': 'TTS', 'C': 'CS', 'D': 'Clerk'}.get(user_dept, user_dept) if is_department_view else None,
        })
