from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_transport', '0004_horaire_sens'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='trajet',
            unique_together={('bus', 'ligne', 'horaire', 'date_trajet')},
        ),
    ]
