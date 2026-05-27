set shell := ["sh", "-cu"]

compose := "docker compose"

dev:
    {{ compose }} up --build

up:
    {{ compose }} up --build -d

logs:
    {{ compose }} logs -f

backend:
    {{ compose }} up --build backend db

frontend:
    {{ compose }} up --build frontend

migrate:
    {{ compose }} run --rm backend uv run python manage.py migrate

test:
    {{ compose }} run --rm backend uv run pytest

manage *args:
    {{ compose }} run --rm backend uv run python manage.py {{ args }}
