# Docker / Compose (NetBox Plus)

This stack uses:

- **Dockerfile**: default `registry.access.redhat.com/ubi9/ubi:latest` (UBI 9) with Python 3.12, dependencies from `requirements.txt`, and Gunicorn. UBI 10 is optional via build-arg (see below).
- **docker-compose.yml**: PostgreSQL 16, Redis 7, NetBox web (Gunicorn), and NetBox RQ worker (`high`, `default`, `low` queues).

## Quick start

```bash
cp docker/.env.example .env
# Edit .env —> set NETBOX_SECRET_KEY (and optionally superuser + password)
docker compose up --build
```

Open `http://localhost:8080`. To create an admin on first boot:

```env
NETBOX_CREATE_SUPERUSER=1
NETBOX_SUPERUSER_PASSWORD=your-secure-password
```

## Configuration

Runtime settings are driven by `docker/configuration_docker.py` (copied into the image as `netbox/configuration_docker.py`) and the `NETBOX_*` environment variables documented in that file.

`NETBOX_CONFIGURATION` is set to `netbox.configuration_docker` in Compose.

## Notes

- **CPU / glibc (x86-64-v3)**: UBI **10** glibc is built for **x86-64-v3**. Older CPUs hit `Fatal glibc error: CPU does not support x86-64-v3` during `RUN dnf`. The default **UBI 9** base avoids that. To build on UBI 10 anyway (v3-capable CPU only):
  `podman build --build-arg BASE_IMAGE=registry.access.redhat.com/ubi10/ubi:latest -t netbox-plus:local .`
  or set `NETBOX_BASE_IMAGE` in Compose (see `docker-compose.yml` `build.args`).
- **Housekeeping** (scheduled jobs) is not included; add a cron sidecar or host job if you need it in production.
- For TLS termination, place a reverse proxy in front and set `NETBOX_CSRF_TRUSTED_ORIGINS` / `NETBOX_ALLOWED_HOSTS` accordingly.
- **Migrations**: only the `netbox` (web) service runs `migrate`; `netbox-worker` waits for `netbox` to be healthy so two containers never migrate in parallel (that caused `django_migrations` / `pg_type` conflicts on first boot).
- **Postgres / `core_configrevision` during `migrate`**: the entrypoint sets `NETBOX_SKIP_DB_CONFIG=1` for `migrate` only so NetBox does not query `ConfigRevision` before that table exists (avoids spurious `ERROR: relation ... does not exist` in Postgres logs). Gunicorn and the worker run without that flag so dynamic config loads normally.
- If a previous attempt left Postgres half-initialized, reset the DB volume: `podman compose down -v` (removes `postgres-data`) then `up --build` again.
- The UBI image pulls unauthenticated from `registry.access.redhat.com`; ensure your registry policy allows it.
