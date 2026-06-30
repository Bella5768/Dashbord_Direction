from django import forms
from django.db.models import Max
from django.utils.translation import gettext_lazy as _
from .models import Project, Document, Request, Partner, Direction, Budget, Employee, Milestone, SubMilestone, ProjectFolder, ProjectDocument, ProjectMember, ProjectNeed, ProjectComment, ProjectRole, Role
from .currencies import CURRENCY_CHOICES, convert_currency, format_currency
from .fields import IntlPhoneField
from .validators import validate_safe_file


class ProjectForm(forms.ModelForm):
    """Formulaire pour les projets"""
    currency = forms.ChoiceField(choices=CURRENCY_CHOICES, initial='GNF', label=_("Devise"))

    class Meta:
        model = Project
        fields = ['name', 'description', 'direction', 'status', 'priority',
                  'budget', 'budget_consumed', 'currency', 'start_date', 'end_date',
                  'manager_employee']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'manager_employee': forms.Select(attrs={'class': 'form-control select-searchable'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
        self.fields['currency'].widget.attrs['class'] = 'form-control select-searchable'
        # Direction optionnelle
        self.fields['direction'].required = False
        self.fields['direction'].empty_label = _("-- Aucune direction --")
        # manager_employee : filtrer les internes uniquement
        self.fields['manager_employee'].queryset = Employee.objects.filter(is_external=False).order_by('name')
        self.fields['manager_employee'].required = True
        self.fields['manager_employee'].empty_label = _("-- Sélectionner un responsable --")
        self.fields['manager_employee'].label = _("Responsable du projet")
        self.fields['manager_employee'].help_text = _("Associe un employé interne comme responsable du projet.")

        # Budget et budget consomme optionnels (valeur par defaut 0 si vide)
        self.fields['budget'].required = False
        self.fields['budget_consumed'].required = False
        self.fields['budget'].widget.attrs['placeholder'] = _('0')
        self.fields['budget_consumed'].widget.attrs['placeholder'] = _('0')
        
        # Si c'est une édition (projet existant), les dates ne sont pas obligatoires
        if self.instance and self.instance.pk:
            self.fields['start_date'].required = False
            self.fields['end_date'].required = False
        
        # Ajouter des informations sur la conversion de devise
        if self.instance and self.instance.pk and self.instance.currency:
            current_currency = self.instance.currency
            if current_currency != 'GNF':
                gnf_equivalent = convert_currency(float(self.instance.budget), current_currency, 'GNF')
                self.fields['budget'].help_text = _("Équivalent: %(amount)s") % {'amount': format_currency(gnf_equivalent, 'GNF')}
                if self.instance.budget_consumed:
                    consumed_gnf = convert_currency(float(self.instance.budget_consumed), current_currency, 'GNF')
                    self.fields['budget_consumed'].help_text = _("Équivalent: %(amount)s") % {'amount': format_currency(consumed_gnf, 'GNF')}
    
    def clean_budget(self):
        """Budget optionnel : valeur par defaut 0 si vide"""
        value = self.cleaned_data.get('budget')
        return value if value is not None else 0

    def clean_budget_consumed(self):
        """Budget consomme optionnel : valeur par defaut 0 si vide"""
        value = self.cleaned_data.get('budget_consumed')
        return value if value is not None else 0

    def clean_start_date(self):
        """Si pas de date fournie en édition, garder l'existante"""
        date = self.cleaned_data.get('start_date')
        if not date and self.instance and self.instance.pk:
            return self.instance.start_date
        return date
    
    def clean_end_date(self):
        """Si pas de date fournie en édition, garder l'existante"""
        date = self.cleaned_data.get('end_date')
        if not date and self.instance and self.instance.pk:
            return self.instance.end_date
        return date

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_date')
        end = cleaned.get('end_date')
        if start and end and end < start:
            self.add_error('end_date', _("La date de fin doit être postérieure ou égale à la date de début."))
        return cleaned


class DocumentForm(forms.ModelForm):
    """Formulaire pour les documents"""
    class Meta:
        model = Document
        fields = ['title', 'doc_type', 'status', 'priority', 'direction', 'due_date', 'created_by', 'file']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
        self.fields['file'].validators = [validate_safe_file]

    def clean(self):
        cleaned = super().clean()
        due = cleaned.get('due_date')
        if self.instance and self.instance.pk and self.instance.created_at:
            created = self.instance.created_at
        else:
            from datetime import date
            created = date.today()
        if due and due < created:
            self.add_error('due_date', _("La date limite doit être postérieure ou égale à la date de création."))
        return cleaned


class MilestoneForm(forms.ModelForm):
    """Formulaire pour les jalons"""
    class Meta:
        model = Milestone
        fields = ['name', 'due_date', 'need', 'status', 'manual_progress', 'completed', 'order']
        widgets = {
            'order': forms.HiddenInput(),
            'manual_progress': forms.NumberInput(attrs={'min': 0, 'max': 100, 'style': 'width: 100px;'}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'need': forms.Textarea(attrs={'rows': 3, 'placeholder': _('Décrivez le besoin lié à cette étape...')}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, project=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
        self.fields['manual_progress'].label = _('Progression (%)')
        self.fields['manual_progress'].help_text = _("Utilisé uniquement si le jalon n'a pas de sous-étapes")
        if project:
            # Auto-incrémenter l'ordre si nouveau jalon
            if not self.instance.pk:
                max_order = project.milestones.aggregate(Max('order'))['order__max']
                self.fields['order'].initial = (max_order or 0) + 1

    def clean(self):
        cleaned = super().clean()
        due = cleaned.get('due_date')
        project = self.project
        if due and project and project.start_date and project.end_date:
            if due < project.start_date or due > project.end_date:
                self.add_error(
                    'due_date',
                    _("La date du jalon doit être comprise entre %(start)s et %(end)s.") % {
                        'start': project.start_date,
                        'end': project.end_date,
                    }
                )
        return cleaned


class SubMilestoneForm(forms.ModelForm):
    """Formulaire pour les sous-étapes"""
    class Meta:
        model = SubMilestone
        fields = ['name', 'due_date', 'need', 'completed', 'order']
        widgets = {
            'order': forms.HiddenInput(),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'need': forms.Textarea(attrs={'rows': 3, 'placeholder': _('Décrivez le besoin lié à cette sous-étape...')}),
        }

    def __init__(self, milestone=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.milestone = milestone
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
        if milestone:
            # Auto-incrémenter l'ordre si nouvelle sous-étape
            if not self.instance.pk:
                max_order = milestone.sub_milestones.aggregate(Max('order'))['order__max']
                self.fields['order'].initial = (max_order or 0) + 1

    def clean(self):
        cleaned = super().clean()
        due = cleaned.get('due_date')
        milestone = self.milestone
        if due and milestone:
            if milestone.due_date and due > milestone.due_date:
                self.add_error(
                    'due_date',
                    _("La date de la sous-étape doit être antérieure ou égale à celle du jalon (%(date)s).") % {
                        'date': milestone.due_date,
                    }
                )
            project = milestone.project
            if project and project.start_date and project.end_date:
                if due < project.start_date or due > project.end_date:
                    self.add_error(
                        'due_date',
                        _("La date de la sous-étape doit être comprise entre %(start)s et %(end)s.") % {
                            'start': project.start_date,
                            'end': project.end_date,
                        }
                    )
        return cleaned


class ProjectFolderForm(forms.ModelForm):
    """Formulaire pour les dossiers de projet"""
    class Meta:
        model = ProjectFolder
        fields = ['name', 'parent']
        widgets = {
            'parent': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        # Filter parent folders to only show folders from the same project
        if self.instance and self.instance.pk:
            self.fields['parent'].queryset = ProjectFolder.objects.filter(project=project).exclude(pk=self.instance.pk)
        else:
            self.fields['parent'].queryset = ProjectFolder.objects.filter(project=project)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'


class ProjectDocumentForm(forms.ModelForm):
    """Formulaire pour les documents de projet"""
    class Meta:
        model = ProjectDocument
        fields = ['title', 'description', 'folder', 'file']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        self.fields['folder'].queryset = ProjectFolder.objects.filter(project=project)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
        self.fields['file'].validators = [validate_safe_file]


class ProjectMemberForm(forms.ModelForm):
    """Formulaire pour les membres de projet."""
    class Meta:
        model = ProjectMember
        fields = ['employee', 'project_role']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-control select-searchable'}),
            'project_role': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        self._is_edit = bool(self.instance and self.instance.pk)
        # Employee obligatoire à la création, optionnel en édition (déjà fixé)
        self.fields['employee'].required = not self._is_edit
        self.fields['project_role'].required = False
        self.fields['project_role'].label = _("Rôle projet")

        if self._is_edit:
            existing_members = project.members.exclude(pk=self.instance.pk)
        else:
            existing_members = project.members.all()

        employee_ids = existing_members.values_list('employee_id', flat=True)
        available_employees = Employee.objects.exclude(id__in=employee_ids).order_by('name')

        employee_choices = [('', _('--- Sélectionner un employé ---'))]
        for emp in available_employees:
            display_text = emp.name
            if emp.role:
                display_text += f" - {emp.role}"
            if emp.email:
                display_text += f" ({emp.email})"
            employee_choices.append((emp.id, display_text))

        self.fields['employee'].choices = employee_choices
        self.fields['employee'].widget.attrs.update({
            'data-placeholder': _('Rechercher un employé...'),
            'data-allow-clear': 'true',
        })

        # Rôles projet disponibles
        self.fields['project_role'].queryset = ProjectRole.objects.all()

        for field_name, field in self.fields.items():
            if field_name != 'employee':
                field.widget.attrs['class'] = 'form-control'

    def clean_employee(self):
        employee = self.cleaned_data.get('employee')
        if not self._is_edit and not employee:
            raise forms.ValidationError(_("Veuillez sélectionner un employé."))
        return employee


class ProjectNeedForm(forms.ModelForm):
    """Formulaire pour les besoins de projet"""
    class Meta:
        model = ProjectNeed
        fields = ['title', 'description', 'priority']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'


class ProjectCommentForm(forms.ModelForm):
    """Formulaire pour les commentaires de projet"""
    class Meta:
        model = ProjectComment
        fields = ['message']
        widgets = {
            'message': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'


class RequestForm(forms.ModelForm):
    """Formulaire pour les demandes"""
    class Meta:
        model = Request
        fields = ['title', 'description', 'direction', 'priority', 'created_by']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'


class PartnerForm(forms.ModelForm):
    """Formulaire pour les partenaires"""
    phone = IntlPhoneField(label=_("Téléphone"), required=True)

    class Meta:
        model = Partner
        fields = ['name', 'partner_type', 'status', 'contact_person', 'email', 'phone', 'start_date', 'logo']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_date')
        if start:
            from datetime import date
            if start > date.today():
                self.add_error('start_date', _("La date de début de collaboration ne peut pas être dans le futur."))
        return cleaned


class BudgetForm(forms.ModelForm):
    """Formulaire pour les budgets"""
    currency = forms.ChoiceField(choices=CURRENCY_CHOICES, initial='GNF', label=_("Devise"))
    
    class Meta:
        model = Budget
        fields = ['project', 'direction', 'allocated', 'consumed', 'currency']
        widgets = {
            'allocated': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'consumed': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
        self.fields['allocated'].label = _('Budget alloué')
        self.fields['consumed'].label = _('Budget consommé')
        self.fields['project'].required = False
        self.fields['project'].empty_label = _("-- Sélectionner un projet --")
        self.fields['direction'].required = False
        self.fields['direction'].empty_label = _("-- Aucune direction --")
        self.fields['currency'].widget.attrs['class'] = 'form-control select-searchable'


class EmployeeForm(forms.ModelForm):
    """Formulaire pour les employés"""
    phone = IntlPhoneField(label=_("Téléphone"), required=False)
    system_role = forms.ModelChoiceField(
        queryset=Role.objects.all().order_by('name'),
        required=False,
        label=_("Rôle système (compte utilisateur)"),
        empty_label=_("-- Ne pas créer de compte --"),
        widget=forms.Select(attrs={'class': 'form-control'}),
    )

    class Meta:
        model = Employee
        fields = ['name', 'direction', 'role', 'phone', 'email', 'workload', 'skills', 'is_external', 'organization']
        widgets = {
            'workload': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100}),
            'skills': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': _('Compétences séparées par des virgules')}),
            'organization': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Ex : Cabinet XYZ, ONG Alpha…')}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name not in ('workload', 'skills', 'is_external', 'organization'):
                field.widget.attrs['class'] = 'form-control'
        self.fields['name'].label = _('Nom complet')
        self.fields['role'].label = _('Fonction / Poste')
        self.fields['phone'].label = _('Téléphone')
        self.fields['email'].label = _('Email')
        self.fields['direction'].required = False
        self.fields['organization'].required = False
        self.fields['email'].required = False

        # Pré-remplir le rôle système si l'employé a déjà un compte
        if self.instance and self.instance.pk:
            try:
                self.fields['system_role'].initial = self.instance.user_profile.role
            except Exception:
                pass

        # Restriction : un directeur ne peut creer/modifier que des employes de sa direction
        profile = getattr(user, 'profile', None) if user else None
        if profile and profile.role_slug == 'directeur' and profile.direction_id:
            from .models import Direction
            self.fields['direction'].queryset = Direction.objects.filter(id=profile.direction_id)
            self.fields['direction'].initial = profile.direction_id
            self.fields['direction'].disabled = True
            self.fields['direction'].help_text = _("Verrouillé sur votre direction.")

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if email:
            qs = Employee.objects.filter(email__iexact=email)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                other = qs.first()
                raise forms.ValidationError(_("L'email « %(email)s » est déjà utilisé par %(name)s.") % {'email': email, 'name': other.name})
        return email

    def clean(self):
        cleaned = super().clean()
        is_external = cleaned.get('is_external', False)
        organization = cleaned.get('organization', '').strip()
        email = cleaned.get('email', '').strip()
        system_role = cleaned.get('system_role')

        if is_external and not organization:
            self.add_error('organization', _("L'organisation est obligatoire pour une personne externe."))

        if not is_external and not email:
            self.add_error('email', _("L'email est obligatoire pour un employé interne (nécessaire pour la création de compte)."))

        if system_role and not email:
            self.add_error('system_role', _("Un email est requis pour créer un compte utilisateur."))

        return cleaned
