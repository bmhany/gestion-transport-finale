from django.apps import AppConfig


class GestionTransportConfig(AppConfig):
    name = 'gestion_transport'

    def ready(self):
        import gestion_transport.signals  # noqa: F401
