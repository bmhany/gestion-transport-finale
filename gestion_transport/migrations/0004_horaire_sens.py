from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_transport', '0003_alter_etudiant_student_number'),
    ]

    operations = [
        migrations.AddField(
            model_name='horaire',
            name='sens',
            field=models.CharField(
                choices=[('aller', 'Aller'), ('retour', 'Retour')],
                default='aller',
                max_length=10,
            ),
        ),
        migrations.AlterUniqueTogether(
            name='horaire',
            unique_together={('ligne', 'jour_semaine', 'sens', 'heure_depart')},
        ),
    ]