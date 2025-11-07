#!/usr/bin/env python3
"""
Alert testing script for CivicPulse monitoring system.

This script tests various alert scenarios to ensure the monitoring and
alerting system is working correctly.
"""

import argparse
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class AlertTester:
    """Test monitoring alerts and escalation procedures."""

    def __init__(self, base_url: str, prometheus_url: str, alertmanager_url: str):
        self.base_url = base_url.rstrip("/")
        self.prometheus_url = prometheus_url.rstrip("/")
        self.alertmanager_url = alertmanager_url.rstrip("/")

        # Configure session with proper connection pooling and retry strategy
        self.session = requests.Session()

        # Set up retry strategy
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            backoff_factor=1,
            respect_retry_after_header=True,
        )

        # Set up HTTP adapter with connection pooling
        adapter = HTTPAdapter(
            pool_connections=10,  # Number of connection pools
            pool_maxsize=20,  # Maximum connections per pool
            max_retries=retry_strategy,
            pool_block=False,  # Don't block when pool is full
        )

        # Mount adapter for both HTTP and HTTPS
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Set reasonable timeouts
        self.session.timeout = (5, 30)  # (connect_timeout, read_timeout)

    def test_health_endpoints(self) -> dict[str, bool]:
        """Test all health check endpoints."""
        logger.info("Testing health check endpoints...")

        endpoints = {
            "basic_health": f"{self.base_url}/health/",
            "detailed_health": f"{self.base_url}/health/detailed/",
            "readiness": f"{self.base_url}/health/ready/",
            "liveness": f"{self.base_url}/health/live/",
            "metrics_summary": f"{self.base_url}/health/metrics/",
        }

        results = {}

        for name, url in endpoints.items():
            try:
                response = self.session.get(url)
                results[name] = {
                    "success": response.status_code == 200,
                    "status_code": response.status_code,
                    "response_time_ms": response.elapsed.total_seconds() * 1000,
                }

                if response.status_code == 200:
                    logger.info(
                        f"✅ {name}: OK ({response.elapsed.total_seconds():.3f}s)"
                    )
                else:
                    logger.warning(f"⚠️  {name}: HTTP {response.status_code}")

            except Exception as e:
                logger.error(f"❌ {name}: Error - {e}")
                results[name] = {"success": False, "error": str(e)}

        return results

    def test_prometheus_metrics(self) -> dict[str, bool]:
        """Test Prometheus metrics collection."""
        logger.info("Testing Prometheus metrics collection...")

        metrics_to_check = [
            "civicpulse_requests_total",
            "civicpulse_request_duration_seconds",
            "civicpulse_database_query_duration_seconds",
            "civicpulse_cache_operations_total",
            "civicpulse_authentication_events_total",
            "civicpulse_audit_events_total",
        ]

        results = {}

        for metric in metrics_to_check:
            try:
                response = self.session.get(
                    f"{self.prometheus_url}/api/v1/query", params={"query": metric}
                )

                if response.status_code == 200:
                    data = response.json()
                    has_data = len(data.get("data", {}).get("result", [])) > 0

                    results[metric] = {
                        "success": True,
                        "has_data": has_data,
                        "status_code": response.status_code,
                    }

                    if has_data:
                        logger.info(f"✅ {metric}: Data available")
                    else:
                        logger.warning(f"⚠️  {metric}: No data yet")
                else:
                    logger.error(f"❌ {metric}: HTTP {response.status_code}")
                    results[metric] = {
                        "success": False,
                        "status_code": response.status_code,
                    }

            except Exception as e:
                logger.error(f"❌ {metric}: Error - {e}")
                results[metric] = {"success": False, "error": str(e)}

        return results

    def test_alerting_rules(self) -> dict[str, bool]:
        """Test Prometheus alerting rules."""
        logger.info("Testing Prometheus alerting rules...")

        try:
            response = self.session.get(f"{self.prometheus_url}/api/v1/rules")

            if response.status_code != 200:
                logger.error(
                    f"❌ Failed to fetch alerting rules: HTTP {response.status_code}"
                )
                return {"alerting_rules": False}

            data = response.json()
            groups = data.get("data", {}).get("groups", [])

            if not groups:
                logger.warning("⚠️  No alerting rule groups found")
                return {"alerting_rules": False}

            total_rules = sum(len(group.get("rules", [])) for group in groups)
            logger.info(
                f"✅ Found {len(groups)} rule groups with {total_rules} total rules"
            )

            # Check specific rule groups
            expected_groups = [
                "civicpulse.application",
                "civicpulse.database",
                "civicpulse.redis",
                "civicpulse.infrastructure",
                "civicpulse.security",
                "civicpulse.cicd",
            ]

            found_groups = [group.get("name") for group in groups]
            missing_groups = set(expected_groups) - set(found_groups)

            if missing_groups:
                logger.warning(f"⚠️  Missing rule groups: {missing_groups}")

            return {
                "alerting_rules": True,
                "total_groups": len(groups),
                "total_rules": total_rules,
                "missing_groups": list(missing_groups),
            }

        except Exception as e:
            logger.error(f"❌ Error checking alerting rules: {e}")
            return {"alerting_rules": False, "error": str(e)}

    def simulate_load_test(
        self, duration: int = 60, concurrent_users: int = 10
    ) -> dict[str, any]:
        """Simulate load to test performance monitoring."""
        logger.info(f"Starting load test: {concurrent_users} users for {duration}s...")

        start_time = time.time()
        results = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "response_times": [],
            "errors": [],
        }

        def make_request():
            try:
                response = self.session.get(f"{self.base_url}/health/")
                response_time = response.elapsed.total_seconds()

                results["total_requests"] += 1
                results["response_times"].append(response_time)

                if response.status_code == 200:
                    results["successful_requests"] += 1
                else:
                    results["failed_requests"] += 1
                    results["errors"].append(f"HTTP {response.status_code}")

                return response.status_code == 200

            except Exception as e:
                results["total_requests"] += 1
                results["failed_requests"] += 1
                results["errors"].append(str(e))
                return False

        with ThreadPoolExecutor(max_workers=min(concurrent_users, 20)) as executor:
            while time.time() - start_time < duration:
                # Submit requests with rate limiting
                futures = [
                    executor.submit(make_request) for _ in range(concurrent_users)
                ]

                # Wait for completion with timeout
                for future in as_completed(futures, timeout=30):
                    try:
                        future.result()
                    except Exception as e:
                        logger.error(f"Request failed: {e}")

                # Rate limiting - small delay between batches
                time.sleep(0.1)

                # Brief pause to avoid overwhelming
                time.sleep(0.1)

        # Calculate statistics
        if results["response_times"]:
            results["avg_response_time"] = sum(results["response_times"]) / len(
                results["response_times"]
            )
            results["max_response_time"] = max(results["response_times"])
            results["min_response_time"] = min(results["response_times"])

            # Calculate percentiles
            sorted_times = sorted(results["response_times"])
            results["p95_response_time"] = sorted_times[int(len(sorted_times) * 0.95)]
            results["p99_response_time"] = sorted_times[int(len(sorted_times) * 0.99)]

        success_rate = (
            (results["successful_requests"] / results["total_requests"]) * 100
            if results["total_requests"] > 0
            else 0
        )

        logger.info("Load test completed:")
        logger.info(f"  Total requests: {results['total_requests']}")
        logger.info(f"  Success rate: {success_rate:.2f}%")
        logger.info(f"  Avg response time: {results.get('avg_response_time', 0):.3f}s")
        logger.info(f"  P95 response time: {results.get('p95_response_time', 0):.3f}s")

        return results

    def test_alert_escalation(self) -> dict[str, bool]:
        """Test alert escalation by checking Alertmanager."""
        logger.info("Testing alert escalation...")

        try:
            # Check Alertmanager API
            response = self.session.get(f"{self.alertmanager_url}/api/v1/alerts")

            if response.status_code != 200:
                logger.warning(
                    f"⚠️  Alertmanager not accessible: HTTP {response.status_code}"
                )
                return {"alertmanager_accessible": False}

            alerts = response.json().get("data", [])
            active_alerts = [
                alert
                for alert in alerts
                if alert.get("status", {}).get("state") == "active"
            ]

            logger.info(
                f"✅ Alertmanager accessible with {len(alerts)} total alerts "
                f"({len(active_alerts)} active)"
            )

            # Check configuration
            config_response = self.session.get(f"{self.alertmanager_url}/api/v1/status")
            if config_response.status_code == 200:
                logger.info("✅ Alertmanager configuration accessible")
                return {
                    "alertmanager_accessible": True,
                    "total_alerts": len(alerts),
                    "active_alerts": len(active_alerts),
                    "config_accessible": True,
                }
            else:
                return {
                    "alertmanager_accessible": True,
                    "total_alerts": len(alerts),
                    "active_alerts": len(active_alerts),
                    "config_accessible": False,
                }

        except Exception as e:
            logger.error(f"❌ Error testing alert escalation: {e}")
            return {"alertmanager_accessible": False, "error": str(e)}

    def simulate_failure_scenarios(self) -> dict[str, bool]:
        """Simulate various failure scenarios to test alerting."""
        logger.info("Simulating failure scenarios...")

        scenarios = {}

        # Scenario 1: High error rate simulation
        logger.info("Scenario 1: Simulating high error rate...")
        try:
            error_requests = 0
            total_error_requests = 50

            for i in range(total_error_requests):
                try:
                    # Request a non-existent endpoint to generate 404s
                    response = self.session.get(
                        f"{self.base_url}/nonexistent-endpoint-{i}"
                    )
                    if response.status_code == 404:
                        error_requests += 1
                except Exception:
                    pass

                if i % 10 == 0:
                    logger.info(
                        f"  Generated {i}/{total_error_requests} error requests..."
                    )
                    time.sleep(0.1)  # Brief pause

            scenarios["high_error_rate"] = {
                "completed": True,
                "error_requests_generated": error_requests,
            }
            logger.info(f"✅ Generated {error_requests} error requests")

        except Exception as e:
            logger.error(f"❌ Error in high error rate scenario: {e}")
            scenarios["high_error_rate"] = {"completed": False, "error": str(e)}

        # Scenario 2: Slow response simulation
        logger.info("Scenario 2: Simulating slow responses...")
        try:
            # This would typically involve hitting an endpoint that can be made slow
            # For demonstration, we'll just record this as a scenario
            scenarios["slow_response"] = {
                "completed": True,
                "note": "Would require endpoint with configurable delay",
            }
            logger.info("✅ Slow response scenario noted")

        except Exception as e:
            logger.error(f"❌ Error in slow response scenario: {e}")
            scenarios["slow_response"] = {"completed": False, "error": str(e)}

        return scenarios

    def generate_report(self, results: dict) -> str:
        """Generate a comprehensive monitoring test report."""
        logger.info("Generating monitoring test report...")

        report = {
            "timestamp": time.time(),
            "test_summary": {
                "health_endpoints": results.get("health_endpoints", {}),
                "prometheus_metrics": results.get("prometheus_metrics", {}),
                "alerting_rules": results.get("alerting_rules", {}),
                "load_test": results.get("load_test", {}),
                "alert_escalation": results.get("alert_escalation", {}),
                "failure_scenarios": results.get("failure_scenarios", {}),
            },
            "recommendations": [],
        }

        # Generate recommendations based on test results
        health_results = results.get("health_endpoints", {})
        if not all(
            endpoint.get("success", False) for endpoint in health_results.values()
        ):
            report["recommendations"].append(
                "Some health endpoints are failing - check application health"
            )

        metrics_results = results.get("prometheus_metrics", {})
        if not all(metric.get("success", False) for metric in metrics_results.values()):
            report["recommendations"].append(
                "Some Prometheus metrics are not available - check monitoring setup"
            )

        alerting_results = results.get("alerting_rules", {})
        if not alerting_results.get("alerting_rules", False):
            report["recommendations"].append(
                "Alerting rules are not properly configured"
            )

        escalation_results = results.get("alert_escalation", {})
        if not escalation_results.get("alertmanager_accessible", False):
            report["recommendations"].append(
                "Alertmanager is not accessible - check alert delivery setup"
            )

        load_results = results.get("load_test", {})
        if (
            load_results
            and load_results.get("successful_requests", 0)
            / load_results.get("total_requests", 1)
            < 0.95
        ):
            report["recommendations"].append(
                "Load test success rate below 95% - investigate performance issues"
            )

        return json.dumps(report, indent=2)

    def run_all_tests(self) -> dict:
        """Run all monitoring tests."""
        logger.info("Starting comprehensive monitoring tests...")

        results = {}

        # Test 1: Health endpoints
        results["health_endpoints"] = self.test_health_endpoints()

        # Test 2: Prometheus metrics
        results["prometheus_metrics"] = self.test_prometheus_metrics()

        # Test 3: Alerting rules
        results["alerting_rules"] = self.test_alerting_rules()

        # Test 4: Load test
        results["load_test"] = self.simulate_load_test(duration=30, concurrent_users=5)

        # Test 5: Alert escalation
        results["alert_escalation"] = self.test_alert_escalation()

        # Test 6: Failure scenarios
        results["failure_scenarios"] = self.simulate_failure_scenarios()

        return results


