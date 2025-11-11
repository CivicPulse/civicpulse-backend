"""
Search views for voter/person data.

This module provides search functionality for the CivicPulse application,
including full-text search, advanced filtering, and API endpoints.
"""

from typing import Any

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import cache_page
from django.views.generic import TemplateView

from civicpulse.models import Person, VoterRecord


class PersonSearchView(LoginRequiredMixin, TemplateView):
    """
    Main search interface for persons/voters.

    This view provides a comprehensive search interface with filtering,
    sorting, and pagination capabilities.
    """

    template_name = "civicpulse/search/person_search.html"
    paginate_by = 25

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """Add search results and filter options to context."""
        context = super().get_context_data(**kwargs)

        # Get search parameters from request
        search_query = self.request.GET.get("q", "").strip()
        state = self.request.GET.get("state", "")
        zip_code = self.request.GET.get("zip_code", "")
        city = self.request.GET.get("city", "")
        voter_status = self.request.GET.get("voter_status", "")
        party = self.request.GET.get("party", "")
        min_score = self.request.GET.get("min_score", "")
        max_score = self.request.GET.get("max_score", "")
        precinct = self.request.GET.get("precinct", "")
        ward = self.request.GET.get("ward", "")
        page = self.request.GET.get("page", 1)

        # Build queryset using advanced search
        queryset = Person.objects.advanced_search(
            search_query=search_query if search_query else None,
            state=state if state else None,
            zip_code=zip_code if zip_code else None,
            city=city if city else None,
            voter_status=voter_status if voter_status else None,
            party_affiliation=party if party else None,
            min_voter_score=int(min_score) if min_score else None,
            max_voter_score=int(max_score) if max_score else None,
            precinct=precinct if precinct else None,
            ward=ward if ward else None,
        )

        # Apply ordering
        sort_by = self.request.GET.get("sort", "last_name")
        if sort_by == "last_name":
            queryset = queryset.order_by("last_name", "first_name")
        elif sort_by == "voter_score":
            queryset = queryset.order_by("-voter_record__voter_score", "last_name")
        elif sort_by == "city":
            queryset = queryset.order_by("city", "last_name")
        elif sort_by == "created_at":
            queryset = queryset.order_by("-created_at")

        # Paginate results
        paginator = Paginator(queryset, self.paginate_by)
        try:
            persons = paginator.page(page)
        except PageNotAnInteger:
            persons = paginator.page(1)
        except EmptyPage:
            persons = paginator.page(paginator.num_pages)

        # US state codes for filter dropdown
        us_states = [
            "AL",
            "AK",
            "AZ",
            "AR",
            "CA",
            "CO",
            "CT",
            "DE",
            "FL",
            "GA",
            "HI",
            "ID",
            "IL",
            "IN",
            "IA",
            "KS",
            "KY",
            "LA",
            "ME",
            "MD",
            "MA",
            "MI",
            "MN",
            "MS",
            "MO",
            "MT",
            "NE",
            "NV",
            "NH",
            "NJ",
            "NM",
            "NY",
            "NC",
            "ND",
            "OH",
            "OK",
            "OR",
            "PA",
            "RI",
            "SC",
            "SD",
            "TN",
            "TX",
            "UT",
            "VT",
            "VA",
            "WA",
            "WV",
            "WI",
            "WY",
            "DC",
        ]

        # Add context data
        context.update(
            {
                "persons": persons,
                "total_results": paginator.count,
                "search_query": search_query,
                "filters": {
                    "state": state,
                    "zip_code": zip_code,
                    "city": city,
                    "voter_status": voter_status,
                    "party": party,
                    "min_score": min_score,
                    "max_score": max_score,
                    "precinct": precinct,
                    "ward": ward,
                },
                "sort_by": sort_by,
                # Filter options
                "us_states": us_states,
                "voter_statuses": VoterRecord.REGISTRATION_STATUS_CHOICES,
                "parties": VoterRecord.PARTY_AFFILIATION_CHOICES,
            }
        )

        return context


