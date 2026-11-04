"""
Telegram Notification Service for Royal Workflow.

Dispatches real-time instant alerts and reminders to Telegram Bot / Group
alongside standard email notifications.
"""

import logging
import os
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def get_active_telegram_config():
    """
    Returns active Telegram configuration from DB (TelegramNotificationConfig)
    or falls back to Django core settings / environment variables.
    """
    try:
        from django_forms_workflows.models import TelegramNotificationConfig

        db_cfg = TelegramNotificationConfig.objects.filter(is_active=True).first()
        if db_cfg and db_cfg.bot_token and db_cfg.chat_id:
            return {
                "token": db_cfg.bot_token,
                "chat_id": db_cfg.chat_id,
                "send_on_submission": db_cfg.send_on_submission,
                "send_on_approval_request": db_cfg.send_on_approval_request,
                "send_on_reminder": db_cfg.send_on_reminder,
                "send_on_approved": db_cfg.send_on_approved,
            }
    except Exception:
        pass

    # Fallback to settings / env
    enabled = getattr(settings, "TELEGRAM_NOTIFICATIONS_ENABLED", True)
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", None) or os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = getattr(settings, "TELEGRAM_CHAT_ID", None) or os.getenv("TELEGRAM_CHAT_ID")
    if enabled and token and chat_id:
        return {
            "token": token,
            "chat_id": chat_id,
            "send_on_submission": True,
            "send_on_approval_request": True,
            "send_on_reminder": True,
            "send_on_approved": True,
        }
    return None


def is_telegram_enabled() -> bool:
    """Check if Telegram bot credentials are configured in DB or environment."""
    return get_active_telegram_config() is not None


