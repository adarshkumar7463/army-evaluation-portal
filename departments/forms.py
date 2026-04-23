"""
Departments App - Forms
"""

from django import forms
from .models import Agniveer
from accounts.models import CustomUser


class AgniveerForm(forms.ModelForm):
    class Meta:
        model = Agniveer
        fields = [
            'enrollment_number', 'first_name', 'last_name', 'date_of_birth',
            'gender', 'phone', 'email', 'address', 'photo',
            'batch', 'joining_date', 'status'
        ]
        widgets = {
            'enrollment_number': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'department': forms.Select(attrs={'class': 'form-control'}),
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
