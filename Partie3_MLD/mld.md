# Partie 3 : Modélisation Logique (MLD)

## Transformation du modèle Entité-Association en modèle relationnel

Le modèle logique est obtenu en transformant les entités et associations en tables relationnelles.

### Tables principales

1. **ETUDIANT** (id_etudiant, nom, prenom, email, telephone, date_inscription)
   - **Clé primaire** : id_etudiant
   - **Clés étrangères** : aucune

2. **BUS** (id_bus, numero_immatriculation, capacite, marque, date_mise_service)
   - **Clé primaire** : id_bus
   - **Clés étrangères** : aucune

3. **LIGNE** (id_ligne, nom_ligne, description, distance_km)
   - **Clé primaire** : id_ligne
   - **Clés étrangères** : aucune

4. **STATION** (id_station, nom_station, adresse, latitude, longitude)
   - **Clé primaire** : id_station
   - **Clés étrangères** : aucune

5. **HORAIRE** (id_horaire, id_ligne, jour_semaine, heure_depart, heure_arrivee)
   - **Clé primaire** : id_horaire
   - **Clé étrangère** : id_ligne → LIGNE(id_ligne)

6. **AFFECTATION_ETUDIANT_LIGNE** (id_affectation_etudiant, id_etudiant, id_ligne, date_debut, date_fin)
   - **Clé primaire** : id_affectation_etudiant
   - **Clés étrangères** : id_etudiant → ETUDIANT(id_etudiant), id_ligne → LIGNE(id_ligne)

7. **AFFECTATION_BUS_LIGNE** (id_affectation_bus, id_bus, id_ligne, date_debut, date_fin)
   - **Clé primaire** : id_affectation_bus
   - **Clés étrangères** : id_bus → BUS(id_bus), id_ligne → LIGNE(id_ligne)

8. **LIGNE_STATION** (id_ligne, id_station, ordre)
   - **Clé primaire** : (id_ligne, id_station)
   - **Clés étrangères** : id_ligne → LIGNE(id_ligne), id_station → STATION(id_station)
   - **Note** : Table d'association pour la relation many-to-many entre LIGNE et STATION. L'attribut "ordre" indique l'ordre des stations sur la ligne.

9. **TRAJET** (id_trajet, id_bus, id_ligne, id_horaire, date_trajet, retard_minutes)
   - **Clé primaire** : id_trajet
   - **Clés étrangères** : id_bus → BUS(id_bus), id_ligne → LIGNE(id_ligne), id_horaire → HORAIRE(id_horaire)

10. **INCIDENT** (id_incident, id_trajet, description, date_heure_incident, type_incident)
    - **Clé primaire** : id_incident
    - **Clé étrangère** : id_trajet → TRAJET(id_trajet)

## Contraintes d'intégrité

- **Clés primaires** : Auto-incrémentées pour les ID.
- **Clés étrangères** : Avec contrainte de référence (RESTRICT ou CASCADE selon besoin).
- **Contraintes métier** :
  - date_fin >= date_debut dans les tables d'affectation.
  - retard_minutes >= 0 dans TRAJET.
  - jour_semaine ∈ {'lundi', 'mardi', ..., 'dimanche'} dans HORAIRE.
  - ordre > 0 dans LIGNE_STATION.
  - Unicité : Un étudiant ne peut avoir qu'une affectation active (date_fin IS NULL) à la fois (contrainte à vérifier via trigger ou application).

## Schéma relationnel complet

```
ETUDIANT(id_etudiant, nom, prenom, email, telephone, date_inscription)
BUS(id_bus, numero_immatriculation, capacite, marque, date_mise_service)
LIGNE(id_ligne, nom_ligne, description, distance_km)
STATION(id_station, nom_station, adresse, latitude, longitude)
HORAIRE(id_horaire, #id_ligne, jour_semaine, heure_depart, heure_arrivee)
AFFECTATION_ETUDIANT_LIGNE(id_affectation_etudiant, #id_etudiant, #id_ligne, date_debut, date_fin)
AFFECTATION_BUS_LIGNE(id_affectation_bus, #id_bus, #id_ligne, date_debut, date_fin)
LIGNE_STATION(#id_ligne, #id_station, ordre)
TRAJET(id_trajet, #id_bus, #id_ligne, #id_horaire, date_trajet, retard_minutes)
INCIDENT(id_incident, #id_trajet, description, date_heure_incident, type_incident)
```