"""
Persist ENTERPRISE_AUTH via ConfigRevision (full config merge) for LDAP/OIDC admin UI.
"""
from __future__ import annotations

import importlib
from copy import deepcopy
from typing import Any

from django.core.cache import cache
from django.utils.translation import gettext_lazy as _

from netbox.config.enterprise_auth import validate_enterprise_auth
from netbox.config.parameters import PARAMS


def build_full_config_revision_data() -> dict[str, Any]:
    """
    Build a complete config dict for a new ConfigRevision, merging Redis cache with PARAM defaults.
    """
    cached = cache.get('config') or {}
    data: dict[str, Any] = {}
    for param in PARAMS:
        if param.name in cached:
            data[param.name] = deepcopy(cached[param.name])
        else:
            data[param.name] = deepcopy(param.default)
    return data


def save_enterprise_auth_revision(
    enterprise_auth: dict[str, Any],
    *,
    comment: str | None = None,
):
    """
    Validate merged ENTERPRISE_AUTH, write a new ConfigRevision with full merged config, activate via post_save.
    """
    from core.models import ConfigRevision
    from netbox.config import clear_config

    merged_ea = validate_enterprise_auth(enterprise_auth)
    data = build_full_config_revision_data()
    data['ENTERPRISE_AUTH'] = merged_ea
    msg = str(comment) if comment else str(_('LDAP / OIDC settings (UI)'))
    rev = ConfigRevision.objects.create(data=data, comment=msg)
    clear_config()
    return rev


def enterprise_ldap_file_active() -> bool:
    """True when netbox/ldap_config.py defines AUTH_LDAP_SERVER_URI (takes precedence over UI)."""
    # ldap_config is optional; do not use ``from netbox import ldap_config`` (not exported in netbox/__init__.py).
    try:
        lc = importlib.import_module('netbox.ldap_config')
    except (ImportError, ModuleNotFoundError, OSError):
        return False
    return bool(getattr(lc, 'AUTH_LDAP_SERVER_URI', None))
