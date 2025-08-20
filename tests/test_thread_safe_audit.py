"""
Comprehensive tests for the new thread-safe audit system.

This test suite covers:
- Thread-local storage functionality
- Context manager behavior
- Signal handler improvements
- Concurrency and thread safety
- Error handling and edge cases
- Backward compatibility
"""

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase

from civicpulse.audit import AuditLog
from civicpulse.audit_context import (
    AuditContext,
    AuditContextMiddleware,
    audit_context_manager,
    clear_audit_context,
    get_audit_context,
    get_audit_stats,
    get_model_audit_data,
    remove_model_audit_data,
    store_model_audit_data,
)
from civicpulse.models import Person

User = get_user_model()


@pytest.mark.django_db
class TestAuditContext(TestCase):
    """Test the AuditContext class functionality."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser_%s" % str(uuid.uuid4())[:8],
            email="test@example.com",
        )
        self.person = Person.objects.create(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
        )

    def tearDown(self):
        """Clean up test data."""
        clear_audit_context()
        AuditLog.objects.all().delete()
        Person.objects.all().delete()
        User.objects.all().delete()

    def test_audit_context_creation(self):
        """Test creating and using an audit context."""
        context = AuditContext()
        self.assertEqual(context.get_active_count(), 0)
        self.assertEqual(len(context.instance_data), 0)

    def test_store_and_retrieve_instance_data(self):
        """Test storing and retrieving audit data for an instance."""
        context = AuditContext()
        changes = {"email": {"old": "old@test.com", "new": "new@test.com"}}
        metadata = {"test_key": "test_value"}

        # Store data
        key = context.store_instance_data(
            instance=self.person,
            changes=changes,
            is_new=False,
            metadata=metadata,
        )

        self.assertIsInstance(key, str)
        self.assertEqual(context.get_active_count(), 1)

        # Retrieve data
        retrieved_data = context.get_instance_data(key)
        self.assertIsNotNone(retrieved_data)
        self.assertEqual(retrieved_data["changes"], changes)
        self.assertEqual(retrieved_data["is_new"], False)
        self.assertEqual(retrieved_data["metadata"], metadata)
        self.assertEqual(retrieved_data["model_class"], Person)

    def test_remove_instance_data(self):
        """Test removing audit data from context."""
        context = AuditContext()
        changes = {"name": {"old": "Old", "new": "New"}}

        key = context.store_instance_data(
            instance=self.person, changes=changes, is_new=True
        )
        self.assertEqual(context.get_active_count(), 1)

        # Remove data
        removed = context.remove_instance_data(key)
        self.assertTrue(removed)
        self.assertEqual(context.get_active_count(), 0)
        self.assertIsNone(context.get_instance_data(key))

        # Try to remove non-existent key
        removed = context.remove_instance_data("non_existent_key")
        self.assertFalse(removed)

    def test_clear_context(self):
        """Test clearing all data from context."""
        context = AuditContext()

        # Store multiple instances
        for i in range(3):
            person = Person.objects.create(first_name=f"Person{i}", last_name="Test")
            context.store_instance_data(instance=person, changes={}, is_new=True)

        self.assertEqual(context.get_active_count(), 3)

        # Clear context
        context.clear()
        self.assertEqual(context.get_active_count(), 0)
        self.assertEqual(len(context.instance_data), 0)

    def test_instance_key_uniqueness(self):
        """Test that instance keys are unique even for similar instances."""
        context = AuditContext()

        # Create two instances and store data for both
        key1 = context.store_instance_data(
            instance=self.person, changes={"field1": "value1"}, is_new=False
        )
        key2 = context.store_instance_data(
            instance=self.person, changes={"field2": "value2"}, is_new=False
        )

        # Keys should be different even for the same instance
        self.assertNotEqual(key1, key2)
        self.assertEqual(context.get_active_count(), 2)

        # Data should be stored separately
        data1 = context.get_instance_data(key1)
        data2 = context.get_instance_data(key2)
        self.assertNotEqual(data1["changes"], data2["changes"])


@pytest.mark.django_db
class TestThreadLocalFunctions(TestCase):
    """Test the thread-local utility functions."""

    def setUp(self):
        """Set up test data."""
        self.person = Person.objects.create(first_name="John", last_name="Doe")

    def tearDown(self):
        """Clean up test data and context."""
        clear_audit_context()
        AuditLog.objects.all().delete()
        Person.objects.all().delete()

    def test_get_audit_context(self):
        """Test getting the current thread's audit context."""
        # Should create a new context if none exists
        context1 = get_audit_context()
        self.assertIsInstance(context1, AuditContext)

        # Should return the same context on subsequent calls
        context2 = get_audit_context()
        self.assertIs(context1, context2)

    def test_store_and_get_model_audit_data(self):
        """Test the convenience functions for storing/retrieving audit data."""
        changes = {"email": {"old": "old@test.com", "new": "new@test.com"}}
        metadata = {"source": "test"}

        # Store data using convenience function
        key = store_model_audit_data(
            instance=self.person,
            changes=changes,
            is_new=False,
            metadata=metadata,
        )

        # Retrieve data using convenience function
        retrieved_data = get_model_audit_data(key)
        self.assertIsNotNone(retrieved_data)
        self.assertEqual(retrieved_data["changes"], changes)
        self.assertEqual(retrieved_data["metadata"], metadata)

        # Remove data using convenience function
        removed = remove_model_audit_data(key)
        self.assertTrue(removed)
        self.assertIsNone(get_model_audit_data(key))

    def test_get_audit_stats(self):
        """Test getting audit context statistics."""
        # Initially should show no active instances
        stats = get_audit_stats()
        self.assertEqual(stats["active_instances"], 0)
        self.assertTrue(stats["context_exists"])
        self.assertIsNotNone(stats["thread_id"])
        self.assertIsNotNone(stats["thread_name"])

        # Add some data and check stats
        store_model_audit_data(instance=self.person, changes={}, is_new=True)
        stats = get_audit_stats()
        self.assertEqual(stats["active_instances"], 1)

    def test_clear_audit_context(self):
        """Test clearing the thread-local audit context."""
        # Store some data
        store_model_audit_data(instance=self.person, changes={}, is_new=True)
        stats = get_audit_stats()
        self.assertEqual(stats["active_instances"], 1)

        # Clear context
        clear_audit_context()
        stats = get_audit_stats()
        self.assertEqual(stats["active_instances"], 0)


