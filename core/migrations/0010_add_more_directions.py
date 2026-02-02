from django.db import migrations


def add_more_directions(apps, schema_editor):
    Direction = apps.get_model('core', 'Direction')

    directions = [
        {'code': 'APPTECH', 'name': "Direction d'appui technique"},
        {'code': 'DG', 'name': 'Direction Générale'},
        {'code': 'SEC', 'name': 'Secrétariat'},
        {'code': 'SANTE', 'name': 'Direction Santé'},
        {'code': 'INNOV', 'name': 'Comité Innovation'},
        {'code': 'STRAT', 'name': 'Comité Stratégique'},
        {'code': 'LABO', 'name': 'Comité laboratoire'},
        {'code': 'FIN', 'name': 'Comité Finances'},
        {'code': 'NUMCLD', 'name': "Centre d'expertise_Numerique/cloud"},
        {'code': 'COPIL', 'name': 'Comité COPIL'},
        {'code': 'INFRA', 'name': 'Comité Infrastructures'},
        {'code': 'STAFF', 'name': 'Comité Staff'},
    ]

    for item in directions:
        Direction.objects.get_or_create(
            code=item['code'],
            defaults={'name': item['name']},
        )


def remove_more_directions(apps, schema_editor):
    Direction = apps.get_model('core', 'Direction')
    codes = ['APPTECH', 'DG', 'SEC', 'SANTE', 'INNOV', 'STRAT', 'LABO', 'FIN', 'NUMCLD', 'COPIL', 'INFRA', 'STAFF']
    Direction.objects.filter(code__in=codes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_userprofile_budget_permissions'),
    ]

    operations = [
        migrations.RunPython(add_more_directions, remove_more_directions),
    ]
