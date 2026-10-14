"""
Service layer for syncing employee data from Royal Corp HRIS API.
"""

import hashlib
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.utils import timezone

from django_forms_workflows.models import EmployeeProfile, UserProfile

logger = logging.getLogger(__name__)
User = get_user_model()


class EmployeeSyncService:
    """
    Syncs employee records from external Royal Corp HRIS API (employeesV2).
    
    Handles:
    1. Automated User provisioning (auth_user) with default password protection.
    2. Dynamic department and functional group assignment (auth_group).
    3. Hierarchical supervisor relationship mapping (L1 and L2).
    4. Synchronization bridge to UserProfile.manager for workflow routing.
    5. Hash-based idempotent skip detection and comprehensive dry-run support.
    """

    MANAGERIAL_KEYWORD_MAP = [
        (["ASM", "AREA SALES MANAGER", "SECTION HEAD"], "Sales Area Manager"),
        (["RSOM", "REGIONAL SALES OPERATION MANAGER", "REGIONAL SALES MANAGER"], "Sales Area Manager"),
        (["BRANCH MANAGER", "KEPALA CABANG"], "Branch Manager"),
        (["GENERAL MANAGER", "GM SALES"], "General Manager Sales"),
        (["DIRECTOR", "DIREKTUR"], "Commercial Director"),
        (["FINANCE HEAD", "FINANCE MANAGER"], "Finance Team"),
    ]

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_token: Optional[str] = None,
        timeout: Optional[int] = None,
        default_password: Optional[str] = None,
    ):
        self.api_url = api_url or getattr(
            settings,
            "HRIS_API_URL",
            "https://dev-api.royalcorp.co.id/api/v1/externalapi/employeesV2",
        )
        self.api_token = api_token or getattr(settings, "HRIS_API_TOKEN", "")
        self.timeout = timeout or getattr(settings, "HRIS_API_TIMEOUT", 30)
        self.default_password = default_password or getattr(
            settings, "HRIS_DEFAULT_PASSWORD", "Bandung*123#"
        )

    def fetch_employees_from_api(
        self, date_from: str = "2025-01-01", date_to: str = "2026-12-31"
    ) -> List[Dict[str, Any]]:
        """
        Calls HRIS external API with retries and returns employee list.
        """
        payload = {
            "from": date_from,
            "to": date_to,
            "internal": True,
            "active": True,
            "api_token": self.api_token,
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Royal-Workflow-Sync/1.0",
        }

        max_retries = 2
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                logger.info(
                    "Calling HRIS API: %s (attempt %d/%d)",
                    self.api_url,
                    attempt + 1,
                    max_retries + 1,
                )
                response = requests.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
                response.raise_for_status()

                data = response.json()
                if isinstance(data, dict):
                    return data.get("data", [])
                elif isinstance(data, list):
                    return data
                return []
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "HRIS API request attempt %d failed: %s", attempt + 1, exc
                )
                if attempt < max_retries:
                    time.sleep(2 * (attempt + 1))

        raise RuntimeError(
            f"Failed to fetch employee data from HRIS API after {max_retries + 1} attempts: {last_error}"
        )

    def _clean_string(self, val: Any) -> str:
        if val is None:
            return ""
        if isinstance(val, dict):
            return str(val.get("name") or val.get("nama") or "").strip()
        return str(val).strip()

    def _generate_username_from_name(self, name: str) -> str:
        """
        Generates standard username like 'first.last' from full name.
        Strips academic degrees and special characters.
        """
        cleaned = re.sub(r",\s*[a-zA-Z\.]+", "", name)
        cleaned = re.sub(r"[^a-zA-Z0-9\s]", "", cleaned).lower()
        parts = [p for p in cleaned.split() if p]
        if not parts:
            return "user"
        if len(parts) == 1:
            return parts[0]
        return f"{parts[0]}.{parts[1]}"

    def _build_atasan_lookup(
        self, records: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, str]]:
        """
        Builds a map from lower-cased full_name to username and email
        found across all atasan records in the payload.
        """
        lookup = {}
        for rec in records:
            atasan_data = rec.get("atasan") or {}
            emp_list = atasan_data.get("employee") or []
            for item in emp_list:
                user_info = item.get("user") or {}
                emp_info = item.get("employee") or {}
                fn = user_info.get("full_name") or emp_info.get("full_name") or ""
                fn_clean = fn.strip().lower()
                username = user_info.get("username") or ""
                work_email = emp_info.get("work_email") or ""
                if fn_clean and username:
                    lookup[fn_clean] = {
                        "username": username,
                        "work_email": work_email,
                        "full_name": fn.strip(),
                    }
        return lookup

    def _get_or_create_supervisor_user(
        self,
        username: str,
        full_name: str,
        work_email: str,
        dry_run: bool = False,
    ) -> Optional[User]:
        """
        Resolves or creates minimal supervisor User (Option A).
        """
        if not username:
            return None

        user = User.objects.filter(username=username).first()
        if user:
            return user

        if dry_run:
            # Return dummy/mock user object in dry-run mode
            return User(username=username, email=work_email)

        name_parts = full_name.strip().split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        user = User(
            username=username,
            email=work_email,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
        )
        user.set_password(self.default_password)
        user.save()
        logger.info("Created minimal User account for supervisor: %s", username)
        return user

    def _assign_groups(
        self, user: User, department: str, position: str, dry_run: bool = False
    ) -> List[str]:
        """
        Assigns user to department group and functional managerial group.
        """
        assigned_group_names = []

        # 1. Department Group (e.g. 'Sales And Marketing', 'Human Capital')
        if department:
            if not dry_run:
                dept_group, _ = Group.objects.get_or_create(name=department)
                user.groups.add(dept_group)
            assigned_group_names.append(department)

        # 2. Functional / Managerial Role Group (D1)
        pos_upper = position.upper()
        for keywords, target_group_name in self.MANAGERIAL_KEYWORD_MAP:
            if any(kw in pos_upper for kw in keywords):
                if not dry_run:
                    func_group, _ = Group.objects.get_or_create(name=target_group_name)
                    user.groups.add(func_group)
                assigned_group_names.append(target_group_name)
                break

        # 3. If position is Sales Staff (and not manager)
        if "SALES" in pos_upper and not any(kw in pos_upper for kw in ["MANAGER", "HEAD", "DIRECTOR", "ASM", "RSOM"]):
            target_group = "Sales Staff"
            if not dry_run:
                sales_group, _ = Group.objects.get_or_create(name=target_group)
                user.groups.add(sales_group)
            if target_group not in assigned_group_names:
                assigned_group_names.append(target_group)

        return assigned_group_names

    def sync_records(
        self,
        records: List[Dict[str, Any]],
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Processes a list of employee records and syncs them to the DB.
        """
        metrics = {
            "total_records": len(records),
            "users_created": 0,
            "users_updated": 0,
            "users_skipped": 0,
            "supervisors_created": 0,
            "supervisor_1_resolved": 0,
            "supervisor_2_resolved": 0,
            "groups_assigned": 0,
            "errors": [],
        }

        atasan_lookup = self._build_atasan_lookup(records)
        now = timezone.now()

        # Group pre-count for metrics
        groups_before = Group.objects.count()

        for idx, rec in enumerate(records):
            nik = str(rec.get("nik") or "").strip()
            nama = self._clean_string(rec.get("nama"))
            if not nik or not nama:
                metrics["errors"].append(f"Record #{idx}: missing NIK or Nama, skipped.")
                continue

            position = self._clean_string(rec.get("position"))
            department = self._clean_string(rec.get("department"))
            company = self._clean_string(rec.get("company"))
            branch = self._clean_string(rec.get("branch"))

            # Determine username & work_email
            username = ""
            work_email = ""

            if isinstance(rec.get("user"), dict):
                username = rec["user"].get("username") or ""
            elif rec.get("username"):
                username = str(rec["username"]).strip()

            if isinstance(rec.get("employee"), dict):
                work_email = rec["employee"].get("work_email") or ""
            elif rec.get("work_email"):
                work_email = str(rec["work_email"]).strip()

            # Fallback to atasan lookup if person is an atasan elsewhere
            if not username or not work_email:
                lookup_match = atasan_lookup.get(nama.lower())
                if lookup_match:
                    if not username:
                        username = lookup_match["username"]
                    if not work_email:
                        work_email = lookup_match["work_email"]

            # Fallback username from name
            if not username:
                username = self._generate_username_from_name(nama)

            # Fallback work_email
            if not work_email:
                work_email = f"{username}@mail.royalcorp.co.id"

            # Parse Atasan L1 & L2 (D4: index 0 is L1, index 1 is L2)
            atasan_list = (rec.get("atasan") or {}).get("employee") or []
            
            # L1
            l1_data = atasan_list[0] if len(atasan_list) > 0 else {}
            l1_u = l1_data.get("user") or {}
            l1_e = l1_data.get("employee") or {}
            l1_jd = l1_data.get("jobDetail") or {}
            l1_username = l1_u.get("username") or ""
            l1_name = l1_u.get("full_name") or l1_e.get("full_name") or ""
            l1_email = l1_e.get("work_email") or ""
            l1_pos = l1_jd.get("position") or ""

            # L2
            l2_data = atasan_list[1] if len(atasan_list) > 1 else {}
            l2_u = l2_data.get("user") or {}
            l2_e = l2_data.get("employee") or {}
            l2_jd = l2_data.get("jobDetail") or {}
            l2_username = l2_u.get("username") or ""
            l2_name = l2_u.get("full_name") or l2_e.get("full_name") or ""
            l2_email = l2_e.get("work_email") or ""
            l2_pos = l2_jd.get("position") or ""

            # Check Idempotency via SHA-256 hash
            hash_input = (
                f"{nik}|{nama}|{username}|{work_email}|{position}|"
                f"{department}|{company}|{branch}|{l1_username}|{l2_username}"
            )
            api_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

            existing_profile = EmployeeProfile.objects.filter(nik=nik).select_related("user").first()
            if existing_profile and existing_profile.raw_api_hash == api_hash:
                metrics["users_skipped"] += 1
                if existing_profile.supervisor_1:
                    metrics["supervisor_1_resolved"] += 1
                if existing_profile.supervisor_2:
                    metrics["supervisor_2_resolved"] += 1
                continue

            # Provision or retrieve main User
            name_parts = nama.split(" ", 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ""

            user = None
            if existing_profile:
                user = existing_profile.user
            else:
                user = User.objects.filter(username=username).first()

            user_created = False
            if not user:
                user_created = True
                if not dry_run:
                    user = User(
                        username=username,
                        email=work_email,
                        first_name=first_name,
                        last_name=last_name,
                        is_active=True,
                    )
                    user.set_password(self.default_password)
                    user.save()
                else:
                    user = User(username=username, email=work_email, first_name=first_name, last_name=last_name)
                metrics["users_created"] += 1
            else:
                # Update existing user attributes ONLY if changed (never overwrite password!)
                metrics["users_updated"] += 1
                if not dry_run:
                    updated = False
                    if user.email != work_email and work_email:
                        user.email = work_email
                        updated = True
                    if user.first_name != first_name and first_name:
                        user.first_name = first_name
                        updated = True
                    if user.last_name != last_name:
                        user.last_name = last_name
                        updated = True
                    if updated:
                        user.save(update_fields=["email", "first_name", "last_name"])

            # Provision supervisors (D2 - Option A)
            s1_user = None
            if l1_username:
                s1_exists = User.objects.filter(username=l1_username).exists()
                s1_user = self._get_or_create_supervisor_user(
                    l1_username, l1_name, l1_email, dry_run=dry_run
                )
                if not s1_exists and not dry_run:
                    metrics["supervisors_created"] += 1
                if s1_user:
                    metrics["supervisor_1_resolved"] += 1

            s2_user = None
            if l2_username:
                s2_exists = User.objects.filter(username=l2_username).exists()
                s2_user = self._get_or_create_supervisor_user(
                    l2_username, l2_name, l2_email, dry_run=dry_run
                )
                if not s2_exists and not dry_run:
                    metrics["supervisors_created"] += 1
                if s2_user:
                    metrics["supervisor_2_resolved"] += 1

            # Assign Groups (D1)
            assigned_groups = self._assign_groups(user, department, position, dry_run=dry_run)
            metrics["groups_assigned"] += len(assigned_groups)

            # Create / Update EmployeeProfile
            if not dry_run:
                if not existing_profile:
                    existing_profile = EmployeeProfile(user=user, nik=nik)

                existing_profile.full_name = nama
                existing_profile.position = position
                existing_profile.department = department
                existing_profile.company = company
                existing_profile.branch = branch
                existing_profile.work_email = work_email

                existing_profile.supervisor_1 = s1_user
                existing_profile.supervisor_1_name = l1_name
                existing_profile.supervisor_1_position = l1_pos

                existing_profile.supervisor_2 = s2_user
                existing_profile.supervisor_2_name = l2_name
                existing_profile.supervisor_2_position = l2_pos

                existing_profile.raw_api_hash = api_hash
                existing_profile.last_synced_at = now
                existing_profile.save()

                # Bridge to UserProfile.manager for existing workflow compatibility
                forms_profile, _ = UserProfile.objects.get_or_create(user=user)
                if s1_user:
                    forms_profile.manager = s1_user
                if department:
                    forms_profile.department = department
                if position:
                    forms_profile.title = position
                if nik:
                    forms_profile.employee_id = nik
                forms_profile.save()

        groups_after = Group.objects.count()
        metrics["groups_created"] = groups_after - groups_before if not dry_run else 0
        return metrics

    def run_sync(
        self,
        date_from: str = "2025-01-01",
        date_to: str = "2026-12-31",
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Orchestrates full sync process with atomic transaction.
        """
        start_time = time.time()
        records = self.fetch_employees_from_api(date_from=date_from, date_to=date_to)

        if dry_run:
            logger.info("Executing HRIS sync in DRY-RUN mode.")
            metrics = self.sync_records(records, dry_run=True)
        else:
            with transaction.atomic():
                metrics = self.sync_records(records, dry_run=False)

        metrics["duration_seconds"] = round(time.time() - start_time, 2)
        metrics["dry_run"] = dry_run
        return metrics
