"""
User Data Source

Provides access to Django User model fields and related profile data.
"""

import logging
from typing import Any

from .base import DataSource

logger = logging.getLogger(__name__)


class UserDataSource(DataSource):
    """
    Data source for Django User model fields.

    Supports:
    - user.email
    - user.first_name
    - user.last_name
    - user.full_name
    - user.username
    - user.is_staff
    - user.is_active
    """

    def get_value(self, user, field_name: str, **kwargs) -> Any | None:
        """
        Get a value from the User model.

        Args:
            user: Django User object
            field_name: Field name (e.g., 'email', 'first_name')
            **kwargs: Unused

        Returns:
            The field value, or None if not found
        """
        if not user or not user.is_authenticated:
            return None

        try:
            # Handle special cases
            if field_name == "full_name":
                return f"{user.first_name} {user.last_name}".strip()

            # Get attribute from user model
            if hasattr(user, field_name):
                value = getattr(user, field_name)
                return value if value else None

            # Try to get from Royal employee profile if it exists
            if hasattr(user, "employee_profile"):
                profile = user.employee_profile

                # Specific field mappings for Workflow Wireframe & PRD
                if field_name in ["supervisor_name", "nama_atasan"]:
                    if profile.supervisor_1_name:
                        return profile.supervisor_1_name
                    if profile.supervisor_1:
                        return profile.supervisor_1.get_full_name() or profile.supervisor_1.username
                    return "Atasan Cabang"
                if field_name in ["department_pembuat", "dept_pembuat"]:
                    return profile.department or "Operasional Cabang"
                if field_name in ["bagian_pembuat", "posisi_pembuat"]:
                    return profile.position or "Kasir Cabang"
                if field_name in ["nama_kasir", "pemohon_nama"]:
                    return profile.full_name or f"{user.first_name} {user.last_name}".strip() or user.username
                if field_name in ["cabang", "branch"]:
                    return profile.branch or "Cabang Bandung"

                if hasattr(profile, field_name):
                    value = getattr(profile, field_name)
                    return value if value else None

            # Try to get from user profile if it exists
            if hasattr(user, "forms_profile"):
                profile = user.forms_profile
                if hasattr(profile, field_name):
                    value = getattr(profile, field_name)
                    return value if value else None

            logger.warning(f"User field not found: {field_name}")
            return None

        except Exception as e:
            logger.error(f"Error getting user field {field_name}: {e}")
            return None

    def is_available(self) -> bool:
        """User data source is always available."""
        return True

    def get_display_name(self) -> str:
        return "User Profile"
