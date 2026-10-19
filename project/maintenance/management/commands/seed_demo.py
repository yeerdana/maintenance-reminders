from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from maintenance.models import Company, Task

# (title, cycle_days, days until the next deadline)
DEMO_TASKS = [
    ("Продлить SSL-сертификат", 90, -2),
    ("Ротация ключей доступа", 30, 0),
    ("Проверка резервных копий", 7, 3),
    ("Обновление лицензии", 365, 4),
]


class Command(BaseCommand):
    help = "Create a demo company with tasks at different distances from their deadline."

    def handle(self, *args, **options):
        today = timezone.localdate()
        company, _ = Company.objects.get_or_create(name="Демо-компания")
        for title, cycle_days, days_left in DEMO_TASKS:
            Task.objects.get_or_create(
                company=company,
                title=title,
                defaults={
                    "responsible_email": "ops@example.com",
                    "cycle_days": cycle_days,
                    "last_done": today + timedelta(days=days_left - cycle_days),
                },
            )
        self.stdout.write(self.style.SUCCESS(f"Demo data ready: {len(DEMO_TASKS)} tasks."))
