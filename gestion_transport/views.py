from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q, F, Case, When, Value, CharField, Prefetch, Avg, Sum
from django.db.models.functions import Concat
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.views.decorators.cache import never_cache
from .forms import (
    EtudiantRegistrationForm,
    EtudiantEditForm,
    ConducteurEditForm,
    BusForm,
    LigneForm,
    HoraireForm,
    HorairePairForm,
    HoraireFormSet,
    StationForm,
    BulkAffectationBusLigneForm,
    AffectationBusLigneForm,
    BusWithAffectationsForm,
    TrajetEditForm,
    ConducteurRegistrationForm,
    LigneStationFormSet,
)
from .models import (
    Etudiant, Bus, Ligne, Station, Horaire,
    AffectationEtudiantLigne, AffectationBusLigne,
    LigneStation, Trajet, Incident, ReservationHoraire, ReservationTrajet,
    ModificationHistorique, Conducteur, SuiviTrajetConducteur, RetardTrajet, AvisTrajet,
)
from .signals import sync_all_future_trajets, set_history_user, clear_history_user
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from django import forms
from datetime import date, datetime, timedelta
import calendar
import json
import csv
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from math import ceil, radians, sin, cos, asin, sqrt


def _log_modification(request, action, objet_type, description):
    """Enregistre un événement d'historique pour affichage dans le dashboard."""
    username = ''
    if request and hasattr(request, 'user') and request.user and request.user.is_authenticated:
        username = request.user.get_username()
    elif request and hasattr(request, 'session'):
        driver_id = request.session.get('driver_id')
        if driver_id:
            try:
                conducteur = Conducteur.objects.get(driver_id=driver_id)
                username = f"{conducteur.driver_id} ({conducteur.prenom} {conducteur.nom})"
            except Conducteur.DoesNotExist:
                username = str(driver_id)

    ModificationHistorique.objects.create(
        action=action,
        objet_type=objet_type,
        description=description,
        utilisateur=username,
    )


def _format_period_end_label(end_date):
    return end_date.strftime('%d/%m/%Y') if end_date else 'en cours'


def _format_period_label(start_date, end_date):
    if end_date:
        return f"du {start_date.strftime('%d/%m/%Y')} au {end_date.strftime('%d/%m/%Y')}"
    return f"à partir du {start_date.strftime('%d/%m/%Y')} (en cours)"


def _add_one_year(start_date):
    """Retourne la même date l'année suivante (avec repli pour le 29/02)."""
    try:
        return start_date.replace(year=start_date.year + 1)
    except ValueError:
        # Cas du 29 février -> 28 février l'année suivante.
        return start_date.replace(year=start_date.year + 1, day=28)


def _effective_period_end(start_date, end_date):
    if end_date:
        return end_date
    if start_date:
        return _add_one_year(start_date)
    return _add_one_year(date.today())


def _auto_set_assignment_end_date(affectation):
    """Applique la règle métier: si date_fin est vide, fixer à date_debut + 1 an."""
    if affectation.date_fin:
        return False
    affectation.date_fin = _effective_period_end(affectation.date_debut, None)
    return True


def _validate_conductor_not_already_assigned(bus, conducteur):
    """
    Vérifie qu'un conducteur n'est pas déjà assigné à un autre bus pour les mêmes périodes.
    Retourne None si valide, sinon retourne un message d'erreur.
    """
    if not conducteur:
        return None
    
    # Récupérer les affectations du bus courant
    affectations = AffectationBusLigne.objects.filter(bus=bus)
    
    if not affectations.exists():
        return None
    
    # Vérifier que le conducteur n'est pas assigné à un autre bus pour les mêmes périodes
    for affectation in affectations:
        period_start = affectation.date_debut
        period_end = _effective_period_end(affectation.date_debut, affectation.date_fin)

        conflicting_affectation = AffectationBusLigne.objects.filter(
            conducteur=conducteur,
            date_debut__lte=period_end,
        ).filter(
            Q(date_fin__isnull=True) | Q(date_fin__gte=period_start)
        ).exclude(
            bus=bus
        ).select_related('bus').first()

        if conflicting_affectation:
            conflict_period = _format_period_label(
                conflicting_affectation.date_debut,
                conflicting_affectation.date_fin,
            )
            return (
                f"Le conducteur {conducteur.prenom} {conducteur.nom} est déjà assigné au bus "
                f"{conflicting_affectation.bus.numero_immatriculation} pour la période {conflict_period}. "
                f"Un conducteur ne peut pas conduire deux bus en même temps."
            )
    
    return None


def _parse_calendar_reference_date(date_str):
    """Retourne la date de reference du calendrier a partir de YYYY-MM ou YYYY-MM-DD."""
    if not date_str:
        return date.today()

    try:
        if len(date_str) == 7:
            return date.fromisoformat(f"{date_str}-01")
        return date.fromisoformat(date_str)
    except ValueError:
        return date.today()


def _extract_direction_labels(ligne):
    """Construit des libellés métier pour les deux sens à partir du nom de la ligne."""
    default_aller = "Point A -> Point B"
    default_retour = "Point B -> Point A"

    if not ligne or not ligne.nom_ligne:
        return default_aller, default_retour

    nom = ligne.nom_ligne.strip()
    if '↔' not in nom:
        return default_aller, default_retour

    gauche, droite = nom.split('↔', 1)
    gauche = gauche.strip()
    droite = droite.strip()

    # Si le nom contient un préfixe du type "Ligne X - ...", on garde la partie métier.
    if ' - ' in gauche:
        gauche = gauche.split(' - ', 1)[1].strip()

    if not gauche or not droite:
        return default_aller, default_retour

    return f"{gauche} -> {droite}", f"{droite} -> {gauche}"


def _build_ligne_name_from_stations(ligne):
    """Construit 'Depart ↔ Arrivee' à partir des stations d'une ligne."""
    if not ligne:
        return ''

    stations = list(
        LigneStation.objects.filter(ligne=ligne)
        .select_related('station')
        .order_by('ordre', 'id')
    )

    if len(stations) < 2:
        return ''

    depart = stations[0].station.nom_station.strip() if stations[0].station else ''
    arrivee = stations[-1].station.nom_station.strip() if stations[-1].station else ''

    if not depart or not arrivee:
        return ''

    return f"{depart} ↔ {arrivee}"


def _build_ligne_name_from_station_formset(ligne_station_formset):
    """Construit 'Depart ↔ Arrivee' depuis les données POST du formset stations."""
    if not ligne_station_formset:
        return ''

    pairs = []
    for form in ligne_station_formset.forms:
        if not hasattr(form, 'cleaned_data'):
            continue
        cleaned = form.cleaned_data
        if not cleaned or cleaned.get('DELETE'):
            continue

        station = cleaned.get('station')
        ordre = cleaned.get('ordre')
        if not station or ordre in (None, ''):
            continue

        try:
            ordre_num = int(ordre)
        except (TypeError, ValueError):
            continue

        station_name = (station.nom_station or '').strip()
        if station_name:
            pairs.append((ordre_num, station_name))

    if len(pairs) < 2:
        return ''

    pairs.sort(key=lambda item: item[0])
    return f"{pairs[0][1]} ↔ {pairs[-1][1]}"


def _haversine_km(lat1, lon1, lat2, lon2):
    """Distance grand cercle en km entre deux points GPS."""
    lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return 6371.0 * c


def _calculate_route_km_osrm(points):
    """Calcule la distance d'itineraire reel (km) via OSRM pour une suite de points (lat, lon)."""
    if not points or len(points) < 2:
        return None

    coordinates = ';'.join(f"{lon:.6f},{lat:.6f}" for lat, lon in points)
    url = (
        f"https://router.project-osrm.org/route/v1/driving/{coordinates}"
        "?overview=false&alternatives=false&steps=false"
    )

    try:
        req = Request(url, headers={'User-Agent': 'TransportUniversitaire/1.0'})
        with urlopen(req, timeout=12) as response:
            payload = json.loads(response.read().decode('utf-8'))

        if payload.get('code') != 'Ok':
            return None

        routes = payload.get('routes') or []
        if not routes:
            return None

        distance_m = routes[0].get('distance')
        if distance_m is None:
            return None

        distance_km = float(distance_m) / 1000.0
        return distance_km if distance_km > 0 else None
    except (ValueError, KeyError, TypeError, URLError, HTTPError, TimeoutError):
        return None


def _calculate_ligne_distance_km_from_stations(ligne):
    """
    Calcule la distance de la ligne (km) selon l'ordre des stations et l'itineraire reel.
    Priorite:
    - calcul route OSRM (distance routiere reelle),
    - fallback Haversine (vol d'oiseau) si l'API route est indisponible.
    Protections:
    - ignore les stations GPS manquantes,
    - supprime les doublons de stations,
    - limite le fallback Haversine si la somme des segments depasse trop la distance directe.
    Retourne un entier (arrondi classique) ou None si calcul impossible.
    """
    if not ligne:
        return None

    points = []
    stations_ligne = (
        LigneStation.objects
        .filter(ligne=ligne)
        .select_related('station')
        .order_by('ordre', 'id')
    )

    seen_station_ids = set()
    for ls in stations_ligne:
        st = ls.station
        if not st or st.latitude is None or st.longitude is None:
            continue

        # Évite les boucles artificielles dues aux doublons de même station.
        if st.id in seen_station_ids:
            continue
        seen_station_ids.add(st.id)

        point = (float(st.latitude), float(st.longitude))
        # Ignore les points consécutifs identiques.
        if points and points[-1] == point:
            continue
        points.append(point)

    if len(points) < 2:
        return None

    route_km = _calculate_route_km_osrm(points)
    if route_km is not None:
        return max(1, int(round(route_km)))

    total_km = 0.0
    for idx in range(len(points) - 1):
        lat1, lon1 = points[idx]
        lat2, lon2 = points[idx + 1]
        segment_km = _haversine_km(lat1, lon1, lat2, lon2)
        # Filtre les micro-segments (bruit GPS).
        if segment_km < 0.02:
            continue
        total_km += segment_km

    if total_km <= 0:
        return None

    # Distance directe extrémité à extrémité (garde-fou anti-surestimation).
    direct_km = _haversine_km(points[0][0], points[0][1], points[-1][0], points[-1][1])
    if direct_km > 0:
        max_reasonable_km = direct_km * 1.35
        total_km = min(total_km, max_reasonable_km)

    return max(1, int(round(total_km)))


def _sync_ligne_distance_km(ligne):
    """Met à jour `distance_km` depuis les stations ordonnées si possible."""
    distance_km = _calculate_ligne_distance_km_from_stations(ligne)
    if distance_km is None:
        return False

    if ligne.distance_km != distance_km:
        ligne.distance_km = distance_km
        ligne.save(update_fields=['distance_km'])
        return True

    return False


def _has_required_sens_for_creation(horaire_formset):
    """Vérifie qu'au moins un horaire aller et un horaire retour sont saisis."""
    sens_set = set()

    for form in horaire_formset.forms:
        if not hasattr(form, 'cleaned_data'):
            continue
        cleaned = form.cleaned_data
        if not cleaned:
            continue
        if cleaned.get('DELETE'):
            continue
        sens = cleaned.get('sens')
        if sens:
            sens_set.add(sens)

    return 'aller' in sens_set and 'retour' in sens_set


def _is_form_marked_for_delete(form):
    """Détecte si une ligne de formset est marquée DELETE dans la requête."""
    if not form or not getattr(form, 'is_bound', False):
        return False

    try:
        delete_key = form.add_prefix('DELETE')
    except Exception:
        return False

    delete_value = form.data.get(delete_key)
    return str(delete_value).lower() in {'1', 'true', 'on', 'yes'}


def _formset_is_effectively_valid(formset):
    """
    Validation robuste: ignore les erreurs de champs pour les lignes DELETE.
    Les erreurs non-form (management form, cohérence globale) restent bloquantes.
    """
    if not formset:
        return True

    if formset.non_form_errors():
        return False

    for form in formset.forms:
        if _is_form_marked_for_delete(form):
            continue
        if form.errors:
            return False

    return True


def _collect_effective_formset_errors(formset, row_prefix):
    """Retourne des erreurs lisibles pour les lignes non supprimées d'un formset."""
    messages_list = []

    if not formset:
        return messages_list

    for err in formset.non_form_errors():
        messages_list.append(str(err))

    for index, form in enumerate(formset.forms, start=1):
        if _is_form_marked_for_delete(form):
            continue

        if not getattr(form, 'errors', None):
            continue

        for field_name, field_errors in form.errors.items():
            for err in field_errors:
                if field_name == '__all__':
                    messages_list.append(f"{row_prefix} {index}: {err}")
                    continue

                try:
                    label = form.fields[field_name].label or field_name
                except Exception:
                    label = field_name
                messages_list.append(f"{row_prefix} {index} - {label}: {err}")

    return messages_list

@csrf_exempt
@require_POST
def verify_student(request):
    """Vérifie si un étudiant existe dans la base de données"""
    try:
        data = json.loads(request.body)
        student_id = data.get('student_id', '').strip()
        if not student_id or len(student_id) != 12 or not student_id.isdigit():
            return JsonResponse({'exists': False, 'error': 'Format matricule invalide'})
        exists = Etudiant.objects.filter(student_number=student_id).exists()
        return JsonResponse({'exists': exists})
    except Exception as e:
        return JsonResponse({'exists': False, 'error': str(e)})


def student_login(request):
    """Vérifie et connecte l'étudiant - vue de vérification"""
    if request.method == 'POST':
        student_id = request.POST.get('student_id', '').strip()
        password = request.POST.get('password', '')
        
        # Validation du format
        if not student_id or len(student_id) != 12 or not student_id.isdigit():
            messages.error(request, 'Matricule invalide. Veuillez entrer 12 chiffres.')
            return redirect('gestion_transport:student_interface')

        if not password:
            messages.error(request, 'Veuillez saisir votre mot de passe.')
            return redirect('gestion_transport:student_interface')
        
        # Vérifier matricule + mot de passe
        try:
            student = Etudiant.objects.get(student_number=student_id)

            if not student.check_password(password):
                messages.error(request, 'Matricule ou mot de passe incorrect.')
                return redirect('gestion_transport:student_interface')

            request.session['student_number'] = student.student_number

            from django.urls import reverse
            url = reverse('gestion_transport:student_dashboard') + f'?id={student_id}'
            return redirect(url)
        except Etudiant.DoesNotExist:
            messages.error(request, 'Matricule ou mot de passe incorrect.')
            return redirect('gestion_transport:student_interface')
    
    # Si ce n'est pas une requête POST, rediriger vers la page de connexion
    return redirect('gestion_transport:student_interface')

def index(request):
    """Page d'accueil avec interface de connexion"""
    return render(request, 'gestion_transport/index.html', {'generic_page': False})

def student_interface(request):
    """Page d'accueil pour les étudiants"""
    return render(request, 'gestion_transport/student_space.html', {
        'generic_page': True
    })


def driver_login(request):
    """Vérifie et connecte le conducteur."""
    if request.method == 'POST':
        driver_id = request.POST.get('driver_id', '').strip().upper()
        password = request.POST.get('password', '')

        if not driver_id:
            messages.error(request, "Veuillez saisir votre ID conducteur.")
            return redirect('gestion_transport:driver_interface')

        if not password:
            messages.error(request, 'Veuillez saisir votre mot de passe.')
            return redirect('gestion_transport:driver_interface')

        try:
            conducteur = Conducteur.objects.get(driver_id__iexact=driver_id)
            if not conducteur.check_password(password):
                messages.error(request, 'ID conducteur ou mot de passe incorrect.')
                return redirect('gestion_transport:driver_interface')

            request.session['driver_id'] = conducteur.driver_id
            return redirect('gestion_transport:driver_home')
        except Conducteur.DoesNotExist:
            messages.error(request, 'ID conducteur ou mot de passe incorrect.')
            return redirect('gestion_transport:driver_interface')

    return redirect('gestion_transport:driver_interface')


