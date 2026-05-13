from django.db import migrations


def create_sample_stations(apps, schema_editor):
    Station = apps.get_model('gestion_transport', 'Station')
    Ligne = apps.get_model('gestion_transport', 'Ligne')
    LigneStation = apps.get_model('gestion_transport', 'LigneStation')

    station_definitions = {
        'Cité': (36.7600, 3.0490),
        'Fac': (36.7540, 3.0560),
        'Tramway': (36.7530, 3.0650),
        'Résidences': (36.7280, 3.0540),
        'Centre Ville': (36.7730, 3.0620),
        'Campus Sud': (36.7430, 3.0550),
        'Bibliothèque': (36.7480, 3.0570),
        'Restaurant U': (36.7485, 3.0585),
        'USTHB': (36.7180, 3.1760),
        'Kouba': (36.7575, 3.0542),
        'Ban Aknoune': (36.7376, 3.2840),
    }

    station_objects = {}
    for nom, (latitude, longitude) in station_definitions.items():
        station, created = Station.objects.get_or_create(
            nom_station=nom,
            defaults={
                'adresse': '',
                'latitude': latitude,
                'longitude': longitude,
            }
        )
        if not created:
            station.latitude = station.latitude or latitude
            station.longitude = station.longitude or longitude
            station.save()
        station_objects[nom] = station

    ligne_routes = {
        'Ligne 1 - Cité ↔ Fac': ['Cité', 'Fac'],
        'Ligne 2 - Tramway ↔ Résidences': ['Tramway', 'Résidences'],
        'Ligne 3 - Centre Ville ↔ Campus Sud': ['Centre Ville', 'Campus Sud'],
        'Ligne 4 - Bibliothèque ↔ Restaurant U': ['Bibliothèque', 'Restaurant U'],
        'usthb-kouba': ['USTHB', 'Kouba'],
        'Ligne Test Modal Auto': ['Cité', 'Fac'],
        'Ligne Test Auto History Signal': ['Tramway', 'Résidences'],
        'Ban Aknoune USTHB': ['Ban Aknoune', 'USTHB'],
    }

    for ligne_nom, stations in ligne_routes.items():
        try:
            ligne = Ligne.objects.get(nom_ligne=ligne_nom)
        except Ligne.DoesNotExist:
            continue

        for ordre, station_name in enumerate(stations, start=1):
            station = station_objects.get(station_name)
            if not station:
                continue
            LigneStation.objects.update_or_create(
                ligne=ligne,
                station=station,
                defaults={'ordre': ordre},
            )


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_transport', '0015_backfill_affectationbusligne_date_fin'),
    ]

    operations = [
        migrations.RunPython(create_sample_stations),
    ]
