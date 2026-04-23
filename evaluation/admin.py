from django.contrib import admin
from .models import EvaluationSheet, Marks

class MarksInline(admin.TabularInline):
    model = Marks
    extra = 0

@admin.register(EvaluationSheet)
class EvaluationSheetAdmin(admin.ModelAdmin):
    list_display = ['agniveer', 'test_type', 'department', 'evaluation_date', 'is_locked', 'get_total_marks']
    list_filter = ['category', 'test_type', 'is_locked', 'department']
    inlines = [MarksInline]

@admin.register(Marks)
class MarksAdmin(admin.ModelAdmin):
    list_display = ['evaluation_sheet', 'evaluator_type', 'marks', 'evaluator', 'submitted_at']
