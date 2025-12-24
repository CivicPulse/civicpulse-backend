from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import AssignmentFilterForm, CampaignForm, ContactAttemptForm
from .models import (
    ContactAttempt,
    ContactEffort,
    EffortAssignment,
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

    return render(
        request,
        "campaigns/campaign_detail.html",
        {"campaign": campaign, "stats": stats},
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
