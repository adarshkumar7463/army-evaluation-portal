"""
Departments App - Forms
Agniveer registration, Excel upload, and edit forms
"""

from django import forms
from .models import Agniveer, YES_NO_CHOICES, TRADE_CHOICES
from accounts.models import CustomUser


# ── Yes/No widget helper ───────────────────────────────────────────────────────
YN_WIDGET = forms.Select(attrs={'class': 'form-select form-select-sm'}, choices=YES_NO_CHOICES)


class AgniveerRegistrationForm(forms.ModelForm):
    """Full registration form with all fields from the official sheet."""

    class Meta:
        model = Agniveer
        fields = [
            'agniveer_no', 'name', 'father_name',
            'dor', 'trade', 'aros_bros', 'bn_desp', 'relationship',
            'afmsf_2a', 'review_cert', 'edn_ql_enrollment',
            'higher_edn_qualification', 'edn_cert', 'verification_roll',
            'character_cert', 'unmarried_cert', 'caste_cert', 'class_field',
            'domicile_cert', 'outside_sanction_letter', 'willingness_cert',
            'ncc_cert', 'additional_cert', 'pan_card', 'aadhar_card', 'remarks',
        ]
        widgets = {
            'agniveer_no': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'e.g. A38018690'
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'Full Name'
            }),
            'father_name': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': "Father's Name"
            }),
            'dor': forms.DateInput(attrs={
                'class': 'form-control form-control-sm', 'type': 'date'
            }),
            'trade': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'aros_bros': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'e.g. VISHAKHAPATNAM'
            }),
            'bn_desp': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'relationship': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'e.g. 2'
            }),
            'afmsf_2a': forms.Select(attrs={'class': 'form-select form-select-sm'}, choices=YES_NO_CHOICES),
            'review_cert': forms.Select(attrs={'class': 'form-select form-select-sm'}, choices=YES_NO_CHOICES),
            'edn_ql_enrollment': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'e.g. 10th, 12th'
            }),
            'higher_edn_qualification': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'e.g. B.A., B.Sc.'
            }),
            'edn_cert': forms.Select(attrs={'class': 'form-select form-select-sm'}, choices=YES_NO_CHOICES),
            'verification_roll': forms.Select(attrs={'class': 'form-select form-select-sm'}, choices=YES_NO_CHOICES),
            'character_cert': forms.Select(attrs={'class': 'form-select form-select-sm'}, choices=YES_NO_CHOICES),
            'unmarried_cert': forms.Select(attrs={'class': 'form-select form-select-sm'}, choices=YES_NO_CHOICES),
            'caste_cert': forms.Select(attrs={'class': 'form-select form-select-sm'}, choices=YES_NO_CHOICES),
            'class_field': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'e.g. AIAC'
            }),
            'domicile_cert': forms.Select(attrs={'class': 'form-select form-select-sm'}, choices=YES_NO_CHOICES),
            'outside_sanction_letter': forms.Select(attrs={'class': 'form-select form-select-sm'}, choices=YES_NO_CHOICES),
            'willingness_cert': forms.Select(attrs={'class': 'form-select form-select-sm'}, choices=YES_NO_CHOICES),
            'ncc_cert': forms.Select(attrs={'class': 'form-select form-select-sm'}, choices=YES_NO_CHOICES),
            'additional_cert': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'Any additional certificate'
            }),
            'pan_card': forms.Select(attrs={'class': 'form-select form-select-sm'}, choices=YES_NO_CHOICES),
            'aadhar_card': forms.Select(attrs={'class': 'form-select form-select-sm'}, choices=YES_NO_CHOICES),
            'remarks': forms.Textarea(attrs={
                'class': 'form-control form-control-sm', 'rows': 2,
                'placeholder': 'Any remarks...'
            }),
        }

    def clean_agniveer_no(self):
        val = self.cleaned_data.get('agniveer_no', '').strip()
        qs = Agniveer.objects.filter(agniveer_no=val)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("An Agniveer with this number already exists.")
        return val


