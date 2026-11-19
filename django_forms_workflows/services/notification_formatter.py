"""
Notification Formatter for Royal Workflow.

Standardizes email and Telegram notifications according to the enterprise template layout:
- Informasi Dokumen (Jenis Dokumen, No. Pengajuan, Unit Kerja, Pemohon)
- Tujuan Pengajuan
- Status Saat Ini
- Instruksi Action
- Detail Pengajuan Link
"""

from __future__ import annotations

import os
from typing import Any
from django.conf import settings
from django.urls import reverse


def _resolve_base_url() -> str:
    """Resolve base URL for links in notifications."""
    url = getattr(settings, "FORMS_WORKFLOWS_BASE_URL", None) or getattr(
        settings, "SITE_BASE_URL", None
    ) or os.getenv("SITE_URL", "")
    if url:
        return url.rstrip("/")
    origins = getattr(settings, "CSRF_TRUSTED_ORIGINS", None)
    if origins:
        return origins[0].rstrip("/")
    return "http://localhost:8069"


def extract_document_info(submission, task=None) -> dict[str, str]:
    """
    Extracts standardized document metadata from submission and form_data:
    - jenis_dokumen
    - nomor_pengajuan
    - unit_kerja
    - pemohon
    - tujuan_pengajuan
    """
    form_data = getattr(submission, "form_data", None) or {}

    # Jenis Dokumen
    jenis_dokumen = getattr(getattr(submission, "form_definition", None), "name", "Pengajuan Dokumen")

    # Nomor Pengajuan
    nomor_pengajuan = (
        form_data.get("nomor_pengajuan")
        or form_data.get("nomor_spk")
        or form_data.get("no_pengajuan")
        or form_data.get("ticket_no")
        or (f"#{submission.id}" if getattr(submission, "id", None) else "-")
    )

    # Unit Kerja (Cabang / Divisi / Departemen)
    cabang = (
        form_data.get("cabang")
        or form_data.get("applicant_branch")
        or form_data.get("branch")
        or form_data.get("unit_kerja")
    )
    divisi = (
        form_data.get("department_pembuat")
        or form_data.get("divisi_pemohon")
        or form_data.get("department")
        or form_data.get("divisi")
        or form_data.get("bagian_pembuat")
    )

    if cabang and divisi:
        unit_kerja = f"{cabang} ({divisi})"
    elif cabang:
        unit_kerja = str(cabang)
    elif divisi:
        unit_kerja = str(divisi)
    else:
        # Fallback to submitter branch attribute or default
        submitter = getattr(submission, "submitter", None)
        unit_kerja = getattr(submitter, "branch", None) or getattr(submitter, "department", None) or "Kantor Pusat / Umum"

    # Pemohon
    submitter = getattr(submission, "submitter", None)
    if submitter:
        pemohon = getattr(submitter, "get_full_name", lambda: "")() or getattr(submitter, "username", "Inisiator")
    else:
        pemohon = form_data.get("inisiator_nama") or "Inisiator"

    # Tujuan Pengajuan
    tujuan_pengajuan = (
        form_data.get("tujuan_pengajuan")
        or form_data.get("tujuan")
        or form_data.get("nama_kegiatan")
        or form_data.get("catatan_justifikasi")
        or form_data.get("keperluan")
        or form_data.get("keterangan")
        or form_data.get("deskripsi")
        or form_data.get("perihal")
        or "-"
    )

    return {
        "jenis_dokumen": str(jenis_dokumen),
        "nomor_pengajuan": str(nomor_pengajuan),
        "unit_kerja": str(unit_kerja),
        "pemohon": str(pemohon),
        "tujuan_pengajuan": str(tujuan_pengajuan),
    }


