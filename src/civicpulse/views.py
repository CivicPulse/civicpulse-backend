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

    return render(
        request,
        "civicpulse/org_campaigns/campaign_detail.html",
        {"campaign": campaign, "drives": drives},
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


@login_required
def candidate_list(request, pk):
    """List candidates for an election."""
    election = get_object_or_404(Election, pk=pk)
    candidates = (
        Candidate.objects.filter(election=election)
        .select_related("person")
        .prefetch_related("person__phone_numbers", "person__emails")
    )

    # Filters
    status = request.GET.get("status")
    party = request.GET.get("party")
    if status:
        candidates = candidates.filter(status=status)
    if party:
        candidates = candidates.filter(party_affiliation=party)

    return render(
        request,
        "civicpulse/elections/candidate_list.html",
        {
            "election": election,
            "candidates": candidates,
            "status_choices": Candidate.Status.choices,
        },
    )


@login_required
def candidate_add(request, pk):
    """Add a candidate to an election."""
    election = get_object_or_404(Election, pk=pk)

    if request.method == "POST":
        form = CandidateForm(request.POST)
        if form.is_valid():
            candidate = form.save(commit=False)
            candidate.election = election
            candidate.save()
            return redirect("civicpulse:election_detail", pk=election.pk)
    else:
        form = CandidateForm()

    return render(
        request,
        "civicpulse/elections/candidate_form.html",
        {"form": form, "election": election, "is_create": True},
    )


@login_required
def candidate_detail(request, pk):
    """View candidate details with contact efforts."""
    candidate = get_object_or_404(
        Candidate.objects.select_related("person", "election", "election__office"),
        pk=pk,
    )

    efforts = ContactEffort.objects.filter(candidate=candidate).annotate(
        total_assignments=Count("assignments"),
        completed_count=Count(
            "assignments",
            filter=Q(assignments__status=EffortAssignment.Status.COMPLETED),
        ),
    )

    # Handle null or missing person gracefully
    person = None
    if candidate.person_id:
        try:
            person = Person.objects.prefetch_related(
                "phone_numbers", "emails", "addresses"
            ).get(pk=candidate.person_id)
        except Person.DoesNotExist:
            pass  # Person was deleted, candidate remains orphaned

    return render(
        request,
        "civicpulse/elections/candidate_detail.html",
        {"candidate": candidate, "person": person, "efforts": efforts},
    )


@login_required
def candidate_edit(request, pk):
    """Edit a candidate."""
    candidate = get_object_or_404(Candidate, pk=pk)

    if request.method == "POST":
        form = CandidateForm(request.POST, instance=candidate)
        if form.is_valid():
            form.save()
            return redirect("civicpulse:candidate_detail", pk=candidate.pk)
    else:
        form = CandidateForm(instance=candidate)

    return render(
        request,
        "civicpulse/elections/candidate_form.html",
        {
            "form": form,
            "candidate": candidate,
            "election": candidate.election,
            "is_create": False,
        },
    )


@login_required
def candidate_delete(request, pk):
    """Delete a candidate with confirmation."""
    candidate = get_object_or_404(Candidate, pk=pk)
    election = candidate.election

    if request.method == "POST":
        candidate.delete()
        return redirect("civicpulse:election_detail", pk=election.pk)

    return render(
        request,
        "civicpulse/elections/candidate_confirm_delete.html",
        {"candidate": candidate},
    )


# =============================================================================
# Election Campaigns View
# =============================================================================


@login_required
def election_campaigns(request, pk):
    """View/manage contact efforts for an election."""
    election = get_object_or_404(Election, pk=pk)
    efforts = ContactEffort.objects.filter(election=election).annotate(
        total_assignments=Count("assignments"),
        completed_count=Count(
            "assignments",
            filter=Q(assignments__status=EffortAssignment.Status.COMPLETED),
        ),
    )

    return render(
        request,
        "civicpulse/elections/election_campaigns.html",
        {"election": election, "efforts": efforts},
    )


# =============================================================================
# Election Date Management (HTMX)
# =============================================================================


@login_required
def election_date_add(request, pk):
    """Add an additional date to an election."""
    election = get_object_or_404(Election, pk=pk)

    if request.method == "POST":
        form = ElectionDateForm(request.POST)
        if form.is_valid():
            election_date = form.save(commit=False)
            election_date.election = election
            election_date.save()
            return redirect("civicpulse:election_detail", pk=election.pk)
    else:
        form = ElectionDateForm()

    return render(
        request,
        "civicpulse/elections/election_date_form.html",
        {"form": form, "election": election},
    )


@login_required
def election_date_delete(request, pk, date_pk):
    """Delete an additional election date."""
    election = get_object_or_404(Election, pk=pk)
    election_date = get_object_or_404(ElectionDate, pk=date_pk, election=election)

    if request.method == "POST":
        election_date.delete()

    return redirect("civicpulse:election_detail", pk=election.pk)


# =============================================================================
# Assignment Management Views
# =============================================================================


@login_required
def assignment_list(request, pk):
    """List and manage assignments for a campaign."""
    campaign = get_object_or_404(ContactEffort, pk=pk)

    status_filter = request.GET.get("status", "")
    assignments = EffortAssignment.objects.filter(effort=campaign).select_related(
        "person", "election_voter", "locked_by"
    )

    if status_filter:
        assignments = assignments.filter(status=status_filter)

    assignments = assignments[:100]  # Limit for performance

    return render(
        request,
        "civicpulse/campaigns/assignment_list.html",
        {
            "campaign": campaign,
            "assignments": assignments,
            "status_filter": status_filter,
            "status_choices": EffortAssignment.Status.choices,
        },
    )


@login_required
def assignment_add(request, pk):
    """Filter and bulk assign persons/voters to a campaign."""
    campaign = get_object_or_404(ContactEffort, pk=pk)

    # Determine if this campaign uses ElectionVoter or Person records
    uses_election_voters = campaign.election is not None

    if request.method == "POST":
        form = AssignmentFilterForm(request.POST)
        if form.is_valid():
            if uses_election_voters:
                # Query ElectionVoter for election-based campaigns
                voters = ElectionVoter.objects.filter(
                    election=campaign.election
                ).exclude(effort_assignments__effort=campaign)

                if form.cleaned_data["has_phone"]:
                    voters = voters.filter(phone_numbers__isnull=False).distinct()

                if form.cleaned_data["party"]:
                    voters = voters.filter(registered_party=form.cleaned_data["party"])

                if form.cleaned_data["likelihood"]:
                    likelihood = form.cleaned_data["likelihood"]
                    if likelihood == "high":
                        voters = voters.filter(
                            likelihood_general__regex=r"^[7-9][0-9]%$|^100%$"
                        )
                    elif likelihood == "medium":
                        voters = voters.filter(
                            likelihood_general__regex=r"^[4-6][0-9]%$"
                        )
                    elif likelihood == "low":
                        voters = voters.filter(
                            likelihood_general__regex=r"^[0-3]?[0-9]%$"
                        )

                # Geographic filtering
                district = form.cleaned_data.get("district")
                radius_miles = form.cleaned_data.get("radius_miles")
                center_lat = form.cleaned_data.get("center_lat")
                center_lon = form.cleaned_data.get("center_lon")

                if district:
                    voters = voters.filter(
                        location__isnull=False, location__within=district.boundary
                    )

                if radius_miles and center_lat and center_lon:
                    from django.contrib.gis.geos import Point
                    from django.contrib.gis.measure import D

                    center = Point(float(center_lon), float(center_lat), srid=4326)
                    voters = voters.filter(
                        location__isnull=False,
                        location__distance_lte=(center, D(mi=radius_miles)),
                    )

                limit = form.cleaned_data.get("limit") or 100
                voter_ids = list(voters.values_list("id", flat=True)[:limit])

                # Bulk create assignments with election_voter FK
                assignments = [
                    EffortAssignment(effort=campaign, election_voter_id=vid)
                    for vid in voter_ids
                ]
                EffortAssignment.objects.bulk_create(assignments, ignore_conflicts=True)
            else:
                # Query Person for non-election campaigns (legacy)
                persons = Person.objects.exclude(effort_assignments__effort=campaign)

                if form.cleaned_data["has_phone"]:
                    persons = persons.filter(phone_numbers__isnull=False).distinct()

                if form.cleaned_data["party"]:
                    persons = persons.filter(
                        voter_record__registered_party=form.cleaned_data["party"]
                    )

                if form.cleaned_data["likelihood"]:
                    likelihood = form.cleaned_data["likelihood"]
                    if likelihood == "high":
                        persons = persons.filter(
                            voter_record__likelihood_general__regex=r"^[7-9][0-9]%$|^100%$"
                        )
                    elif likelihood == "medium":
                        persons = persons.filter(
                            voter_record__likelihood_general__regex=r"^[4-6][0-9]%$"
                        )
                    elif likelihood == "low":
                        persons = persons.filter(
                            voter_record__likelihood_general__regex=r"^[0-3]?[0-9]%$"
                        )

                # Geographic filtering (via voter_record for Person-based campaigns)
                district = form.cleaned_data.get("district")
                radius_miles = form.cleaned_data.get("radius_miles")
                center_lat = form.cleaned_data.get("center_lat")
                center_lon = form.cleaned_data.get("center_lon")

                if district:
                    persons = persons.filter(
                        voter_record__location__isnull=False,
                        voter_record__location__within=district.boundary,
                    )

                if radius_miles and center_lat and center_lon:
                    from django.contrib.gis.geos import Point
                    from django.contrib.gis.measure import D

                    center = Point(float(center_lon), float(center_lat), srid=4326)
                    persons = persons.filter(
                        voter_record__location__isnull=False,
                        voter_record__location__distance_lte=(center, D(mi=radius_miles)),
                    )

                limit = form.cleaned_data.get("limit") or 100
                person_ids = list(persons.values_list("id", flat=True)[:limit])

                # Bulk create assignments with person FK
                assignments = [
                    EffortAssignment(effort=campaign, person_id=pid)
                    for pid in person_ids
                ]
                EffortAssignment.objects.bulk_create(assignments, ignore_conflicts=True)

            return redirect("civicpulse:assignment_list", pk=campaign.pk)
    else:
        form = AssignmentFilterForm()

    # Preview count - use appropriate model based on campaign type
    if uses_election_voters:
        preview_count = (
            ElectionVoter.objects.filter(election=campaign.election)
            .exclude(effort_assignments__effort=campaign)
            .filter(phone_numbers__isnull=False)
            .distinct()
            .count()
        )
    else:
        preview_count = (
            Person.objects.exclude(effort_assignments__effort=campaign)
            .filter(phone_numbers__isnull=False)
            .distinct()
            .count()
        )

    return render(
        request,
        "civicpulse/campaigns/assignment_add.html",
        {
            "campaign": campaign,
            "form": form,
            "preview_count": preview_count,
            "uses_election_voters": uses_election_voters,
        },
    )


@login_required
def assignment_remove(request, pk):
    """Remove assignments from a campaign."""
    campaign = get_object_or_404(ContactEffort, pk=pk)

    if request.method == "POST":
        assignment_ids = request.POST.getlist("assignment_ids")
        EffortAssignment.objects.filter(
            effort=campaign,
            pk__in=assignment_ids,
            status=EffortAssignment.Status.PENDING,
        ).delete()

    return redirect("civicpulse:assignment_list", pk=campaign.pk)


# =============================================================================
# Calling Workflow Views (HTMX)
# =============================================================================


def get_next_assignment(effort, user):
    """Get next uncontacted person with row-level locking."""
    # Release stale locks (>10 min)
    stale_threshold = timezone.now() - timedelta(minutes=10)
    EffortAssignment.objects.filter(
        effort=effort,
        status=EffortAssignment.Status.IN_PROGRESS,
        locked_at__lt=stale_threshold,
    ).update(
        status=EffortAssignment.Status.PENDING,
        locked_by=None,
        locked_at=None,
    )

    # Atomic lock with skip_locked
    with transaction.atomic():
        assignment = (
            EffortAssignment.objects.select_for_update(skip_locked=True)
            .filter(effort=effort, status=EffortAssignment.Status.PENDING)
            .first()
        )

        if assignment:
            assignment.status = EffortAssignment.Status.IN_PROGRESS
            assignment.locked_by = user
            assignment.locked_at = timezone.now()
            assignment.save(update_fields=["status", "locked_by", "locked_at"])

    return assignment


def get_person_with_details(person_id, effort):
    """Fetch person with all calling-relevant data efficiently."""
    return (
        Person.objects.select_related("voter_record")
        .prefetch_related(
            "phone_numbers",
            "addresses",
            Prefetch(
                "contact_attempts",
                queryset=ContactAttempt.objects.filter(effort=effort).order_by(
                    "-created_at"
                )[:5],
                to_attr="effort_attempts",
            ),
        )
        .get(pk=person_id)
    )


def get_assignment_target_with_details(assignment, effort):
    """
    Fetch the assignment target (Person or ElectionVoter) with related data.

    Returns (target, target_type) tuple where:
    - target: The Person or ElectionVoter instance with prefetched data
    - target_type: 'person' or 'election_voter' string

    Returns (None, None) if the assignment has no valid target.
    """
    if assignment.election_voter_id:
        try:
            target = ElectionVoter.objects.prefetch_related(
                "phone_numbers",
                "addresses",
                Prefetch(
                    "contact_attempts",
                    queryset=ContactAttempt.objects.filter(effort=effort).order_by(
                        "-created_at"
                    )[:5],
                    to_attr="effort_attempts",
                ),
            ).get(pk=assignment.election_voter_id)
            return target, "election_voter"
        except ElectionVoter.DoesNotExist:
            pass
    elif assignment.person_id:
        try:
            target = (
                Person.objects.select_related("voter_record")
                .prefetch_related(
                    "phone_numbers",
                    "addresses",
                    Prefetch(
                        "contact_attempts",
                        queryset=ContactAttempt.objects.filter(effort=effort).order_by(
                            "-created_at"
                        )[:5],
                        to_attr="effort_attempts",
                    ),
                )
                .get(pk=assignment.person_id)
            )
            return target, "person"
        except Person.DoesNotExist:
            pass
    return None, None


def get_session_stats(effort):
    """Get progress stats for calling session."""
    stats = EffortAssignment.objects.filter(effort=effort).aggregate(
        total=Count("id"),
        pending=Count("id", filter=Q(status=EffortAssignment.Status.PENDING)),
        in_progress=Count("id", filter=Q(status=EffortAssignment.Status.IN_PROGRESS)),
        completed=Count("id", filter=Q(status=EffortAssignment.Status.COMPLETED)),
    )

    total = stats["total"] or 1
    stats["percentage"] = round((stats["completed"] / total) * 100, 1) if total else 0
    stats["remaining"] = stats["pending"] + stats["in_progress"]

    return stats


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance between two points on Earth in miles."""
    R = 3959  # Earth's radius in miles

    lat1, lon1, lat2, lon2 = map(
        radians, [float(lat1), float(lon1), float(lat2), float(lon2)]
    )

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c


def get_next_assignment_by_distance(effort, user, user_lat, user_lon):
    """Get next uncontacted person sorted by distance from user location.

    Uses GeoDjango's Distance function for database-level spatial sorting
    when spatial fields are available, with fallback to haversine calculation.
    """
    # Release stale locks (>10 min)
    stale_threshold = timezone.now() - timedelta(minutes=10)
    EffortAssignment.objects.filter(
        effort=effort,
        status=EffortAssignment.Status.IN_PROGRESS,
        locked_at__lt=stale_threshold,
    ).update(
        status=EffortAssignment.Status.PENDING,
        locked_by=None,
        locked_at=None,
    )

    # Create user's location as a Point
    user_location = Point(float(user_lon), float(user_lat), srid=4326)

    with transaction.atomic():
        # First try: Use GeoDjango Distance with PointField (preferred)
        assignments_with_location = (
            EffortAssignment.objects.select_for_update(skip_locked=True)
            .filter(
                effort=effort,
                status=EffortAssignment.Status.PENDING,
                person__voter_record__location__isnull=False,
            )
            .annotate(
                distance=Distance("person__voter_record__location", user_location)
            )
            .order_by("distance")
            .select_related("person__voter_record")
            .first()
        )

        if assignments_with_location:
            assignment = assignments_with_location
            assignment.status = EffortAssignment.Status.IN_PROGRESS
            assignment.locked_by = user
            assignment.locked_at = timezone.now()
            assignment.save(update_fields=["status", "locked_by", "locked_at"])
            return assignment

        # Second try: Fallback to legacy lat/lon fields with Python sorting
        assignments_with_coords = (
            EffortAssignment.objects.select_for_update(skip_locked=True)
            .filter(
                effort=effort,
                status=EffortAssignment.Status.PENDING,
                person__voter_record__latitude__isnull=False,
                person__voter_record__longitude__isnull=False,
            )
            .select_related("person__voter_record")[:50]
        )

        # Calculate distances and sort in Python
        candidates = []
        for assignment in assignments_with_coords:
            vr = assignment.person.voter_record
            distance = haversine_distance(user_lat, user_lon, vr.latitude, vr.longitude)
            candidates.append((distance, assignment))

        candidates.sort(key=lambda x: x[0])

        if candidates:
            _, assignment = candidates[0]
            assignment.status = EffortAssignment.Status.IN_PROGRESS
            assignment.locked_by = user
            assignment.locked_at = timezone.now()
            assignment.save(update_fields=["status", "locked_by", "locked_at"])
            return assignment

        # Final fallback: get any pending assignment without coordinates
        assignment = (
            EffortAssignment.objects.select_for_update(skip_locked=True)
            .filter(effort=effort, status=EffortAssignment.Status.PENDING)
            .first()
        )

        if assignment:
            assignment.status = EffortAssignment.Status.IN_PROGRESS
            assignment.locked_by = user
            assignment.locked_at = timezone.now()
            assignment.save(update_fields=["status", "locked_by", "locked_at"])

    return assignment


def get_nearest_assignments(effort, user_lat, user_lon, limit=5):
    """Get the N nearest pending assignments sorted by distance.

    Unlike get_next_assignment_by_distance(), this does NOT lock assignments.
    They remain available for other users until explicitly selected.

    Handles both Person-based and ElectionVoter-based assignments depending
    on whether the effort has an associated election.

    Returns a list of dicts with keys:
    - assignment: The EffortAssignment instance
    - target: The Person or ElectionVoter instance
    - target_type: 'person' or 'election_voter'
    - distance: Distance in miles from user location
    - primary_address: The home/primary address
    - previous_attempts: List of ContactAttempt instances for this effort
    """
    # Release stale locks (>10 min)
    stale_threshold = timezone.now() - timedelta(minutes=10)
    EffortAssignment.objects.filter(
        effort=effort,
        status=EffortAssignment.Status.IN_PROGRESS,
        locked_at__lt=stale_threshold,
    ).update(
        status=EffortAssignment.Status.PENDING,
        locked_by=None,
        locked_at=None,
    )

    user_location = Point(float(user_lon), float(user_lat), srid=4326)
    results = []

    # Determine if this is an election-based or person-based effort
    if effort.election_id:
        # ElectionVoter-based assignments
        # Try with GeoDjango PointField first
        assignments = list(
            EffortAssignment.objects.filter(
                effort=effort,
                status=EffortAssignment.Status.PENDING,
                election_voter__location__isnull=False,
            )
            .annotate(distance=Distance("election_voter__location", user_location))
            .order_by("distance")
            .select_related("election_voter")
            .prefetch_related(
                "election_voter__addresses",
                "election_voter__phone_numbers",
            )[:limit]
        )

        for assignment in assignments:
            ev = assignment.election_voter
            # Get distance in miles
            dist_miles = (
                assignment.distance.mi if hasattr(assignment, "distance") else None
            )

            # Get primary address
            primary_address = ev.addresses.filter(type="home").first()
            if not primary_address:
                primary_address = ev.addresses.first()

            # Get previous attempts
            previous_attempts = list(
                ContactAttempt.objects.filter(
                    effort=effort, election_voter=ev
                ).order_by("-created_at")[:5]
            )

            results.append(
                {
                    "assignment": assignment,
                    "target": ev,
                    "target_type": "election_voter",
                    "distance": dist_miles,
                    "primary_address": primary_address,
                    "previous_attempts": previous_attempts,
                }
            )

        # If we don't have enough, try fallback to lat/lon fields
        if len(results) < limit:
            existing_ids = [r["assignment"].pk for r in results]
            fallback_assignments = list(
                EffortAssignment.objects.filter(
                    effort=effort,
                    status=EffortAssignment.Status.PENDING,
                    election_voter__latitude__isnull=False,
                    election_voter__longitude__isnull=False,
                )
                .exclude(pk__in=existing_ids)
                .select_related("election_voter")
                .prefetch_related(
                    "election_voter__addresses",
                    "election_voter__phone_numbers",
                )[: (limit - len(results)) * 2]
            )

            fallback_with_distance = []
            for assignment in fallback_assignments:
                ev = assignment.election_voter
                dist_miles = haversine_distance(
                    user_lat, user_lon, float(ev.latitude), float(ev.longitude)
                )
                fallback_with_distance.append((dist_miles, assignment, ev))

            fallback_with_distance.sort(key=lambda x: x[0])

            for dist_miles, assignment, ev in fallback_with_distance[
                : limit - len(results)
            ]:
                primary_address = ev.addresses.filter(type="home").first()
                if not primary_address:
                    primary_address = ev.addresses.first()

                previous_attempts = list(
                    ContactAttempt.objects.filter(
                        effort=effort, election_voter=ev
                    ).order_by("-created_at")[:5]
                )

                results.append(
                    {
                        "assignment": assignment,
                        "target": ev,
                        "target_type": "election_voter",
                        "distance": dist_miles,
                        "primary_address": primary_address,
                        "previous_attempts": previous_attempts,
                    }
                )

    else:
        # Person-based assignments
        # Try with GeoDjango PointField first
        assignments = list(
            EffortAssignment.objects.filter(
                effort=effort,
                status=EffortAssignment.Status.PENDING,
                person__voter_record__location__isnull=False,
            )
            .annotate(
                distance=Distance("person__voter_record__location", user_location)
            )
            .order_by("distance")
            .select_related("person__voter_record")
            .prefetch_related(
                "person__addresses",
                "person__phone_numbers",
            )[:limit]
        )

        for assignment in assignments:
            person = assignment.person
            dist_miles = (
                assignment.distance.mi if hasattr(assignment, "distance") else None
            )

            primary_address = person.addresses.filter(type="home").first()
            if not primary_address:
                primary_address = person.addresses.first()

            previous_attempts = list(
                ContactAttempt.objects.filter(effort=effort, person=person).order_by(
                    "-created_at"
                )[:5]
            )

            results.append(
                {
                    "assignment": assignment,
                    "target": person,
                    "target_type": "person",
                    "distance": dist_miles,
                    "primary_address": primary_address,
                    "previous_attempts": previous_attempts,
                }
            )

        # Fallback to lat/lon fields if needed
        if len(results) < limit:
            existing_ids = [r["assignment"].pk for r in results]
            fallback_assignments = list(
                EffortAssignment.objects.filter(
                    effort=effort,
                    status=EffortAssignment.Status.PENDING,
                    person__voter_record__latitude__isnull=False,
                    person__voter_record__longitude__isnull=False,
                )
                .exclude(pk__in=existing_ids)
                .select_related("person__voter_record")
                .prefetch_related(
                    "person__addresses",
                    "person__phone_numbers",
                )[: (limit - len(results)) * 2]
            )

            fallback_with_distance = []
            for assignment in fallback_assignments:
                vr = assignment.person.voter_record
                dist_miles = haversine_distance(
                    user_lat, user_lon, float(vr.latitude), float(vr.longitude)
                )
                fallback_with_distance.append((dist_miles, assignment))

            fallback_with_distance.sort(key=lambda x: x[0])

            for dist_miles, assignment in fallback_with_distance[
                : limit - len(results)
            ]:
                person = assignment.person
                primary_address = person.addresses.filter(type="home").first()
                if not primary_address:
                    primary_address = person.addresses.first()

                previous_attempts = list(
                    ContactAttempt.objects.filter(
                        effort=effort, person=person
                    ).order_by("-created_at")[:5]
                )

                results.append(
                    {
                        "assignment": assignment,
                        "target": person,
                        "target_type": "person",
                        "distance": dist_miles,
                        "primary_address": primary_address,
                        "previous_attempts": previous_attempts,
                    }
                )

    # Sort final results by distance
    results.sort(
        key=lambda x: x["distance"] if x["distance"] is not None else float("inf")
    )

    return results[:limit]


@login_required
def calling_session(request, pk):
    """Main calling session page."""
    campaign = get_object_or_404(ContactEffort, pk=pk)
    stats = get_session_stats(campaign)

    return render(
        request,
        "civicpulse/campaigns/calling_session.html",
        {"campaign": campaign, "stats": stats},
    )


@login_required
def calling_next(request, pk):
    """Get next person to call (HTMX partial)."""
    campaign = get_object_or_404(ContactEffort, pk=pk)

    # First check if user already has a locked assignment
    assignment = EffortAssignment.objects.filter(
        effort=campaign,
        status=EffortAssignment.Status.IN_PROGRESS,
        locked_by=request.user,
    ).first()

    # If not, get a new one
    if not assignment:
        assignment = get_next_assignment(campaign, request.user)

    if not assignment:
        stats = get_session_stats(campaign)
        return render(
            request,
            "civicpulse/campaigns/partials/_session_complete.html",
            {"campaign": campaign, "stats": stats},
        )

    # Get target (Person or ElectionVoter)
    target, target_type = get_assignment_target_with_details(assignment, campaign)
    if not target:
        # Invalid assignment (target deleted) - skip and get next
        assignment.status = EffortAssignment.Status.COMPLETED
        assignment.locked_by = None
        assignment.locked_at = None
        assignment.save(update_fields=["status", "locked_by", "locked_at"])
        return calling_next(request, pk)

    form = ContactAttemptForm()
    stats = get_session_stats(campaign)

    # Get primary phone (works for both Person and ElectionVoter)
    primary_phone = target.phone_numbers.filter(is_primary=True).first()
    if not primary_phone:
        primary_phone = target.phone_numbers.first()

    return render(
        request,
        "civicpulse/campaigns/partials/_person_card.html",
        {
            "campaign": campaign,
            "assignment": assignment,
            "target": target,
            "target_type": target_type,
            "person": target,  # Backward compatibility for template
            "primary_phone": primary_phone,
            "form": form,
            "stats": stats,
        },
    )


@login_required
def calling_log(request, pk):
    """Log outcome and get next person (HTMX)."""
    campaign = get_object_or_404(ContactEffort, pk=pk)

    if request.method == "POST":
        assignment_id = request.POST.get("assignment_id")
        assignment = get_object_or_404(
            EffortAssignment, pk=assignment_id, effort=campaign, locked_by=request.user
        )

        form = ContactAttemptForm(request.POST)
        if form.is_valid():
            attempt = form.save(commit=False)
            attempt.effort = campaign
            attempt.contacted_by = request.user
            # Set the correct target FK based on assignment type
            if assignment.election_voter_id:
                attempt.election_voter = assignment.election_voter
                attempt.person = None
            else:
                attempt.person = assignment.person
                attempt.election_voter = None
            attempt.save()

            # Check if terminal outcome
            if attempt.outcome in [o.value for o in ContactAttempt.TERMINAL_OUTCOMES]:
                assignment.status = EffortAssignment.Status.COMPLETED
            else:
                assignment.status = EffortAssignment.Status.PENDING

            assignment.locked_by = None
            assignment.locked_at = None
            assignment.save()

    # Get next person
    return calling_next(request, pk)


@login_required
def calling_skip(request, pk):
    """Skip current person and get next (HTMX)."""
    campaign = get_object_or_404(ContactEffort, pk=pk)

    if request.method == "POST":
        assignment_id = request.POST.get("assignment_id")
        EffortAssignment.objects.filter(
            pk=assignment_id, effort=campaign, locked_by=request.user
        ).update(
            status=EffortAssignment.Status.PENDING,
            locked_by=None,
            locked_at=None,
        )

    return calling_next(request, pk)


@login_required
def calling_exit(request, pk):
    """Exit calling session, releasing current person back to pool."""
    campaign = get_object_or_404(ContactEffort, pk=pk)

    if request.method == "POST":
        assignment_id = request.POST.get("assignment_id")
        EffortAssignment.objects.filter(
            pk=assignment_id, effort=campaign, locked_by=request.user
        ).update(
            status=EffortAssignment.Status.PENDING,
            locked_by=None,
            locked_at=None,
        )

    return redirect("civicpulse:campaign_detail", pk=pk)


# =============================================================================
# Door Knocking Workflow Views (HTMX)
# =============================================================================


@login_required
def knocking_session(request, pk):
    """Main door knocking session page."""
    campaign = get_object_or_404(ContactEffort, pk=pk)
    stats = get_session_stats(campaign)

    # Check if user has location set in session
    has_location = request.session.get("knocker_location_set", False)
    user_lat = request.session.get("knocker_lat")
    user_lon = request.session.get("knocker_lon")

    return render(
        request,
        "civicpulse/campaigns/knocking_session.html",
        {
            "campaign": campaign,
            "stats": stats,
            "has_location": has_location,
            "user_lat": user_lat,
            "user_lon": user_lon,
        },
    )


@login_required
def knocking_list(request, pk):
    """Show list of 5 closest doors to knock on (HTMX partial)."""
    import json

    campaign = get_object_or_404(ContactEffort, pk=pk)

    user_lat = request.session.get("knocker_lat")
    user_lon = request.session.get("knocker_lon")

    if not user_lat or not user_lon:
        # No location - fall back to knocking_next which can handle this
        return knocking_next(request, pk)

    # Get 5 nearest pending assignments
    doors = get_nearest_assignments(campaign, user_lat, user_lon, limit=5)

    if not doors:
        stats = get_session_stats(campaign)
        return render(
            request,
            "civicpulse/campaigns/partials/_knocking_complete.html",
            {"campaign": campaign, "stats": stats},
        )

    # Add order numbers for map pins
    for i, door in enumerate(doors, start=1):
        door["order"] = i

    # Build GeoJSON for map markers
    map_features = []
    for door in doors:
        target = door["target"]
        target_type = door["target_type"]
        addr = door["primary_address"]

        # Get coordinates
        if target_type == "election_voter":
            lat = float(target.latitude) if target.latitude else None
            lon = float(target.longitude) if target.longitude else None
        else:
            vr = getattr(target, "voter_record", None)
            lat = float(vr.latitude) if vr and vr.latitude else None
            lon = float(vr.longitude) if vr and vr.longitude else None

        if lat and lon:
            map_features.append(
                {
                    "lat": lat,
                    "lon": lon,
                    "order": door["order"],
                    "name": target.full_name,
                    "address": (
                        f"{addr.street_address}, {addr.city}" if addr else "Unknown"
                    ),
                }
            )

    stats = get_session_stats(campaign)

    return render(
        request,
        "civicpulse/campaigns/partials/_doors_list.html",
        {
            "campaign": campaign,
            "doors": doors,
            "stats": stats,
            "user_lat": user_lat,
            "user_lon": user_lon,
            "doors_json": json.dumps(map_features),
        },
    )


@login_required
def knocking_select(request, pk):
    """Lock a specific assignment and show its address card (HTMX)."""
    campaign = get_object_or_404(ContactEffort, pk=pk)

    if request.method != "POST":
        return knocking_list(request, pk)

    assignment_id = request.POST.get("assignment_id")
    if not assignment_id:
        return knocking_list(request, pk)

    # Try to lock the assignment atomically
    with transaction.atomic():
        assignment = (
            EffortAssignment.objects.select_for_update(skip_locked=True)
            .filter(
                pk=assignment_id,
                effort=campaign,
                status=EffortAssignment.Status.PENDING,
            )
            .first()
        )

        if not assignment:
            # Assignment is either locked by another user, doesn't exist, or already completed
            return render(
                request,
                "civicpulse/campaigns/partials/_door_taken.html",
                {
                    "campaign": campaign,
                    "message": "This address was just claimed by another volunteer. Please select another.",
                },
            )

        # Lock the assignment
        assignment.status = EffortAssignment.Status.IN_PROGRESS
        assignment.locked_by = request.user
        assignment.locked_at = timezone.now()
        assignment.save(update_fields=["status", "locked_by", "locked_at"])

    # Get target details
    target, target_type = get_assignment_target_with_details(assignment, campaign)
    if not target:
        # Target was deleted - mark complete and return to list
        assignment.status = EffortAssignment.Status.COMPLETED
        assignment.locked_by = None
        assignment.locked_at = None
        assignment.save(update_fields=["status", "locked_by", "locked_at"])
        return knocking_list(request, pk)

    from .forms import DoorKnockAttemptForm

    form = DoorKnockAttemptForm()
    stats = get_session_stats(campaign)

    # Get primary address
    primary_address = target.addresses.filter(type="home").first()
    if not primary_address:
        primary_address = target.addresses.first()

    # Calculate distance
    distance = None
    user_lat = request.session.get("knocker_lat")
    user_lon = request.session.get("knocker_lon")

    target_lat = None
    target_lon = None
    if (
        target_type == "person"
        and hasattr(target, "voter_record")
        and target.voter_record
    ):
        target_lat = target.voter_record.latitude
        target_lon = target.voter_record.longitude
    elif target_type == "election_voter":
        target_lat = target.latitude
        target_lon = target.longitude

    if user_lat and user_lon and target_lat and target_lon:
        distance = haversine_distance(user_lat, user_lon, target_lat, target_lon)

    return render(
        request,
        "civicpulse/campaigns/partials/_address_card.html",
        {
            "campaign": campaign,
            "assignment": assignment,
            "target": target,
            "target_type": target_type,
            "person": target,  # Backward compatibility
            "primary_address": primary_address,
            "form": form,
            "stats": stats,
            "distance": distance,
            "show_back_to_list": True,  # Flag to show back button
        },
    )


@login_required
def knocking_set_location(request, pk):
    """Set user's current location for door knocking (HTMX)."""
    # Verify campaign exists
    get_object_or_404(ContactEffort, pk=pk)

    if request.method == "POST":
        lat = request.POST.get("latitude")
        lon = request.POST.get("longitude")

        if lat and lon:
            try:
                request.session["knocker_lat"] = float(lat)
                request.session["knocker_lon"] = float(lon)
                request.session["knocker_location_set"] = True
            except ValueError:
                pass

    # Return the doors list
    return knocking_list(request, pk)


@login_required
def knocking_next(request, pk):
    """Get next person to visit (HTMX partial), sorted by distance."""
    campaign = get_object_or_404(ContactEffort, pk=pk)

    # First check if user already has a locked assignment
    assignment = EffortAssignment.objects.filter(
        effort=campaign,
        status=EffortAssignment.Status.IN_PROGRESS,
        locked_by=request.user,
    ).first()

    # If not, get a new one
    if not assignment:
        user_lat = request.session.get("knocker_lat")
        user_lon = request.session.get("knocker_lon")

        if user_lat and user_lon:
            assignment = get_next_assignment_by_distance(
                campaign, request.user, user_lat, user_lon
            )
        else:
            # Fallback to regular assignment if no location
            assignment = get_next_assignment(campaign, request.user)

    if not assignment:
        stats = get_session_stats(campaign)
        return render(
            request,
            "civicpulse/campaigns/partials/_knocking_complete.html",
            {"campaign": campaign, "stats": stats},
        )

    # Get target (Person or ElectionVoter)
    target, target_type = get_assignment_target_with_details(assignment, campaign)
    if not target:
        # Invalid assignment (target deleted) - skip and get next
        assignment.status = EffortAssignment.Status.COMPLETED
        assignment.locked_by = None
        assignment.locked_at = None
        assignment.save(update_fields=["status", "locked_by", "locked_at"])
        return knocking_next(request, pk)

    from .forms import DoorKnockAttemptForm

    form = DoorKnockAttemptForm()
    stats = get_session_stats(campaign)

    # Get primary home address (works for both Person and ElectionVoter)
    primary_address = target.addresses.filter(type="home").first()
    if not primary_address:
        primary_address = target.addresses.first()

    # Calculate distance if we have coordinates
    distance = None
    user_lat = request.session.get("knocker_lat")
    user_lon = request.session.get("knocker_lon")

    # Check for coordinates - Person has voter_record, ElectionVoter has direct lat/lon
    target_lat = None
    target_lon = None
    if (
        target_type == "person"
        and hasattr(target, "voter_record")
        and target.voter_record
    ):
        target_lat = target.voter_record.latitude
        target_lon = target.voter_record.longitude
    elif target_type == "election_voter":
        target_lat = target.latitude
        target_lon = target.longitude

    if user_lat and user_lon and target_lat and target_lon:
        distance = haversine_distance(user_lat, user_lon, target_lat, target_lon)

    return render(
        request,
        "civicpulse/campaigns/partials/_address_card.html",
        {
            "campaign": campaign,
            "assignment": assignment,
            "target": target,
            "target_type": target_type,
            "person": target,  # Backward compatibility
            "primary_address": primary_address,
            "form": form,
            "stats": stats,
            "distance": distance,
        },
    )


@login_required
def knocking_log(request, pk):
    """Log door knock outcome and get next person (HTMX)."""
    campaign = get_object_or_404(ContactEffort, pk=pk)

    if request.method == "POST":
        assignment_id = request.POST.get("assignment_id")
        assignment = get_object_or_404(
            EffortAssignment, pk=assignment_id, effort=campaign, locked_by=request.user
        )

        from .forms import DoorKnockAttemptForm

        form = DoorKnockAttemptForm(request.POST)
        if form.is_valid():
            attempt = form.save(commit=False)
            attempt.effort = campaign
            attempt.contacted_by = request.user
            attempt.contact_type = ContactAttempt.ContactType.DOOR_KNOCK
            # Set the correct target FK based on assignment type
            if assignment.election_voter_id:
                attempt.election_voter = assignment.election_voter
                attempt.person = None
                # Set voter_address_visited if address was visited
                voter_address = assignment.election_voter.addresses.filter(
                    type="home"
                ).first()
                if not voter_address:
                    voter_address = assignment.election_voter.addresses.first()
                attempt.voter_address_visited = voter_address
            else:
                attempt.person = assignment.person
                attempt.election_voter = None
                # Set address_visited if address was visited
                address = assignment.person.addresses.filter(type="home").first()
                if not address:
                    address = assignment.person.addresses.first()
                attempt.address_visited = address
            attempt.save()

            # Check if terminal outcome
            if attempt.outcome in [o.value for o in ContactAttempt.TERMINAL_OUTCOMES]:
                assignment.status = EffortAssignment.Status.COMPLETED
            else:
                assignment.status = EffortAssignment.Status.PENDING

            assignment.locked_by = None
            assignment.locked_at = None
            assignment.save()

    # Return to doors list
    return knocking_list(request, pk)


@login_required
def knocking_skip(request, pk):
    """Skip current address and get next (HTMX)."""
    campaign = get_object_or_404(ContactEffort, pk=pk)

    if request.method == "POST":
        assignment_id = request.POST.get("assignment_id")
        EffortAssignment.objects.filter(
            pk=assignment_id, effort=campaign, locked_by=request.user
        ).update(
            status=EffortAssignment.Status.PENDING,
            locked_by=None,
            locked_at=None,
        )

    # Return to doors list
    return knocking_list(request, pk)


@login_required
def knocking_exit(request, pk):
    """Exit knocking session, releasing current person back to pool."""
    campaign = get_object_or_404(ContactEffort, pk=pk)

    if request.method == "POST":
        assignment_id = request.POST.get("assignment_id")
        EffortAssignment.objects.filter(
            pk=assignment_id, effort=campaign, locked_by=request.user
        ).update(
            status=EffortAssignment.Status.PENDING,
            locked_by=None,
            locked_at=None,
        )

    return redirect("civicpulse:campaign_detail", pk=pk)


# =============================================================================
# HTMX Helper Views
# =============================================================================


@login_required
def campaign_candidates(request):
    """Return candidate dropdown options for a given election (HTMX)."""
    election_id = request.GET.get("election")

    if election_id:
        candidates = Candidate.objects.filter(election_id=election_id).select_related(
            "person"
        )
    else:
        candidates = Candidate.objects.none()

    return render(
        request,
        "civicpulse/campaigns/partials/_candidate_select.html",
        {"candidates": candidates},
    )


# =============================================================================
# Voter Import Views
# =============================================================================


@login_required
def voter_import(request, pk):
    """Handle voter CSV upload and trigger async import."""
    import os
    import uuid as uuid_module

    from django.conf import settings

    election = get_object_or_404(Election, pk=pk)

    if request.method == "POST":
        form = VoterImportForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = form.cleaned_data["csv_file"]

            # Create imports directory if it doesn't exist
            import_dir = os.path.join(settings.MEDIA_ROOT, "imports")
            os.makedirs(import_dir, exist_ok=True)

            # Save file to temporary location
            temp_filename = f"{uuid_module.uuid4()}_{csv_file.name}"
            temp_path = os.path.join(import_dir, temp_filename)

            with open(temp_path, "wb+") as dest:
                for chunk in csv_file.chunks():
                    dest.write(chunk)

            # Create ImportJob record
            import_job = ImportJob.objects.create(
                election=election,
                file_name=csv_file.name,
                file_path=temp_path,
                created_by=request.user,
            )

            # Dispatch Celery task
            from .tasks import process_voter_import

            task = process_voter_import.delay(str(import_job.pk))

            # Update job with task ID
            import_job.task_id = task.id
            import_job.save(update_fields=["task_id"])

            return redirect(
                "civicpulse:import_status", pk=election.pk, job_pk=import_job.pk
            )
    else:
        form = VoterImportForm()

    # Get recent import history for this election
    recent_imports = ImportJob.objects.filter(election=election).order_by(
        "-created_at"
    )[:5]

    return render(
        request,
        "civicpulse/imports/voter_import.html",
        {
            "election": election,
            "form": form,
            "recent_imports": recent_imports,
        },
    )


@login_required
def import_status(request, pk, job_pk):
    """Display import job status with real-time progress."""
    election = get_object_or_404(Election, pk=pk)
    import_job = get_object_or_404(ImportJob, pk=job_pk, election=election)

    return render(
        request,
        "civicpulse/imports/import_status.html",
        {
            "election": election,
            "import_job": import_job,
        },
    )


@login_required
def import_progress(request, pk, job_pk):
    """HTMX endpoint for polling import progress."""
    election = get_object_or_404(Election, pk=pk)
    import_job = get_object_or_404(ImportJob, pk=job_pk, election=election)

    return render(
        request,
        "civicpulse/imports/partials/_import_progress.html",
        {
            "election": election,
            "import_job": import_job,
        },
    )


# =============================================================================
# Spatial Query Helper Functions
# =============================================================================


def get_voters_within_radius(center_lat, center_lon, radius_miles, election=None):
    """
    Find voters within a given radius of a center point.

    Args:
        center_lat: Center latitude
        center_lon: Center longitude
        radius_miles: Search radius in miles
        election: Optional Election to filter by

    Returns:
        QuerySet of ElectionVoter or VoterRecord objects with distance annotation
    """
    center = Point(float(center_lon), float(center_lat), srid=4326)

    if election:
        return (
            ElectionVoter.objects.filter(
                election=election,
                location__isnull=False,
                location__distance_lte=(center, D(mi=radius_miles)),
            )
            .annotate(distance=Distance("location", center))
            .order_by("distance")
        )
    else:
        return (
            VoterRecord.objects.filter(
                location__isnull=False,
                location__distance_lte=(center, D(mi=radius_miles)),
            )
            .annotate(distance=Distance("location", center))
            .order_by("distance")
        )


def get_voters_in_district(district):
    """
    Find all voters whose location falls within a district boundary.

    Args:
        district: District model instance with MultiPolygonField boundary

    Returns:
        QuerySet of VoterRecord objects within the district
    """
    return VoterRecord.objects.filter(
        location__isnull=False,
        location__within=district.boundary,
    )


def get_election_voters_in_district(election, district):
    """
    Find election-specific voters within a district boundary.

    Args:
        election: Election instance
        district: District instance with boundary polygon

    Returns:
        QuerySet of ElectionVoter objects
    """
    return ElectionVoter.objects.filter(
        election=election,
        location__isnull=False,
        location__within=district.boundary,
    )


# =============================================================================
# GeoJSON API Endpoints
# =============================================================================


@login_required
def api_campaign_locations(request, pk):
    """
    Return voter locations for a campaign as GeoJSON FeatureCollection.

    Used by Leaflet maps to display voter markers.
    """
    campaign = get_object_or_404(ContactEffort, pk=pk)

    # Get assignments with voter location data
    assignments = (
        EffortAssignment.objects.filter(effort=campaign)
        .select_related("person__voter_record")
        .filter(person__voter_record__location__isnull=False)
    )

    features = []
    for assignment in assignments:
        vr = assignment.person.voter_record
        if vr.location:
            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [vr.location.x, vr.location.y],
                    },
                    "properties": {
                        "id": str(assignment.pk),
                        "person_id": str(assignment.person.pk),
                        "name": f"{assignment.person.first_name} {assignment.person.last_name}",
                        "status": assignment.status,
                    },
                }
            )

    return JsonResponse(
        {
            "type": "FeatureCollection",
            "features": features,
        }
    )


