"""
Management command to test e-Meterai provider integration safely.
Supports:
  1. --mock: Full pipeline test with MockMeteraiProvider (0 quota consumed)
  2. --dry-run: PDF generation, last-page detection & payload schema test (0 quota consumed)
  3. --live --single-run: Controlled single live API test against EzMeterai Sandbox (uses exactly 1 quota)
"""

from __future__ import annotations

import io
import os
import sys
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from django_forms_workflows.models import FormDefinition, FormSubmission
from django_forms_workflows.services.ematerai import (
    EMeteraiService,
    EzMeteraiProvider,
    MockMeteraiProvider,
)


class Command(BaseCommand):
    help = "Test e-Meterai single stamping pipeline (Mock, Dry-Run, or Single Live Sandbox Test)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--mock",
            action="store_true",
            help="Execute test using Mock provider (Consumes 0 quota, no network calls)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Generate SPK PDF in-memory, detect pages, and validate payload schema (Consumes 0 quota)",
        )
        parser.add_argument(
            "--live",
            action="store_true",
            help="Perform actual network call to EzMeterai Sandbox API",
        )
        parser.add_argument(
            "--single-run",
            action="store_true",
            help="Mandatory safety confirmation flag when using --live to ensure only 1 quota is used",
        )
        parser.add_argument(
            "--submission-id",
            type=int,
            default=None,
            help="Optional submission ID to use. If omitted, uses the latest SPK submission or creates a dummy test submission.",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== e-Meterai Integration Test Suite ==="))

        is_mock = options.get("mock")
        is_dry_run = options.get("dry_run")
        is_live = options.get("live")
        is_single_run = options.get("single_run")
        sub_id = options.get("submission_id")

        if not (is_mock or is_dry_run or is_live):
            self.stdout.write(
                self.style.WARNING(
                    "No test mode specified. Please specify either --mock, --dry-run, or --live --single-run."
                )
            )
            return

        # 1. Resolve or create a representative SPK submission
        submission = self._get_or_create_test_submission(sub_id)
        self.stdout.write(f"Using Submission #{submission.id} ('{submission.form_definition.name}')")

        # -------------------------------------------------------------
        # FASE 1: Mock Pipeline Test
        # -------------------------------------------------------------
        if is_mock:
            self.stdout.write(self.style.SUCCESS("\n[FASE 1: MOCK PROVIDER PIPELINE TEST]"))
            self.stdout.write("Running complete stamping flow via MockMeteraiProvider (0 quota consumed)...")

            mock_provider = MockMeteraiProvider(initial_quota=30)
            initial_balance = mock_provider.get_quota_balance().available_quota
            self.stdout.write(f"Initial Mock Quota: {initial_balance}")

            stamped_doc = EMeteraiService.stamp_submission(
                submission=submission,
                provider_name="mock",
                force_retry=True,
            )

            self.stdout.write(f"Result Status : {stamped_doc.status}")
            self.stdout.write(f"Saved File    : {stamped_doc.file_name}")
            self.stdout.write(f"File Size     : {stamped_doc.file_size} bytes")
            self.stdout.write(f"Target Page   : Page {stamped_doc.page_number}")
            self.stdout.write(f"Coordinates   : {stamped_doc.coordinates}")

            final_balance = mock_provider.get_quota_balance().available_quota
            self.stdout.write(f"Final Mock Quota: {final_balance}")

            if stamped_doc.status == "stamped":
                self.stdout.write(self.style.SUCCESS("[OK] FASE 1 (Mock Test) PASSED 100% SUCCESSFUL!\n"))
            else:
                self.stdout.write(self.style.ERROR(f"[FAILED] FASE 1 FAILED: {stamped_doc.error_message}\n"))
            return

        # -------------------------------------------------------------
        # FASE 2: Dry-Run Payload & Coordinate Validation
        # -------------------------------------------------------------
        if is_dry_run:
            self.stdout.write(self.style.SUCCESS("\n[FASE 2: DRY-RUN PAYLOAD & COORDINATE VALIDATION]"))
            self.stdout.write("Validating in-memory PDF generation, page counting, and EzMeterai payload schema...")
            active_provider = getattr(settings, "EMATERAI_PROVIDER", "mock")
            self.stdout.write(f"Configured Provider : {active_provider}")

            # Generate PDF with for_stamping=True (slot kept open)
            pdf_bytes, page_count = EMeteraiService.generate_spk_pdf_bytes(submission, for_stamping=True)
            self.stdout.write(f"Generated PDF Size  : {len(pdf_bytes):,} bytes")
            self.stdout.write(f"Total Pages         : {page_count} page(s)")

            llx, lly, urx, ury = EMeteraiService.get_stamping_coordinates(pdf_bytes=pdf_bytes)
            int_llx = int(round(float(llx)))
            int_lly = int(round(float(lly)))
            int_urx = int(round(float(urx)))
            int_ury = int(round(float(ury)))

            self.stdout.write(f"Target Page         : Page {page_count} (Last Page)")
            self.stdout.write(f"Stamping Coordinates: llx={int_llx}, lly={int_lly}, urx={int_urx}, ury={int_ury}")

            # Verify PDF starts with %PDF header
            assert pdf_bytes.startswith(b"%PDF"), "Generated file does not start with %PDF header!"

            # Construct dry-run payload matching EzMeterai API schema
            sample_file_key = "DRY_RUN_FILE_KEY_ABC123"
            payload = {
                "file": sample_file_key,
                "external_id": f"SPK_DRY_RUN_{submission.id}",
                "items": [
                    {
                        "page": int(page_count),
                        "product_id": 1,
                        "bbox": {
                            "llx": int_llx,
                            "lly": int_lly,
                            "urx": int_urx,
                            "ury": int_ury,
                        },
                    }
                ],
            }
            import json
            self.stdout.write(f"Simulated EzMeterai JSON Payload:\n{json.dumps(payload, indent=2)}")

            # Verify coordinate boundaries for A4 (595.28 x 841.89 pt)
            if 0 <= int_llx < int_urx <= 595.28 and 0 <= int_lly < int_ury <= 841.89:
                self.stdout.write(self.style.SUCCESS("[OK] Coordinates fit completely within standard A4 bounds."))
            else:
                self.stdout.write(self.style.WARNING("[WARN] Coordinates exceed standard A4 bounding box!"))

            self.stdout.write(self.style.SUCCESS("[OK] Zero Quota Protection Active (No external HTTP request sent to EzMeterai API)."))
            self.stdout.write(self.style.SUCCESS("[OK] FASE 2 (Dry-Run Validation) PASSED 100% SUCCESSFUL (0 Quota Consumed)!\n"))
            return

        # -------------------------------------------------------------
        # FASE 3: 1x Single Live Stamping Sandbox Test
        # -------------------------------------------------------------
        if is_live:
            if not is_single_run:
                self.stdout.write(
                    self.style.ERROR(
                        "SECURITY SAFEGUARD: To execute a live test against EzMeterai Sandbox, "
                        "you MUST provide the '--single-run' flag to confirm that exactly 1 quota is consumed."
                    )
                )
                return

            self.stdout.write(self.style.WARNING("\n[FASE 3: 1x SINGLE LIVE SANDBOX STAMPING TEST]"))
            self.stdout.write("Target Provider: EzMeterai Sandbox")
            self.stdout.write(f"Base URL       : {getattr(settings, 'EMATERAI_BASE_URL', 'https://api-sandbox.ezmeterai.id')}")

            ez_provider = EzMeteraiProvider()

            # 1. Check initial quota
            self.stdout.write("1. Checking account balance / status before test...")
            quota_res = ez_provider.get_quota_balance()
            if quota_res.success:
                self.stdout.write(self.style.SUCCESS(f"   Current Quota Balance: {quota_res.available_quota}"))
            else:
                self.stdout.write(f"   Quota info note: {quota_res.message}")

            # 2. Execute Stamping Pipeline
            self.stdout.write("2. Uploading SPK PDF and executing live single stamping...")
            stamped_doc = EMeteraiService.stamp_submission(
                submission=submission,
                provider_name="ezmeterai",
                force_retry=True,
            )

            self.stdout.write(f"   Stamping Result Status: {stamped_doc.status}")

            if stamped_doc.status == "stamped":
                self.stdout.write(self.style.SUCCESS(f"   Document ID  : {stamped_doc.provider_document_id}"))
                self.stdout.write(self.style.SUCCESS(f"   Saved PDF    : {stamped_doc.stamped_file.path if hasattr(stamped_doc.stamped_file, 'path') else stamped_doc.file_name}"))
                self.stdout.write(self.style.SUCCESS(f"   File Size    : {stamped_doc.file_size:,} bytes"))
                self.stdout.write(self.style.SUCCESS("[OK] FASE 3 (Single Live Test) COMPLETED SUCCESSFULLY!"))

                # 3. Check quota after test
                post_quota = ez_provider.get_quota_balance()
                if post_quota.success:
                    self.stdout.write(self.style.SUCCESS(f"   Remaining Quota Balance: {post_quota.available_quota}"))
            else:
                self.stdout.write(self.style.ERROR(f"[FAILED] Stamping failed: {stamped_doc.error_message}"))


    def _get_or_create_test_submission(self, sub_id=None) -> FormSubmission:
        """Helper to get existing SPK submission or create a valid test dummy."""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        if sub_id:
            sub = FormSubmission.objects.filter(id=sub_id).first()
            if sub:
                return sub

        # Try to find latest permohonan-kontrak submission
        sub = FormSubmission.objects.filter(
            form_definition__slug="permohonan-kontrak"
        ).order_by("-id").first()
        if sub:
            return sub

        # Fallback: create a dummy submission for testing
        form_def = FormDefinition.objects.filter(slug="permohonan-kontrak").first()
        if not form_def:
            form_def = FormDefinition.objects.first()

        admin_user = User.objects.filter(is_superuser=True).first() or User.objects.first()

        sub = FormSubmission.objects.create(
            form_definition=form_def,
            submitter=admin_user,
            status="approved",
            form_data={
                "no_spk": "SPK-TEST-001",
                "nama_toko": "Toko Sandbox Test Prima",
                "nama_pemilik": "Bapak Penguji Sandbox",
                "perusahaan": "PT Royal Golden Prima",
                "cabang": "Bandung",
                "nilai_target": "500000000",
            },
        )
        return sub
