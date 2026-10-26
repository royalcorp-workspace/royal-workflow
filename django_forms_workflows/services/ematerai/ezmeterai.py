"""
EzMeterai REST API Adapter for single stamping.
Documentation & Sandbox: https://api-sandbox.ezmeterai.id / https://sandbox.ezmeterai.id
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import requests
from django.conf import settings

from .base import (
    BaseMeteraiProvider,
    QuotaResult,
    StampingResult,
    StatusResult,
    UploadResult,
)

logger = logging.getLogger(__name__)


class EzMeteraiProvider(BaseMeteraiProvider):
    """
    Adapter implementation for EzMeterai API (Production and Sandbox).
    Handles authentication via `x-api-key` header and communicates with EzMeterai endpoints.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 45,
    ) -> None:
        self.base_url = (
            base_url
            or getattr(settings, "EMATERAI_BASE_URL", "https://api-sandbox.ezmeterai.id")
        ).rstrip("/")
        self.api_key = api_key or getattr(settings, "EMATERAI_API_KEY", "")
        self.timeout = timeout

    def _get_headers(self, content_type: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "x-api-key": self.api_key,
            "Accept": "application/json",
        }
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def upload_document(self, pdf_bytes: bytes, filename: str) -> UploadResult:
        """
        Upload raw PDF document to EzMeterai:
        POST /v2/doc/upload
        Headers: x-api-key
        Files: {'file': (filename, pdf_bytes, 'application/pdf')}
        """
        url = f"{self.base_url}/v2/doc/upload"
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/pdf",
        }

        logger.info("[EzMeterai] Uploading document '%s' (%d bytes) to %s", filename, len(pdf_bytes), url)

        try:
            response = requests.post(
                url,
                headers=headers,
                data=pdf_bytes,
                timeout=self.timeout,
            )
            logger.info("[EzMeterai] Upload response status: %d", response.status_code)


            try:
                res_data = response.json()
            except Exception:
                res_data = {"raw_text": response.text}

            if response.status_code in (200, 201):
                # EzMeterai typically returns {"file_key": "..."} or {"data": {"file_key": "..."}}
                data = res_data.get("data", res_data)
                file_key = (
                    data.get("file_key")
                    or data.get("fileKey")
                    or data.get("id")
                    or data.get("document_id")
                    or ""
                )
                if not file_key and isinstance(res_data, dict):
                    file_key = res_data.get("file_key", "")

                if file_key:
                    return UploadResult(
                        success=True,
                        file_key=file_key,
                        message="Document successfully uploaded to EzMeterai",
                        raw_response=res_data,
                    )

            msg = res_data.get("message") or res_data.get("error") or response.text
            return UploadResult(
                success=False,
                file_key="",
                message=f"Upload failed (HTTP {response.status_code}): {msg}",
                raw_response=res_data,
            )

        except requests.RequestException as exc:
            logger.error("[EzMeterai] Network error during document upload: %s", exc)
            return UploadResult(
                success=False,
                file_key="",
                message=f"Network error during upload: {str(exc)}",
            )

    def stamp_document(
        self,
        file_key: str,
        page_number: int,
        llx: float,
        lly: float,
        urx: float,
        ury: float,
        **kwargs: Any,
    ) -> StampingResult:
        """
        Execute e-Meterai stamping on the uploaded document:
        POST /v1/doc/stamp
        Headers: x-api-key, Content-Type: application/json
        Payload: {
            "file": file_key,
            "external_id": external_id,
            "items": [
                {"page": page_number, "llx": ..., "lly": ..., "urx": ..., "ury": ...}
            ]
        }
        """
        import re
        import time

        url = f"{self.base_url}/v1/doc/stamp"
        headers = self._get_headers(content_type="application/json")

        raw_ext_id = kwargs.get("external_id") or f"SPK_{int(time.time())}"
        clean_ext_id = re.sub(r"[^a-zA-Z0-9_-]", "_", str(raw_ext_id))

        item = {
            "page": int(page_number),
            "product_id": int(kwargs.get("product_id", 1)),
            "bbox": {
                "llx": int(round(float(llx))),
                "lly": int(round(float(lly))),
                "urx": int(round(float(urx))),
                "ury": int(round(float(ury))),
            },
        }
        payload = {
            "file": file_key,
            "external_id": clean_ext_id,
            "items": [item],
        }
        # Include optional metadata if provided
        for k, v in kwargs.items():
            if k not in payload and v is not None and k not in ("product_id", "external_id"):
                payload[k] = v

        logger.info(
            "[EzMeterai] Requesting stamping for file '%s' (external_id: %s) on page %d with payload: %s",
            file_key,
            clean_ext_id,
            page_number,
            payload,
        )

        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            logger.info("[EzMeterai] Stamping response status: %d", response.status_code)

            try:
                res_data = response.json()
            except Exception:
                res_data = {"raw_text": response.text}

            if response.status_code in (200, 201):
                data = res_data.get("data", res_data)
                doc_id = (
                    data.get("external_id")
                    or data.get("document_id")
                    or clean_ext_id
                    or data.get("file_key")
                    or file_key
                )
                status = (
                    data.get("status")
                    or ("success" if response.status_code == 200 else "processing")
                ).lower()

                # If the stamp API directly returns binary or download url, or marks it done:
                return StampingResult(
                    success=True,
                    document_id=doc_id,
                    status=status,
                    message=res_data.get("message", "Stamping request accepted"),
                    raw_response=res_data,
                )


            msg = res_data.get("message") or res_data.get("error") or response.text
            return StampingResult(
                success=False,
                document_id=file_key,
                status="failed",
                message=f"Stamping failed (HTTP {response.status_code}): {msg}",
                raw_response=res_data,
            )

        except requests.RequestException as exc:
            logger.error("[EzMeterai] Network error during stamping: %s", exc)
            return StampingResult(
                success=False,
                document_id=file_key,
                status="failed",
                message=f"Network error during stamping: {str(exc)}",
            )

    def check_status(self, document_id: str) -> StatusResult:
        """
        Check document stamping status:
        GET /v2/doc/{document_id}/status or GET /v2/doc/{document_id}
        """
        # Try status endpoint first, fallback to detail
        url = f"{self.base_url}/v2/doc/{document_id}/status"
        headers = self._get_headers()

        try:
            response = requests.get(url, headers=headers, timeout=self.timeout)
            if response.status_code == 404:
                # Try alternate endpoint without /status
                url = f"{self.base_url}/v2/doc/{document_id}"
                response = requests.get(url, headers=headers, timeout=self.timeout)

            try:
                res_data = response.json()
            except Exception:
                res_data = {"raw_text": response.text}

            if response.status_code == 200:
                data = res_data.get("data", res_data)
                status_raw = str(data.get("status", "completed")).lower()
                status_normalized = (
                    "completed"
                    if status_raw in ("completed", "success", "stamped", "done")
                    else "processing"
                    if status_raw in ("processing", "in_progress", "pending")
                    else "failed"
                )
                return StatusResult(
                    success=True,
                    status=status_normalized,
                    document_id=document_id,
                    message=res_data.get("message", ""),
                    download_url=data.get("download_url"),
                    raw_response=res_data,
                )

            msg = res_data.get("message") or response.text
            return StatusResult(
                success=False,
                status="unknown",
                document_id=document_id,
                message=f"Status check failed (HTTP {response.status_code}): {msg}",
                raw_response=res_data,
            )

        except requests.RequestException as exc:
            return StatusResult(
                success=False,
                status="unknown",
                document_id=document_id,
                message=f"Network error checking status: {str(exc)}",
            )

    def download_stamped_document(self, document_id: str) -> bytes:
        """
        Download final stamped PDF bytes:
        GET /v2/doc/{document_id}/download
        Supports polling retry while stamping is in progress.
        """
        import time
        url = f"{self.base_url}/v2/doc/{document_id}/download"
        headers = {"x-api-key": self.api_key}

        logger.info("[EzMeterai] Downloading stamped document: %s", url)

        max_attempts = 6
        last_resp_text = ""
        for attempt in range(max_attempts):
            try:
                response = requests.get(url, headers=headers, timeout=60, stream=True)
                if response.status_code == 200:
                    content_type = response.headers.get("Content-Type", "")
                    if "application/pdf" in content_type or response.content.startswith(b"%PDF"):
                        return response.content

                    # Check if it returned a JSON containing a download URL
                    try:
                        data = response.json()
                        dl_url = data.get("download_url") or data.get("data", {}).get("download_url")
                        if dl_url:
                            dl_res = requests.get(dl_url, timeout=60)
                            if dl_res.status_code == 200 and dl_res.content.startswith(b"%PDF"):
                                return dl_res.content
                    except Exception:
                        pass

                    if response.content.startswith(b"%PDF"):
                        return response.content

                last_resp_text = response.text[:200]
                if response.status_code in (202, 404, 400, 425) and attempt < max_attempts - 1:
                    logger.info(
                        "[EzMeterai] Stamping in progress (HTTP %d, attempt %d/%d). Waiting 2.5s...",
                        response.status_code,
                        attempt + 1,
                        max_attempts,
                    )
                    time.sleep(2.5)
                    continue

                raise ValueError(
                    f"Download failed with HTTP {response.status_code}: {last_resp_text}"
                )

            except requests.RequestException as exc:
                if attempt < max_attempts - 1:
                    time.sleep(2)
                    continue
                logger.error("[EzMeterai] Error downloading stamped document: %s", exc)
                raise


    def get_quota_balance(self) -> QuotaResult:
        """
        Query available quota balance:
        GET /v1/quota or GET /v1/balance
        """
        endpoints_to_try = [
            f"{self.base_url}/v1/quota",
            f"{self.base_url}/v1/balance",
            f"{self.base_url}/v1/user/balance",
        ]
        headers = self._get_headers()

        last_error = ""
        for url in endpoints_to_try:
            try:
                response = requests.get(url, headers=headers, timeout=15)
                if response.status_code == 200:
                    try:
                        res_data = response.json()
                    except Exception:
                        continue

                    data = res_data.get("data", res_data)
                    quota_val = (
                        data.get("quota")
                        or data.get("balance")
                        or data.get("remaining")
                        or data.get("available_quota")
                    )
                    if quota_val is not None:
                        try:
                            quota_int = int(quota_val)
                            return QuotaResult(
                                success=True,
                                available_quota=quota_int,
                                message="Quota retrieved successfully",
                                raw_response=res_data,
                            )
                        except (ValueError, TypeError):
                            pass
                else:
                    last_error = f"HTTP {response.status_code}: {response.text[:100]}"
            except requests.RequestException as exc:
                last_error = str(exc)

        # If quota endpoint is not strictly documented or returns 404, report gracefully
        return QuotaResult(
            success=False,
            available_quota=0,
            message=f"Unable to query quota balance ({last_error})",
            raw_response={"error": last_error},
        )
