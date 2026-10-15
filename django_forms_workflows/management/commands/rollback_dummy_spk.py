"""
Management command to rollback and delete dummy test accounts (dummy.01 s/d dummy.07).
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django_forms_workflows.models import EmployeeProfile, UserProfile


class Command(BaseCommand):
    help = "Rolls back and deletes all dummy test accounts (dummy.01 to dummy.07)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate the rollback process without actually deleting records.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        dummy_usernames = [f"dummy.{i:02d}" for i in range(1, 8)]

        self.stdout.write(self.style.MIGRATE_HEADING("=== Rollback Akun Dummy SPK (dummy.01 s/d dummy.07) ==="))

        users_to_delete = User.objects.filter(username__in=dummy_usernames)
        count = users_to_delete.count()

        if count == 0:
            self.stdout.write(self.style.WARNING("Tidak ditemukan akun dummy.01 s/d dummy.07 di basis data."))
            return

        for u in users_to_delete:
            self.stdout.write(f"- Menghapus: {u.username} ({u.get_full_name()})")

        if dry_run:
            self.stdout.write(self.style.NOTICE(f"\n[DRY RUN] {count} akun akan dihapus."))
        else:
            # Delete associated EmployeeProfile and UserProfile
            EmployeeProfile.objects.filter(user__in=users_to_delete).delete()
            UserProfile.objects.filter(user__in=users_to_delete).delete()
            users_to_delete.delete()
            self.stdout.write(self.style.SUCCESS(f"\nBerhasil menghapus {count} akun dummy beserta profil terkait."))
