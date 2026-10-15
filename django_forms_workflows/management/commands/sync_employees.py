"""
Management command to synchronize employee data from Royal Corp HRIS API.

Automates:
- User provisioning with default password protection
- Group mapping by department and managerial role
- Supervisor hierarchy (Level 1 and Level 2)
- Bridging to UserProfile.manager for approval workflow routing
"""

import logging
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from django_forms_workflows.services.employee_sync import EmployeeSyncService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Synchronizes employee profiles and supervisor hierarchy from Royal Corp HRIS API."

    def add_arguments(self, parser):
        parser.add_argument(
            "--from",
            dest="date_from",
            type=str,
            default="1990-01-01",
            help="Filter start date for employee records (format: YYYY-MM-DD, default: 1990-01-01 for full sync)",
        )
        parser.add_argument(
            "--to",
            dest="date_to",
            type=str,
            default="2026-12-31",
            help="Filter end date for employee records (format: YYYY-MM-DD, default: 2026-12-31)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate the sync process without writing any changes to the database.",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=getattr(settings, "HRIS_API_TIMEOUT", 45),
            help="API request timeout in seconds (default: settings.HRIS_API_TIMEOUT or 45).",
        )

    def handle(self, *args, **options):
        date_from = options["date_from"]
        date_to = options["date_to"]
        dry_run = options["dry_run"]
        timeout = options["timeout"]
        verbosity = options.get("verbosity", 1)

        mode_str = "DRY-RUN (SIMULATION)" if dry_run else "LIVE SYNC"

        self.stdout.write(self.style.MIGRATE_HEADING(f"=== Starting HRIS Employee Sync [{mode_str}] ==="))
        self.stdout.write(f"Endpoint : {settings.HRIS_API_URL}")
        self.stdout.write(f"Range    : {date_from} -> {date_to}")
        self.stdout.write(f"Timeout  : {timeout}s\n")

        service = EmployeeSyncService(timeout=timeout)

        try:
            metrics = service.run_sync(date_from=date_from, date_to=date_to, dry_run=dry_run)
        except Exception as exc:
            logger.exception("Error executing HRIS employee sync: %s", exc)
            raise CommandError(f"Sync failed with error: {exc}")

        # Summary Presentation
        self.stdout.write(self.style.SUCCESS("=" * 64))
        self.stdout.write(self.style.SUCCESS(f"HRIS Employee Sync - Results [{mode_str}]"))
        self.stdout.write(self.style.SUCCESS("=" * 64))
        self.stdout.write(f"Total records from API   : {metrics['total_records']}")
        self.stdout.write(f"Users created (new)      : {metrics['users_created']}")
        self.stdout.write(f"Users updated (existing) : {metrics['users_updated']}")
        self.stdout.write(f"Users skipped (no change): {metrics['users_skipped']}")
        self.stdout.write(f"Supervisors created (new): {metrics['supervisors_created']}")
        self.stdout.write(f"Supervisor L1 resolved   : {metrics['supervisor_1_resolved']}")
        self.stdout.write(f"Supervisor L2 resolved   : {metrics['supervisor_2_resolved']}")
        self.stdout.write(f"Groups assigned          : {metrics['groups_assigned']}")
        self.stdout.write(f"Duration                 : {metrics['duration_seconds']}s")
        self.stdout.write(f"Errors                   : {len(metrics['errors'])}")
        self.stdout.write(self.style.SUCCESS("=" * 64))

        if metrics["errors"] and verbosity >= 2:
            self.stdout.write(self.style.WARNING("\nEncountered Warnings/Errors:"))
            for err in metrics["errors"]:
                self.stdout.write(f" - {err}")

        if dry_run:
            self.stdout.write(self.style.NOTICE("\nDry run completed successfully. No changes were committed to database."))
        else:
            self.stdout.write(self.style.SUCCESS("\nSync completed successfully and committed to database."))
