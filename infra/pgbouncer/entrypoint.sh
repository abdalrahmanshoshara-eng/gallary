#!/bin/sh
# Renders pgbouncer.ini and the auth file from environment variables, then starts PgBouncer.
# The password is never baked into the image.
set -eu

: "${DB_HOST:?DB_HOST is required}"
: "${DB_USER:?DB_USER is required}"
: "${DB_PASSWORD:?DB_PASSWORD is required}"
export DB_PORT="${DB_PORT:-5432}"
export DB_NAME="${DB_NAME:-postgres}"
export PGB_MAX_CLIENT_CONN="${PGB_MAX_CLIENT_CONN:-1000}"
export PGB_DEFAULT_POOL_SIZE="${PGB_DEFAULT_POOL_SIZE:-20}"
export PGB_RUNTIME_DIR="${PGB_RUNTIME_DIR:-/var/run/pgbouncer}"
TEMPLATE="${PGB_TEMPLATE:-/etc/pgbouncer/pgbouncer.ini.template}"

umask 077
mkdir -p "$PGB_RUNTIME_DIR"
printf '"%s" "%s"\n' "$DB_USER" "$DB_PASSWORD" > "$PGB_RUNTIME_DIR/userlist.txt"

# Substitute ${VAR} placeholders (no envsubst dependency).
awk '{
  line = $0
  while (match(line, /\$\{[A-Z_]+\}/)) {
    name = substr(line, RSTART + 2, RLENGTH - 3)
    line = substr(line, 1, RSTART - 1) ENVIRON[name] substr(line, RSTART + RLENGTH)
  }
  print line
}' "$TEMPLATE" > "$PGB_RUNTIME_DIR/pgbouncer.ini"

exec pgbouncer "$PGB_RUNTIME_DIR/pgbouncer.ini"
