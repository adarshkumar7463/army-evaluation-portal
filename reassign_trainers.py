#!/usr/bin/env python
"""Clear trainer assignments and re-run migration"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'army_portal.settings')
django.setup()

from departments.models import Agniveer
from accounts.models import CustomUser
from evaluation.models import EvaluationSheet

# Clear all assignments first
for agniveer in Agniveer.objects.all():
    agniveer.assigned_trainers.clear()

print("Cleared all trainer assignments")

# Now reassign based on improved logic
dept_roles = ['dept_a', 'dept_b', 'dept_c', 'dept_d']

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
        print(f"✓ {agniveer.enrollment_number}: assigned {trainers.count()} trainers from Dept {dept_code}")
    else:
        print(f"✗ {agniveer.enrollment_number}: could not determine department")

# Verify
unassigned = Agniveer.objects.filter(assigned_trainers__isnull=True).count()
assigned = Agniveer.objects.filter(assigned_trainers__isnull=False).count()
print(f"\n✓ Total assigned: {assigned}, Unassigned: {unassigned}")
