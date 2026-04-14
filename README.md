# NetBox Plus

**NetBox Plus** is a community-oriented fork of [NetBox](https://github.com/netbox-community/netbox), the open-source network source-of-truth and infrastructure resource modeling (IRM) tool. It is developed and maintained by **[Swissmakers GmbH](https://swissmakers.ch)**.

NetBox Plus is **not** [NetBox Enterprise](https://netboxlabs.com/netbox-enterprise/). It is a **separate product path**: free software, **intended to remain free**, with optional **commercial support** available from Swissmakers GmbH for organizations running NetBox.

What is different? For example the LDAP and OIDC integration directly configurable via authentication manager is one feature that is already integrated with NetBox Plus. The goal is to extend NetBox in ways that matter to engineers, without paywalling important product features.

## What you get

NetBox Plus inherits the full NetBox data model, APIs, plugins ecosystem, and operational patterns you already know: DCIM, IPAM, circuits, virtualization, permissions, change logging, and more.

On top of that, NetBox Plus will add Swissmakers improvements such as hardenings, container-files, documentation, packaging, and additional features. Roadmap items will be documented in this repository as they land.

## Container image

This repository includes a ready-to-use container definition, based on the **Red Hat Universal Base Image 10 (UBI 10)** so you can run NetBox Plus directly in a hardened, enterprise-friendly base. See the `docker/` directory and `docker-compose.yml` for a full stack (PostgreSQL, Redis, web, workers).

Quick start:

```bash
cp docker/.env.example .env
# Edit .env —> set NETBOX_SECRET_KEY and change superuser variables
docker compose up --build
# UI: http://localhost:8080
```

Adjust for your orchestrator (e.g. Podman) as needed.


## Documentation

- **NetBox Plus authentication (LDAP / OIDC):** [Enterprise authentication](docs/administration/authentication/enterprise-auth.md), [LDAP installation](docs/installation/6-ldap.md)
- **Upstream NetBox docs** (concepts and features): [docs.netbox.dev](https://docs.netbox.dev)


## License

**NetBox Plus is licensed under the GNU General Public License v3 (GPL-3.0)** from the fork onward. See [`LICENSE.txt`](LICENSE.txt) for the full license text and a **copyright / upstream notice** that explains how this relates to original NetBox (Apache-2.0) code.

Some files that were **not substantively modified** after the fork may still carry **original NetBox or third-party copyright and license headers**. Those notices take precedence for those specific files; the `LICENSE.txt` preamble summarizes the intent.

## Contributing & support

Community contributions are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md) for the project’s contribution workflow.

For **professional support, consulting, or SLAs** on NetBox Plus, contact **Swissmakers GmbH**.


## Acknowledgements

NetBox Plus builds on the work of the **NetBox community** and **NetBox Labs** / upstream contributors. We are grateful for the project they created and maintain upstream.


## Screenshots

<p align="center">
  <img src="docs/media/screenshots/home-light.png" width="600" alt="NetBox user interface screenshot" />
</p>
