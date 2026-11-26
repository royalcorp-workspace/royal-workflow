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

import contextvars
import os
import re
from typing import Any
from urllib.parse import urlparse

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

_ACTIVE_REQUEST_BASE_URL: contextvars.ContextVar[str] = contextvars.ContextVar(
    "active_request_base_url", default=""
)


def set_active_request_base_url(url: str) -> contextvars.Token:
    """Bind the active HTTP request scheme://host for background notifications."""
    return _ACTIVE_REQUEST_BASE_URL.set((url or "").strip().rstrip("/"))


def reset_active_request_base_url(token: contextvars.Token) -> None:
    """Restore previous request base URL ContextVar."""
    _ACTIVE_REQUEST_BASE_URL.reset(token)


def get_active_request_base_url() -> str:
    """Return captured request scheme://host if running inside/from an HTTP request."""
    return (_ACTIVE_REQUEST_BASE_URL.get() or "").strip().rstrip("/")


def _is_loopback_url(url: str) -> bool:
    """Return True if URL points to localhost / 127.0.0.1 / ::1."""
    if not url:
        return False
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        host = ""
    return host in ("localhost", "127.0.0.1", "::1", "0.0.0.0")


def _resolve_base_url() -> str:
    """Resolve base URL dynamically for email/notification links.

    Priority:
    1. Explicit non-loopback env/settings URL
       (FORMS_WORKFLOWS_BASE_URL, SITE_BASE_URL, APP_BASE_URL, SITE_URL).
    2. Active HTTP request origin captured via ContextVar (propagated to threads).
    3. Explicit loopback env/settings URL if set without a non-loopback request.
    4. First valid origin in settings.CSRF_TRUSTED_ORIGINS.
    5. First non-wildcard, non-loopback host in settings.ALLOWED_HOSTS.
    6. Local fallback http://127.0.0.1:8069 (CLI/cron with no config).
    """
    explicit_candidates = [
        getattr(settings, "FORMS_WORKFLOWS_BASE_URL", None),
        getattr(settings, "SITE_BASE_URL", None),
        os.getenv("FORMS_WORKFLOWS_BASE_URL", ""),
        os.getenv("SITE_BASE_URL", ""),
        os.getenv("APP_BASE_URL", ""),
        os.getenv("SITE_URL", ""),
    ]
    explicit_url = ""
    for cand in explicit_candidates:
        val = str(cand or "").strip().rstrip("/")
        if val:
            explicit_url = val
            break

    if explicit_url and not _is_loopback_url(explicit_url):
        return explicit_url

    req_origin = get_active_request_base_url()
    if req_origin and (not explicit_url or not _is_loopback_url(req_origin)):
        return req_origin

    if explicit_url:
        return explicit_url

    origins = getattr(settings, "CSRF_TRUSTED_ORIGINS", None) or []
    for origin in origins:
        cleaned = str(origin or "").strip().rstrip("/")
        if cleaned and "*" not in cleaned:
            return cleaned

    allowed_hosts = getattr(settings, "ALLOWED_HOSTS", None) or []
    for host in allowed_hosts:
        h = str(host or "").strip()
        if not h or h == "*" or h.startswith("."):
            continue
        hostname = h.split(":")[0].lower()
        if hostname in ("localhost", "127.0.0.1", "::1", "testserver", "0.0.0.0"):
            continue
        is_ip = bool(re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", hostname))
        scheme = "http" if (is_ip or ":" in h) else "https"
        return f"{scheme}://{h}".rstrip("/")

    return "http://127.0.0.1:8069"


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
        # Fallback to submitter employee_profile branch/department or default
        submitter = getattr(submission, "submitter", None)
        ep = getattr(submitter, "employee_profile", None) if submitter else None
        unit_kerja = (
            getattr(ep, "branch", None)
            or getattr(ep, "department", None)
            or getattr(submitter, "branch", None)
            or getattr(submitter, "department", None)
            or "Kantor Pusat / Umum"
        )

    # Pemohon
    submitter = getattr(submission, "submitter", None)
    if submitter:
        pemohon = getattr(submitter, "get_full_name", lambda: "")() or getattr(submitter, "username", "Inisiator")
    else:
        pemohon = form_data.get("inisiator_nama") or "Inisiator"

    # Tujuan Pengajuan & Metadata Khusus Kontrak Toko / RCL
    form_slug = getattr(getattr(submission, "form_definition", None), "slug", "")
    extra_rows: list[tuple[str, str]] = []

    if form_slug == "release-credit-limit":
        nama_toko = (
            form_data.get("nama_toko")
            or form_data.get("nama_customer")
            or form_data.get("kode_customer_jde")
            or "Customer"
        )
        kode_jde = form_data.get("kode_customer_jde") or "-"
        jenis_hold = form_data.get("jenis_hold") or "C1"
        brand = form_data.get("brand") or "-"
        nomor_so = form_data.get("nomor_so") or "-"
        raw_total_so = str(form_data.get("total_so") or "0")
        digits_so = re.sub(r"[^\d]", "", raw_total_so)
        total_so_fmt = f"Rp {int(digits_so):,}".replace(",", ".") if digits_so else "Rp 0"
        tujuan_pengajuan = (
            f"Release Credit Limit ({jenis_hold}) untuk {nama_toko} (Kode JDE: {kode_jde}) "
            f"— Brand {brand}, No. SO {nomor_so}, Total SO {total_so_fmt}"
        )
        ket = str(form_data.get("keterangan") or "").strip()
        if ket and ket not in ("-", "—"):
            tujuan_pengajuan += f" | Catatan: {ket}"
    elif form_slug == "permohonan-kontrak":
        nama_toko = (
            form_data.get("nama_toko")
            or form_data.get("nama_dealer")
            or form_data.get("nama_customer")
            or "-"
        )
        nama_pemilik = form_data.get("nama_pemilik") or "-"
        jenis_kontrak = form_data.get("jenis_kontrak")
        if not jenis_kontrak:
            if form_data.get("chk_lampiran_spk_lalu") or "perpanjangan" in str(
                form_data.get("info_kontrak_lama", "")
            ).lower():
                jenis_kontrak = "Perpanjangan"
            else:
                jenis_kontrak = "Baru"
        brand = form_data.get("brand") or "-"
        area_val = str(form_data.get("area") or form_data.get("kota") or "").strip()
        cabang_val = str(cabang or "").strip()
        if cabang_val and area_val and cabang_val.lower() != area_val.lower():
            cabang_area = f"{cabang_val} / {area_val}"
        else:
            cabang_area = cabang_val or area_val or str(unit_kerja)

        # Resolve current workflow stage label cleanly
        sub_status = getattr(submission, "status", "")
        active_task = task
        if not active_task and getattr(submission, "id", None):
            try:
                active_task = (
                    submission.approval_tasks.filter(status="pending")
                    .select_related("workflow_stage")
                    .order_by("stage_number", "id")
                    .first()
                )
            except Exception:
                active_task = None

        stage_name_obj = getattr(getattr(active_task, "workflow_stage", None), "name", None)
        if sub_status == "approved":
            tahapan_saat_ini = "Disetujui Penuh (Final Approval Selesai)"
        elif sub_status == "rejected":
            tahapan_saat_ini = f"Ditolak ({stage_name_obj})" if stage_name_obj else "Ditolak"
        elif sub_status == "needs_revision":
            tahapan_saat_ini = f"Perlu Revisi ({stage_name_obj})" if stage_name_obj else "Perlu Revisi"
        elif sub_status == "withdrawn":
            tahapan_saat_ini = "Ditarik oleh Pemohon"
        elif active_task and getattr(active_task, "workflow_stage", None):
            ws = active_task.workflow_stage
            if getattr(ws, "order", None) == 4:
                is_signed = bool(form_data.get("ttd_toko_image"))
                if not is_signed and getattr(submission, "id", None):
                    try:
                        is_signed = submission.signing_tokens.filter(status="signed").exists()
                    except Exception:
                        is_signed = False
                tahapan_saat_ini = (
                    "Stage 4: Final Approval Direksi"
                    if is_signed
                    else "Gate 4: Menunggu TTD Mitra Toko"
                )
            else:
                tahapan_saat_ini = str(ws.name)
        else:
            tahapan_saat_ini = "Diajukan (Menunggu Review)"

        durasi_val = str(form_data.get("durasi") or "").strip()
        extra_note = str(
            form_data.get("tujuan_pengajuan")
            or form_data.get("tujuan")
            or form_data.get("keterangan")
            or form_data.get("catatan")
            or form_data.get("alasan_pengajuan")
            or ""
        ).strip()
        tujuan_pengajuan = (
            f"Pengajuan Kontrak Kerjasama ({jenis_kontrak}) untuk {nama_toko} "
            f"— Pemilik: {nama_pemilik}, Brand {brand}, Cabang/Area {cabang_area}"
        )
        if durasi_val and durasi_val not in ("-", "—"):
            tujuan_pengajuan += f", Durasi {durasi_val}"
        if extra_note and extra_note not in ("-", "—"):
            tujuan_pengajuan += f" | Catatan: {extra_note}"
        extra_rows = [
            ("No. SPK", str(nomor_pengajuan)),
            ("Nama Toko / Dealer", str(nama_toko)),
            ("Pemilik", str(nama_pemilik)),
            ("Jenis Kontrak", str(jenis_kontrak)),
            ("Cabang / Area", str(cabang_area)),
            ("Brand", str(brand)),
            ("Pemohon", str(pemohon)),
            ("Tahapan Saat Ini", str(tahapan_saat_ini)),
        ]
    else:
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
        "extra_rows": extra_rows,
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
            "action_title": "Review & Persetujuan",
            "action_button_label": "Review & Berikan Persetujuan",
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
            "action_title": "Pengingat Persetujuan",
            "action_button_label": "Review & Berikan Persetujuan",
        }

    elif event in ("workflow_approved", "stage_decision", "approval_notification"):
        is_rcl = getattr(getattr(submission, "form_definition", None), "slug", "") == "release-credit-limit"
        if is_rcl:
            return {
                "judul_notifikasi": "RELEASE CREDIT LIMIT DISETUJUI",
                "emoji": "✅",
                "event_message": "Pengajuan Release Credit Limit berikut telah disetujui penuh sesuai matriks hierarki.",
                "status_label": "Disetujui Sepenuhnya (Siap Release Credit Limit JDE)",
                "action_instruction": "Pengajuan telah disahkan secara resmi dan siap untuk proses release credit limit di JDE.",
                "action_title": "Detail Pengajuan",
                "action_button_label": "Lihat Detail Pengajuan",
            }
        return {
            "judul_notifikasi": "PENGAJUAN TELAH DISETUJUI",
            "emoji": "✅",
            "event_message": "Dokumen pengajuan berikut telah selesai diverifikasi dan resmi disetujui.",
            "status_label": "Disetujui Sepenuhnya",
            "action_instruction": "Dokumen telah disahkan secara resmi dan siap untuk ditindaklanjuti ke tahapan berikutnya.",
            "action_title": "Detail Pengajuan",
            "action_button_label": "Lihat Detail Pengajuan",
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
            "action_title": "Detail Pengajuan",
            "action_button_label": "Lihat Detail Pengajuan",
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
            "action_title": "Tindak Lanjut Revisi",
            "action_button_label": "Perbaiki Pengajuan Sekarang",
        }

    elif event == "escalation":
        return {
            "judul_notifikasi": "ESKALASI PERSETUJUAN",
            "emoji": "⚠️",
            "event_message": "Batas waktu persetujuan telah terlampaui sehingga dokumen ini dialihkan ke eskalasi berikutnya.",
            "status_label": "Menunggu Tindak Lanjut Eskalasi",
            "action_instruction": "Mohon segera menindaklanjuti dokumen eskalasi ini untuk mencegah keterlambatan operasional.",
            "action_title": "Review & Persetujuan",
            "action_button_label": "Review & Berikan Persetujuan",
        }

    elif event == "form_withdrawn":
        return {
            "judul_notifikasi": "PENGAJUAN DITARIK",
            "emoji": "↩️",
            "event_message": "Dokumen pengajuan berikut telah ditarik kembali oleh inisiator/pemohon.",
            "status_label": "Ditarik oleh Pemohon",
            "action_instruction": "Tidak diperlukan tindakan lebih lanjut untuk dokumen ini.",
            "action_title": "Detail Pengajuan",
            "action_button_label": "Lihat Detail Pengajuan",
        }

    else:
        # Default: submission_received / submission_created
        return {
            "judul_notifikasi": "PENGAJUAN BARU DITERIMA",
            "emoji": "📥",
            "event_message": "Pengajuan dokumen baru telah berhasil diserahkan ke dalam sistem Royal Workflow.",
            "status_label": "Diajukan (Menunggu Review)",
            "action_instruction": "Pengajuan Anda saat ini sedang dalam antrean proses review oleh pihak berwenang.",
            "action_title": "Detail Pengajuan",
            "action_button_label": "Lihat Detail Pengajuan",
        }


