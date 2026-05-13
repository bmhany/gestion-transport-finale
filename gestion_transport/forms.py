from django import forms
from django.core.exceptions import ValidationError
from datetime import date
from django.forms import inlineformset_factory
from django.forms.utils import ErrorDict
from .models import Etudiant, Bus, Ligne, Station, Horaire, AffectationBusLigne, Trajet, Conducteur, LigneStation


def _validate_ligne_has_required_sens(ligne):
    """Empêche l'affectation d'un bus à une ligne sans horaires aller et retour."""
    if not ligne:
        return

    sens_disponibles = set(Horaire.objects.filter(ligne=ligne).values_list('sens', flat=True))
    if 'aller' not in sens_disponibles or 'retour' not in sens_disponibles:
        raise ValidationError(
            f"La ligne {ligne.nom_ligne} doit avoir au moins un horaire Aller et un horaire Retour avant l'affectation d'un bus."
        )


def _is_deleted_form_data(form):
    if not form.is_bound:
        return False

    delete_key = form.add_prefix('DELETE')
    delete_value = form.data.get(delete_key)
    return str(delete_value).lower() in {'1', 'true', 'on', 'yes'}


class DeletedRowBypassValidationMixin:
    def full_clean(self):
        if _is_deleted_form_data(self):
            self._errors = ErrorDict()
            self.cleaned_data = {'DELETE': True}
            return

        super().full_clean()

class EtudiantRegistrationForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Mot de passe',
        widget=forms.PasswordInput(attrs={'placeholder': 'Mot de passe', 'required': 'required'}),
    )
    password2 = forms.CharField(
        label='Confirmer le mot de passe',
        widget=forms.PasswordInput(attrs={'placeholder': 'Confirmer le mot de passe', 'required': 'required'}),
    )

    class Meta:
        model = Etudiant
        fields = ['student_number', 'nom', 'prenom', 'email', 'telephone']
        widgets = {
            'student_number': forms.TextInput(attrs={
                'placeholder': '012345678901',
                'pattern': '\\d{12}',
                'maxlength': '12',
                'minlength': '12',
                'required': 'required',
                'title': 'Le matricule doit contenir exactement 12 chiffres',
                'autofocus': 'autofocus',
                'inputmode': 'numeric',
            }),
            'nom': forms.TextInput(attrs={'placeholder': 'Nom', 'required': 'required'}),
            'prenom': forms.TextInput(attrs={'placeholder': 'Prénom', 'required': 'required'}),
            'email': forms.EmailInput(attrs={'placeholder': 'email@example.com', 'required': 'required'}),
            'telephone': forms.TextInput(attrs={'placeholder': 'Téléphone'}),
        }
        labels = {
            'student_number': 'Matricule étudiant',
            'nom': 'Nom',
            'prenom': 'Prénom',
            'email': 'Email',
            'telephone': 'Téléphone',
        }

    def clean_student_number(self):
        student_number = self.cleaned_data.get('student_number', '').strip()
        if len(student_number) != 12 or not student_number.isdigit():
            raise ValidationError("Le matricule doit contenir exactement 12 chiffres.")
        return student_number

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if password1 and password2 and password1 != password2:
            self.add_error('password2', "Les deux mots de passe ne correspondent pas.")

        return cleaned_data

    def save(self, commit=True):
        etudiant = super().save(commit=False)
        etudiant.set_password(self.cleaned_data['password1'])
        if commit:
            etudiant.save()
        return etudiant