@login_required
def api_campaign_route(request, pk):
    """
    Return optimized walking route as GeoJSON LineString.

    Requires user location in query params (lat, lon).
    """
    campaign = get_object_or_404(ContactEffort, pk=pk)

    # Get user location from query params
    try:
        user_lat = float(request.GET.get("lat", 0))
        user_lon = float(request.GET.get("lon", 0))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid lat/lon parameters"}, status=400)

    if not user_lat or not user_lon:
        return JsonResponse(
            {"error": "lat and lon query parameters required"}, status=400
        )

    # Get pending assignments with locations
    from .services.routing import RouteOptimizer, Waypoint

    assignments = (
        EffortAssignment.objects.filter(
            effort=campaign,
            status=EffortAssignment.Status.PENDING,
        )
        .select_related("person__voter_record", "person__addresses")
        .filter(person__voter_record__location__isnull=False)[
            :50
        ]  # Limit for performance
    )

    # Build waypoints
    waypoints = []
    for assignment in assignments:
        vr = assignment.person.voter_record
        if vr.location:
            # Get address for display
            address = (
                assignment.person.addresses.filter(type="home").first()
                or assignment.person.addresses.first()
            )
            address_str = ""
            if address:
                address_str = f"{address.street_address}, {address.city}"

            waypoints.append(
                Waypoint(
                    id=str(assignment.pk),
                    latitude=vr.location.y,
                    longitude=vr.location.x,
                    address=address_str,
                    person_name=f"{assignment.person.first_name} {assignment.person.last_name}",
                )
            )

    if not waypoints:
        return JsonResponse(
            {
                "type": "FeatureCollection",
                "features": [],
                "properties": {"message": "No waypoints with coordinates found"},
            }
        )

    # Get optimized route
    optimizer = RouteOptimizer(str(campaign.pk), request.user.id)
    route = optimizer.get_optimized_route(waypoints, user_lat, user_lon)

    # Build GeoJSON response
    route_coords = []
    if route.geometry:
        route_coords = [[lon, lat] for lat, lon in route.geometry]
    else:
        # Build simple line from waypoints
        route_coords = [[user_lon, user_lat]]
        for wp in route.waypoints:
            route_coords.append([float(wp.longitude), float(wp.latitude)])

    features = [
        {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": route_coords,
            },
            "properties": {
                "source": route.source,
                "total_distance_miles": route.total_distance_miles,
                "total_duration_minutes": route.total_duration_minutes,
            },
        }
    ]

    # Add waypoint markers
    for i, wp in enumerate(route.waypoints):
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(wp.longitude), float(wp.latitude)],
                },
                "properties": {
                    "id": wp.id,
                    "order": i + 1,
                    "name": wp.person_name,
                    "address": wp.address,
                },
            }
        )

    return JsonResponse(
        {
            "type": "FeatureCollection",
            "features": features,
            "properties": {
                "source": route.source,
                "total_distance_miles": round(route.total_distance_miles, 2),
                "total_duration_minutes": round(route.total_duration_minutes, 1),
                "waypoint_count": len(route.waypoints),
            },
        }
    )


