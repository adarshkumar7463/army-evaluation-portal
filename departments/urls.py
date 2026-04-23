from django.urls import path
from . import views

app_name = 'departments'

urlpatterns = [
    path('agniveers/', views.AgniveerListView.as_view(), name='agniveer_list'),
    path('agniveers/create/', views.AgniveerCreateView.as_view(), name='agniveer_create'),
    path('agniveers/<int:pk>/', views.AgniveerDetailView.as_view(), name='agniveer_detail'),
    path('agniveers/<int:pk>/edit/', views.AgniveerUpdateView.as_view(), name='agniveer_edit'),
    path('agniveers/<int:pk>/assign-trainer/', views.AssignTrainerView.as_view(), name='assign_trainer'),
]
