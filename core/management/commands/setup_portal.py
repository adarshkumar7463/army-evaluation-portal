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
        self.stdout.write(self.style.SUCCESS('\nSetting up Army Evaluation Portal...\n'))

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
            self.stdout.write(self.style.SUCCESS('[OK] Commander created: commander / Commander@123'))
        else:
            commander = CustomUser.objects.filter(role='commander').first()
            self.stdout.write('[INFO] Commander already exists')

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
            self.stdout.write(self.style.SUCCESS('[OK] G Head created: ghead / GHead@123'))
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
                self.stdout.write(self.style.SUCCESS(f'[OK] {DEPARTMENT_NAMES.get(dept, dept)}: {uname} / Dept@1234'))
            dept_users[dept] = u

        # Create TTS sub-department user for "Other Trades" (ttsall)
        if not CustomUser.objects.filter(username='ttsall').exists():
            ttsall_user = CustomUser.objects.create_user(
                username='ttsall',
                password='Dept@1234',
                first_name='Capt.',
                last_name='TTSAll',
                role='dept_b',
                department='B',
                tts_trade='OTHER',
                service_number='DB002',
                rank='Captain',
                created_by=dept_users['B'],
            )
            self.stdout.write(self.style.SUCCESS('[OK] TTS All Trades Head created: ttsall / Dept@1234'))



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
                    trade_val = 'Other'
                    bn_val = None
                    if dept == 'A':
                        bn_val = random.choice(['1TB', '2TB', 'STB'])
                    elif dept == 'B':
                        trade_val = random.choice(['DMV', 'OPEM', 'Other'])
                    elif dept == 'D':
                        trade_val = 'CLK'

                    a = Agniveer.objects.create(
                        enrollment_number=enroll,
                        first_name=fname,
                        last_name=lname,
                        date_of_birth=dob,
                        gender=random.choice(['M', 'M', 'M', 'F']),
                        phone=f'98{random.randint(10000000,99999999)}',
                        bn_desp=bn_val,
                        trade=trade_val,
                        batch=f'Batch 2024-{dept}',
                        joining_date=joining,
                        status='active',
                        registered_by=dept_user,
                    )

                    created_agniveers[dept].append(a)
                    agniveer_count += 1
                else:
                    existing = Agniveer.objects.get(enrollment_number=enroll)
                    created_agniveers[dept].append(existing)

        self.stdout.write(self.style.SUCCESS(f'[OK] {agniveer_count} Agniveers created'))

        # ─── 6. Evaluations ───
        test_types = ['physical', 'weapon', 'assessment', 'viva']
        test_category = {'physical': 'on_field', 'weapon': 'on_field', 'assessment': 'trade', 'viva': 'trade'}
        eval_count = 0

        for dept, agniveers_list in created_agniveers.items():
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
                    # Add marks for admin evaluator
                    m = random.randint(30, 50)
                    Marks.objects.create(
                        evaluation_sheet=sheet,
                        evaluator=dept_users.get(dept),
                        evaluator_type='admin',
                        marks=m,
                        remarks=f'Good performance in {test_type}',
                    )
                    # Lock the sheet
                    sheet.is_locked = True
                    sheet.locked_by = dept_users.get(dept)
                    sheet.locked_at = timezone.now()
                    sheet.save()
                    eval_count += 1

        self.stdout.write(self.style.SUCCESS(f'[OK] {eval_count} Evaluation sheets created & locked'))

        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('SETUP COMPLETE! Login credentials:'))
        self.stdout.write('='*60)
        self.stdout.write(self.style.SUCCESS('Commander : commander    / Commander@123'))
        self.stdout.write(self.style.SUCCESS('G Head    : ghead        / GHead@123'))
        self.stdout.write(self.style.SUCCESS('Battalion : deptA        / Dept@1234'))
        self.stdout.write(self.style.SUCCESS('TTS       : deptB        / Dept@1234'))
        self.stdout.write(self.style.SUCCESS('TTS All   : ttsall       / Dept@1234'))
        self.stdout.write(self.style.SUCCESS('CS        : deptC        / Dept@1234'))
        self.stdout.write(self.style.SUCCESS('Clerk     : deptD        / Dept@1234'))

        self.stdout.write('='*60 + '\n')