def driver_home(request):
    """Tableau de bord du conducteur après connexion."""
    session_driver_id = request.session.get('driver_id')
    if not session_driver_id:
        return redirect('gestion_transport:driver_interface')

    try:
        conducteur = Conducteur.objects.get(driver_id=session_driver_id)
    except Conducteur.DoesNotExist:
        request.session.pop('driver_id', None)
        return redirect('gestion_transport:driver_interface')

    today = date.today()
    now_time = datetime.now().time()

    active_affectations = AffectationBusLigne.objects.filter(
        conducteur=conducteur,
        date_debut__lte=today,
    ).filter(
        Q(date_fin__isnull=True) | Q(date_fin__gte=today)
    ).select_related('bus', 'ligne').order_by('-date_debut')

    all_affectations = AffectationBusLigne.objects.filter(
        conducteur=conducteur,
    ).select_related('bus', 'ligne').order_by('-date_debut', '-id')

    active_bus_ids = list(active_affectations.values_list('bus_id', flat=True).distinct())

    def _trajets_with_conducteur_assignments(queryset):
        return queryset.filter(
            bus__affectationbusligne__conducteur=conducteur,
            bus__affectationbusligne__date_debut__lte=F('date_trajet'),
        ).filter(
            Q(bus__affectationbusligne__date_fin__isnull=True) | Q(bus__affectationbusligne__date_fin__gte=F('date_trajet'))
        ).distinct()

    today_trajets_qs = _trajets_with_conducteur_assignments(Trajet.objects.filter(
        date_trajet=today,
    )).select_related('bus', 'ligne', 'horaire').prefetch_related(
        Prefetch(
            'ligne__lignestation_set',
            queryset=LigneStation.objects.select_related('station').order_by('ordre'),
            to_attr='ordered_ligne_stations'
        )
    ).order_by('horaire__heure_depart')

    today_trajets = list(today_trajets_qs)

    route_options = []
    for trajet in today_trajets:
        stations = getattr(trajet.ligne, 'ordered_ligne_stations', [])
        depart_station = stations[0].station if stations else None
        arrivee_station = stations[-1].station if stations else None
        waypoints = []
        for ls in stations:
            st = ls.station
            if not st or st.latitude is None or st.longitude is None:
                continue
            waypoints.append({
                'lat': float(st.latitude),
                'lng': float(st.longitude),
                'name': st.nom_station,
            })

        route_options.append({
            'trajet_id': trajet.id,
            'label': f"{trajet.ligne.nom_ligne} - {trajet.horaire.heure_depart.strftime('%H:%M')}",
            'depart_lat': str(depart_station.latitude) if depart_station and depart_station.latitude is not None else '',
            'depart_lng': str(depart_station.longitude) if depart_station and depart_station.longitude is not None else '',
            'arrivee_lat': str(arrivee_station.latitude) if arrivee_station and arrivee_station.latitude is not None else '',
            'arrivee_lng': str(arrivee_station.longitude) if arrivee_station and arrivee_station.longitude is not None else '',
            'depart_nom': depart_station.nom_station if depart_station else '',
            'arrivee_nom': arrivee_station.nom_station if arrivee_station else '',
            'waypoints_json': json.dumps(waypoints),
            'line_distance_km': trajet.ligne.distance_km if trajet.ligne.distance_km is not None else '',
            'available': bool(depart_station and arrivee_station and depart_station.latitude is not None and depart_station.longitude is not None and arrivee_station.latitude is not None and arrivee_station.longitude is not None),
        })

    suivis_today_map = {
        suivi.trajet_id: suivi
        for suivi in SuiviTrajetConducteur.objects.filter(trajet_id__in=[t.id for t in today_trajets])
    }

    def compute_status(trajet, suivi_obj):
        if suivi_obj and suivi_obj.statut == 'arrivee':
            return 'arrivee', 'Arrive', 'chip-green'
        if suivi_obj and suivi_obj.statut == 'depart':
            return 'en_route', 'En route', 'chip-blue'
        if trajet.date_trajet > today:
            return 'a_venir', 'A venir', 'chip-blue'
        if trajet.date_trajet < today:
            return 'passe', 'Passe', 'chip-gray'
        if trajet.horaire.heure_depart > now_time:
            return 'a_venir', 'A venir', 'chip-blue'
        if trajet.retard_minutes > 0:
            return 'en_attente', f'En attente (+{trajet.retard_minutes} min)', 'chip-red'
        return 'en_attente', 'En attente depart', 'chip-gray'

    today_rows = []
    for trajet in today_trajets:
        suivi_obj = suivis_today_map.get(trajet.id)
        status_key, status_label, status_class = compute_status(trajet, suivi_obj)
        today_rows.append({
            'trajet': trajet,
            'suivi': suivi_obj,
            'status_key': status_key,
            'status_label': status_label,
            'status_class': status_class,
            'can_mark_depart': status_key in ['a_venir', 'en_attente'],
            'can_mark_arrivee': status_key == 'en_route',
        })

    upcoming_trajets = [row for row in today_rows if row['status_key'] in ['a_venir', 'en_attente', 'en_route']]
    completed_today_trajets = [row for row in today_rows if row['status_key'] in ['arrivee', 'passe']]

    next_trajet = upcoming_trajets[0] if upcoming_trajets else None

    all_associated_trajets_qs = _trajets_with_conducteur_assignments(
        Trajet.objects.all()
    ).select_related('bus', 'ligne', 'horaire').order_by('-date_trajet', 'horaire__heure_depart')

    all_associated_trajets = list(all_associated_trajets_qs[:200])
    all_associated_suivis_map = {
        suivi.trajet_id: suivi
        for suivi in SuiviTrajetConducteur.objects.filter(trajet_id__in=[t.id for t in all_associated_trajets])
    }

    associated_rows = []
    for trajet in all_associated_trajets:
        suivi_obj = all_associated_suivis_map.get(trajet.id)
        status_key, status_label, status_class = compute_status(trajet, suivi_obj)
        associated_rows.append({
            'trajet': trajet,
            'status_key': status_key,
            'status_label': status_label,
            'status_class': status_class,
        })

    def classify_affectation(affectation):
        if affectation.date_debut <= today and (affectation.date_fin is None or affectation.date_fin >= today):
            return 'active'
        if affectation.date_debut > today:
            return 'future'
        return 'past'

    affectation_groups = [
        {
            'key': 'active',
            'label': 'Affectations actives',
            'items': [],
        },
        {
            'key': 'future',
            'label': 'Affectations à venir',
            'items': [],
        },
        {
            'key': 'past',
            'label': 'Affectations passées',
            'items': [],
        },
    ]

    group_map = {group['key']: group for group in affectation_groups}
    for aff in all_affectations:
        group_map[classify_affectation(aff)]['items'].append(aff)

    history_qs = _trajets_with_conducteur_assignments(
        Trajet.objects.filter(
            Q(date_trajet__lt=today) |
            Q(date_trajet=today, horaire__heure_depart__lt=now_time)
        )
    ).select_related('bus', 'ligne', 'horaire').order_by('-date_trajet', '-horaire__heure_depart')

    history_date_from = request.GET.get('history_date_from', '').strip()
    history_date_to = request.GET.get('history_date_to', '').strip()
    history_ligne_id = request.GET.get('history_ligne_id', '').strip()
    history_bus_id = request.GET.get('history_bus_id', '').strip()
    history_status = request.GET.get('history_status', '').strip()

    if history_date_from:
        history_qs = history_qs.filter(date_trajet__gte=history_date_from)
    if history_date_to:
        history_qs = history_qs.filter(date_trajet__lte=history_date_to)
    if history_ligne_id:
        history_qs = history_qs.filter(ligne_id=history_ligne_id)
    if history_bus_id:
        history_qs = history_qs.filter(bus_id=history_bus_id)

    history_trajets = list(history_qs[:120])
    history_suivis_map = {
        suivi.trajet_id: suivi
        for suivi in SuiviTrajetConducteur.objects.filter(trajet_id__in=[t.id for t in history_trajets])
    }

    history_rows = []
    for trajet in history_trajets:
        suivi_obj = history_suivis_map.get(trajet.id)
        status_key, status_label, status_class = compute_status(trajet, suivi_obj)
        row = {
            'trajet': trajet,
            'status_key': status_key,
            'status_label': status_label,
            'status_class': status_class,
        }
        history_rows.append(row)

    if history_status:
        history_rows = [row for row in history_rows if row['status_key'] == history_status]

    option_ligne_ids = set([t.ligne_id for t in history_trajets] + [t.ligne_id for t in today_trajets])
    option_bus_ids = set([t.bus_id for t in history_trajets] + [t.bus_id for t in today_trajets])
    history_lignes_options = Ligne.objects.filter(id__in=option_ligne_ids).order_by('nom_ligne')
    history_bus_options = Bus.objects.filter(id__in=option_bus_ids).order_by('numero_immatriculation')

    today_incidents_count = Incident.objects.filter(trajet__in=today_trajets).count()

    # --- UX dashboard conducteur (stats perso, timeline, flux compact) ---
    recent_window_start = today - timedelta(days=30)
    recent_rows = [
        row for row in associated_rows
        if recent_window_start <= row['trajet'].date_trajet <= today
    ]
    past_recent_rows = [
        row for row in recent_rows
        if row['trajet'].date_trajet < today or row['trajet'].horaire.heure_depart <= now_time
    ]

    past_recent_count = len(past_recent_rows)
    if past_recent_count:
        punctual_count = sum(1 for row in past_recent_rows if row['trajet'].retard_minutes == 0)
        punctuality_rate = round((punctual_count / past_recent_count) * 100)
        avg_retard_recent = round(
            sum(row['trajet'].retard_minutes for row in past_recent_rows) / past_recent_count,
            1,
        )
        completed_count = sum(1 for row in past_recent_rows if row['status_key'] in ['arrivee', 'passe'])
        completion_rate = round((completed_count / past_recent_count) * 100)
    else:
        punctuality_rate = 100
        avg_retard_recent = 0
        completion_rate = 100

    fiabilite_score = round((punctuality_rate * 0.65) + (completion_rate * 0.35))

    upcoming_preview_rows = upcoming_trajets[:5]
    quick_action_row = next(
        (row for row in today_rows if row['status_key'] in ['a_venir', 'en_attente', 'en_route']),
        today_rows[0] if today_rows else None,
    )

    associated_trajet_ids = [t.id for t in all_associated_trajets]
    recent_incidents = Incident.objects.filter(
        trajet_id__in=associated_trajet_ids
    ).select_related('trajet__ligne').order_by('-date_heure_incident')[:4]
    recent_retards = RetardTrajet.objects.filter(
        trajet_id__in=associated_trajet_ids
    ).select_related('trajet__ligne').order_by('-date_declaration')[:4]

    recent_activity_feed = []
    for incident in recent_incidents:
        recent_activity_feed.append({
            'kind': 'incident',
            'label': incident.type_incident or 'Incident',
            'line_name': incident.trajet.ligne.nom_ligne,
            'details': incident.description,
            'timestamp': incident.date_heure_incident,
        })
    for retard in recent_retards:
        recent_activity_feed.append({
            'kind': 'retard',
            'label': f"Retard +{retard.retard_minutes} min",
            'line_name': retard.trajet.ligne.nom_ligne,
            'details': retard.motif or 'Déclaration de retard conducteur',
            'timestamp': retard.date_declaration,
        })
    recent_activity_feed.sort(key=lambda item: item['timestamp'], reverse=True)
    recent_activity_feed = recent_activity_feed[:6]

    # --- Calendrier des trajets du conducteur ---
    cal_date_str = request.GET.get('cal_date', '').strip()
    cal_day_str = request.GET.get('cal_day', '').strip()

    # La date de référence sert à la fois à choisir le mois et le jour sélectionné.
    cal_ref_date = _parse_calendar_reference_date(cal_day_str or cal_date_str)
    cal_first_of_month = cal_ref_date.replace(day=1)
    cal_next_month_first = (cal_first_of_month.replace(day=28) + timedelta(days=4)).replace(day=1)

    cal_trajets_qs = _trajets_with_conducteur_assignments(
        Trajet.objects.filter(
            date_trajet__gte=cal_first_of_month,
            date_trajet__lt=cal_next_month_first,
        )
    ).select_related('bus', 'ligne', 'horaire').order_by('date_trajet', 'horaire__heure_depart')

    cal_trajets_by_date = {}
    for t in cal_trajets_qs:
        cal_trajets_by_date.setdefault(t.date_trajet, []).append(t)

    cal_first_weekday, _ = calendar.monthrange(cal_first_of_month.year, cal_first_of_month.month)
    cal_grid_start = cal_first_of_month - timedelta(days=cal_first_weekday)
    cal_cells = []
    for i in range(42):
        cell_date = cal_grid_start + timedelta(days=i)
        cell_params = {
            'panel': 'trajets',
            'cal_date': cal_first_of_month.isoformat(),
            'cal_day': cell_date.isoformat(),
        }
        cell_trips = cal_trajets_by_date.get(cell_date, [])
        cal_cells.append({
            'date': cell_date,
            'in_current_month': cell_date.month == cal_first_of_month.month,
            'is_today': cell_date == today,
            'is_selected': cell_date.isoformat() == cal_ref_date.isoformat() if (cal_day_str or cal_date_str) else False,
            'trajets': cell_trips,
            'trajets_count': len(cell_trips),
            'query': urlencode(cell_params),
        })
    cal_weeks = [cal_cells[i:i + 7] for i in range(0, 42, 7)]

    _cal_month_labels = {
        1: 'Janvier', 2: 'Fevrier', 3: 'Mars', 4: 'Avril', 5: 'Mai', 6: 'Juin',
        7: 'Juillet', 8: 'Aout', 9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Decembre',
    }
    cal_month_label = f"{_cal_month_labels[cal_first_of_month.month]} {cal_first_of_month.year}"

    cal_prev_month = (cal_first_of_month - timedelta(days=1)).replace(day=1)
    cal_next_month = cal_next_month_first
    cal_prev_query = urlencode({'panel': 'trajets', 'cal_date': cal_prev_month.isoformat()})
    cal_next_query = urlencode({'panel': 'trajets', 'cal_date': cal_next_month.isoformat()})

    # Agenda du jour sélectionné
    cal_selected_day_trajets = _trajets_with_conducteur_assignments(
        Trajet.objects.filter(date_trajet=cal_ref_date)
    ).select_related('bus', 'ligne', 'horaire').order_by('horaire__heure_depart')

    cal_selected_suivis_map = {
        s.trajet_id: s
        for s in SuiviTrajetConducteur.objects.filter(
            trajet_id__in=[t.id for t in cal_selected_day_trajets]
        )
    }
    cal_agenda_slots = []
    for t in cal_selected_day_trajets:
        suivi_obj = cal_selected_suivis_map.get(t.id)
        status_key, status_label, status_class = compute_status(t, suivi_obj)
        cal_agenda_slots.append({
            'trajet': t,
            'heure_depart': t.horaire.heure_depart,
            'heure_arrivee': t.horaire.heure_arrivee,
            'sens': t.horaire.sens,
            'sens_display': t.horaire.get_sens_display(),
            'ligne_nom': t.ligne.nom_ligne,
            'bus_immat': t.bus.numero_immatriculation,
            'status_label': status_label,
            'status_class': status_class,
        })

    context = {
        'conducteur': conducteur,
        'driver_id': conducteur.driver_id,
        'driver_name': f"{conducteur.prenom} {conducteur.nom}",
        'driver_email': conducteur.email,
        'driver_phone': conducteur.telephone,
        'active_affectations': active_affectations,
        'all_affectations': all_affectations,
        'affectation_groups': affectation_groups,
        'today_trajets': today_trajets,
        'today_rows': today_rows,
        'associated_rows': associated_rows,
        'upcoming_trajets': upcoming_trajets,
        'completed_today_trajets': completed_today_trajets,
        'history_rows': history_rows,
        'next_trajet': next_trajet,
        'today_date': today.strftime('%d/%m/%Y'),
        'stats_total_affectations': active_affectations.count(),
        'stats_today_trajets': len(today_trajets),
        'stats_associated_trajets': len(associated_rows),
        'stats_completed_today': len(completed_today_trajets),
        'stats_upcoming_today': len(upcoming_trajets),
        'stats_today_incidents': today_incidents_count,
        'stats_punctuality_rate': punctuality_rate,
        'stats_avg_retard_recent': avg_retard_recent,
        'stats_fiabilite_score': fiabilite_score,
        'stats_completion_rate': completion_rate,
        'route_options': route_options,
        'upcoming_preview_rows': upcoming_preview_rows,
        'quick_action_row': quick_action_row,
        'recent_activity_feed': recent_activity_feed,
        'history_date_from': history_date_from,
        'history_date_to': history_date_to,
        'history_ligne_id': history_ligne_id,
        'history_bus_id': history_bus_id,
        'history_status': history_status,
        'history_lignes_options': history_lignes_options,
        'history_bus_options': history_bus_options,
        # calendrier conducteur
        'cal_weeks': cal_weeks,
        'cal_weekday_labels': ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'],
        'cal_month_label': cal_month_label,
        'cal_prev_query': cal_prev_query,
        'cal_next_query': cal_next_query,
        'cal_selected_day': cal_ref_date,
        'cal_agenda_slots': cal_agenda_slots,
        'current_panel': request.GET.get('panel', 'dashboard'),
        'generic_page': True,
    }

    return render(request, 'gestion_transport/driver_home.html', context)


@require_POST
def driver_logout(request):
    """Déconnecte le conducteur et vide sa session."""
    request.session.pop('driver_id', None)
    return JsonResponse({'success': True})


def _driver_has_access_to_trajet(conducteur, trajet):
    return AffectationBusLigne.objects.filter(
        conducteur=conducteur,
        bus=trajet.bus,
        date_debut__lte=trajet.date_trajet,
    ).filter(
        Q(date_fin__isnull=True) | Q(date_fin__gte=trajet.date_trajet)
    ).exists()


def _propagate_driver_to_bus_assignments(bus, conducteur, date_debut=None, date_fin=None, exclude_assignment_id=None):
    """Propager le conducteur aux affectations du bus sur une période chevauchante."""
    if not conducteur:
        return 0

    qs = AffectationBusLigne.objects.filter(bus=bus).exclude(conducteur=conducteur)
    if date_debut:
        period_end = _effective_period_end(date_debut, date_fin)
        qs = qs.filter(date_debut__lte=period_end).filter(Q(date_fin__isnull=True) | Q(date_fin__gte=date_debut))
    if exclude_assignment_id:
        qs = qs.exclude(id=exclude_assignment_id)

    updated = 0
    for assignment in qs:
        assignment.conducteur = conducteur
        assignment.save()
        updated += 1
    return updated


@login_required(login_url='gestion_transport:admin_login')
@user_passes_test(lambda u: u.is_staff, login_url='gestion_transport:admin_login')
def sync_bus_driver_assignments(request, bus_id):
    """Synchronise le conducteur du bus vers toutes ses affectations existantes."""
    if request.method != 'POST':
        return redirect('gestion_transport:liste_bus_affectations')

    try:
        bus = Bus.objects.get(id=bus_id)
    except Bus.DoesNotExist:
        messages.error(request, "Bus introuvable.")
        return redirect('gestion_transport:liste_bus_affectations')

    if not bus.conducteur:
        messages.warning(request, f"Le bus {bus.numero_immatriculation} n'a pas de conducteur assigné.")
        return redirect('gestion_transport:liste_bus_affectations')

    today = date.today()
    propagated_count = _propagate_driver_to_bus_assignments(
        bus=bus,
        conducteur=bus.conducteur,
        date_debut=today,
        date_fin=today,
    )
    _log_modification(
        request,
        'modification',
        'Affectation',
        f"Synchronisation conducteur bus {bus.numero_immatriculation} (période active): {propagated_count} affectation(s) mise(s) à jour."
    )
    messages.success(
        request,
        f"Synchronisation terminée pour le bus {bus.numero_immatriculation} (période active): {propagated_count} affectation(s) mise(s) à jour."
    )
    return redirect('gestion_transport:liste_bus_affectations')


@require_POST
def driver_set_retard(request):
    session_driver_id = request.session.get('driver_id')
    if not session_driver_id:
        return JsonResponse({'success': False, 'error': 'Session conducteur invalide.'}, status=401)

    try:
        conducteur = Conducteur.objects.get(driver_id=session_driver_id)
        data = json.loads(request.body or '{}')
        trajet_id = data.get('trajet_id')
        retard_minutes = int(data.get('retard_minutes', 0))

        if retard_minutes < 0 or retard_minutes > 240:
            return JsonResponse({'success': False, 'error': 'Le retard doit etre entre 0 et 240 minutes.'}, status=400)

        trajet = Trajet.objects.select_related('bus', 'ligne').get(id=trajet_id)
        if not _driver_has_access_to_trajet(conducteur, trajet):
            return JsonResponse({'success': False, 'error': 'Trajet non autorise pour ce conducteur.'}, status=403)

        trajet.retard_minutes = retard_minutes
        trajet.save(update_fields=['retard_minutes'])

        # Enregistrer dans l'historique des retards
        identity = f"{conducteur.driver_id} ({conducteur.prenom} {conducteur.nom})"
        RetardTrajet.objects.create(
            trajet=trajet,
            retard_minutes=retard_minutes,
            conducteur=conducteur,
            utilisateur_declarant=identity,
        )

        _log_modification(
            request,
            'modification',
            'Trajet',
            (
                f"Retard mis a jour par conducteur {conducteur.driver_id} "
                f"({conducteur.prenom} {conducteur.nom}) pour trajet {trajet.id}: {retard_minutes} min."
            )
        )
        return JsonResponse({'success': True, 'retard_minutes': retard_minutes})
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'Valeur de retard invalide.'}, status=400)
    except (Conducteur.DoesNotExist, Trajet.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'Conducteur ou trajet introuvable.'}, status=404)


@require_POST
def driver_report_incident(request):
    session_driver_id = request.session.get('driver_id')
    if not session_driver_id:
        return JsonResponse({'success': False, 'error': 'Session conducteur invalide.'}, status=401)

    try:
        conducteur = Conducteur.objects.get(driver_id=session_driver_id)
        data = json.loads(request.body or '{}')
        trajet_id = data.get('trajet_id')
        incident_type = (data.get('type_incident') or '').strip()
        description = (data.get('description') or '').strip()

        if not incident_type:
            return JsonResponse({'success': False, 'error': "Le type d'incident est obligatoire."}, status=400)

        trajet = Trajet.objects.select_related('bus', 'ligne').get(id=trajet_id)
        if not _driver_has_access_to_trajet(conducteur, trajet):
            return JsonResponse({'success': False, 'error': 'Trajet non autorise pour ce conducteur.'}, status=403)

        Incident.objects.create(
            trajet=trajet,
            description=description,
            date_heure_incident=timezone.now(),
            type_incident=incident_type,
        )

        _log_modification(
            request,
            'ajout',
            'Incident',
            (
                f"Incident signale par conducteur {conducteur.driver_id} "
                f"({conducteur.prenom} {conducteur.nom}) sur trajet {trajet.id}."
            )
        )
        return JsonResponse({'success': True})
    except (Conducteur.DoesNotExist, Trajet.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'Conducteur ou trajet introuvable.'}, status=404)


@require_POST
def driver_update_trajet_status(request):
    session_driver_id = request.session.get('driver_id')
    if not session_driver_id:
        return JsonResponse({'success': False, 'error': 'Session conducteur invalide.'}, status=401)

    try:
        conducteur = Conducteur.objects.get(driver_id=session_driver_id)
        data = json.loads(request.body or '{}')
        trajet_id = data.get('trajet_id')
        action = (data.get('action') or '').strip()

        if action not in ['depart', 'arrivee']:
            return JsonResponse({'success': False, 'error': 'Action invalide.'}, status=400)

        trajet = Trajet.objects.select_related('bus', 'ligne', 'horaire').get(id=trajet_id)
        if not _driver_has_access_to_trajet(conducteur, trajet):
            return JsonResponse({'success': False, 'error': 'Trajet non autorise pour ce conducteur.'}, status=403)

        suivi, _ = SuiviTrajetConducteur.objects.get_or_create(
            trajet=trajet,
            defaults={'conducteur': conducteur, 'statut': 'planifie'}
        )
        if suivi.conducteur_id != conducteur.id:
            suivi.conducteur = conducteur

        now_dt = timezone.now()
        if action == 'depart':
            if not suivi.depart_effectif:
                suivi.depart_effectif = now_dt
            suivi.statut = 'depart'
        elif action == 'arrivee':
            if not suivi.depart_effectif:
                suivi.depart_effectif = now_dt
            suivi.arrivee_effective = now_dt
            suivi.statut = 'arrivee'

        suivi.save()

        status_label = 'En route' if suivi.statut == 'depart' else 'Arrive'
        status_class = 'chip-blue' if suivi.statut == 'depart' else 'chip-green'

        _log_modification(
            request,
            'modification',
            'Trajet',
            f"Statut trajet {trajet.id} mis a jour par conducteur {conducteur.driver_id}: {suivi.statut}."
        )

        return JsonResponse({
            'success': True,
            'status_key': suivi.statut,
            'status_label': status_label,
            'status_class': status_class,
        })
    except (Conducteur.DoesNotExist, Trajet.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'Conducteur ou trajet introuvable.'}, status=404)


@require_POST
def driver_save_route_distance(request):
    """Sauvegarde la distance itineraire (route) dans Ligne.distance_km."""
    session_driver_id = request.session.get('driver_id')
    if not session_driver_id:
        return JsonResponse({'success': False, 'error': 'Session conducteur invalide.'}, status=401)

    try:
        conducteur = Conducteur.objects.get(driver_id=session_driver_id)
        data = json.loads(request.body or '{}')
        trajet_id = data.get('trajet_id')
        route_distance_km = float(data.get('route_distance_km', 0))

        if route_distance_km <= 0 or route_distance_km > 10000:
            return JsonResponse({'success': False, 'error': 'Distance itineraire invalide.'}, status=400)

        trajet = Trajet.objects.select_related('ligne').get(id=trajet_id)
        if not _driver_has_access_to_trajet(conducteur, trajet):
            return JsonResponse({'success': False, 'error': 'Trajet non autorise pour ce conducteur.'}, status=403)

        ligne = trajet.ligne
        new_distance_km = int(ceil(route_distance_km))
        previous_distance_km = ligne.distance_km

        if previous_distance_km != new_distance_km:
            ligne.distance_km = new_distance_km
            ligne.save(update_fields=['distance_km'])
            _log_modification(
                request,
                'modification',
                'Ligne',
                (
                    f"Distance ligne mise a jour depuis itineraire route par conducteur {conducteur.driver_id}: "
                    f"{ligne.nom_ligne} -> {new_distance_km} km (avant: {previous_distance_km if previous_distance_km is not None else 'N/A'})."
                )
            )

        return JsonResponse({
            'success': True,
            'distance_km': ligne.distance_km,
            'updated': previous_distance_km != new_distance_km,
        })
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'Valeur distance invalide.'}, status=400)
    except (Conducteur.DoesNotExist, Trajet.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'Conducteur ou trajet introuvable.'}, status=404)



