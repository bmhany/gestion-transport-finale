from datetime import date, datetime, timedelta

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import check_password as django_check_password, make_password
from django.db.models.functions import Lower
from django.utils.dateparse import parse_time

class Etudiant(models.Model):
    student_number = models.CharField(
        max_length=12,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^\d{12}$',
                message="Le matricule étudiant doit contenir exactement 12 chiffres."
            )
        ]
    )
    password = models.CharField(max_length=128, default='')
    nom = models.CharField(max_length=50)
    prenom = models.CharField(max_length=50)
    email = models.EmailField(unique=True)
    telephone = models.CharField(max_length=20, blank=True)
    date_inscription = models.DateField(default=date.today)

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        if not self.password:
            return False
        return django_check_password(raw_password, self.password)

    def __str__(self):
        return f"{self.student_number} - {self.prenom} {self.nom}"

    class Meta:
        verbose_name = "Étudiant"
        verbose_name_plural = "Étudiants"

class Bus(models.Model):
    numero_immatriculation = models.CharField(max_length=20, unique=True)
    capacite = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    marque = models.CharField(max_length=50, blank=True)
    date_mise_service = models.DateField(null=True, blank=True)
    conducteur = models.ForeignKey('Conducteur', on_delete=models.SET_NULL, null=True, blank=True, related_name='buses')

    def __str__(self):
        return f"Bus {self.numero_immatriculation}"

    class Meta:
        verbose_name = "Bus"
        verbose_name_plural = "Bus"

class Ligne(models.Model):
    nom_ligne = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    distance_km = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return self.nom_ligne

    class Meta:
        verbose_name = "Ligne"
        verbose_name_plural = "Lignes"
        constraints = [
            models.UniqueConstraint(
                Lower('nom_ligne'),
                name='uniq_ligne_nom_ligne_ci',
            ),
        ]

class Station(models.Model):
    nom_station = models.CharField(max_length=100)
    adresse = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)

    def __str__(self):
        return self.nom_station

    class Meta:
        verbose_name = "Station"
        verbose_name_plural = "Stations"
        constraints = [
            models.UniqueConstraint(
                fields=['latitude', 'longitude'],
                condition=models.Q(latitude__isnull=False, longitude__isnull=False),
                name='uniq_station_exact_gps',
            ),
        ]

class Horaire(models.Model):
    JOURS_SEMAINE = [
        ('lundi', 'Lundi'),
        ('mardi', 'Mardi'),
        ('mercredi', 'Mercredi'),
        ('jeudi', 'Jeudi'),
        ('vendredi', 'Vendredi'),
        ('samedi', 'Samedi'),
        ('dimanche', 'Dimanche'),
    ]
    SENS_CHOICES = [
        ('aller', 'Aller'),
        ('retour', 'Retour'),
    ]

    ligne = models.ForeignKey(Ligne, on_delete=models.CASCADE)
    jour_semaine = models.CharField(max_length=10, choices=JOURS_SEMAINE)
    sens = models.CharField(max_length=10, choices=SENS_CHOICES, default='aller')
    heure_depart = models.TimeField()
    heure_arrivee = models.TimeField()

    def _default_heure_arrivee(self):
        depart = self.heure_depart
        if isinstance(depart, str):
            depart = parse_time(depart)
        if not depart:
            return None
        return (datetime.combine(date.today(), depart) + timedelta(hours=1)).time().replace(microsecond=0)

    def clean(self):
        if self.heure_depart and not self.heure_arrivee:
            self.heure_arrivee = self._default_heure_arrivee()

    def save(self, *args, **kwargs):
        if self.heure_depart:
            self.heure_arrivee = self._default_heure_arrivee()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ligne} - {self.get_sens_display()} - {self.jour_semaine} {self.heure_depart}"

    class Meta:
        verbose_name = "Horaire"
        verbose_name_plural = "Horaires"
        unique_together = ['ligne', 'jour_semaine', 'sens', 'heure_depart']

