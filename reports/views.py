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
from evaluation.result_helpers import build_tts_result_row, build_battalion_result_row
from accounts.models import CustomUser
from accounts.mixins import AnyStaffMixin, CommanderOrGHeadMixin
from logs.utils import log_action


DEPARTMENT_NAMES = {'A': 'Battalion', 'B': 'TTS', 'C': 'CS', 'D': 'Clerk'}

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
        return self.request.user.is_authenticated and self.request.user.role == CustomUser.ROLE_CS_HEAD

class ClerkHeadMixin(UserPassesTestMixin):
    """Allow access only to Clerk head users"""
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role == CustomUser.ROLE_CLERK_HEAD


class ReportDashboardView(AnyStaffMixin, View):
    template_name = 'reports/report_dashboard.html'

    def get(self, request):
        user = request.user
        context = {}
        
        if user.is_commander or user.is_g_head:
            # Commander/G-Head sees ALL departments
            context['user_role'] = 'commander_ghead'
            context['show_all_departments'] = True
            
            # Get data for all departments
            dept_data = {}
            for dept_code, dept_name in DEPARTMENT_NAMES.items():
                sheets = EvaluationSheet.objects.filter(department=dept_code, is_locked=True)
                dept_data[dept_code] = {
                    'name': dept_name,
                    'total_agniveers': Agniveer.objects.filter(department=dept_code).count(),
                    'pass_count': sheets.filter(is_locked=True).count(),
                    'fail_count': 0,  # Calculate properly
                    'total_trainers': CustomUser.objects.filter(
                        role__in=[CustomUser.ROLE_TRAINER_NCO, CustomUser.ROLE_TRAINER_JCO, CustomUser.ROLE_TRAINER_OFFICER],
                        department=dept_code
                    ).count()
                }
            context['department_data'] = dept_data
            
            # Overall totals
            total_sheets = EvaluationSheet.objects.filter(is_locked=True)
            context['total_agniveers'] = Agniveer.objects.count()
            context['total_trainers'] = CustomUser.objects.filter(
                role__in=[CustomUser.ROLE_TRAINER_NCO, CustomUser.ROLE_TRAINER_JCO, CustomUser.ROLE_TRAINER_OFFICER]
            ).count()
            context['pass_count'] = total_sheets.filter(is_locked=True).count()
            
        elif user.is_department:
            dept = user.get_department_code()
            context['user_role'] = f'department_{dept}'
            context['department_code'] = dept
            context['department_name'] = DEPARTMENT_NAMES.get(dept, dept)
            
            # Check if user is department head
            if dept == 'A' and user.is_battalion:
                context['is_department_head'] = True
                context['head_type'] = 'battalion'
                # Battalion head sees only their battalion unit
                if user.battalion_unit:
                    agniveers = Agniveer.objects.filter(bn_desp=user.battalion_unit)
                else:
                    agniveers = Agniveer.objects.filter(department='A')
                sheets = EvaluationSheet.objects.filter(department='A', is_locked=True, agniveer__in=agniveers)
                
            elif dept == 'B' and getattr(user, 'tts_trade', None):
                context['is_department_head'] = True
                context['head_type'] = 'tts'
                context['tts_trade'] = user.tts_trade
                # TTS head sees only their trade
                if user.tts_trade == 'DMV':
                    agniveers = Agniveer.objects.filter(trade='DMV')
                elif user.tts_trade == 'OPEM':
                    agniveers = Agniveer.objects.filter(trade='OPEM')
                else:  # OTHER
                    agniveers = Agniveer.objects.exclude(trade__in=['DMV', 'OPEM'])
                sheets = EvaluationSheet.objects.filter(department='B', is_locked=True, agniveer__in=agniveers)
                
            elif dept == 'C' and user.role == CustomUser.ROLE_CS_HEAD:
                context['is_department_head'] = True
                context['head_type'] = 'cs'
                agniveers = Agniveer.objects.filter(department='C')
                sheets = EvaluationSheet.objects.filter(department='C', is_locked=True)
                
            elif dept == 'D' and user.role == CustomUser.ROLE_CLERK_HEAD:
                context['is_department_head'] = True
                context['head_type'] = 'clerk'
                agniveers = Agniveer.objects.filter(department='D', trade__in=['CLK', 'CLERK', 'Clerk', 'CLK_SD', 'CLK_IM'])
                sheets = EvaluationSheet.objects.filter(department='D', is_locked=True, agniveer__in=agniveers)
            else:
                # Regular department user (not head)
                context['is_department_head'] = False
                agniveers = Agniveer.objects.filter(department=dept)
                sheets = EvaluationSheet.objects.filter(department=dept, is_locked=True)
            
            context['total_agniveers'] = agniveers.count()
            context['total_trainers'] = CustomUser.objects.filter(
                role__in=[CustomUser.ROLE_TRAINER_NCO, CustomUser.ROLE_TRAINER_JCO, CustomUser.ROLE_TRAINER_OFFICER],
                department=dept
            ).count()
            context['pass_count'] = sheets.count()
        else:
            # Trainer users
            context['user_role'] = 'trainer'
            agniveers = user.assigned_agniveers.all()
            sheets = EvaluationSheet.objects.filter(agniveer__in=agniveers, is_locked=True)
            context['total_agniveers'] = agniveers.count()
            context['total_trainers'] = 0
            context['pass_count'] = sheets.count()

        context['fail_count'] = context['total_agniveers'] - context['pass_count']

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
            agniveers = Agniveer.objects.filter(bn_desp=battalion_unit, department='A')
        else:
            agniveers = Agniveer.objects.filter(department='A')
        
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
        user = request.user
        agniveers = Agniveer.objects.filter(department='C')
        
        return render(request, self.template_name, {
            'agniveers': agniveers,
            'department_name': 'CS (Communication Systems)',
            'message': 'CS report card schema will be implemented soon.',
        })


