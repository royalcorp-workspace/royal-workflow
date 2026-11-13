"""
Branch and Regional Routing Resolver for Royal Workflow.

Universal service that applies across ALL forms and workflows in the system.
Ensures that approval notifications and task allocations are strictly scoped to the
relevant branch, preventing accidental nationwide blast emails across HRMS
employee records when Super Admin or regional staff submit forms.
"""

import logging
from typing import Optional, Union
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()

# Central corporate keywords (holding / head office oversight)
CENTRAL_KEYWORDS = (
    "direksi",
    "commercial director",
    "director",
    "direktur",
    "general manager",
    "gm",
    "pic pusat",
    "atasan pic pusat",
    "head of division",
    "finance",
    "accounting",
    "sales support",
    "legal",
    "it lead",
    "devops",
    "head of it",
    "system security",
    "administrator",
    "mis",
    "pusat",
    "holding",
    "head office",
    "kantor pusat",
    "audit",
    "procurement",
    "purchasing",
)

# Regional / branch-scoped keywords
REGIONAL_KEYWORDS = (
    "cabang",
    "area",
    "region",
    "regional",
    "wilayah",
    "rayon",
    "distrik",
    "asm",
    "rsom",
    "bom",
    "kasir cabang",
    "atasan cabang",
    "manager cabang",
    "kepala cabang",
    "sales cabang",
    "sales staff",
)


def normalize_branch_slug(name: Optional[str]) -> str:
    """Normalize branch string into a canonical lowercase token for comparison.

    Examples:
        'Cabang Bandung' -> 'bandung'
        'Kantor Cabang Bandung' -> 'bandung'
        'Cabang Denpasar' -> 'bali'
        'Bali' -> 'bali'
        'Cabang Surabaya' -> 'surabaya'
        'Kantor Pusat / Holding' -> 'pusat'
        'Kantor Pusat Bandung' -> 'pusat'
        'Pusat' -> 'pusat'
    """
    if not name:
        return ""
    s = str(name).strip().lower()
    for prefix in (
        "kantor cabang ",
        "cabang ",
        "kantor pusat ",
        "holding / ",
        "holding ",
        "unit kerja ",
        "unit ",
    ):
        if s.startswith(prefix):
            s = s[len(prefix) :].strip()

    if "denpasar" in s or "bali" in s:
        return "bali"
    if any(k in s for k in ("pusat", "holding", "head office", "kantor pusat")):
        return "pusat"
    return s


def is_central_branch(branch_name: Optional[str]) -> bool:
    """Check if branch name designates headquarters / central holding."""
    if not branch_name:
        return True
    norm = normalize_branch_slug(branch_name)
    return norm == "pusat" or any(k in str(branch_name).lower() for k in ("pusat", "holding", "head office"))


def is_central_group(group_name_or_obj) -> bool:
    """Check if an auth.Group represents a central / corporate approval role."""
    name = (
        group_name_or_obj.name
        if hasattr(group_name_or_obj, "name")
        else str(group_name_or_obj or "")
    ).strip().lower()

    # If it contains explicitly "cabang" or "area" without "pusat" / "holding", it's regional
    if any(k in name for k in ("cabang", "area", "distrik", "rayon")) and not any(
        k in name for k in ("kantor pusat", "holding", "pic pusat", "pusat")
    ):
        return False

    return any(k in name for k in CENTRAL_KEYWORDS)


def is_branch_scoped_group(group_name_or_obj) -> bool:
    """Check if an auth.Group represents a regional / branch-specific role."""
    name = (
        group_name_or_obj.name
        if hasattr(group_name_or_obj, "name")
        else str(group_name_or_obj or "")
    ).strip().lower()

    if any(k in name for k in ("kantor pusat", "holding", "pic pusat", "direksi", "corporate")):
        return False

    return any(k in name for k in REGIONAL_KEYWORDS)


def branch_matches(sub_branch: Optional[str], user_branch: Optional[str]) -> bool:
    """Check whether a user's branch matches the target submission branch."""
    if not sub_branch:
        return True
    if not user_branch:
        return False

    norm_sub = normalize_branch_slug(sub_branch)
    norm_user = normalize_branch_slug(user_branch)

    if not norm_sub:
        return True
    if norm_sub == norm_user:
        return True
    if norm_sub in norm_user or norm_user in norm_sub:
        return True
    return False


def resolve_submission_branch(submission, form_data: Optional[dict] = None) -> Optional[str]:
    """Universally extract the effective branch associated with any submission.

    Checks:
    1. Standard form_data keys: cabang, branch, unit_kerja, nama_cabang, etc.
    2. Dynamic form_data keys containing 'cabang' or 'branch' (excluding bank branches).
    3. Submitter's EmployeeProfile branch.
    """
    fd = form_data if form_data is not None else (getattr(submission, "form_data", None) or {})
    if isinstance(fd, dict):
        # 1. Standard priority keys
        for key in (
            "cabang",
            "branch",
            "unit_kerja",
            "nama_cabang",
            "cabang_pemohon",
            "kantor_cabang",
            "lokasi_cabang",
            "cabang_tujuan",
            "kode_cabang",
            "area",
            "wilayah",
            "branch_name",
        ):
            val = fd.get(key)
            if val and str(val).strip() and str(val).strip().lower() not in (
                "none",
                "null",
                "-",
                "",
                "-- select --",
                "—",
            ):
                return str(val).strip()

        # 2. Dynamic keys containing 'cabang' or 'branch' (exclude bank fields)
        for k, val in fd.items():
            k_lower = k.lower()
            if ("cabang" in k_lower or "branch" in k_lower) and not any(
                ign in k_lower for ign in ("bank", "rekening", "tipe", "nomor")
            ):
                if val and str(val).strip() and str(val).strip().lower() not in (
                    "none",
                    "null",
                    "-",
                    "",
                    "-- select --",
                    "—",
                ):
                    return str(val).strip()

    # 3. Fallback to submitter's EmployeeProfile branch
    if submission and getattr(submission, "submitter", None):
        ep = getattr(submission.submitter, "employee_profile", None)
        if ep and ep.branch:
            return str(ep.branch).strip()

    return None