@login_required
def api_election_voter_distribution(request, pk):
    """
    Return voter distribution for an election as GeoJSON.

    Supports optional filtering by party, likelihood, etc.
    """
    election = get_object_or_404(Election, pk=pk)

    voters = ElectionVoter.objects.filter(
        election=election,
        location__isnull=False,
    )

    # Apply filters
    party = request.GET.get("party")
    if party:
        voters = voters.filter(registered_party__iexact=party)

    likelihood = request.GET.get("likelihood")
    if likelihood == "high":
        voters = voters.filter(likelihood_general__regex=r"^[7-9][0-9]%$|^100%$")
    elif likelihood == "medium":
        voters = voters.filter(likelihood_general__regex=r"^[4-6][0-9]%$")
    elif likelihood == "low":
        voters = voters.filter(likelihood_general__regex=r"^[0-3]?[0-9]%$")

    # Limit for performance
    limit = min(int(request.GET.get("limit", 1000)), 5000)
    voters = voters[:limit]

    features = []
    for voter in voters:
        if voter.location:
            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [voter.location.x, voter.location.y],
                    },
                    "properties": {
                        "id": str(voter.pk),
                        "name": f"{voter.first_name} {voter.last_name}",
                        "party": voter.registered_party or "Unknown",
                        "likelihood": voter.likelihood_general or "",
                    },
                }
            )

    return JsonResponse(
        {
            "type": "FeatureCollection",
            "features": features,
            "properties": {
                "election": str(election),
                "count": len(features),
            },
        }
    )


