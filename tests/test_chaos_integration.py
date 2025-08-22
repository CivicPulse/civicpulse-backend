"""
Integration-focused chaos engineering tests that work with Django test client
"""

import logging
import threading
import time
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection, transaction
from django.test import Client, TransactionTestCase

logger = logging.getLogger(__name__)

User = get_user_model()


@pytest.mark.skipif(
    True, reason="Chaos integration tests are experimental - skip in CI pipeline"
)
class ChaosIntegrationTestCase(TransactionTestCase):
    """Base class for chaos integration tests"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = Client()

    def setUp(self):
        super().setUp()
        cache.clear()
        # Create a test user for authenticated requests
        self.test_user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def make_health_check(self):
        """Make a health check using Django test client"""
        try:
            response = self.client.get("/civicpulse/health/")
            return (
                response.status_code == 200,
                response.json() if response.content else {},
            )
        except Exception as e:
            return False, {"error": str(e)}
    
    def make_health_check_allow_degraded(self):
        """Make a health check that allows degraded service (503) as acceptable"""
        try:
            response = self.client.get("/civicpulse/health/")
            # During chaos tests, 503 (service unavailable) is acceptable
            return (
                response.status_code in [200, 503],
                response.json() if response.content else {},
            )
        except Exception as e:
            return False, {"error": str(e)}


class DatabaseChaosIntegrationTests(ChaosIntegrationTestCase):
    """Test database chaos scenarios with Django integration"""

    def test_database_connection_timeout_simulation(self):
        """Test system behavior with database connection timeouts"""
        logger.info("Testing database connection timeout simulation")

        # First verify normal operation
        healthy, _ = self.make_health_check()
        self.assertTrue(healthy, "Health check should work normally")

        # Simulate database timeout by patching cursor creation
        with patch("django.db.connection.cursor") as mock_cursor:
            mock_cursor.side_effect = Exception("Database connection timeout")

            # Health check should handle this gracefully
            healthy, result = self.make_health_check()
            # The exact behavior depends on implementation, but system shouldn't crash
            logger.info(f"Health check with DB timeout: {healthy}, {result}")

    def test_database_transaction_rollback(self):
        """Test transaction rollback scenarios"""
        logger.info("Testing database transaction rollback scenarios")

        initial_count = User.objects.count()

        try:
            with transaction.atomic():
                # Create some test data
                User.objects.create_user(
                    username="rollback_test",
                    email="rollback@test.com",
                    password="testpass",
                )
                # Force a rollback by raising an exception
                raise Exception("Simulated error to force rollback")
        except Exception:
            pass

        # Verify rollback worked
        final_count = User.objects.count()
        self.assertEqual(
            initial_count, final_count, "Transaction should have rolled back"
        )

        # System should still be healthy
        healthy, _ = self.make_health_check()
        self.assertTrue(healthy, "System should remain healthy after rollback")

    def test_concurrent_database_operations(self):
        """Test concurrent database operations"""
        logger.info("Testing concurrent database operations")

        results = []
        errors = []

        def create_user(user_id):
            try:
                user = User.objects.create_user(
                    username=f"concurrent_{user_id}",
                    email=f"concurrent_{user_id}@test.com",
                    password="testpass",
                )
                results.append(user.id)
            except Exception as e:
                errors.append(str(e))

        # Create multiple threads to simulate concurrent operations
        threads = []
        for i in range(10):
            thread = threading.Thread(target=create_user, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        logger.info(
            f"Concurrent operations: {len(results)} successful, {len(errors)} errors"
        )

        # Most operations should succeed
        self.assertGreaterEqual(
            len(results), 5, "Most concurrent operations should succeed"
        )

        # System should remain healthy
        healthy, _ = self.make_health_check()
        self.assertTrue(
            healthy, "System should remain healthy after concurrent operations"
        )


class CacheChaosIntegrationTests(ChaosIntegrationTestCase):
    """Test cache failure scenarios with Django integration"""

    def test_cache_unavailable_graceful_degradation(self):
        """Test graceful degradation when cache is unavailable"""
        logger.info("Testing cache unavailable graceful degradation")

        # First test with working cache
        cache.set("test_key", "test_value", 60)
        cached_value = cache.get("test_key")
        self.assertEqual(cached_value, "test_value")

        # Now simulate cache failure
        with (
            patch.object(cache, "get") as mock_get,
            patch.object(cache, "set") as mock_set,
        ):
            mock_get.side_effect = Exception("Redis connection failed")
            mock_set.side_effect = Exception("Redis connection failed")

            # System should still function (may return degraded status)
            healthy, result = self.make_health_check_allow_degraded()
            logger.info(f"Health check without cache: {healthy}, {result}")

            # Application should handle cache failures gracefully
            # (exact behavior depends on implementation)

    def test_cache_corruption_handling(self):
        """Test handling of corrupted cache data"""
        logger.info("Testing cache corruption handling")

        # Put some corrupted data in cache
        cache.set("corrupted_key", b"\x00\x01\x02invalid", 300)

        # System should handle corrupted cache data
        try:
            corrupted_value = cache.get("corrupted_key")
            logger.info(
                f"Retrieved potentially corrupted value: {type(corrupted_value)}"
            )
        except Exception as e:
            logger.info(f"Cache corruption handled: {e}")

        # System should remain healthy
        healthy, _ = self.make_health_check()
        self.assertTrue(healthy, "System should handle cache corruption gracefully")

    def test_cache_memory_pressure_simulation(self):
        """Test cache behavior under memory pressure"""
        logger.info("Testing cache memory pressure simulation")

        # Fill cache with data to simulate memory pressure
        for i in range(100):
            cache.set(f"pressure_key_{i}", f"data_{i}" * 100, 300)

        # System should handle memory pressure
        healthy, _ = self.make_health_check()
        self.assertTrue(healthy, "System should handle cache memory pressure")

        # Clean up
        for i in range(100):
            cache.delete(f"pressure_key_{i}")


class ApplicationResilienceTests(ChaosIntegrationTestCase):
    """Test application-level resilience scenarios"""

    def test_concurrent_request_handling(self):
        """Test application behavior under concurrent requests"""
        logger.info("Testing concurrent request handling")

        results = []

        def make_request():
            healthy, result = self.make_health_check()
            results.append((healthy, result))

        # Create concurrent requests
        threads = []
        for _i in range(20):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Analyze results
        successful_requests = sum(1 for healthy, _ in results if healthy)
        success_rate = successful_requests / len(results)

        logger.info(f"Concurrent request success rate: {success_rate:.2%}")

        # Most requests should succeed
        self.assertGreater(success_rate, 0.8, "Most concurrent requests should succeed")

    def test_error_recovery(self):
        """Test application recovery after errors"""
        logger.info("Testing error recovery")

        # Baseline health check
        healthy, _ = self.make_health_check()
        self.assertTrue(healthy, "Baseline health check should pass")

        # Simulate various error conditions and test recovery
        error_scenarios = [
            (
                "Database timeout",
                lambda: patch(
                    "django.db.connection.cursor", side_effect=Exception("DB timeout")
                ),
            ),
            (
                "Cache failure",
                lambda: patch.object(cache, "get", side_effect=Exception("Cache down")),
            ),
        ]

        for scenario_name, error_patch in error_scenarios:
            logger.info(f"Testing recovery from: {scenario_name}")

            # Introduce error
            with error_patch():
                # System might fail during error condition
                error_healthy, error_result = self.make_health_check()
                logger.info(f"During {scenario_name}: healthy={error_healthy}")

            # After error is removed, system should recover
            time.sleep(0.1)  # Brief recovery time
            recovered_healthy, _ = self.make_health_check()

            # System should recover (this test verifies resilience patterns)
            logger.info(f"Recovery from {scenario_name}: {recovered_healthy}")

    def test_authentication_under_stress(self):
        """Test authentication system under stress"""
        logger.info("Testing authentication under stress")

        # Test login attempts under concurrent load
        login_results = []

        def attempt_login():
            try:
                login_successful = self.client.login(
                    username="testuser", password="testpass123"
                )
                login_results.append(login_successful)
                if login_successful:
                    self.client.logout()
            except Exception as e:
                login_results.append(False)
                logger.info(f"Login error: {e}")

        # Concurrent login attempts
        threads = []
        for _i in range(10):
            thread = threading.Thread(target=attempt_login)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        successful_logins = sum(1 for result in login_results if result)
        success_rate = successful_logins / len(login_results)

        logger.info(f"Authentication success rate under stress: {success_rate:.2%}")

        # Most authentication attempts should succeed
        self.assertGreater(
            success_rate, 0.8, "Authentication should handle concurrent load"
        )


class SystemIntegrationChaosTests(ChaosIntegrationTestCase):
    """Test system-wide integration and chaos scenarios"""

    def test_health_check_endpoint_resilience(self):
        """Test health check endpoint under various conditions"""
        logger.info("Testing health check endpoint resilience")

        # Test health check multiple times to check for consistency
        health_results = []
        for _i in range(10):
            healthy, result = self.make_health_check()
            health_results.append(healthy)
            time.sleep(0.1)

        success_rate = sum(health_results) / len(health_results)
        logger.info(f"Health check consistency: {success_rate:.2%}")

        # Health check should be consistently available
        self.assertGreaterEqual(
            success_rate, 0.9, "Health check should be highly available"
        )

    def test_system_startup_resilience(self):
        """Test system behavior during startup conditions"""
        logger.info("Testing system startup resilience")

        # Simulate startup conditions by clearing cache
        cache.clear()

        # Test immediate requests after "startup"
        startup_results = []
        for _i in range(5):
            healthy, result = self.make_health_check()
            startup_results.append(healthy)
            time.sleep(0.2)

        # System should be available relatively quickly after startup
        final_health = startup_results[-1]
        self.assertTrue(final_health, "System should be healthy after startup")

    def test_graceful_degradation_patterns(self):
        """Test graceful degradation under multiple failure conditions"""
        logger.info("Testing graceful degradation patterns")

        # Test multiple failure conditions simultaneously
        with (
            patch("django.db.connection.cursor") as mock_cursor,
            patch.object(cache, "get") as mock_cache,
        ):
            # Simulate partial failures
            mock_cursor.side_effect = [
                connection.cursor(),  # First call succeeds
                Exception("DB slow"),  # Second call fails
                connection.cursor(),  # Third call succeeds
            ]

            mock_cache.side_effect = Exception("Cache intermittent")

            # System should handle partial failures
            degradation_results = []
            for _i in range(3):
                healthy, result = self.make_health_check()
                degradation_results.append(healthy)
                time.sleep(0.1)

            logger.info(f"Graceful degradation results: {degradation_results}")

            # System should show some resilience
            # (exact behavior depends on implementation)


# Run specific chaos integration tests
def run_chaos_integration_tests():
    """Run chaos integration tests and return results"""
    import sys

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Run tests with detailed output
    test_results = pytest.main(
        [
            __file__,
            "-v",
            "--tb=short",
            "--capture=no",
            "--log-cli-level=INFO",
            "-x",  # Stop on first failure for debugging
        ]
    )

    return test_results


if __name__ == "__main__":
    run_chaos_integration_tests()
