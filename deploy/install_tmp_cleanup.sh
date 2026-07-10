#!/bin/sh
set -eu

CRON_FILE="/etc/cron.d/proxyfaux-tmp-cleanup"
DEFAULT_TARGET="/tmp/proxyfaux-generated-pdfs"
TARGET_DIR="${1:-$DEFAULT_TARGET}"

cat > "$CRON_FILE" <<EOF
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Remove generated ProxyFaux temp PDFs older than 1 day.
17 3 * * * root find "$TARGET_DIR" -mindepth 1 \\( -type f -o -type l \\) -mtime +1 -delete
18 3 * * * root find "$TARGET_DIR" -mindepth 1 -type d -empty -delete
EOF

chmod 0644 "$CRON_FILE"
mkdir -p "$TARGET_DIR"

echo "Installed cron cleanup at $CRON_FILE for $TARGET_DIR"
