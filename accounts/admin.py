from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'get_full_name', 'role', 'department', 'service_number', 'is_active']
    list_filter = ['role', 'department', 'is_active']
    search_fields = ['username', 'first_name', 'last_name', 'service_number']
    fieldsets = UserAdmin.fieldsets + (
        ('Army Details', {'fields': ('role', 'department', 'service_number', 'rank', 'phone', 'profile_photo', 'created_by', 'last_login_ip')}),
    )
