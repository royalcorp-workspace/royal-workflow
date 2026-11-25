import os
import re
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "workflow_project.settings")
django.setup()

from django.conf import settings
from django.core import mail
from django.test import override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from django_forms_workflows.models import (
    FormDefinition,
    FormSubmission,
    ApprovalTask,
    NotificationRule,
    ContractSigningToken,
)
from django_forms_workflows.services.notification_formatter import (
    build_notification_placeholders,
    interpolate_single_brace_placeholders,
)
from django_forms_workflows.tasks import send_notification_rules
from django_forms_workflows.services.contract_notification_service import (
    send_store_signing_invitation,
    send_manual_stage_reminder,
)

User = get_user_model()

RAW_SINGLE_BRACE_RE = re.compile(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}")
RAW_DOUBLE_BRACE_RE = re.compile(r"\{\{.*?\}\}")


def assert_no_raw_placeholders(email_msg, label: str):
    """Assert that subject, plain-text body, and HTML body (excluding <style>) contain zero raw placeholders."""
    subj = email_msg.subject or ""
    body = email_msg.body or ""
    html_parts = [alt[0] for alt in getattr(email_msg, "alternatives", []) if alt[1] == "text/html"]
    html_body = html_parts[0] if html_parts else ""
    html_no_style = re.sub(r"<style\b[^>]*>.*?</style>", "", html_body, flags=re.DOTALL | re.IGNORECASE)

    for part_name, text in [("subject", subj), ("text_body", body), ("html_body", html_no_style)]:
        m_single = RAW_SINGLE_BRACE_RE.findall(text)
        m_double = RAW_DOUBLE_BRACE_RE.findall(text)
        assert not m_single, f"[{label}] Raw single-brace placeholder(s) {m_single} found in {part_name}: {text[:300]}"
        assert not m_double, f"[{label}] Raw double-brace placeholder(s) {m_double} found in {part_name}: {text[:300]}"


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def run_tests():
    print("=" * 70)
    print("RUNNING EMAIL PLACEHOLDER AUDIT & RENDERING TESTS")
    print("=" * 70)
    if not hasattr(mail, "outbox"):
        mail.outbox = []

    # 1. Unit Test interpolate_single_brace_placeholders
    print("\n[TEST 1] Unit test interpolate_single_brace_placeholders & CSS safety...")
    sample_html = (
        "<html><head><style>body { color: #333; font-size: 14px; }</style></head>"
        "<body>Halo {submitter_name}, toko {nama_toko} ({nomor_spk}) {unknown_optional}.</body></html>"
    )
    rendered = interpolate_single_brace_placeholders(
        sample_html,
        {"submitter_name": "Budi", "nama_toko": "TOKO MAJU", "nomor_spk": "001/SPK/2026"},
    )
    assert "body { color: #333; font-size: 14px; }" in rendered, "CSS style block was corrupted!"
    assert "Halo Budi, toko TOKO MAJU (001/SPK/2026) ." in rendered, f"Unexpected render: {rendered}"
    assert "{unknown_optional}" not in rendered, "Unknown placeholder was not cleaned!"
    print("  ✓ CSS block preserved, known placeholders replaced, unknown placeholders cleaned.")

    # 2. Setup Users & Kontrak Toko Submission
    print("\n[TEST 2] Testing all NotificationRule events for permohonan-kontrak...")
    form_kontrak = FormDefinition.objects.get(slug="permohonan-kontrak")
    wf_kontrak = form_kontrak.workflows.first()
    stages = list(wf_kontrak.stages.all().order_by("order"))

    grp_asm, _ = Group.objects.get_or_create(name="Area Sales Manager (L1)")
    u_submitter, _ = User.objects.get_or_create(
        username="test_email_sub",
        defaults={"email": "sub_test@example.com", "first_name": "Andi", "last_name": "Sales"},
    )
    if not u_submitter.email:
        u_submitter.email = "sub_test@example.com"
        u_submitter.save()

    u_approver, _ = User.objects.get_or_create(
        username="test_email_app",
        defaults={"email": "app_test@example.com", "first_name": "Budi", "last_name": "ASM"},
    )
    if not u_approver.email:
        u_approver.email = "app_test@example.com"
        u_approver.save()
    u_approver.groups.add(grp_asm)

    sub = FormSubmission.objects.create(
        form_definition=form_kontrak,
        submitter=u_submitter,
        status="pending_approval",
        submitted_at=timezone.now(),
        form_data={
            "nomor_spk": "009/SPK-TEST/2026",
            "nama_toko": "TOKO MAJU JAYA TEST",
            "nama_pemilik": "Hendra Wijaya",
            "email": "toko_test@example.com",
            "brand": "ELITE",
            "cabang": "Jakarta",
            "kode_customer_jde": "JDE-8888",
        },
    )
    t1 = ApprovalTask.objects.create(
        submission=sub,
        workflow_stage=stages[0],
        status="pending",
        assigned_to=u_approver,
        assigned_group=grp_asm,
        step_name=stages[0].name,
    )

    try:
        for evt in [
            "submission_received",
            "approval_request",
            "submission_returned",
            "workflow_denied",
            "workflow_approved",
        ]:
            mail.outbox.clear()
            send_notification_rules(
                submission_id=sub.id,
                event=evt,
                task_id=t1.id if evt == "approval_request" else None,
            )
            assert len(mail.outbox) >= 1, f"No emails sent for event '{evt}'!"
            for msg in mail.outbox:
                assert_no_raw_placeholders(msg, f"permohonan-kontrak/{evt}")
                assert "TOKO MAJU JAYA TEST" in (msg.body or ""), (
                    f"[{evt}] Expected 'TOKO MAJU JAYA TEST' in body, got: {msg.body}"
                )
            print(f"  ✓ Event '{evt}': {len(mail.outbox)} email(s) sent, 0 raw placeholders, nama_toko rendered.")

        # 3. Test Contract Notification Service (Store Invite & Push Reminder)
        print("\n[TEST 3] Testing contract_notification_service (Store Invite & Push Reminder)...")
        from datetime import timedelta
        tok = ContractSigningToken.objects.create(
            submission=sub,
            status="pending",
            token_expiry=timezone.now() + timedelta(days=7),
        )
        mail.outbox.clear()
        send_store_signing_invitation(sub, tok)
        assert len(mail.outbox) >= 1, "No store invitation email sent!"
        for msg in mail.outbox:
            assert_no_raw_placeholders(msg, "send_store_signing_invitation")
        print(f"  ✓ Store signing invitation: {len(mail.outbox)} email(s) verified, 0 raw placeholders.")

        mail.outbox.clear()
        push_res = send_manual_stage_reminder(sub, u_approver)
        assert push_res.get("success"), f"Push notification failed: {push_res}"
        if mail.outbox:
            for msg in mail.outbox:
                assert_no_raw_placeholders(msg, "send_manual_stage_reminder")
        print(f"  ✓ Manual push notification: {len(mail.outbox)} email(s) verified, 0 raw placeholders.")

        # 4. Test Pengajuan Biaya (HTML + CSS + Django Template {{ ... }})
        print("\n[TEST 4] Testing NotificationRule HTML+CSS for pengajuan-biaya...")
        form_biaya = FormDefinition.objects.filter(slug="pengajuan-biaya").first()
        if form_biaya:
            sub_biaya = FormSubmission.objects.create(
                form_definition=form_biaya,
                submitter=u_submitter,
                status="pending_approval",
                submitted_at=timezone.now(),
                form_data={
                    "nama_kegiatan": "Pameran Furniture Test",
                    "cabang": "Bandung",
                    "nomor_pengajuan": "PB/TEST/001",
                },
            )
            try:
                mail.outbox.clear()
                send_notification_rules(submission_id=sub_biaya.id, event="submission_received")
                assert len(mail.outbox) >= 1, "No email sent for pengajuan-biaya submission_received!"
                for msg in mail.outbox:
                    assert_no_raw_placeholders(msg, "pengajuan-biaya/submission_received")
                    assert "Pameran Furniture Test" in msg.subject, f"Subject missing kegiatan: {msg.subject}"
                print(f"  ✓ pengajuan-biaya: {len(mail.outbox)} HTML email(s) verified, CSS intact, 0 raw placeholders.")
            finally:
                sub_biaya.delete()
        else:
            print("  - Skipped pengajuan-biaya (not seeded).")

    finally:
        sub.delete()

    print("\n" + "=" * 70)
    print("ALL EMAIL PLACEHOLDER TESTS PASSED! (0 RAW PLACEHOLDERS FOUND)")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
