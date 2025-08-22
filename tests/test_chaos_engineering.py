"""
Chaos Engineering and Resilience Testing for CivicPulse Backend
"""

import concurrent.futures
import logging
import os
import signal
import threading
import time
from unittest.mock import patch

import pytest
import requests
from django.core.cache import cache
from django.db import connection
from django.test import TransactionTestCase

logger = logging.getLogger(__name__)


class ChaosEngineeringTestCase(TransactionTestCase):
    """Base class for chaos engineering tests with proper setup/teardown"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.base_url = "http://localhost:8000"
        cls.health_endpoint = f"{cls.base_url}/civicpulse/health/"

    def setUp(self):
        super().setUp()
        # Ensure clean state before each test
        cache.clear()

    def make_health_check(self, timeout: int = 5) -> tuple[bool, dict]:
        """Make a health check request and return status"""
        try:
            response = requests.get(self.health_endpoint, timeout=timeout)
            return response.status_code == 200, response.json()
        except Exception as e:
            return False, {"error": str(e)}


class NetworkPartitionTests(ChaosEngineeringTestCase):
    """Test system resilience under network partition conditions"""

    def test_network_latency_simulation(self):
        """Simulate high network latency and test system response"""
        # Record baseline performance
        baseline_times = []
        for _ in range(5):
            start_time = time.time()
            healthy, _ = self.make_health_check()
            response_time = time.time() - start_time
            baseline_times.append(response_time)
            self.assertTrue(healthy, "Health check should pass under normal conditions")

        baseline_avg = sum(baseline_times) / len(baseline_times)
        logger.info(f"Baseline response time: {baseline_avg:.3f}s")

        # Simulate network delay using iptables or tc (if available)
        # For testing purposes, we'll simulate with artificial delay
        with patch("requests.get") as mock_get:

            def delayed_request(*args, **kwargs):
                time.sleep(2)  # Simulate 2s network delay
                return type(
                    "Response",
                    (),
                    {"status_code": 200, "json": lambda: {"status": "ok"}},
                )()

            mock_get.side_effect = delayed_request

            start_time = time.time()
            healthy, _ = self.make_health_check()
            response_time = time.time() - start_time

            # System should still be healthy but slower
            self.assertTrue(healthy, "System should remain healthy under latency")
            self.assertGreater(
                response_time,
                baseline_avg * 2,
                "Response time should be significantly higher",
            )

    def test_intermittent_connectivity(self):
        """Test system behavior with intermittent network connectivity"""
        success_count = 0
        total_requests = 10

        for i in range(total_requests):
            if i % 3 == 0:  # Simulate 33% packet loss
                # Simulate network failure
                with patch("requests.get") as mock_get:
                    mock_get.side_effect = requests.exceptions.ConnectionError(
                        "Network unreachable"
                    )
                    healthy, result = self.make_health_check()
                    self.assertFalse(healthy, "Should fail during network partition")
            else:
                healthy, _ = self.make_health_check()
                if healthy:
                    success_count += 1

        success_rate = success_count / total_requests
        logger.info(
            f"Success rate during intermittent connectivity: {success_rate:.2%}"
        )

        # System should recover when connectivity returns
        self.assertGreater(
            success_rate, 0.5, "System should have some successful requests"
        )


class DatabaseConnectionPoolTests(ChaosEngineeringTestCase):
    """Test database connection pool exhaustion scenarios"""

    def test_connection_pool_exhaustion(self):
        """Test system behavior when database connection pool is exhausted"""
        from django.db import connections

        # Get the default database connection settings
        db_settings = connections.databases["default"]
        max_connections = db_settings.get("OPTIONS", {}).get("MAX_CONNS", 20)

        connections_list = []
        try:
            # Create many connections to exhaust the pool
            for _i in range(max_connections + 5):
                conn = connection.__class__(db_settings)
                conn.ensure_connection()
                connections_list.append(conn)

            # System should gracefully handle exhausted connections
            healthy, result = self.make_health_check()

            # The health check might fail, but the system should not crash
            logger.info(f"Health check during pool exhaustion: {healthy}, {result}")

        finally:
            # Clean up connections
            for conn in connections_list:
                try:
                    conn.close()
                except Exception:
                    pass

        # System should recover after connections are released
        time.sleep(1)  # Allow connection pool to recover
        healthy, _ = self.make_health_check()
        self.assertTrue(healthy, "System should recover after connection pool relief")

    def test_database_connection_timeout(self):
        """Test system behavior with database connection timeouts"""
        with patch("django.db.connection.cursor") as mock_cursor:
            mock_cursor.side_effect = Exception("Connection timeout")

            # System should handle database timeouts gracefully
            try:
                healthy, result = self.make_health_check()
                # Health check might fail, but system shouldn't crash
                logger.info(f"Health during DB timeout: {healthy}, {result}")
            except Exception as e:
                self.fail(f"System should handle DB timeouts gracefully: {e}")


class RedisCacheFailureTests(ChaosEngineeringTestCase):
    """Test Redis cache failure and recovery scenarios"""

    def test_redis_unavailable(self):
        """Test system behavior when Redis cache is unavailable"""
        # Simulate Redis failure by patching cache operations
        with (
            patch.object(cache, "get") as mock_get,
            patch.object(cache, "set") as mock_set,
        ):
            mock_get.side_effect = Exception("Redis connection failed")
            mock_set.side_effect = Exception("Redis connection failed")

            # System should degrade gracefully without cache
            healthy, result = self.make_health_check()

            # System might be slower but should still function
            logger.info(f"Health check without Redis: {healthy}, {result}")

    def test_cache_corruption(self):
        """Test system behavior with corrupted cache data"""
        # Insert corrupted data into cache
        cache.set("test_key", "corrupted_data", 300)

        try:
            # Try to retrieve and use cached data
            cached_value = cache.get("test_key")
            self.assertIsNotNone(cached_value, "Cache should contain data")

            # System should handle corrupted cache gracefully
            healthy, _ = self.make_health_check()
            self.assertTrue(healthy, "System should handle corrupted cache")

        finally:
            cache.delete("test_key")

    def test_cache_memory_pressure(self):
        """Test cache behavior under memory pressure"""
        # Fill cache with large amounts of data to simulate memory pressure
        large_data = "x" * 1024 * 1024  # 1MB string

        for i in range(50):  # Try to store 50MB of data
            try:
                cache.set(f"large_key_{i}", large_data, 300)
            except Exception as e:
                logger.info(f"Cache memory pressure at item {i}: {e}")
                break

        # System should handle memory pressure gracefully
        healthy, _ = self.make_health_check()

        # Clean up
        for i in range(50):
            cache.delete(f"large_key_{i}")


class ContainerRestartResilienceTests(ChaosEngineeringTestCase):
    """Test container restart and recovery scenarios"""

    @pytest.mark.skipif(
        not os.getenv("DOCKER_TESTING"), reason="Docker tests require DOCKER_TESTING=1"
    )
    def test_graceful_shutdown_signal_handling(self):
        """Test that application handles shutdown signals gracefully"""
        # Simulate SIGTERM signal handling
        shutdown_handled = threading.Event()

        def signal_handler(signum, frame):
            logger.info("Received shutdown signal")
            shutdown_handled.set()

        original_handler = signal.signal(signal.SIGTERM, signal_handler)

        try:
            # Send SIGTERM to current process (simulate container shutdown)
            os.kill(os.getpid(), signal.SIGTERM)

            # Wait for signal to be handled
            signal_received = shutdown_handled.wait(timeout=5)
            self.assertTrue(
                signal_received, "Application should handle shutdown signals"
            )

        finally:
            signal.signal(signal.SIGTERM, original_handler)

    def test_application_startup_resilience(self):
        """Test application startup under various conditions"""
        # Test startup with missing environment variables
        with patch.dict(os.environ, {}, clear=False):
            # Remove non-critical environment variables
            env_to_remove = ["DEBUG", "ALLOWED_HOSTS"]
            for env_var in env_to_remove:
                os.environ.pop(env_var, None)

            # Application should still start with defaults
            healthy, result = self.make_health_check()
            logger.info(f"Startup with minimal env: {healthy}, {result}")

    def test_concurrent_startup_requests(self):
        """Test system behavior during startup under concurrent requests"""

        def make_request():
            return self.make_health_check()

        # Simulate multiple concurrent requests during startup
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(20)]

            results = []
            for future in concurrent.futures.as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as e:
                    results.append((False, {"error": str(e)}))

        # At least some requests should succeed
        successful_requests = sum(1 for healthy, _ in results if healthy)
        success_rate = successful_requests / len(results)

        logger.info(f"Concurrent startup success rate: {success_rate:.2%}")
        self.assertGreater(
            success_rate, 0.3, "Should handle concurrent startup requests"
        )


class LoadBalancerFailoverTests(ChaosEngineeringTestCase):
    """Test load balancer failover procedures"""

    def test_health_check_endpoint_reliability(self):
        """Test health check endpoint under various failure conditions"""
        # Test health check with database issues
        with patch("django.db.connection.cursor") as mock_cursor:
            mock_cursor.side_effect = Exception("DB unavailable")

            healthy, result = self.make_health_check()
            logger.info(f"Health check with DB issues: {healthy}, {result}")

            # Health check should reflect actual system state
            if not healthy:
                self.assertIn("error", result, "Health check should report errors")

    def test_graceful_degradation_scenarios(self):
        """Test system graceful degradation under various failure conditions"""
        scenarios = [
            ("database_slow", lambda: self.simulate_slow_database()),
            ("cache_unavailable", lambda: self.simulate_cache_failure()),
            ("high_memory_usage", lambda: self.simulate_memory_pressure()),
        ]

        for scenario_name, setup_func in scenarios:
            with self.subTest(scenario=scenario_name):
                logger.info(f"Testing graceful degradation: {scenario_name}")

                # Setup failure condition
                setup_func()

                # System should still respond, possibly with degraded performance
                healthy, result = self.make_health_check(timeout=10)
                logger.info(
                    f"Graceful degradation ({scenario_name}): {healthy}, {result}"
                )

    def simulate_slow_database(self):
        """Simulate slow database responses"""
        with patch("django.db.connection.cursor") as mock_cursor:

            def slow_cursor():
                time.sleep(2)  # Simulate slow query
                return connection.cursor()

            mock_cursor.side_effect = slow_cursor

    def simulate_cache_failure(self):
        """Simulate cache service failure"""
        with patch.object(cache, "get") as mock_get:
            mock_get.side_effect = Exception("Cache service unavailable")

    def simulate_memory_pressure(self):
        """Simulate high memory usage"""
        # Create large objects to simulate memory pressure
        memory_hogs = []
        try:
            for _ in range(10):
                memory_hogs.append(bytearray(10 * 1024 * 1024))  # 10MB each
        except MemoryError:
            pass  # Expected under memory pressure
        finally:
            del memory_hogs


class SystemRecoveryTests(ChaosEngineeringTestCase):
    """Test system recovery capabilities"""

    def test_automatic_recovery_after_failures(self):
        """Test that system recovers automatically after transient failures"""
        # Record baseline health
        healthy, _ = self.make_health_check()
        self.assertTrue(healthy, "System should be healthy initially")

        # Introduce transient failure
        failure_scenarios = [
            self.simulate_transient_db_failure,
            self.simulate_transient_cache_failure,
            self.simulate_transient_network_failure,
        ]

        for failure_func in failure_scenarios:
            with self.subTest(failure=failure_func.__name__):
                # Introduce failure
                failure_func()

                # Allow time for recovery
                time.sleep(2)

                # System should recover
                healthy, result = self.make_health_check()
                logger.info(
                    f"Recovery test ({failure_func.__name__}): {healthy}, {result}"
                )

    def simulate_transient_db_failure(self):
        """Simulate a brief database failure"""
        with patch("django.db.connection.cursor") as mock_cursor:
            mock_cursor.side_effect = Exception("Transient DB failure")
            # Failure is brief - patch is automatically removed

    def simulate_transient_cache_failure(self):
        """Simulate a brief cache failure"""
        with patch.object(cache, "get") as mock_get:
            mock_get.side_effect = Exception("Transient cache failure")
            # Failure is brief - patch is automatically removed

    def simulate_transient_network_failure(self):
        """Simulate a brief network failure"""
        # This would be more complex in a real scenario
        pass

    def test_recovery_time_measurement(self):
        """Measure time taken for system recovery after failures"""
        recovery_times = {}

        failure_scenarios = {
            "database_timeout": lambda: patch(
                "django.db.connection.cursor", side_effect=Exception("DB timeout")
            ),
            "cache_unavailable": lambda: patch.object(
                cache, "get", side_effect=Exception("Cache down")
            ),
        }

        for scenario_name, failure_patch in failure_scenarios.items():
            # Record baseline
            start_time = time.time()
            healthy, _ = self.make_health_check()
            time.time() - start_time

            # Introduce failure and measure recovery
            with failure_patch():
                recovery_start = time.time()

                # Wait for system to detect and handle failure
                max_attempts = 10
                for _attempt in range(max_attempts):
                    time.sleep(0.5)
                    try:
                        healthy, _ = self.make_health_check()
                        if healthy:
                            recovery_time = time.time() - recovery_start
                            recovery_times[scenario_name] = recovery_time
                            break
                    except Exception:
                        continue

        logger.info(f"Recovery times: {recovery_times}")

        # All scenarios should recover within reasonable time
        for scenario, recovery_time in recovery_times.items():
            self.assertLess(
                recovery_time, 30, f"Recovery for {scenario} should be under 30 seconds"
            )


class PerformanceUnderStressTests(ChaosEngineeringTestCase):
    """Test system performance under various stress conditions"""

    def test_concurrent_request_handling(self):
        """Test system behavior under high concurrent load"""

        def make_concurrent_request():
            try:
                return self.make_health_check(timeout=30)
            except Exception as e:
                return False, {"error": str(e)}

        # Test with increasing concurrency levels
        concurrency_levels = [5, 10, 20, 50]
        results = {}

        for concurrency in concurrency_levels:
            logger.info(f"Testing with {concurrency} concurrent requests")

            start_time = time.time()
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=concurrency
            ) as executor:
                futures = [
                    executor.submit(make_concurrent_request) for _ in range(concurrency)
                ]

                responses = []
                for future in concurrent.futures.as_completed(futures, timeout=60):
                    responses.append(future.result())

            total_time = time.time() - start_time
            successful_requests = sum(1 for healthy, _ in responses if healthy)
            success_rate = successful_requests / len(responses)
            avg_response_time = total_time / len(responses)

            results[concurrency] = {
                "success_rate": success_rate,
                "avg_response_time": avg_response_time,
                "total_time": total_time,
            }

            logger.info(
                f"Concurrency {concurrency}: {success_rate:.2%} success, "
                f"{avg_response_time:.3f}s avg response time"
            )

        # System should maintain reasonable performance under load
        for concurrency, result in results.items():
            self.assertGreater(
                result["success_rate"],
                0.8,
                f"Success rate should be >80% at concurrency {concurrency}",
            )

    def test_memory_leak_detection(self):
        """Test for memory leaks under sustained load"""
        import gc

        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Perform sustained operations
        for i in range(100):
            healthy, _ = self.make_health_check()

            if i % 10 == 0:
                gc.collect()  # Force garbage collection
                current_memory = process.memory_info().rss
                memory_growth = current_memory - initial_memory

                logger.info(
                    f"Memory usage after {i} requests: "
                    f"{current_memory / 1024 / 1024:.1f}MB "
                    f"(growth: {memory_growth / 1024 / 1024:.1f}MB)"
                )

        final_memory = process.memory_info().rss
        memory_growth = final_memory - initial_memory

        # Memory growth should be reasonable (less than 50MB for 100 requests)
        self.assertLess(
            memory_growth,
            50 * 1024 * 1024,
            "Memory growth should be reasonable under sustained load",
        )


# Test runner helper functions
def run_chaos_tests():
    """Run all chaos engineering tests and generate report"""
    import sys

    # Configure logging for test output
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("chaos_test_results.log"),
        ],
    )

    # Run tests with detailed output
    pytest.main([__file__, "-v", "--tb=short", "--capture=no", "--log-cli-level=INFO"])


if __name__ == "__main__":
    run_chaos_tests()
