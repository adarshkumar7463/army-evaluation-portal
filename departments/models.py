"""
Departments App - Models
Agniveer registration and department management
"""

from django.db import models
from accounts.models import CustomUser


class Agniveer(models.Model):
    """
    Represents an Agniveer trainee registered under a department.
    """
    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female'), ('O', 'Other')]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('dropped', 'Dropped Out'),
        ('pass', 'Passed'),
        ('fail', 'Failed'),
    ]

    enrollment_number = models.CharField(max_length=30, unique=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default='M')
    phone = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    photo = models.ImageField(upload_to='agniveers/', blank=True, null=True)

    batch = models.CharField(max_length=30)
    joining_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    registered_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, related_name='registered_agniveers'
    )
    assigned_trainers = models.ManyToManyField(
        CustomUser, related_name='assigned_agniveers', blank=True,
        limit_choices_to={'role__in': ['trainer_nco', 'trainer_jco', 'trainer_officer']}
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Agniveer'
        verbose_name_plural = 'Agniveers'
        ordering = ['enrollment_number']

    def __str__(self):
        return f"{self.enrollment_number} - {self.get_full_name()}"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    def get_total_score(self):
        from evaluation.models import EvaluationSheet
        sheets = EvaluationSheet.objects.filter(agniveer=self, is_locked=True)
        return sum(sheet.get_total_marks() for sheet in sheets)

    def get_pass_status(self):
        from evaluation.models import EvaluationSheet
        sheets = EvaluationSheet.objects.filter(agniveer=self, is_locked=True)
        if not sheets.exists():
            return 'Pending'
        total = sum(sheet.get_total_marks() for sheet in sheets)
        max_total = sum(sheet.get_max_marks() for sheet in sheets)
        if max_total == 0:
            return 'Pending'
        percentage = (total / max_total) * 100
        return 'Pass' if percentage >= 50 else 'Fail'
