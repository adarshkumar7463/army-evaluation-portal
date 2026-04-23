"""
Management command to create 400 dummy agniveers
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
import random
from departments.models import Agniveer
from accounts.models import CustomUser


class Command(BaseCommand):
    help = 'Creates 400 dummy agniveers without department assignments'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete-existing',
            action='store_true',
            help='Delete all existing agniveers before creating new ones',
        )

    def handle(self, *args, **options):
        if options['delete_existing']:
            count = Agniveer.objects.count()
            Agniveer.objects.all().delete()
            self.stdout.write(
                self.style.SUCCESS(f'✓ Deleted {count} existing agniveers')
            )

        # Get a registered_by user (commander or dept head)
        registered_by = CustomUser.objects.filter(role='commander').first()
        if not registered_by:
            registered_by = CustomUser.objects.filter(role__in=['dept_a', 'dept_b', 'dept_c', 'dept_d']).first()
        
        if not registered_by:
            self.stdout.write(self.style.ERROR('✗ No commander or department head found to register agniveers'))
            return

        first_names = [
            'Rajesh', 'Amit', 'Vikram', 'Arjun', 'Rohan', 'Karan', 'Priya', 'Neha', 'Ananya', 'Divya',
            'Ashok', 'Suresh', 'Manoj', 'Dinesh', 'Ramesh', 'Harish', 'Nilesh', 'Deepak', 'Sandeep', 'Arun',
            'Bhavesh', 'Chetan', 'Darshan', 'Eshwar', 'Farhan', 'Gaurav', 'Harsh', 'Ishan', 'Jitesh', 'Kunal',
            'Lokesh', 'Manish', 'Naresh', 'Omkar', 'Pawan', 'Qadir', 'Rajat', 'Sanjay', 'Tarun', 'Ujwal',
            'Vaibhav', 'Wazir', 'Xavier', 'Yash', 'Zeeshan', 'Akshay', 'Bhuvan', 'Chiraq', 'Dhruv', 'Eshan'
        ]

        last_names = [
            'Singh', 'Sharma', 'Kumar', 'Patel', 'Gupta', 'Reddy', 'Verma', 'Pandey', 'Rao', 'Nair',
            'Desai', 'Iyer', 'Menon', 'Bhat', 'Sinha', 'Mishra', 'Yadav', 'Khan', 'Malik', 'Ahmed',
            'Hassan', 'Ali', 'Shah', 'Joshi', 'Pillai', 'Nambiar', 'Mukherjee', 'Banerjee', 'Dutta', 'Roy',
            'Sen', 'Ghosh', 'Chatterjee', 'Dubey', 'Tripathi', 'Saxena', 'Srivastava', 'Shukla', 'Tiwari', 'Dwivedi'
        ]

        batches = ['Batch 2024-A', 'Batch 2024-B', 'Batch 2024-C', 'Batch 2024-D', 'Batch 2025-A']
        genders = ['M', 'F', 'O']

        # Calculate date range for joining dates (last 2 years)
        today = timezone.now().date()
        start_date = today - timedelta(days=730)

        self.stdout.write(self.style.WARNING('Creating 400 dummy agniveers...'))

        created_count = 0
        batch_size = 50
        agniveers_to_create = []

        for i in range(1, 401):
            enrollment_number = f"AGN{today.year}{i:04d}"
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            
            # Random DOB (18-35 years old)
            dob = today - timedelta(days=random.randint(365*18, 365*35))
            
            # Random joining date in last 2 years
            joining_date = start_date + timedelta(days=random.randint(0, 730))
            
            agniveer = Agniveer(
                enrollment_number=enrollment_number,
                first_name=first_name,
                last_name=last_name,
                date_of_birth=dob,
                gender=random.choice(genders),
                phone=f"9{random.randint(10**9, 10**10-1)}",
                email=f"{first_name.lower()}.{last_name.lower()}{i}@agniveer.in",
                address=f"{i} Army Street, Cantonment, India",
                batch=random.choice(batches),
                joining_date=joining_date,
                status='active',
                registered_by=registered_by,
            )
            agniveers_to_create.append(agniveer)
            
            if i % batch_size == 0:
                Agniveer.objects.bulk_create(agniveers_to_create)
                created_count += len(agniveers_to_create)
                self.stdout.write(f'  ✓ Created {created_count}/400 agniveers')
                agniveers_to_create = []

        # Create remaining agniveers
        if agniveers_to_create:
            Agniveer.objects.bulk_create(agniveers_to_create)
            created_count += len(agniveers_to_create)

        self.stdout.write(
            self.style.SUCCESS(f'✓ Successfully created {created_count} dummy agniveers!')
        )
        self.stdout.write(
            self.style.SUCCESS('✓ All agniveers created without department assignments')
        )
