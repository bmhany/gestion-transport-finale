"""Sert la page Navéo depuis naveo-integration (même origine que l'API)."""

from pathlib import Path

from django.http import FileResponse, Http404


def naveo_portail(request):
    root = Path(__file__).resolve().parent.parent
    folder = root / 'naveo-integration'
    for name in ('Naveo.finale.html', 'Navéo-Final.html'):
        path = folder / name
        if path.is_file():
            return FileResponse(path.open('rb'), content_type='text/html; charset=utf-8')
    raise Http404('Aucun fichier Navéo (Naveo.finale.html ou Navéo-Final.html) dans naveo-integration/.')
