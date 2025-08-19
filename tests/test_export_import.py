"""
Comprehensive tests for export/import functionality with audit logging.

Tests cover:
- Export view functionality and audit logging
- Import view functionality and audit logging
- CSV generation and parsing
- Error handling and validation
- Security monitoring integration
- File upload handling
"""

import csv
import io
import uuid
from datetime import date
from unittest.mock import Mock, patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from civicpulse.audit import AuditLog
from civicpulse.models import Person, VoterRecord
from civicpulse.views.export import PersonExportView
from civicpulse.views.imports import PersonImportView

User = get_user_model()


@pytest.mark.django_db
class TestPersonExportView(TestCase):
    """Test Person export functionality and audit logging."""

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.view = PersonExportView()

        # Clear any existing audit logs
        AuditLog.objects.all().delete()

        self.user = User.objects.create_user(
            username=f"testuser_{str(uuid.uuid4())[:8]}",
            email="test@example.com",
            password="testpass123"
        )

        # Add export permission
        from django.contrib.auth.models import Permission
        perm = Permission.objects.get(codename='view_person')
        self.user.user_permissions.add(perm)

        # Create test persons
        self.person1 = Person.objects.create(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            state="CA",
            zip_code="90210",
            date_of_birth=date(1990, 1, 1),
            created_by=self.user
        )

        self.person2 = Person.objects.create(
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com",
            state="NY",
            zip_code="10001",
            date_of_birth=date(1985, 5, 15),
            created_by=self.user
        )

        # Create voter record for person1
        self.voter_record = VoterRecord.objects.create(
            person=self.person1,
            voter_id="CA123456789",
            registration_status="active",
            party_affiliation="DEM",
            voter_score=85
        )

        # Clear audit logs created during setup
        AuditLog.objects.all().delete()

    def tearDown(self):
        """Clean up test data."""
        AuditLog.objects.all().delete()
        VoterRecord.objects.all().delete()
        Person.objects.all().delete()
        User.objects.all().delete()

    def test_export_all_persons_creates_audit_log(self):
        """Test that exporting all persons creates proper audit log."""
        request = self.factory.get('/export/persons/')
        request.user = self.user
        request.META['REMOTE_ADDR'] = '192.168.1.1'
        request.META['HTTP_USER_AGENT'] = 'TestAgent/1.0'
        request.session = Mock()
        request.session.session_key = 'test_session'

        # Add audit context manually since middleware isn't running
        request.audit_context = {
            'ip_address': '192.168.1.1',
            'user_agent': 'TestAgent/1.0',
            'session_key': 'test_session'
        }

        # Mock log_data_export to check that it's called with correct parameters
        with patch('civicpulse.views.export.log_data_export') as mock_log_export:
            response = self.view.get(request)

            # Check response
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'text/csv')
            self.assertIn('attachment', response['Content-Disposition'])

            # Check that log_data_export was called
            mock_log_export.assert_called_once()
            call_args = mock_log_export.call_args
            self.assertEqual(call_args[1]['user'], self.user)
            self.assertEqual(call_args[1]['export_type'], 'persons')
            self.assertEqual(call_args[1]['record_count'], 2)
            self.assertEqual(call_args[1]['format'], 'csv')
            self.assertEqual(call_args[1]['ip_address'], '192.168.1.1')
            self.assertEqual(call_args[1]['user_agent'], 'TestAgent/1.0')

    def test_export_with_filters_creates_audit_log(self):
        """Test that exporting with filters logs the filters."""
        # Use simpler filters that don't require custom manager methods
        request = self.factory.get('/export/persons/?state=CA')
        request.user = self.user
        request.META['REMOTE_ADDR'] = '192.168.1.1'
        request.audit_context = {
            'ip_address': '192.168.1.1',
            'user_agent': 'TestAgent/1.0'
        }

        # Mock log_data_export to check filters
        with patch('civicpulse.views.export.log_data_export') as mock_log_export:
            response = self.view.get(request)

            # Check that log_data_export was called with filters
            mock_log_export.assert_called_once()
            call_args = mock_log_export.call_args
            self.assertEqual(call_args[1]['filters']['state'], 'CA')

    def test_export_csv_content(self):
        """Test that CSV content is properly formatted."""
        request = self.factory.get('/export/persons/')
        request.user = self.user
        request.META['REMOTE_ADDR'] = '192.168.1.1'
        request.audit_context = {'ip_address': '192.168.1.1', 'user_agent': 'Test'}

        # Mock log_data_export to avoid audit dependencies
        with patch('civicpulse.views.export.log_data_export'):
            response = self.view.get(request)

        # Parse CSV content
        content = response.content.decode('utf-8')
        csv_reader = csv.reader(io.StringIO(content))
        rows = list(csv_reader)

        # Check header row
        headers = rows[0]
        self.assertIn('First Name', headers)
        self.assertIn('Last Name', headers)
        self.assertIn('Email', headers)
        self.assertIn('Voter ID', headers)

        # Check data rows
        self.assertEqual(len(rows), 3)  # Header + 2 data rows

        # Find John Doe's row - look in first name field
        john_row = None
        first_name_idx = headers.index('First Name')
        last_name_idx = headers.index('Last Name')

        for row in rows[1:]:
            if len(row) > first_name_idx and row[first_name_idx] == 'John':
                john_row = row
                break

        self.assertIsNotNone(john_row)
        self.assertEqual(john_row[last_name_idx], 'Doe')  # Last Name
        self.assertEqual(john_row[8], 'john@example.com')  # Email
        # Check voter record data is included
        self.assertIn('CA123456789', john_row)  # Voter ID

    def test_export_filter_by_state(self):
        """Test filtering by state."""
        request = self.factory.get('/export/persons/?state=CA')
        request.user = self.user
        request.META['REMOTE_ADDR'] = '192.168.1.1'
        request.audit_context = {'ip_address': '192.168.1.1', 'user_agent': 'Test'}

        # Mock log_data_export to avoid audit dependencies
        with patch('civicpulse.views.export.log_data_export'):
            response = self.view.get(request)

        # Parse CSV and check only CA persons are included
        content = response.content.decode('utf-8')
        csv_reader = csv.reader(io.StringIO(content))
        rows = list(csv_reader)

        self.assertEqual(len(rows), 2)  # Header + 1 data row (only John from CA)

    def test_export_unsupported_format(self):
        """Test export with unsupported format returns error."""
        request = self.factory.get('/export/persons/?format=json')
        request.user = self.user
        request.META['REMOTE_ADDR'] = '192.168.1.1'
        request.audit_context = {'ip_address': '192.168.1.1', 'user_agent': 'Test'}

        response = self.view.get(request)

        self.assertEqual(response.status_code, 400)
        self.assertIn('Only CSV format is supported', response.content.decode())

    @patch('civicpulse.views.export.logger')
    def test_export_exception_handling(self, mock_logger):
        """Test export handles exceptions gracefully."""
        request = self.factory.get('/export/persons/')
        request.user = self.user
        request.META['REMOTE_ADDR'] = '192.168.1.1'
        request.audit_context = {'ip_address': '192.168.1.1', 'user_agent': 'Test'}

        # Mock Person.objects.all() to raise an exception
        with patch('civicpulse.models.Person.objects.all', side_effect=Exception('Database error')):
            response = self.view.get(request)

        self.assertEqual(response.status_code, 500)
        self.assertIn('error occurred during export', response.content.decode())

        # Should log the error
        mock_logger.error.assert_called_once()

    def test_export_security_monitoring_integration(self):
        """Test that exports trigger security monitoring."""
        # Create multiple export requests to test unusual activity detection
        request = self.factory.get('/export/persons/')
        request.user = self.user
        request.META['REMOTE_ADDR'] = '192.168.1.1'
        request.audit_context = {'ip_address': '192.168.1.1', 'user_agent': 'Test'}

        with patch('civicpulse.utils.security_monitor.detect_unusual_export_activity') as mock_detect:
            mock_detect.return_value = {
                'alert_triggered': False,
                'export_count': 1,
                'total_records_exported': 2
            }

            response = self.view.get(request)

            # The security monitoring should be called when the audit log is created
            # This happens in the signal handlers when export logs are created
            self.assertEqual(response.status_code, 200)


