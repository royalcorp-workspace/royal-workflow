"""
Mock provider for local development, CI tests, and dry-run simulations.
Consumes 0 external quota and works without internet connectivity.
"""

from __future__ import annotations

import io
import logging
import uuid
from typing import Any, Dict

from .base import (
    BaseMeteraiProvider,
    QuotaResult,
    StampingResult,
    StatusResult,
    UploadResult,
)

logger = logging.getLogger(__name__)


class MockMeteraiProvider(BaseMeteraiProvider):
    """
    Mock implementation of BaseMeteraiProvider.
    Maintains an in-memory document store to simulate upload, stamping, and download flows.
    """

    def __init__(self, initial_quota: int = 30) -> None:
        self.documents: Dict[str, bytes] = {}
        self.quota = initial_quota

    def upload_document(self, pdf_bytes: bytes, filename: str) -> UploadResult:
        logger.info("[MOCK e-Meterai] Uploading document: %s (%d bytes)", filename, len(pdf_bytes))
        file_key = f"mock_file_{uuid.uuid4().hex[:12]}"
        self.documents[file_key] = pdf_bytes
        return UploadResult(
            success=True,
            file_key=file_key,
            message="Mock upload successful (no network call)",
            raw_response={"file_key": file_key, "status": "UPLOADED"},
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
        logger.info(
            "[MOCK e-Meterai] Stamping doc '%s' on page %d at (%.1f, %.1f) - (%.1f, %.1f)",
            file_key,
            page_number,
            llx,
            lly,
            urx,
            ury,
        )
        if file_key not in self.documents:
            return StampingResult(
                success=False,
                document_id=file_key,
                status="failed",
                message=f"Document '{file_key}' not found in mock store",
            )

        if self.quota <= 0:
            return StampingResult(
                success=False,
                document_id=file_key,
                status="failed",
                message="Mock quota exhausted (0 remaining)",
            )

        self.quota -= 1
        original_bytes = self.documents[file_key]
        stamped_id = f"stamped_{file_key}"

        # Visually stamp the mockup e-meterai onto PDF bytes
        stamped_bytes = original_bytes
        try:
            import os
            from pypdf import PdfReader, PdfWriter
            from reportlab.pdfgen import canvas
            from django.conf import settings

            reader = PdfReader(io.BytesIO(original_bytes))
            writer = PdfWriter()
            num_pages = len(reader.pages)
            target_idx = (page_number - 1) if (0 <= page_number - 1 < num_pages) else (num_pages - 1)

            img_candidates = [
                os.path.join(settings.BASE_DIR, "static", "images", "ematerai_mockup.png"),
                os.path.join(settings.BASE_DIR, "django_forms_workflows", "static", "django_forms_workflows", "img", "ematerai_mockup.png"),
            ]
            img_path = next((p for p in img_candidates if os.path.exists(p)), None)

            for idx, p in enumerate(reader.pages):
                if idx == target_idx and img_path:
                    pw = float(p.mediabox.width)
                    ph = float(p.mediabox.height)
                    stamp_buf = io.BytesIO()
                    sc = canvas.Canvas(stamp_buf, pagesize=(pw, ph))
                    # Stamping coordinates
                    w_stamp = max(10.0, urx - llx)
                    h_stamp = max(10.0, ury - lly)
                    sc.drawImage(img_path, llx, lly, width=w_stamp, height=h_stamp, mask='auto')
                    sc.save()
                    stamp_buf.seek(0)
                    stamp_reader = PdfReader(stamp_buf)
                    p.merge_page(stamp_reader.pages[0])
                writer.add_page(p)

            out_buf = io.BytesIO()
            writer.write(out_buf)
            stamped_bytes = out_buf.getvalue()
        except Exception as stamp_err:
            logger.warning("[MOCK e-Meterai] Could not visually stamp PDF bytes (%s), using original bytes", stamp_err)
            stamped_bytes = original_bytes

        # Store stamped bytes
        self.documents[stamped_id] = stamped_bytes

        return StampingResult(
            success=True,
            document_id=stamped_id,
            status="success",
            message=f"Mock stamping successful. Remaining mock quota: {self.quota}",
            stamped_pdf_bytes=stamped_bytes,
            raw_response={
                "document_id": stamped_id,
                "status": "COMPLETED",
                "page": page_number,
                "coordinates": {"llx": llx, "lly": lly, "urx": urx, "ury": ury},
                "remaining_quota": self.quota,
            },
        )

    def check_status(self, document_id: str) -> StatusResult:
        logger.info("[MOCK e-Meterai] Checking status of doc: %s", document_id)
        if document_id in self.documents:
            return StatusResult(
                success=True,
                status="completed",
                document_id=document_id,
                message="Mock document is stamped and ready for download",
                download_url=f"/mock/download/{document_id}",
                raw_response={"status": "COMPLETED", "document_id": document_id},
            )
        return StatusResult(
            success=False,
            status="failed",
            document_id=document_id,
            message=f"Document {document_id} not found in mock store",
        )

    def download_stamped_document(self, document_id: str) -> bytes:
        logger.info("[MOCK e-Meterai] Downloading stamped doc: %s", document_id)
        if document_id in self.documents:
            return self.documents[document_id]
        raise ValueError(f"Document {document_id} not found in mock store")

    def get_quota_balance(self) -> QuotaResult:
        logger.info("[MOCK e-Meterai] Fetching quota balance: %d", self.quota)
        return QuotaResult(
            success=True,
            available_quota=self.quota,
            message="Mock quota retrieved successfully",
            raw_response={"quota": self.quota, "status": "ACTIVE"},
        )
