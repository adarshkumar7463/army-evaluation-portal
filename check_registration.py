#!/usr/bin/env python
"""Check agniveer registration status"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'army_portal.settings')
django.setup()

from departments.models import Agniveer

# Check agniveers that weren't assigned
unassigned = Agniveer.objects.filter(assigned_trainers__isnull=True)
print(f"Total unassigned agniveers: {unassigned.count()}")

for agniveer in unassigned[:5]:
    print(f"\n{agniveer.enrollment_number}:")
    print(f"  registered_by: {agniveer.registered_by}")
    if agniveer.registered_by:
        print(f"  registered_by.role: {agniveer.registered_by.role}")
        print(f"  registered_by.department: {agniveer.registered_by.department}")

# Check assigned agniveers to see pattern
assigned = Agniveer.objects.filter(assigned_trainers__isnull=False).first()
if assigned:
    print(f"\nExample assigned agniveer:")
    print(f"  {assigned.enrollment_number}")
    print(f"  registered_by: {assigned.registered_by}")
    if assigned.registered_by:
        print(f"  registered_by.role: {assigned.registered_by.role}")
        print(f"  registered_by.department: {assigned.registered_by.department}")
