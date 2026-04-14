"""
Build django-auth-ldap LDAPSettings from ENTERPRISE_AUTH['ldap'] dict (NetBox Plus).
"""
from __future__ import annotations

import logging
from typing import Any

from netbox.config.enterprise_auth import ldap_bind_password_resolved

logger = logging.getLogger('netbox.auth.enterprise_ldap')

LDAP_OPTION_NAMES = {
    'REFERRALS': 'OPT_REFERRALS',
    'NETWORK_TIMEOUT': 'OPT_NETWORK_TIMEOUT',
    'TIMEOUT': 'OPT_TIMEOUT',
}

SCOPE_NAMES = {
    'BASE': 'SCOPE_BASE',
    'ONELEVEL': 'SCOPE_ONELEVEL',
    'LEVEL': 'SCOPE_ONELEVEL',
    'SUBTREE': 'SCOPE_SUBTREE',
}


def _ldap_scope(name: str):
    import ldap

    attr = SCOPE_NAMES.get((name or 'SUBTREE').upper(), 'SCOPE_SUBTREE')
    return getattr(ldap, attr)


def _connection_options(raw: dict) -> dict:
    import ldap

    out = {}
    for key, value in (raw or {}).items():
        opt_name = LDAP_OPTION_NAMES.get(str(key).upper(), f'OPT_{key}'.upper())
        if not hasattr(ldap, opt_name):
            logger.warning('Ignoring unknown LDAP connection option key: %s', key)
            continue
        out[getattr(ldap, opt_name)] = value
    return out


def _group_type(name: str):
    from django_auth_ldap.config import GroupOfNamesType, NestedGroupOfNamesType, PosixGroupType

    mapping = {
        'group_of_names': GroupOfNamesType(),
        'nested_group_of_names': NestedGroupOfNamesType(),
        'posix_group': PosixGroupType(),
    }
    return mapping.get(name, GroupOfNamesType())


def _normalized_group_search_filter(ldap_cfg: dict[str, Any]) -> str:
    """
    django-auth-ldap calls LDAPSearch.execute(connection) with no filterargs for group
    membership queries; the filter string must therefore satisfy ``filter % ()``.
    Placeholders such as %(user)s (often copied from the user search filter) raise
    TypeError at login. Normalize legacy/bad values to a broad static filter.
    """
    raw = (ldap_cfg.get('group_search_filter') or '').strip()
    if not raw:
        return raw
    try:
        raw % ()
        return raw
    except (TypeError, ValueError):
        group_type = ldap_cfg.get('group_type') or 'group_of_names'
        if group_type == 'posix_group':
            fallback = '(objectClass=posixGroup)'
        else:
            fallback = '(objectClass=group)'
        logger.warning(
            'LDAP group_search_filter is not compatible with django-auth-ldap '
            '(contains %% formatting tokens). Using fallback %r for group_type=%s.',
            fallback,
            group_type,
        )
        return fallback


def build_ldap_settings_from_dict(ldap_cfg: dict[str, Any]):
    """
    Construct LDAPSettings from merged ENTERPRISE_AUTH['ldap'] configuration.
    """
    from django_auth_ldap.backend import LDAPSettings
    from django_auth_ldap.config import LDAPSearch

    user_scope = _ldap_scope(ldap_cfg.get('user_search_scope') or 'SUBTREE')
    group_scope = _ldap_scope(ldap_cfg.get('group_search_scope') or 'SUBTREE')

    user_search = LDAPSearch(
        ldap_cfg['user_search_base'].strip(),
        user_scope,
        ldap_cfg['user_search_filter'].strip(),
    )

    group_search = None
    group_filter = _normalized_group_search_filter(ldap_cfg)
    if (ldap_cfg.get('group_search_base') or '').strip() and group_filter:
        group_search = LDAPSearch(
            ldap_cfg['group_search_base'].strip(),
            group_scope,
            group_filter,
        )

    bind_password = ldap_bind_password_resolved(ldap_cfg)

    udt = ldap_cfg.get('user_dn_template')
    uqf = (ldap_cfg.get('user_query_field') or '').strip()

    server_uri = ldap_cfg['server_uri'].strip()
    # django-auth-ldap always calls start_tls_s() when START_TLS is True, even for ldaps:// (already TLS).
    # That breaks login while the admin "Test LDAP" path skips STARTTLS for ldaps (see core/auth_testing.py).
    want_start_tls = bool(ldap_cfg.get('start_tls'))
    ldaps = server_uri.lower().startswith('ldaps://')
    effective_start_tls = want_start_tls and not ldaps
    if want_start_tls and ldaps:
        logger.info(
            'LDAP server_uri is ldaps://; START_TLS disabled for django-auth-ldap (TLS is already in use).'
        )

    short: dict[str, Any] = {
        'SERVER_URI': server_uri,
        'BIND_DN': (ldap_cfg.get('bind_dn') or '').strip(),
        'BIND_PASSWORD': bind_password,
        'USER_SEARCH': user_search,
        'USER_DN_TEMPLATE': udt if udt else None,
        'USER_ATTR_MAP': dict(ldap_cfg.get('user_attr_map') or {}),
        'USER_QUERY_FIELD': uqf or None,
        'GROUP_TYPE': _group_type(ldap_cfg.get('group_type') or 'group_of_names'),
        'REQUIRE_GROUP': (ldap_cfg.get('require_group') or '').strip() or None,
        'MIRROR_GROUPS': bool(ldap_cfg.get('mirror_groups')),
        'FIND_GROUP_PERMS': bool(ldap_cfg.get('find_group_perms')),
        'USER_FLAGS_BY_GROUP': dict(ldap_cfg.get('user_flags_by_group') or {}),
        'ALWAYS_UPDATE_USER': bool(ldap_cfg.get('always_update_user', True)),
        'START_TLS': effective_start_tls,
    }
    if group_search is not None:
        short['GROUP_SEARCH'] = group_search

    if ldap_cfg.get('cache_timeout') is not None:
        short['CACHE_TIMEOUT'] = ldap_cfg['cache_timeout']

    opts = _connection_options(ldap_cfg.get('connection_options'))
    if opts:
        short['CONNECTION_OPTIONS'] = opts

    try:
        ls = LDAPSettings('AUTH_LDAP_', short)
    except TypeError:
        ls = LDAPSettings()
        for key, value in short.items():
            setattr(ls, key, value)

    ls._netbox_ignore_cert_errors = bool(ldap_cfg.get('ignore_cert_errors'))
    ls._netbox_ca_cert_dir = (ldap_cfg.get('ca_cert_dir') or '').strip() or None
    ls._netbox_ca_cert_file = (ldap_cfg.get('ca_cert_file') or '').strip() or None
    ls._netbox_source = 'enterprise_auth'

    return ls


def ldap_file_config_available() -> bool:
    try:
        import importlib.util

        return importlib.util.find_spec('netbox.ldap_config') is not None
    except Exception:
        return False
