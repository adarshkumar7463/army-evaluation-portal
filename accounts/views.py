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
    CreateDepartmentUserForm, CreateRegistrationOfficeForm,
    ProfileUpdateForm
)
from .mixins import CommanderRequiredMixin, CommanderOrGHeadMixin, CommanderOrDeptMixin
from logs.utils import log_action


class LoginView(View):
    template_name = 'accounts/login.html'

    # Maps portal_type (sent from login form) → allowed roles for that portal
    PORTAL_ROLE_MAP = {
        'commander':     ['commander'],
        'ghead':         ['g_head'],
        'dephead_a':     ['dept_a'],          # Battalion Head + 1TB/2TB/STB sub-units
        'dephead_b':     ['dept_b'],          # TTS Head + OPEM/DMV/Other trades
        'dephead_c':     ['dept_c'],          # CES/CS Head + CES users
        'dephead_d':     ['dept_d'],          # CTS/Clerk Head + CTS users
        'register_clerk': ['registration'],   # Registration Office
    }

    # Human-readable portal names for error messages
    PORTAL_LABELS = {
        'commander':     'Commander',
        'ghead':         'G-Head',
        'dephead_a':     'Battalion',
        'dephead_b':     'TTS',
        'dephead_c':     'CES',
        'dephead_d':     'CTS',
        'register_clerk': 'Registration Clerk',
    }

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('core:dashboard')
        form = ArmyLoginForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        portal_type = request.POST.get('portal_type', '').strip()
        form = ArmyLoginForm(request, data=request.POST)

        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)

            if user is not None:
                if user.is_account_locked():
                    messages.error(request, f"Account locked. Try again after {user.locked_until.strftime('%H:%M')}.")
                    return render(request, self.template_name, {'form': form, 'selected_portal': portal_type})

                # ── Portal Role Enforcement ──────────────────────────────────
                allowed_roles = self.PORTAL_ROLE_MAP.get(portal_type)
                if not allowed_roles:
                    messages.error(request, "Please select a valid portal before logging in.")
                    return render(request, self.template_name, {'form': form, 'selected_portal': portal_type})

                if user.role not in allowed_roles:
                    portal_label = self.PORTAL_LABELS.get(portal_type, portal_type)
                    messages.error(
                        request,
                        f"Access denied. Your account is not authorised for the {portal_label} portal. "
                        f"Please select the correct portal for your role."
                    )
                    return render(request, self.template_name, {'form': form, 'selected_portal': portal_type})
                # ────────────────────────────────────────────────────────────

                user.login_attempts = 0
                user.last_login_ip = get_client_ip(request)
                user.save(update_fields=['login_attempts', 'last_login_ip'])
                login(request, user)
                log_action(user, 'LOGIN', f'User {user.username} logged in via {portal_type} portal', request)
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

        return render(request, self.template_name, {'form': form, 'selected_portal': portal_type})


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

        # If an agniveer id is provided, render the agniveer profile + results
        agn_id = request.GET.get('agniveer')
        if agn_id:
            agn = get_object_or_404(Agniveer, pk=agn_id)
            # Permission: only commanders, g-heads, department heads, or superusers may view agniveer profiles here
            allowed = (
                getattr(request.user, 'is_commander', False) or 
                getattr(request.user, 'is_g_head', False) or 
                getattr(request.user, 'is_department', False) or 
                request.user.is_superuser
            )
            if not allowed:
                messages.error(request, "You don't have permission to view this profile.")
                return redirect('departments:agniveer_list')
            
            # Prepare evaluations according to permission scope
            sheets = EvaluationSheet.objects.filter(agniveer=agn).order_by('-evaluation_date')
            
            user = request.user
            dept_code = user.get_department_code()
            
            if user.is_commander or user.is_g_head or user.is_superuser:
                # Commander and G-head can see all test sections across all departments
                pass
            elif user.is_department:
                # Filter by department
                sheets = sheets.filter(department=dept_code)
                
                # Further filter by sub-department (trade / battalion unit)
                if dept_code == 'B' and getattr(user, 'tts_trade', None):
                    trade = user.tts_trade
                    if trade == 'DMV':
                        sheets = sheets.filter(test_type__startswith='DMV_')
                    elif trade == 'OPEM':
                        sheets = sheets.filter(test_type__startswith='OPEM_')
                    else: # OTHER, TECHNICAL, TRADESMAN
                        # Exclude DMV and OPEM sheets
                        sheets = sheets.exclude(test_type__startswith='DMV_').exclude(test_type__startswith='OPEM_')
                elif dept_code == 'A' and getattr(user, 'battalion_unit', None):
                    if agn.bn_desp != user.battalion_unit:
                        sheets = sheets.none()
            else:
                sheets = sheets.none()

            # Reorder evaluations: final result sheets first, followed by other tests in date descending order
            FINAL_RESULT_TESTS = {
                'FINAL_RESULT', 'FINAL_MERIT', 'DMV_RESULT', 'OPEM_RESULT',
                'OTHER_ASSESSMENT', 'CS_RESULT', 'CS_CLERK_RESULT', 'CLK_FINAL'
            }
            sheets = list(sheets)  # Convert QuerySet to list to sort
            sheets.sort(
                key=lambda s: 0 if s.test_type in FINAL_RESULT_TESTS else 1
            )

            evals = []
            for s in sheets:
                # Prepare display data: only show sub_event_results and do not fall back to evaluator marks
                data = s.sub_event_results or {}
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

            # Check edit permission
            can_edit = False
            if user.is_department:
                if dept_code == 'B' and getattr(user, 'tts_trade', None):
                    if user.tts_trade == 'DMV' and agn.trade == 'DMV':
                        can_edit = True
                    elif user.tts_trade == 'OPEM' and agn.trade == 'OPEM':
                        can_edit = True
                    elif user.tts_trade in ['OTHER', 'TECHNICAL', 'TRADESMAN'] and agn.trade not in ['DMV', 'OPEM']:
                        can_edit = True
                elif dept_code == 'A' and getattr(user, 'battalion_unit', None):
                    if agn.bn_desp == user.battalion_unit:
                        can_edit = True
                else:
                    can_edit = True

            # Group sheets by department-wise test types for charts
            MAX_MARKS_MAP = {
                # Dept A
                'PPT': 100, 'BPET': 100, 'Firing': 100, 'DST': 160, 'MR_III': 150,
                'BFC': 240, 'PDP': 50, 'FC_All': 90, 'CMK_SHEET': 20,
                'WPN_HANDLING': 20, 'FINAL_MERIT': 130, 'FINAL_RESULT': 120,
                # Dept B
                'DMV_PRACTICAL': 50, 'DMV_DRIVING': 50, 'DMV_ASSESSMENT': 71, 'DMV_RESULT': 40,
                'OPEM_PRACTICAL': 50, 'OPEM_MAINTENANCE': 50, 'OPEM_ASSESSMENT': 71, 'OPEM_RESULT': 40,
                'OTHER_ASSESSMENT': 40, 'DMV_SCREEN_BOARD': 40, 'OPEM_SCREEN_BOARD': 40, 'OTHER_SCREEN_BOARD': 40,
                # Dept C
                'CS_ASSESSMENT': 86, 'CS_RESULT': 40, 'CS_CLERK_RESULT': 40,
                # Dept D
                'CLK_INITIAL': 125, 'CLK_WEEKLY_1': 150, 'CLK_WEEKLY_2': 275, 'CLK_FINAL': 40,
            }
            
            # Compute top stats
            best_test_name = "—"
            max_pct = -1.0
            obtained_sum = 0.0
            max_sum = 0.0
            
            for s in sheets:
                pct = float(s.get_percentage() or 0.0)
                obtained = float(s.get_total_marks() or 0.0)
                max_val = float(MAX_MARKS_MAP.get(s.test_type, 100.0))
                
                if pct > max_pct:
                    max_pct = pct
                    best_test_name = s.get_test_type_display()
                
                obtained_sum += obtained
                max_sum += max_val

            overall_percentage = (obtained_sum / max_sum * 100) if max_sum > 0 else 0.0
            
            from evaluation.result_helpers import get_grade
            passing_pct = 40 if dept_code == 'A' else 50
            overall_grade = get_grade(overall_percentage, passing_pct=passing_pct)

            # Department-wise tests for Slicer and Pie charts
            test_obtained = {}
            test_percentages = {}
            for s in sheets:
                test_label = s.get_test_type_display()
                if test_label not in test_obtained:
                    obtained = s.get_total_marks() or 0.0
                    max_val = MAX_MARKS_MAP.get(s.test_type, 100.0)
                    pct = (float(obtained) / float(max_val) * 100) if max_val > 0 else 0.0
                    
                    test_obtained[test_label] = round(float(obtained), 1)
                    test_percentages[test_label] = round(float(pct), 1)

            pie_labels = list(test_obtained.keys())
            pie_data = list(test_obtained.values())
            
            slicer_labels = list(test_percentages.keys())
            slicer_data = list(test_percentages.values())

            context.update({
                'chart_trend_labels_json': mark_safe(json.dumps(trend_labels)),
                'chart_trend_data_json': mark_safe(json.dumps(trend_data)),
                'exam_details_json': mark_safe(json.dumps(exam_details)),
                'chart_pie_labels_json': mark_safe(json.dumps(pie_labels)),
                'chart_pie_data_json': mark_safe(json.dumps(pie_data)),
                'chart_slicer_labels_json': mark_safe(json.dumps(slicer_labels)),
                'chart_slicer_data_json': mark_safe(json.dumps(slicer_data)),
                'can_edit_evaluation': can_edit,
                'stats_best_subject': best_test_name,
                'stats_total_marks': f"{round(obtained_sum, 1)} / {round(max_sum, 1)}" if max_sum > 0 else "—",
                'stats_percentage': f"{round(overall_percentage, 1)}%" if max_sum > 0 else "—",
                'stats_grade': overall_grade,
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
            queryset = queryset.filter(role__in=['dept_a', 'dept_b', 'dept_c', 'dept_d'])
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
                messages.error(request, "You can only toggle users in your department.")
                return redirect('accounts:user_list')
        
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
