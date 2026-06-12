# proxyfaux

Modern full-stack starter template with Django REST Framework, React, Vite, PostgreSQL, `uv`, TailwindCSS, and Docker Compose.

## Stack

- Backend: Django 5, Django REST Framework, PostgreSQL, `uv`, Ruff, pytest
- Frontend: React, Vite, TypeScript, React Router, Axios, TailwindCSS
- Infrastructure: Docker Compose with separate `db`, `backend`, and `frontend` services

## Project Layout

```text
proxyfaux/
├── backend/
├── frontend/
├── docker-compose.yml
├── Justfile
└── README.md
```

## Prerequisites

- Docker + Docker Compose
- `just`: https://github.com/casey/just
- `uv` for local Python workflows: https://docs.astral.sh/uv/getting-started/installation/
- Node.js 20+ if you want to run the frontend outside Docker

## Quick Start

Run the full stack with Docker:

```bash
docker compose up --build
```

Services:

- App via Django: `http://localhost:8009/`
- Vite dev server: `http://localhost:6174`
- Backend API: `http://localhost:8009/api/`
- Health endpoint: `http://localhost:8009/api/health/`
- PostgreSQL: `localhost:5433`

The app is configured for live reload in development through bind mounts. Django serves the built frontend from `frontend/dist` at `/`, while the Vite dev server remains available separately on port `6174`.

## Local Development

### Backend

```bash
cd backend
cp .env.example .env
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
```

Useful commands:

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
```

### Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
npm run build
```

The frontend expects `VITE_API_BASE_URL` to point to the backend API root. By default it uses `http://localhost:8009/api`.

## Docker Workflow

Start everything:

```bash
just dev
```

Start everything in the background:

```bash
just up
```

Tail the container logs:

```bash
just logs
```

Run backend only:

```bash
just backend
```

Run frontend only:

```bash
just frontend
```

Apply database migrations:

```bash
just migrate
```

Run backend tests:

```bash
just test
```

Run Django management commands:

```bash
just manage shell
just manage showmigrations
```

## Production on Hetzner

This repo includes a single-server production setup for a Hetzner VM using:

- Docker Compose
- PostgreSQL
- Django served by Gunicorn
- Caddy for HTTPS and reverse proxy

### What runs in production

- `db`: PostgreSQL 17
- `app`: Django in `config.settings.prod`
- `caddy`: TLS termination, HTTP to HTTPS redirect, reverse proxy to Django

The production backend image builds the React app during the Docker build and copies `frontend/dist` into the Django container. There is no separate frontend runtime in production.

### Server prerequisites

On the Hetzner server:

1. Install Docker Engine and the Compose plugin.
2. Point your domain DNS at the server IP.
3. Open ports `80` and `443` in the firewall.
4. Clone this repository onto the server.

### Production env files

Create these files on the server:

```bash
cp deploy/.env.prod.example deploy/.env.prod
cp backend/.env.prod.example backend/.env.prod
```

Set at minimum:

- `deploy/.env.prod`
  - `DOMAIN`
  - `POSTGRES_DB`
  - `POSTGRES_USER`
  - `POSTGRES_PASSWORD`
  - `PDF_SERVER_DIR`
- `backend/.env.prod`
  - `DJANGO_SECRET_KEY`
  - `DJANGO_ALLOWED_HOSTS`
  - `CSRF_TRUSTED_ORIGINS`
  - `DATABASE_URL`
  - `CORS_ALLOWED_ORIGINS`
  - `PDF_ROOT`

`DATABASE_URL` should point to the internal Compose database service, for example:

```bash
DATABASE_URL=postgresql://proxyfaux:replace-db-password@db:5432/proxyfaux
```

### Deploy

From the repo root on the server:

```bash
./deploy.sh
```

or:

```bash
just server-deploy
```

Direct Compose still works:

```bash
just prod-up
```

View logs:

```bash
just prod-logs
```

Stop the production stack:

```bash
just prod-down
```

### PDFs In Production

Large PDF datasets should stay out of Git and out of the app image.

Recommended setup:

- keep local PDFs in `backend/data/pdfs`
- sync them separately to the server
- mount them into the app container

The production stack expects:

- server-side PDF directory from `deploy/.env.prod`
  - `PDF_SERVER_DIR=/srv/proxyfaux-data/pdfs`
- container-side path from `backend/.env.prod`
  - `PDF_ROOT=/app/data/pdfs`

Sync PDFs from your local machine:

```bash
./sync-pdfs.sh
```

or:

```bash
just sync-pdfs
```

Then deploy normally:

```bash
just deploy
```

### Notes

- Caddy automatically provisions TLS certificates once the domain resolves to the server.
- The production container runs migrations and `collectstatic` on startup.
- Django serves the built SPA and WhiteNoise serves Django static assets.
- Keep `DJANGO_DEBUG=False` in production.
- `deploy.sh` expects `deploy/.env.prod` and `backend/.env.prod` to already exist.

### Deploy From Your Local Machine

If you want one local command that connects to the Hetzner machine, installs Docker if needed, clones or updates the repo there, uploads the production env files, and deploys, use:

```bash
./deploy-remote.sh
```

or:

```bash
just deploy
```

Optional arguments:

```bash
./deploy-remote.sh [user@host] [repo_url] [branch] [app_dir]
```

Defaults:

- `user@host`: `root@178.105.254.109`
- `repo_url`: current local `git remote.origin.url`
- `branch`: current local branch
- `app_dir`: `/srv/proxyfaux`

This command expects these local files to exist before running:

- `deploy/.env.prod`
- `backend/.env.prod`
- `frontend/.env.prod`

## Environment Variables

### Backend

`backend/.env.example` includes:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `DATABASE_URL`
- `CORS_ALLOWED_ORIGINS`
- `FRONTEND_DIST_DIR`

`backend/.env.prod.example` also includes:

- `CSRF_TRUSTED_ORIGINS`
- `PDF_ROOT`
- `SECURE_SSL_REDIRECT`

### Frontend

`frontend/.env.example` includes:

- `VITE_API_BASE_URL`

## Notes

- Django settings are split into `base.py`, `dev.py`, and `prod.py`.
- Django serves the SPA from `frontend/dist` at `/`.
- Rebuild the frontend with `npm run build` after frontend changes if you want Django to serve the latest bundle.
- In Docker, `frontend/dist` is mounted into the backend container so Django can read the built files.
- `uv` manages Python dependencies via `pyproject.toml`.
- PostgreSQL is the default database in both Docker and local development.
- The starter intentionally keeps architecture simple while leaving room for production hardening.
