"""
Django management command to set up the development environment.
"""

import os
import secrets
import time

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = (
        "Set up the development environment with database, superuser, and initial data"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-superuser",
            action="store_true",
            help="Skip creating the default superuser",
        )
        parser.add_argument(
            "--skip-static",
            action="store_true",
            help="Skip collecting static files",
        )
        parser.add_argument(
            "--use-emoji",
            action="store_true",
            help="Include emoji characters in log messages",
        )

    def handle(self, *args, **options):
        use_emoji = options.get("use_emoji", False)
        self.use_emoji = use_emoji

        setup_msg = (
            "🔧 Setting up CivicPulse development environment..."
            if use_emoji
            else "Setting up CivicPulse development environment..."
        )
        self.stdout.write(self.style.SUCCESS(setup_msg))

        # Wait for database to be ready
        self._wait_for_database()

        # Run migrations
        self._run_migrations()

        # Create cache table
        self._create_cache_table()

        # Create superuser
        if not options["skip_superuser"]:
            self._create_superuser()

        # Collect static files
        if not options["skip_static"]:
            self._collect_static()

        complete_msg = (
            "\n✅ Development environment setup complete!"
            if self.use_emoji
            else "\nDevelopment environment setup complete!"
        )
        self.stdout.write(self.style.SUCCESS(complete_msg))

        access_msg = (
            "\n🚀 You can now access the application at http://localhost:8000"
            if self.use_emoji
            else "\nYou can now access the application at http://localhost:8000"
        )
        self.stdout.write(access_msg)

        admin_msg = (
            "🔑 Admin panel: http://localhost:8000/admin "
            "(check superuser creation output for credentials)\n"
            if self.use_emoji
            else "Admin panel: http://localhost:8000/admin "
            "(check superuser creation output for credentials)\n"
        )
        self.stdout.write(admin_msg)

    def _wait_for_database(self):
        """Wait for database to be ready."""
        wait_msg = (
            "⏳ Waiting for database to be ready..."
            if self.use_emoji
            else "Waiting for database to be ready..."
        )
        self.stdout.write(wait_msg)
        db_conn = None
        retries = 30

        while retries > 0:
            try:
                db_conn = connection.cursor()
                break
            except Exception as e:
                self.stdout.write(f"Database not ready, waiting... ({e})")
                time.sleep(1)
                retries -= 1

        if db_conn:
            ready_msg = (
                "✅ Database is ready!" if self.use_emoji else "Database is ready!"
            )
            self.stdout.write(self.style.SUCCESS(ready_msg))
        else:
            error_msg = (
                "❌ Database connection failed!"
                if self.use_emoji
                else "Database connection failed!"
            )
            self.stdout.write(self.style.ERROR(error_msg))
            raise Exception("Could not connect to database")

    def _run_migrations(self):
        """Run database migrations."""
        migrate_msg = (
            "🔄 Running database migrations..."
            if self.use_emoji
            else "Running database migrations..."
        )
        self.stdout.write(migrate_msg)
        try:
            call_command("migrate", verbosity=0)
            success_msg = (
                "✅ Migrations completed!"
                if self.use_emoji
                else "Migrations completed!"
            )
            self.stdout.write(self.style.SUCCESS(success_msg))
        except Exception as e:
            error_msg = (
                f"❌ Migration failed: {e}"
                if self.use_emoji
                else f"Migration failed: {e}"
            )
            self.stdout.write(self.style.ERROR(error_msg))
            raise

    def _create_cache_table(self):
        """Create cache table for fallback scenarios."""
        cache_msg = (
            "🗃️ Creating cache table..." if self.use_emoji else "Creating cache table..."
        )
        self.stdout.write(cache_msg)
        try:
            call_command("createcachetable", verbosity=0)
            success_msg = (
                "✅ Cache table created!" if self.use_emoji else "Cache table created!"
            )
            self.stdout.write(self.style.SUCCESS(success_msg))
        except Exception as e:
            # Cache table might already exist or not be needed
            info_msg = f"ℹ️ Cache table: {e}" if self.use_emoji else f"Cache table: {e}"
            self.stdout.write(info_msg)

    def _create_superuser(self):
        """Create default superuser if it doesn't exist."""
        create_msg = (
            "👤 Creating superuser (if needed)..."
            if self.use_emoji
            else "Creating superuser (if needed)..."
        )
        self.stdout.write(create_msg)
        User = get_user_model()

        if not User.objects.filter(username="admin").exists():
            try:
                password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
                if not password:
                    # Generate a secure random password
                    password = secrets.token_urlsafe(16)
                User.objects.create_superuser(
                    username="admin", email="admin@civicpulse.com", password=password
                )
                success_msg = (
                    f"✅ Superuser created: admin/{password}"
                    if self.use_emoji
                    else f"Superuser created: admin/{password}"
                )
                self.stdout.write(self.style.SUCCESS(success_msg))
            except Exception as e:
                error_msg = (
                    f"❌ Failed to create superuser: {e}"
                    if self.use_emoji
                    else f"Failed to create superuser: {e}"
                )
                self.stdout.write(self.style.ERROR(error_msg))
                raise
        else:
            exists_msg = (
                "ℹ️ Superuser already exists"
                if self.use_emoji
                else "Superuser already exists"
            )
            self.stdout.write(exists_msg)

    def _collect_static(self):
        """Collect static files."""
        static_msg = (
            "📁 Collecting static files..."
            if self.use_emoji
            else "Collecting static files..."
        )
        self.stdout.write(static_msg)
        try:
            call_command("collectstatic", interactive=False, verbosity=0)
            success_msg = (
                "✅ Static files collected!"
                if self.use_emoji
                else "Static files collected!"
            )
            self.stdout.write(self.style.SUCCESS(success_msg))
        except Exception as e:
            warning_msg = (
                f"⚠️ Static files: {e}" if self.use_emoji else f"Static files: {e}"
            )
            self.stdout.write(self.style.WARNING(warning_msg))
            # Don't raise exception for static files - not critical for development
