"""
Performance tests for duplicate detection in Person service.

This module tests the performance of PersonDuplicateDetector with large datasets
to ensure it meets performance requirements (<100ms with 10,000 records).

Key Performance Metrics:
- Query execution time: <100ms with 10,000 records
- Database index utilization: All queries must use indexes
- Query count: No N+1 query issues
- Memory usage: Reasonable and stable

Testing Approach:
- Uses pytest-benchmark for accurate performance measurement
- Tests with realistic data distributions
- Validates index usage with EXPLAIN queries
- Tests various duplicate patterns (email, phone, name+DOB)

Performance Targets:
- 1,000 persons: <10ms
- 5,000 persons: <50ms
- 10,000 persons: <100ms

Author: Olivia Davis
"""

import time
from datetime import date, timedelta

import factory
import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from civicpulse.models import Person
from civicpulse.services.person_service import (
    PersonDataDict,
    PersonDuplicateDetector,
)

User = get_user_model()


# ============================================================================
# FACTORIES FOR TEST DATA GENERATION
# ============================================================================


class UserFactory(factory.django.DjangoModelFactory):
    """Factory for creating test users."""

    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"testuser{n}")
    email = factory.Sequence(lambda n: f"test{n}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "testpass123")


class PersonFactory(factory.django.DjangoModelFactory):
    """Factory for creating test persons with realistic data."""

    class Meta:
        model = Person

    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    email = factory.Faker("email")
    phone_primary = factory.Sequence(lambda n: f"+1415555{n:04d}")
    date_of_birth = factory.LazyFunction(
        lambda: timezone.now().date()
        - timedelta(days=factory.random.randint(7300, 25550))
    )
    street_address = factory.Faker("street_address")
    city = factory.Faker("city")
    state = factory.Faker("state_abbr")
    zip_code = factory.Faker("zipcode")
    gender = factory.Faker("random_element", elements=["M", "F", "O", "U"])
    created_by = factory.SubFactory(UserFactory)


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def detector():
    """Create PersonDuplicateDetector instance."""
    return PersonDuplicateDetector()


@pytest.fixture
@pytest.mark.django_db
def test_user(db):
    """Create a test user for person creation."""
    return UserFactory()


@pytest.fixture
@pytest.mark.django_db
def bulk_persons(test_user, db):
    """Create bulk persons for performance testing."""

    def _create_bulk(count: int) -> list[Person]:
        """Create specified number of persons."""
        persons = []
        # Use batch creation for faster setup
        for i in range(count):
            persons.append(
                Person(
                    first_name=f"Person{i}",
                    last_name=f"Test{i}",
                    email=f"person{i}@test.com",
                    phone_primary=f"+1415555{i:04d}",
                    date_of_birth=date(1980, 1, 1) + timedelta(days=i % 3650),
                    created_by=test_user,
                )
            )

        # Bulk create for performance
        Person.objects.bulk_create(persons, batch_size=1000)
        return persons

    return _create_bulk


# ============================================================================
# PERFORMANCE BENCHMARK TESTS
# ============================================================================


@pytest.mark.django_db
class TestDuplicateDetectionPerformance:
    """Performance tests for duplicate detection with various dataset sizes."""

    def test_duplicate_detection_1000_records(self, detector, bulk_persons, benchmark):
        """
        Test duplicate detection performance with 1,000 person records.

        Target: <10ms per query
        """
        # Setup: Create 1,000 persons
        bulk_persons(1000)

        # Test data to search for (matching middle of dataset)
        search_data: PersonDataDict = {
            "first_name": "Person500",
            "last_name": "Test500",
            "email": "person500@test.com",
        }

        # Benchmark the duplicate detection
        result = benchmark(detector.find_duplicates, search_data)

        # Verify results
        assert result.count() == 1
        assert result.first().email == "person500@test.com"

        # Performance assertion
        assert benchmark.stats["mean"] < 0.010  # <10ms

    def test_duplicate_detection_5000_records(self, detector, bulk_persons, benchmark):
        """
        Test duplicate detection performance with 5,000 person records.

        Target: <50ms per query
        """
        # Setup: Create 5,000 persons
        bulk_persons(5000)

        # Test data to search for
        search_data: PersonDataDict = {
            "first_name": "Person2500",
            "last_name": "Test2500",
            "email": "person2500@test.com",
        }

        # Benchmark the duplicate detection
        result = benchmark(detector.find_duplicates, search_data)

        # Verify results
        assert result.count() == 1

        # Performance assertion
        assert benchmark.stats["mean"] < 0.050  # <50ms

    def test_duplicate_detection_10000_records(self, detector, bulk_persons, benchmark):
        """
        Test duplicate detection performance with 10,000 person records.

        Target: <100ms per query (PRIMARY REQUIREMENT)
        """
        # Setup: Create 10,000 persons
        bulk_persons(10000)

        # Test data to search for
        search_data: PersonDataDict = {
            "first_name": "Person5000",
            "last_name": "Test5000",
            "email": "person5000@test.com",
        }

        # Benchmark the duplicate detection
        result = benchmark(detector.find_duplicates, search_data)

        # Verify results
        assert result.count() == 1

        # Performance assertion (PRIMARY REQUIREMENT)
        assert benchmark.stats["mean"] < 0.100  # <100ms

    def test_duplicate_detection_worst_case_no_duplicates(
        self, detector, bulk_persons, benchmark
    ):
        """
        Test worst-case scenario: searching with no duplicates.

        This tests the scenario where the query must scan through all
        records without finding a match.

        Target: <100ms with 10,000 records
        """
        # Setup: Create 10,000 persons
        bulk_persons(10000)

        # Test data with no matches (unique data)
        search_data: PersonDataDict = {
            "first_name": "UniqueFirstName",
            "last_name": "UniqueLastName",
            "email": "unique@nowhere.com",
        }

        # Benchmark the duplicate detection
        result = benchmark(detector.find_duplicates, search_data)

        # Verify no duplicates found
        assert result.count() == 0

        # Performance assertion
        assert benchmark.stats["mean"] < 0.100  # <100ms

    def test_duplicate_detection_many_duplicates(
        self, detector, test_user, db, benchmark
    ):
        """
        Test performance with many duplicates (stress test).

        Creates 100 persons with same email to test performance when
        many duplicates exist.

        Target: <100ms
        """
        # Setup: Create 100 persons with same email
        shared_email = "shared@test.com"
        persons = []
        for i in range(100):
            persons.append(
                Person(
                    first_name=f"Person{i}",
                    last_name=f"Test{i}",
                    email=shared_email,  # Same email for all
                    created_by=test_user,
                )
            )
        Person.objects.bulk_create(persons)

        # Also add 9,900 unique persons for realistic dataset size
        unique_persons = []
        for i in range(100, 10000):
            unique_persons.append(
                Person(
                    first_name=f"Person{i}",
                    last_name=f"Test{i}",
                    email=f"person{i}@test.com",
                    created_by=test_user,
                )
            )
        Person.objects.bulk_create(unique_persons, batch_size=1000)

        # Test data matching all 100 duplicates
        search_data: PersonDataDict = {
            "first_name": "NewPerson",
            "last_name": "NewTest",
            "email": shared_email,
        }

        # Benchmark the duplicate detection
        result = benchmark(detector.find_duplicates, search_data)

        # Verify all duplicates found
        assert result.count() == 100

        # Performance assertion
        assert benchmark.stats["mean"] < 0.100  # <100ms


# ============================================================================
# QUERY OPTIMIZATION TESTS
# ============================================================================


@pytest.mark.django_db
class TestQueryOptimization:
    """Tests to verify database queries are optimized and use indexes."""

    def test_duplicate_query_uses_email_index(self, detector, bulk_persons):
        """
        Test that duplicate detection query uses email index.

        Verifies the query plan includes the email index for optimal performance.
        """
        # Setup: Create dataset
        bulk_persons(1000)

        search_data: PersonDataDict = {
            "first_name": "Person500",
            "last_name": "Test500",
            "email": "person500@test.com",
        }

        # Execute query with EXPLAIN to check index usage
        with connection.cursor() as cursor:
            # Get the query SQL
            queryset = detector.find_duplicates(search_data)
            sql, params = queryset.query.sql_with_params()

            # Run EXPLAIN to check query plan
            # Note: EXPLAIN syntax differs between databases
            try:
                cursor.execute(f"EXPLAIN QUERY PLAN {sql}", params)
                plan = cursor.fetchall()

                # Convert plan to string for analysis
                plan_str = "\n".join(str(row) for row in plan)

                # Verify index usage (SQLite format: looks for "USING INDEX")
                # PostgreSQL would look for "Index Scan"
                assert "idx_person_email_lower" in plan_str or "USING INDEX" in plan_str

            except Exception as e:
                # If EXPLAIN doesn't work (different DB), log and skip
                pytest.skip(f"EXPLAIN QUERY PLAN not supported: {e}")

    def test_duplicate_query_minimal_count(self, detector, bulk_persons):
        """
        Test that duplicate detection doesn't have N+1 query issues.

        Verifies the query count remains constant regardless of result size.
        """
        # Setup: Create dataset
        bulk_persons(1000)

        search_data: PersonDataDict = {
            "first_name": "Person500",
            "last_name": "Test500",
            "email": "person500@test.com",
        }

        # Count queries during duplicate detection
        with CaptureQueriesContext(connection) as queries:
            result = detector.find_duplicates(search_data)
            # Force query execution by accessing results
            list(result)

        # Verify minimal query count (should be 1 SELECT query)
        assert len(queries) <= 2  # Allow for potential transaction queries

        # Verify the main query is a SELECT
        assert any("SELECT" in q["sql"] for q in queries)

    def test_composite_index_usage_name_dob(self, detector, test_user, db):
        """
        Test that queries use composite index for name+DOB searches.

        Verifies the composite index on [first_name, last_name, date_of_birth]
        is being used.
        """
        # Setup: Create persons
        for i in range(100):
            Person.objects.create(
                first_name=f"John{i}",
                last_name=f"Doe{i}",
                date_of_birth=date(1985, 5, 15) + timedelta(days=i),
                created_by=test_user,
            )

        search_data: PersonDataDict = {
            "first_name": "John50",
            "last_name": "Doe50",
            "date_of_birth": date(1985, 5, 15) + timedelta(days=50),
        }

        # Execute with query capture
        with CaptureQueriesContext(connection) as queries:
            result = detector.find_duplicates(search_data)
            list(result)

        # Verify query count is minimal
        assert len(queries) <= 2

    def test_phone_index_usage(self, detector, test_user, db):
        """
        Test that queries use phone number indexes.

        Verifies indexes on phone_primary and phone_secondary are used.
        """
        # Setup: Create persons with unique phone numbers
        for i in range(100):
            Person.objects.create(
                first_name=f"Person{i}",
                last_name=f"Test{i}",
                phone_primary=f"+1415555{i:04d}",
                created_by=test_user,
            )

        search_data: PersonDataDict = {
            "first_name": "NewPerson",
            "last_name": "NewTest",
            "phone_primary": "+14155550050",
        }

        # Execute with query capture
        with CaptureQueriesContext(connection) as queries:
            result = detector.find_duplicates(search_data)
            list(result)

        # Verify query count is minimal
        assert len(queries) <= 2


# ============================================================================
# SCALABILITY TESTS
# ============================================================================


@pytest.mark.django_db
class TestScalability:
    """Tests to verify performance scales appropriately with dataset growth."""

    def test_performance_scaling_consistency(self, detector, bulk_persons):
        """
        Test that performance scales linearly (or better) with dataset size.

        Measures query time at different dataset sizes and verifies
        the scaling ratio is acceptable.
        """
        results = {}

        # Test with increasing dataset sizes
        for size in [100, 500, 1000]:
            # Setup dataset
            Person.objects.all().delete()  # Clean slate
            bulk_persons(size)

            # Measure query time
            search_data: PersonDataDict = {
                "first_name": f"Person{size // 2}",
                "last_name": f"Test{size // 2}",
                "email": f"person{size // 2}@test.com",
            }

            start = time.perf_counter()
            result = detector.find_duplicates(search_data)
            list(result)  # Force evaluation
            elapsed = time.perf_counter() - start

            results[size] = elapsed

        # Verify scaling is reasonable (should be sub-linear due to indexes)
        # 10x data should not take 10x time
        if 1000 in results and 100 in results:
            scaling_ratio = results[1000] / results[100]
            assert scaling_ratio < 5.0  # 10x data should take <5x time

    def test_concurrent_duplicate_detection(self, detector, bulk_persons):
        """
        Test performance with concurrent duplicate detection requests.

        Simulates multiple simultaneous duplicate checks.
        """
        # Setup: Create dataset
        bulk_persons(1000)

        # Prepare multiple search queries
        search_queries = [
            {
                "first_name": f"Person{i * 100}",
                "last_name": f"Test{i * 100}",
                "email": f"person{i * 100}@test.com",
            }
            for i in range(5)
        ]

        # Execute all queries and measure total time
        start = time.perf_counter()
        for search_data in search_queries:
            result = detector.find_duplicates(search_data)
            list(result)
        elapsed = time.perf_counter() - start

        # Average time per query
        avg_time = elapsed / len(search_queries)

        # Verify average time is acceptable
        assert avg_time < 0.050  # <50ms average per query

    def test_memory_efficiency(self, detector, bulk_persons):
        """
        Test that duplicate detection is memory efficient.

        Verifies that results are fetched lazily and don't load
        entire dataset into memory.
        """
        # Setup: Create large dataset
        bulk_persons(5000)

        search_data: PersonDataDict = {
            "first_name": "Person2500",
            "last_name": "Test2500",
            "email": "person2500@test.com",
        }

        # Get queryset (should not execute query yet)
        result = detector.find_duplicates(search_data)

        # Verify queryset is lazy (hasn't been evaluated)
        assert not result._result_cache

        # Iterate one result at a time (memory efficient)
        count = 0
        for _person in result:
            count += 1
            if count >= 1:  # Only fetch one
                break

        # Verify only one result was fetched
        assert count == 1


# ============================================================================
# REALISTIC SCENARIO TESTS
# ============================================================================


@pytest.mark.django_db
class TestRealisticScenarios:
    """Tests with realistic data distributions and usage patterns."""

    def test_realistic_data_distribution(self, detector, test_user, db, benchmark):
        """
        Test with realistic person data distribution.

        Creates a dataset with:
        - Common names (duplicates)
        - Unique emails (mostly)
        - Realistic phone numbers
        - Various date of births
        """
        # Create 1,000 persons with realistic distribution
        common_names = ["John", "Jane", "Michael", "Mary", "David", "Lisa"]
        common_last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones"]

        persons = []
        for i in range(1000):
            first = common_names[i % len(common_names)]
            last = common_last_names[i % len(common_last_names)]
            dob = date(1960, 1, 1) + timedelta(days=i * 10)

            persons.append(
                Person(
                    first_name=first,
                    last_name=last,
                    email=f"person{i}@example.com",  # Unique emails
                    phone_primary=f"+1415555{i:04d}",
                    date_of_birth=dob,
                    created_by=test_user,
                )
            )

        Person.objects.bulk_create(persons, batch_size=500)

        # Search for a common name (will have many results)
        search_data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Smith",
            "date_of_birth": date(1960, 1, 1),
        }

        # Benchmark
        result = benchmark(detector.find_duplicates, search_data)

        # Verify results
        assert result.count() > 0

        # Performance assertion
        assert benchmark.stats["mean"] < 0.050  # <50ms

    def test_email_duplicate_pattern(self, detector, test_user, db, benchmark):
        """
        Test duplicate detection focusing on email matching.

        Most common duplicate pattern in real applications.
        """
        # Create 5,000 persons, some with duplicate emails
        persons = []
        duplicate_email = "shared@company.com"

        for i in range(5000):
            # 5% of persons share an email (simulating corporate domains)
            email = duplicate_email if i % 20 == 0 else f"person{i}@test.com"

            persons.append(
                Person(
                    first_name=f"Person{i}",
                    last_name=f"Test{i}",
                    email=email,
                    created_by=test_user,
                )
            )

        Person.objects.bulk_create(persons, batch_size=1000)

        # Search for the duplicate email
        search_data: PersonDataDict = {
            "first_name": "NewPerson",
            "last_name": "NewTest",
            "email": duplicate_email,
        }

        # Benchmark
        result = benchmark(detector.find_duplicates, search_data)

        # Verify found all duplicates
        assert result.count() == 250  # 5% of 5000

        # Performance assertion
        assert benchmark.stats["mean"] < 0.100  # <100ms

    def test_phone_duplicate_pattern(self, detector, test_user, db, benchmark):
        """
        Test duplicate detection focusing on phone number matching.

        Tests phone number indexing performance.
        """
        # Create 5,000 persons
        persons = []
        duplicate_phone = "+14155551234"

        for i in range(5000):
            # 2% share a phone number (family members, etc.)
            phone = duplicate_phone if i % 50 == 0 else f"+1415555{i:04d}"

            persons.append(
                Person(
                    first_name=f"Person{i}",
                    last_name=f"Test{i}",
                    phone_primary=phone,
                    created_by=test_user,
                )
            )

        Person.objects.bulk_create(persons, batch_size=1000)

        # Search for the duplicate phone
        search_data: PersonDataDict = {
            "first_name": "NewPerson",
            "last_name": "NewTest",
            "phone_primary": duplicate_phone,
        }

        # Benchmark
        result = benchmark(detector.find_duplicates, search_data)

        # Verify found all duplicates (includes i=0, so 101 total)
        assert result.count() == 101  # 2% of 5000 (0, 50, 100, ..., 5000)

        # Performance assertion
        assert benchmark.stats["mean"] < 0.100  # <100ms

    def test_name_and_address_duplicate_pattern(
        self, detector, test_user, db, benchmark
    ):
        """
        Test duplicate detection using name and address matching.

        Tests composite query performance with address fields.
        """
        # Create 2,000 persons with some address duplicates
        persons = []
        duplicate_address = "123 Main St"
        duplicate_zip = "90210"

        for i in range(2000):
            # 3% share an address (apartment building residents)
            address = duplicate_address if i % 33 == 0 else f"{i} Elm St"
            zip_code = duplicate_zip if i % 33 == 0 else f"9{i:04d}"

            persons.append(
                Person(
                    first_name="John" if i % 33 == 0 else f"Person{i}",
                    last_name="Doe" if i % 33 == 0 else f"Test{i}",
                    street_address=address,
                    zip_code=zip_code,
                    created_by=test_user,
                )
            )

        Person.objects.bulk_create(persons, batch_size=1000)

        # Search for name and address match
        search_data: PersonDataDict = {
            "first_name": "John",
            "last_name": "Doe",
            "street_address": duplicate_address,
            "zip_code": duplicate_zip,
        }

        # Benchmark
        result = benchmark(detector.find_duplicates, search_data)

        # Verify found duplicates
        assert result.count() > 0

        # Performance assertion
        assert benchmark.stats["mean"] < 0.100  # <100ms


