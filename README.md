# Напоминания о регламентных задачах (Django + Celery)

Django-проект с повторяющимися задачами компаний («продлить SSL-сертификат раз в 90 дней»). Каждый день Celery beat находит задачи со сроком в ближайшие 3 дня и отправляет каждому ответственному **одно** письмо-дайджест. Повторно в тот же день письмо не уходит. Отметка «выполнено» в админке сдвигает следующий срок.

| Требование ТЗ | Где реализовано |
|---|---|
| Модели `Company` и `Task` (название, email, `cycle_days`, дата последнего выполнения, статус) | [`maintenance/models.py`](project/maintenance/models.py) |
| `Task.is_due(days_ahead)` | [`maintenance/models.py`](project/maintenance/models.py) → `Task.is_due`, тот же критерий для запросов: `Task.objects.due()` |
| Ежедневная задача Celery beat, один дайджест на ответственного | [`maintenance/tasks.py`](project/maintenance/tasks.py) → `send_due_digests`, расписание в [`core/settings.py`](project/core/settings.py) |
| Повторно в тот же день письмо не уходит | модель `DigestLog` с уникальным `(email, sent_on)` |
| Console email backend | `MAILERS` в [`core/settings.py`](project/core/settings.py) (переменная `EMAIL_BACKEND`) |
| Отметка «выполнено» в Django admin сдвигает срок | [`maintenance/admin.py`](project/maintenance/admin.py): массовое действие и кнопка на странице задачи |
| README, docker-compose (web, db, redis, celery, beat) | этот файл, [`docker-compose.yml`](docker-compose.yml) |
| Тесты pytest-django на `is_due` и рассылку | [`project/maintenance/tests/`](project/maintenance/tests) |
| **Бонус:** страница «Ближайшие сроки» на HTMX | [`maintenance/views.py`](project/maintenance/views.py), [`templates/maintenance/`](project/maintenance/templates/maintenance) |

## Быстрый старт

```bash
docker compose up --build
```

Web-контейнер сам применяет миграции и создаёт администратора `admin` / `admin` (переменные `DJANGO_SUPERUSER_*`). Демо-данные:

```bash
docker compose exec web python manage.py seed_demo
```

- Админка: http://localhost:8000/admin/ (задачи, действие «Отметить выполненным»)
- «Ближайшие сроки» (HTMX, нужен вход как staff): http://localhost:8000/
- Письма печатаются в консоль: `docker compose logs -f celery`
- Запустить рассылку сразу, не дожидаясь 09:00:
  `docker compose exec web python manage.py shell -c "from maintenance.tasks import send_due_digests; print(send_due_digests())"`

## Тесты — одной командой

Без Docker (SQLite):

```bash
cd project
pip install -r requirements.txt
pytest
```

На PostgreSQL, как в CI:

```bash
docker compose run --rm web pytest
```

Время в тестах не замораживается: дата `today` передаётся в `is_due`, `Task.objects.due` и `send_due_digests` явно. Письма проверяются через `mail.outbox` (locmem backend).

| Что проверяется | Тесты |
|---|---|
| `is_due`: сегодня, ровно через 3 дня (да), через 4 дня (нет), просрочено, paused, свой `days_ahead` | `test_models.py` |
| `next_due` пересчитывается при сохранении, `mark_done` сдвигает срок | `test_models.py` |
| Дайджест: одно письмо на ответственного со всеми задачами, нет писем без задач, нет дубля в тот же день, на следующий день письмо уходит снова, paused исключены, сбой отправки не оставляет `DigestLog` | `test_digest.py` |
| Админка: массовое действие и кнопка «отметить выполненным» | `test_admin.py` |
| HTMX-страница: список, фильтр (partial), POST «Выполнено», доступ только staff | `test_views.py` |

## Конфигурация

