"""
API REST versionnée pour le front statique (ex. Navéo-Final.html).

Authentification : pas de cookie de session. Les actions sensibles exigent
`student_number` + `password` dans le corps JSON (même règles que l'espace étudiant Django).
"""
import json
from datetime import date, datetime

from django.core.exceptions import ValidationError
from django.db.models import Count
from django.http import JsonResponse
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import (
    AffectationBusLigne,
    AffectationEtudiantLigne,
    Bus,
    Conducteur,
    Etudiant,
    Horaire,
    Ligne,
    LigneStation,
    ReservationTrajet,
    Station,
    Trajet,
)


def _load_json(request):
    try:
        return json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return None


def _etudiant_par_mot_de_passe(student_number, password):
    if not student_number or not password:
        return None, 'Matricule et mot de passe requis.'
    try:
        etu = Etudiant.objects.get(student_number=student_number)
    except Etudiant.DoesNotExist:
        return None, 'Matricule ou mot de passe incorrect.'
    if not etu.check_password(password):
        return None, 'Matricule ou mot de passe incorrect.'
    return etu, None


@csrf_exempt
@require_POST
def etudiant_verifier_matricule(request):
    data = _load_json(request)
    if data is None:
        return JsonResponse({'exists': False, 'error': 'JSON invalide.'}, status=400)
    student_id = (data.get('student_id') or data.get('student_number') or data.get('matricule') or '').strip()
    if not student_id or len(student_id) != 12 or not student_id.isdigit():
        return JsonResponse({'exists': False, 'error': 'Format matricule invalide'})
    exists = Etudiant.objects.filter(student_number=student_id).exists()
    return JsonResponse({'exists': exists})


@csrf_exempt
@require_POST
def abonnement_souscrire(request):
    data = _load_json(request)
    if data is None:
        return JsonResponse({'success': False, 'error': 'JSON invalide.'}, status=400)
    student_id = (data.get('student_id') or data.get('student_number') or '').strip()
    password = data.get('password') or ''
    etu, err = _etudiant_par_mot_de_passe(student_id, password)
    if err:
        return JsonResponse({'success': False, 'error': err}, status=401)

    ligne_id = data.get('ligne_id')
    date_debut = data.get('date_debut')
    date_fin = data.get('date_fin') or None
    if not ligne_id or not date_debut:
        return JsonResponse({'success': False, 'error': 'ligne_id et date_debut sont obligatoires.'}, status=400)
    try:
        ligne = Ligne.objects.get(id=ligne_id)
    except Ligne.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Ligne non trouvée'}, status=404)
    try:
        affectation = AffectationEtudiantLigne(
            etudiant=etu,
            ligne=ligne,
            date_debut=date_debut,
            date_fin=date_fin,
        )
        affectation.full_clean()
        affectation.save()
    except ValidationError as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    return JsonResponse({
        'success': True,
        'message': f"Abonnement à la {ligne.nom_ligne} enregistré avec succès!",
        'affectation_id': affectation.id,
    })


@csrf_exempt
@require_POST
def abonnement_resilier(request):
    data = _load_json(request)
    if data is None:
        return JsonResponse({'success': False, 'error': 'JSON invalide.'}, status=400)
    student_id = (data.get('student_id') or data.get('student_number') or '').strip()
    password = data.get('password') or ''
    etu, err = _etudiant_par_mot_de_passe(student_id, password)
    if err:
        return JsonResponse({'success': False, 'error': err}, status=401)
    ligne_id = data.get('ligne_id')
    if not ligne_id:
        return JsonResponse({'success': False, 'error': 'ligne_id manquant.'}, status=400)
    try:
        ligne = Ligne.objects.get(id=ligne_id)
    except Ligne.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Ligne non trouvée'}, status=404)
    affectation = AffectationEtudiantLigne.objects.filter(etudiant=etu, ligne=ligne).exclude(
        date_fin__lt=date.today()
    ).first()
    if affectation:
        affectation.delete()
        return JsonResponse({'success': True, 'message': 'Désabonnement effectué avec succès!'})
    return JsonResponse({'success': False, 'error': 'Aucun abonnement actif trouvé'}, status=404)