@login_required
def api_districts(request):
    """
    Return district boundaries as GeoJSON.

    Supports filtering by type and state.
    """
    districts = District.objects.all()

    # Apply filters
    district_type = request.GET.get("type")
    if district_type:
        districts = districts.filter(district_type=district_type)

    state = request.GET.get("state")
    if state:
        districts = districts.filter(state__iexact=state)

    features = []
    for district in districts:
        if district.boundary:
            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "MultiPolygon",
                        "coordinates": district.boundary.coords,
                    },
                    "properties": {
                        "id": str(district.pk),
                        "name": district.name,
                        "district_type": district.district_type,
                        "identifier": district.identifier,
                        "state": district.state,
                    },
                }
            )

    return JsonResponse(
        {
            "type": "FeatureCollection",
            "features": features,
        }
    )


@login_required
def api_election_districts(request, pk):
    """
    Return GeoJSON of all districts linked to an election.

    Used by election detail page to display district boundaries on the map.
    """
    election = get_object_or_404(Election, pk=pk)

    districts = election.districts.all()

    features = []
    for district in districts:
        if district.boundary:
            features.append(
                {
                    "type": "Feature",
                    "geometry": json.loads(district.boundary.geojson),
                    "properties": {
                        "id": str(district.pk),
                        "name": district.name,
                        "district_type": district.get_district_type_display(),
                        "identifier": district.identifier,
                        "state": district.state,
                    },
                }
            )

    return JsonResponse(
        {
            "type": "FeatureCollection",
            "features": features,
        }
    )


