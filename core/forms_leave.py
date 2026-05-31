"""Formulaires pour la gestion des demandes de conge CSIG."""
from django import forms
from django.utils import timezone

from .models import LeaveRequest, LeaveDocument, Employee, Direction


_DATE_INPUT = forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
_TEXTAREA = forms.Textarea(attrs={'rows': 3, 'class': 'form-control'})
_INPUT = forms.TextInput(attrs={'class': 'form-control'})
_SELECT = forms.Select(attrs={'class': 'form-control'})
_FILE = forms.ClearableFileInput(attrs={'class': 'form-control'})


class _MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """Champ permettant l'upload de plusieurs fichiers en une seule fois."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', _MultipleFileInput(attrs={'class': 'form-control', 'multiple': True}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_clean(d, initial) for d in data if d]
        if data:
            return [single_clean(data, initial)]
        return []


class LeaveRequestForm(forms.ModelForm):
    """Formulaire de creation/modification d'une demande de conge."""

    extra_documents = MultipleFileField(
        required=False,
        label="Pièces justificatives supplémentaires",
        help_text="Vous pouvez sélectionner plusieurs fichiers à la fois (Ctrl/Cmd + clic).",
    )

    class Meta:
        model = LeaveRequest
        fields = [
            'employee', 'direction', 'leave_type',
            'start_date', 'end_date', 'reason',
            'replacement', 'handover_note', 'justification',
        ]
        widgets = {
            'employee': _SELECT,
            'direction': _SELECT,
            'leave_type': _SELECT,
            'start_date': _DATE_INPUT,
            'end_date': _DATE_INPUT,
            'reason': _TEXTAREA,
            'replacement': _INPUT,
            'handover_note': _TEXTAREA,
            'justification': _FILE,
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['employee'].queryset = Employee.objects.select_related('direction').order_by('name')
        self.fields['direction'].queryset = Direction.objects.order_by('name')
        self.fields['justification'].required = False
        self.fields['replacement'].required = False
        self.fields['handover_note'].required = False

        # Pre-remplir l'employe et la direction depuis le profil utilisateur si possible
        if user is not None and not self.instance.pk:
            profile = getattr(user, 'profile', None)
            if profile is not None:
                if profile.employee_id and not self.initial.get('employee'):
                    self.initial['employee'] = profile.employee_id
                if profile.direction_id and not self.initial.get('direction'):
                    self.initial['direction'] = profile.direction_id

    def save_extra_documents(self, leave):
        """Cree des LeaveDocument pour chaque fichier supplementaire uploade."""
        files = self.cleaned_data.get('extra_documents') or []
        for f in files:
            LeaveDocument.objects.create(leave_request=leave, file=f, label=f.name)

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_date')
        end = cleaned.get('end_date')
        leave_type = cleaned.get('leave_type')
        justification = cleaned.get('justification') or (self.instance.justification if self.instance.pk else None)

        if start and end and end < start:
            self.add_error('end_date', "La date de fin doit être postérieure ou égale à la date de début.")

        if start and leave_type == 'annuel':
            min_delay = (start - timezone.now().date()).days
            if min_delay < 15:
                self.add_error('start_date', "Un congé annuel doit être demandé au moins 15 jours avant le départ.")

        # Certains types exigent un justificatif
        types_requiring_doc = {'maladie', 'maternite', 'formation'}
        if leave_type in types_requiring_doc and not justification:
            self.add_error('justification', "Un justificatif est requis pour ce type de congé.")

        return cleaned


class LeaveManagerDecisionForm(forms.ModelForm):
    """Avis du superieur hierarchique (etape 1)."""

    class Meta:
        model = LeaveRequest
        fields = ['manager_decision', 'manager_comment']
        widgets = {
            'manager_decision': _SELECT,
            'manager_comment': _TEXTAREA,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['manager_decision'].choices = [
            ('favorable', 'Favorable'),
            ('defavorable', 'Défavorable'),
        ]
        self.fields['manager_decision'].required = True


class LeaveHRDecisionForm(forms.ModelForm):
    """Verification RH (etape 2)."""

    class Meta:
        model = LeaveRequest
        fields = ['hr_decision', 'hr_comment']
        widgets = {
            'hr_decision': _SELECT,
            'hr_comment': _TEXTAREA,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['hr_decision'].choices = [
            ('conforme', 'Conforme'),
            ('non_conforme', 'Non conforme'),
        ]
        self.fields['hr_decision'].required = True


class LeaveFinalDecisionForm(forms.ModelForm):
    """Decision finale Direction / Coordination (etape 3)."""

    class Meta:
        model = LeaveRequest
        fields = ['final_decision', 'final_comment']
        widgets = {
            'final_decision': _SELECT,
            'final_comment': _TEXTAREA,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['final_decision'].choices = [
            ('approuve', 'Approuvée'),
            ('rejete', 'Rejetée'),
        ]
        self.fields['final_decision'].required = True


class LeaveDocumentForm(forms.ModelForm):
    class Meta:
        model = LeaveDocument
        fields = ['file', 'label']
        widgets = {
            'file': _FILE,
            'label': _INPUT,
        }
