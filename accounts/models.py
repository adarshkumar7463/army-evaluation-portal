"""
Accounts App - Models
Custom User Model with Role-Based Access Control
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class CustomUser(AbstractUser):
    """
    Custom User Model extending AbstractUser.
    Implements Role-Based Access Control for Army Evaluation Portal.
    """

    ROLE_COMMANDER = 'commander'
    ROLE_G_HEAD = 'g_head'
    ROLE_DEPT_A = 'dept_a'
    ROLE_DEPT_B = 'dept_b'
    ROLE_DEPT_C = 'dept_c'
    ROLE_DEPT_D = 'dept_d'
    ROLE_TRAINER_NCO = 'trainer_nco'
    ROLE_TRAINER_JCO = 'trainer_jco'
    ROLE_TRAINER_OFFICER = 'trainer_officer'

    ROLE_CHOICES = [
        (ROLE_COMMANDER, 'Commander'),
        (ROLE_G_HEAD, 'G Department Head'),
        (ROLE_DEPT_A, 'Department A'),
        (ROLE_DEPT_B, 'Department B'),
        (ROLE_DEPT_C, 'Department C'),
        (ROLE_DEPT_D, 'Department D'),
        (ROLE_TRAINER_NCO, 'Trainer - NCO'),
        (ROLE_TRAINER_JCO, 'Trainer - JCO'),
        (ROLE_TRAINER_OFFICER, 'Trainer - Officer'),
    ]

    DEPARTMENT_CHOICES = [
        ('A', 'Department A'),
        ('B', 'Department B'),
        ('C', 'Department C'),
        ('D', 'Department D'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_TRAINER_NCO)
    department = models.CharField(max_length=1, choices=DEPARTMENT_CHOICES, blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    service_number = models.CharField(max_length=30, unique=True, blank=True, null=True)
    rank = models.CharField(max_length=50, blank=True, null=True)
    profile_photo = models.ImageField(upload_to='profiles/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_users'
    )
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    login_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_full_name()} ({self.get_role_display()})"

    @property
    def is_commander(self):
        return self.role == self.ROLE_COMMANDER

    @property
    def is_g_head(self):
        return self.role == self.ROLE_G_HEAD

    @property
    def is_department(self):
        return self.role in [self.ROLE_DEPT_A, self.ROLE_DEPT_B, self.ROLE_DEPT_C, self.ROLE_DEPT_D]

    @property
    def is_trainer(self):
        return self.role in [self.ROLE_TRAINER_NCO, self.ROLE_TRAINER_JCO, self.ROLE_TRAINER_OFFICER]

    @property
    def is_nco(self):
        return self.role == self.ROLE_TRAINER_NCO

    @property
    def is_jco(self):
        return self.role == self.ROLE_TRAINER_JCO

    @property
    def is_officer(self):
        return self.role == self.ROLE_TRAINER_OFFICER

    @property
    def can_view_all(self):
        return self.role in [self.ROLE_COMMANDER, self.ROLE_G_HEAD]

    def get_department_code(self):
        dept_map = {
            self.ROLE_DEPT_A: 'A',
            self.ROLE_DEPT_B: 'B',
            self.ROLE_DEPT_C: 'C',
            self.ROLE_DEPT_D: 'D',
        }
        return dept_map.get(self.role, self.department)

    def is_account_locked(self):
        if self.locked_until and self.locked_until > timezone.now():
            return True
        return False

    def get_role_color(self):
        color_map = {
            self.ROLE_COMMANDER: 'danger',
            self.ROLE_G_HEAD: 'warning',
            self.ROLE_DEPT_A: 'primary',
            self.ROLE_DEPT_B: 'info',
            self.ROLE_DEPT_C: 'success',
            self.ROLE_DEPT_D: 'secondary',
            self.ROLE_TRAINER_NCO: 'dark',
            self.ROLE_TRAINER_JCO: 'dark',
            self.ROLE_TRAINER_OFFICER: 'dark',
        }
        return color_map.get(self.role, 'secondary')
