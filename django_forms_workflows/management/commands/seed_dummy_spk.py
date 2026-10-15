"""
Management command to seed dedicated dummy test accounts for SPK workflow testing.
Accounts: dummy.01 s/d dummy.07 with password 'Bandung*123#'
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from django_forms_workflows.models import EmployeeProfile, UserProfile


class Command(BaseCommand):
    help = "Seeds dummy.01 to dummy.07 accounts for full end-to-end SPK workflow simulation."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            type=str,
            default="Bandung*123#",
            help="Default password for all dummy accounts (default: Bandung*123#)",
        )

    def handle(self, *args, **options):
        password = options["password"]

        dummy_users_data = [
            {
                "username": "dummy.01",
                "nik": "DUMMY001",
                "full_name": "Dummy Sales Bali (Pemohon)",
                "position": "Sales Staff",
                "department": "Sales And Marketing",
                "company": "PT Cemerlang Abadi Mulia",
                "branch": "Bali",
                "groups": ["Sales Staff", "Sales And Marketing"],
                "stage_role": "Inisiator (Cabang Bali)",
            },
            {
                "username": "dummy.02",
                "nik": "DUMMY002",
                "full_name": "Dummy Sales Pusat (Pemohon)",
                "position": "Sales Staff",
                "department": "Sales And Marketing",
                "company": "PT Royal Abadi Sejahtera",
                "branch": "Pusat",
                "groups": ["Sales Staff", "Sales And Marketing"],
                "stage_role": "Inisiator (Cabang Pusat)",
            },
            {
                "username": "dummy.03",
                "nik": "DUMMY003",
                "full_name": "Dummy ASM (Reviewer L1)",
                "position": "Area Sales Manager",
                "department": "Sales And Marketing",
                "company": "PT Royal Abadi Sejahtera",
                "branch": "Pusat",
                "groups": ["Sales Area Manager", "Sales And Marketing"],
                "stage_role": "Stage 1: ASM Reviewer L1",
            },
            {
                "username": "dummy.04",
                "nik": "DUMMY004",
                "full_name": "Dummy RSOM (Reviewer L2)",
                "position": "Regional Sales Operations Manager",
                "department": "Sales And Marketing",
                "company": "PT Royal Abadi Sejahtera",
                "branch": "Pusat",
                "groups": ["Sales Area Manager", "Sales And Marketing"],
                "stage_role": "Stage 2: RSOM Reviewer L2",
            },
            {
                "username": "dummy.05",
                "nik": "DUMMY005",
                "full_name": "Dummy Support (Input Materai)",
                "position": "Sales Administration",
                "department": "Sales And Marketing",
                "company": "PT Royal Abadi Sejahtera",
                "branch": "Pusat",
                "groups": ["Sales Support", "Sales And Marketing"],
                "stage_role": "Stage 3: Sales Support Materai",
            },
            {
                "username": "dummy.06",
                "nik": "DUMMY006",
                "full_name": "Dummy Support (Verifikasi Toko)",
                "position": "Sales Administration",
                "department": "Sales And Marketing",
                "company": "PT Royal Abadi Sejahtera",
                "branch": "Pusat",
                "groups": ["Sales Support", "Sales And Marketing"],
                "stage_role": "Stage 4: Sales Support TTD Toko",
            },
            {
                "username": "dummy.07",
                "nik": "DUMMY007",
                "full_name": "Dummy Direktur Komersial",
                "position": "Direktur",
                "department": "Sales And Marketing",
                "company": "PT Royal Abadi Sejahtera",
                "branch": "Pusat",
                "groups": ["Commercial Director", "Direksi", "Sales And Marketing"],
                "stage_role": "Stage 5: Approval Final Direksi",
            },
        ]

        self.stdout.write(self.style.MIGRATE_HEADING("=== Provisioning Akun Dummy SPK (dummy.01 s/d dummy.07) ==="))

        created_users = {}

        for d in dummy_users_data:
            u, created = User.objects.get_or_create(
                username=d["username"],
                defaults={"email": f"{d['username']}@dummy.ras"},
            )
            u.set_password(password)
            u.first_name = d["full_name"].split()[0]
            u.last_name = " ".join(d["full_name"].split()[1:])
            u.is_active = True
            u.save()
            created_users[d["username"]] = u

            for gname in d["groups"]:
                g, _ = Group.objects.get_or_create(name=gname)
                u.groups.add(g)

            EmployeeProfile.objects.update_or_create(
                user=u,
                defaults={
                    "nik": d["nik"],
                    "full_name": d["full_name"],
                    "position": d["position"],
                    "department": d["department"],
                    "company": d["company"],
                    "branch": d["branch"],
                    "work_email": f"{d['username']}@dummy.ras",
                },
            )

            forms_profile, _ = UserProfile.objects.get_or_create(user=u)
            forms_profile.department = d["department"]
            forms_profile.title = d["position"]
            forms_profile.save()

            status_str = "Dibuat Baru" if created else "Diperbarui"
            self.stdout.write(f"- {d['stage_role']:<30} | {u.username:<10} | {status_str}")

        # Hubungkan hierarki supervisor untuk inisiator dummy.01 dan dummy.02
        asm_user = created_users.get("dummy.03")
        rsom_user = created_users.get("dummy.04")

        for uname in ["dummy.01", "dummy.02"]:
            ep = EmployeeProfile.objects.filter(user__username=uname).first()
            if ep:
                ep.supervisor_1 = asm_user
                ep.supervisor_1_name = "Dummy ASM (Reviewer L1)"
                ep.supervisor_1_position = "Area Sales Manager"
                ep.supervisor_2 = rsom_user
                ep.supervisor_2_name = "Dummy RSOM (Reviewer L2)"
                ep.supervisor_2_position = "Regional Sales Operations Manager"
                ep.save()

            fp = UserProfile.objects.filter(user__username=uname).first()
            if fp:
                fp.manager = asm_user
                fp.save()

        self.stdout.write(self.style.SUCCESS("\nHierarki supervisor dummy.01 & dummy.02 -> L1: dummy.03 (ASM), L2: dummy.04 (RSOM) TERHUBUNG."))
        self.stdout.write(self.style.SUCCESS(f"Password seluruh akun: {password}\n"))
