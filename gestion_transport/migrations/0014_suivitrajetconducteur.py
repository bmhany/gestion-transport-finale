from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_transport', '0013_affectationbusligne_conducteur'),
    ]

    operations = [
        migrations.CreateModel(
            name='SuiviTrajetConducteur',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('statut', models.CharField(choices=[('planifie', 'Planifie'), ('depart', 'Depart'), ('arrivee', 'Arrivee')], default='planifie', max_length=20)),
                ('depart_effectif', models.DateTimeField(blank=True, null=True)),
                ('arrivee_effective', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('conducteur', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='suivis_trajets', to='gestion_transport.conducteur')),
                ('trajet', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='suivi_conducteur', to='gestion_transport.trajet')),
            ],
            options={
                'verbose_name': 'Suivi Trajet Conducteur',
                'verbose_name_plural': 'Suivis Trajets Conducteurs',
                'ordering': ['-updated_at'],
            },
        ),
    ]
