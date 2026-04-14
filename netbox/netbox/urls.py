from django.conf import settings
from django.conf.urls import include
from django.http import Http404
from django.urls import path
from django.views.static import serve
from django.views.decorators.cache import cache_page
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from account.views import LoginView, LogoutView
from netbox.api.views import APIRootView, AuthenticationCheckView, StatusView
from netbox.graphql.schema import schema
from netbox.graphql.views import NetBoxGraphQLView
from netbox.plugins.urls import plugin_api_patterns, plugin_patterns
from netbox.views import HomeView, MediaView, SearchView, StaticMediaFailureView, htmx


def _serve_static_if_enabled(request, path):
    """
    Serve collected static files when SERVE_STATIC_IN_APP is set (no nginx in front). Otherwise behave as if the
    route did not exist so reverse proxies can own STATIC_URL.
    """
    if not getattr(settings, 'SERVE_STATIC_IN_APP', False):
        raise Http404()
    return serve(request, path, document_root=settings.STATIC_ROOT)


_patterns = [

    # Base views
    path('', HomeView.as_view(), name='home'),
    path('search/', SearchView.as_view(), name='search'),

    # Login/logout
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('oauth/', include('social_django.urls', namespace='social')),

    # Apps
    path('circuits/', include('circuits.urls')),
    path('core/', include('core.urls')),
    path('dcim/', include('dcim.urls')),
    path('extras/', include('extras.urls')),
    path('ipam/', include('ipam.urls')),
    path('tenancy/', include('tenancy.urls')),
    path('users/', include('users.urls')),
    path('virtualization/', include('virtualization.urls')),
    path('vpn/', include('vpn.urls')),
    path('wireless/', include('wireless.urls')),

    # Current user views
    path('user/', include('account.urls')),

    # HTMX views
    path('htmx/object-selector/', htmx.ObjectSelectorView.as_view(), name='htmx_object_selector'),

    # REST API
    path('api/', APIRootView.as_view(), name='api-root'),
    path('api/circuits/', include('circuits.api.urls')),
    path('api/core/', include('core.api.urls')),
    path('api/dcim/', include('dcim.api.urls')),
    path('api/extras/', include('extras.api.urls')),
    path('api/ipam/', include('ipam.api.urls')),
    path('api/tenancy/', include('tenancy.api.urls')),
    path('api/users/', include('users.api.urls')),
    path('api/virtualization/', include('virtualization.api.urls')),
    path('api/vpn/', include('vpn.api.urls')),
    path('api/wireless/', include('wireless.api.urls')),
    path('api/status/', StatusView.as_view(), name='api-status'),
    path('api/authentication-check/', AuthenticationCheckView.as_view(), name='api-authentication-check'),

    # REST API schema
    path(
        "api/schema/",
        cache_page(timeout=86400, key_prefix=f"api_schema_{settings.RELEASE.version}")(
            SpectacularAPIView.as_view()
        ),
        name="schema",
    ),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='api_docs'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='api_redocs'),

    # GraphQL
    path('graphql/', NetBoxGraphQLView.as_view(schema=schema), name='graphql'),

    # Serving static media in Django to pipe it through LoginRequiredMiddleware
    path('media/<path:path>', MediaView.as_view(), name='media'),
    path('media-failure/', StaticMediaFailureView.as_view(), name='media_failure'),

    # Plugins
    path('plugins/', include((plugin_patterns, 'plugins'))),
    path('api/plugins/', include((plugin_api_patterns, 'plugins-api'))),
]

# django-debug-toolbar
if settings.DEBUG:
    import debug_toolbar
    _patterns.append(path('__debug__/', include(debug_toolbar.urls)))

# Prometheus metrics
if settings.METRICS_ENABLED:
    _patterns.append(path('', include('django_prometheus.urls')))

# Collected static (see SERVE_STATIC_IN_APP); listed before BASE_PATH so it matches STATIC_URL when BASE_PATH is set.
_static_route = f"{settings.STATIC_URL.strip('/')}/<path:path>"

# Prepend BASE_PATH
urlpatterns = [
    path(_static_route, _serve_static_if_enabled),
    path(settings.BASE_PATH, include(_patterns)),
]

handler404 = 'netbox.views.errors.handler_404'
handler500 = 'netbox.views.errors.handler_500'
