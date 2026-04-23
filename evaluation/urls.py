from django.urls import path
from . import views

app_name = 'evaluation'

urlpatterns = [
    path('', views.EvaluationListView.as_view(), name='evaluation_list'),
    path('create/', views.EvaluationCreateView.as_view(), name='evaluation_create'),
    path('agniveer/<int:pk>/evaluate/', views.AgniveerEvaluateView.as_view(), name='evaluate_agniveer'),
    path('<int:pk>/', views.EvaluationDetailView.as_view(), name='evaluation_detail'),
    path('<int:pk>/marks/', views.MarksEntryView.as_view(), name='marks_entry'),
    path('<int:pk>/lock/', views.LockSheetView.as_view(), name='lock_sheet'),
    path('<int:pk>/unlock/', views.UnlockSheetView.as_view(), name='unlock_sheet'),
    path('report-card/<int:pk>/', views.AgniveerReportCardView.as_view(), name='report_card'),
]
