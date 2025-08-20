"""
Thread-local storage for audit context management.

This module provides a thread-safe way to store and retrieve audit data
without relying on private attributes on model instances. It replaces the
fragile approach of storing temporary data on models with a robust
thread-local storage system.

The audit context is managed through a context manager pattern that ensures
proper cleanup and prevents memory leaks in high-concurrency environments.
"""

import threading
import uuid
from contextlib import contextmanager
from typing import Any

from django.db import models

# Thread-local storage for audit context
_audit_locals = threading.local()


class AuditContext:
    """
    Thread-local audit context for storing audit data during model operations.

    This class provides a thread-safe way to store audit-related information
    that needs to be passed between signal handlers without modifying model
    instances directly.
    """

    def __init__(self):
        """Initialize an empty audit context."""
        self.instance_data: dict[str, dict[str, Any]] = {}
        self.active_instances: set[str] = set()

    def _get_instance_key(self, instance: models.Model) -> str:
        """
        Generate a unique key for a model instance.

        Args:
            instance: The model instance

        Returns:
            A unique string key for the instance
        """
        # Use object id and a UUID for uniqueness in case of rapid creation/deletion
        return f"{instance.__class__.__name__}_{id(instance)}_{uuid.uuid4().hex[:8]}"

    def store_instance_data(
        self,
        instance: models.Model,
        changes: dict[str, Any],
        is_new: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Store audit data for a model instance.

        Args:
            instance: The model instance
            changes: Dictionary of field changes
            is_new: Whether this is a new instance
            metadata: Additional metadata to store

        Returns:
            The unique key for this instance data
        """
        key = self._get_instance_key(instance)

        self.instance_data[key] = {
            "changes": changes,
            "is_new": is_new,
            "model_class": instance.__class__,
            "instance_id": instance.pk,
            "instance_str": str(instance),
            "metadata": metadata or {},
            "timestamp": threading.current_thread().ident,
        }

        self.active_instances.add(key)
        return key

    def get_instance_data(self, key: str) -> dict[str, Any] | None:
        """
        Retrieve audit data for an instance.

        Args:
            key: The unique key for the instance data

        Returns:
            The stored audit data or None if not found
        """
        return self.instance_data.get(key)

    def remove_instance_data(self, key: str) -> bool:
        """
        Remove audit data for an instance.

        Args:
            key: The unique key for the instance data

        Returns:
            True if data was removed, False if key not found
        """
        if key in self.instance_data:
            del self.instance_data[key]
            self.active_instances.discard(key)
            return True
        return False

    def clear(self) -> None:
        """Clear all audit data from this context."""
        self.instance_data.clear()
        self.active_instances.clear()

    def get_active_count(self) -> int:
        """Get the number of active instances being tracked."""
        return len(self.active_instances)


def get_audit_context() -> AuditContext:
    """
    Get the current thread's audit context.

    Creates a new context if one doesn't exist for this thread.

    Returns:
        The current thread's audit context
    """
    if not hasattr(_audit_locals, "context"):
        _audit_locals.context = AuditContext()
    return _audit_locals.context


def clear_audit_context() -> None:
    """
    Clear the current thread's audit context.

    This should be called at the end of request processing to prevent
    memory leaks in long-running threads.
    """
    if hasattr(_audit_locals, "context"):
        _audit_locals.context.clear()
        delattr(_audit_locals, "context")


@contextmanager
def audit_context_manager():
    """
    Context manager for audit operations.

    This ensures proper cleanup of audit context even if exceptions occur.

    Usage:
        with audit_context_manager():
            # Perform operations that require audit context
            model.save()
    """
    context = get_audit_context()
    try:
        yield context
    finally:
        # Clean up any remaining audit data
        context.clear()


class AuditContextMiddleware:
    """
    Middleware to manage audit context lifecycle.

    This middleware ensures that audit context is properly cleaned up
    at the end of each request to prevent memory leaks.
    """

    def __init__(self, get_response):
        """Initialize the middleware."""
        self.get_response = get_response

    def __call__(self, request):
        """Process request and clean up audit context."""
        try:
            response = self.get_response(request)
            return response
        finally:
            # Always clean up audit context at the end of request
            clear_audit_context()

    def process_exception(self, request, exception):
        """Clean up audit context if an exception occurs."""
        clear_audit_context()
        return None


# Utility functions for backward compatibility
def store_model_audit_data(
    instance: models.Model,
    changes: dict[str, Any],
    is_new: bool = False,
    metadata: dict[str, Any] | None = None,
) -> str:
    """
    Store audit data for a model instance.

    This is a convenience function that wraps the audit context.

    Args:
        instance: The model instance
        changes: Dictionary of field changes
        is_new: Whether this is a new instance
        metadata: Additional metadata to store

    Returns:
        The unique key for this instance data
    """
    context = get_audit_context()
    return context.store_instance_data(instance, changes, is_new, metadata)


def get_model_audit_data(key: str) -> dict[str, Any] | None:
    """
    Retrieve audit data for a model instance.

    Args:
        key: The unique key for the instance data

    Returns:
        The stored audit data or None if not found
    """
    context = get_audit_context()
    return context.get_instance_data(key)


def remove_model_audit_data(key: str) -> bool:
    """
    Remove audit data for a model instance.

    Args:
        key: The unique key for the instance data

    Returns:
        True if data was removed, False if key not found
    """
    context = get_audit_context()
    return context.remove_instance_data(key)


def get_audit_stats() -> dict[str, Any]:
    """
    Get statistics about the current audit context.

    Useful for debugging and monitoring.

    Returns:
        Dictionary with context statistics
    """
    try:
        context = get_audit_context()
        return {
            "active_instances": context.get_active_count(),
            "thread_id": threading.current_thread().ident,
            "thread_name": threading.current_thread().name,
            "context_exists": True,
        }
    except Exception:
        return {
            "active_instances": 0,
            "thread_id": threading.current_thread().ident,
            "thread_name": threading.current_thread().name,
            "context_exists": False,
        }
