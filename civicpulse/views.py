from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    AssignmentFilterForm,
    CampaignForm,
    CandidateForm,
    ContactAttemptForm,
    ElectionDateForm,
    ElectionForm,
    OfficeForm,
)
from .models import (
    Candidate,
    ContactAttempt,
    ContactEffort,
    EffortAssignment,
    Election,
    ElectionDate,
    Office,
    Person,
)


@login_required
def index(request):
    return render(request, "index.html")


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

    return render(request, "campaigns/campaign_list.html", {"campaigns": campaigns})


@login_required
def campaign_create(request):
    """Create a new campaign."""
    if request.method == "POST":
        form = CampaignForm(request.POST)
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.created_by = request.user
            campaign.save()
            return redirect("campaign_detail", pk=campaign.pk)
    else:
        form = CampaignForm()

    return render(
        request, "campaigns/campaign_form.html", {"form": form, "is_create": True}
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
        "campaigns/campaign_detail.html",
        {"campaign": campaign, "stats": stats, "user_in_progress": user_in_progress},
    )


@login_required
def campaign_edit(request, pk):
    """Edit an existing campaign."""
    campaign = get_object_or_404(ContactEffort, pk=pk)

    if request.method == "POST":
        form = CampaignForm(request.POST, instance=campaign)
        if form.is_valid():
            form.save()
            return redirect("campaign_detail", pk=campaign.pk)
    else:
        form = CampaignForm(instance=campaign)

    return render(
        request,
        "campaigns/campaign_form.html",
        {"form": form, "campaign": campaign, "is_create": False},
    )


@login_required
def campaign_delete(request, pk):
    """Delete a campaign with confirmation."""
    campaign = get_object_or_404(ContactEffort, pk=pk)

    if request.method == "POST":
        campaign.delete()
        return redirect("campaign_list")

    return render(
        request, "campaigns/campaign_confirm_delete.html", {"campaign": campaign}
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
        "elections/office_list.html",
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
        "elections/office_detail.html",
        {"office": office, "elections": elections},
    )


@login_required
def office_create(request):
    """Create a new office."""
    if request.method == "POST":
        form = OfficeForm(request.POST)
        if form.is_valid():
            office = form.save()
            return redirect("office_detail", pk=office.pk)
    else:
        form = OfficeForm()

    return render(
        request, "elections/office_form.html", {"form": form, "is_create": True}
    )


@login_required
def office_edit(request, pk):
    """Edit an existing office."""
    office = get_object_or_404(Office, pk=pk)

    if request.method == "POST":
        form = OfficeForm(request.POST, instance=office)
        if form.is_valid():
            form.save()
            return redirect("office_detail", pk=office.pk)
    else:
        form = OfficeForm(instance=office)

    return render(
        request,
        "elections/office_form.html",
        {"form": form, "office": office, "is_create": False},
    )


@login_required
def office_delete(request, pk):
    """Delete an office with confirmation."""
    office = get_object_or_404(Office, pk=pk)

    if request.method == "POST":
        office.delete()
        return redirect("office_list")

    return render(request, "elections/office_confirm_delete.html", {"office": office})


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
        "elections/election_list.html",
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
        "elections/election_detail.html",
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
            return redirect("election_detail", pk=election.pk)
    else:
        form = ElectionForm()

    return render(
        request, "elections/election_form.html", {"form": form, "is_create": True}
    )


@login_required
def election_edit(request, pk):
    """Edit an existing election."""
    election = get_object_or_404(Election, pk=pk)

    if request.method == "POST":
        form = ElectionForm(request.POST, instance=election)
        if form.is_valid():
            form.save()
            return redirect("election_detail", pk=election.pk)
    else:
        form = ElectionForm(instance=election)

    return render(
        request,
        "elections/election_form.html",
        {"form": form, "election": election, "is_create": False},
    )


@login_required
def election_delete(request, pk):
    """Delete an election with confirmation."""
    election = get_object_or_404(Election, pk=pk)

    if request.method == "POST":
        election.delete()
        return redirect("election_list")

    return render(
        request, "elections/election_confirm_delete.html", {"election": election}
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
        "elections/candidate_list.html",
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
            return redirect("election_detail", pk=election.pk)
    else:
        form = CandidateForm()

    return render(
        request,
        "elections/candidate_form.html",
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
        "elections/candidate_detail.html",
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
            return redirect("candidate_detail", pk=candidate.pk)
    else:
        form = CandidateForm(instance=candidate)

    return render(
        request,
        "elections/candidate_form.html",
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
        return redirect("election_detail", pk=election.pk)

    return render(
        request, "elections/candidate_confirm_delete.html", {"candidate": candidate}
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
        "elections/election_campaigns.html",
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
            return redirect("election_detail", pk=election.pk)
    else:
        form = ElectionDateForm()

    return render(
        request,
        "elections/election_date_form.html",
        {"form": form, "election": election},
    )


@login_required
def election_date_delete(request, pk, date_pk):
    """Delete an additional election date."""
    election = get_object_or_404(Election, pk=pk)
    election_date = get_object_or_404(ElectionDate, pk=date_pk, election=election)

    if request.method == "POST":
        election_date.delete()

    return redirect("election_detail", pk=election.pk)


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
        "campaigns/assignment_list.html",
        {
            "campaign": campaign,
            "assignments": assignments,
            "status_filter": status_filter,
            "status_choices": EffortAssignment.Status.choices,
        },
    )


@login_required
def assignment_add(request, pk):
    """Filter and bulk assign persons to a campaign."""
    campaign = get_object_or_404(ContactEffort, pk=pk)

    if request.method == "POST":
        form = AssignmentFilterForm(request.POST)
        if form.is_valid():
            # Build query based on filters
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

            # Bulk create assignments
            assignments = [
                EffortAssignment(effort=campaign, person_id=pid) for pid in person_ids
            ]
            EffortAssignment.objects.bulk_create(assignments, ignore_conflicts=True)

            return redirect("assignment_list", pk=campaign.pk)
    else:
        form = AssignmentFilterForm()

    # Preview count
    preview_count = (
        Person.objects.exclude(effort_assignments__effort=campaign)
        .filter(phone_numbers__isnull=False)
        .distinct()
        .count()
    )

    return render(
        request,
        "campaigns/assignment_add.html",
        {"campaign": campaign, "form": form, "preview_count": preview_count},
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

    return redirect("assignment_list", pk=campaign.pk)


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


@login_required
def calling_session(request, pk):
    """Main calling session page."""
    campaign = get_object_or_404(ContactEffort, pk=pk)
    stats = get_session_stats(campaign)

    return render(
        request,
        "campaigns/calling_session.html",
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
            "campaigns/partials/_session_complete.html",
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
        "campaigns/partials/_person_card.html",
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
        "campaigns/partials/_candidate_select.html",
        {"candidates": candidates},
    )
