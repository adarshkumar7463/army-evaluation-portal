"""
Core App - Dashboard Views
Role-based dashboards with analytics
"""

from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.db.models import Count, Avg, Q, F
from django.utils import timezone
from datetime import timedelta
import json

from accounts.models import CustomUser
from departments.models import Agniveer
from evaluation.models import EvaluationSheet, Marks
from logs.models import ActivityLog


class DashboardView(LoginRequiredMixin, View):
    """
    Main dashboard - routes to role-specific dashboard.
    """
    def get(self, request):
        user = request.user
        if user.is_commander:
            return CommanderDashboard().get(request)
        elif user.is_g_head:
            return GHeadDashboard().get(request)
        elif user.is_department:
            return DepartmentDashboard().get(request)
        elif user.is_trainer:
            return TrainerDashboard().get(request)
        return render(request, 'core/dashboard.html', {})


class CommanderDashboard(LoginRequiredMixin, View):
    def get(self, request):
        # Key stats
        total_agniveers = Agniveer.objects.count()
        total_trainers = CustomUser.objects.filter(role__in=['trainer_nco', 'trainer_jco', 'trainer_officer']).count()
        total_g_heads = CustomUser.objects.filter(role='g_head').count()
        total_depts = CustomUser.objects.filter(role__in=['dept_a', 'dept_b', 'dept_c', 'dept_d']).count()

        # Get sheets with marks or locked
        sheets_with_marks_ids = Marks.objects.values_list('evaluation_sheet_id', flat=True).distinct()
        all_sheets = EvaluationSheet.objects.filter(Q(is_locked=True) | Q(id__in=sheets_with_marks_ids)).prefetch_related('marks')
        
        # Overall pass/fail stats at Agniveer level (Total possible marks across all departments)
        from evaluation.constants import get_overall_total_marks
        overall_max_marks = get_overall_total_marks()
        
        passed_agniveers = []
        failed_agniveers = []
        
        all_agniveers_qs = Agniveer.objects.prefetch_related('evaluations__marks')
        for agniveer in all_agniveers_qs:
            total_marks = 0
            valid_sheets = [s for s in agniveer.evaluations.all() if s.id in sheets_with_marks_ids or s.is_locked]
            for sheet in valid_sheets:
                total_marks += sheet.get_total_marks()
            
            if overall_max_marks > 0:
                percentage = (total_marks / overall_max_marks) * 100
                info = {
                    'name': agniveer.get_full_name(),
                    'enrollment': agniveer.enrollment_number,
                    'score': f"{total_marks}/{overall_max_marks}",
                    'percentage': round(percentage, 1),
                    'id': agniveer.pk
                }
                if percentage >= 50:
                    passed_agniveers.append(info)
                else:
                    failed_agniveers.append(info)

        pass_count = len(passed_agniveers)
        fail_count = len(failed_agniveers)
        completion_rate = (all_sheets.count() / max(total_agniveers * 28, 1)) * 100 if total_agniveers > 0 else 0

        # Department-wise breakdown
        dept_stats = {}
        dept_charts = {'labels': [], 'passed': [], 'failed': [], 'colors': ['#52B788', '#EF5350']}
        colors = {'A': '#1B4332', 'B': '#2D6A4F', 'C': '#40916C', 'D': '#52B788'}
        
        for dept in ['A', 'B', 'C', 'D']:
            dept_sheets = all_sheets.filter(department=dept)
            dept_pass = sum(1 for s in dept_sheets if s.is_pass())
            dept_fail = dept_sheets.count() - dept_pass
            dept_stats[dept] = {
                'passed': dept_pass,
                'failed': dept_fail,
                'total': dept_sheets.count(),
                'pass_rate': (dept_pass / max(dept_sheets.count(), 1)) * 100
            }
            dept_charts['labels'].append(f'Dept {dept}')
            dept_charts['passed'].append(dept_pass)
            dept_charts['failed'].append(dept_fail)

        # Test-type wise performance
        test_stats = {}
        test_labels = []
        test_avg_marks = []
        test_pass_rates = []
        
        for test_type, label in EvaluationSheet.TEST_TYPE_CHOICES:
            test_sheets = all_sheets.filter(test_type=test_type)
            if test_sheets.exists():
                avg_marks = sum(s.get_total_marks() for s in test_sheets) / test_sheets.count()
                test_pass = sum(1 for s in test_sheets if s.is_pass())
                pass_rate = (test_pass / test_sheets.count()) * 100
                
                test_stats[test_type] = {
                    'avg_marks': avg_marks,
                    'pass_rate': pass_rate,
                    'total': test_sheets.count()
                }
                test_labels.append(label)
                test_avg_marks.append(round(avg_marks, 1))
                test_pass_rates.append(round(pass_rate, 1))

        # Top performers
        top_agniveers = []
        agniveer_scores = []
        for agniveer in Agniveer.objects.all()[:10]:
            sheets = EvaluationSheet.objects.filter(agniveer=agniveer, is_locked=True)
            if sheets.exists():
                avg_score = sum(s.get_total_marks() for s in sheets) / sheets.count()
                agniveer_scores.append({
                    'name': agniveer.enrollment_number,
                    'score': round(avg_score, 1)
                })
        
        agniveer_scores.sort(key=lambda x: x['score'], reverse=True)
        top_agniveers = agniveer_scores[:10]

        # Monthly trend
        months = []
        month_counts = []
        month_pass = []
        for i in range(5, -1, -1):
            month_date = timezone.now() - timedelta(days=30 * i)
            month_sheets = all_sheets.filter(
                evaluation_date__year=month_date.year,
                evaluation_date__month=month_date.month
            )
            sheets_count = month_sheets.count()
            sheets_pass = sum(1 for s in month_sheets if s.is_pass())
            months.append(month_date.strftime('%b'))
            month_counts.append(sheets_count)
            month_pass.append(sheets_pass)

        # Recent activity
        recent_logs = ActivityLog.objects.select_related('user').order_by('-timestamp')[:15]

        # Test type performance by department
        test_type_data = {}
        for dept in ['A', 'B', 'C', 'D']:
            dept_test_data = {'labels': [], 'avg_marks': [], 'pass_rates': []}
            for test_type, label in EvaluationSheet.TEST_TYPE_CHOICES:
                dept_test_sheets = all_sheets.filter(test_type=test_type, department=dept)
                if dept_test_sheets.exists():
                    avg_marks = sum(s.get_total_marks() for s in dept_test_sheets) / dept_test_sheets.count()
                    test_pass = sum(1 for s in dept_test_sheets if s.is_pass())
                    pass_rate = (test_pass / dept_test_sheets.count()) * 100
                    dept_test_data['labels'].append(label)
                    dept_test_data['avg_marks'].append(round(avg_marks, 1))
                    dept_test_data['pass_rates'].append(round(pass_rate, 1))
            test_type_data[dept] = dept_test_data

        # Department agniveer counts
        dept_counts = {}
        for dept in ['A', 'B', 'C', 'D']:
            dept_counts[dept] = Agniveer.objects.filter(evaluations__department=dept).distinct().count()

        context = {
            'page_title': 'Commander Dashboard',
            'total_agniveers': total_agniveers,
            'total_trainers': total_trainers,
            'total_g_heads': total_g_heads,
            'total_depts': total_depts,
            'pass_count': pass_count,
            'fail_count': fail_count,
            'passed_agniveers': passed_agniveers,
            'failed_agniveers': failed_agniveers,
            'completion_rate': round(completion_rate, 1),
            'total_evaluations': all_sheets.count(),
            
            # Department chart data
            'dept_labels': json.dumps(dept_charts['labels']),
            'dept_passed': json.dumps(dept_charts['passed']),
            'dept_failed': json.dumps(dept_charts['failed']),
            'dept_stats': dept_stats,
            'dept_counts': dept_counts,
            
            # Test-type chart data
            'test_labels': json.dumps(test_labels),
            'test_avg_marks': json.dumps(test_avg_marks),
            'test_pass_rates': json.dumps(test_pass_rates),
            'test_type_data': json.dumps(test_type_data),
            
            # Monthly trend
            'months_labels': json.dumps(months),
            'month_counts': json.dumps(month_counts),
            'month_pass': json.dumps(month_pass),
            
            # Top performers
            'top_agniveers': top_agniveers,
            
            'recent_logs': recent_logs,
        }
        return render(request, 'core/commander_dashboard_advanced.html', context)


