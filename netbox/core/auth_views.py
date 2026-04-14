"""
LDAP / OIDC dedicated admin UI (NetBox Plus).
"""
from __future__ import annotations

import json
import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from django.views.generic import FormView, View

from core.auth_services import (
    enterprise_ldap_file_active,
    save_enterprise_auth_revision,
)
from core.auth_testing import test_ldap_configuration, test_oidc_discovery
from core.forms.enterprise_auth import (
    EnterpriseLDAPForm,
    EnterpriseLDAPTestForm,
    EnterpriseOIDCForm,
    EnterpriseOIDCTestForm,
)
from netbox.config import get_config
from netbox.config.enterprise_auth import enterprise_auth_preset, get_enterprise_auth, validate_enterprise_auth


class EnterpriseAuthUIMixin(UserPassesTestMixin):

    def test_func(self):
        u = self.request.user
        # NetBox User has no is_staff; staff_only menu items use is_superuser (see navigation.py).
        return u.is_active and u.is_superuser and u.has_perm('core.add_configrevision')

    def handle_no_permission(self):
        return HttpResponseForbidden()


class EnterpriseAuthStaticBlockedMixin(EnterpriseAuthUIMixin):
    """Block UI when ENTERPRISE_AUTH is defined statically in configuration."""

    def dispatch(self, request, *args, **kwargs):
        if not self.test_func():
            return self.handle_no_permission()
        if hasattr(settings, 'ENTERPRISE_AUTH'):
            return render(request, 'core/auth_static_blocked.html', {
                'title': _('LDAP / OIDC'),
            })
        return super().dispatch(request, *args, **kwargs)


class EnterpriseAuthHubView(EnterpriseAuthStaticBlockedMixin, View):
    template_name = 'core/auth_hub.html'

    def get(self, request):
        ea = get_enterprise_auth(getattr(get_config(), 'ENTERPRISE_AUTH', None))
        return render(request, self.template_name, {
            'title': _('LDAP / OIDC'),
            'enterprise_auth': ea,
            'ldap_file_active': enterprise_ldap_file_active(),
        })


class EnterpriseLDAPEditView(EnterpriseAuthStaticBlockedMixin, FormView):
    form_class = EnterpriseLDAPForm
    template_name = 'core/auth_ldap.html'

    @staticmethod
    def _env_overrides():
        return {
            'bind_password': bool(os.environ.get('NETBOX_LDAP_BIND_PASSWORD')),
        }

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['env_overrides'] = self._env_overrides()
        return kwargs

    def get_initial(self):
        ldap = get_enterprise_auth(getattr(get_config(), 'ENTERPRISE_AUTH', None)).get('ldap') or {}
        preset = self.request.GET.get('preset')
        if preset in ('active_directory', 'freeipa'):
            try:
                ldap = enterprise_auth_preset(preset)['ldap']
                messages.info(self.request, _('Template values loaded into the form. Save to apply.'))
            except ValueError:
                messages.error(self.request, _('Unknown preset.'))
        return EnterpriseLDAPForm.ldap_to_initial(ldap)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = _('LDAP authentication')
        ctx['return_url'] = reverse('core:auth_hub')
        ctx['ldap_file_active'] = enterprise_ldap_file_active()
        ctx['env_overrides'] = self._env_overrides()
        ctx['test_form'] = EnterpriseLDAPTestForm()
        return ctx

    def form_valid(self, form):
        prior = get_enterprise_auth(getattr(get_config(), 'ENTERPRISE_AUTH', None))
        ldap_new = form.to_ldap_dict()
        if not (ldap_new.get('bind_password') or '').strip():
            ldap_new['bind_password'] = prior['ldap'].get('bind_password', '')
        ea = {**prior, 'ldap': {**prior['ldap'], **ldap_new}}
        validate_enterprise_auth(ea)
        save_enterprise_auth_revision(ea, comment=_('LDAP settings (UI)'))
        messages.success(self.request, _('LDAP settings saved and activated.'))
        return redirect('core:auth_hub')


