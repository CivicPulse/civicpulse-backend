"""
URL configuration for the CivicPulse example project.

This demonstrates how to include django-civicpulse URLs in your project.
"""

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    # Django auth views for login/logout
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(template_name="civicpulse/registration/login.html"),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    # Include CivicPulse URLs at root
    path("", include("civicpulse.urls")),
]
