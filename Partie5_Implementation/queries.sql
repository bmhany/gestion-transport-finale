-- Requêtes SQL pour le système de transport universitaire

USE transport_universitaire;

-- 1. Nombre d'étudiants par ligne (actifs)
SELECT 
    l.nom_ligne,
    COUNT(ael.id_etudiant) AS nombre_etudiants
FROM LIGNE l
LEFT JOIN AFFECTATION_ETUDIANT_LIGNE ael ON l.id_ligne = ael.id_ligne 
    AND ael.date_fin IS NULL  -- Abonnements actifs
GROUP BY l.id_ligne, l.nom_ligne
ORDER BY nombre_etudiants DESC;

-- 2. Taux de remplissage des bus (pour les trajets récents)
SELECT 
    t.id_trajet,
    b.numero_immatriculation,
    b.capacite,
    COUNT(DISTINCT e.id_etudiant) AS etudiants_transportes,
    ROUND((COUNT(DISTINCT e.id_etudiant) / b.capacite) * 100, 2) AS taux_remplissage_pourcent
FROM TRAJET t
JOIN BUS b ON t.id_bus = b.id_bus
LEFT JOIN AFFECTATION_ETUDIANT_LIGNE ael ON t.id_ligne = ael.id_ligne 
    AND ael.date_fin IS NULL
    AND ael.date_debut <= t.date_trajet
LEFT JOIN ETUDIANT e ON ael.id_etudiant = e.id_etudiant
WHERE t.date_trajet >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)  -- Trajets des 30 derniers jours
GROUP BY t.id_trajet, b.id_bus, b.numero_immatriculation, b.capacite
ORDER BY taux_remplissage_pourcent DESC;

-- 3. Horaires d'une ligne donnée (exemple: ligne 1)
SELECT 
    h.jour_semaine,
    h.heure_depart,
    h.heure_arrivee
FROM HORAIRE h
WHERE h.id_ligne = 1  -- Remplacer par l'ID de la ligne souhaitée
ORDER BY FIELD(h.jour_semaine, 'lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche'), h.heure_depart;

-- 4. Étudiants sans abonnement actif
SELECT 
    e.id_etudiant,
    CONCAT(e.prenom, ' ', e.nom) AS nom_complet,
    e.email,
    e.date_inscription
FROM ETUDIANT e
WHERE NOT EXISTS (
    SELECT 1 FROM AFFECTATION_ETUDIANT_LIGNE ael 
    WHERE ael.id_etudiant = e.id_etudiant 
    AND ael.date_fin IS NULL
)
ORDER BY e.date_inscription DESC;

-- 5. Historique des affectations d'un étudiant (exemple: étudiant 1)
SELECT 
    l.nom_ligne,
    ael.date_debut,
    ael.date_fin,
    CASE 
        WHEN ael.date_fin IS NULL THEN 'Actif'
        ELSE 'Terminé'
    END AS statut
FROM AFFECTATION_ETUDIANT_LIGNE ael
JOIN LIGNE l ON ael.id_ligne = l.id_ligne
WHERE ael.id_etudiant = 1  -- Remplacer par l'ID de l'étudiant souhaité
ORDER BY ael.date_debut DESC;

-- 6. Bus affectés à une ligne à une date donnée (exemple: ligne 1, date '2024-01-15')
SELECT 
    b.numero_immatriculation,
    b.capacite,
    abl.date_debut,
    abl.date_fin
FROM AFFECTATION_BUS_LIGNE abl
JOIN BUS b ON abl.id_bus = b.id_bus
WHERE abl.id_ligne = 1  -- Remplacer par l'ID de la ligne
    AND abl.date_debut <= '2024-01-15'  -- Date donnée
    AND (abl.date_fin IS NULL OR abl.date_fin >= '2024-01-15')
ORDER BY abl.date_debut;

-- 7. Lignes les plus chargées (par nombre d'étudiants actifs)
SELECT 
    l.nom_ligne,
    COUNT(ael.id_etudiant) AS nombre_etudiants_actifs
FROM LIGNE l
LEFT JOIN AFFECTATION_ETUDIANT_LIGNE ael ON l.id_ligne = ael.id_ligne 
    AND ael.date_fin IS NULL
GROUP BY l.id_ligne, l.nom_ligne
HAVING nombre_etudiants_actifs > 0
ORDER BY nombre_etudiants_actifs DESC
LIMIT 10;  -- Top 10

-- 8. Liste des trajets avec retard
SELECT 
    t.id_trajet,
    l.nom_ligne,
    b.numero_immatriculation,
    h.jour_semaine,
    h.heure_depart,
    t.date_trajet,
    t.retard_minutes,
    CASE 
        WHEN t.retard_minutes > 0 THEN 'En retard'
        ELSE 'À l\'heure'
    END AS statut
FROM TRAJET t
JOIN LIGNE l ON t.id_ligne = l.id_ligne
JOIN BUS b ON t.id_bus = b.id_bus
JOIN HORAIRE h ON t.id_horaire = h.id_horaire
WHERE t.retard_minutes > 0
ORDER BY t.retard_minutes DESC, t.date_trajet DESC;