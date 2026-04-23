#!/usr/bin/env python
"""Assign all trainers to all agniveers for universal access"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'army_portal.settings')
django.setup()

from departments.models import Agniveer
from accounts.models import CustomUser

# Get all trainers
all_trainers = CustomUser.objects.filter(
    role__in=['trainer_nco', 'trainer_jco', 'trainer_officer'],
    is_active=True
)

print(f"Total active trainers: {all_trainers.count()}")
print(f"Total agniveers: {Agniveer.objects.count()}")

# Assign all trainers to all agniveers
for agniveer in Agniveer.objects.all():
    agniveer.assigned_trainers.set(all_trainers)
    print(f"✓ {agniveer.enrollment_number}: assigned {all_trainers.count()} trainers")

print(f"\n✓ All trainers assigned to all agniveers for universal access!")

# Verify
unassigned = Agniveer.objects.filter(assigned_trainers__isnull=True).count()
print(f"✓ Agniveers without trainers: {unassigned} (should be 0)")