# =============================================================================
# Stripe Connect OAuth Views
# =============================================================================


@login_required
def stripe_connect_candidate(request, pk):
    """
    Start Stripe OAuth flow for a Candidate.

    Stores candidate reference in session and redirects to Stripe's OAuth page.
    """
    from secrets import token_urlsafe
    from urllib.parse import urlencode

    from django.contrib import messages
    from django.urls import reverse

    from .conf import stripe_settings
    from .models import Candidate

    candidate = get_object_or_404(Candidate, pk=pk)

    # Check if Stripe is configured
    if not stripe_settings.is_configured:
        messages.error(request, "Stripe Connect is not configured.")
        return redirect("civicpulse:candidate_detail", pk=pk)

    # Check if already connected
    if hasattr(candidate, "stripe_connection") and candidate.stripe_connection:
        messages.warning(request, "This candidate already has a Stripe connection.")
        return redirect("civicpulse:candidate_detail", pk=pk)

    # Store owner info in session for callback
    request.session["stripe_owner_type"] = "candidate"
    request.session["stripe_owner_pk"] = str(pk)

    # Generate state token for CSRF protection
    state = token_urlsafe(32)
    request.session["stripe_oauth_state"] = state

    # Build OAuth URL
    callback_url = request.build_absolute_uri(
        reverse("civicpulse:stripe_oauth_callback")
    )
    params = {
        "response_type": "code",
        "client_id": stripe_settings.CLIENT_ID,
        "scope": stripe_settings.OAUTH_SCOPE,
        "redirect_uri": callback_url,
        "state": state,
    }

    oauth_url = f"https://connect.stripe.com/oauth/authorize?{urlencode(params)}"
    return redirect(oauth_url)


