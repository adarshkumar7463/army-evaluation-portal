"""
Departments App - Views
Agniveer management, registration dashboard, and bulk upload
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db.models import Q, Count
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse
from django import forms as django_forms
from django.core.paginator import Paginator
import json
import io

from .models import Agniveer, TRADE_CHOICES, BATCH_NO_CHOICES, COMPANY_CHOICES, PLATOON_CHOICES, BN_DESP_CHOICES
from .forms import (
    AgniveerForm, AgniveerRegistrationForm, AgniveerEditForm,
    AgniveerExcelUploadForm, AssignTrainerForm
)
from accounts.mixins import (
    CommanderOrDeptMixin, AnyStaffMixin, GHeadMixin, CommanderOrGHeadMixin,
    RegistrationOfficeMixin, AgniveerEditMixin
)
from accounts.models import CustomUser
from evaluation.models import EvaluationSheet
from evaluation.forms import AgniveerEvaluationForm
from logs.utils import log_action


# ── Registration Dashboard ──────────────────────────────────────────────────────

class RegistrationDashboardView(RegistrationOfficeMixin, View):
    """
    Dedicated Agniveer Registration Dashboard.
    Accessible to Commander and G-Head only.
    Shows registration form, bulk Excel upload, and the full Agniveer list.
    """
    template_name = 'departments/registration_dashboard.html'

    def get(self, request):
        reg_form = AgniveerRegistrationForm()
        upload_form = AgniveerExcelUploadForm()
        agniveers = Agniveer.objects.all().order_by('-created_at')

        # Search / filter
        search = request.GET.get('search', '').strip()
        trade_filter = request.GET.get('trade', '')
        company_filter = request.GET.get('company', '')
        platoon_filter = request.GET.get('platoon', '')
        if search:
            agniveers = agniveers.filter(
                Q(enrollment_number__icontains=search) |
                Q(agniveer_no__icontains=search) |
                Q(name__icontains=search) |
                Q(father_name__icontains=search) |
                Q(aros_bros__icontains=search)
            )
        if trade_filter:
            agniveers = agniveers.filter(trade=trade_filter)
        if company_filter:
            agniveers = agniveers.filter(company=company_filter)
        if platoon_filter:
            agniveers = agniveers.filter(platoon=platoon_filter)

        
        cert_fields = [
            {'name': 'afmsf_2a', 'label': 'AFMSF-2A'},
            {'name': 'review_cert', 'label': 'Review Cert'},
            {'name': 'edn_cert', 'label': 'EDN Cert'},
            {'name': 'verification_roll', 'label': 'Verification Roll'},
            {'name': 'character_cert', 'label': 'Character Cert'},
            {'name': 'unmarried_cert', 'label': 'Unmarried Cert'},
            {'name': 'caste_cert', 'label': 'Caste Cert'},
            {'name': 'domicile_cert', 'label': 'Domicile Cert'},
            {'name': 'outside_sanction_letter', 'label': 'Sanction Letter'},
            {'name': 'willingness_cert', 'label': 'Willingness Cert'},
            {'name': 'ncc_cert', 'label': 'NCC Cert'},
            {'name': 'pan_card', 'label': 'PAN Card'},
            {'name': 'aadhar_card', 'label': 'Aadhar Card'},
        ]

        paginator = Paginator(agniveers, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # Fetch uploaded files list
        import os
        from django.conf import settings
        from datetime import datetime
        uploaded_files = []
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'excel_uploads')
        if os.path.exists(upload_dir):
            for fname in os.listdir(upload_dir):
                fpath = os.path.join(upload_dir, fname)
                if os.path.isfile(fpath):
                    mtime = os.path.getmtime(fpath)
                    uploaded_files.append({
                        'name': fname,
                        'size': f"{os.path.getsize(fpath) / 1024:.1f} KB",
                        'uploaded_at': datetime.fromtimestamp(mtime),
                    })
        uploaded_files.sort(key=lambda x: x['uploaded_at'], reverse=True)

        context = {
            'reg_form': reg_form,
            'upload_form': upload_form,
            'agniveers': page_obj.object_list,
            'page_obj': page_obj,
            'paginator': paginator,
            'is_paginated': page_obj.has_other_pages(),
            'total_count': Agniveer.objects.count(),
            'search': search,
            'trade_filter': trade_filter,
            'company_filter': company_filter,
            'platoon_filter': platoon_filter,
            'trade_choices': TRADE_CHOICES,
            'batch_no_choices': BATCH_NO_CHOICES,
            'company_choices': COMPANY_CHOICES,
            'platoon_choices': PLATOON_CHOICES,
            'cert_fields': cert_fields,
            'status_choices': Agniveer.STATUS_CHOICES,
            'uploaded_files': uploaded_files,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        action = request.POST.get('action', 'register')

        if action == 'register':
            reg_form = AgniveerRegistrationForm(request.POST, request.FILES)
            # Allow dynamic platoon values generated client-side (e.g., 'T2')
            submitted_platoon = request.POST.get('platoon')
            if submitted_platoon:
                # Replace platoon field with a free-text CharField to accept dynamic values
                try:
                    if 'platoon' in reg_form.fields:
                        reg_form.fields['platoon'] = django_forms.CharField(required=False)
                except Exception:
                    pass
            if reg_form.is_valid():
                agniveer = reg_form.save(commit=False)
                agniveer.registered_by = request.user
                agniveer.save()
                log_action(request.user, 'CREATE',
                           f'Registered Agniveer: {agniveer.enrollment_number}', request)
                messages.success(
                    request,
                    f"✅ Agniveer '{agniveer.name}' registered successfully. "
                    f"Enrollment No: {agniveer.enrollment_number}"
                )
                return redirect('departments:registration_dashboard')
            else:
                upload_form = AgniveerExcelUploadForm()
                agniveers = Agniveer.objects.all().order_by('-created_at')
                
                cert_fields = [
                    {'name': 'afmsf_2a', 'label': 'AFMSF-2A'},
                    {'name': 'review_cert', 'label': 'Review Cert'},
                    {'name': 'edn_cert', 'label': 'EDN Cert'},
                    {'name': 'verification_roll', 'label': 'Verification Roll'},
                    {'name': 'character_cert', 'label': 'Character Cert'},
                    {'name': 'unmarried_cert', 'label': 'Unmarried Cert'},
                    {'name': 'caste_cert', 'label': 'Caste Cert'},
                    {'name': 'domicile_cert', 'label': 'Domicile Cert'},
                    {'name': 'outside_sanction_letter', 'label': 'Sanction Letter'},
                    {'name': 'willingness_cert', 'label': 'Willingness Cert'},
                    {'name': 'ncc_cert', 'label': 'NCC Cert'},
                    {'name': 'pan_card', 'label': 'PAN Card'},
                    {'name': 'aadhar_card', 'label': 'Aadhar Card'},
                ]

                messages.error(request, "❌ Please fix the errors in the registration form.")
                return render(request, self.template_name, {
                    'reg_form': reg_form,
                    'upload_form': upload_form,
                    'agniveers': agniveers,
                    'total_count': Agniveer.objects.count(),
                    'trade_choices': TRADE_CHOICES,
                    'batch_no_choices': BATCH_NO_CHOICES,
                    'company_choices': COMPANY_CHOICES,
                    'platoon_choices': PLATOON_CHOICES,
                    'active_tab': 'register',
                    'cert_fields': cert_fields,
                    'status_choices': Agniveer.STATUS_CHOICES,
                })

        return redirect('departments:registration_dashboard')


class AgniveerBulkUploadView(RegistrationOfficeMixin, View):
    """Handle Excel bulk upload for Agniveer registration."""

    def post(self, request):
        upload_form = AgniveerExcelUploadForm(request.POST, request.FILES)
        if not upload_form.is_valid():
            messages.error(request, "Please select a valid Excel file.")
            return redirect('departments:registration_dashboard')

        file_obj = request.FILES['excel_file']
        
        # Save Excel file to storage
        import os
        from django.conf import settings
        from django.core.files.storage import FileSystemStorage
        
        fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'excel_uploads'))
        filename = fs.save(file_obj.name, file_obj)

        from .utils import parse_agniveer_excel
        
        # Open and parse the saved file
        with fs.open(filename, 'rb') as f:
            records, errors = parse_agniveer_excel(f)

        created_count = 0
        skip_errors = list(errors)

        for data in records:
            agniveer_no = data.get('agniveer_no', '')
            if Agniveer.objects.filter(agniveer_no=agniveer_no).exists():
                skip_errors.append(f"Agniveer No '{agniveer_no}' already exists — skipped.")
                continue
            try:
                ag = Agniveer(**data)
                ag.registered_by = request.user
                ag.save()
                created_count += 1
            except Exception as e:
                skip_errors.append(f"Could not save '{agniveer_no}': {e}")

        if created_count:
            log_action(request.user, 'CREATE',
                       f'Bulk uploaded {created_count} Agniveers via Excel', request)
            messages.success(request, f"✅ {created_count} Agniveer(s) registered from Excel.")
        if skip_errors:
            for err in skip_errors[:10]:
                messages.warning(request, err)

        return redirect('departments:registration_dashboard')


class DeleteUploadedFileView(RegistrationOfficeMixin, View):
    """Delete an uploaded Excel file from storage."""

    def post(self, request, filename):
        import os
        from django.conf import settings
        
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'excel_uploads')
        safe_filename = os.path.basename(filename)
        fpath = os.path.join(upload_dir, safe_filename)
        
        if os.path.exists(fpath):
            os.remove(fpath)
            messages.success(request, f"Deleted file {safe_filename} successfully.")
        else:
            messages.error(request, "File not found.")
            
        return redirect('departments:registration_dashboard')


class AgniveerExcelTemplateView(RegistrationOfficeMixin, View):
    """Download blank Excel template with correct headers."""

    def get(self, request):
        from .utils import generate_excel_template
        wb = generate_excel_template()
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        response = HttpResponse(
            buffer.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="agniveer_registration_template.xlsx"'
        return response


class AgniveerEditAjaxView(RegistrationOfficeMixin, View):
    """
    GET  → return JSON of agniveer fields for pre-filling the edit modal
    POST → save changes and return JSON result
    """

    def get(self, request, pk):
        ag = get_object_or_404(Agniveer, pk=pk)
        data = {
            'id': ag.pk,
            'enrollment_number': ag.enrollment_number,
            'agniveer_no': ag.agniveer_no,
            'name': ag.name,
            'father_name': ag.father_name,
            'dor': ag.dor.isoformat() if ag.dor else '',
            'trade': ag.trade,
            'aros_bros': ag.aros_bros or '',
            'bn_desp': ag.bn_desp or '',
            'batch_no': ag.batch_no or '',
            'company': ag.company or '',
            'platoon': ag.platoon or '',
            'relationship': ag.relationship or '',
            'afmsf_2a': ag.afmsf_2a,
            'review_cert': ag.review_cert,
            'edn_ql_enrollment': ag.edn_ql_enrollment or '',
            'higher_edn_qualification': ag.higher_edn_qualification or '',
            'edn_cert': ag.edn_cert,
            'verification_roll': ag.verification_roll,
            'character_cert': ag.character_cert,
            'unmarried_cert': ag.unmarried_cert,
            'caste_cert': ag.caste_cert,
            'class_field': ag.class_field or '',
            'domicile_cert': ag.domicile_cert,
            'outside_sanction_letter': ag.outside_sanction_letter,
            'willingness_cert': ag.willingness_cert,
            'ncc_cert': ag.ncc_cert,
            'additional_cert': ag.additional_cert or '',
            'pan_card': ag.pan_card,
            'aadhar_card': ag.aadhar_card,
            'remarks': ag.remarks or '',
            'status': ag.status,
            'rank': ag.rank or '',
            'photo': ag.photo.url if ag.photo else '',
        }
        return JsonResponse(data)

    def post(self, request, pk):
        ag = get_object_or_404(Agniveer, pk=pk)
        form = AgniveerEditForm(request.POST, request.FILES, instance=ag)
        # Allow dynamic platoon values generated client-side by replacing with CharField
        submitted_platoon = request.POST.get('platoon')
        if submitted_platoon:
            try:
                if 'platoon' in form.fields:
                    form.fields['platoon'] = django_forms.CharField(required=False)
            except Exception:
                pass
        if form.is_valid():
            form.save()
            log_action(request.user, 'UPDATE',
                       f'Updated Agniveer: {ag.enrollment_number}', request)
            return JsonResponse({'success': True, 'message': 'Agniveer updated successfully.'})
        else:
            errors = {field: list(errs) for field, errs in form.errors.items()}
            return JsonResponse({'success': False, 'errors': errors}, status=400)


# ── Existing Views (unchanged) ─────────────────────────────────────────────────

class AgniveerListView(AnyStaffMixin, ListView):
    model = Agniveer
    template_name = 'departments/agniveer_list.html'
    context_object_name = 'agniveers'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        queryset = Agniveer.objects.select_related('registered_by')
        dept = user.get_department_code()

        # TTS (Dept B) Specific Filtering
        if dept == 'B' and hasattr(user, 'tts_trade'):
            if user.tts_trade == 'DMV':
                queryset = queryset.filter(trade='DMV')
            elif user.tts_trade == 'OPEM':
                queryset = queryset.filter(trade='OPEM')
            elif user.tts_trade == 'OTHER':
                queryset = queryset.exclude(trade__in=['DMV', 'OPEM'])
                # Allow trade filter for 'OTHER' login
                trade_param = self.request.GET.get('trade')
                if trade_param:
                    queryset = queryset.filter(trade=trade_param)

        # Clerk AV dashboard shows only Clerk trade Agniveers.
        if user.get_department_code() == 'D':
            queryset = queryset.filter(trade__in=['CLK', 'CLERK', 'Clerk', 'CLK_SD', 'CLK_IM'])

        # Battalion Level Isolation
        if user.is_battalion and user.battalion_unit:
            queryset = queryset.filter(bn_desp=user.battalion_unit)

        # Company/Platoon Level Isolation
        if not user.can_view_all:
            if hasattr(user, 'company') and user.company:
                queryset = queryset.filter(company=user.company)
            if hasattr(user, 'platoon') and user.platoon:
                queryset = queryset.filter(platoon=user.platoon)

        status = self.request.GET.get('status')
        search = self.request.GET.get('search')
        batch = self.request.GET.get('batch')
        batch_no = self.request.GET.get('batch_no')
        eval_filter = self.request.GET.get('eval_status')
        trade_param = self.request.GET.get('trade')
        battalion_param = self.request.GET.get('battalion')
        company_param = self.request.GET.get('company')
        platoon_param = self.request.GET.get('platoon')

        if status:
            queryset = queryset.filter(status=status)
        if batch:
            queryset = queryset.filter(batch__icontains=batch)
        if batch_no:
            queryset = queryset.filter(batch_no=batch_no)
        if search:
            queryset = queryset.filter(
                Q(enrollment_number__icontains=search) |
                Q(agniveer_no__icontains=search) |
                Q(name__icontains=search) |
                Q(father_name__icontains=search)
            )
        if trade_param:
            # For TTS (Dept B) 'OTHER' login, trade filter is already applied, so avoid double-filtering
            if not (dept == 'B' and hasattr(user, 'tts_trade') and user.tts_trade == 'OTHER'):
                queryset = queryset.filter(trade=trade_param)
        if battalion_param:
            queryset = queryset.filter(bn_desp=battalion_param)
        if company_param:
            queryset = queryset.filter(company=company_param)
        if platoon_param:
            queryset = queryset.filter(platoon=platoon_param)

        if eval_filter and user.is_department:
            from evaluation.models import Marks
            from evaluation.constants import get_dept_config
            config = get_dept_config(dept or 'A', user)
            test_types = [test[0] for test in config['test_types']]

            evaluated_ids = EvaluationSheet.objects.filter(
                department=dept,
                test_type__in=test_types,
                marks__isnull=False,
            ).values('agniveer_id').annotate(
                completed=Count('test_type', distinct=True)
            ).filter(completed__gte=len(test_types)).values_list('agniveer_id', flat=True)

            if eval_filter == 'evaluated':
                queryset = queryset.filter(pk__in=evaluated_ids)
            elif eval_filter == 'not_evaluated':
                queryset = queryset.exclude(pk__in=evaluated_ids)

        return queryset.order_by('enrollment_number')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = Agniveer.STATUS_CHOICES
        ctx['batch_no_choices'] = BATCH_NO_CHOICES
        ctx['bn_choices'] = BN_DESP_CHOICES
        ctx['trade_choices'] = TRADE_CHOICES
        ctx['company_choices'] = COMPANY_CHOICES
        ctx['platoon_choices'] = PLATOON_CHOICES
        user = self.request.user
        dept = user.get_department_code() or 'A'

        dept_names = {'A': 'Battalion', 'B': 'TTS', 'C': 'CS', 'D': 'Clerk AV'}
        ctx['portal_title'] = f"{dept_names.get(dept, 'Agniveer')} Dashboard"
        ctx['portal_subtitle'] = f"Manage {dept_names.get(dept, 'Agniveer')} evaluation records"
        if user.is_registration_office:
            ctx['portal_title'] = "Agniveer Registration Dashboard"
            ctx['portal_subtitle'] = "Manage individual and bulk Agniveer registrations"

        if user.is_department:
            from evaluation.models import EvaluationSheet, Marks
            from evaluation.constants import get_dept_config

            config = get_dept_config(dept, user)
            total_test_types = len(config['test_types'])

            sheets = EvaluationSheet.objects.filter(
                department=dept,
                test_type__in=[test[0] for test in config['test_types']],
                marks__isnull=False,
            ).values('agniveer_id', 'test_type').distinct()

            from collections import defaultdict
            eval_count = defaultdict(int)
            for s in sheets:
                eval_count[s['agniveer_id']] += 1

            for ag in ctx['agniveers']:
                count = eval_count.get(ag.pk, 0)
                ag.eval_count = count
                ag.eval_total = total_test_types
                ag.is_fully_evaluated = count >= total_test_types

            ctx['eval_filter'] = self.request.GET.get('eval_status', '')

        # TTS specific context
        if user.get_department_code() == 'B':
            ctx['tts_trade'] = getattr(user, 'tts_trade', None)
            if ctx['tts_trade'] == 'OTHER':
                ctx['technical_trades'] = [
                    t for t in TRADE_CHOICES 
                    if t[0] not in ['DMV', 'OPEM', 'Other']
                ]
                ctx['trade_filter'] = self.request.GET.get('trade', '')

        return ctx


class AgniveerCreateView(RegistrationOfficeMixin, CreateView):
    model = Agniveer
    form_class = AgniveerForm
    template_name = 'departments/agniveer_form.html'
    success_url = reverse_lazy('departments:agniveer_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Register New Agniveer'
        ctx['action'] = 'Register'
        return ctx

        return redirect('departments:registration_dashboard')


class AgniveerUpdateView(AgniveerEditMixin, UpdateView):
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
        log_action(self.request.user, 'UPDATE',
                   f'Updated Agniveer: {agniveer.enrollment_number}', self.request)
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

        if user.is_department:
            evaluations = evaluations.filter(department=department)

        ctx['evaluations'] = evaluations

        from evaluation.constants import CS_CLERK_RESULT_TRADES, get_dept_total_marks, get_dept_config, get_overall_total_marks

        config = get_dept_config(department, user)
        test_type_choices = config['test_types']
        if department == 'C':
            if agniveer.trade in CS_CLERK_RESULT_TRADES:
                hidden_tests = {'CS_RESULT'}
            else:
                hidden_tests = {'CS_CLERK_RESULT'}
            test_type_choices = [test for test in test_type_choices if test[0] not in hidden_tests]

        if user.is_commander or user.is_g_head:
            total_score = sum(e.get_total_marks() for e in evaluations)
            max_marks = sum(e.get_max_marks() for e in evaluations)
            if max_marks == 0:
                max_marks = get_overall_total_marks(user)
        else:
            total_score = sum(e.get_total_marks() for e in evaluations.filter(department=department))
            max_marks = sum(e.get_max_marks() for e in evaluations.filter(department=department))
            if max_marks == 0:
                max_marks = config.get('total_marks', 300)

        percentage = (total_score / max_marks * 100) if max_marks > 0 else 0

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
        # Editability: department users could evaluate via the profile UI.
        # Department heads, G-Head and Commander behavior is handled elsewhere.
        ctx['can_evaluate'] = user.is_department

        import json
        ctx['dept_config'] = config
        ctx['category_choices'] = config['categories']
        ctx['test_type_choices'] = test_type_choices
        ctx['test_to_category_json'] = json.dumps(config['test_to_category'])
        ctx['evaluation_form'] = AgniveerEvaluationForm(department=department)
        # Dynamic marks for Battalion Final Result
        from evaluation.result_helpers import get_ces_final_marks, get_btt_final_marks
        ctx['dynamic_ces_marks'] = get_ces_final_marks(agniveer)
        ctx['dynamic_btt_marks'] = get_btt_final_marks(agniveer)

        return ctx


class AssignTrainerView(CommanderOrDeptMixin, UpdateView):
    def get(self, request, *args, **kwargs):
        messages.info(request, "Trainers are now automatically assigned to all agniveers in their department.")
        return redirect('departments:agniveer_list')

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)
