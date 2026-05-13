from django.db import migrations, models


def deduplicate_exact_station_gps(apps, schema_editor):
    Station = apps.get_model('gestion_transport', 'Station')
    LigneStation = apps.get_model('gestion_transport', 'LigneStation')

    duplicates = {}
    for station in Station.objects.exclude(latitude__isnull=True).exclude(longitude__isnull=True).order_by('id'):
        key = (station.latitude, station.longitude)
        duplicates.setdefault(key, []).append(station)

    for stations in duplicates.values():
        if len(stations) < 2:
            continue

        keeper = stations[0]
        for duplicate in stations[1:]:
            LigneStation.objects.filter(station_id=duplicate.id).update(station_id=keeper.id)
            duplicate.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_transport', '0020_reservationtrajet_ticket_code'),
    ]

    operations = [
        migrations.RunPython(deduplicate_exact_station_gps, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='station',
            constraint=models.UniqueConstraint(
                fields=('latitude', 'longitude'),
                condition=models.Q(latitude__isnull=False, longitude__isnull=False),
                name='uniq_station_exact_gps',
            ),
        ),
    ]