@pytest.mark.django_db
class TestAuditContextManager(TestCase):
    """Test the audit context manager."""

    def setUp(self):
        """Set up test data."""
        self.person = Person.objects.create(first_name="John", last_name="Doe")

    def tearDown(self):
        """Clean up test data."""
        clear_audit_context()
        AuditLog.objects.all().delete()
        Person.objects.all().delete()

    def test_context_manager_normal_operation(self):
        """Test context manager under normal operation."""
        with audit_context_manager() as context:
            self.assertIsInstance(context, AuditContext)

            # Store some data
            key = context.store_instance_data(
                instance=self.person, changes={}, is_new=True
            )
            self.assertEqual(context.get_active_count(), 1)

        # Context should be cleared after exiting
        stats = get_audit_stats()
        self.assertEqual(stats["active_instances"], 0)

    def test_context_manager_exception_handling(self):
        """Test context manager when an exception occurs."""
        try:
            with audit_context_manager() as context:
                # Store some data
                context.store_instance_data(
                    instance=self.person, changes={}, is_new=True
                )
                self.assertEqual(context.get_active_count(), 1)

                # Raise an exception
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Context should still be cleared despite the exception
        stats = get_audit_stats()
        self.assertEqual(stats["active_instances"], 0)


@pytest.mark.django_db
class TestAuditContextMiddleware(TestCase):
    """Test the audit context middleware."""

    def setUp(self):
        """Set up middleware and mock request."""
        self.get_response = Mock(return_value=Mock())
        self.middleware = AuditContextMiddleware(self.get_response)
        self.request = Mock()

    def tearDown(self):
        """Clean up context."""
        clear_audit_context()

    def test_middleware_normal_request(self):
        """Test middleware processing a normal request."""
        # Store some audit data to simulate ongoing operations
        context = get_audit_context()
        person = Person.objects.create(first_name="Test", last_name="User")
        context.store_instance_data(instance=person, changes={}, is_new=True)
        initial_count = context.get_active_count()
        self.assertGreater(initial_count, 0)

        # Process request through middleware
        response = self.middleware(self.request)

        # Should have cleaned up audit context
        stats = get_audit_stats()
        self.assertEqual(stats["active_instances"], 0)
        self.assertTrue(self.get_response.called)

    def test_middleware_exception_handling(self):
        """Test middleware when an exception occurs."""
        # Mock an exception in get_response
        self.get_response.side_effect = ValueError("Test exception")

        # Store some audit data
        context = get_audit_context()
        person = Person.objects.create(first_name="Test", last_name="User")
        context.store_instance_data(instance=person, changes={}, is_new=True)

        # Process request (should raise exception)
        with self.assertRaises(ValueError):
            self.middleware(self.request)

        # Context should still be cleaned up
        stats = get_audit_stats()
        self.assertEqual(stats["active_instances"], 0)

    def test_process_exception_method(self):
        """Test the process_exception method directly."""
        # Store some audit data
        context = get_audit_context()
        person = Person.objects.create(first_name="Test", last_name="User")
        context.store_instance_data(instance=person, changes={}, is_new=True)

        # Call process_exception
        result = self.middleware.process_exception(self.request, ValueError("Test"))

        # Should return None and clean up context
        self.assertIsNone(result)
        stats = get_audit_stats()
        self.assertEqual(stats["active_instances"], 0)


