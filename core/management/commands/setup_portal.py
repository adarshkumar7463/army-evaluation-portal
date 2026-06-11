"""
Management Command: setup_portal
Creates sample data for the Army Evaluation Portal.
Usage: python manage.py setup_portal
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
import random


DEPARTMENT_NAMES = {
    'A': 'Battalion',
    'B': 'TTS',
    'C': 'CS',
    'D': 'Clerk',
}


class Command(BaseCommand):
    help = 'Setup Army Evaluation Portal with initial data'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n🪖 Setting up Army Evaluation Portal...\n'))

        from accounts.models import CustomUser
        from departments.models import Agniveer
        from evaluation.models import EvaluationSheet, Marks

        # ─── 1. Commander ───
        if not CustomUser.objects.filter(role='commander').exists():
            commander = CustomUser.objects.create_superuser(
                username='commander',
                password='Commander@123',
                email='commander@army.mil',
                first_name='Gen.',
                last_name='Commander',
                role='commander',
                service_number='CMD001',
                rank='General',
            )
            self.stdout.write(self.style.SUCCESS('✅ Commander created: commander / Commander@123'))
        else:
            commander = CustomUser.objects.filter(role='commander').first()
            self.stdout.write('ℹ️  Commander already exists')

        # ─── 2. G Head ───
        if not CustomUser.objects.filter(role='g_head').exists():
            g_head = CustomUser.objects.create_user(
                username='ghead',
                password='GHead@123',
                first_name='Col.',
                last_name='GHead',
                email='ghead@army.mil',
                role='g_head',
                service_number='GH001',
                rank='Colonel',
                created_by=commander,
            )
            self.stdout.write(self.style.SUCCESS('✅ G Head created: ghead / GHead@123'))
        else:
            g_head = CustomUser.objects.filter(role='g_head').first()

        # ─── 3. Department Users ───
        dept_data = [
            ('dept_a', 'deptA', 'Maj.', 'DeptA', 'A', 'DA001', 'Major'),
            ('dept_b', 'deptB', 'Maj.', 'DeptB', 'B', 'DB001', 'Major'),
            ('dept_c', 'deptC', 'Maj.', 'DeptC', 'C', 'DC001', 'Major'),
            ('dept_d', 'deptD', 'Maj.', 'DeptD', 'D', 'DD001', 'Major'),
        ]
        dept_users = {}
        for role, uname, fname, lname, dept, sno, rank in dept_data:
            u, created = CustomUser.objects.get_or_create(
                username=uname,
                defaults={
                    'first_name': fname, 'last_name': lname,
                    'role': role, 'department': dept,
                    'service_number': sno, 'rank': rank,
                    'created_by': g_head,
                }
            )
            if created:
                u.set_password('Dept@1234')
                u.save()
                self.stdout.write(self.style.SUCCESS(f'✅ {DEPARTMENT_NAMES.get(dept, dept)}: {uname} / Dept@1234'))
            dept_users[dept] = u

        # ─── 4. Trainers ───
        trainer_data = [
            ('trainer_nco', 'ncoA', 'Hav.', 'NCO_A', 'A', 'NA001', 'Havildar'),
            ('trainer_jco', 'jcoA', 'Nb Sub', 'JCO_A', 'A', 'JA001', 'Naib Subedar'),
            ('trainer_officer', 'officerA', 'Lt.', 'Off_A', 'A', 'OA001', 'Lieutenant'),
            ('trainer_nco', 'ncoB', 'Hav.', 'NCO_B', 'B', 'NB001', 'Havildar'),
            ('trainer_jco', 'jcoB', 'Nb Sub', 'JCO_B', 'B', 'JB001', 'Naib Subedar'),
            ('trainer_officer', 'officerB', 'Lt.', 'Off_B', 'B', 'OB001', 'Lieutenant'),
        ]
        trainers = {}
        for role, uname, fname, lname, dept, sno, rank in trainer_data:
            u, created = CustomUser.objects.get_or_create(
                username=uname,
                defaults={
                    'first_name': fname, 'last_name': lname,
                    'role': role, 'department': dept,
                    'service_number': sno, 'rank': rank,
                    'created_by': dept_users.get(dept, g_head),
                }
            )
            if created:
                u.set_password('Trainer@123')
                u.save()
                self.stdout.write(self.style.SUCCESS(f'✅ Trainer: {uname} / Trainer@123'))
            trainers.setdefault(dept, []).append(u)

        # ─── 5. Agniveers ───
        first_names = ['Arjun', 'Ravi', 'Suresh', 'Mohit', 'Deepak', 'Akash', 'Vikram', 'Rohit', 'Nikhil', 'Sanjay',
                       'Priya', 'Anita', 'Kavita', 'Sunita', 'Pooja', 'Nisha', 'Rekha', 'Geeta', 'Seema', 'Neha']
        last_names = ['Sharma', 'Verma', 'Singh', 'Yadav', 'Kumar', 'Gupta', 'Tiwari', 'Mishra', 'Joshi', 'Patel']

        agniveer_count = 0
        created_agniveers = {dept: [] for dept in 'ABCD'}

        for dept in 'ABCD':
            dept_user = dept_users[dept]
            for i in range(1, 11):  # 10 per department
                enroll = f'AGN{dept}2024{i:03d}'
                if not Agniveer.objects.filter(enrollment_number=enroll).exists():
                    fname = random.choice(first_names)
                    lname = random.choice(last_names)
                    dob = date(2002, random.randint(1,12), random.randint(1,28))
                    joining = date(2024, random.randint(1,6), random.randint(1,28))
                    a = Agniveer.objects.create(
                        enrollment_number=enroll,
                        first_name=fname,
                        last_name=lname,
                        date_of_birth=dob,
                        gender=random.choice(['M', 'M', 'M', 'F']),
                        phone=f'98{random.randint(10000000,99999999)}',
                        department=dept,
                        batch=f'Batch 2024-{dept}',
                        joining_date=joining,
                        status='active',
                        registered_by=dept_user,
                    )
                    # Assign trainers if available (guarded — field may be removed)
                    if dept in trainers and hasattr(a, 'assigned_trainers'):
                        a.assigned_trainers.set(trainers[dept])
                    created_agniveers[dept].append(a)
                    agniveer_count += 1
                else:
                    existing = Agniveer.objects.get(enrollment_number=enroll)
                    created_agniveers[dept].append(existing)

        self.stdout.write(self.style.SUCCESS(f'✅ {agniveer_count} Agniveers created'))

        # ─── 6. Evaluations ───
        test_types = ['physical', 'weapon', 'assessment', 'viva']
        test_category = {'physical': 'on_field', 'weapon': 'on_field', 'assessment': 'trade', 'viva': 'trade'}
        eval_count = 0

        for dept, agniveers_list in created_agniveers.items():
            dept_trainers = trainers.get(dept, [])
            nco = next((t for t in dept_trainers if t.is_nco), None)
            jco = next((t for t in dept_trainers if t.is_jco), None)
            officer = next((t for t in dept_trainers if t.is_officer), None)

            for agniveer in agniveers_list[:5]:  # Evaluate first 5 per dept
                for test_type in test_types:
                    if EvaluationSheet.objects.filter(agniveer=agniveer, test_type=test_type).exists():
                        continue
                    sheet = EvaluationSheet.objects.create(
                        agniveer=agniveer,
                        category=test_category[test_type],
                        test_type=test_type,
                        department=dept,
                        evaluation_date=date.today() - timedelta(days=random.randint(1,30)),
                        created_by=dept_users.get(dept),
                    )
                    # Add marks for all 3 evaluators
                    for evaluator_type, evaluator in [('nco', nco), ('jco', jco), ('officer', officer)]:
                        if evaluator:
                            m = random.randint(10, 20)
                            Marks.objects.create(
                                evaluation_sheet=sheet,
                                evaluator=evaluator,
                                evaluator_type=evaluator_type,
                                marks=m,
                                remarks=f'Good performance in {test_type}',
                            )
                    # Lock the sheet
                    if sheet.can_be_locked():
                        sheet.is_locked = True
                        sheet.locked_by = dept_users.get(dept)
                        sheet.locked_at = timezone.now()
                        sheet.save()
                    eval_count += 1

        self.stdout.write(self.style.SUCCESS(f'✅ {eval_count} Evaluation sheets created & locked'))

        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('🎉 SETUP COMPLETE! Login credentials:'))
        self.stdout.write('='*60)
        self.stdout.write(self.style.SUCCESS('Commander : commander    / Commander@123'))
        self.stdout.write(self.style.SUCCESS('G Head    : ghead        / GHead@123'))
        self.stdout.write(self.style.SUCCESS('Battalion : deptA        / Dept@1234'))
        self.stdout.write(self.style.SUCCESS('TTS       : deptB        / Dept@1234'))
        self.stdout.write(self.style.SUCCESS('CS        : deptC        / Dept@1234'))
        self.stdout.write(self.style.SUCCESS('Clerk     : deptD        / Dept@1234'))
        self.stdout.write(self.style.SUCCESS('NCO-A     : ncoA         / Trainer@123'))
        self.stdout.write(self.style.SUCCESS('JCO-A     : jcoA         / Trainer@123'))
        self.stdout.write(self.style.SUCCESS('Officer-A : officerA     / Trainer@123'))
        self.stdout.write('='*60 + '\n')
