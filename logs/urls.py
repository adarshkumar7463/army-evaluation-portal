from django.urls import path
from . import views

app_name = 'logs'

urlpatterns = [
    path('', views.ActivityLogListView.as_view(), name='activity_log'),
    path('export/', views.ExportLogsView.as_view(), name='export_logs'),
]
