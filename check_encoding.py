#!/usr/bin/env python
import sys
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'transport.settings')
import django
django.setup()

from gestion_transport.models import Bus, Conducteur, Ligne, Station

# Vérifier Bus 15 et affectations
try:
    bus = Bus.objects.get(id=15)
    print(f"✓ Bus trouvé: {bus}")
    print(f"  - ID: {bus.id}")
    print(f"  - Numéro: {repr(bus.numero_immatriculation)}")
    print(f"  - Marque: {repr(bus.marque)}")
    print(f"  - Capacité: {bus.capacite}")
    if bus.conducteur:
        print(f"  - Conducteur: {bus.conducteur.nom} {bus.conducteur.prenom} (repr: {repr(bus.conducteur.nom)} {repr(bus.conducteur.prenom)})")
    
    # Vérifier les affectations du bus
    from gestion_transport.models import AffectationBusLigne
    affectations = AffectationBusLigne.objects.filter(bus=bus)
    for aff in affectations:
        print(f"  - Affectation: {aff.ligne.nom_ligne} ({repr(aff.ligne.nom_ligne)})")
        if aff.conducteur:
            print(f"    Conducteur: {repr(aff.conducteur.nom)} {repr(aff.conducteur.prenom)}")
        
except Bus.DoesNotExist:
    print("Bus 15 introuvable")
except UnicodeDecodeError as e:
    print(f"UnicodeDecodeError détecté: {e}")
except Exception as e:
    print(f"Erreur: {type(e).__name__}: {e}")
