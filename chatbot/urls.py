from django.urls import path
from . import views

app_name = 'chatbot'

urlpatterns = [
    path('', views.ChatbotView.as_view(), name='chatbot_home'),
    path('query/', views.ChatbotQueryApiView.as_view(), name='chatbot_query'),
    path('models/', views.ChatbotModelsApiView.as_view(), name='chatbot_models'),
]
