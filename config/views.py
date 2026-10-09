"""
Views for main application and overrides for django_forms_workflows.
"""
from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django_forms_workflows.models import (
    FormDefinition,
    FormSubmission,
    FormField,
    ApprovalTask,
)
from django_forms_workflows.views import (
    _build_grouped_forms,
    _get_accessible_category_pks,
    form_submit as upstream_form_submit,
)
from django_forms_workflows.forms import DynamicForm

# Configure DynamicForm to disable crispy's outer <form> wrapper and default buttons,
# allowing templates to render the semantic <form> container with unified action buttons.
_orig_dynamic_form_init = DynamicForm.__init__

def _patched_dynamic_form_init(self, *args, **kwargs):
    _orig_dynamic_form_init(self, *args, **kwargs)
    if hasattr(self, 'helper') and self.helper:
        self.helper.form_tag = False
        if hasattr(self.helper, 'layout') and hasattr(self.helper.layout, 'fields'):
            self.helper.layout.fields = [
                elem for elem in self.helper.layout.fields
                if not (hasattr(elem, 'css_class') and 'mt-4' in getattr(elem, 'css_class', ''))
            ]

DynamicForm.__init__ = _patched_dynamic_form_init


@login_required
def custom_form_list(request):
    """
    Enhanced form list view with comprehensive search filtering:
    Q(name__icontains=q) | Q(description__icontains=q) | Q(category__name__icontains=q).
    """
    if request.user.is_staff or request.user.is_superuser:
        forms = FormDefinition.objects.filter(
            is_active=True, is_listed=True
        ).select_related("category")
    else:
        user_groups = request.user.groups.all()
        accessible_cat_pks = _get_accessible_category_pks(request.user)
        forms = (
            FormDefinition.objects.filter(is_active=True, is_listed=True)
            .annotate(
                submit_group_count=models.Count("submit_groups", distinct=True),
                view_group_count=models.Count("view_groups", distinct=True),
            )
            .filter(
                models.Q(view_groups__in=user_groups) | models.Q(view_group_count=0)
            )
            .filter(
                models.Q(submit_groups__in=user_groups) | models.Q(submit_group_count=0)
            )
            .filter(
                models.Q(category__isnull=True)
                | models.Q(category_id__in=accessible_cat_pks)
            )
            .distinct()
            .select_related("category")
        )

    # Capture search query parameter
    q = (request.GET.get("q") or request.GET.get("search") or "").strip()
    if q:
        forms = forms.filter(
            models.Q(name__icontains=q)
            | models.Q(description__icontains=q)
            | models.Q(category__name__icontains=q)
        )

    grouped_forms = _build_grouped_forms(forms)

    return render(
        request,
        "django_forms_workflows/form_list.html",
        {
            "forms": forms,
            "grouped_forms": grouped_forms,
            "search_query": q,
            "q": q,
        },
    )


def custom_form_submit(request, slug):
    """
    Enhanced form submission view supporting both standard POST and action="draft"/"submit"
    from the unified button bar.
    """
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "draft" and "save_draft" not in request.POST:
            post = request.POST.copy()
            post["save_draft"] = "Save Draft"
            request.POST = post
    return upstream_form_submit(request, slug)


