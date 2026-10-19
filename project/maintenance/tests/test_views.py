from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from maintenance.models import Task


@pytest.fixture
def staff_client(client, db):
    user = get_user_model().objects.create_user("staff", password="pass", is_staff=True)
    client.force_login(user)
    return client


@pytest.fixture
def make_local_task(company):
    """Tasks relative to the real current date, because views use timezone.localdate()."""

    def factory(due_in, title):
        return Task.objects.create(
            company=company,
            title=title,
            responsible_email="ops@example.com",
            cycle_days=30,
            last_done=timezone.localdate() + timedelta(days=due_in - 30),
        )

    return factory


def test_page_requires_staff_login(client, db):
    response = client.get(reverse("maintenance:upcoming"))

    assert response.status_code == 302
    assert "/admin/login/" in response["Location"]


def test_page_lists_due_tasks_only(staff_client, make_local_task):
    make_local_task(2, "Soon task")
    make_local_task(10, "Later task")

    response = staff_client.get(reverse("maintenance:upcoming"))

    content = response.content.decode()
    assert "<html" in content
    assert "Soon task" in content
    assert "Later task" not in content


def test_filter_htmx_returns_partial_with_wider_range(staff_client, make_local_task):
    make_local_task(2, "Soon task")
    make_local_task(10, "Later task")

    response = staff_client.get(
        reverse("maintenance:upcoming"), {"days": 14}, headers={"HX-Request": "true"}
    )

    content = response.content.decode()
    assert "<html" not in content
    assert "Soon task" in content and "Later task" in content


def test_invalid_days_falls_back_to_default(staff_client, make_local_task):
    make_local_task(10, "Later task")

    response = staff_client.get(reverse("maintenance:upcoming"), {"days": "abc"})

    assert "Later task" not in response.content.decode()


def test_empty_state(staff_client):
    response = staff_client.get(reverse("maintenance:upcoming"))

    assert "Нет задач" in response.content.decode()


def test_overdue_task_is_labelled(staff_client, make_local_task):
    make_local_task(-2, "Late task")

    response = staff_client.get(reverse("maintenance:upcoming"))

    content = response.content.decode()
    assert "просрочено на 2 дн." in content
    assert 'class="overdue"' in content


def test_mark_done_post_returns_updated_row(staff_client, make_local_task):
    task = make_local_task(-2, "Late task")

    response = staff_client.post(reverse("maintenance:mark_done", args=[task.pk]))

    task.refresh_from_db()
    today = timezone.localdate()
    assert task.last_done == today
    assert task.next_due == today + timedelta(days=30)
    content = response.content.decode()
    assert f'id="task-{task.pk}"' in content
    assert "через 30 дн." in content


def test_mark_done_rejects_get(staff_client, make_local_task):
    task = make_local_task(0, "Task")

    response = staff_client.get(reverse("maintenance:mark_done", args=[task.pk]))

    assert response.status_code == 405


def test_mark_done_requires_staff(client, make_local_task):
    task = make_local_task(0, "Task")

    response = client.post(reverse("maintenance:mark_done", args=[task.pk]))

    assert response.status_code == 302
    task.refresh_from_db()
    assert task.last_done != timezone.localdate()
