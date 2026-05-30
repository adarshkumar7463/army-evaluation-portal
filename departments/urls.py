from django.urls import path
from . import views

app_name = 'departments'

urlpatterns = [
    # ── Registration Dashboard (Commander + G-Head) ──────────────────────────
    path('registration/', views.RegistrationDashboardView.as_view(), name='registration_dashboard'),
    path('registration/bulk-upload/', views.AgniveerBulkUploadView.as_view(), name='bulk_upload'),
    path('registration/excel-template/', views.AgniveerExcelTemplateView.as_view(), name='excel_template'),
    path('registration/delete-file/<str:filename>/', views.DeleteUploadedFileView.as_view(), name='delete_uploaded_file'),
    path('registration/<int:pk>/edit-ajax/', views.AgniveerEditAjaxView.as_view(), name='agniveer_edit_ajax'),

    # ── Standard Agniveer views (all roles) ──────────────────────────────────
    path('agniveers/', views.AgniveerListView.as_view(), name='agniveer_list'),
    path('agniveers/create/', views.AgniveerCreateView.as_view(), name='agniveer_create'),
    path('agniveers/<int:pk>/', views.AgniveerDetailView.as_view(), name='agniveer_detail'),
    path('agniveers/<int:pk>/edit/', views.AgniveerUpdateView.as_view(), name='agniveer_edit'),
    path('agniveers/<int:pk>/assign-trainer/', views.AssignTrainerView.as_view(), name='assign_trainer'),
]
