"""Backfill des slugs vides ou NULL (audit du 08/10, classe de bugs 2).

0001_initial crée les colonnes slug sans backfill : toute ligne héritée
d'une ancienne version ou chargée hors ORM (SQL/imports) peut avoir
slug = NULL ou ''. Chaque {% url %} sur un tel objet levait alors
NoReverseMatch → 500.

Les modèles historiques de migration n'ont ni __str__ ni
slug_source/_make_unique_slug (les méthodes custom ne sont pas portées par
ModelState) : la logique est donc réimplémentée ici, calquée sur
SluggableModel._make_unique_slug (slugify, base 'item', suffixe -2, -3…,
unicité, troncature à max_length du champ).
"""

from django.db import migrations
from django.utils.text import slugify

# (modèle, source du slug) — Direction utilise code ou name (slug_source
# surchargé dans models.py), tous les autres prennent name.
MODELS = [
    ('Direction', 'code_or_name'),
    ('Project', 'name'),
    ('Milestone', 'name'),
    ('SubMilestone', 'name'),
    ('ProjectNeed', 'name'),
    ('ProjectFolder', 'name'),
    ('ProjectDocument', 'name'),
    ('Document', 'name'),
    ('Partner', 'name'),
    ('Event', 'name'),
    ('Request', 'name'),
    ('Employee', 'name'),
    ('Role', 'name'),
    ('ProjectRole', 'name'),
]


def _unique_slug(model, base, exclude_pk):
    candidate = base
    n = 1
    qs = model.objects.all()
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    while qs.filter(slug=candidate).exists():
        n += 1
        candidate = f"{base}-{n}"
    return candidate


def backfill_empty_slugs(apps, schema_editor):
    for model_name, source_kind in MODELS:
        model = apps.get_model('core', model_name)
        max_len = model._meta.get_field('slug').max_length or 200
        for obj in model.objects.all():
            if obj.slug:
                continue
            if source_kind == 'code_or_name':
                source = obj.code or obj.name
            else:
                source = getattr(obj, 'name', None) or str(obj.pk)
            base = (slugify(str(source)) or 'item')[: max_len - 10]
            obj.slug = _unique_slug(model, base, obj.pk)
            obj.save(update_fields=['slug'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_budget_rate_date_budget_rate_snapshot_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_empty_slugs, migrations.RunPython.noop),
    ]
