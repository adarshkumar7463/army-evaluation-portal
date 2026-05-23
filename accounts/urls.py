from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/create/g-head/', views.CreateGHeadView.as_view(), name='create_g_head'),
    path('users/create/department/', views.CreateDepartmentView.as_view(), name='create_department'),
    path('users/create/trainer/', views.CreateTrainerView.as_view(), name='create_trainer'),
    path('users/create/registration/', views.CreateRegistrationOfficeView.as_view(), name='create_registration'),
    path('my-team/', views.MyTeamListView.as_view(), name='my_team'),
    path('my-team/create/', views.CreateTrainerView.as_view(), name='create_my_team_trainer'),
    path('users/<int:pk>/toggle/', views.ToggleUserActiveView.as_view(), name='toggle_user'),
]
