"""Formulaires pour la gestion des demandes de conge CSIG."""
from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import LeaveRequest, LeaveDocument, Employee, Direction
from .validators import validate_safe_file


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
            files = [single_clean(d, initial) for d in data if d]
        elif data:
            files = [single_clean(data, initial)]
        else:
            files = []
        for f in files:
            validate_safe_file(f)
        return files


class LeaveRequestForm(forms.ModelForm):
    """Formulaire de creation/modification d'une demande de conge."""

    extra_documents = MultipleFileField(
        required=False,
        label=_("Pièces justificatives"),
        help_text=_("Vous pouvez sélectionner plusieurs fichiers à la fois (Ctrl/Cmd + clic) ou les glisser-déposer."),
    )

    class Meta:
        model = LeaveRequest
        fields = [
            'employee', 'direction', 'leave_type',
            'start_date', 'end_date', 'reason',
            'replacement', 'handover_note',
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
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['employee'].queryset = Employee.objects.select_related('direction').order_by('name')
        self.fields['direction'].queryset = Direction.objects.order_by('name')
        self.fields['replacement'].required = False
        self.fields['handover_note'].required = False

        if user is not None:
            profile = getattr(user, 'profile', None)
            if profile is not None:
                is_privileged = profile.is_admin() or profile.is_directeur_general() or profile.is_hr()
                if not is_privileged:
                    # Restreindre à l'employé et la direction de l'utilisateur
                    if profile.employee_id:
                        self.fields['employee'].queryset = Employee.objects.filter(id=profile.employee_id)
                    if profile.direction_id:
                        self.fields['direction'].queryset = Direction.objects.filter(id=profile.direction_id)

                # Pré-remplir depuis le profil si nouvelle demande
                if not self.instance.pk:
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
        new_files = cleaned.get('extra_documents') or []
        has_existing_docs = bool(self.instance.pk and self.instance.documents.exists())
        has_any_doc = bool(new_files) or has_existing_docs

        if start and end and end < start:
            self.add_error('end_date', _("La date de fin doit être postérieure ou égale à la date de début."))

        if start and leave_type == 'annuel':
            min_delay = (start - timezone.now().date()).days
            if min_delay < 15:
                self.add_error('start_date', _("Un congé annuel doit être demandé au moins 15 jours avant le départ."))

        # Certains types exigent au moins une piece justificative
        types_requiring_doc = {'maladie', 'maternite', 'formation'}
        if leave_type in types_requiring_doc and not has_any_doc:
            self.add_error('extra_documents', _("Une pièce justificative est requise pour ce type de congé."))

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
            ('favorable', _('Favorable')),
            ('defavorable', _('Défavorable')),
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
            ('conforme', _('Conforme')),
            ('non_conforme', _('Non conforme')),
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
            ('approuve', _('Approuvée')),
            ('rejete', _('Rejetée')),
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
