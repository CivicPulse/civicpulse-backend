from django.urls import path

from . import views

app_name = "civicpulse"

urlpatterns = [
    # Home
    path("", views.index, name="index"),
    # Campaign (Organization) CRUD - groups multiple drives
    path("campaigns/", views.org_campaign_list, name="org_campaign_list"),
    path("campaigns/create/", views.org_campaign_create, name="org_campaign_create"),
    path("campaigns/<uuid:pk>/", views.org_campaign_detail, name="org_campaign_detail"),
    path(
        "campaigns/<uuid:pk>/edit/", views.org_campaign_edit, name="org_campaign_edit"
    ),
    path(
        "campaigns/<uuid:pk>/delete/",
        views.org_campaign_delete,
        name="org_campaign_delete",
    ),
    # Drive (ContactEffort) CRUD - individual voter outreach efforts
    path("drives/", views.campaign_list, name="campaign_list"),
    path("drives/create/", views.campaign_create, name="campaign_create"),
    path("drives/<uuid:pk>/", views.campaign_detail, name="campaign_detail"),
    path("drives/<uuid:pk>/edit/", views.campaign_edit, name="campaign_edit"),
    path("drives/<uuid:pk>/delete/", views.campaign_delete, name="campaign_delete"),
    # Assignment Management
    path(
        "drives/<uuid:pk>/assignments/",
        views.assignment_list,
        name="assignment_list",
    ),
    path(
        "drives/<uuid:pk>/assignments/add/",
        views.assignment_add,
        name="assignment_add",
    ),
    path(
        "drives/<uuid:pk>/assignments/remove/",
        views.assignment_remove,
        name="assignment_remove",
    ),
    # Calling Workflow (HTMX)
    path("drives/<uuid:pk>/call/", views.calling_session, name="calling_session"),
    path("drives/<uuid:pk>/call/next/", views.calling_next, name="calling_next"),
    path("drives/<uuid:pk>/call/log/", views.calling_log, name="calling_log"),
    path("drives/<uuid:pk>/call/skip/", views.calling_skip, name="calling_skip"),
    path("drives/<uuid:pk>/call/exit/", views.calling_exit, name="calling_exit"),
    # Door Knocking Workflow (HTMX)
    path("drives/<uuid:pk>/knock/", views.knocking_session, name="knocking_session"),
    path(
        "drives/<uuid:pk>/knock/location/",
        views.knocking_set_location,
        name="knocking_set_location",
    ),
    path("drives/<uuid:pk>/knock/list/", views.knocking_list, name="knocking_list"),
    path(
        "drives/<uuid:pk>/knock/select/",
        views.knocking_select,
        name="knocking_select",
    ),
    path("drives/<uuid:pk>/knock/next/", views.knocking_next, name="knocking_next"),
    path("drives/<uuid:pk>/knock/log/", views.knocking_log, name="knocking_log"),
    path("drives/<uuid:pk>/knock/skip/", views.knocking_skip, name="knocking_skip"),
    path("drives/<uuid:pk>/knock/exit/", views.knocking_exit, name="knocking_exit"),
    # HTMX Helpers
    path(
        "drives/candidates/",
        views.campaign_candidates,
        name="campaign_candidates",
    ),
    # Office CRUD
    path("offices/", views.office_list, name="office_list"),
    path("offices/create/", views.office_create, name="office_create"),
    path("offices/<uuid:pk>/", views.office_detail, name="office_detail"),
    path("offices/<uuid:pk>/edit/", views.office_edit, name="office_edit"),
    path("offices/<uuid:pk>/delete/", views.office_delete, name="office_delete"),
    # Organization CRUD
    path("organizations/", views.organization_list, name="organization_list"),
    path("organizations/create/", views.organization_create, name="organization_create"),
    path("organizations/<uuid:pk>/", views.organization_detail, name="organization_detail"),
    path("organizations/<uuid:pk>/edit/", views.organization_edit, name="organization_edit"),
    path(
        "organizations/<uuid:pk>/delete/",
        views.organization_delete,
        name="organization_delete",
    ),
    # Election CRUD
    path("elections/", views.election_list, name="election_list"),
    path("elections/create/", views.election_create, name="election_create"),
    path("elections/<uuid:pk>/", views.election_detail, name="election_detail"),
    path("elections/<uuid:pk>/edit/", views.election_edit, name="election_edit"),
    path("elections/<uuid:pk>/delete/", views.election_delete, name="election_delete"),
    path(
        "elections/<uuid:pk>/drives/",
        views.election_campaigns,
        name="election_campaigns",
    ),
    # Voter Import
    path(
        "elections/<uuid:pk>/import/",
        views.voter_import,
        name="voter_import",
    ),
    path(
        "elections/<uuid:pk>/import/<uuid:job_pk>/",
        views.import_status,
        name="import_status",
    ),
    path(
        "elections/<uuid:pk>/import/<uuid:job_pk>/progress/",
        views.import_progress,
        name="import_progress",
    ),
    # Election Date Management
    path(
        "elections/<uuid:pk>/dates/add/",
        views.election_date_add,
        name="election_date_add",
    ),
    path(
        "elections/<uuid:pk>/dates/<uuid:date_pk>/delete/",
        views.election_date_delete,
        name="election_date_delete",
    ),
    # Candidate CRUD
    path(
        "elections/<uuid:pk>/candidates/",
        views.candidate_list,
        name="candidate_list",
    ),
    path(
        "elections/<uuid:pk>/candidates/add/",
        views.candidate_add,
        name="candidate_add",
    ),
    path("candidates/<uuid:pk>/", views.candidate_detail, name="candidate_detail"),
    path("candidates/<uuid:pk>/edit/", views.candidate_edit, name="candidate_edit"),
    path(
        "candidates/<uuid:pk>/delete/",
        views.candidate_delete,
        name="candidate_delete",
    ),
    # GeoJSON API Endpoints
    path(
        "api/drives/<uuid:pk>/locations/",
        views.api_campaign_locations,
        name="api_campaign_locations",
    ),
    path(
        "api/drives/<uuid:pk>/route/",
        views.api_campaign_route,
        name="api_campaign_route",
    ),
    path(
        "api/elections/<uuid:pk>/voter-distribution/",
        views.api_election_voter_distribution,
        name="api_election_voter_distribution",
    ),
    path(
        "api/districts/",
        views.api_districts,
        name="api_districts",
    ),
    path(
        "api/elections/<uuid:pk>/districts/",
        views.api_election_districts,
        name="api_election_districts",
    ),
    # Stripe Connect - Candidates
    path(
        "candidates/<uuid:pk>/stripe/connect/",
        views.stripe_connect_candidate,
        name="stripe_connect_candidate",
    ),
    path(
        "candidates/<uuid:pk>/donations/",
        views.candidate_donations,
        name="candidate_donations",
    ),
    path(
        "candidates/<uuid:pk>/donations/sync/",
        views.candidate_donations_sync,
        name="candidate_donations_sync",
    ),
    # Stripe Connect - Campaigns
    path(
        "campaigns/<uuid:pk>/stripe/connect/",
        views.stripe_connect_campaign,
        name="stripe_connect_campaign",
    ),
    path(
        "campaigns/<uuid:pk>/donations/",
        views.campaign_donations,
        name="campaign_donations",
    ),
    path(
        "campaigns/<uuid:pk>/donations/sync/",
        views.campaign_donations_sync,
        name="campaign_donations_sync",
    ),
    # Stripe - Shared
    path(
        "stripe/oauth/callback/",
        views.stripe_oauth_callback,
        name="stripe_oauth_callback",
    ),
    path(
        "stripe/<uuid:connection_pk>/disconnect/",
        views.stripe_disconnect,
        name="stripe_disconnect",
    ),
    # Stripe - Generic redirects (for polymorphic template usage)
    path(
        "stripe/<str:owner_type>/<uuid:owner_id>/connect/",
        views.stripe_connect_redirect,
        name="stripe_connect",
    ),
    path(
        "stripe/<str:owner_type>/<uuid:owner_id>/donations/",
        views.stripe_donations_redirect,
        name="stripe_donations",
    ),
    path(
        "stripe/<str:owner_type>/<uuid:owner_id>/disconnect/",
        views.stripe_disconnect_confirm_redirect,
        name="stripe_disconnect_confirm",
    ),
    # Checking Account Management
    path(
        "campaigns/<uuid:pk>/accounts/",
        views.account_list,
        name="account_list",
    ),
    path(
        "campaigns/<uuid:pk>/accounts/create/",
        views.account_create,
        name="account_create",
    ),
    path(
        "accounts/<uuid:pk>/",
        views.account_detail,
        name="account_detail",
    ),
    path(
        "accounts/<uuid:pk>/edit/",
        views.account_edit,
        name="account_edit",
    ),
    path(
        "accounts/<uuid:pk>/delete/",
        views.account_delete,
        name="account_delete",
    ),
    path(
        "accounts/<uuid:pk>/import/",
        views.transaction_import,
        name="transaction_import",
    ),
]