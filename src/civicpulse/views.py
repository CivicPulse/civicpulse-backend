import csv
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from math import atan2, cos, radians, sin, sqrt

from django.contrib.auth.decorators import login_required
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    AssignmentFilterForm,
    CampaignForm,
    CandidateForm,
    CheckingAccountForm,
    ContactAttemptForm,
    DriveForm,
    ElectionDateForm,
    ElectionForm,
    OfficeForm,
    OrganizationForm,
    TransactionImportForm,
    VoterImportForm,
)
from .models import (
    Campaign,
    Candidate,
    CheckingAccount,
    ContactAttempt,
    ContactEffort,
    District,
    Donation,
    DonationSyncJob,
    EffortAssignment,
    Election,
    ElectionDate,
    ElectionVoter,
    ImportJob,
    Office,
    Organization,
    Person,
    StripeConnection,
    Transaction,
    VoterRecord,
)


@login_required
def index(request):
    return render(request, "civicpulse/index.html")


# =============================================================================
# Campaign CRUD Views
# =============================================================================


@login_required
def campaign_list(request):
    """List all campaigns with stats."""
    campaigns = ContactEffort.objects.annotate(
        total_assignments=Count("assignments"),
        pending_count=Count(
            "assignments", filter=Q(assignments__status=EffortAssignment.Status.PENDING)
        ),
        completed_count=Count(
            "assignments",
            filter=Q(assignments__status=EffortAssignment.Status.COMPLETED),
        ),
    ).order_by("-created_at")

    return render(
        request, "civicpulse/campaigns/campaign_list.html", {"campaigns": campaigns}
    )


@login_required
def campaign_create(request):
    """Create a new drive (voter contact effort)."""
    if request.method == "POST":
        form = DriveForm(request.POST)
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.created_by = request.user
            campaign.save()
            return redirect("civicpulse:campaign_detail", pk=campaign.pk)
    else:
        form = DriveForm()

    return render(
        request,
        "civicpulse/campaigns/campaign_form.html",
        {"form": form, "is_create": True},
    )


@login_required
def campaign_detail(request, pk):
    """View campaign details with progress stats."""
    campaign = get_object_or_404(ContactEffort, pk=pk)

    stats = EffortAssignment.objects.filter(effort=campaign).aggregate(
        total=Count("id"),
        pending=Count("id", filter=Q(status=EffortAssignment.Status.PENDING)),
        in_progress=Count("id", filter=Q(status=EffortAssignment.Status.IN_PROGRESS)),
        completed=Count("id", filter=Q(status=EffortAssignment.Status.COMPLETED)),
    )

    total = stats["total"] or 1
    stats["percentage"] = round((stats["completed"] / total) * 100, 1) if total else 0

    # Check if user has an in-progress assignment locked to them
    user_in_progress = EffortAssignment.objects.filter(
        effort=campaign,
        status=EffortAssignment.Status.IN_PROGRESS,
        locked_by=request.user,
    ).first()

    return render(
        request,
        "civicpulse/campaigns/campaign_detail.html",
        {"campaign": campaign, "stats": stats, "user_in_progress": user_in_progress},
    )


@login_required
def campaign_edit(request, pk):
    """Edit an existing drive (voter contact effort)."""
    campaign = get_object_or_404(ContactEffort, pk=pk)

    if request.method == "POST":
        form = DriveForm(request.POST, instance=campaign)
        if form.is_valid():
            form.save()
            return redirect("civicpulse:campaign_detail", pk=campaign.pk)
    else:
        form = DriveForm(instance=campaign)

    return render(
        request,
        "civicpulse/campaigns/campaign_form.html",
        {"form": form, "campaign": campaign, "is_create": False},
    )


@login_required
def campaign_delete(request, pk):
    """Delete a campaign with confirmation."""
    campaign = get_object_or_404(ContactEffort, pk=pk)

    if request.method == "POST":
        campaign.delete()
        return redirect("civicpulse:campaign_list")

    return render(
        request,
        "civicpulse/campaigns/campaign_confirm_delete.html",
        {"campaign": campaign},
    )


# =============================================================================
# Organization Campaign CRUD Views
# =============================================================================


@login_required
def org_campaign_list(request):
    """List all organization campaigns with drive counts."""
    campaigns = Campaign.objects.annotate(
        drive_count=Count("drives"),
        active_drives=Count("drives", filter=Q(drives__is_active=True)),
    ).order_by("-created_at")

    return render(
        request,
        "civicpulse/org_campaigns/campaign_list.html",
        {"campaigns": campaigns},
    )


@login_required
def org_campaign_create(request):
    """Create a new organization campaign."""
    if request.method == "POST":
        form = CampaignForm(request.POST)
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.created_by = request.user
            campaign.save()
            return redirect("civicpulse:org_campaign_detail", pk=campaign.pk)
    else:
        form = CampaignForm()

    return render(
        request,
        "civicpulse/org_campaigns/campaign_form.html",
        {"form": form, "is_create": True},
    )


