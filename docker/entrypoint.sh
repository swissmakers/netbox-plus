#!/bin/bash
set -euo pipefail

APP_DIR="/opt/netbox/app"
cd "${APP_DIR}"

PY="${PYTHON_BIN:-python}"

wait_for_tcp() {
  local host="$1" port="$2" name="$3" max="${4:-60}"
  local i=0
  while (( i < max )); do
    if timeout 1 bash -c "echo > /dev/tcp/${host}/${port}" 2>/dev/null; then
      echo "${name} (${host}:${port}) is reachable."
      return 0
    fi
    echo "Waiting for ${name} (${host}:${port})..."
    sleep 2
    ((i++)) || true
  done
  echo "Timeout waiting for ${name}."
  exit 1
}

DB_HOST="${NETBOX_DB_HOST:-postgres}"
DB_PORT="${NETBOX_DB_PORT:-5432}"
REDIS_HOST="${NETBOX_REDIS_HOST:-redis}"
REDIS_PORT="${NETBOX_REDIS_PORT:-6379}"

ROLE="${1:-web}"

wait_for_tcp "${DB_HOST}" "${DB_PORT}" "PostgreSQL"
wait_for_tcp "${REDIS_HOST}" "${REDIS_PORT}" "Redis"

# Only the web container must run migrations. Parallel migrate from worker + web
# corrupts PostgreSQL catalog state (django_migrations / pg_type race).
if [[ "${ROLE}" == "worker" ]]; then
  echo "Worker mode: skipping migrate and collectstatic (handled by the netbox web service)."
  echo "Starting RQ worker (high, default, low)..."
  exec ${PY} manage.py rqworker high default low
fi

echo "Running database migrations..."
# Skip ConfigRevision query until core tables exist (avoids Postgres ERROR noise in logs).
NETBOX_SKIP_DB_CONFIG=1 ${PY} manage.py migrate --no-input

echo "Collecting static files..."
${PY} manage.py collectstatic --no-input

if [[ "${NETBOX_CREATE_SUPERUSER:-0}" == "1" ]]; then
  if ${PY} manage.py shell -c "from django.contrib.auth import get_user_model; import sys; sys.exit(0 if get_user_model().objects.filter(is_superuser=True).exists() else 1)"; then
    echo "Superuser already exists; skipping createsuperuser."
  else
    echo "Creating Django superuser from environment..."
    export DJANGO_SUPERUSER_USERNAME="${NETBOX_SUPERUSER_NAME:-admin}"
    export DJANGO_SUPERUSER_EMAIL="${NETBOX_SUPERUSER_EMAIL:-admin@example.com}"
    export DJANGO_SUPERUSER_PASSWORD="${NETBOX_SUPERUSER_PASSWORD:?NETBOX_SUPERUSER_PASSWORD must be set when NETBOX_CREATE_SUPERUSER=1}"
    ${PY} manage.py createsuperuser --no-input
  fi
fi

echo "Starting Gunicorn..."
BIND="${NETBOX_BIND_ADDRESS:-0.0.0.0}:${NETBOX_HTTP_PORT:-8080}"
WORKERS="${GUNICORN_WORKERS:-3}"
THREADS="${GUNICORN_THREADS:-3}"
exec ${PY} -m gunicorn \
  --bind "${BIND}" \
  --workers "${WORKERS}" \
  --threads "${THREADS}" \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  netbox.wsgi:application
