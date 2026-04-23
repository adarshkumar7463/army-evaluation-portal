from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.ReportDashboardView.as_view(), name='report_dashboard'),
    path('export/agniveers/csv/', views.ExportAgniveersCSVView.as_view(), name='export_agniveers_csv'),
    path('export/evaluations/csv/', views.ExportEvaluationsCSVView.as_view(), name='export_evaluations_csv'),
    path('export/evaluations/excel/', views.ExportExcelView.as_view(), name='export_excel'),
    path('export/report-card/<int:pk>/pdf/', views.ExportPDFReportCardView.as_view(), name='export_report_card_pdf'),
    path('export/department/<str:dept>/pdf/', views.ExportDepartmentPDFView.as_view(), name='export_dept_pdf'),
]
