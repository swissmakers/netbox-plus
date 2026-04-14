"""
LDAP / OIDC connectivity checks for the admin UI (NetBox Plus).
"""
from __future__ import annotations

import json
import ssl
import threading
import time
import urllib.error
import urllib.request
from typing import Any

from django.utils.translation import gettext_lazy as _

from netbox.authentication.enterprise_ldap import _connection_options
from netbox.config.enterprise_auth import ldap_bind_password_resolved

_LDAP_TEST_LOCK = threading.Lock()


def _apply_tls_defaults_for_process(ldap_mod, ldap_cfg: dict[str, Any]) -> None:
    """
    Apply TLS defaults at module level for backends that honor global OpenLDAP options.
    """
    if bool(ldap_cfg.get('ignore_cert_errors')):
        ldap_mod.set_option(ldap_mod.OPT_X_TLS_REQUIRE_CERT, ldap_mod.OPT_X_TLS_NEVER)
    ca_dir = (ldap_cfg.get('ca_cert_dir') or '').strip() or None
    if ca_dir:
        ldap_mod.set_option(ldap_mod.OPT_X_TLS_CACERTDIR, ca_dir)
    ca_file = (ldap_cfg.get('ca_cert_file') or '').strip() or None
    if ca_file:
        ldap_mod.set_option(ldap_mod.OPT_X_TLS_CACERTFILE, ca_file)


def _apply_tls_to_ldap_connection(conn, ldap_mod, ldap_cfg: dict[str, Any]) -> None:
    """
    Apply TLS-related options on this LDAP connection only (not process-wide).

    Module-level ``ldap.set_option`` races under concurrent requests (e.g. double
    "Test LDAP" or login + test), which makes ``Ignore TLS certificate errors`` flaky.
    """
    if bool(ldap_cfg.get('ignore_cert_errors')):
        conn.set_option(ldap_mod.OPT_X_TLS_REQUIRE_CERT, ldap_mod.OPT_X_TLS_NEVER)
    ca_dir = (ldap_cfg.get('ca_cert_dir') or '').strip() or None
    if ca_dir:
        conn.set_option(ldap_mod.OPT_X_TLS_CACERTDIR, ca_dir)
    ca_file = (ldap_cfg.get('ca_cert_file') or '').strip() or None
    if ca_file:
        conn.set_option(ldap_mod.OPT_X_TLS_CACERTFILE, ca_file)


def _ldap_uri_is_ldaps(uri: str) -> bool:
    return uri.strip().lower().startswith('ldaps://')


def _format_ldap_exc(exc: BaseException) -> str:
    """Readable message for python-ldap errors (often dict-like)."""
    if exc is None:
        return ''
    args = getattr(exc, 'args', None) or ()
    if args and isinstance(args[0], dict):
        d = args[0]
        parts = [d.get('desc'), d.get('info')]
        return ': '.join(p for p in parts if p) or str(d)
    return str(exc)


def _ldap_build_connection(uri: str, ldap_cfg: dict[str, Any]):
    """
    Initialize LDAP connection, TLS options, and optionally STARTTLS.

    STARTTLS must not be used with ldaps:// —> the SSL session is already active
    (otherwise: Operations error / SSL connection already established).
    """
    import ldap

    _apply_tls_defaults_for_process(ldap, ldap_cfg)
    conn = ldap.initialize(uri)
    conn.set_option(ldap.OPT_PROTOCOL_VERSION, ldap.VERSION3)
    for opt, val in _connection_options(ldap_cfg.get('connection_options')).items():
        conn.set_option(opt, val)
    _apply_tls_to_ldap_connection(conn, ldap, ldap_cfg)
    # Force OpenLDAP to build a fresh TLS context from current options.
    try:
        conn.set_option(ldap.OPT_X_TLS_NEWCTX, 0)
    except Exception:
        pass
    want_start_tls = bool(ldap_cfg.get('start_tls'))
    ldaps = _ldap_uri_is_ldaps(uri)
    start_tls_applied = want_start_tls and not ldaps
    if start_tls_applied:
        conn.start_tls_s()
    elif want_start_tls and ldaps:
        # Informational only; not an error
        pass
    if ldaps:
        transport = 'LDAPS (TLS from connect)'
    elif start_tls_applied:
        transport = 'ldap:// + STARTTLS'
    else:
        transport = 'ldap:// (no TLS upgrade)'
    return conn, {
        'transport': transport,
        'start_tls_requested': want_start_tls,
        'start_tls_applied': start_tls_applied,
        'start_tls_skipped_ldaps': want_start_tls and ldaps,
    }


