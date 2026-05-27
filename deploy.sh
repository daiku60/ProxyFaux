#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

DEPLOY_ENV_FILE="deploy/.env.prod"
BACKEND_ENV_FILE="backend/.env.prod"
FRONTEND_ENV_FILE="frontend/.env.prod"

if [ ! -f "$DEPLOY_ENV_FILE" ]; then
  echo "Missing $DEPLOY_ENV_FILE"
  echo "Create it from deploy/.env.prod.example before deploying."
  exit 1
fi

if [ ! -f "$BACKEND_ENV_FILE" ]; then
  echo "Missing $BACKEND_ENV_FILE"
  echo "Create it from backend/.env.prod.example before deploying."
  exit 1
fi

if [ ! -f "$FRONTEND_ENV_FILE" ]; then
  echo "Missing $FRONTEND_ENV_FILE"
  echo "Create it before deploying so the production frontend build has its env values."
  exit 1
fi

docker compose \
  --env-file "$DEPLOY_ENV_FILE" \
  -f docker-compose.prod.yml \
  up --build -d

echo "Production deploy started."
echo "Follow logs with:"
echo "  docker compose --env-file $DEPLOY_ENV_FILE -f docker-compose.prod.yml logs -f"
