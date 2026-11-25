import os
import json
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "workflow_project.settings")
django.setup()

from datetime import timedelta
from django.core import mail
from django.core.cache import cache
from django.test import RequestFactory, override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from django_forms_workflows.models import (
    FormDefinition,
    FormSubmission,
    ApprovalTask,
    ContractSigningToken,
    AuditLog,
)
from django_forms_workflows.views import (
    approval_inbox_ajax,
    push_stage_notification,
    bulk_push_stage_notifications,
)

User = get_user_model()
rf = RequestFactory()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def run_tests():
    print("=" * 70)
    print("RUNNING INBOX PER-ROW & BULK PUSH NOTIFICATION TESTS")
    print("=" * 70)
    if not hasattr(mail, "outbox"):
        mail.outbox = []

    form_def = FormDefinition.objects.get(slug="permohonan-kontrak")
    wf = form_def.workflows.first()
    stages = list(wf.stages.all().order_by("order"))
    s1, s4 = stages[0], stages[3]

    grp_support, _ = Group.objects.get_or_create(name="Sales Support")
    grp_asm, _ = Group.objects.get_or_create(name="Area Sales Manager (L1)")
    grp_direksi, _ = Group.objects.get_or_create(name="Direksi")
    form_def.reviewer_groups.add(grp_support)

    u_support, _ = User.objects.get_or_create(
        username="test_push_support",
        defaults={"email": "support_push@example.com", "first_name": "Rizma", "last_name": "Support"},
    )
    u_support.groups.add(grp_support)

    u_asm, _ = User.objects.get_or_create(
        username="test_push_asm",
        defaults={"email": "asm_push@example.com", "first_name": "Buddy", "last_name": "ASM"},
    )
    if not u_asm.email:
        u_asm.email = "asm_push@example.com"
        u_asm.save()
    u_asm.groups.add(grp_asm)

    u_sales, _ = User.objects.get_or_create(
        username="test_push_sales",
        defaults={"email": "sales_push@example.com", "first_name": "Andi", "last_name": "Sales"},
    )

    now = timezone.now()

    # Sub A: Active Stage 1 ASM (for single push test)
    sub_a = FormSubmission.objects.create(
        form_definition=form_def,
        submitter=u_sales,
        status="pending_approval",
        submitted_at=now,
        form_data={"nomor_spk": "SPK/PUSH/001", "nama_toko": "Toko Push Satu"},
    )
    t_a = ApprovalTask.objects.create(
        submission=sub_a,
        workflow_stage=s1,
        status="pending",
        assigned_to=u_asm,
        assigned_group=grp_asm,
    )

    # Sub B: Active Stage 1 ASM (for bulk push test)
    sub_b = FormSubmission.objects.create(
        form_definition=form_def,
        submitter=u_sales,
        status="pending_approval",
        submitted_at=now,
        form_data={"nomor_spk": "SPK/PUSH/002", "nama_toko": "Toko Push Dua"},
    )
    t_b = ApprovalTask.objects.create(
        submission=sub_b,
        workflow_stage=s1,
        status="pending",
        assigned_to=u_asm,
        assigned_group=grp_asm,
    )

    # Sub C: Active Stage 4 Waiting Store Sign (for bulk push test)
    sub_c = FormSubmission.objects.create(
        form_definition=form_def,
        submitter=u_sales,
        status="pending_approval",
        submitted_at=now,
        form_data={
            "nomor_spk": "SPK/PUSH/003",
            "nama_toko": "Toko Push Tiga",
            "email": "toko_push3@example.com",
        },
    )
    t_c = ApprovalTask.objects.create(
        submission=sub_c,
        workflow_stage=s4,
        status="pending",
        assigned_group=grp_direksi,
    )
    ContractSigningToken.objects.create(
        submission=sub_c,
        status="pending",
        token_expiry=now + timedelta(days=7),
    )

    # Sub D: Already Approved (should be skipped in bulk push)
    sub_d = FormSubmission.objects.create(
        form_definition=form_def,
        submitter=u_sales,
        status="approved",
        submitted_at=now,
        completed_at=now,
        form_data={"nomor_spk": "SPK/PUSH/004", "nama_toko": "Toko Sudah Selesai"},
    )

    try:
        # Clear any leftover cooldowns
        for s in (sub_a, sub_b, sub_c, sub_d):
            cache.delete(f"push_notif_cooldown_{s.id}")

        # [TEST 1] approval_inbox_ajax button visibility
        print("\n[TEST 1] Verifying Push button visibility in approval_inbox_ajax...")
        req_ss = rf.post(
            "/forms/approvals/ajax/",
            data={"draw": "1", "start": "0", "length": "50", "role": "reviewing", "search[value]": "SPK/PUSH/001"},
        )
        req_ss.user = u_support
        resp_ss = approval_inbox_ajax(req_ss)
        assert resp_ss.status_code == 200
        rows_ss = json.loads(resp_ss.content.decode("utf-8"))["data"]
        assert len(rows_ss) >= 1, "No rows returned for Sales Support!"
        assert "js-btn-push-notif" in rows_ss[0]["actions"], "Push button missing for Sales Support!"
        assert "export-check" in rows_ss[0]["checkbox"], "Checkbox missing for Sales Support!"
        print("  ✓ Sales Support sees Push button and selection checkbox.")

        req_asm = rf.post(
            "/forms/approvals/ajax/",
            data={"draw": "1", "start": "0", "length": "50", "search[value]": "SPK/PUSH/001"},
        )
        req_asm.user = u_asm
        resp_asm = approval_inbox_ajax(req_asm)
        rows_asm = json.loads(resp_asm.content.decode("utf-8"))["data"]
        assert len(rows_asm) >= 1
        assert "js-btn-push-notif" not in rows_asm[0]["actions"], "Push button must NOT appear for ASM!"
        print("  ✓ ASM does NOT see Push button.")

        # [TEST 2] Single AJAX push_stage_notification + Cooldown
        print("\n[TEST 2] Testing single AJAX push_stage_notification & 60s cooldown...")
        mail.outbox.clear()
        req_single = rf.post(
            f"/forms/submissions/{sub_a.id}/push-notification/",
            data=json.dumps({"note": "Mohon dicek hari ini ya"}),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )
        req_single.user = u_support
        resp_single = push_stage_notification(req_single, sub_a.id)
        assert resp_single.status_code == 200, f"Expected 200, got {resp_single.status_code}: {resp_single.content}"
        res_single = json.loads(resp_single.content.decode("utf-8"))
        assert res_single["success"] is True
        assert len(mail.outbox) == 1, f"Expected 1 email, got {len(mail.outbox)}"
        assert "Mohon dicek hari ini ya" in mail.outbox[0].body, "Custom note missing from email body!"
        assert AuditLog.objects.filter(object_type="FormSubmission", object_id=sub_a.id).exists()
        print(f"  ✓ Single AJAX push succeeded: {res_single['recipient_summary']}")

        # Cooldown check (immediate second request -> 429)
        resp_cd = push_stage_notification(req_single, sub_a.id)
        assert resp_cd.status_code == 429, f"Expected 429 cooldown, got {resp_cd.status_code}"
        print("  ✓ Cooldown 60s enforced cleanly (429).")

        # [TEST 3] Bulk Push Notifications (Authorization + Mixed Valid/Invalid)
        print("\n[TEST 3] Testing bulk_push_stage_notifications...")
        # Unauthorized user -> 403
        req_unauth = rf.post(
            "/forms/approvals/bulk-push-notifications/",
            data=json.dumps({"submission_ids": [sub_b.id]}),
            content_type="application/json",
        )
        req_unauth.user = u_asm
        resp_unauth = bulk_push_stage_notifications(req_unauth)
        assert resp_unauth.status_code == 403, f"Expected 403 for ASM, got {resp_unauth.status_code}"
        print("  ✓ Non-Sales Support blocked (403 Forbidden).")

        # Authorized bulk push (sub_b [ASM], sub_c [Store], sub_d [Approved/skip])
        mail.outbox.clear()
        req_bulk = rf.post(
            "/forms/approvals/bulk-push-notifications/",
            data=json.dumps({
                "submission_ids": [sub_b.id, sub_c.id, sub_d.id, sub_b.id],  # includes duplicate ID
                "note": "Pengingat massal dari Sales Support",
            }),
            content_type="application/json",
        )
        req_bulk.user = u_support
        resp_bulk = bulk_push_stage_notifications(req_bulk)
        assert resp_bulk.status_code == 200
        res_bulk = json.loads(resp_bulk.content.decode("utf-8"))
        assert res_bulk["total_selected"] == 3, f"Expected 3 unique selected, got {res_bulk['total_selected']}"
        assert res_bulk["sent_count"] == 2, f"Expected 2 sent, got {res_bulk['sent_count']}"
        assert res_bulk["skipped_count"] == 1, f"Expected 1 skipped, got {res_bulk['skipped_count']}"
        assert len(mail.outbox) == 2, f"Expected 2 emails (ASM + Store), got {len(mail.outbox)}"
        print(f"  ✓ Bulk push summary: {res_bulk['message']}")

    finally:
        for s in (sub_a, sub_b, sub_c, sub_d):
            cache.delete(f"push_notif_cooldown_{s.id}")
            s.delete()

    print("\n" + "=" * 70)
    print("ALL INBOX PUSH NOTIFICATION TESTS PASSED! (100%)")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()

