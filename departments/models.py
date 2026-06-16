"""
Departments App - Models
Agniveer registration and department management
"""

from django.db import models
from django.utils import timezone
from accounts.models import CustomUser


YES_NO_CHOICES = [
    ('Yes', 'Yes'),
    ('No', 'No'),
]

TRADE_CHOICES = [
    ('CLK', 'Clerk'),
    ('DMV', 'DMV'),
    ('OPEM', 'OPEM'),
    ('A/CONSTR', 'A/Constr'),
    ('AWW', 'AWW'),
    ('P&D', 'P&D'),
    ('ELET', 'ELET'),
    ('FTR_MACH', 'FTR & MACH'),
    ('OPR_RADIO', 'OPR RADIO'),
    ('RST', 'RST'),
    ('WELDER', 'A/MET/WELDER/MACM'),
    ('SVY_TOPO', 'SVY TOPO'),
    ('DTMN_TECH', 'DTMN TECH'),
    ('AFV', 'AFV'),
    ('Other', 'Other'),
]

BN_DESP_CHOICES = [
    ('1TB', '1TB'),
    ('2TB', '2TB'),
    ('STB', 'STB'),
]

BATCH_NO_CHOICES = [
    ('2023', '2023'),
    ('2024', '2024'),
    ('2025', '2025'),
    ('2026', '2026'),
    ('2027', '2027'),
    ('2028', '2028'),
    ('2029', '2029'),
    ('2030', '2030'),
]

PLATOON_CHOICES = [
    ('P1', 'P1'),
    ('P2', 'P2'),
    ('P3', 'P3'),
    ('P4', 'P4'),
    ('P5', 'P5'),
    ('P6', 'P6'),
    ('P7', 'P7'),
    ('P8', 'P8'),
    ('P9', 'P9'),
]

# Company naming per battalion
COMPANY_CHOICES = [
    ('Tirah Company', 'Tirah Company'),
    ('Megiddo Company', 'Megiddo Company'),
    ('Ghuznee Company', 'Ghuznee Company'),
    ('Maktila Company', 'Maktila Company'),
    ('Cassino Company', 'Cassino Company'),
    ('Pigris Company', 'Pigris Company'),
    ('Company A', 'Company A'),
    ('Company B', 'Company B'),
    ('Company C', 'Company C'),
]


