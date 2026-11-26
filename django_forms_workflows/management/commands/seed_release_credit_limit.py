"""
Management command to seed the 'Release Credit Limit' form definition and fields
under the 'Sales & Marketing' category.
Idempotent: safe to run multiple times without creating duplicates.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction

from django_forms_workflows.models import (
    FormCategory,
    FormDefinition,
    FormField,
    NotificationRule,
    SharedOptionList,
    StageApprovalGroup,
    WorkflowDefinition,
    WorkflowStage,
)

User = get_user_model()


class Command(BaseCommand):
    help = "Seed the 'Release Credit Limit' form under Sales & Marketing."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("=================================================================")
        self.stdout.write("Seeding 'Release Credit Limit' FormDefinition & FormFields...")
        self.stdout.write("=================================================================")

        # 1. Category: Sales & Marketing
        category, _ = FormCategory.objects.get_or_create(
            slug="sales-marketing",
            defaults={
                "name": "Sales & Marketing",
                "description": "Formulir dan alur kerja divisi Sales & Marketing.",
                "order": 1,
                "is_active": True,
            },
        )

        # 2. SharedOptionLists (reuse existing cabang-list and brand-list)
        sol_cabang = SharedOptionList.objects.filter(slug="cabang-list").first()
        if not sol_cabang:
            sol_cabang = SharedOptionList.objects.create(
                slug="cabang-list",
                name="Daftar Cabang / Area",
                items=[
                    "Bali", "Bandung", "Banyumas", "Cirebon", "Jakarta", "Kediri",
                    "Lampung", "Makassar", "Manado", "Medan", "Palembang", "Pekanbaru",
                    "Pontianak", "Pusat", "Samarinda", "Semarang", "Surabaya", "Yogyakarta",
                ],
            )

        sol_brand = SharedOptionList.objects.filter(slug="brand-list").first()
        if not sol_brand:
            sol_brand = SharedOptionList.objects.create(
                slug="brand-list",
                name="Daftar Brand Royal",
                items=["ELITE", "LADY", "ROYAL", "SERENITY", "CLASSIC"],
            )

        # 3. FormDefinition
        form_def, _ = FormDefinition.objects.update_or_create(
            slug="release-credit-limit",
            defaults={
                "name": "Release Credit Limit",
                "category": category,
                "description": "Pengajuan pelepasan hold Credit Limit / TOP pada Sales Order sebelum diproses Accounting Cabang.",
                "instructions": "",
                "is_active": True,
                "is_listed": True,
                "allow_save_draft": True,
                "enable_auto_save": True,
                "allow_withdrawal": True,
                "enable_multi_step": False,
            },
        )

        # Assign submit & view groups (all Sales & Marketing + Accounting/GM workflow roles)
        submit_group_names = [
            "Sales Staff",
            "Promotor",
            "Sales Support",
            "Area Sales Manager (L1)",
            "Sales Area Manager",
            "Regional Sales Operation Manager (L2)",
            "Direksi",
        ]
        view_group_names = submit_group_names + [
            "Accounting",
            "Finance Accounting Tax",
            "Finance And Accounting",
            "Branch Manager",
            "Sales National Manager",
            "General Manager Sales",
        ]
        submit_groups = [Group.objects.get_or_create(name=g)[0] for g in submit_group_names]
        view_groups = [Group.objects.get_or_create(name=g)[0] for g in view_group_names]
        form_def.submit_groups.set(submit_groups)
        form_def.view_groups.set(view_groups)

        # 4. FormFields across Sections 01 - 04
        fields_spec = [
            # Section 01 — Informasi Dasar
            {
                "field_name": "no_pengajuan",
                "field_label": "No Pengajuan",
                "field_type": "text",
                "required": False,
                "readonly": True,
                "placeholder": "Dibuat otomatis saat submit",
                "width": "third",
                "section_name": "01. Informasi Dasar",
                "order": 10,
            },
            {
                "field_name": "cabang",
                "field_label": "Cabang",
                "field_type": "select",
                "required": True,
                "placeholder": "Pilih Cabang",
                "shared_option_list": sol_cabang,
                "width": "third",
                "section_name": "01. Informasi Dasar",
                "order": 20,
            },
            {
                "field_name": "brand",
                "field_label": "Brand",
                "field_type": "select",
                "required": True,
                "placeholder": "Pilih Brand",
                "shared_option_list": sol_brand,
                "width": "third",
                "section_name": "01. Informasi Dasar",
                "order": 30,
            },
            # Section 02 — Informasi Toko
            {
                "field_name": "kode_customer_jde",
                "field_label": "Kode Customer (JDE)",
                "field_type": "text",
                "required": True,
                "placeholder": "Cari / masukkan kode JDE",
                "width": "half",
                "section_name": "02. Informasi Toko",
                "order": 40,
            },
            {
                "field_name": "nama_customer",
                "field_label": "Nama Customer",
                "field_type": "text",
                "required": False,
                "placeholder": "Nama customer",
                "width": "half",
                "section_name": "02. Informasi Toko",
                "order": 50,
            },
            {
                "field_name": "nama_toko",
                "field_label": "Nama Toko",
                "field_type": "text",
                "required": False,
                "placeholder": "Nama toko",
                "width": "half",
                "section_name": "02. Informasi Toko",
                "order": 60,
            },
            {
                "field_name": "nama_toko_parent",
                "field_label": "Nama Toko Parent",
                "field_type": "text",
                "required": False,
                "placeholder": "Nama parent",
                "width": "half",
                "section_name": "02. Informasi Toko",
                "order": 70,
            },
            {
                "field_name": "nama_pemilik",
                "field_label": "Nama Pemilik",
                "field_type": "text",
                "required": False,
                "placeholder": "Nama pemilik",
                "width": "third",
                "section_name": "02. Informasi Toko",
                "order": 80,
            },
            {
                "field_name": "email",
                "field_label": "Email",
                "field_type": "email",
                "required": False,
                "placeholder": "nama@perusahaan.com",
                "width": "third",
                "section_name": "02. Informasi Toko",
                "order": 90,
            },
            {
                "field_name": "no_telepon",
                "field_label": "No. Telepon",
                "field_type": "text",
                "required": False,
                "placeholder": "08xxxxxxxxxx",
                "width": "third",
                "section_name": "02. Informasi Toko",
                "order": 100,
            },
            {
                "field_name": "keterangan",
                "field_label": "Keterangan",
                "field_type": "textarea",
                "required": False,
                "placeholder": "Tambahkan informasi toko jika diperlukan...",
                "width": "full",
                "section_name": "02. Informasi Toko",
                "order": 110,
            },
            # Section 03 — Informasi Sales Order
            {
                "field_name": "nomor_so",
                "field_label": "Nomor SO",
                "field_type": "text",
                "required": True,
                "placeholder": "Cari / masukkan nomor SO",
                "width": "half",
                "section_name": "03. Informasi Sales Order",
                "order": 120,
            },
            {
                "field_name": "jenis_so",
                "field_label": "Jenis SO",
                "field_type": "select",
                "required": True,
                "choices": "SO, ZO, S6, S5, SG",
                "width": "half",
                "section_name": "03. Informasi Sales Order",
                "order": 130,
            },
            {
                "field_name": "total_so",
                "field_label": "Total SO",
                "field_type": "text",
                "required": True,
                "placeholder": "0",
                "width": "half",
                "section_name": "03. Informasi Sales Order",
                "order": 140,
            },
            {
                "field_name": "jenis_hold",
                "field_label": "Jenis Hold",
                "field_type": "select",
                "required": True,
                "choices": (
                    "C1|C1 - Credit Limit Hold\n"
                    "C2|C2 - TOP Hold\n"
                    "C1 + C2|C1 + C2 - Kedua jenis hold"
                ),
                "width": "half",
                "section_name": "03. Informasi Sales Order",
                "order": 150,
            },
            # Section 04 — Lampiran
            {
                "field_name": "lampiran_dokumen",
                "field_label": "Lampiran Pendukung",
                "field_type": "textarea",
                "required": False,
                "placeholder": "[]",
                "width": "full",
                "section_name": "04. Lampiran",
                "order": 160,
            },
        ]

        active_names = []
        for spec in fields_spec:
            fname = spec["field_name"]
            active_names.append(fname)
            FormField.objects.update_or_create(
                form_definition=form_def,
                field_name=fname,
                defaults={
                    "field_label": spec["field_label"],
                    "field_type": spec["field_type"],
                    "required": spec.get("required", False),
                    "readonly": spec.get("readonly", False),
                    "placeholder": spec.get("placeholder", ""),
                    "shared_option_list": spec.get("shared_option_list"),
                    "choices": spec.get("choices", ""),
                    "width": spec.get("width", "full"),
                    "order": spec.get("order", 0),
                },
            )

        # Remove stale fields if any
        FormField.objects.filter(form_definition=form_def).exclude(field_name__in=active_names).delete()

        # 5. Seed 4-Stage Dynamic Approval Workflow (Accounting Cabang -> ASM/BM -> NSM -> GM)
        grp_acc_1, _ = Group.objects.get_or_create(name="Accounting")
        grp_acc_2, _ = Group.objects.get_or_create(name="Finance Accounting Tax")
        grp_acc_3, _ = Group.objects.get_or_create(name="Finance And Accounting")

        # Map existing local Accounting Cabang account if present (without creating new users)
        for acc_uname in ("dummy.06",):
            acc_user = User.objects.filter(username=acc_uname).first()
            if acc_user:
                acc_user.groups.add(grp_acc_1)

        grp_asm_1, _ = Group.objects.get_or_create(name="Sales Area Manager")
        grp_asm_2, _ = Group.objects.get_or_create(name="Branch Manager")
        grp_asm_3, _ = Group.objects.get_or_create(name="Area Sales Manager (L1)")

        grp_nsm, _ = Group.objects.get_or_create(name="Sales National Manager")
        grp_rsom_l2, _ = Group.objects.get_or_create(name="Regional Sales Operation Manager (L2)")

        # Link existing L2/RSOM employees to 'Sales National Manager' without removing existing groups
        for uname in (
            "irsan.suryawinata",
            "ricky.tanyael",
            "david.dharmawan",
            "alex.santana",
            "dummy.04",
        ):
            nsm_user = User.objects.filter(username=uname).first()
            if nsm_user:
                nsm_user.groups.add(grp_nsm)

        grp_gm, _ = Group.objects.get_or_create(name="General Manager Sales")
        for gm_uname in ("dummy.07",):
            gm_user = User.objects.filter(username=gm_uname).first()
            if gm_user:
                gm_user.groups.add(grp_gm)

        workflow, _ = WorkflowDefinition.objects.update_or_create(
            form_definition=form_def,
            defaults={
                "name_label": "Alur Persetujuan Release Credit Limit",
                "requires_approval": True,
                "start_trigger": "on_submission",
                "collapse_parallel_stages": False,
                "hide_approval_history": False,
            },
        )

        stages_spec = [
            {
                "order": 1,
                "name": "Review Accounting Cabang",
                "approval_logic": "any",
                "trigger_conditions": None,
                "allow_send_back": False,
                "allow_edit_form_data": False,
                "groups": [grp_acc_1, grp_acc_2, grp_acc_3],
            },
            {
                "order": 2,
                "name": "Approval ASM / BM",
                "approval_logic": "any",
                "trigger_conditions": None,
                "allow_send_back": False,
                "allow_edit_form_data": False,
                "groups": [grp_asm_1, grp_asm_2, grp_asm_3],
            },
            {
                "order": 3,
                "name": "Approval NSM",
                "approval_logic": "any",
                "trigger_conditions": {
                    "operator": "AND",
                    "conditions": [
                        {
                            "field": "rcl_target_final_level",
                            "operator": "in",
                            "value": ["NSM", "GM"],
                        }
                    ],
                },
                "allow_send_back": False,
                "allow_edit_form_data": False,
                "groups": [grp_nsm, grp_rsom_l2],
            },
            {
                "order": 4,
                "name": "Approval GM",
                "approval_logic": "any",
                "trigger_conditions": {
                    "operator": "AND",
                    "conditions": [
                        {
                            "field": "rcl_target_final_level",
                            "operator": "equals",
                            "value": "GM",
                        }
                    ],
                },
                "allow_send_back": False,
                "allow_edit_form_data": False,
                "groups": [grp_gm],
            },
        ]

        active_orders = []
        for st in stages_spec:
            active_orders.append(st["order"])
            stage_obj = WorkflowStage.objects.filter(
                workflow=workflow, order=st["order"]
            ).first()
            if stage_obj:
                stage_obj.name = st["name"]
                stage_obj.approval_logic = st["approval_logic"]
                stage_obj.trigger_conditions = st["trigger_conditions"]
                stage_obj.allow_send_back = st["allow_send_back"]
                stage_obj.allow_edit_form_data = st["allow_edit_form_data"]
                stage_obj.requires_manager_approval = False
                stage_obj.save()
            else:
                stage_obj = WorkflowStage.objects.create(
                    workflow=workflow,
                    order=st["order"],
                    name=st["name"],
                    approval_logic=st["approval_logic"],
                    trigger_conditions=st["trigger_conditions"],
                    allow_send_back=st["allow_send_back"],
                    allow_edit_form_data=st["allow_edit_form_data"],
                    requires_manager_approval=False,
                )

            StageApprovalGroup.objects.filter(stage=stage_obj, role="approval").delete()
            for pos, grp in enumerate(st["groups"], start=1):
                StageApprovalGroup.objects.create(
                    stage=stage_obj,
                    group=grp,
                    role="approval",
                    position=pos,
                )

        WorkflowStage.objects.filter(workflow=workflow).exclude(order__in=active_orders).delete()

        # 6. NotificationRules (Selaras 5 aturan standar dengan permohonan-kontrak)
        workflow.notification_rules.filter(
            event="approval_request",
            stage__isnull=False,
        ).delete()

        notif_rules_spec = [
            {
                "event": "submission_received",
                "stage": None,
                "use_triggering_stage": False,
                "defaults": {
                    "notify_submitter": True,
                    "notify_stage_assignees": False,
                    "notify_stage_groups": False,
                    "subject_template": "Release Credit Limit {no_pengajuan} Berhasil Diajukan",
                    "body_template": "",
                },
            },
            {
                "event": "approval_request",
                "stage": None,
                "use_triggering_stage": True,
                "defaults": {
                    "notify_submitter": False,
                    "notify_stage_assignees": True,
                    "notify_stage_groups": True,
                    "subject_template": "Persetujuan Diperlukan: Release Credit Limit {no_pengajuan} - {nama_toko}",
                    "body_template": "",
                },
            },
            {
                "event": "submission_returned",
                "stage": None,
                "use_triggering_stage": False,
                "defaults": {
                    "notify_submitter": True,
                    "notify_stage_assignees": False,
                    "notify_stage_groups": False,
                    "subject_template": "Permintaan Revisi: Release Credit Limit {no_pengajuan} - {nama_toko}",
                    "body_template": "",
                },
            },
            {
                "event": "workflow_denied",
                "stage": None,
                "use_triggering_stage": False,
                "defaults": {
                    "notify_submitter": True,
                    "notify_stage_assignees": False,
                    "notify_stage_groups": False,
                    "subject_template": "Pemberitahuan: Release Credit Limit {no_pengajuan} - {nama_toko} Ditolak",
                    "body_template": "",
                },
            },
            {
                "event": "workflow_approved",
                "stage": None,
                "use_triggering_stage": False,
                "defaults": {
                    "notify_submitter": True,
                    "notify_stage_assignees": False,
                    "notify_stage_groups": False,
                    "subject_template": "Release Credit Limit {no_pengajuan} - {nama_toko} Telah Disetujui (Siap Release JDE)",
                    "body_template": "",
                },
            },
        ]

        allowed_events = [r["event"] for r in notif_rules_spec]
        workflow.notification_rules.exclude(event__in=allowed_events).delete()

        for r in notif_rules_spec:
            existing_qs = NotificationRule.objects.filter(
                workflow=workflow,
                event=r["event"],
                stage=r["stage"],
            ).order_by("id")
            if existing_qs.count() > 1:
                keep_id = existing_qs.first().id
                existing_qs.exclude(id=keep_id).delete()
            NotificationRule.objects.update_or_create(
                workflow=workflow,
                event=r["event"],
                stage=r["stage"],
                defaults={
                    "use_triggering_stage": r["use_triggering_stage"],
                    **r["defaults"],
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Seeded FormDefinition '{form_def.name}' ({form_def.slug}) with {len(active_names)} fields & 4-stage dynamic workflow."
            )
        )
