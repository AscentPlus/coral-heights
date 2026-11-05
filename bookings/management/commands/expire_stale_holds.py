"""
Management command: expire_stale_holds

Cancels all held bookings whose hold_expires_at is in the past.
Intended to run periodically (cron/celery-beat) once deployed.
Can also be called manually: python manage.py expire_stale_holds

Usage:
    python manage.py expire_stale_holds
"""
from django.core.management.base import BaseCommand
from bookings.services import expire_stale_holds


class Command(BaseCommand):
    help = (
        'Cancels all held bookings whose hold_expires_at is in the past. '
        'Run periodically via cron or celery-beat in production.'
    )

    def handle(self, *args, **options):
        count = expire_stale_holds()
        if count:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Expired {count} stale hold(s) — status set to cancelled.'
                )
            )
        else:
            self.stdout.write('No stale holds found.')
