# Docker / Compose (NetBox Plus)

NetBox Plus ships a **Dockerfile** and **Compose** stack in the repository root: PostgreSQL 16, Redis 7, Gunicorn (web), and RQ workers. The image is based on **Red Hat UBI** (UBI 9 by default; UBI 10 optional on CPUs that support x86-64-v3).

## Official pre-built image

Swissmakers publishes a ready-to-use image to Docker Hub:

**[swissmakers/netbox-plus on Docker Hub](https://hub.docker.com/repository/docker/swissmakers/netbox-plus)**

Pull the latest tag (or a specific tag if published):

```bash
docker pull swissmakers/netbox-plus:latest
```

Use it with the bundled Compose file:

1. Copy the environment template: `cp docker/.env.example .env`
2. Set at least `NETBOX_SECRET_KEY`, change admin credentials and modify any host/CSRF values you need.
3. Point Compose at the registry image in `.env` like:

   ```env
   NETBOX_IMAGE=swissmakers/netbox-plus:latest
   ```

4. From the **repository root** (where `docker-compose.yml` lives):

   ```bash
   podman compose pull netbox
   podman compose up -d
   ```

After the image is present locally, Compose will use it for both `netbox` and `netbox-worker`. Use `docker compose up --build` only when you intend to **build** the image from the local `Dockerfile` instead of using the pre-built one.

Open the UI on `http://localhost:8080` (or the host/port you mapped with `NETBOX_PUBLISH_PORT`).

## Build from source instead

To build the UBI image locally (same layout as CI):

```bash
cp docker/.env.example .env
# edit .env — set NETBOX_SECRET_KEY, superuser vars, etc.
docker compose up --build
```

Optional: `NETBOX_BASE_IMAGE` for UBI 10 (see repository `docker/README.md`).

## Further reading

- Repository **`docker/README.md`**
- **LDAP** — [LDAP installation](6-ldap.md) and [Enterprise authentication](../administration/authentication/enterprise-auth.md).