def is_user_eligible_for_submission(
    user,
    group_name_or_obj,
    submission,
    form_data: Optional[dict] = None,
) -> bool:
    """Determine if a user in an approval group should receive notifications for a submission.

    Applies to ALL forms:
    1. User without email is skipped.
    2. Central / Corporate groups (Finance, PIC Pusat, Direksi, IT, GM) oversee submissions
       company-wide and are always eligible.
    3. Branch-scoped groups (ASM, Branch Manager, Kasir Cabang, etc.):
       - If submission branch is identified: user MUST belong to the matching branch
         via their EmployeeProfile. Regional employees from OTHER branches are excluded.
       - If submission has no branch and submitter is Super Admin (e.g. testing):
         regional branch employees from other branches are EXCLUDED to prevent national blast.
    4. If user has an explicit regional branch in EmployeeProfile and the submission is for
       a different regional branch: ALWAYS EXCLUDE to protect cross-branch integrity.
    """
    if not getattr(user, "email", None) or not user.email.strip():
        return False

    sub_branch = resolve_submission_branch(submission, form_data)
    user_ep = getattr(user, "employee_profile", None)
    user_branch = user_ep.branch if user_ep else None

    # Central groups oversee submissions across all branches
    if is_central_group(group_name_or_obj):
        return True

    # If the group is explicitly branch-scoped
    if is_branch_scoped_group(group_name_or_obj):
        if not user_branch:
            if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
                return True
            return False

        if sub_branch:
            if is_central_branch(user_branch) and not is_central_branch(sub_branch):
                return False
            return branch_matches(sub_branch, user_branch)

        # No branch on submission & submitter is superuser
        submitter = getattr(submission, "submitter", None) if submission else None
        if submitter and getattr(submitter, "is_superuser", False):
            logger.info(
                "Suppressing regional notification for user %s (branch %s): submitter is superuser without branch context.",
                user.username,
                user_branch,
            )
            return False
        return True

    # For any other group: if both user and submission have distinct regional branches, enforce matching
    if sub_branch and user_branch:
        if not is_central_branch(sub_branch) and not is_central_branch(user_branch):
            return branch_matches(sub_branch, user_branch)

    return True


def find_branch_manager_for_stage(
    sub_branch: str,
    stage_order: int = 1,
    stage_or_groups=None,
) -> Optional[User]:
    """Find a specific managerial approver for a branch when submitter has no supervisor.

    Applies to ANY form:
    1. Searches candidate active employees matching the target branch.
    2. If stage has approval groups, prioritizes candidates belonging to those groups.
    3. Falls back to ASM / Branch Manager / Kepala Cabang for Stage 1, RSOM / GM for Stage 2.
    """
    if not sub_branch:
        return None

    norm_sub = normalize_branch_slug(sub_branch)
    if not norm_sub or norm_sub == "pusat":
        return None

    from django_forms_workflows.models import EmployeeProfile

    ep_qs = EmployeeProfile.objects.select_related("user").filter(user__is_active=True)

    candidate_eps = [
        ep for ep in ep_qs if ep.branch and branch_matches(norm_sub, ep.branch)
    ]
    if not candidate_eps:
        return None

    # Check against stage's approval groups if provided
    target_group_names = set()
    if stage_or_groups:
        if hasattr(stage_or_groups, "get_approval_groups"):
            target_group_names = {g.name for g in stage_or_groups.get_approval_groups()}
        elif hasattr(stage_or_groups, "__iter__"):
            target_group_names = {
                g.name if hasattr(g, "name") else str(g) for g in stage_or_groups
            }

    if target_group_names:
        for ep in candidate_eps:
            user_groups = set(ep.user.groups.values_list("name", flat=True))
            if user_groups.intersection(target_group_names):
                return ep.user

    # Fallback by stage_order
    if stage_order == 1:
        for ep in candidate_eps:
            pos_upper = (ep.position or "").upper()
            groups = set(ep.user.groups.values_list("name", flat=True))
            if any(
                g in groups
                for g in (
                    "Sales Area Manager",
                    "Branch Manager",
                    "Atasan Cabang (Manager Cabang)",
                    "Manager Cabang & Atasan Langsung",
                )
            ) or any(
                k in pos_upper
                for k in ("ASM", "AREA SALES", "BRANCH", "KEPALA CABANG", "BOM", "MANAGER", "ATASAN")
            ):
                return ep.user
    elif stage_order == 2:
        for ep in candidate_eps:
            pos_upper = (ep.position or "").upper()
            groups = set(ep.user.groups.values_list("name", flat=True))
            if any(
                g in groups
                for g in ("Sales Area Manager", "General Manager Sales", "Commercial Director")
            ) or any(k in pos_upper for k in ("RSOM", "REGIONAL", "GENERAL MANAGER", "GM")):
                return ep.user

    return candidate_eps[0].user if candidate_eps else None