class AffectationEtudiantLigne(models.Model):
    etudiant = models.ForeignKey(Etudiant, on_delete=models.CASCADE)
    ligne = models.ForeignKey(Ligne, on_delete=models.CASCADE)
    date_debut = models.DateField()
    date_fin = models.DateField(null=True, blank=True)

    def clean(self):
        if self.date_fin and self.date_fin < self.date_debut:
            raise ValidationError("La date de fin doit être postérieure à la date de début.")

        duplicate_qs = AffectationEtudiantLigne.objects.filter(etudiant=self.etudiant, ligne=self.ligne)
        if self.pk:
            duplicate_qs = duplicate_qs.exclude(pk=self.pk)

        if duplicate_qs.exists():
            raise ValidationError("Un étudiant ne peut pas avoir deux abonnements à la même ligne.")

    def __str__(self):
        return f"{self.etudiant} - {self.ligne}"

    class Meta:
        verbose_name = "Affectation Étudiant-Ligne"
        verbose_name_plural = "Affectations Étudiant-Ligne"
        constraints = [
            models.UniqueConstraint(
                fields=['etudiant', 'ligne'],
                name='uniq_etudiant_ligne_subscription',
            ),
        ]

class AffectationBusLigne(models.Model):
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE)
    ligne = models.ForeignKey(Ligne, on_delete=models.CASCADE)
    conducteur = models.ForeignKey('Conducteur', on_delete=models.SET_NULL, null=True, blank=True, related_name='affectations')
    date_debut = models.DateField()
    date_fin = models.DateField(null=True, blank=True)

    @staticmethod
    def _format_period_end_label(end_date):
        return end_date.strftime('%d/%m/%Y') if end_date else 'en cours'

    @staticmethod
    def _format_period_label(start_date, end_date):
        if end_date:
            return f"du {start_date.strftime('%d/%m/%Y')} au {end_date.strftime('%d/%m/%Y')}"
        return f"à partir du {start_date.strftime('%d/%m/%Y')} (en cours)"

    @staticmethod
    def _add_one_year(start_date):
        try:
            return start_date.replace(year=start_date.year + 1)
        except ValueError:
            # Cas du 29 fevrier -> 28 fevrier l'annee suivante.
            return start_date.replace(year=start_date.year + 1, day=28)

    @classmethod
    def _effective_period_end(cls, start_date, end_date):
        if end_date:
            return end_date
        if start_date:
            return cls._add_one_year(start_date)
        return None

    def clean(self):
        from datetime import date
        from django.core.exceptions import ValidationError
        
        # Règle métier: date_fin vide => date_debut + 1 an.
        if not self.date_fin and self.date_debut:
            self.date_fin = self._effective_period_end(self.date_debut, None)

        # Vérifier que la date de fin est postérieure à la date de début
        if self.date_fin and self.date_fin < self.date_debut:
            raise ValidationError("La date de fin doit être postérieure à la date de début.")

        # Vérifier que la ligne permet des trajets dans les deux sens (aller/retour)
        if self.ligne_id:
            sens_disponibles = set(
                Horaire.objects.filter(ligne=self.ligne).values_list('sens', flat=True)
            )

            if 'aller' not in sens_disponibles or 'retour' not in sens_disponibles:
                raise ValidationError(
                    f"La ligne {self.ligne.nom_ligne} doit contenir au moins un horaire aller "
                    f"et un horaire retour avant d'affecter un bus."
                )

        # Vérifier qu'un bus n'est pas affecté à deux lignes dans la même période
        existing_affectations = AffectationBusLigne.objects.filter(bus=self.bus)
        
        # Exclure l'affectation actuelle si elle existe (pour les modifications)
        if self.pk:
            existing_affectations = existing_affectations.exclude(pk=self.pk)

        for affectation in existing_affectations:
            # Vérifier le chevauchement des périodes
            period_start = affectation.date_debut
            period_end = self._effective_period_end(affectation.date_debut, affectation.date_fin)
            
            new_start = self.date_debut
            new_end = self._effective_period_end(self.date_debut, self.date_fin)

            # Chevauchement si : start1 <= end2 et start2 <= end1
            if new_start <= period_end and period_start <= new_end:
                raise ValidationError(
                    f"Le bus {self.bus.numero_immatriculation} est déjà affecté à la ligne {affectation.ligne.nom_ligne} "
                    f"durant la période {self._format_period_label(affectation.date_debut, affectation.date_fin)}. "
                    f"Un bus ne peut pas être affecté à deux lignes dans la même période."
                )

        # Règle métier : un conducteur ne peut pas être affecté à deux bus différents
        # en même temps (périodes qui se chevauchent).
        if self.conducteur_id:
            new_end = self._effective_period_end(self.date_debut, self.date_fin)
            conflicting = AffectationBusLigne.objects.filter(
                conducteur=self.conducteur,
                date_debut__lte=new_end,
            ).exclude(bus=self.bus)
            if self.pk:
                conflicting = conflicting.exclude(pk=self.pk)
            for aff in conflicting:
                aff_end = self._effective_period_end(aff.date_debut, aff.date_fin)
                if aff.date_debut <= new_end and self.date_debut <= aff_end:
                    raise ValidationError(
                        f"Le conducteur {self.conducteur.prenom} {self.conducteur.nom} est déjà "
                        f"assigné au bus {aff.bus.numero_immatriculation} (ligne {aff.ligne.nom_ligne}) "
                        f"pour la période {self._format_period_label(aff.date_debut, aff.date_fin)}. "
                        f"Un conducteur ne peut pas conduire deux bus en même temps."
                    )

    def save(self, *args, **kwargs):
        if not self.date_fin and self.date_debut:
            self.date_fin = self._effective_period_end(self.date_debut, None)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.bus} - {self.ligne}"

    class Meta:
        verbose_name = "Affectation Bus-Ligne"
        verbose_name_plural = "Affectations Bus-Ligne"