@csrf_exempt
@require_GET
def sante(request):
    return JsonResponse({'ok': True, 'service': 'transport-univ', 'version': '1'})


@csrf_exempt
@require_GET
def list_lignes(request):
    lignes = Ligne.objects.all().order_by('nom_ligne')
    return JsonResponse({
        'success': True,
        'lignes': [
            {
                'id': l.id,
                'nom_ligne': l.nom_ligne,
                'description': l.description or '',
                'distance_km': l.distance_km,
            }
            for l in lignes
        ],
    })


@csrf_exempt
@require_GET
def ligne_horaires(request, ligne_id):
    try:
        ligne = Ligne.objects.get(pk=ligne_id)
    except Ligne.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Ligne introuvable.'}, status=404)
    horaires = Horaire.objects.filter(ligne=ligne).order_by('jour_semaine', 'sens', 'heure_depart')
    return JsonResponse({
        'success': True,
        'ligne_id': ligne.id,
        'nom_ligne': ligne.nom_ligne,
        'horaires': [
            {
                'id': h.id,
                'jour_semaine': h.jour_semaine,
                'sens': h.sens,
                'heure_depart': h.heure_depart.strftime('%H:%M'),
                'heure_arrivee': h.heure_arrivee.strftime('%H:%M') if h.heure_arrivee else None,
            }
            for h in horaires
        ],
    })


@csrf_exempt
@require_GET
def ligne_stations(request, ligne_id):
    try:
        ligne = Ligne.objects.get(pk=ligne_id)
    except Ligne.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Ligne introuvable.'}, status=404)
    ls = (
        LigneStation.objects.filter(ligne=ligne)
        .select_related('station')
        .order_by('ordre')
    )
    return JsonResponse({
        'success': True,
        'ligne_id': ligne.id,
        'stations': [
            {
                'ordre': x.ordre,
                'id': x.station_id,
                'nom': x.station.nom_station,
                'adresse': x.station.adresse or '',
                'latitude': float(x.station.latitude) if x.station.latitude is not None else None,
                'longitude': float(x.station.longitude) if x.station.longitude is not None else None,
            }
            for x in ls
        ],
    })


@csrf_exempt
@require_POST
def etudiant_connexion(request):
    data = _load_json(request)
    if data is None:
        return JsonResponse({'success': False, 'error': 'JSON invalide.'}, status=400)
    sid = (data.get('student_number') or data.get('matricule') or '').strip()
    password = data.get('password') or ''
    etu, err = _etudiant_par_mot_de_passe(sid, password)
    if err:
        return JsonResponse({'success': False, 'error': err}, status=401)
    return JsonResponse({
        'success': True,
        'etudiant': {
            'student_number': etu.student_number,
            'nom': etu.nom,
            'prenom': etu.prenom,
            'email': etu.email,
            'telephone': etu.telephone or '',
        },
    })


@csrf_exempt
@require_GET
def etudiant_abonnements(request):
    student_id = request.GET.get('student_number') or request.GET.get('student_id')
    if not student_id:
        return JsonResponse({'success': False, 'error': 'Paramètre student_number manquant.'}, status=400)
    try:
        etu = Etudiant.objects.get(student_number=student_id.strip())
    except Etudiant.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Étudiant non trouvé.'}, status=404)
    subscriptions = (
        AffectationEtudiantLigne.objects.filter(etudiant=etu)
        .exclude(date_fin__lt=date.today())
        .select_related('ligne')
    )
    return JsonResponse({
        'success': True,
        'subscriptions': [
            {
                'id': s.id,
                'ligne_id': s.ligne_id,
                'ligne': s.ligne.nom_ligne,
                'dateDebut': s.date_debut.strftime('%Y-%m-%d'),
                'dateFin': s.date_fin.strftime('%Y-%m-%d') if s.date_fin else None,
            }
            for s in subscriptions
        ],
    })


