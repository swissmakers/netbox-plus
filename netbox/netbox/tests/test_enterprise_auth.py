from unittest import mock

from django import forms
from django.test import SimpleTestCase, override_settings

from netbox.config.enterprise_auth import (
    ENTERPRISE_AUTH_DEFAULT,
    enterprise_auth_preset,
    get_enterprise_auth,
    validate_enterprise_auth,
)
from netbox.middleware import EnterpriseAuthMiddleware
from netbox.authentication.enterprise_ldap import build_ldap_settings_from_dict


class BuildLdapSettingsTests(SimpleTestCase):
    """LDAPSettings shape for django-auth-ldap (login path)."""

    _minimal_ldap = {
        'server_uri': 'ldap://ldap.example.com',
        'user_search_base': 'dc=example,dc=com',
        'user_search_filter': '(uid=%(user)s)',
    }

    def test_start_tls_true_for_ldap_uri(self):
        ls = build_ldap_settings_from_dict({**self._minimal_ldap, 'start_tls': True})
        self.assertTrue(ls.START_TLS)

    def test_start_tls_false_when_ldaps_even_if_flag_true(self):
        ls = build_ldap_settings_from_dict({
            **self._minimal_ldap,
            'server_uri': 'ldaps://ldap.example.com:636',
            'start_tls': True,
        })
        self.assertFalse(ls.START_TLS)

    def test_group_search_filter_with_percent_user_normalized(self):
        """Legacy FreeIPA-style (member=%(user)s) must not reach django-auth-ldap execute()."""
        ls = build_ldap_settings_from_dict({
            **self._minimal_ldap,
            'group_type': 'posix_group',
            'group_search_base': 'cn=groups,cn=accounts,dc=example,dc=com',
            'group_search_filter': '(member=%(user)s)',
        })
        self.assertEqual(ls.GROUP_SEARCH.filterstr, '(objectClass=posixGroup)')


class EnterpriseAuthConfigTests(SimpleTestCase):

    def test_get_enterprise_auth_merges_defaults(self):
        merged = get_enterprise_auth({'ldap': {'enabled': True, 'server_uri': 'ldap://x'}})
        self.assertTrue(merged['ldap']['enabled'])
        self.assertEqual(merged['ldap']['server_uri'], 'ldap://x')
        self.assertIn('oidc', merged)

    def test_validate_empty_ok(self):
        out = validate_enterprise_auth({})
        self.assertEqual(out['ldap']['enabled'], False)

    def test_validate_ldap_enabled_requires_fields(self):
        with self.assertRaises(forms.ValidationError):
            validate_enterprise_auth({'ldap': {'enabled': True, 'server_uri': ''}})

    def test_validate_oidc_requires_secret(self):
        with self.assertRaises(forms.ValidationError):
            validate_enterprise_auth({
                'oidc': {
                    'enabled': True,
                    'oidc_endpoint': 'https://idp.example.com/realms/foo',
                    'key': 'client',
                    'secret': '',
                }
            })

    def test_preset_active_directory_shape(self):
        cfg = enterprise_auth_preset('active_directory')
        self.assertIn('sAMAccountName', cfg['ldap']['user_search_filter'])
        self.assertEqual(cfg['ldap']['group_type'], 'nested_group_of_names')

    def test_preset_freeipa_shape(self):
        cfg = enterprise_auth_preset('freeipa')
        self.assertIn('uid=', cfg['ldap']['user_search_filter'])
        self.assertEqual(cfg['ldap']['group_type'], 'posix_group')
        self.assertEqual(cfg['ldap']['group_search_filter'], '(objectClass=posixGroup)')

    def test_validate_rejects_group_filter_with_user_placeholder(self):
        with self.assertRaises(forms.ValidationError):
            validate_enterprise_auth({
                'ldap': {
                    **ENTERPRISE_AUTH_DEFAULT['ldap'],
                    'enabled': True,
                    'server_uri': 'ldap://ldap.example.com',
                    'user_search_base': 'dc=example,dc=com',
                    'user_search_filter': '(uid=%(user)s)',
                    'group_search_base': 'cn=groups,dc=example,dc=com',
                    'group_search_filter': '(member=%(user)s)',
                },
            })


class EnterpriseAuthMiddlewareTests(SimpleTestCase):

    @override_settings(
        NETBOX_AUTHENTICATION_BACKENDS_BASE=(
            'django.contrib.auth.backends.ModelBackend',
            'netbox.authentication.ObjectPermissionBackend',
        ),
        AUTHENTICATION_BACKENDS=(
            'django.contrib.auth.backends.ModelBackend',
            'netbox.authentication.ObjectPermissionBackend',
        ),
    )
    def test_middleware_prepends_ldap_then_oidc(self):
        from django.conf import settings as dj_settings

        class _Cfg:
            ENTERPRISE_AUTH = {
                'ldap': {
                    **ENTERPRISE_AUTH_DEFAULT['ldap'],
                    'enabled': True,
                    'server_uri': 'ldap://ldap.example.com',
                    'user_search_base': 'dc=example,dc=com',
                    'user_search_filter': '(uid=%(user)s)',
                },
                'oidc': {
                    **ENTERPRISE_AUTH_DEFAULT['oidc'],
                    'enabled': True,
                    'oidc_endpoint': 'https://idp.example.com/realms/foo',
                    'key': 'k',
                    'secret': 's',
                },
            }

        mw = EnterpriseAuthMiddleware(lambda r: r)
        with mock.patch('netbox.middleware.get_config', return_value=_Cfg()):
            mw._apply_enterprise_auth()
        backends = dj_settings.AUTHENTICATION_BACKENDS
        self.assertEqual(backends[0], 'netbox.authentication.LDAPBackend')
        self.assertEqual(
            backends[1],
            'social_core.backends.open_id_connect.OpenIdConnectAuth',
        )
        self.assertEqual(
            backends[-1],
            'netbox.authentication.ObjectPermissionBackend',
        )
        self.assertEqual(dj_settings.SOCIAL_AUTH_OIDC_KEY, 'k')
