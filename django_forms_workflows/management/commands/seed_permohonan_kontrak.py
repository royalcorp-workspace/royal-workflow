"""
Management command to seed the multi-step 'Permohonan Kontrak' (Contract Request) form,
complete with 5 dynamic grid widgets, JDE Customer lookup support, legal contract preview,
and the 4-stage approval workflow.

Usage:
    python manage.py seed_permohonan_kontrak
"""

import datetime
import json
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.utils import timezone
from django_forms_workflows.models import (
    FormCategory,
    FormDefinition,
    FormField,
    SharedOptionList,
    WorkflowDefinition,
    WorkflowStage,
    StageApprovalGroup,
    DocumentTemplate,
    NotificationRule,
    FormSubmission,
    ApprovalTask,
)

User = get_user_model()


class Command(BaseCommand):
    help = "Seed the Permohonan Kontrak (Sales & Marketing) form and 4-stage workflow."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("=================================================================")
        self.stdout.write("Seeding 'Permohonan Kontrak' & 4-Stage Approval Workflow...")
        self.stdout.write("=================================================================")

        # 1. Groups & Users
        groups = self._seed_groups()
        users = self._seed_users(groups)

        # 2. Shared Option Lists
        sol_cabang = self._ensure_shared_option_list(
            slug="cabang-list",
            name="Daftar Cabang / Area",
            items=[
                "Bali", "Bandung", "Banyumas", "Cirebon", "Jakarta", "Kediri",
                "Lampung", "Makassar", "Manado", "Medan", "Palembang", "Pekanbaru",
                "Pusat", "R1", "R2", "Semarang", "Surabaya", "Tangerang",
            ],
        )
        sol_brand = self._ensure_shared_option_list(
            slug="brand-list",
            name="Daftar Brand Royal",
            items=["SERENITY", "ROYAL FOAM", "GRAND EXCLUSIVE", "LADY AMERICANA"],
        )
        sol_perusahaan = self._ensure_shared_option_list(
            slug="perusahaan-list",
            name="Daftar Perusahaan (Pihak Pertama)",
            items=[
                "PT Royal Abadi Sejahtera",
                "PT Anugrah Cemerlang Abadi",
                "PT Bangun Cipta Primatara",
                "PT Bestari Mulia",
                "PT Cemerlang Abadi Mulia",
            ],
        )
        sol_identitas = self._ensure_shared_option_list(
            slug="jenis-identitas-list",
            name="Daftar Jenis Identitas",
            items=["NIK", "NPWP"],
        )

        # 3. Category
        category = self._ensure_category(
            slug="sales-marketing",
            name="Sales & Marketing PT RAS",
            description="Formulir pengajuan kontrak ritel, diskon promo, dan perjanjian kerjasama.",
            icon="bi-graph-up-arrow",
            order=20,
        )

        # 4. Form Definition
        form_steps = [
            {
                "title": "Informasi Pengajuan & Toko",
                "fields": [
                    "nomor_spk", "cabang", "brand", "perusahaan",
                    "kode_customer_jde", "nama_toko", "nama_pemilik", "alamat_toko",
                    "no_telepon", "kota", "jenis_identitas", "nomor_identitas",
                    "asset_toko", "market_share"
                ],
            },
            {
                "title": "Detail Kontrak",
                "fields": [
                    "info_kontrak_lama", "tanggal_mulai", "tanggal_berakhir", "durasi", "grace_period",
                    "jenis_pajak", "top", "metode_pembayaran", "discount_do", "ketentuan_do",
                    "target_incentive", "discount_scheme",
                    "is_support_provided",
                    "support_promosi", "pct_support_promo", "frekuensi_pencairan", "syarat_pencairan",
                    "komponen_biaya", "pengecualian_ketentuan_support", "tier_support",
                    "kota_penandatanganan", "tanggal_penandatanganan", "rekening_perusahaan", "catatan_lain"
                ],
            },
            {
                "title": "Preview & Konfirmasi",
                "fields": [
                    "preview_contract_tab",
                    "chk_konfirmasi_data", "chk_konfirmasi_preview"
                ],
            },
        ]

        clean_description = (
            "Formulir pengajuan kontrak kerjasama penjualan toko/dealer ritel "
            "untuk penerbitan Surat Perjanjian Kerjasama (SPK) dan persetujuan bertingkat."
        )

        form = self._ensure_form(
            slug="permohonan-kontrak",
            defaults={
                "category": category,
                "name": "Surat Permohonan Kontrak & Pencairan Kontrak",
                "description": clean_description,
                "enable_multi_step": True,
                "form_steps": form_steps,
                "allow_save_draft": True,
                "allow_withdrawal": True,
                "allow_resubmit": True,
                "pdf_generation": "anytime",
                "is_active": True,
                "is_listed": True,
            },
        )
        if form.description != clean_description:
            form.description = clean_description
            form.save(update_fields=["description"])

        # Assign form access groups: strictly Sales Staff only (initiators)
        self._set_form_groups(
            form,
            submit_groups=[
                groups["Sales Staff"],
            ],
            view_groups=[
                groups["Sales Staff"],
            ],
            admin_groups=[],
            reviewer_groups=[groups["General Manager Sales"], groups["Legal Team"]],
        )

        # 5. Form Fields (43 fields)
        field_definitions = self._get_field_definitions(sol_cabang, sol_brand, sol_perusahaan, sol_identitas)
        self._sync_fields(form, field_definitions)

        # 6. Workflow Definition & Stages
        workflow = self._ensure_workflow(
            form,
            name_label="Contract Approval Workflow",
            defaults={
                "requires_approval": True,
                "allow_bulk_export": True,
            },
        )

        # Run migration for legacy 5-stage workflow if present
        self._migrate_existing_workflow_stages_and_tasks(workflow, groups)

        # Stage 1: Review SPK oleh ASM (Dinamis: supervisor_1) - Unconditional (Always Run)
        st1 = self._ensure_stage(
            workflow,
            name="Review SPK oleh ASM",
            order=1,
            defaults={
                "approval_logic": "any",
                "requires_manager_approval": True,
                "allow_edit_form_data": False,
                "allow_send_back": True,
                "allow_reassign": True,
                "approve_label": "Setujui (ASM)",
                "trigger_conditions": None,
            },
        )
        self._set_stage_groups(st1, [groups["Sales Area Manager"], groups["Branch Manager"]])

        # Stage 2: Review SPK oleh RSOM (Dinamis: supervisor_2) - Unconditional (Always Run)
        st2 = self._ensure_stage(
            workflow,
            name="Review SPK oleh RSOM",
            order=2,
            defaults={
                "approval_logic": "any",
                "requires_manager_approval": True,
                "allow_edit_form_data": False,
                "allow_send_back": True,
                "allow_reassign": True,
                "approve_label": "Setujui (RSOM)",
                "trigger_conditions": None,
            },
        )
        self._set_stage_groups(st2, [groups["Sales Area Manager"], groups["General Manager Sales"]])

        # Stage 3: Review, Penomoran & Koordinasi TTD Toko (Sales Support - Unconditional)
        st3 = self._ensure_stage(
            workflow,
            name="Review, Penomoran & Koordinasi TTD Toko (Sales Support)",
            order=3,
            defaults={
                "approval_logic": "any",
                "requires_manager_approval": False,
                "allow_edit_form_data": False,
                "allow_send_back": True,
                "allow_reassign": True,
                "approve_label": "Approve",
                "trigger_conditions": None,
            },
        )
        self._set_stage_groups(st3, [groups["Sales Support"]])

        # Stage 4: Final Review & Approval (Final Stage)
        st4 = self._ensure_stage(
            workflow,
            name="Final Review & Approval",
            order=4,
            defaults={
                "approval_logic": "any",
                "requires_manager_approval": False,
                "allow_edit_form_data": False,
                "allow_send_back": True,
                "allow_reassign": False,
                "approve_label": "Approve SPK",
                "trigger_conditions": None,
            },
        )
        self._set_stage_groups(st4, [groups["Direksi"]])

        # Ensure tokens exist for any active/pending Stage 3 tasks
        from django_forms_workflows.workflow_engine import ensure_signing_token_for_stage
        for task in ApprovalTask.objects.filter(workflow_stage=st3, status="pending").select_related("submission"):
            ensure_signing_token_for_stage(task.submission, st3, task)

        # 7. Document Template (Surat Perjanjian Kerjasama)
        self._ensure_document_template(form)

        # 8. Notification Rules
        self._ensure_notification_rules(workflow, st1, st4)

        # 9. Clean up any existing submissions with raw markdown in info_kontrak_lama & official SPK format
        for sub in FormSubmission.objects.filter(form_definition=form):
            if sub.form_data:
                updated = False
                for obsolete_chk in [
                    "chk_lampiran_spk_lalu",
                    "chk_asset_toko_diisi",
                    "chk_market_share_diisi",
                    "chk_lampiran_umum",
                ]:
                    if obsolete_chk in sub.form_data:
                        sub.form_data.pop(obsolete_chk, None)
                        updated = True

                val = str(sub.form_data.get("info_kontrak_lama", ""))
                if "[!NOTE]" in val or val.startswith(">"):
                    sub.form_data["info_kontrak_lama"] = (
                        "Status Kontrak: Sistem siap untuk data kontrak tahun sebelumnya. "
                        "Pada pengajuan ini dianggap sebagai kontrak baru / perpanjangan aktif."
                    )
                    updated = True

                spk = str(sub.form_data.get("nomor_spk", ""))
                from django_forms_workflows.company_profiles import format_official_spk_number
                sub.form_data["nomor_spk"] = format_official_spk_number(
                    sub.id,
                    sub.form_data.get("brand", "LADY"),
                    sub.form_data.get("cabang", "Tangerang"),
                    sub.submitted_at or datetime.date.today(),
                )
                updated = True

                if sub.id == 14:
                    sub.form_data["asset_toko"] = json.dumps([
                        {"no": 1, "keterangan": "SENIKMAT MEUBEL", "alamat": "JLN IMAM BONJOL NO 92 SINGARAJA", "status": "Pribadi"}
                    ])
                    sub.form_data["market_share"] = "[]"
                    updated = True

                if updated:
                    sub.save(update_fields=["form_data"])

        # Summary
        self.stdout.write(self.style.SUCCESS("\n[SUCCESS] Seeding Permohonan Kontrak selesai!"))
        self.stdout.write("  • Akun Pengujian (Password: Bandung*123#):")
        self.stdout.write("      - Submitter        : sales.staff")
        self.stdout.write("      - Stage 1 Approver : area.sales.manager (Sales Area Manager / Branch Manager)")
        self.stdout.write("      - Stage 2 Approver : general.manager (General Manager Sales)")
        self.stdout.write("      - Stage 3 Approver : Sales Support (Review, Penomoran & Koordinasi TTD Toko)")
        self.stdout.write("      - Stage 4 Approver : aalvin / Direksi (Review & TTD Final Direksi)")
        self.stdout.write("  • Form Definition : 'permohonan-kontrak' (3 steps, 39 fields, 5 dynamic grids)")
        self.stdout.write("  • Mock JDE Lookup : /api/lookup/jde-customer/?code=150731")
        self.stdout.write("  • Document Template: 'Surat Perjanjian Kerjasama' (SPK)")
        self.stdout.write("  • Workflow Stages : 4 stages (ASM -> RSOM -> Sales Support & TTD Toko -> Direksi Final)")

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _migrate_existing_workflow_stages_and_tasks(self, workflow, groups):
        """Safely migrate legacy 5-stage pipeline to unified 4-stage pipeline.

        Merges legacy Stage 4 ('Verifikasi TTD Toko') into Stage 3 ('Review, Penomoran &
        Koordinasi TTD Toko'), and shifts legacy Stage 5 ('Review & TTD Final Direksi')
        to Stage 4, preserving all ContractSigningToken associations and history.
        """
        st3 = workflow.stages.filter(order=3).first()
        st4 = workflow.stages.filter(order=4).first()
        st5 = workflow.stages.filter(order=5).first()

        if st3:
            st3.name = "Review, Penomoran & Koordinasi TTD Toko (Sales Support)"
            st3.approve_label = "Approve"
            st3.save()

        # Handle legacy stage 5 & stage 4
        if st5:
            # First, resolve any tasks in old stage 4 before moving stage 5 to order 4
            if st4 and st4.id != st5.id:
                for task in ApprovalTask.objects.filter(workflow_stage=st4):
                    # If this submission already has a task in st5, complete the redundant st4 task
                    sub = task.submission
                    if sub and sub.approval_tasks.filter(workflow_stage=st5).exists():
                        task.status = "approved"
                        task.decision = "approve"
                        task.comments = task.comments or "Auto-approved during 4-stage migration (Direksi task active)"
                        if not task.completed_at:
                            task.completed_at = timezone.now()
                    task.workflow_stage = st3
                    task.stage_number = 3
                    task.step_name = "Stage 3"
                    task.save()
                st4.delete()

            # Now update all tasks belonging to st5 to stage_number=4
            ApprovalTask.objects.filter(workflow_stage=st5).update(stage_number=4, step_name="Stage 4")
            st5.order = 4
            st5.name = "Final Review & Approval"
            st5.approve_label = "Approve SPK"
            st5.save()
        elif st4:
            # st4 is already order 4; verify if it was the old 'Verifikasi TTD Toko' without st5
            if "toko" in (st4.name or "").lower():
                ApprovalTask.objects.filter(workflow_stage=st4).update(workflow_stage=st3, stage_number=3, step_name="Stage 3")
                st4.name = "Final Review & Approval"
                st4.approve_label = "Approve SPK"
                st4.save()

    def _seed_groups(self):
        group_names = [
            "Sales Staff",
            "Sales Area Manager",
            "Branch Manager",
            "General Manager Sales",
            "Commercial Director",
            "Finance Team",
            "Legal Team",
            "Sales Support",
            "Direksi",
            "Sales And Marketing",
        ]
        groups = {}
        for name in group_names:
            grp, _ = Group.objects.get_or_create(name=name)
            groups[name] = grp
        return groups

    def _seed_users(self, groups):
        default_pwd = "Bandung*123#"
        user_specs = [
            {
                "username": "sales.staff",
                "email": "sales.staff@royal.local",
                "first_name": "Sales",
                "last_name": "Staff",
                "is_staff": False,
                "groups": ["Sales Staff"],
            },
            {
                "username": "area.sales.manager",
                "email": "area.sales.manager@royal.local",
                "first_name": "Area",
                "last_name": "Sales Manager",
                "is_staff": True,
                "groups": ["Sales Area Manager", "Branch Manager"],
            },
            {
                "username": "general.manager",
                "email": "general.manager@royal.local",
                "first_name": "General",
                "last_name": "Manager",
                "is_staff": True,
                "groups": ["General Manager Sales", "Commercial Director"],
            },
            {
                "username": "approver.finance",
                "email": "approver.finance@royal.local",
                "first_name": "Finance",
                "last_name": "Approver",
                "is_staff": True,
                "groups": ["Finance Team"],
            },
            {
                "username": "legal.officer",
                "email": "legal.officer@royal.local",
                "first_name": "Legal",
                "last_name": "Officer",
                "is_staff": True,
                "groups": ["Legal Team"],
            },
            {
                "username": "aalvin",
                "email": "aalvin@royalcorp.co.id",
                "first_name": "Alvin",
                "last_name": "Steven",
                "is_staff": False,
                "groups": ["Direksi"],
            },
        ]

        users = {}
        for spec in user_specs:
            user, created = User.objects.get_or_create(
                username=spec["username"],
                defaults={
                    "email": spec["email"],
                    "first_name": spec["first_name"],
                    "last_name": spec["last_name"],
                    "is_staff": spec["is_staff"],
                },
            )
            user.set_password(default_pwd)
            user.is_staff = spec["is_staff"]
            user.save()

            for grp_name in spec["groups"]:
                if grp_name in groups:
                    user.groups.add(groups[grp_name])

            users[spec["username"]] = user

        return users

    def _ensure_shared_option_list(self, slug, name, items):
        sol, _ = SharedOptionList.objects.update_or_create(
            slug=slug,
            defaults={"name": name, "items": items, "is_active": True},
        )
        return sol

    def _ensure_category(self, slug, name, description, icon, order):
        cat, _ = FormCategory.objects.update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "description": description,
                "icon": icon,
                "order": order,
            },
        )
        return cat

    def _ensure_form(self, slug, defaults):
        form, _ = FormDefinition.objects.update_or_create(slug=slug, defaults=defaults)
        return form

    def _set_form_groups(self, form, *, submit_groups, view_groups, admin_groups, reviewer_groups):
        form.submit_groups.set(submit_groups)
        form.view_groups.set(view_groups)
        form.admin_groups.set(admin_groups)
        form.reviewer_groups.set(reviewer_groups)

    def _ensure_field(self, form, field_name, defaults):
        field, _ = FormField.objects.update_or_create(
            form_definition=form,
            field_name=field_name,
            defaults=defaults,
        )
        return field

    def _sync_fields(self, form, field_defs):
        valid_names = set()
        for field_def in field_defs:
            field_copy = dict(field_def)
            field_name = field_copy.pop("field_name")
            valid_names.add(field_name)
            self._ensure_field(form, field_name, field_copy)
        # Delete obsolete fields not in the active definitions
        form.fields.exclude(field_name__in=valid_names).delete()

    def _ensure_workflow(self, form, name_label, defaults):
        wf, _ = WorkflowDefinition.objects.update_or_create(
            form_definition=form,
            name_label=name_label,
            defaults=defaults,
        )
        return wf

    def _ensure_stage(self, workflow, name, order, defaults):
        st, _ = WorkflowStage.objects.update_or_create(
            workflow=workflow,
            order=order,
            defaults={"name": name, **defaults},
        )
        return st

    def _set_stage_groups(self, stage, groups):
        stage.approval_groups.set(groups)
        for position, grp in enumerate(groups, start=1):
            StageApprovalGroup.objects.update_or_create(
                stage=stage,
                group=grp,
                role="approval",
                defaults={"position": position},
            )

    def _ensure_document_template(self, form):
        spk_standard_html = """
<div class="spk-paper-preview contract-paper-pages" style="font-family: 'Times New Roman', Times, serif; font-size: 13.5px; line-height: 1.5; color: #111827; max-width: 820px; margin: 0 auto;">
    <!-- ==================== HALAMAN 1 (STANDARD) ==================== -->
    <div class="spk-page-sheet">
        <div class="spk-page-content">
            <!-- KOP SURAT RESMI -->
            <div style="text-align: center; margin-bottom: 20px;">
                <div style="margin-bottom: 8px;">{company_header_logo}</div>
                <h2 style="font-size: 16px; font-weight: bold; margin: 0; text-transform: uppercase; letter-spacing: 0.5px;">SURAT PERJANJIAN KERJASAMA</h2>
                <div style="font-size: 13.5px; font-weight: bold; margin-top: 4px;">{nomor_spk}</div>
            </div>

            <!-- IDENTITAS PARA PIHAK -->
            <p style="margin-bottom: 6px;">Yang bertanda tangan di bawah ini :</p>
            
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 8px; margin-left: 15px;">
                <tr><td style="width: 130px; vertical-align: top;">Nama</td><td style="width: 15px; vertical-align: top;">:</td><td style="font-weight: bold;">{pihak_pertama_nama}</td></tr>
                <tr><td style="vertical-align: top;">Jabatan</td><td style="vertical-align: top;">:</td><td style="font-weight: bold;">{pihak_pertama_jabatan}</td></tr>
                <tr><td style="vertical-align: top;">Alamat</td><td style="vertical-align: top;">:</td><td>{pihak_pertama_alamat}</td></tr>
            </table>
            
            <p style="margin-bottom: 12px;">Selanjutnya disebut sebagai <strong>PIHAK PERTAMA</strong> selaku Produsen produk Springbed merk <strong>“{brand}”</strong></p>

            <table style="width: 100%; border-collapse: collapse; margin-bottom: 8px; margin-left: 15px;">
                <tr><td style="width: 130px; vertical-align: top;">Nama</td><td style="width: 15px; vertical-align: top;">:</td><td style="font-weight: bold;">{nama_pemilik}</td></tr>
                <tr><td style="vertical-align: top;">Pemilik Tk.</td><td style="vertical-align: top;">:</td><td style="font-weight: bold;">{nama_toko}</td></tr>
                <tr><td style="vertical-align: top;">Alamat</td><td style="vertical-align: top;">:</td><td>{alamat_toko}</td></tr>
                <tr><td style="vertical-align: top;">NIK / NPWP</td><td style="vertical-align: top;">:</td><td>{nomor_identitas}</td></tr>
            </table>

            <p style="margin-bottom: 12px;">Selanjutnya disebut sebagai <strong>PIHAK KEDUA</strong> Dealer produk Springbed merk <strong>“{brand}”</strong></p>

            <p style="text-align: justify; margin-bottom: 16px;">
                Dalam upaya meningkatkan kerjasama dalam penjualan produk <strong>{brand}</strong>, kedua belah pihak di atas sepakat untuk menandatangani kontrak perjanjian kerja sama dengan mengikuti syarat – syarat dan ketentuan – ketentuan sebagai berikut :
            </p>

            <!-- BAB I -->
            <div style="text-align: center; font-weight: bold; margin-top: 18px; margin-bottom: 8px;">
                BAB I<br>OBJEK PERJANJIAN
            </div>
            <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 1</div>
            <p style="text-align: justify; margin-bottom: 12px;">
                <strong>Pihak Pertama</strong> menitipkan/menjual kepada <strong>Pihak Kedua</strong> Produk Springbed dengan merk “ <strong>{brand}</strong> “ untuk dijual oleh <strong>Pihak Kedua</strong> pada tempat yang telah diberitahukan dan disetujui oleh <strong>Pihak Pertama</strong> dengan mengacu pada ketentuan Volume dan Harga Penjualan yang telah di sepakati.
            </p>

            <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 2</div>
            <p style="text-align: justify; margin-bottom: 16px;">
                Omzet penjualan {brand} PIHAK KEDUA dihitung berdasarkan harga setelah dikurangi potongan retur, discount dan potongan – potongan lainnya (harga netto), berdasarkan price list yang berlaku mulai tanggal 1 Februari 2023 dan mengikuti perubahannya. (Harga tidak mengikat)
            </p>

            <!-- BAB II (11 PASAL VERSION) -->
            <div style="text-align: center; font-weight: bold; margin-top: 18px; margin-bottom: 8px;">
                BAB II<br>VOLUME PENJUALAN dan PENGHARGAAN – PERIODE KONTRAK - SKEMA DISCOUNT
            </div>
            
            <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 3</div>
            <div style="margin-top: 0; margin-bottom: 12px;">
                <p style="text-align: justify; margin-bottom: 4px; text-indent: -24px; padding-left: 24px;">(1) Para Pihak sepakat bahwa Target Volume Penjualan produk selama jangka waktu perjanjian ini <strong>{target_volume_text}</strong> per bulan Exclude Ppn.</p>
                <p style="text-align: justify; margin-bottom: 0; text-indent: -24px; padding-left: 24px;">(2) Pihak Kedua wajib memenuhi Volume Penjualan yang telah ditentukan dalam perjanjian ini.</p>
            </div>
            <div style="margin-bottom: 12px;">{target_incentive_table}</div>

            <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 4</div>
            <p style="text-align: justify; margin-bottom: 12px;">
                Perjanjian berlaku untuk Jangka Waktu <strong>{durasi}</strong> terhitung dari sejak tanggal <strong>{tanggal_mulai}</strong> dan akan berakhir pada tanggal <strong>{tanggal_berakhir}</strong>.
            </p>

            <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 5</div>
            <p style="text-align: justify; margin-bottom: 6px;">
                Skema discount untuk penjualan Produk yang berlaku untuk Pihak Kedua dalam Perjanjian ini adalah sebagai berikut :
            </p>
            <div style="margin-bottom: 12px;">{discount_scheme_table}</div>
        </div>
        <div class="spk-page-footer">Halaman 1 dari 2</div>
    </div>

    <!-- ==================== HALAMAN 2 (STANDARD) ==================== -->
    <div class="spk-page-sheet">
        <div class="spk-page-content">
            <div style="text-align: center; margin-bottom: 15px;">
                <div style="margin-bottom: 8px;">{company_header_logo}</div>
            </div>

            <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 6</div>
            <p style="text-align: justify; margin-bottom: 6px;">
                Pihak Pertama memberikan kompensasi Insentive Reward kepada Pihak Kedua saat perjanjian ini berakhir dan seluruh kewajiban Pihak Kedua kepada Pihak Pertama telah selesai atau LUNAS<br>
                Adapun perhitungan insentif adalah sebagai berikut :
            </p>
            <div style="margin-left: 15px; margin-bottom: 16px;">
                <p style="margin: 3px 0;">• Target Rp. {target_per_periode} per {frekuensi_bulan} Bulan mendapatkan insentif reward {reward_rate}</p>
                <table style="width: 100%; border-collapse: collapse; margin-top: 4px;">
                    <tr><td style="width: 250px;">Insentive Reward</td><td style="width: 15px;">=</td><td>Rp. {insentive_reward_nominal} &nbsp; &nbsp; ( {reward_rate} x Pencapaian Omzet )</td></tr>
                    <tr><td>Pph 23 Untuk Insentive Kontrak</td><td>=</td><td>Rp. {pph23_nominal} &nbsp; &nbsp; ( Insentive x 15% )</td></tr>
                    <tr><td>Netto Reward</td><td>=</td><td>Rp. {netto_reward_nominal} &nbsp; &nbsp; (Total Insentive – Pph 23)</td></tr>
                </table>
                <p style="margin-top: 6px; font-weight: bold;">Maka insentive yang dibayarkan adalah sebesar Rp. {netto_reward_nominal}.</p>
            </div>

            <!-- BAB III -->
            <div style="text-align: center; font-weight: bold; margin-top: 18px; margin-bottom: 8px;">
                BAB III<br>TATA CARA PEMBAYARAN
            </div>
            
            <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 7</div>
            <p style="text-align: justify; margin-bottom: 12px;">
                Wajib melaksanakan Pembayaran kepada Pihak Pertama paling lambat <strong>{top}</strong> hari setelah tanggal pengiriman ( selanjutnya disebut “ Jangka Waktu Pembayaran” ).
            </p>

            <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 8</div>
            <p style="text-align: justify; margin-bottom: 12px;">
                Sistem pembayaran melalui Transfer atau buka Cek/Giro yang telah di tulis nama <strong>{perusahaan}</strong> dengan Nomer Rekening sesuai yang ada pada Faktur dan kontrabon. Serta <strong>TIDAK DIPERKENANKAN</strong> membayar secara TUNAI kepada Salesman/Collector/Kepala Depo/ASM/BM atau menitip pembayaran kepada Supir maupun Karyawan lainnya.
            </p>

            <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 9</div>
            <p style="text-align: justify; margin-bottom: 6px;">
                Pembayaran dianggap sah apabila dana telah masuk ke rekening {perusahaan}, dengan nomer rekening sbb :
            </p>
            <div style="text-align: center; margin: 8px 0;">
                <table style="margin: 0 auto; border-collapse: collapse; border: none; font-size: 13.5px; font-weight: bold;">
                    <tr>
                        <td style="padding: 1px 4px; text-align: left; width: 75px; border: none;">AN</td>
                        <td style="padding: 1px 4px; text-align: center; width: 15px; border: none;">:</td>
                        <td style="padding: 1px 4px; text-align: left; border: none;">{bank_account_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 1px 4px; text-align: left; border: none;">BANK</td>
                        <td style="padding: 1px 4px; text-align: center; border: none;">:</td>
                        <td style="padding: 1px 4px; text-align: left; border: none;">{bank_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 1px 4px; text-align: left; border: none;">NO REK</td>
                        <td style="padding: 1px 4px; text-align: center; border: none;">:</td>
                        <td style="padding: 1px 4px; text-align: left; border: none;">{bank_account_no}</td>
                    </tr>
                </table>
            </div>
            <p style="text-align: justify; margin-bottom: 16px;">
                Walaupun nota asli sudah di serahkan / dititipkan oleh salesman maka belum dianggap sebagai pembayaran.
            </p>

            <!-- BAB IV -->
            <div style="text-align: center; font-weight: bold; margin-top: 18px; margin-bottom: 8px;">
                BAB IV<br>ITIKAD BAIK DAN PERSELISIHAN
            </div>
            
            <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 10</div>
            <p style="text-align: justify; margin-bottom: 12px;">
                Para pihak dengan itikad baik dan penuh tanggung jawab menjalankan tugas, hak dan kewajibannya dengan mengindahkan peraturan perundangan yang berlaku.
            </p>

            <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 11</div>
            <p style="text-align: justify; margin-bottom: 14px;">
                Apabila terjadi perselisihan/sengketa diantara Para Pihak terkait dengan isi dan/atau Pelaksanaan Perjanjian ini maka perselisihan tersebut akan di selesaikan terlebih dahulu melalui musyawarah mufakat diantara Para Pihak. Apabila dengan cara musyawarah mufakat tidak dapat dilakukan atau tidak tercapai sesuatu penyelesaian yang baik bagi Para Pihak maka Para Pihak sepakat untuk memilih <strong>{pengadilan_negeri}</strong> sebagai satu satunya domisili hukum yang tetap bagi Para Pihak.
            </p>

            <p style="text-align: justify; margin-bottom: 24px;">
                DENGAN DEMIKIAN,Para Pihak telah menandatangani Perjanjian ini dalam 2 (dua) rangkap yang masing-masing berlaku sebagai asli, bermaterai cukup dan berkekuatan hukum yang sama yang dapat dipergunakan secara sah sebagai bukti adanya kesepakatan diantara Para Pihak.
            </p>

            <!-- BLOK TANDA TANGAN -->
            <div style="margin-top: 25px;">
                <div style="text-align: left; margin-bottom: 15px; font-weight: bold;">
                    {kota_penandatanganan}, {tanggal_penandatanganan}
                </div>
                <table style="width: 100%; border-collapse: collapse; text-align: center;">
                    <tr>
                        <td style="width: 50%; font-weight: bold; vertical-align: top;">
                            PIHAK PERTAMA<br>
                            {perusahaan}
                        </td>
                        <td style="width: 50%; font-weight: bold; vertical-align: top;">
                            PIHAK KEDUA<br>
                            {nama_toko}
                        </td>
                    </tr>
                    <tr>
                        <td style="height: 90px; vertical-align: middle;">
                            {ttd_direksi_image}
                        </td>
                        <td style="height: 90px; vertical-align: middle;">
                            {ttd_toko_image}
                        </td>
                    </tr>
                    <tr>
                        <td style="vertical-align: top;">
                            <div style="border-bottom: 1px solid #111; display: inline-block; min-width: 180px; font-weight: bold;">{pihak_pertama_nama}</div><br>
                            Direktur
                        </td>
                        <td style="vertical-align: top;">
                            <div style="border-bottom: 1px solid #111; display: inline-block; min-width: 180px; font-weight: bold;">{nama_pemilik}</div><br>
                            Pemilik Toko
                        </td>
                    </tr>
                </table>
            </div>
        </div>
        <div class="spk-page-footer">Halaman 2 dari 2</div>
    </div>
</div>
        """

        spk_support_html = """
<div class="spk-paper-preview contract-paper-pages" style="font-family: 'Times New Roman', Times, serif; font-size: 13.5px; line-height: 1.5; color: #111827; max-width: 820px; margin: 0 auto;">
    <!-- ==================== HALAMAN 1 (SUPPORT PROMOSI) ==================== -->
    <div class="spk-page-sheet">
        <div class="spk-page-content">
            <!-- KOP SURAT RESMI -->
            <div style="text-align: center; margin-bottom: 20px;">
                <div style="margin-bottom: 8px;">{company_header_logo}</div>
                <h2 style="font-size: 16px; font-weight: bold; margin: 0; text-transform: uppercase; letter-spacing: 0.5px;">SURAT PERJANJIAN KERJASAMA</h2>
                <div style="font-size: 13.5px; font-weight: bold; margin-top: 4px;">{nomor_spk}</div>
            </div>

            <!-- IDENTITAS PARA PIHAK -->
            <p style="margin-bottom: 6px;">Yang bertanda tangan di bawah ini :</p>
            
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 8px; margin-left: 15px;">
                <tr><td style="width: 130px; vertical-align: top;">Nama</td><td style="width: 15px; vertical-align: top;">:</td><td style="font-weight: bold;">{pihak_pertama_nama}</td></tr>
                <tr><td style="vertical-align: top;">Jabatan</td><td style="vertical-align: top;">:</td><td style="font-weight: bold;">{pihak_pertama_jabatan}</td></tr>
                <tr><td style="vertical-align: top;">Alamat</td><td style="vertical-align: top;">:</td><td>{pihak_pertama_alamat}</td></tr>
            </table>
            
            <p style="margin-bottom: 12px;">Selanjutnya disebut sebagai <strong>PIHAK PERTAMA</strong> selaku Produsen produk Springbed merk <strong>“{brand}”</strong></p>

            <table style="width: 100%; border-collapse: collapse; margin-bottom: 8px; margin-left: 15px;">
                <tr><td style="width: 130px; vertical-align: top;">Nama</td><td style="width: 15px; vertical-align: top;">:</td><td style="font-weight: bold;">{nama_pemilik}</td></tr>
                <tr><td style="vertical-align: top;">Pemilik Tk.</td><td style="vertical-align: top;">:</td><td style="font-weight: bold;">{nama_toko}</td></tr>
                <tr><td style="vertical-align: top;">Alamat</td><td style="vertical-align: top;">:</td><td>{alamat_toko}</td></tr>
                <tr><td style="vertical-align: top;">NIK / NPWP</td><td style="vertical-align: top;">:</td><td>{nomor_identitas}</td></tr>
            </table>

            <p style="margin-bottom: 12px;">Selanjutnya disebut sebagai <strong>PIHAK KEDUA</strong> Dealer produk Springbed merk <strong>“{brand}”</strong></p>

            <p style="text-align: justify; margin-bottom: 16px;">
                Dalam upaya meningkatkan kerjasama dalam penjualan produk <strong>{brand}</strong>, kedua belah pihak di atas sepakat untuk menandatangani kontrak perjanjian kerja sama dengan mengikuti syarat – syarat dan ketentuan – ketentuan sebagai berikut :
            </p>

            <!-- BAB I -->
            <div style="text-align: center; font-weight: bold; margin-top: 18px; margin-bottom: 8px;">
                BAB I<br>OBJEK PERJANJIAN
            </div>
            <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 1</div>
            <p style="text-align: justify; margin-bottom: 12px;">
                <strong>Pihak Pertama</strong> menitipkan/menjual kepada <strong>Pihak Kedua</strong> Produk Springbed dengan merk “ <strong>{brand}</strong> “ untuk dijual oleh <strong>Pihak Kedua</strong> pada tempat yang telah diberitahukan dan disetujui oleh <strong>Pihak Pertama</strong> dengan mengacu pada ketentuan Volume dan Harga Penjualan yang telah di sepakati.
            </p>

            <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 2</div>
            <p style="text-align: justify; margin-bottom: 16px;">
                Omzet penjualan {brand} PIHAK KEDUA dihitung berdasarkan harga setelah dikurangi potongan retur, discount dan potongan – potongan lainnya (harga netto), berdasarkan price list yang berlaku mulai tanggal 1 Februari 2023 dan mengikuti perubahannya. (Harga tidak mengikat)
            </p>

            <!-- BAB II: KONTRAK + SUPPORT PROMOSI (12 PASAL) -->
            <div style="text-align: center; font-weight: bold; margin-top: 18px; margin-bottom: 8px;">
                BAB II<br>VOLUME PENJUALAN dan PENGHARGAAN – PERIODE KONTRAK - SKEMA DISCOUNT
            </div>
            
            <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 3</div>
            <div style="margin-top: 0; margin-bottom: 12px;">
                <p style="text-align: justify; margin-bottom: 4px; text-indent: -24px; padding-left: 24px;">(1) Para Pihak sepakat bahwa Target Volume Penjualan produk selama jangka waktu perjanjian ini <strong>{target_volume_text}</strong> per bulan Exclude Ppn.</p>
                <p style="text-align: justify; margin-bottom: 0; text-indent: -24px; padding-left: 24px;">(2) Pihak Kedua wajib memenuhi Volume Penjualan yang telah ditentukan dalam perjanjian ini.</p>
            </div>
            <div style="margin-bottom: 12px;">{target_incentive_table}</div>

            <!-- PASAL 4 KHUSUS SUPPORT PROMOSI -->
            <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 4</div>
            <ol style="margin-top: 0; margin-bottom: 12px; padding-left: 20px;">
                <li style="text-align: justify; margin-bottom: 4px;">Pihak Pertama memberikan support promosi yang meliputi biaya (sewa, instore, pameran, listrik, dan asuransi) kepada Pihak Kedua sebesar <strong>{pct_support_promo}%</strong>. Support promosi tersebut <strong>TIDAK</strong> meliputi biaya Billboard, Pajak Billboard, dan Backdrop apabila Pihak Kedua membuka cabang baru atau toko baru.</li>
                <li style="text-align: justify; margin-bottom: 4px;">Support promosi ini dapat dicairkan setelah pembayaran <strong>LUNAS</strong>.</li>
                <li style="text-align: justify;">Grace period selama 1 (satu) bulan dari masa kontrak berakhir, apabila Pihak Kedua belum mencapai target.</li>
            </ol>

            <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 5</div>
            <p style="text-align: justify; margin-bottom: 12px;">
                Perjanjian berlaku untuk Jangka Waktu <strong>{durasi}</strong> terhitung dari sejak tanggal <strong>{tanggal_mulai}</strong> dan akan berakhir pada tanggal <strong>{tanggal_berakhir}</strong>.
            </p>

            <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 6</div>
            <p style="text-align: justify; margin-bottom: 6px;">
                Skema discount untuk penjualan Produk yang berlaku untuk Pihak Kedua dalam Perjanjian ini adalah sebagai berikut :
            </p>
            <div style="margin-bottom: 12px;">{discount_scheme_table}</div>
        </div>
        <div class="spk-page-footer">Halaman 1 dari 2</div>
    </div>

    <!-- ==================== HALAMAN 2 (SUPPORT PROMOSI) ==================== -->
    <div class="spk-page-sheet">
        <div class="spk-page-content">
            <div style="text-align: center; margin-bottom: 15px;">
                <div style="margin-bottom: 8px;">{company_header_logo}</div>
            </div>

            <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 7</div>
            <p style="text-align: justify; margin-bottom: 6px;">
                Pihak Pertama memberikan kompensasi Insentive Reward kepada Pihak Kedua saat perjanjian ini berakhir dan seluruh kewajiban Pihak Kedua kepada Pihak Pertama telah selesai atau LUNAS<br>
                Adapun perhitungan insentif adalah sebagai berikut :
            </p>
            <div style="margin-left: 15px; margin-bottom: 16px;">
                <p style="margin: 3px 0;">• Target Rp. {target_per_periode} per {frekuensi_bulan} Bulan mendapatkan reward (support promosi) {pct_support_promo}%</p>
                <table style="width: 100%; border-collapse: collapse; margin-top: 4px;">
                    <tr><td style="width: 250px;">Insentive Reward</td><td style="width: 15px;">=</td><td>Rp. {insentive_reward_nominal} &nbsp; &nbsp; ( {pct_support_promo}% x Pencapaian Omzet )</td></tr>
                    <tr><td>Pph 23 Untuk Insentive Kontrak</td><td>=</td><td>Rp. {pph23_nominal} &nbsp; &nbsp; ( Reward x 2% )</td></tr>
                    <tr><td>Netto Reward</td><td>=</td><td>Rp. {netto_reward_nominal} &nbsp; &nbsp; (Total Insentive – Pph 23)</td></tr>
                </table>
                <p style="margin-top: 6px; font-weight: bold;">Maka insentive yang dibayarkan adalah sebesar Rp. {netto_reward_nominal}.</p>
            </div>
            <div style="margin-bottom: 12px;">{tier_support_table}</div>

            <!-- BAB III (PASAL 8, 9, 10) -->
            <div style="text-align: center; font-weight: bold; margin-top: 18px; margin-bottom: 8px;">
                BAB III<br>TATA CARA PEMBAYARAN
            </div>
            
            <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 8</div>
            <p style="text-align: justify; margin-bottom: 12px;">
                Wajib melaksanakan Pembayaran kepada Pihak Pertama paling lambat <strong>{top}</strong> hari setelah tanggal pengiriman ( selanjutnya disebut “ Jangka Waktu Pembayaran” ).
            </p>

            <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 9</div>
            <p style="text-align: justify; margin-bottom: 12px;">
                Sistem pembayaran melalui Transfer atau buka Cek/Giro yang telah di tulis nama <strong>{perusahaan}</strong> dengan Nomer Rekening sesuai yang ada pada Faktur dan kontrabon. Serta <strong>TIDAK DIPERKENANKAN</strong> membayar secara TUNAI kepada Salesman/Collector/Kepala Depo/ASM/BM atau menitip pembayaran kepada Supir maupun Karyawan lainnya.
            </p>

            <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 10</div>
            <p style="text-align: justify; margin-bottom: 6px;">
                Pembayaran dianggap sah apabila dana telah masuk ke rekening {perusahaan}, dengan nomer rekening sbb :
            </p>
            <div style="text-align: center; margin: 8px 0;">
                <table style="margin: 0 auto; border-collapse: collapse; border: none; font-size: 13.5px; font-weight: bold;">
                    <tr>
                        <td style="padding: 1px 4px; text-align: left; width: 75px; border: none;">AN</td>
                        <td style="padding: 1px 4px; text-align: center; width: 15px; border: none;">:</td>
                        <td style="padding: 1px 4px; text-align: left; border: none;">{bank_account_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 1px 4px; text-align: left; border: none;">BANK</td>
                        <td style="padding: 1px 4px; text-align: center; border: none;">:</td>
                        <td style="padding: 1px 4px; text-align: left; border: none;">{bank_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 1px 4px; text-align: left; border: none;">NO REK</td>
                        <td style="padding: 1px 4px; text-align: center; border: none;">:</td>
                        <td style="padding: 1px 4px; text-align: left; border: none;">{bank_account_no}</td>
                    </tr>
                </table>
            </div>
            <p style="text-align: justify; margin-bottom: 16px;">
                Walaupun nota asli sudah di serahkan / dititipkan oleh salesman maka belum dianggap sebagai pembayaran.
            </p>

            <!-- BAB IV (PASAL 11 & 12) -->
            <div style="text-align: center; font-weight: bold; margin-top: 18px; margin-bottom: 8px;">
                BAB IV<br>ITIKAD BAIK DAN PERSELISIHAN
            </div>
            
            <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 11</div>
            <p style="text-align: justify; margin-bottom: 12px;">
                Para pihak dengan itikad baik dan penuh tanggung jawab menjalankan tugas, hak dan kewajibannya dengan mengindahkan peraturan perundangan yang berlaku.
            </p>

            <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 12</div>
            <p style="text-align: justify; margin-bottom: 14px;">
                Apabila terjadi perselisihan/sengketa diantara Para Pihak terkait dengan isi dan/atau Pelaksanaan Perjanjian ini maka perselisihan tersebut akan di selesaikan terlebih dahulu melalui musyawarah mufakat diantara Para Pihak. Apabila dengan cara musyawarah mufakat tidak dapat dilakukan atau tidak tercapai sesuatu penyelesaian yang baik bagi Para Pihak maka Para Pihak sepakat untuk memilih <strong>{pengadilan_negeri}</strong> sebagai satu satunya domisili hukum yang tetap bagi Para Pihak.
            </p>

            <p style="text-align: justify; margin-bottom: 24px;">
                DENGAN DEMIKIAN,Para Pihak telah menandatangani Perjanjian ini dalam 2 (dua) rangkap yang masing-masing berlaku sebagai asli, bermaterai cukup dan berkekuatan hukum yang sama yang dapat dipergunakan secara sah sebagai bukti adanya kesepakatan diantara Para Pihak.
            </p>

            <!-- BLOK TANDA TANGAN -->
            <div style="margin-top: 25px;">
                <div style="text-align: left; margin-bottom: 15px; font-weight: bold;">
                    {kota_penandatanganan}, {tanggal_penandatanganan}
                </div>
                <table style="width: 100%; border-collapse: collapse; text-align: center;">
                    <tr>
                        <td style="width: 50%; font-weight: bold; vertical-align: top;">
                            PIHAK PERTAMA<br>
                            {perusahaan}
                        </td>
                        <td style="width: 50%; font-weight: bold; vertical-align: top;">
                            PIHAK KEDUA<br>
                            {nama_toko}
                        </td>
                    </tr>
                    <tr>
                        <td style="height: 90px; vertical-align: middle;">
                            {ttd_direksi_image}
                        </td>
                        <td style="height: 90px; vertical-align: middle;">
                            {ttd_toko_image}
                        </td>
                    </tr>
                    <tr>
                        <td style="vertical-align: top;">
                            <div style="border-bottom: 1px solid #111; display: inline-block; min-width: 180px; font-weight: bold;">{pihak_pertama_nama}</div><br>
                            Direktur
                        </td>
                        <td style="vertical-align: top;">
                            <div style="border-bottom: 1px solid #111; display: inline-block; min-width: 180px; font-weight: bold;">{nama_pemilik}</div><br>
                            Pemilik Toko
                        </td>
                    </tr>
                </table>
            </div>
        </div>
        <div class="spk-page-footer">Halaman 2 dari 2</div>
    </div>
</div>
        """

        # Register Template 1: Standard (11 Pasal) - Default
        DocumentTemplate.objects.update_or_create(
            form_definition=form,
            name="Surat Perjanjian Kerjasama (Standard)",
            defaults={
                "is_default": True,
                "is_active": True,
                "html_content": spk_standard_html.strip(),
                "page_size": "a4",
            },
        )

        # Register Template 2: Support Promosi (12 Pasal)
        DocumentTemplate.objects.update_or_create(
            form_definition=form,
            name="Surat Perjanjian Kerjasama (Support Promosi)",
            defaults={
                "is_default": False,
                "is_active": True,
                "html_content": spk_support_html.strip(),
                "page_size": "a4",
            },
        )

        # Also update legacy name 'Surat Perjanjian Kerjasama' if exists for compatibility
        DocumentTemplate.objects.filter(
            form_definition=form,
            name="Surat Perjanjian Kerjasama",
        ).update(
            html_content=spk_standard_html.strip(),
            name="Surat Perjanjian Kerjasama (Standard)",
            is_default=True,
        )

    def _ensure_notification_rules(self, workflow, st1, st4):
        rules = [
            {
                "event": "submission_received",
                "stage": None,
                "defaults": {
                    "notify_submitter": True,
                    "subject_template": "Permohonan Kontrak {nomor_spk} Berhasil Diajukan",
                    "body_template": "Pengajuan kontrak kerjasama untuk toko {nama_toko} telah diterima dan sedang diproses pada tahap Review ASM.",
                },
            },
            {
                "event": "approval_request",
                "stage": st1,
                "defaults": {
                    "notify_stage_groups": True,
                    "notify_stage_assignees": True,
                    "subject_template": "Persetujuan Diperlukan: Permohonan Kontrak {nomor_spk} - {nama_toko}",
                    "body_template": "Permohonan kontrak baru untuk toko {nama_toko} menunggu review dan persetujuan Anda.",
                },
            },
            {
                "event": "workflow_approved",
                "stage": None,
                "defaults": {
                    "notify_submitter": True,
                    "subject_template": "Selamat! Permohonan Kontrak {nomor_spk} Telah Disetujui Penuh",
                    "body_template": "Permohonan kontrak untuk toko {nama_toko} telah disetujui hingga tahap Final Sign-off. Surat Perjanjian Kerjasama telah resmi berlaku.",
                },
            },
        ]

        for r in rules:
            NotificationRule.objects.update_or_create(
                workflow=workflow,
                event=r["event"],
                stage=r["stage"],
                defaults=r["defaults"],
            )

    def _get_field_definitions(self, sol_cabang, sol_brand, sol_perusahaan, sol_identitas):
        fields = [
            # -----------------------------------------------------------------
            # Step 1: Informasi Pengajuan & Toko
            # -----------------------------------------------------------------
            {
                "field_name": "nomor_spk",
                "field_label": "Nomor SPK",
                "field_type": "text",
                "width": "half",
                "order": 1,
                "step_number": 1,
                "required": False,
                "readonly": True,
                "default_value": "",
                "placeholder": "—",
                "help_text": "Terbit otomatis sesuai Brand dan Cabang.",
            },
            {
                "field_name": "cabang",
                "field_label": "Cabang / Area",
                "field_type": "select",
                "width": "half",
                "order": 2,
                "step_number": 1,
                "required": False,
                "readonly": True,
                "css_class": "field-readonly",
                "shared_option_list": sol_cabang,
                "help_text": "Terkunci otomatis sesuai kantor cabang pemohon.",
            },
            {
                "field_name": "brand",
                "field_label": "Brand Produk",
                "field_type": "select",
                "width": "half",
                "order": 3,
                "step_number": 1,
                "required": True,
                "readonly": False,
                "shared_option_list": sol_brand,
                "help_text": "Pilih brand utama kontrak kerjasama.",
            },
            {
                "field_name": "perusahaan",
                "field_label": "Perusahaan (Pihak Pertama)",
                "field_type": "select",
                "width": "half",
                "order": 4,
                "step_number": 1,
                "required": False,
                "readonly": True,
                "css_class": "field-readonly",
                "shared_option_list": sol_perusahaan,
                "help_text": "Terkunci otomatis sesuai badan hukum pemohon.",
            },
            {
                "field_name": "kode_customer_jde",
                "field_label": "Kode Customer JDE",
                "field_type": "text",
                "width": "full",
                "order": 5,
                "step_number": 1,
                "required": True,
                "help_text": "Masukkan kode customer JDE (contoh: 150731) lalu klik 'Cari Customer JDE' untuk autofill.",
            },
            {
                "field_name": "nama_toko",
                "field_label": "Nama Toko / Dealer",
                "field_type": "text",
                "width": "half",
                "order": 6,
                "step_number": 1,
                "required": False,
                "readonly": True,
                "help_text": "Autofill dari JDE Customer Lookup (readonly).",
            },
            {
                "field_name": "nama_pemilik",
                "field_label": "Nama Pemilik / Penanggung Jawab",
                "field_type": "text",
                "width": "half",
                "order": 7,
                "step_number": 1,
                "required": False,
                "readonly": True,
                "help_text": "Autofill dari JDE Customer Lookup (readonly).",
            },
            {
                "field_name": "alamat_toko",
                "field_label": "Alamat Lengkap Toko",
                "field_type": "text",
                "width": "half",
                "order": 8,
                "step_number": 1,
                "required": False,
                "readonly": True,
                "help_text": "Autofill dari JDE Customer Lookup (readonly).",
            },
            {
                "field_name": "no_telepon",
                "field_label": "No. Telepon / HP",
                "field_type": "text",
                "width": "half",
                "order": 9,
                "step_number": 1,
                "required": False,
                "readonly": True,
                "help_text": "Autofill dari JDE Customer Lookup (readonly).",
            },
            {
                "field_name": "kota",
                "field_label": "Kota / Kabupaten",
                "field_type": "text",
                "width": "third",
                "order": 10,
                "step_number": 1,
                "required": False,
                "readonly": True,
                "help_text": "Autofill dari JDE Customer Lookup (readonly).",
            },
            {
                "field_name": "jenis_identitas",
                "field_label": "Jenis Identitas",
                "field_type": "select",
                "width": "third",
                "order": 11,
                "step_number": 1,
                "required": True,
                "readonly": False,
                "shared_option_list": sol_identitas,
                "help_text": "Pilih jenis identitas (KTP / NPWP).",
            },
            {
                "field_name": "nomor_identitas",
                "field_label": "Nomor Identitas (NIK / NPWP)",
                "field_type": "text",
                "width": "third",
                "order": 12,
                "step_number": 1,
                "required": True,
                "readonly": False,
                "help_text": "Nomor KTP/NIK atau NPWP pemilik toko.",
            },
            {
                "field_name": "asset_toko",
                "field_label": "Data Asset Toko",
                "field_type": "textarea",
                "width": "full",
                "order": 13,
                "step_number": 1,
                "required": False,
                "help_text": "Tabel dinamis aset display, neon box, dan papan nama toko.",
            },
            {
                "field_name": "market_share",
                "field_label": "Data Market Share",
                "field_type": "textarea",
                "width": "full",
                "order": 14,
                "step_number": 1,
                "required": False,
                "help_text": "Tabel dinamis estimasi omset penjualan produk vs kompetitor per bulan.",
            },

            # -----------------------------------------------------------------
            # Step 2: Detail Kontrak
            # -----------------------------------------------------------------
            {
                "field_name": "info_kontrak_lama",
                "field_label": "Informasi Kontrak Sebelumnya",
                "field_type": "display_text",
                "width": "full",
                "order": 15,
                "step_number": 2,
                "required": False,
                "default_value": "Status Kontrak: Sistem siap untuk data kontrak tahun sebelumnya. Pada pengajuan ini dianggap sebagai kontrak baru / perpanjangan aktif.",
            },
            {
                "field_name": "tanggal_mulai",
                "field_label": "Tanggal Mulai",
                "field_type": "date",
                "width": "fourth",
                "order": 16,
                "step_number": 2,
                "required": True,
            },
            {
                "field_name": "tanggal_berakhir",
                "field_label": "Tanggal Berakhir",
                "field_type": "date",
                "width": "fourth",
                "order": 17,
                "step_number": 2,
                "required": True,
            },
            {
                "field_name": "durasi",
                "field_label": "Durasi Kontrak",
                "field_type": "text",
                "width": "fourth",
                "order": 18,
                "step_number": 2,
                "required": False,
                "help_text": "Dihitung otomatis (misal: 1 Tahun atau 6 Bulan).",
            },
            {
                "field_name": "grace_period",
                "field_label": "Grace Period",
                "field_type": "text",
                "width": "fourth",
                "order": 19,
                "step_number": 2,
                "required": False,
                "placeholder": "Contoh: 5 Bulan",
            },
            {
                "field_name": "jenis_pajak",
                "field_label": "Jenis Pajak",
                "field_type": "select",
                "width": "third",
                "order": 20,
                "step_number": 2,
                "required": True,
                "choices": ["Exclude PPN", "Include PPN"],
            },
            {
                "field_name": "top",
                "field_label": "TOP (Term of Payment)",
                "field_type": "number",
                "width": "third",
                "order": 21,
                "step_number": 2,
                "required": True,
                "placeholder": "60",
                "help_text": "Satuan: Hari kerja",
            },
            {
                "field_name": "metode_pembayaran",
                "field_label": "Metode Pembayaran",
                "field_type": "select",
                "width": "third",
                "order": 22,
                "step_number": 2,
                "required": True,
                "choices": ["Transfer", "Cek", "Giro"],
            },
            {
                "field_name": "discount_do",
                "field_label": "Discount DO (%)",
                "field_type": "decimal",
                "width": "third",
                "order": 23,
                "step_number": 2,
                "required": False,
            },
            {
                "field_name": "ketentuan_do",
                "field_label": "Ketentuan DO",
                "field_type": "text",
                "width": "third",
                "order": 24,
                "step_number": 2,
                "required": False,
                "placeholder": "Jatuh tempo sebelum pengambilan barang",
            },
            {
                "field_name": "target_incentive",
                "field_label": "Target & Incentive Scheme (Pasal 3)",
                "field_type": "textarea",
                "width": "full",
                "order": 25,
                "step_number": 2,
                "required": False,
                "help_text": "Tabel dinamis skema target penjualan bulanan dan reward insentif.",
            },
            {
                "field_name": "discount_scheme",
                "field_label": "Discount Scheme (Pasal 6)",
                "field_type": "textarea",
                "width": "full",
                "order": 26,
                "step_number": 2,
                "required": False,
                "help_text": "Tabel dinamis komponen potongan harga.",
            },
            {
                "field_name": "is_support_provided",
                "field_label": "Terdapat Fasilitas / Bentuk Support Tambahan?",
                "field_type": "checkbox",
                "width": "full",
                "order": 27,
                "step_number": 2,
                "required": False,
                "default_value": "",
                "help_text": "Aktifkan jika kontrak memiliki fasilitas support promosi atau biaya sewa (Pasal 4 & Pasal 7). Jika tidak, kontrak berlaku reguler.",
            },
            {
                "field_name": "support_promosi",
                "field_label": "Bentuk Support Promosi",
                "field_type": "select",
                "width": "third",
                "order": 28,
                "step_number": 2,
                "required": False,
                "choices": ["Material Promosi", "Dana Promosi", "Gabungan"],
            },
            {
                "field_name": "pct_support_promo",
                "field_label": "Persentase Support Promo (%)",
                "field_type": "decimal",
                "width": "third",
                "order": 29,
                "step_number": 2,
                "required": False,
                "help_text": "Dari total omzet bulanan (Pasal 4).",
            },
            {
                "field_name": "frekuensi_pencairan",
                "field_label": "Frekuensi Pencairan",
                "field_type": "select",
                "width": "third",
                "order": 30,
                "step_number": 2,
                "required": False,
                "choices": ["Setiap Bulan", "Per Kuartal", "Per Semester"],
            },
            {
                "field_name": "syarat_pencairan",
                "field_label": "Syarat Pencairan",
                "field_type": "text",
                "width": "full",
                "order": 31,
                "step_number": 2,
                "required": False,
                "placeholder": "Setelah pembayaran lunas",
            },
            {
                "field_name": "komponen_biaya",
                "field_label": "Komponen Biaya Support",
                "field_type": "text",
                "width": "full",
                "order": 32,
                "step_number": 2,
                "required": False,
                "default_value": "",
                "placeholder": "Contoh: Sewa, Listrik, Asuransi",
                "help_text": "Pisahkan dengan koma.",
            },
            {
                "field_name": "pengecualian_ketentuan_support",
                "field_label": "Pengecualian / Ketentuan Khusus Support",
                "field_type": "textarea",
                "width": "full",
                "order": 33,
                "step_number": 2,
                "required": False,
                "placeholder": "Catatan persentase discount/pajak billboard atau batasan biaya lainnya.",
            },
            {
                "field_name": "tier_support",
                "field_label": "Tier Support Tahunan / Biaya Sewa (Pasal 7)",
                "field_type": "textarea",
                "width": "full",
                "order": 34,
                "step_number": 2,
                "required": False,
                "help_text": "Tabel dinamis target tahunan, support %, PPh %, dan Netto otomatis.",
            },
            {
                "field_name": "kota_penandatanganan",
                "field_label": "Kota Penandatanganan",
                "field_type": "text",
                "width": "third",
                "order": 35,
                "step_number": 2,
                "required": True,
                "default_value": "",
            },
            {
                "field_name": "tanggal_penandatanganan",
                "field_label": "Tanggal Penandatanganan",
                "field_type": "date",
                "width": "third",
                "order": 36,
                "step_number": 2,
                "required": True,
            },
            {
                "field_name": "rekening_perusahaan",
                "field_label": "Rekening Perusahaan",
                "field_type": "text",
                "width": "third",
                "order": 37,
                "step_number": 2,
                "required": False,
                "default_value": "BCA 084-3012899 a/n PT Bestari Mulia",
            },
            {
                "field_name": "catatan_lain",
                "field_label": "Lain-lain / Catatan Klausul Khusus",
                "field_type": "textarea",
                "width": "full",
                "order": 38,
                "step_number": 2,
                "required": False,
                "placeholder": "Catatan klausul kontrak khusus yang tidak tercakup pada poin-poin di atas.",
            },

            # -----------------------------------------------------------------
            # Step 3: Preview & Konfirmasi
            # -----------------------------------------------------------------
            {
                "field_name": "preview_contract_tab",
                "field_label": "Preview Surat Perjanjian & Ringkasan",
                "field_type": "display_text",
                "width": "full",
                "order": 39,
                "step_number": 3,
                "required": False,
                "default_value": "",
            },
            {
                "field_name": "chk_konfirmasi_data",
                "field_label": "Saya telah memeriksa seluruh data pengajuan permohonan kontrak dengan benar.",
                "field_type": "checkbox",
                "width": "full",
                "order": 40,
                "step_number": 3,
                "required": True,
            },
            {
                "field_name": "chk_konfirmasi_preview",
                "field_label": "Saya telah memeriksa draft klausul Surat Perjanjian Kerjasama (SPK).",
                "field_type": "checkbox",
                "width": "full",
                "order": 41,
                "step_number": 3,
                "required": True,
            },
        ]
        return fields
