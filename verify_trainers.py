#!/usr/bin/env python
"""Verify trainer auto-assignment"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'army_portal.settings')
django.setup()

from departments.models import Agniveer
from accounts.models import CustomUser

# Count agniveers without trainers
agniveers_no_trainers = Agniveer.objects.filter(assigned_trainers__isnull=True).count()
print(f"Agniveers without trainers: {agniveers_no_trainers}")

# Show agniveers with trainers assigned
agniveers_with_trainers = Agniveer.objects.filter(assigned_trainers__isnull=False).count()
print(f"Agniveers with trainers: {agniveers_with_trainers}")

# Show some examples
for agniveer in Agniveer.objects.all()[:3]:
    trainers = agniveer.assigned_trainers.all()
    print(f"\n{agniveer.enrollment_number}: {trainers.count()} trainer(s)")
    for trainer in trainers:
        print(f"  - {trainer.get_full_name()} ({trainer.get_role_display()})")

print("\n✓ Trainer auto-assignment verification complete!")
