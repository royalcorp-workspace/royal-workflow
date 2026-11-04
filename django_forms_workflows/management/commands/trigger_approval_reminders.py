"""
Management command: trigger_approval_reminders

Executes the workflow reminder sweep for pending approval tasks,
dispatching email reminders and Telegram alerts to approvers.

Usage:
    python manage.py trigger_approval_reminders [--submission-id=X] [--force]
"""

from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django_forms_workflows.models import ApprovalTask, FormSubmission
from django_forms_workflows.workflow_engine import _dispatch_notification_rules


class Command(BaseCommand):
    help = "Sweeps pending tasks and triggers email & Telegram approval reminders."

    def add_arguments(self, parser):
        parser.add_argument(
            "--submission-id",
            type=int,
            help="Optionally target a specific submission ID to trigger reminder.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force trigger reminder even if reminder_sent_at is already stamped.",
        )

    def handle(self, *args, **options):
        sub_id = options.get("submission_id")
        force = options.get("force", False)
        now = timezone.now()

        tasks_qs = ApprovalTask.objects.select_related(
            "submission__form_definition", "workflow_stage"
        ).filter(status="pending")

        if sub_id:
            tasks_qs = tasks_qs.filter(submission_id=sub_id)

        self.stdout.write(f"Checking {tasks_qs.count()} pending approval tasks for reminders...")
        reminded_count = 0

        for task in tasks_qs:
            submission = task.submission
            workflow = getattr(submission.form_definition, "workflow", None)
            if not workflow:
                # Try from workflow_stage
                workflow = getattr(task.workflow_stage, "workflow", None) if task.workflow_stage else None

            # Check if reminder is due or forced
            reminder_days = getattr(workflow, "send_reminder_after_days", 1) if workflow else 1
            is_due = force or (
                task.created_at
                and not task.reminder_sent_at
                and now > (task.created_at + timedelta(days=reminder_days))
            )

            if is_due or force:
                self.stdout.write(
                    f"-> Dispatching reminder for Task #{task.id} (Submission #{submission.id}: {submission.form_definition.name})"
                )
                _dispatch_notification_rules(
                    submission, "approval_reminder", task_id=task.id
                )
                task.reminder_sent_at = now
                task.save(update_fields=["reminder_sent_at"])
                reminded_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"[SUCCESS] Reminder sweep complete! Total reminders dispatched: {reminded_count}"
            )
        )
