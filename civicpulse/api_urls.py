"""
API URL configuration for CivicPulse REST API endpoints.

This module configures URL routing for all DRF-based API endpoints using
Django REST Framework's DefaultRouter. All API endpoints are versioned under
the /api/v1/ prefix (configured in main urls.py).

Architecture:
    - Uses DefaultRouter for automatic ViewSet URL generation
    - Provides standard REST endpoints for all registered ViewSets
    - Generates browsable API with DRF's built-in interface
    - Follows RESTful URL conventions

URL Structure:
    /api/v1/campaigns/                      - List/Create campaigns (GET, POST)
    /api/v1/campaigns/{id}/                 - Detail/Update/Delete
                                              (GET, PUT, PATCH, DELETE)
    /api/v1/campaigns/{id}/archive/         - Archive campaign (PATCH)
    /api/v1/campaigns/{id}/activate/        - Activate campaign (PATCH)
    /api/v1/campaigns/duplicate_check/      - Check for duplicates (POST)

Router Benefits:
    - Automatic URL pattern generation for ViewSets
    - Consistent URL structure across all endpoints
    - Built-in hypermedia linking (HATEOAS)
    - Automatic OPTIONS support for API discovery

Example API Calls:
    # List all campaigns
    GET /api/v1/campaigns/?search=senate&status=active

    # Create new campaign
    POST /api/v1/campaigns/
    {
        "name": "2024 Senate Campaign",
        "candidate_name": "Jane Smith",
        "election_date": "2024-11-05"
    }

    # Get campaign details
    GET /api/v1/campaigns/{campaign_id}/

    # Archive a campaign
    PATCH /api/v1/campaigns/{campaign_id}/archive/

Authentication:
    All API endpoints require authentication (IsAuthenticated permission).
    Supports SessionAuthentication and BasicAuthentication.

Rate Limiting:
    Rate limits are applied at the ViewSet level:
    - list: 100 requests/hour
    - create: 20 requests/hour
    - update/partial_update: 50 requests/hour
    - destroy: 10 requests/hour

Future Expansion:
    As new ViewSets are added, register them here following the same pattern:
    router.register(r'resource-name', ResourceViewSet, basename='resource')
"""

from rest_framework.routers import DefaultRouter

from civicpulse.viewsets import CampaignViewSet

# Initialize DRF router for automatic ViewSet URL generation
router = DefaultRouter()

# Register CampaignViewSet to handle all Campaign API endpoints
# Using basename='campaign-api' to avoid URL name collision with Django views
# This creates the following URL patterns:
#   - ^campaigns/$ [name='campaign-api-list']
#   - ^campaigns\.(?P<format>[a-z0-9]+)/?$ [name='campaign-api-list']
#   - ^campaigns/(?P<pk>[^/.]+)/$ [name='campaign-api-detail']
#   - ^campaigns/(?P<pk>[^/.]+)\.(?P<format>[a-z0-9]+)/?$ [name='campaign-api-detail']
#   - ^campaigns/(?P<pk>[^/.]+)/archive/$ [name='campaign-api-archive']
#   - ^campaigns/(?P<pk>[^/.]+)/activate/$ [name='campaign-api-activate']
#   - ^campaigns/duplicate_check/$ [name='campaign-api-duplicate-check']
router.register(r"campaigns", CampaignViewSet, basename="campaign-api")

# Export router URLs for inclusion in main urls.py
# These will be prefixed with /api/v1/ in the main URL configuration
urlpatterns = router.urls
