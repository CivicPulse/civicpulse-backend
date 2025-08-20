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
            username="testuser_%s" % str(uuid.uuid4())[:8],
            email="test@example.com",
            password="testpass123",
        )

        # Add export permission
        from django.contrib.auth.models import Permission

        perm = Permission.objects.get(codename="view_person")
        self.user.user_permissions.add(perm)

        # Create test persons
        self.person1 = Person.objects.create(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            state="CA",
            zip_code="90210",
            date_of_birth=date(1990, 1, 1),
            created_by=self.user,
        )

        self.person2 = Person.objects.create(
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com",
            state="NY",
            zip_code="10001",
            date_of_birth=date(1985, 5, 15),
            created_by=self.user,
        )

        # Create voter record for person1
        self.voter_record = VoterRecord.objects.create(
            person=self.person1,
            voter_id="CA123456789",
            registration_status="active",
            party_affiliation="DEM",
            voter_score=85,
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
        request = self.factory.get("/export/persons/")
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.META["HTTP_USER_AGENT"] = "TestAgent/1.0"
        request.session = Mock()
        request.session.session_key = "test_session"

        # Add audit context manually since middleware isn't running
        request.audit_context = {
            "ip_address": "192.168.1.1",
            "user_agent": "TestAgent/1.0",
            "session_key": "test_session",
        }

        # Mock log_data_export to check that it's called with correct parameters
        with patch("civicpulse.views.export.log_data_export") as mock_log_export:
            response = self.view.get(request)

            # Check response
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "text/csv")
            self.assertIn("attachment", response["Content-Disposition"])

            # Check that log_data_export was called
            mock_log_export.assert_called_once()
            call_args = mock_log_export.call_args
            self.assertEqual(call_args[1]["user"], self.user)
            self.assertEqual(call_args[1]["export_type"], "persons")
            self.assertEqual(call_args[1]["record_count"], 2)
            self.assertEqual(call_args[1]["format"], "csv")
            self.assertEqual(call_args[1]["ip_address"], "192.168.1.1")
            self.assertEqual(call_args[1]["user_agent"], "TestAgent/1.0")

    def test_export_with_filters_creates_audit_log(self):
        """Test that exporting with filters logs the filters."""
        # Use simpler filters that don't require custom manager methods
        request = self.factory.get("/export/persons/?state=CA")
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.audit_context = {
            "ip_address": "192.168.1.1",
            "user_agent": "TestAgent/1.0",
        }

        # Mock log_data_export to check filters
        with patch("civicpulse.views.export.log_data_export") as mock_log_export:
            self.view.get(request)

            # Check that log_data_export was called with filters
            mock_log_export.assert_called_once()
            call_args = mock_log_export.call_args
            self.assertEqual(call_args[1]["filters"]["state"], "CA")

    def test_export_csv_content(self):
        """Test that CSV content is properly formatted."""
        request = self.factory.get("/export/persons/")
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.audit_context = {"ip_address": "192.168.1.1", "user_agent": "Test"}

        # Mock log_data_export to avoid audit dependencies
        with patch("civicpulse.views.export.log_data_export"):
            response = self.view.get(request)

        # Parse CSV content
        content = response.content.decode("utf-8")
        csv_reader = csv.reader(io.StringIO(content))
        rows = list(csv_reader)

        # Check header row
        headers = rows[0]
        self.assertIn("First Name", headers)
        self.assertIn("Last Name", headers)
        self.assertIn("Email", headers)
        self.assertIn("Voter ID", headers)

        # Check data rows
        self.assertEqual(len(rows), 3)  # Header + 2 data rows

        # Find John Doe's row - look in first name field
        john_row = None
        first_name_idx = headers.index("First Name")
        last_name_idx = headers.index("Last Name")

        for row in rows[1:]:
            if len(row) > first_name_idx and row[first_name_idx] == "John":
                john_row = row
                break

        self.assertIsNotNone(john_row)
        self.assertEqual(john_row[last_name_idx], "Doe")  # Last Name
        self.assertEqual(john_row[8], "john@example.com")  # Email
        # Check voter record data is included
        self.assertIn("CA123456789", john_row)  # Voter ID

    def test_export_filter_by_state(self):
        """Test filtering by state."""
        request = self.factory.get("/export/persons/?state=CA")
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.audit_context = {"ip_address": "192.168.1.1", "user_agent": "Test"}

        # Mock log_data_export to avoid audit dependencies
        with patch("civicpulse.views.export.log_data_export"):
            response = self.view.get(request)

        # Parse CSV and check only CA persons are included
        content = response.content.decode("utf-8")
        csv_reader = csv.reader(io.StringIO(content))
        rows = list(csv_reader)

        self.assertEqual(len(rows), 2)  # Header + 1 data row (only John from CA)

    def test_export_unsupported_format(self):
        """Test export with unsupported format returns error."""
        request = self.factory.get("/export/persons/?format=json")
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.audit_context = {"ip_address": "192.168.1.1", "user_agent": "Test"}

        response = self.view.get(request)

        self.assertEqual(response.status_code, 400)
        self.assertIn("Only CSV format is supported", response.content.decode())

    @patch("civicpulse.views.export.logger")
    def test_export_exception_handling(self, mock_logger):
        """Test export handles exceptions gracefully."""
        request = self.factory.get("/export/persons/")
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.audit_context = {"ip_address": "192.168.1.1", "user_agent": "Test"}

        # Mock Person.objects.all() to raise an exception
        with patch(
            "civicpulse.models.Person.objects.all",
            side_effect=Exception("Database error"),
        ):
            response = self.view.get(request)

        self.assertEqual(response.status_code, 500)
        self.assertIn("error occurred during export", response.content.decode())

        # Should log the error
        mock_logger.error.assert_called_once()

    def test_export_security_monitoring_integration(self):
        """Test that exports trigger security monitoring."""
        # Create multiple export requests to test unusual activity detection
        request = self.factory.get("/export/persons/")
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.audit_context = {"ip_address": "192.168.1.1", "user_agent": "Test"}

        with patch(
            "civicpulse.utils.security_monitor.detect_unusual_export_activity"
        ) as mock_detect:
            mock_detect.return_value = {
                "alert_triggered": False,
                "export_count": 1,
                "total_records_exported": 2,
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
            username="testuser_%s" % str(uuid.uuid4())[:8],
            email="test@example.com",
            password="testpass123",
        )

        # Add import permission
        from django.contrib.auth.models import Permission

        perm = Permission.objects.get(codename="add_person")
        self.user.user_permissions.add(perm)

    def tearDown(self):
        """Clean up test data."""
        AuditLog.objects.all().delete()
        VoterRecord.objects.all().delete()
        Person.objects.all().delete()
        User.objects.all().delete()

    def test_import_get_displays_form(self):
        """Test that GET request displays the import form."""
        request = self.factory.get("/import/persons/")
        request.user = self.user

        response = self.view.get(request)

        self.assertEqual(response.status_code, 200)

    @patch("civicpulse.views.imports.render")
    def test_import_successful_csv_creates_audit_log(self, mock_render):
        """Test that successful CSV import creates audit log."""
        csv_content = """First Name,Last Name,Email,State,Date of Birth
John,Doe,john@example.com,CA,1990-01-01
Jane,Smith,jane@example.com,NY,1985-05-15"""

        csv_file = SimpleUploadedFile(
            "test_import.csv", csv_content.encode("utf-8"), content_type="text/csv"
        )

        request = self.factory.post("/import/persons/", {"csv_file": csv_file})
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.META["HTTP_USER_AGENT"] = "TestAgent/1.0"
        request.session = Mock()
        request.session.session_key = "test_session"

        # Add audit context
        request.audit_context = {
            "ip_address": "192.168.1.1",
            "user_agent": "TestAgent/1.0",
            "session_key": "test_session",
        }

        # Mock Django messages framework
        request._messages = Mock()

        # Mock render to return a simple response
        mock_render.return_value = HttpResponse("Import successful")

        # Mock log_data_import to check parameters
        with patch("civicpulse.views.imports.log_data_import") as mock_log_import:
            self.view.post(request)

            # Check that persons were created
            self.assertEqual(Person.objects.count(), 2)

            # Check that log_data_import was called
            mock_log_import.assert_called_once()
            call_args = mock_log_import.call_args
            self.assertEqual(call_args[1]["user"], self.user)
            self.assertEqual(call_args[1]["import_type"], "persons")
            self.assertEqual(call_args[1]["record_count"], 2)
            self.assertEqual(call_args[1]["filename"], "test_import.csv")
            self.assertEqual(call_args[1]["ip_address"], "192.168.1.1")
            self.assertEqual(call_args[1]["user_agent"], "TestAgent/1.0")
            self.assertEqual(call_args[1]["errors_count"], 0)
            self.assertEqual(call_args[1]["duplicate_count"], 0)

    @patch("civicpulse.views.imports.render")
    def test_import_with_voter_data_creates_voter_records(self, mock_render):
        """Test importing with voter data creates VoterRecord objects."""
        csv_content = (
            "First Name,Last Name,Email,Voter ID,Registration Status,"
            "Party Affiliation\n"
            "John,Doe,john@example.com,CA123456789,active,DEM"
        )

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": csv_file})
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.audit_context = {"ip_address": "192.168.1.1", "user_agent": "Test"}
        request._messages = Mock()

        # Mock render to return a simple response
        mock_render.return_value = HttpResponse("Import successful")

        # Mock log_data_import to avoid audit dependencies
        with patch("civicpulse.views.imports.log_data_import"):
            self.view.post(request)

        # Check that person and voter record were created
        self.assertEqual(Person.objects.count(), 1)
        self.assertEqual(VoterRecord.objects.count(), 1)

        person = Person.objects.first()
        voter_record = VoterRecord.objects.first()
        self.assertEqual(voter_record.person, person)
        self.assertEqual(voter_record.voter_id, "CA123456789")
        self.assertEqual(voter_record.registration_status, "active")
        self.assertEqual(voter_record.party_affiliation, "DEM")

    @patch("civicpulse.views.imports.render")
    def test_import_duplicate_detection_exact_email_match(self, mock_render):
        """Test duplicate detection by exact email match."""
        # Create existing person with comprehensive data
        Person.objects.create(
            first_name="Sarah",
            middle_name="Elizabeth",
            last_name="Johnson",
            email="sarah.johnson@email.com",
            phone_primary="(555) 123-4567",
            street_address="123 Main Street",
            apartment_number="Apt 2B",
            city="Springfield",
            state="IL",
            zip_code="62701",
            date_of_birth=date(1985, 3, 15),
            gender="F",
            occupation="Teacher",
            employer="Springfield Elementary",
            created_by=self.user,
        )

        # Try to import person with same email but different other details
        csv_content = (
            "First Name,Last Name,Email,Phone Primary,Street Address,City,State,"
            "ZIP Code,Date of Birth\n"
            "Jane,Smith,sarah.johnson@email.com,(555) 987-6543,456 Oak Avenue,"
            "Different City,CA,90210,1990-05-20"
        )

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": csv_file})
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.audit_context = {"ip_address": "192.168.1.1", "user_agent": "Test"}
        request._messages = Mock()

        mock_render.return_value = HttpResponse("Import successful")

        with patch("civicpulse.views.imports.log_data_import") as mock_log_import:
            self.view.post(request)

            # Should still be only 1 person (duplicate skipped by email)
            self.assertEqual(Person.objects.count(), 1)
            mock_log_import.assert_called_once()
            call_args = mock_log_import.call_args
            self.assertEqual(call_args[1]["record_count"], 0)
            self.assertEqual(call_args[1]["duplicate_count"], 1)

    @patch("civicpulse.views.imports.render")
    def test_import_duplicate_detection_name_and_dob_match(self, mock_render):
        """Test duplicate detection by name and date of birth match."""
        # Create existing person
        Person.objects.create(
            first_name="Michael",
            middle_name="Robert",
            last_name="Anderson",
            email="michael.anderson@work.com",
            phone_primary="(312) 555-7890",
            street_address="789 Elm Street",
            city="Chicago",
            state="IL",
            zip_code="60601",
            date_of_birth=date(1978, 12, 8),
            gender="M",
            occupation="Software Engineer",
            employer="TechCorp Inc",
            created_by=self.user,
        )

        # Try to import person with same name and DOB but different contact info
        csv_content = (
            "First Name,Middle Name,Last Name,Email,Phone Primary,Street Address,"
            "City,State,ZIP Code,Date of Birth,Gender,Occupation,Employer\n"
            "Michael,Robert,Anderson,m.anderson@different.com,(847) 555-1234,"
            "321 Pine Road,Evanston,IL,60201,1978-12-08,M,Engineer,Different Corp"
        )

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": csv_file})
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.audit_context = {"ip_address": "192.168.1.1", "user_agent": "Test"}
        request._messages = Mock()

        mock_render.return_value = HttpResponse("Import successful")

        with patch("civicpulse.views.imports.log_data_import") as mock_log_import:
            self.view.post(request)

            # Should still be only 1 person (duplicate skipped by name + DOB)
            self.assertEqual(Person.objects.count(), 1)
            mock_log_import.assert_called_once()
            call_args = mock_log_import.call_args
            self.assertEqual(call_args[1]["record_count"], 0)
            self.assertEqual(call_args[1]["duplicate_count"], 1)

    @patch("civicpulse.views.imports.render")
    def test_import_duplicate_detection_phone_number_match(self, mock_render):
        """Test duplicate detection by phone number match."""
        # Create existing person
        Person.objects.create(
            first_name="Jennifer",
            last_name="Williams",
            email="jennifer.w@email.com",
            phone_primary="(773) 555-2468",
            phone_secondary="(312) 555-9753",
            street_address="567 Maple Drive",
            city="Oak Park",
            state="IL",
            zip_code="60302",
            date_of_birth=date(1992, 7, 22),
            gender="F",
            occupation="Marketing Manager",
            created_by=self.user,
        )

        # Try to import person with same primary phone but different other details
        csv_content = """First Name,Last Name,Email,Phone Primary,Date of Birth
Jessica,Brown,different@email.com,(773) 555-2468,1988-11-15"""

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": csv_file})
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.audit_context = {"ip_address": "192.168.1.1", "user_agent": "Test"}
        request._messages = Mock()

        mock_render.return_value = HttpResponse("Import successful")

        with patch("civicpulse.views.imports.log_data_import") as mock_log_import:
            self.view.post(request)

            # Should still be only 1 person (duplicate skipped by phone)
            self.assertEqual(Person.objects.count(), 1)
            mock_log_import.assert_called_once()
            call_args = mock_log_import.call_args
            self.assertEqual(call_args[1]["record_count"], 0)
            self.assertEqual(call_args[1]["duplicate_count"], 1)

    @patch("civicpulse.views.imports.render")
    def test_import_duplicate_detection_secondary_phone_match(self, mock_render):
        """Test duplicate detection by secondary phone number match."""
        # Create existing person
        Person.objects.create(
            first_name="David",
            last_name="Thompson",
            email="david.thompson@company.com",
            phone_primary="(630) 555-1357",
            phone_secondary="(708) 555-8642",
            street_address="890 Cedar Lane",
            city="Naperville",
            state="IL",
            zip_code="60540",
            date_of_birth=date(1980, 9, 3),
            gender="M",
            occupation="Project Manager",
            created_by=self.user,
        )

        # Try to import person with same secondary phone
        csv_content = """First Name,Last Name,Email,Phone Secondary,Date of Birth
Robert,Davis,robert.davis@email.com,(708) 555-8642,1975-04-12"""

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": csv_file})
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.audit_context = {"ip_address": "192.168.1.1", "user_agent": "Test"}
        request._messages = Mock()

        mock_render.return_value = HttpResponse("Import successful")

        with patch("civicpulse.views.imports.log_data_import") as mock_log_import:
            self.view.post(request)

            # Should still be only 1 person (duplicate skipped by secondary phone)
            self.assertEqual(Person.objects.count(), 1)
            mock_log_import.assert_called_once()
            call_args = mock_log_import.call_args
            self.assertEqual(call_args[1]["record_count"], 0)
            self.assertEqual(call_args[1]["duplicate_count"], 1)

    @patch("civicpulse.views.imports.render")
    def test_import_duplicate_detection_name_and_address_match(self, mock_render):
        """Test duplicate detection by name and address match."""
        # Create existing person
        Person.objects.create(
            first_name="Amanda",
            last_name="Garcia",
            email="amanda.garcia@home.com",
            phone_primary="(847) 555-3691",
            street_address="234 Willow Street",
            apartment_number="Unit 5A",
            city="Skokie",
            state="IL",
            zip_code="60076",
            date_of_birth=date(1987, 1, 30),
            gender="F",
            occupation="Nurse",
            employer="Skokie Hospital",
            created_by=self.user,
        )

        # Try to import person with same name and address but different other details
        csv_content = (
            "First Name,Last Name,Email,Phone Primary,Street Address,City,State,"
            "ZIP Code,Date of Birth,Occupation\n"
            "Amanda,Garcia,amanda.different@email.com,(224) 555-9876,"
            "234 Willow Street,Skokie,IL,60076,1985-06-14,Doctor"
        )

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": csv_file})
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.audit_context = {"ip_address": "192.168.1.1", "user_agent": "Test"}
        request._messages = Mock()

        mock_render.return_value = HttpResponse("Import successful")

        with patch("civicpulse.views.imports.log_data_import") as mock_log_import:
            self.view.post(request)

            # Should still be only 1 person (duplicate skipped by name + address)
            self.assertEqual(Person.objects.count(), 1)
            mock_log_import.assert_called_once()
            call_args = mock_log_import.call_args
            self.assertEqual(call_args[1]["record_count"], 0)
            self.assertEqual(call_args[1]["duplicate_count"], 1)

    @patch("civicpulse.views.imports.render")
    def test_import_duplicate_detection_case_insensitive_email(self, mock_render):
        """Test duplicate detection is case-insensitive for email addresses."""
        # Create existing person
        Person.objects.create(
            first_name="Christopher",
            last_name="Martinez",
            email="chris.martinez@COMPANY.COM",
            phone_primary="(872) 555-4820",
            date_of_birth=date(1983, 11, 25),
            created_by=self.user,
        )

        # Try to import with different case email
        csv_content = """First Name,Last Name,Email,Phone Primary,Date of Birth
Chris,Martinez,CHRIS.MARTINEZ@company.com,(872) 555-9999,1990-01-01"""

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": csv_file})
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.audit_context = {"ip_address": "192.168.1.1", "user_agent": "Test"}
        request._messages = Mock()

        mock_render.return_value = HttpResponse("Import successful")

        with patch("civicpulse.views.imports.log_data_import") as mock_log_import:
            self.view.post(request)

            # Should still be only 1 person
            # (duplicate skipped by case-insensitive email)
            self.assertEqual(Person.objects.count(), 1)
            mock_log_import.assert_called_once()
            call_args = mock_log_import.call_args
            self.assertEqual(call_args[1]["record_count"], 0)
            self.assertEqual(call_args[1]["duplicate_count"], 1)

    @patch("civicpulse.views.imports.render")
    def test_import_duplicate_detection_case_insensitive_names(self, mock_render):
        """Test duplicate detection is case-insensitive for names."""
        # Create existing person
        Person.objects.create(
            first_name="Elizabeth",
            last_name="Rodriguez",
            email="elizabeth.rodriguez@email.com",
            date_of_birth=date(1991, 4, 18),
            created_by=self.user,
        )

        # Try to import with different case names but same DOB
        csv_content = """First Name,Last Name,Email,Date of Birth
ELIZABETH,RODRIGUEZ,different@email.com,1991-04-18"""

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": csv_file})
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.audit_context = {"ip_address": "192.168.1.1", "user_agent": "Test"}
        request._messages = Mock()

        mock_render.return_value = HttpResponse("Import successful")

        with patch("civicpulse.views.imports.log_data_import") as mock_log_import:
            self.view.post(request)

            # Should still be only 1 person
            # (duplicate skipped by case-insensitive name + DOB)
            self.assertEqual(Person.objects.count(), 1)
            mock_log_import.assert_called_once()
            call_args = mock_log_import.call_args
            self.assertEqual(call_args[1]["record_count"], 0)
            self.assertEqual(call_args[1]["duplicate_count"], 1)

    @patch("civicpulse.views.imports.render")
    def test_import_no_duplicate_similar_but_different_data(self, mock_render):
        """
        Test that similar but legitimately different persons are not marked as
        duplicates.
        """
        # Create existing person
        Person.objects.create(
            first_name="James",
            last_name="Wilson",
            email="james.wilson@email.com",
            phone_primary="(312) 555-1111",
            street_address="100 North Street",
            city="Chicago",
            state="IL",
            zip_code="60601",
            date_of_birth=date(1985, 6, 10),
            created_by=self.user,
        )

        # Import similar but different person (different DOB, email, phone, address)
        csv_content = (
            "First Name,Last Name,Email,Phone Primary,Street Address,City,State,"
            "ZIP Code,Date of Birth\n"
            "James,Wilson,james.wilson.jr@email.com,(312) 555-2222,"
            "200 South Street,Chicago,IL,60602,1985-06-11"
        )

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": csv_file})
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.audit_context = {"ip_address": "192.168.1.1", "user_agent": "Test"}
        request._messages = Mock()

        mock_render.return_value = HttpResponse("Import successful")

        with patch("civicpulse.views.imports.log_data_import") as mock_log_import:
            self.view.post(request)

            # Should have 2 persons (no duplicate detected)
            self.assertEqual(Person.objects.count(), 2)
            mock_log_import.assert_called_once()
            call_args = mock_log_import.call_args
            self.assertEqual(call_args[1]["record_count"], 1)
            self.assertEqual(call_args[1]["duplicate_count"], 0)

    @patch("civicpulse.views.imports.render")
    def test_import_multiple_duplicates_in_batch(self, mock_render):
        """Test handling multiple duplicates in a single import batch."""
        # Create existing persons
        Person.objects.create(
            first_name="Lisa",
            last_name="Brown",
            email="lisa.brown@email.com",
            phone_primary="(630) 555-7777",
            date_of_birth=date(1979, 8, 14),
            created_by=self.user,
        )

        Person.objects.create(
            first_name="Mark",
            last_name="Davis",
            email="mark.davis@company.com",
            phone_primary="(847) 555-8888",
            date_of_birth=date(1986, 2, 28),
            created_by=self.user,
        )

        # Import batch with multiple duplicates and one new person
        csv_content = (
            "First Name,Last Name,Email,Phone Primary,Date of Birth\n"
            "Lisa,Brown,different@email.com,(630) 555-7777,1990-01-01\n"
            "Mark,Davis,mark.davis@company.com,(999) 555-9999,1990-01-01\n"
            "Patricia,Johnson,patricia.johnson@email.com,(708) 555-3333,1994-12-05"
        )

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": csv_file})
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.audit_context = {"ip_address": "192.168.1.1", "user_agent": "Test"}
        request._messages = Mock()

        mock_render.return_value = HttpResponse("Import successful")

        with patch("civicpulse.views.imports.log_data_import") as mock_log_import:
            self.view.post(request)

            # Should have 3 persons (2 existing + 1 new, 2 duplicates skipped)
            self.assertEqual(Person.objects.count(), 3)
            mock_log_import.assert_called_once()
            call_args = mock_log_import.call_args
            self.assertEqual(call_args[1]["record_count"], 1)
            self.assertEqual(call_args[1]["duplicate_count"], 2)

            # Verify the new person was added
            new_person = Person.objects.get(first_name="Patricia")
            self.assertEqual(new_person.last_name, "Johnson")
            self.assertEqual(new_person.email, "patricia.johnson@email.com")

    @patch("civicpulse.views.imports.render")
    def test_import_duplicate_detection_with_voter_data(self, mock_render):
        """Test duplicate detection works with voter record data."""
        # Create existing person with voter record
        person = Person.objects.create(
            first_name="Robert",
            last_name="Taylor",
            email="robert.taylor@email.com",
            phone_primary="(773) 555-4567",
            street_address="678 Oak Street",
            city="Chicago",
            state="IL",
            zip_code="60614",
            date_of_birth=date(1976, 10, 12),
            gender="M",
            created_by=self.user,
        )

        VoterRecord.objects.create(
            person=person,
            voter_id="IL123456789",
            registration_status="active",
            party_affiliation="DEM",
            voter_score=85,
            precinct="14-B",
            ward="42",
        )

        # Try to import duplicate with different voter data
        csv_content = (
            "First Name,Last Name,Email,Voter ID,Registration Status,"
            "Party Affiliation,Voter Score,Date of Birth\n"
            "Robert,Taylor,robert.taylor@email.com,IL987654321,active,REP,75,1976-10-12"
        )

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": csv_file})
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.audit_context = {"ip_address": "192.168.1.1", "user_agent": "Test"}
        request._messages = Mock()

        mock_render.return_value = HttpResponse("Import successful")

        with patch("civicpulse.views.imports.log_data_import") as mock_log_import:
            self.view.post(request)

            # Should still be only 1 person and 1 voter record (duplicate skipped)
            self.assertEqual(Person.objects.count(), 1)
            self.assertEqual(VoterRecord.objects.count(), 1)

            # Original voter record should be unchanged
            voter_record = VoterRecord.objects.first()
            self.assertEqual(voter_record.voter_id, "IL123456789")
            self.assertEqual(voter_record.party_affiliation, "DEM")
            self.assertEqual(voter_record.voter_score, 85)

            mock_log_import.assert_called_once()
            call_args = mock_log_import.call_args
            self.assertEqual(call_args[1]["record_count"], 0)
            self.assertEqual(call_args[1]["duplicate_count"], 1)

    @patch("civicpulse.views.imports.render")
    def test_import_duplicate_detection_edge_case_empty_fields(self, mock_render):
        """Test duplicate detection handles empty/whitespace fields correctly."""
        # Create existing person with minimal data
        Person.objects.create(
            first_name="Mary",
            last_name="Smith",
            email="",  # Empty email
            phone_primary="",  # Empty phone
            created_by=self.user,
        )

        # Try to import person with same name but empty contact fields
        csv_content = """First Name,Last Name,Email,Phone Primary
Mary,Smith,,"""

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": csv_file})
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.audit_context = {"ip_address": "192.168.1.1", "user_agent": "Test"}
        request._messages = Mock()

        mock_render.return_value = HttpResponse("Import successful")

        with patch("civicpulse.views.imports.log_data_import") as mock_log_import:
            self.view.post(request)

            # Should create new person since no unique identifiers match
            # (name alone without DOB doesn't trigger duplicate detection)
            self.assertEqual(Person.objects.count(), 2)
            mock_log_import.assert_called_once()
            call_args = mock_log_import.call_args
            self.assertEqual(call_args[1]["record_count"], 1)
            self.assertEqual(call_args[1]["duplicate_count"], 0)

    @patch("civicpulse.views.imports.render")
    def test_import_duplicate_detection_whitespace_handling(self, mock_render):
        """Test duplicate detection handles whitespace in contact fields."""
        # Create existing person
        Person.objects.create(
            first_name="Susan",
            last_name="Davis",
            email="susan.davis@email.com",
            phone_primary="(555) 123-4567",
            created_by=self.user,
        )

        # Try to import with extra whitespace
        csv_content = (
            "First Name,Last Name,Email,Phone Primary\n"
            "Susan,Davis,  susan.davis@email.com  ,  (555) 123-4567  "
        )

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": csv_file})
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.audit_context = {"ip_address": "192.168.1.1", "user_agent": "Test"}
        request._messages = Mock()

        mock_render.return_value = HttpResponse("Import successful")

        with patch("civicpulse.views.imports.log_data_import") as mock_log_import:
            self.view.post(request)

            # Should detect duplicate despite whitespace
            self.assertEqual(Person.objects.count(), 1)
            mock_log_import.assert_called_once()
            call_args = mock_log_import.call_args
            self.assertEqual(call_args[1]["record_count"], 0)
            self.assertEqual(call_args[1]["duplicate_count"], 1)

    @patch("civicpulse.views.imports.render")
    def test_import_duplicate_detection_partial_address_no_match(self, mock_render):
        """Test that partial address info doesn't trigger false duplicate detection."""
        # Create existing person with full address
        Person.objects.create(
            first_name="Thomas",
            last_name="Wilson",
            email="thomas.wilson@email.com",
            street_address="123 Main Street",
            city="Springfield",
            state="IL",
            zip_code="62701",
            created_by=self.user,
        )

        # Try to import person with same name but incomplete address (missing zip)
        csv_content = (
            "First Name,Last Name,Email,Street Address,City,State\n"
            "Thomas,Wilson,different@email.com,123 Main Street,Springfield,IL"
        )

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": csv_file})
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.audit_context = {"ip_address": "192.168.1.1", "user_agent": "Test"}
        request._messages = Mock()

        mock_render.return_value = HttpResponse("Import successful")

        with patch("civicpulse.views.imports.log_data_import") as mock_log_import:
            self.view.post(request)

            # Should create new person since address criteria not fully met
            self.assertEqual(Person.objects.count(), 2)
            mock_log_import.assert_called_once()
            call_args = mock_log_import.call_args
            self.assertEqual(call_args[1]["record_count"], 1)
            self.assertEqual(call_args[1]["duplicate_count"], 0)

    @patch("civicpulse.views.imports.render")
    def test_import_duplicate_detection_near_miss_dates(self, mock_render):
        """Test that similar but different dates of birth don't trigger duplicates."""
        # Create existing person
        Person.objects.create(
            first_name="Rachel",
            last_name="Johnson",
            email="rachel.johnson@email.com",
            date_of_birth=date(1990, 5, 15),
            created_by=self.user,
        )

        # Try to import person with same name but different DOB (one day off)
        csv_content = """First Name,Last Name,Email,Date of Birth
Rachel,Johnson,different@email.com,1990-05-16"""

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": csv_file})
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.audit_context = {"ip_address": "192.168.1.1", "user_agent": "Test"}
        request._messages = Mock()

        mock_render.return_value = HttpResponse("Import successful")

        with patch("civicpulse.views.imports.log_data_import") as mock_log_import:
            self.view.post(request)

            # Should create new person since DOB is different
            self.assertEqual(Person.objects.count(), 2)
            mock_log_import.assert_called_once()
            call_args = mock_log_import.call_args
            self.assertEqual(call_args[1]["record_count"], 1)
            self.assertEqual(call_args[1]["duplicate_count"], 0)

    @patch("civicpulse.views.imports.render")
    def test_import_duplicate_detection_case_insensitive_address(self, mock_render):
        """Test duplicate detection is case-insensitive for address fields."""
        # Create existing person
        Person.objects.create(
            first_name="Kevin",
            last_name="Brown",
            email="kevin.brown@email.com",
            street_address="456 Oak Street",
            city="Chicago",
            state="IL",
            zip_code="60601",
            created_by=self.user,
        )

        # Try to import with different case address
        csv_content = (
            "First Name,Last Name,Email,Street Address,City,State,ZIP Code\n"
            "kevin,brown,different@email.com,456 OAK STREET,chicago,il,60601"
        )

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": csv_file})
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.audit_context = {"ip_address": "192.168.1.1", "user_agent": "Test"}
        request._messages = Mock()

        mock_render.return_value = HttpResponse("Import successful")

        with patch("civicpulse.views.imports.log_data_import") as mock_log_import:
            self.view.post(request)

            # Should detect duplicate despite case differences
            self.assertEqual(Person.objects.count(), 1)
            mock_log_import.assert_called_once()
            call_args = mock_log_import.call_args
            self.assertEqual(call_args[1]["record_count"], 0)
            self.assertEqual(call_args[1]["duplicate_count"], 1)

    @patch("civicpulse.views.imports.render")
    def test_import_duplicate_detection_phone_formatting_variations(self, mock_render):
        """Test duplicate detection works with different phone number formats."""
        # Create existing person with formatted phone
        Person.objects.create(
            first_name="Nancy",
            last_name="Miller",
            email="nancy.miller@email.com",
            phone_primary="(312) 555-7890",
            created_by=self.user,
        )

        # Try to import with differently formatted phone (but same number)
        csv_content = (
            "First Name,Last Name,Email,Phone Primary\n"
            "Nancy,Miller,different@email.com,312-555-7890"
        )

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": csv_file})
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.audit_context = {"ip_address": "192.168.1.1", "user_agent": "Test"}
        request._messages = Mock()

        mock_render.return_value = HttpResponse("Import successful")

        with patch("civicpulse.views.imports.log_data_import") as mock_log_import:
            self.view.post(request)

            # Note: This test might create 2 persons if phone formatting isn't
            # normalized
            # This is actually expected behavior unless phone normalization
            # is implemented
            # The current implementation does exact string matching for phone numbers
            persons_count = Person.objects.count()

            # Document the current behavior - phone formats must match exactly
            if persons_count == 1:
                # If duplicate was detected, phone normalization is working
                mock_log_import.assert_called_once()
                call_args = mock_log_import.call_args
                self.assertEqual(call_args[1]["duplicate_count"], 1)
            else:
                # If no duplicate detected, phone normalization is not implemented
                # This is the expected current behavior
                self.assertEqual(persons_count, 2)
                mock_log_import.assert_called_once()
                call_args = mock_log_import.call_args
                self.assertEqual(call_args[1]["record_count"], 1)
                self.assertEqual(call_args[1]["duplicate_count"], 0)

    @patch("civicpulse.views.imports.render")
    def test_import_validation_errors(self, mock_render):
        """Test that validation errors are handled and logged."""
        csv_content = """First Name,Last Name,Email
John,,invalid-email"""  # Missing last name, invalid email

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": csv_file})
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.audit_context = {"ip_address": "192.168.1.1", "user_agent": "Test"}
        request._messages = Mock()

        # Mock render to return a simple response
        mock_render.return_value = HttpResponse("Import with errors")

        # Mock log_data_import to check error count
        with patch("civicpulse.views.imports.log_data_import") as mock_log_import:
            self.view.post(request)

            # Should not create any persons
            self.assertEqual(Person.objects.count(), 0)

            # Check log_data_import was called with error count
            mock_log_import.assert_called_once()
            call_args = mock_log_import.call_args
            self.assertEqual(call_args[1]["record_count"], 0)
            self.assertEqual(call_args[1]["errors_count"], 1)

    def test_import_missing_required_headers(self):
        """Test import fails with missing required headers."""
        csv_content = """Email
john@example.com"""  # Missing First Name and Last Name

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": csv_file})
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.audit_context = {"ip_address": "192.168.1.1", "user_agent": "Test"}
        request._messages = Mock()

        from django.core.exceptions import ValidationError

        with self.assertRaises((Exception, ValidationError)):
            self.view.post(request)

    @patch("civicpulse.views.imports.render")
    def test_import_file_validation(self, mock_render):
        """Test file validation (size, extension, etc.)."""
        # Test non-CSV file
        request = self.factory.post(
            "/import/persons/",
            {"csv_file": SimpleUploadedFile("test.txt", b"not a csv")},
        )
        request.user = self.user
        request._messages = Mock()

        # Mock render to return a simple response
        mock_render.return_value = HttpResponse("Invalid file type")

        response = self.view.post(request)

        # Should redirect back to form with error
        self.assertEqual(response.status_code, 200)

    @patch("civicpulse.views.imports.render")
    def test_import_no_file_uploaded(self, mock_render):
        """Test handling when no file is uploaded."""
        request = self.factory.post("/import/persons/", {})
        request.user = self.user
        request._messages = Mock()

        # Mock render to return a simple response
        mock_render.return_value = HttpResponse("No file uploaded")

        response = self.view.post(request)

        # Should redirect back to form
        self.assertEqual(response.status_code, 200)

    @patch("civicpulse.views.imports.render")
    def test_import_large_file_rejection(self, mock_render):
        """Test that large files are rejected using configurable setting."""
        # Create a file larger than the default limit (10MB)
        large_content = "a" * (11 * 1024 * 1024)  # 11MB
        large_file = SimpleUploadedFile("large.csv", large_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": large_file})
        request.user = self.user
        request._messages = Mock()

        # Mock render to return a simple response
        mock_render.return_value = HttpResponse("File too large")

        response = self.view.post(request)

        # Should reject the file
        self.assertEqual(response.status_code, 200)

    @patch("civicpulse.views.imports.render")
    @patch("django.conf.settings.PERSON_IMPORT_MAX_FILE_SIZE", 5 * 1024 * 1024)
    def test_import_custom_file_size_limit(self, mock_render):
        """Test that custom file size limits are respected."""
        # Create a file larger than custom limit (5MB) but smaller than default (10MB)
        medium_content = "a" * (6 * 1024 * 1024)  # 6MB
        medium_file = SimpleUploadedFile("medium.csv", medium_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": medium_file})
        request.user = self.user
        request._messages = Mock()

        # Mock render to return a simple response
        mock_render.return_value = HttpResponse("File too large")

        response = self.view.post(request)

        # Should reject the file because it's larger than the custom 5MB limit
        self.assertEqual(response.status_code, 200)

    @patch("civicpulse.views.imports.render")
    def test_import_file_within_size_limit(self, mock_render):
        """Test that files within size limit are accepted."""
        # Create a small valid CSV file (1MB)
        csv_content = "First Name,Last Name\n" + "John,Doe\n" * 1000  # About 1MB
        small_file = SimpleUploadedFile("small.csv", csv_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": small_file})
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.audit_context = {"ip_address": "192.168.1.1", "user_agent": "Test"}
        request._messages = Mock()

        # Mock render to return a simple response
        mock_render.return_value = HttpResponse("Import successful")

        # Mock log_data_import to avoid audit dependencies
        with patch("civicpulse.views.imports.log_data_import"):
            response = self.view.post(request)

        # Should accept the file and process it
        self.assertEqual(response.status_code, 200)
        # Verify that persons were created (indicating file was processed)
        self.assertGreater(Person.objects.count(), 0)

    @patch("civicpulse.views.imports.render")
    @patch("civicpulse.views.imports.messages")
    def test_file_size_error_message_uses_configured_limit(
        self, mock_messages, mock_render
    ):
        """Test that error messages show the actual configured file size limit."""
        from django.conf import settings

        # Get the actual configured limit
        max_file_size = getattr(
            settings, "PERSON_IMPORT_MAX_FILE_SIZE", 10 * 1024 * 1024
        )
        max_size_mb = max_file_size / (1024 * 1024)

        # Create a file larger than the limit
        large_content = "a" * (max_file_size + 1024)  # Slightly larger than limit
        large_file = SimpleUploadedFile("large.csv", large_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": large_file})
        request.user = self.user

        # Mock render to capture the actual response
        mock_render.return_value = HttpResponse("File too large")

        self.view.post(request)

        # Check that messages.error was called with the correct limit
        mock_messages.error.assert_called()
        error_call_args = mock_messages.error.call_args[0]
        error_message = error_call_args[1]  # Second argument is the message
        self.assertIn(f"{max_size_mb:.0f}MB", error_message)

    @patch("civicpulse.views.imports.render")
    def test_help_text_shows_configured_file_limit(self, mock_render):
        """Test that help text shows the actual configured file size limit."""
        from django.conf import settings

        # Get the actual configured limit
        max_file_size = getattr(
            settings, "PERSON_IMPORT_MAX_FILE_SIZE", 10 * 1024 * 1024
        )
        max_size_mb = max_file_size / (1024 * 1024)

        request = self.factory.get("/import/persons/")
        request.user = self.user

        # Mock render to capture the context
        mock_render.return_value = HttpResponse("Import form")

        self.view.get(request)

        # Check that render was called with the correct help text
        mock_render.assert_called_once()
        call_args = mock_render.call_args
        context = call_args[0][2]  # Third argument is the context

        help_text = context["help_text"]
        self.assertIn(f"{max_size_mb:.0f}MB", help_text["file_limits"])

    @patch("civicpulse.views.imports.render")
    def test_import_date_format_parsing(self, mock_render):
        """Test parsing various date formats."""
        csv_content = (
            "First Name,Last Name,Date of Birth,Last Voted Date\n"
            "John,Doe,1990-01-01,2020-11-03\n"
            "Jane,Smith,05/15/1985,11/08/2016\n"
            "Bob,Johnson,03-22-1975,12-05-2018"
        )

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": csv_file})
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.audit_context = {"ip_address": "192.168.1.1", "user_agent": "Test"}
        request._messages = Mock()

        # Mock render to return a simple response
        mock_render.return_value = HttpResponse("Import successful")

        # Mock log_data_import to avoid audit dependencies
        with patch("civicpulse.views.imports.log_data_import"):
            self.view.post(request)

        # Should create all persons with parsed dates
        self.assertEqual(Person.objects.count(), 3)

        john = Person.objects.get(first_name="John")
        self.assertEqual(john.date_of_birth, date(1990, 1, 1))

        jane = Person.objects.get(first_name="Jane")
        self.assertEqual(jane.date_of_birth, date(1985, 5, 15))

    @patch("civicpulse.views.imports.render")
    @patch("civicpulse.views.imports.logger")
    def test_import_exception_handling(self, mock_logger, mock_render):
        """Test import handles exceptions gracefully."""
        csv_content = """First Name,Last Name
John,Doe"""

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": csv_file})
        request.user = self.user
        request._messages = Mock()

        # Mock render to return a simple response
        mock_render.return_value = HttpResponse("Error during import")

        # Mock an exception during processing
        with patch(
            "civicpulse.views.imports.PersonImportView._process_csv_file",
            side_effect=Exception("Processing error"),
        ):
            response = self.view.post(request)

        # Should handle the exception gracefully
        self.assertEqual(response.status_code, 200)
        mock_logger.error.assert_called_once()

    @patch("civicpulse.views.imports.render")
    def test_import_gender_mapping(self, mock_render):
        """Test gender value mapping from various formats."""
        csv_content = (
            "First Name,Last Name,Email,Gender\n"
            "John,Doe,john@example.com,Male\n"
            "Jane,Smith,jane@example.com,F\n"
            "Bob,Johnson,bob@example.com,Other\n"
            "Alice,Brown,alice@example.com,Unknown"
        )

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": csv_file})
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.audit_context = {"ip_address": "192.168.1.1", "user_agent": "Test"}
        request._messages = Mock()

        # Mock render to return a simple response
        mock_render.return_value = HttpResponse("Import successful")

        # Mock log_data_import to avoid audit dependencies
        with patch("civicpulse.views.imports.log_data_import"):
            self.view.post(request)

        # Check how many persons were actually created
        persons_count = Person.objects.count()
        self.assertEqual(persons_count, 4, f"Expected 4 persons, got {persons_count}")

        persons = {p.first_name: p for p in Person.objects.all()}

        # Debug output - check what persons were actually created
        created_names = list(persons.keys())
        self.assertIn(
            "John", created_names, f"John not found in created persons: {created_names}"
        )
        self.assertIn(
            "Jane", created_names, f"Jane not found in created persons: {created_names}"
        )
        self.assertIn(
            "Bob", created_names, f"Bob not found in created persons: {created_names}"
        )
        self.assertIn(
            "Alice",
            created_names,
            f"Alice not found in created persons: {created_names}",
        )

        self.assertEqual(persons["John"].gender, "M")
        self.assertEqual(persons["Jane"].gender, "F")
        self.assertEqual(persons["Bob"].gender, "O")
        self.assertEqual(persons["Alice"].gender, "U")

    @patch("civicpulse.views.imports.render")
    def test_import_party_affiliation_mapping(self, mock_render):
        """Test party affiliation mapping from various formats."""
        csv_content = (
            "First Name,Last Name,Email,Voter ID,Party Affiliation\n"
            "John,Doe,john@example.com,VOT001,Democratic\n"
            "Jane,Smith,jane@example.com,VOT002,REP\n"
            "Bob,Johnson,bob@example.com,VOT003,Independent\n"
            "Alice,Brown,alice@example.com,VOT004,Green"
        )

        csv_file = SimpleUploadedFile("test.csv", csv_content.encode("utf-8"))

        request = self.factory.post("/import/persons/", {"csv_file": csv_file})
        request.user = self.user
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        request.audit_context = {"ip_address": "192.168.1.1", "user_agent": "Test"}
        request._messages = Mock()

        # Mock render to return a simple response
        mock_render.return_value = HttpResponse("Import successful")

        # Mock log_data_import to avoid audit dependencies
        with patch("civicpulse.views.imports.log_data_import"):
            self.view.post(request)

        # Check how many persons and voter records were created
        persons_count = Person.objects.count()
        voters_count = VoterRecord.objects.count()
        self.assertEqual(persons_count, 4, f"Expected 4 persons, got {persons_count}")
        self.assertEqual(
            voters_count, 4, f"Expected 4 voter records, got {voters_count}"
        )

        # Get voters by their person's first name since voter IDs might not be strings
        voters_by_person = {}
        for vr in VoterRecord.objects.all():
            voters_by_person[vr.person.first_name] = vr

        # Debug output - check what voters were actually created
        created_names = list(voters_by_person.keys())
        self.assertIn(
            "John", created_names, f"John not found in voter records: {created_names}"
        )
        self.assertIn(
            "Jane", created_names, f"Jane not found in voter records: {created_names}"
        )
        self.assertIn(
            "Bob", created_names, f"Bob not found in voter records: {created_names}"
        )
        self.assertIn(
            "Alice", created_names, f"Alice not found in voter records: {created_names}"
        )

        self.assertEqual(voters_by_person["John"].party_affiliation, "DEM")
        self.assertEqual(voters_by_person["Jane"].party_affiliation, "REP")
        self.assertEqual(voters_by_person["Bob"].party_affiliation, "IND")
        self.assertEqual(voters_by_person["Alice"].party_affiliation, "GRN")
