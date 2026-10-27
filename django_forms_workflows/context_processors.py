"""
Context processors for django_forms_workflows.
"""

from django.conf import settings
from django.db.models import Q


def forms_workflows(request):
    """
    Inject package-level settings into every template context.

    Adds:
        site_name (str): Human-readable name of the site, used in page
            titles, the navbar brand, and the footer.  Configured via::

                FORMS_WORKFLOWS = {
                    'SITE_NAME': 'My Organisation Workflows',
                    ...
                }

            Defaults to ``"Django Forms Workflows"`` when not set.

        user_is_approver (bool): True when the current user is superuser/staff
            or has ever been assigned an ApprovalTask (directly or via a
            group).  Used to gate the Approvals nav link so it is only shown
            to users who have an approver role.
    """
    fw_settings = getattr(settings, "FORMS_WORKFLOWS", {})

    user_is_approver = False
    sidebar_categories = []
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        if user.is_superuser or user.is_staff:
            user_is_approver = True
        else:
            from .models import ApprovalTask, StageApprovalGroup

            user_groups = user.groups.all()
            user_is_approver = (
                ApprovalTask.objects.filter(
                    Q(assigned_to=user) | Q(assigned_group__in=user_groups)
                ).exists()
                or StageApprovalGroup.objects.filter(group__in=user_groups).exists()
            )

        try:
            from .models import FormCategory, FormDefinition
            from django.urls import reverse

            # Fetch active forms accessible to the user
            if user.is_superuser or user.is_staff:
                forms_qs = (
                    FormDefinition.objects.filter(is_active=True)
                    .select_related("category")
                    .order_by("category__order", "category__name", "name")
                )
            else:
                user_groups = user.groups.all()
                forms_qs = (
                    FormDefinition.objects.filter(is_active=True)
                    .filter(
                        Q(view_groups__in=user_groups) | Q(view_groups__isnull=True),
                        Q(submit_groups__in=user_groups) | Q(submit_groups__isnull=True),
                    )
                    .select_related("category")
                    .distinct()
                    .order_by("category__order", "category__name", "name")
                )

            cat_map = {}
            for form in forms_qs:
                cat = form.category
                cat_key = cat.id if cat else 0
                if cat_key not in cat_map:
                    cat_name = cat.name if cat else "General"
                    if "sales" in cat_name.lower():
                        cat_name = "SALES & MARKETING PT RAS"
                    cat_map[cat_key] = {
                        "category": cat,
                        "category_name": cat_name,
                        "forms": [],
                    }

                try:
                    hub_url = reverse("forms_workflows:form_submission_hub", kwargs={"slug": form.slug})
                except Exception:
                    hub_url = f"/forms/{form.slug}/"

                cat_map[cat_key]["forms"].append({
                    "slug": form.slug,
                    "name": form.name,
                    "hub_url": hub_url,
                })


            sidebar_categories = list(cat_map.values())
        except Exception:
            sidebar_categories = []

    return {
        "site_name": fw_settings.get("SITE_NAME", "Django Forms Workflows"),
        "user_is_approver": user_is_approver,
        "sidebar_categories": sidebar_categories,
    }
