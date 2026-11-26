"""
Business logic, dynamic approval matrix evaluator, and review helper
for the 'Release Credit Limit' (release-credit-limit) workflow.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from django.db import models

from django_forms_workflows.services.branch_resolver import (
    branch_matches,
    resolve_submission_branch,
)

# Brand grouping for C1 (Credit Limit Hold) matrix
FOAM_BRAND_KEYWORDS = ("ROYAL", "FOAM", "CLASSIC", "GRAND", "NON WOVEN", "NON-WOVEN")

# Stage order constants
STAGE_ACCOUNTING = 1
STAGE_ASM = 2
STAGE_NSM = 3
STAGE_GM = 4

LEVEL_LABELS = {
    "ASM": "ASM / BM",
    "NSM": "NSM",
    "GM": "GM",
}


def parse_rupiah_amount(val: Any) -> int:
    """Parse an integer/float/Rupiah-formatted string (e.g. 'Rp 30.000.000') into int."""
    if val is None or val == "":
        return 0
    if isinstance(val, bool):
        return 0
    if isinstance(val, (int, float)):
        return max(0, int(val))
    s = str(val).strip()
    if not s:
        return 0
    # Strip Rp prefix, spaces, dots (thousand separators); handle decimal comma if present
    s = re.sub(r"(?i)rp\.?", "", s).strip()
    if "," in s and "." in s:
        # Assume Indonesian format 1.000.000,00
        s = s.split(",")[0]
    elif "," in s:
        parts = s.split(",")
        if len(parts[-1]) <= 2:
            s = parts[0]
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else 0


def format_rupiah_display(val: Any) -> str:
    """Format a numeric value as 'Rp 1.000.000'."""
    num = parse_rupiah_amount(val)
    return f"Rp {num:,}".replace(",", ".")


def classify_rcl_brand_category(brand: Optional[str]) -> tuple[str, str]:
    """Return (category_code, human_label) for a Release Credit Limit brand."""
    b_upper = str(brand or "").strip().upper()
    if any(k in b_upper for k in FOAM_BRAND_KEYWORDS):
        return "FOAM_NON_WOVEN", "Foam / Non Woven"
    return "NON_FOAM_SPRINGBED", "Non-Foam (Springbed)"


def normalize_jenis_hold(val: Optional[str]) -> str:
    """Normalize jenis_hold into 'C1', 'C2', or 'C1 + C2'."""
    raw = str(val or "").strip().upper()
    has_c1 = "C1" in raw
    has_c2 = "C2" in raw
    if has_c1 and has_c2:
        return "C1 + C2"
    if has_c2:
        return "C2"
    return "C1"


def evaluate_rcl_approval_matrix(form_data: Optional[dict]) -> dict:
    """Evaluate target final approver ('ASM', 'NSM', or 'GM') for Release Credit Limit."""
    fd = form_data or {}
    jenis_hold = normalize_jenis_hold(fd.get("jenis_hold"))
    brand = str(fd.get("brand") or "").strip()
    cat_code, cat_label = classify_rcl_brand_category(brand)
    total_so = parse_rupiah_amount(fd.get("total_so"))
    omzet = parse_rupiah_amount(fd.get("acc_rata_rata_omzet"))

    if jenis_hold in ("C2", "C1 + C2"):
        target_level = "GM"
        if jenis_hold == "C2":
            reason = "Jenis Hold C2 (TOP Hold) wajib melalui persetujuan penuh hingga GM."
        else:
            reason = "Jenis Hold C1 + C2 mengikuti aturan terketat (TOP Hold) sehingga wajib hingga GM."
    elif cat_code == "FOAM_NON_WOVEN":
        if total_so <= 30_000_000:
            target_level = "ASM"
            reason = "C1 Foam / Non Woven dengan Total SO <= Rp 30.000.000 berhenti di ASM / BM."
        elif total_so < 100_000_000:
            target_level = "NSM"
            reason = "C1 Foam / Non Woven dengan Total SO > Rp 30.000.000 s.d. < Rp 100.000.000 sampai NSM."
        else:
            target_level = "GM"
            reason = "C1 Foam / Non Woven dengan Total SO >= Rp 100.000.000 wajib hingga GM."
    else:
        # NON_FOAM_SPRINGBED
        if omzet <= 30_000_000:
            if total_so <= 5_000_000:
                target_level = "ASM"
                reason = "C1 Non-Foam (Omzet <= Rp 30 Jt, Total SO <= Rp 5 Jt) berhenti di ASM / BM."
            elif total_so <= 10_000_000:
                target_level = "NSM"
                reason = "C1 Non-Foam (Omzet <= Rp 30 Jt, Total SO Rp 5-10 Jt) sampai NSM."
            else:
                target_level = "GM"
                reason = "C1 Non-Foam (Omzet <= Rp 30 Jt, Total SO > Rp 10 Jt) wajib hingga GM."
        elif omzet < 50_000_000:
            if total_so <= 5_000_000:
                target_level = "ASM"
                reason = "C1 Non-Foam (Omzet Rp 30-50 Jt, Total SO <= Rp 5 Jt) berhenti di ASM / BM."
            elif total_so < 10_000_000:
                target_level = "NSM"
                reason = "C1 Non-Foam (Omzet Rp 30-50 Jt, Total SO Rp 5-10 Jt) sampai NSM."
            else:
                target_level = "GM"
                reason = "C1 Non-Foam (Omzet Rp 30-50 Jt, Total SO >= Rp 10 Jt) wajib hingga GM."
        else:
            # omzet >= 50_000_000
            if total_so <= 25_000_000:
                target_level = "ASM"
                reason = "C1 Non-Foam (Omzet >= Rp 50 Jt, Total SO <= Rp 25 Jt) berhenti di ASM / BM."
            elif total_so < 75_000_000:
                target_level = "NSM"
                reason = "C1 Non-Foam (Omzet >= Rp 50 Jt, Total SO Rp 25-75 Jt) sampai NSM."
            else:
                target_level = "GM"
                reason = "C1 Non-Foam (Omzet >= Rp 50 Jt, Total SO >= Rp 75 Jt) wajib hingga GM."

    if target_level == "ASM":
        required_levels = ["ACCOUNTING", "ASM"]
    elif target_level == "NSM":
        required_levels = ["ACCOUNTING", "ASM", "NSM"]
    else:
        required_levels = ["ACCOUNTING", "ASM", "NSM", "GM"]

    return {
        "jenis_hold_norm": jenis_hold,
        "product_category": cat_code,
        "product_category_label": cat_label,
        "total_so": total_so,
        "rata_rata_omzet": omzet,
        "target_final_level": target_level,
        "target_final_label": LEVEL_LABELS[target_level],
        "required_levels": required_levels,
        "matrix_reason": reason,
    }


def is_rcl_user_branch_eligible(user, submission, stage_order: Optional[int]) -> bool:
    """Enforce branch matching on Stage 1 (Accounting Cabang) & Stage 2 (ASM/BM)."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    if stage_order not in (STAGE_ACCOUNTING, STAGE_ASM):
        return True

    sub_branch = resolve_submission_branch(submission)
    if not sub_branch:
        return True

    ep = getattr(user, "employee_profile", None)
    user_branch = getattr(ep, "branch", None) if ep else None
    if not user_branch:
        # Service/test accounts without a branch profile remain eligible if assigned to group
        return True

    return branch_matches(sub_branch, user_branch)


