from django.db import models


class FuelStation(models.Model):
    opis_id = models.PositiveIntegerField(unique=True)
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=200)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2, db_index=True)
    latitude = models.FloatField(null=True)
    longitude = models.FloatField(null=True)
    price_usd_per_gallon = models.DecimalField(max_digits=6, decimal_places=4)
    price_rows_merged = models.PositiveSmallIntegerField(default=1)
    price_min = models.DecimalField(max_digits=6, decimal_places=4)
    price_max = models.DecimalField(max_digits=6, decimal_places=4)
    geocode_quality = models.CharField(max_length=12, default="city")
    is_price_outlier = models.BooleanField(default=False)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["state", "city"]),
            models.Index(fields=["latitude", "longitude"]),
            models.Index(fields=["price_usd_per_gallon"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price_usd_per_gallon__gt=0),
                name="price_positive",
            ),
        ]