def _reserve_trajet_core(etudiant, ligne_id, horaire_id, sens):
    """Logique alignée sur views.reserve_trajet (sans session). Retourne (dict, http_status)."""
    ligne_id = int(ligne_id)
    horaire_id = int(horaire_id)
    if not sens:
        return {'success': False, 'error': 'Ligne, sens et horaire sont obligatoires.'}, 400

    try:
        horaire = Horaire.objects.select_related('ligne').get(id=horaire_id)
    except Horaire.DoesNotExist:
        return {'success': False, 'error': 'Horaire introuvable.'}, 404

    if ligne_id != horaire.ligne_id or horaire.sens != sens:
        return {'success': False, 'error': 'Le créneau sélectionné est incohérent (ligne/sens/horaire).'}, 400

    today = date.today()

    if horaire.heure_depart < datetime.now().time():
        return {'success': False, 'error': 'Cet horaire est déjà passé, vous ne pouvez plus réserver.'}, 400

    has_active_subscription = AffectationEtudiantLigne.objects.filter(
        etudiant=etudiant,
        ligne_id=ligne_id,
        date_debut__lte=today,
    ).exclude(date_fin__lt=today).exists()

    if not has_active_subscription:
        return {'success': False, 'error': 'Vous devez avoir un abonnement actif sur cette ligne.'}, 403

    existing_reservation = ReservationTrajet.objects.filter(
        etudiant=etudiant,
        trajet__date_trajet=today,
        trajet__horaire__heure_depart=horaire.heure_depart,
    ).select_related('trajet__bus', 'trajet__ligne', 'trajet__horaire').first()

    if existing_reservation:
        return {
            'success': False,
            'error': (
                f"Vous avez déjà une réservation à "
                f"{existing_reservation.trajet.horaire.heure_depart.strftime('%H:%M')} "
                f"sur la ligne {existing_reservation.trajet.ligne.nom_ligne}."
            ),
            'assigned_bus': existing_reservation.trajet.bus.numero_immatriculation,
        }, 409

    candidate_trajets = list(
        Trajet.objects.filter(
            date_trajet=today,
            ligne_id=ligne_id,
            horaire_id=horaire_id,
        ).select_related('bus', 'horaire').order_by('bus__id', 'id')
    )

    if not candidate_trajets:
        return {'success': False, 'error': "Aucun trajet disponible aujourd'hui pour ce créneau."}, 404

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
        return {'success': False, 'error': 'Tous les bus sont complets pour ce créneau.'}, 409

    res = ReservationTrajet.objects.create(etudiant=etudiant, trajet=selected_trajet)

    return {
        'success': True,
        'message': f"Réservation enregistrée. Bus attribué: {selected_trajet.bus.numero_immatriculation}.",
        'assigned_bus': selected_trajet.bus.numero_immatriculation,
        'trajet_id': selected_trajet.id,
        'ticket_code': res.ticket_code,
    }, 200


@csrf_exempt
@require_POST
def reservation_trajet(request):
    data = _load_json(request)
    if data is None:
        return JsonResponse({'success': False, 'error': 'JSON invalide.'}, status=400)
    sid = (data.get('student_number') or data.get('matricule') or '').strip()
    password = data.get('password') or ''
    etu, err = _etudiant_par_mot_de_passe(sid, password)
    if err:
        return JsonResponse({'success': False, 'error': err}, status=401)

    ligne_id = data.get('ligne_id')
    horaire_id = data.get('horaire_id')
    sens = data.get('sens')
    if ligne_id is None or horaire_id is None or not sens:
        return JsonResponse({'success': False, 'error': 'ligne_id, horaire_id et sens sont obligatoires.'}, status=400)

    try:
        payload, status = _reserve_trajet_core(etu, ligne_id, horaire_id, sens)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    return JsonResponse(payload, status=status)


