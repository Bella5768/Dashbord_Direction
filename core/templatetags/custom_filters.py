from django import template
from datetime import date
from django.utils.dates import MONTHS

register = template.Library()


@register.filter
def month_label(month):
    """Nom de mois localisé (via la traduction Django, ex: 'octobre', 'October')."""
    try:
        return str(MONTHS[int(month)])
    except (ValueError, TypeError, KeyError):
        return month


@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary using a key."""
    if dictionary is None:
        return []
    return dictionary.get(key, [])


@register.filter
def number_format(value):
    """Formate un nombre avec des séparateurs d'espaces (ex: 2 351 902)"""
    try:
        value = int(float(value))
        return '{:,}'.format(value).replace(',', ' ')
    except (ValueError, TypeError):
        return value


@register.filter
def currency_fmt(value, currency='GNF'):
    """Formate un montant selon la devise : 8 655 000 GNF / 1 234,56 USD"""
    from ..currencies import format_currency
    try:
        return format_currency(float(value), currency)
    except (ValueError, TypeError):
        return value


@register.filter
def split(value, separator=','):
    """Split a string by separator."""
    return value.split(separator)


@register.filter
def is_user_employee(assigned_to_m2m, user_employee):
    """Retourne True si user_employee est parmi les assignés (M2M manager)."""
    if not user_employee:
        return False
    try:
        return assigned_to_m2m.filter(pk=user_employee.pk).exists()
    except Exception:
        return False


@register.filter
def is_overdue(due_date):
    """Retourne True si la date est dépassée (strictement avant aujourd'hui)."""
    if not due_date:
        return False
    try:
        return due_date < date.today()
    except (TypeError, AttributeError):
        return False


@register.filter
def completed_count(queryset):
    """Compte le nombre d'éléments avec completed=True dans un queryset/itérable."""
    try:
        return sum(1 for item in queryset if item.completed)
    except (TypeError, AttributeError):
        return 0


@register.filter
def sub_milestone_stats(milestone):
    """Retourne un dict {total, done} des sous-étapes d'un jalon (une seule itération)."""
    total = 0
    done = 0
    try:
        for sub in milestone.sub_milestones.all():
            total += 1
            if sub.completed:
                done += 1
    except (AttributeError, TypeError):
        pass
    return {'total': total, 'done': done}


@register.filter
def get_stat(stats_dict, employee_id):
    """Récupère les stats d'un employé depuis member_task_stats (clé = int pk)."""
    if not stats_dict:
        return None
    return stats_dict.get(int(employee_id)) if employee_id else None
