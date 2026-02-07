from django import template

register = template.Library()


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
