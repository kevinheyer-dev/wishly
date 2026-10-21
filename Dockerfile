FROM ghcr.io/astral-sh/uv:0.12.16 AS uv

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH

WORKDIR /app

# Dependencies first, so code changes do not reinstall them
COPY --from=uv /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --no-cache

COPY . .

# Static files are built into the image; the key exists only for this one command
RUN DJANGO_DEBUG=false DJANGO_SECRET_KEY=collectstatic-only WISHLY_STATIC_ROOT=/app/staticfiles \
    python manage.py collectstatic --noinput -v0

RUN useradd --system --uid 1000 --home /app wishly
USER wishly

EXPOSE 8000
ENTRYPOINT ["docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
