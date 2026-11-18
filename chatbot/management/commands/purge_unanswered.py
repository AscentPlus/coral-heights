from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from hotel_info.models import UnansweredQuestion


class Command(BaseCommand):
    help = 'Purges handled unanswered questions older than 90 days to keep the database tidy.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Number of days threshold for purging handled questions (default: 90).'
        )

    def handle(self, *args, **options):
        days = options['days']
        cutoff = timezone.now() - timedelta(days=days)

        qs = UnansweredQuestion.objects.filter(
            is_handled=True,
            last_asked__lt=cutoff
        )
        count = qs.count()
        deleted_count, _ = qs.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully purged {deleted_count} handled question(s) older than {days} days (before {cutoff.date()})."
            )
        )