class AgniveerEditForm(forms.ModelForm):
    """Edit form — same fields as registration, used in the edit modal."""

    class Meta:
        model = Agniveer
        fields = [
            'agniveer_no', 'name', 'father_name',
            'dor', 'trade', 'aros_bros', 'bn_desp', 'relationship',
            'afmsf_2a', 'review_cert', 'edn_ql_enrollment',
            'higher_edn_qualification', 'edn_cert', 'verification_roll',
            'character_cert', 'unmarried_cert', 'caste_cert', 'class_field',
            'domicile_cert', 'outside_sanction_letter', 'willingness_cert',
            'ncc_cert', 'additional_cert', 'pan_card', 'aadhar_card', 'remarks',
            'status',
        ]
        widgets = {
            'agniveer_no': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'name': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'father_name': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'dor': forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}),
            'trade': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'aros_bros': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'bn_desp': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'relationship': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'afmsf_2a': forms.Select(attrs={'class': 'form-select form-select-sm'}, choices=YES_NO_CHOICES),
            'review_cert': forms.Select(attrs={'class': 'form-select form-select-sm'}, choices=YES_NO_CHOICES),
            'edn_ql_enrollment': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'higher_edn_qualification': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'edn_cert': forms.Select(attrs={'class': 'form-select form-select-sm'}, choices=YES_NO_CHOICES),
            'verification_roll': forms.Select(attrs={'class': 'form-select form-select-sm'}, choices=YES_NO_CHOICES),
            'character_cert': forms.Select(attrs={'class': 'form-select form-select-sm'}, choices=YES_NO_CHOICES),
            'unmarried_cert': forms.Select(attrs={'class': 'form-select form-select-sm'}, choices=YES_NO_CHOICES),
            'caste_cert': forms.Select(attrs={'class': 'form-select form-select-sm'}, choices=YES_NO_CHOICES),
            'class_field': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'domicile_cert': forms.Select(attrs={'class': 'form-select form-select-sm'}, choices=YES_NO_CHOICES),
            'outside_sanction_letter': forms.Select(attrs={'class': 'form-select form-select-sm'}, choices=YES_NO_CHOICES),
            'willingness_cert': forms.Select(attrs={'class': 'form-select form-select-sm'}, choices=YES_NO_CHOICES),
            'ncc_cert': forms.Select(attrs={'class': 'form-select form-select-sm'}, choices=YES_NO_CHOICES),
            'additional_cert': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'pan_card': forms.Select(attrs={'class': 'form-select form-select-sm'}, choices=YES_NO_CHOICES),
            'aadhar_card': forms.Select(attrs={'class': 'form-select form-select-sm'}, choices=YES_NO_CHOICES),
            'remarks': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 2}),
            'status': forms.Select(attrs={'class': 'form-select form-select-sm'}),
        }

    def clean_agniveer_no(self):
        val = self.cleaned_data.get('agniveer_no', '').strip()
        qs = Agniveer.objects.filter(agniveer_no=val)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("An Agniveer with this number already exists.")
        return val


class AgniveerExcelUploadForm(forms.Form):
    """Form for bulk Excel upload."""
    excel_file = forms.FileField(
        label='Select Excel File (.xlsx)',
        widget=forms.FileInput(attrs={
            'class': 'form-control form-control-sm',
            'accept': '.xlsx,.xls'
        })
    )


# ── Legacy form — kept for backward compat with existing views ─────────────────
class AgniveerForm(forms.ModelForm):
    class Meta:
        model = Agniveer
        fields = [
            'agniveer_no', 'name', 'father_name',
            'dor', 'trade', 'aros_bros', 'bn_desp',
            'gender', 'phone', 'email', 'address', 'photo',
            'batch', 'joining_date', 'status'
        ]
        widgets = {
            'agniveer_no': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'father_name': forms.TextInput(attrs={'class': 'form-control'}),
            'dor': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'trade': forms.Select(attrs={'class': 'form-control'}),
            'aros_bros': forms.TextInput(attrs={'class': 'form-control'}),
            'bn_desp': forms.Select(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'batch': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Batch 2024-A'}),
            'joining_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }


class AssignTrainerForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        trainers_qs = CustomUser.objects.filter(
            role__in=['trainer_nco', 'trainer_jco', 'trainer_officer'],
            is_active=True
        )
        if self.user and self.user.is_department:
            trainers_qs = trainers_qs.filter(department=self.user.get_department_code())
        self.fields['assigned_trainers'].queryset = trainers_qs
        self.fields['assigned_trainers'].widget.attrs.update({'class': 'form-control', 'size': 8})

    class Meta:
        model = Agniveer
        fields = ['assigned_trainers']
