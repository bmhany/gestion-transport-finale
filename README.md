# Système de Gestion du Transport Universitaire

## Description

Application Django de gestion du transport universitaire.

Le projet couvre:
- la gestion des étudiants, conducteurs, bus, lignes et stations
- les abonnements étudiants aux lignes
- la planification des trajets et horaires
- les incidents, notifications et historique
- les tickets étudiants avec code QR

En plus de l'application web, le dépôt contient les livrables de conception base de données:
- **Partie1_Analyse/**
- **Partie2_MCD/**
- **Partie3_MLD/**
- **Partie4_Normalisation/**
- **Partie5_Implementation/**

## Technologies utilisées

- Python
- Django
- SQLite
- HTML / CSS / JavaScript
- Mermaid pour certains diagrammes

## Lancer le projet en local

### Option simple sous Windows

Le dossier [PackPretAPartager/](PackPretAPartager) contient des scripts prêts à l'emploi:
- `1_Installer.bat` : installe automatiquement l'environnement
- `2_Lancer_Local.bat` : lance l'application sur le PC local
- `3_Lancer_Reseau_Wifi.bat` : partage l'application sur le même Wi-Fi

### Option manuelle

1. Installer Python 3.11 ou plus récent
2. Créer un environnement virtuel
3. Installer les dépendances avec `pip install -r requirements.txt`
4. Lancer les migrations avec `python manage.py migrate`
5. Lancer le serveur avec `python manage.py runserver`

## Partage avec des camarades non techniques

La méthode la plus simple est:

1. lancer `PackPretAPartager/3_Lancer_Reseau_Wifi.bat` sur votre PC
2. récupérer le lien affiché par le script
3. envoyer ce lien à vos camarades

Ils n'ont rien à installer tant qu'ils sont sur le même réseau Wi-Fi que vous.

## Mettre le projet sur GitHub

Le dépôt est maintenant prêt à être publié sur GitHub avec un `.gitignore` adapté.

### Étapes recommandées

1. Créer un nouveau dépôt vide sur GitHub
2. Dans le dossier du projet, exécuter:

```bash
git init
git add .
git commit -m "Initial project import"
git branch -M main
git remote add origin https://github.com/VOTRE_UTILISATEUR/VOTRE_REPO.git
git push -u origin main
```

### Important

- le fichier `db.sqlite3` peut maintenant être envoyé sur GitHub avec vos données actuelles
- les environnements virtuels `venv/` et `.venv/` ne sont pas envoyés
- le dossier `staticfiles/` généré localement n'est pas envoyé
- si vous partagez `db.sqlite3`, vos camarades récupèrent directement la même base de données que vous

### Partager aussi la base de données

Si vous voulez que vos camarades récupèrent immédiatement les mêmes données que vous:

1. laissez `db.sqlite3` dans le dossier du projet
2. faites `git add .`
3. faites votre commit puis `git push`

Quand ils cloneront le dépôt GitHub, ils auront déjà la base SQLite avec les données incluses.

## Structure principale du projet

- `gestion_transport/` : application Django principale
- `transport/` : configuration Django
- `PackPretAPartager/` : scripts Windows de partage simplifié
- `requirements.txt` : dépendances Python
- `manage.py` : point d'entrée Django

## Auteur

Projet réalisé dans le cadre du module de base de données, puis étendu en application web de gestion du transport universitaire.