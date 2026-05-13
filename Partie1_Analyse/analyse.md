# Partie 1 : Analyse

## Compréhension du problème

Le système de gestion du transport universitaire en Algérie fait face à plusieurs défis majeurs :

- **Surcharge des bus** : Les bus sont souvent pleins, causant inconfort et retards.
- **Mauvaise répartition des étudiants** : Les étudiants ne sont pas équitablement distribués sur les lignes.
- **Manque de visibilité sur les horaires** : Les étudiants ne connaissent pas facilement les horaires.
- **Absence de suivi des affectations** : Pas de traçabilité des changements d'abonnement ou d'affectation des bus.
- **Gestion inefficace des changements et incidents** : Les retards et incidents ne sont pas gérés systématiquement.

Le projet vise à concevoir une base de données pour une plateforme web/mobile qui améliore cette gestion.

## Fonctionnalités requises

- Gestion des étudiants et abonnements
- Gestion des bus et capacités
- Gestion des lignes de transport
- Gestion des stations et trajets
- Planification des horaires
- Affectation bus-lignes
- Affectation étudiants-lignes
- Suivi historique des affectations
- Gestion des incidents et retards

## Contraintes métier (règles de gestion)

- Un étudiant abonné à une seule ligne à la fois
- Une ligne dessert plusieurs stations
- Une station appartient à plusieurs lignes
- Un bus a une capacité maximale
- Un bus affecté à une ligne pour une période donnée
- Une ligne a plusieurs horaires selon les jours
- Un étudiant peut changer de ligne (historique conservé)
- Les affectations des bus sont historisées
- Un trajet = passage d'un bus sur une ligne à un horaire donné

## Contraintes supplémentaires identifiées

- Chaque entité (étudiant, bus, ligne, station) a un identifiant unique
- Les horaires sont définis par jour de la semaine (lundi-dimanche)
- Les affectations ont des dates de début et fin
- Les trajets peuvent avoir des retards (en minutes)
- Les incidents sont associés aux trajets
- Un bus ne peut être affecté qu'à une ligne à la fois (implicite)
- Les étudiants doivent être inscrits pour s'abonner
- Les bus doivent être en service pour être affectés

## Entités principales identifiées

1. **Étudiant** : ID, nom, prénom, email, téléphone, etc.
2. **Bus** : ID, capacité, numéro d'immatriculation, etc.
3. **Ligne** : ID, nom, description, etc.
4. **Station** : ID, nom, adresse, etc.
5. **Horaire** : ID, ligne_ID, jour, heure_départ, etc.
6. **Affectation_Étudiant_Ligne** : ID, étudiant_ID, ligne_ID, date_début, date_fin
7. **Affectation_Bus_Ligne** : ID, bus_ID, ligne_ID, date_début, date_fin
8. **Trajet** : ID, bus_ID, ligne_ID, horaire_ID, date, retard_minutes
9. **Incident** : ID, trajet_ID, description, date_heure

## Associations

- Ligne ↔ Station : many-to-many (table Ligne_Station avec ordre?)
- Étudiant → Ligne : one-to-many (via affectation)
- Bus → Ligne : one-to-many (via affectation)
- Trajet → Bus, Ligne, Horaire
- Incident → Trajet