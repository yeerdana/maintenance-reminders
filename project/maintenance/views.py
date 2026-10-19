from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Task

DAYS_CHOICES = (3, 7, 14, 30)


def parse_days(raw):
    try:
        days = int(raw)
    except (TypeError, ValueError):
        return settings.REMINDER_DAYS_AHEAD
    return days if days in DAYS_CHOICES else settings.REMINDER_DAYS_AHEAD


@staff_member_required
def upcoming(request):
    days = parse_days(request.GET.get("days"))
    context = {
        "tasks": Task.objects.due(days).select_related("company"),
        "days": days,
        "days_choices": DAYS_CHOICES,
    }
    # htmx requests (filter change) get only the table, a normal visit gets the page.
    template = "maintenance/_table.html" if request.headers.get("HX-Request") else "maintenance/upcoming.html"
    return render(request, template, context)


@staff_member_required
@require_POST
def mark_done(request, pk):
    task = get_object_or_404(Task, pk=pk)
    task.mark_done(timezone.localdate())
    return render(request, "maintenance/_row.html", {"task": task})