class EnterpriseOIDCEditView(EnterpriseAuthStaticBlockedMixin, FormView):
    form_class = EnterpriseOIDCForm
    template_name = 'core/auth_oidc.html'

    @staticmethod
    def _env_overrides():
        return {
            'key': bool(os.environ.get('NETBOX_OIDC_KEY')),
            'secret': bool(os.environ.get('NETBOX_OIDC_SECRET')),
        }

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['env_overrides'] = self._env_overrides()
        return kwargs

    def get_initial(self):
        oidc = get_enterprise_auth(getattr(get_config(), 'ENTERPRISE_AUTH', None)).get('oidc') or {}
        return EnterpriseOIDCForm.oidc_to_initial(oidc)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = _('OpenID Connect')
        ctx['return_url'] = reverse('core:auth_hub')
        ctx['env_overrides'] = self._env_overrides()
        return ctx

    def form_valid(self, form):
        prior = get_enterprise_auth(getattr(get_config(), 'ENTERPRISE_AUTH', None))
        oidc_new = form.to_oidc_dict()
        if not (oidc_new.get('secret') or '').strip():
            oidc_new['secret'] = prior['oidc'].get('secret', '')
        ea = {**prior, 'oidc': {**prior['oidc'], **oidc_new}}
        validate_enterprise_auth(ea)
        save_enterprise_auth_revision(ea, comment=_('OIDC settings (UI)'))
        messages.success(self.request, _('OpenID Connect settings saved and activated.'))
        return redirect('core:auth_hub')


@method_decorator(require_POST, name='dispatch')
class EnterpriseLDAPTestView(EnterpriseAuthUIMixin, View):

    def post(self, request):
        if hasattr(settings, 'ENTERPRISE_AUTH'):
            return JsonResponse({'ok': False, 'error': str(_('ENTERPRISE_AUTH is defined statically.'))}, status=400)
        ldap_form = EnterpriseLDAPForm(request.POST)
        test_form = EnterpriseLDAPTestForm(request.POST)
        if not ldap_form.is_valid() or not test_form.is_valid():
            err = ldap_form.errors.as_json() if ldap_form.errors else test_form.errors.as_json()
            return JsonResponse({'ok': False, 'error': str(_('Invalid form data.')), 'fields': err}, status=400)
        ldap_cfg = ldap_form.to_ldap_dict()
        prior = get_enterprise_auth(getattr(get_config(), 'ENTERPRISE_AUTH', None))
        if not (ldap_cfg.get('bind_password') or '').strip():
            ldap_cfg['bind_password'] = prior['ldap'].get('bind_password', '')
        result = test_ldap_configuration(
            ldap_cfg,
            test_username=test_form.cleaned_data.get('test_username') or '',
            test_password=test_form.cleaned_data.get('test_password') or '',
        )
        status = 200 if result.get('ok') else 400
        return JsonResponse(result, status=status)


@method_decorator(require_POST, name='dispatch')
class EnterpriseOIDCTestView(EnterpriseAuthUIMixin, View):

    def post(self, request):
        if hasattr(settings, 'ENTERPRISE_AUTH'):
            return JsonResponse({'ok': False, 'error': str(_('ENTERPRISE_AUTH is defined statically.'))}, status=400)
        # Accept JSON body {oidc_endpoint: ...} or form POST from OIDC page
        if request.content_type and 'application/json' in request.content_type:
            try:
                body = json.loads(request.body.decode() or '{}')
            except json.JSONDecodeError:
                return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)
            form = EnterpriseOIDCTestForm(body)
        else:
            form = EnterpriseOIDCTestForm(request.POST)
        if not form.is_valid():
            return JsonResponse(
                {'ok': False, 'error': str(_('Invalid OIDC endpoint.')), 'fields': str(form.errors)},
                status=400,
            )
        result = test_oidc_discovery(form.cleaned_data['oidc_endpoint'])
        status = 200 if result.get('ok') else 400
        return JsonResponse(result, status=status)
