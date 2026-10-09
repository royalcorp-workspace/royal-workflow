"""
Management command to safely purge a FormDefinition and its entire lifecycle
graph without triggering ProtectedError constraints.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django_forms_workflows.models import (
    ActionExecutionLog,
    ApprovalTask,
    AuditLog,
    ChangeHistory,
    DocumentTemplate,
    FileWorkflowHook,
    FormField,
    FormDefinition,
    FormSubmission,
    FormTemplate,
    ManagedFile,
    NotificationLog,
    PaymentRecord,
    PendingNotification,
    PostSubmissionAction,
    SubWorkflowDefinition,
    SubWorkflowInstance,
    WebhookDeliveryLog,
    WebhookEndpoint,
    WorkflowDefinition,
    WorkflowStage,
)


class Command(BaseCommand):
    help = (
        "Safely delete a FormDefinition and all associated submissions, "
        "tasks, logs, and files without triggering ProtectedError."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--slug",
            type=str,
            required=True,
            help="Slug of the FormDefinition to purge",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Bypass interactive confirmation prompt",
        )
        parser.add_argument(
            "--keep-files",
            action="store_true",
            help="Do not delete uploaded physical files from storage",
        )
        parser.add_argument(
            "--delete-template",
            action="store_true",
            help="Also delete matching FormTemplate if one exists with the same slug",
        )

    def handle(self, *args, **options):
        slug = options["slug"].strip()
        force = options["force"]
        keep_files = options["keep_files"]
        delete_template = options["delete_template"]

        try:
            form_def = FormDefinition.objects.get(slug=slug)
        except FormDefinition.DoesNotExist:
            raise CommandError(f'FormDefinition with slug "{slug}" does not exist.')

        submissions = FormSubmission.objects.filter(form_definition=form_def)
        submission_count = submissions.count()
        sub_ids = list(submissions.values_list("id", flat=True))

        workflows = WorkflowDefinition.objects.filter(form_definition=form_def)
        wf_ids = list(workflows.values_list("id", flat=True))
        stages = WorkflowStage.objects.filter(workflow__in=workflows)
        stage_ids = list(stages.values_list("id", flat=True))

        tasks = ApprovalTask.objects.filter(submission__in=submissions)
        task_count = tasks.count()

        if not force:
            self.stdout.write(
                self.style.WARNING(
                    f'Target: FormDefinition "{form_def.name}" (slug: {slug}, pk: {form_def.pk})\n'
                    f"Related entities to purge:\n"
                    f"  - Submissions: {submission_count}\n"
                    f"  - Approval Tasks: {task_count}\n"
                    f"  - Workflows: {len(wf_ids)} (Stages: {len(stage_ids)})\n"
                    f"  - Fields: {form_def.fields.count()}\n"
                )
            )
            confirm = input('Are you sure you want to permanently PURGE this form? [y/N]: ')
            if confirm.lower() != "y":
                self.stdout.write(self.style.NOTICE("Purge aborted by user."))
                return

        with transaction.atomic():
            self.stdout.write("Purging lifecycle entities in safe topological order...")

            # 1. Clean physical and managed files
            managed_files = ManagedFile.objects.filter(
                models.Q(submission__in=submissions) | models.Q(form_field__form_definition=form_def)
            ) if hasattr(models, "Q") else ManagedFile.objects.filter(submission__in=submissions)
            
            from django.db.models import Q
            managed_files = ManagedFile.objects.filter(
                Q(submission__in=submissions) | Q(form_field__form_definition=form_def)
            )

            file_del_count = 0
            if not keep_files:
                for mf in managed_files:
                    if mf.file:
                        try:
                            mf.file.delete(save=False)
                            file_del_count += 1
                        except Exception as e:
                            self.stdout.write(
                                self.style.WARNING(f"Could not delete physical file: {e}")
                            )
            managed_files.delete()

            # 2. FileWorkflowHook
            FileWorkflowHook.objects.filter(form_definition=form_def).delete()

            # 3. SubWorkflow Instances & Definitions
            SubWorkflowInstance.objects.filter(parent_submission__in=submissions).delete()
            SubWorkflowDefinition.objects.filter(
                Q(parent_workflow__in=workflows) | Q(sub_workflow__in=workflows)
            ).delete()

            # 4. Webhook Delivery Logs & Endpoints
            WebhookDeliveryLog.objects.filter(
                Q(submission__in=submissions) | Q(workflow__in=workflows)
            ).delete()
            WebhookEndpoint.objects.filter(workflow__in=workflows).delete()

            # 5. PendingNotifications & Notification Logs
            PendingNotification.objects.filter(
                Q(submission__in=submissions) | Q(workflow__in=workflows)
            ).delete()
            NotificationLog.objects.filter(submission__in=submissions).delete()

            # 6. ActionExecutionLog & PostSubmissionAction
            ActionExecutionLog.objects.filter(submission__in=submissions).delete()
            PostSubmissionAction.objects.filter(form_definition=form_def).delete()

            # 7. DocumentTemplate
            DocumentTemplate.objects.filter(form_definition=form_def).delete()

            # 8. ApprovalTasks
            ApprovalTask.objects.filter(
                Q(submission__in=submissions) | Q(workflow_stage__in=stages)
            ).delete()

            # 9. PaymentRecords
            PaymentRecord.objects.filter(
                Q(submission__in=submissions) | Q(form_definition=form_def)
            ).delete()

            # 10. AuditLogs & ChangeHistory
            from django.contrib.contenttypes.models import ContentType

            try:
                ct_submission = ContentType.objects.get_for_model(FormSubmission)
                ChangeHistory.objects.filter(
                    content_type=ct_submission,
                    object_id__in=[str(sid) for sid in sub_ids],
                ).delete()
            except Exception:
                pass

            try:
                ct_formdef = ContentType.objects.get_for_model(FormDefinition)
                ChangeHistory.objects.filter(
                    content_type=ct_formdef,
                    object_id=str(form_def.id),
                ).delete()
            except Exception:
                pass

            AuditLog.objects.filter(
                object_type="FormSubmission",
                object_id__in=sub_ids,
            ).delete()
            AuditLog.objects.filter(
                object_type="FormDefinition",
                object_id=form_def.id,
            ).delete()

            # 11. Delete all FormSubmissions (unlocks protected foreign keys)
            submissions.delete()

            # 12. Delete Workflow definitions and stages
            workflows.delete()

            # 13. Delete FormFields
            form_def.fields.all().delete()

            # 14. Optional: Delete matching FormTemplate
            template_deleted = False
            if delete_template:
                tpls = FormTemplate.objects.filter(slug=slug)
                if tpls.exists():
                    tpls.delete()
                    template_deleted = True

            # 15. Delete FormDefinition
            form_name = form_def.name
            form_def.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully purged FormDefinition "{form_name}" ({slug})!\n'
                f"  - Deleted {submission_count} submissions\n"
                f"  - Deleted {task_count} approval tasks\n"
                f"  - Cleaned {file_del_count} physical files"
                + (f"\n  - Deleted matching FormTemplate ({slug})" if template_deleted else "")
            )
        )
