#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WIKI_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
ENV_FILE="$WIKI_DIR/.env"
COMPOSE_FILE="$WIKI_DIR/docker-compose.yml"

if [ "$#" -ne 1 ]; then
    printf '%s\n' "Usage: $0 /path/to/wikijs-backup.dump" >&2
    exit 2
fi

BACKUP_FILE=$1
if [ ! -f "$BACKUP_FILE" ]; then
    printf '%s\n' "Backup file does not exist: $BACKUP_FILE" >&2
    exit 2
fi
if [ ! -f "$ENV_FILE" ]; then
    printf '%s\n' "Missing $ENV_FILE. Copy .env.example and configure it first." >&2
    exit 2
fi

printf '%s\n' "WARNING: this replaces objects in the configured Wiki.js database."
printf '%s\n' "Backup: $BACKUP_FILE"

if [ "${WIKIJS_RESTORE_CONFIRM:-}" != "RESTORE_WIKIJS" ]; then
    if [ ! -t 0 ]; then
        printf '%s\n' "Refusing non-interactive restore. Set WIKIJS_RESTORE_CONFIRM=RESTORE_WIKIJS." >&2
        exit 3
    fi
    printf '%s' "Type RESTORE_WIKIJS to continue: "
    read -r confirmation
    if [ "$confirmation" != "RESTORE_WIKIJS" ]; then
        printf '%s\n' "Restore cancelled."
        exit 3
    fi
fi

compose() {
    docker compose \
        --project-directory "$WIKI_DIR" \
        --env-file "$ENV_FILE" \
        -f "$COMPOSE_FILE" \
        "$@"
}

compose up -d --wait wikijs-db
if ! compose exec -T wikijs-db pg_restore --list < "$BACKUP_FILE" > /dev/null; then
    printf '%s\n' "The selected file is not a readable pg_dump custom archive." >&2
    exit 4
fi
compose stop wikijs
if ! compose exec -T wikijs-db \
    sh -c 'pg_restore --clean --if-exists --exit-on-error --no-owner --no-privileges --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"' \
    < "$BACKUP_FILE"; then
    printf '%s\n' "Restore failed. Wiki.js remains stopped; inspect the database before restarting it." >&2
    exit 4
fi
compose up -d --wait wikijs
printf '%s\n' "Wiki.js database restore completed."
