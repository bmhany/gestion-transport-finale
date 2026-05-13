from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import AffectationBusLigne, AffectationEtudiantLigne, Bus, Conducteur, Etudiant, Horaire, Ligne, LigneStation, ReservationTrajet, Station, Trajet


class AdminCrudViewsTestCase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='AdminPass123!'
        )
        self.admin.is_staff = True
        self.admin.is_superuser = True
        self.admin.save()
        self.client.force_login(self.admin)

        self.station_a = Station.objects.create(nom_station='Cite U', adresse='Adresse A')
        self.station_b = Station.objects.create(nom_station='Faculte', adresse='Adresse B')
        self.station_c = Station.objects.create(nom_station='Tramway', adresse='Adresse C')

    def _create_line_with_roundtrip(self, name='Ligne Test'):
        ligne = Ligne.objects.create(nom_ligne=name)
        LigneStation.objects.create(ligne=ligne, station=self.station_a, ordre=1)
        LigneStation.objects.create(ligne=ligne, station=self.station_b, ordre=2)
        Horaire.objects.create(
            ligne=ligne,
            jour_semaine='lundi',
            sens='aller',
            heure_depart='08:00',
            heure_arrivee='09:00',
        )
        Horaire.objects.create(
            ligne=ligne,
            jour_semaine='lundi',
            sens='retour',
            heure_depart='09:30',
            heure_arrivee='10:30',
        )
        return ligne

    def _create_driver(self, driver_id='DRV-001', email='drv1@example.com'):
        driver = Conducteur.objects.create(
            driver_id=driver_id,
            nom='Benali',
            prenom='Yacine',
            email=email,
            telephone='0555000000',
        )
        driver.set_password('DriverPass123!')
        driver.save()
        return driver

    def test_add_and_edit_student(self):
        add_url = reverse('gestion_transport:inscription')
        response = self.client.post(add_url, {
            'student_number': '123456789012',
            'nom': 'Doe',
            'prenom': 'John',
            'email': 'john.doe@example.com',
            'telephone': '0555123456',
            'password1': 'EtuPass123!',
            'password2': 'EtuPass123!',
        })
        self.assertEqual(response.status_code, 302)
        student = Etudiant.objects.get(student_number='123456789012')

        edit_url = reverse('gestion_transport:edit_etudiant', args=[student.id])
        response = self.client.post(edit_url, {
            'student_number': '123456789012',
            'nom': 'DoeUpdated',
            'prenom': 'John',
            'email': 'john.updated@example.com',
            'telephone': '0666000000',
        })
        self.assertEqual(response.status_code, 302)

        student.refresh_from_db()
        self.assertEqual(student.nom, 'DoeUpdated')
        self.assertEqual(student.email, 'john.updated@example.com')

    def test_add_and_edit_conducteur(self):
        add_url = reverse('gestion_transport:inscription_driver')
        response = self.client.post(add_url, {
            'driver_id': 'DRV-100',
            'nom': 'Mansouri',
            'prenom': 'Ahmed',
            'email': 'ahmed@example.com',
            'telephone': '0555111111',
            'password1': 'DriverPass123!',
            'password2': 'DriverPass123!',
        })
        self.assertEqual(response.status_code, 302)
        conducteur = Conducteur.objects.get(driver_id='DRV-100')

        edit_url = reverse('gestion_transport:edit_conducteur', args=[conducteur.id])
        response = self.client.post(edit_url, {
            'driver_id': 'DRV-100',
            'nom': 'MansouriMaj',
            'prenom': 'Ahmed',
            'email': 'ahmed.maj@example.com',
            'telephone': '0777000000',
            'password1': 'NewDriverPass123!',
            'password2': 'NewDriverPass123!',
        })
        self.assertEqual(response.status_code, 302)

        conducteur.refresh_from_db()
        self.assertEqual(conducteur.nom, 'MansouriMaj')
        self.assertEqual(conducteur.email, 'ahmed.maj@example.com')

    def test_add_and_edit_station(self):
        add_url = reverse('gestion_transport:add_station')
        response = self.client.post(add_url, {
            'nom_station': 'Gare Centrale',
            'adresse': 'Alger Centre',
            'latitude': '36.752887',
            'longitude': '3.042048',
        })
        self.assertEqual(response.status_code, 302)
        station = Station.objects.get(nom_station='Gare Centrale')

        edit_url = reverse('gestion_transport:edit_station', args=[station.id])
        response = self.client.post(edit_url, {
            'nom_station': 'Gare Centrale Mod',
            'adresse': 'Alger Centre Mod',
            'latitude': '36.752000',
            'longitude': '3.043000',
        })
        self.assertEqual(response.status_code, 302)

        station.refresh_from_db()
        self.assertEqual(station.nom_station, 'Gare Centrale Mod')

    def test_add_station_rejects_duplicate_exact_gps(self):
        Station.objects.create(
            nom_station='Station GPS A',
            adresse='Adresse A',
            latitude='36.752887',
            longitude='3.042048',
        )

        response = self.client.post(reverse('gestion_transport:add_station'), {
            'nom_station': 'Station GPS B',
            'adresse': 'Adresse B',
            'latitude': '36.752887',
            'longitude': '3.042048',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Deux stations ne peuvent pas avoir exactement les mêmes coordonnées GPS.')
        self.assertEqual(Station.objects.filter(latitude='36.752887', longitude='3.042048').count(), 1)

    def test_delete_station_removes_associated_lines(self):
        ligne = self._create_line_with_roundtrip('Ligne Station Delete')
        self.assertTrue(Ligne.objects.filter(id=ligne.id).exists())
        self.assertTrue(LigneStation.objects.filter(station=self.station_a).exists())

        delete_url = reverse('gestion_transport:delete_station', args=[self.station_a.id])
        response = self.client.post(delete_url)
        self.assertEqual(response.status_code, 302)

        self.assertFalse(Station.objects.filter(id=self.station_a.id).exists())
        self.assertFalse(Ligne.objects.filter(id=ligne.id).exists())
        self.assertFalse(LigneStation.objects.filter(station=self.station_a).exists())
        self.assertFalse(Horaire.objects.filter(ligne_id=ligne.id).exists())

    def test_student_cannot_subscribe_twice_to_same_line(self):
        ligne = self._create_line_with_roundtrip('Ligne Abonnement Unique')
        etudiant = Etudiant.objects.create(
            student_number='999999999999',
            nom='Dupont',
            prenom='Nadia',
            email='nadia.dupont@example.com',
            telephone='0555999999',
        )
        etudiant.set_password('EtuPass123!')
        etudiant.save()

        AffectationEtudiantLigne.objects.create(
            etudiant=etudiant,
            ligne=ligne,
            date_debut=date.today(),
        )

        response = self.client.post(
            reverse('gestion_transport:subscribe_to_line'),
            data={
                'student_id': etudiant.student_number,
                'ligne_id': ligne.id,
                'date_debut': str(date.today()),
                'date_fin': '',
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {'success': False, 'error': 'Un étudiant ne peut pas avoir deux abonnements à la même ligne.'}
        )
        self.assertEqual(AffectationEtudiantLigne.objects.filter(etudiant=etudiant, ligne=ligne).count(), 1)


class StudentTicketsViewTestCase(TestCase):
    def setUp(self):
        self.station_a = Station.objects.create(nom_station='Cite Ticket', adresse='Adresse Ticket A')
        self.station_b = Station.objects.create(nom_station='Fac Ticket', adresse='Adresse Ticket B')
        self.ligne = Ligne.objects.create(nom_ligne='Ligne Tickets')
        LigneStation.objects.create(ligne=self.ligne, station=self.station_a, ordre=1)
        LigneStation.objects.create(ligne=self.ligne, station=self.station_b, ordre=2)
        self.horaire = Horaire.objects.create(
            ligne=self.ligne,
            jour_semaine='lundi',
            sens='aller',
            heure_depart='08:00',
            heure_arrivee='09:00',
        )
        self.bus = Bus.objects.create(numero_immatriculation='TICKET-BUS-01', capacite=40)
        self.etudiant = Etudiant.objects.create(
            student_number='111122223333',
            nom='Ticket',
            prenom='Student',
            email='ticket.student@example.com',
            telephone='0555000011',
        )
        self.etudiant.set_password('StudentPass123!')
        self.etudiant.save()
        session = self.client.session
        session['student_number'] = self.etudiant.student_number
        session.save()

    def test_student_tickets_page_backfills_missing_ticket_codes(self):
        trajet = Trajet.objects.create(
            bus=self.bus,
            ligne=self.ligne,
            horaire=self.horaire,
            date_trajet=date.today() + timedelta(days=1),
        )
        reservation = ReservationTrajet.objects.create(etudiant=self.etudiant, trajet=trajet, ticket_code=None)
        ReservationTrajet.objects.filter(pk=reservation.pk).update(ticket_code=None)

        response = self.client.get(reverse('gestion_transport:student_tickets'))

        self.assertEqual(response.status_code, 200)
        reservation.refresh_from_db()
        self.assertTrue(reservation.ticket_code)
        self.assertContains(response, reservation.ticket_code)
        self.assertContains(response, 'Mes tickets bus')

    def test_add_and_edit_ligne_with_formsets(self):
        add_url = reverse('gestion_transport:add_ligne')
        add_payload = {
            'nom_ligne': '',
            'description': 'Ligne de test',
            'distance_km': '12',
            'stations-TOTAL_FORMS': '2',
            'stations-INITIAL_FORMS': '0',
            'stations-MIN_NUM_FORMS': '0',
            'stations-MAX_NUM_FORMS': '1000',
            'stations-0-id': '',
            'stations-0-ligne': '',
            'stations-0-station': str(self.station_a.id),
            'stations-0-ordre': '1',
            'stations-1-id': '',
            'stations-1-ligne': '',
            'stations-1-station': str(self.station_b.id),
            'stations-1-ordre': '2',
            'horaires-TOTAL_FORMS': '2',
            'horaires-INITIAL_FORMS': '0',
            'horaires-MIN_NUM_FORMS': '0',
            'horaires-MAX_NUM_FORMS': '1000',
            'horaires-0-id': '',
            'horaires-0-ligne': '',
            'horaires-0-jour_semaine': 'lundi',
            'horaires-0-sens': 'aller',
            'horaires-0-heure_depart': '08:00',
            'horaires-1-id': '',
            'horaires-1-ligne': '',
            'horaires-1-jour_semaine': 'mardi',
            'horaires-1-sens': 'retour',
            'horaires-1-heure_depart': '10:00',
        }
        response = self.client.post(add_url, add_payload)
        self.assertEqual(response.status_code, 302)

        ligne = Ligne.objects.latest('id')
        self.assertEqual(Horaire.objects.filter(ligne=ligne).count(), 2)
        self.assertEqual(LigneStation.objects.filter(ligne=ligne).count(), 2)
        horaires = list(Horaire.objects.filter(ligne=ligne).order_by('id'))
        self.assertEqual(horaires[0].heure_arrivee.strftime('%H:%M'), '09:00')
        self.assertEqual(horaires[1].heure_arrivee.strftime('%H:%M'), '11:00')

        edit_url = reverse('gestion_transport:edit_ligne', args=[ligne.id])
        stations = list(LigneStation.objects.filter(ligne=ligne).order_by('ordre'))

        edit_payload = {
            'nom_ligne': ligne.nom_ligne,
            'description': 'Ligne modifiee',
            'distance_km': '14',
            'stations-TOTAL_FORMS': '2',
            'stations-INITIAL_FORMS': '2',
            'stations-MIN_NUM_FORMS': '0',
            'stations-MAX_NUM_FORMS': '1000',
            'stations-0-id': str(stations[0].id),
            'stations-0-ligne': str(ligne.id),
            'stations-0-station': str(self.station_a.id),
            'stations-0-ordre': '1',
            'stations-1-id': str(stations[1].id),
            'stations-1-ligne': str(ligne.id),
            'stations-1-station': str(self.station_c.id),
            'stations-1-ordre': '2',
            'horaires-TOTAL_FORMS': '2',
            'horaires-INITIAL_FORMS': '2',
            'horaires-MIN_NUM_FORMS': '0',
            'horaires-MAX_NUM_FORMS': '1000',
            'horaires-0-id': str(horaires[0].id),
            'horaires-0-ligne': str(ligne.id),
            'horaires-0-jour_semaine': 'lundi',
            'horaires-0-sens': 'aller',
            'horaires-0-heure_depart': '08:10',
            'horaires-1-id': str(horaires[1].id),
            'horaires-1-ligne': str(ligne.id),
            'horaires-1-jour_semaine': 'mardi',
            'horaires-1-sens': 'retour',
            'horaires-1-heure_depart': '10:10',
        }
        response = self.client.post(edit_url, edit_payload)
        self.assertEqual(response.status_code, 302)

        ligne.refresh_from_db()
        self.assertEqual(ligne.description, 'Ligne modifiee')
        self.assertTrue(LigneStation.objects.filter(ligne=ligne, station=self.station_c).exists())
        horaires = list(Horaire.objects.filter(ligne=ligne).order_by('id'))
        self.assertEqual(horaires[0].heure_arrivee.strftime('%H:%M'), '09:10')
        self.assertEqual(horaires[1].heure_arrivee.strftime('%H:%M'), '11:10')

    def test_add_and_edit_bus(self):
        driver = self._create_driver('DRV-200', 'drv200@example.com')

        add_url = reverse('gestion_transport:add_bus')
        response = self.client.post(add_url, {
            'numero_immatriculation': '123-TEST-01',
            'capacite': '50',
            'marque': 'Mercedes',
            'date_mise_service': '2024-01-01',
            'conducteur': str(driver.id),
        })
        self.assertEqual(response.status_code, 302)
        bus = Bus.objects.get(numero_immatriculation='123-TEST-01')

        edit_url = reverse('gestion_transport:edit_bus', args=[bus.id])
        response = self.client.post(edit_url, {
            'numero_immatriculation': '123-TEST-01',
            'capacite': '55',
            'marque': 'Volvo',
            'date_mise_service': '2024-02-01',
            'conducteur': str(driver.id),
            'new_ligne': '',
            'new_date_debut': '',
            'new_date_fin': '',
        })
        self.assertEqual(response.status_code, 302)

        bus.refresh_from_db()
        self.assertEqual(bus.capacite, 55)
        self.assertEqual(bus.marque, 'Volvo')

    def test_add_bus_duplicate_matricule_shows_field_error(self):
        Bus.objects.create(numero_immatriculation='123-TEST-01', capacite=40, marque='Mercedes')

        response = self.client.post(reverse('gestion_transport:add_bus'), {
            'numero_immatriculation': '123-TEST-01',
            'capacite': '50',
            'marque': 'Volvo',
            'date_mise_service': '2024-01-01',
            'conducteur': '',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ce matricule existe deja. Veuillez saisir une immatriculation unique.')
        self.assertEqual(Bus.objects.filter(numero_immatriculation='123-TEST-01').count(), 1)

    def test_add_and_edit_affectation(self):
        ligne = self._create_line_with_roundtrip('Ligne Affectation')
        bus = Bus.objects.create(numero_immatriculation='456-TEST-02', capacite=40)
        conducteur_1 = self._create_driver('DRV-300', 'drv300@example.com')
        conducteur_2 = self._create_driver('DRV-301', 'drv301@example.com')

        add_url = reverse('gestion_transport:add_affectation_bus', args=[bus.id])
        response = self.client.post(add_url, {
            'ligne': str(ligne.id),
            'conducteur': str(conducteur_1.id),
            'date_debut': str(date.today()),
            'date_fin': str(date.today() + timedelta(days=30)),
        })
        self.assertEqual(response.status_code, 302)

        affectation = AffectationBusLigne.objects.get(bus=bus, ligne=ligne)

        edit_url = reverse('gestion_transport:edit_affectation', args=[affectation.id])
        response = self.client.post(edit_url, {
            'bus': str(bus.id),
            'ligne': str(ligne.id),
            'conducteur': str(conducteur_2.id),
            'date_debut': str(date.today()),
            'date_fin': str(date.today() + timedelta(days=45)),
            'confirm_conducteur_override': '1',
        })
        self.assertEqual(response.status_code, 302)

        affectation.refresh_from_db()
        self.assertEqual(affectation.conducteur_id, conducteur_2.id)
        self.assertEqual(affectation.date_fin, date.today() + timedelta(days=45))
