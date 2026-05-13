from datetime import date, timedelta
from threading import local

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import AffectationBusLigne, Horaire, Trajet, ReservationHoraire, Bus, Ligne, ModificationHistorique


_history_context = local()


def set_history_user(username):
    _history_context.username = username or ''


def clear_history_user():
    if hasattr(_history_context, 'username'):
        del _history_context.username


WEEKDAY_TO_JOUR = {
    0: 'lundi',
    1: 'mardi',
    2: 'mercredi',
    3: 'jeudi',
    4: 'vendredi',
    5: 'samedi',
    6: 'dimanche',
}
ROLLING_DAYS = 30


def _date_window_for_affectation(affectation):
    start = max(affectation.date_debut, date.today())
    # Pour une affectation future sans date_fin, générer une fenêtre glissante
    # à partir du début effectif de l'affectation (et non depuis aujourd'hui).
    end = affectation.date_fin or (start + timedelta(days=ROLLING_DAYS))

    if end < start:
        return None, None
    return start, end


def _iter_dates_for_jour(start, end, jour_semaine):
    current = start
    while current <= end:
        if WEEKDAY_TO_JOUR[current.weekday()] == jour_semaine:
            yield current
        current += timedelta(days=1)


def _get_available_buses_for_line_date(ligne, target_date):
    """Retourne les bus affectes a la ligne et actifs a la date donnee."""
    return list(
        Bus.objects.filter(
            affectationbusligne__ligne=ligne,
            affectationbusligne__date_debut__lte=target_date,
        ).filter(
            affectationbusligne__date_fin__isnull=True,
        )
        .union(
            Bus.objects.filter(
                affectationbusligne__ligne=ligne,
                affectationbusligne__date_debut__lte=target_date,
                affectationbusligne__date_fin__gte=target_date,
            )
        )
        .order_by('id')
    )


def _pick_equitable_buses(available_buses, buses_needed, target_date, horaire_id):
    """Selectionne les bus en rotation stable pour equilibrer la charge."""
    if not available_buses:
        return []

    buses_needed = max(1, min(buses_needed, len(available_buses)))
    start_index = (target_date.toordinal() + horaire_id) % len(available_buses)
    rotated = available_buses[start_index:] + available_buses[:start_index]
    return rotated[:buses_needed]


def _count_reservations_for_horaire(horaire):
    """
    Compte le nombre de réservations pour un horaire donné.
    Retourne le nombre d'étudiants qui ont réservé cet horaire.
    """
    return ReservationHoraire.objects.filter(horaire=horaire).count()


def _calculate_buses_needed_for_horaire(horaire):
    """
    Calcule combien de buses sont nécessaires pour un horaire donné,
    basé sur le nombre de réservations réelles.
    
    Logique :
    - Compte les réservations pour cet horaire
    - Divise par la capacité maximale des buses disponibles → nombre de buses
    - Retourne au minimum 1 (pour les horaires sans réservation)
    """
    try:
        reservation_count = _count_reservations_for_horaire(horaire)
        if reservation_count == 0:
            return 1  # Au moins 1 bus par défaut même sans réservation
        
        # Obtenir la capacité maximale des buses disponibles pour cette ligne
        available_buses = Bus.objects.filter(
            affectationbusligne__ligne=horaire.ligne
        ).distinct()
        
        if not available_buses.exists():
            return 1  # Pas de bus disponible
        
        max_capacity = max([b.capacite for b in available_buses])
        
        # Nombre de buses = réservations / capacité (arrondi sup)
        buses_needed = (reservation_count + max_capacity - 1) // max_capacity
        return max(1, buses_needed)
    except Exception:
        return 1  # Défaut à 1 bus en cas d'erreur


def _generate_trajets_for_affectation(affectation):
    """
    Génère les trajets pour une affectation bus-ligne donnée.
    Alloue automatiquement les buses en fonction des réservations par horaire.
    """
    start, end = _date_window_for_affectation(affectation)
    if not start:
        return 0

    created_count = 0
    horaires = Horaire.objects.filter(ligne=affectation.ligne)
    
    for horaire in horaires:
        # Calculer le nombre de buses nécessaires pour cet horaire
        buses_needed = _calculate_buses_needed_for_horaire(horaire)

        for d in _iter_dates_for_jour(start, end, horaire.jour_semaine):
            available_buses = _get_available_buses_for_line_date(affectation.ligne, d)
            if not available_buses:
                available_buses = [affectation.bus]

            buses_for_horaire = _pick_equitable_buses(
                available_buses,
                buses_needed,
                d,
                horaire.id,
            )

            # Créer un trajet pour chaque bus assigné à cet horaire
            for bus in buses_for_horaire:
                _, created = Trajet.objects.get_or_create(
                    bus=bus,
                    ligne=affectation.ligne,
                    horaire=horaire,
                    date_trajet=d,
                    defaults={'retard_minutes': 0},
                )
                if created:
                    created_count += 1

    return created_count


