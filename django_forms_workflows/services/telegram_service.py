"""
Telegram Notification Service for Royal Workflow.

Dispatches real-time instant alerts and reminders to Telegram Bot / Group
alongside standard email notifications.
"""

import html
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
    Formats a clean HTML Telegram message matching Royal Workflow standard,
    escaping dynamic text safely and rendering extra metadata rows when available.
    """
    from django_forms_workflows.services.notification_formatter import (
        extract_document_info,
        get_event_wording,
        get_notification_action_url,
    )

    doc_info = extract_document_info(submission, task=task)
    wording = get_event_wording(event, submission=submission, task=task)
    action_url = get_notification_action_url(submission, task=task, event=event)

    esc = html.escape
    emoji = wording["emoji"]
    judul = esc(wording["judul_notifikasi"])
    info_singkat = esc(wording["event_message"])
    status_label = esc(wording["status_label"])
    action_inst = esc(wording["action_instruction"]) if wording.get("action_instruction") else ""
    tujuan = esc(doc_info["tujuan_pengajuan"])

    extra_rows = doc_info.get("extra_rows") or []
    if extra_rows:
        info_lines = "\n".join(
            f"{esc(lbl)}: <b>{esc(val)}</b>" for lbl, val in extra_rows
        )
    else:
        info_lines = (
            f"Jenis Dokumen: <b>{esc(doc_info['jenis_dokumen'])}</b>\n"
            f"No. Pengajuan: <b>{esc(doc_info['nomor_pengajuan'])}</b>\n"
            f"Unit Kerja: <b>{esc(doc_info['unit_kerja'])}</b>\n"
            f"Pemohon: <b>{esc(doc_info['pemohon'])}</b>"
        )

    action_block = f"\n{action_inst}\n" if action_inst else ""
    safe_url = esc(action_url)

    message = (
        f"{emoji} <b>[ROYAL WORKFLOW] [{judul}]</b>\n\n"
        f"{info_singkat}\n\n"
        f"📄 <b>Informasi Dokumen</b>\n"
        f"{info_lines}\n\n"
        f"🎯 <b>Tujuan Pengajuan</b>\n"
        f"{tujuan}\n\n"
        f"📌 <b>Status</b>\n"
        f"{status_label}\n"
        f"{action_block}\n"
        f"📑 <b>Detail Pengajuan</b>\n"
        f"<a href=\"{safe_url}\">{safe_url}</a>\n\n"
        f"<i>Royal Workflow Notifications</i>"
    )
    return message


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
        return send_telegram_message(text, parse_mode="HTML")
    except Exception as exc:
        logger.error("Error in dispatch_telegram_workflow_event: %s", exc)
        return False
