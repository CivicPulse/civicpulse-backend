"""
URL configuration for CivicPulse application.

This module defines URL patterns for the CivicPulse application views,
including import/export functionality.
"""

from django.urls import path

from civicpulse.views import PersonExportView, PersonImportView

app_name = "civicpulse"

urlpatterns = [
    # Export URLs
    path("export/persons/", PersonExportView.as_view(), name="person_export"),
    # Import URLs
    path("import/persons/", PersonImportView.as_view(), name="person_import"),
]
