from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone


@pytest.fixture
def admin_client(client, db):
    user = get_user_model().objects.create_superuser("admin", "admin@example.com", "pass")
    client.force_login(user)
    return client


def test_mark_done_action_shifts_next_due(admin_client, make_task):
    task = make_task(due_in=-3, cycle_days=90)

    response = admin_client.post(
        reverse("admin:maintenance_task_changelist"),
        {"action": "mark_done", "_selected_action": [task.pk]},
        follow=True,
    )

    task.refresh_from_db()
    today = timezone.localdate()
    assert response.status_code == 200
    assert task.last_done == today
    assert task.next_due == today + timedelta(days=90)


def test_change_form_button_marks_done(admin_client, make_task):
    task = make_task(due_in=-3, cycle_days=30)

    admin_client.post(
        reverse("admin:maintenance_task_change", args=[task.pk]),
        {
            "company": task.company_id,
            "title": task.title,
            "responsible_email": task.responsible_email,
            "cycle_days": 30,
            "last_done": task.last_done.isoformat(),
            "status": "active",
            "_mark_done": "1",
        },
    )

    task.refresh_from_db()
    assert task.last_done == timezone.localdate()
    assert task.next_due == timezone.localdate() + timedelta(days=30)


def test_changelist_shows_next_due(admin_client, make_task):
    make_task(due_in=1, title="Visible task")

    response = admin_client.get(reverse("admin:maintenance_task_changelist"))

    assert response.status_code == 200
    assert "Visible task" in response.content.decode()
