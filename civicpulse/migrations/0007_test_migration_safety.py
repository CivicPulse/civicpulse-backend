# Generated migration for safety testing
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('civicpulse', '0006_test_migration_safety'),
    ]

    operations = [
        # This is a no-op migration for testing purposes
        migrations.RunSQL("SELECT 1;", "SELECT 1;"),
    ]
