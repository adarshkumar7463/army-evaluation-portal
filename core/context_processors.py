"""
Core App - Context Processors
Global context available in all templates
"""

from departments.models import Agniveer
from evaluation.models import EvaluationSheet


def global_context(request):
    if not request.user.is_authenticated:
        return {}

    user = request.user
    context = {
        'user_role': user.role,
        'is_commander': user.is_commander,
        'is_g_head': user.is_g_head,
        'is_department': user.is_department,
        'is_trainer': user.is_trainer,
    }

    # Quick stats for navbar
    try:
        if user.is_commander or user.is_g_head or user.is_department:
            context['total_agniveers'] = Agniveer.objects.count()
        elif user.is_trainer:
            context['total_agniveers'] = user.assigned_agniveers.count()
    except Exception:
        context['total_agniveers'] = 0

    return context