def test_ldap_configuration(
    ldap_cfg: dict[str, Any],
    *,
    test_username: str = '',
    test_password: str = '',
) -> dict[str, Any]:
    """
    Perform a service bind (if bind_dn set) and optionally verify user credentials via search + bind.
    Uses only the passed ``ldap_cfg`` (typically from the form): no save required.
    """
    import ldap
    import ldap.filter

    uri = (ldap_cfg.get('server_uri') or '').strip()
    if not uri:
        return {'ok': False, 'error': str(_('Server URI is empty.')), 'steps': []}

    steps: list[dict[str, Any]] = []
    t0 = time.monotonic()

    def add_step(label: str, message: str, status: str = 'ok'):
        steps.append({'label': label, 'message': message, 'status': status})

    with _LDAP_TEST_LOCK:
        try:
            conn, tls_meta = _ldap_build_connection(uri, ldap_cfg)
            add_step(
                str(_('Connect / TLS')),
                str(_('Transport: %(t)s') % {'t': tls_meta['transport']}),
            )
            if tls_meta.get('start_tls_skipped_ldaps'):
                add_step(
                    str(_('STARTTLS')),
                    str(_('STARTTLS not used: URI is ldaps:// (already encrypted).')),
                    'skip',
                )

            bind_dn = (ldap_cfg.get('bind_dn') or '').strip()
            bind_pw = ldap_bind_password_resolved(ldap_cfg)
            if bind_dn:
                conn.simple_bind_s(bind_dn, bind_pw)
                add_step(
                    str(_('Service bind')),
                    str(_('Bound as %(dn)s.') % {'dn': bind_dn}),
                )
                detail = str(_('Service account bind succeeded.'))
            else:
                conn.simple_bind_s('', '')
                add_step(str(_('Service bind')), str(_('Anonymous bind.')))
                detail = str(_('Anonymous bind succeeded.'))

            if test_username and test_password:
                base = (ldap_cfg.get('user_search_base') or '').strip()
                filt_tmpl = (ldap_cfg.get('user_search_filter') or '').strip()
                if not base or not filt_tmpl:
                    try:
                        conn.unbind_s()
                    except Exception:
                        pass
                    return {
                        'ok': False,
                        'error': str(_('User search base and filter are required for user test.')),
                        'steps': steps,
                    }
                filt = filt_tmpl.replace('%(user)s', ldap.filter.escape_filter_chars(test_username))
                scope_name = (ldap_cfg.get('user_search_scope') or 'SUBTREE').upper()
                scope = getattr(ldap, f'SCOPE_{scope_name}', ldap.SCOPE_SUBTREE)
                results = conn.search_s(base, scope, filt, ['dn'])
                add_step(
                    str(_('User search')),
                    str(
                        _('Base: %(base)s, scope: %(scope)s, matches: %(n)s')
                        % {'base': base, 'scope': scope_name, 'n': len(results)},
                    ),
                )
                try:
                    conn.unbind_s()
                except Exception:
                    pass
                if not results:
                    return {'ok': False, 'error': str(_('User not found in directory.')), 'steps': steps}
                user_dn = results[0][0]
                if user_dn is None:
                    return {'ok': False, 'error': str(_('User search returned no DN.')), 'steps': steps}
                add_step(str(_('Resolved DN')), user_dn)

                conn2, tls_meta2 = _ldap_build_connection(uri, ldap_cfg)
                add_step(str(_('Second connection')), str(tls_meta2['transport']))
                if tls_meta2.get('start_tls_skipped_ldaps'):
                    add_step(
                        str(_('STARTTLS')),
                        str(_('Skipped (ldaps://).')),
                        'skip',
                    )
                conn2.simple_bind_s(user_dn, test_password)
                conn2.unbind_s()
                add_step(str(_('User bind')), str(_('Password bind succeeded for the resolved DN.')))
                detail = str(_('Service bind, search, and user password bind succeeded.'))
            else:
                add_step(str(_('User bind test')), str(_('Skipped (no test username/password).')), 'skip')
                conn.unbind_s()

            elapsed_ms = int((time.monotonic() - t0) * 1000)
            add_step(str(_('Timing')), str(_('Total elapsed: %(ms)s ms') % {'ms': elapsed_ms}))
            return {
                'ok': True,
                'detail': detail,
                'steps': steps,
                'elapsed_ms': elapsed_ms,
            }
        except Exception as exc:
            err = _format_ldap_exc(exc)
            steps.append({'label': str(_('Error')), 'message': err, 'status': 'error'})
            return {'ok': False, 'error': err, 'steps': steps}


