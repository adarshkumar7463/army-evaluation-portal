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
from .forms import (
    ArmyLoginForm, CreateGHeadForm,
    CreateDepartmentUserForm, CreateTrainerForm, ProfileUpdateForm
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
        return render(request, self.template_name, {'form': form})

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
