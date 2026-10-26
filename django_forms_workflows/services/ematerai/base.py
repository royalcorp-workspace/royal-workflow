"""
Base abstraction layer for e-Meterai providers.
Supports vendor-agnostic e-Meterai integration with single stamping flow.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class UploadResult:
    success: bool
    file_key: str = ""
    message: str = ""
    raw_response: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StampingResult:
    success: bool
    document_id: str = ""
    status: str = ""  # 'success', 'processing', 'failed'
    message: str = ""
    stamped_pdf_bytes: Optional[bytes] = None
    raw_response: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QuotaResult:
    success: bool
    available_quota: int = 0
    message: str = ""
    raw_response: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StatusResult:
    success: bool
    status: str = ""  # 'pending', 'processing', 'completed', 'failed'
    document_id: str = ""
    message: str = ""
    download_url: Optional[str] = None
    raw_response: Dict[str, Any] = field(default_factory=dict)


class BaseMeteraiProvider(ABC):
    """
    Abstract interface for e-Meterai stamping providers.
    All provider adapters (EzMeterai, Privy, Peruri, Mock, etc.) must implement this interface.
    """

    @abstractmethod
    def upload_document(self, pdf_bytes: bytes, filename: str) -> UploadResult:
        """
        Upload raw PDF document to provider storage.
        Returns UploadResult with file_key needed for subsequent stamping.
        """
        pass

    @abstractmethod
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
        Execute e-Meterai stamping on the uploaded document at the given coordinates.
        Coordinates follow standard PDF points (lower-left: llx, lly; upper-right: urx, ury).
        """
        pass

    @abstractmethod
    def check_status(self, document_id: str) -> StatusResult:
        """
        Check the status of a stamping job.
        """
        pass

    @abstractmethod
    def download_stamped_document(self, document_id: str) -> bytes:
        """
        Download the final stamped PDF bytes from the provider.
        """
        pass

    @abstractmethod
    def get_quota_balance(self) -> QuotaResult:
        """
        Check available e-Meterai quota balance from provider account.
        """
        pass