def test_oidc_discovery(oidc_endpoint: str, *, timeout: int = 10) -> dict[str, Any]:
    """
    Fetch OpenID Provider metadata from {issuer}/.well-known/openid-configuration .
    """
    steps: list[dict[str, Any]] = []

    def add_step(label: str, message: str, status: str = 'ok'):
        steps.append({'label': label, 'message': message, 'status': status})

    base = (oidc_endpoint or '').strip().rstrip('/')
    if not base:
        return {'ok': False, 'error': str(_('OIDC endpoint is empty.')), 'steps': []}

    url = f'{base}/.well-known/openid-configuration'
    add_step(str(_('Request')), url)
    req = urllib.request.Request(url, headers={'Accept': 'application/json'})
    ctx = ssl.create_default_context()
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            status = getattr(resp, 'status', None) or resp.getcode()
            body = resp.read().decode()
            doc = json.loads(body)
        add_step(str(_('HTTP')), str(_('Status %(code)s, body length %(len)s bytes') % {'code': status, 'len': len(body)}))
    except urllib.error.HTTPError as exc:
        add_step(str(_('HTTP')), f'{exc.code} {exc.reason}', 'error')
        return {'ok': False, 'error': f'HTTP {exc.code}: {exc.reason}', 'steps': steps}
    except urllib.error.URLError as exc:
        err = str(exc.reason or exc)
        add_step(str(_('Network')), err, 'error')
        return {'ok': False, 'error': err, 'steps': steps}
    except json.JSONDecodeError as exc:
        msg = str(_('Invalid JSON in discovery document: %(e)s') % {'e': exc})
        add_step(str(_('JSON')), msg, 'error')
        return {'ok': False, 'error': msg, 'steps': steps}

    issuer = doc.get('issuer')
    if not issuer:
        return {'ok': False, 'error': str(_('Discovery document missing issuer.')), 'steps': steps}

    add_step(str(_('Issuer')), issuer)
    for key, label in (
        ('authorization_endpoint', str(_('Authorization endpoint'))),
        ('token_endpoint', str(_('Token endpoint'))),
        ('userinfo_endpoint', str(_('Userinfo endpoint'))),
        ('jwks_uri', str(_('JWKS URI'))),
    ):
        val = doc.get(key) or ''
        if val:
            add_step(label, val)

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    add_step(str(_('Timing')), str(_('Total elapsed: %(ms)s ms') % {'ms': elapsed_ms}))

    return {
        'ok': True,
        'detail': str(_('Discovery OK.')),
        'issuer': issuer,
        'authorization_endpoint': doc.get('authorization_endpoint', ''),
        'token_endpoint': doc.get('token_endpoint', ''),
        'userinfo_endpoint': doc.get('userinfo_endpoint', ''),
        'jwks_uri': doc.get('jwks_uri', ''),
        'steps': steps,
        'elapsed_ms': elapsed_ms,
    }