# --- MULTI-PAGE ETUDIANT ---
def student_dashboard(request):
    """Tableau de bord étudiant (dashboard)"""
    return _student_panel_render(request, 'gestion_transport/student_dashboard.html')

def student_trips(request):
    """Page des trajets du jour"""
    return _student_panel_render(request, 'gestion_transport/student_trips.html')

def student_history(request):
    """Page de l'historique des trajets"""
    return _student_panel_render(request, 'gestion_transport/student_history.html')

def student_subscription(request):
    """Page de gestion des abonnements"""
    return _student_panel_render(request, 'gestion_transport/student_subscription.html')

def student_notifications(request):
    """Page des notifications"""
    return _student_panel_render(request, 'gestion_transport/student_notifications.html')

def student_tickets(request):
    """Page des tickets de réservation étudiant"""
    return _student_panel_render(request, 'gestion_transport/student_tickets.html')

def student_location(request):
    """Page de l'assistant de localisation étudiant"""
    return _student_panel_render(request, 'gestion_transport/student_location.html')

def student_profile(request):
    """Page du profil étudiant"""
    return _student_panel_render(request, 'gestion_transport/student_profile.html')

def _student_panel_render(request, template_name):
    """Facteur commun pour charger le contexte étudiant (reprend l'ancien student_home)"""
    session_student_id = request.session.get('student_number')
    if not session_student_id:
        return redirect('gestion_transport:student_interface')
    student_id = session_student_id
    try:
        etudiant = Etudiant.objects.get(student_number=student_id)
        subscriptions = AffectationEtudiantLigne.objects.filter(etudiant=etudiant).exclude(date_fin__lt=date.today()).select_related('ligne')
        active_subscriptions = subscriptions.filter(date_debut__lte=date.today())
        subscription_lignes = [sub.ligne for sub in active_subscriptions]
        subscription_ligne_ids = [ligne.id for ligne in subscription_lignes]
        subscriptions_data = []
        for sub in subscriptions:
            subscriptions_data.append({
                'id': sub.id,
                'ligne': sub.ligne.nom_ligne,
                'dateDebut': sub.date_debut.strftime('%Y-%m-%d'),
                'dateFin': sub.date_fin.strftime('%Y-%m-%d') if sub.date_fin else 'Indéterminée',
                'statut': 'Actif',
                'ligne_id': sub.ligne.id
            })
        reservation_horaires = Horaire.objects.filter(ligne_id__in=subscription_ligne_ids).select_related('ligne').order_by('ligne__nom_ligne', 'jour_semaine', 'heure_depart')
        horaires_by_line = {}
        for h in reservation_horaires:
            horaires_by_line.setdefault(str(h.ligne_id), []).append({
                'id': h.id,
                'jour_semaine': h.get_jour_semaine_display(),
                'sens': h.get_sens_display(),
                'heure_depart': h.heure_depart.strftime('%H:%M'),
                'heure_arrivee': h.heure_arrivee.strftime('%H:%M'),
                'label': f"{h.get_jour_semaine_display()} - {h.get_sens_display()} ({h.heure_depart.strftime('%H:%M')})",
            })
        student_reservations = ReservationHoraire.objects.filter(etudiant=etudiant).select_related('horaire__ligne').order_by('horaire__ligne__nom_ligne', 'horaire__jour_semaine', 'horaire__heure_depart')
        today = date.today()
        today_trajets_qs = Trajet.objects.filter(ligne_id__in=subscription_ligne_ids, date_trajet=today).select_related('ligne', 'horaire', 'bus').order_by('ligne__nom_ligne', 'horaire__heure_depart', 'bus__id')
        today_reserved_trajet_ids = set(ReservationTrajet.objects.filter(etudiant=etudiant, trajet__date_trajet=today).values_list('trajet_id', flat=True))
        now_time = datetime.now().time()
        today_slots_map = {}
        for t in today_trajets_qs:
            slot_key = (t.ligne_id, t.horaire_id)
            if slot_key not in today_slots_map:
                today_slots_map[slot_key] = {
                    'ligne_id': t.ligne_id,
                    'horaire_id': t.horaire_id,
                    'slot_key': f"{t.ligne_id}-{t.horaire_id}",
                    'ligne_nom': t.ligne.nom_ligne,
                    'sens_code': t.horaire.sens,
                    'sens': t.horaire.get_sens_display(),
                    'heure_depart': t.horaire.heure_depart.strftime('%H:%M'),
                    'heure_arrivee': t.horaire.heure_arrivee.strftime('%H:%M'),
                    'bus_count': 0,
                    'total_capacity': 0,
                    'reserved': False,
                    'reserved_bus': '',
                    'same_time_locked': False,
                    'is_past': t.horaire.heure_depart < now_time,
                }
            today_slots_map[slot_key]['bus_count'] += 1
            today_slots_map[slot_key]['total_capacity'] += t.bus.capacite
        student_today_reservations = ReservationTrajet.objects.filter(etudiant=etudiant, trajet__date_trajet=today).select_related('trajet__ligne', 'trajet__horaire', 'trajet__bus')
        reserved_departure_times = set()
        for r in student_today_reservations:
            if r.trajet.horaire.heure_depart > now_time:
                reserved_departure_times.add(r.trajet.horaire.heure_depart.strftime('%H:%M'))
            slot_key = (r.trajet.ligne_id, r.trajet.horaire_id)
            if slot_key in today_slots_map and r.trajet.horaire.heure_depart > now_time:
                today_slots_map[slot_key]['reserved'] = True
                today_slots_map[slot_key]['reserved_bus'] = r.trajet.bus.numero_immatriculation
        for slot in today_slots_map.values():
            if not slot['reserved'] and not slot['is_past'] and slot['heure_depart'] in reserved_departure_times:
                slot['same_time_locked'] = True
        today_slots = list(today_slots_map.values())
        now_time = datetime.now().time()
        today_reservations = ReservationTrajet.objects.filter(etudiant=etudiant, trajet__date_trajet=today).select_related('trajet__ligne', 'trajet__horaire', 'trajet__bus').order_by('trajet__horaire__heure_depart')
        upcoming_slots = []
        passed_today_slots = []
        for r in today_reservations:
            slot_data = {
                'trajet_id': r.trajet.id,
                'ligne_id': r.trajet.ligne_id,
                'horaire_id': r.trajet.horaire_id,
                'slot_key': f"{r.trajet.ligne_id}-{r.trajet.horaire_id}",
                'date_trajet': r.trajet.date_trajet,
                'ligne_nom': r.trajet.ligne.nom_ligne,
                'sens_code': r.trajet.horaire.sens,
                'sens': r.trajet.horaire.get_sens_display(),
                'heure_depart': r.trajet.horaire.heure_depart.strftime('%H:%M'),
                'heure_arrivee': r.trajet.horaire.heure_arrivee.strftime('%H:%M'),
                'bus': r.trajet.bus.numero_immatriculation,
                'status': "Effectué aujourd'hui",
            }
            if r.trajet.horaire.heure_depart <= now_time:
                passed_today_slots.append(slot_data)
            else:
                upcoming_slots.append(slot_data)
        history_reservations = ReservationTrajet.objects.filter(etudiant=etudiant, trajet__date_trajet__lt=today).select_related('trajet__ligne', 'trajet__horaire', 'trajet__bus').order_by('-trajet__date_trajet', '-trajet__horaire__heure_depart')
        all_history_slots = [
            {
                'trajet_id': r.trajet.id,
                'date_trajet': r.trajet.date_trajet,
                'ligne_nom': r.trajet.ligne.nom_ligne,
                'sens': r.trajet.horaire.get_sens_display(),
                'heure_depart': r.trajet.horaire.heure_depart.strftime('%H:%M'),
                'heure_arrivee': r.trajet.horaire.heure_arrivee.strftime('%H:%M'),
                'bus': r.trajet.bus.numero_immatriculation,
                'status': 'Effectué',
            }
            for r in history_reservations
        ]
        all_history_slots = passed_today_slots + all_history_slots
        all_history_slots = sorted(all_history_slots, key=lambda x: (x['date_trajet'], x['heure_depart']), reverse=True)
        history_trajet_ids = [slot['trajet_id'] for slot in all_history_slots if slot.get('trajet_id')]
        ratings_by_trajet = {avis.trajet_id: avis for avis in AvisTrajet.objects.filter(etudiant=etudiant, trajet_id__in=history_trajet_ids)}
        for slot in all_history_slots:
            trajet_id = slot.get('trajet_id')
            existing = ratings_by_trajet.get(trajet_id)
            slot['rating_exists'] = bool(existing)
            slot['rating_note_generale'] = existing.note_generale if existing else None
            slot['rating_note_bus'] = existing.note_bus if existing else None
            slot['rating_note_conducteur'] = existing.note_conducteur if existing else None
        history_line_options = sorted({slot['ligne_nom'] for slot in all_history_slots})
        history_slots = all_history_slots[:60]
        next_upcoming_slot = upcoming_slots[0] if upcoming_slots else None
        available_slots_count = sum(1 for slot in today_slots if (not slot['reserved'] and not slot['is_past'] and not slot['same_time_locked']))
        reservation_tickets = list(
            ReservationTrajet.objects.filter(etudiant=etudiant)
            .select_related('trajet__ligne', 'trajet__horaire', 'trajet__bus')
            .order_by('trajet__date_trajet', 'trajet__horaire__heure_depart')
        )
        for reservation in reservation_tickets:
            if not reservation.ticket_code:
                reservation.save(update_fields=['ticket_code'])

        active_ticket_cards = []
        used_ticket_cards = []
        for reservation in reservation_tickets:
            trajet = reservation.trajet
            is_today = trajet.date_trajet == today
            is_used = trajet.date_trajet < today or (is_today and trajet.horaire.heure_depart <= now_time)
            ticket_data = {
                'reservation_id': reservation.id,
                'trajet_id': trajet.id,
                'ticket_code': reservation.ticket_code,
                'qr_payload': reservation.ticket_code,
                'date_trajet': trajet.date_trajet,
                'date_label': trajet.date_trajet.strftime('%d/%m/%Y'),
                'ligne_nom': trajet.ligne.nom_ligne,
                'sens': trajet.horaire.get_sens_display(),
                'heure_depart': trajet.horaire.heure_depart.strftime('%H:%M'),
                'heure_arrivee': trajet.horaire.heure_arrivee.strftime('%H:%M'),
                'bus': trajet.bus.numero_immatriculation,
                'reserved_at': timezone.localtime(reservation.date_reservation).strftime('%d/%m/%Y %H:%M'),
                'status_label': "Utilisé" if is_used else ("À utiliser aujourd'hui" if is_today else "À venir"),
                'status_class': 'inactive' if is_used else ('pending' if is_today else 'active'),
            }
            if is_used:
                used_ticket_cards.append(ticket_data)
            else:
                active_ticket_cards.append(ticket_data)

        active_ticket_cards.sort(key=lambda item: (item['date_trajet'], item['heure_depart']))
        used_ticket_cards.sort(key=lambda item: (item['date_trajet'], item['heure_depart']), reverse=True)
        recent_start = today - timedelta(days=3)
        incident_feed = Incident.objects.filter(trajet__ligne_id__in=subscription_ligne_ids, trajet__date_trajet__gte=recent_start).select_related('trajet__ligne').order_by('-date_heure_incident')[:8]
        retard_feed = Trajet.objects.filter(ligne_id__in=subscription_ligne_ids, date_trajet__gte=recent_start, retard_minutes__gt=0).select_related('ligne', 'bus').order_by('-date_trajet', '-horaire__heure_depart')[:8]
        notifications_feed = []
        def _as_aware(dt_value):
            if timezone.is_naive(dt_value):
                return timezone.make_aware(dt_value, timezone.get_current_timezone())
            return dt_value
        for incident in incident_feed:
            notifications_feed.append({
                'type': 'incident',
                'title': incident.type_incident or 'Incident signalé',
                'message': incident.description,
                'line': incident.trajet.ligne.nom_ligne,
                'when': _as_aware(incident.date_heure_incident),
            })
        for retard in retard_feed:
            notifications_feed.append({
                'type': 'retard',
                'title': f"Retard de {retard.retard_minutes} min",
                'message': f"Bus {retard.bus.numero_immatriculation} impacté",
                'line': retard.ligne.nom_ligne,
                'when': _as_aware(datetime.combine(retard.date_trajet, retard.horaire.heure_depart)),
            })
        notifications_feed.sort(key=lambda item: item['when'], reverse=True)
        notifications_feed = notifications_feed[:10]
        urgent_alert_count = sum(1 for item in notifications_feed if item['type'] == 'incident')
        context = {
            'student': etudiant,
            'student_id': student_id,
            'student_name': etudiant.nom + " " + etudiant.prenom,
            'student_email': etudiant.email,
            'student_phone': etudiant.telephone,
            'student_inscription_date': etudiant.date_inscription,
            'lignes': Ligne.objects.all().order_by('nom_ligne'),
            'subscriptions': subscriptions_data,
            'subscriptions_json': json.dumps(subscriptions_data),
            'student_ligne': etudiant.affectationetudiantligne_set.exclude(date_fin__lt=date.today()).select_related('ligne').first().ligne if etudiant.affectationetudiantligne_set.exclude(date_fin__lt=date.today()).exists() else None,
            'reservation_lines': subscription_lignes,
            'horaires_by_line_json': json.dumps(horaires_by_line),
            'student_reservations': student_reservations,
            'today_slots': today_slots,
            'today_date': today.strftime('%d/%m/%Y'),
            'upcoming_slots': upcoming_slots,
            'history_slots': history_slots,
            'full_history_slots': all_history_slots,
            'history_line_options': history_line_options,
            'student_ratings_count': len(ratings_by_trajet),
            'next_upcoming_slot': next_upcoming_slot,
            'available_slots_count': available_slots_count,
            'notifications_feed': notifications_feed,
            'notifications_count': len(notifications_feed),
            'urgent_alert_count': urgent_alert_count,
            'stats_active_subscriptions': len(subscriptions_data),
            'stats_upcoming_today': len(upcoming_slots),
            'stats_history_total': len(all_history_slots),
            'stats_reservations_total': student_reservations.count(),
            'ticket_cards': active_ticket_cards,
            'used_ticket_cards': used_ticket_cards,
            'stats_ticket_count': len(active_ticket_cards),
            'stats_used_ticket_count': len(used_ticket_cards),
            'generic_page': True
        }
        return render(request, template_name, context)
    except Etudiant.DoesNotExist:
        return redirect('gestion_transport:student_interface')