def generate_enrollment_number():
    """Auto-generate a unique enrollment number in format AGN-YYYYMMDD-XXXX."""
    today = timezone.now().strftime('%Y%m%d')
    prefix = f"AGN-{today}-"
    last = (
        Agniveer.objects.filter(enrollment_number__startswith=prefix)
        .order_by('enrollment_number')
        .last()
    )
    if last:
        try:
            seq = int(last.enrollment_number.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"


class Agniveer(models.Model):
    """
    Represents an Agniveer trainee.
    All fields as per the official registration sheet.
    """

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('dropped', 'Dropped Out'),
        ('pass', 'Passed'),
        ('fail', 'Failed'),
    ]

    # ── Core Identity ──────────────────────────────────────────────────────────
    enrollment_number = models.CharField(
        max_length=30, unique=True, editable=False,
        help_text="Auto-generated unique key"
    )
    agniveer_no = models.CharField(
        max_length=30, unique=True, blank=True, null=True,
        help_text="Unique Agniveer Number (not auto-generated)"
    )
    name = models.CharField(max_length=100, blank=True, null=True, help_text="Full name of Agniveer")
    father_name = models.CharField(max_length=100, blank=True, null=True, help_text="Father's Name")

    # ── Service Details ────────────────────────────────────────────────────────
    dor = models.DateField(blank=True, null=True, help_text="Date of Reporting (DOR)")
    trade = models.CharField(
        max_length=20, choices=TRADE_CHOICES, default='AST', blank=True,
        help_text="Trade"
    )
    aros_bros = models.CharField(
        max_length=100, blank=True, null=True,
        help_text="AROs / BROs"
    )
    bn_desp = models.CharField(
        max_length=10, choices=BN_DESP_CHOICES, blank=True, null=True,
        help_text="Battalion Designation (e.g. 1TB, 2TB, STB)"
    )
    relationship = models.CharField(
        max_length=50, blank=True, null=True,
        help_text="Relationship"
    )

    # ── Certificate / Document Status (Yes / No only) ─────────────────────────
    afmsf_2a = models.CharField(
        max_length=3, choices=YES_NO_CHOICES, default='No', blank=True,
        help_text="AFMSF-2A"
    )
    review_cert = models.CharField(
        max_length=3, choices=YES_NO_CHOICES, default='No', blank=True,
        help_text="Review Certificate"
    )
    edn_cert = models.CharField(
        max_length=3, choices=YES_NO_CHOICES, default='No', blank=True,
        help_text="Education Certificate"
    )
    verification_roll = models.CharField(
        max_length=3, choices=YES_NO_CHOICES, default='No', blank=True,
        help_text="Verification Roll"
    )
    character_cert = models.CharField(
        max_length=3, choices=YES_NO_CHOICES, default='No', blank=True,
        help_text="Character Certificate"
    )
    unmarried_cert = models.CharField(
        max_length=3, choices=YES_NO_CHOICES, default='No', blank=True,
        help_text="Unmarried Certificate"
    )
    caste_cert = models.CharField(
        max_length=3, choices=YES_NO_CHOICES, default='No', blank=True,
        help_text="Caste Certificate"
    )
    domicile_cert = models.CharField(
        max_length=3, choices=YES_NO_CHOICES, default='No', blank=True,
        help_text="Domicile Certificate"
    )
    outside_sanction_letter = models.CharField(
        max_length=3, choices=YES_NO_CHOICES, default='No', blank=True,
        help_text="Outside Sanction Letter"
    )
    willingness_cert = models.CharField(
        max_length=3, choices=YES_NO_CHOICES, default='No', blank=True,
        help_text="Willingness Certificate"
    )
    ncc_cert = models.CharField(
        max_length=3, choices=YES_NO_CHOICES, default='No', blank=True,
        help_text="NCC Certificate"
    )
    pan_card = models.CharField(
        max_length=3, choices=YES_NO_CHOICES, default='No', blank=True,
        help_text="PAN Card"
    )
    aadhar_card = models.CharField(
        max_length=3, choices=YES_NO_CHOICES, default='No', blank=True,
        help_text="Aadhar Card"
    )

    # ── Education ─────────────────────────────────────────────────────────────
    edn_ql_enrollment = models.CharField(
        max_length=50, blank=True, null=True,
        help_text="Education Qualification at time of Enrolment (e.g. 10th, 12th)"
    )
    higher_edn_qualification = models.CharField(
        max_length=100, blank=True, null=True,
        help_text="Higher Education Qualification"
    )
    class_field = models.CharField(
        max_length=20, blank=True, null=True,
        help_text="Class"
    )

    # ── Additional ────────────────────────────────────────────────────────────
    additional_cert = models.CharField(
        max_length=200, blank=True, null=True,
        help_text="Any Additional Certificate"
    )
    remarks = models.TextField(blank=True, null=True, help_text="Remarks")

    # ── Status & Housekeeping ─────────────────────────────────────────────────
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='active'
    )
    registered_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True,
        related_name='registered_agniveers'
    )
    # Note: trainer assignment field removed from active model per 'hide-only' policy.
    # Historical migrations may still reference `assigned_trainers`.

    # ── Legacy / Optional fields (kept for backward compat) ───────────────────
    first_name = models.CharField(max_length=50, blank=True, null=True)
    last_name = models.CharField(max_length=50, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=1, choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')], default='M', blank=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    photo = models.ImageField(upload_to='agniveers/', blank=True, null=True)
    rank = models.CharField(max_length=50, blank=True, null=True)
    batch = models.CharField(max_length=30, blank=True, null=True)
    batch_no = models.CharField(max_length=10, choices=BATCH_NO_CHOICES, blank=True, null=True)
    company = models.CharField(max_length=20, choices=COMPANY_CHOICES, blank=True, null=True)
    platoon = models.CharField(max_length=10, choices=PLATOON_CHOICES, blank=True, null=True)
    joining_date = models.DateField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Agniveer'
        verbose_name_plural = 'Agniveers'
        ordering = ['enrollment_number']

    def __str__(self):
        return f"{self.enrollment_number} - {self.get_full_name()}"

    def save(self, *args, **kwargs):
        if not self.enrollment_number:
            self.enrollment_number = generate_enrollment_number()
        # Sync legacy name fields
        if self.name and not self.first_name:
            parts = self.name.split(' ', 1)
            self.first_name = parts[0]
            self.last_name = parts[1] if len(parts) > 1 else ''
        super().save(*args, **kwargs)

    def get_full_name(self):
        if self.name:
            return self.name
        return f"{self.first_name or ''} {self.last_name or ''}".strip()

    def get_consolidated_scores(self):
        from evaluation.models import EvaluationSheet
        from evaluation.result_helpers import build_department_result_row, is_sheet_evaluated
        
        evaluations = list(EvaluationSheet.objects.filter(agniveer=self).prefetch_related('marks'))
        
        total_score = 0.0
        max_marks = 0.0
        has_eval = False
        
        for d in ['A', 'B', 'C', 'D']:
            d_sheets = [s for s in evaluations if s.department == d]
            if d_sheets and any(is_sheet_evaluated(s) for s in d_sheets):
                has_eval = True
                d_row = build_department_result_row(self, d_sheets, d)
                total_score += float(d_row.get('grand_total', 0.0) or 0.0)
                max_marks += float(d_row.get('max_total') or (120 if d == 'A' else 40))
                
        return total_score, max_marks, has_eval

    def get_total_score(self):
        total, max_val, has_eval = self.get_consolidated_scores()
        return round(total, 2)

    def get_pass_status(self):
        total, max_val, has_eval = self.get_consolidated_scores()
        if not has_eval or max_val == 0:
            return 'Pending'
            
        from evaluation.models import EvaluationSheet
        from evaluation.result_helpers import is_sheet_evaluated
        evaluations = list(EvaluationSheet.objects.filter(agniveer=self).prefetch_related('marks'))
        evaluated_depts = []
        for d in ['A', 'B', 'C', 'D']:
            d_sheets = [s for s in evaluations if s.department == d]
            if d_sheets and any(is_sheet_evaluated(s) for s in d_sheets):
                evaluated_depts.append(d)
                
        passing_threshold = 40 if evaluated_depts == ['A'] else 50
        percentage = (total / max_val) * 100
        return 'Pass' if percentage >= passing_threshold else 'Fail'

    def get_evaluation_progress(self, dept_code='A'):
        from evaluation.models import EvaluationSheet
        from evaluation.constants import DEPT_CONFIG
        config = DEPT_CONFIG.get(dept_code)
        if not config:
            return "0/0"
        
        test_types = [t[0] for t in config['test_types']]
        total_tests = len(test_types)
        
        # Count locked sheets for this department
        completed_tests = EvaluationSheet.objects.filter(
            agniveer=self,
            department=dept_code,
            is_locked=True,
            test_type__in=test_types
        ).count()
        
        return f"{completed_tests}/{total_tests}"
