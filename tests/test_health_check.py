"""
Tests for health check and monitoring functionality.
"""

import json

from django.test import Client, TestCase
from django.urls import reverse


class HealthCheckTests(TestCase):
    """Test cases for the health check endpoint."""

    def setUp(self):
        """Set up test client."""
        self.client = Client()

    def test_health_check_endpoint_exists(self):
        """Test that the health check endpoint is accessible."""
        url = reverse("civicpulse:health_check")
        response = self.client.get(url)

        # Should return JSON response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_health_check_response_format(self):
        """Test that the health check returns expected JSON format."""
        url = reverse("civicpulse:health_check")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)

        # Check required fields exist
        self.assertIn("status", data)
        self.assertIn("timestamp", data)
        self.assertIn("version", data)
        self.assertIn("checks", data)

        # Check status is either healthy or unhealthy
        self.assertIn(data["status"], ["healthy", "unhealthy"])

        # Check version is set
        self.assertEqual(data["version"], "0.1.0")

        # Check timestamp is a number
        self.assertIsInstance(data["timestamp"], (int, float))

    def test_health_check_database_check(self):
        """Test that database connectivity is checked."""
        url = reverse("civicpulse:health_check")
        response = self.client.get(url)

        data = json.loads(response.content)

        # Should have database check
        self.assertIn("database", data["checks"])
        self.assertEqual(data["checks"]["database"], "healthy")

    def test_health_check_cache_check(self):
        """Test that cache connectivity is checked."""
        url = reverse("civicpulse:health_check")
        response = self.client.get(url)

        data = json.loads(response.content)

        # Should have cache check
        self.assertIn("cache", data["checks"])
        self.assertEqual(data["checks"]["cache"], "healthy")

    def test_health_check_overall_status(self):
        """Test that overall status is healthy when all checks pass."""
        url = reverse("civicpulse:health_check")
        response = self.client.get(url)

        data = json.loads(response.content)

        # With working database and cache, status should be healthy
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(response.status_code, 200)