class GHeadDashboard(LoginRequiredMixin, View):
    def get(self, request):
        total_agniveers = Agniveer.objects.count()
        # Get sheets with marks or locked
        sheets_with_marks_ids = Marks.objects.values_list('evaluation_sheet_id', flat=True).distinct()
        all_sheets = EvaluationSheet.objects.filter(Q(is_locked=True) | Q(id__in=sheets_with_marks_ids)).prefetch_related('marks')
        
        # Overall pass/fail stats at Agniveer level (Total possible marks across all departments)
        from evaluation.constants import get_overall_total_marks
        overall_max_marks = get_overall_total_marks()
        
        passed_agniveers = []
        failed_agniveers = []
        
        all_agniveers_qs = Agniveer.objects.prefetch_related('evaluations__marks')
        for agniveer in all_agniveers_qs:
            total_marks = 0
            valid_sheets = [s for s in agniveer.evaluations.all() if s.id in sheets_with_marks_ids or s.is_locked]
            for sheet in valid_sheets:
                total_marks += sheet.get_total_marks()
            
            if overall_max_marks > 0:
                percentage = (total_marks / overall_max_marks) * 100
                info = {
                    'name': agniveer.get_full_name(),
                    'enrollment': agniveer.enrollment_number,
                    'score': f"{total_marks}/{overall_max_marks}",
                    'percentage': round(percentage, 1),
                    'id': agniveer.pk
                }
                if percentage >= 50:
                    passed_agniveers.append(info)
                else:
                    failed_agniveers.append(info)

        pass_count = len(passed_agniveers)
        fail_count = len(failed_agniveers)
        total_trainers = CustomUser.objects.filter(role__in=['trainer_nco', 'trainer_jco', 'trainer_officer']).count()
        completion_rate = (all_sheets.count() / max(total_agniveers * 28, 1)) * 100 if total_agniveers > 0 else 0

        # Department-wise breakdown
        dept_stats = {}
        dept_labels = []
        dept_passed = []
        dept_failed = []
        
        for dept in ['A', 'B', 'C', 'D']:
            dept_sheets = all_sheets.filter(department=dept)
            dept_pass = sum(1 for s in dept_sheets if s.is_pass())
            dept_fail = dept_sheets.count() - dept_pass
            dept_stats[dept] = {
                'passed': dept_pass,
                'failed': dept_fail,
                'total': dept_sheets.count(),
                'pass_rate': (dept_pass / max(dept_sheets.count(), 1)) * 100,
                'agniveers': total_agniveers
            }
            dept_labels.append(f'Dept {dept}')
            dept_passed.append(dept_pass)
            dept_failed.append(dept_fail)

        # Category-wise performance
        category_stats = {}
        category_labels = []
        category_pass_rates = []
        
        for category, label in EvaluationSheet.CATEGORY_CHOICES:
            cat_sheets = all_sheets.filter(category=category)
            if cat_sheets.exists():
                cat_pass = sum(1 for s in cat_sheets if s.is_pass())
                pass_rate = (cat_pass / cat_sheets.count()) * 100
                category_stats[category] = {
                    'passed': cat_pass,
                    'failed': cat_sheets.count() - cat_pass,
                    'total': cat_sheets.count(),
                    'pass_rate': pass_rate
                }
                category_labels.append(label)
                category_pass_rates.append(round(pass_rate, 1))

        # Monthly trend
        months = []
        month_counts = []
        month_pass = []
        for i in range(5, -1, -1):
            month_date = timezone.now() - timedelta(days=30 * i)
            month_sheets = all_sheets.filter(
                evaluation_date__year=month_date.year,
                evaluation_date__month=month_date.month
            )
            sheets_count = month_sheets.count()
            sheets_pass = sum(1 for s in month_sheets if s.is_pass())
            months.append(month_date.strftime('%b'))
            month_counts.append(sheets_count)
            month_pass.append(sheets_pass)

        # Test type performance by department
        test_type_data = {}
        for dept in ['A', 'B', 'C', 'D']:
            dept_test_data = {'labels': [], 'avg_marks': [], 'pass_rates': []}
            for test_type, label in EvaluationSheet.TEST_TYPE_CHOICES:
                dept_test_sheets = all_sheets.filter(test_type=test_type, department=dept)
                if dept_test_sheets.exists():
                    avg_marks = sum(s.get_total_marks() for s in dept_test_sheets) / dept_test_sheets.count()
                    test_pass = sum(1 for s in dept_test_sheets if s.is_pass())
                    pass_rate = (test_pass / dept_test_sheets.count()) * 100
                    dept_test_data['labels'].append(label)
                    dept_test_data['avg_marks'].append(round(avg_marks, 1))
                    dept_test_data['pass_rates'].append(round(pass_rate, 1))
            test_type_data[dept] = dept_test_data

        # Department agniveer counts
        dept_counts = {}
        for dept in ['A', 'B', 'C', 'D']:
            dept_counts[dept] = Agniveer.objects.filter(evaluations__department=dept).distinct().count()

        context = {
            'page_title': 'G Head Dashboard',
            'total_agniveers': total_agniveers,
            'total_trainers': total_trainers,
            'pass_count': pass_count,
            'fail_count': fail_count,
            'passed_agniveers': passed_agniveers,
            'failed_agniveers': failed_agniveers,
            'completion_rate': round(completion_rate, 1),
            'total_evaluations': all_sheets.count(),
            
            # Department chart
            'dept_labels': json.dumps(dept_labels),
            'dept_passed': json.dumps(dept_passed),
            'dept_failed': json.dumps(dept_failed),
            'dept_stats': dept_stats,
            'dept_counts': dept_counts,
            
            # Category chart
            'category_labels': json.dumps(category_labels),
            'category_pass_rates': json.dumps(category_pass_rates),
            'category_stats': category_stats,
            
            # Test type data
            'test_type_data': json.dumps(test_type_data),
            
            # Monthly trend
            'months_labels': json.dumps(months),
            'month_counts': json.dumps(month_counts),
            'month_pass': json.dumps(month_pass),
        }
        return render(request, 'core/g_head_dashboard_advanced.html', context)


