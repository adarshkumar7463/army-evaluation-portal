"""
Reports App - Views
PDF, Excel, and CSV export functionality with department-specific access control
"""

import csv
import io
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, FileResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.utils import timezone
from django.db.models import Q, Sum, F, Value, FloatField
from django.db.models.functions import Coalesce

from departments.models import Agniveer
from evaluation.models import EvaluationSheet, Marks
from evaluation.result_helpers import build_tts_result_row, build_battalion_result_row, build_department_result_row, build_cs_result_row, build_clerk_result_row
from accounts.models import CustomUser
from accounts.mixins import AnyStaffMixin, CommanderOrGHeadMixin
from logs.utils import log_action


DEPARTMENT_NAMES = {'A': 'Battalion', 'B': 'TTS', 'C': 'CS', 'D': 'Clerk'}
CLERK_TRADES = ['CLK', 'CLERK', 'Clerk', 'CLK_SD', 'CLK_IM']
TTS_DIRECT_TRADES = ['DMV', 'OPEM']


def scoped_agniveers(queryset, user, dept=None):
    dept = dept or user.get_department_code()
    if dept == 'A':
        if user.is_department and user.battalion_unit:
            return queryset.filter(bn_desp=user.battalion_unit)
        battalion_units = [choice[0] for choice in CustomUser.BATTALION_CHOICES]
        return queryset.filter(bn_desp__in=battalion_units)
    if dept == 'B':
        if user.is_department and user.tts_trade == 'DMV':
            return queryset.filter(trade='DMV')
        if user.is_department and user.tts_trade == 'OPEM':
            return queryset.filter(trade='OPEM')
        if user.is_department and user.tts_trade == 'OTHER':
            return queryset.exclude(trade__in=TTS_DIRECT_TRADES + CLERK_TRADES)
        return queryset.exclude(trade__in=CLERK_TRADES)
    if dept == 'C':
        return queryset
    if dept == 'D':
        return queryset.filter(trade__in=CLERK_TRADES)
    return queryset


def scoped_sheets(queryset, user, dept=None):
    dept = dept or user.get_department_code()
    queryset = queryset.filter(department=dept)
    if dept == 'A':
        if user.is_department and user.battalion_unit:
            return queryset.filter(agniveer__bn_desp=user.battalion_unit)
        battalion_units = [choice[0] for choice in CustomUser.BATTALION_CHOICES]
        return queryset.filter(agniveer__bn_desp__in=battalion_units)
    if dept == 'B':
        if user.is_department and user.tts_trade == 'DMV':
            return queryset.filter(agniveer__trade='DMV')
        if user.is_department and user.tts_trade == 'OPEM':
            return queryset.filter(agniveer__trade='OPEM')
        if user.is_department and user.tts_trade == 'OTHER':
            return queryset.exclude(agniveer__trade__in=TTS_DIRECT_TRADES)
        return queryset
    if dept == 'D':
        return queryset.filter(agniveer__trade__in=CLERK_TRADES)
    return queryset


def user_can_access_agniveer(user, agniveer, dept=None):
    return scoped_agniveers(Agniveer.objects.filter(pk=agniveer.pk), user, dept).exists()


def pass_fail_counts_for_scope(user, dept=None):
    from evaluation.result_helpers import is_sheet_evaluated
    departments = [dept] if dept else ['A', 'B', 'C', 'D']
    all_sheets = EvaluationSheet.objects.all().prefetch_related('marks')

    if dept:
        all_sheets = scoped_sheets(all_sheets, user, dept)
        agniveers = scoped_agniveers(Agniveer.objects.all(), user, dept)
    else:
        agniveers = Agniveer.objects.all()

    passed = 0
    failed = 0
    for agniveer in agniveers:
        total_marks = 0
        max_marks = 0
        for dept_code in departments:
            dept_sheets = [s for s in all_sheets.filter(agniveer=agniveer, department=dept_code) if is_sheet_evaluated(s)]
            if not dept_sheets:
                continue
            result_row = build_department_result_row(agniveer, dept_sheets, dept_code)
            total_marks += result_row.get('grand_total', 0) or 0
            max_marks += result_row.get('max_total') or 40
        if max_marks <= 0:
            continue
        percentage = (total_marks / max_marks) * 100
        passing_threshold = 40 if 'A' in departments and len(departments) == 1 else 50
        if percentage >= passing_threshold:
            passed += 1
        else:
            failed += 1

    return {
        'evaluated': passed + failed,
        'passed': passed,
        'failed': failed,
    }

# Department-specific access mixins
class TTSTradeHeadMixin(UserPassesTestMixin):
    """Allow access only to TTS Trade Head users"""
    def test_func(self):
        return self.request.user.is_authenticated and getattr(self.request.user, 'tts_trade', None) is not None

class BattalionHeadMixin(UserPassesTestMixin):
    """Allow access only to Battalion Head users"""
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_battalion

class CSHeadMixin(UserPassesTestMixin):
    """Allow access only to CS head users"""
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role == CustomUser.ROLE_DEPT_C

class ClerkHeadMixin(UserPassesTestMixin):
    """Allow access only to Clerk head users"""
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role == CustomUser.ROLE_DEPT_D


class ReportDashboardView(AnyStaffMixin, View):
    template_name = 'reports/report_dashboard.html'

    def get(self, request):
        user = request.user
        context = {}
        
        if user.is_commander or user.is_g_head:
            # Commander/G-Head sees ALL departments
            context['user_role'] = 'commander_ghead'
            context['show_all_departments'] = True
            context['report_departments'] = ['A', 'B', 'C', 'D']
            
            # Get data for all departments
            dept_data = {}
            for dept_code, dept_name in DEPARTMENT_NAMES.items():
                counts = pass_fail_counts_for_scope(user, dept_code)
                dept_data[dept_code] = {
                    'name': dept_name,
                    'total_agniveers': scoped_agniveers(Agniveer.objects.all(), user, dept_code).count(),
                    'evaluated_agniveers': counts['evaluated'],
                    'pass_count': counts['passed'],
                    'fail_count': counts['failed'],
                    'total_trainers': CustomUser.objects.filter(
                        role__in=[CustomUser.ROLE_TRAINER_NCO, CustomUser.ROLE_TRAINER_JCO, CustomUser.ROLE_TRAINER_OFFICER],
                        department=dept_code
                    ).count()
                }
            context['department_data'] = dept_data
            
            # Overall totals
            counts = pass_fail_counts_for_scope(user)
            context['total_agniveers'] = Agniveer.objects.count()
            context['total_trainers'] = CustomUser.objects.filter(
                role__in=[CustomUser.ROLE_TRAINER_NCO, CustomUser.ROLE_TRAINER_JCO, CustomUser.ROLE_TRAINER_OFFICER]
            ).count()
            context['evaluated_agniveers'] = counts['evaluated']
            context['pass_count'] = counts['passed']
            context['fail_count'] = counts['failed']
            
        elif user.is_department:
            dept = user.get_department_code()
            context['user_role'] = f'department_{dept}'
            context['department_code'] = dept
            context['department_name'] = DEPARTMENT_NAMES.get(dept, dept)
            context['report_departments'] = [dept]

            context['is_department_head'] = True
            if dept == 'A':
                context['head_type'] = 'battalion'
            elif dept == 'B':
                context['head_type'] = 'tts'
                context['tts_trade'] = user.tts_trade
            elif dept == 'C':
                context['head_type'] = 'cs'
            elif dept == 'D':
                context['head_type'] = 'clerk'

            agniveers = scoped_agniveers(Agniveer.objects.all(), user, dept)
            counts = pass_fail_counts_for_scope(user, dept)
            
            context['total_agniveers'] = agniveers.count()
            context['total_trainers'] = CustomUser.objects.filter(
                role__in=[CustomUser.ROLE_TRAINER_NCO, CustomUser.ROLE_TRAINER_JCO, CustomUser.ROLE_TRAINER_OFFICER],
                department=dept
            ).count()
            context['evaluated_agniveers'] = counts['evaluated']
            context['pass_count'] = counts['passed']
            context['fail_count'] = counts['failed']
        else:
            # Non-department users (trainers hidden): provide empty/default report data
            context['user_role'] = 'trainer'
            context['report_departments'] = []
            context['total_agniveers'] = 0
            context['total_trainers'] = 0
            context['pass_count'] = 0
            context['evaluated_agniveers'] = 0

        context['fail_count'] = context.get('fail_count', 0)

        return render(request, self.template_name, context)


# Department-specific report card views
class TTSReportCardView(TTSTradeHeadMixin, View):
    """TTS Trade Head sees report cards for their specific trade only"""
    template_name = 'reports/tts_report_card.html'
    
    def get(self, request):
        user = request.user
        tts_trade = user.tts_trade
        
        # Filter agniveers by trade
        if tts_trade == 'DMV':
            agniveers = Agniveer.objects.filter(trade='DMV')
        elif tts_trade == 'OPEM':
            agniveers = Agniveer.objects.filter(trade='OPEM')
        else:  # OTHER
            agniveers = Agniveer.objects.exclude(trade__in=['DMV', 'OPEM'])
        
        sheets = EvaluationSheet.objects.filter(
            department='B', 
            is_locked=True,
            agniveer__in=agniveers
        ).select_related('agniveer').prefetch_related('marks')
        
        # Build result rows using existing TTS result helper
        result_rows = []
        for agniveer in agniveers:
            ag_sheets = list(sheets.filter(agniveer=agniveer))
            if ag_sheets:
                row = build_tts_result_row(agniveer, ag_sheets)
                result_rows.append(row)
        
        return render(request, self.template_name, {
            'result_rows': result_rows,
            'trade': tts_trade,
            'department_name': 'TTS',
        })


