from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import UserProfile, Direction, Employee, Event


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
    employee = forms.ModelChoiceField(
        queryset=Employee.objects.all(),
        required=False,
        label="Employé",
        empty_label="-- Aucun employé --"
    )
    phone = forms.CharField(max_length=20, required=False, label="Téléphone")
    
    # Permissions budgets
    budget_view = forms.BooleanField(required=False, label="Peut voir les budgets")
    budget_manage = forms.BooleanField(required=False, label="Peut gérer les budgets")
    budget_view_all_directions = forms.BooleanField(required=False, label="Peut voir les budgets de toutes les directions")
    
    # Permissions projets
    can_create_project = forms.BooleanField(required=False, label="Peut créer des projets")
    can_edit_projects = forms.BooleanField(required=False, label="Peut modifier les projets")
    can_add_milestones = forms.BooleanField(required=False, label="Peut ajouter des jalons")
    can_add_members = forms.BooleanField(required=False, label="Peut ajouter des membres")
    
    # Permissions utilisateurs et demandes
    can_manage_users = forms.BooleanField(required=False, label="Peut gérer les utilisateurs")
    can_approve_requests = forms.BooleanField(required=False, label="Peut approuver les demandes")
    
    # Permissions événements
    can_create_events = forms.BooleanField(required=False, label="Peut créer des événements")
    
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
            profile.employee = self.cleaned_data.get('employee')
            profile.phone = self.cleaned_data.get('phone', '')
            
            # Permissions budgets
            profile.budget_view = self.cleaned_data.get('budget_view', False)
            profile.budget_manage = self.cleaned_data.get('budget_manage', False)
            profile.budget_view_all_directions = self.cleaned_data.get('budget_view_all_directions', False)
            
            # Permissions projets
            profile.can_create_project = self.cleaned_data.get('can_create_project', False)
            profile.can_edit_projects = self.cleaned_data.get('can_edit_projects', False)
            profile.can_add_milestones = self.cleaned_data.get('can_add_milestones', False)
            profile.can_add_members = self.cleaned_data.get('can_add_members', False)
            
            # Permissions utilisateurs et demandes
            profile.can_manage_users = self.cleaned_data.get('can_manage_users', False)
            profile.can_approve_requests = self.cleaned_data.get('can_approve_requests', False)
            
            # Permissions événements
            profile.can_create_events = self.cleaned_data.get('can_create_events', False)
            
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
    employee = forms.ModelChoiceField(
        queryset=Employee.objects.all(),
        required=False,
        label="Employé",
        empty_label="-- Aucun employé --"
    )
    phone = forms.CharField(max_length=20, required=False, label="Téléphone")
    
    # Permissions budgets
    budget_view = forms.BooleanField(required=False, label="Peut voir les budgets")
    budget_manage = forms.BooleanField(required=False, label="Peut gérer les budgets")
    budget_view_all_directions = forms.BooleanField(required=False, label="Peut voir les budgets de toutes les directions")
    
    # Permissions projets
    can_create_project = forms.BooleanField(required=False, label="Peut créer des projets")
    can_edit_projects = forms.BooleanField(required=False, label="Peut modifier les projets")
    can_add_milestones = forms.BooleanField(required=False, label="Peut ajouter des jalons")
    can_add_members = forms.BooleanField(required=False, label="Peut ajouter des membres")
    
    # Permissions utilisateurs et demandes
    can_manage_users = forms.BooleanField(required=False, label="Peut gérer les utilisateurs")
    can_approve_requests = forms.BooleanField(required=False, label="Peut approuver les demandes")
    
    # Permissions événements
    can_create_events = forms.BooleanField(required=False, label="Peut créer des événements")
    
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
            profile = self.instance.profile
            self.fields['role'].initial = profile.role
            self.fields['direction'].initial = profile.direction
            self.fields['employee'].initial = profile.employee
            self.fields['phone'].initial = profile.phone
            # Permissions budgets
            self.fields['budget_view'].initial = profile.budget_view
            self.fields['budget_manage'].initial = profile.budget_manage
            self.fields['budget_view_all_directions'].initial = profile.budget_view_all_directions
            # Permissions projets
            self.fields['can_create_project'].initial = profile.can_create_project
            self.fields['can_edit_projects'].initial = profile.can_edit_projects
            self.fields['can_add_milestones'].initial = profile.can_add_milestones
            self.fields['can_add_members'].initial = profile.can_add_members
            # Permissions utilisateurs et demandes
            self.fields['can_manage_users'].initial = profile.can_manage_users
            self.fields['can_approve_requests'].initial = profile.can_approve_requests
            # Permissions événements
            self.fields['can_create_events'].initial = profile.can_create_events
    
    def save(self, commit=True):
        user = super().save(commit=False)
        
        if commit:
            user.save()
            # Update profile
            profile = user.profile
            profile.role = self.cleaned_data['role']
            profile.direction = self.cleaned_data.get('direction')
            profile.employee = self.cleaned_data.get('employee')
            profile.phone = self.cleaned_data.get('phone', '')
            
            # Permissions budgets
            profile.budget_view = self.cleaned_data.get('budget_view', False)
            profile.budget_manage = self.cleaned_data.get('budget_manage', False)
            profile.budget_view_all_directions = self.cleaned_data.get('budget_view_all_directions', False)
            
            # Permissions projets
            profile.can_create_project = self.cleaned_data.get('can_create_project', False)
            profile.can_edit_projects = self.cleaned_data.get('can_edit_projects', False)
            profile.can_add_milestones = self.cleaned_data.get('can_add_milestones', False)
            profile.can_add_members = self.cleaned_data.get('can_add_members', False)
            
            # Permissions utilisateurs et demandes
            profile.can_manage_users = self.cleaned_data.get('can_manage_users', False)
            profile.can_approve_requests = self.cleaned_data.get('can_approve_requests', False)
            
            # Permissions événements
            profile.can_create_events = self.cleaned_data.get('can_create_events', False)
            
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


class EventForm(forms.ModelForm):
    """Formulaire pour les événements du calendrier"""
    class Meta:
        model = Event
        fields = ['title', 'event_type', 'description', 'date', 'time', 'duration', 'location', 'participants']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'participants': forms.SelectMultiple(attrs={'class': 'form-control', 'size': 5}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'
