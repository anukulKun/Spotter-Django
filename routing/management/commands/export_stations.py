import csv
from pathlib import Path
from django.core.management.base import BaseCommand
from routing.models import FuelStation

class Command(BaseCommand):
    help = "Export imported stations into a portable geocoded CSV."
    def add_arguments(self, parser):
        parser.add_argument("--output", type=Path, default=Path("data/stations_geocoded.csv"))
    def handle(self, *args, **options):
        output = options["output"]
        output.parent.mkdir(parents=True, exist_ok=True)
        fields = ["opis_id", "name", "address", "city", "state", "lat", "lng", "price", "price_min", "price_max", "rows_merged", "geocode_quality"]
        with output.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for station in FuelStation.objects.order_by("opis_id"):
                writer.writerow({"opis_id": station.opis_id, "name": station.name, "address": station.address, "city": station.city, "state": station.state, "lat": station.latitude or "", "lng": station.longitude or "", "price": station.price_usd_per_gallon, "price_min": station.price_min, "price_max": station.price_max, "rows_merged": station.price_rows_merged, "geocode_quality": station.geocode_quality})
        self.stdout.write(f"Exported {FuelStation.objects.count()} stations to {output}")