@pytest.mark.django_db
class TestThreadSafetyAndConcurrency(TransactionTestCase):
    """Test thread safety and concurrency of the audit system."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser_%s" % str(uuid.uuid4())[:8],
            email="test@example.com",
        )

    def tearDown(self):
        """Clean up test data."""
        clear_audit_context()
        AuditLog.objects.all().delete()
        Person.objects.all().delete()
        User.objects.all().delete()

    def test_thread_isolation(self):
        """Test that audit contexts are isolated between threads."""
        results = {}
        barrier = threading.Barrier(2)

        def thread_worker(thread_id):
            """Worker function for thread isolation test."""
            try:
                # Wait for both threads to start
                barrier.wait()

                # Create audit data specific to this thread
                person = Person.objects.create(
                    first_name=f"Person{thread_id}",
                    last_name="Thread",
                )
                key = store_model_audit_data(
                    instance=person,
                    changes={"thread_id": thread_id},
                    is_new=True,
                )

                # Store thread-specific information
                context = get_audit_context()
                results[thread_id] = {
                    "key": key,
                    "active_count": context.get_active_count(),
                    "data": get_model_audit_data(key),
                    "stats": get_audit_stats(),
                }

                # Sleep to allow other thread to work
                time.sleep(0.1)

                # Verify our data is still there and isolated
                our_data = get_model_audit_data(key)
                results[thread_id]["final_data"] = our_data
                results[thread_id]["final_count"] = context.get_active_count()

            except Exception as e:
                results[thread_id] = {"error": str(e)}

        # Run two threads concurrently
        threads = []
        for i in range(2):
            thread = threading.Thread(target=thread_worker, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify results
        self.assertIn(0, results)
        self.assertIn(1, results)
        self.assertNotIn("error", results[0])
        self.assertNotIn("error", results[1])

        # Each thread should have seen only its own data
        self.assertEqual(results[0]["active_count"], 1)
        self.assertEqual(results[1]["active_count"], 1)

        # Thread IDs should be different
        self.assertNotEqual(
            results[0]["stats"]["thread_id"],
            results[1]["stats"]["thread_id"],
        )

        # Data should be thread-specific
        self.assertEqual(results[0]["data"]["changes"]["thread_id"], 0)
        self.assertEqual(results[1]["data"]["changes"]["thread_id"], 1)

    def test_concurrent_model_operations(self):
        """Test concurrent model creation with audit logging."""
        results = []
        num_threads = 5

        def create_person_worker(worker_id):
            """Worker that creates a person and checks audit logs."""
            try:
                person = Person.objects.create(
                    first_name=f"Worker{worker_id}",
                    last_name="Concurrent",
                    email=f"worker{worker_id}@test.com",
                )

                # Give time for audit signals to process
                time.sleep(0.1)

                # Check that audit log was created
                audit_logs = AuditLog.objects.filter(object_id=str(person.pk))
                return {
                    "worker_id": worker_id,
                    "person_id": person.pk,
                    "audit_count": audit_logs.count(),
                    "success": True,
                }
            except Exception as e:
                return {
                    "worker_id": worker_id,
                    "error": str(e),
                    "success": False,
                }

        # Run concurrent operations
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(create_person_worker, i) for i in range(num_threads)
            ]

            for future in as_completed(futures):
                results.append(future.result())

        # Verify all operations succeeded
        self.assertEqual(len(results), num_threads)
        for result in results:
            self.assertTrue(result["success"])
            self.assertEqual(result["audit_count"], 1)

        # Verify all persons were created
        total_persons = Person.objects.filter(last_name="Concurrent").count()
        self.assertEqual(total_persons, num_threads)

        # Verify all audit logs were created
        total_audit_logs = AuditLog.objects.filter(
            action=AuditLog.ACTION_CREATE
        ).count()
        self.assertGreaterEqual(total_audit_logs, num_threads)

    def test_error_recovery_in_concurrent_environment(self):
        """Test error recovery when audit operations fail concurrently."""
        results = []

        def worker_with_mock_failure(worker_id):
            """Worker that simulates audit failures."""
            try:
                with patch(
                    "civicpulse.audit_context.store_model_audit_data"
                ) as mock_store:
                    # Make audit storage fail for some workers
                    if worker_id % 2 == 0:
                        mock_store.side_effect = Exception("Simulated failure")
                    else:
                        mock_store.return_value = f"key_{worker_id}"

                    # This should still succeed even if audit fails
                    person = Person.objects.create(
                        first_name=f"ErrorTest{worker_id}",
                        last_name="Recovery",
                    )

                    return {
                        "worker_id": worker_id,
                        "person_id": person.pk,
                        "success": True,
                    }
            except Exception as e:
                return {
                    "worker_id": worker_id,
                    "error": str(e),
                    "success": False,
                }

        # Run concurrent operations with simulated failures
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(worker_with_mock_failure, i) for i in range(4)]

            for future in as_completed(futures):
                results.append(future.result())

        # All model operations should still succeed despite audit failures
        self.assertEqual(len(results), 4)
        for result in results:
            self.assertTrue(result["success"])

        # Verify all persons were created despite audit failures
        total_persons = Person.objects.filter(last_name="Recovery").count()
        self.assertEqual(total_persons, 4)


@pytest.mark.django_db
class TestBackwardCompatibility(TestCase):
    """Test backward compatibility with existing audit functionality."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="testuser_%s" % str(uuid.uuid4())[:8],
            email="test@example.com",
        )

    def tearDown(self):
        """Clean up test data."""
        clear_audit_context()
        AuditLog.objects.all().delete()
        Person.objects.all().delete()
        User.objects.all().delete()

    def test_audit_log_creation_still_works(self):
        """Test that AuditLog.log_action still works as expected."""
        person = Person.objects.create(
            first_name="John",
            last_name="Doe",
            email="john@test.com",
        )

        # Clear any audit logs created by signals
        AuditLog.objects.all().delete()

        # Manually create an audit log (as before)
        audit_log = AuditLog.log_action(
            action=AuditLog.ACTION_UPDATE,
            user=self.user,
            obj=person,
            message="Manual audit log",
            changes={"email": {"old": "old@test.com", "new": "new@test.com"}},
        )

        self.assertIsNotNone(audit_log)
        self.assertEqual(audit_log.action, AuditLog.ACTION_UPDATE)
        self.assertEqual(audit_log.user, self.user)
        self.assertEqual(audit_log.content_object, person)

    def test_signal_handlers_still_create_audit_logs(self):
        """Test that model signals still create audit logs."""
        # Clear existing audit logs
        AuditLog.objects.all().delete()

        # Create a person (should trigger audit signal)
        person = Person.objects.create(
            first_name="Signal",
            last_name="Test",
            email="signal@test.com",
            created_by=self.user,
        )

        # Should have created an audit log
        audit_logs = AuditLog.objects.filter(
            action=AuditLog.ACTION_CREATE,
            object_id=str(person.pk),
        )
        self.assertEqual(audit_logs.count(), 1)

        audit_log = audit_logs.first()
        self.assertEqual(audit_log.user, self.user)
        self.assertEqual(audit_log.content_object, person)

    def test_password_history_still_works(self):
        """Test that password history tracking still works."""
        from civicpulse.models import PasswordHistory

        # Clear existing password history
        PasswordHistory.objects.all().delete()

        # Create a new user (should create password history)
        new_user = User.objects.create_user(
            username="pwdtest_%s" % str(uuid.uuid4())[:8],
            email="pwd@test.com",
            password="testpass123",
        )

        # Should have created password history entry
        pwd_history = PasswordHistory.objects.filter(user=new_user)
        self.assertEqual(pwd_history.count(), 1)

        # Change password (should create another entry)
        new_user.set_password("newpass456")
        new_user.save()

        pwd_history = PasswordHistory.objects.filter(user=new_user)
        self.assertEqual(pwd_history.count(), 2)

    def test_existing_audit_queries_still_work(self):
        """Test that existing audit log queries still function."""
        # Create some audit data
        person = Person.objects.create(
            first_name="Query",
            last_name="Test",
            created_by=self.user,
        )

        # Test existing manager methods
        user_logs = AuditLog.objects.by_user(self.user)
        self.assertGreater(user_logs.count(), 0)

        object_logs = AuditLog.objects.for_object(person)
        self.assertGreater(object_logs.count(), 0)

        action_logs = AuditLog.objects.by_action(AuditLog.ACTION_CREATE)
        self.assertGreater(action_logs.count(), 0)

        # Test search functionality
        search_results = AuditLog.objects.search("Query")
        self.assertGreater(search_results.count(), 0)


