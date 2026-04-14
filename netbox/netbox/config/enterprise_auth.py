"""
Enterprise authentication (LDAP / OIDC) helpers for NetBox Plus dynamic configuration.

Settings are edited in Admin -> Authentication -> LDAP / OIDC and persisted in
ConfigRevision under ENTERPRISE_AUTH. Optional environment overrides (never
stored in the database):

- NETBOX_LDAP_BIND_PASSWORD
- NETBOX_OIDC_SECRET
"""
from __future__ import annotations

import copy
import os
import re
from typing import Any

import jsonschema
from django import forms
from django.utils.translation import gettext_lazy as _

__all__ = (
    'ENTERPRISE_AUTH_DEFAULT',
    'ENTERPRISE_AUTH_SCHEMA',
    'get_enterprise_auth',
    'validate_enterprise_auth',
    'ldap_preset_active_directory',
    'ldap_preset_freeipa',
    'OIDC_BACKEND_PATH',
    'LDAP_BACKEND_PATH',
    'MODEL_BACKEND_PATH',
)

OIDC_BACKEND_PATH = 'social_core.backends.open_id_connect.OpenIdConnectAuth'
LDAP_BACKEND_PATH = 'netbox.authentication.LDAPBackend'
MODEL_BACKEND_PATH = 'django.contrib.auth.backends.ModelBackend'

ENTERPRISE_AUTH_DEFAULT: dict[str, Any] = {
    'ldap': {
        'enabled': False,
        'server_uri': '',
        'bind_dn': '',
        'bind_password': '',
        'start_tls': False,
        'ignore_cert_errors': False,
        'ca_cert_dir': '',
        'ca_cert_file': '',
        'connection_options': {},
        'user_search_base': '',
        'user_search_scope': 'SUBTREE',
        'user_search_filter': '',
        'user_dn_template': None,
        'user_attr_map': {},
        'user_query_field': '',
        'group_search_base': '',
        'group_search_scope': 'SUBTREE',
        'group_search_filter': '',
        'group_type': 'group_of_names',
        'require_group': '',
        'mirror_groups': False,
        'find_group_perms': False,
        'user_flags_by_group': {},
        'cache_timeout': None,
        'always_update_user': True,
    },
    'oidc': {
        'enabled': False,
        'oidc_endpoint': '',
        'key': '',
        'secret': '',
        'username_key': 'preferred_username',
    },
}

