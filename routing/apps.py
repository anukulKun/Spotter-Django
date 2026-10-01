import sys
import time
from django.apps import AppConfig

class RoutingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "routing"
    def ready(self):
        if "pytest" in sys.modules or (len(sys.argv) > 1 and sys.argv[1] in {"migrate", "makemigrations", "test", "pytest", "check"}): return
        try:
            from routing.providers.geocode import get_gazetteer
            from routing.station_index import load
            get_gazetteer(); load()
        except Exception:
            # Database and source files may not exist yet; request-time loading remains available.
            pass