class EtudiantAdminForm(forms.ModelForm):
    """Admin Django : le mot de passe saisi est toujours chiffré (set_password), sinon la connexion échoue."""

    mot_de_passe = forms.CharField(
        label='Mot de passe',
        widget=forms.PasswordInput(render_value=False),
        required=False,
        help_text='Obligatoire pour un nouvel étudiant. En modification, laisser vide pour ne pas changer.',
    )

    class Meta:
        model = Etudiant
        fields = ['student_number', 'nom', 'prenom', 'email', 'telephone']

    def clean(self):
        cleaned = super().clean()
        pwd = (cleaned.get('mot_de_passe') or '').strip()
        if not self.instance.pk and not pwd:
            raise ValidationError({'mot_de_passe': 'Renseignez un mot de passe pour le nouvel étudiant.'})
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        pwd = (self.cleaned_data.get('mot_de_passe') or '').strip()
        if pwd:
            instance.set_password(pwd)
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class ConducteurAdminForm(forms.ModelForm):
    """Même principe que pour les étudiants : mot de passe chiffré à l'enregistrement."""

    mot_de_passe = forms.CharField(
        label='Mot de passe',
        widget=forms.PasswordInput(render_value=False),
        required=False,
        help_text='Obligatoire pour un nouveau conducteur. En modification, laisser vide pour ne pas changer.',
    )

    class Meta:
        model = Conducteur
        fields = ['driver_id', 'nom', 'prenom', 'email', 'telephone']

    def clean(self):
        cleaned = super().clean()
        pwd = (cleaned.get('mot_de_passe') or '').strip()
        if not self.instance.pk and not pwd:
            raise ValidationError({'mot_de_passe': 'Renseignez un mot de passe pour le nouveau conducteur.'})
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        pwd = (self.cleaned_data.get('mot_de_passe') or '').strip()
        if pwd:
            instance.set_password(pwd)
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class EtudiantEditForm(forms.ModelForm):
    class Meta:
        model = Etudiant
        fields = ['student_number', 'nom', 'prenom', 'email', 'telephone']
        widgets = {
            'student_number': forms.TextInput(attrs={
                'placeholder': '012345678901',
                'pattern': '\\d{12}',
                'maxlength': '12',
                'minlength': '12',
                'required': 'required',
                'title': 'Le matricule doit contenir exactement 12 chiffres',
                'inputmode': 'numeric',
            }),
            'nom': forms.TextInput(attrs={'placeholder': 'Nom', 'required': 'required'}),
            'prenom': forms.TextInput(attrs={'placeholder': 'Prénom', 'required': 'required'}),
            'email': forms.EmailInput(attrs={'placeholder': 'email@example.com', 'required': 'required'}),
            'telephone': forms.TextInput(attrs={'placeholder': 'Téléphone'}),
        }
        labels = {
            'student_number': 'Matricule étudiant',
            'nom': 'Nom',
            'prenom': 'Prénom',
            'email': 'Email',
            'telephone': 'Téléphone',
        }

    def clean_student_number(self):
        student_number = self.cleaned_data.get('student_number', '').strip()
        if len(student_number) != 12 or not student_number.isdigit():
            raise ValidationError("Le matricule doit contenir exactement 12 chiffres.")
        return student_number


