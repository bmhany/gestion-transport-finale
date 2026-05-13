from django.contrib import admin
from .forms import EtudiantAdminForm, ConducteurAdminForm
from .models import (
    Etudiant, Bus, Ligne, Station, Horaire,
    AffectationEtudiantLigne, AffectationBusLigne,
    LigneStation, Trajet, Incident, ReservationHoraire,
    ReservationTrajet, ModificationHistorique, Conducteur, SuiviTrajetConducteur,
    RetardTrajet, AvisTrajet,
)
@admin.register(Conducteur)
class ConducteurAdmin(admin.ModelAdmin):
    form = ConducteurAdminForm
    list_display = ['driver_id', 'prenom', 'nom', 'email', 'telephone']
    search_fields = ['prenom', 'nom', 'driver_id']
    list_filter = ['prenom', 'nom']

@admin.register(Etudiant)
class EtudiantAdmin(admin.ModelAdmin):
    form = EtudiantAdminForm
    list_display = ['student_number', 'nom', 'prenom', 'email', 'telephone', 'date_inscription']
    search_fields = ['student_number', 'nom', 'prenom', 'email']
    list_filter = ['date_inscription']

@admin.register(Bus)
class BusAdmin(admin.ModelAdmin):
    list_display = ['numero_immatriculation', 'capacite', 'marque', 'date_mise_service']
    search_fields = ['numero_immatriculation', 'marque']
    list_filter = ['marque', 'date_mise_service']

@admin.register(Ligne)
class LigneAdmin(admin.ModelAdmin):
    list_display = ['nom_ligne', 'description', 'distance_km']
    search_fields = ['nom_ligne']

@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ['nom_station', 'adresse', 'latitude', 'longitude']
    search_fields = ['nom_station', 'adresse']
    list_filter = ['nom_station']
    fieldsets = (
        (None, {
            'fields': ('nom_station', 'adresse')
        }),
        ('Coordonnées GPS', {
            'fields': ('latitude', 'longitude'),
            'description': 'Saisissez les coordonnées GPS exactes de la station pour le calcul automatique du kilométrage et de la durée.'
        }),
    )

@admin.register(Horaire)
class HoraireAdmin(admin.ModelAdmin):
    list_display = ['ligne', 'jour_semaine', 'sens', 'heure_depart', 'heure_arrivee']
    list_filter = ['jour_semaine', 'sens', 'ligne']
    search_fields = ['ligne__nom_ligne']

@admin.register(AffectationEtudiantLigne)
class AffectationEtudiantLigneAdmin(admin.ModelAdmin):
    list_display = ['etudiant', 'ligne', 'date_debut', 'date_fin']
    list_filter = ['date_debut', 'date_fin', 'ligne']
    search_fields = ['etudiant__nom', 'etudiant__prenom', 'ligne__nom_ligne']

@admin.register(AffectationBusLigne)
class AffectationBusLigneAdmin(admin.ModelAdmin):
    list_display = ['bus', 'ligne', 'date_debut', 'date_fin']
    list_filter = ['date_debut', 'date_fin', 'ligne']
    search_fields = ['bus__numero_immatriculation', 'ligne__nom_ligne']

@admin.register(LigneStation)
class LigneStationAdmin(admin.ModelAdmin):
    list_display = ['ligne', 'station', 'ordre']
    list_filter = ['ligne']
    search_fields = ['ligne__nom_ligne', 'station__nom_station']

@admin.register(Trajet)
class TrajetAdmin(admin.ModelAdmin):
    list_display = ['bus', 'ligne', 'horaire', 'date_trajet', 'retard_minutes']
    list_filter = ['date_trajet', 'ligne', 'retard_minutes']
    search_fields = ['bus__numero_immatriculation', 'ligne__nom_ligne']

@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ['trajet', 'description', 'date_heure_incident', 'type_incident']
    list_filter = ['date_heure_incident', 'type_incident']
    search_fields = ['trajet__bus__numero_immatriculation', 'description']

@admin.register(ReservationHoraire)
class ReservationHoraireAdmin(admin.ModelAdmin):
    list_display = ['etudiant', 'horaire', 'date_reservation']
    list_filter = ['date_reservation', 'horaire__ligne']
    search_fields = ['etudiant__nom', 'etudiant__prenom', 'horaire__ligne__nom_ligne']
    readonly_fields = ['date_reservation']


@admin.register(ReservationTrajet)
class ReservationTrajetAdmin(admin.ModelAdmin):
    list_display = ['etudiant', 'trajet', 'date_reservation']
    list_filter = ['date_reservation', 'trajet__ligne']
    search_fields = ['etudiant__nom', 'etudiant__prenom', 'trajet__ligne__nom_ligne', 'trajet__bus__numero_immatriculation']
    readonly_fields = ['date_reservation']


@admin.register(ModificationHistorique)
class ModificationHistoriqueAdmin(admin.ModelAdmin):
    list_display = ['action', 'objet_type', 'utilisateur', 'date_action']
    list_filter = ['action', 'objet_type', 'date_action']
    search_fields = ['description', 'utilisateur', 'objet_type']
    readonly_fields = ['date_action']


@admin.register(SuiviTrajetConducteur)
class SuiviTrajetConducteurAdmin(admin.ModelAdmin):
    list_display = ['trajet', 'conducteur', 'statut', 'depart_effectif', 'arrivee_effective', 'updated_at']
    list_filter = ['statut', 'updated_at', 'trajet__ligne']
    search_fields = ['conducteur__driver_id', 'conducteur__nom', 'conducteur__prenom', 'trajet__ligne__nom_ligne', 'trajet__bus__numero_immatriculation']
    readonly_fields = ['updated_at']


@admin.register(RetardTrajet)
class RetardTrajetAdmin(admin.ModelAdmin):
    list_display = ['trajet', 'retard_minutes', 'conducteur', 'date_declaration']
    list_filter = ['date_declaration', 'trajet__ligne', 'retard_minutes']
    search_fields = ['trajet__bus__numero_immatriculation', 'trajet__ligne__nom_ligne', 'conducteur__driver_id', 'conducteur__nom', 'motif']
    readonly_fields = ['date_declaration']
    fieldsets = (
        ('Retard', {
            'fields': ('trajet', 'retard_minutes', 'motif')
        }),
        ('Déclaration', {
            'fields': ('conducteur', 'utilisateur_declarant', 'date_declaration')
        }),
    )


@admin.register(AvisTrajet)
class AvisTrajetAdmin(admin.ModelAdmin):
    list_display = ['etudiant', 'trajet', 'note_generale', 'note_bus', 'note_conducteur', 'date_mise_a_jour']
    list_filter = ['date_mise_a_jour', 'trajet__ligne', 'note_generale', 'note_bus', 'note_conducteur']
    search_fields = ['etudiant__student_number', 'etudiant__nom', 'trajet__ligne__nom_ligne', 'trajet__bus__numero_immatriculation', 'commentaire']
    readonly_fields = ['date_evaluation', 'date_mise_a_jour']