@pytest.mark.django_db
class TestErrorHandlingAndEdgeCases(TestCase):
    """Test error handling and edge cases in the audit system."""

    def setUp(self):
        """Set up test data."""
        self.person = Person.objects.create(first_name="Test", last_name="Error")

    def tearDown(self):
        """Clean up test data."""
        clear_audit_context()
        AuditLog.objects.all().delete()
        Person.objects.all().delete()

    def test_invalid_audit_key_handling(self):
        """Test handling of invalid audit keys."""
        # Try to get data with invalid key
        data = get_model_audit_data("invalid_key")
        self.assertIsNone(data)

        # Try to remove data with invalid key
        removed = remove_model_audit_data("invalid_key")
        self.assertFalse(removed)

    def test_context_without_audit_key(self):
        """Test signal handling when audit key is missing."""
        # This simulates what happens if pre_save fails but post_save runs
        with patch("civicpulse.signals.logger.warning") as mock_warning:
            # Manually trigger post_save without pre_save setting up audit data
            from civicpulse.signals import audit_model_post_save

            audit_model_post_save(
                sender=Person,
                instance=self.person,
                created=False,
            )

            # Should have logged a warning about missing audit key
            mock_warning.assert_called()

    def test_audit_context_stats_when_no_context(self):
        """Test audit stats when no context exists."""
        # Clear any existing context
        clear_audit_context()

        # Mock threading local to simulate no context
        with patch("civicpulse.audit_context._audit_locals") as mock_locals:
            delattr(mock_locals, "context")
            mock_locals.context = None

            stats = get_audit_stats()
            self.assertEqual(stats["active_instances"], 0)
            self.assertFalse(stats["context_exists"])

    def test_memory_cleanup_under_stress(self):
        """Test that memory is properly cleaned up under stress."""
        initial_stats = get_audit_stats()

        # Create and clean up many audit contexts
        for i in range(100):
            with audit_context_manager() as context:
                # Store data
                person = Person.objects.create(
                    first_name=f"Stress{i}",
                    last_name="Test",
                )
                context.store_instance_data(instance=person, changes={}, is_new=True)

        # Context should be clean after all operations
        final_stats = get_audit_stats()
        self.assertEqual(final_stats["active_instances"], 0)

        # Clean up created persons
        Person.objects.filter(last_name="Test").delete()

    def test_signal_handler_exception_handling(self):
        """Test that signal handlers handle exceptions gracefully."""
        with patch("civicpulse.signals.get_model_changes") as mock_changes:
            # Make get_model_changes raise an exception
            mock_changes.side_effect = Exception("Test exception")

            with patch("civicpulse.signals.logger.error") as mock_error:
                # Create a person (should not fail even though audit fails)
                person = Person.objects.create(
                    first_name="Exception",
                    last_name="Test",
                )

                # Should have logged the error
                mock_error.assert_called()

                # Person should still be created
                self.assertIsNotNone(person.pk)
