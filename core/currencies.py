from django.utils.translation import gettext_lazy as _

CURRENCY_CHOICES = [
    ('GNF', _('GNF - Franc Guinéen')),
    ('USD', _('USD - Dollar Américain')),
]

# Repli quand aucun taux figé (rate_snapshot) n'est disponible sur l'enregistrement.
# La valeur courante est portée par core.exchange.DEFAULT_USD_GNF_RATE (appel API live).
FALLBACK_USD_GNF_RATE = 8788.75


def _normalize(currency):
    """Seules GNF et USD sont supportées ; toute autre valeur historique est traitée comme USD."""
    return currency if currency in ('GNF', 'USD') else 'USD'


def convert_currency(amount, from_currency, to_currency, rate=None):
    """Convertit un montant entre GNF et USD (dans les deux sens).

    rate : nombre de GNF pour 1 USD, figé à la saisie (rate_snapshot).
    Sans rate, utilise le taux de repli.
    """
    src = _normalize(from_currency)
    dst = _normalize(to_currency)
    if src == dst:
        return round(float(amount), 2)

    gnf_per_usd = float(rate) if rate else FALLBACK_USD_GNF_RATE
    amount_in_usd = float(amount) / gnf_per_usd if src == 'GNF' else float(amount)
    converted = amount_in_usd * gnf_per_usd if dst == 'GNF' else amount_in_usd
    return round(converted, 2)


def format_currency(amount, currency):
    """Formate un montant au format français : 8 655 000 GNF / 1 234,56 USD."""
    value = float(amount)
    if currency == 'GNF':
        return f"{int(round(value)):,}".replace(',', ' ') + ' GNF'
    whole, _, frac = f"{value:,.2f}".partition('.')
    return f"{whole.replace(',', ' ')},{frac} {currency}"


def convert_display(amount, from_currency, to_currency, rate=None):
    """Convertit puis formate : l'affichage de l'équivalent dans l'autre devise."""
    return format_currency(convert_currency(amount, from_currency, to_currency, rate=rate), to_currency)


def convert_sum(queryset, field, to_currency, currency_attr='currency', rate_attr='rate_snapshot'):
    """Somme d'un champ de queryset convertie dans to_currency, en appliquant le taux figé de chaque ligne."""
    total = 0.0
    for row in queryset:
        total += convert_currency(
            float(getattr(row, field) or 0),
            getattr(row, currency_attr) or 'GNF',
            to_currency,
            rate=getattr(row, rate_attr, None),
        )
    return total
