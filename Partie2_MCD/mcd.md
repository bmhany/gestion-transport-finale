# Partie 2 : Modélisation Conceptuelle (MCD)

## Modèle Entité-Association

Le modèle conceptuel est représenté ci-dessous sous forme de diagramme ER (Entity-Relationship) utilisant Mermaid.

```mermaid
graph TD
    %% Entités
    ETUDIANT[ETUDIANT<br/>id_etudiant<br/>nom<br/>prenom<br/>email<br/>telephone<br/>date_inscription]
    BUS[BUS<br/>id_bus<br/>numero_immatriculation<br/>capacite<br/>marque<br/>date_mise_service]
    LIGNE[LIGNE<br/>id_ligne<br/>nom_ligne<br/>description<br/>distance_km]
    STATION[STATION<br/>id_station<br/>nom_station<br/>adresse<br/>latitude<br/>longitude]
    HORAIRE[HORAIRE<br/>id_horaire<br/>id_ligne<br/>jour_semaine<br/>heure_depart<br/>heure_arrivee]
    AEL[AFFECTATION_ETUDIANT_LIGNE<br/>id_affectation_etudiant<br/>id_etudiant<br/>id_ligne<br/>date_debut<br/>date_fin]
    ABL[AFFECTATION_BUS_LIGNE<br/>id_affectation_bus<br/>id_bus<br/>id_ligne<br/>date_debut<br/>date_fin]
    TRAJET[TRAJET<br/>id_trajet<br/>id_bus<br/>id_ligne<br/>id_horaire<br/>date_trajet<br/>retard_minutes]
    INCIDENT[INCIDENT<br/>id_incident<br/>id_trajet<br/>description<br/>date_heure_incident<br/>type_incident]

    %% Associations
    S_ABONNE_HISTORIQUE{s_abonne_historique<br/>1,N - 1,N}
    EST_AFFECTE_HISTORIQUE{est_affecte_historique<br/>1,N - 1,N}
    A{a<br/>1,N - 1,1}
    DESSERT{dessert<br/>1,N - 1,N}
    UTILISE{utilise<br/>1,1 - 1,1}
    SUR{sur<br/>1,1 - 1,1}
    A_H{a<br/>1,1 - 1,1}
    A_I{a<br/>1,1 - 0,N}

    %% Relations
    ETUDIANT --> S_ABONNE_HISTORIQUE
    S_ABONNE_HISTORIQUE --> AEL
    AEL --> LIGNE

    BUS --> EST_AFFECTE_HISTORIQUE
    EST_AFFECTE_HISTORIQUE --> ABL
    ABL --> LIGNE

    LIGNE --> A
    A --> HORAIRE

    LIGNE --> DESSERT
    DESSERT --> STATION

    TRAJET --> UTILISE
    UTILISE --> BUS

    TRAJET --> SUR
    SUR --> LIGNE

    TRAJET --> A_H
    A_H --> HORAIRE

    TRAJET --> A_I
    A_I --> INCIDENT
```

## Explication du modèle

- **ETUDIANT** : Représente les étudiants inscrits au système.
- **BUS** : Les véhicules de transport avec leur capacité.
- **LIGNE** : Les parcours de transport.
- **STATION** : Les arrêts sur les lignes.
- **HORAIRE** : Les plannings par ligne et jour.
- **AFFECTATION_ETUDIANT_LIGNE** : Historique des abonnements des étudiants aux lignes.
- **AFFECTATION_BUS_LIGNE** : Historique des affectations des bus aux lignes.
- **TRAJET** : Les passages effectifs des bus.
- **INCIDENT** : Les problèmes survenus lors des trajets.

Les cardinalités :
- Un étudiant peut avoir plusieurs affectations historiques, mais une seule active (date_fin NULL).
- Un bus peut avoir plusieurs affectations historiques.
- Une ligne a plusieurs horaires.
- Une ligne dessert plusieurs stations, une station sur plusieurs lignes (many-to-many).
- Un trajet utilise un bus, sur une ligne, à un horaire donné.
- Un trajet peut avoir plusieurs incidents.