@login_required
def custom_my_submissions(request):
    """
    Enhanced My Submissions view supporting status tabs (All, Draft, Pending, Approved, Rejected)
    and category filtering.
    """
    user_groups = request.user.groups.all()
    privileged_form_ids = (
        FormDefinition.objects.filter(
            models.Q(reviewer_groups__in=user_groups)
            | models.Q(admin_groups__in=user_groups)
        )
        .values_list("id", flat=True)
        .distinct()
    )
    base_submissions = FormSubmission.objects.filter(
        models.Q(submitter=request.user)
        | models.Q(
            form_definition__in=privileged_form_ids,
            status__in=[
                "submitted",
                "pending_approval",
                "approved",
                "rejected",
                "withdrawn",
            ],
        )
    ).distinct()

    # Status counts for filter pills
    status_counts = {
        "all": base_submissions.count(),
        "draft": base_submissions.filter(status="draft").count(),
        "pending": base_submissions.filter(status__in=["submitted", "pending_approval"]).count(),
        "approved": base_submissions.filter(status="approved").count(),
        "rejected": base_submissions.filter(status="rejected").count(),
    }

    # Category counts
    raw_counts = (
        base_submissions.values(
            "form_definition__category__pk",
            "form_definition__category__name",
            "form_definition__category__slug",
            "form_definition__category__icon",
            "form_definition__category__order",
        )
        .annotate(count=models.Count("id"))
        .order_by(
            "form_definition__category__order",
            "form_definition__category__name",
        )
    )
    category_counts = []
    for row in raw_counts:
        slug = row["form_definition__category__slug"]
        if slug:
            category_counts.append(
                {
                    "name": row["form_definition__category__name"],
                    "slug": slug,
                    "icon": row["form_definition__category__icon"] or "",
                    "count": row["count"],
                }
            )

    status_filter = request.GET.get("status", "all").strip().lower()
    category_slug = request.GET.get("category", "").strip()
    active_category = next((c for c in category_counts if c["slug"] == category_slug), None) if category_slug else None

    # Check if any submissions support bulk export
    any_exportable = base_submissions.filter(
        form_definition__workflows__allow_bulk_export=True
    ).exists()

    return render(
        request,
        "django_forms_workflows/my_submissions.html",
        {
            "status_filter": status_filter,
            "status_counts": status_counts,
            "category_counts": category_counts,
            "active_category": active_category,
            "category_slug": category_slug,
            "any_exportable": any_exportable,
            "total_submissions_count": status_counts["all"],
        },
    )


