"""
Django management command to set up the development environment.
"""

import time
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.db import connection
from django.conf import settings


class Command(BaseCommand):
    help = 'Set up the development environment with database, superuser, and initial data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-superuser',
            action='store_true',
            help='Skip creating the default superuser',
        )
        parser.add_argument(
            '--skip-static',
            action='store_true',
            help='Skip collecting static files',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🔧 Setting up CivicPulse development environment...')
        )

        # Wait for database to be ready
        self._wait_for_database()

        # Run migrations
        self._run_migrations()

        # Create cache table
        self._create_cache_table()

        # Create superuser
        if not options['skip_superuser']:
            self._create_superuser()

        # Collect static files
        if not options['skip_static']:
            self._collect_static()

        self.stdout.write(
            self.style.SUCCESS('\n✅ Development environment setup complete!')
        )
        self.stdout.write(
            '\n🚀 You can now access the application at http://localhost:8000'
        )
        self.stdout.write(
            '🔑 Admin panel: http://localhost:8000/admin (admin/admin123)\n'
        )

    def _wait_for_database(self):
        """Wait for database to be ready."""
        self.stdout.write('⏳ Waiting for database to be ready...')
        db_conn = None
        retries = 30
        
        while retries > 0:
            try:
                db_conn = connection.cursor()
                break
            except Exception as e:
                self.stdout.write(f'Database not ready, waiting... ({e})')
                time.sleep(1)
                retries -= 1
        
        if db_conn:
            self.stdout.write(self.style.SUCCESS('✅ Database is ready!'))
        else:
            self.stdout.write(self.style.ERROR('❌ Database connection failed!'))
            raise Exception('Could not connect to database')

    def _run_migrations(self):
        """Run database migrations."""
        self.stdout.write('🔄 Running database migrations...')
        try:
            call_command('migrate', verbosity=0)
            self.stdout.write(self.style.SUCCESS('✅ Migrations completed!'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Migration failed: {e}'))
            raise

    def _create_cache_table(self):
        """Create cache table for fallback scenarios."""
        self.stdout.write('🗃️ Creating cache table...')
        try:
            call_command('createcachetable', verbosity=0)
            self.stdout.write(self.style.SUCCESS('✅ Cache table created!'))
        except Exception as e:
            # Cache table might already exist or not be needed
            self.stdout.write(f'ℹ️ Cache table: {e}')

    def _create_superuser(self):
        """Create default superuser if it doesn't exist."""
        self.stdout.write('👤 Creating superuser (if needed)...')
        User = get_user_model()
        
        if not User.objects.filter(username='admin').exists():
            try:
                User.objects.create_superuser(
                    username='admin',
                    email='admin@civicpulse.com',
                    password='admin123'
                )
                self.stdout.write(
                    self.style.SUCCESS('✅ Superuser created: admin/admin123')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Failed to create superuser: {e}')
                )
                raise
        else:
            self.stdout.write('ℹ️ Superuser already exists')

    def _collect_static(self):
        """Collect static files."""
        self.stdout.write('📁 Collecting static files...')
        try:
            call_command('collectstatic', interactive=False, verbosity=0)
            self.stdout.write(self.style.SUCCESS('✅ Static files collected!'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'⚠️ Static files: {e}'))
            # Don't raise exception for static files - not critical for development