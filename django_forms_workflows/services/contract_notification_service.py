"""
Contract Notification Service for Surat Kontrak SPK (permohonan-kontrak).

Handles business-specific notifications across the contract lifecycle:
1. Trigger 1 (Enter Stage 3): Digital signing invitation email to Store Owner (form_data['email']).
2. Trigger 2 (Store Sign Complete): Notice to Sales Support & Confirmation to Store Owner.
3. Trigger 3 (Final Approval & e-Meterai): Official legal contract email with stamped PDF attachment
   to Submitter, Sales Support, and Store Owner.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from typing import Any, Iterable, Sequence

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .notification_formatter import (
    _resolve_base_url,
    build_standard_notification_context,
    extract_document_info,
)

logger = logging.getLogger(__name__)


def _is_valid_email(email: str | None) -> bool:
    if not email or not isinstance(email, str):
        return False
    email = email.strip()
    if not email or "@" not in email:
        return False
    try:
        validate_email(email)
        return True
    except Exception:
        return False


def _record_log(
    *,
    notification_type: str,
    submission_id: int | None,
    recipient_email: str,
    subject: str,
    status: str,
    error_message: str = "",
    delivery_detail: str = "",
) -> None:
    """Safely record an entry in NotificationLog."""
    try:
        from ..models import NotificationLog

        NotificationLog.objects.create(
            notification_type=notification_type,
            submission_id=submission_id,
            recipient_email=recipient_email,
            subject=subject,
            status=status,
            error_message=error_message,
            delivery_detail=delivery_detail,
        )
    except Exception as log_err:
        logger.warning("Could not record NotificationLog: %s", log_err)


def _send_email_message(
    subject: str,
    to_list: list[str],
    html_content: str,
    *,
    notification_type: str,
    submission_id: int | None,
    attachment_path: str | None = None,
) -> bool:
    """Send HTML email with optional PDF attachment and record NotificationLog."""
    valid_recipients = [e.strip() for e in to_list if _is_valid_email(e)]
    if not valid_recipients:
        logger.info("ContractNotification: No valid recipients for '%s'", subject)
        for r in to_list:
            _record_log(
                notification_type=notification_type,
                submission_id=submission_id,
                recipient_email=r or "(none)",
                subject=subject,
                status="skipped",
                error_message="Invalid or empty recipient email",
            )
        return False

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@royalcorp.co.id")
    text_content = strip_tags(
        re.sub(r"<style.*?>.*?</style>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
    ).strip()

    redirect_target = getattr(settings, "EMAIL_TEST_REDIRECT", None)
    all_success = True
    for recipient in valid_recipients:
        target_to = [redirect_target] if redirect_target else [recipient]
        target_subject = f"[TEST REDIRECT -> {recipient}] {subject}" if redirect_target else subject

        msg = EmailMultiAlternatives(
            subject=target_subject,
            body=text_content,
            from_email=from_email,
            to=target_to,
        )
        msg.attach_alternative(html_content, "text/html")

        if attachment_path and os.path.isfile(attachment_path):
            try:
                filename = os.path.basename(attachment_path)
                with open(attachment_path, "rb") as f:
                    msg.attach(filename, f.read(), "application/pdf")
            except Exception as att_err:
                logger.warning("Failed attaching file %s: %s", attachment_path, att_err)

        try:
            msg.send(fail_silently=False)
            detail = f"Redirected to {redirect_target} from original={recipient}" if redirect_target else "ContractNotificationService direct delivery"
            _record_log(
                notification_type=notification_type,
                submission_id=submission_id,
                recipient_email=recipient,
                subject=subject,
                status="sent",
                delivery_detail=detail,
            )
            logger.info("Sent email '%s' to %s (submission #%s)", subject, recipient, submission_id)
        except Exception as send_err:
            all_success = False
            err_msg = str(send_err)
            _record_log(
                notification_type=notification_type,
                submission_id=submission_id,
                recipient_email=recipient,
                subject=subject,
                status="failed",
                error_message=err_msg,
            )
            logger.error("Failed sending email '%s' to %s: %s", subject, recipient, send_err)

    return all_success


# -----------------------------------------------------------------------------
# Trigger 1: Saat Masuk Stage 3 (Undangan TTD Digital Toko)
# -----------------------------------------------------------------------------

def send_store_signing_invitation(submission, token) -> bool:
    """Send digital signing invitation to Store Owner (form_data['email']) when entering Stage 3."""
    if not submission or getattr(submission.form_definition, "slug", "") != "permohonan-kontrak":
        return False

    form_data = submission.form_data or {}
    store_email = (form_data.get("email") or "").strip()
    nama_toko = form_data.get("nama_toko") or "Toko Mitra"
    nomor_spk = form_data.get("nomor_spk") or f"SPK#{submission.id}"

    if not _is_valid_email(store_email):
        logger.info(
            "Store signing invitation skipped for submission #%s: store email '%s' is empty or invalid.",
            submission.id,
            store_email,
        )
        _record_log(
            notification_type="signing_invitation",
            submission_id=submission.id,
            recipient_email=store_email or "(empty)",
            subject=f"Undangan Penandatanganan Kontrak Digital SPK - {nama_toko} ({nomor_spk})",
            status="skipped",
            error_message="Store email empty or invalid",
        )
        return False

    # Deduplication check: do not resend invitation if already sent for this token
    from ..models import NotificationLog
    if NotificationLog.objects.filter(
        submission_id=submission.id,
        notification_type="signing_invitation",
        recipient_email=store_email,
        status="sent",
    ).exists():
        logger.info("Signing invitation already sent to %s for submission #%s; skipping duplicate.", store_email, submission.id)
        return True

    base_url = _resolve_base_url()
    signing_url = f"{base_url}/spk/sign/{token.token}/"
    subject = f"Undangan Penandatanganan Kontrak Digital SPK - {nama_toko} ({nomor_spk})"

    doc_info = extract_document_info(submission)
    ctx = {
        "submission": submission,
        "token": token,
        "form_data": form_data,
        "doc_info": doc_info,
        "event_message": (
            f"Dokumen Perjanjian Kerjasama (SPK) untuk {nama_toko} telah selesai direview dan disetujui "
            f"secara internal oleh tim sales. Kami mengundang Bapak/Ibu mitra toko untuk meninjau draf dokumen "
            f"dan membubuhkan tanda tangan digital pada tautan resmi berikut."
        ),
        "status_label": "Menunggu Tanda Tangan Toko",
        "action_instruction": "Silakan klik tombol di bawah untuk memeriksa draf dan menandatangani dokumen secara digital. Tautan ini berlaku selama 7 hari.",
        "action_url": signing_url,
        "action_title": "Tanda Tangani Dokumen Digital",
        "action_button_label": "Tanda Tangani SPK Digital",
        "site_name": getattr(settings, "SITE_NAME", "Royal Workflow"),
    }

    html = render_to_string("emails/standard_notification.html", ctx)
    return _send_email_message(
        subject=subject,
        to_list=[store_email],
        html_content=html,
        notification_type="signing_invitation",
        submission_id=submission.id,
    )


# -----------------------------------------------------------------------------
# Trigger 2: Saat Toko Menyelesaikan TTD Digital di Portal Publik
# -----------------------------------------------------------------------------

def send_store_signature_completed_notifications(submission, token) -> None:
    """Notify Sales Support that store signed, and confirm to Store Owner."""
    if not submission or getattr(submission.form_definition, "slug", "") != "permohonan-kontrak":
        return

    form_data = submission.form_data or {}
    nama_toko = form_data.get("nama_toko") or "Toko Mitra"
    nomor_spk = form_data.get("nomor_spk") or f"SPK#{submission.id}"
    store_email = (form_data.get("email") or "").strip()
    signer_name = token.signer_name or form_data.get("nama_pemilik") or "Pimpinan Toko"
    signer_title = token.signer_title or "Pemilik"

    base_url = _resolve_base_url()
    doc_info = extract_document_info(submission)

    # 1. Notify Direksi & Sales Support Group
    direksi_group = Group.objects.filter(name="Direksi").first()
    sales_support_group = Group.objects.filter(name="Sales Support").first()
    internal_emails: list[str] = []
    if direksi_group:
        internal_emails.extend(
            direksi_group.user_set.filter(is_active=True).exclude(email="").values_list("email", flat=True)
        )
    if sales_support_group:
        internal_emails.extend(
            sales_support_group.user_set.filter(is_active=True).exclude(email="").values_list("email", flat=True)
        )
    internal_emails = list(dict.fromkeys(internal_emails))

    task = token.task
    if not task or task.status != "pending":
        task = submission.approval_tasks.filter(
            status="pending", workflow_stage__order=4
        ).first()

    review_url = (
        f"{base_url}/forms/approvals/{task.id}/approve/"
        if task
        else f"{base_url}/forms/submissions/{submission.id}/"
    )

    ss_subject = f"[TTD Toko Selesai] SPK {nomor_spk} - {nama_toko} Siap Disahkan Direksi"
    ss_ctx = {
        "submission": submission,
        "token": token,
        "form_data": form_data,
        "doc_info": doc_info,
        "event_message": (
            f"Mitra toko {nama_toko} atas nama {signer_name} ({signer_title}) telah selesai "
            f"membubuhkan tanda tangan digital pada SPK {nomor_spk}. "
            f"Dokumen kini siap disahkan oleh Direksi (Final Review & e-Meterai)."
        ),
        "status_label": "TTD Toko Selesai (Menunggu Approval Direksi)",
        "action_instruction": (
            "Mohon periksa kelengkapan berkas dan lakukan persetujuan final (Approve SPK) "
            "untuk membubuhi sertifikat e-Meterai resmi Peruri."
        ),
        "action_url": review_url,
        "action_title": "Pengesahan Final SPK",
        "action_button_label": "Review & Sahkan SPK",
        "site_name": getattr(settings, "SITE_NAME", "Royal Workflow"),
    }
    ss_html = render_to_string("emails/standard_notification.html", ss_ctx)
    if internal_emails:
        _send_email_message(
            subject=ss_subject,
            to_list=internal_emails,
            html_content=ss_html,
            notification_type="toko_signed_notice",
            submission_id=submission.id,
        )

    # 2. Confirm to Store Owner
    if _is_valid_email(store_email):
        store_subject = f"Konfirmasi: Tanda Tangan Digital SPK {nomor_spk} Berhasil Diterima"
        store_ctx = {
            "submission": submission,
            "token": token,
            "form_data": form_data,
            "doc_info": doc_info,
            "event_message": (
                f"Terima kasih. Tanda tangan digital atas nama {signer_name} ({signer_title}) untuk dokumen SPK "
                f"{nomor_spk} ({nama_toko}) telah berhasil kami terima dan tersimpan dengan aman di sistem Royal Workflow."
            ),
            "status_label": "Tanda Tangan Diterima (Proses Verifikasi Internal)",
            "action_instruction": (
                "Dokumen saat ini dalam tahap pengesahan final dan pembubuhan sertifikat e-Meterai resmi oleh Direksi. "
                "Salinan resmi SPK yang telah sah akan dikirimkan ke email ini setelah seluruh persetujuan selesai."
            ),
            "action_url": f"{base_url}/spk/sign/{token.token}/",
            "action_title": "Status Dokumen",
            "action_button_label": "Lihat Dokumen Tertanda Tangan",
            "site_name": getattr(settings, "SITE_NAME", "Royal Workflow"),
        }
        store_html = render_to_string("emails/standard_notification.html", store_ctx)
        _send_email_message(
            subject=store_subject,
            to_list=[store_email],
            html_content=store_html,
            notification_type="toko_signed_confirmation",
            submission_id=submission.id,
        )


# -----------------------------------------------------------------------------
# Trigger 3: Saat Final Approval Direksi + Pasca e-Meterai Stamping
# -----------------------------------------------------------------------------

def send_final_spk_approved_notifications(submission, stamped_pdf_path: str | None = None) -> None:
    """Send legal stamped SPK contract with PDF attachment to Submitter, Sales Support, and Store Owner."""
    if not submission or getattr(submission.form_definition, "slug", "") != "permohonan-kontrak":
        return

    form_data = submission.form_data or {}
    nama_toko = form_data.get("nama_toko") or "Toko Mitra"
    nomor_spk = form_data.get("nomor_spk") or f"SPK#{submission.id}"
    store_email = (form_data.get("email") or "").strip()

    # Resolve submitter email
    submitter_email = ""
    if submission.submitter and submission.submitter.email:
        submitter_email = submission.submitter.email
    elif form_data.get("submitter_email"):
        submitter_email = form_data.get("submitter_email")

    # Resolve Sales Support emails
    sales_support_emails: list[str] = []
    sales_support_group = Group.objects.filter(name="Sales Support").first()
    if sales_support_group:
        sales_support_emails = list(
            sales_support_group.user_set.filter(is_active=True)
            .exclude(email="")
            .values_list("email", flat=True)
        )

    base_url = _resolve_base_url()
    doc_info = extract_document_info(submission)
    detail_url = f"{base_url}/forms/submissions/{submission.id}/"

    subject = f"Surat Perjanjian Kerjasama (SPK) Resmi - {nama_toko} ({nomor_spk}) Telah Sah Ber-e-Meterai"
    ctx = {
        "submission": submission,
        "form_data": form_data,
        "doc_info": doc_info,
        "event_message": (
            f"Kabar baik! Surat Perjanjian Kerjasama (SPK) {nomor_spk} untuk {nama_toko} telah disetujui penuh "
            f"oleh Direksi dan telah resmi dibubuhi e-Meterai sah. Dokumen ini telah sah berkekuatan hukum dan mulai berlaku."
        ),
        "status_label": "Disahkan Sepenuhnya (Sah Ber-e-Meterai)",
        "action_instruction": "Terlampir berkas resmi SPK ber-e-Meterai dalam format PDF untuk disimpan sebagai arsip legal kerjasama.",
        "action_url": detail_url,
        "action_title": "Detail Dokumen Sistem",
        "action_button_label": "Buka Dokumen di Portal",
        "site_name": getattr(settings, "SITE_NAME", "Royal Workflow"),
    }
    html = render_to_string("emails/standard_notification.html", ctx)

    # 1. Send to Submitter
    if _is_valid_email(submitter_email):
        _send_email_message(
            subject=subject,
            to_list=[submitter_email],
            html_content=html,
            notification_type="final_spk_stamped",
            submission_id=submission.id,
            attachment_path=stamped_pdf_path,
        )

    # 2. Send to Sales Support
    if sales_support_emails:
        _send_email_message(
            subject=subject,
            to_list=sales_support_emails,
            html_content=html,
            notification_type="final_spk_stamped",
            submission_id=submission.id,
            attachment_path=stamped_pdf_path,
        )

    # 3. Send to Store Owner
    if _is_valid_email(store_email):
        _send_email_message(
            subject=subject,
            to_list=[store_email],
            html_content=html,
            notification_type="final_spk_stamped",
            submission_id=submission.id,
            attachment_path=stamped_pdf_path,
        )


# Background dispatcher wrappers to prevent blocking HTTP request thread
def dispatch_store_signing_invitation_async(submission, token) -> None:
    threading.Thread(
        target=send_store_signing_invitation,
        args=(submission, token),
        daemon=True,
    ).start()


def dispatch_store_signature_completed_async(submission, token) -> None:
    threading.Thread(
        target=send_store_signature_completed_notifications,
        args=(submission, token),
        daemon=True,
    ).start()


def dispatch_final_spk_approved_async(submission, stamped_pdf_path: str | None = None) -> None:
    threading.Thread(
        target=send_final_spk_approved_notifications,
        args=(submission, stamped_pdf_path),
        daemon=True,
    ).start()


# -----------------------------------------------------------------------------
# Manual Push Reminder by Sales Support
# -----------------------------------------------------------------------------

def resolve_active_stage_push_target(submission) -> dict:
    """Resolve active stage and recipient targets for manual push notification."""
    if not submission or getattr(submission.form_definition, "slug", "") != "permohonan-kontrak":
        return {"valid": False, "reason": "Bukan formulir Kontrak Toko"}

    if submission.status not in ["pending_approval", "submitted"]:
        return {"valid": False, "reason": "Pengajuan tidak dalam status aktif berjalan"}

    form_data = submission.form_data or {}
    nama_toko = form_data.get("nama_toko") or "Toko Mitra"
    nomor_spk = form_data.get("nomor_spk") or f"SPK#{submission.id}"

    # Get active pending tasks
    all_tasks = list(submission.approval_tasks.all())
    pending_tasks = [t for t in all_tasks if t.status == "pending"]
    if not pending_tasks:
        return {"valid": False, "reason": "Tidak ada tugas approval yang sedang pending"}

    active_task = pending_tasks[0]
    stage = active_task.workflow_stage
    stage_order = stage.order if stage else 0

    tokens = list(submission.signing_tokens.order_by("-id"))
    latest_token = tokens[0] if tokens else None
    is_token_signed = (latest_token and latest_token.status == "signed") or bool(form_data.get("ttd_toko_image"))

    base_url = _resolve_base_url()

    # Stage 1: Review ASM
    if stage_order == 1:
        stage_name = "Stage 1: Review ASM"
        role_label = "ASM (Sales Area Manager)"
        recipient_users = []
        if active_task.assigned_to and active_task.assigned_to.email:
            recipient_users = [active_task.assigned_to]
        elif active_task.assigned_group:
            recipient_users = list(active_task.assigned_group.user_set.filter(is_active=True).exclude(email=""))
        else:
            asm_group = Group.objects.filter(name="Sales Area Manager").first()
            if asm_group:
                recipient_users = list(asm_group.user_set.filter(is_active=True).exclude(email=""))

        recipient_emails = list(dict.fromkeys([u.email.strip() for u in recipient_users if _is_valid_email(u.email)]))
        recipient_names = [u.get_full_name() or u.username for u in recipient_users]
        action_url = f"{base_url}/forms/approvals/{active_task.id}/approve/"
        return {
            "valid": True,
            "stage_order": 1,
            "stage_name": stage_name,
            "role_label": role_label,
            "is_store": False,
            "task": active_task,
            "token": None,
            "recipient_emails": recipient_emails,
            "recipient_names": recipient_names,
            "action_url": action_url,
            "nomor_spk": nomor_spk,
            "nama_toko": nama_toko,
        }

    # Stage 2: Review Sales Support
    elif stage_order == 2:
        stage_name = "Stage 2: Review Sales Support"
        role_label = "Sales Support"
        recipient_users = []
        if active_task.assigned_to and active_task.assigned_to.email:
            recipient_users = [active_task.assigned_to]
        elif active_task.assigned_group:
            recipient_users = list(active_task.assigned_group.user_set.filter(is_active=True).exclude(email=""))
        else:
            ss_group = Group.objects.filter(name="Sales Support").first()
            if ss_group:
                recipient_users = list(ss_group.user_set.filter(is_active=True).exclude(email=""))

        recipient_emails = list(dict.fromkeys([u.email.strip() for u in recipient_users if _is_valid_email(u.email)]))
        recipient_names = [u.get_full_name() or u.username for u in recipient_users]
        action_url = f"{base_url}/forms/approvals/{active_task.id}/approve/"
        return {
            "valid": True,
            "stage_order": 2,
            "stage_name": stage_name,
            "role_label": role_label,
            "is_store": False,
            "task": active_task,
            "token": None,
            "recipient_emails": recipient_emails,
            "recipient_names": recipient_names,
            "action_url": action_url,
            "nomor_spk": nomor_spk,
            "nama_toko": nama_toko,
        }

    # Stage 3: Review RSOM
    elif stage_order == 3:
        stage_name = "Stage 3: Review RSOM"
        role_label = "RSOM (Regional Sales Operations Manager)"
        recipient_users = []
        if active_task.assigned_to and active_task.assigned_to.email:
            recipient_users = [active_task.assigned_to]
        elif active_task.assigned_group:
            recipient_users = list(active_task.assigned_group.user_set.filter(is_active=True).exclude(email=""))
        else:
            rsom_group = Group.objects.filter(name__in=["General Manager Sales", "Sales Area Manager"]).first()
            if rsom_group:
                recipient_users = list(rsom_group.user_set.filter(is_active=True).exclude(email=""))

        recipient_emails = list(dict.fromkeys([u.email.strip() for u in recipient_users if _is_valid_email(u.email)]))
        recipient_names = [u.get_full_name() or u.username for u in recipient_users]
        action_url = f"{base_url}/forms/approvals/{active_task.id}/approve/"
        return {
            "valid": True,
            "stage_order": 3,
            "stage_name": stage_name,
            "role_label": role_label,
            "is_store": False,
            "task": active_task,
            "token": None,
            "recipient_emails": recipient_emails,
            "recipient_names": recipient_names,
            "action_url": action_url,
            "nomor_spk": nomor_spk,
            "nama_toko": nama_toko,
        }

    # Stage 4: Gate TTD Toko vs Approval Direksi
    elif stage_order == 4:
        if not is_token_signed:
            stage_name = "Gate: Menunggu TTD Mitra Toko"
            role_label = "Mitra Toko"
            store_email = (form_data.get("email") or "").strip()
            signer_name = latest_token.signer_name if latest_token else (form_data.get("nama_pemilik") or "Pimpinan Toko")
            signing_url = f"{base_url}/spk/sign/{latest_token.token}/" if latest_token else f"{base_url}/forms/submissions/{submission.id}/"
            return {
                "valid": True,
                "stage_order": 4,
                "stage_name": stage_name,
                "role_label": role_label,
                "is_store": True,
                "task": active_task,
                "token": latest_token,
                "recipient_emails": [store_email] if _is_valid_email(store_email) else [],
                "recipient_names": [f"{nama_toko} ({signer_name})"],
                "action_url": signing_url,
                "nomor_spk": nomor_spk,
                "nama_toko": nama_toko,
            }
        else:
            stage_name = "Stage 4: Final Approval Direksi"
            role_label = "Direksi"
            recipient_users = []
            if active_task.assigned_to and active_task.assigned_to.email:
                recipient_users = [active_task.assigned_to]
            elif active_task.assigned_group:
                recipient_users = list(active_task.assigned_group.user_set.filter(is_active=True).exclude(email=""))
            else:
                dir_group = Group.objects.filter(name="Direksi").first()
                if dir_group:
                    recipient_users = list(dir_group.user_set.filter(is_active=True).exclude(email=""))

            recipient_emails = list(dict.fromkeys([u.email.strip() for u in recipient_users if _is_valid_email(u.email)]))
            recipient_names = [u.get_full_name() or u.username for u in recipient_users]
            action_url = f"{base_url}/forms/approvals/{active_task.id}/approve/"
            return {
                "valid": True,
                "stage_order": 4,
                "stage_name": stage_name,
                "role_label": role_label,
                "is_store": False,
                "task": active_task,
                "token": latest_token,
                "recipient_emails": recipient_emails,
                "recipient_names": recipient_names,
                "action_url": action_url,
                "nomor_spk": nomor_spk,
                "nama_toko": nama_toko,
            }

    return {"valid": False, "reason": f"Tahap urutan ke-{stage_order} tidak terdefinisi"}


def send_manual_stage_reminder(submission, sender_user, custom_note: str = "") -> dict:
    """Send manual push reminder to the current active stage PIC or store partner."""
    target = resolve_active_stage_push_target(submission)
    if not target.get("valid"):
        return {"success": False, "message": target.get("reason", "Target tahap tidak valid")}

    sender_name = (sender_user.get_full_name() or sender_user.username) if sender_user else "Sales Support"
    nomor_spk = target["nomor_spk"]
    nama_toko = target["nama_toko"]
    stage_name = target["stage_name"]
    recipient_emails = target["recipient_emails"]
    recipient_names = target["recipient_names"]
    action_url = target["action_url"]
    is_store = target["is_store"]

    if not recipient_emails:
        return {
            "success": False,
            "message": f"Tidak ditemukan alamat email valid untuk penerima pada {stage_name}.",
            "stage_label": stage_name,
            "recipient_summary": "Belum ada email terdaftar",
            "recipient_emails": [],
        }

    doc_info = extract_document_info(submission)

    if is_store:
        subject = f"[Pengingat TTD Digital] Mohon Tandatangani SPK {nomor_spk} - {nama_toko}"
        event_message = (
            f"Tim Sales Support ({sender_name}) mengirimkan pengingat penandatanganan Perjanjian Kerjasama (SPK) "
            f"untuk {nama_toko}. Mohon kesediaan Bapak/Ibu mitra toko untuk meninjau draf dan menandatangani dokumen "
            f"secara digital melalui tautan resmi berikut."
        )
        status_label = "Pengingat: Menunggu TTD Mitra Toko"
        action_instruction = "Klik tombol di bawah untuk membuka portal tanda tangan digital resmi kami."
        action_button_label = "Tanda Tangani SPK Sekarang"
        notification_type = "signing_reminder"
    else:
        subject = f"[Pengingat {target['role_label']}] SPK {nomor_spk} - {nama_toko} Menunggu Persetujuan Anda"
        event_message = (
            f"Tim Sales Support ({sender_name}) mengirimkan pengingat bahwa pengajuan SPK {nomor_spk} "
            f"untuk toko {nama_toko} saat ini sedang berada pada tahap {stage_name} dan menunggu persetujuan Anda."
        )
        status_label = f"Pengingat: {stage_name}"
        action_instruction = "Mohon tinjau berkas dan berikan persetujuan untuk meneruskan pengajuan ke tahap selanjutnya."
        action_button_label = "Review & Berikan Persetujuan"
        notification_type = "manual_reminder"

    cleaned_note = (custom_note or "").strip()
    if cleaned_note:
        event_message = f"{event_message} Catatan tambahan dari {sender_name}: \"{cleaned_note}\""

    ctx = {
        "submission": submission,
        "token": target.get("token"),
        "form_data": submission.form_data or {},
        "doc_info": doc_info,
        "event_message": event_message,
        "status_label": status_label,
        "action_instruction": action_instruction,
        "action_url": action_url,
        "action_title": f"Pengingat: {stage_name}",
        "action_button_label": action_button_label,
        "site_name": getattr(settings, "SITE_NAME", "Royal Workflow"),
    }
    html = render_to_string("emails/standard_notification.html", ctx)

    sent = _send_email_message(
        subject=subject,
        to_list=recipient_emails,
        html_content=html,
        notification_type=notification_type,
        submission_id=submission.id,
    )

    # Optional background Telegram dispatch
    try:
        from .telegram_service import dispatch_telegram_workflow_event
        task = target.get("task")
        if task:
            threading.Thread(
                target=dispatch_telegram_workflow_event,
                args=(submission.id, "approval_request", task.id),
                daemon=True,
            ).start()
    except Exception as tel_err:
        logger.debug("Telegram manual reminder dispatch skipped: %s", tel_err)

    rec_summary = ", ".join(recipient_names) if recipient_names else ", ".join(recipient_emails)
    if sent:
        return {
            "success": True,
            "message": f"Push notifikasi pengingat berhasil dikirimkan ke {stage_name} ({rec_summary}).",
            "stage_label": stage_name,
            "recipient_summary": rec_summary,
            "recipient_emails": recipient_emails,
        }
    else:
        return {
            "success": False,
            "message": f"Gagal mengirimkan email pengingat ke {rec_summary}. Periksa konfigurasi email server.",
            "stage_label": stage_name,
            "recipient_summary": rec_summary,
            "recipient_emails": recipient_emails,
        }
