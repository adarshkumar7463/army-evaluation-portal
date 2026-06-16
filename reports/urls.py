from django.urls import path
from . import views

app_name = 'reports'



urlpatterns = [
    # Existing URLs...
    path('dashboard/', views.ReportDashboardView.as_view(), name='report_dashboard'),
    
    # Department-specific report card views
    path('tts-report-card/', views.TTSReportCardView.as_view(), name='tts_report_card'),
    path('battalion-report-card/', views.BattalionReportCardView.as_view(), name='battalion_report_card'),
    path('cs-report-card/', views.CSReportCardView.as_view(), name='cs_report_card'),
    path('clerk-report-card/', views.ClerkReportCardView.as_view(), name='clerk_report_card'),
    
    # Individual report card detail views
    path('report-card/<int:pk>/', views.ReportCardDetailView.as_view(), name='report_card_detail'),

    # Export URLs
    path('export/agniveers/csv/', views.ExportAgniveersCSVView.as_view(), name='export_agniveers_csv'),
    path('export/evaluations/csv/', views.ExportEvaluationsCSVView.as_view(), name='export_evaluations_csv'),
    path('export/evaluations/excel/', views.ExportExcelView.as_view(), name='export_excel'),
    path('export/report-card/<int:pk>/pdf/', views.ExportPDFReportCardView.as_view(), name='export_report_card_pdf'),
    path('export/department/<str:dept>/pdf/', views.ExportDepartmentPDFView.as_view(), name='export_dept_pdf'),
    path('export/dashboard/excel/', views.ExportDashboardResultsExcelView.as_view(), name='export_dashboard_excel'),
    path('export/test/<str:dept>/<str:test_type>/excel/', views.ExportTestTypeExcelView.as_view(), name='export_test_excel'),
    path('test-results/<str:dept>/<str:test_type>/', views.TestTypeResultsView.as_view(), name='test_results'),
    path('dept-test-results/<str:dept>/<str:test_type>/', views.DeptTestResultsView.as_view(), name='dept_test_results'),
    path('api/test-results/<str:dept>/<str:test_type>/json/', views.DeptTestResultsJsonView.as_view(), name='test_results_json'),
]