def get_notification_action_url(submission, task=None, event: str = "") -> str:
    """Build full absolute URL for the notification action/detail link."""
    base = _resolve_base_url()
    fdef = getattr(submission, "form_definition", None) if submission else None
    form_slug = getattr(fdef, "slug", "") if fdef else ""
    ev = (event or "").lower()
    if submission and getattr(submission, "status", "") == "needs_revision":
        if form_slug:
            step_qs = "&step=1" if form_slug == "permohonan-kontrak" else ""
            return f"{base}/forms/{form_slug}/submit/?revision={submission.id}{step_qs}"
    if ev in (
        "submission_received",
        "submission_created",
        "workflow_approved",
        "workflow_denied",
        "approval_notification",
        "rejection_notification",
        "form_withdrawn",
    ) and submission and getattr(submission, "id", None):
        try:
            rel = reverse("forms_workflows:submission_detail", args=[submission.id])
            return f"{base}{rel}"
        except Exception:
            return f"{base}/forms/submissions/{submission.id}/"
    if form_slug == "release-credit-limit" and submission and getattr(submission, "id", None):
        try:
            rel = reverse("forms_workflows:submission_detail", args=[submission.id])
            return f"{base}{rel}"
        except Exception:
            return f"{base}/forms/submissions/{submission.id}/"
    if task and getattr(task, "id", None):
        try:
            rel = reverse("forms_workflows:approve_submission", args=[task.id])
            return f"{base}{rel}"
        except Exception:
            return f"{base}/forms/approvals/{task.id}/approve/"
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
    action_url = custom_action_url or get_notification_action_url(submission, task=task, event=event)

    return {
        "submission": submission,
        "task": task,
        "approver": approver,
        "doc_info": doc_info,
        "event_message": wording["event_message"],
        "status_label": wording["status_label"],
        "action_instruction": wording["action_instruction"],
        "action_url": action_url,
        "action_title": wording.get("action_title", "Detail Pengajuan"),
        "action_button_label": wording.get("action_button_label", "Lihat Detail Pengajuan"),
        "judul_notifikasi": wording["judul_notifikasi"],
        "emoji": wording["emoji"],
    }


