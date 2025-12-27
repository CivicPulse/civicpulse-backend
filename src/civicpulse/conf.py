"""
CivicPulse settings configuration.

Usage in Django settings::

    CIVICPULSE = {
        "LOCK_TIMEOUT_MINUTES": 15,
        "USE_COMPRESSOR": True,
        "SITE_NAME": "My Organization",
    }

All settings are optional and have sensible defaults.
"""

from django.conf import settings

DEFAULTS = {
    # Lock timeout for concurrent user support (minutes)
    # After this time, abandoned locks are released
    "LOCK_TIMEOUT_MINUTES": 10,
    # Whether to use django-compressor for CSS compression
    # Requires django-compressor to be installed and configured
    "USE_COMPRESSOR": False,
    # Site name for branding in templates
    "SITE_NAME": "CivicPulse",
    # Whether to include the default navigation bar
    "INCLUDE_DEFAULT_NAV": True,
    # CDN URLs (can be overridden for self-hosting)
    "CDN_FLOWBITE": "https://cdn.jsdelivr.net/npm/flowbite@4.0.1/dist/flowbite.min.js",
    "CDN_HTMX": "https://unpkg.com/htmx.org@2.0.4",
    # Leaflet.js for interactive maps
    "CDN_LEAFLET_JS": "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js",
    "CDN_LEAFLET_CSS": "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css",
    # Leaflet Markercluster for clustering markers
    "CDN_LEAFLET_MARKERCLUSTER_JS": "https://unpkg.com/leaflet.markercluster@1.4.1/dist/leaflet.markercluster.js",
    "CDN_LEAFLET_MARKERCLUSTER_CSS": "https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.css",
    "CDN_LEAFLET_MARKERCLUSTER_DEFAULT_CSS": "https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.Default.css",
    # Default map tile provider (OpenStreetMap)
    "MAP_TILE_URL": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    "MAP_TILE_ATTRIBUTION": '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    # Default map center (continental US)
    "MAP_DEFAULT_CENTER": [39.8283, -98.5795],
    "MAP_DEFAULT_ZOOM": 4,
    # Routing service configuration
    # Local OSRM server URL (e.g., "http://localhost:5000")
    # If not set, falls back to OpenRouteService or OSRM demo server
    "OSRM_URL": None,
    # OpenRouteService API key (https://openrouteservice.org/)
    # Free tier: 2,000 requests/day. Falls back to OSRM demo if not set.
    "OPENROUTESERVICE_API_KEY": None,
}


class CivicPulseSettings:
    """
    Lazy settings object that reads from Django settings.

    Access settings via the civicpulse_settings instance::

        from civicpulse.conf import civicpulse_settings

        timeout = civicpulse_settings.LOCK_TIMEOUT_MINUTES
    """

    def __getattr__(self, name):
        if name not in DEFAULTS:
            raise AttributeError(f"Unknown CivicPulse setting: {name}")

        user_settings = getattr(settings, "CIVICPULSE", {})
        return user_settings.get(name, DEFAULTS[name])

    def __dir__(self):
        return list(DEFAULTS.keys())


civicpulse_settings = CivicPulseSettings()