@login_required
def stripe_connect_campaign(request, pk):
    """
    Start Stripe OAuth flow for a Campaign.

    Stores campaign reference in session and redirects to Stripe's OAuth page.
    """
    from secrets import token_urlsafe
    from urllib.parse import urlencode

    from django.contrib import messages
    from django.urls import reverse

    from .conf import stripe_settings

    campaign = get_object_or_404(Campaign, pk=pk)

    # Check if Stripe is configured
    if not stripe_settings.is_configured:
        messages.error(request, "Stripe Connect is not configured.")
        return redirect("civicpulse:org_campaign_detail", pk=pk)

    # Check if already connected
    if hasattr(campaign, "stripe_connection") and campaign.stripe_connection:
        messages.warning(request, "This campaign already has a Stripe connection.")
        return redirect("civicpulse:org_campaign_detail", pk=pk)

    # Store owner info in session for callback
    request.session["stripe_owner_type"] = "campaign"
    request.session["stripe_owner_pk"] = str(pk)

    # Generate state token for CSRF protection
    state = token_urlsafe(32)
    request.session["stripe_oauth_state"] = state

    # Build OAuth URL
    callback_url = request.build_absolute_uri(
        reverse("civicpulse:stripe_oauth_callback")
    )
    params = {
        "response_type": "code",
        "client_id": stripe_settings.CLIENT_ID,
        "scope": stripe_settings.OAUTH_SCOPE,
        "redirect_uri": callback_url,
        "state": state,
    }

    oauth_url = f"https://connect.stripe.com/oauth/authorize?{urlencode(params)}"
    return redirect(oauth_url)


@login_required
def stripe_oauth_callback(request):
    """
    Handle Stripe OAuth callback.

    Validates state, exchanges code for tokens, creates StripeConnection.
    """
    import stripe
    from django.contrib import messages

    from .conf import stripe_settings
    from .services.encryption import get_encryption_service

    # Validate state parameter
    state = request.GET.get("state")
    expected_state = request.session.get("stripe_oauth_state")

    if not state or state != expected_state:
        messages.error(request, "Invalid OAuth state. Please try again.")
        return redirect("civicpulse:index")

    # Check for OAuth errors
    error = request.GET.get("error")
    if error:
        error_description = request.GET.get("error_description", "Unknown error")
        messages.error(request, f"Stripe authorization failed: {error_description}")
        return _stripe_redirect_to_owner(request)

    # Get authorization code
    code = request.GET.get("code")
    if not code:
        messages.error(request, "No authorization code received from Stripe.")
        return _stripe_redirect_to_owner(request)

    # Retrieve owner info from session
    owner_type = request.session.get("stripe_owner_type")
    owner_pk = request.session.get("stripe_owner_pk")

    if not owner_type or not owner_pk:
        messages.error(request, "Session expired. Please try connecting again.")
        return redirect("civicpulse:index")

    # Exchange code for tokens
    try:
        stripe.api_key = stripe_settings.SECRET_KEY
        response = stripe.OAuth.token(
            grant_type="authorization_code",
            code=code,
        )
    except stripe.oauth_error.OAuthError as e:
        messages.error(request, f"Failed to connect Stripe account: {e.user_message}")
        return _stripe_redirect_to_owner(request)
    except stripe.error.StripeError as e:
        messages.error(request, f"Stripe error: {str(e)}")
        return _stripe_redirect_to_owner(request)

    # Extract tokens and account info
    access_token = response.get("access_token")
    refresh_token = response.get("refresh_token")
    stripe_user_id = response.get("stripe_user_id")
    livemode = response.get("livemode", False)

    if not access_token or not stripe_user_id:
        messages.error(request, "Invalid response from Stripe.")
        return _stripe_redirect_to_owner(request)

    # Encrypt tokens before storage
    encryption = get_encryption_service()
    encrypted_access_token = encryption.encrypt_token(access_token)
    encrypted_refresh_token = encryption.encrypt_token(refresh_token) if refresh_token else ""

    # Create StripeConnection for the appropriate owner
    try:
        if owner_type == "candidate":
            candidate = get_object_or_404(Candidate, pk=owner_pk)
            StripeConnection.objects.create(
                candidate=candidate,
                stripe_user_id=stripe_user_id,
                access_token_encrypted=encrypted_access_token,
                refresh_token_encrypted=encrypted_refresh_token,
                livemode=livemode,
                status=StripeConnection.Status.ACTIVE,
            )
            redirect_url = "civicpulse:candidate_detail"
        elif owner_type == "campaign":
            campaign = get_object_or_404(Campaign, pk=owner_pk)
            StripeConnection.objects.create(
                campaign=campaign,
                stripe_user_id=stripe_user_id,
                access_token_encrypted=encrypted_access_token,
                refresh_token_encrypted=encrypted_refresh_token,
                livemode=livemode,
                status=StripeConnection.Status.ACTIVE,
            )
            redirect_url = "civicpulse:org_campaign_detail"
        else:
            messages.error(request, "Invalid owner type.")
            return redirect("civicpulse:index")

    except Exception as exc:
        messages.error(request, f"Failed to save connection: {exc}")
        return _stripe_redirect_to_owner(request)

    # Clear session data
    for key in ["stripe_owner_type", "stripe_owner_pk", "stripe_oauth_state"]:
        request.session.pop(key, None)

    messages.success(request, "Stripe account connected successfully!")
    return redirect(redirect_url, pk=owner_pk)


def _stripe_redirect_to_owner(request):
    """Helper to redirect back to owner detail page."""
    owner_type = request.session.get("stripe_owner_type")
    owner_pk = request.session.get("stripe_owner_pk")

    # Clear session data
    for key in ["stripe_owner_type", "stripe_owner_pk", "stripe_oauth_state"]:
        request.session.pop(key, None)

    if owner_type == "candidate" and owner_pk:
        return redirect("civicpulse:candidate_detail", pk=owner_pk)
    elif owner_type == "campaign" and owner_pk:
        return redirect("civicpulse:org_campaign_detail", pk=owner_pk)
    else:
        return redirect("civicpulse:index")


