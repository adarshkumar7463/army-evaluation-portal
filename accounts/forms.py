"""
Accounts App - Forms
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from .models import CustomUser


class ArmyLoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Service Number / Username',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password',
        })
    )


class CreateGHeadForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'username', 'email', 'service_number', 'rank', 'phone']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'service_number': forms.TextInput(attrs={'class': 'form-control'}),
            'rank': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        if password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.role = CustomUser.ROLE_G_HEAD
        if commit:
            user.save()
        return user


class CreateDepartmentUserForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    DEPT_ROLE_CHOICES = [
        ('dept_a', 'Battalion'),
        ('dept_b', 'TTS'),
        ('dept_c', 'CS'),
        ('dept_d', 'Clerk'),
    ]
    role = forms.ChoiceField(choices=DEPT_ROLE_CHOICES, widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_role_select'}))
    
    battalion_unit = forms.ChoiceField(
        choices=[('', 'Battalion Head (All Units)')] + CustomUser.BATTALION_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_battalion_select'})
    )
    
    tts_trade = forms.ChoiceField(
        choices=[('', 'TTS Head (All Trades)')] + CustomUser.TTS_TRADE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_tts_select'})
    )
    
    platoon = forms.ChoiceField(
        choices=[('', '--- All Platoons / No Platoon ---')] + CustomUser.PLATOON_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_platoon_select'})
    )
    
    company = forms.ChoiceField(
        choices=[('', '--- All Companies / No Company ---')] + CustomUser.COMPANY_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_company_select'})
    )

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'username', 'email', 'service_number', 'rank', 'phone', 'role', 'battalion_unit', 'tts_trade', 'company', 'platoon']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'service_number': forms.TextInput(attrs={'class': 'form-control'}),
            'rank': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("password") != cleaned_data.get("confirm_password"):
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.role = self.cleaned_data['role']
        dept_map = {'dept_a': 'A', 'dept_b': 'B', 'dept_c': 'C', 'dept_d': 'D'}
        user.department = dept_map.get(user.role)
        user.company = self.cleaned_data.get('company')
        user.platoon = self.cleaned_data.get('platoon')
        
        if user.role == 'dept_a':
            user.battalion_unit = self.cleaned_data.get('battalion_unit')
            user.tts_trade = None
        elif user.role == 'dept_b':
            user.tts_trade = self.cleaned_data.get('tts_trade')
            user.battalion_unit = None
        else:
            user.battalion_unit = None
            user.tts_trade = None
            
        if commit:
            user.save()
        return user


class CreateTrainerForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    TRAINER_ROLE_CHOICES = [
        ('trainer_nco', 'NCO'),
        ('trainer_jco', 'JCO'),
        ('trainer_officer', 'Officer'),
    ]
    battalion_unit = forms.ChoiceField(
        choices=[('', '--- Select Battalion ---')] + CustomUser.BATTALION_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_battalion_select'})
    )
    
    tts_trade = forms.ChoiceField(
        choices=[('', '--- Select TTS Trade ---')] + CustomUser.TTS_TRADE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_tts_select'})
    )
    
    platoon = forms.ChoiceField(
        choices=[('', '--- All Platoons / No Platoon ---')] + CustomUser.PLATOON_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_platoon_select'})
    )
    
    company = forms.ChoiceField(
        choices=[('', '--- All Companies / No Company ---')] + CustomUser.COMPANY_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_company_select'})
    )

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'username', 'email', 'service_number', 'rank', 'phone', 'role', 'battalion_unit', 'tts_trade', 'company', 'platoon']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'service_number': forms.TextInput(attrs={'class': 'form-control'}),
            'rank': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("password") != cleaned_data.get("confirm_password"):
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.role = self.cleaned_data['role']
        user.battalion_unit = self.cleaned_data.get('battalion_unit')
        user.tts_trade = self.cleaned_data.get('tts_trade')
        user.company = self.cleaned_data.get('company')
        user.platoon = self.cleaned_data.get('platoon')
        if commit:
            user.save()
        return user


class CreateRegistrationOfficeForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'username', 'email', 'service_number', 'rank', 'phone']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'service_number': forms.TextInput(attrs={'class': 'form-control'}),
            'rank': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("password") != cleaned_data.get("confirm_password"):
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.role = CustomUser.ROLE_REGISTRATION
        if commit:
            user.save()
        return user


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'phone', 'rank', 'profile_photo']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'rank': forms.TextInput(attrs={'class': 'form-control'}),
        }
