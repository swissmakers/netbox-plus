"""
Dedicated LDAP / OIDC admin forms (NetBox Plus).
"""
from __future__ import annotations

import json
from typing import Any

from django import forms
from django.utils.translation import gettext_lazy as _

from netbox.config.enterprise_auth import ENTERPRISE_AUTH_DEFAULT
from utilities.forms.rendering import FieldSet


def _empty_json(val) -> dict:
    if val in (None, '', {}):
        return {}
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        return json.loads(val)
    return {}


class EnterpriseLDAPForm(forms.Form):
    fieldsets = (
        FieldSet(
            'enabled', 'server_uri', 'start_tls', 'ignore_cert_errors',
            name=_('Connection'),
        ),
        FieldSet(
            'bind_dn', 'bind_password', 'ca_cert_dir', 'ca_cert_file',
            name=_('Bind & TLS'),
        ),
        FieldSet(
            'user_search_base', 'user_search_scope', 'user_search_filter',
            'user_dn_template', 'user_query_field',
            name=_('User search'),
        ),
        FieldSet(
            'user_attr_map', 'connection_options',
            name=_('Advanced (JSON)'),
        ),
        FieldSet(
            'group_search_base', 'group_search_scope', 'group_search_filter', 'group_type',
            'require_group', 'mirror_groups', 'find_group_perms', 'user_flags_by_group',
            name=_('Groups'),
        ),
        FieldSet(
            'cache_timeout', 'always_update_user',
            name=_('Caching & sync'),
        ),
    )

    enabled = forms.BooleanField(label=_('Enable LDAP authentication'), required=False)
    server_uri = forms.CharField(label=_('Server URI'), required=False, max_length=500)
    bind_dn = forms.CharField(label=_('Bind DN'), required=False, max_length=500)
    bind_password = forms.CharField(
        label=_('Bind password'),
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text=_('Leave blank to keep the current password.'),
    )
    start_tls = forms.BooleanField(label=_('Use STARTTLS'), required=False)
    ignore_cert_errors = forms.BooleanField(label=_('Ignore TLS certificate errors'), required=False)
    ca_cert_dir = forms.CharField(label=_('CA certificate directory'), required=False, max_length=500)
    ca_cert_file = forms.CharField(label=_('CA certificate file'), required=False, max_length=500)
    connection_options = forms.CharField(
        label=_('LDAP connection options (JSON object)'),
        required=False,
        widget=forms.Textarea(attrs={'class': 'font-monospace', 'rows': 4}),
        help_text=_('Example: {"REFERRALS": 0}'),
    )
    user_search_base = forms.CharField(label=_('User search base'), required=False, max_length=500)
    user_search_scope = forms.ChoiceField(
        label=_('User search scope'),
        choices=[('BASE', 'BASE'), ('ONELEVEL', 'ONELEVEL'), ('SUBTREE', 'SUBTREE')],
        initial='SUBTREE',
    )
    user_search_filter = forms.CharField(
        label=_('User search filter'),
        required=False,
        max_length=500,
        help_text=_('Use %(user)s for the login name.'),
    )
    user_dn_template = forms.CharField(
        label=_('User DN template'),
        required=False,
        max_length=500,
        help_text=_('Optional; leave empty when using search-based bind.'),
    )
    user_attr_map = forms.CharField(
        label=_('User attribute map (JSON object)'),
        required=False,
        widget=forms.Textarea(attrs={'class': 'font-monospace', 'rows': 5}),
    )
    user_query_field = forms.CharField(label=_('User query field'), required=False, max_length=200)
    group_search_base = forms.CharField(label=_('Group search base'), required=False, max_length=500)
    group_search_scope = forms.ChoiceField(
        label=_('Group search scope'),
        choices=[('BASE', 'BASE'), ('ONELEVEL', 'ONELEVEL'), ('SUBTREE', 'SUBTREE')],
        initial='SUBTREE',
    )
    group_search_filter = forms.CharField(
        label=_('Group search filter'),
        required=False,
        max_length=500,
        help_text=_(
            'Static LDAP filter only (no user placeholders). django-auth-ldap adds '
            'member clauses when mirroring groups.'
        ),
    )
    group_type = forms.ChoiceField(
        label=_('Group type'),
        choices=[
            ('group_of_names', _('Group of names')),
            ('nested_group_of_names', _('Nested group of names')),
            ('posix_group', _('POSIX group')),
        ],
        initial='group_of_names',
    )
    require_group = forms.CharField(label=_('Require group (DN)'), required=False, max_length=500)
    mirror_groups = forms.BooleanField(label=_('Mirror groups'), required=False)
    find_group_perms = forms.BooleanField(label=_('Find group permissions'), required=False)
    user_flags_by_group = forms.CharField(
        label=_('User flags by group (JSON object)'),
        required=False,
        widget=forms.Textarea(attrs={'class': 'font-monospace', 'rows': 4}),
    )
    cache_timeout = forms.IntegerField(label=_('Cache timeout (seconds)'), required=False, min_value=0)
    always_update_user = forms.BooleanField(label=_('Always update user on login'), required=False)

    def __init__(self, *args, **kwargs):
        env_overrides = kwargs.pop('env_overrides', {}) or {}
        super().__init__(*args, **kwargs)
        self._apply_env_overrides(env_overrides)

    def _apply_env_overrides(self, env_overrides: dict[str, bool]) -> None:
        if env_overrides.get('bind_password') and 'bind_password' in self.fields:
            field = self.fields['bind_password']
            field.disabled = True
            note = _('Overridden by environment variable NETBOX_LDAP_BIND_PASSWORD.')
            field.help_text = f'{field.help_text}<br>{note}' if field.help_text else note

    @staticmethod
    def ldap_to_initial(ldap: dict[str, Any]) -> dict[str, Any]:
        d = {**ENTERPRISE_AUTH_DEFAULT['ldap'], **(ldap or {})}
        initial = {k: d.get(k) for k in ENTERPRISE_AUTH_DEFAULT['ldap']}
        initial['connection_options'] = json.dumps(d.get('connection_options') or {}, indent=2)
        initial['user_attr_map'] = json.dumps(d.get('user_attr_map') or {}, indent=2)
        initial['user_flags_by_group'] = json.dumps(d.get('user_flags_by_group') or {}, indent=2)
        udt = d.get('user_dn_template')
        initial['user_dn_template'] = udt if udt else ''
        initial['bind_password'] = ''  # never pre-fill
        ct = d.get('cache_timeout')
        initial['cache_timeout'] = '' if ct is None else ct
        return initial

    def clean_connection_options(self):
        raw = self.cleaned_data.get('connection_options')
        if not (raw or '').strip():
            return {}
        try:
            val = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(_('Invalid JSON: {e}').format(e=exc)) from exc
        if not isinstance(val, dict):
            raise forms.ValidationError(_('Must be a JSON object.'))
        return val

    def clean_user_attr_map(self):
        raw = self.cleaned_data.get('user_attr_map')
        if not (raw or '').strip():
            return {}
        try:
            val = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(_('Invalid JSON: {e}').format(e=exc)) from exc
        if not isinstance(val, dict):
            raise forms.ValidationError(_('Must be a JSON object.'))
        return val

    def clean_user_flags_by_group(self):
        raw = self.cleaned_data.get('user_flags_by_group')
        if not (raw or '').strip():
            return {}
        try:
            val = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(_('Invalid JSON: {e}').format(e=exc)) from exc
        if not isinstance(val, dict):
            raise forms.ValidationError(_('Must be a JSON object.'))
        return val

    def clean_user_dn_template(self):
        v = self.cleaned_data.get('user_dn_template')
        return v.strip() or None if isinstance(v, str) else v

    def clean_cache_timeout(self):
        v = self.cleaned_data.get('cache_timeout')
        if v in ('', None):
            return None
        return v

    def to_ldap_dict(self) -> dict[str, Any]:
        """Return ldap branch dict (defaults merged) from cleaned_data."""
        data = {}
        for key in ENTERPRISE_AUTH_DEFAULT['ldap']:
            if key not in self.cleaned_data:
                continue
            data[key] = self.cleaned_data[key]
        udt = data.get('user_dn_template')
        if udt == '':
            data['user_dn_template'] = None
        return data