def get_event_wording(event: str, submission=None, task=None) -> dict[str, str]:
    """
    Returns standardized wording dictionary for each workflow lifecycle event:
    - judul_notifikasi
    - emoji
    - event_message
    - status_label
    - action_instruction
    """
    event = (event or "").lower()

    if event in ("approval_request", "task.created"):
        stage_name = getattr(getattr(task, "workflow_stage", None), "name", None)
        status_suffix = f" ({stage_name})" if stage_name else ""
        return {
            "judul_notifikasi": "PERSETUJUAN DIPERLUKAN",
            "emoji": "🔔",
            "event_message": "Terdapat dokumen pengajuan baru yang memerlukan evaluasi dan persetujuan dari Anda.",
            "status_label": f"Menunggu Persetujuan{status_suffix}",
            "action_instruction": "Mohon untuk meninjau rincian dokumen dan memproses persetujuan melalui sistem.",
        }

    elif event == "approval_reminder":
        stage_name = getattr(getattr(task, "workflow_stage", None), "name", None)
        status_suffix = f" ({stage_name})" if stage_name else ""
        return {
            "judul_notifikasi": "PENGINGAT PERSETUJUAN TERTUNDA",
            "emoji": "⏰",
            "event_message": "Ini adalah pengingat bahwa dokumen pengajuan berikut masih menunggu tindak lanjut persetujuan Anda.",
            "status_label": f"Menunggu Persetujuan (Tertunda){status_suffix}",
            "action_instruction": "Mohon kesediaan Bapak/Ibu untuk segera meninjau dan menyelesaikan persetujuan pengajuan ini.",
        }

    elif event in ("workflow_approved", "stage_decision", "approval_notification"):
        return {
            "judul_notifikasi": "PENGAJUAN TELAH DISETUJUI",
            "emoji": "✅",
            "event_message": "Dokumen pengajuan berikut telah selesai diverifikasi dan resmi disetujui.",
            "status_label": "Disetujui Sepenuhnya",
            "action_instruction": "Dokumen telah disahkan secara resmi dan siap untuk ditindaklanjuti ke tahapan berikutnya.",
        }

    elif event in ("workflow_denied", "rejection_notification"):
        comments = getattr(task, "comments", "") if task else ""
        catatan = f"Catatan Peninjau: {comments}" if comments else "Silakan periksa catatan pada sistem dan lakukan revisi jika diperlukan."
        return {
            "judul_notifikasi": "PENGAJUAN DITOLAK",
            "emoji": "❌",
            "event_message": "Pemberitahuan bahwa dokumen pengajuan berikut tidak disetujui oleh peninjau.",
            "status_label": "Ditolak",
            "action_instruction": catatan,
        }

    elif event in ("submission_returned", "needs_revision"):
        comments = getattr(task, "comments", "") if task else ""
        catatan = f"Catatan Revisi: {comments}" if comments else "Mohon periksa catatan peninjau dan ajukan kembali perbaikan formulir."
        return {
            "judul_notifikasi": "PERMINTAAN REVISI DOKUMEN",
            "emoji": "📝",
            "event_message": "Dokumen pengajuan berikut dikembalikan oleh peninjau untuk dilakukan revisi/perbaikan data.",
            "status_label": "Membutuhkan Revisi",
            "action_instruction": catatan,
        }

    elif event == "escalation":
        return {
            "judul_notifikasi": "ESKALASI PERSETUJUAN",
            "emoji": "⚠️",
            "event_message": "Batas waktu persetujuan telah terlampaui sehingga dokumen ini dialihkan ke eskalasi berikutnya.",
            "status_label": "Menunggu Tindak Lanjut Eskalasi",
            "action_instruction": "Mohon segera menindaklanjuti dokumen eskalasi ini untuk mencegah keterlambatan operasional.",
        }

    elif event == "form_withdrawn":
        return {
            "judul_notifikasi": "PENGAJUAN DITARIK",
            "emoji": "↩️",
            "event_message": "Dokumen pengajuan berikut telah ditarik kembali oleh inisiator/pemohon.",
            "status_label": "Ditarik oleh Pemohon",
            "action_instruction": "Tidak diperlukan tindakan lebih lanjut untuk dokumen ini.",
        }

    else:
        # Default: submission_received / submission_created
        return {
            "judul_notifikasi": "PENGAJUAN BARU DITERIMA",
            "emoji": "📥",
            "event_message": "Pengajuan dokumen baru telah berhasil diserahkan ke dalam sistem Royal Workflow.",
            "status_label": "Diajukan (Menunggu Review)",
            "action_instruction": "Pengajuan Anda saat ini sedang dalam antrean proses review oleh pihak berwenang.",
        }


def get_notification_action_url(submission, task=None) -> str:
    """Build full absolute URL for the notification action/detail link."""
    base = _resolve_base_url()
    if submission and getattr(submission, "status", "") == "needs_revision":
        fdef = getattr(submission, "form_definition", None)
        if fdef and getattr(fdef, "slug", ""):
            return f"{base}/forms/{fdef.slug}/submit/?revision={submission.id}&step=1"
    if task and getattr(task, "id", None):
        try:
            rel = reverse("forms_workflows:approve_submission", args=[task.id])
            return f"{base}{rel}"
        except Exception:
            return f"{base}/forms/approvals/{task.id}/"
    elif submission and getattr(submission, "id", None):
        try:
            rel = reverse("forms_workflows:submission_detail", args=[submission.id])
            return f"{base}{rel}"
        except Exception:
            return f"{base}/forms/submissions/{submission.id}/"
    return f"{base}/forms/"


def build_standard_notification_context(submission, event: str, task=None, approver=None, custom_action_url: str | None = None) -> dict[str, Any]:
    """
    Builds the standardized template context dictionary for emails matching Email Notifikasi layout.
    """
    doc_info = extract_document_info(submission, task=task)
    wording = get_event_wording(event, submission=submission, task=task)
    action_url = custom_action_url or get_notification_action_url(submission, task=task)

    return {
        "submission": submission,
        "task": task,
        "approver": approver,
        "doc_info": doc_info,
        "event_message": wording["event_message"],
        "status_label": wording["status_label"],
        "action_instruction": wording["action_instruction"],
        "action_url": action_url,
        "judul_notifikasi": wording["judul_notifikasi"],
        "emoji": wording["emoji"],
    }
