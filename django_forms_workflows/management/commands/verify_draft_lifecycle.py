import json
from django.core.management.base import BaseCommand
from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django_forms_workflows.models import FormDefinition, FormSubmission
from django_forms_workflows.views import form_auto_save, discard_draft

User = get_user_model()

class Command(BaseCommand):
    help = "Verify Draft Lifecycle: Lazy creation, substantive check, and discard draft"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("=== TESTING DRAFT LIFECYCLE ==="))
        
        user = User.objects.filter(is_superuser=True).first() or User.objects.first()
        self.stdout.write(f"Using test user: {user.username}")
        
        form_def = FormDefinition.objects.get(slug="permohonan-kontrak")
        factory = RequestFactory()

        # Clean up any existing test drafts for this user first
        FormSubmission.objects.filter(form_definition=form_def, submitter=user, status="draft").delete()

        # TEST 1: Blank / Default-only Form Auto-Save (Lazy Creation Guard)
        self.stdout.write("\n[TEST 1] Testing Auto-save with default/empty data...")
        default_payload = {
            "brand": "LADY AMERICANA",
            "cabang": "Tangerang",
            "durasi": "12 Bulan",
            "jenis_pajak": "Exclude PPN",
            "rekening_perusahaan": "123-456-789",
            "target_omset_toko": "[]",
            "skema_incentive": "[]",
            "support_facility": "[]",
            "cabang_toko_alamat": '[{"no":1,"keterangan":"","alamat":"","status":"Pribadi"}]',
        }
        
        req1 = factory.post(
            "/forms/permohonan-kontrak/auto-save/",
            data=json.dumps(default_payload),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        req1.user = user
        res1 = form_auto_save(req1, slug="permohonan-kontrak")
        res1_json = json.loads(res1.content.decode("utf-8"))
        
        drafts_count_1 = FormSubmission.objects.filter(form_definition=form_def, submitter=user, status="draft").count()
        self.stdout.write(f"Response: {res1_json}")
        self.stdout.write(f"Drafts in DB: {drafts_count_1}")
        
        assert res1_json.get("ignored") is True, "Expected ignored: True on empty/default data!"
        assert res1_json.get("draft_id") is None, "Expected draft_id to be None on empty/default data!"
        assert drafts_count_1 == 0, "No draft row should be created in DB for blank form!"
        self.stdout.write(self.style.SUCCESS("✓ TEST 1 PASSED: Lazy Creation successfully prevented junk draft!"))

        # TEST 2: Substantive Data Auto-Save (Draft Creation)
        self.stdout.write("\n[TEST 2] Testing Auto-save with substantive customer data...")
        substantive_payload = {
            **default_payload,
            "kode_customer_jde": "CUST-9999",
            "nama_toko": "TOKO MEKAR ABADI TEST",
            "nama_pemilik": "BAPAK BUDI",
        }
        req2 = factory.post(
            "/forms/permohonan-kontrak/auto-save/",
            data=json.dumps(substantive_payload),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        req2.user = user
        res2 = form_auto_save(req2, slug="permohonan-kontrak")
        res2_json = json.loads(res2.content.decode("utf-8"))
        
        drafts_count_2 = FormSubmission.objects.filter(form_definition=form_def, submitter=user, status="draft").count()
        created_draft = FormSubmission.objects.filter(form_definition=form_def, submitter=user, status="draft").first()
        self.stdout.write(f"Response: {res2_json}")
        self.stdout.write(f"Drafts in DB: {drafts_count_2}")
        
        assert res2_json.get("success") is True, "Expected success: True"
        assert res2_json.get("draft_id") is not None, "Expected valid draft_id"
        assert drafts_count_2 == 1, "Exactly 1 draft should exist in DB"
        assert created_draft.form_data.get("nama_toko") == "TOKO MEKAR ABADI TEST"
        self.stdout.write(self.style.SUCCESS(f"✓ TEST 2 PASSED: Draft {created_draft.id} successfully created when substantive data filled!"))

        # TEST 3: Discard Draft via AJAX (Hapus Draf)
        self.stdout.write("\n[TEST 3] Testing Discard Draft endpoint via AJAX...")
        draft_id = created_draft.id
        req3 = factory.post(
            f"/forms/submissions/{draft_id}/discard/",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        req3.user = user
        res3 = discard_draft(req3, submission_id=draft_id)
        res3_json = json.loads(res3.content.decode("utf-8"))
        
        drafts_count_3 = FormSubmission.objects.filter(id=draft_id).count()
        self.stdout.write(f"Response: {res3_json}")
        self.stdout.write(f"Drafts with ID {draft_id} in DB: {drafts_count_3}")
        
        assert res3_json.get("success") is True, "Expected success: True on discard"
        assert drafts_count_3 == 0, "Draft row should be permanently removed from DB"
        self.stdout.write(self.style.SUCCESS("✓ TEST 3 PASSED: Discard Draft permanently removed draft row from DB!"))

        self.stdout.write(self.style.SUCCESS("\n🎉 ALL DRAFT LIFECYCLE TESTS PASSED PERFECTLY!"))
