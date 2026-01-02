from datetime import date, timedelta
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
    ContactAttemptForm,
    DriveForm,
    ElectionDateForm,
    ElectionForm,
    OfficeForm,
    VoterImportForm,
)
from .models import (
    Campaign,
    Candidate,
    ContactAttempt,
    ContactEffort,
    District,
    EffortAssignment,
    Election,
    ElectionDate,
    ElectionVoter,
    ImportJob,
    Office,
    Person,
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

    person = Person.objects.prefetch_related(
        "phone_numbers", "emails", "addresses"
    ).get(pk=candidate.person_id)

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
        "person", "locked_by"
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

    person = get_person_with_details(assignment.person_id, campaign)
    form = ContactAttemptForm()
    stats = get_session_stats(campaign)

    # Get primary phone
    primary_phone = person.phone_numbers.filter(is_primary=True).first()
    if not primary_phone:
        primary_phone = person.phone_numbers.first()

    return render(
        request,
        "civicpulse/campaigns/partials/_person_card.html",
        {
            "campaign": campaign,
            "assignment": assignment,
            "person": person,
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
            attempt.person = assignment.person
            attempt.contacted_by = request.user
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

    # Return the next person card
    return knocking_next(request, pk)


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

    person = get_person_with_details(assignment.person_id, campaign)
    from .forms import DoorKnockAttemptForm

    form = DoorKnockAttemptForm()
    stats = get_session_stats(campaign)

    # Get primary home address
    primary_address = person.addresses.filter(type="home").first()
    if not primary_address:
        primary_address = person.addresses.first()

    # Calculate distance if we have coordinates
    distance = None
    user_lat = request.session.get("knocker_lat")
    user_lon = request.session.get("knocker_lon")
    if (
        user_lat
        and user_lon
        and hasattr(person, "voter_record")
        and person.voter_record
        and person.voter_record.latitude
        and person.voter_record.longitude
    ):
        distance = haversine_distance(
            user_lat,
            user_lon,
            person.voter_record.latitude,
            person.voter_record.longitude,
        )

    return render(
        request,
        "civicpulse/campaigns/partials/_address_card.html",
        {
            "campaign": campaign,
            "assignment": assignment,
            "person": person,
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
            attempt.person = assignment.person
            attempt.contacted_by = request.user
            attempt.contact_type = ContactAttempt.ContactType.DOOR_KNOCK
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
    return knocking_next(request, pk)


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

    return knocking_next(request, pk)


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
