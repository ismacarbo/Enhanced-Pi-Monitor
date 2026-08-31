#!/bin/sh
set -eu

umask 077

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WIKI_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
REPOSITORY_ROOT=$(CDPATH= cd -- "$WIKI_DIR/../.." && pwd)
ENV_FILE="$WIKI_DIR/.env"
COMPOSE_FILE="$WIKI_DIR/docker-compose.yml"
BACKUP_DIR=${WIKIJS_BACKUP_DIR:-"$REPOSITORY_ROOT/backups/wikijs"}

if [ ! -f "$ENV_FILE" ]; then
    printf '%s\n' "Missing $ENV_FILE. Copy .env.example and configure it first." >&2
    exit 2
fi

mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUTPUT="$BACKUP_DIR/wikijs-$TIMESTAMP.dump"
TEMP_OUTPUT="$OUTPUT.tmp"
trap 'rm -f "$TEMP_OUTPUT"' EXIT HUP INT TERM

docker compose \
    --project-directory "$WIKI_DIR" \
    --env-file "$ENV_FILE" \
    -f "$COMPOSE_FILE" \
    exec -T wikijs-db \
    sh -c 'pg_dump --format=custom --compress=9 --no-owner --no-privileges --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"' \
    > "$TEMP_OUTPUT"

mv "$TEMP_OUTPUT" "$OUTPUT"
trap - EXIT HUP INT TERM
printf '%s\n' "Wiki.js database backup created: $OUTPUT"
