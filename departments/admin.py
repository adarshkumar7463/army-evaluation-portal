from django.contrib import admin
from .models import Agniveer

@admin.register(Agniveer)
class AgniveerAdmin(admin.ModelAdmin):
    list_display = ['enrollment_number', 'get_full_name', 'batch', 'status']
    list_filter = ['status', 'batch']
    search_fields = ['enrollment_number', 'first_name', 'last_name']
