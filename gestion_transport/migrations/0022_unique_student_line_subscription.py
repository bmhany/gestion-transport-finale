from django.db import migrations, models


def deduplicate_student_line_subscriptions(apps, schema_editor):
    AffectationEtudiantLigne = apps.get_model('gestion_transport', 'AffectationEtudiantLigne')

    duplicates = {}
    for affectation in AffectationEtudiantLigne.objects.order_by('date_debut', 'id'):
        key = (affectation.etudiant_id, affectation.ligne_id)
        duplicates.setdefault(key, []).append(affectation)

    for affectations in duplicates.values():
        if len(affectations) < 2:
            continue

        keeper = affectations[0]
        for duplicate in affectations[1:]:
            duplicate.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_transport', '0021_station_exact_gps_unique'),
    ]

    operations = [
        migrations.RunPython(deduplicate_student_line_subscriptions, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='affectationetudiantligne',
            constraint=models.UniqueConstraint(
                fields=('etudiant', 'ligne'),
                name='uniq_etudiant_ligne_subscription',
            ),
        ),
    ]