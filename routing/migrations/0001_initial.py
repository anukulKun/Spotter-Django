from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="FuelStation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("opis_id", models.PositiveIntegerField(unique=True)),
                ("name", models.CharField(max_length=200)),
                ("address", models.CharField(max_length=200)),
                ("city", models.CharField(max_length=100)),
                ("state", models.CharField(db_index=True, max_length=2)),
                ("latitude", models.FloatField(null=True)),
                ("longitude", models.FloatField(null=True)),
                ("price_usd_per_gallon", models.DecimalField(decimal_places=4, max_digits=6)),
                ("price_rows_merged", models.PositiveSmallIntegerField(default=1)),
                ("price_min", models.DecimalField(decimal_places=4, max_digits=6)),
                ("price_max", models.DecimalField(decimal_places=4, max_digits=6)),
                ("geocode_quality", models.CharField(default="city", max_length=12)),
                ("is_price_outlier", models.BooleanField(default=False)),
                ("imported_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "indexes": [
                    models.Index(fields=["state", "city"], name="routing_fue_state_217c0f_idx"),
                    models.Index(fields=["latitude", "longitude"], name="routing_fue_latitud_6dc999_idx"),
                    models.Index(fields=["price_usd_per_gallon"], name="routing_fue_price_u_99045c_idx"),
                ],
                "constraints": [models.CheckConstraint(condition=models.Q(("price_usd_per_gallon__gt", 0)), name="price_positive")],
            },
        ),
    ]
