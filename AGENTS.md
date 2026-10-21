# wishly

Wishlist platform for families and friends: lists per occasion, shared within family groups and by
public link, reservations with surprise protection, product data read from shop links, Amazon
affiliate tags, birthday reminders. Developer and user docs are German (`README.md`, `docs/`).

## Stack

- Python 3.13+, Django 5.2 (LTS), managed with `uv` (`pyproject.toml`, `uv.lock`)
- Plain Django templates, one stylesheet (`static/css/wishly.css`), one small script
  (`static/js/wishly.js`); no CSS/JS framework, no build step, no external resources
- SQLite in development, PostgreSQL when `POSTGRES_DB` is set
- Celery + Redis for scraping and reminders; without `CELERY_BROKER_URL` tasks run inline
- requests + BeautifulSoup for scraping; gunicorn + WhiteNoise in production

## Commands

```sh
uv sync
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver                       # http://127.0.0.1:8000
uv run python manage.py test                            # full suite (~15 s)
uv run python manage.py makemigrations --check --dry-run   # must report "No changes detected"
uvx ruff check .                                        # lint (config in pyproject.toml)
uv run celery -A config worker -B -l info               # needs CELERY_BROKER_URL
uv run python manage.py send_birthday_reminders         # cron alternative to Celery beat
```

## Code map

- `accounts/` – `User` (AbstractUser), `FamilyGroup` + `Membership` (roles admin/member), `Profile`
  (one per user, or a child profile without login with `guardians` and an optional secret
  `child_token`), birthday reminders
  (`reminders.py`, `tasks.py`, command `send_birthday_reminders`)
- `wishlists/child_views.py` – pages behind a child's secret link (`/kind/<token>/`): the child sees
  its lists like a recipient and adds or changes only wishes with `added_by_child`
- `wishlists/` – `Wishlist`, `Product` (a wish), `Reservation`; **all visibility rules live in
  `wishlists/access.py`** – views never decide on their own who sees what
- `scraper/` – `fetch.py` (SSRF-safe download), `parse.py` (JSON-LD → shop selectors → OpenGraph),
  `tasks.py` (`scrape_url` for the live form preview, Celery task for saved products), `affiliate.py` (tags added at render time via the `affiliate` filter)
- `templates/` – `base.html`, `form_page.html` (generic form page), one folder per app
- `config/` – settings (all environment-driven), `celery.py`

## Rules

- Surprise protection is the core promise: the recipient (`Profile.user`) must never see
  reservations, purchases or secret suggestions – not in lists, counts, the public page, the child
  link, mails or messages. Guardians of a child profile are gift givers and do see them. Add a test for every
  new place that shows product or reservation data.
- Every fetch of a user-supplied URL goes through `scraper.fetch.fetch_html` (blocks non-public
  addresses on every redirect hop).
- Stored shop URLs stay clean; affiliate tags are only added when rendering.
- UI text and URLs are German, code, comments and commit messages English.
- Public links are `/<family>/<profile>/<list>/` (slugs, `accounts/slugs.py`) and are matched
  last. A new top-level path segment must be added to `RESERVED` there, or a family could shadow it.
- Redirect targets from requests (`next`) are checked with `url_has_allowed_host_and_scheme`.
- Keep it small: no new dependencies or frameworks without a reason; match the existing style.
- Record user-visible changes in `CHANGELOG.md` (German).