class BusForm(forms.ModelForm):
    class Meta:
        model = Bus
        fields = ['numero_immatriculation', 'capacite', 'marque', 'date_mise_service', 'conducteur']
        widgets = {
            'numero_immatriculation': forms.TextInput(attrs={'placeholder': '123-ABC-45', 'required': 'required'}),
            'capacite': forms.NumberInput(attrs={'min': '1', 'required': 'required'}),
            'marque': forms.TextInput(attrs={'placeholder': 'Marque'}),
            'date_mise_service': forms.DateInput(attrs={'type': 'date'}),
            'conducteur': forms.Select(),
        }
        labels = {
            'numero_immatriculation': 'Immatriculation',
            'capacite': 'Capacité',
            'marque': 'Marque',
            'date_mise_service': 'Date de mise en service',
            'conducteur': 'Conducteur assigné',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['conducteur'].queryset = Conducteur.objects.all().order_by('nom', 'prenom')
        self.fields['conducteur'].required = False

    def clean_numero_immatriculation(self):
        numero_immatriculation = (self.cleaned_data.get('numero_immatriculation') or '').strip()
        duplicate_qs = Bus.objects.filter(numero_immatriculation=numero_immatriculation)

        if self.instance.pk:
            duplicate_qs = duplicate_qs.exclude(pk=self.instance.pk)

        if duplicate_qs.exists():
            raise ValidationError("Ce matricule existe deja. Veuillez saisir une immatriculation unique.")

        return numero_immatriculation

class LigneForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Le nom est généré automatiquement depuis les stations (départ/arrivée).
        self.fields['nom_ligne'].required = False
        self.fields['nom_ligne'].widget.attrs.pop('required', None)

    class Meta:
        model = Ligne
        fields = ['nom_ligne', 'description', 'distance_km']
        widgets = {
            'nom_ligne': forms.TextInput(attrs={'placeholder': 'Nom de la ligne'}),
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Description de la ligne'}),
            'distance_km': forms.NumberInput(attrs={'min': '0'}),
        }
        labels = {
            'nom_ligne': 'Nom de la ligne',
            'description': 'Description',
            'distance_km': 'Distance (km)',
        }


class HoraireForm(DeletedRowBypassValidationMixin, forms.ModelForm):
    class Meta:
        model = Horaire
        fields = ['jour_semaine', 'sens', 'heure_depart']
        widgets = {
            'jour_semaine': forms.Select(),
            'sens': forms.Select(),
            'heure_depart': forms.TimeInput(attrs={'type': 'time'}),
        }
        labels = {
            'jour_semaine': 'Jour',
            'sens': 'Sens de circulation',
            'heure_depart': 'Heure de départ',
        }


class HorairePairForm(forms.Form):
    jour_semaine = forms.ChoiceField(label='Jour', choices=Horaire.JOURS_SEMAINE)
    heure_depart_aller = forms.TimeField(
        label='Heure de départ aller',
        widget=forms.TimeInput(attrs={'type': 'time'})
    )
    heure_depart_retour = forms.TimeField(
        label='Heure de départ retour',
        widget=forms.TimeInput(attrs={'type': 'time'})
    )


HoraireFormSet = inlineformset_factory(
    Ligne,
    Horaire,
    form=HoraireForm,
    extra=4,
    can_delete=True,
)

class LigneStationForm(DeletedRowBypassValidationMixin, forms.ModelForm):
    class Meta:
        model = LigneStation
        fields = ['station', 'ordre']
        widgets = {
            'station': forms.Select(),
            'ordre': forms.NumberInput(attrs={'type': 'number', 'min': '1'}),
        }
        labels = {
            'station': 'Station',
            'ordre': 'Ordre d\'arrivée',
        }

LigneStationFormSet = inlineformset_factory(
    Ligne,
    LigneStation,
    form=LigneStationForm,
    extra=3,
    can_delete=True,
)

class StationForm(forms.ModelForm):
    def clean(self):
        cleaned_data = super().clean()
        latitude = cleaned_data.get('latitude')
        longitude = cleaned_data.get('longitude')

        if latitude is None or longitude is None:
            return cleaned_data

        duplicate_qs = Station.objects.filter(latitude=latitude, longitude=longitude)
        if self.instance.pk:
            duplicate_qs = duplicate_qs.exclude(pk=self.instance.pk)

        if duplicate_qs.exists():
            raise ValidationError("Deux stations ne peuvent pas avoir exactement les mêmes coordonnées GPS.")

        return cleaned_data

    class Meta:
        model = Station
        fields = ['nom_station', 'adresse', 'latitude', 'longitude']
        widgets = {
            'nom_station': forms.TextInput(attrs={'placeholder': 'Nom de la station', 'required': 'required'}),
            'adresse': forms.TextInput(attrs={'placeholder': 'Adresse complète', 'required': 'required'}),
            'latitude': forms.NumberInput(attrs={'step': '0.000001', 'placeholder': '48.8566'}),
            'longitude': forms.NumberInput(attrs={'step': '0.000001', 'placeholder': '2.3522'}),
        }
        labels = {
            'nom_station': 'Nom de la station',
            'adresse': 'Adresse',
            'latitude': 'Latitude',
            'longitude': 'Longitude',
        }

class AffectationBusLigneForm(forms.ModelForm):
    class Meta:
        model = AffectationBusLigne
        fields = ['bus', 'ligne', 'conducteur', 'date_debut', 'date_fin']
        widgets = {
            'bus': forms.Select(attrs={'required': 'required'}),
            'ligne': forms.Select(attrs={'required': 'required'}),
            'conducteur': forms.Select(attrs={}),
            'date_debut': forms.DateInput(attrs={'type': 'date', 'required': 'required'}),
            'date_fin': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'bus': 'Bus',
            'ligne': 'Ligne',
            'conducteur': 'Conducteur',
            'date_debut': 'Date de début',
            'date_fin': 'Date de fin',
        }

    def clean(self):
        cleaned_data = super().clean()
        bus = cleaned_data.get('bus')
        ligne = cleaned_data.get('ligne')
        date_debut = cleaned_data.get('date_debut')
        date_fin = cleaned_data.get('date_fin')

        if not all([bus, ligne, date_debut]):
            return cleaned_data

        # Vérifier que la date de fin est postérieure à la date de début
        if date_fin and date_fin < date_debut:
            raise ValidationError("La date de fin doit être postérieure à la date de début.")

        _validate_ligne_has_required_sens(ligne)

        # Vérifier qu'un bus n'est pas affecté à deux lignes dans la même période
        # Exclure l'affectation actuelle si elle existe (pour les modifications)
        existing_affectations = AffectationBusLigne.objects.filter(bus=bus)
        
        if self.instance.pk:
            existing_affectations = existing_affectations.exclude(pk=self.instance.pk)

        for affectation in existing_affectations:
            # Vérifier le chevauchement des périodes
            period_start = affectation.date_debut
            period_end = affectation.date_fin if affectation.date_fin else date(9999, 12, 31)
            
            new_start = date_debut
            new_end = date_fin if date_fin else date(9999, 12, 31)

            # Chevauchement si : start1 <= end2 et start2 <= end1
            if new_start <= period_end and period_start <= new_end:
                raise ValidationError(
                    f"Le bus {bus.numero_immatriculation} est déjà affecté à la ligne {affectation.ligne.nom_ligne} "
                    f"pendant la période du {affectation.date_debut} au {affectation.date_fin or 'aujourd\'hui'}. "
                    f"Un bus ne peut pas être affecté à deux lignes dans la même période."
                )

        return cleaned_data

class BulkAffectationBusLigneForm(forms.Form):
    """Formulaire pour affecter plusieurs bus à une ligne"""
    ligne = forms.ModelChoiceField(
        queryset=Ligne.objects.all(),
        empty_label="Choisir une ligne",
        widget=forms.Select(attrs={'required': 'required'}),
        label="Ligne"
    )
    date_debut = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'required': 'required'}),
        label="Date de début"
    )
    date_fin = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label="Date de fin (optionnel)"
    )

    def clean(self):
        cleaned_data = super().clean()
        ligne = cleaned_data.get('ligne')
        date_debut = cleaned_data.get('date_debut')
        date_fin = cleaned_data.get('date_fin')

        if not all([ligne, date_debut]):
            return cleaned_data

        # Vérifier que la date de fin est postérieure à la date de début
        if date_fin and date_fin < date_debut:
            raise ValidationError("La date de fin doit être postérieure à la date de début.")

        return cleaned_data


