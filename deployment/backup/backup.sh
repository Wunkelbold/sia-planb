#!/usr/bin/env bash
# Offsite backup for the SIA PlanB production stack.
#
# Backs up the PostgreSQL database, mail data/config, uploaded images, and
# /etc/sia-planb into a restic repository, applies retention, and checks the
# repository. Reports success/failure to an Uptime Kuma push monitor.
#
# Setup and restore instructions: see "Backups" in the repository README.

set -euo pipefail

CONFIG_FILE="${BACKUP_CONFIG_FILE:-/etc/sia-planb/backup.env}"
COMPOSE_FILE="${SIA_COMPOSE_FILE:-/etc/sia-planb/compose.yml}"
COMPOSE_ENV_FILE="${SIA_COMPOSE_ENV_FILE:-/etc/sia-planb/production.env}"
LOCK_FILE="/run/sia-planb-backup.lock"
RESTIC_HOST_NAME="sia-planb"

log() { printf '%s %s\n' "$(date -Is)" "$*"; }
fail() { log "ERROR: $*"; exit 1; }

[[ $EUID -eq 0 ]] || fail "must run as root"
[[ -f "$CONFIG_FILE" ]] || fail "missing config file: $CONFIG_FILE"
[[ -f "$COMPOSE_FILE" ]] || fail "missing compose file: $COMPOSE_FILE"
[[ -f "$COMPOSE_ENV_FILE" ]] || fail "missing compose env file: $COMPOSE_ENV_FILE"

set -a
# shellcheck disable=SC1090
source "$CONFIG_FILE"
# shellcheck disable=SC1090
source "$COMPOSE_ENV_FILE"
set +a

BACKUP_ROOT="${BACKUP_ROOT:-/var/lib/sia-planb/backups}"
staging=""

[[ -n "${RESTIC_REPOSITORY:-}" ]] || fail "RESTIC_REPOSITORY is not set in $CONFIG_FILE"
[[ -n "${RESTIC_PASSWORD_FILE:-}" ]] || fail "RESTIC_PASSWORD_FILE is not set in $CONFIG_FILE"
for required in DATABASE_NAME DATABASE_USER MAIL_DATA_PATH MAIL_CONFIG_PATH MAIL_STATE_PATH FLASK_IMAGE; do
  [[ -n "${!required:-}" ]] || fail "$required is not set in $COMPOSE_ENV_FILE"
done

start=$SECONDS

send_kuma() {
  local status="$1" message="$2" ping="${3:-}"
  [[ -n "${KUMA_PUSH_URL:-}" ]] || return 0
  local args=(-fsS -m 15 -G "$KUMA_PUSH_URL" --data-urlencode "status=$status" --data-urlencode "msg=$message")
  if [[ -n "$ping" ]]; then
    args+=(--data-urlencode "ping=$ping")
  fi
  curl "${args[@]}" >/dev/null 2>&1 || log "WARN: Uptime Kuma heartbeat failed"
}

on_exit() {
  local code=$?
  if [[ -n "$staging" ]]; then
    rm -rf "$staging"
  fi
  if (( code != 0 )); then
    set +e
    send_kuma down "backup failed (exit $code)"
  fi
  exit "$code"
}
trap on_exit EXIT

compose() {
  docker compose --project-name sia-backend --file "$COMPOSE_FILE" --env-file "$COMPOSE_ENV_FILE" "$@"
}

mkdir -p "$BACKUP_ROOT"
exec 9>"$LOCK_FILE"
flock -n 9 || fail "another backup run is already active"

staging="$BACKUP_ROOT/staging"
rm -rf "$staging"
mkdir -p "$staging"

[[ -d "$MAIL_DATA_PATH" ]] || fail "mail data path does not exist: $MAIL_DATA_PATH"
[[ -d "$MAIL_CONFIG_PATH" ]] || fail "mail config path does not exist: $MAIL_CONFIG_PATH"

log "dumping database $DATABASE_NAME"
compose exec -T database pg_dump --format=custom --username "$DATABASE_USER" "$DATABASE_NAME" >"$staging/database.dump"
compose exec -T database pg_dumpall --globals-only --username "$DATABASE_USER" >"$staging/globals.sql"
[[ -s "$staging/database.dump" ]] || fail "database dump is empty"

for volume in eventposter drinkimages; do
  docker volume inspect "sia-backend_${volume}" >/dev/null 2>&1 || fail "missing docker volume sia-backend_${volume}"
  log "archiving volume sia-backend_$volume"
  docker run --rm --entrypoint tar \
    -v "sia-backend_${volume}:/data:ro" \
    "$FLASK_IMAGE" -czf - -C /data . >"$staging/${volume}.tar.gz"
done

log "uploading snapshot to $RESTIC_REPOSITORY"
backup_paths=(
  "$staging"
  "$MAIL_DATA_PATH"
  "$MAIL_CONFIG_PATH"
  /etc/sia-planb
)
if [[ -d "$MAIL_STATE_PATH/lib-redis" ]]; then
  backup_paths+=("$MAIL_STATE_PATH/lib-redis")
fi

restic backup \
  --host "$RESTIC_HOST_NAME" \
  --tag scheduled \
  --exclude=/etc/sia-planb/backup.env \
  --exclude=/etc/sia-planb/restic-password \
  "${backup_paths[@]}"

log "applying retention"
restic forget --host "$RESTIC_HOST_NAME" --keep-daily 7 --keep-weekly 5 --keep-monthly 12 --prune

log "checking repository"
restic check

duration=$((SECONDS - start))
send_kuma up "backup ok" "$((duration * 1000))"
log "backup finished in ${duration}s"
