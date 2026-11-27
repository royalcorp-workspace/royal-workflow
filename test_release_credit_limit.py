import os
import json
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "workflow_project.settings")
django.setup()

from django.conf import settings
settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from django_forms_workflows.models import FormDefinition, FormField, FormSubmission
from django_forms_workflows.context_processors import forms_workflows
from django.test import RequestFactory

User = get_user_model()


def run_tests():
    print("=" * 70)
    print("RUNNING RELEASE CREDIT LIMIT END-TO-END TESTS")
    print("=" * 70)

    # 1. Verify FormDefinition & FormFields
    form_def = FormDefinition.objects.get(slug="release-credit-limit")
    assert form_def.category and form_def.category.slug == "sales-marketing", "Category must be sales-marketing!"
    fields = list(FormField.objects.filter(form_definition=form_def).values_list("field_name", flat=True))
    expected_fields = [
        "no_pengajuan", "cabang", "brand",
        "kode_customer_jde", "nama_customer", "nama_toko", "nama_toko_parent",
        "nama_pemilik", "email", "no_telepon", "keterangan",
        "nomor_so", "jenis_so", "total_so", "jenis_hold",
        "lampiran_dokumen",
    ]
    for ef in expected_fields:
        assert ef in fields, f"Missing FormField: {ef}"
    print(f"✓ FormDefinition '{form_def.name}' seeded with {len(fields)} fields under '{form_def.category.name}'.")

    # 2. Verify Sidebar Visibility alongside Kontrak Toko using existing dummy.02
    u_sales = User.objects.get(username="dummy.02")

    rf = RequestFactory()
    req = rf.get("/")
    req.user = u_sales
    ctx = forms_workflows(req)
    sales_cat = [c for c in ctx["sidebar_categories"] if c["category_name"] == "Sales & Marketing"]
    assert sales_cat, "Sales & Marketing category missing in sidebar!"
    slugs = [f["slug"] for f in sales_cat[0]["forms"]]
    assert "permohonan-kontrak" in slugs and "release-credit-limit" in slugs, f"Expected both forms in sidebar, got {slugs}"
    print(f"✓ Sidebar 'Sales & Marketing' contains: {slugs}")

    # 3. Test Hub, Form Page, Save Draft, Submit, and Detail Page via Django Test Client
    client = Client()
    client.force_login(u_sales)

    resp_hub = client.get("/forms/release-credit-limit/")
    assert resp_hub.status_code == 200, f"Hub returned {resp_hub.status_code}"
    assert "Release Credit Limit" in resp_hub.content.decode("utf-8")
    print("✓ Hub /forms/release-credit-limit/ returned 200 OK.")

    resp_get = client.get("/forms/release-credit-limit/submit/")
    assert resp_get.status_code == 200, f"Submit GET returned {resp_get.status_code}"
    html_get = resp_get.content.decode("utf-8")
    assert "Form Pengajuan Release Credit Limit" in html_get
    assert "release-credit-limit-widget.js?v=20261125_rcl_v11" in html_get, "Missing ?v=20261125_rcl_v11 script tag!"
    assert "Terdapat Fasilitas" not in html_get, "Terdapat Fasilitas toggle leaked!"
    for ef in expected_fields:
        assert f'name="{ef}"' in html_get, f"Missing input name='{ef}' in form HTML!"
    for btn_txt in ["Kembali", "Simpan Draft", "Submit Pengajuan"]:
        assert btn_txt in html_get, f"Missing footer button '{btn_txt}'!"
    import pathlib
    kg_js = pathlib.Path("/app/staticfiles/django_forms_workflows/js/kontrak-grid-widget.js").read_text(encoding="utf-8")
    assert "formSlug !== 'permohonan-kontrak'" in kg_js, "Missing formSlug isolation guard in staticfiles kontrak-grid-widget.js!"
    rcl_js = pathlib.Path("/app/staticfiles/django_forms_workflows/js/release-credit-limit-widget.js").read_text(encoding="utf-8")
    assert "getFieldInput" in rcl_js, "Missing getFieldInput in staticfiles release-credit-limit-widget.js!"
    print("✓ Form page /forms/release-credit-limit/submit/ rendered 200 OK with all 16 inputs, 3 footer buttons, and 0 Kontrak Toko leaks.")

    # Save Draft with attachment
    draft_file = SimpleUploadedFile("draft_lampiran.pdf", b"%PDF-1.4 draft", content_type="application/pdf")
    resp_draft = client.post(
        "/forms/release-credit-limit/submit/",
        data={
            "action": "draft",
            "cabang": "Pusat",
            "brand": "Lady Americana",
            "kode_customer_jde": "100200",
            "nama_toko": "Toko Draft RCL",
            "lampiran_dokumen": json.dumps([{"index": 0, "nama_lampiran": "Lampiran Draft"}]),
            "rcl_lampiran_file_0": draft_file,
        },
        follow=False,
    )
    assert resp_draft.status_code in (200, 302), f"Draft POST returned {resp_draft.status_code}"
    draft_sub = FormSubmission.objects.filter(form_definition=form_def, submitter=u_sales, status="draft").last()
    assert draft_sub is not None, "Draft submission was not created!"
    assert not draft_sub.form_data.get("no_pengajuan"), f"Draft should NOT have no_pengajuan, got {draft_sub.form_data.get('no_pengajuan')}"
    assert len(draft_sub.form_data.get("lampiran_dokumen") or []) == 1, "Draft attachment not saved!"
    print(f"✓ Draft saved successfully (ID #{draft_sub.id}, no_pengajuan='', attachment saved).")

    # Hub should show Draf Otomatis + Lanjutkan + Ajukan Release Credit Limit
    resp_hub_draft = client.get("/forms/release-credit-limit/")
    hub_html = resp_hub_draft.content.decode("utf-8")
    assert "Ajukan Release Credit Limit" in hub_html
    assert "Draf Otomatis" in hub_html
    assert "Lanjutkan" in hub_html
    print("✓ Hub displays 'Ajukan Release Credit Limit', 'Draf Otomatis', and 'Lanjutkan'.")

    # Resume Draft (?draft=<id>)
    resp_resume = client.get(f"/forms/release-credit-limit/submit/?draft={draft_sub.id}")
    assert resp_resume.status_code == 200
    resume_html = resp_resume.content.decode("utf-8")
    assert "Toko Draft RCL" in resume_html
    assert "active_server_draft_data" in resume_html
    assert "Lampiran Draft" in resume_html
    print(f"✓ Resume Draft (?draft={draft_sub.id}) restored fields and attachment JSON.")

    # Discard Draft via AJAX
    resp_discard = client.post(
        f"/forms/submissions/{draft_sub.id}/discard/",
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    assert resp_discard.status_code == 200
    assert not FormSubmission.objects.filter(id=draft_sub.id).exists()
    print(f"✓ Draft #{draft_sub.id} discarded cleanly via AJAX.")

    # Submit Application #1 (Pusat / Lady Americana -> 001/CL-RAS/PUSAT/LADY/...)
    uploaded = SimpleUploadedFile("po_customer.pdf", b"%PDF-1.4 dummy content", content_type="application/pdf")
    resp_submit_1 = client.post(
        "/forms/release-credit-limit/submit/",
        data={
            "action": "submit",
            "cabang": "Pusat",
            "brand": "Lady Americana",
            "kode_customer_jde": "100200",
            "nama_customer": "PT Toko Uji",
            "nama_toko": "Toko Uji Mandiri",
            "nama_toko_parent": "Group Mandiri",
            "nama_pemilik": "Budi Santoso",
            "email": "budi@tokouji.com",
            "no_telepon": "081234567890",
            "keterangan": "Mohon release CL untuk SO urgent.",
            "nomor_so": "SO-2026-00991",
            "jenis_so": "SO",
            "total_so": "15.750.000",
            "jenis_hold": "C1 + C2",
            "lampiran_dokumen": json.dumps([{"index": 0, "nama_lampiran": "PO Customer"}]),
            "rcl_lampiran_file_0": uploaded,
        },
        follow=False,
    )
    assert resp_submit_1.status_code == 302, f"Submit #1 expected 302 redirect, got {resp_submit_1.status_code}"
    sub_1 = FormSubmission.objects.filter(form_definition=form_def, submitter=u_sales).exclude(status="draft").order_by("id").last()
    assert sub_1 is not None
    fd1 = sub_1.form_data
    no1 = str(fd1.get("no_pengajuan") or "")
    assert "/CL-" in no1 and "/PUSAT/LADY/" in no1, f"Expected format .../CL-.../PUSAT/LADY/..., got {no1}"
    assert no1.startswith("001/"), f"Expected 001/ prefix, got {no1}"
    assert fd1.get("total_so") == "15750000"
    assert len(fd1.get("lampiran_dokumen") or []) == 1
    print(f"✓ Submit #1 succeeded: No. {no1}, Total SO={fd1['total_so']}, Lampiran={fd1['lampiran_dokumen'][0]['filename']}")

    # Submit Application #2 (same Cabang/Brand -> increments to 002/CL-RAS/PUSAT/LADY/...)
    resp_submit_2 = client.post(
        "/forms/release-credit-limit/submit/",
        data={
            "action": "submit",
            "cabang": "Pusat",
            "brand": "Lady Americana",
            "kode_customer_jde": "100201",
            "nama_toko": "Toko Uji Kedua",
            "nomor_so": "SO-2026-00992",
            "jenis_so": "ZO",
            "total_so": "5.000.000",
            "jenis_hold": "C1",
            "lampiran_dokumen": "[]",
        },
        follow=False,
    )
    assert resp_submit_2.status_code == 302
    sub_2 = FormSubmission.objects.filter(form_definition=form_def, submitter=u_sales).exclude(status="draft").order_by("id").last()
    no2 = str((sub_2.form_data or {}).get("no_pengajuan") or "")
    assert no2.startswith("002/CL-") and "/PUSAT/LADY/" in no2, f"Expected increment 002/CL-.../PUSAT/LADY/..., got {no2}"
    print(f"✓ Submit #2 incremented cleanly: No. {no2}")

    # Check Submission Detail Page
    resp_det = client.get(f"/forms/submissions/{sub_1.id}/")
    assert resp_det.status_code == 200, f"Detail page returned {resp_det.status_code}"
    html_det = resp_det.content.decode("utf-8")
    assert no1 in html_det
    assert "SO-2026-00991" in html_det
    assert "PO Customer" in html_det
    print(f"✓ Detail page /forms/submissions/{sub_1.id}/ rendered 200 OK with all 4 sections & attachment.")

    # Check JDE Customer Lookup endpoint (/api/lookup/jde-customer/?code=100228)
    resp_jde = client.get("/api/lookup/jde-customer/?code=100228")
    assert resp_jde.status_code == 200, f"JDE lookup returned {resp_jde.status_code}: {resp_jde.content}"
    jde_json = json.loads(resp_jde.content.decode("utf-8"))
    assert jde_json.get("success") is True and jde_json.get("customer"), f"Unexpected JDE payload: {jde_json}"
    cust = jde_json["customer"]
    for key in ["nama_customer", "nama_toko", "nama_toko_parent", "nama_pemilik", "email", "no_telepon"]:
        assert key in cust, f"Missing key '{key}' in JDE customer payload!"
    print(f"✓ JDE lookup (100228) returned 200 OK: nama_toko='{cust['nama_toko']}', nama_customer='{cust['nama_customer']}', parent='{cust['nama_toko_parent']}'.")

    # Check Live Preview No Pengajuan endpoint (/forms/release-credit-limit/next-spk-number/)
    resp_next_cl = client.get("/forms/release-credit-limit/next-spk-number/?cabang=Pusat&brand=Lady+Americana")
    assert resp_next_cl.status_code == 200, f"next-spk-number returned {resp_next_cl.status_code}"
    next_cl_json = json.loads(resp_next_cl.content.decode("utf-8"))
    assert next_cl_json.get("success") is True
    assert str(next_cl_json.get("nomor_spk", "")).startswith("003/CL-") and "/PUSAT/LADY/" in str(next_cl_json.get("nomor_spk", "")), (
        f"Expected 003/CL-.../PUSAT/LADY/..., got {next_cl_json}"
    )
    print(f"✓ Live Preview CL number endpoint returned: {next_cl_json['nomor_spk']}")

    resp_elite_cl = client.get("/forms/release-credit-limit/next-spk-number/?cabang=Pusat&brand=Elite+Springbed")
    assert resp_elite_cl.status_code == 200
    elite_json = json.loads(resp_elite_cl.content.decode("utf-8"))
    assert "/CL-" in elite_json.get("nomor_spk", "") and "/PUSAT/ELITE/" in elite_json.get("nomor_spk", ""), (
        f"Expected .../CL-.../PUSAT/ELITE/..., got {elite_json}"
    )
    print(f"✓ Live Preview Elite Springbed CL number returned: {elite_json['nomor_spk']}")

    resp_serenity_cl = client.get("/forms/release-credit-limit/next-spk-number/?cabang=Pusat&brand=Serenity")
    assert resp_serenity_cl.status_code == 200
    serenity_json = json.loads(resp_serenity_cl.content.decode("utf-8"))
    assert "/CL-" in serenity_json.get("nomor_spk", "") and "/PUSAT/SERENITY/" in serenity_json.get("nomor_spk", ""), (
        f"Expected .../CL-.../PUSAT/SERENITY/..., got {serenity_json}"
    )
    print(f"✓ Live Preview Serenity CL number returned: {serenity_json['nomor_spk']}")

    rcl_js = pathlib.Path("/app/staticfiles/django_forms_workflows/js/release-credit-limit-widget.js").read_text(encoding="utf-8")
    for token in ["jde-lookup-wrap", "jde-lookup-btn", "refreshClNumberPreview", "getControlValue", "MutationObserver", "next-spk-number", "AbortController", "nama_toko_parent", "formatIndonesianMobile", "lookupBtn.addEventListener('click'", "jdeInput.addEventListener('keydown'"]:
        assert token in rcl_js, f"Missing '{token}' in staticfiles release-credit-limit-widget.js!"
    assert "jdeInput.addEventListener('blur'" not in rcl_js, "Unexpected blur auto-lookup in release-credit-limit-widget.js!"
    assert "jdeInput.addEventListener('input'" not in rcl_js, "Unexpected input auto-lookup in release-credit-limit-widget.js!"
    print("✓ staticfiles release-credit-limit-widget.js verified (CL preview, JDE button/Enter only, AbortController, 6-field mapping).")

    # ==================================================================
    # WORKFLOW MATRIX & E2E APPROVAL TESTS (C1, C2, C1+C2)
    # ==================================================================
    from django_forms_workflows.services.release_credit_limit_workflow import (
        evaluate_rcl_approval_matrix,
        get_allowed_jenis_produk_for_jenis_so,
        get_pending_rcl_task,
    )
    from django_forms_workflows.models import WorkflowDefinition

    # 1. Unit assertions for Jenis SO -> Jenis Produk mapping & matrix rules
    assert get_allowed_jenis_produk_for_jenis_so("ZO") == ["Mattress", "Non Woven"]
    assert get_allowed_jenis_produk_for_jenis_so("SG") == ["Mattress", "Foam", "Non Woven"]
    assert get_allowed_jenis_produk_for_jenis_so("S5") == ["Foam", "Non Woven"]
    assert get_allowed_jenis_produk_for_jenis_so("S6") == ["Foam", "Non Woven"]
    assert get_allowed_jenis_produk_for_jenis_so("SO") == ["Mattress", "Foam", "Non Woven"]
    assert evaluate_rcl_approval_matrix({"jenis_hold": "C1", "brand": "Elite Springbed", "acc_jenis_produk": "Foam", "total_so": 30000000, "acc_rata_rata_omzet": 0})["target_final_level"] == "ASM"
    assert evaluate_rcl_approval_matrix({"jenis_hold": "C1", "brand": "Elite Springbed", "acc_jenis_produk": "Non Woven", "total_so": 50000000, "acc_rata_rata_omzet": 0})["target_final_level"] == "NSM"
    assert evaluate_rcl_approval_matrix({"jenis_hold": "C1", "brand": "Royal Foam", "acc_jenis_produk": "Mattress", "total_so": 8000000, "acc_rata_rata_omzet": 20000000})["target_final_level"] == "NSM"
    assert evaluate_rcl_approval_matrix({"jenis_hold": "C1", "brand": "Royal Foam", "acc_jenis_produk": "Mattress", "total_so": 15000000, "acc_rata_rata_omzet": 20000000})["target_final_level"] == "GM"
    assert evaluate_rcl_approval_matrix({"jenis_hold": "C2", "brand": "Royal Foam", "total_so": 1000000, "acc_rata_rata_omzet": 999000000})["target_final_level"] == "GM"
    assert evaluate_rcl_approval_matrix({"jenis_hold": "C1 + C2", "brand": "Serenity", "total_so": 1000000, "acc_rata_rata_omzet": 999000000})["target_final_level"] == "GM"
    assert evaluate_rcl_approval_matrix({"jenis_hold": "C1", "brand": "Royal Foam", "total_so": 30000000, "acc_rata_rata_omzet": 0})["target_final_level"] == "ASM"
    assert evaluate_rcl_approval_matrix({"jenis_hold": "C1", "brand": "Classic", "total_so": 50000000, "acc_rata_rata_omzet": 0})["target_final_level"] == "NSM"
    assert evaluate_rcl_approval_matrix({"jenis_hold": "C1", "brand": "Royal Foam", "total_so": 100000000, "acc_rata_rata_omzet": 0})["target_final_level"] == "GM"
    assert evaluate_rcl_approval_matrix({"jenis_hold": "C1", "brand": "Lady Americana", "total_so": 5000000, "acc_rata_rata_omzet": 20000000})["target_final_level"] == "ASM"
    assert evaluate_rcl_approval_matrix({"jenis_hold": "C1", "brand": "Lady Americana", "total_so": 10000000, "acc_rata_rata_omzet": 30000000})["target_final_level"] == "NSM"
    assert evaluate_rcl_approval_matrix({"jenis_hold": "C1", "brand": "Lady Americana", "total_so": 10000001, "acc_rata_rata_omzet": 30000000})["target_final_level"] == "GM"
    assert evaluate_rcl_approval_matrix({"jenis_hold": "C1", "brand": "Elite Springbed", "total_so": 5000000, "acc_rata_rata_omzet": 40000000})["target_final_level"] == "ASM"
    assert evaluate_rcl_approval_matrix({"jenis_hold": "C1", "brand": "Elite Springbed", "total_so": 8000000, "acc_rata_rata_omzet": 40000000})["target_final_level"] == "NSM"
    assert evaluate_rcl_approval_matrix({"jenis_hold": "C1", "brand": "Elite Springbed", "total_so": 10000000, "acc_rata_rata_omzet": 40000000})["target_final_level"] == "NSM"
    assert evaluate_rcl_approval_matrix({"jenis_hold": "C1", "brand": "Elite Springbed", "total_so": 10000001, "acc_rata_rata_omzet": 40000000})["target_final_level"] == "GM"
    assert evaluate_rcl_approval_matrix({"jenis_hold": "C1", "brand": "Serenity", "total_so": 25000000, "acc_rata_rata_omzet": 50000000})["target_final_level"] == "ASM"
    assert evaluate_rcl_approval_matrix({"jenis_hold": "C1", "brand": "Serenity", "total_so": 50000000, "acc_rata_rata_omzet": 50000000})["target_final_level"] == "NSM"
    assert evaluate_rcl_approval_matrix({"jenis_hold": "C1", "brand": "Serenity", "total_so": 75000000, "acc_rata_rata_omzet": 50000000})["target_final_level"] == "GM"
    print("✓ All C1 / C2 / C1+C2 matrix unit assertions passed.")

    # Evaluate-matrix endpoint check
    resp_mat = client.get("/forms/release-credit-limit/evaluate-matrix/?jenis_hold=C1&brand=Classic&total_so=50000000&rata_rata_omzet=10000000")
    assert resp_mat.status_code == 200 and json.loads(resp_mat.content.decode())["target_final_level"] == "NSM"
    print("✓ Live evaluate-matrix endpoint returned 200 OK (NSM).")

    wf = WorkflowDefinition.objects.get(form_definition=form_def)
    stages = list(wf.stages.order_by("order"))
    assert [s.order for s in stages] == [1, 2, 3, 4], f"Unexpected stage orders: {stages}"
    print("✓ WorkflowDefinition 4 stages verified: Accounting Cabang -> ASM/BM -> NSM -> GM.")

    # Load branch-appropriate local dummy actors (dummy.01 - dummy.07 only)
    from django_forms_workflows.services.release_credit_limit_workflow import user_can_act_on_rcl_task

    u_submitter_bali = User.objects.get(username="dummy.01")
    u_submitter_pusat = User.objects.get(username="dummy.02")
    u_acc_pusat = User.objects.get(username="dummy.06")
    u_asm_pusat = User.objects.get(username="dummy.03")
    u_nsm = User.objects.get(username="dummy.04")
    u_gm = User.objects.get(username="dummy.07")

    created_subs = []

    def submit_rcl(brand, total_so_str, jenis_hold, so_no, cabang="Pusat", actor=None):
        submitter = actor or u_submitter_pusat
        c = Client()
        c.force_login(submitter)
        r = c.post(
            "/forms/release-credit-limit/submit/",
            data={
                "action": "submit",
                "cabang": cabang,
                "brand": brand,
                "kode_customer_jde": "100228",
                "nama_customer": "VERONICA SHERLY BERATA",
                "nama_toko": "VERONICA SHERLY BERATA",
                "nomor_so": so_no,
                "jenis_so": "SO",
                "total_so": total_so_str,
                "jenis_hold": jenis_hold,
                "lampiran_dokumen": "[]",
            },
            follow=False,
        )
        assert r.status_code == 302
        s = FormSubmission.objects.filter(form_definition=form_def, submitter=submitter).exclude(status="draft").order_by("id").last()
        created_subs.append(s)
        return s

    # CASE A: C1 Non-Foam (Serenity), SO=20Jt, Omzet=60Jt -> Stops at ASM
    sub_a = submit_rcl("Serenity", "20.000.000", "C1", "SO-E2E-ASM-01")
    t_a1 = get_pending_rcl_task(sub_a)
    assert t_a1 and t_a1.workflow_stage.order == 1

    # Branch isolation: Pusat Accounting (dummy.06) cannot act on Bali submission
    sub_bali = submit_rcl("Serenity", "10.000.000", "C1", "SO-E2E-BALI-01", cabang="Bali", actor=u_submitter_bali)
    t_bali1 = get_pending_rcl_task(sub_bali)
    assert t_bali1 and not user_can_act_on_rcl_task(u_acc_pusat, sub_bali, t_bali1), "Pusat Accounting must NOT act on Bali submission!"
    c_acc = Client()
    c_acc.force_login(u_acc_pusat)
    c_acc.post(
        f"/forms/release-credit-limit/review/{sub_bali.id}/",
        data={"decision": "save_accounting_draft", "acc_plafon_saat_ini": "99.000.000"},
    )
    sub_bali.refresh_from_db()
    assert (sub_bali.form_data or {}).get("acc_plafon_saat_ini") is None, "Branch isolation breach on POST!"

    # Accounting Pusat UI check & Save Draft
    c_acc = Client()
    c_acc.force_login(u_acc_pusat)
    r_acc_get = c_acc.get(f"/forms/submissions/{sub_a.id}/")
    assert r_acc_get.status_code == 200
    h_acc = r_acc_get.content.decode("utf-8")
    for expected_txt in [
        "Review Pengajuan Release Credit Limit",
        "Mode detail dibuka: seluruh data Sales Counter dapat diperiksa tanpa mengubahnya.",
        "Ringkasan Pengajuan",
        "Data Pengajuan Sales Counter",
        "Input Informasi Credit Accounting Cabang",
        "Detail Sales Counter tidak dapat diedit oleh Accounting Cabang.",
        "Simpan Draft",
        "Kembalikan Revisi",
        "Setujui &amp; Lanjutkan",
        'name="acc_plafon_saat_ini"',
        'name="acc_rata_rata_omzet"',
    ]:
        assert expected_txt in h_acc, f"Accounting review UI missing: {expected_txt}"

    c_acc.post(
        f"/forms/release-credit-limit/review/{sub_a.id}/",
        data={
            "decision": "save_accounting_draft",
            "acc_plafon_saat_ini": "50.000.000",
            "acc_rata_rata_omzet": "60.000.000",
        },
    )
    sub_a.refresh_from_db()
    assert (sub_a.form_data or {}).get("acc_plafon_saat_ini") == 50000000
    assert get_pending_rcl_task(sub_a).workflow_stage.order == 1

    # Accounting Approve -> advances to Stage 2 (ASM), target_final_level == ASM
    c_acc.post(
        f"/forms/release-credit-limit/review/{sub_a.id}/",
        data={
            "decision": "approve_accounting",
            "acc_plafon_saat_ini": "50.000.000",
            "acc_total_over_credit": "15.000.000",
            "acc_open_order_amount": "20.000.000",
            "acc_over_due": "0",
            "acc_rata_rata_omzet": "60.000.000",
            "comments": "Data JDE valid",
        },
    )
    sub_a.refresh_from_db()
    assert sub_a.form_data.get("rcl_target_final_level") == "ASM"
    t_a2 = get_pending_rcl_task(sub_a)
    assert t_a2 and t_a2.workflow_stage.order == 2

    # ASM & Pemohon see Read-Only Card 01 (no editable acc inputs!)
    c_asm = Client()
    c_asm.force_login(u_asm_pusat)
    h_asm = c_asm.get(f"/forms/submissions/{sub_a.id}/").content.decode("utf-8")
    assert "Informasi Credit Accounting Cabang" in h_asm
    assert 'name="acc_plafon_saat_ini"' not in h_asm, "ASM must NOT see editable Accounting inputs!"
    assert "Target Approver Akhir: ASM / BM" in h_asm
    assert "Kembalikan Revisi" in h_asm and "Setujui" in h_asm

    c_pem = Client()
    c_pem.force_login(u_submitter_pusat)
    h_pem = c_pem.get(f"/forms/submissions/{sub_a.id}/").content.decode("utf-8")
    assert "Informasi Credit Accounting Cabang" in h_pem
    assert 'name="acc_plafon_saat_ini"' not in h_pem
    assert "Rp 60.000.000" in h_pem

    # ASM Approves -> directly approved (NSM & GM skipped!)
    c_asm.post(f"/forms/release-credit-limit/review/{sub_a.id}/", data={"decision": "approve", "comments": "OK ASM"})
    sub_a.refresh_from_db()
    assert sub_a.status == "approved", f"Expected approved after ASM, got {sub_a.status}"
    assert get_pending_rcl_task(sub_a) is None
    print("✓ Case A passed: C1 Non-Foam stopped at ASM & read-only Accounting card visible to ASM + Pemohon.")

    # CASE B: C1 Foam (Classic), SO=50Jt -> Stops at NSM
    sub_b = submit_rcl("Classic", "50.000.000", "C1", "SO-E2E-NSM-01")
    c_acc.post(
        f"/forms/release-credit-limit/review/{sub_b.id}/",
        data={
            "decision": "approve_accounting",
            "acc_plafon_saat_ini": "40.000.000",
            "acc_total_over_credit": "10.000.000",
            "acc_open_order_amount": "50.000.000",
            "acc_over_due": "0",
            "acc_rata_rata_omzet": "10.000.000",
        },
    )
    sub_b.refresh_from_db()
    assert sub_b.form_data.get("rcl_target_final_level") == "NSM"
    c_asm.post(f"/forms/release-credit-limit/review/{sub_b.id}/", data={"decision": "approve", "comments": "Lanjut NSM"})
    sub_b.refresh_from_db()
    assert get_pending_rcl_task(sub_b).workflow_stage.order == 3

    c_nsm = Client()
    c_nsm.force_login(u_nsm)
    h_nsm = c_nsm.get(f"/forms/submissions/{sub_b.id}/").content.decode("utf-8")
    assert 'name="acc_plafon_saat_ini"' not in h_nsm
    assert "Target Approver Akhir: NSM" in h_nsm
    c_nsm.post(f"/forms/release-credit-limit/review/{sub_b.id}/", data={"decision": "approve", "comments": "OK NSM"})
    sub_b.refresh_from_db()
    assert sub_b.status == "approved", f"Expected approved after NSM, got {sub_b.status}"
    print("✓ Case B passed: C1 Foam (Classic 50Jt) went Accounting -> ASM -> NSM -> Approved (GM skipped).")

    # CASE C: C2 TOP Hold -> Full chain to GM
    sub_c = submit_rcl("Elite Springbed", "2.000.000", "C2", "SO-E2E-GM-01")
    c_acc.post(
        f"/forms/release-credit-limit/review/{sub_c.id}/",
        data={
            "decision": "approve_accounting",
            "acc_plafon_saat_ini": "100.000.000",
            "acc_total_over_credit": "0",
            "acc_open_order_amount": "2.000.000",
            "acc_over_due": "5.000.000",
            "acc_rata_rata_omzet": "80.000.000",
        },
    )
    sub_c.refresh_from_db()
    assert sub_c.form_data.get("rcl_target_final_level") == "GM"
    c_asm.post(f"/forms/release-credit-limit/review/{sub_c.id}/", data={"decision": "approve"})
    c_nsm.post(f"/forms/release-credit-limit/review/{sub_c.id}/", data={"decision": "approve"})
    sub_c.refresh_from_db()
    assert get_pending_rcl_task(sub_c).workflow_stage.order == 4

    c_gm = Client()
    c_gm.force_login(u_gm)
    h_gm = c_gm.get(f"/forms/submissions/{sub_c.id}/").content.decode("utf-8")
    assert 'name="acc_plafon_saat_ini"' not in h_gm
    assert "Target Approver Akhir: GM" in h_gm
    c_gm.post(f"/forms/release-credit-limit/review/{sub_c.id}/", data={"decision": "approve", "comments": "OK GM"})
    sub_c.refresh_from_db()
    assert sub_c.status == "approved"
    print("✓ Case C passed: C2 (TOP Hold) completed full chain Accounting -> ASM -> NSM -> GM -> Approved.")

    # CASE D: Revision Cycle (Kembalikan Revisi -> Pemohon Resubmit -> Stage 1 Accounting)
    sub_d = submit_rcl("Lady Americana", "12.000.000", "C1 + C2", "SO-E2E-REV-01")
    c_acc.post(
        f"/forms/release-credit-limit/review/{sub_d.id}/",
        data={"decision": "request_revision", "revision_reason": "Mohon lampirkan PO terbaru yang sudah ditandatangani."},
    )
    sub_d.refresh_from_db()
    assert sub_d.status == "needs_revision"
    c_pem.post(
        f"/forms/release-credit-limit/submit/?revision={sub_d.id}",
        data={
            "action": "submit",
            "revision_id": str(sub_d.id),
            "cabang": "Pusat",
            "brand": "Lady Americana",
            "kode_customer_jde": "100228",
            "nama_customer": "VERONICA SHERLY BERATA",
            "nama_toko": "VERONICA SHERLY BERATA",
            "nomor_so": "SO-E2E-REV-01-R1",
            "jenis_so": "SO",
            "total_so": "12.000.000",
            "jenis_hold": "C1 + C2",
            "lampiran_dokumen": "[]",
        },
        follow=False,
    )
    sub_d.refresh_from_db()
    assert sub_d.status == "pending_approval"
    assert get_pending_rcl_task(sub_d).workflow_stage.order == 1
    print("✓ Case D passed: Kembalikan Revisi -> Pemohon resubmit -> Stage 1 Accounting Cabang reopened.")

    # Cleanup test submissions
    sub_1.delete()
    sub_2.delete()
    for s in created_subs:
        s.delete()

    print("\n" + "=" * 70)
    print("ALL RELEASE CREDIT LIMIT TESTS PASSED! (100%)")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
