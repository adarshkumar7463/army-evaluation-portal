"""
Departments App - Views
Agniveer management and department administration
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db.models import Q
from django.urls import reverse_lazy

from .models import Agniveer
from .forms import AgniveerForm, AssignTrainerForm
from accounts.mixins import CommanderOrDeptMixin, AnyStaffMixin, GHeadMixin
from accounts.models import CustomUser
from evaluation.models import EvaluationSheet
from evaluation.forms import AgniveerEvaluationForm
from logs.utils import log_action


class AgniveerListView(AnyStaffMixin, ListView):
    model = Agniveer
    template_name = 'departments/agniveer_list.html'
    context_object_name = 'agniveers'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        queryset = Agniveer.objects.select_related('registered_by')

        # Filters
        status = self.request.GET.get('status')
        search = self.request.GET.get('search')
        batch = self.request.GET.get('batch')

        if status:
            queryset = queryset.filter(status=status)
        if batch:
            queryset = queryset.filter(batch__icontains=batch)
        if search:
            queryset = queryset.filter(
                Q(enrollment_number__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search)
            )
        return queryset.order_by('enrollment_number')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = Agniveer.STATUS_CHOICES
        return ctx


class AgniveerCreateView(GHeadMixin, CreateView):
    model = Agniveer
    form_class = AgniveerForm
    template_name = 'departments/agniveer_form.html'
    success_url = reverse_lazy('departments:agniveer_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Register New Agniveer'
        ctx['action'] = 'Register'
        return ctx

    def form_valid(self, form):
        agniveer = form.save(commit=False)
        agniveer.registered_by = self.request.user
        agniveer.save()
        form.save_m2m()
        log_action(self.request.user, 'CREATE', f'Registered Agniveer: {agniveer.enrollment_number}', self.request)
        messages.success(self.request, f"Agniveer '{agniveer.get_full_name()}' registered successfully.")
        return redirect(self.success_url)


class AgniveerUpdateView(CommanderOrDeptMixin, UpdateView):
    model = Agniveer
    form_class = AgniveerForm
    template_name = 'departments/agniveer_form.html'
    success_url = reverse_lazy('departments:agniveer_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = f'Edit Agniveer - {self.object.enrollment_number}'
        ctx['action'] = 'Update'
        return ctx

    def form_valid(self, form):
        agniveer = form.save()
        log_action(self.request.user, 'UPDATE', f'Updated Agniveer: {agniveer.enrollment_number}', self.request)
        messages.success(self.request, "Agniveer updated successfully.")
        return redirect(self.success_url)


class AgniveerDetailView(AnyStaffMixin, DetailView):
    model = Agniveer
    template_name = 'departments/agniveer_detail.html'
    context_object_name = 'agniveer'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        agniveer = self.object
        user = self.request.user
        department = user.get_department_code()
        
        evaluations = EvaluationSheet.objects.filter(
            agniveer=agniveer
        ).prefetch_related('marks')
        
        if user.is_department or user.is_trainer:
            # Only show evaluation of their own department
            evaluations = evaluations.filter(department=department)
            
        ctx['evaluations'] = evaluations
        
        from evaluation.constants import get_dept_total_marks, DEPT_CONFIG, get_overall_total_marks
        
        if user.is_commander or user.is_g_head:
            max_marks = get_overall_total_marks()
            total_score = sum(e.get_total_marks() for e in evaluations) # This shows all dept evals if commander
        else:
            max_marks = get_dept_total_marks(department)
            total_score = sum(e.get_total_marks() for e in evaluations.filter(department=department))

        percentage = (total_score / max_marks * 100) if max_marks > 0 else 0
        
        # UI Colors
        if percentage >= 50:
            score_color = "#52B788"
            score_color_dark = "#1B4332"
        else:
            score_color = "#4FC3F7"
            score_color_dark = "#2E6F82"

        ctx['total_score'] = total_score
        ctx['max_marks'] = max_marks
        ctx['percentage'] = round(percentage, 1)
        ctx['score_color'] = score_color
        ctx['score_color_dark'] = score_color_dark
        ctx['pass_status'] = agniveer.get_pass_status()
        ctx['can_evaluate'] = user.is_trainer
        
        # Get dynamic choices for evaluation form
        import json
        config = DEPT_CONFIG.get(department, DEPT_CONFIG['A'])
        ctx['category_choices'] = config['categories']
        ctx['test_type_choices'] = config['test_types']
        ctx['test_to_category_json'] = json.dumps(config['test_to_category'])
        ctx['evaluation_form'] = AgniveerEvaluationForm(department=department)
        return ctx


class AssignTrainerView(CommanderOrDeptMixin, UpdateView):
    def get(self, request, *args, **kwargs):
        messages.info(request, "Trainers are now automatically assigned to all agniveers in their department.")
        return redirect('departments:agniveer_list')

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)
