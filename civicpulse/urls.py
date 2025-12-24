from django.urls import path

from . import views

urlpatterns = [
    # Home
    path("", views.index, name="index"),
    # Campaign CRUD
    path("campaigns/", views.campaign_list, name="campaign_list"),
    path("campaigns/create/", views.campaign_create, name="campaign_create"),
    path("campaigns/<uuid:pk>/", views.campaign_detail, name="campaign_detail"),
    path("campaigns/<uuid:pk>/edit/", views.campaign_edit, name="campaign_edit"),
    path("campaigns/<uuid:pk>/delete/", views.campaign_delete, name="campaign_delete"),
    # Assignment Management
    path(
        "campaigns/<uuid:pk>/assignments/",
        views.assignment_list,
        name="assignment_list",
    ),
    path(
        "campaigns/<uuid:pk>/assignments/add/",
        views.assignment_add,
        name="assignment_add",
    ),
    path(
        "campaigns/<uuid:pk>/assignments/remove/",
        views.assignment_remove,
        name="assignment_remove",
    ),
    # Calling Workflow (HTMX)
    path("campaigns/<uuid:pk>/call/", views.calling_session, name="calling_session"),
    path("campaigns/<uuid:pk>/call/next/", views.calling_next, name="calling_next"),
    path("campaigns/<uuid:pk>/call/log/", views.calling_log, name="calling_log"),
    path("campaigns/<uuid:pk>/call/skip/", views.calling_skip, name="calling_skip"),
]
