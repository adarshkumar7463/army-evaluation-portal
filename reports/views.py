"""
Reports App - Views
PDF, Excel, and CSV export functionality
"""

import csv
import io
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, FileResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone

from departments.models import Agniveer
from evaluation.models import EvaluationSheet
from accounts.mixins import AnyStaffMixin, CommanderOrGHeadMixin
from logs.utils import log_action


class ReportDashboardView(AnyStaffMixin, View):
    template_name = 'reports/report_dashboard.html'

    def get(self, request):
        from accounts.models import User
        user = request.user
        if user.is_commander or user.is_g_head:
            total = Agniveer.objects.count()
            sheets = EvaluationSheet.objects.filter(is_locked=True)
            # Get total trainers (NCO, JCO, Officer) from all departments
            total_trainers = User.objects.filter(role__in=[User.ROLE_NCO, User.ROLE_JCO, User.ROLE_OFFICER]).count()
        elif user.is_department:
            dept = user.get_department_code()
            total = Agniveer.objects.count()  # Universal agniveers
            sheets = EvaluationSheet.objects.filter(department=dept, is_locked=True)
            # Get trainers for this department
            total_trainers = User.objects.filter(
                role__in=[User.ROLE_NCO, User.ROLE_JCO, User.ROLE_OFFICER]
            ).count()
        else:
            total = user.assigned_agniveers.count()
            sheets = EvaluationSheet.objects.filter(
                agniveer__in=user.assigned_agniveers.all(), is_locked=True
            )
            total_trainers = 0

        pass_count = sum(1 for s in sheets if s.is_pass())
        fail_count = sheets.count() - pass_count

        return render(request, self.template_name, {
            'total_agniveers': total,
            'total_trainers': total_trainers,
            'pass_count': pass_count,
            'fail_count': fail_count,
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
                f'Dept {a.department}',
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
                f'Dept {sheet.department}',
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
                f'Dept {sheet.department}',
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
