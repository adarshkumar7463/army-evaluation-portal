#!/usr/bin/env python
"""Check trainer availability by department"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'army_portal.settings')
django.setup()

from accounts.models import CustomUser

for dept in ['A', 'B', 'C', 'D']:
    trainers = CustomUser.objects.filter(
        role__in=['trainer_nco', 'trainer_jco', 'trainer_officer'],
        department=dept,
        is_active=True
    )
    print(f"Dept {dept}: {trainers.count()} trainers")
    for trainer in trainers:
        print(f"  - {trainer.get_full_name()} ({trainer.get_role_display()})")
