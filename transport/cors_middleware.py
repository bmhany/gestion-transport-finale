"""CORS minimal pour l'API JSON consommée par le front statique (Navéo, Live Server, etc.)."""


class ApiV1CorsMiddleware:
    """Ajoute les en-têtes CORS aux réponses dont le chemin commence par /api/v1/."""

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _headers():
        return {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Accept',
            'Access-Control-Max-Age': '86400',
        }

    def __call__(self, request):
        if request.method == 'OPTIONS' and request.path.startswith('/api/v1/'):
            from django.http import HttpResponse

            resp = HttpResponse(status=204)
            for k, v in self._headers().items():
                resp[k] = v
            return resp

        response = self.get_response(request)
        if request.path.startswith('/api/v1/'):
            for k, v in self._headers().items():
                response[k] = v
        return response
