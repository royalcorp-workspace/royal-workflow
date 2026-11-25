import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "workflow_project.settings")
django.setup()

import json
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import RequestFactory
from django_forms_workflows.models import (
    FormDefinition,
    FormSubmission,
    WorkflowDefinition,
    WorkflowStage,
    ApprovalTask,
    ContractSigningToken,
)
from django_forms_workflows.views import (
    approval_inbox_ajax,
    completed_approvals_ajax,
    form_submission_hub,
)
from django_forms_workflows.context_processors import forms_workflows
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.messages.middleware import MessageMiddleware

User = get_user_model()
rf = RequestFactory()

def setup_request(req, user):
    req.user = user
    SessionMiddleware(lambda r: None).process_request(req)
    MessageMiddleware(lambda r: None).process_request(req)
    req.session.save()
    return req

def run_tests():
    print("=" * 60)
    print("RUNNING SEARCH & STAGE FILTER & SIDEBAR TESTS")
    print("=" * 60)

    # 1. Setup Form and Groups
    form_def = FormDefinition.objects.filter(slug="permohonan-kontrak").first()
    assert form_def is not None, "FormDefinition permohonan-kontrak not found!"

    grp_asm, _ = Group.objects.get_or_create(name="Area Sales Manager (L1)")
    grp_support, _ = Group.objects.get_or_create(name="Sales Support")
    grp_rsom, _ = Group.objects.get_or_create(name="Regional Sales Operation Manager (L2)")
    grp_direksi, _ = Group.objects.get_or_create(name="Direksi")
    grp_sales, _ = Group.objects.get_or_create(name="Promotor")

    # Ensure reviewer groups includes Sales Support
    form_def.reviewer_groups.add(grp_support)

    # Users
    u_admin, _ = User.objects.get_or_create(username="test_admin_sf", defaults={"is_superuser": True, "is_staff": True})
    u_asm, _ = User.objects.get_or_create(username="test_asm_sf", defaults={"first_name": "Buddy", "last_name": "ASM"})
    u_asm.groups.add(grp_asm)
    u_support, _ = User.objects.get_or_create(username="test_support_sf", defaults={"first_name": "Chandra", "last_name": "Support"})
    u_support.groups.add(grp_support)
    u_rsom, _ = User.objects.get_or_create(username="test_rsom_sf", defaults={"first_name": "David", "last_name": "RSOM"})
    u_rsom.groups.add(grp_rsom)
    u_direksi, _ = User.objects.get_or_create(username="test_direksi_sf", defaults={"first_name": "Edward", "last_name": "Direktur"})
    u_direksi.groups.add(grp_direksi)
    u_sales, _ = User.objects.get_or_create(username="test_sales_sf", defaults={"first_name": "Ferry", "last_name": "Sales"})
    u_sales.groups.add(grp_sales)

    # 2. Test Context Processor Sidebar Visibility
    print("\n[TEST 1] Sidebar Visibility across all roles...")
    for role_name, u in [
        ("Admin", u_admin),
        ("ASM", u_asm),
        ("Sales Support", u_support),
        ("RSOM", u_rsom),
        ("Direksi", u_direksi),
        ("Sales/Submitter", u_sales),
    ]:
        req = rf.get("/forms/permohonan-kontrak/")
        req.user = u
        ctx = forms_workflows(req)
        sidebar_cats = ctx.get("sidebar_categories", [])
        found_slugs = []
        for cat in sidebar_cats:
            for f in cat.get("forms", []):
                found_slugs.append(f["slug"])
        assert "permohonan-kontrak" in found_slugs, f"permohonan-kontrak missing from sidebar for {role_name}!"
        print(f"  ✓ {role_name}: permohonan-kontrak correctly present in sidebar categories.")

    # 3. Test Form Submission Hub Access
    print("\n[TEST 2] Form Submission Hub Access (is_privileged)...")
    for role_name, u in [
        ("Admin", u_admin),
        ("ASM", u_asm),
        ("Sales Support", u_support),
        ("RSOM", u_rsom),
        ("Direksi", u_direksi),
    ]:
        req = rf.get("/forms/permohonan-kontrak/")
        setup_request(req, u)
        resp = form_submission_hub(req, "permohonan-kontrak")
        assert resp.status_code == 200, f"Hub access returned {resp.status_code} for {role_name}!"
        print(f"  ✓ {role_name}: Hub access allowed (200 OK).")

    # 4. Setup Test Submissions & Tasks for Workflow Stages
    print("\n[TEST 3] Setup Test Submissions for Stages 1 to 4...")
    wf = form_def.workflows.first()
    assert wf is not None, "Workflow not found!"
    stages = list(wf.stages.all().order_by("order"))
    assert len(stages) >= 4, f"Expected at least 4 stages, got {len(stages)}"

    s1, s2, s3, s4 = stages[0], stages[1], stages[2], stages[3]

    # Create 5 test submissions
    now = timezone.now()
    # Sub 1: Stage 1 ASM
    sub_1 = FormSubmission.objects.create(
        form_definition=form_def,
        submitter=u_sales,
        status="pending_approval",
        submitted_at=now,
        form_data={
            "nomor_spk": "SPK/TEST/ASM/001",
            "nama_toko": "Toko Bintang Timur",
            "brand": "ELITE",
            "kode_customer_jde": "JDE-1111",
        }
    )
    t1 = ApprovalTask.objects.create(
        submission=sub_1,
        workflow_stage=s1,
        status="pending",
        assigned_to=u_asm,
        assigned_group=grp_asm,
    )

    # Sub 2: Stage 2 Support
    sub_2 = FormSubmission.objects.create(
        form_definition=form_def,
        submitter=u_sales,
        status="pending_approval",
        submitted_at=now,
        form_data={
            "nomor_spk": "SPK/TEST/SUPP/002",
            "nama_toko": "Toko Sentosa Abadi",
            "brand": "LADY",
            "kode_customer_jde": "JDE-2222",
        }
    )
    t2 = ApprovalTask.objects.create(
        submission=sub_2,
        workflow_stage=s2,
        status="pending",
        assigned_to=u_support,
        assigned_group=grp_support,
    )

    # Sub 3: Stage 3 RSOM
    sub_3 = FormSubmission.objects.create(
        form_definition=form_def,
        submitter=u_sales,
        status="pending_approval",
        submitted_at=now,
        form_data={
            "nomor_spk": "SPK/TEST/RSOM/003",
            "nama_toko": "Toko Makmur Jaya",
            "brand": "ROYAL",
            "kode_customer_jde": "JDE-3333",
        }
    )
    t3 = ApprovalTask.objects.create(
        submission=sub_3,
        workflow_stage=s3,
        status="pending",
        assigned_to=u_rsom,
        assigned_group=grp_rsom,
    )

    # Sub 4: Stage 4 Menunggu TTD Toko
    sub_4 = FormSubmission.objects.create(
        form_definition=form_def,
        submitter=u_sales,
        status="pending_approval",
        submitted_at=now,
        form_data={
            "nomor_spk": "SPK/TEST/TOKO/004",
            "nama_toko": "Toko Sejahtera Bersama",
            "brand": "SERENITY",
            "kode_customer_jde": "JDE-4444",
        }
    )
    t4 = ApprovalTask.objects.create(
        submission=sub_4,
        workflow_stage=s4,
        status="pending",
        assigned_to=u_direksi,
        assigned_group=grp_direksi,
    )
    # Token created but pending (not signed)
    tok_4 = ContractSigningToken.objects.create(
        submission=sub_4,
        status="pending",
        token_expiry=now + timedelta(days=7),
    )

    # Sub 5: Stage 4 Approval Direksi (Signed by Store)
    sub_5 = FormSubmission.objects.create(
        form_definition=form_def,
        submitter=u_sales,
        status="pending_approval",
        submitted_at=now,
        form_data={
            "nomor_spk": "SPK/TEST/DIR/005",
            "nama_toko": "Toko Cahaya Gemilang",
            "brand": "ELITE",
            "kode_customer_jde": "JDE-5555",
            "ttd_toko_image": "data:image/png;base64,fake",
        }
    )
    t5 = ApprovalTask.objects.create(
        submission=sub_5,
        workflow_stage=s4,
        status="pending",
        assigned_to=u_direksi,
        assigned_group=grp_direksi,
    )
    tok_5 = ContractSigningToken.objects.create(
        submission=sub_5,
        status="signed",
        signed_at=now,
        token_expiry=now + timedelta(days=7),
    )

    # 5. Test AJAX stage_filter
    print("\n[TEST 4] Testing approval_inbox_ajax stage_filter...")
    # Admin viewing inbox with role=reviewing (sees all pending contract tasks)
    stage_cases = [
        ("stage_1_asm", [t1.id]),
        ("stage_2_support", [t2.id]),
        ("stage_3_rsom", [t3.id]),
        ("waiting_toko", [t4.id]),
        ("stage_4_direksi", [t5.id]),
    ]

    for stage_val, expected_ids in stage_cases:
        req = rf.post(
            "/forms/approvals/ajax/",
            data={
                "draw": "1",
                "start": "0",
                "length": "200",
                "role": "reviewing",
                "form": "permohonan-kontrak",
                "stage_filter": stage_val,
            }
        )
        req.user = u_admin
        resp = approval_inbox_ajax(req)
        assert resp.status_code == 200, f"AJAX returned {resp.status_code}"
        res_data = json.loads(resp.content.decode("utf-8"))
        row_ids = [int(r["DT_RowId"].replace("row_", "")) for r in res_data["data"]]
        for exp_id in expected_ids:
            assert exp_id in row_ids, f"Expected task {exp_id} in results for {stage_val}, got {row_ids}"
        # And ensure other test ids are not present
        other_test_ids = {t1.id, t2.id, t3.id, t4.id, t5.id} - set(expected_ids)
        for other_id in other_test_ids:
            assert other_id not in row_ids, f"Task {other_id} should NOT be in results for {stage_val}"
        print(f"  ✓ stage_filter='{stage_val}': Returned {len(row_ids)} task(s), correctly matched {expected_ids}")

    # 6. Test AJAX Multi-Field Search
    print("\n[TEST 5] Testing approval_inbox_ajax search multi-field...")
    search_cases = [
        ("SPK/TEST/ASM/001", [t1.id], "by SPK Number"),
        ("Toko Sentosa Abadi", [t2.id], "by Store Name"),
        ("JDE-3333", [t3.id], "by JDE Code"),
        ("SERENITY", [t4.id], "by Brand"),
        ("test_sales_sf", [t1.id, t2.id, t3.id, t4.id, t5.id], "by Submitter Username"),
    ]

    for search_term, expected_ids, desc in search_cases:
        req = rf.post(
            "/forms/approvals/ajax/",
            data={
                "draw": "1",
                "start": "0",
                "length": "200",
                "role": "reviewing",
                "form": "permohonan-kontrak",
                "search[value]": search_term,
            }
        )
        req.user = u_admin
        resp = approval_inbox_ajax(req)
        assert resp.status_code == 200, f"AJAX returned {resp.status_code}"
        res_data = json.loads(resp.content.decode("utf-8"))
        row_ids = [int(r["DT_RowId"].replace("row_", "")) for r in res_data["data"]]
        for exp_id in expected_ids:
            assert exp_id in row_ids, f"Expected task {exp_id} in results for search '{search_term}' ({desc})"
        print(f"  ✓ Search '{search_term}' ({desc}): Correctly matched tasks {expected_ids}")

    # 7. Test Completed Approvals AJAX (History tab)
    print("\n[TEST 6] Testing completed_approvals_ajax search & stage_filter...")
    # Create an approved submission for history
    sub_hist = FormSubmission.objects.create(
        form_definition=form_def,
        submitter=u_sales,
        status="approved",
        submitted_at=now,
        completed_at=now,
        form_data={
            "nomor_spk": "SPK/TEST/HIST/099",
            "nama_toko": "Toko Sejarah Indah",
            "brand": "ELITE",
            "kode_customer_jde": "JDE-9999",
        }
    )
    t_hist = ApprovalTask.objects.create(
        submission=sub_hist,
        workflow_stage=s4,
        status="approved",
        assigned_to=u_direksi,
        assigned_group=grp_direksi,
    )

    req_hist = rf.post(
        "/forms/approvals/completed/ajax/",
        data={
            "draw": "1",
            "start": "0",
            "length": "50",
            "form": "permohonan-kontrak",
            "search[value]": "SPK/TEST/HIST/099",
        }
    )
    req_hist.user = u_admin
    resp_hist = completed_approvals_ajax(req_hist)
    assert resp_hist.status_code == 200, f"History AJAX returned {resp_hist.status_code}"
    res_hist = json.loads(resp_hist.content.decode("utf-8"))
    assert res_hist["recordsFiltered"] >= 1, f"Expected at least 1 record for history search, got {res_hist['recordsFiltered']}"
    print(f"  ✓ completed_approvals_ajax search by SPK: Successfully found {res_hist['recordsFiltered']} completed submission(s).")

    # Clean up test artifacts
    print("\nCleaning up test submissions...")
    for s in [sub_1, sub_2, sub_3, sub_4, sub_5, sub_hist]:
        s.delete()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED SUCCESSFULLY! (100%)")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
