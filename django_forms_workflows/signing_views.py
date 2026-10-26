"""
Public Signing Portal Views for External Store Partners (Stage 4 SPK).

Allows external signatories without Django user credentials to securely preview
and digitally sign contract drafts using an unguessable UUID-tokenized URL.
"""

from __future__ import annotations

import json
import logging
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import ContractSigningToken, DocumentTemplate, FormSubmission
from .workflow_engine import (
    process_external_toko_rejection,
    process_external_toko_signature,
)

logger = logging.getLogger(__name__)


def get_client_ip(request: HttpRequest) -> str | None:
    """Extract client IP address considering proxy headers."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


@require_http_methods(["GET"])
def public_spk_signing_view(request: HttpRequest, token: str) -> HttpResponse:
    """Render public signing portal or corresponding status page based on token state."""
    token_obj = get_object_or_404(
        ContractSigningToken.objects.select_related("submission", "submission__form_definition"),
        token=token,
    )
    submission = token_obj.submission

    # Status: Already signed -> Success confirmation page with full signed SPK preview
    if token_obj.status == "signed":
        form_def = submission.form_definition
        doc_template = form_def.document_templates.filter(is_active=True).first()
        rendered_spk_html = ""
        if doc_template:
            try:
                rendered_spk_html = doc_template.render(submission)
            except Exception as exc:
                logger.error("Error rendering SPK template on success page for token %s: %s", token, exc)
                rendered_spk_html = ""

        context = {
            "token_obj": token_obj,
            "submission": submission,
            "rendered_spk_html": rendered_spk_html,
            "page_title": "Dokumen Berhasil Ditandatangani",
        }
        return render(request, "django_forms_workflows/public_signing_success.html", context)

    # Status: Rejected/Returned -> Rejection status page
    if token_obj.status == "rejected":
        context = {
            "token_obj": token_obj,
            "submission": submission,
            "page_title": "Pengajuan Revisi Telah Dikirimkan",
        }
        return render(request, "django_forms_workflows/public_signing_status.html", context)

    # Status: Expired or Revoked -> Expiration notice page
    if token_obj.is_expired or token_obj.status in ("expired", "revoked"):
        context = {
            "token_obj": token_obj,
            "submission": submission,
            "page_title": "Tautan Kedaluwarsa",
        }
        return render(request, "django_forms_workflows/public_signing_expired.html", context)

    # Status: Pending -> Render active signing portal
    form_def = submission.form_definition
    if form_def.slug == "permohonan-kontrak":
        from .company_profiles import resolve_spk_document_template
        doc_template = resolve_spk_document_template(form_def, submission=submission)
    else:
        doc_template = form_def.document_templates.filter(is_active=True).first()

    rendered_spk_html = ""
    if doc_template:
        try:
            rendered_spk_html = doc_template.render(submission)
        except Exception as exc:
            logger.error("Error rendering SPK template for token %s: %s", token, exc)
            rendered_spk_html = f"<div class='alert alert-danger'>Gagal memuat draf: {exc}</div>"
    else:
        rendered_spk_html = "<div class='alert alert-warning'>Draf dokumen Surat Perjanjian Kerjasama belum tersedia.</div>"

    form_data = submission.form_data or {}
    nama_toko = form_data.get("nama_toko") or "Mitra Toko"
    nama_pemilik = form_data.get("nama_pemilik") or ""
    nomor_spk = form_data.get("nomor_spk") or f"SPK-SUB-{submission.id}"
    perusahaan = form_data.get("perusahaan") or "PT Royal Corp"
    cabang = form_data.get("cabang") or ""

    context = {
        "token_obj": token_obj,
        "submission": submission,
        "rendered_spk_html": rendered_spk_html,
        "nama_toko": nama_toko,
        "nama_pemilik": nama_pemilik,
        "nomor_spk": nomor_spk,
        "perusahaan": perusahaan,
        "cabang": cabang,
        "page_title": f"Penandatanganan SPK - {nama_toko}",
    }
    return render(request, "django_forms_workflows/public_signing_portal.html", context)


@require_http_methods(["POST"])
def public_spk_submit_signature(request: HttpRequest, token: str) -> HttpResponse:
    """Handle digital signature submission from the external store partner."""
    token_obj = get_object_or_404(
        ContractSigningToken.objects.select_related("submission", "submission__form_definition"),
        token=token,
    )

    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest" or request.content_type == "application/json"

    if not token_obj.is_valid:
        msg = "Tautan penandatanganan ini sudah tidak aktif atau telah kedaluwarsa."
        if is_ajax:
            return JsonResponse({"success": False, "error": msg}, status=400)
        return redirect(f"/spk/sign/{token}/")

    # Extract parameters (supports form-data or JSON payload)
    if request.content_type == "application/json":
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except Exception:
            payload = {}
        signature_data = payload.get("signature_data", "").strip()
        signer_name = payload.get("signer_name", "").strip()
        signer_title = payload.get("signer_title", "").strip()
        signer_identity = payload.get("signer_identity", "").strip()
    else:
        signature_data = request.POST.get("signature_data", "").strip()
        signer_name = request.POST.get("signer_name", "").strip()
        signer_title = request.POST.get("signer_title", "").strip()
        signer_identity = request.POST.get("signer_identity", "").strip()

    if not signature_data or not signature_data.startswith("data:image/"):
        msg = "Coretan tanda tangan digital wajib dibubuhkan sebelum mengirimkan dokumen."
        if is_ajax:
            return JsonResponse({"success": False, "error": msg}, status=400)
        return redirect(f"/spk/sign/{token}/")

    form_data = token_obj.submission.form_data or {}
    default_name = form_data.get("nama_pemilik") or "Pemilik Toko"
    final_signer_name = signer_name or default_name
    final_signer_title = signer_title or "Pemilik / Penanggung Jawab"

    ip_addr = get_client_ip(request)
    user_agent = request.META.get("HTTP_USER_AGENT", "")

    try:
        process_external_toko_signature(
            token=token_obj,
            signer_name=final_signer_name,
            signer_title=final_signer_title,
            signer_identity=signer_identity,
            signature_image_base64=signature_data,
            ip_address=ip_addr,
            user_agent=user_agent,
        )
    except Exception as exc:
        logger.exception("Failed to process external signature for token %s: %s", token, exc)
        if is_ajax:
            return JsonResponse({"success": False, "error": f"Terjadi kesalahan saat memproses tanda tangan: {exc}"}, status=500)
        return redirect(f"/spk/sign/{token}/")

    if is_ajax:
        return JsonResponse({"success": True, "redirect_url": f"/spk/sign/{token}/"})
    return redirect(f"/spk/sign/{token}/")


@require_http_methods(["POST"])
def public_spk_reject_view(request: HttpRequest, token: str) -> HttpResponse:
    """Handle contract rejection / revision request by the external store partner."""
    token_obj = get_object_or_404(
        ContractSigningToken.objects.select_related("submission", "submission__form_definition"),
        token=token,
    )

    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest" or request.content_type == "application/json"

    if not token_obj.is_valid:
        msg = "Tautan ini sudah tidak aktif atau telah kedaluwarsa."
        if is_ajax:
            return JsonResponse({"success": False, "error": msg}, status=400)
        return redirect(f"/spk/sign/{token}/")

    if request.content_type == "application/json":
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except Exception:
            payload = {}
        rejection_reason = payload.get("rejection_reason", "").strip()
        signer_name = payload.get("signer_name", "").strip()
        signer_title = payload.get("signer_title", "").strip()
    else:
        rejection_reason = request.POST.get("rejection_reason", "").strip()
        signer_name = request.POST.get("signer_name", "").strip()
        signer_title = request.POST.get("signer_title", "").strip()

    if not rejection_reason:
        msg = "Alasan penolakan / catatan revisi wajib diisi."
        if is_ajax:
            return JsonResponse({"success": False, "error": msg}, status=400)
        return redirect(f"/spk/sign/{token}/")

    ip_addr = get_client_ip(request)
    user_agent = request.META.get("HTTP_USER_AGENT", "")

    try:
        process_external_toko_rejection(
            token=token_obj,
            rejection_reason=rejection_reason,
            signer_name=signer_name,
            signer_title=signer_title,
            ip_address=ip_addr,
            user_agent=user_agent,
        )
    except Exception as exc:
        logger.exception("Failed to process external rejection for token %s: %s", token, exc)
        if is_ajax:
            return JsonResponse({"success": False, "error": f"Terjadi kesalahan saat memproses penolakan: {exc}"}, status=500)
        return redirect(f"/spk/sign/{token}/")

    if is_ajax:
        return JsonResponse({"success": True, "redirect_url": f"/spk/sign/{token}/"})
    return redirect(f"/spk/sign/{token}/")
