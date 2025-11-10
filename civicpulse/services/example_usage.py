"""
Example usage of the Person service layer.

This file demonstrates how to use PersonCreationService and PersonDuplicateDetector
in various contexts (views, management commands, tasks, etc.).

NOTE: This is for documentation purposes only. Do not import or use in production.
"""

from datetime import date

from django.core.exceptions import ValidationError
from django.http import HttpRequest

from civicpulse.models import User
from civicpulse.services import PersonCreationService, PersonDuplicateDetector


def example_create_person_from_view(request: HttpRequest) -> dict:
    """
    Example: Creating a person from a Django view.

    This shows how to use the service layer in a view context.
    """
    service = PersonCreationService()

    # Person data typically comes from a form's cleaned_data
    person_data = {
        "first_name": "Jane",
        "last_name": "Smith",
        "email": "jane.smith@example.com",
        "phone_primary": "(555) 123-4567",
        "date_of_birth": date(1985, 5, 15),
        "street_address": "123 Main St",
        "city": "Springfield",
        "state": "CA",
        "zip_code": "90210",
    }

    try:
        person, duplicates = service.create_person(
            person_data=person_data, created_by=request.user, check_duplicates=True
        )

        if duplicates:
            # Handle duplicate warning - maybe show a modal to user
            return {
                "status": "warning",
                "message": f"Found {len(duplicates)} potential duplicates",
                "person": person,
                "duplicates": duplicates,
            }

        # Success case
        return {
            "status": "success",
            "message": f"Successfully created {person.full_name}",
            "person": person,
        }

    except ValidationError as e:
        # Handle validation errors - typically show in form
        return {
            "status": "error",
            "message": "Validation failed",
            "errors": e.message_dict,
        }


def example_check_duplicates_only() -> None:
    """
    Example: Checking for duplicates without creating a person.

    Useful for AJAX duplicate checks or validation endpoints.
    """
    detector = PersonDuplicateDetector()

    # Data from form or API request
    person_data = {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "date_of_birth": date(1990, 1, 1),
    }

    # Find potential duplicates
    duplicates = detector.find_duplicates(person_data)

    if duplicates.exists():
        print(f"Found {duplicates.count()} potential duplicates:")
        for dup in duplicates:
            print(f"  - {dup.full_name} ({dup.email})")
    else:
        print("No duplicates found")


def example_validate_data_before_form_submission() -> None:
    """
    Example: Pre-validating data before showing a form.

    This can be useful for multi-step forms or API validation.
    """
    service = PersonCreationService()

    person_data = {
        "first_name": "Bob",
        "last_name": "",  # Invalid - empty last name
        "email": "invalid-email",  # Invalid format
        "date_of_birth": "2030-01-01",  # Invalid - future date
        "state": "ZZ",  # Invalid state code
    }

    # Validate without creating
    errors = service.validate_person_data(person_data)

    if errors:
        print("Validation errors found:")
        for field, error_list in errors.items():
            for error in error_list:
                print(f"  {field}: {error}")
    else:
        print("Data is valid!")


def example_create_person_from_management_command() -> None:
    """
    Example: Creating a person from a Django management command.

    This shows how to use the service layer in a non-view context.
    """
    service = PersonCreationService()

    # Get a system user or use None if allowed
    try:
        system_user = User.objects.get(username="system")
    except User.DoesNotExist:
        print("System user not found - create one first")
        return

    person_data = {
        "first_name": "Import",
        "last_name": "User",
        "email": "import.user@example.com",
        "phone_primary": "+15551234567",
    }

    try:
        person, duplicates = service.create_person(
            person_data=person_data, created_by=system_user, check_duplicates=True
        )

        print(f"Created person: {person.pk}")

        if duplicates:
            print(f"Warning: {len(duplicates)} potential duplicates found")

    except ValidationError as e:
        print(f"Validation failed: {e.message_dict}")


def example_create_person_from_celery_task() -> None:
    """
    Example: Creating a person from a Celery task.

    This shows how to use the service layer in an async task context.
    """
    service = PersonCreationService()

    # In a real Celery task, you'd receive this data as task parameters
    person_data = {
        "first_name": "Task",
        "last_name": "User",
        "email": "task.user@example.com",
    }

    # Get the user who triggered the task (from task parameters)
    try:
        created_by = User.objects.get(pk="some-user-id")
    except User.DoesNotExist:
        print("User not found")
        return

    try:
        person, duplicates = service.create_person(
            person_data=person_data, created_by=created_by, check_duplicates=True
        )

        # Log or send notification about duplicates
        if duplicates:
            print(f"Task created person with {len(duplicates)} potential duplicates")

        return person.pk

    except ValidationError as e:
        # Log error and maybe send notification
        print(f"Task failed validation: {e.message_dict}")
        raise