class LigneStation(models.Model):
    ligne = models.ForeignKey(Ligne, on_delete=models.CASCADE)
    station = models.ForeignKey(Station, on_delete=models.CASCADE)
    ordre = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    def __str__(self):
        return f"{self.ligne} - {self.station} (ordre {self.ordre})"

    class Meta:
        verbose_name = "Ligne-Station"
        verbose_name_plural = "Lignes-Stations"
        unique_together = ['ligne', 'station']

class Trajet(models.Model):
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE)
    ligne = models.ForeignKey(Ligne, on_delete=models.CASCADE)
    horaire = models.ForeignKey(Horaire, on_delete=models.CASCADE)
    date_trajet = models.DateField()
    retard_minutes = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Trajet {self.id} - {self.bus} sur {self.ligne}"

    class Meta:
        verbose_name = "Trajet"
        verbose_name_plural = "Trajets"
        unique_together = ['bus', 'ligne', 'horaire', 'date_trajet']

class ReservationHoraire(models.Model):
    """
    Modèle pour tracker les réservations d'étudiants par horaire spécifique.
    Permet de compter précisément la demande par (ligne, horaire) pour allouer les buses.
    """
    etudiant = models.ForeignKey(Etudiant, on_delete=models.CASCADE)
    horaire = models.ForeignKey(Horaire, on_delete=models.CASCADE)
    date_reservation = models.DateField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.etudiant} - {self.horaire}"
    
    class Meta:
        verbose_name = "Réservation Horaire"
        verbose_name_plural = "Réservations Horaires"
        unique_together = ['etudiant', 'horaire']

class ReservationTrajet(models.Model):
    """
    Réservation d'un étudiant sur un trajet précis (bus + ligne + date).
    La réservation n'est acceptée que le jour même du trajet.
    """

    etudiant = models.ForeignKey(Etudiant, on_delete=models.CASCADE)
    trajet = models.ForeignKey(Trajet, on_delete=models.CASCADE)
    date_reservation = models.DateTimeField(auto_now_add=True)
    ticket_code = models.CharField(max_length=64, unique=True, blank=True, null=True, help_text="Code unique pour le ticket QR")

    def save(self, *args, **kwargs):
        import uuid
        if not self.ticket_code:
            self.ticket_code = uuid.uuid4().hex
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.etudiant} - Trajet {self.trajet.id} ({self.trajet.date_trajet})"

    class Meta:
        verbose_name = "Réservation Trajet"
        verbose_name_plural = "Réservations Trajets"
        unique_together = ['etudiant', 'trajet']

class Incident(models.Model):
    trajet = models.ForeignKey(Trajet, on_delete=models.CASCADE)
    description = models.TextField()
    date_heure_incident = models.DateTimeField()
    type_incident = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"Incident {self.id} - {self.trajet}"

    class Meta:
        verbose_name = "Incident"
        verbose_name_plural = "Incidents"


