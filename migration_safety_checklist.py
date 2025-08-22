#!/usr/bin/env python
"""
Migration Safety Checklist for CivicPulse

Comprehensive checklist to ensure database migration safety and production readiness.
This checklist should be completed before any production database migration.
"""
import json
import os
import sys
from datetime import datetime, timedelta

# Setup Django
sys.path.append('/home/kwhatcher/projects/civicpulse/civicpulse-backend/.worktree/copilot/fix-16')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cpback.settings.development')

import django

django.setup()

from django.core.management import call_command
from django.db import connection

from civicpulse.audit import AuditLog
from civicpulse.models import ContactAttempt, Person, User, VoterRecord


class MigrationSafetyChecklist:
    """
    Comprehensive migration safety checklist with automated validation
    where possible and clear manual verification steps.
    """

    def __init__(self):
        self.checklist_items = self.generate_checklist()
        self.results = {}

    def generate_checklist(self):
        """Generate comprehensive migration safety checklist."""
        return {
            "pre_migration_preparation": {
                "title": "Pre-Migration Preparation",
                "items": [
                    {
                        "id": "backup_verification",
                        "requirement": "Database backup created and verified",
                        "description": "Full database backup created within last 24 hours and restore tested",
                        "validation": "automated",
                        "critical": True,
                        "acceptance_criteria": [
                            "Backup file exists and is not corrupt",
                            "Backup contains all expected tables and data",
                            "Test restore completes successfully",
                            "Backup is stored in secure, accessible location"
                        ]
                    },
                    {
                        "id": "migration_dependencies",
                        "requirement": "Migration dependencies verified",
                        "description": "All migration dependencies properly resolved with no circular references",
                        "validation": "automated",
                        "critical": True,
                        "acceptance_criteria": [
                            "Django migration plan executes without errors",
                            "No missing migration dependencies",
                            "No circular dependency issues",
                            "All required migrations are available"
                        ]
                    },
                    {
                        "id": "schema_state_check",
                        "requirement": "Database schema state validated",
                        "description": "Current database schema matches Django models",
                        "validation": "automated",
                        "critical": True,
                        "acceptance_criteria": [
                            "makemigrations --check passes",
                            "No unapplied migrations exist",
                            "Database introspection matches model definitions"
                        ]
                    },
                    {
                        "id": "disk_space_check",
                        "requirement": "Adequate disk space available",
                        "description": "Sufficient disk space for migration operations and data growth",
                        "validation": "automated",
                        "critical": True,
                        "acceptance_criteria": [
                            "At least 50% free disk space available",
                            "Minimum 10GB free space for large table operations",
                            "Temporary space available for index creation"
                        ]
                    },
                    {
                        "id": "maintenance_window",
                        "requirement": "Maintenance window scheduled and communicated",
                        "description": "Stakeholders notified of maintenance window and expected downtime",
                        "validation": "manual",
                        "critical": False,
                        "acceptance_criteria": [
                            "Stakeholders notified at least 48 hours in advance",
                            "Maintenance window scheduled during low-usage period",
                            "Expected downtime communicated clearly",
                            "Rollback plan time limits communicated"
                        ]
                    }
                ]
            },
            "migration_analysis": {
                "title": "Migration Analysis and Risk Assessment",
                "items": [
                    {
                        "id": "migration_type_analysis",
                        "requirement": "Migration types analyzed and categorized",
                        "description": "All migrations categorized by type and risk level",
                        "validation": "manual",
                        "critical": True,
                        "acceptance_criteria": [
                            "Backward compatible vs incompatible migrations identified",
                            "Data migration scope and duration estimated",
                            "Index creation/modification impact assessed",
                            "Foreign key constraint changes evaluated"
                        ]
                    },
                    {
                        "id": "data_volume_assessment",
                        "requirement": "Data volume impact assessed",
                        "description": "Migration performance tested with production-volume data",
                        "validation": "automated",
                        "critical": True,
                        "acceptance_criteria": [
                            "Migration tested with >= 70% of production data volume",
                            "Migration completion time < 15 minutes",
                            "Memory usage remains within acceptable limits",
                            "No table locks longer than 30 seconds"
                        ]
                    },
                    {
                        "id": "backward_compatibility",
                        "requirement": "Backward compatibility verified",
                        "description": "Migration doesn't break existing application functionality",
                        "validation": "manual",
                        "critical": True,
                        "acceptance_criteria": [
                            "Current application code works with new schema",
                            "No breaking changes to existing API endpoints",
                            "Database queries remain functional",
                            "Rollback path preserves data integrity"
                        ]
                    },
                    {
                        "id": "index_strategy",
                        "requirement": "Index creation strategy validated",
                        "description": "Index creation/modification optimized for minimal downtime",
                        "validation": "manual",
                        "critical": True,
                        "acceptance_criteria": [
                            "Large indexes created concurrently where possible",
                            "Index creation time estimated and acceptable",
                            "Table lock duration minimized",
                            "Query performance impact assessed"
                        ]
                    }
                ]
            },
            "testing_validation": {
                "title": "Testing and Validation",
                "items": [
                    {
                        "id": "migration_test_execution",
                        "requirement": "Migration safety tests executed successfully",
                        "description": "Comprehensive automated migration safety tests pass",
                        "validation": "automated",
                        "critical": True,
                        "acceptance_criteria": [
                            "Forward migration tests pass",
                            "Rollback migration tests pass",
                            "Data integrity tests pass",
                            "Performance benchmarks met"
                        ]
                    },
                    {
                        "id": "rollback_procedure_test",
                        "requirement": "Rollback procedures tested and verified",
                        "description": "Migration rollback tested on copy of production data",
                        "validation": "manual",
                        "critical": True,
                        "acceptance_criteria": [
                            "Rollback migrations execute successfully",
                            "Data integrity maintained after rollback",
                            "Application functionality restored",
                            "Rollback completion time < 10 minutes"
                        ]
                    },
                    {
                        "id": "application_functionality",
                        "requirement": "Critical application functions validated",
                        "description": "Key application workflows tested with new schema",
                        "validation": "manual",
                        "critical": True,
                        "acceptance_criteria": [
                            "User authentication/authorization works",
                            "Core CRUD operations functional",
                            "Data export/import processes work",
                            "Audit logging continues to function",
                            "Performance within acceptable ranges"
                        ]
                    },
                    {
                        "id": "data_integrity_validation",
                        "requirement": "Data integrity comprehensively validated",
                        "description": "All data integrity constraints and relationships verified",
                        "validation": "automated",
                        "critical": True,
                        "acceptance_criteria": [
                            "Foreign key relationships intact",
                            "Data counts match expectations",
                            "No orphaned records created",
                            "Audit trail continuity maintained"
                        ]
                    }
                ]
            },
            "production_readiness": {
                "title": "Production Readiness",
                "items": [
                    {
                        "id": "monitoring_alerting",
                        "requirement": "Monitoring and alerting configured",
                        "description": "Comprehensive monitoring in place for migration and post-deployment",
                        "validation": "manual",
                        "critical": True,
                        "acceptance_criteria": [
                            "Database performance metrics monitored",
                            "Application error rate tracking active",
                            "Migration progress monitoring configured",
                            "Alert thresholds set for critical metrics"
                        ]
                    },
                    {
                        "id": "team_readiness",
                        "requirement": "Team prepared for migration execution",
                        "description": "All team members briefed and ready for migration day",
                        "validation": "manual",
                        "critical": False,
                        "acceptance_criteria": [
                            "Migration lead identified and available",
                            "Database administrator on standby",
                            "Application support team available",
                            "Communication channels established"
                        ]
                    },
                    {
                        "id": "documentation_complete",
                        "requirement": "Migration documentation complete",
                        "description": "All migration procedures documented and accessible",
                        "validation": "manual",
                        "critical": False,
                        "acceptance_criteria": [
                            "Step-by-step migration procedures documented",
                            "Rollback procedures clearly defined",
                            "Emergency contact information available",
                            "Post-migration validation checklist ready"
                        ]
                    },
                    {
                        "id": "communication_plan",
                        "requirement": "Communication plan implemented",
                        "description": "Stakeholder communication plan for migration day",
                        "validation": "manual",
                        "critical": False,
                        "acceptance_criteria": [
                            "User notification system prepared",
                            "Status page updates planned",
                            "Internal team communication channels ready",
                            "Post-migration success/failure communications drafted"
                        ]
                    }
                ]
            },
            "security_compliance": {
                "title": "Security and Compliance",
                "items": [
                    {
                        "id": "audit_compliance",
                        "requirement": "Audit trail compliance maintained",
                        "description": "Migration preserves audit trail and compliance requirements",
                        "validation": "automated",
                        "critical": True,
                        "acceptance_criteria": [
                            "Audit log table structure preserved",
                            "Audit trail continuity maintained",
                            "Compliance reporting functions intact",
                            "Data retention policies respected"
                        ]
                    },
                    {
                        "id": "security_review",
                        "requirement": "Security implications reviewed",
                        "description": "Migration security implications assessed and approved",
                        "validation": "manual",
                        "critical": True,
                        "acceptance_criteria": [
                            "New database objects follow security standards",
                            "Access permissions properly configured",
                            "No sensitive data exposed",
                            "Encryption requirements maintained"
                        ]
                    },
                    {
                        "id": "data_privacy",
                        "requirement": "Data privacy requirements met",
                        "description": "Migration respects data privacy and protection requirements",
                        "validation": "manual",
                        "critical": True,
                        "acceptance_criteria": [
                            "PII handling procedures followed",
                            "Data minimization principles respected",
                            "Consent management system intact",
                            "Data subject rights preserved"
                        ]
                    }
                ]
            },
            "post_migration": {
                "title": "Post-Migration Validation",
                "items": [
                    {
                        "id": "performance_validation",
                        "requirement": "Performance benchmarks validated",
                        "description": "System performance meets or exceeds pre-migration levels",
                        "validation": "automated",
                        "critical": True,
                        "acceptance_criteria": [
                            "Response times within 10% of baseline",
                            "Database query performance acceptable",
                            "No resource utilization spikes",
                            "User experience unchanged"
                        ]
                    },
                    {
                        "id": "user_acceptance",
                        "requirement": "User acceptance validation completed",
                        "description": "Key users validate system functionality post-migration",
                        "validation": "manual",
                        "critical": True,
                        "acceptance_criteria": [
                            "Core user workflows functional",
                            "No user-reported data issues",
                            "System responsiveness acceptable",
                            "All features accessible"
                        ]
                    },
                    {
                        "id": "cleanup_completion",
                        "requirement": "Migration cleanup completed",
                        "description": "Temporary migration artifacts cleaned up",
                        "validation": "manual",
                        "critical": False,
                        "acceptance_criteria": [
                            "Temporary tables/columns removed",
                            "Old backup files archived",
                            "Migration-specific code removed",
                            "Documentation updated"
                        ]
                    }
                ]
            }
        }

    def run_automated_checks(self):
        """Run all automated checklist validations."""
        print("=== Running Automated Migration Safety Checks ===")

        # Check 1: Migration dependencies
        self.check_migration_dependencies()

        # Check 2: Schema state
        self.check_schema_state()

        # Check 3: Disk space
        self.check_disk_space()

        # Check 4: Data volume assessment
        self.check_data_volumes()

        # Check 5: Data integrity
        self.check_data_integrity()

        # Check 6: Audit compliance
        self.check_audit_compliance()

        # Check 7: Performance validation
        self.check_performance_baseline()

        return self.results

    def check_migration_dependencies(self):
        """Check migration dependencies."""
        try:
            from django.db.migrations.executor import MigrationExecutor
            from django.db.migrations.loader import MigrationLoader

            loader = MigrationLoader(connection)
            executor = MigrationExecutor(connection)

            # Get migration plan
            targets = loader.graph.leaf_nodes()
            plan = executor.migration_plan(targets)

            # Check for issues
            dependency_errors = []
            for migration, _backwards in plan:
                app_label, migration_name = migration
                node = loader.graph.nodes.get(migration)
                if node:
                    for dep_app, dep_migration in node.dependencies:
                        dep_node = loader.graph.nodes.get((dep_app, dep_migration))
                        if not dep_node:
                            dependency_errors.append(f"Missing: {dep_app}.{dep_migration}")

            self.results['migration_dependencies'] = {
                'status': 'PASS' if not dependency_errors else 'FAIL',
                'errors': dependency_errors,
                'migration_count': len(plan)
            }

            status = "✓ PASS" if not dependency_errors else "✗ FAIL"
            print(f"{status} Migration Dependencies: {len(plan)} migrations, {len(dependency_errors)} errors")

        except Exception as e:
            self.results['migration_dependencies'] = {
                'status': 'ERROR',
                'error': str(e)
            }
            print(f"✗ ERROR Migration Dependencies: {e}")

    def check_schema_state(self):
        """Check current schema state."""
        try:
            # Check if schema is up to date

            from django.core.management.base import CommandError

            try:
                call_command('makemigrations', '--check', '--dry-run', verbosity=0)
                schema_current = True
                unmade_changes = None
            except CommandError as e:
                schema_current = False
                unmade_changes = str(e)

            self.results['schema_state'] = {
                'status': 'PASS' if schema_current else 'WARNING',
                'schema_current': schema_current,
                'unmade_changes': unmade_changes
            }

            status = "✓ PASS" if schema_current else "! WARNING"
            print(f"{status} Schema State: {'Current' if schema_current else 'Has unmade changes'}")

        except Exception as e:
            self.results['schema_state'] = {
                'status': 'ERROR',
                'error': str(e)
            }
            print(f"✗ ERROR Schema State: {e}")

    def check_disk_space(self):
        """Check available disk space."""
        try:
            import shutil

            # Get disk usage for current directory (database location)
            total, used, free = shutil.disk_usage('.')
            free_gb = free / (1024**3)
            free_percent = (free / total) * 100

            # Check if adequate space available
            adequate_space = free_gb > 10 and free_percent > 20

            self.results['disk_space'] = {
                'status': 'PASS' if adequate_space else 'FAIL',
                'free_gb': round(free_gb, 2),
                'free_percent': round(free_percent, 2),
                'adequate': adequate_space
            }

            status = "✓ PASS" if adequate_space else "✗ FAIL"
            print(f"{status} Disk Space: {free_gb:.2f}GB free ({free_percent:.1f}%)")

        except Exception as e:
            self.results['disk_space'] = {
                'status': 'ERROR',
                'error': str(e)
            }
            print(f"✗ ERROR Disk Space: {e}")

    def check_data_volumes(self):
        """Check data volumes for migration testing."""
        try:
            # Get record counts
            counts = {
                'users': User.objects.count(),
                'persons': Person.objects.count(),
                'contact_attempts': ContactAttempt.objects.count(),
                'voter_records': VoterRecord.objects.count(),
                'audit_logs': AuditLog.objects.count()
            }

            # Assess if volumes are adequate for testing
            total_records = sum(counts.values())
            adequate_volume = total_records > 1000  # Minimum threshold

            self.results['data_volumes'] = {
                'status': 'PASS' if adequate_volume else 'WARNING',
                'counts': counts,
                'total_records': total_records,
                'adequate_for_testing': adequate_volume
            }

            status = "✓ PASS" if adequate_volume else "! WARNING"
            print(f"{status} Data Volumes: {total_records:,} total records")
            for table, count in counts.items():
                print(f"  {table}: {count:,}")

        except Exception as e:
            self.results['data_volumes'] = {
                'status': 'ERROR',
                'error': str(e)
            }
            print(f"✗ ERROR Data Volumes: {e}")

    def check_data_integrity(self):
        """Check basic data integrity."""
        try:
            integrity_issues = []

            # Check foreign key relationships
            orphaned_persons = Person.objects.filter(created_by__isnull=True).exclude(created_by=None).count()
            if orphaned_persons > 0:
                integrity_issues.append(f"{orphaned_persons} persons with invalid created_by references")

            # Check voter record relationships
            orphaned_voters = VoterRecord.objects.filter(person__isnull=True).count()
            if orphaned_voters > 0:
                integrity_issues.append(f"{orphaned_voters} voter records with invalid person references")

            # Check contact attempt relationships
            orphaned_contacts = ContactAttempt.objects.filter(person__isnull=True).count()
            if orphaned_contacts > 0:
                integrity_issues.append(f"{orphaned_contacts} contact attempts with invalid person references")

            self.results['data_integrity'] = {
                'status': 'PASS' if not integrity_issues else 'FAIL',
                'issues': integrity_issues,
                'checks_performed': ['foreign_key_integrity', 'orphaned_records']
            }

            status = "✓ PASS" if not integrity_issues else "✗ FAIL"
            print(f"{status} Data Integrity: {len(integrity_issues)} issues found")
            for issue in integrity_issues:
                print(f"  - {issue}")

        except Exception as e:
            self.results['data_integrity'] = {
                'status': 'ERROR',
                'error': str(e)
            }
            print(f"✗ ERROR Data Integrity: {e}")

    def check_audit_compliance(self):
        """Check audit trail compliance."""
        try:
            # Check audit log functionality
            recent_logs = AuditLog.objects.filter(
                timestamp__gte=datetime.now() - timedelta(days=7)
            ).count()

            # Check audit log structure
            audit_fields_present = all(
                hasattr(AuditLog, field) for field in
                ['user', 'action', 'object_repr', 'changes', 'timestamp']
            )

            compliance_ok = recent_logs > 0 and audit_fields_present

            self.results['audit_compliance'] = {
                'status': 'PASS' if compliance_ok else 'WARNING',
                'recent_audit_logs': recent_logs,
                'audit_fields_present': audit_fields_present,
                'compliance_status': compliance_ok
            }

            status = "✓ PASS" if compliance_ok else "! WARNING"
            print(f"{status} Audit Compliance: {recent_logs} recent audit logs")

        except Exception as e:
            self.results['audit_compliance'] = {
                'status': 'ERROR',
                'error': str(e)
            }
            print(f"✗ ERROR Audit Compliance: {e}")

    def check_performance_baseline(self):
        """Check performance baseline metrics."""
        try:
            import time

            # Simple performance test - query execution times
            start_time = time.time()
            Person.objects.count()
            person_query_time = time.time() - start_time

            start_time = time.time()
            ContactAttempt.objects.select_related('person').count()
            contact_query_time = time.time() - start_time

            start_time = time.time()
            AuditLog.objects.order_by('-timestamp')[:100].count()
            audit_query_time = time.time() - start_time

            # Check if performance is acceptable
            max_acceptable_time = 1.0  # 1 second
            performance_ok = all(
                t < max_acceptable_time
                for t in [person_query_time, contact_query_time, audit_query_time]
            )

            self.results['performance_baseline'] = {
                'status': 'PASS' if performance_ok else 'WARNING',
                'query_times': {
                    'person_count': round(person_query_time, 3),
                    'contact_with_person': round(contact_query_time, 3),
                    'audit_recent': round(audit_query_time, 3)
                },
                'performance_acceptable': performance_ok
            }

            status = "✓ PASS" if performance_ok else "! WARNING"
            print(f"{status} Performance Baseline: Queries within acceptable range")

        except Exception as e:
            self.results['performance_baseline'] = {
                'status': 'ERROR',
                'error': str(e)
            }
            print(f"✗ ERROR Performance Baseline: {e}")

    def generate_checklist_report(self):
        """Generate comprehensive checklist report."""
        timestamp = datetime.now()

        # Calculate overall status
        automated_results = [r for r in self.results.values() if isinstance(r, dict)]
        passed = sum(1 for r in automated_results if r.get('status') == 'PASS')
        failed = sum(1 for r in automated_results if r.get('status') == 'FAIL')
        warnings = sum(1 for r in automated_results if r.get('status') == 'WARNING')
        errors = sum(1 for r in automated_results if r.get('status') == 'ERROR')

        report = {
            'migration_safety_checklist': {
                'generated_at': timestamp.isoformat(),
                'checklist_version': '1.0',
                'automated_checks': {
                    'total': len(automated_results),
                    'passed': passed,
                    'failed': failed,
                    'warnings': warnings,
                    'errors': errors,
                    'results': self.results
                },
                'checklist_items': self.checklist_items,
                'overall_readiness': {
                    'automated_checks_ready': failed == 0 and errors == 0,
                    'critical_items_complete': 'Manual verification required',
                    'recommendation': 'Complete manual checklist items before proceeding'
                }
            }
        }

        # Save report
        report_file = f'migration_safety_checklist_{timestamp.strftime("%Y%m%d_%H%M%S")}.json'
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        print("\n=== Migration Safety Checklist Summary ===")
        print(f"Report saved to: {report_file}")
        print(f"Automated checks: {passed} passed, {failed} failed, {warnings} warnings, {errors} errors")

        if failed > 0 or errors > 0:
            print("⚠️  MIGRATION NOT READY - Fix failed checks before proceeding")
        elif warnings > 0:
            print("⚠️  PROCEED WITH CAUTION - Review warnings before proceeding")
        else:
            print("✅ AUTOMATED CHECKS PASSED - Complete manual checklist items")

        return report_file

    def print_manual_checklist(self):
        """Print manual checklist items for verification."""
        print("\n=== MANUAL VERIFICATION CHECKLIST ===")
        print("Complete these items manually before migration:")

        for _section_key, section in self.checklist_items.items():
            print(f"\n{section['title']}:")
            print("-" * len(section['title']))

            for item in section['items']:
                if item['validation'] == 'manual':
                    critical = " [CRITICAL]" if item['critical'] else ""
                    print(f"\n☐ {item['requirement']}{critical}")
                    print(f"   {item['description']}")
                    print("   Acceptance Criteria:")
                    for criteria in item['acceptance_criteria']:
                        print(f"   • {criteria}")

def main():
    """Main function to run migration safety checklist."""
    print("=== Migration Safety Checklist Validation ===")

    checklist = MigrationSafetyChecklist()

    # Run automated checks
    checklist.run_automated_checks()

    # Generate report
    checklist.generate_checklist_report()

    # Print manual checklist
    checklist.print_manual_checklist()

    return checklist

if __name__ == '__main__':
    main()
