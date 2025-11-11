"""
Service layer for CivicPulse application.

This package contains business logic separated from view logic,
following the service layer pattern for better testability and reusability.
"""

from .person_service import PersonCreationService, PersonDuplicateDetector

__all__ = ["PersonCreationService", "PersonDuplicateDetector"]
