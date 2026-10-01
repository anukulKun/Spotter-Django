#!/bin/sh
set -eu
python manage.py migrate --noinput
if [ "$(python manage.py shell -c 'from routing.models import FuelStation; print(FuelStation.objects.count())' | tail -n 1)" = "0" ]; then
  python manage.py import_fuel_prices --from-geocoded data/stations_geocoded.csv
fi
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2