class BusWithAffectationsForm(forms.ModelForm):
    """Formulaire pour modifier un bus et ses affectations"""

    # Champs pour ajouter une nouvelle affectation
    new_ligne = forms.ModelChoiceField(
        queryset=Ligne.objects.all(),
        required=False,
        empty_label="Sélectionner une ligne",
        label="Ajouter une affectation à la ligne"
    )
    new_date_debut = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label="Date de début"
    )
    new_date_fin = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label="Date de fin (optionnel)"
    )

    class Meta:
        model = Bus
        fields = ['numero_immatriculation', 'capacite', 'marque', 'date_mise_service', 'conducteur']
        widgets = {
            'numero_immatriculation': forms.TextInput(attrs={'placeholder': '123-ABC-45', 'required': 'required'}),
            'capacite': forms.NumberInput(attrs={'min': '1', 'required': 'required'}),
            'marque': forms.TextInput(attrs={'placeholder': 'Marque'}),
            'date_mise_service': forms.DateInput(attrs={'type': 'date'}),
            'conducteur': forms.Select(),
        }
        labels = {
            'numero_immatriculation': 'Immatriculation',
            'capacite': 'Capacité',
            'marque': 'Marque',
            'date_mise_service': 'Date de mise en service',
            'conducteur': 'Conducteur assigné',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['conducteur'].queryset = Conducteur.objects.all().order_by('nom', 'prenom')
        self.fields['conducteur'].required = False
        if self.instance and self.instance.pk:
            # Formulaire pour les affectations existantes
            self.affectations = AffectationBusLigne.objects.filter(bus=self.instance).order_by('date_debut')
        else:
            self.affectations = AffectationBusLigne.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        new_ligne = cleaned_data.get('new_ligne')
        new_date_debut = cleaned_data.get('new_date_debut')
        new_date_fin = cleaned_data.get('new_date_fin')

        # Si on essaie d'ajouter une nouvelle affectation, vérifier que ligne et date_debut sont fournis
        if new_ligne and not new_date_debut:
            raise ValidationError("La date de début est requise pour une nouvelle affectation.")
        if new_date_debut and not new_ligne:
            raise ValidationError("La ligne est requise pour une nouvelle affectation.")

        # Vérifier que la date de fin est postérieure à la date de début
        if new_date_fin and new_date_debut and new_date_fin < new_date_debut:
            raise ValidationError("La date de fin doit être postérieure ou égale à la date de début.")

        if new_ligne and new_date_debut:
            _validate_ligne_has_required_sens(new_ligne)

        # Vérifier qu'un bus n'est pas affecté à deux lignes dans la même période
        if new_ligne and new_date_debut and self.instance and self.instance.pk:
            bus = self.instance
            existing_affectations = AffectationBusLigne.objects.filter(bus=bus)

            for affectation in existing_affectations:
                # Vérifier le chevauchement des périodes
                period_start = affectation.date_debut
                period_end = affectation.date_fin if affectation.date_fin else date(9999, 12, 31)
                
                new_start = new_date_debut
                new_end = new_date_fin if new_date_fin else date(9999, 12, 31)

                # Chevauchement si : start1 <= end2 et start2 <= end1
                if new_start <= period_end and period_start <= new_end:
                    raise ValidationError(
                        f"Le bus {bus.numero_immatriculation} est déjà affecté à la ligne {affectation.ligne.nom_ligne} "
                        f"durant la période du {affectation.date_debut.strftime('%d/%m/%Y')} "
                        f"au {affectation.date_fin.strftime('%d/%m/%Y') if affectation.date_fin else 'aujourd\'hui'}. "
                        f"Un bus ne peut pas être affecté à deux lignes dans la même période."
                    )

        return cleaned_data


class TrajetEditForm(forms.ModelForm):
    class Meta:
        model = Trajet
        fields = ['horaire', 'date_trajet', 'retard_minutes']
        widgets = {
            'horaire': forms.Select(attrs={'required': 'required'}),
            'date_trajet': forms.DateInput(attrs={'type': 'date', 'required': 'required'}),
            'retard_minutes': forms.NumberInput(attrs={'min': '0', 'required': 'required'}),
        }
        labels = {
            'horaire': 'Horaire',
            'date_trajet': 'Date du trajet',
            'retard_minutes': 'Retard (minutes)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['horaire'].queryset = Horaire.objects.filter(ligne=self.instance.ligne).order_by('jour_semaine', 'heure_depart')

# creat ConducteurRegistrationForm

class ConducteurRegistrationForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Mot de passe',
        widget=forms.PasswordInput(attrs={'placeholder': 'Mot de passe', 'required': 'required'}),
    )
    password2 = forms.CharField(
        label='Confirmer le mot de passe',
        widget=forms.PasswordInput(attrs={'placeholder': 'Confirmer le mot de passe', 'required': 'required'}),
    )    

    class Meta:
        model = Conducteur
        fields = ['driver_id', 'prenom', 'nom', 'email', 'telephone']
        widgets = {
            'driver_id': forms.TextInput(attrs={'required': 'required'}),
            'prenom': forms.TextInput(attrs={'required': 'required'}),
            'nom': forms.TextInput(attrs={'required': 'required'}),
            'email': forms.EmailInput(attrs={'required': 'required'}),
            'telephone': forms.TextInput(attrs={'required': 'required'}),
        }
        labels = {
            'driver_id': 'ID Conducteur',
            'prenom': 'Prénom',
            'nom': 'Nom',
            'email': 'Email',
            'telephone': 'Téléphone',
        }

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if password1 and password2 and password1 != password2:
            self.add_error('password2', "Les deux mots de passe ne correspondent pas.")

        return cleaned_data

    def save(self, commit=True):
        conducteur = super().save(commit=False)
        conducteur.set_password(self.cleaned_data['password1'])
        if commit:
            conducteur.save()
        return conducteur


class ConducteurEditForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Nouveau mot de passe',
        required=False,
        widget=forms.PasswordInput(attrs={'placeholder': 'Laisser vide pour ne pas changer'}),
    )
    password2 = forms.CharField(
        label='Confirmer le nouveau mot de passe',
        required=False,
        widget=forms.PasswordInput(attrs={'placeholder': 'Confirmer le nouveau mot de passe'}),
    )

    class Meta:
        model = Conducteur
        fields = ['driver_id', 'prenom', 'nom', 'email', 'telephone']
        widgets = {
            'driver_id': forms.TextInput(attrs={'required': 'required'}),
            'prenom': forms.TextInput(attrs={'required': 'required'}),
            'nom': forms.TextInput(attrs={'required': 'required'}),
            'email': forms.EmailInput(attrs={'required': 'required'}),
            'telephone': forms.TextInput(),
        }
        labels = {
            'driver_id': 'ID Conducteur',
            'prenom': 'Prénom',
            'nom': 'Nom',
            'email': 'Email',
            'telephone': 'Téléphone',
        }

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if password1 or password2:
            if password1 != password2:
                self.add_error('password2', "Les deux mots de passe ne correspondent pas.")

        return cleaned_data

    def save(self, commit=True):
        conducteur = super().save(commit=False)
        new_password = self.cleaned_data.get('password1')
        if new_password:
            conducteur.set_password(new_password)
        if commit:
            conducteur.save()
        return conducteur
