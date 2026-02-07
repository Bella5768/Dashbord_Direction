from django import forms
from django.db.models import Max
from .models import Project, Document, Request, Partner, Event, Direction, Budget, Employee, Milestone, SubMilestone, ProjectFolder, ProjectDocument, ProjectMember, ProjectNeed, ProjectComment
from .currencies import CURRENCY_CHOICES, convert_currency, format_currency


class ProjectForm(forms.ModelForm):
    """Formulaire pour les projets"""
    currency = forms.ChoiceField(choices=CURRENCY_CHOICES, initial='GNF', label="Devise")
    
    class Meta:
        model = Project
        fields = ['name', 'description', 'direction', 'status', 'priority', 
                  'budget', 'budget_consumed', 'currency', 'start_date', 'end_date', 'manager']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
        self.fields['currency'].widget.attrs['class'] = 'form-control select-searchable'
        
        # Si c'est une édition (projet existant), les dates ne sont pas obligatoires
        if self.instance and self.instance.pk:
            self.fields['start_date'].required = False
            self.fields['end_date'].required = False
        
        # Ajouter des informations sur la conversion de devise
        if self.instance and self.instance.pk and self.instance.currency:
            current_currency = self.instance.currency
            if current_currency != 'GNF':
                gnf_equivalent = convert_currency(float(self.instance.budget), current_currency, 'GNF')
                self.fields['budget'].help_text = f"Équivalent: {format_currency(gnf_equivalent, 'GNF')}"
                if self.instance.budget_consumed:
                    consumed_gnf = convert_currency(float(self.instance.budget_consumed), current_currency, 'GNF')
                    self.fields['budget_consumed'].help_text = f"Équivalent: {format_currency(consumed_gnf, 'GNF')}"
    
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


class MilestoneForm(forms.ModelForm):
    """Formulaire pour les jalons"""
    class Meta:
        model = Milestone
        fields = ['name', 'assigned_to', 'need', 'manual_progress', 'completed', 'order']
        widgets = {
            'order': forms.HiddenInput(),
            'manual_progress': forms.NumberInput(attrs={'min': 0, 'max': 100, 'style': 'width: 100px;'}),
            'assigned_to': forms.Select(attrs={'class': 'form-control'}),
            'need': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Décrivez le besoin lié à cette étape...'}),
        }
    
    def __init__(self, project=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
        self.fields['manual_progress'].label = 'Progression (%)'
        self.fields['manual_progress'].help_text = 'Utilisé uniquement si le jalon n\'a pas de sous-étapes'
        if project:
            from .models import Employee
            # Montrer tous les employés du système pour l'affectation
            self.fields['assigned_to'].queryset = Employee.objects.all().order_by('name')
            # Auto-incrémenter l'ordre si nouveau jalon
            if not self.instance.pk:
                max_order = project.milestones.aggregate(Max('order'))['order__max']
                self.fields['order'].initial = (max_order or 0) + 1


class SubMilestoneForm(forms.ModelForm):
    """Formulaire pour les sous-étapes"""
    class Meta:
        model = SubMilestone
        fields = ['name', 'assigned_to', 'need', 'completed', 'order']
        widgets = {
            'order': forms.HiddenInput(),
            'assigned_to': forms.Select(attrs={'class': 'form-control'}),
            'need': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Décrivez le besoin lié à cette sous-étape...'}),
        }
    
    def __init__(self, milestone=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.milestone = milestone
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
        if milestone:
            from .models import Employee
            # Montrer tous les employés du système pour l'affectation
            self.fields['assigned_to'].queryset = Employee.objects.all().order_by('name')
            # Auto-incrémenter l'ordre si nouvelle sous-étape
            if not self.instance.pk:
                max_order = milestone.sub_milestones.aggregate(Max('order'))['order__max']
                self.fields['order'].initial = (max_order or 0) + 1


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
        # Filter folders to only show folders from the same project
        self.fields['folder'].queryset = ProjectFolder.objects.filter(project=project)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'


class ProjectMemberForm(forms.ModelForm):
    """Formulaire pour les membres de projet"""
    class Meta:
        model = ProjectMember
        fields = ['employee', 'role', 'can_manage_members_perm', 'can_edit_project_perm', 
                  'can_add_milestones_perm', 'can_add_documents_perm', 'can_add_needs_perm', 'can_add_comments_perm']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-control select-searchable'}),
            'role': forms.Select(attrs={'class': 'form-control', 'onchange': 'togglePermissions()'}),
            'can_manage_members_perm': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_edit_project_perm': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_add_milestones_perm': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_add_documents_perm': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_add_needs_perm': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_add_comments_perm': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        # Rendre employee non requis pour permettre la création d'un nouvel employé
        self.fields['employee'].required = False
        # Filter employees to exclude those already in the project
        if self.instance and self.instance.pk:
            existing_members = project.members.exclude(pk=self.instance.pk)
        else:
            existing_members = project.members.all()
        
        employee_ids = existing_members.values_list('employee_id', flat=True)
        
        # Get available employees with their details
        available_employees = Employee.objects.exclude(id__in=employee_ids).order_by('name')
        
        # Create custom choices with employee details
        employee_choices = [('', '--- Sélectionner un employé ---')]
        for emp in available_employees:
            display_text = f"{emp.name}"
            if emp.role:
                display_text += f" - {emp.role}"
            if emp.email:
                display_text += f" ({emp.email})"
            employee_choices.append((emp.id, display_text))
        
        self.fields['employee'].choices = employee_choices
        
        # Add search capability
        self.fields['employee'].widget.attrs.update({
            'data-placeholder': 'Rechercher un employé...',
            'data-allow-clear': 'true'
        })
        
        # Ensure role field has proper choices
        self.fields['role'].choices = ProjectMember.ROLE_CHOICES
        
        for field_name, field in self.fields.items():
            if field_name != 'employee':
                field.widget.attrs['class'] = 'form-control'


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
        fields = ['title', 'description', 'direction', 'priority', 'status', 'created_by']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'


class PartnerForm(forms.ModelForm):
    """Formulaire pour les partenaires"""
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


class EventForm(forms.ModelForm):
    """Formulaire pour les événements"""
    class Meta:
        model = Event
        fields = ['title', 'event_type', 'description', 'date', 'time', 'duration', 'location', 'participants']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'time': forms.TimeInput(attrs={'type': 'time'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'participants': forms.CheckboxSelectMultiple(),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'participants':
                field.widget.attrs['class'] = 'form-control'


class BudgetForm(forms.ModelForm):
    """Formulaire pour les budgets"""
    currency = forms.ChoiceField(choices=CURRENCY_CHOICES, initial='GNF', label="Devise")
    
    class Meta:
        model = Budget
        fields = ['direction', 'allocated', 'consumed', 'currency']
        widgets = {
            'allocated': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'consumed': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
        self.fields['allocated'].label = 'Budget alloué'
        self.fields['consumed'].label = 'Budget consommé'
        self.fields['currency'].widget.attrs['class'] = 'form-control select-searchable'


class EmployeeForm(forms.ModelForm):
    """Formulaire pour les employés"""
    class Meta:
        model = Employee
        fields = ['name', 'direction', 'role', 'phone', 'email']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
        self.fields['name'].label = 'Nom complet'
        self.fields['phone'].label = 'Téléphone'
        self.fields['email'].label = 'Email'
