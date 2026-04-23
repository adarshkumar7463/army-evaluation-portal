"""
Evaluation App - Forms
"""

from django import forms
from django.core.exceptions import ValidationError
from .models import EvaluationSheet, Marks
from departments.models import Agniveer
from accounts.models import CustomUser


class EvaluationSheetForm(forms.ModelForm):
    department = forms.ChoiceField(
        choices=[('A','Department A'),('B','Department B'),('C','Department C'),('D','Department D')],
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = EvaluationSheet
        fields = ['agniveer', 'category', 'test_type', 'department', 'evaluation_date', 'remarks']
        widgets = {
            'agniveer': forms.Select(attrs={'class': 'form-control select2'}),
            'category': forms.Select(attrs={'class': 'form-control', 'id': 'id_category'}),
            'test_type': forms.Select(attrs={'class': 'form-control', 'id': 'id_test_type'}),
            'evaluation_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.user:
            if self.user.is_department:
                # Allow all agniveers for department users to evaluate
                self.fields['agniveer'].queryset = Agniveer.objects.all()
            elif self.user.is_trainer:
                self.fields['agniveer'].queryset = self.user.assigned_agniveers.all()
            else:
                self.fields['agniveer'].queryset = Agniveer.objects.all()

        # Limit test_type choices by category
        on_field_types = ['physical', 'weapon', 'field']
        trade_types = ['assessment', 'viva', 'ojt', 'written']
        self.on_field_types = on_field_types
        self.trade_types = trade_types


class AgniveerEvaluationForm(forms.Form):
    category = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_eval_category'})
    )
    test_type = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_eval_test_type'})
    )
    marks = forms.IntegerField(
        min_value=0, max_value=20,
        widget=forms.NumberInput(attrs={
            'class': 'form-control marks-input text-center',
            'min': 0, 'max': 20,
            'placeholder': '0 - 20'
        })
    )
    remarks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional remarks'})
    )

    def __init__(self, *args, **kwargs):
        department = kwargs.pop('department', 'A')
        super().__init__(*args, **kwargs)
        from .constants import DEPT_CONFIG
        config = DEPT_CONFIG.get(department, DEPT_CONFIG['A'])
        self.fields['category'].choices = config['categories']
        self.fields['test_type'].choices = config['test_types']
        self.test_to_category = config['test_to_category']

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        test_type = cleaned_data.get('test_type')
        if category and test_type:
            expected_category = self.test_to_category.get(test_type)
            if category != expected_category:
                raise ValidationError(f'Test type "{test_type}" does not belong to category "{category}".')
        return cleaned_data


class MarksForm(forms.ModelForm):
    class Meta:
        model = Marks
        fields = ['marks', 'remarks']
        widgets = {
            'marks': forms.NumberInput(attrs={
                'class': 'form-control marks-input',
                'min': 0, 'max': 20,
                'placeholder': '0 - 20'
            }),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def clean_marks(self):
        marks = self.cleaned_data.get('marks')
        if marks is not None and marks > 20:
            raise ValidationError("Marks cannot exceed 20.")
        return marks


class MarksEntryForm(forms.Form):
    """Single form for entering marks from evaluator."""
    marks = forms.IntegerField(
        min_value=0, max_value=20,
        widget=forms.NumberInput(attrs={
            'class': 'form-control marks-input text-center fw-bold',
            'min': 0, 'max': 20,
            'style': 'font-size:1.5rem;'
        })
    )
    remarks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional remarks'})
    )


class EvaluationFilterForm(forms.Form):
    department = forms.ChoiceField(
        choices=[('', 'All Departments')] + [('A','Dept A'),('B','Dept B'),('C','Dept C'),('D','Dept D')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    category = forms.ChoiceField(
        choices=[('', 'All Categories')] + EvaluationSheet.CATEGORY_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    test_type = forms.ChoiceField(
        choices=[('', 'All Types')] + EvaluationSheet.TEST_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    pass_fail = forms.ChoiceField(
        choices=[('', 'All'), ('pass', 'Pass'), ('fail', 'Fail')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search enrollment / name...'})
    )
