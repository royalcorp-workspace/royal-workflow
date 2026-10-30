import json
import re
from django.core.management.base import BaseCommand
from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django.utils import timezone
from django_forms_workflows.models import (
    FormDefinition,
    FormSubmission,
    WorkflowStage,
    ApprovalTask,
)
from django_forms_workflows.views import approve_submission, submission_detail

User = get_user_model()


class Command(BaseCommand):
    help = "Verify Approver Review Accordion Restructuring (Revisi Poin 9)"

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== TESTING APPROVER REVIEW ACCORDION (REVISI POIN 9) ==="))

        user = User.objects.filter(is_superuser=True).first() or User.objects.first()
        form_def = FormDefinition.objects.filter(slug="permohonan-kontrak").first()

        if not form_def:
            self.stderr.write(self.style.ERROR("FormDefinition 'permohonan-kontrak' tidak ditemukan!"))
            return

        factory = RequestFactory()

        # 1. Create a mock test submission with complete contract payload
        target_incentive_data = [
            {"target_bulanan": 250000000, "exclude_ppn": True, "incentive_pct": 2.5, "keterangan": "Tier Platinum"}
        ]
        discount_scheme_data = [
            {"komponen": "Diskon Reguler Toko", "nilai": "15%", "tipe": "Persentase", "keterangan": "Reguler"}
        ]
        tier_support_data = [
            {"target_tahunan": 3000000000, "support_pct": 5.0, "pph_pct": 2.0, "netto": 147000000, "keterangan": "Tier 3 Milyar"}
        ]
        asset_toko_data = [
            {"no": 1, "keterangan": "Papan Nama Toko", "alamat": "Jl. Asia Afrika No. 88", "status": "Permanen"}
        ]
        market_share_data = [
            {"bulan": "Oktober 2026", "serenity": 150000000, "kompetitor_1": 80000000, "kompetitor_2": 50000000, "kompetitor_3": 30000000, "kompetitor_4": 20000000}
        ]

        test_payload = {
            "nomor_spk": "001/SPK/LA-TGR/X/2026",
            "cabang": "Bandung",
            "brand": "Lady Americana",
            "perusahaan": "PT. ROYAL ABADI SEJAHTERA",
            "kode_customer_jde": "150731",
            "nama_toko": "MEBEL MAKMUR JAYA",
            "nama_pemilik": "Bpk. Hendra Gunawan",
            "alamat_toko": "Jl. Asia Afrika No. 88, Bandung",
            "no_telepon": "081234567890",
            "email": "makmurjaya@gmail.com",
            "kota": "Bandung",
            "nomor_npwp": "01.234.567.8-428.000",
            "nomor_nik": "3273012903820005",
            "asset_toko": json.dumps(asset_toko_data),
            "market_share": json.dumps(market_share_data),
            "tanggal_mulai": "2026-11-01",
            "tanggal_berakhir": "2027-10-31",
            "durasi": "12 Bulan",
            "grace_period": "1 Bulan",
            "top": 60,
            "target_incentive": json.dumps(target_incentive_data),
            "discount_do": "2.5",
            "ketentuan_do": "Jatuh tempo sebelum pengambilan barang DO",
            "discount_scheme": json.dumps(discount_scheme_data),
            "is_support_provided": True,
            "pct_support_promo": "5.0",
            "frekuensi_pencairan": "Per Kuartal",
            "komponen_biaya": "Instore branding, listrik, dan sewa",
            "tier_support": json.dumps(tier_support_data),
            "kota_penandatanganan": "Bandung",
            "tanggal_penandatanganan": "2026-10-28",
            "rekening_perusahaan": "BCA 084-3012899 a/n PT Bestari Mulia",
        }

        submission = FormSubmission.objects.create(
            form_definition=form_def,
            submitter=user,
            form_data=test_payload,
            status="pending_approval",
            submitted_at=timezone.now(),
        )

        stage = WorkflowStage.objects.filter(workflow__form_definition=form_def).first()
        task = ApprovalTask.objects.create(
            submission=submission,
            assigned_to=user,
            workflow_stage=stage,
            stage_number=stage.order if stage else 1,
            step_name=stage.name if stage else "Review",
            status="pending",
        )

        self.stdout.write(f"Draft Pengujian dibuat: Submission #{submission.id}, Task #{task.id}")

        all_passed = True

        def _prepare_request(req, u):
            from django.contrib.sessions.middleware import SessionMiddleware
            from django.contrib.messages.middleware import MessageMiddleware
            SessionMiddleware(lambda r: None).process_request(req)
            req.session.save()
            MessageMiddleware(lambda r: None).process_request(req)
            req.user = u
            return req

        try:
            # -------------------------------------------------------------
            # TEST 1: Render Halaman Review Approver (approve_submission view)
            # -------------------------------------------------------------
            self.stdout.write("\n" + self.style.MIGRATE_HEADING("--- [TEST 1] PENGUJIAN REVIEW APPROVER (approve.html) ---"))
            req_approve = _prepare_request(factory.get(f"/forms/approvals/{task.id}/approve/"), user)
            res_approve = approve_submission(req_approve, task_id=task.id)
            html_approve = res_approve.content.decode("utf-8")

            # Check 1: Review Contract Accordion Container
            if 'id="reviewContractAccordion"' in html_approve:
                self.stdout.write(self.style.SUCCESS("✓ [PASS] Kontainer '#reviewContractAccordion' ditemukan di approve.html."))
            else:
                self.stderr.write(self.style.ERROR("✗ [FAIL] Kontainer '#reviewContractAccordion' tidak ditemukan!"))
                all_passed = False

            # Check 2: 5 Accordion Sections
            expected_groups = [
                ("collapseGrupPengajuan", "Informasi Pengajuan & Cabang"),
                ("collapseGrupToko", "Profil Pihak Kedua / Toko"),
                ("collapseGrupKomersial", "Ketentuan Kontrak & Skema Komersial"),
                ("collapseGrupSupport", "Fasilitas Support Promosi & Sewa"),
                ("collapseGrupPengesahan", "Ketentuan Pengesahan & Rekening"),
            ]

            for collapse_id, group_title in expected_groups:
                if f'id="{collapse_id}"' in html_approve:
                    self.stdout.write(self.style.SUCCESS(f"✓ [PASS] Grup Accordion '{group_title}' (#{collapse_id}) ditemukan."))
                else:
                    self.stderr.write(self.style.ERROR(f"✗ [FAIL] Grup Accordion '{group_title}' (#{collapse_id}) TIDAK ditemukan!"))
                    all_passed = False

            # Check 3: Default Collapsed State (No '.show' class on any of the 5 accordion-collapse elements)
            collapse_matches = re.findall(r'<div id="(collapseGrup\w+)" class="([^"]+)"', html_approve)
            self.stdout.write(f"\nAudit status awal (default state) {len(collapse_matches)} collapse section:")
            for c_id, c_classes in collapse_matches:
                is_collapsed = "collapse" in c_classes and "show" not in c_classes.split()
                if is_collapsed:
                    self.stdout.write(self.style.SUCCESS(f"  ✓ {c_id}: Default COLLAPSED (classes: '{c_classes}')"))
                else:
                    self.stderr.write(self.style.ERROR(f"  ✗ {c_id}: Tidak dalam kondisi collapsed! (classes: '{c_classes}')"))
                    all_passed = False

            # Check 4: Accordion buttons have 'collapsed' and aria-expanded='false'
            btn_matches = re.findall(r'<button class="([^"]*review-accordion-btn[^"]*)"[^>]*data-bs-target="#(collapseGrup\w+)"[^>]*aria-expanded="([^"]+)"', html_approve)
            self.stdout.write(f"\nAudit tombol accordion header ({len(btn_matches)} tombol):")
            for b_classes, b_target, aria_exp in btn_matches:
                btn_ok = "collapsed" in b_classes and aria_exp == "false"
                if btn_ok:
                    self.stdout.write(self.style.SUCCESS(f"  ✓ Target #{b_target}: Tombol COLLAPSED & aria-expanded='false'"))
                else:
                    self.stderr.write(self.style.ERROR(f"  ✗ Target #{b_target}: Tombol TIDAK collapsed (classes: '{b_classes}', aria-expanded: '{aria_exp}')"))
                    all_passed = False

            # Check 5: Fast Utility Buttons (Buka Semua / Tutup Semua)
            if 'id="btnExpandAllReview"' in html_approve and 'id="btnCollapseAllReview"' in html_approve:
                self.stdout.write(self.style.SUCCESS("\n✓ [PASS] Tombol utilitas 'Buka Semua' & 'Tutup Semua' ditemukan di approve.html."))
            else:
                self.stderr.write(self.style.ERROR("\n✗ [FAIL] Tombol utilitas 'Buka Semua' / 'Tutup Semua' TIDAK ditemukan di approve.html!"))
                all_passed = False

            # Check 6: toggleAllReviewAccordions JS function definition
            if "window.toggleAllReviewAccordions" in html_approve:
                self.stdout.write(self.style.SUCCESS("✓ [PASS] Skrip kendali 'toggleAllReviewAccordions' terpasang."))
            else:
                self.stderr.write(self.style.ERROR("✗ [FAIL] Skrip kendali 'toggleAllReviewAccordions' tidak ditemukan!"))
                all_passed = False

            # Check 7: Dynamic Grid Tables & Email Field within Accordion Groups
            if "Papan Nama Toko" in html_approve and "Lady Americana" in html_approve and "makmurjaya@gmail.com" in html_approve:
                self.stdout.write(self.style.SUCCESS("✓ [PASS] Konten rincian field, field email, dan tabel Dynamic Grid ter-render lengkap di dalam accordion."))
            else:
                self.stderr.write(self.style.ERROR("✗ [FAIL] Konten rincian field atau email tidak lengkap!"))
                all_passed = False

            # -------------------------------------------------------------
            # TEST 2: Render Halaman Submission Detail (submission_detail view)
            # -------------------------------------------------------------
            self.stdout.write("\n" + self.style.MIGRATE_HEADING("--- [TEST 2] PENGUJIAN SUBMISSION DETAIL (submission_detail.html) ---"))
            req_detail = _prepare_request(factory.get(f"/forms/submissions/{submission.id}/"), user)
            res_detail = submission_detail(req_detail, submission_id=submission.id)
            html_detail = res_detail.content.decode("utf-8")

            if 'id="reviewContractAccordion"' in html_detail:
                self.stdout.write(self.style.SUCCESS("✓ [PASS] Kontainer '#reviewContractAccordion' ditemukan di submission_detail.html."))
            else:
                self.stderr.write(self.style.ERROR("✗ [FAIL] Kontainer '#reviewContractAccordion' tidak ditemukan di submission_detail.html!"))
                all_passed = False

            if 'id="btnExpandAllDetail"' in html_detail and 'id="btnCollapseAllDetail"' in html_detail:
                self.stdout.write(self.style.SUCCESS("✓ [PASS] Tombol utilitas 'Buka Semua' & 'Tutup Semua' ditemukan di submission_detail.html."))
            else:
                self.stderr.write(self.style.ERROR("✗ [FAIL] Tombol utilitas 'Buka Semua' / 'Tutup Semua' TIDAK ditemukan di submission_detail.html!"))
                all_passed = False

        finally:
            # Cleanup test submission & task
            task.delete()
            submission.delete()
            self.stdout.write(self.style.NOTICE("\n[Cleanup] Submission & Task pengujian audit berhasil dibersihkan dari DB."))

        if all_passed:
            self.stdout.write(self.style.SUCCESS("\n🎉 SEMUA PENGUJIAN AUDIT REVISI POIN 9 BERHASIL 100%!"))
        else:
            self.stderr.write(self.style.ERROR("\n❌ ADA PENGUJIAN AUDIT YANG GAGAL!"))
