"""
Logs App - Views
"""

from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
import csv

from .models import ActivityLog
from accounts.mixins import CommanderOrGHeadMixin


class ActivityLogListView(CommanderOrGHeadMixin, ListView):
    model = ActivityLog
    template_name = 'logs/activity_log.html'
    context_object_name = 'logs'
    paginate_by = 50

    def get_queryset(self):
        queryset = ActivityLog.objects.select_related('user').all()
        action = self.request.GET.get('action')
        user_id = self.request.GET.get('user')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')

        if action:
            queryset = queryset.filter(action=action)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if date_from:
            queryset = queryset.filter(timestamp__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(timestamp__date__lte=date_to)

        return queryset

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['action_choices'] = ActivityLog.ACTION_CHOICES
        return ctx


class ExportLogsView(CommanderOrGHeadMixin, ListView):
    def get(self, request):
        logs = ActivityLog.objects.select_related('user').all()[:1000]
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="activity_logs.csv"'
        writer = csv.writer(response)
        writer.writerow(['Timestamp', 'User', 'Role', 'Action', 'Description', 'IP Address'])
        for log in logs:
            writer.writerow([
                log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                log.user.username if log.user else 'N/A',
                log.role or 'N/A',
                log.get_action_display(),
                log.description,
                log.ip_address or 'N/A',
            ])
        return response
