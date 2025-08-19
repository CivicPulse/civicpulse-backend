"""
Management command to set up production environment.

This command ensures that all necessary components for production deployment
are properly configured, including cache tables and Redis connectivity.
"""

import redis
from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    """Management command to set up production environment."""

    help = "Set up production environment with Redis and cache tables"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--skip-redis-test",
            action="store_true",
            help="Skip Redis connection test",
        )
        parser.add_argument(
            "--create-cache-table",
            action="store_true",
            help="Create database cache table (for fallback)",
        )

    def handle(self, *args, **options):
        """Handle the command execution."""
        self.stdout.write(
            self.style.SUCCESS("Setting up CivicPulse production environment...")
        )

        # Test Redis connection
        if not options["skip_redis_test"]:
            self._test_redis_connection()

        # Create cache table if requested
        if options["create_cache_table"]:
            self._create_cache_table()

        # Test cache functionality
        self._test_cache()

        self.stdout.write(
            self.style.SUCCESS("Production environment setup complete!")
        )

    def _test_redis_connection(self):
        """Test Redis connection."""
        self.stdout.write("Testing Redis connection...")

        try:
            # Test Redis connection using environment variable
            redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
            redis_client = redis.from_url(redis_url)
            redis_client.ping()
            self.stdout.write(
                self.style.SUCCESS(f"✓ Redis connection successful to {redis_url}")
            )
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠ Redis connection failed: {e}. "
                    "Application will use database cache as fallback."
                )
            )

    def _create_cache_table(self):
        """Create database cache table for fallback."""
        self.stdout.write("Creating database cache table...")

        try:
            call_command("createcachetable", "civicpulse_cache_table")
            self.stdout.write(
                self.style.SUCCESS("✓ Database cache table created successfully")
            )
        except Exception as e:
            if "already exists" in str(e).lower():
                self.stdout.write(
                    self.style.WARNING("⚠ Database cache table already exists")
                )
            else:
                raise CommandError(f"Failed to create cache table: {e}") from e

    def _test_cache(self):
        """Test cache functionality."""
        self.stdout.write("Testing cache functionality...")

        try:
            # Test basic cache operations
            test_key = "civicpulse_setup_test"
            test_value = "setup_successful"

            cache.set(test_key, test_value, 60)
            retrieved_value = cache.get(test_key)

            if retrieved_value == test_value:
                self.stdout.write(
                    self.style.SUCCESS("✓ Cache functionality working correctly")
                )
            else:
                raise CommandError("Cache test failed: value mismatch")

            # Clean up test key
            cache.delete(test_key)

        except Exception as e:
            raise CommandError(f"Cache test failed: {e}") from e
