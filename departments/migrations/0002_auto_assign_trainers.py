# Generated migration: Auto-assign all department trainers to all agniveers

from django.db import migrations
from django.db.models import Q


def auto_assign_trainers(apps, schema_editor):
    """Auto-assign all trainers in a department to all agniveers in that department."""
    Agniveer = apps.get_model('departments', 'Agniveer')
    EvaluationSheet = apps.get_model('evaluation', 'EvaluationSheet')
    CustomUser = apps.get_model('accounts', 'CustomUser')
    
    dept_roles = ['dept_a', 'dept_b', 'dept_c', 'dept_d']
    
    # Get all agniveers
    for agniveer in Agniveer.objects.all():
        dept_code = None
        
        if agniveer.registered_by:
            if agniveer.registered_by.role in dept_roles:
                # If registered by department user, use their department
                dept_code = agniveer.registered_by.department
            elif agniveer.registered_by.role == 'g_head':
                # If registered by G_Head, infer from first evaluation sheet
                first_eval = EvaluationSheet.objects.filter(agniveer=agniveer).first()
                if first_eval:
                    dept_code = first_eval.department
        
        # If we found a department, assign trainers from that department
        if dept_code:
            trainers = CustomUser.objects.filter(
                role__in=['trainer_nco', 'trainer_jco', 'trainer_officer'],
                department=dept_code,
                is_active=True
            )
            agniveer.assigned_trainers.set(trainers)


def reverse_auto_assign(apps, schema_editor):
    """Reverse the assignment."""
    Agniveer = apps.get_model('departments', 'Agniveer')
    for agniveer in Agniveer.objects.all():
        agniveer.assigned_trainers.clear()


class Migration(migrations.Migration):

    dependencies = [
        ('departments', '0001_initial'),
        ('evaluation', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(auto_assign_trainers, reverse_auto_assign),
    ]