class ModificationHistorique(models.Model):
    ACTION_CHOICES = [
        ('ajout', 'Ajout'),
        ('modification', 'Modification'),
        ('suppression', 'Suppression'),
        ('systeme', 'Système'),
    ]

    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    objet_type = models.CharField(max_length=50)
    description = models.TextField()
    utilisateur = models.CharField(max_length=150, blank=True)
    date_action = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_action_display()} {self.objet_type} - {self.date_action:%d/%m/%Y %H:%M}"

    class Meta:
        verbose_name = "Historique de modification"
        verbose_name_plural = "Historique des modifications"
        ordering = ['-date_action']

# add drivers and conducteurs models if needed in the future, with appropriate relationships to Bus and Trajet. 
class Conducteur(models.Model):
    driver_id = models.CharField(max_length=20, unique=True)
    password = models.CharField(max_length=128, default='')

    nom = models.CharField(max_length=50)
    prenom = models.CharField(max_length=50)
    telephone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(unique=True)

    def __str__(self):
        return f"{self.prenom} {self.nom}"
    def set_password(self, raw_password):
        self.password = make_password(raw_password)
    def check_password(self, raw_password):
        if not self.password:
            return False
        return django_check_password(raw_password, self.password)
    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.driver_id})"

    class Meta:
        
        verbose_name = "Conducteur"
        verbose_name_plural = "Conducteurs"


class SuiviTrajetConducteur(models.Model):
    STATUT_CHOICES = [
        ('planifie', 'Planifie'),
        ('depart', 'Depart'),
        ('arrivee', 'Arrivee'),
    ]

    conducteur = models.ForeignKey('Conducteur', on_delete=models.CASCADE, related_name='suivis_trajets')
    trajet = models.OneToOneField(Trajet, on_delete=models.CASCADE, related_name='suivi_conducteur')
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='planifie')
    depart_effectif = models.DateTimeField(null=True, blank=True)
    arrivee_effective = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Suivi trajet {self.trajet_id} - {self.get_statut_display()}"

    class Meta:
        verbose_name = "Suivi Trajet Conducteur"
        verbose_name_plural = "Suivis Trajets Conducteurs"
        ordering = ['-updated_at']


class RetardTrajet(models.Model):
    """Historique complet des retards déclarés pour un trajet."""
    trajet = models.ForeignKey(Trajet, on_delete=models.CASCADE, related_name='retards_historique')
    retard_minutes = models.PositiveIntegerField()
    motif = models.TextField(blank=True, null=True)
    conducteur = models.ForeignKey(Conducteur, on_delete=models.SET_NULL, null=True, blank=True, related_name='retards_declares')
    utilisateur_declarant = models.CharField(max_length=150, blank=True, help_text="Identité de qui a déclaré le retard")
    date_declaration = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Retard trajet {self.trajet_id}: {self.retard_minutes} min ({self.date_declaration:%d/%m/%Y %H:%M})"

    class Meta:
        verbose_name = "Retard Trajet"
        verbose_name_plural = "Retards Trajets"
        ordering = ['-date_declaration']


class AvisTrajet(models.Model):
    """Evaluation d'un trajet par un étudiant (note générale obligatoire, bus/conducteur optionnels)."""
    etudiant = models.ForeignKey(Etudiant, on_delete=models.CASCADE, related_name='avis_trajets')
    trajet = models.ForeignKey(Trajet, on_delete=models.CASCADE, related_name='avis_etudiants')
    bus = models.ForeignKey(Bus, on_delete=models.SET_NULL, null=True, blank=True, related_name='avis_trajets')
    conducteur = models.ForeignKey(Conducteur, on_delete=models.SET_NULL, null=True, blank=True, related_name='avis_trajets')
    note_generale = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    note_bus = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True)
    note_conducteur = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True)
    commentaire = models.TextField(blank=True)
    date_evaluation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Avis {self.etudiant.student_number} - Trajet {self.trajet_id} ({self.note_generale}/5)"

    class Meta:
        verbose_name = "Avis Trajet"
        verbose_name_plural = "Avis Trajets"
        ordering = ['-date_mise_a_jour']
        unique_together = ['etudiant', 'trajet']

