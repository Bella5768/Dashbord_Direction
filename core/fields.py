"""Champs et widgets réutilisables pour le projet."""
import phonenumbers
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_phone_number(value, default_region='GN'):
    """
    Valide et normalise un numéro de téléphone au format E.164.
    Retourne le numéro normalisé ou None si la valeur est vide.
    Lève ValidationError si le numéro est invalide.
    """
    if not value:
        return value

    number = value.strip()
    if not number:
        return number

    try:
        parsed = phonenumbers.parse(number, default_region)
    except phonenumbers.NumberParseException as exc:
        if exc._error_type == phonenumbers.NumberParseException.INVALID_COUNTRY_CODE:
            raise ValidationError(_("Le code pays du numéro est invalide ou non pris en charge."))
        raise ValidationError(_("Le numéro de téléphone n'est pas valide."))

    if not phonenumbers.is_valid_number(parsed):
        raise ValidationError(_("Le numéro de téléphone n'est pas valide."))

    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


class IntlTelInputWidget(forms.TextInput):
    """Widget qui affiche un sélecteur de téléphone international (drapeau + indicatif)."""

    def __init__(self, attrs=None, default_region='GN'):
        self.default_region = default_region
        super().__init__(attrs=attrs)

    def build_attrs(self, base_attrs, extra_attrs=None):
        attrs = super().build_attrs(base_attrs, extra_attrs)
        attrs['type'] = 'tel'
        attrs.setdefault('class', '')
        attrs['class'] += ' intl-tel-input'
        attrs['data-default-region'] = self.default_region
        return attrs


class IntlPhoneField(forms.CharField):
    """Champ téléphone international validé et normalisé au format E.164."""

    widget = IntlTelInputWidget
    default_region = 'GN'
    default_error_messages = {
        'invalid': _("Le numéro de téléphone n'est pas valide."),
        'invalid_country': _("Le code pays du numéro est invalide ou non pris en charge."),
    }

    def __init__(self, *args, default_region=None, **kwargs):
        if default_region is not None:
            self.default_region = default_region
        kwargs.setdefault('max_length', 32)
        super().__init__(*args, **kwargs)

    def widget_attrs(self, widget):
        attrs = super().widget_attrs(widget)
        attrs.setdefault('class', '')
        attrs['class'] += ' intl-tel-input'
        attrs['data-default-region'] = self.default_region
        return attrs

    def clean(self, value):
        value = super().clean(value)
        if value in self.empty_values:
            return value

        number = value.strip()

        # Si le numéro ne commence pas par +, on tente d'ajouter l'indicatif par défaut
        # ou on le parse tel quel (phonenumbers gère les numéros locaux avec la région).
        try:
            parsed = phonenumbers.parse(number, self.default_region)
        except phonenumbers.NumberParseException as exc:
            if exc._error_type == phonenumbers.NumberParseException.INVALID_COUNTRY_CODE:
                raise forms.ValidationError(
                    self.error_messages['invalid_country'],
                    code='invalid_country',
                )
            raise forms.ValidationError(
                self.error_messages['invalid'],
                code='invalid',
            )

        if not phonenumbers.is_valid_number(parsed):
            raise forms.ValidationError(
                self.error_messages['invalid'],
                code='invalid',
            )

        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
