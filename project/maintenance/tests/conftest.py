from datetime import date, timedelta

import pytest

from maintenance.models import Company, Task

TODAY = date(2026, 3, 10)


@pytest.fixture
def company(db):
    return Company.objects.create(name="Acme")


@pytest.fixture
def make_task(company):
    """Create a task whose next deadline is `due_in` days after TODAY."""

    def factory(due_in=0, cycle_days=30, email="ops@example.com", title="Task", **extra):
        return Task.objects.create(
            company=company,
            title=title,
            responsible_email=email,
            cycle_days=cycle_days,
            last_done=TODAY + timedelta(days=due_in - cycle_days),
            **extra,
        )

    return factory