@csrf_exempt
@require_POST
def subscribe_to_line(request):
    """Abonner un étudiant à une ligne"""
    try:
        data = json.loads(request.body)
        student_id = data.get('student_id')
        ligne_id = data.get('ligne_id')
        date_debut = data.get('date_debut')
        date_fin = data.get('date_fin') or None
        
        if not all([student_id, ligne_id, date_debut]):
            return JsonResponse({'success': False, 'error': 'Données manquantes'})
        
        # Récupérer l'étudiant et la ligne
        etudiant = Etudiant.objects.get(student_number=student_id)
        ligne = Ligne.objects.get(id=ligne_id)
        
        # Créer l'affectation
        affectation = AffectationEtudiantLigne(
            etudiant=etudiant,
            ligne=ligne,
            date_debut=date_debut,
            date_fin=date_fin
        )
        affectation.full_clean()
        affectation.save()
        
        return JsonResponse({
            'success': True, 
            'message': f'Abonnement à la {ligne.nom_ligne} enregistré avec succès!',
            'affectation_id': affectation.id
        })
        
    except Etudiant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Étudiant non trouvé'})
    except Ligne.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Ligne non trouvée'})
    except ValidationError as exc:
        if hasattr(exc, 'messages') and exc.messages:
            return JsonResponse({'success': False, 'error': exc.messages[0]})
        return JsonResponse({'success': False, 'error': 'Abonnement invalide'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@require_POST
def unsubscribe_from_line(request):
    """Désabonner un étudiant d'une ligne"""
    try:
        data = json.loads(request.body)
        student_id = data.get('student_id')
        ligne_id = data.get('ligne_id')
        
        if not all([student_id, ligne_id]):
            return JsonResponse({'success': False, 'error': 'Données manquantes'})
        
        # Récupérer l'étudiant et la ligne
        etudiant = Etudiant.objects.get(student_number=student_id)
        ligne = Ligne.objects.get(id=ligne_id)
        
        # Trouver et supprimer l'affectation active (sans date_fin ou avec date_fin future)
        affectation = AffectationEtudiantLigne.objects.filter(
            etudiant=etudiant,
            ligne=ligne
        ).exclude(
            date_fin__lt=date.today()
        ).first()
        
        if affectation:
            affectation.delete()
            return JsonResponse({
                'success': True, 
                'message': 'Désabonnement effectué avec succès!'
            })
        else:
            return JsonResponse({'success': False, 'error': 'Aucun abonnement actif trouvé'})
            
    except Etudiant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Étudiant non trouvé'})
    except Ligne.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Ligne non trouvée'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def get_student_subscriptions(request):
    """Récupérer les abonnements actifs d'un étudiant"""
    try:
        student_id = request.GET.get('student_id')
        
        if not student_id:
            return JsonResponse({'success': False, 'error': 'ID étudiant manquant'})
        
        # Récupérer l'étudiant
        etudiant = Etudiant.objects.get(student_number=student_id)
        
        # Récupérer les abonnements actifs (sans date_fin ou avec date_fin future)
        subscriptions = AffectationEtudiantLigne.objects.filter(
            etudiant=etudiant
        ).exclude(
            date_fin__lt=date.today()
        ).select_related('ligne')
        
        # Formater les données pour le frontend
        subscriptions_data = []
        for sub in subscriptions:
            subscriptions_data.append({
                'id': sub.id,
                'ligne_id': sub.ligne.id,
                'ligne': sub.ligne.nom_ligne,
                'dateDebut': sub.date_debut.strftime('%Y-%m-%d'),
                'dateFin': sub.date_fin.strftime('%Y-%m-%d') if sub.date_fin else 'Indéterminée',
                'statut': 'Actif'
            })
        
        return JsonResponse({
            'success': True,
            'subscriptions': subscriptions_data
        })
        
    except Etudiant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Étudiant non trouvé'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@require_POST
def reserve_trajet(request):
    """Réserver une place sur un créneau (ligne + sens + horaire) du jour même.
    Le bus est attribué automatiquement en remplissant d'abord le premier bus disponible.
    """
    try:
        session_student_id = request.session.get('student_number')
        if not session_student_id:
            return JsonResponse({'success': False, 'error': 'Session étudiante invalide.'}, status=401)

        data = json.loads(request.body)
        ligne_id = data.get('ligne_id')
        horaire_id = data.get('horaire_id')
        sens = data.get('sens')

        if not ligne_id or not horaire_id or not sens:
            return JsonResponse({'success': False, 'error': 'Ligne, sens et horaire sont obligatoires.'}, status=400)

        etudiant = Etudiant.objects.get(student_number=session_student_id)
        horaire = Horaire.objects.select_related('ligne').get(id=horaire_id)

        if int(ligne_id) != horaire.ligne_id or horaire.sens != sens:
            return JsonResponse(
                {'success': False, 'error': 'Le créneau sélectionné est incohérent (ligne/sens/horaire).'},
                status=400,
            )

        today = date.today()

        # Bloquer si l'heure de départ est déjà passée
        if horaire.heure_depart < datetime.now().time():
            return JsonResponse(
                {'success': False, 'error': 'Cet horaire est déjà passé, vous ne pouvez plus réserver.'},
                status=400,
            )

        # Vérification abonnement actif sur la ligne du trajet
        has_active_subscription = AffectationEtudiantLigne.objects.filter(
            etudiant=etudiant,
            ligne_id=ligne_id,
            date_debut__lte=today,
        ).exclude(date_fin__lt=today).exists()

        if not has_active_subscription:
            return JsonResponse(
                {'success': False, 'error': 'Vous devez avoir un abonnement actif sur cette ligne.'},
                status=403,
            )

        # Un étudiant ne peut pas réserver deux trajets à la même heure le même jour,
        # même si la ligne est différente.
        existing_reservation = ReservationTrajet.objects.filter(
            etudiant=etudiant,
            trajet__date_trajet=today,
            trajet__horaire__heure_depart=horaire.heure_depart,
        ).select_related('trajet__bus', 'trajet__ligne', 'trajet__horaire').first()

        if existing_reservation:
            return JsonResponse(
                {
                    'success': False,
                    'error': (
                        f"Vous avez déjà une réservation à "
                        f"{existing_reservation.trajet.horaire.heure_depart.strftime('%H:%M')} "
                        f"sur la ligne {existing_reservation.trajet.ligne.nom_ligne}."
                    ),
                    'assigned_bus': existing_reservation.trajet.bus.numero_immatriculation,
                },
                status=409,
            )

        # Récupérer les trajets candidats (un trajet par bus pour ce créneau aujourd'hui)
        candidate_trajets = list(
            Trajet.objects.filter(
                date_trajet=today,
                ligne_id=ligne_id,
                horaire_id=horaire_id,
            ).select_related('bus', 'horaire').order_by('bus__id', 'id')
        )

        if not candidate_trajets:
            return JsonResponse(
                {'success': False, 'error': 'Aucun trajet disponible aujourd\'hui pour ce créneau.'},
                status=404,
            )

        # Compter les réservations par trajet pour appliquer la capacité
        reservation_counts = {
            item['trajet_id']: item['total']
            for item in ReservationTrajet.objects.filter(
                trajet_id__in=[t.id for t in candidate_trajets]
            ).values('trajet_id').annotate(total=Count('id'))
        }

        selected_trajet = None
        for trajet in candidate_trajets:
            current_count = reservation_counts.get(trajet.id, 0)
            if current_count < trajet.bus.capacite:
                selected_trajet = trajet
                break

        if not selected_trajet:
            return JsonResponse(
                {'success': False, 'error': 'Tous les bus sont complets pour ce créneau.'},
                status=409,
            )

        ReservationTrajet.objects.create(
            etudiant=etudiant,
            trajet=selected_trajet,
        )

        return JsonResponse(
            {
                'success': True,
                'message': f"Réservation enregistrée. Bus attribué: {selected_trajet.bus.numero_immatriculation}.",
                'assigned_bus': selected_trajet.bus.numero_immatriculation,
            }
        )

    except Etudiant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Étudiant non trouvé.'}, status=404)
    except Horaire.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Horaire introuvable.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def cancel_reservation_trajet(request):
    """Annuler une réservation sur un créneau (ligne + sens + horaire) du jour même."""
    try:
        session_student_id = request.session.get('student_number')
        if not session_student_id:
            return JsonResponse({'success': False, 'error': 'Session étudiante invalide.'}, status=401)

        data = json.loads(request.body)
        ligne_id = data.get('ligne_id')
        horaire_id = data.get('horaire_id')
        sens = data.get('sens')

        if not ligne_id or not horaire_id or not sens:
            return JsonResponse({'success': False, 'error': 'Ligne, sens et horaire sont obligatoires.'}, status=400)

        etudiant = Etudiant.objects.get(student_number=session_student_id)
        horaire = Horaire.objects.get(id=horaire_id)

        if int(ligne_id) != horaire.ligne_id or horaire.sens != sens:
            return JsonResponse(
                {'success': False, 'error': 'Le créneau sélectionné est incohérent (ligne/sens/horaire).'},
                status=400,
            )

        if horaire.heure_depart <= datetime.now().time():
            return JsonResponse(
                {
                    'success': False,
                    'error': "L'horaire est dépassé, l'annulation n'est plus possible.",
                    'past_slot': True,
                },
                status=400,
            )

        deleted_count, _ = ReservationTrajet.objects.filter(
            etudiant=etudiant,
            trajet__date_trajet=date.today(),
            trajet__ligne_id=ligne_id,
            trajet__horaire_id=horaire_id,
        ).delete()

        if deleted_count == 0:
            return JsonResponse({'success': True, 'message': 'Aucune réservation à annuler pour ce créneau.'})

        return JsonResponse({'success': True, 'message': 'Réservation annulée avec succès.'})

    except Etudiant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Étudiant non trouvé.'}, status=404)
    except Horaire.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Horaire introuvable.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def rate_trajet(request):
    """Permet à l'étudiant de noter un trajet (général obligatoire, bus/conducteur optionnels)."""
    try:
        session_student_id = request.session.get('student_number')
        if not session_student_id:
            return JsonResponse({'success': False, 'error': 'Session étudiante invalide.'}, status=401)

        etudiant = Etudiant.objects.get(student_number=session_student_id)
        data = json.loads(request.body or '{}')

        trajet_id = data.get('trajet_id')
        note_generale = data.get('note_generale')
        note_bus = data.get('note_bus')
        note_conducteur = data.get('note_conducteur')
        commentaire = (data.get('commentaire') or '').strip()

        if not trajet_id:
            return JsonResponse({'success': False, 'error': 'Trajet manquant.'}, status=400)

        try:
            note_generale = int(note_generale)
        except (TypeError, ValueError):
            return JsonResponse({'success': False, 'error': 'La note générale est obligatoire.'}, status=400)

        if note_generale < 1 or note_generale > 5:
            return JsonResponse({'success': False, 'error': 'La note générale doit être entre 1 et 5.'}, status=400)

        def _parse_optional_note(value):
            if value in [None, '']:
                return None
            parsed = int(value)
            if parsed < 1 or parsed > 5:
                raise ValueError('Les notes optionnelles doivent être entre 1 et 5.')
            return parsed

        try:
            note_bus = _parse_optional_note(note_bus)
            note_conducteur = _parse_optional_note(note_conducteur)
        except (TypeError, ValueError):
            return JsonResponse({'success': False, 'error': 'Les notes bus/conducteur doivent être entre 1 et 5.'}, status=400)

        trajet = Trajet.objects.select_related('bus__conducteur', 'horaire').get(id=trajet_id)

        # Vérifier que l'étudiant a bien réservé ce trajet.
        has_reserved = ReservationTrajet.objects.filter(etudiant=etudiant, trajet=trajet).exists()
        if not has_reserved:
            return JsonResponse({'success': False, 'error': 'Vous ne pouvez noter que vos trajets réservés.'}, status=403)

        # Notation autorisée uniquement pour les trajets déjà passés.
        today = date.today()
        now_time = datetime.now().time()
        if trajet.date_trajet > today or (trajet.date_trajet == today and trajet.horaire.heure_depart > now_time):
            return JsonResponse({'success': False, 'error': 'Vous pourrez noter ce trajet après son départ.'}, status=400)

        avis, created = AvisTrajet.objects.update_or_create(
            etudiant=etudiant,
            trajet=trajet,
            defaults={
                'bus': trajet.bus,
                'conducteur': trajet.bus.conducteur,
                'note_generale': note_generale,
                'note_bus': note_bus,
                'note_conducteur': note_conducteur,
                'commentaire': commentaire,
            },
        )

        _log_modification(
            request,
            'ajout' if created else 'modification',
            'AvisTrajet',
            f"Évaluation étudiant {etudiant.student_number} pour trajet {trajet.id}: générale {avis.note_generale}/5.",
        )

        return JsonResponse({
            'success': True,
            'created': created,
            'note_generale': avis.note_generale,
            'note_bus': avis.note_bus,
            'note_conducteur': avis.note_conducteur,
        })

    except Etudiant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Étudiant non trouvé.'}, status=404)
    except Trajet.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Trajet introuvable.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

def driver_interface(request):
    """Page d'accueil pour les conducteurs"""
    return render(request, 'gestion_transport/driver_space.html', {
        'generic_page': True
    })


def admin_interface(request):
    """Page d'accueil pour les administrateurs"""
    return render(request, 'gestion_transport/admin_space.html', {
        'generic_page': True
    })


def inscription(request):
    """Formulaire d'inscription d'un étudiant"""
    if request.method == 'POST':
        form = EtudiantRegistrationForm(request.POST)
        if form.is_valid():
            etudiant = form.save()
            _log_modification(
                request,
                'ajout',
                'Étudiant',
                f"Étudiant {etudiant.student_number} ajouté ({etudiant.prenom} {etudiant.nom})."
            )
            messages.success(request, "Étudiant ajouté avec succès.")
            return redirect('gestion_transport:admin_dashboard')
    else:
        form = EtudiantRegistrationForm()

    return render(request, 'gestion_transport/inscription.html', {
        'form': form,
        'generic_page': True
    })


inscription = login_required(login_url='gestion_transport:admin_login')(inscription)
inscription = user_passes_test(lambda u: u.is_staff, login_url='gestion_transport:admin_login')(inscription)

def inscription_conducteur(request):
    """Formulaire d'inscription d'un conducteur"""
    if request.method == 'POST':
        form = ConducteurRegistrationForm(request.POST)
        if form.is_valid():
            conducteur = form.save()
            _log_modification(
                request,
                'ajout',
                'Conducteur',
                f"Conducteur {conducteur.driver_id} ajouté ({conducteur.prenom} {conducteur.nom})."
            )
            messages.success(request, "Conducteur ajouté avec succès.")
            return redirect('gestion_transport:liste_conducteurs')
    else:
        form = ConducteurRegistrationForm()

    return render(request, 'gestion_transport/inscription_conducteur.html', {
        'form': form,
        'generic_page': True
    })

inscription_conducteur = login_required(login_url='gestion_transport:admin_login')(inscription_conducteur)
inscription_conducteur = user_passes_test(lambda u: u.is_staff, login_url='gestion_transport:admin_login')(inscription_conducteur)  
   





@login_required(login_url='gestion_transport:admin_login')
@user_passes_test(lambda u: u.is_staff, login_url='gestion_transport:admin_login')
def admin_dashboard(request):
    """Tableau de bord administrateur"""
    stats = {
        'total_bus': Bus.objects.count(),
        'total_lignes': Ligne.objects.count(),
        'total_etudiants': Etudiant.objects.count(),
    }
    modifications_history = ModificationHistorique.objects.all()[:10]
    driver_notifications = ModificationHistorique.objects.filter(
        objet_type__in=['Trajet', 'Incident'],
        description__icontains='conducteur',
    )[:6]

    return render(request, 'gestion_transport/admin_dashboard.html', {
        'stats': stats,
        'modifications_history': modifications_history,
        'driver_notifications': driver_notifications,
        'generic_page': True
    })


@login_required(login_url='gestion_transport:admin_login')
@user_passes_test(lambda u: u.is_staff, login_url='gestion_transport:admin_login')
def historique_modifications(request):
    """Historique détaillé des modifications avec filtres et pagination."""
    action = (request.GET.get('action') or '').strip()
    objet_type = (request.GET.get('objet_type') or '').strip()
    utilisateur = (request.GET.get('utilisateur') or '').strip()
    q = (request.GET.get('q') or '').strip()
    date_debut = (request.GET.get('date_debut') or '').strip()
    date_fin = (request.GET.get('date_fin') or '').strip()

    history_qs = ModificationHistorique.objects.all()

    if action:
        history_qs = history_qs.filter(action=action)
    if objet_type:
        history_qs = history_qs.filter(objet_type__icontains=objet_type)
    if utilisateur:
        history_qs = history_qs.filter(utilisateur__icontains=utilisateur)
    if q:
        history_qs = history_qs.filter(
            Q(description__icontains=q) |
            Q(objet_type__icontains=q) |
            Q(utilisateur__icontains=q)
        )

    if date_debut:
        try:
            d1 = date.fromisoformat(date_debut)
            history_qs = history_qs.filter(date_action__date__gte=d1)
        except ValueError:
            pass

    if date_fin:
        try:
            d2 = date.fromisoformat(date_fin)
            history_qs = history_qs.filter(date_action__date__lte=d2)
        except ValueError:
            pass

    paginator = Paginator(history_qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    existing_objets = (
        ModificationHistorique.objects
        .exclude(objet_type__isnull=True)
        .exclude(objet_type='')
        .values_list('objet_type', flat=True)
        .distinct()
        .order_by('objet_type')
    )

    existing_users = (
        ModificationHistorique.objects
        .exclude(utilisateur__isnull=True)
        .exclude(utilisateur='')
        .values_list('utilisateur', flat=True)
        .distinct()
        .order_by('utilisateur')
    )

    return render(request, 'gestion_transport/historique_modifications.html', {
        'page_obj': page_obj,
        'selected_action': action,
        'selected_objet_type': objet_type,
        'selected_utilisateur': utilisateur,
        'selected_q': q,
        'selected_date_debut': date_debut,
        'selected_date_fin': date_fin,
        'action_choices': ModificationHistorique.ACTION_CHOICES,
        'objet_choices': existing_objets,
        'utilisateur_choices': existing_users,
        'generic_page': True,
    })


@login_required(login_url='gestion_transport:admin_login')
@user_passes_test(lambda u: u.is_staff, login_url='gestion_transport:admin_login')
def resync_trajets(request):
    """Resynchronise les trajets avec les affectations bus-ligne et horaires."""
    if request.method != 'POST':
        return redirect('gestion_transport:admin_dashboard')

    created_count = sync_all_future_trajets()
    _log_modification(
        request,
        'systeme',
        'Trajets',
        f"Resynchronisation des trajets: {created_count} trajet(s) créé(s)."
    )
    messages.success(request, f"Resynchronisation terminée: {created_count} trajet(s) créé(s).")
    return redirect('gestion_transport:admin_dashboard')


@login_required(login_url='gestion_transport:admin_login')
@user_passes_test(lambda u: u.is_staff, login_url='gestion_transport:admin_login')
def recompute_lignes_distances(request):
    """Recalcule les distances de toutes les lignes selon les stations et l'itineraire reel."""
    if request.method != 'POST':
        return redirect('gestion_transport:admin_dashboard')

    total = 0
    updated = 0
    skipped = 0

    for ligne in Ligne.objects.all().order_by('id'):
        total += 1
        distance_km = _calculate_ligne_distance_km_from_stations(ligne)
        if distance_km is None:
            skipped += 1
            continue

        if ligne.distance_km != distance_km:
            ligne.distance_km = distance_km
            ligne.save(update_fields=['distance_km'])
            updated += 1

    unchanged = total - updated - skipped
    _log_modification(
        request,
        'systeme',
        'Ligne',
        (
            "Recalcul global des distances lignes (itineraire reel prioritaire): "
            f"total={total}, modifiees={updated}, inchangees={unchanged}, ignorees={skipped}."
        )
    )
    messages.success(
        request,
        (
            "Recalcul des distances termine. "
            f"Total: {total} | Modifiees: {updated} | Inchangees: {unchanged} | Ignorees: {skipped}."
        )
    )
    return redirect('gestion_transport:admin_dashboard')

@login_required(login_url='gestion_transport:admin_login')
@user_passes_test(lambda u: u.is_staff, login_url='gestion_transport:admin_login')
def add_bus(request):
    """Ajout d'un bus"""
    if request.method == 'POST':
        form = BusForm(request.POST)
        if form.is_valid():
            bus = form.save()
            _log_modification(
                request,
                'ajout',
                'Bus',
                f"Bus {bus.numero_immatriculation} ajouté."
            )
            messages.success(request, f"Bus {bus.numero_immatriculation} ajouté avec succès.")
            # Check if we're in popup mode and should redirect to return_to
            return_to = request.GET.get('return_to')
            if request.GET.get('popup') == '1' and return_to:
                return redirect(return_to)
            return redirect('gestion_transport:admin_dashboard')
    else:
        form = BusForm()

    return render(request, 'gestion_transport/bus_form.html', {
        'form': form,
        'title': 'Ajouter un bus',
        'generic_page': True
    })

@never_cache
@login_required(login_url='gestion_transport:admin_login')
@user_passes_test(lambda u: u.is_staff, login_url='gestion_transport:admin_login')
def add_ligne(request):
    """Ajout d'une ligne"""
    if request.method == 'POST':
        form = LigneForm(request.POST)
        ligne_station_formset = LigneStationFormSet(request.POST, prefix='stations')
        form_valid = form.is_valid()
        ligne_station_formset.is_valid()
        forms_valid = form_valid and _formset_is_effectively_valid(ligne_station_formset)

        generated_name = ''
        if forms_valid:
            generated_name = _build_ligne_name_from_station_formset(ligne_station_formset)
            if not generated_name:
                msg = "Veuillez renseigner au moins deux stations valides (départ et arrivée)."
                ligne_station_formset._non_form_errors = ligne_station_formset.error_class([msg])
                forms_valid = False

        if forms_valid:
            normalized_name = generated_name.strip()
            if Ligne.objects.filter(nom_ligne__iexact=normalized_name).exists():
                form.add_error('nom_ligne', "Une ligne avec ce nom existe déjà.")
                forms_valid = False

        if forms_valid:
            username = request.user.get_username() if request.user.is_authenticated else ''
            set_history_user(username)
            try:
                ligne = form.save(commit=False)
                ligne.nom_ligne = generated_name
                ligne.save()
                ligne_station_formset.instance = ligne
                ligne_station_formset.save()
                distance_updated = _sync_ligne_distance_km(ligne)
            finally:
                clear_history_user()

            messages.success(request, "Ligne et stations enregistrées avec succès.")
            messages.info(request, "Ajoutez maintenant les horaires depuis l'écran dédié \"Horaires\".")
            if distance_updated:
                messages.info(request, f"Distance recalculée automatiquement: {ligne.distance_km} km.")
            return redirect('gestion_transport:horaires_ligne_detail', ligne_id=ligne.id)

        explicit_errors = []
        if not form_valid:
            for field_name, field_errors in form.errors.items():
                if field_name == 'nom_ligne':
                    continue
                for err in field_errors:
                    if field_name == '__all__':
                        explicit_errors.append(str(err))
                    else:
                        label = form.fields.get(field_name).label if field_name in form.fields else field_name
                        explicit_errors.append(f"Ligne - {label}: {err}")

        explicit_errors.extend(_collect_effective_formset_errors(ligne_station_formset, 'Station'))

        seen = set()
        for err in explicit_errors:
            normalized = str(err).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            messages.error(request, normalized)
    else:
        form = LigneForm()
        ligne_station_formset = LigneStationFormSet(prefix='stations')

    return render(request, 'gestion_transport/ligne_form.html', {
        'form': form,
        'ligne_station_formset': ligne_station_formset,
        'title': 'Ajouter une ligne',
        'generic_page': True,
    })



@never_cache
@login_required(login_url='gestion_transport:admin_login')
@user_passes_test(lambda u: u.is_staff, login_url='gestion_transport:admin_login')
def edit_ligne(request, ligne_id):
    """Modification d'une ligne"""
    try:
        ligne = Ligne.objects.get(id=ligne_id)
    except Ligne.DoesNotExist:
        messages.error(request, "Ligne introuvable.")
        return redirect('gestion_transport:admin_dashboard')

    if request.method == 'POST':
        form = LigneForm(request.POST, instance=ligne)
        ligne_station_formset = LigneStationFormSet(request.POST, prefix='stations', instance=ligne)
        form_valid = form.is_valid()
        ligne_station_formset.is_valid()
        forms_valid = form_valid and _formset_is_effectively_valid(ligne_station_formset)

        generated_name = ''
        if forms_valid:
            generated_name = _build_ligne_name_from_station_formset(ligne_station_formset)
            if not generated_name:
                msg = "Veuillez renseigner au moins deux stations valides (départ et arrivée)."
                ligne_station_formset._non_form_errors = ligne_station_formset.error_class([msg])
                forms_valid = False

        if forms_valid:
            normalized_name = generated_name.strip()
            if Ligne.objects.filter(nom_ligne__iexact=normalized_name).exclude(id=ligne.id).exists():
                form.add_error('nom_ligne', "Une ligne avec ce nom existe déjà.")
                forms_valid = False

        if forms_valid:
            form.instance.nom_ligne = generated_name

            username = request.user.get_username() if request.user.is_authenticated else ''
            set_history_user(username)
            try:
                form.save()
                ligne_station_formset.save()
                distance_updated = _sync_ligne_distance_km(form.instance)
            finally:
                clear_history_user()

            _log_modification(
                request,
                'modification',
                'Ligne',
                (
                    f"Ligne {form.instance.nom_ligne} modifiée "
                    f"({ligne_station_formset.instance.lignestation_set.count()} station(s), "
                    f"{form.instance.horaire_set.count()} horaire(s))."
                )
            )

            messages.success(request, "Ligne et stations modifiées avec succès.")
            if distance_updated:
                messages.info(request, f"Distance recalculée automatiquement: {form.instance.distance_km} km.")
            if request.GET.get('popup') == '1' and request.GET.get('return_to'):
                return redirect(request.GET.get('return_to'))
            return redirect('gestion_transport:admin_dashboard')

        explicit_errors = []
        if not form_valid:
            for field_name, field_errors in form.errors.items():
                if field_name == 'nom_ligne':
                    continue
                for err in field_errors:
                    if field_name == '__all__':
                        explicit_errors.append(str(err))
                    else:
                        label = form.fields.get(field_name).label if field_name in form.fields else field_name
                        explicit_errors.append(f"Ligne - {label}: {err}")

        explicit_errors.extend(_collect_effective_formset_errors(ligne_station_formset, 'Station'))

        seen = set()
        for err in explicit_errors:
            normalized = str(err).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            messages.error(request, normalized)
    else:
        form = LigneForm(instance=ligne)
        ligne_station_formset = LigneStationFormSet(prefix='stations', instance=ligne)

    line_summary = {
        'station_count': ligne.lignestation_set.count(),
        'horaire_count': ligne.horaire_set.count(),
        'mode_label': 'Modification',
    }

    horaires_groupes = []
    for jour_value, jour_label in Horaire.JOURS_SEMAINE:
        horaires_jour = ligne.horaire_set.filter(jour_semaine=jour_value).order_by('sens', 'heure_depart')
        group = {
            'jour_value': jour_value,
            'jour_label': jour_label,
            'aller': list(horaires_jour.filter(sens='aller')),
            'retour': list(horaires_jour.filter(sens='retour')),
        }
        if group['aller'] or group['retour']:
            horaires_groupes.append(group)
    sens_label_aller, sens_label_retour = _extract_direction_labels(ligne)

    return render(request, 'gestion_transport/ligne_form.html', {
        'form': form,
        'ligne_station_formset': ligne_station_formset,
        'title': f'Modifier la ligne: {ligne.nom_ligne}',
        'generic_page': True,
        'ligne_id': ligne.id,
        'line_summary': line_summary,
        'horaires_groupes': horaires_groupes,
        'sens_label_aller': sens_label_aller,
        'sens_label_retour': sens_label_retour,
    })

@login_required(login_url='gestion_transport:admin_login')
@user_passes_test(lambda u: u.is_staff, login_url='gestion_transport:admin_login')
def delete_ligne(request, ligne_id):
    """Suppression d'une ligne"""
    try:
        ligne = Ligne.objects.get(id=ligne_id)
    except Ligne.DoesNotExist:
        return redirect('gestion_transport:liste_lignes')

    if request.method == 'POST':
        ligne_nom = ligne.nom_ligne
        ligne.delete()
        _log_modification(
            request,
            'suppression',
            'Ligne',
            f"Ligne {ligne_nom} supprimée."
        )
        messages.success(request, f'Ligne {ligne_nom} supprimée avec succès.')
        return redirect('gestion_transport:liste_lignes')

    return render(request, 'gestion_transport/ligne_confirm_delete.html', {
        'ligne': ligne,
        'title': 'Confirmer la suppression',
        'generic_page': True
    })

@login_required(login_url='gestion_transport:admin_login')
@user_passes_test(lambda u: u.is_staff, login_url='gestion_transport:admin_login')
def add_station(request):
    """Ajout d'une station"""
    if request.method == 'POST':
        form = StationForm(request.POST)
        if form.is_valid():
            username = request.user.get_username() if request.user.is_authenticated else ''
            set_history_user(username)
            try:
                form.save()
            finally:
                clear_history_user()
            messages.success(request, "Station enregistrée avec succès.")
            if request.GET.get('popup') == '1':
                return redirect(request.GET.get('return_to') or 'gestion_transport:admin_dashboard')
            return redirect('gestion_transport:admin_dashboard')
    else:
        form = StationForm()

    return render(request, 'gestion_transport/station_form.html', {
        'form': form,
        'title': 'Ajouter une station',
        'generic_page': True
    })

@login_required(login_url='gestion_transport:admin_login')
@user_passes_test(lambda u: u.is_staff, login_url='gestion_transport:admin_login')
def edit_station(request, station_id):
    """Modification d'une station"""
    try:
        station = Station.objects.get(id=station_id)
    except Station.DoesNotExist:
        return redirect('gestion_transport:liste_stations')

    if request.method == 'POST':
        form = StationForm(request.POST, instance=station)
        if form.is_valid():
            previous_name = station.nom_station
            username = request.user.get_username() if request.user.is_authenticated else ''
            set_history_user(username)
            try:
                station = form.save()
            finally:
                clear_history_user()

            _log_modification(
                request,
                'modification',
                'Station',
                f"Station {previous_name} modifiée en {station.nom_station}."
            )

            messages.success(request, "Station modifiée avec succès.")
            # Check if we're in popup mode and should redirect to return_to
            return_to = request.GET.get('return_to')
            if request.GET.get('popup') == '1' and return_to:
                return redirect(return_to)
            return redirect('gestion_transport:liste_stations')
    else:
        form = StationForm(instance=station)

    return render(request, 'gestion_transport/station_form.html', {
        'form': form,
        'title': 'Modifier une station',
        'generic_page': True
    })

@login_required(login_url='gestion_transport:admin_login')
@user_passes_test(lambda u: u.is_staff, login_url='gestion_transport:admin_login')
def delete_station(request, station_id):
    """Suppression d'une station"""
    try:
        station = Station.objects.get(id=station_id)
    except Station.DoesNotExist:
        return redirect('gestion_transport:liste_stations')

    if request.method == 'POST':
        station_nom = station.nom_station
        lignes_associees = Ligne.objects.filter(lignestation__station=station).distinct()
        lignes_supprimees = list(lignes_associees)

        with transaction.atomic():
            for ligne in lignes_supprimees:
                ligne.delete()
            station.delete()

        if lignes_supprimees:
            lignes_labels = ', '.join(ligne.nom_ligne for ligne in lignes_supprimees[:3])
            if len(lignes_supprimees) > 3:
                lignes_labels += '...'
            _log_modification(
                request,
                'suppression',
                'Station',
                f"Station {station_nom} supprimée avec {len(lignes_supprimees)} ligne(s) associée(s): {lignes_labels}."
            )
            messages.success(
                request,
                f"Station {station_nom} supprimée avec succès. {len(lignes_supprimees)} ligne(s) associée(s) ont aussi été supprimée(s)."
            )
        else:
            _log_modification(
                request,
                'suppression',
                'Station',
                f"Station {station_nom} supprimée."
            )
            messages.success(request, f'Station {station_nom} supprimée avec succès.')
        return redirect('gestion_transport:liste_stations')

    return render(request, 'gestion_transport/station_confirm_delete.html', {
        'station': station,
        'title': 'Confirmer la suppression de la station',
        'generic_page': True
    })


@login_required(login_url='gestion_transport:admin_login')
@user_passes_test(lambda u: u.is_staff, login_url='gestion_transport:admin_login')
def geocode_station_address(request):
    """Recherche d'adresse en Algérie et récupération des coordonnées GPS via Nominatim."""
    query = (request.GET.get('q') or '').strip()
    if len(query) < 3:
        return JsonResponse(
            {
                'ok': False,
                'message': "Saisissez au moins 3 caractères pour rechercher une adresse.",
                'results': [],
            },
            status=400,
        )

    normalized_query = query
    if 'algerie' not in query.lower() and 'algérie' not in query.lower() and 'algeria' not in query.lower():
        normalized_query = f"{query}, Algérie"

    params = {
        'q': normalized_query,
        'format': 'jsonv2',
        'addressdetails': 1,
        'limit': 5,
        'countrycodes': 'dz',
        'accept-language': 'fr,ar',
    }
    url = f"https://nominatim.openstreetmap.org/search?{urlencode(params)}"

    req = Request(
        url,
        headers={
            'User-Agent': 'TransportUniversitaire/1.0 (station-geocode)',
            'Accept': 'application/json',
            'Accept-Language': 'fr,ar;q=0.9,en;q=0.6',
        },
    )

    try:
        with urlopen(req, timeout=8) as response:
            payload = response.read().decode('utf-8')
            raw_results = json.loads(payload)
    except (URLError, HTTPError, TimeoutError, ValueError):
        return JsonResponse(
            {
                'ok': False,
                'message': "Le service de géolocalisation est momentanément indisponible.",
                'results': [],
            },
            status=502,
        )

    results = []
    for item in raw_results:
        lat = item.get('lat')
        lon = item.get('lon')
        name = item.get('name') or item.get('display_name') or ''
        if not lat or not lon:
            continue
        results.append(
            {
                'display_name': item.get('display_name', ''),
                'name': name,
                'latitude': lat,
                'longitude': lon,
            }
        )

    return JsonResponse({'ok': True, 'country': 'DZ', 'results': results})

@login_required(login_url='gestion_transport:admin_login')
@user_passes_test(lambda u: u.is_staff, login_url='gestion_transport:admin_login')
def edit_bus(request, bus_id):
    """Modification d'un bus et gestion de ses affectations"""
    try:
        bus = Bus.objects.get(id=bus_id)
    except Bus.DoesNotExist:
        return redirect('gestion_transport:liste_bus_affectations')

    def build_edit_bus_context(current_form):
        affectations = AffectationBusLigne.objects.filter(bus=bus).order_by('date_debut')
        affectations_data = []
        total_trajets_affectations = 0
        trajets_par_ligne_totaux = {}
        for affectation in affectations:
            trajets_qs = Trajet.objects.filter(
                bus=bus,
                ligne=affectation.ligne,
                date_trajet__gte=affectation.date_debut,
            )
            if affectation.date_fin:
                trajets_qs = trajets_qs.filter(date_trajet__lte=affectation.date_fin)

            trajet_count = trajets_qs.count()
            total_trajets_affectations += trajet_count
            ligne_nom = affectation.ligne.nom_ligne
            trajets_par_ligne_totaux[ligne_nom] = trajets_par_ligne_totaux.get(ligne_nom, 0) + trajet_count

            affectations_data.append({
                'affectation': affectation,
                'trajet_count': trajet_count,
            })

        trajets_par_ligne_totaux = [
            {'ligne_nom': ligne_nom, 'trajet_count': trajet_count}
            for ligne_nom, trajet_count in sorted(trajets_par_ligne_totaux.items(), key=lambda item: item[0])
        ]
        trajets_bus_qs = Trajet.objects.filter(bus=bus)
        total_trajets_bus = trajets_bus_qs.count()
        total_dates_trajets_bus = trajets_bus_qs.values('date_trajet').distinct().count()

        return {
            'form': current_form,
            'bus': bus,
            'affectations': affectations,
            'affectations_data': affectations_data,
            'total_trajets_affectations': total_trajets_affectations,
            'trajets_par_ligne_totaux': trajets_par_ligne_totaux,
            'total_trajets_bus': total_trajets_bus,
            'total_dates_trajets_bus': total_dates_trajets_bus,
            'title': 'Modifier un bus',
            'generic_page': True
        }

    if request.method == 'POST':
        form = BusWithAffectationsForm(request.POST, instance=bus)
        if form.is_valid():
            # Vérifier que le conducteur assigné ne viole pas les contraintes avant de sauvegarder
            new_conducteur = form.cleaned_data.get('conducteur')
            if new_conducteur or (form.instance.conducteur and form.cleaned_data.get('conducteur') is not None):
                # Si le conducteur a changé, vérifier les conflits
                conductor_error = _validate_conductor_not_already_assigned(bus, new_conducteur)
                if conductor_error:
                    form.add_error('conducteur', conductor_error)
                    return render(request, 'gestion_transport/edit_bus.html', build_edit_bus_context(form))
            
            # Sauvegarder le bus
            bus = form.save()
            propagated_count = _propagate_driver_to_bus_assignments(
                bus=bus,
                conducteur=bus.conducteur,
                date_debut=date.today(),
                date_fin=date.today(),
            )
            _log_modification(
                request,
                'modification',
                'Bus',
                f"Bus {bus.numero_immatriculation} modifié."
            )

            # Gérer les modifications des affectations existantes
            for affectation in form.affectations:
                # Les modifications d'affectations existantes seront gérées via des formulaires séparés
                pass

            if propagated_count:
                messages.success(
                    request,
                    f"Bus modifié avec succès. Conducteur propagé sur {propagated_count} affectation(s) du bus."
                )
            else:
                messages.success(request, "Bus modifié avec succès.")
            # Check if we're in popup mode and should redirect to return_to
            return_to = request.GET.get('return_to')
            if request.GET.get('popup') == '1' and return_to:
                return redirect(return_to)
            return redirect('gestion_transport:liste_bus_affectations')
    else:
        form = BusWithAffectationsForm(instance=bus)

    return render(request, 'gestion_transport/edit_bus.html', build_edit_bus_context(form))


@login_required(login_url='gestion_transport:admin_login')
@user_passes_test(lambda u: u.is_staff, login_url='gestion_transport:admin_login')
def add_affectation_bus(request, bus_id):
    """Ajout d'une affectation pour un bus depuis la liste des bus"""
    try:
        bus = Bus.objects.get(id=bus_id)
    except Bus.DoesNotExist:
        messages.error(request, "Bus introuvable.")
        return redirect('gestion_transport:liste_bus_affectations')

    if request.method == 'POST':
        post_data = request.POST.copy()
        post_data['bus'] = str(bus.id)
        form = AffectationBusLigneForm(post_data)
        form.fields['bus'].widget = forms.HiddenInput()
        if form.is_valid():
            affectation = form.save(commit=False)
            auto_end_applied = _auto_set_assignment_end_date(affectation)
            affectation.save()
            propagated_count = _propagate_driver_to_bus_assignments(
                bus=bus,
                conducteur=affectation.conducteur,
                date_debut=affectation.date_debut,
                date_fin=affectation.date_fin,
                exclude_assignment_id=affectation.id,
            )
            _log_modification(
                request,
                'ajout',
                'Affectation',
                f"Affectation ajoutée: bus {bus.numero_immatriculation} / ligne {affectation.ligne.nom_ligne} ({affectation.date_debut} -> {affectation.date_fin or 'en cours'})."
            )
            if propagated_count:
                messages.success(
                    request,
                    f"Affectation ajoutée avec succès. Conducteur propagé sur {propagated_count} autre(s) affectation(s) du bus."
                )
            else:
                messages.success(request, "Affectation ajoutée avec succès.")
            if auto_end_applied:
                messages.info(
                    request,
                    f"Date de fin non renseignée: elle a été fixée automatiquement au {affectation.date_fin.strftime('%d/%m/%Y')} (1 an après la date de début)."
                )
            # Check if we're in popup mode and should redirect to return_to
            return_to = request.GET.get('return_to')
            if request.GET.get('popup') == '1' and return_to:
                return redirect(return_to)
            return redirect('gestion_transport:liste_bus_affectations')
        else:
            messages.error(request, "Impossible d'ajouter l'affectation : corrigez les erreurs ci-dessous.")
    else:
        form = AffectationBusLigneForm(initial={'bus': bus})
        form.fields['bus'].widget = forms.HiddenInput()

    return render(request, 'gestion_transport/add_affectation_bus.html', {
        'form': form,
        'bus': bus,
        'title': f'Ajouter une affectation — {bus.numero_immatriculation}',
        'generic_page': True
    })

@login_required(login_url='gestion_transport:admin_login')
@user_passes_test(lambda u: u.is_staff, login_url='gestion_transport:admin_login')
def edit_affectation(request, affectation_id):
    """Modification d'une affectation bus-ligne"""
    try:
        affectation = AffectationBusLigne.objects.get(id=affectation_id)
    except AffectationBusLigne.DoesNotExist:
        messages.error(request, "Affectation introuvable.")
        return redirect('gestion_transport:liste_bus_affectations')

    if request.method == 'POST':
        previous_conducteur = affectation.conducteur
        form = AffectationBusLigneForm(request.POST, instance=affectation)
        if form.is_valid():
            affectation_saved = form.save(commit=False)
            auto_end_applied = _auto_set_assignment_end_date(affectation_saved)
            requested_conducteur = affectation_saved.conducteur

            conducteur_changed = (
                previous_conducteur is not None
                and requested_conducteur is not None
                and previous_conducteur.id != requested_conducteur.id
            )
            confirm_override = request.POST.get('confirm_conducteur_override') == '1'

            if conducteur_changed and not confirm_override:
                form.add_error(
                    'conducteur',
                    "Cette affectation a déjà un conducteur. Confirmez pour le remplacer uniquement sur cette affectation."
                )
                return render(request, 'gestion_transport/edit_affectation.html', {
                    'form': form,
                    'affectation': affectation,
                    'title': 'Modifier une affectation',
                    'show_conducteur_override_confirm': True,
                    'current_conducteur_label': f"{previous_conducteur.prenom} {previous_conducteur.nom}",
                    'requested_conducteur_label': f"{requested_conducteur.prenom} {requested_conducteur.nom}",
                    'generic_page': True,
                })

            affectation_saved.save()
            if conducteur_changed and confirm_override:
                # Changement volontaire local: ne pas propager pour permettre
                # plusieurs conducteurs sur des affectations distinctes du meme bus.
                propagated_count = 0
            else:
                propagated_count = _propagate_driver_to_bus_assignments(
                    bus=affectation_saved.bus,
                    conducteur=affectation_saved.conducteur,
                    date_debut=affectation_saved.date_debut,
                    date_fin=affectation_saved.date_fin,
                    exclude_assignment_id=affectation_saved.id,
                )
            _log_modification(
                request,
                'modification',
                'Affectation',
                f"Affectation modifiée: bus {affectation_saved.bus.numero_immatriculation} / ligne {affectation_saved.ligne.nom_ligne} ({affectation_saved.date_debut} -> {affectation_saved.date_fin or 'en cours'})."
            )
            if propagated_count:
                messages.success(
                    request,
                    f"Affectation modifiée avec succès. Conducteur propagé sur {propagated_count} autre(s) affectation(s) du bus."
                )
            else:
                messages.success(request, "Affectation modifiée avec succès.")
            if conducteur_changed and confirm_override:
                messages.warning(
                    request,
                    "Conducteur remplacé uniquement pour cette affectation. Les autres affectations du bus n'ont pas été modifiées."
                )
            if auto_end_applied:
                messages.info(
                    request,
                    f"Date de fin non renseignée: elle a été fixée automatiquement au {affectation_saved.date_fin.strftime('%d/%m/%Y')} (1 an après la date de début)."
                )
            # Check if we're in popup mode and should redirect to return_to
            return_to = request.GET.get('return_to')
            if request.GET.get('popup') == '1' and return_to:
                return redirect(return_to)
            return redirect('gestion_transport:liste_bus_affectations')
    else:
        form = AffectationBusLigneForm(instance=affectation)

    return render(request, 'gestion_transport/edit_affectation.html', {
        'form': form,
        'affectation': affectation,
        'title': 'Modifier une affectation',
        'show_conducteur_override_confirm': False,
        'current_conducteur_label': '',
        'requested_conducteur_label': '',
        'generic_page': True
    })


@login_required(login_url='gestion_transport:admin_login')
@user_passes_test(lambda u: u.is_staff, login_url='gestion_transport:admin_login')
def delete_affectation(request, affectation_id):
    """Suppression d'une affectation bus-ligne"""
    try:
        affectation = AffectationBusLigne.objects.get(id=affectation_id)
        bus = affectation.bus
    except AffectationBusLigne.DoesNotExist:
        messages.error(request, "Affectation introuvable.")
        return redirect('gestion_transport:liste_bus_affectations')

    if request.method == 'POST':
        bus_immat = affectation.bus.numero_immatriculation
        ligne_nom = affectation.ligne.nom_ligne
        period = f"{affectation.date_debut} -> {affectation.date_fin or 'en cours'}"
        affectation.delete()
        _log_modification(
            request,
            'suppression',
            'Affectation',
            f"Affectation supprimée: bus {bus_immat} / ligne {ligne_nom} ({period})."
        )
        messages.success(request, f"Affectation supprimée avec succès.")
        return redirect('gestion_transport:liste_bus_affectations')

    return render(request, 'gestion_transport/delete_affectation.html', {
        'affectation': affectation,
        'title': 'Confirmer la suppression',
        'generic_page': True
    })


@login_required(login_url='gestion_transport:admin_login')
@user_passes_test(lambda u: u.is_staff, login_url='gestion_transport:admin_login')
def delete_bus(request, bus_id):
    """Suppression d'un bus"""
    try:
        bus = Bus.objects.get(id=bus_id)
    except Bus.DoesNotExist:
        return redirect('gestion_transport:liste_bus_affectations')

    if request.method == 'POST':
        # Vérifier s'il y a des affectations actives pour ce bus
        affectations_actives = AffectationBusLigne.objects.filter(
            bus=bus,
            date_debut__lte=date.today()
        ).filter(
            Q(date_fin__isnull=True) | Q(date_fin__gte=date.today())
        ).exists()

        if affectations_actives:
            # Ne pas supprimer si le bus a des affectations actives
            messages.error(request, f'Impossible de supprimer le bus {bus.numero_immatriculation} car il a des affectations actives.')
            return redirect('gestion_transport:liste_bus_affectations')

        bus_immat = bus.numero_immatriculation
        bus.delete()
        _log_modification(
            request,
            'suppression',
            'Bus',
            f"Bus {bus_immat} supprimé."
        )
        messages.success(request, f'Bus {bus_immat} supprimé avec succès.')
        return redirect('gestion_transport:liste_bus_affectations')

    return render(request, 'gestion_transport/bus_confirm_delete.html', {
        'bus': bus,
        'title': 'Confirmer la suppression du bus',
        'generic_page': True
    })

def bulk_assign_buses(request):
    """Vue retirée en douceur: redirection vers la gestion standard des affectations."""
    messages.info(request, "L'affectation en masse n'est plus disponible. Utilisez la gestion standard des bus et affectations.")
    return redirect('gestion_transport:liste_bus_affectations')

def nombre_etudiants_par_ligne(request):
    """Liste et gestion des etudiants avec filtre d'abonnement actif."""
    today = date.today()

    selected_ligne_id = request.GET.get('ligne_id', '').strip()
    selected_statut = request.GET.get('statut', '').strip()
    query = request.GET.get('q', '').strip()

    active_affectations_qs = AffectationEtudiantLigne.objects.filter(
        date_debut__lte=today
    ).filter(
        Q(date_fin__isnull=True) | Q(date_fin__gte=today)
    )

    active_etudiant_ids = set(active_affectations_qs.values_list('etudiant_id', flat=True).distinct())

    etudiants_qs = Etudiant.objects.all().order_by('-date_inscription', 'nom', 'prenom')

    if query:
        etudiants_qs = etudiants_qs.filter(
            Q(student_number__icontains=query)
            | Q(nom__icontains=query)
            | Q(prenom__icontains=query)
            | Q(email__icontains=query)
        )

    if selected_ligne_id:
        etudiants_qs = etudiants_qs.filter(
            affectationetudiantligne__ligne_id=selected_ligne_id,
            affectationetudiantligne__date_debut__lte=today,
        ).filter(
            Q(affectationetudiantligne__date_fin__isnull=True)
            | Q(affectationetudiantligne__date_fin__gte=today)
        ).distinct()

    if selected_statut == 'abonnes':
        etudiants_qs = etudiants_qs.filter(id__in=active_etudiant_ids)
    elif selected_statut == 'non_abonnes':
        etudiants_qs = etudiants_qs.exclude(id__in=active_etudiant_ids)

    etudiants = list(etudiants_qs)
    etudiant_ids = [e.id for e in etudiants]

    active_affectations = list(
        active_affectations_qs.filter(etudiant_id__in=etudiant_ids)
        .select_related('etudiant', 'ligne')
        .order_by('etudiant_id', '-date_debut', '-id')
    )

    active_affectation_map = {}
    for aff in active_affectations:
        if aff.etudiant_id not in active_affectation_map:
            active_affectation_map[aff.etudiant_id] = aff

    etudiants_data = []
    for etudiant in etudiants:
        active_aff = active_affectation_map.get(etudiant.id)
        etudiants_data.append({
            'etudiant': etudiant,
            'active_affectation': active_aff,
            'is_abonne': active_aff is not None,
        })

    lignes = Ligne.objects.order_by('nom_ligne')

    nb_total = len(etudiants_data)
    nb_abonnes = sum(1 for item in etudiants_data if item['is_abonne'])
    nb_non_abonnes = nb_total - nb_abonnes

    return render(request, 'gestion_transport/etudiants_par_ligne.html', {
        'etudiants_data': etudiants_data,
        'lignes': lignes,
        'nb_total': nb_total,
        'nb_abonnes': nb_abonnes,
        'nb_non_abonnes': nb_non_abonnes,
        'selected_ligne_id': selected_ligne_id,
        'selected_statut': selected_statut,
        'query': query,
        'generic_page': True,
    })


def liste_conducteurs(request):
    """Liste des conducteurs avec leurs bus et lignes associées."""
    query = request.GET.get('q', '').strip()
    selected_statut = request.GET.get('statut', '').strip()

    conducteurs_qs = Conducteur.objects.all().order_by('nom', 'prenom')

    if query:
        conducteurs_qs = conducteurs_qs.filter(
            Q(driver_id__icontains=query)
            | Q(nom__icontains=query)
            | Q(prenom__icontains=query)
            | Q(email__icontains=query)
            | Q(telephone__icontains=query)
        )

    if selected_statut == 'avec_telephone':
        conducteurs_qs = conducteurs_qs.exclude(telephone='')
    elif selected_statut == 'sans_telephone':
        conducteurs_qs = conducteurs_qs.filter(telephone='')

    conducteurs_data = []
    for conducteur in conducteurs_qs:
            # Récupérer les buses via deux voies: Bus.conducteur directe OU AffectationBusLigne.conducteur
            buses_direct_qs = conducteur.buses.all()  # Via Bus.conducteur FK
            buses_via_affectation_qs = Bus.objects.filter(
                affectationbusligne__conducteur=conducteur
            ).distinct()  # Via AffectationBusLigne.conducteur
            # Combiner les deux ensembles de buses en utilisant les IDs
            buses_direct_ids = set(buses_direct_qs.values_list('id', flat=True))
            buses_affectation_ids = set(buses_via_affectation_qs.values_list('id', flat=True))
            all_buses_ids = buses_direct_ids | buses_affectation_ids
            buses_combined = Bus.objects.filter(id__in=all_buses_ids) if all_buses_ids else Bus.objects.none()
            bus_count = len(all_buses_ids)
        
            # Récupérer les lignes associées à ces buses
            lignes_combined = Ligne.objects.filter(
                affectationbusligne__bus__in=buses_combined
            ).distinct() if buses_combined.exists() else Ligne.objects.none()
            lignes_count = lignes_combined.count()
        
            conducteurs_data.append({
                'conducteur': conducteur,
                    'buses': list(buses_combined),
                'bus_count': bus_count,
                'lignes_count': lignes_count,
                'lignes': list(lignes_combined),
            })

    nb_total = len(conducteurs_data)
    nb_avec_telephone = sum(1 for item in conducteurs_data if item['conducteur'].telephone)
    nb_sans_telephone = nb_total - nb_avec_telephone

    return render(request, 'gestion_transport/driver_liste.html', {
        'conducteurs_data': conducteurs_data,
        'nb_total': nb_total,
        'nb_avec_telephone': nb_avec_telephone,
        'nb_sans_telephone': nb_sans_telephone,
        'selected_statut': selected_statut,
        'query': query,
        'generic_page': True
    })


@login_required(login_url='gestion_transport:admin_login')
@user_passes_test(lambda u: u.is_staff, login_url='gestion_transport:admin_login')
def edit_conducteur(request, conducteur_id):
    """Modification d'un conducteur."""
    try:
        conducteur = Conducteur.objects.get(id=conducteur_id)
    except Conducteur.DoesNotExist:
        return redirect('gestion_transport:liste_conducteurs')

    if request.method == 'POST':
        form = ConducteurEditForm(request.POST, instance=conducteur)
        if form.is_valid():
            conducteur = form.save()
            _log_modification(
                request,
                'modification',
                'Conducteur',
                f"Conducteur {conducteur.driver_id} modifié ({conducteur.prenom} {conducteur.nom})."
            )
            messages.success(request, f"Conducteur {conducteur.driver_id} modifié avec succès.")
            return redirect('gestion_transport:liste_conducteurs')
    else:
        form = ConducteurEditForm(instance=conducteur)

    return render(request, 'gestion_transport/conducteur_form.html', {
        'form': form,
        'title': 'Modifier un conducteur',
        'is_edit': True,
        'generic_page': True,
    })


@login_required(login_url='gestion_transport:admin_login')
@user_passes_test(lambda u: u.is_staff, login_url='gestion_transport:admin_login')
def delete_conducteur(request, conducteur_id):
    """Suppression d'un conducteur."""
    try:
        conducteur = Conducteur.objects.get(id=conducteur_id)
    except Conducteur.DoesNotExist:
        return redirect('gestion_transport:liste_conducteurs')

    if request.method != 'POST':
        return redirect('gestion_transport:liste_conducteurs')

    driver_id = conducteur.driver_id
    full_name = f"{conducteur.prenom} {conducteur.nom}"

    Bus.objects.filter(conducteur=conducteur).update(conducteur=None)
    conducteur.delete()

    _log_modification(
        request,
        'suppression',
        'Conducteur',
        f"Conducteur {driver_id} supprimé ({full_name})."
    )
    messages.success(request, f"Conducteur {driver_id} supprimé avec succès.")
    return redirect('gestion_transport:liste_conducteurs')


@login_required(login_url='gestion_transport:admin_login')
@user_passes_test(lambda u: u.is_staff, login_url='gestion_transport:admin_login')
def edit_etudiant(request, etudiant_id):
    """Modification d'un étudiant."""
    try:
        etudiant = Etudiant.objects.get(id=etudiant_id)
    except Etudiant.DoesNotExist:
        return redirect('gestion_transport:etudiants_par_ligne')

    if request.method == 'POST':
        form = EtudiantEditForm(request.POST, instance=etudiant)
        if form.is_valid():
            etudiant = form.save()
            _log_modification(
                request,
                'modification',
                'Étudiant',
                f"Étudiant {etudiant.student_number} modifié ({etudiant.prenom} {etudiant.nom})."
            )
            messages.success(request, f"Étudiant {etudiant.student_number} modifié avec succès.")
            return redirect('gestion_transport:etudiants_par_ligne')
    else:
        form = EtudiantEditForm(instance=etudiant)

    return render(request, 'gestion_transport/etudiant_form.html', {
        'form': form,
        'etudiant': etudiant,
        'is_edit': True,
        'generic_page': True,
    })


@login_required(login_url='gestion_transport:admin_login')
@user_passes_test(lambda u: u.is_staff, login_url='gestion_transport:admin_login')
def delete_etudiant(request, etudiant_id):
    """Suppression d'un étudiant."""
    try:
        etudiant = Etudiant.objects.get(id=etudiant_id)
    except Etudiant.DoesNotExist:
        return redirect('gestion_transport:etudiants_par_ligne')

    if request.method != 'POST':
        return redirect('gestion_transport:etudiants_par_ligne')

    student_number = etudiant.student_number
    full_name = f"{etudiant.prenom} {etudiant.nom}"
    etudiant.delete()

    _log_modification(
        request,
        'suppression',
        'Étudiant',
        f"Étudiant {student_number} supprimé ({full_name})."
    )
    messages.success(request, f"Étudiant {student_number} supprimé avec succès.")
    return redirect('gestion_transport:etudiants_par_ligne')


def taux_remplissage_bus(request):
    """Taux de remplissage des bus"""
    # Pour simplifier, calcul basé sur les affectations actives
    bus_stats = []
    bus_list = Bus.objects.all()

    period_days_raw = request.GET.get('period_days', '30').strip()
    selected_ligne_id = request.GET.get('incident_ligne_id', '').strip()
    selected_incident_type = request.GET.get('incident_type', '').strip()
    retard_min_raw = request.GET.get('retard_min', '').strip()

    period_options = [7, 30, 90, 180, 365]
    try:
        selected_period_days = int(period_days_raw)
    except (TypeError, ValueError):
        selected_period_days = 30
    if selected_period_days not in period_options:
        selected_period_days = 30

    selected_retard_min = None
    if retard_min_raw:
        try:
            parsed_retard_min = int(retard_min_raw)
            if parsed_retard_min >= 0:
                selected_retard_min = parsed_retard_min
        except (TypeError, ValueError):
            selected_retard_min = None

    period_start = date.today() - timedelta(days=selected_period_days)

    for bus in bus_list:
        lignes_actives = AffectationBusLigne.objects.filter(
            Q(bus=bus) & Q(date_debut__lte=date.today()) & (Q(date_fin__isnull=True) | Q(date_fin__gte=date.today()))
        )

        if lignes_actives.exists():
            ligne = lignes_actives.first().ligne
            etudiants_ligne = AffectationEtudiantLigne.objects.filter(
                Q(ligne=ligne) & Q(date_debut__lte=date.today()) & (Q(date_fin__isnull=True) | Q(date_fin__gte=date.today()))
            ).count()

            taux = min((etudiants_ligne / bus.capacite) * 100, 100) if bus.capacite > 0 else 0

            bus_stats.append({
                'bus': bus,
                'ligne': ligne,
                'capacite': bus.capacite,
                'etudiants': etudiants_ligne,
                'taux': round(taux, 2)
            })

    bus_stats.sort(key=lambda x: x['taux'], reverse=True)

    incidents_30_qs = Incident.objects.filter(date_heure_incident__date__gte=period_start)
    trajets_retard_30_qs = Trajet.objects.filter(
        date_trajet__gte=period_start,
        retard_minutes__gt=0,
    )
    trajets_period_qs = Trajet.objects.filter(
        date_trajet__gte=period_start,
    ).select_related('ligne', 'bus', 'horaire').order_by('-date_trajet', '-horaire__heure_depart')

    if selected_ligne_id:
        incidents_30_qs = incidents_30_qs.filter(trajet__ligne_id=selected_ligne_id)
        trajets_retard_30_qs = trajets_retard_30_qs.filter(ligne_id=selected_ligne_id)
        trajets_period_qs = trajets_period_qs.filter(ligne_id=selected_ligne_id)

    incident_type_options = list(
        incidents_30_qs
        .exclude(type_incident='')
        .values_list('type_incident', flat=True)
        .distinct()
        .order_by('type_incident')
    )

    if selected_incident_type:
        incidents_30_qs = incidents_30_qs.filter(type_incident=selected_incident_type)

    if selected_retard_min is not None:
        trajets_retard_30_qs = trajets_retard_30_qs.filter(retard_minutes__gte=selected_retard_min)

    trajets_period = list(trajets_period_qs)
    suivis_map = {
        suivi.trajet_id: suivi
        for suivi in SuiviTrajetConducteur.objects.filter(trajet_id__in=[t.id for t in trajets_period])
    }

    today_local = date.today()
    now_time_local = datetime.now().time()

    trajets_a_temps_recents = []
    for trajet in trajets_period:
        if trajet.retard_minutes > 0:
            continue

        suivi_obj = suivis_map.get(trajet.id)
        depart_a_l_heure_ou_avant = False
        if suivi_obj and suivi_obj.depart_effectif:
            depart_date = suivi_obj.depart_effectif.date()
            depart_time = suivi_obj.depart_effectif.time()
            depart_a_l_heure_ou_avant = (
                depart_date < trajet.date_trajet
                or (depart_date == trajet.date_trajet and depart_time <= trajet.horaire.heure_depart)
            )

        statut_passe_sans_retard = (
            trajet.date_trajet < today_local
            or (trajet.date_trajet == today_local and trajet.horaire.heure_depart <= now_time_local)
        )

        if depart_a_l_heure_ou_avant or statut_passe_sans_retard:
            trajets_a_temps_recents.append(trajet)

    incidents_count_30 = incidents_30_qs.count()
    retards_count_30 = trajets_retard_30_qs.count()
    trajets_a_temps_count_30 = len(trajets_a_temps_recents)
    retard_total_minutes = trajets_retard_30_qs.aggregate(total=Sum('retard_minutes'))['total'] or 0
    retard_avg_minutes = trajets_retard_30_qs.aggregate(avg=Avg('retard_minutes'))['avg'] or 0

    top_lignes_incidents = list(
        incidents_30_qs
        .values('trajet__ligne__nom_ligne')
        .annotate(nb=Count('id'))
        .order_by('-nb')[:5]
    )
    top_lignes_retards = list(
        trajets_retard_30_qs
        .values('ligne__nom_ligne')
        .annotate(nb=Count('id'), avg_retard=Avg('retard_minutes'))
        .order_by('-nb', '-avg_retard')[:5]
    )
    incidents_recents = list(
        incidents_30_qs
        .select_related('trajet__ligne', 'trajet__bus')
        .order_by('-date_heure_incident')[:6]
    )
    trajets_retardes_recents = list(
        trajets_retard_30_qs
        .select_related('ligne', 'bus', 'horaire')
        .order_by('-date_trajet', '-horaire__heure_depart')[:6]
    )
    trajets_a_temps_recents = trajets_a_temps_recents[:6]

    return render(request, 'gestion_transport/remplissage_bus.html', {
        'bus_stats': bus_stats,
        'incidents_count_30': incidents_count_30,
        'retards_count_30': retards_count_30,
        'trajets_a_temps_count_30': trajets_a_temps_count_30,
        'retard_total_minutes': retard_total_minutes,
        'retard_avg_minutes': retard_avg_minutes,
        'top_lignes_incidents': top_lignes_incidents,
        'top_lignes_retards': top_lignes_retards,
        'incidents_recents': incidents_recents,
        'trajets_retardes_recents': trajets_retardes_recents,
        'trajets_a_temps_recents': trajets_a_temps_recents,
        'period_start': period_start,
        'period_options': period_options,
        'selected_period_days': selected_period_days,
        'selected_ligne_id': selected_ligne_id,
        'incident_type_options': incident_type_options,
        'selected_incident_type': selected_incident_type,
        'selected_retard_min': selected_retard_min,
        'lignes': Ligne.objects.order_by('nom_ligne'),
        'generic_page': True
    })

def horaires_ligne(request, ligne_id=None):
    """Horaires d'une ligne donnée"""
    selected_ligne_id = request.GET.get('ligne_id')
    if selected_ligne_id:
        ligne_id = selected_ligne_id

    edit_id = request.GET.get('edit_id')
    ligne = None
    horaires = []
    horaires_aller = []
    horaires_retour = []
    editing_horaire = None
    horaire_form = None
    horaire_pair_form = None
    sens_label_aller = "Point A -> Point B"
    sens_label_retour = "Point B -> Point A"

    if ligne_id:
        try:
            ligne = Ligne.objects.get(id=ligne_id)
        except Ligne.DoesNotExist:
            ligne = None

    if ligne:
        sens_label_aller, sens_label_retour = _extract_direction_labels(ligne)

    if edit_id and ligne:
        try:
            editing_horaire = Horaire.objects.get(id=edit_id, ligne=ligne)
        except Horaire.DoesNotExist:
            editing_horaire = None

    def _build_pair_initial(horaire):
        if not horaire:
            return None

        counterpart = Horaire.objects.filter(
            ligne=horaire.ligne,
            jour_semaine=horaire.jour_semaine,
        ).exclude(id=horaire.id)

        if horaire.sens == 'aller':
            counterpart = counterpart.filter(sens='retour')
        else:
            counterpart = counterpart.filter(sens='aller')

        counterpart = counterpart.order_by('heure_depart', 'id').first()

        return {
            'jour_semaine': horaire.jour_semaine,
            'heure_depart_aller': horaire.heure_depart if horaire.sens == 'aller' else (counterpart.heure_depart if counterpart else None),
            'heure_depart_retour': horaire.heure_depart if horaire.sens == 'retour' else (counterpart.heure_depart if counterpart else None),
        }

    if request.method == 'POST':
        action = request.POST.get('action', 'create')
        posted_ligne_id = request.POST.get('ligne_id')
        if posted_ligne_id and ligne is None:
            try:
                ligne = Ligne.objects.get(id=posted_ligne_id)
            except Ligne.DoesNotExist:
                ligne = None

        if ligne:
            sens_label_aller, sens_label_retour = _extract_direction_labels(ligne)

        if action == 'delete' and ligne:
            horaire_id = request.POST.get('horaire_id')
            if horaire_id:
                try:
                    horaire = Horaire.objects.get(id=horaire_id, ligne=ligne)
                    horaire.delete()
                    messages.success(request, "Horaire supprimé avec succès.")
                except Horaire.DoesNotExist:
                    messages.error(request, "Horaire introuvable.")
            return redirect('gestion_transport:horaires_ligne_detail', ligne_id=ligne.id)

        if action == 'start_edit' and ligne:
            horaire_id = request.POST.get('horaire_id')
            if horaire_id:
                return redirect(f"{redirect('gestion_transport:horaires_ligne_detail', ligne_id=ligne.id).url}?edit_id={horaire_id}")

        if action == 'update' and ligne:
            horaire_id = request.POST.get('editing_horaire_id')
            if horaire_id:
                try:
                    editing_horaire = Horaire.objects.get(id=horaire_id, ligne=ligne)
                except Horaire.DoesNotExist:
                    editing_horaire = None

            if editing_horaire is None:
                messages.error(request, "Horaire à modifier introuvable.")
                return redirect('gestion_transport:horaires_ligne_detail', ligne_id=ligne.id)

            horaire_pair_form = HorairePairForm(request.POST)

            if horaire_pair_form.is_valid():
                cleaned = horaire_pair_form.cleaned_data

                if editing_horaire.sens == 'aller':
                    aller_depart = cleaned['heure_depart_aller']
                    retour_depart = cleaned['heure_depart_retour']
                else:
                    aller_depart = cleaned['heure_depart_aller']
                    retour_depart = cleaned['heure_depart_retour']

                counterpart = Horaire.objects.filter(
                    ligne=ligne,
                    jour_semaine=editing_horaire.jour_semaine,
                ).exclude(id=editing_horaire.id)
                if editing_horaire.sens == 'aller':
                    counterpart = counterpart.filter(sens='retour')
                else:
                    counterpart = counterpart.filter(sens='aller')
                counterpart = counterpart.order_by('heure_depart', 'id').first()

                editing_horaire.jour_semaine = cleaned['jour_semaine']
                editing_horaire.heure_depart = aller_depart if editing_horaire.sens == 'aller' else retour_depart
                editing_horaire.save()

                if counterpart:
                    counterpart.jour_semaine = cleaned['jour_semaine']
                    counterpart.heure_depart = retour_depart if editing_horaire.sens == 'aller' else aller_depart
                    counterpart.save()
                else:
                    Horaire.objects.create(
                        ligne=ligne,
                        jour_semaine=cleaned['jour_semaine'],
                        sens='retour' if editing_horaire.sens == 'aller' else 'aller',
                        heure_depart=retour_depart if editing_horaire.sens == 'aller' else aller_depart,
                    )

                messages.success(request, "Paire d'horaires modifiée avec succès.")
                return redirect('gestion_transport:horaires_ligne_detail', ligne_id=ligne.id)

            messages.error(request, "Impossible de modifier la paire d'horaires. Vérifiez les champs saisis.")
        else:
            horaire_pair_form = HorairePairForm(request.POST)

            if ligne and horaire_pair_form.is_valid():
                cleaned = horaire_pair_form.cleaned_data
                Horaire.objects.create(
                    ligne=ligne,
                    jour_semaine=cleaned['jour_semaine'],
                    sens='aller',
                    heure_depart=cleaned['heure_depart_aller'],
                )
                Horaire.objects.create(
                    ligne=ligne,
                    jour_semaine=cleaned['jour_semaine'],
                    sens='retour',
                    heure_depart=cleaned['heure_depart_retour'],
                )
                messages.success(request, "Paire d'horaires ajoutée avec succès.")
                return redirect('gestion_transport:horaires_ligne_detail', ligne_id=ligne.id)

            if ligne:
                messages.error(request, "Impossible d'ajouter la paire d'horaires. Vérifiez les champs saisis.")
    else:
        if editing_horaire is not None:
            horaire_pair_form = HorairePairForm(initial=_build_pair_initial(editing_horaire))
        else:
            horaire_pair_form = HorairePairForm()

    if ligne:
        horaires = Horaire.objects.filter(ligne=ligne).order_by('jour_semaine', 'sens', 'heure_depart')
        horaires_aller = horaires.filter(sens='aller')
        horaires_retour = horaires.filter(sens='retour')
        horaires_groupes = []
        for jour_value, jour_label in Horaire.JOURS_SEMAINE:
            horaires_jour = horaires.filter(jour_semaine=jour_value)
            horaires_groupes.append({
                'jour_value': jour_value,
                'jour_label': jour_label,
                'aller': list(horaires_jour.filter(sens='aller')),
                'retour': list(horaires_jour.filter(sens='retour')),
            })
        horaires_groupes = [g for g in horaires_groupes if g['aller'] or g['retour']]

    lignes = Ligne.objects.all()

    return render(request, 'gestion_transport/horaires_ligne.html', {
        'ligne': ligne,
        'horaires': horaires,
        'horaires_aller': horaires_aller,
        'horaires_retour': horaires_retour,
        'horaires_groupes': horaires_groupes if ligne else [],
        'horaire_form': horaire_form,
        'horaire_pair_form': horaire_pair_form,
        'editing_horaire': editing_horaire,
        'sens_label_aller': sens_label_aller,
        'sens_label_retour': sens_label_retour,
        'selected_ligne': ligne,
        'lignes': lignes,
        'generic_page': True
    })

def etudiants_sans_abonnement(request):
    """Vue retirée en douceur: redirection vers la liste consolidée des étudiants."""
    messages.info(request, "La vue 'Étudiants sans abonnement' n'est plus disponible. Utilisez la liste complète des étudiants.")
    return redirect('gestion_transport:etudiants_par_ligne')

def historique_etudiant(request, etudiant_id=None):
    """Historique des affectations d'un étudiant"""
    if etudiant_id:
        etudiant = Etudiant.objects.get(id=etudiant_id)
        affectations = AffectationEtudiantLigne.objects.filter(
            etudiant=etudiant
        ).select_related('ligne').order_by('-date_debut')
    else:
        etudiant = None
        affectations = []

    etudiants = Etudiant.objects.all()

    return render(request, 'gestion_transport/historique_etudiant.html', {
        'etudiant': etudiant,
        'affectations': affectations,
        'etudiants': etudiants,
        'generic_page': True
    })

def bus_affectes_ligne_date(request):
    """Bus affectés à une ligne à une date donnée"""
    ligne_id = request.GET.get('ligne_id')
    date_str = request.GET.get('date')

    bus_affectes = []
    if ligne_id and date_str:
        try:
            ligne = Ligne.objects.get(id=ligne_id)
            date_obj = date.fromisoformat(date_str)
            bus_affectes = AffectationBusLigne.objects.filter(
                Q(ligne=ligne) & Q(date_debut__lte=date_obj) & (Q(date_fin__isnull=True) | Q(date_fin__gte=date_obj))
            ).select_related('bus')
        except (ValueError, Ligne.DoesNotExist):
            ligne = None
    else:
        ligne = None

    lignes = Ligne.objects.all()

    return render(request, 'gestion_transport/bus_affectes.html', {
        'bus_affectes': bus_affectes,
        'lignes': lignes,
        'selected_ligne': ligne,
        'selected_date': date_str,
        'generic_page': True
    })

def lignes_plus_chargees(request):
    """Lignes les plus chargées"""
    lignes = Ligne.objects.annotate(
        nombre_etudiants=Count(
            'affectationetudiantligne',
            filter=Q(affectationetudiantligne__date_fin__isnull=True)
        )
    ).filter(nombre_etudiants__gt=0).order_by('-nombre_etudiants')[:10]

    return render(request, 'gestion_transport/lignes_chargees.html', {
        'lignes': lignes,
        'generic_page': True
    })

def liste_lignes(request):
    """Liste de toutes les lignes avec leurs informations et filtres"""
    # Récupérer les paramètres de filtrage
    statut = request.GET.get('statut')  # 'active', 'inactive', or ''
    etudiants_min = request.GET.get('etudiants_min')
    description_filter = request.GET.get('description')

    # Récupérer toutes les lignes par défaut
    lignes_queryset = Ligne.objects.all()

    # Appliquer les filtres
    if description_filter:
        lignes_queryset = lignes_queryset.filter(description__icontains=description_filter)

    if etudiants_min:
        try:
            etudiants_min_int = int(etudiants_min)
            lignes_queryset = lignes_queryset.annotate(
                nombre_etudiants=Count(
                    'affectationetudiantligne',
                    filter=Q(affectationetudiantligne__date_fin__isnull=True)
                )
            ).filter(nombre_etudiants__gte=etudiants_min_int)
        except ValueError:
            pass

    # Annoter chaque ligne avec des informations supplémentaires
    lignes_data = []
    for ligne in lignes_queryset:
        # Compter les étudiants actifs
        nombre_etudiants = AffectationEtudiantLigne.objects.filter(
            Q(ligne=ligne) & Q(date_fin__isnull=True)
        ).count()

        # Compter les bus actuellement affectés à la ligne
        nombre_bus = AffectationBusLigne.objects.filter(
            ligne=ligne,
           
        ).filter(
            Q(date_fin__isnull=True) | Q(date_fin__gte=date.today())
        ).values('bus_id').distinct().count()

        # Trajets programmés futurs de la ligne dont le bus est bien affecté à cette ligne à la date du trajet
        trajets_ligne = Trajet.objects.filter(
            ligne=ligne,
            date_trajet__gte=date.today(),
            bus__affectationbusligne__ligne=ligne,
            bus__affectationbusligne__date_debut__lte=F('date_trajet'),
        ).filter(
            Q(bus__affectationbusligne__date_fin__isnull=True) | Q(bus__affectationbusligne__date_fin__gte=F('date_trajet'))
        ).distinct().select_related('bus', 'horaire').order_by('date_trajet', 'horaire__heure_depart', 'bus__numero_immatriculation')

        groupes_map = {}
        for trajet in trajets_ligne:
            key = (trajet.date_trajet, trajet.horaire_id)
            if key not in groupes_map:
                groupes_map[key] = {
                    'date_trajet': trajet.date_trajet,
                    'horaire': trajet.horaire,
                    'buses': [],
                    'capacite_totale': 0,
                }

            groupes_map[key]['buses'].append(trajet.bus)
            groupes_map[key]['capacite_totale'] += trajet.bus.capacite

        trajets_groupes = []
        for grp in groupes_map.values():
            bus_count = len(grp['buses'])
            estimation_bus_requis = ceil(nombre_etudiants / max(1, grp['capacite_totale'] / max(1, bus_count))) if nombre_etudiants else 0
            trajets_groupes.append({
                'date_trajet': grp['date_trajet'],
                'horaire': grp['horaire'],
                'buses': grp['buses'],
                'bus_count': bus_count,
                'estimation_bus_requis': estimation_bus_requis,
            })

        # Récupérer les horaires
        horaires_count = Horaire.objects.filter(ligne=ligne).count()

        # Déterminer le statut
        is_active = nombre_bus > 0

        # Appliquer le filtre de statut
        if statut == 'active' and not is_active:
            continue
        elif statut == 'inactive' and is_active:
            continue

        lignes_data.append({
            'ligne': ligne,
            'nombre_etudiants': nombre_etudiants,
            'nombre_bus': nombre_bus,
            'nombre_trajets': len(trajets_groupes),
            'trajets_groupes': trajets_groupes,
            'horaires_count': horaires_count,
            'is_active': is_active,
        })

    # Trier par nom de ligne
    lignes_data.sort(key=lambda x: x['ligne'].nom_ligne)

    return render(request, 'gestion_transport/liste_lignes.html', {
        'lignes_data': lignes_data,
        'selected_statut': statut or '',
        'selected_etudiants_min': etudiants_min or '',
        'selected_description': description_filter or '',
        'generic_page': True
    })

def liste_stations(request):
    """Liste de toutes les stations avec leurs coordonnées GPS"""
    # Récupérer les paramètres de filtrage
    nom_filter = request.GET.get('nom')
    adresse_filter = request.GET.get('adresse')
    gps_only = request.GET.get('gps_only')  # 'oui' pour stations avec GPS

    # Récupérer toutes les stations
    stations_queryset = Station.objects.all()

    # Appliquer les filtres
    if nom_filter:
        stations_queryset = stations_queryset.filter(nom_station__icontains=nom_filter)

    if adresse_filter:
        stations_queryset = stations_queryset.filter(adresse__icontains=adresse_filter)

    if gps_only == 'oui':
        stations_queryset = stations_queryset.filter(latitude__isnull=False, longitude__isnull=False)

    # Annoter avec informations supplémentaires
    stations_data = []
    for station in stations_queryset:
        # Compter les lignes utilisant cette station
        lignes_count = LigneStation.objects.filter(station=station).values('ligne').distinct().count()

        # Vérifier si GPS est défini
        has_gps = station.latitude is not None and station.longitude is not None

        stations_data.append({
            'station': station,
            'lignes_count': lignes_count,
            'has_gps': has_gps,
        })

    # Trier par nom de station
    stations_data.sort(key=lambda x: x['station'].nom_station)

    # Compter les stations avec GPS dans l'ensemble des résultats filtrés
    gps_count = sum(1 for station_data in stations_data if station_data['has_gps'])

    return render(request, 'gestion_transport/liste_stations.html', {
        'stations_data': stations_data,
        'gps_count': gps_count,
        'selected_nom': nom_filter or '',
        'selected_adresse': adresse_filter or '',
        'selected_gps_only': gps_only or '',
        'generic_page': True
    })

def liste_bus_affectations(request):
    """Liste de tous les bus avec leurs affectations et filtres"""
    # Récupérer les paramètres de filtrage
    ligne_id = request.GET.get('ligne_id')
    date_str = (request.GET.get('date') or '').strip()
    statut = request.GET.get('statut')  # 'affecte', 'non_affecte', or ''
    marque = request.GET.get('marque')
    capacite_min = request.GET.get('capacite_min')

    # Date par défaut : aujourd'hui. Accepte aussi les formats FR (jj/mm/aaaa, jj-mm-aaaa).
    parsed_date_str = ''
    if date_str:
        date_obj = None
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
            try:
                date_obj = datetime.strptime(date_str, fmt).date()
                parsed_date_str = date_obj.isoformat()
                break
            except ValueError:
                continue
        if date_obj is None:
            date_obj = date.today()
    else:
        date_obj = date.today()

    # Récupérer tous les bus par défaut
    bus_queryset = Bus.objects.all()

    # Appliquer les filtres
    if marque:
        bus_queryset = bus_queryset.filter(marque__icontains=marque)

    if capacite_min:
        try:
            capacite_min_int = int(capacite_min)
            bus_queryset = bus_queryset.filter(capacite__gte=capacite_min_int)
        except ValueError:
            pass

    # Appliquer le filtre date au niveau des bus : afficher uniquement les bus avec une affectation
    # active OU future par rapport à la date sélectionnée.
    date_filter_active = 'date' in request.GET and bool(parsed_date_str)
    if date_filter_active:
        # Affectation active à la date sélectionnée
        affectation_active_filter = Q(
            affectationbusligne__date_debut__lte=date_obj,
            affectationbusligne__date_fin__isnull=True
        ) | Q(
            affectationbusligne__date_debut__lte=date_obj,
            affectationbusligne__date_fin__gte=date_obj
        )
        # Affectation future (commence après la date sélectionnée)
        affectation_future_filter = Q(
            affectationbusligne__date_debut__gt=date_obj
        )
        affectation_date_filter = affectation_active_filter | affectation_future_filter

        if statut == 'non_affecte':
            bus_queryset = bus_queryset.exclude(affectation_date_filter).distinct()
        else:
            bus_queryset = bus_queryset.filter(affectation_date_filter).distinct()

    # Variables pour le contexte du template
    selected_ligne = None
    ligne_affectations = []

    # Récupérer les affectations pour la ligne filtrée si spécifiée
    if ligne_id:
        try:
            selected_ligne = Ligne.objects.get(id=ligne_id)
            # Récupérer tous les bus ayant une affectation sur cette ligne (toute période)
            ligne_affectations = AffectationBusLigne.objects.filter(
                ligne=selected_ligne
            ).values_list('bus_id', flat=True).distinct()

            # Filtrer les bus pour ne garder que ceux affectés à la ligne sélectionnée
            bus_queryset = bus_queryset.filter(id__in=ligne_affectations)
        except Ligne.DoesNotExist:
            selected_ligne = None

    # Récupérer les affectations pour chaque bus à la date donnée
    bus_affectations = []
    for bus in bus_queryset:
        all_affectations = list(
            AffectationBusLigne.objects.filter(bus=bus).select_related('ligne', 'conducteur').order_by('-date_debut')
        )

        # Trouver l'affectation active pour ce bus à la date donnée
        affectation_active = AffectationBusLigne.objects.filter(
            Q(bus=bus) &
            Q(date_debut__lte=date_obj) &
            (Q(date_fin__isnull=True) | Q(date_fin__gte=date_obj))
        ).select_related('ligne', 'conducteur').first()

        # Vérifier s'il y a des affectations futures
        affectation_future = AffectationBusLigne.objects.filter(
            Q(bus=bus) &
            Q(date_debut__gt=date_obj)
        ).select_related('ligne', 'conducteur').first()

        # Déterminer le statut du bus
        if affectation_active:
            statut_bus = 'affecte'
            affectation = affectation_active
            bus_ligne = affectation_active.ligne
        elif affectation_future:
            statut_bus = 'affecte_futur'
            affectation = affectation_future
            bus_ligne = affectation_future.ligne
        else:
            statut_bus = 'non_affecte'
            affectation = None
            bus_ligne = None

        # Appliquer le filtre de statut
        if statut == 'affecte' and statut_bus != 'affecte':
            continue
        elif statut == 'non_affecte' and statut_bus == 'affecte':
            continue

        # Vérifier si ce bus est affecté à la ligne filtrée
        is_affecte_a_ligne = bus.id in ligne_affectations if ligne_affectations else False

        affectations_details = []
        for aff in all_affectations:
            trajets_aff_qs = Trajet.objects.filter(
                bus=bus,
                ligne=aff.ligne,
                date_trajet__gte=aff.date_debut,
            )
            if aff.date_fin:
                trajets_aff_qs = trajets_aff_qs.filter(date_trajet__lte=aff.date_fin)

            if aff.date_debut <= date_obj and (aff.date_fin is None or aff.date_fin >= date_obj):
                statut_affectation = 'active'
            elif aff.date_debut > date_obj:
                statut_affectation = 'future'
            else:
                statut_affectation = 'passee'

            affectations_details.append({
                'id': aff.id,
                'ligne_nom': aff.ligne.nom_ligne,
                'conducteur_nom': f"{aff.conducteur.prenom} {aff.conducteur.nom}" if aff.conducteur else '',
                'date_debut': aff.date_debut,
                'date_fin': aff.date_fin,
                'trajets_count': trajets_aff_qs.count(),
                'statut': statut_affectation,
            })

        # Résumé des trajets pour l'affectation active/future principale
        resume_trajets_count = 0
        resume_prochain_trajet = None
        if affectation and bus_ligne:
            trajets_qs = Trajet.objects.filter(
                bus=bus,
                ligne=bus_ligne,
                date_trajet__gte=date_obj,
            ).select_related('ligne', 'horaire').order_by('date_trajet', 'horaire__heure_depart')

            resume_trajets_count = trajets_qs.count()
            prochain_trajet_obj = trajets_qs.first()
            if prochain_trajet_obj:
                resume_prochain_trajet = {
                    'date_trajet': prochain_trajet_obj.date_trajet,
                    'heure_depart': prochain_trajet_obj.horaire.heure_depart.strftime('%H:%M'),
                    'heure_arrivee': prochain_trajet_obj.horaire.heure_arrivee.strftime('%H:%M'),
                    'sens': prochain_trajet_obj.horaire.get_sens_display(),
                }

        bus_affectations.append({
            'bus': bus,
            'affectation': affectation,
            'current_conducteur': affectation.conducteur if affectation else None,
            'ligne': bus_ligne,
            'date_debut': affectation.date_debut if affectation else None,
            'date_fin': affectation.date_fin if affectation else None,
            'statut_bus': statut_bus,
            'is_affecte_a_ligne': is_affecte_a_ligne,
            'affectations_details': affectations_details,
            'prochains_trajets_count': resume_trajets_count,
            'prochain_trajet': resume_prochain_trajet,
        })

    # Trier par numéro d'immatriculation
    bus_affectations.sort(key=lambda x: x['bus'].numero_immatriculation)

    # Récupérer toutes les lignes pour le filtre
    lignes = Ligne.objects.all()

    # Récupérer les marques distinctes pour le filtre
    marques = Bus.objects.values_list('marque', flat=True).distinct().exclude(marque__isnull=True).exclude(marque='')

    # Compter les bus non affectés pour afficher la section d'affectation en masse
    # Vérifier indépendamment des filtres appliqués
    has_unassigned_buses = Bus.objects.exclude(
        Q(affectationbusligne__date_debut__lte=date_obj) &
        (Q(affectationbusligne__date_fin__isnull=True) | Q(affectationbusligne__date_fin__gte=date_obj))
    ).exists()

    # Statistiques pour l'affichage
    nb_total = len(bus_affectations)
    nb_affectes = sum(1 for x in bus_affectations if x['statut_bus'] == 'affecte')
    nb_futurs = sum(1 for x in bus_affectations if x['statut_bus'] == 'affecte_futur')
    nb_non_affectes = sum(1 for x in bus_affectations if x['statut_bus'] == 'non_affecte')

    return render(request, 'gestion_transport/liste_bus_affectations.html', {
        'bus_affectations': bus_affectations,
        'lignes': lignes,
        'marques': marques,
        'selected_ligne': selected_ligne,
        'selected_date': parsed_date_str,
        'selected_statut': statut or '',
        'selected_marque': marque or '',
        'selected_capacite_min': capacite_min or '',
        'has_unassigned_buses': has_unassigned_buses,
        'nb_total': nb_total,
        'nb_affectes': nb_affectes,
        'nb_futurs': nb_futurs,
        'nb_non_affectes': nb_non_affectes,
        'generic_page': True
    })


@login_required(login_url='gestion_transport:admin_login')
@user_passes_test(lambda u: u.is_staff, login_url='gestion_transport:admin_login')
def edit_trajet(request, trajet_id):
    """Modifier un trajet depuis la vue détaillée du bus."""
    try:
        trajet = Trajet.objects.select_related('bus', 'ligne', 'horaire').get(id=trajet_id)
    except Trajet.DoesNotExist:
        messages.error(request, "Trajet introuvable.")
        return redirect('gestion_transport:liste_bus_affectations')

    if trajet.date_trajet < date.today():
        messages.error(request, "Impossible de modifier un trajet passé.")
        return redirect('gestion_transport:bus_trajets', bus_id=trajet.bus_id)

    if request.method == 'POST':
        form = TrajetEditForm(request.POST, instance=trajet)
        if form.is_valid():
            trajet_updated = form.save(commit=False)
            try:
                trajet_updated.full_clean()
                trajet_updated.save()
                _log_modification(
                    request,
                    'modification',
                    'Trajet',
                    f"Trajet modifié: bus {trajet.bus.numero_immatriculation}, ligne {trajet.ligne.nom_ligne}, date {trajet_updated.date_trajet}."
                )
                messages.success(request, "Trajet modifié avec succès.")
                return redirect('gestion_transport:bus_trajets', bus_id=trajet.bus_id)
            except ValidationError as e:
                form.add_error(None, e)
    else:
        form = TrajetEditForm(instance=trajet)

    return render(request, 'gestion_transport/edit_trajet.html', {
        'form': form,
        'trajet': trajet,
        'bus': trajet.bus,
        'title': 'Modifier un trajet',
        'generic_page': True,
    })


@login_required(login_url='gestion_transport:admin_login')
@user_passes_test(lambda u: u.is_staff, login_url='gestion_transport:admin_login')
def delete_trajet(request, trajet_id):
    """Supprimer un trajet avec écran de confirmation."""
    try:
        trajet = Trajet.objects.select_related('bus', 'ligne', 'horaire').get(id=trajet_id)
    except Trajet.DoesNotExist:
        messages.error(request, "Trajet introuvable.")
        return redirect('gestion_transport:liste_bus_affectations')

    if trajet.date_trajet < date.today():
        messages.error(request, "Impossible de supprimer un trajet passé.")
        return redirect('gestion_transport:bus_trajets', bus_id=trajet.bus_id)

    reservations_count = ReservationTrajet.objects.filter(trajet=trajet).count()
    incidents_count = Incident.objects.filter(trajet=trajet).count()

    if request.method == 'POST':
        bus_id = trajet.bus_id
        trajet_info = f"bus {trajet.bus.numero_immatriculation}, ligne {trajet.ligne.nom_ligne}, date {trajet.date_trajet}"
        trajet.delete()
        _log_modification(
            request,
            'suppression',
            'Trajet',
            f"Trajet supprimé: {trajet_info}."
        )
        messages.success(request, "Trajet supprimé avec succès.")
        return redirect('gestion_transport:bus_trajets', bus_id=bus_id)

    return render(request, 'gestion_transport/delete_trajet.html', {
        'trajet': trajet,
        'bus': trajet.bus,
        'reservations_count': reservations_count,
        'incidents_count': incidents_count,
        'title': 'Supprimer un trajet',
        'generic_page': True,
    })


@login_required(login_url='gestion_transport:admin_login')
@user_passes_test(lambda u: u.is_staff, login_url='gestion_transport:admin_login')
def bus_trajets(request, bus_id):
    """Vue dédiée aux trajets d'un bus avec filtres ergonomiques."""
    try:
        bus = Bus.objects.get(id=bus_id)
    except Bus.DoesNotExist:
        messages.error(request, "Bus introuvable.")
        return redirect('gestion_transport:liste_bus_affectations')

    selected_ligne_id = request.GET.get('ligne_id', '')
    selected_date_debut = request.GET.get('date_debut', '')
    selected_date_fin = request.GET.get('date_fin', '')
    selected_periode = request.GET.get('periode', '')
    export_format = request.GET.get('export', '')

    trajets_qs = Trajet.objects.filter(bus=bus).select_related('ligne', 'horaire').order_by(
        'ligne__nom_ligne', 'date_trajet', 'horaire__heure_depart'
    )

    if selected_ligne_id:
        try:
            trajets_qs = trajets_qs.filter(ligne_id=int(selected_ligne_id))
        except ValueError:
            selected_ligne_id = ''

    # Les filtres rapides pilotent automatiquement la plage de dates.
    if selected_periode in {'today', 'week', 'month'}:
        today = date.today()
        if selected_periode == 'today':
            date_debut, date_fin = today, today
        elif selected_periode == 'week':
            date_debut = today - timedelta(days=today.weekday())
            date_fin = date_debut + timedelta(days=6)
        else:
            date_debut = today.replace(day=1)
            date_fin = (date_debut.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

        trajets_qs = trajets_qs.filter(date_trajet__gte=date_debut, date_trajet__lte=date_fin)
        selected_date_debut = date_debut.isoformat()
        selected_date_fin = date_fin.isoformat()

    if selected_date_debut:
        try:
            date_debut = datetime.strptime(selected_date_debut, '%Y-%m-%d').date()
            trajets_qs = trajets_qs.filter(date_trajet__gte=date_debut)
        except ValueError:
            selected_date_debut = ''

    if selected_date_fin:
        try:
            date_fin = datetime.strptime(selected_date_fin, '%Y-%m-%d').date()
            trajets_qs = trajets_qs.filter(date_trajet__lte=date_fin)
        except ValueError:
            selected_date_fin = ''

    if export_format == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="trajets_bus_{bus.numero_immatriculation}.csv"'

        writer = csv.writer(response)
        writer.writerow(['Bus', 'Ligne', 'Date', 'Depart', 'Arrivee', 'Sens', 'Retard (minutes)'])
        for trajet in trajets_qs:
            writer.writerow([
                bus.numero_immatriculation,
                trajet.ligne.nom_ligne,
                trajet.date_trajet.isoformat(),
                trajet.horaire.heure_depart.strftime('%H:%M'),
                trajet.horaire.heure_arrivee.strftime('%H:%M'),
                trajet.horaire.get_sens_display(),
                trajet.retard_minutes,
            ])

        return response

    trajets_par_ligne = []
    lignes_map = {}
    for trajet in trajets_qs:
        ligne_id = trajet.ligne_id
        if ligne_id not in lignes_map:
            lignes_map[ligne_id] = {
                'ligne_nom': trajet.ligne.nom_ligne,
                'dates': [],
                '_dates_map': {},
                'total_trajets': 0,
            }
            trajets_par_ligne.append(lignes_map[ligne_id])

        ligne_group = lignes_map[ligne_id]
        if trajet.date_trajet not in ligne_group['_dates_map']:
            date_group = {
                'date_trajet': trajet.date_trajet,
                'trajets': [],
            }
            ligne_group['_dates_map'][trajet.date_trajet] = date_group
            ligne_group['dates'].append(date_group)

        ligne_group['_dates_map'][trajet.date_trajet]['trajets'].append(trajet)
        ligne_group['total_trajets'] += 1

    for ligne_group in trajets_par_ligne:
        ligne_group.pop('_dates_map', None)

    lignes_bus = Ligne.objects.filter(trajet__bus=bus).distinct().order_by('nom_ligne')
    total_retards_bus = trajets_qs.filter(retard_minutes__gt=0).count()

    base_params = {}
    if selected_ligne_id:
        base_params['ligne_id'] = str(selected_ligne_id)
    export_params = dict(base_params)
    if selected_periode:
        export_params['periode'] = selected_periode
    else:
        if selected_date_debut:
            export_params['date_debut'] = selected_date_debut
        if selected_date_fin:
            export_params['date_fin'] = selected_date_fin

    export_csv_query = urlencode({**export_params, 'export': 'csv'})

    return render(request, 'gestion_transport/bus_trajets.html', {
        'bus': bus,
        'trajets_par_ligne': trajets_par_ligne,
        'total_trajets_bus': trajets_qs.count(),
        'total_dates_trajets_bus': trajets_qs.values('date_trajet').distinct().count(),
        'total_retards_bus': total_retards_bus,
        'lignes_bus': lignes_bus,
        'selected_ligne_id': str(selected_ligne_id),
        'selected_date_debut': selected_date_debut,
        'selected_date_fin': selected_date_fin,
        'selected_periode': selected_periode,
        'export_csv_query': export_csv_query,
        'title': 'Trajets du bus',
        'generic_page': True,
    })

def trajets_avec_retard(request):
    """Rapport des trajets en retard et des trajets a temps."""
    selected_date = request.GET.get('date', '').strip()
    selected_ligne_id = request.GET.get('ligne_id', '').strip()

    trajets_base = Trajet.objects.select_related('bus', 'ligne', 'horaire').all()

    if selected_date:
        try:
            filter_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
            trajets_base = trajets_base.filter(date_trajet=filter_date)
        except ValueError:
            selected_date = ''

    if selected_ligne_id:
        try:
            trajets_base = trajets_base.filter(ligne_id=int(selected_ligne_id))
        except ValueError:
            selected_ligne_id = ''

    trajets_retard = trajets_base.filter(
        retard_minutes__gt=0
    ).order_by('-retard_minutes', '-date_trajet')

    trajets_a_temps = trajets_base.filter(
        retard_minutes=0
    ).order_by('-date_trajet', 'horaire__heure_depart')

    lignes = Ligne.objects.order_by('nom_ligne')

    return render(request, 'gestion_transport/trajets_retard.html', {
        'trajets_retard': trajets_retard,
        'trajets_a_temps': trajets_a_temps,
        'stats_retard_count': trajets_retard.count(),
        'stats_on_time_count': trajets_a_temps.count(),
        'lignes': lignes,
        'selected_date': selected_date,
        'selected_ligne_id': selected_ligne_id,
        'generic_page': True
    })


def trajets_programmes(request):
    """Liste des trajets programmés avec filtres et vue calendrier mensuelle."""
    bus_id = request.GET.get('bus_id')
    ligne_id = request.GET.get('ligne_id')
    date_str = request.GET.get('date')

    trajets_base = Trajet.objects.select_related('bus', 'ligne', 'horaire').all()

    if bus_id:
        try:
            trajets_base = trajets_base.filter(bus_id=int(bus_id))
        except ValueError:
            pass

    if ligne_id:
        try:
            trajets_base = trajets_base.filter(ligne_id=int(ligne_id))
        except ValueError:
            pass

    # Mois de référence du calendrier.
    # Le champ date peut être un mois (YYYY-MM) ou une date (YYYY-MM-DD).
    calendar_ref_date = _parse_calendar_reference_date(date_str)

    first_of_month = calendar_ref_date.replace(day=1)
    next_month_first = (first_of_month.replace(day=28) + timedelta(days=4)).replace(day=1)

    # Le filtre "date" pilote le mois affiché du calendrier, pas un jour unique.
    trajets = trajets_base.filter(
        date_trajet__gte=first_of_month,
        date_trajet__lt=next_month_first
    )

    trajets = trajets.order_by('date_trajet', 'horaire__heure_depart', 'bus__numero_immatriculation')

    first_weekday, days_in_month = calendar.monthrange(first_of_month.year, first_of_month.month)

    trajets_by_date = {}
    for trajet in trajets:
        trajets_by_date.setdefault(trajet.date_trajet, []).append(trajet)

    calendar_cells = []
    grid_start = first_of_month - timedelta(days=first_weekday)
    for index in range(42):
        cell_date = grid_start + timedelta(days=index)
        day_params = {}
        if bus_id:
            day_params['bus_id'] = bus_id
        if ligne_id:
            day_params['ligne_id'] = ligne_id
        day_params['date'] = cell_date.isoformat()

        calendar_cells.append({
            'date': cell_date,
            'in_current_month': cell_date.month == first_of_month.month,
            'is_today': cell_date == date.today(),
            'is_selected': bool(date_str and cell_date.isoformat() == date_str),
            'trajets': trajets_by_date.get(cell_date, []),
            'trajets_count': len(trajets_by_date.get(cell_date, [])),
            'query': urlencode(day_params),
        })

    calendar_weeks = [calendar_cells[i:i + 7] for i in range(0, len(calendar_cells), 7)]

    weekday_labels = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
    month_labels = {
        1: 'Janvier', 2: 'Fevrier', 3: 'Mars', 4: 'Avril', 5: 'Mai', 6: 'Juin',
        7: 'Juillet', 8: 'Aout', 9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Decembre'
    }
    month_label = f"{month_labels[first_of_month.month]} {first_of_month.year}"

    prev_month = (first_of_month - timedelta(days=1)).replace(day=1)
    next_month = (first_of_month.replace(day=28) + timedelta(days=4)).replace(day=1)

    base_params = {}
    if bus_id:
        base_params['bus_id'] = bus_id
    if ligne_id:
        base_params['ligne_id'] = ligne_id

    prev_params = base_params.copy()
    prev_params['date'] = prev_month.isoformat()
    next_params = base_params.copy()
    next_params['date'] = next_month.isoformat()

    selected_month = date_str[:7] if date_str else first_of_month.isoformat()[:7]

    selected_day_trajets = trajets_base.filter(date_trajet=calendar_ref_date).order_by(
        'horaire__heure_depart',
        'bus__numero_immatriculation'
    )

    agenda_slots_map = {}
    for trajet in selected_day_trajets:
        key = (trajet.horaire_id, trajet.ligne_id)
        if key not in agenda_slots_map:
            agenda_slots_map[key] = {
                'heure_depart': trajet.horaire.heure_depart,
                'heure_arrivee': trajet.horaire.heure_arrivee,
                'sens': trajet.horaire.sens,
                'sens_display': trajet.horaire.get_sens_display(),
                'ligne_nom': trajet.ligne.nom_ligne,
                'buses': [],
            }
        agenda_slots_map[key]['buses'].append(trajet.bus.numero_immatriculation)

    agenda_slots = list(agenda_slots_map.values())

    # liste bus affectés à la ligne sélectionnée (ou tous les bus si aucune ligne sélectionnée) pour le filtre de sélection rapide du jour
    bus_list= Bus.objects.filter(
        affectationbusligne__ligne_id=ligne_id
    ).distinct() if ligne_id else Bus.objects.all()
    
    # bus_list = Bus.objects.all().order_by('numero_immatriculation')
    lignes = Ligne.objects.all().order_by('nom_ligne')

    return render(request, 'gestion_transport/trajets_programmes.html', {
        'trajets': trajets,
        'bus_list': bus_list,

        'lignes': lignes,
        'selected_bus_id': bus_id or '',
        'selected_ligne_id': ligne_id or '',
        'selected_ligne_nom': lignes.get(id=ligne_id).nom_ligne if ligne_id else '',
        'selected_date': selected_month,
        'calendar_weeks': calendar_weeks,
        'weekday_labels': weekday_labels,
        'month_label': month_label,
        'prev_month_query': urlencode(prev_params),
        'next_month_query': urlencode(next_params),
        'selected_day': calendar_ref_date,
        'selected_day_trajets': selected_day_trajets,
        'selected_day_slots': agenda_slots,
        'generic_page': True,
    })


@login_required(login_url='gestion_transport:admin_login')
@user_passes_test(lambda u: u.is_staff, login_url='gestion_transport:admin_login')
@require_POST
def dispatch_trajets_equitable(request):
    """Repartit les trajets d'un mois sur les bus disponibles de facon equitable."""
    ligne_id = request.POST.get('ligne_id')
    bus_id = request.POST.get('bus_id', '')
    date_str = request.POST.get('date', '')

    if not ligne_id:
        messages.error(request, "Veuillez selectionner une ligne avant de lancer le dispatch equitable.")
        return redirect('gestion_transport:trajets_programmes')

    try:
        ligne_id_int = int(ligne_id)
    except (TypeError, ValueError):
        messages.error(request, "Identifiant de ligne invalide.")
        return redirect('gestion_transport:trajets_programmes')

    calendar_ref_date = _parse_calendar_reference_date(date_str)
    first_of_month = calendar_ref_date.replace(day=1)
    next_month_first = (first_of_month.replace(day=28) + timedelta(days=4)).replace(day=1)

    trajets_qs = Trajet.objects.filter(
        ligne_id=ligne_id_int,
        date_trajet__gte=first_of_month,
        date_trajet__lt=next_month_first,
    ).select_related('bus', 'horaire').order_by('date_trajet', 'horaire__heure_depart', 'id')

    trajets_groupes = {}
    for trajet in trajets_qs:
        key = (trajet.date_trajet, trajet.horaire_id)
        trajets_groupes.setdefault(key, []).append(trajet)

    if not trajets_groupes:
        messages.info(request, "Aucun trajet a dispatcher pour ce mois et cette ligne.")
    else:
        updated_groups = 0
        skipped_groups = 0
        updated_trajets = 0

        # Pour equilibrer la charge au fil du mois, on avance un index par jour.
        day_rotation_index = {}

        with transaction.atomic():
            for (trajet_date, horaire_id), group_trajets in trajets_groupes.items():
                available_buses = list(
                    Bus.objects.filter(
                        affectationbusligne__ligne_id=ligne_id_int,
                        affectationbusligne__date_debut__lte=trajet_date,
                    ).filter(
                        Q(affectationbusligne__date_fin__isnull=True)
                        | Q(affectationbusligne__date_fin__gte=trajet_date)
                    ).distinct().order_by('id')
                )

                if len(available_buses) < len(group_trajets):
                    skipped_groups += 1
                    continue

                rotation = day_rotation_index.get(trajet_date, 0) % len(available_buses)
                rotated_buses = available_buses[rotation:] + available_buses[:rotation]
                chosen_buses = rotated_buses[:len(group_trajets)]
                day_rotation_index[trajet_date] = (rotation + len(group_trajets)) % len(available_buses)

                old_trajets = list(group_trajets)
                retard_values = [t.retard_minutes for t in old_trajets]
                ligne_obj = old_trajets[0].ligne
                horaire_obj = old_trajets[0].horaire

                Trajet.objects.filter(id__in=[t.id for t in old_trajets]).delete()

                new_trajets = []
                for idx, bus in enumerate(chosen_buses):
                    new_trajets.append(
                        Trajet(
                            bus=bus,
                            ligne=ligne_obj,
                            horaire=horaire_obj,
                            date_trajet=trajet_date,
                            retard_minutes=retard_values[idx] if idx < len(retard_values) else 0,
                        )
                    )

                Trajet.objects.bulk_create(new_trajets)
                updated_groups += 1
                updated_trajets += len(new_trajets)

        if updated_groups:
            msg = (
                f"Dispatch equitable termine: {updated_trajets} trajet(s) redistribue(s) "
                f"sur {updated_groups} plage(s) horaire(s)."
            )
            if skipped_groups:
                msg += f" {skipped_groups} plage(s) ignoree(s): pas assez de bus disponibles."
            messages.success(request, msg)
        else:
            messages.warning(
                request,
                "Dispatch non applique: pas assez de bus disponibles pour les plages du mois selectionne.",
            )

    redirect_params = {'ligne_id': ligne_id_int}
    if bus_id:
        redirect_params['bus_id'] = bus_id
    if date_str:
        redirect_params['date'] = date_str

    return redirect(f"{redirect('gestion_transport:trajets_programmes').url}?{urlencode(redirect_params)}")
# la view qui affiche une simple page html trajets.html

def trajets(request):
    """Affiche une page avec la liste de tous les trajets programmés."""
    trajets = Trajet.objects.select_related('bus', 'ligne', 'horaire').order_by('date_trajet', 'horaire__heure_depart')

    return render(request, 'gestion_transport/trajets.html', {
        'trajets': trajets,
        'generic_page': True
    })


@csrf_exempt
def get_nearby_lines(request):
    """
    Retourne les lignes les plus proches de la position GPS de l'étudiant.
    
    Paramètres GET/POST:
    - latitude: latitude de l'utilisateur (float)
    - longitude: longitude de l'utilisateur (float)
    - limit: nombre de lignes à retourner (default: 5)
    
    Retourne JSON avec les lignes triées par distance.
    """
    try:
        lat_str = request.GET.get('latitude') or request.POST.get('latitude')
        lon_str = request.GET.get('longitude') or request.POST.get('longitude')
        limit = int(request.GET.get('limit', '5') or request.POST.get('limit', '5'))
        
        if not lat_str or not lon_str:
            return JsonResponse({
                'success': False,
                'error': 'Latitude et longitude sont obligatoires'
            }, status=400)
        
        try:
            user_lat = float(lat_str)
            user_lon = float(lon_str)
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': 'Latitude et longitude doivent être des nombres valides'
            }, status=400)
        
        # Récupérer toutes les lignes avec leurs stations
        lignes = Ligne.objects.all().prefetch_related(
            Prefetch(
                'lignestation_set',
                queryset=LigneStation.objects.select_related('station').order_by('ordre')
            )
        )

        stations = list(
            Station.objects.filter(latitude__isnull=False, longitude__isnull=False).prefetch_related(
                Prefetch(
                    'lignestation_set',
                    queryset=LigneStation.objects.select_related('ligne').order_by('ordre')
                )
            )
        )

        station_distances = []
        for station in stations:
            distance = _haversine_km(
                user_lat,
                user_lon,
                float(station.latitude),
                float(station.longitude),
            )
            station_distances.append({
                'station': station,
                'distance_km': round(distance, 2),
            })

        station_distances.sort(key=lambda item: item['distance_km'])
        nearest_stations = station_distances[:limit]
        nearest_station_entry = nearest_stations[0] if nearest_stations else None
        nearest_station = nearest_station_entry['station'] if nearest_station_entry else None
        nearest_station_distance = nearest_station_entry['distance_km'] if nearest_station_entry else None

        def serialize_station_lines(station):
            station_lines = []
            seen_line_ids = set()
            for relation in station.lignestation_set.all():
                if not relation.ligne_id or relation.ligne_id in seen_line_ids:
                    continue
                seen_line_ids.add(relation.ligne_id)
                station_lines.append({
                    'id': relation.ligne.id,
                    'nom': relation.ligne.nom_ligne,
                    'ordre_station': relation.ordre,
                })
            station_lines.sort(key=lambda item: item['nom'].lower())
            return station_lines

        lines_at_station = serialize_station_lines(nearest_station) if nearest_station else []
        alternative_station_lines = []
        for item in nearest_stations[1:]:
            station = item['station']
            station_lines = serialize_station_lines(station)
            if not station_lines:
                continue
            alternative_station_lines.append({
                'id': station.id,
                'nom': station.nom_station,
                'adresse': station.adresse,
                'distance_km': item['distance_km'],
                'lines': station_lines,
            })
        
        lignes_distances = []
        for ligne in lignes:
            # Récupérer les stations de cette ligne
            try:
                ligne_stations = list(ligne.lignestation_set.all())
            except:
                ligne_stations = []
            
            # Filtrer les stations avec coordonnées valides
            valid_stations = [
                ls for ls in ligne_stations
                if ls.station and ls.station.latitude is not None and ls.station.longitude is not None
            ]
            
            if not valid_stations:
                continue
            
            # Calculer la distance minimale entre l'utilisateur et toutes les stations
            min_distance = float('inf')
            closest_station = None
            
            for ls in valid_stations:
                station = ls.station
                distance = _haversine_km(
                    user_lat, user_lon,
                    float(station.latitude), float(station.longitude)
                )
                if distance < min_distance:
                    min_distance = distance
                    closest_station = station
            
            if closest_station and min_distance != float('inf'):
                lignes_distances.append({
                    'id': ligne.id,
                    'nom': ligne.nom_ligne,
                    'distance_km': round(min_distance, 2),
                    'station_proche': closest_station.nom_station,
                    'station_lat': float(closest_station.latitude),
                    'station_lon': float(closest_station.longitude),
                })
        
        # Trier par distance et limiter
        lignes_distances.sort(key=lambda x: x['distance_km'])
        nearby_lines = lignes_distances[:limit]
        
        return JsonResponse({
            'success': True,
            'lignes': nearby_lines,
            'nearest_station': {
                'id': nearest_station.id,
                'nom': nearest_station.nom_station,
                'adresse': nearest_station.adresse,
                'distance_km': round(nearest_station_distance, 2),
                'latitude': float(nearest_station.latitude),
                'longitude': float(nearest_station.longitude),
            } if nearest_station else None,
            'nearest_stations': [
                {
                    'id': item['station'].id,
                    'nom': item['station'].nom_station,
                    'adresse': item['station'].adresse,
                    'distance_km': item['distance_km'],
                    'latitude': float(item['station'].latitude),
                    'longitude': float(item['station'].longitude),
                }
                for item in nearest_stations
            ],
            'lines_at_station': lines_at_station,
            'alternative_station_lines': alternative_station_lines,
            'count': len(nearby_lines),
            'user_position': {
                'latitude': user_lat,
                'longitude': user_lon
            }
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