ENTERPRISE_AUTH_SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    'properties': {
        'ldap': {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'enabled': {'type': 'boolean'},
                'server_uri': {'type': 'string'},
                'bind_dn': {'type': 'string'},
                'bind_password': {'type': 'string'},
                'start_tls': {'type': 'boolean'},
                'ignore_cert_errors': {'type': 'boolean'},
                'ca_cert_dir': {'type': 'string'},
                'ca_cert_file': {'type': 'string'},
                'connection_options': {'type': 'object'},
                'user_search_base': {'type': 'string'},
                'user_search_scope': {'type': 'string', 'enum': ['BASE', 'ONELEVEL', 'SUBTREE']},
                'user_search_filter': {'type': 'string'},
                'user_dn_template': {'type': ['string', 'null']},
                'user_attr_map': {'type': 'object'},
                'user_query_field': {'type': 'string'},
                'group_search_base': {'type': 'string'},
                'group_search_scope': {'type': 'string', 'enum': ['BASE', 'ONELEVEL', 'SUBTREE']},
                'group_search_filter': {'type': 'string'},
                'group_type': {
                    'type': 'string',
                    'enum': ['group_of_names', 'nested_group_of_names', 'posix_group'],
                },
                'require_group': {'type': 'string'},
                'mirror_groups': {'type': 'boolean'},
                'find_group_perms': {'type': 'boolean'},
                'user_flags_by_group': {'type': 'object'},
                'cache_timeout': {'type': ['integer', 'null']},
                'always_update_user': {'type': 'boolean'},
            },
        },
        'oidc': {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'enabled': {'type': 'boolean'},
                'oidc_endpoint': {'type': 'string'},
                'key': {'type': 'string'},
                'secret': {'type': 'string'},
                'username_key': {'type': 'string'},
            },
        },
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, val in (override or {}).items():
        if key in out and isinstance(out[key], dict) and isinstance(val, dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = copy.deepcopy(val)
    return out


def get_enterprise_auth(raw: dict | None) -> dict[str, Any]:
    """Return ENTERPRISE_AUTH dict merged with defaults."""
    return _deep_merge(ENTERPRISE_AUTH_DEFAULT, raw or {})


def validate_enterprise_auth(data: dict | None) -> dict[str, Any]:
    merged = get_enterprise_auth(data)
    try:
        jsonschema.validate(instance=merged, schema=ENTERPRISE_AUTH_SCHEMA)
    except jsonschema.ValidationError as exc:
        raise forms.ValidationError(
            _('Invalid enterprise authentication configuration: {msg}').format(msg=exc.message)
        )

    ldap = merged['ldap']
    if ldap['enabled']:
        if not ldap['server_uri'].strip():
            raise forms.ValidationError(_('LDAP is enabled but server URI is empty.'))
        if not ldap['user_search_base'].strip() or not ldap['user_search_filter'].strip():
            raise forms.ValidationError(
                _('LDAP is enabled: user search base and user search filter are required.')
            )
        uri = ldap['server_uri'].strip()
        if not re.match(r'^ldaps?://', uri, re.I):
            raise forms.ValidationError(_('LDAP server URI must start with ldap:// or ldaps://.'))

        gf = (ldap.get('group_search_filter') or '').strip()
        if gf:
            try:
                gf % ()
            except (TypeError, ValueError):
                raise forms.ValidationError(
                    _(
                        'LDAP group search filter cannot contain Python-style placeholders '
                        '(for example the user-search token). django-auth-ldap builds '
                        'member clauses itself; use a static filter such as '
                        '(objectClass=posixGroup) or (objectClass=group).'
                    )
                )

    oidc = merged['oidc']
    if oidc['enabled']:
        if not oidc['oidc_endpoint'].strip():
            raise forms.ValidationError(_('OpenID Connect is enabled but OIDC endpoint is empty.'))
        if not oidc['key'].strip() and not os.environ.get('NETBOX_OIDC_KEY'):
            raise forms.ValidationError(_('OpenID Connect is enabled: client key is required (or set NETBOX_OIDC_KEY).'))
        secret = (oidc.get('secret') or '').strip() or os.environ.get('NETBOX_OIDC_SECRET', '')
        if not secret:
            raise forms.ValidationError(
                _('OpenID Connect is enabled: client secret is required (or set NETBOX_OIDC_SECRET).')
            )

    return merged


def ldap_bind_password_resolved(ldap: dict) -> str:
    return os.environ.get('NETBOX_LDAP_BIND_PASSWORD', '') or (ldap.get('bind_password') or '')


def oidc_secret_resolved(oidc: dict) -> str:
    return os.environ.get('NETBOX_OIDC_SECRET', '') or (oidc.get('secret') or '')


def oidc_key_resolved(oidc: dict) -> str:
    return os.environ.get('NETBOX_OIDC_KEY', '') or (oidc.get('key') or '')


def ldap_preset_active_directory() -> dict[str, Any]:
    """
    Demo template for Microsoft Active Directory (placeholders only).
    Replace DC components, bind DN, and use NETBOX_LDAP_BIND_PASSWORD for the service account secret.
    """
    cfg = get_enterprise_auth({})
    cfg['ldap'].update({
        'enabled': False,
        'server_uri': 'ldaps://ad.example.com:3269',
        'bind_dn': 'CN=NETBOXSA,OU=Service Accounts,DC=example,DC=com',
        'bind_password': '',
        'start_tls': False,
        'ignore_cert_errors': False,
        'connection_options': {'REFERRALS': 0},
        'user_search_base': 'OU=Users,DC=example,DC=com',
        'user_search_scope': 'SUBTREE',
        'user_search_filter': '(sAMAccountName=%(user)s)',
        'user_dn_template': None,
        'user_attr_map': {
            'username': 'sAMAccountName',
            'first_name': 'givenName',
            'last_name': 'sn',
            'email': 'mail',
        },
        'user_query_field': 'username',
        'group_search_base': 'DC=example,DC=com',
        'group_search_scope': 'SUBTREE',
        'group_search_filter': '(objectClass=group)',
        'group_type': 'nested_group_of_names',
        'require_group': '',
        'mirror_groups': True,
        'find_group_perms': False,
    })
    return cfg


def ldap_preset_freeipa() -> dict[str, Any]:
    """
    Demo template for FreeIPA / 389 Directory Server (placeholders only).
    Adjust basedn (dc=example,dc=com) and bind account; set NETBOX_LDAP_BIND_PASSWORD.
    """
    cfg = get_enterprise_auth({})
    cfg['ldap'].update({
        'enabled': False,
        'server_uri': 'ldap://ipa.example.com',
        'bind_dn': 'uid=netbox-bind,cn=sysaccounts,cn=etc,dc=example,dc=com',
        'bind_password': '',
        'start_tls': True,
        'ignore_cert_errors': False,
        'connection_options': {},
        'user_search_base': 'cn=users,cn=accounts,dc=example,dc=com',
        'user_search_scope': 'SUBTREE',
        'user_search_filter': '(uid=%(user)s)',
        'user_dn_template': None,
        'user_attr_map': {
            'first_name': 'givenName',
            'last_name': 'sn',
            'email': 'mail',
        },
        'user_query_field': '',
        'group_search_base': 'cn=groups,cn=accounts,dc=example,dc=com',
        'group_search_scope': 'SUBTREE',
        # Must be static: django-auth-ldap ANDs member/memberUid terms itself; %(user)s breaks execute().
        'group_search_filter': '(objectClass=posixGroup)',
        'group_type': 'posix_group',
        'require_group': '',
        'mirror_groups': True,
        'find_group_perms': False,
    })
    return cfg


def enterprise_auth_preset(preset_id: str) -> dict[str, Any]:
    if preset_id == 'active_directory':
        return ldap_preset_active_directory()
    if preset_id == 'freeipa':
        return ldap_preset_freeipa()
    raise ValueError(f'Unknown enterprise auth preset: {preset_id}')
