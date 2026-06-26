from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/create/g-head/', views.CreateGHeadView.as_view(), name='create_g_head'),
    path('users/create/department/', views.CreateDepartmentView.as_view(), name='create_department'),
    path('users/create/registration/', views.CreateRegistrationOfficeView.as_view(), name='create_registration'),
    path('users/<int:pk>/toggle/', views.ToggleUserActiveView.as_view(), name='toggle_user'),
    # Password change for users (visible link for commanders)
    path('password_change/', auth_views.PasswordChangeView.as_view(template_name='registration/password_change_form.html'), name='password_change'),
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='registration/password_change_done.html'), name='password_change_done'),
]