@login_required
def stripe_disconnect(request, connection_pk):
    """
    Disconnect a Stripe account.

    GET: Show confirmation page
    POST: Revoke access and delete connection
    """
    import stripe
    from django.contrib import messages

    from .conf import stripe_settings

    connection = get_object_or_404(StripeConnection, pk=connection_pk)

    # Determine owner for redirect
    if connection.candidate:
        owner = connection.candidate
        owner_type = "candidate"
        redirect_url = "civicpulse:candidate_detail"
        owner_pk = owner.pk
    elif connection.campaign:
        owner = connection.campaign
        owner_type = "campaign"
        redirect_url = "civicpulse:org_campaign_detail"
        owner_pk = owner.pk
    else:
        messages.error(request, "Invalid connection.")
        return redirect("civicpulse:index")

    if request.method == "POST":
        # Revoke access at Stripe
        try:
            stripe.api_key = stripe_settings.SECRET_KEY
            stripe.OAuth.deauthorize(
                client_id=stripe_settings.CLIENT_ID,
                stripe_user_id=connection.stripe_user_id,
            )
        except stripe.error.StripeError:
            # Log error but continue - connection may already be revoked
            pass

        # Delete local connection record
        connection.delete()

        messages.success(request, "Stripe account disconnected successfully.")
        return redirect(redirect_url, pk=owner_pk)

    # GET: Show confirmation page
    return render(
        request,
        "civicpulse/stripe/disconnect_confirm.html",
        {
            "connection": connection,
            "owner": owner,
            "owner_type": owner_type,
        },
    )


