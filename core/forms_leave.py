"""Formulaires pour la gestion des demandes de conge CSIG."""
import json
from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import LeaveRequest, LeaveDocument, Employee, Direction


_DATE_INPUT = forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
_TEXTAREA = forms.Textarea(attrs={'rows': 3, 'class': 'form-control'})
_INPUT = forms.TextInput(attrs={'class': 'form-control'})
_SELECT = forms.Select(attrs={'class': 'form-control'})


class LeaveRequestForm(forms.ModelForm):
    """Formulaire de creation/modification d'une demande de conge."""

    extra_documents_json = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        label=_("Pièces justificatives (JSON)"),
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
                    if profile.employee_id:
                        self.fields['employee'].queryset = Employee.objects.filter(id=profile.employee_id)
                    if profile.direction_id:
                        self.fields['direction'].queryset = Direction.objects.filter(id=profile.direction_id)

                if not self.instance.pk:
                    if profile.employee_id and not self.initial.get('employee'):
                        self.initial['employee'] = profile.employee_id
                    if profile.direction_id and not self.initial.get('direction'):
                        self.initial['direction'] = profile.direction_id

    def save_extra_documents(self, leave):
        """Cree des LeaveDocument pour chaque URL Cloudinary uploadee."""
        raw = self.cleaned_data.get('extra_documents_json') or '[]'
        try:
            docs = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            docs = []
        for doc_data in docs:
            url = doc_data.get('url', '') if isinstance(doc_data, dict) else str(doc_data)
            label = doc_data.get('name', '') if isinstance(doc_data, dict) else ''
            if url:
                LeaveDocument.objects.create(leave_request=leave, file=url, label=label)

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_date')
        end = cleaned.get('end_date')
        leave_type = cleaned.get('leave_type')
        raw_json = cleaned.get('extra_documents_json') or '[]'
        try:
            new_files = json.loads(raw_json)
        except (json.JSONDecodeError, TypeError):
            new_files = []
        has_existing_docs = bool(self.instance.pk and self.instance.documents.exists())
        has_any_doc = bool(new_files) or has_existing_docs

        if start and end and end < start:
            self.add_error('end_date', _("La date de fin doit être postérieure ou égale à la date de début."))

        if start and leave_type == 'annuel':
            min_delay = (start - timezone.now().date()).days
            if min_delay < 15:
                self.add_error('start_date', _("Un congé annuel doit être demandé au moins 15 jours avant le départ."))

        types_requiring_doc = {'maladie', 'maternite', 'formation'}
        if leave_type in types_requiring_doc and not has_any_doc:
            self.add_error('extra_documents_json', _("Une pièce justificative est requise pour ce type de congé."))

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
            'file': forms.HiddenInput(),
            'label': _INPUT,
        }
