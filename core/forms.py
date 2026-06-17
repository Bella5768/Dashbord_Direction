from django import forms
from django.db.models import Q
from django.contrib.auth.models import User
from django.contrib.auth.forms import SetPasswordForm  # noqa: F401  (réexporté pour les vues)
from .models import UserProfile, Direction, Employee, Event, Role


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
    """Création de compte depuis une fiche employé existante."""
    employee = forms.ModelChoiceField(
        queryset=Employee.objects.none(),
        required=True,
        label="Employé",
        empty_label="-- Sélectionner un employé --",
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_employee'}),
    )
    role = forms.ModelChoiceField(
        queryset=Role.objects.all(),
        required=False,
        label="Rôle",
        empty_label="-- Sélectionner un rôle --",
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
    """Formulaire de modification d'utilisateur."""
    email = forms.EmailField(required=True, label="Email")
    first_name = forms.CharField(max_length=100, required=False, label="Prénom")
    last_name = forms.CharField(max_length=100, required=False, label="Nom")
    is_active = forms.BooleanField(required=False, label="Compte actif")

    role = forms.ModelChoiceField(
        queryset=Role.objects.all(),
        required=False,
        label="Rôle",
        empty_label="-- Sans rôle --",
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_role'}),
    )
    direction = forms.ModelChoiceField(
        queryset=Direction.objects.all(),
        required=False,
        label="Direction",
        empty_label="-- Aucune direction --",
    )
    employee = forms.ModelChoiceField(
        queryset=Employee.objects.all(),
        required=False,
        label="Employé",
        empty_label="-- Aucun employé --",
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

        current_employee_id = None
        if self.instance and hasattr(self.instance, 'profile') and self.instance.profile.employee_id:
            current_employee_id = self.instance.profile.employee_id

        self.fields['employee'].queryset = Employee.objects.filter(
            Q(user_profile__isnull=True) | Q(id=current_employee_id)
        ).distinct().order_by('name')

        if self.instance and hasattr(self.instance, 'profile'):
            profile = self.instance.profile
            self.fields['role'].initial = profile.role
            self.fields['direction'].initial = profile.direction
            self.fields['employee'].initial = profile.employee
            self.fields['phone'].initial = profile.phone

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
            profile = user.profile
            profile.role = self.cleaned_data.get('role')
            profile.direction = self.cleaned_data.get('direction')
            profile.employee = self.cleaned_data.get('employee')
            profile.phone = self.cleaned_data.get('phone', '')
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

    def clean_date(self):
        from django.utils import timezone
        date = self.cleaned_data.get('date')
        # En édition, on autorise la date existante même si elle est passée
        if date and not self.instance.pk and date < timezone.now().date():
            raise forms.ValidationError("La date ne peut pas être dans le passé.")
        return date

    def clean_duration(self):
        duration = self.cleaned_data.get('duration')
        if duration is not None and duration < 5:
            raise forms.ValidationError("La durée minimale est de 5 minutes.")
        if duration is not None and duration > 1440:
            raise forms.ValidationError("La durée maximale est de 24h (1440 min).")
        return duration
