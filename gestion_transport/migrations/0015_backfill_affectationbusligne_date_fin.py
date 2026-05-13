from datetime import date

from django.db import migrations


def _add_one_year(start_date):
    try:
        return start_date.replace(year=start_date.year + 1)
    except ValueError:
        # Cas du 29 fevrier -> 28 fevrier l'annee suivante.
        return start_date.replace(year=start_date.year + 1, day=28)


def forwards(apps, schema_editor):
    AffectationBusLigne = apps.get_model('gestion_transport', 'AffectationBusLigne')

    qs = AffectationBusLigne.objects.filter(date_fin__isnull=True)
    for aff in qs.iterator():
        if aff.date_debut:
            aff.date_fin = _add_one_year(aff.date_debut)
            aff.save(update_fields=['date_fin'])


def backwards(apps, schema_editor):
    # Migration de donnees non reversible de maniere fiable.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_transport', '0014_suivitrajetconducteur'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
