from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import UserProfile, Direction


class UserCreateForm(UserCreationForm):
    """Formulaire de création d'utilisateur avec profil"""
    email = forms.EmailField(required=True, label="Email")
    first_name = forms.CharField(max_length=100, required=True, label="Prénom")
    last_name = forms.CharField(max_length=100, required=True, label="Nom")
    
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES, label="Rôle")
    direction = forms.ModelChoiceField(
        queryset=Direction.objects.all(), 
        required=False, 
        label="Direction",
        empty_label="-- Aucune direction --"
    )
    phone = forms.CharField(max_length=20, required=False, label="Téléphone")
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
            if field_name == 'password1':
                field.widget.attrs['placeholder'] = 'Mot de passe'
            elif field_name == 'password2':
                field.widget.attrs['placeholder'] = 'Confirmer le mot de passe'
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            # Update or create profile
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.role = self.cleaned_data['role']
            profile.direction = self.cleaned_data.get('direction')
            profile.phone = self.cleaned_data.get('phone', '')
            profile.save()
        
        return user


class UserUpdateForm(forms.ModelForm):
    """Formulaire de modification d'utilisateur"""
    email = forms.EmailField(required=True, label="Email")
    first_name = forms.CharField(max_length=100, required=True, label="Prénom")
    last_name = forms.CharField(max_length=100, required=True, label="Nom")
    is_active = forms.BooleanField(required=False, label="Compte actif")
    
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES, label="Rôle")
    direction = forms.ModelChoiceField(
        queryset=Direction.objects.all(), 
        required=False, 
        label="Direction",
        empty_label="-- Aucune direction --"
    )
    phone = forms.CharField(max_length=20, required=False, label="Téléphone")
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'is_active']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'is_active':
                field.widget.attrs['class'] = 'form-control'
        
        # Pre-fill profile fields
        if self.instance and hasattr(self.instance, 'profile'):
            self.fields['role'].initial = self.instance.profile.role
            self.fields['direction'].initial = self.instance.profile.direction
            self.fields['phone'].initial = self.instance.profile.phone
    
    def save(self, commit=True):
        user = super().save(commit=False)
        
        if commit:
            user.save()
            # Update profile
            profile = user.profile
            profile.role = self.cleaned_data['role']
            profile.direction = self.cleaned_data.get('direction')
            profile.phone = self.cleaned_data.get('phone', '')
            profile.save()
        
        return user


class PasswordChangeForm(forms.Form):
    """Formulaire de changement de mot de passe"""
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Nouveau mot de passe'}),
        label="Nouveau mot de passe"
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirmer le mot de passe'}),
        label="Confirmer le mot de passe"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('new_password1')
        password2 = cleaned_data.get('new_password2')
        
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Les mots de passe ne correspondent pas.")
        
        return cleaned_data