| Переменная | По умолчанию | Описание |
|---|---|---|
| `SECRET_KEY` | dev-значение | задайте своё вне разработки |
| `DEBUG` | `0` (в compose `1`) | режим отладки |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1]` | через запятую |
| `POSTGRES_HOST` | не задан | если задан, используется PostgreSQL (`POSTGRES_DB/USER/PASSWORD/PORT`), иначе SQLite |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | брокер Celery |
| `REMINDER_DAYS_AHEAD` | `3` | за сколько дней предупреждать |
| `DIGEST_HOUR` | `9` | час ежедневной рассылки |
| `TIME_ZONE` | `Asia/Almaty` | часовой пояс расписания и «сегодня» |
| `EMAIL_BACKEND` | console | для настоящей почты — SMTP backend |
| `DJANGO_SUPERUSER_*` | в compose `admin`/`admin` | автосоздание администратора в web-контейнере |

## Решения

- **Срок хранится в `next_due`.** Поле считается в `save()` как `last_done + cycle_days` и проиндексировано, поэтому «что скоро» — обычный запрос по диапазону, а не пересчёт в Python. `is_due` и `Task.objects.due()` используют одно условие: активная задача, `next_due <= today + days_ahead`. Сюда входят сегодня и просроченные; paused не входят никогда.
- **Нет дублей писем.** `DigestLog(email, sent_on)` с уникальным ограничением. Запись и отправка письма идут в одной транзакции: сбой отправки откатывает запись, и следующий запуск повторит рассылку; уже существующая запись означает, что сегодня письмо отправлено. Это работает и при двух одновременных запусках задачи.
- **Сбой одному адресату не блокирует остальных**: ошибка логируется, цикл продолжается.
- **«Выполнено» считается от даты отметки**, а не от старого срока: `last_done = сегодня`, следующий срок через `cycle_days` дней.
- **Адреса группируются без учёта регистра**, чтобы `Anna@x.com` и `anna@x.com` получили одно письмо.
- **Миграции выполняет только `web`.** `celery` и `beat` стартуют после того, как `web` стал healthy, поэтому гонки при `migrate` нет. Файл расписания beat лежит в `/tmp`.
- **HTMX.** Фильтр по числу дней перерисовывает только таблицу (`hx-get`), кнопка «Выполнено» (`hx-post`) заменяет одну строку. Страница доступна только staff-пользователям; библиотека htmx подключается с unpkg фиксированной версии.
- `runserver` в compose — режим разработки; для продакшена нужен gunicorn и раздача статики.

## Происхождение кода

Проект основан на открытом репозитории [testdrivenio/django-celery-beat](https://github.com/testdrivenio/django-celery-beat) (лицензия MIT, см. [`LICENSE`](LICENSE)); история его коммитов сохранена. Из него взяты структура проекта (`core/` с настройкой Celery), схема compose и Dockerfile.

| Было в исходной версии | Стало |
|---|---|
| Демо-приложение `orders` и примерные задачи `sample_task`, `send_email_report` | Приложение `maintenance`: `Company`, `Task`, `DigestLog`, задача `send_due_digests` |
| Задача каждую минуту / каждый час | Один раз в день в 09:00 по `Asia/Almaty` |
| Бинарный файл `celerybeat-schedule` закоммичен в репозиторий | Файл расписания в `/tmp` контейнера |
| Каждый контейнер (web, celery, beat) выполняет `migrate` и `collectstatic` при старте | `migrate` только в `web`, остальные ждут его healthcheck |
| Нет базы данных, кроме SQLite; `db` отсутствует в compose | PostgreSQL 16 с healthcheck, SQLite только для локальных тестов |
| `SECRET_KEY` вписан в compose, настройки не из окружения | Все настройки из переменных окружения |
| Образ `python:3.12.4-alpine`, зависимости Django 5.0 / Celery 5.4 | `python:3.12-slim`, зависимости закреплены (Django 6.1, Celery 5.6) |
| Тестов нет | 38 тестов pytest-django |
