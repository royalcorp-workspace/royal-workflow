"""
e-Meterai Integration Service Package.
Vendor-agnostic electronic stamp service with EzMeterai and Mock adapters.
"""

from __future__ import annotations

import logging
from typing import Optional

from django.conf import settings

from .base import (
    BaseMeteraiProvider,
    QuotaResult,
    StampingResult,
    StatusResult,
    UploadResult,
)
from .ezmeterai import EzMeteraiProvider
from .mock import MockMeteraiProvider
from .service import EMeteraiService

logger = logging.getLogger(__name__)

_PROVIDER_REGISTRY = {
    "ezmeterai": EzMeteraiProvider,
    "mock": MockMeteraiProvider,
}


def get_meterai_provider(provider_name: Optional[str] = None) -> BaseMeteraiProvider:
    """
    Factory helper to resolve active e-Meterai provider based on configuration.
    Defaults to settings.EMATERAI_PROVIDER or 'mock'.
    """
    selected = (
        provider_name
        or getattr(settings, "EMATERAI_PROVIDER", "mock")
    ).lower().strip()

    provider_cls = _PROVIDER_REGISTRY.get(selected)
    if not provider_cls:
        logger.warning(
            "Unknown EMATERAI_PROVIDER '%s'. Falling back to 'mock'.",
            selected,
        )
        provider_cls = MockMeteraiProvider

    return provider_cls()


__all__ = [
    "BaseMeteraiProvider",
    "EzMeteraiProvider",
    "MockMeteraiProvider",
    "EMeteraiService",
    "get_meterai_provider",
    "UploadResult",
    "StampingResult",
    "QuotaResult",
    "StatusResult",
]
