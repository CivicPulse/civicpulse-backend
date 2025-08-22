# Generated migration for safety testing
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('civicpulse', '0005_merge_0003_passwordhistory_0004_fix_audit_log_fields'),
    ]

    operations = [
        # This is a no-op migration for testing purposes
        migrations.RunSQL("SELECT 1;", "SELECT 1;"),
    ]
