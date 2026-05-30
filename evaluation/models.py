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
        ('physical', 'Physical Efficiency'),
        ('weapon', 'Weapon Training'),
        ('field', 'Field Craft'),
        ('assessment', 'Assessment'),
        ('theory', 'Theory & TMA'),
        ('practical', 'Practical Assessment'),
        ('result', 'Final Result'),
        ('initial', 'Initial Test'),
        ('weekly', 'Weekly Tests'),
        ('final', 'Final Test'),
        ('screening', 'Screening'),
        ('driving', 'Final Driving Test'),
        ('maintenance', 'Maintenance Test'),
    ]

    TEST_TYPE_CHOICES = [
        ('PPT', 'PPT'),
        ('BPET', 'BPET'),
        ('Firing', 'Firing'),
        ('DST', 'DST'),
        ('FC_Practical', 'FC Practical'),
        ('FC_Online', 'FC Online'),
        ('PDP', 'PDP Test'),
        ('BFC', 'BFC Test'),
        ('MR', 'MR'),
        ('MR_III', 'MR-III'),
        ('FC_All', 'FC Practical, FC Online & Camp Trg'),
        ('CS_RESULT', 'CS Final Result'),
        ('CLK_INITIAL', 'Clerk Initial Test'),
        ('CLK_WEEKLY_1', 'Clerk 1st Weekly Test'),
        ('CLK_WEEKLY_2', 'Clerk 2nd Weekly Progress Test'),
        ('CLK_FINAL', 'Clerk Final Test'),
        ('CMK_SHEET', 'Common Mil Knowledge Sheet'),
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

    # Sub-event results stored as JSON: {"2.4 KM Run": 15, "100M Sprint": 18, ...}
    sub_event_results = models.JSONField(default=dict, blank=True)

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

    def get_admin_marks(self):
        mark = self.marks.filter(evaluator_type='admin').first()
        return mark.marks if mark else 0

    def get_total_marks(self):
        # Admin marks supersede individual evaluator marks if present
        admin_marks = self.get_admin_marks()
        if admin_marks > 0:
            return admin_marks
        return self.get_nco_marks() + self.get_jco_marks() + self.get_officer_marks()

    def get_max_marks(self):
        from .constants import get_dept_config
        config = get_dept_config(self.department)
        configured_max = config.get('max_marks', {}).get(self.test_type)
        if configured_max:
            score_event = config.get('score_events', {}).get(self.test_type)
            if score_event and score_event in configured_max:
                return configured_max[score_event]
            if 'CONVERTED TO 40' in configured_max:
                return configured_max['CONVERTED TO 40']
            return configured_max.get('TOTAL (600)') or sum(
                max_mark for event, max_mark in configured_max.items()
                if not event.upper().startswith('TOTAL') and event != 'FEE TOTAL'
            )
        # Dynamic max marks based on sub-events if they exist
        if self.test_type in config.get('sub_events', {}):
             return len(config['sub_events'][self.test_type]) * 20 # Assuming 20 max per sub-event
        return 60

    def get_percentage(self):
        total = self.get_total_marks()
        max_marks = self.get_max_marks()
        return round((total / max_marks) * 100, 2) if max_marks else 0

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
        ('admin', 'Department Admin'),
    ]

    evaluation_sheet = models.ForeignKey(
        EvaluationSheet, on_delete=models.CASCADE, related_name='marks'
    )
    evaluator = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, related_name='given_marks'
    )
    evaluator_type = models.CharField(max_length=10, choices=EVALUATOR_CHOICES)
    marks = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(500)]
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
        if self.marks > 500:
            raise ValidationError("Marks cannot exceed 500 per evaluator.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