@login_required
def org_campaign_detail(request, pk):
    """View organization campaign details with its drives."""
    campaign = get_object_or_404(Campaign, pk=pk)

    # Get drives with stats
    drives = campaign.drives.annotate(
        total_assignments=Count("assignments"),
        pending_count=Count(
            "assignments", filter=Q(assignments__status=EffortAssignment.Status.PENDING)
        ),
        completed_count=Count(
            "assignments",
            filter=Q(assignments__status=EffortAssignment.Status.COMPLETED),
        ),
    ).order_by("-created_at")

    # Get checking accounts for this campaign
    checking_accounts = campaign.checking_accounts.all()

    return render(
        request,
        "civicpulse/org_campaigns/campaign_detail.html",
        {"campaign": campaign, "drives": drives, "checking_accounts": checking_accounts},
    )


@login_required
def org_campaign_edit(request, pk):
    """Edit an existing organization campaign."""
    campaign = get_object_or_404(Campaign, pk=pk)

    if request.method == "POST":
        form = CampaignForm(request.POST, instance=campaign)
        if form.is_valid():
            form.save()
            return redirect("civicpulse:org_campaign_detail", pk=campaign.pk)
    else:
        form = CampaignForm(instance=campaign)

    return render(
        request,
        "civicpulse/org_campaigns/campaign_form.html",
        {"form": form, "campaign": campaign, "is_create": False},
    )


@login_required
def org_campaign_delete(request, pk):
    """Delete an organization campaign with confirmation."""
    campaign = get_object_or_404(Campaign, pk=pk)

    if request.method == "POST":
        campaign.delete()
        return redirect("civicpulse:org_campaign_list")

    return render(
        request,
        "civicpulse/org_campaigns/campaign_confirm_delete.html",
        {"campaign": campaign},
    )


# =============================================================================
# Office CRUD Views
# =============================================================================


@login_required
def office_list(request):
    """List all offices with election counts."""
    offices = Office.objects.annotate(
        election_count=Count("elections"),
        active_elections=Count(
            "elections", filter=Q(elections__status=Election.Status.ACTIVE)
        ),
    ).order_by("level", "state", "city", "name")

    # Optional filtering
    level = request.GET.get("level")
    state = request.GET.get("state")
    if level:
        offices = offices.filter(level=level)
    if state:
        offices = offices.filter(state=state)

    return render(
        request,
        "civicpulse/elections/office_list.html",
        {"offices": offices, "level_choices": Office.Level.choices},
    )


@login_required
def office_detail(request, pk):
    """View office with associated elections."""
    office = get_object_or_404(Office, pk=pk)
    elections = (
        Election.objects.filter(office=office)
        .annotate(candidate_count=Count("candidates"))
        .order_by("-year", "-election_day")
    )

    return render(
        request,
        "civicpulse/elections/office_detail.html",
        {"office": office, "elections": elections},
    )


@login_required
def office_create(request):
    """Create a new office."""
    if request.method == "POST":
        form = OfficeForm(request.POST)
        if form.is_valid():
            office = form.save()
            return redirect("civicpulse:office_detail", pk=office.pk)
    else:
        form = OfficeForm()

    return render(
        request,
        "civicpulse/elections/office_form.html",
        {"form": form, "is_create": True},
    )


@login_required
def office_edit(request, pk):
    """Edit an existing office."""
    office = get_object_or_404(Office, pk=pk)

    if request.method == "POST":
        form = OfficeForm(request.POST, instance=office)
        if form.is_valid():
            form.save()
            return redirect("civicpulse:office_detail", pk=office.pk)
    else:
        form = OfficeForm(instance=office)

    return render(
        request,
        "civicpulse/elections/office_form.html",
        {"form": form, "office": office, "is_create": False},
    )


@login_required
def office_delete(request, pk):
    """Delete an office with confirmation."""
    office = get_object_or_404(Office, pk=pk)

    if request.method == "POST":
        office.delete()
        return redirect("civicpulse:office_list")

    return render(
        request, "civicpulse/elections/office_confirm_delete.html", {"office": office}
    )


# =============================================================================
# Organization CRUD Views
# =============================================================================


@login_required
def organization_list(request):
    """List all organizations with office counts."""
    organizations = Organization.objects.annotate(
        office_count=Count("offices"),
    ).order_by("organization_type", "state", "name")

    return render(
        request,
        "civicpulse/organizations/organization_list.html",
        {"organizations": organizations},
    )


@login_required
def organization_detail(request, pk):
    """View organization with associated offices."""
    organization = get_object_or_404(Organization, pk=pk)
    offices = (
        Office.objects.filter(organization=organization)
        .annotate(election_count=Count("elections"))
        .order_by("level", "name")
    )

    return render(
        request,
        "civicpulse/organizations/organization_detail.html",
        {"organization": organization, "offices": offices},
    )