def example_create_person_from_api() -> dict:
    """
    Example: Creating a person from a REST API endpoint.

    This shows how to use the service layer with Django REST Framework.
    """
    service = PersonCreationService()

    # In a real API view, this would come from request.data
    # and request.user would come from authentication
    person_data = {
        "first_name": "API",
        "last_name": "User",
        "email": "api.user@example.com",
        "phone_primary": "555-9876",
    }

    # Simulate request.user
    api_user = User.objects.first()

    try:
        person, duplicates = service.create_person(
            person_data=person_data, created_by=api_user, check_duplicates=True
        )

        # Return API response
        response = {
            "id": str(person.pk),
            "full_name": person.full_name,
            "created_at": person.created_at.isoformat(),
        }

        if duplicates:
            response["warnings"] = [
                {
                    "message": f"Found {len(duplicates)} potential duplicates",
                    "type": "duplicate",
                }
            ]

        return response

    except ValidationError as e:
        # Return 400 Bad Request with validation errors
        return {"error": "Validation failed", "details": e.message_dict}


def example_bulk_import_with_duplicate_detection() -> None:
    """
    Example: Bulk importing persons with duplicate detection.

    This shows how to efficiently use the service layer for bulk operations.
    """
    service = PersonCreationService()
    detector = PersonDuplicateDetector()

    # Simulate bulk data (typically from CSV or API)
    bulk_data = [
        {
            "first_name": "Alice",
            "last_name": "Johnson",
            "email": "alice@example.com",
        },
        {
            "first_name": "Bob",
            "last_name": "Williams",
            "email": "bob@example.com",
        },
        # ... more records
    ]

    import_user = User.objects.first()
    results = {"created": 0, "skipped": 0, "errors": []}

    for data in bulk_data:
        try:
            # Check for duplicates first
            duplicates = detector.find_duplicates(data)
            if duplicates.exists():
                first = data["first_name"]
                last = data["last_name"]
                print(f"Skipping {first} {last} - duplicate found")
                results["skipped"] += 1
                continue

            # Create if no duplicates (already checked above)
            person, _ = service.create_person(
                person_data=data, created_by=import_user, check_duplicates=False
            )
            results["created"] += 1

        except ValidationError as e:
            results["errors"].append({"data": data, "errors": e.message_dict})

    created = results["created"]
    skipped = results["skipped"]
    print(f"Import complete: {created} created, {skipped} skipped")


# Additional helper examples


def example_custom_validation() -> None:
    """
    Example: Adding custom validation on top of service layer.

    This shows how to extend the service layer validation.
    """
    service = PersonCreationService()

    person_data = {
        "first_name": "Custom",
        "last_name": "Validation",
        "email": "custom@example.com",
        "age": 25,  # Custom field not in model
    }

    # First, run service validation
    errors = service.validate_person_data(person_data)

    # Add your custom validation
    if person_data.get("age") and person_data["age"] < 18:
        errors.setdefault("age", []).append("Person must be 18 or older")

    if errors:
        print(f"Validation errors: {errors}")
    else:
        print("All validation passed!")


def example_transaction_rollback() -> None:
    """
    Example: How transactions work with the service layer.

    The service layer uses @transaction.atomic, so if something fails
    after person creation, the entire transaction is rolled back.
    """
    from django.db import transaction

    service = PersonCreationService()
    user = User.objects.first()

    person_data = {
        "first_name": "Transaction",
        "last_name": "Test",
        "email": "transaction@example.com",
    }

    try:
        with transaction.atomic():
            # Create person (inside service's atomic block)
            person, _ = service.create_person(
                person_data=person_data, created_by=user, check_duplicates=False
            )

            # Do something else that might fail
            # If this raises an exception, person creation is also rolled back
            # raise Exception("Something went wrong")

            print(f"Person created: {person.pk}")

    except Exception as e:
        print(f"Transaction rolled back: {e}")
        # Person was NOT saved to database


if __name__ == "__main__":
    print("This file is for documentation purposes only.")
    print("See function docstrings for usage examples.")
