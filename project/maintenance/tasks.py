from collections import defaultdict

from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import DigestLog, Task

logger = get_task_logger(__name__)


def build_digest(tasks, today):
    lines = [
        f"- {task.company}: {task.title}, срок {task.next_due:%d.%m.%Y} ({task.due_label(today)})"
        for task in tasks
    ]
    subject = f"Регламентные задачи: ближайшие сроки ({len(tasks)})"
    body = (
        "Здравствуйте!\n\n"
        f"Сроки наступают в ближайшие {settings.REMINDER_DAYS_AHEAD} дн.:\n\n"
        + "\n".join(lines)
        + "\n"
    )
    return subject, body


@shared_task
def send_due_digests(today=None):
    """Send one digest per responsible email and return how many were sent.

    The DigestLog row and the email share one transaction: if sending fails the row
    is rolled back and the next run retries; an existing row means the digest has
    already gone out today. `today` is only passed explicitly by tests.
    """
    today = today or timezone.localdate()
    by_email = defaultdict(list)
    for task in Task.objects.due(today=today).select_related("company"):
        by_email[task.responsible_email.lower()].append(task)

    sent = 0
    for email, tasks in by_email.items():
        try:
            with transaction.atomic():
                _, created = DigestLog.objects.get_or_create(email=email, sent_on=today)
                if not created:
                    continue
                subject, body = build_digest(tasks, today)
                send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [email])
        except Exception:
            logger.exception("Digest for %s failed, will retry on the next run", email)
        else:
            sent += 1
    return sent
