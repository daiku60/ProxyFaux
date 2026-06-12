set shell := ["sh", "-cu"]

compose := "docker compose"

dev:
    {{ compose }} up --build

up:
    {{ compose }} up --build -d

logs:
    {{ compose }} logs -f

prod-up:
    docker compose --env-file deploy/.env.prod -f docker-compose.prod.yml up --build -d

server-deploy:
    ./deploy.sh

deploy *args:
    ./deploy-remote.sh {{ args }}

sync-pdfs *args:
    ./sync-pdfs.sh {{ args }}

prod-logs:
    docker compose --env-file deploy/.env.prod -f docker-compose.prod.yml logs -f

prod-down:
    docker compose --env-file deploy/.env.prod -f docker-compose.prod.yml down

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