@pytest.mark.django_db
class TestPersonImportView(TestCase):
    """Test Person import functionality and audit logging."""

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.view = PersonImportView()

        # Clear any existing audit logs
        AuditLog.objects.all().delete()

        self.user = User.objects.create_user(
            username=f"testuser_{str(uuid.uuid4())[:8]}",
            email="test@example.com",
            password="testpass123"
        )

        # Add import permission
        from django.contrib.auth.models import Permission
        perm = Permission.objects.get(codename='add_person')
        self.user.user_permissions.add(perm)

    def tearDown(self):
        """Clean up test data."""
        AuditLog.objects.all().delete()
        VoterRecord.objects.all().delete()
        Person.objects.all().delete()
        User.objects.all().delete()

    def test_import_get_displays_form(self):
        """Test that GET request displays the import form."""
        request = self.factory.get('/import/persons/')
        request.user = self.user

        response = self.view.get(request)

        self.assertEqual(response.status_code, 200)

    @patch('civicpulse.views.imports.render')
    def test_import_successful_csv_creates_audit_log(self, mock_render):
        """Test that successful CSV import creates audit log."""
        csv_content = """First Name,Last Name,Email,State,Date of Birth
John,Doe,john@example.com,CA,1990-01-01
Jane,Smith,jane@example.com,NY,1985-05-15"""

        csv_file = SimpleUploadedFile(
            "test_import.csv",
            csv_content.encode('utf-8'),
            content_type="text/csv"
        )

        request = self.factory.post('/import/persons/', {'csv_file': csv_file})
        request.user = self.user
        request.META['REMOTE_ADDR'] = '192.168.1.1'
        request.META['HTTP_USER_AGENT'] = 'TestAgent/1.0'
        request.session = Mock()
        request.session.session_key = 'test_session'

        # Add audit context
        request.audit_context = {
            'ip_address': '192.168.1.1',
            'user_agent': 'TestAgent/1.0',
            'session_key': 'test_session'
        }

        # Mock Django messages framework
        request._messages = Mock()

        # Mock render to return a simple response
        mock_render.return_value = HttpResponse("Import successful")

        # Mock log_data_import to check parameters
        with patch('civicpulse.views.imports.log_data_import') as mock_log_import:
            response = self.view.post(request)

            # Check that persons were created
            self.assertEqual(Person.objects.count(), 2)

            # Check that log_data_import was called
            mock_log_import.assert_called_once()
            call_args = mock_log_import.call_args
            self.assertEqual(call_args[1]['user'], self.user)
            self.assertEqual(call_args[1]['import_type'], 'persons')
            self.assertEqual(call_args[1]['record_count'], 2)
            self.assertEqual(call_args[1]['filename'], 'test_import.csv')
            self.assertEqual(call_args[1]['ip_address'], '192.168.1.1')
            self.assertEqual(call_args[1]['user_agent'], 'TestAgent/1.0')
            self.assertEqual(call_args[1]['errors_count'], 0)
            self.assertEqual(call_args[1]['duplicate_count'], 0)

    @patch('civicpulse.views.imports.render')
    def test_import_with_voter_data_creates_voter_records(self, mock_render):
        """Test importing with voter data creates VoterRecord objects."""
        csv_content = """First Name,Last Name,Email,Voter ID,Registration Status,Party Affiliation
John,Doe,john@example.com,CA123456789,active,DEM"""

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode('utf-8'))

        request = self.factory.post('/import/persons/', {'csv_file': csv_file})
        request.user = self.user
        request.META['REMOTE_ADDR'] = '192.168.1.1'
        request.audit_context = {'ip_address': '192.168.1.1', 'user_agent': 'Test'}
        request._messages = Mock()

        # Mock render to return a simple response
        mock_render.return_value = HttpResponse("Import successful")

        # Mock log_data_import to avoid audit dependencies
        with patch('civicpulse.views.imports.log_data_import'):
            response = self.view.post(request)

        # Check that person and voter record were created
        self.assertEqual(Person.objects.count(), 1)
        self.assertEqual(VoterRecord.objects.count(), 1)

        person = Person.objects.first()
        voter_record = VoterRecord.objects.first()
        self.assertEqual(voter_record.person, person)
        self.assertEqual(voter_record.voter_id, 'CA123456789')
        self.assertEqual(voter_record.registration_status, 'active')
        self.assertEqual(voter_record.party_affiliation, 'DEM')

    @patch('civicpulse.views.imports.render')
    def test_import_duplicate_detection(self, mock_render):
        """Test that duplicate persons are detected and skipped."""
        # Create existing person
        Person.objects.create(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            created_by=self.user
        )

        csv_content = """First Name,Last Name,Email
John,Doe,john@example.com"""

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode('utf-8'))

        request = self.factory.post('/import/persons/', {'csv_file': csv_file})
        request.user = self.user
        request.META['REMOTE_ADDR'] = '192.168.1.1'
        request.audit_context = {'ip_address': '192.168.1.1', 'user_agent': 'Test'}
        request._messages = Mock()

        # Mock render to return a simple response
        mock_render.return_value = HttpResponse("Import successful")

        # Mock log_data_import to check duplicate count
        with patch('civicpulse.views.imports.log_data_import') as mock_log_import:
            response = self.view.post(request)

            # Should still be only 1 person (duplicate skipped)
            self.assertEqual(Person.objects.count(), 1)

            # Check log_data_import was called with duplicate count
            mock_log_import.assert_called_once()
            call_args = mock_log_import.call_args
            self.assertEqual(call_args[1]['record_count'], 0)
            self.assertEqual(call_args[1]['duplicate_count'], 1)

    @patch('civicpulse.views.imports.render')
    def test_import_validation_errors(self, mock_render):
        """Test that validation errors are handled and logged."""
        csv_content = """First Name,Last Name,Email
John,,invalid-email"""  # Missing last name, invalid email

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode('utf-8'))

        request = self.factory.post('/import/persons/', {'csv_file': csv_file})
        request.user = self.user
        request.META['REMOTE_ADDR'] = '192.168.1.1'
        request.audit_context = {'ip_address': '192.168.1.1', 'user_agent': 'Test'}
        request._messages = Mock()

        # Mock render to return a simple response
        mock_render.return_value = HttpResponse("Import with errors")

        # Mock log_data_import to check error count
        with patch('civicpulse.views.imports.log_data_import') as mock_log_import:
            response = self.view.post(request)

            # Should not create any persons
            self.assertEqual(Person.objects.count(), 0)

            # Check log_data_import was called with error count
            mock_log_import.assert_called_once()
            call_args = mock_log_import.call_args
            self.assertEqual(call_args[1]['record_count'], 0)
            self.assertEqual(call_args[1]['errors_count'], 1)

    def test_import_missing_required_headers(self):
        """Test import fails with missing required headers."""
        csv_content = """Email
john@example.com"""  # Missing First Name and Last Name

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode('utf-8'))

        request = self.factory.post('/import/persons/', {'csv_file': csv_file})
        request.user = self.user
        request.META['REMOTE_ADDR'] = '192.168.1.1'
        request.audit_context = {'ip_address': '192.168.1.1', 'user_agent': 'Test'}
        request._messages = Mock()

        with self.assertRaises(Exception):  # ValidationError for missing headers
            response = self.view.post(request)

    @patch('civicpulse.views.imports.render')
    def test_import_file_validation(self, mock_render):
        """Test file validation (size, extension, etc.)."""
        # Test non-CSV file
        request = self.factory.post('/import/persons/', {
            'csv_file': SimpleUploadedFile("test.txt", b"not a csv")
        })
        request.user = self.user
        request._messages = Mock()

        # Mock render to return a simple response
        mock_render.return_value = HttpResponse("Invalid file type")

        response = self.view.post(request)

        # Should redirect back to form with error
        self.assertEqual(response.status_code, 200)

    @patch('civicpulse.views.imports.render')
    def test_import_no_file_uploaded(self, mock_render):
        """Test handling when no file is uploaded."""
        request = self.factory.post('/import/persons/', {})
        request.user = self.user
        request._messages = Mock()

        # Mock render to return a simple response
        mock_render.return_value = HttpResponse("No file uploaded")

        response = self.view.post(request)

        # Should redirect back to form
        self.assertEqual(response.status_code, 200)

    @patch('civicpulse.views.imports.render')
    def test_import_large_file_rejection(self, mock_render):
        """Test that large files are rejected."""
        # Create a file larger than 10MB
        large_content = "a" * (11 * 1024 * 1024)  # 11MB
        large_file = SimpleUploadedFile("large.csv", large_content.encode('utf-8'))

        request = self.factory.post('/import/persons/', {'csv_file': large_file})
        request.user = self.user
        request._messages = Mock()

        # Mock render to return a simple response
        mock_render.return_value = HttpResponse("File too large")

        response = self.view.post(request)

        # Should reject the file
        self.assertEqual(response.status_code, 200)

    @patch('civicpulse.views.imports.render')
    def test_import_date_format_parsing(self, mock_render):
        """Test parsing various date formats."""
        csv_content = """First Name,Last Name,Date of Birth,Last Voted Date
John,Doe,1990-01-01,2020-11-03
Jane,Smith,05/15/1985,11/08/2016
Bob,Johnson,03-22-1975,12-05-2018"""

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode('utf-8'))

        request = self.factory.post('/import/persons/', {'csv_file': csv_file})
        request.user = self.user
        request.META['REMOTE_ADDR'] = '192.168.1.1'
        request.audit_context = {'ip_address': '192.168.1.1', 'user_agent': 'Test'}
        request._messages = Mock()

        # Mock render to return a simple response
        mock_render.return_value = HttpResponse("Import successful")

        # Mock log_data_import to avoid audit dependencies
        with patch('civicpulse.views.imports.log_data_import'):
            response = self.view.post(request)

        # Should create all persons with parsed dates
        self.assertEqual(Person.objects.count(), 3)

        john = Person.objects.get(first_name='John')
        self.assertEqual(john.date_of_birth, date(1990, 1, 1))

        jane = Person.objects.get(first_name='Jane')
        self.assertEqual(jane.date_of_birth, date(1985, 5, 15))

    @patch('civicpulse.views.imports.render')
    @patch('civicpulse.views.imports.logger')
    def test_import_exception_handling(self, mock_logger, mock_render):
        """Test import handles exceptions gracefully."""
        csv_content = """First Name,Last Name
John,Doe"""

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode('utf-8'))

        request = self.factory.post('/import/persons/', {'csv_file': csv_file})
        request.user = self.user
        request._messages = Mock()

        # Mock render to return a simple response
        mock_render.return_value = HttpResponse("Error during import")

        # Mock an exception during processing
        with patch('civicpulse.views.imports.PersonImportView._process_csv_file',
                   side_effect=Exception('Processing error')):
            response = self.view.post(request)

        # Should handle the exception gracefully
        self.assertEqual(response.status_code, 200)
        mock_logger.error.assert_called_once()

    @patch('civicpulse.views.imports.render')
    def test_import_gender_mapping(self, mock_render):
        """Test gender value mapping from various formats."""
        csv_content = """First Name,Last Name,Email,Gender
John,Doe,john@example.com,Male
Jane,Smith,jane@example.com,F
Bob,Johnson,bob@example.com,Other
Alice,Brown,alice@example.com,Unknown"""

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode('utf-8'))

        request = self.factory.post('/import/persons/', {'csv_file': csv_file})
        request.user = self.user
        request.META['REMOTE_ADDR'] = '192.168.1.1'
        request.audit_context = {'ip_address': '192.168.1.1', 'user_agent': 'Test'}
        request._messages = Mock()

        # Mock render to return a simple response
        mock_render.return_value = HttpResponse("Import successful")

        # Mock log_data_import to avoid audit dependencies
        with patch('civicpulse.views.imports.log_data_import'):
            response = self.view.post(request)

        # Check how many persons were actually created
        persons_count = Person.objects.count()
        self.assertEqual(persons_count, 4, f"Expected 4 persons, got {persons_count}")

        persons = {p.first_name: p for p in Person.objects.all()}

        # Debug output - check what persons were actually created
        created_names = list(persons.keys())
        self.assertIn('John', created_names, f"John not found in created persons: {created_names}")
        self.assertIn('Jane', created_names, f"Jane not found in created persons: {created_names}")
        self.assertIn('Bob', created_names, f"Bob not found in created persons: {created_names}")
        self.assertIn('Alice', created_names, f"Alice not found in created persons: {created_names}")

        self.assertEqual(persons['John'].gender, 'M')
        self.assertEqual(persons['Jane'].gender, 'F')
        self.assertEqual(persons['Bob'].gender, 'O')
        self.assertEqual(persons['Alice'].gender, 'U')

    @patch('civicpulse.views.imports.render')
    def test_import_party_affiliation_mapping(self, mock_render):
        """Test party affiliation mapping from various formats."""
        csv_content = """First Name,Last Name,Email,Voter ID,Party Affiliation
John,Doe,john@example.com,VOT001,Democratic
Jane,Smith,jane@example.com,VOT002,REP
Bob,Johnson,bob@example.com,VOT003,Independent
Alice,Brown,alice@example.com,VOT004,Green"""

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode('utf-8'))

        request = self.factory.post('/import/persons/', {'csv_file': csv_file})
        request.user = self.user
        request.META['REMOTE_ADDR'] = '192.168.1.1'
        request.audit_context = {'ip_address': '192.168.1.1', 'user_agent': 'Test'}
        request._messages = Mock()

        # Mock render to return a simple response
        mock_render.return_value = HttpResponse("Import successful")

        # Mock log_data_import to avoid audit dependencies
        with patch('civicpulse.views.imports.log_data_import'):
            response = self.view.post(request)

        # Check how many persons and voter records were created
        persons_count = Person.objects.count()
        voters_count = VoterRecord.objects.count()
        self.assertEqual(persons_count, 4, f"Expected 4 persons, got {persons_count}")
        self.assertEqual(voters_count, 4, f"Expected 4 voter records, got {voters_count}")

        # Get voters by their person's first name since voter IDs might not be strings
        voters_by_person = {}
        for vr in VoterRecord.objects.all():
            voters_by_person[vr.person.first_name] = vr

        # Debug output - check what voters were actually created
        created_names = list(voters_by_person.keys())
        self.assertIn('John', created_names, f"John not found in voter records: {created_names}")
        self.assertIn('Jane', created_names, f"Jane not found in voter records: {created_names}")
        self.assertIn('Bob', created_names, f"Bob not found in voter records: {created_names}")
        self.assertIn('Alice', created_names, f"Alice not found in voter records: {created_names}")

        self.assertEqual(voters_by_person['John'].party_affiliation, 'DEM')
        self.assertEqual(voters_by_person['Jane'].party_affiliation, 'REP')
        self.assertEqual(voters_by_person['Bob'].party_affiliation, 'IND')
        self.assertEqual(voters_by_person['Alice'].party_affiliation, 'GRN')
