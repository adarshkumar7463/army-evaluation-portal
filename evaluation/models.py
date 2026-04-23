"""
Evaluation App - Models
Core evaluation system with marks logic
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from accounts.models import CustomUser
from departments.models import Agniveer


class EvaluationSheet(models.Model):
    """
    Evaluation sheet for each Agniveer per training category.
    """
    CATEGORY_CHOICES = [
        ('on_field', 'On Field Training'),
        ('trade', 'Basic Trade Training'),
    ]

    TEST_TYPE_CHOICES = [
        # On Field
        ('physical', 'Physical Test'),
        ('weapon', 'Weapon Test'),
        ('field', 'Field Training'),
        # Trade
        ('assessment', 'Assessment'),
        ('viva', 'Viva'),
        ('ojt', 'On Job Training'),
        ('written', 'Written Exam'),
    ]

    agniveer = models.ForeignKey(Agniveer, on_delete=models.CASCADE, related_name='evaluations')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    test_type = models.CharField(max_length=20, choices=TEST_TYPE_CHOICES)
    department = models.CharField(max_length=1, choices=[('A','A'),('B','B'),('C','C'),('D','D')])
    evaluation_date = models.DateField()
    remarks = models.TextField(blank=True, null=True)

    is_locked = models.BooleanField(default=False)
    locked_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='locked_sheets'
    )
    locked_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, related_name='created_sheets'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['agniveer', 'test_type', 'department']
        verbose_name = 'Evaluation Sheet'
        ordering = ['-evaluation_date']

    def __str__(self):
        return f"{self.agniveer} - {self.get_test_type_display()}"

    def get_nco_marks(self):
        mark = self.marks.filter(evaluator_type='nco').first()
        return mark.marks if mark else 0

    def get_jco_marks(self):
        mark = self.marks.filter(evaluator_type='jco').first()
        return mark.marks if mark else 0

    def get_officer_marks(self):
        mark = self.marks.filter(evaluator_type='officer').first()
        return mark.marks if mark else 0

    def get_total_marks(self):
        return self.get_nco_marks() + self.get_jco_marks() + self.get_officer_marks()

    def get_max_marks(self):
        return 60

    def get_percentage(self):
        total = self.get_total_marks()
        return round((total / 60) * 100, 2)

    def is_pass(self):
        return self.get_percentage() >= 50

    def is_complete(self):
        return self.marks.count() >= 3

    def can_be_locked(self):
        return self.is_complete() and not self.is_locked


class Marks(models.Model):
    """
    Individual marks given by each evaluator type.
    Max 20 marks per evaluator.
    """
    EVALUATOR_CHOICES = [
        ('nco', 'NCO'),
        ('jco', 'JCO'),
        ('officer', 'Officer'),
    ]

    evaluation_sheet = models.ForeignKey(
        EvaluationSheet, on_delete=models.CASCADE, related_name='marks'
    )
    evaluator = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, related_name='given_marks'
    )
    evaluator_type = models.CharField(max_length=10, choices=EVALUATOR_CHOICES)
    marks = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(20)]
    )
    remarks = models.TextField(blank=True, null=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['evaluation_sheet', 'evaluator_type']
        verbose_name = 'Mark Entry'

    def __str__(self):
        return f"{self.evaluation_sheet} - {self.get_evaluator_type_display()}: {self.marks}"

    def clean(self):
        if self.evaluation_sheet.is_locked:
            raise ValidationError("Cannot modify marks on a locked evaluation sheet.")
        if self.marks > 20:
            raise ValidationError("Marks cannot exceed 20 per evaluator.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
