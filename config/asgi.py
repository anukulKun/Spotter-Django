import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_asgi_application()
try:
    from routing.providers.geocode import get_gazetteer
    from routing.station_index import load

    get_gazetteer()
    load()
except Exception:
    pass