class BattalionReportCardView(BattalionHeadMixin, View):
    """Battalion Head sees report cards for their battalion unit only"""
    template_name = 'reports/battalion_report_card.html'
    
    def get(self, request):
        user = request.user
        battalion_unit = user.battalion_unit
        
        # Filter agniveers by battalion unit
        if battalion_unit:
            agniveers = Agniveer.objects.filter(bn_desp=battalion_unit)
        else:
            battalion_units = [choice[0] for choice in CustomUser.BATTALION_CHOICES]
            agniveers = Agniveer.objects.filter(bn_desp__in=battalion_units)
        
        sheets = EvaluationSheet.objects.filter(
            department='A', 
            is_locked=True,
            agniveer__in=agniveers
        ).select_related('agniveer').prefetch_related('marks')
        
        # Build result rows using existing Battalion result helper
        result_rows = []
        for agniveer in agniveers:
            ag_sheets = list(sheets.filter(agniveer=agniveer))
            if ag_sheets:
                row = build_battalion_result_row(agniveer, ag_sheets)
                result_rows.append(row)
        
        return render(request, self.template_name, {
            'result_rows': result_rows,
            'battalion_unit': battalion_unit,
            'department_name': 'Battalion',
        })


class CSReportCardView(CSHeadMixin, View):
    """CS Head sees report cards (loads report card without schema for now)"""
    template_name = 'reports/cs_report_card.html'
    
    def get(self, request):
        agniveers = Agniveer.objects.filter(evaluations__department='C').distinct()
        
        return render(request, self.template_name, {
            'agniveers': agniveers,
            'department_name': 'CS (Communication Systems)',
            'message': 'CS report card schema will be implemented soon.',
        })


class ClerkReportCardView(ClerkHeadMixin, View):
    """Clerk Head sees report cards (loads report card without schema for now)"""
    template_name = 'reports/clerk_report_card.html'
    
    def get(self, request):
        agniveers = Agniveer.objects.filter(trade__in=CLERK_TRADES)
        
        return render(request, self.template_name, {
            'agniveers': agniveers,
            'department_name': 'Clerk Department',
            'message': 'Clerk report card schema will be implemented soon.',
        })


# Report Card Detail View (Individual Agniveer)
class ReportCardDetailView(AnyStaffMixin, View):
    """Individual report card view with department-based access control"""
    template_name = 'reports/report_card_detail.html'
    
    def get(self, request, pk):
        agniveer = get_object_or_404(Agniveer, pk=pk)
        user = request.user
        
        # Access control: Check if user has permission to view this agniveer's report
        has_access = False
        is_department_view = False
        user_dept = None
        
        if user.is_commander or user.is_g_head:
            # Commander/G-Head can see ALL
            has_access = True
            
        elif user.is_department:
            user_dept = user.get_department_code()
            has_access = user_can_access_agniveer(user, agniveer, user_dept)
        
        if not has_access:
            return HttpResponse("You don't have permission to view this report card.", status=403)
        
        # Determine which evaluations to show (department-specific)
        if user.is_commander or user.is_g_head:
            evaluations = EvaluationSheet.objects.filter(agniveer=agniveer).prefetch_related('marks')
            departments_to_show = ['A', 'B', 'C', 'D']
            is_department_view = False
        else:
            user_dept = user.get_department_code()
            evaluations = scoped_sheets(
                EvaluationSheet.objects.filter(agniveer=agniveer).prefetch_related('marks'),
                user,
                user_dept,
            )
            departments_to_show = [user_dept]
            is_department_view = True
        
        # Build department evaluations data
        dept_evaluations = {}
        from evaluation.constants import get_dept_total_marks, get_overall_total_marks
        
        for dept in departments_to_show:
            dept_evals = evaluations.filter(department=dept)
            if dept_evals.exists():
                dept_evaluations[dept] = {
                    'on_field': dept_evals.filter(category='on_field'),
                    'trade': dept_evals.filter(category='trade'),
                    'total_marks': sum(e.get_total_marks() for e in dept_evals),
                    'max_marks': get_dept_total_marks(dept),
                }
        
        # Calculate overall scores
        grand_total = sum(e.get_total_marks() for e in evaluations)
        max_total = get_dept_total_marks(user_dept) if is_department_view else get_overall_total_marks()
        percentage = round((grand_total / max_total * 100), 2) if max_total > 0 else 0
        passing_threshold = 40 if is_department_view and user_dept == 'A' else 50
        overall_pass = percentage >= passing_threshold
        
        # For TTS department, also build TTS result row
        tts_result_row = None
        if not is_department_view or user_dept == 'B':
            tts_sheets = evaluations.filter(department='B')
            if tts_sheets.exists():
                tts_result_row = build_tts_result_row(agniveer, list(tts_sheets))
        
        battalion_result_row = None
        if not is_department_view or user_dept == 'A':
            battalion_sheets = evaluations.filter(department='A')
            if battalion_sheets.exists():
                battalion_result_row = build_battalion_result_row(agniveer, list(battalion_sheets))
        
        return render(request, self.template_name, {
            'agniveer': agniveer,
            'dept_evaluations': dept_evaluations,
            'grand_total': grand_total,
            'max_total': max_total,
            'percentage': percentage,
            'overall_pass': overall_pass,
            'is_department_view': is_department_view,
            'user_department_name': DEPARTMENT_NAMES.get(user_dept, '') if is_department_view else None,
            'tts_result_row': tts_result_row,
            'battalion_result_row': battalion_result_row,
        })

class ExportAgniveersCSVView(AnyStaffMixin, View):
    def get(self, request):
        user = request.user
        if user.is_commander or user.is_g_head:
            agniveers = Agniveer.objects.all()
        elif user.is_department:
            agniveers = scoped_agniveers(Agniveer.objects.all(), user)
        else:
            agniveers = Agniveer.objects.none()

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="agniveers.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Enrollment No', 'Name', 'Department', 'Batch',
            'Joining Date', 'Status', 'Total Score', 'Pass/Fail'
        ])

        for a in agniveers:
            dept_codes = list(
                a.evaluations.values_list('department', flat=True).distinct()
            )
            department_text = ', '.join(DEPARTMENT_NAMES.get(dept, dept) for dept in dept_codes)
            writer.writerow([
                a.enrollment_number,
                a.get_full_name(),
                DEPARTMENT_NAMES.get(user.get_department_code(), '') if user.is_department else department_text,
                a.batch,
                a.joining_date.strftime('%Y-%m-%d') if a.joining_date else '',
                a.get_status_display(),
                a.get_total_score(),
                a.get_pass_status(),
            ])

        log_action(user, 'EXPORT', 'Exported Agniveers CSV', request)
        return response


class ExportEvaluationsCSVView(AnyStaffMixin, View):
    def get(self, request):
        user = request.user
        sheets = EvaluationSheet.objects.filter(is_locked=True).select_related('agniveer').prefetch_related('marks')

        if user.is_department:
            sheets = scoped_sheets(sheets, user)
        else:
            sheets = EvaluationSheet.objects.none()

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="evaluations.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Enrollment No', 'Name', 'Department', 'Category', 'Test Type',
            'NCO Marks', 'JCO Marks', 'Officer Marks', 'Total', 'Percentage', 'Result'
        ])

        for sheet in sheets:
            writer.writerow([
                sheet.agniveer.enrollment_number,
                sheet.agniveer.get_full_name(),
                DEPARTMENT_NAMES.get(sheet.department, sheet.department),
                sheet.get_category_display(),
                sheet.get_test_type_display(),
                sheet.get_nco_marks(),
                sheet.get_jco_marks(),
                sheet.get_officer_marks(),
                sheet.get_total_marks(),
                f'{sheet.get_percentage()}%',
                'Pass' if sheet.is_pass() else 'Fail',
            ])

        log_action(user, 'EXPORT', 'Exported Evaluations CSV', request)
        return response


