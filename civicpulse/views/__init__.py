"""
Views package for CivicPulse application.

This package contains all view logic for the CivicPulse application,
organized by functionality.
"""

from .campaign import (
    CampaignCreateView,
    CampaignDeleteView,
    CampaignDetailView,
    CampaignListView,
    CampaignUpdateView,
)
from .export import PersonExportView
from .imports import PersonImportView
from .person import PersonCreateView, PersonDetailView
from .search import (
    PersonSearchAPIView,
    PersonSearchView,
    QuickSearchAPIView,
    SearchStatsAPIView,
    export_search_results,
)

__all__ = [
    "CampaignCreateView",
    "CampaignDeleteView",
    "CampaignDetailView",
    "CampaignListView",
    "CampaignUpdateView",
    "PersonExportView",
    "PersonImportView",
    "PersonCreateView",
    "PersonDetailView",
    "PersonSearchView",
    "PersonSearchAPIView",
    "QuickSearchAPIView",
    "SearchStatsAPIView",
    "export_search_results",
]
