from django.db import migrations, models
from django.db.models.functions import Lower


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_transport', '0016_add_sample_stations'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='ligne',
            constraint=models.UniqueConstraint(
                Lower('nom_ligne'),
                name='uniq_ligne_nom_ligne_ci',
            ),
        ),
    ]