def _render_donations(request, connection, owner, owner_type):
    """
    Shared helper for rendering donation lists.

    Returns template context with donations, stats, and pagination.
    """
    from django.core.paginator import Paginator
    from django.db.models import Sum

    # Get donations for this connection
    donations = Donation.objects.filter(connection=connection).order_by("-created_at")

    # Calculate stats
    stats = donations.filter(status=Donation.Status.SUCCEEDED).aggregate(
        total_amount=Sum("amount_cents"),
        total_count=Count("id"),
    )
    total_amount_dollars = (stats["total_amount"] or 0) / 100
    total_count = stats["total_count"] or 0

    # Date range
    first_donation = donations.order_by("created_at").first()
    last_donation = donations.order_by("-created_at").first()

    # Paginate donations
    paginator = Paginator(donations, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Get latest sync job
    latest_sync = connection.sync_jobs.order_by("-created_at").first()

    return {
        "connection": connection,
        "owner": owner,
        "owner_type": owner_type,
        "donations": page_obj,
        "page_obj": page_obj,
        "total_amount": total_amount_dollars,
        "total_count": total_count,
        "first_donation": first_donation,
        "last_donation": last_donation,
        "latest_sync": latest_sync,
    }


@login_required
def candidate_donations(request, pk):
    """
    View donations for a candidate's connected Stripe account.
    """
    from django.contrib import messages

    candidate = get_object_or_404(
        Candidate.objects.select_related("stripe_connection"), pk=pk
    )

    if not hasattr(candidate, "stripe_connection") or not candidate.stripe_connection:
        messages.warning(request, "No Stripe account connected to this candidate.")
        return redirect("civicpulse:candidate_detail", pk=pk)

    context = _render_donations(
        request,
        candidate.stripe_connection,
        candidate,
        "candidate",
    )

    return render(request, "civicpulse/stripe/donations.html", context)


@login_required
def campaign_donations(request, pk):
    """
    View donations for a campaign's connected Stripe account.
    """
    from django.contrib import messages

    campaign = get_object_or_404(
        Campaign.objects.select_related("stripe_connection"), pk=pk
    )

    if not hasattr(campaign, "stripe_connection") or not campaign.stripe_connection:
        messages.warning(request, "No Stripe account connected to this campaign.")
        return redirect("civicpulse:org_campaign_detail", pk=pk)

    context = _render_donations(
        request,
        campaign.stripe_connection,
        campaign,
        "campaign",
    )

    return render(request, "civicpulse/stripe/donations.html", context)


@login_required
def candidate_donations_sync(request, pk):
    """
    Trigger donation sync for a candidate's Stripe account.

    POST only - queues a Celery task to sync donations from Stripe.
    """
    from django.contrib import messages

    from .tasks import sync_donations

    if request.method != "POST":
        return redirect("civicpulse:candidate_donations", pk=pk)

    candidate = get_object_or_404(
        Candidate.objects.select_related("stripe_connection"), pk=pk
    )

    if not hasattr(candidate, "stripe_connection") or not candidate.stripe_connection:
        messages.error(request, "No Stripe account connected to this candidate.")
        return redirect("civicpulse:candidate_detail", pk=pk)

    connection = candidate.stripe_connection

    # Check for already running sync
    running_sync = connection.sync_jobs.filter(
        status__in=[DonationSyncJob.Status.PENDING, DonationSyncJob.Status.RUNNING]
    ).exists()

    if running_sync:
        messages.warning(request, "A sync is already in progress.")
        return redirect("civicpulse:candidate_donations", pk=pk)

    # Queue sync task (task creates its own sync job)
    sync_donations.delay(str(connection.pk))

    messages.success(request, "Donation sync started. This may take a few minutes.")
    return redirect("civicpulse:candidate_donations", pk=pk)


@login_required
def campaign_donations_sync(request, pk):
    """
    Trigger donation sync for a campaign's Stripe account.

    POST only - queues a Celery task to sync donations from Stripe.
    """
    from django.contrib import messages

    from .tasks import sync_donations

    if request.method != "POST":
        return redirect("civicpulse:campaign_donations", pk=pk)

    campaign = get_object_or_404(
        Campaign.objects.select_related("stripe_connection"), pk=pk
    )

    if not hasattr(campaign, "stripe_connection") or not campaign.stripe_connection:
        messages.error(request, "No Stripe account connected to this campaign.")
        return redirect("civicpulse:org_campaign_detail", pk=pk)

    connection = campaign.stripe_connection

    # Check for already running sync
    running_sync = connection.sync_jobs.filter(
        status__in=[DonationSyncJob.Status.PENDING, DonationSyncJob.Status.RUNNING]
    ).exists()

    if running_sync:
        messages.warning(request, "A sync is already in progress.")
        return redirect("civicpulse:campaign_donations", pk=pk)

    # Queue sync task (task creates its own sync job)
    sync_donations.delay(str(connection.pk))

    messages.success(request, "Donation sync started. This may take a few minutes.")
    return redirect("civicpulse:campaign_donations", pk=pk)


# =============================================================================
# Stripe Generic Redirects (for polymorphic template usage)
# =============================================================================


@login_required
def stripe_connect_redirect(request, owner_type, owner_id):
    """Redirect to the appropriate stripe connect view based on owner_type."""
    if owner_type == "candidate":
        return redirect("civicpulse:stripe_connect_candidate", pk=owner_id)
    elif owner_type == "campaign":
        return redirect("civicpulse:stripe_connect_campaign", pk=owner_id)
    else:
        messages.error(request, f"Invalid owner type: {owner_type}")
        return redirect("civicpulse:index")


@login_required
def stripe_donations_redirect(request, owner_type, owner_id):
    """Redirect to the appropriate donations view based on owner_type."""
    if owner_type == "candidate":
        return redirect("civicpulse:candidate_donations", pk=owner_id)
    elif owner_type == "campaign":
        return redirect("civicpulse:campaign_donations", pk=owner_id)
    else:
        messages.error(request, f"Invalid owner type: {owner_type}")
        return redirect("civicpulse:index")


@login_required
def stripe_disconnect_confirm_redirect(request, owner_type, owner_id):
    """Redirect to the appropriate disconnect confirmation based on owner_type."""
    if owner_type == "candidate":
        candidate = get_object_or_404(Candidate, pk=owner_id)
        if hasattr(candidate, "stripe_connection") and candidate.stripe_connection:
            return redirect(
                "civicpulse:stripe_disconnect", connection_pk=candidate.stripe_connection.pk
            )
        messages.error(request, "No Stripe account connected to this candidate.")
        return redirect("civicpulse:candidate_detail", pk=owner_id)
    elif owner_type == "campaign":
        campaign = get_object_or_404(Campaign, pk=owner_id)
        if hasattr(campaign, "stripe_connection") and campaign.stripe_connection:
            return redirect(
                "civicpulse:stripe_disconnect", connection_pk=campaign.stripe_connection.pk
            )
        messages.error(request, "No Stripe account connected to this campaign.")
        return redirect("civicpulse:org_campaign_detail", pk=owner_id)
    else:
        messages.error(request, f"Invalid owner type: {owner_type}")
        return redirect("civicpulse:index")

# =============================================================================
# Checking Account Management Views
# =============================================================================


@login_required
def account_list(request, pk):
    """List all checking accounts for a campaign."""
    campaign = get_object_or_404(Campaign, pk=pk)

    # Get accounts ordered by most recently created
    accounts = campaign.checking_accounts.all().order_by('-created_at')

    return render(
        request,
        "civicpulse/accounts/account_list.html",
        {
            "campaign": campaign,
            "accounts": accounts,
        },
    )


@login_required
def account_create(request, pk):
    """Create a new checking account for a campaign."""
    campaign = get_object_or_404(Campaign, pk=pk)

    if request.method == "POST":
        form = CheckingAccountForm(request.POST)
        if form.is_valid():
            account = form.save(commit=False)
            account.campaign = campaign
            account.created_by = request.user
            account.save()
            return redirect("civicpulse:account_detail", pk=account.pk)
    else:
        form = CheckingAccountForm()

    return render(
        request,
        "civicpulse/accounts/account_form.html",
        {
            "campaign": campaign,
            "form": form,
            "is_create": True,
        },
    )


@login_required
def account_detail(request, pk):
    """View checking account details with transaction history."""
    account = get_object_or_404(CheckingAccount, pk=pk)
    campaign = account.campaign

    # Get transactions ordered by posted date (newest first)
    transactions = account.transactions.order_by('-posted_date', '-created_at')

    # Calculate running balances
    transactions_with_balance = []
    running_balance = 0

    # Iterate in reverse to calculate running balance forward
    for txn in reversed(list(transactions)):
        running_balance += txn.amount_cents / 100
        transactions_with_balance.insert(0, {
            'transaction': txn,
            'running_balance': running_balance,
        })

    return render(
        request,
        "civicpulse/accounts/account_detail.html",
        {
            "campaign": campaign,
            "account": account,
            "transactions": transactions_with_balance,
        },
    )


@login_required
def account_edit(request, pk):
    """Edit an existing checking account."""
    account = get_object_or_404(CheckingAccount, pk=pk)
    campaign = account.campaign

    if request.method == "POST":
        form = CheckingAccountForm(request.POST, instance=account)
        if form.is_valid():
            form.save()
            return redirect("civicpulse:account_detail", pk=account.pk)
    else:
        form = CheckingAccountForm(instance=account)

    return render(
        request,
        "civicpulse/accounts/account_form.html",
        {
            "campaign": campaign,
            "account": account,
            "form": form,
            "is_create": False,
        },
    )


@login_required
def account_delete(request, pk):
    """Delete a checking account with confirmation."""
    account = get_object_or_404(CheckingAccount, pk=pk)
    campaign = account.campaign

    if request.method == "POST":
        campaign_pk = campaign.pk
        account.delete()  # CASCADE will delete all transactions
        return redirect("civicpulse:account_list", pk=campaign_pk)

    return render(
        request,
        "civicpulse/accounts/account_confirm_delete.html",
        {
            "campaign": campaign,
            "account": account,
        },
    )


@login_required
def transaction_import(request, pk):
    """Handle transaction CSV upload with preview and confirmation."""
    account = get_object_or_404(CheckingAccount, pk=pk)
    campaign = account.campaign

    # Check if we're in preview mode (data stored in session)
    preview_data = request.session.get(f'transaction_import_preview_{pk}')

    if request.method == "POST":
        action = request.POST.get('action')

        # Handle cancel action
        if action == 'cancel':
            if f'transaction_import_preview_{pk}' in request.session:
                del request.session[f'transaction_import_preview_{pk}']
            return redirect("civicpulse:account_detail", pk=account.pk)

        # Handle confirm action (import transactions)
        if action == 'confirm' and preview_data:
            import_batch = str(uuid.uuid4())
            transactions = preview_data['transactions']

            # Create Transaction objects in bulk
            transaction_objects = []
            for txn_data in transactions:
                transaction_objects.append(
                    Transaction(
                        account=account,
                        posted_date=datetime.strptime(txn_data['posted_date'], '%Y-%m-%d').date(),
                        transaction_date=datetime.strptime(txn_data['transaction_date'], '%Y-%m-%d').date(),
                        transaction_type=txn_data['transaction_type'],
                        check_number=txn_data['check_number'],
                        description=txn_data['description'],
                        amount_cents=txn_data['amount_cents'],
                        import_batch=import_batch,
                    )
                )

            # Bulk create for efficiency
            Transaction.objects.bulk_create(transaction_objects)

            # Clear session data
            del request.session[f'transaction_import_preview_{pk}']

            return redirect("civicpulse:account_detail", pk=account.pk)

        # Handle file upload (preview mode)
        form = TransactionImportForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = form.cleaned_data['csv_file']

            # Parse CSV
            transactions = []
            parse_errors = []
            duplicate_warnings = []

            try:
                # Decode file content
                file_content = csv_file.read().decode('utf-8').splitlines()
                reader = csv.DictReader(file_content)

                # Expected columns (flexible matching)
                expected_cols = {
                    'posted_date': ['Posted Date', 'Post Date', 'Date Posted'],
                    'transaction_date': ['Transaction Date', 'Txn Date', 'Date'],
                    'transaction_type': ['Transaction Type', 'Type', 'Txn Type'],
                    'check_number': ['Check/Serial #', 'Check Number', 'Check #', 'Serial'],
                    'description': ['Description', 'Memo', 'Details'],
                    'amount': ['Amount', 'Amt', 'Transaction Amount'],
                }

                # Map actual column names to expected fields
                col_mapping = {}
                for field, possible_names in expected_cols.items():
                    for col_name in reader.fieldnames or []:
                        if col_name in possible_names:
                            col_mapping[field] = col_name
                            break

                # Validate required columns found
                required = ['posted_date', 'description', 'amount']
                missing = [f for f in required if f not in col_mapping]
                if missing:
                    raise ValueError(f"Missing required columns: {', '.join(missing)}")

                # Parse rows
                row_num = 1
                for row in reader:
                    row_num += 1
                    try:
                        # Parse posted date
                        posted_date_str = row.get(col_mapping['posted_date'], '').strip()
                        posted_date = parse_date_flexible(posted_date_str)

                        # Parse transaction date (fallback to posted date)
                        if 'transaction_date' in col_mapping:
                            txn_date_str = row.get(col_mapping['transaction_date'], '').strip()
                            transaction_date = parse_date_flexible(txn_date_str) if txn_date_str else posted_date
                        else:
                            transaction_date = posted_date

                        # Parse amount
                        amount_str = row.get(col_mapping['amount'], '').strip()
                        amount_cents = parse_amount_to_cents(amount_str)

                        # Detect transaction type from amount or explicit field
                        if 'transaction_type' in col_mapping:
                            txn_type_str = row.get(col_mapping['transaction_type'], '').strip().lower()
                            transaction_type = detect_transaction_type(txn_type_str, amount_cents)
                        else:
                            transaction_type = 'debit' if amount_cents < 0 else 'deposit'

                        # Get optional fields
                        check_number = row.get(col_mapping.get('check_number', ''), '').strip() or ''
                        description = row.get(col_mapping['description'], '').strip()

                        # Check for potential duplicates
                        existing = Transaction.objects.filter(
                            account=account,
                            posted_date=posted_date,
                            amount_cents=amount_cents,
                            description=description,
                        ).exists()

                        if existing:
                            duplicate_warnings.append(
                                f"Row {row_num}: {posted_date} - {description[:30]} "
                                f"(${abs(amount_cents)/100:.2f}) may already exist"
                            )

                        # Add to transactions list
                        transactions.append({
                            'posted_date': posted_date.strftime('%Y-%m-%d'),
                            'transaction_date': transaction_date.strftime('%Y-%m-%d'),
                            'transaction_type': transaction_type,
                            'check_number': check_number,
                            'description': description,
                            'amount_cents': amount_cents,
                            'amount_display': format_amount_display(amount_cents),
                        })

                    except Exception as e:
                        parse_errors.append(f"Row {row_num}: {str(e)}")
                        if len(parse_errors) >= 10:
                            parse_errors.append("... (too many errors, stopping)")
                            break

            except Exception as e:
                return render(
                    request,
                    "civicpulse/accounts/transaction_import.html",
                    {
                        "campaign": campaign,
                        "account": account,
                        "form": form,
                        "error": f"Failed to parse CSV: {str(e)}",
                    },
                )

            # Store in session for confirmation step
            request.session[f'transaction_import_preview_{pk}'] = {
                'transactions': transactions,
                'parse_errors': parse_errors,
                'duplicate_warnings': duplicate_warnings,
                'filename': csv_file.name,
            }

            # Render preview
            return render(
                request,
                "civicpulse/accounts/transaction_import.html",
                {
                    "campaign": campaign,
                    "account": account,
                    "preview": True,
                    "transactions": transactions,
                    "parse_errors": parse_errors,
                    "duplicate_warnings": duplicate_warnings,
                    "total_count": len(transactions),
                    "filename": csv_file.name,
                },
            )

    else:
        # GET request - show upload form
        form = TransactionImportForm()

        # Clear any stale preview data
        if f'transaction_import_preview_{pk}' in request.session:
            del request.session[f'transaction_import_preview_{pk}']

    return render(
        request,
        "civicpulse/accounts/transaction_import.html",
        {
            "campaign": campaign,
            "account": account,
            "form": form,
        },
    )


# Helper functions for transaction import

def parse_date_flexible(date_str):
    """Parse date from various formats."""
    date_str = date_str.strip()

    # Try common formats
    formats = [
        '%m/%d/%Y',  # 01/15/2024
        '%Y-%m-%d',  # 2024-01-15
        '%m-%d-%Y',  # 01-15-2024
        '%m/%d/%y',  # 01/15/24
        '%Y/%m/%d',  # 2024/01/15
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue

    raise ValueError(f"Could not parse date: {date_str}")


def parse_amount_to_cents(amount_str):
    """
    Parse amount string to cents (integer).

    Handles formats like:
    - $500.00
    - 500
    - ($128.80)  (parentheses indicate negative/debit)
    - -128.80
    """
    amount_str = amount_str.strip()

    # Check for parentheses (indicates negative)
    is_negative = amount_str.startswith('(') and amount_str.endswith(')')

    # Remove currency symbols, commas, parentheses
    amount_str = amount_str.replace('$', '').replace(',', '').replace('(', '').replace(')', '').strip()

    try:
        amount = Decimal(amount_str)
        if is_negative:
            amount = -abs(amount)

        # Convert to cents
        amount_cents = int(amount * 100)
        return amount_cents

    except (ValueError, InvalidOperation) as e:
        raise ValueError(f"Invalid amount format: {amount_str}")


def detect_transaction_type(type_str, amount_cents):
    """Detect transaction type from string or amount."""
    type_str = type_str.lower()

    type_mapping = {
        'deposit': Transaction.TransactionType.DEPOSIT,
        'debit': Transaction.TransactionType.DEBIT,
        'credit': Transaction.TransactionType.CREDIT,
        'check': Transaction.TransactionType.CHECK,
        'transfer': Transaction.TransactionType.TRANSFER,
        'fee': Transaction.TransactionType.FEE,
        'withdrawal': Transaction.TransactionType.DEBIT,
        'payment': Transaction.TransactionType.DEBIT,
    }

    for key, value in type_mapping.items():
        if key in type_str:
            return value

    # Fallback based on amount
    return Transaction.TransactionType.DEBIT if amount_cents < 0 else Transaction.TransactionType.DEPOSIT


def format_amount_display(amount_cents):
    """Format amount in cents for display."""
    amount = amount_cents / 100
    if amount >= 0:
        return f"+${amount:.2f}"
    else:
        return f"-${abs(amount):.2f}"
