#!/bin/sh
set -eu

usage() {
  cat <<'EOF'
Usage:
  ./sync-pdfs.sh [user@host] [remote_pdf_dir]

Defaults:
  user@host       root@178.105.254.109
  remote_pdf_dir  /srv/proxyfaux-data/pdfs

Requirements:
  - rsync
  - ssh
  - local backend/data/pdfs directory
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

TARGET="${1:-root@178.105.254.109}"
REMOTE_PDF_DIR="${2:-/srv/proxyfaux-data/pdfs}"
LOCAL_PDF_DIR="backend/data/pdfs"

if [ ! -d "$LOCAL_PDF_DIR" ]; then
  echo "Missing local PDF directory: $LOCAL_PDF_DIR"
  exit 1
fi

if ! command -v rsync >/dev/null 2>&1; then
  echo "rsync is required to sync PDFs."
  exit 1
fi

ssh "$TARGET" "mkdir -p '$REMOTE_PDF_DIR'"
rsync -av --delete "$LOCAL_PDF_DIR"/ "$TARGET:$REMOTE_PDF_DIR"/

echo "PDF sync completed to $TARGET:$REMOTE_PDF_DIR"
