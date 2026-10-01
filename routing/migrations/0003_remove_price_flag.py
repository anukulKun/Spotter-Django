from django.db import migrations, models
class Migration(migrations.Migration):
    dependencies = [("routing", "0002_geocodecache_importrun")]
    operations = [migrations.SeparateDatabaseAndState(database_operations=[migrations.RunSQL("ALTER TABLE routing_fuelstation DROP COLUMN is_price_outlier", "ALTER TABLE routing_fuelstation ADD COLUMN is_price_outlier bool NOT NULL DEFAULT 0")], state_operations=[migrations.RemoveField(model_name="fuelstation", name="is_price_outlier")])]
