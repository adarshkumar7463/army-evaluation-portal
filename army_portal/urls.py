"""
Army Evaluation Portal - Main URL Configuration
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.offline_views import OfflinePageView, offline_sync_api, offline_cache_api, offline_status_api

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('', include('core.urls', namespace='core')),
    path('departments/', include('departments.urls', namespace='departments')),
    path('evaluation/', include('evaluation.urls', namespace='evaluation')),
    path('reports/', include('reports.urls', namespace='reports')),
    path('logs/', include('logs.urls', namespace='logs')),
    
    # Offline Support URLs
    path('offline/', OfflinePageView.as_view(), name='offline_page'),
    path('api/offline/sync/', offline_sync_api, name='offline_sync'),
    path('api/offline/cache/', offline_cache_api, name='offline_cache'),
    path('api/offline/status/', offline_status_api, name='offline_status'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

admin.site.site_header = "Army Evaluation Portal"
admin.site.site_title = "Army Portal Admin"
admin.site.index_title = "Welcome to Army Evaluation Portal"
