from django.db import migrations
from django.core.management import call_command


def create_cache_table(apps, schema_editor):
    try:
        call_command('createcachetable', 'cache_table', verbosity=0)
    except Exception:
        # Table might already exist or command is no-op
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('staff_panel', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_cache_table, reverse_code=migrations.RunPython.noop),
    ]