def _annuler_reservation_core(etudiant, ligne_id, horaire_id, sens):
    ligne_id = int(ligne_id)
    horaire_id = int(horaire_id)
    try:
        horaire = Horaire.objects.get(id=horaire_id)
    except Horaire.DoesNotExist:
        return {'success': False, 'error': 'Horaire introuvable.'}, 404

    if ligne_id != horaire.ligne_id or horaire.sens != sens:
        return {'success': False, 'error': 'Le créneau sélectionné est incohérent (ligne/sens/horaire).'}, 400

    if horaire.heure_depart <= datetime.now().time():
        return {
            'success': False,
            'error': "L'horaire est dépassé, l'annulation n'est plus possible.",
            'past_slot': True,
        }, 400

    deleted_count, _ = ReservationTrajet.objects.filter(
        etudiant=etudiant,
        trajet__date_trajet=date.today(),
        trajet__ligne_id=ligne_id,
        trajet__horaire_id=horaire_id,
    ).delete()

    if deleted_count == 0:
        return {'success': True, 'message': 'Aucune réservation à annuler pour ce créneau.'}, 200
    return {'success': True, 'message': 'Réservation annulée avec succès.'}, 200


@csrf_exempt
@require_POST
def reservation_trajet_annuler(request):
    data = _load_json(request)
    if data is None:
        return JsonResponse({'success': False, 'error': 'JSON invalide.'}, status=400)
    sid = (data.get('student_number') or data.get('matricule') or '').strip()
    password = data.get('password') or ''
    etu, err = _etudiant_par_mot_de_passe(sid, password)
    if err:
        return JsonResponse({'success': False, 'error': err}, status=401)

    ligne_id = data.get('ligne_id')
    horaire_id = data.get('horaire_id')
    sens = data.get('sens')
    if ligne_id is None or horaire_id is None or not sens:
        return JsonResponse({'success': False, 'error': 'ligne_id, horaire_id et sens sont obligatoires.'}, status=400)

    try:
        payload, status = _annuler_reservation_core(etu, ligne_id, horaire_id, sens)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    return JsonResponse(payload, status=status)


@csrf_exempt
def geolocalisation_lignes_proches(request):
    """Délègue à la vue existante (évite import circulaire au chargement du module)."""
    from .views import get_nearby_lines

    return get_nearby_lines(request)


def _json_error(message, status=400):
    return JsonResponse({'message': message, 'error': message}, status=status)


@csrf_exempt
@require_POST
def auth_admin(request):
    """Mot de passe = celui d'un compte superutilisateur Django (/admin/)."""
    from django.contrib.auth.models import User

    data = _load_json(request) or {}
    password = data.get('password') or ''
    if not password:
        return _json_error('Mot de passe requis.', 400)
    for u in User.objects.filter(is_superuser=True):
        if u.check_password(password):
            return JsonResponse({'ok': True, 'uid': u.get_username()})
    return _json_error('Mot de passe administrateur incorrect.', 401)


@csrf_exempt
@require_POST
def auth_student(request):
    data = _load_json(request) or {}
    sid = (data.get('studentId') or data.get('student_number') or '').strip()
    password = data.get('password') or ''
    if len(sid) != 12 or not sid.isdigit():
        return _json_error('Le matricule doit comporter exactement 12 chiffres.', 400)
    etu, err = _etudiant_par_mot_de_passe(sid, password)
    if err:
        return _json_error(err, 401)
    return JsonResponse({'ok': True, 'uid': etu.student_number})


