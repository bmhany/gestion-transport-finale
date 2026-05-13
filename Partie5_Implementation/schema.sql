-- Schéma SQL pour le système de transport universitaire

-- Création de la base de données
CREATE DATABASE IF NOT EXISTS transport_universitaire;
USE transport_universitaire;

-- Table ETUDIANT
CREATE TABLE ETUDIANT (
    id_etudiant INT PRIMARY KEY AUTO_INCREMENT,
    nom VARCHAR(50) NOT NULL,
    prenom VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE,
    telephone VARCHAR(20),
    date_inscription DATE NOT NULL
);

-- Table BUS
CREATE TABLE BUS (
    id_bus INT PRIMARY KEY AUTO_INCREMENT,
    numero_immatriculation VARCHAR(20) UNIQUE NOT NULL,
    capacite INT NOT NULL CHECK (capacite > 0),
    marque VARCHAR(50),
    date_mise_service DATE
);

-- Table LIGNE
CREATE TABLE LIGNE (
    id_ligne INT PRIMARY KEY AUTO_INCREMENT,
    nom_ligne VARCHAR(100) NOT NULL,
    description TEXT,
    distance_km INT
);

-- Table STATION
CREATE TABLE STATION (
    id_station INT PRIMARY KEY AUTO_INCREMENT,
    nom_station VARCHAR(100) NOT NULL,
    adresse TEXT,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8)
);

-- Table HORAIRE
CREATE TABLE HORAIRE (
    id_horaire INT PRIMARY KEY AUTO_INCREMENT,
    id_ligne INT NOT NULL,
    jour_semaine ENUM('lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche') NOT NULL,
    heure_depart TIME NOT NULL,
    heure_arrivee TIME NOT NULL,
    FOREIGN KEY (id_ligne) REFERENCES LIGNE(id_ligne) ON DELETE CASCADE
);

-- Table AFFECTATION_ETUDIANT_LIGNE
CREATE TABLE AFFECTATION_ETUDIANT_LIGNE (
    id_affectation_etudiant INT PRIMARY KEY AUTO_INCREMENT,
    id_etudiant INT NOT NULL,
    id_ligne INT NOT NULL,
    date_debut DATE NOT NULL,
    date_fin DATE,
    FOREIGN KEY (id_etudiant) REFERENCES ETUDIANT(id_etudiant) ON DELETE CASCADE,
    FOREIGN KEY (id_ligne) REFERENCES LIGNE(id_ligne) ON DELETE CASCADE,
    CHECK (date_fin IS NULL OR date_fin >= date_debut)
);

-- Table AFFECTATION_BUS_LIGNE
CREATE TABLE AFFECTATION_BUS_LIGNE (
    id_affectation_bus INT PRIMARY KEY AUTO_INCREMENT,
    id_bus INT NOT NULL,
    id_ligne INT NOT NULL,
    date_debut DATE NOT NULL,
    date_fin DATE,
    FOREIGN KEY (id_bus) REFERENCES BUS(id_bus) ON DELETE CASCADE,
    FOREIGN KEY (id_ligne) REFERENCES LIGNE(id_ligne) ON DELETE CASCADE,
    CHECK (date_fin IS NULL OR date_fin >= date_debut)
);

-- Table LIGNE_STATION
CREATE TABLE LIGNE_STATION (
    id_ligne INT NOT NULL,
    id_station INT NOT NULL,
    ordre INT NOT NULL CHECK (ordre > 0),
    PRIMARY KEY (id_ligne, id_station),
    FOREIGN KEY (id_ligne) REFERENCES LIGNE(id_ligne) ON DELETE CASCADE,
    FOREIGN KEY (id_station) REFERENCES STATION(id_station) ON DELETE CASCADE
);

-- Table TRAJET
CREATE TABLE TRAJET (
    id_trajet INT PRIMARY KEY AUTO_INCREMENT,
    id_bus INT NOT NULL,
    id_ligne INT NOT NULL,
    id_horaire INT NOT NULL,
    date_trajet DATE NOT NULL,
    retard_minutes INT DEFAULT 0 CHECK (retard_minutes >= 0),
    FOREIGN KEY (id_bus) REFERENCES BUS(id_bus) ON DELETE CASCADE,
    FOREIGN KEY (id_ligne) REFERENCES LIGNE(id_ligne) ON DELETE CASCADE,
    FOREIGN KEY (id_horaire) REFERENCES HORAIRE(id_horaire) ON DELETE CASCADE
);

-- Table INCIDENT
CREATE TABLE INCIDENT (
    id_incident INT PRIMARY KEY AUTO_INCREMENT,
    id_trajet INT NOT NULL,
    description TEXT NOT NULL,
    date_heure_incident DATETIME NOT NULL,
    type_incident VARCHAR(50),
    FOREIGN KEY (id_trajet) REFERENCES TRAJET(id_trajet) ON DELETE CASCADE
);

-- Index pour optimiser les requêtes
CREATE INDEX idx_horaire_ligne ON HORAIRE(id_ligne);
CREATE INDEX idx_affectation_etudiant_etudiant ON AFFECTATION_ETUDIANT_LIGNE(id_etudiant);
CREATE INDEX idx_affectation_etudiant_ligne ON AFFECTATION_ETUDIANT_LIGNE(id_ligne);
CREATE INDEX idx_affectation_bus_bus ON AFFECTATION_BUS_LIGNE(id_bus);
CREATE INDEX idx_affectation_bus_ligne ON AFFECTATION_BUS_LIGNE(id_ligne);
CREATE INDEX idx_trajet_bus ON TRAJET(id_bus);
CREATE INDEX idx_trajet_ligne ON TRAJET(id_ligne);
CREATE INDEX idx_trajet_horaire ON TRAJET(id_horaire);
CREATE INDEX idx_incident_trajet ON INCIDENT(id_trajet);