class DepartmentDashboard(LoginRequiredMixin, View):
    def get(self, request):
        dept = request.user.get_department_code()
        agniveers = Agniveer.objects.all()
        trainers = CustomUser.objects.filter(
            role__in=['trainer_nco', 'trainer_jco', 'trainer_officer'],
            department=dept
        )

        # Get department-specific config
        from evaluation.constants import DEPT_CONFIG, get_dept_total_marks
        config = DEPT_CONFIG.get(dept, DEPT_CONFIG['A'])
        dept_max_marks = get_dept_total_marks(dept)
        
        # Include all sheets with marks (not just locked ones)
        sheets_with_marks_ids = Marks.objects.values_list('evaluation_sheet_id', flat=True).distinct()
        all_dept_sheets = EvaluationSheet.objects.filter(
            department=dept
        ).filter(Q(is_locked=True) | Q(id__in=sheets_with_marks_ids)).prefetch_related('marks')
        
        # Pass/Fail logic at Agniveer level for THIS department
        passed_agniveers = []
        failed_agniveers = []
        
        all_agniveers = Agniveer.objects.prefetch_related('evaluations__marks')
        for agniveer in all_agniveers:
            dept_evals = all_dept_sheets.filter(agniveer=agniveer)
            total_score = sum(e.get_total_marks() for e in dept_evals)
            
            if dept_max_marks > 0:
                percentage = (total_score / dept_max_marks) * 100
                info = {
                    'name': agniveer.get_full_name(),
                    'enrollment': agniveer.enrollment_number,
                    'score': f"{total_score}/{dept_max_marks}",
                    'percentage': round(percentage, 1),
                    'id': agniveer.pk
                }
                if percentage >= 50:
                    passed_agniveers.append(info)
                else:
                    failed_agniveers.append(info)

        pass_count = len(passed_agniveers)
        fail_count = len(failed_agniveers)
        
        total_tests_expected = all_agniveers.count() * len(config['test_types'])
        completion_rate = (all_dept_sheets.count() / max(total_tests_expected, 1)) * 100 if all_agniveers.count() > 0 else 0

        # Chart data for Pie Chart (Overall Pass/Fail in this Dept)
        pie_labels = ['Passed', 'Failed']
        pie_data = [pass_count, fail_count]

        # Slicer (Polar Area) for categories
        slicer_labels = []
        slicer_data = []
        
        for cat_key, cat_label in config['categories']:
            cat_sheets = all_dept_sheets.filter(category=cat_key)
            if cat_sheets.exists():
                cat_pass = sum(1 for s in cat_sheets if s.is_pass())
                pass_rate = (cat_pass / cat_sheets.count()) * 100
                slicer_labels.append(cat_label)
                slicer_data.append(round(pass_rate, 1))

        # Category-wise bar chart
        category_bar_labels = []
        category_pass_rates = []
        for cat_key, cat_label in config['categories']:
            cat_sheets = all_dept_sheets.filter(category=cat_key)
            if cat_sheets.exists():
                cat_pass = sum(1 for s in cat_sheets if s.is_pass())
                pass_rate = (cat_pass / cat_sheets.count()) * 100
                category_bar_labels.append(cat_label)
                category_pass_rates.append(round(pass_rate, 1))

        # Test type-wise performance
        test_labels = []
        test_avg_marks = []
        test_pass_rates = []
        
        for test_key, test_label in config['test_types']:
            test_sheets = all_dept_sheets.filter(test_type=test_key)
            if test_sheets.exists():
                avg_marks = sum(s.get_total_marks() for s in test_sheets) / test_sheets.count()
                test_pass = sum(1 for s in test_sheets if s.is_pass())
                test_pass_rate = (test_pass / test_sheets.count()) * 100
                test_labels.append(test_label)
                test_avg_marks.append(round(avg_marks, 1))
                test_pass_rates.append(round(test_pass_rate, 1))

        # Monthly trend for this department
        months = []
        month_counts = []
        month_pass = []
        for i in range(5, -1, -1):
            month_date = timezone.now() - timedelta(days=30 * i)
            month_sheets = all_dept_sheets.filter(
                evaluation_date__year=month_date.year,
                evaluation_date__month=month_date.month
            )
            sheets_count = month_sheets.count()
            sheets_pass = sum(1 for s in month_sheets if s.is_pass())
            months.append(month_date.strftime('%b'))
            month_counts.append(sheets_count)
            month_pass.append(sheets_pass)

        context = {
            'dept': dept,
            'total_agniveers': all_agniveers.count(),
            'total_trainers': trainers.count(),
            'completion_rate': round(completion_rate, 1),
            'pass_count': pass_count,
            'fail_count': fail_count,
            'passed_agniveers': json.dumps(passed_agniveers),
            'failed_agniveers': json.dumps(failed_agniveers),
            'pie_labels': json.dumps(pie_labels),
            'pie_data': json.dumps(pie_data),
            'slicer_labels': json.dumps(slicer_labels),
            'slicer_data': json.dumps(slicer_data),
            'category_bar_labels': json.dumps(category_bar_labels),
            'category_pass_rates': json.dumps(category_pass_rates),
            'test_labels': json.dumps(test_labels),
            'test_avg_marks': json.dumps(test_avg_marks),
            'test_pass_rates': json.dumps(test_pass_rates),
            'months_labels': json.dumps(months),
            'month_counts': json.dumps(month_counts),
            'month_pass': json.dumps(month_pass),
        }
        return render(request, 'core/department_dashboard_advanced.html', context)


