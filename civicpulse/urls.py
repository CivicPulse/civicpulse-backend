"""
URL configuration for CivicPulse application.

This module defines URL patterns for the CivicPulse application,
including authentication, import/export, and dashboard functionality.
"""

from django.urls import path

from civicpulse.views import (
    PersonExportView,
    PersonImportView,
    PersonSearchAPIView,
    PersonSearchView,
    QuickSearchAPIView,
    SearchStatsAPIView,
    export_search_results,
)

from . import views_old as views

app_name = "civicpulse"

urlpatterns = [
    # Authentication URLs
    path("login/", views.SecureLoginView.as_view(), name="login"),
    path("logout/", views.SecureLogoutView.as_view(), name="logout"),
    path("register/", views.RegistrationView.as_view(), name="register"),
    path(
        "registration/complete/",
        views.RegistrationCompleteView.as_view(),
        name="registration_complete",
    ),
    # Email verification
    path(
        "verify/<str:uidb64>/<str:token>/",
        views.account_verification_view,
        name="account_verify",
    ),
    # Password reset URLs
    path(
        "password-reset/",
        views.SecurePasswordResetView.as_view(),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        views.SecurePasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "password-reset-confirm/<str:uidb64>/<str:token>/",
        views.SecurePasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        views.PasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
    # Password change URLs (for authenticated users)
    path(
        "password-change/", views.PasswordChangeView.as_view(), name="password_change"
    ),
    path(
        "password-change/done/",
        views.PasswordChangeDoneView.as_view(),
        name="password_change_done",
    ),
    # Dashboard and profile URLs
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    # Health check endpoint
    path("health/", views.health_check, name="health_check"),
    # Search URLs
    path("search/", PersonSearchView.as_view(), name="person_search"),
    path("api/search/", PersonSearchAPIView.as_view(), name="person_search_api"),
    path("api/search/quick/", QuickSearchAPIView.as_view(), name="quick_search_api"),
    path("api/search/stats/", SearchStatsAPIView.as_view(), name="search_stats_api"),
    path("search/export/", export_search_results, name="search_export"),
    # Export URLs
    path("export/persons/", PersonExportView.as_view(), name="person_export"),
    # Import URLs
    path("import/persons/", PersonImportView.as_view(), name="person_import"),
    # Root redirect to dashboard for authenticated users, login for anonymous
    path("", views.DashboardView.as_view(), name="home"),
]
