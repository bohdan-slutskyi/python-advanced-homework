# syntax=docker/dockerfile:1
# Django image for local verification and cloud WSGI (Compose overrides the command).
FROM python:3.14-slim-bookworm AS builder

ENV UV_LINK_MODE=copy UV_NO_PROGRESS=1
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.13.7

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --all-groups --no-install-project

FROM python:3.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libmariadb3 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 django \
    && useradd --system --uid 10001 --gid django --home-dir /app django

COPY --from=builder --chown=django:django /app/.venv /app/.venv
COPY --chown=django:django manage.py ./
COPY --chown=django:django config/ ./config/
COPY --chown=django:django apps/ ./apps/
COPY --chown=django:django tests/ ./tests/
COPY --chown=django:django infra/smoke_container.py ./infra/smoke_container.py

USER django
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--no-control-socket", "--workers", "1", "--threads", "2", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-"]
