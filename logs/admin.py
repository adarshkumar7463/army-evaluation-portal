from django.contrib import admin
from .models import ActivityLog

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'user', 'role', 'action', 'description', 'ip_address']
    list_filter = ['action', 'role']
    search_fields = ['user__username', 'description']
    readonly_fields = ['timestamp']
