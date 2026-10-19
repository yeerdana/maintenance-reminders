from datetime import timedelta
from unittest import mock

from django.core import mail

from maintenance.models import DigestLog, Task
from maintenance.tasks import send_due_digests

from .conftest import TODAY


def test_one_email_per_responsible_with_all_their_tasks(make_task):
    make_task(due_in=0, email="anna@example.com", title="SSL")
    make_task(due_in=3, email="anna@example.com", title="Backups")
    make_task(due_in=-2, email="boris@example.com", title="Keys")

    assert send_due_digests(today=TODAY) == 2

    assert len(mail.outbox) == 2
    by_recipient = {m.to[0]: m for m in mail.outbox}
    anna = by_recipient["anna@example.com"].body
    assert "SSL" in anna and "Backups" in anna and "Keys" not in anna
    boris = by_recipient["boris@example.com"].body
    assert "Keys" in boris and "просрочено на 2 дн." in boris


def test_no_email_when_nothing_is_due(make_task):
    make_task(due_in=4)

    assert send_due_digests(today=TODAY) == 0

    assert mail.outbox == []
    assert DigestLog.objects.count() == 0


def test_no_duplicate_on_the_same_day(make_task):
    make_task(due_in=1)

    send_due_digests(today=TODAY)
    assert send_due_digests(today=TODAY) == 0

    assert len(mail.outbox) == 1


def test_sends_again_next_day(make_task):
    make_task(due_in=2)

    send_due_digests(today=TODAY)
    send_due_digests(today=TODAY + timedelta(days=1))

    assert len(mail.outbox) == 2


def test_paused_tasks_are_excluded(make_task):
    make_task(due_in=0, status=Task.Status.PAUSED)

    assert send_due_digests(today=TODAY) == 0
    assert mail.outbox == []


def test_email_grouping_ignores_case(make_task):
    make_task(due_in=0, email="Anna@Example.com", title="A")
    make_task(due_in=0, email="anna@example.com", title="B")

    send_due_digests(today=TODAY)

    assert len(mail.outbox) == 1


def test_send_failure_leaves_no_log_and_is_retried(make_task):
    make_task(due_in=0)

    with mock.patch("maintenance.tasks.send_mail", side_effect=OSError("smtp down")):
        assert send_due_digests(today=TODAY) == 0
    assert DigestLog.objects.count() == 0

    assert send_due_digests(today=TODAY) == 1
    assert len(mail.outbox) == 1


def test_failure_for_one_recipient_does_not_block_others(make_task):
    make_task(due_in=0, email="anna@example.com")
    make_task(due_in=0, email="boris@example.com")
    real_send_mail = mail.send_mail

    def flaky(subject, body, sender, recipients):
        if recipients == ["anna@example.com"]:
            raise OSError("smtp down")
        return real_send_mail(subject, body, sender, recipients)

    with mock.patch("maintenance.tasks.send_mail", side_effect=flaky):
        assert send_due_digests(today=TODAY) == 1

    assert [m.to for m in mail.outbox] == [["boris@example.com"]]
    assert list(DigestLog.objects.values_list("email", flat=True)) == ["boris@example.com"]
