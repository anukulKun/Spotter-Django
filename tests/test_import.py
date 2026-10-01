import csv

import pytest
from django.core.management import call_command

from routing.models import FuelStation


@pytest.mark.django_db
def test_import_filters_merges_resolves_reports_and_is_idempotent(tmp_path, capsys):
    csv_path = tmp_path / "prices.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "OPIS Truckstop ID",
                "Truckstop Name",
                "Address",
                "City",
                "State",
                "Rack ID",
                "Retail Price",
            ]
        )
        writer.writerow(["1", "A", "Exit", "Springfield", "IL", "R", "3.00"])
        writer.writerow(["1", "LONGER STATION NAME", "Exit", "Springfield", "IL", "R", "3.20"])
        writer.writerow(["2", "B", "Exit", "Missing", "IL", "R", "6.40"])
        writer.writerow(["3", "Canada", "Exit", "Toronto", "ON", "R", "3.00"])
    gazetteer = tmp_path / "cities.csv"
    gazetteer.write_text(
        "city,state,lat,lng,population\nSpringfield,IL,39.8,-89.6,100\n", encoding="utf-8"
    )
    call_command("import_fuel_prices", csv_path, "--gazetteer", gazetteer)
    output = capsys.readouterr().out
    assert "Dropped (non-US):          1" in output
    assert "Missing, IL" in output
    station = FuelStation.objects.get(opis_id=1)
    assert station.name == "LONGER STATION NAME"
    assert float(station.price_usd_per_gallon) == pytest.approx(3.1)
    assert FuelStation.objects.count() == 2
    call_command("import_fuel_prices", csv_path, "--gazetteer", gazetteer)
    assert FuelStation.objects.count() == 2