@login_required
def organization_create(request):
    """Create a new organization."""
    if request.method == "POST":
        form = OrganizationForm(request.POST)
        if form.is_valid():
            organization = form.save()
            return redirect("civicpulse:organization_detail", pk=organization.pk)
    else:
        form = OrganizationForm()

    return render(
        request,
        "civicpulse/organizations/organization_form.html",
        {"form": form, "is_create": True},
    )


@login_required
def organization_edit(request, pk):
    """Edit an existing organization."""
    organization = get_object_or_404(Organization, pk=pk)

    if request.method == "POST":
        form = OrganizationForm(request.POST, instance=organization)
        if form.is_valid():
            form.save()
            return redirect("civicpulse:organization_detail", pk=organization.pk)
    else:
        form = OrganizationForm(instance=organization)

    return render(
        request,
        "civicpulse/organizations/organization_form.html",
        {"form": form, "organization": organization, "is_create": False},
    )


@login_required
def organization_delete(request, pk):
    """Delete an organization with confirmation."""
    organization = get_object_or_404(Organization, pk=pk)

    if request.method == "POST":
        organization.delete()
        return redirect("civicpulse:organization_list")

    return render(
        request,
        "civicpulse/organizations/organization_confirm_delete.html",
        {"organization": organization},
    )


# =============================================================================
# Election CRUD Views
# =============================================================================


@login_required
def election_list(request):
    """List elections with filtering."""
    elections = Election.objects.select_related("office").annotate(
        candidate_count=Count("candidates"),
        effort_count=Count("contact_efforts"),
    )

    # Filters
    status = request.GET.get("status")
    year = request.GET.get("year")
    election_type = request.GET.get("type")

    if status:
        elections = elections.filter(status=status)
    if year:
        elections = elections.filter(year=year)
    if election_type:
        elections = elections.filter(election_type=election_type)

    elections = elections.order_by("-year", "-election_day")

    # Get distinct years for filter dropdown
    years = Election.objects.values_list("year", flat=True).distinct().order_by("-year")

    return render(
        request,
        "civicpulse/elections/election_list.html",
        {
            "elections": elections,
            "status_choices": Election.Status.choices,
            "type_choices": Election.ElectionType.choices,
            "years": years,
        },
    )


@login_required
def election_detail(request, pk):
    """View election details with candidates and dates."""
    election = get_object_or_404(
        Election.objects.select_related("office", "parent_election"), pk=pk
    )
    # Annotate candidates with will_vote counts from their associated campaigns
    candidates = (
        Candidate.objects.filter(election=election)
        .select_related("person")
        .annotate(
            will_vote_count=Count(
                "contact_efforts__attempts",
                filter=Q(
                    contact_efforts__attempts__outcome=ContactAttempt.Outcome.WILL_VOTE
                ),
            )
        )
    )
    additional_dates = ElectionDate.objects.filter(election=election)
    contact_efforts = ContactEffort.objects.filter(election=election).annotate(
        total_assignments=Count("assignments"),
        completed_count=Count(
            "assignments",
            filter=Q(assignments__status=EffortAssignment.Status.COMPLETED),
        ),
    )

    # Calculate days until/since election
    days_info = None
    if election.election_day:
        delta = election.election_day - date.today()
        days_info = {"days": abs(delta.days), "is_future": delta.days > 0}

    return render(
        request,
        "civicpulse/elections/election_detail.html",
        {
            "election": election,
            "candidates": candidates,
            "additional_dates": additional_dates,
            "contact_efforts": contact_efforts,
            "days_info": days_info,
        },
    )


@login_required
def election_create(request):
    """Create a new election."""
    if request.method == "POST":
        form = ElectionForm(request.POST)
        if form.is_valid():
            election = form.save()
            return redirect("civicpulse:election_detail", pk=election.pk)
    else:
        form = ElectionForm()

    return render(
        request,
        "civicpulse/elections/election_form.html",
        {"form": form, "is_create": True},
    )


@login_required
def election_edit(request, pk):
    """Edit an existing election."""
    election = get_object_or_404(Election, pk=pk)

    if request.method == "POST":
        form = ElectionForm(request.POST, instance=election)
        if form.is_valid():
            form.save()
            return redirect("civicpulse:election_detail", pk=election.pk)
    else:
        form = ElectionForm(instance=election)

    return render(
        request,
        "civicpulse/elections/election_form.html",
        {"form": form, "election": election, "is_create": False},
    )


@login_required
def election_delete(request, pk):
    """Delete an election with confirmation."""
    election = get_object_or_404(Election, pk=pk)

    if request.method == "POST":
        election.delete()
        return redirect("civicpulse:election_list")

    return render(
        request,
        "civicpulse/elections/election_confirm_delete.html",
        {"election": election},
    )


# =============================================================================
# Candidate Views
# =============================================================================