class TrainerDashboard(LoginRequiredMixin, View):
    def get(self, request):
        trainer = request.user
        agniveers = Agniveer.objects.all()

        # Evaluations done by this trainer
        my_marks = Marks.objects.filter(evaluator=trainer).select_related('evaluation_sheet__agniveer')

        context = {
            'page_title': f'{trainer.get_role_display()} Dashboard',
            'total_assigned': agniveers.count(),
            'evaluations_done': my_marks.count(),
            'assigned_agniveers': agniveers[:10],
        }
        return render(request, 'core/trainer_dashboard.html', context)


class AgniveerSearchView(LoginRequiredMixin, View):
    """
    Search Agniveer by enrollment number (army number) and show profile with report card.
    """
    def get(self, request):
        query = request.GET.get('q', '').strip()
        agniveer = None
        if query:
            try:
                agniveer = Agniveer.objects.get(enrollment_number__iexact=query)
            except Agniveer.DoesNotExist:
                pass

        if agniveer:
            # Get evaluations grouped by department
            evaluations = EvaluationSheet.objects.filter(
                agniveer=agniveer
            ).prefetch_related('marks').order_by('department', 'category', 'test_type')

            dept_evaluations = {}
            for dept in ['A', 'B', 'C', 'D']:
                dept_evals = evaluations.filter(department=dept)
                if dept_evals.exists():
                    dept_evaluations[dept] = {
                        'on_field': dept_evals.filter(category='on_field'),
                        'trade': dept_evals.filter(category='trade'),
                        'total_locked': sum(e.get_total_marks() for e in dept_evals if e.is_locked),
                        'max_total': sum(e.get_max_marks() for e in dept_evals if e.is_locked),
                    }

            grand_total = sum(e.get_total_marks() for e in evaluations if e.is_locked)
            max_total = sum(e.get_max_marks() for e in evaluations if e.is_locked)
            percentage = round((grand_total / max_total * 100), 2) if max_total > 0 else 0
            overall_pass = percentage >= 50

            # Chart data
            chart_data = {
                'departments': [],
                'on_field_totals': [],
                'trade_totals': [],
                'overall_totals': []
            }
            for dept in ['A', 'B', 'C', 'D']:
                if dept in dept_evaluations:
                    data = dept_evaluations[dept]
                    chart_data['departments'].append(f'Dept {dept}')
                    on_field_total = sum(e.get_total_marks() for e in data['on_field'] if e.is_locked)
                    trade_total = sum(e.get_total_marks() for e in data['trade'] if e.is_locked)
                    chart_data['on_field_totals'].append(on_field_total)
                    chart_data['trade_totals'].append(trade_total)
                    chart_data['overall_totals'].append(on_field_total + trade_total)
                else:
                    chart_data['departments'].append(f'Dept {dept}')
                    chart_data['on_field_totals'].append(0)
                    chart_data['trade_totals'].append(0)
                    chart_data['overall_totals'].append(0)

            context = {
                'agniveer': agniveer,
                'dept_evaluations': dept_evaluations,
                'chart_data': chart_data,
                'grand_total': grand_total,
                'max_total': max_total,
                'percentage': percentage,
                'overall_pass': overall_pass,
                'query': query,
            }
            return render(request, 'core/agniveer_profile.html', context)
        else:
            return render(request, 'core/search.html', {'query': query, 'not_found': bool(query)})
