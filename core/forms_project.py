from django import forms
from .models import Project, Document, Request, Partner, Event, Direction, Budget, Employee, Milestone, ProjectFolder, ProjectDocument, ProjectMember, ProjectNeed, ProjectComment


class ProjectForm(forms.ModelForm):
    """Formulaire pour les projets"""
    class Meta:
        model = Project
        fields = ['name', 'description', 'direction', 'status', 'priority', 
                  'budget', 'budget_consumed', 'start_date', 'end_date', 'manager']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'


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
        fields = ['name', 'completed', 'order']
        widgets = {
            'order': forms.NumberInput(attrs={'min': 0, 'style': 'width: 100px;'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'


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
        fields = ['employee', 'role']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        # Filter employees to exclude those already in the project
        if self.instance and self.instance.pk:
            existing_members = project.members.exclude(pk=self.instance.pk)
        else:
            existing_members = project.members.all()
        
        employee_ids = existing_members.values_list('employee_id', flat=True)
        self.fields['employee'].queryset = Employee.objects.exclude(id__in=employee_ids).order_by('name')
        
        for field_name, field in self.fields.items():
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
    class Meta:
        model = Budget
        fields = ['direction', 'allocated', 'consumed']
        widgets = {
            'allocated': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'consumed': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
        self.fields['allocated'].label = 'Budget alloué (GNF)'
        self.fields['consumed'].label = 'Budget consommé (GNF)'


class EmployeeForm(forms.ModelForm):
    """Formulaire pour les employés"""
    class Meta:
        model = Employee
        fields = ['name', 'direction', 'role', 'workload', 'skills']
        widgets = {
            'workload': forms.NumberInput(attrs={'min': '0', 'max': '100'}),
            'skills': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Compétences séparées par des virgules'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
        self.fields['name'].label = 'Nom complet'
        self.fields['workload'].label = 'Charge de travail (%)'
        self.fields['skills'].label = 'Compétences'