class PersonSearchAPIView(LoginRequiredMixin, View):
    """
    API endpoint for person/voter search.

    Provides JSON responses for AJAX/HTMX requests.
    """

    def get(self, request: HttpRequest) -> JsonResponse:
        """Handle GET requests for search."""
        # Get search parameters
        search_query = request.GET.get("q", "").strip()
        state = request.GET.get("state", "")
        zip_code = request.GET.get("zip_code", "")
        city = request.GET.get("city", "")
        voter_status = request.GET.get("voter_status", "")
        party = request.GET.get("party", "")
        min_score = request.GET.get("min_score", "")
        max_score = request.GET.get("max_score", "")
        precinct = request.GET.get("precinct", "")
        ward = request.GET.get("ward", "")
        page = request.GET.get("page", 1)
        page_size = min(int(request.GET.get("page_size", 25)), 100)  # Max 100 per page

        # Build queryset
        queryset = Person.objects.advanced_search(
            search_query=search_query if search_query else None,
            state=state if state else None,
            zip_code=zip_code if zip_code else None,
            city=city if city else None,
            voter_status=voter_status if voter_status else None,
            party_affiliation=party if party else None,
            min_voter_score=int(min_score) if min_score else None,
            max_voter_score=int(max_score) if max_score else None,
            precinct=precinct if precinct else None,
            ward=ward if ward else None,
        )

        # Apply ordering
        sort_by = request.GET.get("sort", "last_name")
        if sort_by == "last_name":
            queryset = queryset.order_by("last_name", "first_name")
        elif sort_by == "voter_score":
            queryset = queryset.order_by("-voter_record__voter_score", "last_name")
        elif sort_by == "city":
            queryset = queryset.order_by("city", "last_name")
        elif sort_by == "created_at":
            queryset = queryset.order_by("-created_at")

        # Paginate
        paginator = Paginator(queryset, page_size)
        try:
            persons = paginator.page(page)
        except (PageNotAnInteger, EmptyPage):
            persons = paginator.page(1)

        # Serialize results
        results = []
        for person in persons:
            result = {
                "id": str(person.id),
                "full_name": person.full_name,
                "first_name": person.first_name,
                "last_name": person.last_name,
                "email": person.email,
                "phone_primary": person.phone_primary,
                "city": person.city,
                "state": person.state,
                "zip_code": person.zip_code,
            }

            # Add voter record info if available
            if hasattr(person, "voter_record") and person.voter_record:
                result["voter"] = {
                    "voter_id": person.voter_record.voter_id,
                    "registration_status": person.voter_record.registration_status,
                    "party_affiliation": person.voter_record.party_affiliation,
                    "voter_score": person.voter_record.voter_score,
                    "precinct": person.voter_record.precinct,
                    "ward": person.voter_record.ward,
                }

            results.append(result)

        # Return JSON response
        return JsonResponse(
            {
                "results": results,
                "total": paginator.count,
                "page": persons.number,
                "num_pages": paginator.num_pages,
                "has_next": persons.has_next(),
                "has_previous": persons.has_previous(),
            }
        )


class QuickSearchAPIView(LoginRequiredMixin, View):
    """
    Quick search API for autocomplete/typeahead functionality.

    Returns limited results optimized for real-time search suggestions.
    """

    @method_decorator(cache_page(60 * 5))  # Cache for 5 minutes
    def get(self, request: HttpRequest) -> JsonResponse:
        """Handle GET requests for quick search."""
        query = request.GET.get("q", "").strip()
        limit = min(int(request.GET.get("limit", 10)), 50)  # Max 50 results

        if not query or len(query) < 2:
            return JsonResponse({"results": []})

        # Quick search across name and basic fields
        persons = (
            Person.objects.filter(
                Q(first_name__istartswith=query)
                | Q(last_name__istartswith=query)
                | Q(email__icontains=query)
            )
            .select_related("voter_record")
            .order_by("last_name", "first_name")[:limit]
        )

        results = [
            {
                "id": str(p.id),
                "label": f"{p.full_name} - {p.city}, {p.state}"
                if p.city and p.state
                else p.full_name,
                "value": p.full_name,
                "city": p.city,
                "state": p.state,
            }
            for p in persons
        ]

        return JsonResponse({"results": results})