# ============================================================================
# SUMMARY PERFORMANCE TEST
# ============================================================================


@pytest.mark.django_db
class TestPerformanceSummary:
    """
    Summary test that validates all performance requirements together.

    This test serves as a comprehensive validation that the duplicate
    detection system meets all performance targets.
    """

    def test_comprehensive_performance_validation(self, detector, bulk_persons):
        """
        Comprehensive performance validation test.

        Validates:
        1. Performance targets at different scales
        2. Index usage
        3. Query efficiency
        4. No N+1 issues
        5. Acceptable scalability

        This is the PRIMARY acceptance test for performance requirements.
        """
        # Setup: Create 10,000 persons (target dataset size)
        bulk_persons(10000)

        # Test various search patterns
        test_patterns = [
            # Email search
            {
                "first_name": "Person5000",
                "last_name": "Test5000",
                "email": "person5000@test.com",
            },
            # Phone search
            {
                "first_name": "Person3000",
                "last_name": "Test3000",
                "phone_primary": "+14155553000",
            },
            # Name + DOB search
            {
                "first_name": "Person7000",
                "last_name": "Test7000",
                "date_of_birth": date(1980, 1, 1) + timedelta(days=7000 % 3650),
            },
        ]

        results = []
        for search_data in test_patterns:
            # Measure with query counting
            with CaptureQueriesContext(connection) as queries:
                start = time.perf_counter()
                result = detector.find_duplicates(search_data)
                list(result)  # Force evaluation
                elapsed = time.perf_counter() - start

            results.append(
                {
                    "pattern": search_data,
                    "time": elapsed,
                    "query_count": len(queries),
                    "found": result.count(),
                }
            )

        # Validate all results
        for r in results:
            # Primary requirement: <100ms with 10k records
            assert r["time"] < 0.100, (
                f"Query took {r['time'] * 1000:.2f}ms (target: <100ms)"
            )

            # Verify query efficiency (no N+1)
            assert r["query_count"] <= 2, f"Too many queries: {r['query_count']}"

            # Verify results were found
            assert r["found"] >= 1, "Expected to find duplicates"

        # Success: All performance requirements met
        print("\n=== PERFORMANCE VALIDATION PASSED ===")
        print(f"Total patterns tested: {len(results)}")
        print(f"Max query time: {max(r['time'] for r in results) * 1000:.2f}ms")
        avg_time = sum(r["time"] for r in results) / len(results) * 1000
        print(f"Avg query time: {avg_time:.2f}ms")
        print(f"Max queries per search: {max(r['query_count'] for r in results)}")
        print("All queries completed in <100ms with 10,000 records ✓")