class ClerkReportCardView(ClerkHeadMixin, View):
    """Clerk Head sees report cards (loads report card without schema for now)"""
    template_name = 'reports/clerk_report_card.html'
    
    def get(self, request):
        user = request.user
        agniveers = Agniveer.objects.filter(department='D', trade__in=['CLK', 'CLERK', 'Clerk', 'CLK_SD', 'CLK_IM'])
        
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
            agniveer_dept = agniveer.department
            
            # Department users can only see their own department's agniveers
            if user_dept == agniveer_dept:
                # For Battalion head: also check battalion unit
                if user.is_battalion:
                    if user.battalion_unit:
                        if agniveer.bn_desp == user.battalion_unit:
                            has_access = True
                    else:
                        has_access = True
                # For TTS head: check trade
                elif user_dept == 'B' and getattr(user, 'tts_trade', None):
                    if user.tts_trade == 'DMV' and agniveer.trade == 'DMV':
                        has_access = True
                    elif user.tts_trade == 'OPEM' and agniveer.trade == 'OPEM':
                        has_access = True
                    elif user.tts_trade == 'OTHER' and agniveer.trade not in ['DMV', 'OPEM']:
                        has_access = True
                    else:
                        has_access = False
                # For CS and Clerk heads
                elif user_dept == 'C' and user.role == CustomUser.ROLE_CS_HEAD:
                    has_access = True
                elif user_dept == 'D' and user.role == CustomUser.ROLE_CLERK_HEAD:
                    if agniveer.trade in ['CLK', 'CLERK', 'Clerk', 'CLK_SD', 'CLK_IM']:
                        has_access = True
                else:
                    has_access = True
            else:
                has_access = False
        elif user.is_trainer:
            # Trainers can only see their assigned agniveers
            if agniveer in user.assigned_agniveers.all():
                has_access = True
        
        if not has_access:
            return HttpResponse("You don't have permission to view this report card.", status=403)
        
        # Determine which evaluations to show (department-specific)
        if user.is_commander or user.is_g_head:
            evaluations = EvaluationSheet.objects.filter(agniveer=agniveer).prefetch_related('marks')
            departments_to_show = ['A', 'B', 'C', 'D']
            is_department_view = False
        else:
            user_dept = user.get_department_code()
            evaluations = EvaluationSheet.objects.filter(agniveer=agniveer, department=user_dept).prefetch_related('marks')
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
        overall_pass = percentage >= 50
        
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
            agniveers = Agniveer.objects.all()  # Universal agniveers
        else:
            agniveers = user.assigned_agniveers.all()

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="agniveers.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Enrollment No', 'Name', 'Department', 'Batch',
            'Joining Date', 'Status', 'Total Score', 'Pass/Fail'
        ])

        for a in agniveers:
            writer.writerow([
                a.enrollment_number,
                a.get_full_name(),
                DEPARTMENT_NAMES.get(a.department, a.department),
                a.batch,
                a.joining_date.strftime('%Y-%m-%d'),
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
            sheets = sheets.filter(department=user.get_department_code())
        elif user.is_trainer:
            sheets = sheets.filter(agniveer__in=user.assigned_agniveers.all())

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
            sheets = sheets.filter(department=user.get_department_code())

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
        ws.merge_cells('A1:L1')
        title_cell = ws['A1']
        title_cell.value = "ARMY EVALUATION PORTAL - EVALUATION REPORT"
        title_cell.font = Font(bold=True, size=14, color="1B4332")
        title_cell.alignment = center
        ws.row_dimensions[1].height = 30

        # Headers
        headers = [
            'S.No', 'Enrollment No', 'Name', 'Department', 'Category',
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
                sheet.agniveer.enrollment_number,
                sheet.agniveer.get_full_name(),
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
        col_widths = [5, 15, 20, 12, 18, 16, 10, 10, 12, 12, 12, 8]
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
    def _export_battalion_results(self, request, status_filter):
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from django.db.models import Q
        from evaluation.models import Marks
        from evaluation.result_helpers import build_battalion_result_row
        from departments.models import Agniveer
        from evaluation.models import EvaluationSheet

        user = request.user
        is_pass_filter = status_filter == 'pass'
        sheets_with_marks_ids = Marks.objects.values_list('evaluation_sheet_id', flat=True).distinct()

        agniveers = Agniveer.objects.all()
        sheets = EvaluationSheet.objects.filter(
            department='A'
        ).filter(Q(is_locked=True) | Q(id__in=sheets_with_marks_ids)).select_related('agniveer').prefetch_related('marks')

        if user.is_battalion and user.battalion_unit:
            agniveers = agniveers.filter(bn_desp=user.battalion_unit)
            sheets = sheets.filter(agniveer__bn_desp=user.battalion_unit)

        rows = []
        for agniveer in agniveers.order_by('agniveer_no', 'enrollment_number'):
            ag_sheets = list(sheets.filter(agniveer=agniveer))
            if not ag_sheets:
                continue
            row = build_battalion_result_row(agniveer, ag_sheets)
            if row['is_pass'] == is_pass_filter:
                rows.append(row)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"BN {status_filter.upper()}"

        header_fill = PatternFill(start_color="D9EAF7", end_color="D9EAF7", fill_type="solid")
        title_fill = PatternFill(start_color="EAF2F8", end_color="EAF2F8", fill_type="solid")
        border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin')
        )
        center = Alignment(horizontal='center', vertical='center', wrap_text=True)

        headers = [
            'ARMY NO', 'RANK', 'TRADE', 'NAME',
            'COMMON MIL KNOWLEDGE (20)', 'BASIC TACTICE (CES) (40)',
            'TRADE PROFICIENCY (BTT) (40)', 'WPN & EQPT HANDLING (20)',
            'TOTAL (120)', 'ROUND FIGURE(120)'
        ]
        
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
                row['cmk'], row['ces'], row['btt'], row['wpn'],
                row['total'], row['round_figure']
            ]
            for col, value in enumerate(values, 1):
                cell = ws.cell(row=index + 2, column=col, value=value)
                cell.alignment = center
                cell.border = border

        widths = [15, 10, 15, 25, 25, 25, 25, 25, 15, 20]
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
    def _export_tts_results(self, request, status_filter):
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from django.db.models import Q
        from evaluation.models import Marks

        user = request.user
        is_pass_filter = status_filter == 'pass'
        sheets_with_marks_ids = Marks.objects.values_list('evaluation_sheet_id', flat=True).distinct()

        agniveers = Agniveer.objects.all()
        sheets = EvaluationSheet.objects.filter(
            department='B'
        ).filter(Q(is_locked=True) | Q(id__in=sheets_with_marks_ids)).select_related('agniveer').prefetch_related('marks')

        if getattr(user, 'tts_trade', None):
            if user.tts_trade == 'DMV':
                agniveers = agniveers.filter(trade='DMV')
                sheets = sheets.filter(agniveer__trade='DMV')
            elif user.tts_trade == 'OPEM':
                agniveers = agniveers.filter(trade='OPEM')
                sheets = sheets.filter(agniveer__trade='OPEM')
            elif user.tts_trade == 'OTHER':
                agniveers = agniveers.exclude(trade__in=['DMV', 'OPEM'])
                sheets = sheets.exclude(agniveer__trade__in=['DMV', 'OPEM'])

        rows = []
        for agniveer in agniveers.order_by('agniveer_no', 'enrollment_number'):
            ag_sheets = list(sheets.filter(agniveer=agniveer))
            if not ag_sheets:
                continue
            row = build_tts_result_row(agniveer, ag_sheets)
            if row['is_pass'] == is_pass_filter:
                rows.append(row)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"TTS {status_filter.upper()}"

        header_fill = PatternFill(start_color="D9EAF7", end_color="D9EAF7", fill_type="solid")
        title_fill = PatternFill(start_color="EAF2F8", end_color="EAF2F8", fill_type="solid")
        border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin')
        )
        center = Alignment(horizontal='center', vertical='center', wrap_text=True)
        left = Alignment(horizontal='left', vertical='center', wrap_text=True)

        headers = [
            'S. No.', 'Army No', 'Rank', 'Trade', 'Name', 'Unit',
            'Online Test-100', 'Convert in 20 Mks',
            'JOB-40', 'Convert in 10 Mks',
            'Practical-60', 'Convert in 10 Mks',
            'Grand Total-40', '%', 'Grading',
        ]
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
        ws.cell(row=1, column=1, value=f"SCREEN BOARD OF AGNIVEER: {status_filter.upper()} LIST").fill = title_fill
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
                index, row['army_no'], row['rank'], row['trade'], row['name'], row['unit'],
                row['online'], row['online_conv'],
                row['job'], row['job_conv'],
                row['practical'], row['practical_conv'],
                row['grand_total'], row['percentage'], row['grading'],
            ]
            for col, value in enumerate(values, 1):
                cell = ws.cell(row=index + 2, column=col, value=value)
                cell.alignment = left if col in [4, 5] else center
                cell.border = border

        widths = [7, 16, 10, 14, 28, 12, 15, 16, 10, 16, 14, 16, 16, 10, 12]
        for col, width in enumerate(widths, 1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = width
        ws.freeze_panes = 'A3'

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        log_action(user, 'EXPORT', f'Exported TTS {status_filter} dashboard results Excel', request)
        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="tts_{status_filter}_results.xlsx"'
        return response

    def get(self, request):
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        except ImportError:
            return HttpResponse("openpyxl not installed.", status=500)

        status_filter = request.GET.get('status', 'pass') # 'pass' or 'fail'
        is_pass_filter = status_filter == 'pass'
        
        user = request.user

        if user.is_department and user.get_department_code() == 'A':
            return self._export_battalion_results(request, status_filter)
        if user.is_department and user.get_department_code() == 'B':
            return self._export_tts_results(request, status_filter)
        
        # We need to replicate the pass/fail logic of the dashboard
        from evaluation.models import Marks
        from django.db.models import Q
        
        sheets_with_marks_ids = Marks.objects.values_list('evaluation_sheet_id', flat=True).distinct()
        all_sheets = EvaluationSheet.objects.filter(Q(is_locked=True) | Q(id__in=sheets_with_marks_ids)).prefetch_related('marks')
        
        is_dept = user.is_department
        dept_code = user.get_department_code() if is_dept else None
        
        if is_dept:
            all_sheets = all_sheets.filter(department=dept_code)
            if user.is_battalion:
                if user.battalion_unit:
                    all_sheets = all_sheets.filter(agniveer__bn_desp=user.battalion_unit)
                else:
                    from accounts.models import CustomUser
                    battalion_units = [choice[0] for choice in CustomUser.BATTALION_CHOICES]
                    all_sheets = all_sheets.filter(agniveer__bn_desp__in=battalion_units)
            elif dept_code == 'D':
                all_sheets = all_sheets.filter(agniveer__trade__in=['CLK', 'CLERK', 'Clerk', 'CLK_SD', 'CLK_IM'])
        else:
            # We use max_marks of valid sheets as per the updated dashboard logic
            pass
            
        filtered_agniveers = []
        all_agniveers = Agniveer.objects.prefetch_related('evaluations__marks')
        if is_dept:
            if user.is_battalion:
                if user.battalion_unit:
                    all_agniveers = all_agniveers.filter(bn_desp=user.battalion_unit)
                else:
                    from accounts.models import CustomUser
                    battalion_units = [choice[0] for choice in CustomUser.BATTALION_CHOICES]
                    all_agniveers = all_agniveers.filter(bn_desp__in=battalion_units)
            elif dept_code == 'D':
                all_agniveers = all_agniveers.filter(trade__in=['CLK', 'CLERK', 'Clerk', 'CLK_SD', 'CLK_IM'])
        
        for agniveer in all_agniveers:
            ag_sheets = all_sheets.filter(agniveer=agniveer)
            total_marks = sum(s.get_total_marks() for s in ag_sheets)
            max_marks = sum(s.get_max_marks() for s in ag_sheets)
                
            if max_marks > 0:
                percentage = (total_marks / max_marks) * 100
                is_pass = percentage >= 50
                if is_pass == is_pass_filter:
                    filtered_agniveers.append({
                        'enrollment_number': agniveer.enrollment_number,
                        'name': agniveer.get_full_name(),
                        'score': f"{total_marks}/{max_marks}",
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
        header_font = Font(color="FFFFFF", bold=True, size=11)
        center = Alignment(horizontal='center', vertical='center')

        # Title
        ws.merge_cells('A1:E1')
        title_cell = ws['A1']
        dept_text = f" - DEPARTMENT {dept_code}" if is_dept else ""
        title_cell.value = f"ARMY EVALUATION PORTAL{dept_text} - {status_filter.upper()} AGNIVEERS"
        title_cell.font = Font(bold=True, size=14, color=brand_color)
        title_cell.alignment = center
        ws.row_dimensions[1].height = 30

        # Headers
        headers = ['S.No', 'Enrollment No', 'Name', 'Score', 'Percentage']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=2, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center

        # Data
        for row_idx, data in enumerate(filtered_agniveers, 1):
            ws.cell(row=row_idx + 2, column=1, value=row_idx).alignment = center
            ws.cell(row=row_idx + 2, column=2, value=data['enrollment_number']).alignment = center
            ws.cell(row=row_idx + 2, column=3, value=data['name']).alignment = center
            ws.cell(row=row_idx + 2, column=4, value=data['score']).alignment = center
            ws.cell(row=row_idx + 2, column=5, value=f"{data['percentage']}%").alignment = center

        ws.column_dimensions['A'].width = 8
        ws.column_dimensions['B'].width = 18
        ws.column_dimensions['C'].width = 25
        ws.column_dimensions['D'].width = 15
        ws.column_dimensions['E'].width = 15

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
            evaluations = evaluations.filter(department=user_dept)
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


class ExportDepartmentPDFView(CommanderOrGHeadMixin, View):
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

        agniveers = Agniveer.objects.filter(evaluations__department=dept).distinct()
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
            data.append([
                str(i),
                a.enrollment_number,
                a.get_full_name(),
                a.batch,
                str(a.get_total_score()),
                a.get_pass_status(),
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