class SearchStatsAPIView(LoginRequiredMixin, View):
    """
    API endpoint for search statistics and aggregations.

    Provides summary statistics about the voter database.
    """

    @method_decorator(cache_page(60 * 15))  # Cache for 15 minutes
    def get(self, request: HttpRequest) -> JsonResponse:
        """Get search statistics."""
        # Total counts
        total_persons = Person.objects.count()
        total_voters = Person.objects.filter(voter_record__isnull=False).count()

        # Status breakdown
        status_counts = dict(
            VoterRecord.objects.values("registration_status")
            .annotate(count=Count("id"))
            .values_list("registration_status", "count")
        )

        # Party breakdown
        party_counts = dict(
            VoterRecord.objects.values("party_affiliation")
            .annotate(count=Count("id"))
            .values_list("party_affiliation", "count")
        )

        # Geographic breakdown
        state_counts = dict(
            Person.objects.values("state")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
            .values_list("state", "count")
        )

        # Voter score ranges
        high_priority = VoterRecord.objects.filter(voter_score__gte=70).count()
        medium_priority = VoterRecord.objects.filter(
            voter_score__gte=40, voter_score__lt=70
        ).count()
        low_priority = VoterRecord.objects.filter(voter_score__lt=40).count()

        return JsonResponse(
            {
                "totals": {
                    "persons": total_persons,
                    "voters": total_voters,
                    "non_voters": total_persons - total_voters,
                },
                "registration_status": status_counts,
                "party_affiliation": party_counts,
                "states": state_counts,
                "priority": {
                    "high": high_priority,
                    "medium": medium_priority,
                    "low": low_priority,
                },
            }
        )


@login_required
def export_search_results(request: HttpRequest) -> HttpResponse:
    """
    Export search results to CSV.

    Uses the same search parameters as the main search view.
    """
    import csv

    from django.utils.text import slugify

    # Get search parameters (same as PersonSearchView)
    search_query = request.GET.get("q", "").strip()
    state = request.GET.get("state", "")
    zip_code = request.GET.get("zip_code", "")
    city = request.GET.get("city", "")
    voter_status = request.GET.get("voter_status", "")
    party = request.GET.get("party", "")
    min_score = request.GET.get("min_score", "")
    max_score = request.GET.get("max_score", "")

    # Build queryset
    queryset = Person.objects.advanced_search(
        search_query=search_query if search_query else None,
        state=state if state else None,
        zip_code=zip_code if zip_code else None,
        city=city if city else None,
        voter_status=voter_status if voter_status else None,
        party_affiliation=party if party else None,
        min_voter_score=int(min_score) if min_score else None,
        max_voter_score=int(max_score) if max_score else None,
    ).select_related("voter_record")

    # Create CSV response
    response = HttpResponse(content_type="text/csv")
    filename = f"voter_search_{slugify(search_query or 'results')}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(
        [
            "First Name",
            "Last Name",
            "Email",
            "Phone",
            "Street Address",
            "City",
            "State",
            "ZIP",
            "Voter ID",
            "Status",
            "Party",
            "Voter Score",
            "Precinct",
            "Ward",
        ]
    )

    for person in queryset:
        voter_id = ""
        status = ""
        party = ""
        score = ""
        precinct = ""
        ward = ""

        if hasattr(person, "voter_record") and person.voter_record:
            voter_id = person.voter_record.voter_id
            status = person.voter_record.registration_status
            party = person.voter_record.party_affiliation
            score = str(person.voter_record.voter_score)
            precinct = person.voter_record.precinct
            ward = person.voter_record.ward

        writer.writerow(
            [
                person.first_name,
                person.last_name,
                person.email,
                person.phone_primary,
                person.street_address,
                person.city,
                person.state,
                person.zip_code,
                voter_id,
                status,
                party,
                score,
                precinct,
                ward,
            ]
        )

    return response
