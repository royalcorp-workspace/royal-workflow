"""
Context processors for config project.
"""

def user_notification_settings(request):
    """
    Injects user notification preference status into template context.
    """
    if not hasattr(request, "user") or not request.user.is_authenticated:
        return {"notifications_enabled": True}

    if "notifications_enabled" in request.session:
        return {"notifications_enabled": request.session["notifications_enabled"]}

    try:
        from django_forms_workflows.models import UserNotificationPreference
        is_muted = UserNotificationPreference.objects.filter(
            user=request.user, muted=True
        ).exists()
        return {"notifications_enabled": not is_muted}
    except Exception:
        return {"notifications_enabled": True}


def topbar_notifications(request):
    """
    Injects recent notifications and unread count for topbar bell dropdown.
    """
    if not hasattr(request, "user") or not request.user.is_authenticated:
        return {"unread_notifications_count": 0, "recent_notifications": []}

    try:
        from django_forms_workflows.models import ApprovalTask
        from django.db.models import Q

        pending_tasks = (
            ApprovalTask.objects.filter(
                Q(assigned_to=request.user) | Q(assigned_group__in=request.user.groups.all()),
                status="pending",
            )
            .select_related("submission", "submission__form_definition", "workflow_stage")
            .order_by("-created_at")[:5]
        )

        items = []
        for t in pending_tasks:
            form_name = (
                t.submission.form_definition.name
                if t.submission and t.submission.form_definition
                else "Form"
            )
            stage_name = t.workflow_stage.name if t.workflow_stage else "Review Stage"
            items.append({
                "title": f"Review Pending: {form_name}",
                "text": f"Submission #{t.submission_id} requires review on stage '{stage_name}'",
                "url": f"/forms/approvals/{t.id}/approve/",
                "time": t.created_at,
                "icon": "bi-hourglass-split text-warning",
            })

        return {
            "unread_notifications_count": len(items),
            "recent_notifications": items,
        }
    except Exception:
        return {"unread_notifications_count": 0, "recent_notifications": []}
