"""
Accounts App - Role-Based Access Control Mixins
"""

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from django.contrib import messages


class RoleRequiredMixin(LoginRequiredMixin):
    """Base mixin that checks user role."""
    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if self.allowed_roles and request.user.role not in self.allowed_roles:
            messages.error(request, "You don't have permission to access this page.")
            return redirect('core:dashboard')
        return super().dispatch(request, *args, **kwargs)


class CommanderRequiredMixin(RoleRequiredMixin):
    """Only Commander can access."""
    allowed_roles = ['commander']


class CommanderOrGHeadMixin(RoleRequiredMixin):
    """Commander or G Head can access."""
    allowed_roles = ['commander', 'g_head']


class GHeadMixin(RoleRequiredMixin):
    """G Head can access."""
    allowed_roles = ['g_head']


class TrainerMixin(RoleRequiredMixin):
    """Trainers can access."""
    allowed_roles = ['trainer_nco', 'trainer_jco', 'trainer_officer']


class CommanderOrDeptMixin(RoleRequiredMixin):
    """Commander, G Head, or Department can access."""
    allowed_roles = ['commander', 'g_head', 'dept_a', 'dept_b', 'dept_c', 'dept_d']


class AnyStaffMixin(RoleRequiredMixin):
    """Any authenticated staff member can access."""
    allowed_roles = [
        'commander', 'g_head',
        'dept_a', 'dept_b', 'dept_c', 'dept_d',
        'trainer_nco', 'trainer_jco', 'trainer_officer',
        'registration'
    ]

class RegistrationOfficeMixin(RoleRequiredMixin):
    """Only Registration Office can access."""
    allowed_roles = ['registration']

class AgniveerEditMixin(RoleRequiredMixin):
    """Registration, Commander or G-Head can edit."""
    allowed_roles = ['registration', 'commander', 'g_head']