class ExportExcelView(AnyStaffMixin, View):
    def get(self, request):
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        except ImportError:
            return HttpResponse("openpyxl not installed. Run: pip install openpyxl", status=500)

        user = request.user
        sheets = EvaluationSheet.objects.filter(is_locked=True).select_related('agniveer').prefetch_related('marks')

        if user.is_department:
            sheets = scoped_sheets(sheets, user)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Evaluation Report"

        # Styling
        header_fill = PatternFill(start_color="1B4332", end_color="1B4332", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True, size=11)
        pass_fill = PatternFill(start_color="D4EDDA", end_color="D4EDDA", fill_type="solid")
        fail_fill = PatternFill(start_color="F8D7DA", end_color="F8D7DA", fill_type="solid")
        center = Alignment(horizontal='center', vertical='center')

        # Title row
        ws.merge_cells('A1:P1')
        title_cell = ws['A1']
        title_cell.value = "ARMY EVALUATION PORTAL - EVALUATION REPORT"
        title_cell.font = Font(bold=True, size=14, color="1B4332")
        title_cell.alignment = center
        ws.row_dimensions[1].height = 30

        # Headers
        headers = [
            'S.No', 'ARMY NO', 'RANK', 'TRADE', 'NAME', 'UNIT', 'Enrollment No', 'Department', 'Category',
            'Test Type', 'NCO (20)', 'JCO (20)', 'Officer (20)',
            'Total (60)', 'Percentage', 'Result'
        ]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=2, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center

        # Data rows
        for row_idx, sheet in enumerate(sheets, 1):
            is_pass = sheet.is_pass()
            row_fill = pass_fill if is_pass else fail_fill
            data = [
                row_idx,
                sheet.agniveer.agniveer_no or sheet.agniveer.enrollment_number,
                getattr(sheet.agniveer, 'rank', '') or '',
                sheet.agniveer.trade or '',
                sheet.agniveer.get_full_name(),
                sheet.agniveer.bn_desp or '',
                sheet.agniveer.enrollment_number,
                DEPARTMENT_NAMES.get(sheet.department, sheet.department),
                sheet.get_category_display(),
                sheet.get_test_type_display(),
                sheet.get_nco_marks(),
                sheet.get_jco_marks(),
                sheet.get_officer_marks(),
                sheet.get_total_marks(),
                f"{sheet.get_percentage()}%",
                'PASS' if is_pass else 'FAIL',
            ]
            for col, value in enumerate(data, 1):
                cell = ws.cell(row=row_idx + 2, column=col, value=value)
                cell.fill = row_fill
                cell.alignment = center

        # Auto-size columns
        col_widths = [5, 15, 10, 10, 20, 10, 15, 12, 18, 16, 10, 10, 12, 12, 12, 8]
        for i, width in enumerate(col_widths, 1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = width

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        log_action(user, 'EXPORT', 'Exported Excel Report', request)
        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="evaluation_report.xlsx"'
        return response


class ExportDashboardResultsExcelView(AnyStaffMixin, View):
    def _export_battalion_results(self, request, status_filter, sub_dept=None):
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from django.db.models import Q
        from evaluation.models import Marks, EvaluationSheet
        from evaluation.result_helpers import build_battalion_result_row
        from departments.models import Agniveer

        from evaluation.result_helpers import is_sheet_evaluated
        user = request.user
        is_pass_filter = status_filter == 'pass'

        agniveers = Agniveer.objects.all()
        sheets = EvaluationSheet.objects.all().select_related('agniveer').prefetch_related('marks')

        unit_filter = sub_dept
        if not unit_filter and user.is_battalion and user.battalion_unit:
            unit_filter = user.battalion_unit

        if unit_filter and unit_filter != 'all':
            agniveers = agniveers.filter(bn_desp=unit_filter)
            sheets = sheets.filter(agniveer__bn_desp=unit_filter)

        from collections import defaultdict
        sheets_by_agniveer = defaultdict(list)
        for s in sheets:
            if is_sheet_evaluated(s):
                sheets_by_agniveer[s.agniveer_id].append(s)

        rows = []
        for agniveer in agniveers.order_by('agniveer_no', 'enrollment_number'):
            ag_sheets = sheets_by_agniveer.get(agniveer.id, [])
            if not ag_sheets and is_pass_filter:
                continue
            row = build_battalion_result_row(agniveer, ag_sheets)
            if row['is_pass'] == is_pass_filter:
                rows.append(row)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"BN {status_filter.upper()}"

        pass_fill = PatternFill(start_color="DDF4E8", end_color="DDF4E8", fill_type="solid")
        fail_fill = PatternFill(start_color="FCE4E4", end_color="FCE4E4", fill_type="solid")
        row_fill = pass_fill if status_filter == 'pass' else fail_fill

        header_fill = PatternFill(start_color="D9EAF7", end_color="D9EAF7", fill_type="solid")
        title_fill = PatternFill(start_color="EAF2F8", end_color="EAF2F8", fill_type="solid")
        border = Border(
            left=Side(style='thin', color='B7C4B7'),
            right=Side(style='thin', color='B7C4B7'),
            top=Side(style='thin', color='B7C4B7'),
            bottom=Side(style='thin', color='B7C4B7'),
        )
        center = Alignment(horizontal='center', vertical='center', wrap_text=True)

        headers = [
            'ARMY NO', 'RANK', 'TRADE', 'NAME',
            'COMMON MIL KNOWLEDGE (20)', 'BASIC TACTICE (CES) (40)',
            'TRADE PROFICIENCY (BTT) (40)', 'WPN & EQPT HANDLING (20)',
            'TOTAL (120)', 'ROUND FIGURE (120)', '%'
        ]
        if status_filter != 'fail':
            headers.append('GRADING')
        
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
        ws.cell(row=1, column=1, value=f"BATTALION SCREENING: {status_filter.upper()} LIST").fill = title_fill
        ws.cell(row=1, column=1).font = Font(bold=True, size=13)
        ws.cell(row=1, column=1).alignment = center

        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=2, column=col, value=header)
            cell.fill = header_fill
            cell.font = Font(bold=True, size=10)
            cell.alignment = center
            cell.border = border

        for index, row in enumerate(rows, 1):
            values = [
                row['army_no'], row['rank'], row['trade'], row['name'],
                row['cmk_20'], row['basic_tac_40'], row['trade_prof_40'], row['wpn_handling_20'],
                row['total_120'], row['round_figure_120'],
                f"{row['percentage']}%" if row['percentage'] else '0%'
            ]
            if status_filter != 'fail':
                values.append(row['grading'])
            for col, value in enumerate(values, 1):
                cell = ws.cell(row=index + 2, column=col, value=value)
                cell.fill = row_fill
                cell.alignment = center
                cell.border = border

        widths = [15, 10, 15, 25, 25, 25, 25, 25, 15, 18, 12]
        if status_filter != 'fail':
            widths.append(15)
        for col, width in enumerate(widths, 1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = width
        ws.freeze_panes = 'A3'

        import io
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        from logs.utils import log_action
        log_action(user, 'EXPORT', f'Exported BN {status_filter} dashboard results Excel', request)
        from django.http import HttpResponse
        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="bn_{status_filter}_results.xlsx"'
        return response

    def _export_tts_results(self, request, status_filter, sub_dept=None):
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from django.db.models import Q
        from evaluation.models import Marks, EvaluationSheet
        from evaluation.result_helpers import build_tts_result_row, _marks_from_sheet, _num, get_grade
        from departments.models import Agniveer

        user = request.user
        is_pass_filter = status_filter == 'pass'
        from evaluation.result_helpers import is_sheet_evaluated
        agniveers = Agniveer.objects.exclude(trade__in=CLERK_TRADES)
        agniveers = scoped_agniveers(agniveers, user, 'B')
        sheets = EvaluationSheet.objects.filter(
            department='B'
        ).select_related('agniveer').prefetch_related('marks')

        trade_filter = sub_dept
        if not trade_filter and getattr(user, 'tts_trade', None):
            trade_filter = user.tts_trade

        if trade_filter and trade_filter != 'all':
            if trade_filter == 'DMV':
                agniveers = agniveers.filter(trade='DMV')
                sheets = sheets.filter(agniveer__trade='DMV')
            elif trade_filter == 'OPEM':
                agniveers = agniveers.filter(trade='OPEM')
                sheets = sheets.filter(agniveer__trade='OPEM')
            elif trade_filter == 'OTHER':
                agniveers = agniveers.exclude(trade__in=['DMV', 'OPEM'] + CLERK_TRADES)
                sheets = sheets.exclude(agniveer__trade__in=['DMV', 'OPEM'] + CLERK_TRADES)
        else:
            agniveers = agniveers.exclude(trade__in=CLERK_TRADES)
            sheets = sheets.exclude(agniveer__trade__in=CLERK_TRADES)

        from collections import defaultdict
        sheets_by_agniveer = defaultdict(list)
        for s in sheets:
            if is_sheet_evaluated(s):
                sheets_by_agniveer[s.agniveer_id].append(s)

        rows = []
        for agniveer in agniveers.order_by('agniveer_no', 'enrollment_number'):
            ag_sheets = sheets_by_agniveer.get(agniveer.id, [])
            if not ag_sheets and is_pass_filter:
                continue
            
            row = build_tts_result_row(agniveer, ag_sheets)
            if row['is_pass'] == is_pass_filter:
                rows.append(row)

        wb = openpyxl.Workbook()
        ws = wb.active

        pass_fill = PatternFill(start_color="DDF4E8", end_color="DDF4E8", fill_type="solid")
        fail_fill = PatternFill(start_color="FCE4E4", end_color="FCE4E4", fill_type="solid")
        row_fill = pass_fill if status_filter == 'pass' else fail_fill

        header_fill = PatternFill(start_color="D9EAF7", end_color="D9EAF7", fill_type="solid")
        title_fill = PatternFill(start_color="EAF2F8", end_color="EAF2F8", fill_type="solid")
        border = Border(
            left=Side(style='thin', color='B7C4B7'),
            right=Side(style='thin', color='B7C4B7'),
            top=Side(style='thin', color='B7C4B7'),
            bottom=Side(style='thin', color='B7C4B7'),
        )
        center = Alignment(horizontal='center', vertical='center', wrap_text=True)

        if trade_filter == 'DMV':
            ws.title = f"DMV {status_filter.upper()}"
            title_text = "Final Result sheet of Dmv"
            headers = [
                'ARMY NO', 'RANK', 'TRADE', 'NAME', 'UNIT',
                'Online Test (100)', 'Practical Test (50)', 'Driving Test (50)',
                'Total (200)', '% Age'
            ]
            if status_filter != 'fail':
                headers.append('Grading')
            headers.extend(['Convert 40 Marks', 'REMARKS'])
        elif trade_filter == 'OPEM':
            ws.title = f"OPEM {status_filter.upper()}"
            title_text = "Final Result sheet of opem"
            headers = [
                'ARMY NO', 'RANK', 'TRADE', 'NAME', 'UNIT',
                'Written Test (100)', 'Practical Test (50)', 'Maintenance Test (50)',
                'Total (200)', '% Age'
            ]
            if status_filter != 'fail':
                headers.append('Grading')
            headers.extend(['Convert 40 Marks', 'REMARKS'])
        else:
            ws.title = f"TTS {status_filter.upper()}"
            title_text = "Screen Board of Agniveer  (TTS Result)"
            headers = [
                'ARMY NO', 'RANK', 'TRADE', 'NAME', 'UNIT',
                'Mid Term Test (50)', 'Convert In 10 Mks (Mid Term)',
                'Online Test (100)', 'Convert In 15 Mks',
                'Job (40)', 'Convert In 05 Mks',
                'Practical (60)', 'Convert In 10 Mks (Practical)',
                'Grand Total (40)', '% Age'
            ]
            if status_filter != 'fail':
                headers.append('Grading')

        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
        ws.cell(row=1, column=1, value=title_text).fill = title_fill
        ws.cell(row=1, column=1).font = Font(bold=True, size=13)
        ws.cell(row=1, column=1).alignment = center

        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=2, column=col, value=header)
            cell.fill = header_fill
            cell.font = Font(bold=True, size=10)
            cell.alignment = center
            cell.border = border

        for index, r in enumerate(rows, 1):
            if trade_filter == 'DMV':
                values = [
                    r['army_no'], r['rank'], r['trade'], r['name'], r['unit'],
                    r['online'], r['practical'], r['job'],
                    r['total_200'], f"{r['percentage']}%" if r['percentage'] else '0%'
                ]
                if status_filter != 'fail':
                    values.append(r['grading'])
                values.extend([r['grand_total'], r['remarks']])
            elif trade_filter == 'OPEM':
                values = [
                    r['army_no'], r['rank'], r['trade'], r['name'], r['unit'],
                    r['online'], r['practical'], r['job'],
                    r['total_200'], f"{r['percentage']}%" if r['percentage'] else '0%'
                ]
                if status_filter != 'fail':
                    values.append(r['grading'])
                values.extend([r['grand_total'], r['remarks']])
            else:
                values = [
                    r['army_no'], r['rank'], r['trade'], r['name'], r['unit'],
                    r['mid_term'], r['mid_term_conv'],
                    r['online'], r['online_conv'],
                    r['job'], r['job_conv'],
                    r['practical'], r['practical_conv'],
                    r['grand_total'], f"{r['percentage']}%" if r['percentage'] else '0%'
                ]
                if status_filter != 'fail':
                    values.append(r['grading'])
            for col, value in enumerate(values, 1):
                cell = ws.cell(row=index + 2, column=col, value=value)
                cell.fill = row_fill
                cell.alignment = center
                cell.border = border

        for col_idx in range(1, len(headers) + 1):
            col_letter = openpyxl.utils.get_column_letter(col_idx)
            max_len = max(len(str(ws.cell(row=r, column=col_idx).value or '')) for r in range(2, len(rows) + 3))
            ws.column_dimensions[col_letter].width = max(max_len + 3, 10)
        ws.freeze_panes = 'A3'

        import io
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        log_action(user, 'EXPORT', f'Exported TTS {status_filter} dashboard results Excel', request)
        from django.http import HttpResponse
        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="tts_{status_filter}_results.xlsx"'
        return response

    def _export_cs_results(self, request, status_filter, sub_dept=None):
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from django.db.models import Q
        from evaluation.models import Marks, EvaluationSheet
        from evaluation.result_helpers import build_cs_result_row, _marks_from_sheet, _num, get_grade
        from departments.models import Agniveer
        import io

        user = request.user
        is_pass_filter = status_filter == 'pass'
        from evaluation.result_helpers import is_sheet_evaluated
        agniveers = Agniveer.objects.all()
        agniveers = scoped_agniveers(agniveers, user, 'C')
        
        sheets = EvaluationSheet.objects.filter(
            department='C'
        ).select_related('agniveer').prefetch_related('marks')

        if sub_dept and sub_dept != 'all':
            agniveers = agniveers.filter(bn_desp=sub_dept)
            sheets = sheets.filter(agniveer__bn_desp=sub_dept)

        cs_final_rows = []
        cs_clerk_rows = []

        from evaluation.constants import CS_CLERK_RESULT_TRADES

        from collections import defaultdict
        sheets_by_agniveer = defaultdict(list)
        for s in sheets:
            if is_sheet_evaluated(s):
                sheets_by_agniveer[s.agniveer_id].append(s)

        for agniveer in agniveers.order_by('agniveer_no', 'enrollment_number'):
            ag_sheets = sheets_by_agniveer.get(agniveer.id, [])
            if not ag_sheets and is_pass_filter:
                continue
            
            sheet_map = {s.test_type: s for s in ag_sheets}
            
            if agniveer.trade in CS_CLERK_RESULT_TRADES:
                result_sheet = sheet_map.get('CS_CLERK_RESULT')
                if not result_sheet:
                    if not is_pass_filter:
                        cs_clerk_rows.append({
                            'rank': getattr(agniveer, 'rank', '') or '',
                            'trade': agniveer.trade or '',
                            'name': agniveer.get_full_name(),
                            'pl': agniveer.platoon or '',
                            'bn': agniveer.bn_desp or '',
                            'online': 0.0,
                            'prac': 0.0,
                            'total': 0.0,
                            'remarks': 'No evaluation'
                        })
                    continue
                marks = _marks_from_sheet(result_sheet)
                online = _num(marks.get('Online (20)'))
                prac = _num(marks.get('TPrac (20)'))
                total = _num(marks.get('Total (40)')) or (online + prac)
                percentage = round((total / 40) * 100, 2) if total else 0
                is_pass = percentage >= 50
                
                if is_pass == is_pass_filter:
                    cs_clerk_rows.append({
                        'rank': getattr(agniveer, 'rank', '') or '',
                        'trade': agniveer.trade or '',
                        'name': agniveer.get_full_name(),
                        'pl': agniveer.platoon or '',
                        'bn': agniveer.bn_desp or '',
                        'online': online,
                        'prac': prac,
                        'total': total,
                        'remarks': result_sheet.remarks if result_sheet.remarks else ''
                    })
            else:
                result_sheet = sheet_map.get('CS_RESULT')
                if not result_sheet:
                    if not is_pass_filter:
                        cs_final_rows.append({
                            'army_no': agniveer.agniveer_no or agniveer.enrollment_number,
                            'rank': getattr(agniveer, 'rank', '') or '',
                            'trade': agniveer.trade or '',
                            'name': agniveer.get_full_name(),
                            'unit': agniveer.bn_desp or '',
                            'toet_i': 0.0,
                            'toet_ii': 0.0,
                            'toet_total': 0.0,
                            'toet_25': 0.0,
                            'fe_online': 0.0,
                            'fe_prac': 0.0,
                            'fe_total': 0.0,
                            'br_online': 0.0,
                            'br_prac': 0.0,
                            'br_total': 0.0,
                            'total_160': 0.0,
                            'converted_40': 0.0,
                            'remarks': 'No evaluation'
                        })
                    continue
                marks = _marks_from_sheet(result_sheet)
                
                toet_i = _num(marks.get('TOET-I (25)'))
                toet_ii = _num(marks.get('TOET-II (25)'))
                toet_total = _num(marks.get('TOTAL TOET (50)')) or (toet_i + toet_ii)
                toet_25 = _num(marks.get('25% OF TOET (25)')) or round(toet_total * 0.5, 2)
                fe_online = _num(marks.get('FE Online Exam (50)'))
                fe_prac = _num(marks.get('FE Prac (20)'))
                fe_total = _num(marks.get('FE Total (70)')) or (fe_online + fe_prac)
                br_online = _num(marks.get('BR Online Exam (40)'))
                br_prac = _num(marks.get('BR Prac (25)'))
                br_total = _num(marks.get('BR Total (65)')) or (br_online + br_prac)
                total_160 = _num(marks.get('TOTAL (160)')) or (toet_total + fe_total + br_total)
                converted_40 = _num(marks.get('CONVERTED TO 40')) or round(total_160 * 0.25, 2)
                percentage = round((converted_40 / 40) * 100, 2) if converted_40 else 0
                is_pass = percentage >= 50
                
                if is_pass == is_pass_filter:
                    cs_final_rows.append({
                        'army_no': agniveer.agniveer_no or agniveer.enrollment_number,
                        'rank': getattr(agniveer, 'rank', '') or '',
                        'trade': agniveer.trade or '',
                        'name': agniveer.get_full_name(),
                        'unit': agniveer.bn_desp or '',
                        'toet_i': toet_i,
                        'toet_ii': toet_ii,
                        'toet_total': toet_total,
                        'toet_25': toet_25,
                        'fe_online': fe_online,
                        'fe_prac': fe_prac,
                        'fe_total': fe_total,
                        'br_online': br_online,
                        'br_prac': br_prac,
                        'br_total': br_total,
                        'total_160': total_160,
                        'converted_40': converted_40,
                        'remarks': result_sheet.remarks if result_sheet.remarks else ''
                    })

        format_param = request.GET.get('format') # 'final' or 'clerk'
        wb = openpyxl.Workbook()

        pass_fill = PatternFill(start_color="DDF4E8", end_color="DDF4E8", fill_type="solid")
        fail_fill = PatternFill(start_color="FCE4E4", end_color="FCE4E4", fill_type="solid")
        row_fill = pass_fill if status_filter == 'pass' else fail_fill

        header_fill = PatternFill(start_color="D9EAF7", end_color="D9EAF7", fill_type="solid")
        title_fill = PatternFill(start_color="EAF2F8", end_color="EAF2F8", fill_type="solid")
        border = Border(
            left=Side(style='thin', color='B7C4B7'),
            right=Side(style='thin', color='B7C4B7'),
            top=Side(style='thin', color='B7C4B7'),
            bottom=Side(style='thin', color='B7C4B7'),
        )
        center = Alignment(horizontal='center', vertical='center', wrap_text=True)

        # Main Sheet
        if not format_param or format_param == 'final':
            ws1 = wb.active
            ws1.title = "CES Final"
            
            headers1 = [
                'ARMY NO', 'RANK', 'TRADE', 'NAME', 'UNIT',
                'TOET-I (25)', 'TOET-II (25)', 'TOET TOTAL (50)', '25% OF TOET (25)',
                'FE Online Exam (50)', 'FE Prac (20)', 'FE Total (70)',
                'BR Online Exam (40)', 'BR Prac (25)', 'BR Total (65)',
                'TOTAL (160)', 'CONVERTED TO 40', 'REMARKS'
            ]
            
            ws1.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers1))
            ws1.cell(row=1, column=1, value="FINAL RESULT OF CES").fill = title_fill
            ws1.cell(row=1, column=1).font = Font(bold=True, size=13)
            ws1.cell(row=1, column=1).alignment = center
            
            for col, header in enumerate(headers1, 1):
                cell = ws1.cell(row=2, column=col, value=header)
                cell.fill = header_fill
                cell.font = Font(bold=True, size=10)
                cell.alignment = center
                cell.border = border
                
            for index, r in enumerate(cs_final_rows, 1):
                values = [
                    r['army_no'], r['rank'], r['trade'], r['name'], r['unit'],
                    r['toet_i'], r['toet_ii'], r['toet_total'], r['toet_25'],
                    r['fe_online'], r['fe_prac'], r['fe_total'],
                    r['br_online'], r['br_prac'], r['br_total'],
                    r['total_160'], r['converted_40'], r['remarks']
                ]
                for col, value in enumerate(values, 1):
                    cell = ws1.cell(row=index + 2, column=col, value=value)
                    cell.fill = row_fill
                    cell.alignment = center
                    cell.border = border
                    
            for col_idx in range(1, len(headers1) + 1):
                col_letter = openpyxl.utils.get_column_letter(col_idx)
                max_len = max(len(str(ws1.cell(row=r, column=col_idx).value or '')) for r in range(2, len(cs_final_rows) + 3))
                ws1.column_dimensions[col_letter].width = max(max_len + 3, 10)
            ws1.freeze_panes = 'A3'

        # Clerk Sheet
        if not format_param or format_param == 'clerk':
            if not format_param:
                ws2 = wb.create_sheet(title="CES Clerk Final")
            else:
                ws2 = wb.active
                ws2.title = "CES Clerk Final"
                
            headers2 = [
                'RANK', 'TRADE', 'NAME', 'PL', 'BN',
                'Online (20)', 'Prac (20)', 'Total (40)', 'REMARKS'
            ]
            
            ws2.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers2))
            ws2.cell(row=1, column=1, value="FINAL RESULT OF CES").fill = title_fill
            ws2.cell(row=1, column=1).font = Font(bold=True, size=13)
            ws2.cell(row=1, column=1).alignment = center
            
            for col, header in enumerate(headers2, 1):
                cell = ws2.cell(row=2, column=col, value=header)
                cell.fill = header_fill
                cell.font = Font(bold=True, size=10)
                cell.alignment = center
                cell.border = border
                
            for index, r in enumerate(cs_clerk_rows, 1):
                values = [
                    r['rank'], r['trade'], r['name'], r['pl'], r['bn'],
                    r['online'], r['prac'], r['total'], r['remarks']
                ]
                for col, value in enumerate(values, 1):
                    cell = ws2.cell(row=index + 2, column=col, value=value)
                    cell.fill = row_fill
                    cell.alignment = center
                    cell.border = border
                    
            for col_idx in range(1, len(headers2) + 1):
                col_letter = openpyxl.utils.get_column_letter(col_idx)
                max_len = max(len(str(ws2.cell(row=r, column=col_idx).value or '')) for r in range(2, len(cs_clerk_rows) + 3))
                ws2.column_dimensions[col_letter].width = max(max_len + 3, 10)
            ws2.freeze_panes = 'A3'

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        log_action(user, 'EXPORT', f'Exported CS {status_filter} dashboard results Excel', request)
        suffix = f"_{format_param}" if format_param else ""
        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="cs_{status_filter}_results{suffix}.xlsx"'
        return response

    def _export_clerk_results(self, request, status_filter, sub_dept=None):
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from django.db.models import Q
        from evaluation.models import Marks, EvaluationSheet
        from evaluation.result_helpers import build_clerk_result_row, _marks_from_sheet, _num, get_grade
        from departments.models import Agniveer
        import io

        user = request.user
        is_pass_filter = status_filter == 'pass'
        from evaluation.result_helpers import is_sheet_evaluated
        agniveers = Agniveer.objects.all()
        agniveers = scoped_agniveers(agniveers, user, 'D')
        
        sheets = EvaluationSheet.objects.filter(
            department='D'
        ).select_related('agniveer').prefetch_related('marks')

        if sub_dept and sub_dept != 'all':
            agniveers = agniveers.filter(bn_desp=sub_dept)
            sheets = sheets.filter(agniveer__bn_desp=sub_dept)

        from collections import defaultdict
        sheets_by_agniveer = defaultdict(list)
        for s in sheets:
            if is_sheet_evaluated(s):
                sheets_by_agniveer[s.agniveer_id].append(s)

        rows = []
        for agniveer in agniveers.order_by('agniveer_no', 'enrollment_number'):
            ag_sheets = sheets_by_agniveer.get(agniveer.id, [])
            if not ag_sheets and is_pass_filter:
                continue
            
            sheet_map = {s.test_type: s for s in ag_sheets}
            sheet = sheet_map.get('CLK_FINAL')
            if not sheet:
                if not is_pass_filter:
                    rows.append({
                        'army_no': agniveer.agniveer_no or agniveer.enrollment_number,
                        'rank': getattr(agniveer, 'rank', '') or '',
                        'trade': agniveer.trade or '',
                        'name': agniveer.get_full_name(),
                        'unit': agniveer.bn_desp or '',
                        'tech_online': '',
                        'tech_proj': '',
                        'academic': '',
                        'comp_online': '',
                        'comp_prac': '',
                        'comp_total': '',
                        'extempore': '',
                        'typing_20': '',
                        'marks_obtained_300': 0,
                        'percentage': 0,
                        'result_str': 'FAIL',
                        'grading': '—',
                        'converted_40': 0,
                        'remarks': 'No final test evaluation'
                    })
                continue
                
            marks = _marks_from_sheet(sheet)
            tech_online = _num(marks.get('Tech Online (115)'))
            tech_proj = _num(marks.get('Tech Proj HRMS (25)'))
            academic = _num(marks.get('Academic Online (85)'))
            comp_online = _num(marks.get('Computer Online (25)'))
            comp_prac = _num(marks.get('Computer Prac (25)'))
            comp_total = _num(marks.get('Computer Total (50)')) or (comp_online + comp_prac)
            extempore = _num(marks.get('Extempore (25)'))
            typing_20 = marks.get('Typing 20 WPM', '')
            marks_obtained_300 = _num(marks.get('Marks Obtained (300)')) or (tech_online + tech_proj + academic + comp_total + extempore)
            percentage = round((marks_obtained_300 / 300) * 100, 2) if marks_obtained_300 else 0
            converted_40 = _num(marks.get('Marks Obtained (40)')) or round((marks_obtained_300 / 300) * 40, 2)
            is_pass = percentage >= 46
            
            if is_pass == is_pass_filter:
                rows.append({
                    'army_no': agniveer.agniveer_no or agniveer.enrollment_number,
                    'rank': getattr(agniveer, 'rank', '') or '',
                    'trade': agniveer.trade or '',
                    'name': agniveer.get_full_name(),
                    'unit': agniveer.bn_desp or '',
                    'tech_online': tech_online,
                    'tech_proj': tech_proj,
                    'academic': academic,
                    'comp_online': comp_online,
                    'comp_prac': comp_prac,
                    'comp_total': comp_total,
                    'extempore': extempore,
                    'typing_20': typing_20,
                    'marks_obtained_300': marks_obtained_300,
                    'percentage': percentage,
                    'result_str': 'PASS' if is_pass else 'FAIL',
                    'grading': get_grade(percentage, [(tech_online, 115), (tech_proj, 25), (academic, 85), (comp_online, 25), (comp_prac, 25), (extempore, 25)], passing_pct=46),
                    'converted_40': converted_40,
                    'remarks': sheet.remarks if sheet.remarks else ''
                })

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"CTS {status_filter.upper()}"

        pass_fill = PatternFill(start_color="DDF4E8", end_color="DDF4E8", fill_type="solid")
        fail_fill = PatternFill(start_color="FCE4E4", end_color="FCE4E4", fill_type="solid")
        row_fill = pass_fill if status_filter == 'pass' else fail_fill

        header_fill = PatternFill(start_color="D9EAF7", end_color="D9EAF7", fill_type="solid")
        title_fill = PatternFill(start_color="EAF2F8", end_color="EAF2F8", fill_type="solid")
        border = Border(
            left=Side(style='thin', color='B7C4B7'),
            right=Side(style='thin', color='B7C4B7'),
            top=Side(style='thin', color='B7C4B7'),
            bottom=Side(style='thin', color='B7C4B7'),
        )
        center = Alignment(horizontal='center', vertical='center', wrap_text=True)

        # Merge row 1 for title
        title_end_letter = 'R' if status_filter == 'fail' else 'S'
        ws.merge_cells(f'A1:{title_end_letter}1')
        ws.cell(row=1, column=1, value="FINAL RESULT OF CTS").fill = title_fill
        ws.cell(row=1, column=1).font = Font(bold=True, size=13)
        ws.cell(row=1, column=1).alignment = center
        ws.row_dimensions[1].height = 30

        # Row 2 Category Headers
        ws.cell(row=2, column=1, value='ARMY NO')
        ws.cell(row=2, column=2, value='RANK')
        ws.cell(row=2, column=3, value='TRADE')
        ws.cell(row=2, column=4, value='NAME')
        ws.cell(row=2, column=5, value='UNIT')
        ws.cell(row=2, column=6, value='Tech')
        ws.cell(row=2, column=8, value='Academic')
        ws.cell(row=2, column=9, value='CMPTR')
        ws.cell(row=2, column=12, value='Extempore (25/10)')
        ws.cell(row=2, column=13, value='Typing 20 WPM')
        ws.cell(row=2, column=14, value='Marks Obtained (MM 300) 46%/138')
        ws.cell(row=2, column=15, value='%AGE')
        ws.cell(row=2, column=16, value='Result')
        if status_filter != 'fail':
            ws.cell(row=2, column=17, value='Grading')
            ws.cell(row=2, column=18, value='Converted Out of 40')
            ws.cell(row=2, column=19, value='Remarks')
        else:
            ws.cell(row=2, column=17, value='Converted Out of 40')
            ws.cell(row=2, column=18, value='Remarks')

        # Row 3 Sub-headers
        ws.cell(row=3, column=6, value='Online (115/46)')
        ws.cell(row=3, column=7, value='Tech Proj (HRMS) (25/10)')
        ws.cell(row=3, column=8, value='Online (85/34)')
        ws.cell(row=3, column=9, value='Online (25/10)')
        ws.cell(row=3, column=10, value='Prac (25/10)')
        ws.cell(row=3, column=11, value='Total (50/20)')

        # Apply header styling to all cells in Row 2 and Row 3 first
        num_cols = 18 if status_filter == 'fail' else 19
        for r in [2, 3]:
            ws.row_dimensions[r].height = 25
            for col in range(1, num_cols + 1):
                cell = ws.cell(row=r, column=col)
                cell.fill = header_fill
                cell.font = Font(bold=True, size=10)
                cell.alignment = center
                cell.border = border

        # Merges
        # Vertical merges
        v_merges = [1, 2, 3, 4, 5, 12, 13, 14, 15, 16]
        if status_filter != 'fail':
            v_merges.extend([17, 18, 19])
        else:
            v_merges.extend([17, 18])
        for col in v_merges:
            ws.merge_cells(start_row=2, start_column=col, end_row=3, end_column=col)

        # Horizontal merges
        ws.merge_cells('F2:G2') # Tech
        ws.merge_cells('I2:K2') # CMPTR

        # Insert data starting at Row 4
        for index, r in enumerate(rows, 1):
            values = [
                r['army_no'], r['rank'], r['trade'], r['name'], r['unit'],
                r['tech_online'], r['tech_proj'], r['academic'],
                r['comp_online'], r['comp_prac'], r['comp_total'],
                r['extempore'], r['typing_20'], r['marks_obtained_300'],
                f"{r['percentage']}%" if r['percentage'] else '0%', r['result_str'],
            ]
            if status_filter != 'fail':
                values.append(r['grading'])
            values.extend([r['converted_40'], r['remarks']])
            for col, value in enumerate(values, 1):
                cell = ws.cell(row=index + 3, column=col, value=value)
                cell.fill = row_fill
                cell.alignment = center
                cell.border = border

        for col_idx in range(1, num_cols + 1):
            col_letter = openpyxl.utils.get_column_letter(col_idx)
            max_len = max(len(str(ws.cell(row=r, column=col_idx).value or '')) for r in range(2, len(rows) + 4))
            ws.column_dimensions[col_letter].width = max(max_len + 3, 10)
        ws.freeze_panes = 'A4'

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        log_action(user, 'EXPORT', f'Exported Clerk {status_filter} dashboard results Excel', request)
        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="clerk_{status_filter}_results.xlsx"'
        return response

    def _export_specific_test_results(self, request, dept_code, sub_dept_key, test_type, status_filter):
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        import io
        from django.db.models import Q
        from django.http import HttpResponse
        from departments.models import Agniveer
        from evaluation.models import EvaluationSheet
        from evaluation.constants import DEPT_CONFIG
        from logs.utils import log_action

        CLERK_TRADES = ['CLK', 'CLERK', 'Clerk', 'CLK_SD', 'CLK_IM']

        # Get all agniveers and sheets for this department and sub-department
        all_agniveers = Agniveer.objects.all()
        if dept_code == 'A':
            if sub_dept_key and sub_dept_key != 'all':
                agniveers_qs = all_agniveers.filter(bn_desp=sub_dept_key)
            else:
                agniveers_qs = all_agniveers
        elif dept_code == 'B':
            if sub_dept_key and sub_dept_key != 'all':
                if sub_dept_key == 'DMV':
                    agniveers_qs = all_agniveers.filter(trade='DMV')
                elif sub_dept_key == 'OPEM':
                    agniveers_qs = all_agniveers.filter(trade='OPEM')
                else:  # OTHER
                    agniveers_qs = all_agniveers.exclude(trade__in=['DMV', 'OPEM'] + CLERK_TRADES)
            else:
                agniveers_qs = all_agniveers.exclude(trade__in=CLERK_TRADES)
        elif dept_code == 'C':
            agniveers_qs = all_agniveers
        elif dept_code == 'D':
            agniveers_qs = all_agniveers.filter(trade__in=CLERK_TRADES)
        else:
            agniveers_qs = all_agniveers.none()

        sheets_qs = EvaluationSheet.objects.filter(
            department=dept_code,
            test_type=test_type,
            agniveer__in=agniveers_qs
        ).select_related('agniveer').prefetch_related('marks')

        filtered_rows = []
        for agniveer in agniveers_qs.order_by('agniveer_no', 'enrollment_number'):
            sheet = sheets_qs.filter(agniveer=agniveer).first()
            is_evaluated = sheet is not None
            is_pass = sheet.is_pass() if is_evaluated else False

            if status_filter == 'evaluated' and not is_evaluated:
                continue
            elif status_filter == 'pass' and (not is_evaluated or not is_pass):
                continue
            elif status_filter == 'fail' and (not is_evaluated or is_pass):
                continue

            filtered_rows.append({
                'agniveer': agniveer,
                'sheet': sheet,
                'is_evaluated': is_evaluated,
                'is_pass': is_pass
            })

        # Get sub-events if they exist
        config = DEPT_CONFIG.get(dept_code, {})
        sub_events = []

        if dept_code == 'B' and sub_dept_key in ['DMV', 'OPEM', 'OTHER']:
            sub_conf = config.get('sub_departments', {}).get(sub_dept_key, {})
            sub_events = sub_conf.get('sub_events', {}).get(test_type, [])
        else:
            sub_events = config.get('sub_events', {}).get(test_type, [])

        test_type_label = test_type
        if dept_code == 'B' and sub_dept_key in ['DMV', 'OPEM', 'OTHER']:
            sub_conf = config.get('sub_departments', {}).get(sub_dept_key, {})
            for tt_val, tt_lbl in sub_conf.get('test_types', []):
                if tt_val == test_type:
                    test_type_label = tt_lbl
                    break
        else:
            for tt_val, tt_lbl in config.get('test_types', []):
                if tt_val == test_type:
                    test_type_label = tt_lbl
                    break

        headers = ['S.No', 'Enrollment No', 'Army No', 'Name', 'Trade', 'Unit']
        for event in sub_events:
            headers.append(event)
        headers.extend(['NCO Marks', 'JCO Marks', 'Officer Marks', 'Total Marks', 'Result'])

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = test_type[:30]

        # Styles
        brand_color = "1B4332"
        header_fill = PatternFill(start_color=brand_color, end_color=brand_color, fill_type="solid")
        title_fill = PatternFill(start_color="EAF2F8", end_color="EAF2F8", fill_type="solid")
        pass_fill = PatternFill(start_color="DDF4E8", end_color="DDF4E8", fill_type="solid")
        fail_fill = PatternFill(start_color="FCE4E4", end_color="FCE4E4", fill_type="solid")
        unevaluated_fill = PatternFill(start_color="F2F4F4", end_color="F2F4F4", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True, size=11)
        border = Border(
            left=Side(style='thin', color='B7C4B7'),
            right=Side(style='thin', color='B7C4B7'),
            top=Side(style='thin', color='B7C4B7'),
            bottom=Side(style='thin', color='B7C4B7'),
        )
        center = Alignment(horizontal='center', vertical='center', wrap_text=True)
        left = Alignment(horizontal='left', vertical='center', wrap_text=True)

        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
        title_cell = ws.cell(row=1, column=1)
        dept_name = config.get('name', f'Dept {dept_code}')
        sub_dept_text = f" ({sub_dept_key})" if sub_dept_key and sub_dept_key != 'all' else ""
        title_cell.value = f"ARMY EVALUATION PORTAL - {dept_name.upper()}{sub_dept_text.upper()} - {test_type_label.upper()} ({status_filter.upper()} LIST)"
        title_cell.font = Font(bold=True, size=13, color=brand_color)
        title_cell.fill = title_fill
        title_cell.alignment = center
        ws.row_dimensions[1].height = 30

        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=2, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center
            cell.border = border
        ws.row_dimensions[2].height = 25

        for row_idx, row_data in enumerate(filtered_rows, 1):
            agniveer = row_data['agniveer']
            sheet = row_data['sheet']
            is_eval = row_data['is_evaluated']
            is_pass = row_data['is_pass']

            if not is_eval:
                row_fill = unevaluated_fill
            elif is_pass:
                row_fill = pass_fill
            else:
                row_fill = fail_fill

            values = [
                row_idx,
                agniveer.enrollment_number,
                agniveer.agniveer_no or agniveer.enrollment_number,
                agniveer.get_full_name(),
                agniveer.trade or '',
                agniveer.bn_desp or ''
            ]

            from evaluation.result_helpers import _marks_from_sheet
            res = sheet.sub_event_results if is_eval else {}
            marks_dict = _marks_from_sheet(sheet) if is_eval else {}

            for event in sub_events:
                if is_eval and res:
                    val = ''
                    if event in res:
                        val = res[event]
                    elif event in marks_dict:
                        val = marks_dict[event]
                    else:
                        for col in ['Event Wise Best', 'Best Attempt', '3rd Attempt', '2nd Attempt', '1st Attempt']:
                            if col in res and isinstance(res[col], dict):
                                if event in res[col] and res[col][event] is not None:
                                    val = res[col][event]
                                    break
                        if val == '':
                            for k, v in res.items():
                                if isinstance(v, dict) and event in v and v[event] is not None:
                                    val = v[event]
                                    break
                    values.append(val)
                else:
                    values.append('')

            if is_eval:
                values.extend([
                    sheet.get_nco_marks(),
                    sheet.get_jco_marks(),
                    sheet.get_officer_marks(),
                    sheet.get_total_marks(),
                    'PASS' if is_pass else 'FAIL'
                ])
            else:
                values.extend(['', '', '', '', 'NOT EVALUATED'])

            for col, value in enumerate(values, 1):
                cell = ws.cell(row=row_idx + 2, column=col, value=value)
                cell.fill = row_fill
                cell.alignment = left if col == 4 else center
                cell.border = border
            ws.row_dimensions[row_idx + 2].height = 20

        ws.freeze_panes = 'A3'
        for col_idx in range(1, len(headers) + 1):
            col_letter = openpyxl.utils.get_column_letter(col_idx)
            max_len = max(len(str(ws.cell(row=r, column=col_idx).value or '')) for r in range(2, len(filtered_rows) + 3))
            ws.column_dimensions[col_letter].width = max(max_len + 3, 10)

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        log_action(request.user, 'EXPORT', f'Exported {test_type_label} Excel results ({status_filter})', request)

        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        filename = f"{dept_code}_{sub_dept_key or 'all'}_{test_type}_{status_filter}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    def get(self, request):
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        except ImportError:
            return HttpResponse("openpyxl not installed.", status=500)
        status_filter = request.GET.get('status', 'pass')
        if status_filter not in ['pass', 'fail', 'eligible', 'evaluated']:
            status_filter = 'pass'
        is_pass_filter = status_filter == 'pass'
        
        user = request.user

        dept_code = request.GET.get('dept')
        sub_dept_key = request.GET.get('sub_dept')
        test_type = request.GET.get('test_type')

        if dept_code and test_type:
            return self._export_specific_test_results(request, dept_code, sub_dept_key, test_type, status_filter)

        # Resolve target department (GET parameter takes precedence)
        target_dept = dept_code
        if not target_dept and user.is_department:
            target_dept = user.get_department_code()

        if target_dept == 'A':
            return self._export_battalion_results(request, status_filter, sub_dept=sub_dept_key)
        if target_dept == 'B':
            return self._export_tts_results(request, status_filter, sub_dept=sub_dept_key)
        if target_dept == 'C':
            return self._export_cs_results(request, status_filter, sub_dept=sub_dept_key)
        if target_dept == 'D':
            return self._export_clerk_results(request, status_filter, sub_dept=sub_dept_key)

        from evaluation.result_helpers import is_sheet_evaluated
        is_dept = user.is_department
        dept_code = user.get_department_code() if is_dept else None
        departments = [dept_code] if is_dept else ['A', 'B', 'C', 'D']

        all_sheets = EvaluationSheet.objects.all().prefetch_related('marks')

        if is_dept:
            all_sheets = scoped_sheets(all_sheets, user, dept_code)
            
        filtered_agniveers = []
        all_agniveers = Agniveer.objects.all()
        if is_dept:
            all_agniveers = scoped_agniveers(all_agniveers, user, dept_code)
        
        for agniveer in all_agniveers.order_by('agniveer_no', 'enrollment_number'):
            total_marks = 0
            max_marks = 0
            evaluated_departments = []

            for dept in departments:
                dept_sheets = [s for s in all_sheets.filter(agniveer=agniveer, department=dept) if is_sheet_evaluated(s)]
                if not dept_sheets:
                    continue
                result_row = build_department_result_row(agniveer, dept_sheets, dept)
                total_marks += result_row.get('grand_total', 0) or 0
                max_marks += result_row.get('max_total') or 40
                evaluated_departments.append(DEPARTMENT_NAMES.get(dept, dept))

            if max_marks <= 0:
                if not is_pass_filter:
                    total_max = sum(120 if d == 'A' else 40 for d in departments)
                    filtered_agniveers.append({
                        'enrollment_number': agniveer.enrollment_number,
                        'army_no': agniveer.agniveer_no or agniveer.enrollment_number,
                        'rank': getattr(agniveer, 'rank', '') or '',
                        'name': agniveer.get_full_name(),
                        'trade': agniveer.trade or '',
                        'unit': agniveer.bn_desp or '',
                        'departments': 'None',
                        'score': f"0/{total_max}",
                        'percentage': 0.0,
                        'status': 'FAIL'
                    })
                continue

            percentage = (total_marks / max_marks) * 100
            is_pass = percentage >= 50
            if is_pass == is_pass_filter:
                filtered_agniveers.append({
                    'enrollment_number': agniveer.enrollment_number,
                    'army_no': agniveer.agniveer_no or agniveer.enrollment_number,
                    'rank': getattr(agniveer, 'rank', '') or '',
                    'name': agniveer.get_full_name(),
                    'trade': agniveer.trade or '',
                    'unit': agniveer.bn_desp or '',
                    'departments': ', '.join(evaluated_departments),
                    'score': f"{total_marks:g}/{max_marks:g}",
                    'percentage': round(percentage, 1),
                    'status': 'PASS' if is_pass else 'FAIL'
                })

        # Create Excel
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"{status_filter.upper()} Agniveers"

        # Styling
        brand_color = "1B4332"
        header_fill = PatternFill(start_color=brand_color, end_color=brand_color, fill_type="solid")
        title_fill = PatternFill(start_color="EAF2F8", end_color="EAF2F8", fill_type="solid")
        pass_fill = PatternFill(start_color="DDF4E8", end_color="DDF4E8", fill_type="solid")
        fail_fill = PatternFill(start_color="FCE4E4", end_color="FCE4E4", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True, size=11)
        border = Border(
            left=Side(style='thin', color='B7C4B7'),
            right=Side(style='thin', color='B7C4B7'),
            top=Side(style='thin', color='B7C4B7'),
            bottom=Side(style='thin', color='B7C4B7'),
        )
        center = Alignment(horizontal='center', vertical='center', wrap_text=True)
        left = Alignment(horizontal='left', vertical='center', wrap_text=True)

        # Title
        ws.merge_cells('A1:H1')
        title_cell = ws['A1']
        dept_text = f" - DEPARTMENT {dept_code}" if is_dept else ""
        title_cell.value = f"ARMY EVALUATION PORTAL{dept_text} - {status_filter.upper()} AGNIVEERS"
        title_cell.font = Font(bold=True, size=14, color=brand_color)
        title_cell.fill = title_fill
        title_cell.alignment = center
        ws.row_dimensions[1].height = 30

        # Headers
        headers = ['ARMY NO', 'RANK', 'TRADE', 'NAME', 'UNIT', 'DEPARTMENTS', 'SCORE', 'PERCENTAGE']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=2, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center
            cell.border = border

        # Data
        row_fill = pass_fill if is_pass_filter else fail_fill
        for row_idx, data in enumerate(filtered_agniveers, 1):
            values = [
                data['army_no'],
                data['rank'],
                data['trade'],
                data['name'],
                data['unit'],
                data['departments'],
                data['score'],
                f"{data['percentage']}%",
            ]
            for col, value in enumerate(values, 1):
                cell = ws.cell(row=row_idx + 2, column=col, value=value)
                cell.fill = row_fill
                cell.alignment = left if col == 4 else center
                cell.border = border

        widths = [18, 10, 14, 28, 12, 24, 15, 14]
        for col, width in enumerate(widths, 1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = width
        ws.freeze_panes = 'A3'
        ws.auto_filter.ref = f"A2:H{max(len(filtered_agniveers) + 2, 2)}"

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        log_action(user, 'EXPORT', f'Exported {status_filter} dashboard results Excel', request)
        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="dashboard_{status_filter}_results.xlsx"'
        return response

class ExportPDFReportCardView(AnyStaffMixin, View):
    """Export individual Agniveer report card as PDF with enhanced ReportLab styling."""

    def get(self, request, pk):
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, HRFlowable
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        except ImportError:
            return HttpResponse("reportlab not installed.", status=500)

        agniveer = get_object_or_404(Agniveer, pk=pk)
        evaluations = EvaluationSheet.objects.filter(agniveer=agniveer).prefetch_related('marks').order_by('department', 'category', 'test_type')

        if request.user.is_trainer:
            return HttpResponse("You don't have permission to export report cards.", status=403)

        # Determine filtering based on role and optional query parameter
        target_dept = request.GET.get('dept')
        is_department_export = False
        user_dept = None

        if request.user.is_department:
            user_dept = request.user.get_department_code()
            if not user_can_access_agniveer(request.user, agniveer, user_dept):
                return HttpResponse("You don't have permission to export this report card.", status=403)
            evaluations = scoped_sheets(evaluations, request.user, user_dept)
            is_department_export = True
            departments_to_show = [user_dept]
        elif target_dept and target_dept in ['A', 'B', 'C', 'D'] and (request.user.is_commander or request.user.is_g_head):
            # Privileged users can optionally filter by department
            evaluations = evaluations.filter(department=target_dept)
            is_department_export = True
            departments_to_show = [target_dept]
            user_dept = target_dept
        else:
            # Commanders/G-Heads see everything by default
            is_department_export = False
            departments_to_show = ['A', 'B', 'C', 'D']

        dept_evaluations = {}
        from evaluation.constants import get_dept_total_marks, get_overall_total_marks
        
        for dept in departments_to_show:
            dept_evals = evaluations.filter(department=dept)
            if dept_evals.exists():
                dept_evaluations[dept] = {
                    'on_field': dept_evals.filter(category='on_field'),
                    'trade': dept_evals.filter(category='trade'),
                    'total_marks': sum(e.get_total_marks() for e in dept_evals),
                    'max_marks': get_dept_total_marks(dept),
                }

        grand_total = sum(e.get_total_marks() for e in evaluations)
        max_total = get_dept_total_marks(user_dept) if is_department_export else get_overall_total_marks()
        percentage = round((grand_total / max_total * 100), 2) if max_total else 0
        overall_pass = percentage >= 50

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.4*inch, bottomMargin=0.4*inch, leftMargin=0.5*inch, rightMargin=0.5*inch)
        styles = getSampleStyleSheet()

        # Color Palette (Matching Web UI)
        brand_dark = colors.HexColor('#1B4332')
        brand_medium = colors.HexColor('#2D6A4F')
        accent_green = colors.HexColor('#1B4332')
        gold_color = colors.HexColor('#D4A017')
        text_dark = colors.HexColor('#0F1419')
        text_muted = colors.HexColor('#6C757D')
        pass_green = colors.HexColor('#4CAF50')
        fail_red = colors.HexColor('#EF5350')
        
        # Styles
        title_style = ParagraphStyle('Title', fontSize=18, textColor=colors.white, fontName='Helvetica-Bold', alignment=TA_CENTER)
        subtitle_style = ParagraphStyle('Sub', fontSize=7, textColor=colors.white, fontName='Helvetica', alignment=TA_CENTER, letterSpacing=2)
        badge_style = ParagraphStyle('Badge', fontSize=14, textColor=colors.white, fontName='Helvetica-Bold', alignment=TA_CENTER)
        badge_sub_style = ParagraphStyle('BadgeSub', fontSize=8, textColor=colors.white, fontName='Helvetica', alignment=TA_CENTER)
        
        dept_title_style = ParagraphStyle('Dept', fontSize=12, textColor=brand_dark, fontName='Helvetica-Bold', spaceBefore=10, spaceAfter=6)
        section_style = ParagraphStyle('Section', fontSize=9, textColor=brand_medium, fontName='Helvetica-Bold', spaceBefore=6, spaceAfter=4)
        label_style = ParagraphStyle('Label', fontSize=7, textColor=text_muted, fontName='Helvetica-Bold', leading=8)
        value_style = ParagraphStyle('Value', fontSize=10, textColor=text_dark, fontName='Helvetica-Bold', leading=12)

        elements = []

        # ==== HEADER WITH BADGE ====
        result_text = '✓ PASS' if overall_pass else '✗ FAIL'
        result_color = pass_green if overall_pass else fail_red
        
        badge_content = [
            [Paragraph(result_text, ParagraphStyle('RT', parent=badge_style, textColor=result_color))],
            [Paragraph(f'{percentage}%', ParagraphStyle('PC', parent=badge_sub_style, textColor=colors.white))]
        ]
        badge_table = Table(badge_content, colWidths=[1.1*inch])
        badge_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.Color(result_color.red, result_color.green, result_color.blue, alpha=0.1)),
            ('BORDER', (0, 0), (0, -1), 1.5, result_color),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))

        header_data = [
            [
                Paragraph('ARMY EVALUATION PORTAL', title_style),
                badge_table
            ],
            [
                Paragraph('AGNIVEER PROFILE & PERFORMANCE REPORT', subtitle_style),
                ''
            ]
        ]
        
        header_table = Table(header_data, colWidths=[5.7*inch, 1.6*inch])
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), brand_dark),
            ('SPAN', (1, 0), (1, 1)),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (1, 0), (1, 1), 15),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 12))

        # ==== PROFILE SECTION ====
        try:
            if agniveer.photo:
                img = Image(agniveer.photo.path, 0.8*inch, 0.8*inch)
            else:
                img = Paragraph('PHOTO\nN/A', label_style)
        except:
            img = Paragraph('N/A', label_style)

        profile_grid = [
            [Paragraph('NAME', label_style), Paragraph('ENROLLMENT NO', label_style)],
            [Paragraph(agniveer.get_full_name().upper(), value_style), Paragraph(agniveer.enrollment_number, value_style)],
            [Spacer(1, 6), Spacer(1, 6)],
            [Paragraph('BATCH', label_style), Paragraph('JOINING DATE', label_style)],
            [Paragraph(agniveer.batch, value_style), Paragraph(agniveer.joining_date.strftime('%d %b %Y'), value_style)],
        ]
        
        grid_table = Table(profile_grid, colWidths=[2.8*inch, 2.8*inch])
        grid_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))

        main_profile_table = Table([[img, grid_table]], colWidths=[1.1*inch, 6.1*inch])
        main_profile_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ]))
        elements.append(main_profile_table)
        elements.append(Spacer(1, 5))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey, spaceAfter=10))

        # ==== EVALUATIONS ====
        for dept, data in dept_evaluations.items():
            elements.append(Paragraph(f'DEPARTMENT {dept} EVALUATIONS', dept_title_style))
            
            # Compact Score Bar
            score_data = [[f'ACHIEVED SCORE: {data["total_marks"]} / {data["max_marks"]}']]
            score_bar = Table(score_data, colWidths=[7.2*inch])
            score_bar.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8F9FA')),
                ('TEXTCOLOR', (0, 0), (-1, -1), brand_dark),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('PADDING', (0, 0), (-1, -1), 5),
            ]))
            elements.append(score_bar)

            for cat_name, cat_key, head_col in [('ON FIELD TRAINING', 'on_field', brand_dark), ('TRADE TRAINING', 'trade', brand_medium)]:
                if data[cat_key]:
                    elements.append(Paragraph(f'• {cat_name}', section_style))
                    
                    table_data = [['Test Type', 'NCO', 'JCO', 'Officer', 'Total', '%', 'Result']]
                    for ev in data[cat_key]:
                        res = 'PASS' if ev.is_pass() else 'FAIL'
                        table_data.append([
                            ev.get_test_type_display(),
                            str(ev.get_nco_marks()),
                            str(ev.get_jco_marks()),
                            str(ev.get_officer_marks()),
                            str(ev.get_total_marks()),
                            f'{ev.get_percentage()}%',
                            res
                        ])
                    
                    t = Table(table_data, colWidths=[2.1*inch, 0.7*inch, 0.7*inch, 0.7*inch, 0.7*inch, 0.7*inch, 1.2*inch])
                    t.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), head_col),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 8),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9F9F9')]),
                        ('TOPPADDING', (0, 0), (-1, -1), 3),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                    ]))
                    elements.append(t)
                    elements.append(Spacer(1, 8))

        # ==== SUMMARY ====
        elements.append(Spacer(1, 10))
        elements.append(HRFlowable(width="100%", thickness=1, color=brand_dark))
        
        summary_title = f'{"DEPARTMENT " + user_dept if is_department_export else "OVERALL"} PERFORMANCE SUMMARY'
        elements.append(Paragraph(summary_title, ParagraphStyle('Sum', fontSize=11, fontName='Helvetica-Bold', alignment=TA_CENTER, spaceBefore=10, spaceAfter=8)))
        
        # Professional Summary Card
        summary_data = [
            [Paragraph('CRITERIA', ParagraphStyle('CL', fontSize=8, fontName='Helvetica-Bold', textColor=colors.white)), 
             Paragraph('ACHIEVEMENT', ParagraphStyle('CR', fontSize=8, fontName='Helvetica-Bold', textColor=colors.white, alignment=TA_RIGHT))],
            ['TOTAL SCORE ACHIEVED', f'{grand_total} / {max_total}'],
            ['PERCENTAGE ACHIEVEMENT', f'{percentage}%'],
            ['FINAL QUALIFICATION STATUS', Paragraph('✓ PASSED' if overall_pass else '✗ FAILED', ParagraphStyle('Res', fontSize=10, fontName='Helvetica-Bold', alignment=TA_RIGHT, textColor=pass_green if overall_pass else fail_red))]
        ]
        
        summary_table = Table(summary_data, colWidths=[3.65*inch, 3.65*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), brand_dark),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, brand_dark),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#F8F9FA')),
        ]))
        elements.append(summary_table)

        doc.build(elements)
        pdf = buffer.getvalue()
        buffer.close()
        
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="ReportCard_{agniveer.enrollment_number}.pdf"'
        return response

        # ==== FOOTER ====
        elements.append(Spacer(1, 15))
        footer_style = ParagraphStyle('Footer', fontSize=7, alignment=TA_CENTER, textColor=text_muted)
        elements.append(Paragraph(f'Generated by Army Evaluation Portal | Report ID: {agniveer.enrollment_number} | Date: {timezone.now().strftime("%d %b %Y, %H:%M")}', footer_style))

        doc.build(elements)
        buffer.seek(0)
        log_action(request.user, 'EXPORT', f'Exported PDF Report Card for {agniveer.enrollment_number}', request)
        return FileResponse(buffer, as_attachment=True, filename=f'report_card_{agniveer.enrollment_number}.pdf')


