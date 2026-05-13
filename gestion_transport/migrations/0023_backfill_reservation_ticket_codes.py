import uuid

from django.db import migrations


def backfill_reservation_ticket_codes(apps, schema_editor):
    ReservationTrajet = apps.get_model('gestion_transport', 'ReservationTrajet')

    for reservation in ReservationTrajet.objects.filter(ticket_code__isnull=True):
        reservation.ticket_code = uuid.uuid4().hex
        reservation.save(update_fields=['ticket_code'])

    for reservation in ReservationTrajet.objects.filter(ticket_code=''):
        reservation.ticket_code = uuid.uuid4().hex
        reservation.save(update_fields=['ticket_code'])


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_transport', '0022_unique_student_line_subscription'),
    ]

    operations = [
        migrations.RunPython(backfill_reservation_ticket_codes, migrations.RunPython.noop),
    ]