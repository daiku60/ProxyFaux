#!/bin/sh
set -eu

usage() {
  cat <<'EOF'
Usage:
  ./deploy-remote.sh [user@host] [repo_url] [branch] [app_dir]

Defaults:
  user@host root@178.105.254.109
  repo_url  current git remote.origin.url
  branch    current local branch
  app_dir   /srv/proxyfaux

Requirements on the local machine:
  - ssh
  - scp
  - git
  - deploy/.env.prod
  - backend/.env.prod
  - frontend/.env.prod
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

TARGET="${1:-root@178.105.254.109}"
REPO_URL="${2:-$(git config --get remote.origin.url || true)}"
BRANCH="${3:-$(git rev-parse --abbrev-ref HEAD)}"
APP_DIR="${4:-/srv/proxyfaux}"

DEPLOY_ENV_FILE="deploy/.env.prod"
BACKEND_ENV_FILE="backend/.env.prod"
FRONTEND_ENV_FILE="frontend/.env.prod"

if [ -z "$REPO_URL" ]; then
  echo "Unable to determine repo URL."
  echo "Pass it explicitly as the second argument."
  exit 1
fi

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

REMOTE_SCRIPT="$(mktemp)"
cat > "$REMOTE_SCRIPT" <<EOF
set -eu

if [ "\$(id -u)" -eq 0 ]; then
  SUDO=""
else
  SUDO="sudo"
fi

if ! command -v git >/dev/null 2>&1; then
  \$SUDO apt-get update
  \$SUDO apt-get install -y git ca-certificates curl
fi

if ! command -v git-lfs >/dev/null 2>&1; then
  \$SUDO apt-get update
  \$SUDO apt-get install -y git-lfs
fi

if ! command -v docker >/dev/null 2>&1; then
  \$SUDO apt-get update
  \$SUDO apt-get install -y ca-certificates curl gnupg
  \$SUDO install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \$SUDO gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  \$SUDO chmod a+r /etc/apt/keyrings/docker.gpg
  . /etc/os-release
  echo "deb [arch=\$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \$VERSION_CODENAME stable" | \$SUDO tee /etc/apt/sources.list.d/docker.list >/dev/null
  \$SUDO apt-get update
  \$SUDO apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

APP_DIR='$APP_DIR'
REPO_URL='$REPO_URL'
BRANCH='$BRANCH'

\$SUDO mkdir -p "\$(dirname "\$APP_DIR")"

if [ ! -d "\$APP_DIR/.git" ]; then
  \$SUDO rm -rf "\$APP_DIR"
  \$SUDO git clone --branch "\$BRANCH" "\$REPO_URL" "\$APP_DIR"
else
  \$SUDO git -C "\$APP_DIR" fetch origin "\$BRANCH"
  \$SUDO git -C "\$APP_DIR" checkout "\$BRANCH"
  \$SUDO git -C "\$APP_DIR" reset --hard "origin/\$BRANCH"
fi

\$SUDO mkdir -p "\$APP_DIR/deploy" "\$APP_DIR/backend"
\$SUDO chown -R "\$(id -un):\$(id -gn)" "\$APP_DIR"
git -C "\$APP_DIR" lfs install --local
git -C "\$APP_DIR" lfs fetch origin "\$BRANCH"
git -C "\$APP_DIR" lfs checkout
git -C "\$APP_DIR" lfs pull origin "\$BRANCH"

if [ ! -d "\$APP_DIR/backend/data/cards" ]; then
  echo "Git LFS assets were not materialized at \$APP_DIR/backend/data/cards"
  exit 1
fi

\$SUDO chmod +x "\$APP_DIR/deploy/install_tmp_cleanup.sh"
\$SUDO "\$APP_DIR/deploy/install_tmp_cleanup.sh"
EOF

ssh "$TARGET" 'sh -s' < "$REMOTE_SCRIPT"
rm -f "$REMOTE_SCRIPT"

scp "$DEPLOY_ENV_FILE" "$TARGET:$APP_DIR/deploy/.env.prod"
scp "$BACKEND_ENV_FILE" "$TARGET:$APP_DIR/backend/.env.prod"
scp "$FRONTEND_ENV_FILE" "$TARGET:$APP_DIR/frontend/.env.prod"

ssh "$TARGET" "cd '$APP_DIR' && chmod +x deploy.sh && ./deploy.sh"
