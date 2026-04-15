# Installation

The installation instructions provided here have been tested to work on Rocky Linux 10. The particular commands needed to install dependencies on other distributions may vary significantly. Unfortunately, this is outside the control of the NetBox maintainers. Please consult your distribution's documentation for assistance with any errors.

For **NetBox Plus** using containers, Swissmakers provides an official image on Docker Hub and a Compose stack in the repository. See **[Containers with Podman Compose (NetBox Plus)](docker.md)** for the pre-built image, `podman compose` commands, why Podman is recommended, and how to set `NETBOX_IMAGE`.

The following sections detail how to set up a new instance of NetBox on a Linux host (traditional install):

1. [PostgreSQL database](1-postgresql.md)
2. [Redis](2-redis.md)
3. [NetBox components](3-netbox.md)
4. [Gunicorn](4a-gunicorn.md) or [uWSGI](4b-uwsgi.md)
5. [HTTP server](5-http-server.md)
6. [LDAP authentication](6-ldap.md)

## Requirements

| Dependency | Supported Versions |
|------------|--------------------|
| Python     | 3.12, 3.13, 3.14   |
| PostgreSQL | 14+                |
| Redis      | 4.0+               |

Below is a simplified overview of the NetBox application stack for reference:

![NetBox UI as seen by a non-authenticated user](../media/installation/netbox_application_stack.png)

## Upgrading

If you are upgrading from an existing installation, please consult the [upgrading guide](upgrading.md).