def _cleanup_orphan_future_trajets_for_bus_ligne(bus, ligne):
    """
    Supprime les trajets futurs d'un bus/ligne qui ne sont couverts
    par aucune affectation (reliquats apres modification de periode).
    """
    today = date.today()
    deleted = 0

    trajets = Trajet.objects.filter(
        bus=bus,
        ligne=ligne,
        date_trajet__gte=today,
    ).only('id', 'date_trajet')

    for trajet in trajets:
        covered = AffectationBusLigne.objects.filter(
            bus=bus,
            ligne=ligne,
            date_debut__lte=trajet.date_trajet,
        ).filter(
            date_fin__isnull=True,
        ).exists() or AffectationBusLigne.objects.filter(
            bus=bus,
            ligne=ligne,
            date_debut__lte=trajet.date_trajet,
            date_fin__gte=trajet.date_trajet,
        ).exists()

        if not covered:
            trajet.delete()
            deleted += 1

    return deleted


def _generate_trajets_for_horaire(horaire):
    """
    Génère les trajets pour un horaire donné.
    Appelé quand un nouvel horaire est créé ou modifié.
    """
    today = date.today()
    horizon = today + timedelta(days=ROLLING_DAYS)

    affectations = AffectationBusLigne.objects.filter(ligne=horaire.ligne).filter(
        date_debut__lte=horizon
    )

    # Calculer le nombre de buses nécessaires pour cet horaire
    buses_needed = _calculate_buses_needed_for_horaire(horaire)

    for affectation in affectations:
        start, end = _date_window_for_affectation(affectation)
        if not start:
            continue

        for d in _iter_dates_for_jour(start, end, horaire.jour_semaine):
            available_buses = _get_available_buses_for_line_date(horaire.ligne, d)
            if not available_buses:
                available_buses = [affectation.bus]

            buses_for_horaire = _pick_equitable_buses(
                available_buses,
                buses_needed,
                d,
                horaire.id,
            )

            # Créer un trajet pour chaque bus assigné à cet horaire
            for bus in buses_for_horaire:
                Trajet.objects.get_or_create(
                    bus=bus,
                    ligne=horaire.ligne,
                    horaire=horaire,
                    date_trajet=d,
                    defaults={'retard_minutes': 0},
                )


def sync_all_future_trajets():
    """Regénère les trajets futurs à partir des affectations et horaires."""
    # Nettoyer d'abord les trajets futurs pour éviter les reliquats incohérents
    # (bus sur une ligne hors période d'affectation après changements historiques).
    Trajet.objects.filter(date_trajet__gte=date.today()).delete()

    created_total = 0
    for affectation in AffectationBusLigne.objects.all():
        created_total += _generate_trajets_for_affectation(affectation)
    return created_total


@receiver(post_save, sender=AffectationBusLigne)
def create_trajets_on_affectation_save(sender, instance, **kwargs):
    _cleanup_orphan_future_trajets_for_bus_ligne(instance.bus, instance.ligne)
    _generate_trajets_for_affectation(instance)


@receiver(post_save, sender=Horaire)
def create_trajets_on_horaire_save(sender, instance, **kwargs):
    _generate_trajets_for_horaire(instance)


@receiver(post_delete, sender=AffectationBusLigne)
def delete_future_trajets_on_affectation_delete(sender, instance, **kwargs):
    start, end = _date_window_for_affectation(instance)
    if not start:
        return

    Trajet.objects.filter(
        bus=instance.bus,
        ligne=instance.ligne,
        date_trajet__range=(start, end),
    ).delete()


@receiver(post_delete, sender=Horaire)
def delete_future_trajets_on_horaire_delete(sender, instance, **kwargs):
    Trajet.objects.filter(horaire=instance, date_trajet__gte=date.today()).delete()


@receiver(post_save, sender=Ligne)
def create_history_on_ligne_create(sender, instance, created, **kwargs):
    if not created:
        return

    username = getattr(_history_context, 'username', '')
    ModificationHistorique.objects.create(
        action='ajout',
        objet_type='Ligne',
        description=f"Ligne {instance.nom_ligne} ajoutée avec ses horaires.",
        utilisateur=username,
    )
