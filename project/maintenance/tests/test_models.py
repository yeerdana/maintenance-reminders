from datetime import timedelta

import pytest
from django.db import IntegrityError

from maintenance.models import Task

from .conftest import TODAY


@pytest.mark.parametrize(
    "due_in, expected",
    [
        (-10, True),  # overdue
        (-1, True),
        (0, True),  # due today
        (1, True),
        (3, True),  # exactly the boundary
        (4, False),  # one day too far
        (90, False),
    ],
)
def test_is_due_boundaries(make_task, due_in, expected):
    assert make_task(due_in=due_in).is_due(days_ahead=3, today=TODAY) is expected


def test_is_due_custom_days_ahead(make_task):
    task = make_task(due_in=7)
    assert not task.is_due(days_ahead=6, today=TODAY)
    assert task.is_due(days_ahead=7, today=TODAY)
    assert task.is_due(days_ahead=30, today=TODAY)


def test_is_due_defaults_to_three_days(make_task):
    assert make_task(due_in=3).is_due(today=TODAY)
    assert not make_task(due_in=4).is_due(today=TODAY)


def test_paused_task_is_never_due(make_task):
    assert not make_task(due_in=-5, status=Task.Status.PAUSED).is_due(today=TODAY)


def test_queryset_due_matches_is_due(make_task):
    tasks = [make_task(due_in=d, title=f"t{d}") for d in (-2, 0, 3, 4)]
    tasks.append(make_task(due_in=0, title="paused", status=Task.Status.PAUSED))

    due_ids = set(Task.objects.due(3, today=TODAY).values_list("id", flat=True))

    assert due_ids == {t.id for t in tasks if t.is_due(3, TODAY)}
    assert len(due_ids) == 3


def test_next_due_is_last_done_plus_cycle(make_task):
    task = make_task(due_in=0, cycle_days=90)
    assert task.next_due == task.last_done + timedelta(days=90)


def test_next_due_recalculated_on_save(make_task):
    task = make_task(due_in=0, cycle_days=30)

    task.cycle_days = 10
    task.save()
    task.refresh_from_db()

    assert task.next_due == task.last_done + timedelta(days=10)


def test_mark_done_shifts_next_due(make_task):
    task = make_task(due_in=-2, cycle_days=90)

    task.mark_done(today=TODAY)
    task.refresh_from_db()

    assert task.last_done == TODAY
    assert task.next_due == TODAY + timedelta(days=90)
    assert not task.is_due(days_ahead=3, today=TODAY)


def test_cycle_days_must_be_positive(make_task):
    with pytest.raises(IntegrityError):
        make_task(cycle_days=0)


@pytest.mark.parametrize(
    "due_in, label",
    [(-2, "просрочено на 2 дн."), (0, "сегодня"), (3, "через 3 дн.")],
)
def test_due_label(make_task, due_in, label):
    assert make_task(due_in=due_in).due_label(today=TODAY) == label
