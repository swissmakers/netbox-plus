# Containers with Podman Compose (NetBox Plus)

NetBox Plus ships a **Dockerfile** and **Compose** stack in the repository root: PostgreSQL 16, Redis 7, Gunicorn (web), and RQ workers. The image is based on **Red Hat UBI** (UBI 9 by default; UBI 10 optional on CPUs that support x86-64-v3).

Documentation and examples use **`podman`** and **`podman compose`**. If your organization standardizes on Docker Engine, the same `docker-compose.yml` works with **`docker compose`**; only the CLI prefix changes.

## Why we recommend Podman

- **Daemonless model:** Podman runs containers as regular processes instead of relying on a single long-lived root daemon for every operation. That simplifies threat modeling and avoids the “access to the Docker socket” pattern that is effectively broad host privilege on many setups.
- **Rootless-first:** Building and running images as an unprivileged user is a well-supported path, which matters on shared servers and in regulated environments.
- **Same images and workflows:** Podman uses **OCI** images and registries like Docker Hub; commands mirror Docker’s (`podman run`, `podman build`, `podman compose`).
- **Alignment with RHEL / UBI:** The NetBox Plus image is built on **Red Hat UBI**; Podman is the supported container stack on RHEL and integrates cleanly with **SELinux** and enterprise Linux policies.
- **Licensing on workstations:** **Docker Desktop** has commercial licensing constraints for some companies; **Podman Desktop** is a practical alternative where that applies.

Some tools still assume a Docker socket; if you depend on those, Docker may remain the right choice for that environment. For typical NetBox Plus deployments on Linux, **Podman is the default we document and recommend**.

## Official pre-built image

Swissmakers publishes a ready-to-use image to Docker Hub:

**[swissmakers/netbox-plus on Docker Hub](https://hub.docker.com/repository/docker/swissmakers/netbox-plus)**

Pull the latest tag (or a specific tag if published):

```bash
podman pull swissmakers/netbox-plus:latest
```

Use it with the bundled Compose file (the default `image` is `swissmakers/netbox-plus:latest`; set `NETBOX_IMAGE` in `.env` only for another tag or registry):

1. Copy the environment template: `cp docker/.env.example .env`
2. Set at least `NETBOX_SECRET_KEY`, change admin credentials and modify any host/CSRF values you need.
3. From the **repository root** (where `docker-compose.yml` lives):

   ```bash
   podman compose pull netbox
   podman compose up -d
   ```

After the image is present locally, Compose will use it for both `netbox` and `netbox-worker`. The main Compose file does **not** define `build:` for `netbox` (so `NETBOX_IMAGE` is not ignored by an automatic rebuild). To build from the local `Dockerfile`, run `podman build` and set `NETBOX_IMAGE=localhost/netbox-plus:dev` in `.env` (see `docker/README.md`).

Open the UI on `http://localhost:8080` (or the host/port you mapped with `NETBOX_PUBLISH_PORT`).

## Build from source instead

To build the UBI image locally (same layout as CI):

```bash
podman build -t netbox-plus:dev .
cp docker/.env.example .env
# edit .env — set NETBOX_SECRET_KEY, superuser vars, and NETBOX_IMAGE=localhost/netbox-plus:dev
podman compose up -d
```

Optional: `NETBOX_BASE_IMAGE` for UBI 10 (see repository `docker/README.md`).

## Further reading

- Repository **`docker/README.md`**
- **LDAP** — [LDAP installation](6-ldap.md) and [Enterprise authentication](../administration/authentication/enterprise-auth.md).
