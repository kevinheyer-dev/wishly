from django.core.management.base import BaseCommand

from accounts.reminders import send_birthday_reminders


class Command(BaseCommand):
    help = "Send due birthday reminders (for cron, when Celery beat is not used)."

    def handle(self, *args, **options):
        self.stdout.write(f"{send_birthday_reminders()} reminder(s) sent")
