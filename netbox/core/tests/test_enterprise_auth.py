from unittest import mock

from django import forms
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse

from core.models import ConfigRevision
from netbox.config.enterprise_auth import get_enterprise_auth
from utilities.testing import TestCase


def _ldap_form_post_data(initial):
    from core.forms.enterprise_auth import EnterpriseLDAPForm

    post = {}
    for name, field in EnterpriseLDAPForm.base_fields.items():
        val = initial.get(name, '')
        if isinstance(field, forms.BooleanField):
            if val:
                post[name] = 'on'
        elif val in (None, ''):
            post[name] = ''
        else:
            post[name] = val
    return post


class EnterpriseAuthUIViewTests(TestCase):
    user_permissions = ('core.add_configrevision',)

    def setUp(self):
        super().setUp()
        self.user.is_superuser = True
        self.user.save()

    def test_hub_requires_superuser(self):
        self.user.is_superuser = False
        self.user.save()
        self.assertHttpStatus(self.client.get(reverse('core:auth_hub')), 403)

    def test_hub_get_ok(self):
        self.assertHttpStatus(self.client.get(reverse('core:auth_hub')), 200)

    @override_settings(ENTERPRISE_AUTH={'ldap': {}, 'oidc': {}})
    def test_hub_static_config_blocked(self):
        r = self.client.get(reverse('core:auth_hub'))
        self.assertHttpStatus(r, 200)
        self.assertContains(r, 'ENTERPRISE_AUTH', status_code=200)

    def test_ldap_page_get_ok(self):
        self.assertHttpStatus(self.client.get(reverse('core:auth_ldap')), 200)

    def test_oidc_page_get_ok(self):
        self.assertHttpStatus(self.client.get(reverse('core:auth_oidc')), 200)

    @mock.patch('core.auth_views.test_ldap_configuration')
    def test_ldap_test_json(self, mock_ldap):
        mock_ldap.return_value = {'ok': True, 'detail': 'bind ok'}
        from core.forms.enterprise_auth import EnterpriseLDAPForm

        initial = EnterpriseLDAPForm.ldap_to_initial(get_enterprise_auth({})['ldap'])
        post = _ldap_form_post_data(initial)
        post['test_username'] = ''
        post['test_password'] = ''
        r = self.client.post(reverse('core:auth_ldap_test'), post)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['ok'], True)
        mock_ldap.assert_called_once()

    @mock.patch('core.auth_views.test_oidc_discovery')
    def test_oidc_test_json(self, mock_oidc):
        mock_oidc.return_value = {'ok': True, 'detail': 'd', 'issuer': 'https://idp'}
        r = self.client.post(
            reverse('core:auth_oidc_test'),
            {'oidc_endpoint': 'https://idp.example.com/realms/r'},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['ok'], True)

    def test_ldap_save_creates_revision(self):
        from core.forms.enterprise_auth import EnterpriseLDAPForm

        before = ConfigRevision.objects.count()
        initial = EnterpriseLDAPForm.ldap_to_initial(get_enterprise_auth({})['ldap'])
        post = _ldap_form_post_data(initial)
        post['enabled'] = ''
        r = self.client.post(reverse('core:auth_ldap'), post)
        self.assertHttpStatus(r, 302)
        self.assertEqual(ConfigRevision.objects.count(), before + 1)
        cache.delete('config')
        cache.delete('config_version')
