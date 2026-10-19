from datetime import timedelta

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Company(models.Model):
    name = models.CharField("название", max_length=200, unique=True)

    class Meta:
        verbose_name = "компания"
        verbose_name_plural = "компании"
        ordering = ["name"]

    def __str__(self):
        return self.name


class TaskQuerySet(models.QuerySet):
    def due(self, days_ahead=None, today=None):
        """Active tasks due within `days_ahead` days, including today and overdue ones."""
        days_ahead = settings.REMINDER_DAYS_AHEAD if days_ahead is None else days_ahead
        today = today or timezone.localdate()
        return self.filter(
            status=Task.Status.ACTIVE,
            next_due__lte=today + timedelta(days=days_ahead),
        )


class Task(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Активна"
        PAUSED = "paused", "Приостановлена"

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="tasks", verbose_name="компания"
    )
    title = models.CharField("название", max_length=200)
    responsible_email = models.EmailField("email ответственного")
    cycle_days = models.PositiveIntegerField(
        "периодичность, дней", validators=[MinValueValidator(1)]
    )
    last_done = models.DateField("последнее выполнение", default=timezone.localdate)
    status = models.CharField(
        "статус", max_length=10, choices=Status.choices, default=Status.ACTIVE
    )
    # Denormalised (last_done + cycle_days) so "due soon" is a plain indexed range query.
    next_due = models.DateField("следующий срок", editable=False, db_index=True)

    objects = TaskQuerySet.as_manager()

    class Meta:
        verbose_name = "задача"
        verbose_name_plural = "задачи"
        ordering = ["next_due", "title"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(cycle_days__gte=1), name="task_cycle_days_gte_1"
            ),
        ]

    def __str__(self):
        return f"{self.company}: {self.title}"

    def save(self, *args, **kwargs):
        self.next_due = self.last_done + timedelta(days=self.cycle_days)
        super().save(*args, **kwargs)

    def is_due(self, days_ahead=None, today=None):
        """True if the task is active and due within `days_ahead` days (overdue counts)."""
        days_ahead = settings.REMINDER_DAYS_AHEAD if days_ahead is None else days_ahead
        today = today or timezone.localdate()
        return (
            self.status == self.Status.ACTIVE
            and self.next_due <= today + timedelta(days=days_ahead)
        )

    def mark_done(self, today=None):
        """Record completion; the next deadline moves `cycle_days` forward from `today`."""
        self.last_done = today or timezone.localdate()
        self.save()

    def is_overdue(self, today=None):
        return self.next_due < (today or timezone.localdate())

    def due_label(self, today=None):
        days = (self.next_due - (today or timezone.localdate())).days
        if days < 0:
            return f"просрочено на {-days} дн."
        if days == 0:
            return "сегодня"
        return f"через {days} дн."


class DigestLog(models.Model):
    """One row per recipient per day; the unique constraint prevents duplicate digests."""

    email = models.EmailField()
    sent_on = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["email", "sent_on"], name="digest_once_per_day"),
        ]

    def __str__(self):
        return f"{self.email} {self.sent_on}"