@csrf_exempt
@require_POST
def auth_driver(request):
    data = _load_json(request) or {}
    did = (data.get('driverId') or '').strip()
    password = data.get('password') or ''
    if not did:
        return _json_error('ID conducteur requis.', 400)
    try:
        c = Conducteur.objects.get(driver_id__iexact=did)
    except Conducteur.DoesNotExist:
        return _json_error('Conducteur inconnu.', 404)
    if not c.check_password(password):
        return _json_error('Mot de passe conducteur incorrect.', 401)
    return JsonResponse({'ok': True, 'uid': c.driver_id})


@csrf_exempt
def bootstrap(request):
    """Données pour l'interface Navéo (chargement initial). PUT = no-op (l'UI garde l'édition locale)."""
    if request.method in ('PUT', 'POST'):
        return JsonResponse({'ok': True})

    if request.method != 'GET':
        return JsonResponse({'message': 'Méthode non autorisée'}, status=405)

    today = date.today()

    lines_out = []
    for ligne in Ligne.objects.all().order_by('nom_ligne'):
        h = Horaire.objects.filter(ligne=ligne).order_by('heure_depart').first()
        ls = LigneStation.objects.filter(ligne=ligne).select_related('station').order_by('ordre').first()
        lines_out.append({
            'name': ligne.nom_ligne,
            'status': 'active',
            'nextTime': h.heure_depart.strftime('%H:%M') if h else '08:00',
            'station': ls.station.nom_station if ls else '—',
        })

    stations_out = list(
        Station.objects.order_by('nom_station').values_list('nom_station', flat=True)[:200]
    )

    buses_out = []
    for bus in Bus.objects.all().order_by('numero_immatriculation'):
        aff = (
            AffectationBusLigne.objects.filter(bus=bus, date_debut__lte=today)
            .exclude(date_fin__lt=today)
            .select_related('ligne')
            .first()
        )
        line_name = aff.ligne.nom_ligne if aff else '—'
        reserved = ReservationTrajet.objects.filter(trajet__bus=bus, trajet__date_trajet=today).count()
        tj = Trajet.objects.filter(bus=bus, date_trajet=today).select_related('horaire').first()
        tstr = tj.horaire.heure_depart.strftime('%H:%M') if tj and tj.horaire else '08:00'
        buses_out.append({
            'name': bus.numero_immatriculation,
            'capacity': bus.capacite,
            'reserved': reserved,
            'line': line_name,
            'time': tstr,
        })

    drivers_out = []
    for c in Conducteur.objects.all().order_by('driver_id'):
        aff = (
            AffectationBusLigne.objects.filter(conducteur=c, date_debut__lte=today)
            .exclude(date_fin__lt=today)
            .select_related('ligne')
            .first()
        )
        drivers_out.append({
            'id': c.driver_id,
            'name': f'{c.prenom} {c.nom}'.strip(),
            'line': aff.ligne.nom_ligne if aff else '',
            'time': '08:00',
            'station': '',
        })

    return JsonResponse({
        'lines': lines_out,
        'stations': stations_out,
        'buses': buses_out,
        'drivers': drivers_out,
        'incidents': [],
        'reservations': [],
        'notifications': [],
    })


urlpatterns = [
    path('bootstrap/', bootstrap),
    path('auth/admin/', auth_admin),
    path('auth/student/', auth_student),
    path('auth/driver/', auth_driver),
    path('sante/', sante),
    path('lignes/', list_lignes),
    path('lignes/<int:ligne_id>/horaires/', ligne_horaires),
    path('lignes/<int:ligne_id>/stations/', ligne_stations),
    path('etudiants/verifier-matricule/', etudiant_verifier_matricule),
    path('etudiants/connexion/', etudiant_connexion),
    path('etudiants/abonnements/', etudiant_abonnements),
    path('abonnements/', abonnement_souscrire),
    path('abonnements/resilier/', abonnement_resilier),
    path('reservations/trajet/', reservation_trajet),
    path('reservations/trajet/annuler/', reservation_trajet_annuler),
    path('geolocalisation/lignes-proches/', geolocalisation_lignes_proches),
]