def send_telegram_message(
    text: str,
    chat_id: str | None = None,
    bot_token: str | None = None,
    parse_mode: str = "Markdown",
) -> bool:
    """
    Sends a message via Telegram Bot API.

    Args:
        text: Formatted message string (supports Markdown or HTML).
        chat_id: Target user or group chat ID.
        bot_token: Optional Telegram Bot Token override.
        parse_mode: 'Markdown' or 'HTML' (default: 'Markdown').

    Returns:
        bool: True if delivered successfully (HTTP 200), False otherwise.
    """
    cfg = get_active_telegram_config()
    token = (
        bot_token
        or (cfg.get("token") if cfg else None)
        or getattr(settings, "TELEGRAM_BOT_TOKEN", None)
        or os.getenv("TELEGRAM_BOT_TOKEN")
    )
    target_chat = (
        chat_id
        or (cfg.get("chat_id") if cfg else None)
        or getattr(settings, "TELEGRAM_CHAT_ID", None)
        or os.getenv("TELEGRAM_CHAT_ID")
    )
    timeout = getattr(settings, "TELEGRAM_API_TIMEOUT", 10)

    if not token or not target_chat:
        logger.debug("Telegram notification skipped: Bot Token or Chat ID not set.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": target_chat,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(url, json=payload, timeout=timeout)
        if response.status_code == 200:
            logger.info("Telegram notification delivered to chat_id=%s", target_chat)
            return True
        else:
            logger.warning(
                "Telegram API returned %s: %s", response.status_code, response.text
            )
            return False
    except Exception as exc:
        logger.error("Failed to connect to Telegram API: %s", exc)
        return False


def format_workflow_telegram_message(submission, event: str, task=None) -> str:
    """
    Formats a clean, enterprise-grade Markdown message for Telegram.
    """
    form_data = submission.form_data or {}
    form_name = submission.form_definition.name
    submitter_name = (
        submission.submitter.get_full_name() or submission.submitter.username
        if submission.submitter
        else "Inisiator"
    )
    base_url = os.getenv("SITE_URL", "http://localhost:8069").rstrip("/")
    detail_url = f"{base_url}/forms/submissions/{submission.id}/"
    approval_url = f"{base_url}/forms/approvals/"

    task_name = (
        form_data.get("nama_kegiatan")
        or form_data.get("nama_task")
        or form_data.get("nomor_spk")
        or form_name
    )

    # Dynamic extra fields for financial or technical forms
    extra_lines = []
    total_nominal = form_data.get("total_nominal")
    if total_nominal:
        try:
            nom_formatted = f"Rp {int(float(total_nominal)):,}".replace(",", ".")
            extra_lines.append(f"💰 *Nominal Biaya:* `{nom_formatted}`")
        except Exception:
            extra_lines.append(f"💰 *Nominal Biaya:* `Rp {total_nominal}`")

    cabang = form_data.get("cabang")
    divisi = form_data.get("divisi_pemohon")
    if cabang:
        unit_str = f"{cabang} ({divisi})" if divisi else cabang
        extra_lines.append(f"🏢 *Unit Kerja:* `{unit_str}`")
    elif form_data.get("target_environment"):
        extra_lines.append(f"🏢 *Target Server:* `{form_data.get('target_environment')}`")

    if form_data.get("kategori_biaya"):
        extra_lines.append(f"📂 *Kategori:* `{form_data.get('kategori_biaya')}`")
    elif form_data.get("mail_provider"):
        extra_lines.append(f"⚙️ *Provider:* `{form_data.get('mail_provider')}`")

    extra_info_block = "\n".join(extra_lines) + "\n" if extra_lines else ""

    if event == "approval_reminder":
        return (
            f"⏰ *[REMINDER] PERSETUJUAN TERTUNDA*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *Pengajuan:* {task_name}\n"
            f"{extra_info_block}"
            f"👤 *Inisiator:* {submitter_name}\n"
            f"🆔 *Ref Tiket:* `#{submission.id}`\n\n"
            f"⚠️ *Perhatian:* Pengajuan ini masih menunggu review dan persetujuan dari peninjau.\n\n"
            f"👉 [Review & Selesaikan Sekarang]({approval_url})\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"_Royal Workflow Automated Reminder_"
        )

    elif event == "approval_request":
        return (
            f"🔔 *[ROYAL WORKFLOW] PERSETUJUAN DIPERLUKAN*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *Pengajuan:* {task_name}\n"
            f"{extra_info_block}"
            f"👤 *Diajukan Oleh:* {submitter_name}\n"
            f"🆔 *Ref Pengajuan:* `#{submission.id}`\n\n"
            f"Dokumen dan rincian telah diajukan dan siap dievaluasi oleh Tim Reviewer.\n\n"
            f"👉 [Review & Otorisasi di Sistem]({approval_url})\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"_Royal Workflow Notifications_"
        )

    elif event == "workflow_approved":
        return (
            f"✅ *[APPROVED] PENGAJUAN DISETUJUI PENUH*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *Pengajuan:* {task_name}\n"
            f"{extra_info_block}"
            f"👤 *Inisiator:* {submitter_name}\n"
            f"🆔 *Ref Tiket:* `#{submission.id}`\n\n"
            f"Seluruh tahap persetujuan telah selesai dan pengajuan resmi disahkan.\n\n"
            f"📄 [Lihat Detail Pengajuan]({detail_url})\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"_Royal Workflow Notifications_"
        )

    else:
        # Default: submission_received
        return (
            f"📥 *[ROYAL WORKFLOW] PENGAJUAN BARU DITERIMA*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *Pengajuan:* {task_name}\n"
            f"{extra_info_block}"
            f"👤 *Inisiator:* {submitter_name}\n"
            f"🆔 *Ref Tiket:* `#{submission.id}`\n\n"
            f"Pengajuan berhasil dicatat dan masuk ke antrean review persetujuan.\n\n"
            f"📄 [Buka Detail Tiket]({detail_url})\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"_Royal Workflow Notifications_"
        )


def dispatch_telegram_workflow_event(submission_id: int, event: str, task_id: int | None = None) -> bool:
    """Dispatches Telegram notification for a workflow lifecycle event."""
    cfg = get_active_telegram_config()
    if not cfg:
        return False

    # Event filtering based on configuration
    if event in ("submission_received", "task.created") and not cfg.get("send_on_submission", True):
        return False
    if event == "approval_request" and not cfg.get("send_on_approval_request", True):
        return False
    if event == "approval_reminder" and not cfg.get("send_on_reminder", True):
        return False
    if event == "workflow_approved" and not cfg.get("send_on_approved", True):
        return False

    try:
        from django_forms_workflows.models import FormSubmission, ApprovalTask

        submission = FormSubmission.objects.select_related("form_definition", "submitter").get(id=submission_id)
        task = ApprovalTask.objects.filter(id=task_id).first() if task_id else None
        text = format_workflow_telegram_message(submission, event, task=task)
        return send_telegram_message(text)
    except Exception as exc:
        logger.error("Error in dispatch_telegram_workflow_event: %s", exc)
        return False