_STYLE_BLOCK_RE = re.compile(r"(<style\b[^>]*>.*?</style>)", re.DOTALL | re.IGNORECASE)
_SINGLE_BRACE_RE = re.compile(r"(?<!\{)\{([a-zA-Z_][a-zA-Z0-9_]*)\}(?!\})")


def _stringify_placeholder_value(val: Any) -> str:
    """Safely convert a form_data or system value to a string for email templates."""
    if val is None:
        return ""
    if isinstance(val, list):
        return ", ".join(str(item) for item in val if item is not None)
    if isinstance(val, dict):
        return str(val.get("label") or val.get("name") or val.get("value") or "")
    return str(val)


def build_notification_placeholders(
    submission,
    task=None,
    approver=None,
    comments: str = "",
    action_url: str = "",
    site_name: str = "",
) -> dict[str, str]:
    """
    Build a unified flat dictionary of string placeholders from submission.form_data,
    workflow/task metadata, and system attributes for safe interpolation into
    both email subject_template and body_template strings.
    """
    form_data = getattr(submission, "form_data", None) or {}
    if not isinstance(form_data, dict):
        form_data = {}

    placeholders: dict[str, str] = {}
    for k, v in form_data.items():
        placeholders[str(k)] = _stringify_placeholder_value(v)

    # Smart aliases & fallbacks for common contract & workflow fields
    nama_toko = (
        placeholders.get("nama_toko")
        or placeholders.get("nama_pemilik")
        or placeholders.get("kode_customer_jde")
        or "Mitra Toko"
    )
    placeholders["nama_toko"] = nama_toko
    placeholders.setdefault("nama_pemilik", placeholders.get("nama_pemilik") or nama_toko)

    sub_id_str = str(getattr(submission, "id", "") or "")
    nomor_spk = (
        placeholders.get("nomor_spk")
        or placeholders.get("no_pengajuan")
        or placeholders.get("nomor_pengajuan")
        or (f"#{sub_id_str}" if sub_id_str else "")
    )
    placeholders["nomor_spk"] = nomor_spk
    placeholders.setdefault("nomor_pengajuan", nomor_spk)
    placeholders.setdefault("no_pengajuan", nomor_spk)

    # Date formatting
    dt_val = getattr(submission, "submitted_at", None) or getattr(submission, "created_at", None)
    if dt_val:
        try:
            dt_local = timezone.localtime(dt_val)
            tanggal_str = dt_local.strftime("%d %b %Y %H:%M")
        except Exception:
            tanggal_str = str(dt_val)
    else:
        tanggal_str = ""
    placeholders.setdefault("tanggal_pengajuan", tanggal_str)
    placeholders.setdefault("submitted_at", tanggal_str)

    # Form & submission system attributes
    fdef = getattr(submission, "form_definition", None)
    placeholders["form_name"] = str(getattr(fdef, "name", "") or "")
    placeholders["form_slug"] = str(getattr(fdef, "slug", "") or "")
    placeholders["submission_id"] = sub_id_str
    placeholders["status"] = str(getattr(submission, "status", "") or "")
    try:
        placeholders["status_display"] = str(submission.get_status_display())
    except Exception:
        placeholders["status_display"] = placeholders["status"]

    # Submitter info
    submitter = getattr(submission, "submitter", None)
    if submitter:
        sub_name = getattr(submitter, "get_full_name", lambda: "")() or getattr(submitter, "username", "")
        sub_email = getattr(submitter, "email", "") or ""
    else:
        sub_name = placeholders.get("inisiator_nama") or "Inisiator"
        sub_email = ""
    placeholders["submitter"] = sub_name
    placeholders["submitter_name"] = sub_name
    placeholders["submitter_email"] = sub_email

    # Stage & task info
    stage_name = ""
    task_comments = ""
    if task:
        ws = getattr(task, "workflow_stage", None)
        stage_name = (getattr(ws, "name", None) or getattr(task, "step_name", "") or "")
        task_comments = getattr(task, "comments", "") or ""
    placeholders["stage_name"] = str(stage_name)
    placeholders["comments"] = str(comments or task_comments or "")

    # Approver info
    if approver:
        app_name = getattr(approver, "get_full_name", lambda: "")() or getattr(approver, "username", "")
    else:
        app_name = ""
    placeholders["approver"] = str(app_name)
    placeholders["approver_name"] = str(app_name)

    # URLs & site name
    resolved_url = action_url or get_notification_action_url(submission, task=task)
    placeholders["action_url"] = resolved_url
    placeholders["approval_url"] = resolved_url
    placeholders["submission_url"] = resolved_url
    if site_name:
        placeholders["site_name"] = site_name
    else:
        fw_settings = getattr(settings, "FORMS_WORKFLOWS", {})
        placeholders["site_name"] = fw_settings.get("SITE_NAME", "Royal Workflow")

    return placeholders


def interpolate_single_brace_placeholders(text: str, placeholders: dict[str, str]) -> str:
    """
    Safely replace single-brace ``{identifier}`` placeholders in ``text`` using
    ``placeholders``, while:
    1. Leaving ``<style>...</style>`` CSS blocks untouched.
    2. Leaving double-brace ``{{ ... }}`` Django template tags untouched.
    3. Replacing any missing/unknown ``{identifier}`` with ``""`` so no raw
       placeholder ever leaks to an email recipient.
    """
    if not text:
        return ""

    def _replace_match(match: re.Match) -> str:
        key = match.group(1)
        return str(placeholders.get(key, ""))

    parts = _STYLE_BLOCK_RE.split(text)
    for i in range(0, len(parts), 2):
        parts[i] = _SINGLE_BRACE_RE.sub(_replace_match, parts[i])
    return "".join(parts)

