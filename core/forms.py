from django import forms
from django.db.models import Q
from django.contrib.auth.models import User
from django.contrib.auth.forms import SetPasswordForm  # noqa: F401  (réexporté pour les vues)
from .models import UserProfile, Direction, Employee, Event


class DirectionForm(forms.ModelForm):
    """Formulaire pour les directions"""
    class Meta:
        model = Direction
        fields = ['name', 'code', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom de la direction'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Code (ex: DG, DSI, DRH)'}),
            'color': forms.TextInput(attrs={'type': 'color', 'class': 'form-control', 'style': 'height: 40px; padding: 5px;'}),
        }
        labels = {
            'name': 'Nom de la direction',
            'code': 'Code',
            'color': 'Couleur',
        }


class UserCreateForm(forms.Form):
    """Création de compte depuis une fiche employé existante.

    L'admin choisit l'employé et le rôle. Le username est auto-généré (nom.prenom),
    la direction est reprise de la fiche, et un email d'invitation est envoyé —
    l'employé définit lui-même son mot de passe via le lien reçu.
    """
    employee = forms.ModelChoiceField(
        queryset=Employee.objects.none(),
        required=True,
        label="Employé",
        empty_label="-- Sélectionner un employé --",
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_employee'}),
    )
    role = forms.ChoiceField(
        choices=UserProfile.ROLE_CHOICES,
        label="Rôle",
        widget=forms.Select(attrs={'class': 'form-control'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = (
            Employee.objects
            .filter(user_profile__isnull=True)
            .select_related('direction')
            .order_by('name')
        )

    def clean_employee(self):
        emp = self.cleaned_data.get('employee')
        if emp:
            if not emp.email:
                raise forms.ValidationError(
                    f"La fiche de {emp.name} n'a pas d'adresse email. "
                    "Ajoutez-en une avant de créer un compte."
                )
            if UserProfile.objects.filter(employee=emp).exists():
                raise forms.ValidationError(f"{emp.name} a déjà un compte utilisateur.")
        return emp


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

    # Permissions congés / RH
    is_hr_manager = forms.BooleanField(required=False, label="Gestionnaire RH")
    can_approve_leaves = forms.BooleanField(required=False, label="Peut approuver les congés (avis hiérarchique)")

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'is_active':
                field.widget.attrs['class'] = 'form-control'

        # Build employee queryset: exclude those already linked, but include the current user's employee
        current_employee_id = None
        if self.instance and hasattr(self.instance, 'profile') and self.instance.profile.employee_id:
            current_employee_id = self.instance.profile.employee_id

        self.fields['employee'].queryset = Employee.objects.filter(
            Q(user_profile__isnull=True) | Q(id=current_employee_id)
        ).distinct().order_by('name')

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
            # Permissions congés / RH
            self.fields['is_hr_manager'].initial = profile.is_hr_manager
            self.fields['can_approve_leaves'].initial = profile.can_approve_leaves

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if self.instance and User.objects.filter(username=username).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(f"Le nom d'utilisateur « {username} » est déjà utilisé.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        employee = cleaned_data.get('employee')
        if employee and self.instance:
            existing = UserProfile.objects.filter(employee=employee).exclude(user=self.instance).first()
            if existing:
                self.add_error('employee',
                    f"Cet employé ({employee.name}) est déjà lié au compte {existing.user.username}.")
        return cleaned_data

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

            # Permissions congés / RH
            profile.is_hr_manager = self.cleaned_data.get('is_hr_manager', False)
            profile.can_approve_leaves = self.cleaned_data.get('can_approve_leaves', False)

            profile.save()

        return user



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