@login_required
def custom_my_submissions_ajax(request):
    """
    Server-side DataTables JSON for My Submissions with status filtering,
    active workflow step/assignee info, and clean enterprise action buttons.
    """
    import re
    from django.http import JsonResponse
    from django.urls import reverse
    from django.utils.html import escape
    from django_forms_workflows.models import FormSubmission, FormField, ApprovalTask
    from django_forms_workflows.views import _dt_params, _cat_html

    draw, start, length, search, col_name, order_dir = _dt_params(request)
    params = request.POST if request.method == "POST" else request.GET
    status_filter = params.get("status", "").strip().lower()
    category_slug = params.get("category", "").strip()

    user_groups = request.user.groups.all()
    privileged_form_ids = (
        FormDefinition.objects.filter(
            models.Q(reviewer_groups__in=user_groups)
            | models.Q(admin_groups__in=user_groups)
        )
        .values_list("id", flat=True)
        .distinct()
    )
    qs = FormSubmission.objects.filter(
        models.Q(submitter=request.user)
        | models.Q(
            form_definition__in=privileged_form_ids,
            status__in=[
                "submitted",
                "pending_approval",
                "approved",
                "rejected",
                "withdrawn",
            ],
        )
    ).distinct()

    records_total = qs.count()

    # Filter by status
    if status_filter == "draft":
        qs = qs.filter(status="draft")
    elif status_filter == "pending":
        qs = qs.filter(status__in=["submitted", "pending_approval"])
    elif status_filter == "approved":
        qs = qs.filter(status="approved")
    elif status_filter == "rejected":
        qs = qs.filter(status="rejected")
    elif status_filter and status_filter != "all":
        qs = qs.filter(status=status_filter)

    # Filter by category
    if category_slug:
        qs = qs.filter(form_definition__category__slug=category_slug)

    # Search
    if search:
        qs = qs.filter(
            models.Q(id__icontains=search)
            | models.Q(form_definition__name__icontains=search)
            | models.Q(form_definition__category__name__icontains=search)
            | models.Q(status__icontains=search)
            | models.Q(current_step__icontains=search)
        )

    records_filtered = qs.count()

    # Ordering
    sort_map = {
        "id": "id",
        "form": "form_definition__name",
        "status": "status",
        "submitted_at": "submitted_at",
    }
    order_field = sort_map.get(col_name, "submitted_at")
    prefix = "" if order_dir == "asc" else "-"
    qs = qs.order_by(f"{prefix}{order_field}", "-id")

    page_qs = qs.select_related(
        "form_definition__category"
    ).prefetch_related(
        "form_definition__workflows",
        "approval_tasks__assigned_to",
        "approval_tasks__assigned_group",
        "approval_tasks__workflow_stage",
    )[start : start + length]

    data = []
    for sub in page_qs:
        wf = getattr(sub.form_definition, "workflow", None)
        can_exp = wf and wf.allow_bulk_export
        det_url = reverse("forms_workflows:submission_detail", args=[sub.id])
        cat = getattr(sub.form_definition, "category", None)

        # Action Buttons: Solid dark neutral primary action (btn btn-sm btn-dark) + standard outline secondary action (btn btn-sm btn-outline-secondary)
        actions_parts = []
        if sub.status == "draft":
            submit_url = reverse("forms_workflows:form_submit", args=[sub.form_definition.slug])
            discard_url = reverse("forms_workflows:discard_draft", args=[sub.id])
            actions_parts.append(
                f'<a href="{submit_url}" class="btn btn-sm btn-dark"><i class="bi bi-pencil me-1"></i>Continue</a>'
            )
            actions_parts.append(
                f'<a href="{discard_url}" class="btn btn-sm btn-outline-secondary"><i class="bi bi-trash3 me-1"></i>Discard</a>'
            )
        elif sub.status in ("submitted", "pending_approval"):
            actions_parts.append(
                f'<a href="{det_url}" class="btn btn-sm btn-dark"><i class="bi bi-eye me-1"></i>View</a>'
            )
            if sub.form_definition.allow_withdrawal:
                withdraw_url = reverse("forms_workflows:withdraw_submission", args=[sub.id])
                actions_parts.append(
                    f'<a href="{withdraw_url}" class="btn btn-sm btn-outline-secondary"><i class="bi bi-x-circle me-1"></i>Withdraw</a>'
                )
        elif sub.status == "approved":
            actions_parts.append(
                f'<a href="{det_url}" class="btn btn-sm btn-dark"><i class="bi bi-eye me-1"></i>View</a>'
            )
            pdf_gen = sub.form_definition.pdf_generation
            if pdf_gen in ("anytime", "post_approval"):
                pdf_url = reverse("forms_workflows:submission_pdf", args=[sub.id])
                actions_parts.append(
                    f'<a href="{pdf_url}" target="_blank" class="btn btn-sm btn-outline-secondary"><i class="bi bi-file-earmark-pdf me-1"></i>PDF</a>'
                )
        elif sub.status in ("rejected", "withdrawn"):
            actions_parts.append(
                f'<a href="{det_url}" class="btn btn-sm btn-dark"><i class="bi bi-eye me-1"></i>View</a>'
            )
            if sub.form_definition.allow_resubmit:
                resubmit_url = reverse("forms_workflows:resubmit_submission", args=[sub.id])
                actions_parts.append(
                    f'<a href="{resubmit_url}" class="btn btn-sm btn-outline-secondary"><i class="bi bi-arrow-repeat me-1"></i>Resubmit</a>'
                )
        else:
            actions_parts.append(
                f'<a href="{det_url}" class="btn btn-sm btn-dark"><i class="bi bi-eye me-1"></i>View</a>'
            )

        # Current step / assignee display
        current_step_text = "—"
        if sub.status == "draft":
            current_step_text = '<span class="text-muted small">Draft (Not submitted)</span>'
        elif sub.status in ("submitted", "pending_approval"):
            active_task = next((t for t in sub.approval_tasks.all() if t.status == "pending"), None)
            if active_task:
                assignee = (
                    active_task.assigned_to.get_full_name() or active_task.assigned_to.username
                    if active_task.assigned_to
                    else (active_task.assigned_group.name if active_task.assigned_group else "Unassigned")
                )
                step_name = active_task.display_label
                step_name = re.sub(r'^(Step \d+:\s*)(Step \d+:\s*)+', r'\1', step_name)
                current_step_text = (
                    f'<div class="d-flex flex-column py-0.5">'
                    f'<span class="text-dark fw-medium" style="font-size: 13px;">{escape(step_name)}</span>'
                    f'<span class="text-muted small mt-0.5" style="font-size: 12px;"><i class="bi bi-person-badge me-1"></i>{escape(assignee)}</span>'
                    f'</div>'
                )
            elif sub.current_step:
                current_step_text = f'<span class="text-dark fw-medium" style="font-size: 13px;">{escape(sub.current_step)}</span>'
            else:
                current_step_text = '<span class="text-secondary small">Pending Review</span>'
        elif sub.status == "approved":
            current_step_text = '<span class="text-success small fw-medium"><i class="bi bi-check-circle me-1"></i>Workflow Completed</span>'
        elif sub.status == "rejected":
            current_step_text = '<span class="text-danger small fw-medium"><i class="bi bi-x-circle me-1"></i>Request Rejected</span>'
        elif sub.status == "withdrawn":
            current_step_text = '<span class="text-muted small"><i class="bi bi-dash-circle me-1"></i>Request Withdrawn</span>'

        # Status badge
        # Standard pill badge: flat light background, thin border, dark legible text
        status_badges = {
            "draft": '<span class="badge-status-pill badge-status-draft">Draft</span>',
            "submitted": '<span class="badge-status-pill badge-status-submitted">Submitted</span>',
            "pending_approval": '<span class="badge-status-pill badge-status-pending">Pending Approval</span>',
            "approved": '<span class="badge-status-pill badge-status-approved">Approved</span>',
            "rejected": '<span class="badge-status-pill badge-status-rejected">Rejected</span>',
            "withdrawn": '<span class="badge-status-pill badge-status-withdrawn">Withdrawn</span>',
        }
        status_html = status_badges.get(
            sub.status,
            f'<span class="badge-status-pill badge-status-draft">{escape(sub.status.title())}</span>'
        )

        submitted_html = (
            sub.submitted_at.strftime("%Y-%m-%d %H:%M")
            if sub.submitted_at
            else "—"
        )

        row = {
            "DT_RowId": f"row_{sub.id}",
            "checkbox": (
                f'<input type="checkbox" name="submission_ids" value="{sub.id}" class="form-check-input export-check">'
                if can_exp
                else ""
            ),
            "id": str(sub.id),
            "form": escape(sub.form_definition.name),
            "category": _cat_html(cat),
            "current_step": current_step_text,
            "status": status_html,
            "submitted_at": submitted_html,
            "actions": f'<div class="d-inline-flex align-items-center justify-content-end gap-2 text-nowrap">{" ".join(actions_parts)}</div>',
        }
        data.append(row)

    return JsonResponse(
        {
            "draw": draw,
            "recordsTotal": records_total,
            "recordsFiltered": records_filtered,
            "data": data,
        }
    )