class EnterpriseOIDCForm(forms.Form):
    fieldsets = (
        FieldSet(
            'enabled', 'oidc_endpoint', 'key', 'secret', 'username_key',
            name=_('OpenID Connect'),
        ),
    )

    enabled = forms.BooleanField(label=_('Enable OpenID Connect'), required=False)
    oidc_endpoint = forms.CharField(
        label=_('OIDC issuer base URL'),
        required=False,
        max_length=500,
        help_text=_('Without /.well-known/openid-configuration'),
    )
    key = forms.CharField(label=_('Client ID'), required=False, max_length=500)
    secret = forms.CharField(
        label=_('Client secret'),
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text=_('Leave blank to keep the current secret.'),
    )
    username_key = forms.CharField(
        label=_('Username claim'),
        required=False,
        max_length=200,
        initial='preferred_username',
    )

    def __init__(self, *args, **kwargs):
        env_overrides = kwargs.pop('env_overrides', {}) or {}
        super().__init__(*args, **kwargs)
        self._apply_env_overrides(env_overrides)

    def _apply_env_overrides(self, env_overrides: dict[str, bool]) -> None:
        mapping = (
            ('key', 'NETBOX_OIDC_KEY'),
            ('secret', 'NETBOX_OIDC_SECRET'),
        )
        for field_name, env_name in mapping:
            if env_overrides.get(field_name) and field_name in self.fields:
                field = self.fields[field_name]
                field.disabled = True
                note = _('Overridden by environment variable {name}.').format(name=env_name)
                field.help_text = f'{field.help_text}<br>{note}' if field.help_text else note

    @staticmethod
    def oidc_to_initial(oidc: dict[str, Any]) -> dict[str, Any]:
        d = {**ENTERPRISE_AUTH_DEFAULT['oidc'], **(oidc or {})}
        d['secret'] = ''
        return d

    def to_oidc_dict(self) -> dict[str, Any]:
        data = {}
        for key in ENTERPRISE_AUTH_DEFAULT['oidc']:
            if key in self.cleaned_data:
                data[key] = self.cleaned_data[key]
        return data


class EnterpriseLDAPTestForm(forms.Form):
    """Optional credentials for LDAP bind test (in addition to posted LDAP fields)."""

    test_username = forms.CharField(label=_('Test username'), required=False, max_length=200)
    test_password = forms.CharField(
        label=_('Test password'),
        required=False,
        widget=forms.PasswordInput(render_value=False),
    )


class EnterpriseOIDCTestForm(forms.Form):
    """Minimal OIDC discovery test."""

    oidc_endpoint = forms.CharField(label=_('OIDC issuer base URL'), required=True, max_length=500)
