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
from django.http import JsonResponse
from django.urls import reverse_lazy
from datetime import date

from .models import EvaluationSheet, Marks
from .forms import EvaluationSheetForm, MarksForm, EvaluationFilterForm, AgniveerEvaluationForm
from departments.models import Agniveer
from accounts.mixins import AnyStaffMixin, CommanderOrDeptMixin, TrainerMixin
from logs.utils import log_action


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


class AgniveerEvaluateView(TrainerMixin, View):
    template_name = 'evaluation/agniveer_evaluate.html'

    def get_evaluator_type(self, user):
        if user.is_nco:
            return 'nco'
        elif user.is_jco:
            return 'jco'
        elif user.is_officer:
            return 'officer'
        return None

    def get(self, request, pk):
        agniveer = get_object_or_404(Agniveer, pk=pk)
        department = request.user.get_department_code()
        form = AgniveerEvaluationForm(department=department)
        
        from .constants import DEPT_CONFIG
        config = DEPT_CONFIG.get(department, DEPT_CONFIG['A'])
        
        return render(request, self.template_name, {
            'agniveer': agniveer,
            'form': form,
            'category_choices': config['categories'],
            'test_type_choices': config['test_types'],
            'test_to_category': config['test_to_category'],
        })

    def post(self, request, pk):
        agniveer = get_object_or_404(Agniveer, pk=pk)
        department = request.user.get_department_code()

        form = AgniveerEvaluationForm(request.POST, department=department)
        if not form.is_valid():
            messages.error(request, "Invalid evaluation details. Please select a valid category and test type for your department.")
            return redirect('departments:agniveer_detail', pk=agniveer.pk)

        category = form.cleaned_data['category']
        test_type = form.cleaned_data['test_type']
        marks_value = form.cleaned_data['marks']
        remarks = form.cleaned_data['remarks']

        sheet, created = EvaluationSheet.objects.get_or_create(
            agniveer=agniveer,
            category=category,
            test_type=test_type,
            department=department,
            defaults={
                'evaluation_date': date.today(),
                'created_by': request.user,
                'remarks': ''
            }
        )

        if sheet.is_locked:
            messages.error(request, "This evaluation sheet is locked and cannot be modified.")
            return redirect('departments:agniveer_detail', pk=agniveer.pk)

        marks_obj, created_mark = Marks.objects.update_or_create(
            evaluation_sheet=sheet,
            evaluator_type=self.get_evaluator_type(request.user),
            defaults={
                'evaluator': request.user,
                'marks': marks_value,
                'remarks': remarks,
            }
        )

        action = 'created' if created_mark else 'updated'
        log_action(request.user, 'EVALUATE', f'{request.user.get_role_display()} {action} marks for {agniveer.enrollment_number} - {test_type}: {marks_value}/20', request)
        messages.success(request, f"Evaluation {action} successfully.")
        return redirect('departments:agniveer_detail', pk=agniveer.pk)


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

        if request.user.is_department:
            user_dept = request.user.get_department_code()
            evaluations = evaluations.filter(department=user_dept)
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
                    'max_marks': get_dept_total_marks(dept),
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
                chart_data['departments'].append(f'Dept {dept}')
                on_field_total = sum(e.get_total_marks() for e in data['on_field'])
                trade_total = sum(e.get_total_marks() for e in data['trade'])
                chart_data['on_field_totals'].append(on_field_total)
                chart_data['trade_totals'].append(trade_total)
                chart_data['overall_totals'].append(on_field_total + trade_total)
            else:
                chart_data['departments'].append(f'Dept {dept}')
                chart_data['on_field_totals'].append(0)
                chart_data['trade_totals'].append(0)
                chart_data['overall_totals'].append(0)

        grand_total = sum(e.get_total_marks() for e in evaluations)
        
        # For department view, use only department's max marks
        if is_department_view:
            max_total = get_dept_total_marks(user_dept)
        else:
            max_total = get_overall_total_marks()
            
        percentage = round((grand_total / max_total * 100), 2) if max_total else 0
        overall_pass = percentage >= 50

        return render(request, self.template_name, {
            'agniveer': agniveer,
            'dept_evaluations': dept_evaluations,
            'chart_data': chart_data,
            'grand_total': grand_total,
            'max_total': max_total,
            'percentage': percentage,
            'overall_pass': overall_pass,
            'is_department_view': is_department_view,
            'user_department': user_dept if is_department_view else None,
        })
