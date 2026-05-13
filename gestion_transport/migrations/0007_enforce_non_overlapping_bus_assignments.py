from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("gestion_transport", "0006_reservationhoraire"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
CREATE TRIGGER IF NOT EXISTS gestion_transport_affectation_bus_no_overlap_insert
BEFORE INSERT ON gestion_transport_affectationbusligne
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'Un bus ne peut etre affecte qu a une seule ligne dans une periode donnee.')
    WHERE EXISTS (
        SELECT 1
        FROM gestion_transport_affectationbusligne AS a
        WHERE a.bus_id = NEW.bus_id
          AND COALESCE(a.date_fin, '9999-12-31') >= NEW.date_debut
          AND COALESCE(NEW.date_fin, '9999-12-31') >= a.date_debut
    );
END;
""",
            reverse_sql="""
DROP TRIGGER IF EXISTS gestion_transport_affectation_bus_no_overlap_insert;
""",
        ),
        migrations.RunSQL(
            sql="""
CREATE TRIGGER IF NOT EXISTS gestion_transport_affectation_bus_no_overlap_update
BEFORE UPDATE ON gestion_transport_affectationbusligne
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'Un bus ne peut etre affecte qu a une seule ligne dans une periode donnee.')
    WHERE EXISTS (
        SELECT 1
        FROM gestion_transport_affectationbusligne AS a
        WHERE a.bus_id = NEW.bus_id
          AND a.id != NEW.id
          AND COALESCE(a.date_fin, '9999-12-31') >= NEW.date_debut
          AND COALESCE(NEW.date_fin, '9999-12-31') >= a.date_debut
    );
END;
""",
            reverse_sql="""
DROP TRIGGER IF EXISTS gestion_transport_affectation_bus_no_overlap_update;
""",
        ),
    ]