def main():
    """Main function to run monitoring tests."""
    parser = argparse.ArgumentParser(
        description="Test CivicPulse monitoring and alerting system"
    )
    parser.add_argument(
        "--app-url", default="http://localhost:8000", help="Application URL"
    )
    parser.add_argument(
        "--prometheus-url", default="http://localhost:9090", help="Prometheus URL"
    )
    parser.add_argument(
        "--alertmanager-url", default="http://localhost:9093", help="Alertmanager URL"
    )
    parser.add_argument("--output", help="Output file for test report")
    parser.add_argument(
        "--load-test-duration",
        type=int,
        default=30,
        help="Load test duration in seconds",
    )
    parser.add_argument(
        "--load-test-users", type=int, default=5, help="Concurrent users for load test"
    )

    args = parser.parse_args()

    # Initialize tester
    tester = AlertTester(args.app_url, args.prometheus_url, args.alertmanager_url)

    # Run tests
    try:
        results = tester.run_all_tests()

        # Generate report
        report = tester.generate_report(results)

        # Save report if output file specified
        if args.output:
            with open(args.output, "w") as f:
                f.write(report)
            logger.info(f"Test report saved to {args.output}")
        else:
            print("\n" + "=" * 60)
            print("MONITORING TEST REPORT")
            print("=" * 60)
            print(report)

        # Check overall success
        overall_success = True

        # Check critical systems
        health_success = all(
            endpoint.get("success", False)
            for endpoint in results.get("health_endpoints", {}).values()
        )
        metrics_success = all(
            metric.get("success", False)
            for metric in results.get("prometheus_metrics", {}).values()
        )
        alerting_success = results.get("alerting_rules", {}).get(
            "alerting_rules", False
        )

        if not health_success:
            logger.error("❌ Health endpoint tests failed")
            overall_success = False

        if not metrics_success:
            logger.error("❌ Prometheus metrics tests failed")
            overall_success = False

        if not alerting_success:
            logger.error("❌ Alerting rules tests failed")
            overall_success = False

        if overall_success:
            logger.info("✅ All critical monitoring tests passed")
            sys.exit(0)
        else:
            logger.error("❌ Some critical monitoring tests failed")
            sys.exit(1)

    except Exception as e:
        logger.error(f"❌ Error running monitoring tests: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
