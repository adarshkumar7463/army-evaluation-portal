"""
Accounts App - Views
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q

from .models import CustomUser
import json
from django.utils.safestring import mark_safe
from departments.models import Agniveer
from evaluation.models import EvaluationSheet
from .forms import (
    ArmyLoginForm, CreateGHeadForm,
    CreateDepartmentUserForm, CreateTrainerForm, CreateRegistrationOfficeForm,
    ProfileUpdateForm
)
from .mixins import CommanderRequiredMixin, CommanderOrGHeadMixin, CommanderOrDeptMixin
from logs.utils import log_action


class LoginView(View):
    template_name = 'accounts/login.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('core:dashboard')
        form = ArmyLoginForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = ArmyLoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)

            if user is not None:
                if user.is_account_locked():
                    messages.error(request, f"Account locked. Try again after {user.locked_until.strftime('%H:%M')}.")
                    return render(request, self.template_name, {'form': form})

                user.login_attempts = 0
                user.last_login_ip = get_client_ip(request)
                user.save(update_fields=['login_attempts', 'last_login_ip'])
                login(request, user)
                log_action(user, 'LOGIN', f'User {user.username} logged in', request)
                messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
                return redirect('core:dashboard')
            else:
                # Track failed attempts
                try:
                    failed_user = CustomUser.objects.get(username=username)
                    failed_user.login_attempts += 1
                    if failed_user.login_attempts >= 5:
                        failed_user.locked_until = timezone.now() + timezone.timedelta(minutes=30)
                        messages.error(request, "Too many failed attempts. Account locked for 30 minutes.")
                    else:
                        messages.error(request, f"Invalid credentials. {5 - failed_user.login_attempts} attempts remaining.")
                    failed_user.save(update_fields=['login_attempts', 'locked_until'])
                except CustomUser.DoesNotExist:
                    messages.error(request, "Invalid credentials.")
        else:
            messages.error(request, "Invalid credentials. Please try again.")

        return render(request, self.template_name, {'form': form})


class LogoutView(LoginRequiredMixin, View):
    def get(self, request):
        log_action(request.user, 'LOGOUT', f'User {request.user.username} logged out', request)
        logout(request)
        messages.success(request, "You have been logged out successfully.")
        return redirect('accounts:login')


class ProfileView(LoginRequiredMixin, View):
    template_name = 'accounts/profile.html'

    def get(self, request):
        form = ProfileUpdateForm(instance=request.user)
        context = {'form': form}

        # If an agniveer id is provided, render the agniveer profile + results (read-only)
        agn_id = request.GET.get('agniveer')
        if agn_id:
            agn = get_object_or_404(Agniveer, pk=agn_id)
            # Permission: only commanders, g-heads, department heads or superusers may view agniveer profiles here
            allowed = getattr(request.user, 'is_commander', False) or getattr(request.user, 'is_g_head', False) or getattr(request.user, 'is_department', False) or request.user.is_superuser
            if not allowed:
                messages.error(request, "You don't have permission to view this profile.")
                return redirect('departments:agniveer_list')
            # Prepare evaluations according to permission scope
            sheets = EvaluationSheet.objects.filter(agniveer=agn, is_locked=True).order_by('-evaluation_date')
            # Department heads see only their department's results
            if getattr(request.user, 'is_department', False):
                dept_code = request.user.department
                sheets = sheets.filter(department=dept_code)

            evals = []
            for s in sheets:
                # Prepare display data: prefer sub_event_results, else breakdown by evaluator marks
                data = s.sub_event_results or {
                    'NCO': s.get_nco_marks(),
                    'JCO': s.get_jco_marks(),
                    'Officer': s.get_officer_marks(),
                    'Admin': s.get_admin_marks(),
                }
                evals.append({
                    'test_type': s.test_type,
                    'test_type_display': s.get_test_type_display(),
                    'evaluation_date': s.evaluation_date.strftime('%d %b %Y'),
                    'department': s.department,
                    'total_marks': s.get_total_marks(),
                    'percentage': s.get_percentage(),
                    'data': data,
                })

            # Prepare chart JSON (server-side) to avoid DOM parsing in template JS
            trend_labels = [f"{e['test_type_display']} - {e['evaluation_date']}" for e in evals]
            trend_data = [e['total_marks'] for e in evals]
            # Ensure exam details are serializable
            exam_details = []
            for e in evals:
                exam_details.append({
                    'name': e['test_type_display'],
                    'date': e['evaluation_date'],
                    'total': e['total_marks'],
                    'percentage': e['percentage'],
                    'data': e['data'],
                    'department': e['department'],
                })

            context.update({
                'chart_trend_labels_json': mark_safe(json.dumps(trend_labels)),
                'chart_trend_data_json': mark_safe(json.dumps(trend_data)),
                'exam_details_json': mark_safe(json.dumps(exam_details)),
            })

            # Departments list for filter (for ghead/commander)
            departments = [{'id': c[0], 'name': c[1]} for c in CustomUser.DEPARTMENT_CHOICES]
            is_ghead_flag = getattr(request.user, 'is_g_head', False) or getattr(request.user, 'is_commander', False)

            context.update({
                'agniveer': agn,
                'evaluations': evals,
                'departments': departments,
                'is_ghead': is_ghead_flag,
                'is_department': getattr(request.user, 'is_department', False),
            })

        # If an agniveer profile was requested, render the dedicated agniveer profile template
        if agn_id:
            return render(request, 'core/agniveer_profile.html', context)
        return render(request, self.template_name, context)

    def post(self, request):
        form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            log_action(request.user, 'UPDATE', 'Profile updated', request)
            messages.success(request, "Profile updated successfully.")
            return redirect('accounts:profile')
        return render(request, self.template_name, {'form': form})


class UserListView(CommanderOrGHeadMixin, ListView):
    model = CustomUser
    template_name = 'accounts/user_list.html'
    context_object_name = 'users'
    paginate_by = 20

    def get_queryset(self):
        queryset = CustomUser.objects.exclude(role='commander').select_related('created_by')
        if self.request.user.is_g_head:
            queryset = queryset.filter(role__in=['dept_a', 'dept_b', 'dept_c', 'dept_d',
                                                'trainer_nco', 'trainer_jco', 'trainer_officer'])
        # Filter
        role_filter = self.request.GET.get('role')
        dept_filter = self.request.GET.get('department')
        search = self.request.GET.get('search')

        if role_filter:
            queryset = queryset.filter(role=role_filter)
        if dept_filter:
            queryset = queryset.filter(department=dept_filter)
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(service_number__icontains=search)
            )
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['role_choices'] = CustomUser.ROLE_CHOICES
        ctx['dept_choices'] = CustomUser.DEPARTMENT_CHOICES
        ctx['is_user_list'] = True
        return ctx


class MyTeamListView(CommanderOrDeptMixin, ListView):
    model = CustomUser
    template_name = 'accounts/user_list.html'
    context_object_name = 'users'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        queryset = CustomUser.objects.filter(
            role__in=['trainer_nco', 'trainer_jco', 'trainer_officer']
        ).select_related('created_by')
        
        # Commanders and G-Heads see all trainers. Department heads only see their own.
        if user.is_department:
            dept = user.get_department_code()
            queryset = queryset.filter(department=dept)
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(service_number__icontains=search)
            )
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'My Team'
        ctx['is_my_team'] = True
        return ctx


class CreateGHeadView(CommanderRequiredMixin, CreateView):
    model = CustomUser
    form_class = CreateGHeadForm
    template_name = 'accounts/create_user.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Create G Department Head'
        ctx['role_label'] = 'G Head'
        return ctx

    def form_valid(self, form):
        user = form.save(commit=False)
        user.created_by = self.request.user
        user.save()
        log_action(self.request.user, 'CREATE', f'Created G Head: {user.username}', self.request)
        messages.success(self.request, f"G Head '{user.get_full_name()}' created successfully.")
        return redirect('accounts:user_list')


class CreateDepartmentView(CommanderOrGHeadMixin, CreateView):
    model = CustomUser
    form_class = CreateDepartmentUserForm
    template_name = 'accounts/create_user.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Create Department Head'
        ctx['role_label'] = 'Department'
        return ctx

    def form_valid(self, form):
        user = form.save(commit=False)
        user.created_by = self.request.user
        user.save()
        log_action(self.request.user, 'CREATE', f'Created Department: {user.username}', self.request)
        messages.success(self.request, f"Department user '{user.get_full_name()}' created successfully.")
        return redirect('accounts:user_list')


class CreateTrainerView(CommanderOrDeptMixin, CreateView):
    model = CustomUser
    form_class = CreateTrainerForm
    template_name = 'accounts/create_user.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Create Trainer'
        ctx['role_label'] = 'Trainer'
        if self.request.user.is_department:
            ctx['department_code'] = self.request.user.get_department_code()
        return ctx

    def form_valid(self, form):
        user = form.save(commit=False)
        user.created_by = self.request.user
        # Department trainers inherit the department
        if self.request.user.is_department:
            user.department = self.request.user.get_department_code()
        user.save()
        log_action(self.request.user, 'CREATE', f'Created Trainer: {user.username}', self.request)
        messages.success(self.request, f"Trainer '{user.get_full_name()}' created successfully.")
        
        if self.request.user.is_department:
            return redirect('accounts:my_team')
        return redirect('accounts:user_list')


class CreateRegistrationOfficeView(CommanderRequiredMixin, CreateView):
    model = CustomUser
    form_class = CreateRegistrationOfficeForm
    template_name = 'accounts/create_user.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Create Registration Office'
        ctx['role_label'] = 'Registration Office'
        return ctx

    def form_valid(self, form):
        user = form.save(commit=False)
        user.created_by = self.request.user
        user.save()
        log_action(self.request.user, 'CREATE', f'Created Registration Office: {user.username}', self.request)
        messages.success(self.request, f"Registration Office user '{user.get_full_name()}' created successfully.")
        return redirect('accounts:user_list')


class ToggleUserActiveView(CommanderOrDeptMixin, View):
    def post(self, request, pk):
        user = get_object_or_404(CustomUser, pk=pk)
        
        # Permission check: Department heads can only toggle trainers in their department
        if request.user.is_department:
            if user.department != request.user.get_department_code():
                messages.error(request, "You can only toggle trainers in your department.")
                return redirect('accounts:my_team')
        
        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])
        status = "activated" if user.is_active else "deactivated"
        log_action(request.user, 'UPDATE', f'User {user.username} {status}', request)
        messages.success(request, f"User '{user.username}' has been {status}.")
        
        # Redirect back to where they came from
        referer = request.META.get('HTTP_REFERER')
        if referer:
            return redirect(referer)
        return redirect('accounts:user_list')


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