def user_can_act_on_rcl_task(user, submission, task) -> bool:
    """Return True if user is authorized to act on the given Release Credit Limit task."""
    if not task or task.status != "pending":
        return False
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True

    form_def = submission.form_definition
    user_groups = user.groups.all()
    is_admin = user_groups.filter(id__in=form_def.admin_groups.all()).exists()
    if is_admin:
        return True

    is_direct = task.assigned_to_id == user.id
    is_group = bool(
        task.assigned_group_id and user_groups.filter(id=task.assigned_group_id).exists()
    )
    if not (is_direct or is_group):
        return False

    stage_order = (
        task.workflow_stage.order
        if task.workflow_stage_id and task.workflow_stage
        else task.stage_number
    )
    if is_direct:
        return True
    return is_rcl_user_branch_eligible(user, submission, stage_order)


def get_pending_rcl_task(submission):
    """Return the active pending ApprovalTask for a Release Credit Limit submission."""
    return (
        submission.approval_tasks.filter(status="pending")
        .select_related("workflow_stage", "assigned_group", "assigned_to")
        .order_by("stage_number", "id")
        .first()
    )


def get_rcl_review_context(user, submission, form_data: Optional[dict] = None) -> dict:
    """Build template & handler context for Release Credit Limit detail/review page."""
    fd = form_data if form_data is not None else (submission.form_data or {})
    pending_task = get_pending_rcl_task(submission)
    stage_order = None
    if pending_task:
        stage_order = (
            pending_task.workflow_stage.order
            if pending_task.workflow_stage_id and pending_task.workflow_stage
            else pending_task.stage_number
        )

    can_act_current = bool(
        pending_task
        and submission.status in ("pending_approval", "submitted")
        and user_can_act_on_rcl_task(user, submission, pending_task)
    )
    is_accounting_pending_actor = bool(
        can_act_current and stage_order == STAGE_ACCOUNTING
    )
    is_approver_pending_actor = bool(
        can_act_current and stage_order in (STAGE_ASM, STAGE_NSM, STAGE_GM)
    )

    acc_fields_present = any(
        fd.get(k) not in (None, "", "—")
        for k in (
            "acc_plafon_saat_ini",
            "acc_total_over_credit",
            "acc_open_order_amount",
            "acc_over_due",
            "acc_rata_rata_omzet",
        )
    )

    # Use stored matrix result if already evaluated by Accounting; otherwise evaluate live if omzet present
    stored_target = str(fd.get("rcl_target_final_level") or "").strip().upper()
    matrix = evaluate_rcl_approval_matrix(fd)
    if stored_target in LEVEL_LABELS:
        matrix["target_final_level"] = stored_target
        matrix["target_final_label"] = fd.get("rcl_target_final_label") or LEVEL_LABELS[stored_target]
        if fd.get("rcl_matrix_reason"):
            matrix["matrix_reason"] = fd.get("rcl_matrix_reason")

    # Determine status pill label for header
    if submission.status == "draft":
        rcl_status_badge = "Draft"
    elif submission.status == "needs_revision":
        rcl_status_badge = "Perlu Revisi"
    elif submission.status == "approved":
        rcl_status_badge = "Disetujui / Siap Release JDE"
    elif submission.status == "rejected":
        rcl_status_badge = "Ditolak"
    elif submission.status == "withdrawn":
        rcl_status_badge = "Ditarik"
    elif stage_order == STAGE_ACCOUNTING:
        rcl_status_badge = "Menunggu Review"
    elif stage_order == STAGE_ASM:
        rcl_status_badge = "Menunggu ASM / BM"
    elif stage_order == STAGE_NSM:
        rcl_status_badge = "Menunggu NSM"
    elif stage_order == STAGE_GM:
        rcl_status_badge = "Menunggu GM"
    else:
        rcl_status_badge = "Pending Approval"

    # Format accounting fields nicely for both input initial value and read-only view
    def _fmt_input(key: str) -> str:
        raw = fd.get(key)
        if raw in (None, "", "—"):
            return ""
        return f"{parse_rupiah_amount(raw):,}".replace(",", ".")

    def _fmt_ro(key: str) -> str:
        raw = fd.get(key)
        if raw in (None, "", "—"):
            return "—"
        return format_rupiah_display(raw)

    accounting_data = {
        "plafon_saat_ini_input": _fmt_input("acc_plafon_saat_ini"),
        "total_over_credit_input": _fmt_input("acc_total_over_credit"),
        "open_order_amount_input": _fmt_input("acc_open_order_amount"),
        "over_due_input": _fmt_input("acc_over_due"),
        "rata_rata_omzet_input": _fmt_input("acc_rata_rata_omzet"),
        "plafon_saat_ini_display": _fmt_ro("acc_plafon_saat_ini"),
        "total_over_credit_display": _fmt_ro("acc_total_over_credit"),
        "open_order_amount_display": _fmt_ro("acc_open_order_amount"),
        "over_due_display": _fmt_ro("acc_over_due"),
        "rata_rata_omzet_display": _fmt_ro("acc_rata_rata_omzet"),
        "reviewed_by": fd.get("acc_reviewed_by") or "",
        "reviewed_at": fd.get("acc_reviewed_at") or "",
        "has_values": acc_fields_present,
    }

    target_lvl = matrix.get("target_final_level", "GM")
    if stage_order == STAGE_ACCOUNTING:
        next_stage_preview_label = (
            f"Approval ASM / BM (Akhir: {matrix.get('target_final_label', target_lvl)})"
        )
    elif stage_order == STAGE_ASM:
        next_stage_preview_label = (
            "Disetujui Penuh (Siap Release JDE)"
            if target_lvl == "ASM"
            else "Approval NSM"
        )
    elif stage_order == STAGE_NSM:
        next_stage_preview_label = (
            "Disetujui Penuh (Siap Release JDE)"
            if target_lvl == "NSM"
            else "Approval GM"
        )
    elif stage_order == STAGE_GM:
        next_stage_preview_label = "Disetujui Penuh (Siap Release JDE)"
    else:
        next_stage_preview_label = ""

    raw_lamps = fd.get("lampiran_dokumen") or []
    if not isinstance(raw_lamps, list):
        raw_lamps = []
    lampiran_items = []
    for idx, item in enumerate(raw_lamps):
        if not isinstance(item, dict):
            continue
        fname = str(item.get("filename") or "").strip()
        fpath = str(item.get("path") or "").strip()
        ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else (fpath.rsplit(".", 1)[-1].lower() if "." in fpath else "")
        if ext in ("jpg", "jpeg", "png", "gif", "webp"):
            preview_kind = "image"
        elif ext in ("pdf", "txt", "csv"):
            preview_kind = "iframe"
        else:
            preview_kind = "unsupported"
        lampiran_items.append({
            "index": idx,
            "nama_lampiran": item.get("nama_lampiran") or "Lampiran",
            "filename": fname or "—",
            "path": fpath,
            "ext": ext.upper() if ext else "FILE",
            "preview_kind": preview_kind,
        })

    # Build simplified user-facing approval history rows:
    # - exclude internal/system "skipped" tasks
    # - coalesce parallel "pending" tasks in the same stage into one compact row
    all_tasks = list(
        submission.approval_tasks.select_related(
            "workflow_stage", "assigned_to", "assigned_group", "completed_by"
        )
        .prefetch_related("delegations__delegated_to", "delegations__delegated_by")
        .order_by("created_at", "id")
    )
    history_rows = []
    pending_stage_map = {}
    for task in all_tasks:
        if task.status == "skipped":
            continue
        if task.status == "pending":
            stage_key = (task.workflow_stage_id, task.stage_number)
            if task.assigned_to:
                actor_name = task.assigned_to.get_full_name() or task.assigned_to.username
            elif task.assigned_group:
                actor_name = task.assigned_group.name
            else:
                actor_name = "Reviewer"

            if stage_key in pending_stage_map:
                entry = pending_stage_map[stage_key]
                if actor_name not in entry["pending_actors"]:
                    entry["pending_actors"].append(actor_name)
                    entry["pending_actors_text"] = ", ".join(entry["pending_actors"])
                    entry["is_multi_group"] = len(entry["pending_actors"]) > 1
            else:
                entry = {
                    "is_pending_merged": True,
                    "task": task,
                    "pending_actors": [actor_name],
                    "pending_actors_text": actor_name,
                    "is_multi_group": False,
                }
                pending_stage_map[stage_key] = entry
                history_rows.append(entry)
        else:
            history_rows.append({
                "is_pending_merged": False,
                "task": task,
                "pending_actors": [],
                "pending_actors_text": "",
                "is_multi_group": False,
            })

    return {
        "pending_task": pending_task,
        "stage_order": stage_order,
        "is_accounting_pending_actor": is_accounting_pending_actor,
        "is_approver_pending_actor": is_approver_pending_actor,
        "can_act_current": can_act_current,
        "accounting_data": accounting_data,
        "matrix": matrix,
        "rcl_status_badge": rcl_status_badge,
        "next_stage_preview_label": next_stage_preview_label,
        "lampiran_items": lampiran_items,
        "history_rows": history_rows,
    }

