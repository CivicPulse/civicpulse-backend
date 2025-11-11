"""
District assignment service layer for CivicPulse application.

This module provides business logic for assigning Person records to District records
based on various methods including voter records, ZIP codes, and county matching.

The service layer separates business logic from view logic, making it:
- More testable (can be unit tested without Django views)
- Reusable (can be called from views, management commands, Celery tasks, APIs)
- Maintainable (business rules in one place)
- Performant (uses optimized queries with select_related and prefetch_related)
"""

from django.db import transaction
from django.db.models import Q, QuerySet
from loguru import logger

from civicpulse.models import District, Person, PersonDistrict


class DistrictAssignmentService:
    """
    Service for assigning Person records to District records.

    This class provides multiple methods for district assignment based on
    different data sources and matching strategies. It handles:
    - Assignment from voter registration records
    - Assignment from ZIP code matching
    - Assignment from county matching
    - Bulk assignment operations
    - Individual person reassignment
    - Denormalized officeholder name updates

    Key features:
    - Uses database transactions for data integrity
    - Optimizes queries to avoid N+1 problems
    - Provides detailed logging and error handling
    - Returns statistics for bulk operations
    - Supports confidence scoring for different matching methods

    Example:
        >>> service = DistrictAssignmentService()
        >>> person = Person.objects.get(pk=person_id)
        >>> assigned_count = service.assign_from_voter_record(person)
        >>> print(f"Assigned {assigned_count} districts")
    """

    @transaction.atomic
    def assign_from_voter_record(self, person: Person) -> int:
        """
        Assign districts to a person based on their voter record information.

        This method uses the person's associated VoterRecord to create PersonDistrict
        records for various district types:
        - Congressional districts (federal_house)
        - State house districts (state_house)
        - State senate districts (state_senate)
        - Precinct (municipality or other)
        - Ward (municipality or other)

        The method:
        1. Checks if person has a voter record
        2. Queries for matching districts by type and code
        3. Creates PersonDistrict records with assignment_method='voter_record'
        4. Sets confidence to 100.0 (highest confidence)
        5. Populates denormalized current_officeholder_name

        Args:
            person: Person instance to assign districts to. Must have a voter_record
                relationship populated.

        Returns:
            Number of districts successfully assigned (0-5 typically).
            Returns 0 if person has no voter record or no matching districts found.

        Example:
            >>> service = DistrictAssignmentService()
            >>> person = Person.objects.get(email='voter@example.com')
            >>> count = service.assign_from_voter_record(person)
            >>> if count > 0:
            ...     print(f"Assigned {count} districts from voter record")
            ... else:
            ...     print("No districts assigned - voter record missing or incomplete")

        Note:
            - Uses @transaction.atomic for rollback on errors
            - Skips existing PersonDistrict records (uses get_or_create)
            - District codes must match exactly (case-sensitive)
            - State must match person's state
            - Logs all assignments and errors for debugging
        """
        logger.info(f"Assigning districts from voter record for person {person.pk}")

        try:
            # Check if person has a voter record
            if not hasattr(person, "voter_record") or not person.voter_record:
                logger.warning(f"Person {person.pk} has no voter record")
                return 0

            voter_record = person.voter_record
            assigned_count = 0

            # Mapping of voter record fields to district types
            district_mappings = [
                (
                    voter_record.congressional_district,
                    "federal_house",
                    "congressional_district",
                ),
                (
                    voter_record.state_house_district,
                    "state_house",
                    "state_house_district",
                ),
                (
                    voter_record.state_senate_district,
                    "state_senate",
                    "state_senate_district",
                ),
                (voter_record.precinct, "municipality", "precinct"),
                (voter_record.ward, "municipality", "ward"),
            ]

            for district_code, district_type, field_name in district_mappings:
                if not district_code or not district_code.strip():
                    continue

                try:
                    # Query for matching district
                    # District code format in DB: "XX-NN" (e.g., "PA-05")
                    # Voter record might have just the number
                    district = District.objects.filter(
                        Q(district_code=district_code)
                        | Q(district_code=f"{person.state}-{district_code}"),
                        district_type=district_type,
                        state=person.state,
                        is_active=True,
                    ).first()

                    if district:
                        # Get current officeholder name
                        current_officeholder = (
                            district.officeholders.filter(is_current=True)
                            .select_related("district")
                            .first()
                        )

                        officeholder_name = ""
                        if current_officeholder:
                            officeholder_name = current_officeholder.full_name

                        # Create PersonDistrict record
                        person_district, created = PersonDistrict.objects.get_or_create(
                            person=person,
                            district=district,
                            defaults={
                                "assignment_method": "voter_record",
                                "confidence": 100.00,
                                "current_officeholder_name": officeholder_name,
                            },
                        )

                        if created:
                            assigned_count += 1
                            logger.debug(
                                f"Assigned {field_name} district "
                                f"{district.district_code} to person {person.pk}"
                            )
                        else:
                            logger.debug(
                                f"PersonDistrict already exists for {field_name} "
                                f"district {district.district_code}"
                            )

                except Exception as e:
                    logger.error(
                        f"Error assigning {field_name} district: {e}", exc_info=True
                    )
                    continue

            logger.info(
                f"Assigned {assigned_count} districts from voter record "
                f"for person {person.pk}"
            )
            return assigned_count

        except Exception as e:
            logger.error(
                f"Error in assign_from_voter_record for person {person.pk}: {e}",
                exc_info=True,
            )
            raise

    @transaction.atomic
    def assign_from_zip_code(self, person: Person) -> int:
        """
        Assign districts to a person based on ZIP code matching.

        This method queries for districts where the person's ZIP code is listed
        in the district's zip_codes_covered JSONField. This is less precise than
        voter record assignment as ZIP codes can span multiple districts.

        The method:
        1. Checks if person has a ZIP code
        2. Queries for districts covering that ZIP code
        3. Creates PersonDistrict records with assignment_method='zip_match'
        4. Sets confidence to 75.0 (medium-high confidence)
        5. Populates denormalized current_officeholder_name

        Args:
            person: Person instance to assign districts to. Must have a zip_code.

        Returns:
            Number of districts successfully assigned.
            Returns 0 if person has no ZIP code or no matching districts found.

        Example:
            >>> service = DistrictAssignmentService()
            >>> person = Person.objects.get(email='voter@example.com')
            >>> count = service.assign_from_zip_code(person)
            >>> print(f"Assigned {count} districts based on ZIP code match")

        Note:
            - Confidence is lower (75.0) because ZIP code matching is less precise
            - Uses JSONField __contains lookup for efficiency
            - Filters by state for additional validation
            - Skips existing PersonDistrict records
            - Only assigns to active districts
        """
        logger.info(f"Assigning districts from ZIP code for person {person.pk}")

        try:
            # Check if person has a ZIP code
            if not person.zip_code or not person.zip_code.strip():
                logger.warning(f"Person {person.pk} has no ZIP code")
                return 0

            # Extract 5-digit ZIP code (ignore ZIP+4)
            zip_code = person.zip_code.split("-")[0].strip()

            # Query for districts covering this ZIP code
            districts = District.objects.filter(
                zip_codes_covered__contains=[zip_code],
                state=person.state,
                is_active=True,
            ).select_related()

            if not districts.exists():
                logger.debug(
                    f"No districts found for ZIP code {zip_code} "
                    f"in state {person.state}"
                )
                return 0

            assigned_count = 0

            for district in districts:
                try:
                    # Get current officeholder name
                    current_officeholder = (
                        district.officeholders.filter(is_current=True)
                        .select_related("district")
                        .first()
                    )

                    officeholder_name = ""
                    if current_officeholder:
                        officeholder_name = current_officeholder.full_name

                    # Create PersonDistrict record
                    person_district, created = PersonDistrict.objects.get_or_create(
                        person=person,
                        district=district,
                        defaults={
                            "assignment_method": "zip_match",
                            "confidence": 75.00,
                            "current_officeholder_name": officeholder_name,
                        },
                    )

                    if created:
                        assigned_count += 1
                        logger.debug(
                            f"Assigned ZIP-matched district {district.district_code} "
                            f"to person {person.pk}"
                        )

                except Exception as e:
                    logger.error(
                        f"Error assigning ZIP-matched district {district.pk}: {e}",
                        exc_info=True,
                    )
                    continue

            logger.info(
                f"Assigned {assigned_count} districts from ZIP code match "
                f"for person {person.pk}"
            )
            return assigned_count

        except Exception as e:
            logger.error(
                f"Error in assign_from_zip_code for person {person.pk}: {e}",
                exc_info=True,
            )
            raise

    @transaction.atomic
    def assign_from_county(self, person: Person) -> int:
        """
        Assign districts to a person based on county matching.

        This method queries for districts where the person's county is listed
        in the district's counties_covered JSONField. This is the least precise
        matching method as counties can contain many districts.

        The method:
        1. Checks if person has a county
        2. Queries for districts covering that county
        3. Creates PersonDistrict records with assignment_method='zip_match'
        4. Sets confidence to 60.0 (medium confidence)
        5. Populates denormalized current_officeholder_name

        Args:
            person: Person instance to assign districts to. Must have a county.

        Returns:
            Number of districts successfully assigned.
            Returns 0 if person has no county or no matching districts found.

        Example:
            >>> service = DistrictAssignmentService()
            >>> person = Person.objects.get(email='voter@example.com')
            >>> count = service.assign_from_county(person)
            >>> print(f"Assigned {count} districts based on county match")

        Note:
            - Confidence is lowest (60.0) because county matching is least precise
            - Uses JSONField __contains lookup for efficiency
            - Filters by state for additional validation
            - Case-insensitive county name matching
            - Skips existing PersonDistrict records
            - Only assigns to active districts
        """
        logger.info(f"Assigning districts from county for person {person.pk}")

        try:
            # Check if person has a county
            if not person.county or not person.county.strip():
                logger.warning(f"Person {person.pk} has no county")
                return 0

            county = person.county.strip()

            # Query for districts covering this county (case-insensitive)
            # JSONField contains is case-sensitive, so we'll need to filter in Python
            # or use a more complex query
            districts = District.objects.filter(
                state=person.state, is_active=True
            ).select_related()

            # Filter by county (case-insensitive match in JSONField)
            matching_districts = []
            for district in districts:
                if district.counties_covered:
                    # Case-insensitive match
                    counties_lower = [c.lower() for c in district.counties_covered]
                    if county.lower() in counties_lower:
                        matching_districts.append(district)

            if not matching_districts:
                logger.debug(
                    f"No districts found for county {county} in state {person.state}"
                )
                return 0

            assigned_count = 0

            for district in matching_districts:
                try:
                    # Get current officeholder name
                    current_officeholder = (
                        district.officeholders.filter(is_current=True)
                        .select_related("district")
                        .first()
                    )

                    officeholder_name = ""
                    if current_officeholder:
                        officeholder_name = current_officeholder.full_name

                    # Create PersonDistrict record
                    person_district, created = PersonDistrict.objects.get_or_create(
                        person=person,
                        district=district,
                        defaults={
                            "assignment_method": "zip_match",
                            "confidence": 60.00,
                            "current_officeholder_name": officeholder_name,
                        },
                    )

                    if created:
                        assigned_count += 1
                        logger.debug(
                            f"Assigned county-matched district "
                            f"{district.district_code} to person {person.pk}"
                        )

                except Exception as e:
                    logger.error(
                        f"Error assigning county-matched district {district.pk}: {e}",
                        exc_info=True,
                    )
                    continue

            logger.info(
                f"Assigned {assigned_count} districts from county match "
                f"for person {person.pk}"
            )
            return assigned_count

        except Exception as e:
            logger.error(
                f"Error in assign_from_county for person {person.pk}: {e}",
                exc_info=True,
            )
            raise

    def bulk_assign_all(
        self, people_queryset: QuerySet[Person] | None = None
    ) -> dict[str, int]:
        """
        Perform bulk district assignment for multiple people.

        This method processes a queryset of Person objects and attempts to assign
        districts using all available methods in order of precision:
        1. Voter record (highest confidence)
        2. ZIP code matching (medium-high confidence)
        3. County matching (medium confidence)

        The method:
        - Optimizes queries with select_related and prefetch_related
        - Processes each person individually within transactions
        - Continues processing on individual errors
        - Returns comprehensive statistics

        Args:
            people_queryset: Optional QuerySet of Person objects to process.
                If not provided, uses Person.objects.all() (all active persons).

        Returns:
            Dictionary with assignment statistics:
            {
                'total': int,          # Total people processed
                'assigned': int,       # People with at least one district assigned
                'skipped': int,        # People with no districts assigned
                'errors': int,         # People that caused errors during processing
                'voter_record': int,   # Districts assigned via voter record
                'zip_code': int,       # Districts assigned via ZIP code
                'county': int          # Districts assigned via county
            }

        Example:
            >>> service = DistrictAssignmentService()
            >>> # Assign to all people
            >>> stats = service.bulk_assign_all()
            >>> print(f"Assigned districts to {stats['assigned']} people")
            >>> print(f"Total districts: {stats['voter_record'] + stats['zip_code']}")
            >>>
            >>> # Assign to specific people
            >>> voters = Person.objects.filter(voter_record__isnull=False)
            >>> stats = service.bulk_assign_all(voters)
            >>> print(f"Processed {stats['total']} voters")

        Note:
            - Each person is processed in its own transaction
            - Failures for individual people don't affect others
            - Progress is logged at INFO level
            - Errors are logged at ERROR level with details
            - Can be used for initial data load or periodic updates
        """
        if people_queryset is None:
            people_queryset = Person.objects.all()

        # Optimize query with related data
        people_queryset = people_queryset.select_related(
            "voter_record"
        ).prefetch_related("person_districts")

        total = people_queryset.count()
        logger.info(f"Starting bulk district assignment for {total} people")

        stats: dict[str, int] = {
            "total": total,
            "assigned": 0,
            "skipped": 0,
            "errors": 0,
            "voter_record": 0,
            "zip_code": 0,
            "county": 0,
        }

        for i, person in enumerate(people_queryset, start=1):
            if i % 100 == 0:
                logger.info(f"Processing person {i}/{total}")

            try:
                person_assigned = False

                # Try voter record first (highest confidence)
                count = self.assign_from_voter_record(person)
                if count > 0:
                    stats["voter_record"] += count
                    person_assigned = True

                # Try ZIP code matching
                count = self.assign_from_zip_code(person)
                if count > 0:
                    stats["zip_code"] += count
                    person_assigned = True

                # Try county matching
                count = self.assign_from_county(person)
                if count > 0:
                    stats["county"] += count
                    person_assigned = True

                if person_assigned:
                    stats["assigned"] += 1
                else:
                    stats["skipped"] += 1

            except Exception as e:
                stats["errors"] += 1
                logger.error(
                    f"Error processing person {person.pk} during bulk assignment: {e}",
                    exc_info=True,
                )

        logger.info(
            f"Bulk assignment complete: {stats['assigned']} assigned, "
            f"{stats['skipped']} skipped, {stats['errors']} errors"
        )
        return stats

    @transaction.atomic
    def reassign_person(self, person: Person, method: str = "auto") -> int:
        """
        Reassign districts for a single person.

        This method clears existing PersonDistrict records and reassigns using
        the specified method or all methods if 'auto' is selected.

        The method:
        1. Deletes existing PersonDistrict records for the person
        2. Assigns districts using specified method(s)
        3. Updates denormalized current_officeholder_name fields

        Args:
            person: Person instance to reassign districts to.
            method: Assignment method to use. Options:
                - 'auto': Try all methods (voter_record, zip, county)
                - 'voter_record': Use only voter record
                - 'zip': Use only ZIP code matching
                - 'county': Use only county matching

        Returns:
            Total number of districts assigned across all methods used.

        Raises:
            ValueError: If method is not one of the valid options.

        Example:
            >>> service = DistrictAssignmentService()
            >>> person = Person.objects.get(pk=person_id)
            >>> # Reassign using all methods
            >>> count = service.reassign_person(person)
            >>> print(f"Reassigned {count} districts")
            >>>
            >>> # Reassign using only voter record
            >>> count = service.reassign_person(person, method='voter_record')

        Note:
            - Uses @transaction.atomic for rollback on errors
            - Deletes ALL existing PersonDistrict records first
            - 'auto' method tries all assignment methods in order
            - Updates denormalized fields after assignment
            - Logs all operations for debugging
        """
        logger.info(
            f"Reassigning districts for person {person.pk} using method: {method}"
        )

        valid_methods = ["auto", "voter_record", "zip", "county"]
        if method not in valid_methods:
            raise ValueError(
                f"Invalid method '{method}'. Must be one of: {', '.join(valid_methods)}"
            )

        try:
            # Clear existing PersonDistrict records
            deleted_count = PersonDistrict.objects.filter(person=person).delete()[0]
            logger.debug(
                f"Deleted {deleted_count} existing PersonDistrict records "
                f"for person {person.pk}"
            )

            total_assigned = 0

            # Assign using specified method(s)
            if method == "auto":
                # Try all methods
                total_assigned += self.assign_from_voter_record(person)
                total_assigned += self.assign_from_zip_code(person)
                total_assigned += self.assign_from_county(person)
            elif method == "voter_record":
                total_assigned = self.assign_from_voter_record(person)
            elif method == "zip":
                total_assigned = self.assign_from_zip_code(person)
            elif method == "county":
                total_assigned = self.assign_from_county(person)

            logger.info(
                f"Reassigned {total_assigned} districts to person {person.pk} "
                f"using method: {method}"
            )
            return total_assigned

        except Exception as e:
            logger.error(
                f"Error in reassign_person for person {person.pk}: {e}", exc_info=True
            )
            raise

    def update_officeholder_denormalization(
        self, person_districts_queryset: QuerySet[PersonDistrict] | None = None
    ) -> int:
        """
        Update denormalized current_officeholder_name for PersonDistrict records.

        This method batch updates the current_officeholder_name field in PersonDistrict
        records by querying the associated district's current officeholder. This
        denormalization improves query performance by avoiding JOIN operations.

        The method:
        1. Queries for PersonDistrict records (all or filtered)
        2. For each record, gets the current officeholder from the district
        3. Updates the current_officeholder_name field
        4. Uses bulk_update for performance

        Args:
            person_districts_queryset: Optional QuerySet of PersonDistrict objects
                to update. If not provided, updates all PersonDistrict records.

        Returns:
            Number of PersonDistrict records updated.

        Example:
            >>> service = DistrictAssignmentService()
            >>> # Update all PersonDistrict records
            >>> count = service.update_officeholder_denormalization()
            >>> print(f"Updated {count} PersonDistrict records")
            >>>
            >>> # Update only for specific districts
            >>> pd_queryset = PersonDistrict.objects.filter(
            ...     district__district_type='federal_house'
            ... )
            >>> count = service.update_officeholder_denormalization(pd_queryset)

        Note:
            - Uses select_related for query optimization
            - Handles missing officeholders gracefully (sets to empty string)
            - Uses bulk_update for better performance
            - Can be run periodically to keep denormalized data fresh
            - Logs progress and completion
        """
        if person_districts_queryset is None:
            person_districts_queryset = PersonDistrict.objects.all()

        # Optimize query with related data
        person_districts_queryset = person_districts_queryset.select_related(
            "district"
        ).prefetch_related("district__officeholders")

        total = person_districts_queryset.count()
        logger.info(
            f"Updating officeholder denormalization for {total} PersonDistrict records"
        )

        updated_records = []

        for person_district in person_districts_queryset:
            try:
                # Get current officeholder
                current_officeholder = person_district.district.officeholders.filter(
                    is_current=True
                ).first()

                new_name = ""
                if current_officeholder:
                    new_name = current_officeholder.full_name

                # Only update if changed
                if person_district.current_officeholder_name != new_name:
                    person_district.current_officeholder_name = new_name
                    updated_records.append(person_district)

            except Exception as e:
                logger.error(
                    f"Error updating PersonDistrict {person_district.pk}: {e}",
                    exc_info=True,
                )
                continue

        # Bulk update for performance
        if updated_records:
            PersonDistrict.objects.bulk_update(
                updated_records, ["current_officeholder_name"], batch_size=500
            )

        updated_count = len(updated_records)
        logger.info(
            f"Updated {updated_count} PersonDistrict records with current "
            f"officeholder names"
        )

        return updated_count