@login_required
def toggle_notification_preference(request):
    """
    API endpoint to toggle user email notifications preference via background AJAX.
    """
    import json
    from django_forms_workflows.models import UserNotificationPreference, NotificationRule

    if request.method == "POST":
        try:
            body = json.loads(request.body.decode("utf-8")) if request.body else {}
        except Exception:
            body = request.POST

        enabled = body.get("enabled")
        if isinstance(enabled, str):
            enabled = enabled.lower() in ("true", "1", "yes", "on")
        elif not isinstance(enabled, bool):
            enabled = True

        request.session["notifications_enabled"] = enabled

        if enabled:
            # Unmute: clear muted preferences for current user
            UserNotificationPreference.objects.filter(user=request.user).delete()
        else:
            # Mute: mark notification rules as muted for current user
            all_rules = NotificationRule.objects.all()
            for rule in all_rules:
                UserNotificationPreference.objects.update_or_create(
                    user=request.user,
                    rule=rule,
                    defaults={"muted": True},
                )

        return JsonResponse({"success": True, "enabled": enabled})

    # GET returns current status
    is_muted = UserNotificationPreference.objects.filter(user=request.user, muted=True).exists()
    current_enabled = request.session.get("notifications_enabled", not is_muted)
    return JsonResponse({"success": True, "enabled": current_enabled})


