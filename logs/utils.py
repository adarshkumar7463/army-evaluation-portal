"""
Logs App - Utility Functions
"""


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def log_action(user, action, description, request=None):
    """
    Create an activity log entry.
    """
    try:
        from .models import ActivityLog
        ip = get_client_ip(request) if request else None
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:255] if request else ''
        ActivityLog.objects.create(
            user=user,
            role=user.role if user else '',
            action=action,
            description=description,
            ip_address=ip,
            user_agent=user_agent,
        )
    except Exception:
        pass  # Never let logging break the app
