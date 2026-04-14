# Enterprise authentication (NetBox Plus)

LDAP and OIDC settings in NetBox Plus are primarily managed in **Admin → Authentication → LDAP / OIDC**. Changes saved there are persisted in the database (`ENTERPRISE_AUTH` in `ConfigRevision`) and hot-applied without restarting workers.

## Precedence

1. **Environment overrides** —> `NETBOX_LDAP_BIND_PASSWORD`, `NETBOX_OIDC_SECRET`, and `NETBOX_OIDC_KEY` override secret values at runtime. Corresponding UI fields are read-only while those environment variables are set.
2. **`ENTERPRISE_AUTH` dynamic config (database)** —> Primary persistent source, edited in Admin UI.
3. **`netbox/ldap_config.py` (legacy fallback)** —> If this module exists and defines `AUTH_LDAP_SERVER_URI`, LDAP is loaded from that file for compatibility with legacy deployments.

## OpenID Connect

- Enable `oidc.enabled`, set `oidc_endpoint` (issuer base URL **without** `/.well-known/openid-configuration`), `key`, and `secret` (or use the environment variables above).
- When both LDAP and OIDC are enabled in `ENTERPRISE_AUTH`, `netbox.authentication.LDAPBackend` is registered **before** `social_core.backends.open_id_connect.OpenIdConnectAuth` so username/password login tries LDAP first; OIDC remains the SSO button flow on the login page. Either backend is omitted when its `enabled` flag is false, unless already present from `REMOTE_AUTH_BACKEND` in `configuration.py`.
- `django.conf.settings` is updated **per request** so changes take effect without restarting the WSGI workers.

## LDAP

- Install system LDAP libraries and `django-auth-ldap` (included in NetBox Plus `requirements.txt`).
- Set `REMOTE_AUTH_BACKEND` in `configuration.py` to include `netbox.authentication.LDAPBackend` (and typically `django.contrib.auth.backends.ModelBackend` for local users), **or** enable `ldap.enabled` in `ENTERPRISE_AUTH`; the middleware will inject `LDAPBackend` when it is missing from the static backend list.
- When using **only** dynamic config (no `ldap_config.py`), fill `server_uri`, `user_search_base`, `user_search_filter`, and other fields as described in the [LDAP installation guide](../../installation/6-ldap.md) (the same concepts apply).

## Demo templates (Active Directory / FreeIPA)

On **Admin → Authentication → LDAP / OIDC**, open **Configure LDAP**, then use **Active Directory** or **FreeIPA** to load placeholders into the form (save to apply). Replace all `example.com` / `dc=example,dc=com` values with your directory. Do not use the demo bind passwords in production; prefer `NETBOX_LDAP_BIND_PASSWORD`.
