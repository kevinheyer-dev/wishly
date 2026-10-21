# Betrieb

wishly ist eine normale Django-Anwendung: ein Webprozess (gunicorn), ein Celery-Worker mit
Zeitplaner (beat), PostgreSQL und Redis. TLS übernimmt ein Reverse-Proxy davor.

## Konfiguration

Alle Einstellungen kommen aus Umgebungsvariablen; Vorlage: [`.env.example`](../.env.example).

| Variable | Bedeutung |
|---|---|
| `DJANGO_SECRET_KEY` | Pflicht, sobald `DJANGO_DEBUG=false` |
| `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` | Hostname(n) der Seite |
| `DJANGO_BEHIND_HTTPS_PROXY` | `true` hinter einem Proxy mit TLS (sichere Cookies) |
| `WISHLY_SITE_URL` | Basis-URL für Links in E-Mails |
| `WISHLY_ALLOW_SIGNUP` | `false` = neue Konten nur über `/verwaltung/` |
| `POSTGRES_*` | PostgreSQL; ohne `POSTGRES_DB` SQLite (`WISHLY_SQLITE_PATH`) |
| `CELERY_BROKER_URL` | z. B. `redis://localhost:6379/0`; leer = Aufgaben laufen im Webprozess |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` | SMTP |
| `WISHLY_BIRTHDAY_REMINDER_DAYS` | Tage vor dem Geburtstag, ab denen erinnert wird (Standard 14) |
| `WISHLY_AMAZON_TAG` | eigener Amazon-Partner-Tag, z. B. `meinshop-21` |
| `WISHLY_SCRAPER_USER_AGENT` | User-Agent für den Abruf von Shopseiten |
| `WISHLY_TIME_ZONE` | Standard `Europe/Berlin` |

## Einrichtung

```sh
uv sync --no-dev
uv run python manage.py migrate
uv run python manage.py collectstatic --noinput
uv run python manage.py createsuperuser
```

## Prozesse

```sh
uv run gunicorn config.wsgi --bind 127.0.0.1:8000 --workers 3
uv run celery -A config worker -l info
uv run celery -A config beat -l info
```

Der Worker liest Shopseiten ein, beat stößt täglich um 8 Uhr die Geburtstags-Erinnerungen an.
Wer kein beat betreiben will, ruft stattdessen täglich per cron
`uv run python manage.py send_birthday_reminders` auf. Erinnerungen werden pro Geburtstag nur
einmal verschickt; fällt ein Lauf aus, holt der nächste ihn nach.

## Sicherheit

- Shop-Links werden nur abgerufen, wenn sie auf öffentliche Adressen zeigen – bei jeder
  Weiterleitung neu geprüft. So lassen sich über wishly keine Dienste im internen Netz abfragen.
- Seiten über 3 MB und Abrufe über 10 Sekunden werden abgebrochen.
- Gäste, die über einen öffentlichen Link reservieren, können ihre Reservierung nur in derselben
  Browsersitzung wieder aufheben.