class ExportDepartmentPDFView(AnyStaffMixin, View):
    """Export department summary as PDF with polished styling."""

    def get(self, request, dept):
        try:
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib import colors
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_CENTER
        except ImportError:
            return HttpResponse("reportlab not installed.", status=500)

        if request.user.is_department and request.user.get_department_code() != dept:
            return HttpResponse("You don't have permission to export this department.", status=403)

        agniveers = scoped_agniveers(
            Agniveer.objects.filter(evaluations__department=dept).distinct(),
            request.user,
            dept,
        )
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=0.4*inch, bottomMargin=0.4*inch)
        styles = getSampleStyleSheet()
        
        # Brand Colors
        brand_dark = colors.HexColor('#1B4332')
        text_muted = colors.HexColor('#6C757D')

        elements = []

        # Header
        title_style = ParagraphStyle('Title', fontSize=20, textColor=colors.white, fontName='Helvetica-Bold', alignment=TA_CENTER)
        header_table = Table([[Paragraph(f"ARMY EVALUATION PORTAL - DEPARTMENT {dept} SUMMARY", title_style)]], colWidths=[10*inch])
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), brand_dark),
            ('PADDING', (0, 0), (-1, -1), 15),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 20))

        headers = ['S.No', 'Enrollment No', 'Name', 'Batch', 'Total Score', 'Pass/Fail Status']
        data = [headers]

        for i, a in enumerate(agniveers, 1):
            a_sheets = scoped_sheets(
                EvaluationSheet.objects.filter(agniveer=a, is_locked=True).prefetch_related('marks'),
                request.user,
                dept,
            )
            total_score = sum(sheet.get_total_marks() for sheet in a_sheets)
            max_score = sum(sheet.get_max_marks() for sheet in a_sheets)
            pass_status = 'Pass' if max_score and (total_score / max_score) * 100 >= 50 else 'Fail'
            data.append([
                str(i),
                a.enrollment_number,
                a.get_full_name(),
                a.batch,
                str(total_score),
                pass_status,
            ])

        table = Table(data, colWidths=[0.6*inch, 1.8*inch, 2.8*inch, 1.5*inch, 1.5*inch, 1.8*inch])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), brand_dark),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')]),
        ]))
        elements.append(table)
        
        # Footer
        elements.append(Spacer(1, 30))
        elements.append(Paragraph(f'Generated by Army Evaluation Portal | Date: {timezone.now().strftime("%d %b %Y")}', ParagraphStyle('Footer', fontSize=8, alignment=TA_CENTER, textColor=text_muted)))

        doc.build(elements)
        buffer.seek(0)

        log_action(request.user, 'EXPORT', f'Exported Department {dept} PDF', request)
        return FileResponse(buffer, as_attachment=True, filename=f"dept_{dept}_summary.pdf")
