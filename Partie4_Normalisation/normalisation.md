# Partie 4 : Normalisation

## Normalisation jusqu'à BCNF

La normalisation vise à éliminer les redondances et les anomalies dans la base de données en appliquant les formes normales.

### Rappel des formes normales

- **1NF** : Attributs atomiques, pas de groupes répétitifs.
- **2NF** : Pas de dépendance partielle (tous les attributs non-clés dépendent de la clé entière).
- **3NF** : Pas de dépendance transitive (attributs non-clés ne dépendent pas d'autres attributs non-clés).
- **BCNF** : Tout déterminant est une clé candidate.

### Analyse du schéma relationnel

Le schéma obtenu après transformation est déjà en 3NF et BCNF, car :

1. **Toutes les tables sont en 1NF** : Attributs atomiques (pas de listes ou structures complexes).

2. **Toutes les tables sont en 2NF** : 
   - Les clés primaires sont simples (un seul attribut) ou composées.
   - Aucun attribut non-clé ne dépend d'une partie de la clé.

3. **Toutes les tables sont en 3NF** :
   - Pas de dépendance transitive.
   - Exemple : Dans HORAIRE(id_horaire, id_ligne, jour_semaine, heure_depart, heure_arrivee), id_horaire → id_ligne, mais id_ligne → nom_ligne est dans une autre table. Aucun attribut non-clé ne dépend d'un autre attribut non-clé.

4. **Toutes les tables sont en BCNF** :
   - Les seuls déterminants sont les clés primaires.
   - Aucun attribut non-clé ne détermine un autre attribut.
   - Exemple : id_ligne apparaît dans plusieurs tables comme FK, mais n'est pas un déterminant dans ces tables (il ne détermine pas d'autres attributs dans la même table).

### Dépendances fonctionnelles identifiées

- ETUDIANT : id_etudiant → nom, prenom, email, telephone, date_inscription
- BUS : id_bus → numero_immatriculation, capacite, marque, date_mise_service
- LIGNE : id_ligne → nom_ligne, description, distance_km
- STATION : id_station → nom_station, adresse, latitude, longitude
- HORAIRE : id_horaire → id_ligne, jour_semaine, heure_depart, heure_arrivee
- AFFECTATION_ETUDIANT_LIGNE : id_affectation_etudiant → id_etudiant, id_ligne, date_debut, date_fin
- AFFECTATION_BUS_LIGNE : id_affectation_bus → id_bus, id_ligne, date_debut, date_fin
- LIGNE_STATION : (id_ligne, id_station) → ordre
- TRAJET : id_trajet → id_bus, id_ligne, id_horaire, date_trajet, retard_minutes
- INCIDENT : id_incident → id_trajet, description, date_heure_incident, type_incident

Aucune dépendance fonctionnelle problématique n'est présente. Le schéma est donc en BCNF sans nécessiter de décomposition supplémentaire.

### Conclusion

Le modèle relationnel est normalisé jusqu'à la forme normale de Boyce-Codd (BCNF). Aucune anomalie d'insertion, de suppression ou de mise à jour n'est attendue.