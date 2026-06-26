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
        ('clerk_result', 'Final Result (Clerk)'),
        ('screen_board', 'Screen Board'),
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
        ('CS_ASSESSMENT', 'CS Assessment'),
        ('CS_RESULT', 'CS Final Result'),
        ('CS_CLERK_RESULT', 'CS Final Result (Clerk)'),
        ('CLK_INITIAL', 'Clerk Initial Test'),
        ('CLK_WEEKLY_1', 'Clerk 1st Weekly Test'),
        ('CLK_WEEKLY_2', 'Clerk 2nd Weekly Progress Test'),
        ('CLK_FINAL', 'Clerk Final Test'),
        ('CMK_SHEET', 'Common Mil Knowledge Sheet'),
        ('FINAL_MERIT', 'AV Merit List'),
        ('FINAL_RESULT', 'Final Result'),
        ('OPEM_ASSESSMENT', 'OPEM Final Assessment'),
        ('DMV_ASSESSMENT', 'DMV Final Assessment'),
        ('OTHER_ASSESSMENT', 'OTHER Final Assessment'),
        ('DMV_SCREEN_BOARD', 'DMV Screen Board'),
        ('OPEM_SCREEN_BOARD', 'OPEM Screen Board'),
        ('OTHER_SCREEN_BOARD', 'OTHER Screen Board'),
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


    def get_admin_marks(self):
        mark = self.marks.filter(evaluator_type='admin').first()
        return mark.marks if mark else 0

    def get_total_marks(self):
        if self.test_type == 'DMV_RESULT':
            from .result_helpers import get_sheet_total_marks, _num, _marks_from_sheet
            res = self.sub_event_results or {}
            m_dict = res.get('Marks', res) if isinstance(res.get('Marks'), dict) else res
            online = _num(m_dict.get('Online Test (100)'))
            prac_sheet = self.agniveer.evaluations.filter(test_type='DMV_PRACTICAL').first()
            practical = get_sheet_total_marks(prac_sheet) if prac_sheet else _num(m_dict.get('Practical Test (50)'))
            drive_sheet = self.agniveer.evaluations.filter(test_type='DMV_DRIVING').first()
            job = get_sheet_total_marks(drive_sheet) if drive_sheet else _num(m_dict.get('Driving Test (50)'))
            raw_total = online + practical + job
            if raw_total == 0:
                assess_sheet = self.agniveer.evaluations.filter(test_type='DMV_ASSESSMENT').first()
                if assess_sheet:
                    total_assess = get_sheet_total_marks(assess_sheet)
                    return round((total_assess / 71) * 40, 2)
                return 0.0
            return round(raw_total * 0.2, 2)

        if self.test_type == 'OPEM_RESULT':
            from .result_helpers import get_sheet_total_marks, _num, _marks_from_sheet
            res = self.sub_event_results or {}
            m_dict = res.get('Marks', res) if isinstance(res.get('Marks'), dict) else res
            online = _num(m_dict.get('Written Test (100)'))
            prac_sheet = self.agniveer.evaluations.filter(test_type='OPEM_PRACTICAL').first()
            practical = get_sheet_total_marks(prac_sheet) if prac_sheet else _num(m_dict.get('Practical Test (50)'))
            maint_sheet = self.agniveer.evaluations.filter(test_type='OPEM_MAINTENANCE').first()
            job = get_sheet_total_marks(maint_sheet) if maint_sheet else _num(m_dict.get('Maintenance Test (50)'))
            raw_total = online + practical + job
            if raw_total == 0:
                assess_sheet = self.agniveer.evaluations.filter(test_type='OPEM_ASSESSMENT').first()
                if assess_sheet:
                    total_assess = get_sheet_total_marks(assess_sheet)
                    return round((total_assess / 71) * 40, 2)
                return 0.0
            return round(raw_total * 0.2, 2)

        if self.test_type == 'FINAL_RESULT':
            from .result_helpers import get_ces_final_marks, get_btt_final_marks, _num, _marks_from_sheet
            basic_tac = get_ces_final_marks(self.agniveer)
            trade_prof = get_btt_final_marks(self.agniveer)
            
            cmk_sheet = self.agniveer.evaluations.filter(test_type='CMK_SHEET').first()
            cmk_20 = 0.0
            if cmk_sheet:
                cmk_marks = _marks_from_sheet(cmk_sheet)
                cmk_20 = _num(cmk_marks.get('CONVERTED (20)'))
            else:
                res = self.sub_event_results or {}
                m_dict = res.get('Marks', res) if isinstance(res.get('Marks'), dict) else res
                cmk_20 = _num(m_dict.get('COMMON MIL KNOWLEDGE (20)'))
                
            wpn_sheet = self.agniveer.evaluations.filter(test_type='WPN_HANDLING').first()
            wpn_handling_20 = 0.0
            if wpn_sheet:
                wpn_marks = _marks_from_sheet(wpn_sheet)
                wpn_handling_20 = _num(wpn_marks.get('CONVERTED (20)'))
            else:
                res = self.sub_event_results or {}
                m_dict = res.get('Marks', res) if isinstance(res.get('Marks'), dict) else res
                wpn_handling_20 = _num(m_dict.get('WPN & EQPT HANDLING (20)'))
                
            return round(cmk_20 + basic_tac + trade_prof + wpn_handling_20)

        # Admin marks represent the official marks for this sheet
        admin_mark = self.marks.filter(evaluator_type='admin').first()
        return admin_mark.marks if admin_mark is not None else 0

    def get_max_marks(self):
        if self.test_type in ['DMV_RESULT', 'OPEM_RESULT']:
            return 40
        if self.department == 'A':
            max_marks_map = {
                'PPT': 100,
                'BPET': 100,
                'Firing': 100,
                'DST': 100,
                'MR_III': 100,
                'BFC': 240,
                'PDP': 50,
                'FC_All': 90,
                'CMK_SHEET': 20,
                'WPN_HANDLING': 20,
                'FINAL_MERIT': 130,
                'FINAL_RESULT': 120,
            }
            return max_marks_map.get(self.test_type, 100)
        from .constants import get_dept_config
        if self.department == 'B' and self.agniveer:
            from .constants import DEPT_CONFIG
            trade = getattr(self.agniveer, 'trade', None)
            sub_depts = DEPT_CONFIG['B'].get('sub_departments', {})
            if trade in sub_depts:
                config = sub_depts[trade]
            elif self.test_type.startswith('OPEM_') and 'OPEM' in sub_depts:
                config = sub_depts['OPEM']
            elif self.test_type.startswith('DMV_') and 'DMV' in sub_depts:
                config = sub_depts['DMV']
            else:
                config = get_dept_config(self.department)
        else:
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
        passing_percentage = 40 if self.department == 'A' else 50
        return self.get_percentage() >= passing_percentage

    def is_complete(self):
        # Completed when admin marks have been entered
        return self.marks.filter(evaluator_type='admin').exists()

    def can_be_locked(self):
        return self.is_complete() and not self.is_locked


class Marks(models.Model):
    """
    Individual marks given by each evaluator type.
    Max 20 marks per evaluator.
    """
    EVALUATOR_CHOICES = [
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
