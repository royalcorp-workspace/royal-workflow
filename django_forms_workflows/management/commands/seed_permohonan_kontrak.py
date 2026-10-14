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
            items=["Bali", "Jakarta", "Bandung", "Surabaya", "Medan", "Makassar", "Semarang", "Palembang"],
        )
        sol_brand = self._ensure_shared_option_list(
            slug="brand-list",
            name="Daftar Brand Royal",
            items=["SERENITY", "ROYAL FOAM", "GRAND EXCLUSIVE", "LADY AMERICANA"],
        )
        sol_perusahaan = self._ensure_shared_option_list(
            slug="perusahaan-list",
            name="Daftar Perusahaan (Pihak Pertama)",
            items=["PT Bestari Mulia", "PT Royal Abadi Sejahtera"],
        )
        sol_identitas = self._ensure_shared_option_list(
            slug="jenis-identitas-list",
            name="Daftar Jenis Identitas",
            items=["NIK / NPWP", "NIK (KTP)", "NPWP"],
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
                    "jenis_pajak", "top", "support_promosi",
                    "target_incentive", "pct_support_promo", "frekuensi_pencairan", "syarat_pencairan",
                    "komponen_biaya", "pengecualian_ketentuan_support", "discount_scheme",
                    "tier_support", "metode_pembayaran", "discount_do", "ketentuan_do",
                    "kota_penandatanganan", "tanggal_penandatanganan", "rekening_perusahaan", "catatan_lain"
                ],
            },
            {
                "title": "Preview & Konfirmasi",
                "fields": [
                    "preview_contract_tab",
                    "chk_lampiran_spk_lalu", "chk_asset_toko_diisi", "chk_market_share_diisi", "chk_lampiran_umum",
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
                "pdf_generation": "post_approval",
                "is_active": True,
                "is_listed": True,
            },
        )
        if form.description != clean_description:
            form.description = clean_description
            form.save(update_fields=["description"])

        # Assign form access groups
        self._set_form_groups(
            form,
            submit_groups=[groups["Sales Staff"], groups["Sales Area Manager"]],
            view_groups=[
                groups["Sales Staff"],
                groups["Sales Area Manager"],
                groups["General Manager Sales"],
                groups["Finance Team"],
                groups["Legal Team"],
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

        # Stage 1: Review SPK oleh ASM (Dinamis: supervisor_1)
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
            },
        )
        self._set_stage_groups(st1, [groups["Sales Area Manager"], groups["Branch Manager"]])

        # Stage 2: Review SPK oleh RSOM (Dinamis: supervisor_2)
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
            },
        )
        self._set_stage_groups(st2, [groups["Sales Area Manager"], groups["General Manager Sales"]])

        # Stage 3: Review SPK & Pemberian Materai oleh Sales Support
        st3 = self._ensure_stage(
            workflow,
            name="Review & Penomoran Materai (Sales Support)",
            order=3,
            defaults={
                "approval_logic": "any",
                "requires_manager_approval": False,
                "allow_edit_form_data": False,
                "allow_send_back": True,
                "allow_reassign": True,
                "approve_label": "Verifikasi & Beri Materai",
            },
        )
        self._set_stage_groups(st3, [groups["Sales Support"]])

        # Stage 4: Review & TTD oleh Toko / Verifikasi Dokumen
        st4 = self._ensure_stage(
            workflow,
            name="Verifikasi TTD Toko",
            order=4,
            defaults={
                "approval_logic": "any",
                "requires_manager_approval": False,
                "allow_edit_form_data": False,
                "allow_send_back": True,
                "allow_reassign": True,
                "approve_label": "Verifikasi TTD Toko",
            },
        )
        self._set_stage_groups(st4, [groups["Sales Support"]])

        # Stage 5: Review & TTD Final oleh Direksi
        st5 = self._ensure_stage(
            workflow,
            name="Review & TTD Final Direksi",
            order=5,
            defaults={
                "approval_logic": "any",
                "requires_manager_approval": False,
                "allow_edit_form_data": False,
                "allow_send_back": True,
                "allow_reassign": False,
                "approve_label": "Sahkan SPK (Direksi)",
            },
        )
        self._set_stage_groups(st5, [groups["Direksi"]])

        # 7. Document Template (Surat Perjanjian Kerjasama)
        self._ensure_document_template(form)

        # 8. Notification Rules
        self._ensure_notification_rules(workflow, st1, st5)

        # 9. Clean up any existing submissions with raw markdown in info_kontrak_lama & official SPK format
        for sub in FormSubmission.objects.filter(form_definition=form):
            if sub.form_data:
                updated = False
                val = str(sub.form_data.get("info_kontrak_lama", ""))
                if "[!NOTE]" in val or val.startswith(">"):
                    sub.form_data["info_kontrak_lama"] = (
                        "Status Kontrak: Sistem siap untuk data kontrak tahun sebelumnya. "
                        "Pada pengajuan ini dianggap sebagai kontrak baru / perpanjangan aktif."
                    )
                    updated = True

                spk = str(sub.form_data.get("nomor_spk", ""))
                if not spk or "OTOMATIS" in spk.upper() or spk.startswith("SPK-") or "{" in spk:
                    b = str(sub.form_data.get("brand", "LADY")).upper().replace(" ", "")
                    c = str(sub.form_data.get("cabang", "Tangerang")).title().replace(" ", "")
                    m = sub.submitted_at.month if sub.submitted_at else datetime.date.today().month
                    y = sub.submitted_at.year if sub.submitted_at else datetime.date.today().year
                    sub.form_data["nomor_spk"] = f"No. {sub.id:04d}/{b}/{c}/{m}/{y}"
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
        self.stdout.write("      - Stage 1 Approver : area.sales.manager (is_staff=True)")
        self.stdout.write("      - Stage 2 Approver : general.manager (is_staff=True)")
        self.stdout.write("      - Stage 3 Approver : approver.finance (is_staff=True)")
        self.stdout.write("      - Stage 4 Approver : legal.officer (is_staff=True)")
        self.stdout.write("  • Form Definition : 'permohonan-kontrak' (3 steps, 43 fields, 5 dynamic grids)")
        self.stdout.write("  • Mock JDE Lookup : /api/lookup/jde-customer/?code=150731")
        self.stdout.write("  • Document Template: 'Surat Perjanjian Kerjasama' (SPK)")
        self.stdout.write("  • Workflow Stages : 4 stages (ASM -> GM -> Finance -> Legal Sign-off)")

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

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
        for field_def in field_defs:
            field_copy = dict(field_def)
            field_name = field_copy.pop("field_name")
            self._ensure_field(form, field_name, field_copy)

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
        spk_html = """
<div class="spk-paper-preview" style="font-family: 'Times New Roman', serif; max-width: 820px; margin: auto; padding: 40px; color: #111; line-height: 1.6;">
    <div style="text-align: center; margin-bottom: 25px;">
        <h2 style="font-size: 20px; text-decoration: underline; margin-bottom: 4px;">SURAT PERJANJIAN KERJASAMA (SPK)</h2>
        <p style="font-size: 14px; margin: 0; font-weight: bold;">Nomor: {nomor_spk}</p>
    </div>

    <p style="text-align: justify;">
        Pada hari ini, tanggal <strong>{tanggal_penandatanganan}</strong>, bertempat di <strong>{kota_penandatanganan}</strong>, dibuat dan ditandatangani perjanjian kerjasama penjualan dan pemasaran oleh dan antara:
    </p>

    <table style="width: 100%; margin-bottom: 15px; font-size: 14px;">
        <tr>
            <td style="width: 160px; font-weight: bold; vertical-align: top;">I. PIHAK PERTAMA</td>
            <td style="width: 10px; vertical-align: top;">:</td>
            <td><strong>{perusahaan}</strong></td>
        </tr>
        <tr>
            <td style="vertical-align: top;">Alamat Domisili</td>
            <td style="vertical-align: top;">:</td>
            <td>Jl. Industri Raya Blok A No. 10, Tangerang, Banten</td>
        </tr>
        <tr>
            <td style="vertical-align: top;">Rekening Pembayaran</td>
            <td style="vertical-align: top;">:</td>
            <td>{rekening_perusahaan}</td>
        </tr>
    </table>

    <table style="width: 100%; margin-bottom: 20px; font-size: 14px;">
        <tr>
            <td style="width: 160px; font-weight: bold; vertical-align: top;">II. PIHAK KEDUA</td>
            <td style="width: 10px; vertical-align: top;">:</td>
            <td><strong>{nama_pemilik}</strong> (Pemilik / Penanggung Jawab)</td>
        </tr>
        <tr>
            <td style="vertical-align: top;">Nama Toko / Usaha</td>
            <td style="vertical-align: top;">:</td>
            <td><strong>{nama_toko}</strong> (Kode JDE: {kode_customer_jde})</td>
        </tr>
        <tr>
            <td style="vertical-align: top;">Alamat Toko</td>
            <td style="vertical-align: top;">:</td>
            <td>{alamat_toko}, {kota}</td>
        </tr>
        <tr>
            <td style="vertical-align: top;">No. Identitas ({jenis_identitas})</td>
            <td style="vertical-align: top;">:</td>
            <td>{nomor_identitas}</td>
        </tr>
        <tr>
            <td style="vertical-align: top;">No. Telepon / HP</td>
            <td style="vertical-align: top;">:</td>
            <td>{no_telepon}</td>
        </tr>
    </table>

    <h4 style="font-size: 15px; border-bottom: 1px solid #333; padding-bottom: 4px; margin-top: 25px;">BAB I - PENUNJUKAN & PERIODE KERJASAMA</h4>
    <p style="text-align: justify;">
        <strong>Pasal 1:</strong> PIHAK PERTAMA menunjuk PIHAK KEDUA sebagai dealer/mitra resmi penjualan produk dengan brand <strong>{brand}</strong> untuk wilayah <strong>{cabang}</strong>.<br>
        <strong>Pasal 2:</strong> Perjanjian kerjasama ini berlaku efektif terhitung sejak <strong>{tanggal_mulai}</strong> sampai dengan <strong>{tanggal_berakhir}</strong> (Durasi: <strong>{durasi}</strong>, Grace Period: <strong>{grace_period}</strong>).
    </p>

    <h4 style="font-size: 15px; border-bottom: 1px solid #333; padding-bottom: 4px; margin-top: 25px;">BAB II - TARGET VOLUME PENJUALAN & INSENTIF</h4>
    <p style="text-align: justify;">
        <strong>Pasal 3:</strong> PIHAK KEDUA berkomitmen mencapai target penjualan bulanan sesuai dengan rincian Skema Target & Incentive Scheme sebagai berikut:
    </p>
    {target_incentive}

    <h4 style="font-size: 15px; border-bottom: 1px solid #333; padding-bottom: 4px; margin-top: 25px;">BAB III - DUKUNGAN PROMOSI & DISCOUNT SCHEME</h4>
    <p style="text-align: justify;">
        <strong>Pasal 4:</strong> PIHAK PERTAMA memberikan dukungan promosi sebesar <strong>{pct_support_promo}%</strong> yang dicairkan <strong>{frekuensi_pencairan}</strong> dengan syarat: <em>{syarat_pencairan}</em>.<br>
        <strong>Pasal 5:</strong> Komponen biaya promosi mencakup: {komponen_biaya}. Ketentuan khusus: {pengecualian_ketentuan_support}<br>
        <strong>Pasal 6:</strong> Rincian skema diskon yang berlaku pada perjanjian ini adalah:
    </p>
    {discount_scheme}

    <h4 style="font-size: 15px; border-bottom: 1px solid #333; padding-bottom: 4px; margin-top: 25px;">BAB IV - TIER SUPPORT TAHUNAN / BIAYA SEWA</h4>
    <p style="text-align: justify;">
        <strong>Pasal 7:</strong> Skema Tier Support Tahunan dan perhitungan Netto setelah pemotongan PPh ditetapkan sebagai berikut:
    </p>
    {tier_support}

    <h4 style="font-size: 15px; border-bottom: 1px solid #333; padding-bottom: 4px; margin-top: 25px;">BAB V - TATA CARA PEMBAYARAN & KETENTUAN DO</h4>
    <p style="text-align: justify;">
        <strong>Pasal 8:</strong> Pembayaran dilakukan melalui metode <strong>{metode_pembayaran}</strong> dengan Term of Payment (TOP) selama <strong>{top} Hari</strong>.<br>
        <strong>Pasal 9:</strong> Ketentuan Delivery Order (DO) berhak memperoleh diskon tambahan sebesar <strong>{discount_do}%</strong> dengan ketentuan: <em>{ketentuan_do}</em>.<br>
        <strong>Pasal 10 (Pajak):</strong> Ketentuan pengenaan pajak yang berlaku adalah <strong>{jenis_pajak}</strong>.
    </p>

    {% if catatan_lain %}
    <h4 style="font-size: 15px; border-bottom: 1px solid #333; padding-bottom: 4px; margin-top: 25px;">BAB VI - KETENTUAN TAMBAHAN / LAIN-LAIN</h4>
    <p style="text-align: justify;">{catatan_lain}</p>
    {% endif %}

    <div style="margin-top: 50px;">
        <table style="width: 100%; text-align: center; font-size: 14px;">
            <tr>
                <td style="width: 50%;">
                    <strong>PIHAK PERTAMA</strong><br>
                    {perusahaan}<br><br><br><br><br>
                    <u>Direktur Komersial</u>
                </td>
                <td style="width: 50%;">
                    <strong>PIHAK KEDUA</strong><br>
                    {nama_toko}<br><br><br><br><br>
                    <u>{nama_pemilik}</u><br>
                    Pemilik / Penanggung Jawab
                </td>
            </tr>
        </table>
    </div>
</div>
        """
        DocumentTemplate.objects.update_or_create(
            form_definition=form,
            name="Surat Perjanjian Kerjasama",
            defaults={
                "is_default": True,
                "is_active": True,
                "html_content": spk_html.strip(),
                "page_size": "a4",
            },
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
                "required": True,
                "shared_option_list": sol_cabang,
                "help_text": "Pilih kantor cabang / area sales.",
            },
            {
                "field_name": "brand",
                "field_label": "Brand Produk",
                "field_type": "select",
                "width": "half",
                "order": 3,
                "step_number": 1,
                "required": True,
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
                "required": True,
                "shared_option_list": sol_perusahaan,
                "help_text": "Badan hukum Pihak Pertama penandatangan kontrak.",
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
                "field_name": "support_promosi",
                "field_label": "Bentuk Support Promosi",
                "field_type": "select",
                "width": "third",
                "order": 22,
                "step_number": 2,
                "required": False,
                "choices": ["Material Promosi", "Dana Promosi", "Gabungan"],
            },
            {
                "field_name": "target_incentive",
                "field_label": "Target & Incentive Scheme (Pasal 3)",
                "field_type": "textarea",
                "width": "full",
                "order": 23,
                "step_number": 2,
                "required": False,
                "help_text": "Tabel dinamis skema target penjualan bulanan dan reward insentif.",
            },
            {
                "field_name": "pct_support_promo",
                "field_label": "Persentase Support Promo (%)",
                "field_type": "decimal",
                "width": "third",
                "order": 24,
                "step_number": 2,
                "required": False,
                "help_text": "Dari total omzet bulanan (Pasal 4).",
            },
            {
                "field_name": "frekuensi_pencairan",
                "field_label": "Frekuensi Pencairan",
                "field_type": "select",
                "width": "third",
                "order": 25,
                "step_number": 2,
                "required": False,
                "choices": ["Setiap Bulan", "Per Kuartal", "Per Semester"],
            },
            {
                "field_name": "syarat_pencairan",
                "field_label": "Syarat Pencairan",
                "field_type": "text",
                "width": "third",
                "order": 26,
                "step_number": 2,
                "required": False,
                "placeholder": "Setelah pembayaran lunas",
            },
            {
                "field_name": "komponen_biaya",
                "field_label": "Komponen Biaya Support",
                "field_type": "text",
                "width": "full",
                "order": 27,
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
                "order": 28,
                "step_number": 2,
                "required": False,
                "placeholder": "Catatan persentase discount/pajak billboard atau batasan biaya lainnya.",
            },
            {
                "field_name": "discount_scheme",
                "field_label": "Discount Scheme (Pasal 6)",
                "field_type": "textarea",
                "width": "full",
                "order": 29,
                "step_number": 2,
                "required": False,
                "help_text": "Tabel dinamis komponen potongan harga.",
            },
            {
                "field_name": "tier_support",
                "field_label": "Tier Support Tahunan / Biaya Sewa (Pasal 7)",
                "field_type": "textarea",
                "width": "full",
                "order": 30,
                "step_number": 2,
                "required": False,
                "help_text": "Tabel dinamis target tahunan, support %, PPh %, dan Netto otomatis.",
            },
            {
                "field_name": "metode_pembayaran",
                "field_label": "Metode Pembayaran",
                "field_type": "select",
                "width": "third",
                "order": 31,
                "step_number": 2,
                "required": True,
                "choices": ["Transfer / Cek / Giro", "Transfer Bank", "Cek / Bilyet Giro"],
            },
            {
                "field_name": "discount_do",
                "field_label": "Discount DO (%)",
                "field_type": "decimal",
                "width": "third",
                "order": 32,
                "step_number": 2,
                "required": False,
            },
            {
                "field_name": "ketentuan_do",
                "field_label": "Ketentuan DO",
                "field_type": "text",
                "width": "third",
                "order": 33,
                "step_number": 2,
                "required": False,
                "placeholder": "Jatuh tempo sebelum pengambilan barang",
            },
            {
                "field_name": "kota_penandatanganan",
                "field_label": "Kota Penandatanganan",
                "field_type": "text",
                "width": "third",
                "order": 34,
                "step_number": 2,
                "required": True,
                "default_value": "Tangerang",
            },
            {
                "field_name": "tanggal_penandatanganan",
                "field_label": "Tanggal Penandatanganan",
                "field_type": "date",
                "width": "third",
                "order": 35,
                "step_number": 2,
                "required": True,
            },
            {
                "field_name": "rekening_perusahaan",
                "field_label": "Rekening Perusahaan",
                "field_type": "text",
                "width": "third",
                "order": 36,
                "step_number": 2,
                "required": False,
                "default_value": "BCA 084-3012899 a/n PT Bestari Mulia",
            },
            {
                "field_name": "catatan_lain",
                "field_label": "Lain-lain / Catatan Klausul Khusus",
                "field_type": "textarea",
                "width": "full",
                "order": 37,
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
                "order": 38,
                "step_number": 3,
                "required": False,
                "default_value": "",
            },
            {
                "field_name": "chk_lampiran_spk_lalu",
                "field_label": "Lampiran SPK Tahun Lalu tersedia",
                "field_type": "checkbox",
                "width": "half",
                "order": 39,
                "step_number": 3,
                "required": False,
            },
            {
                "field_name": "chk_asset_toko_diisi",
                "field_label": "Asset Toko telah diisi lengkap",
                "field_type": "checkbox",
                "width": "half",
                "order": 40,
                "step_number": 3,
                "required": False,
            },
            {
                "field_name": "chk_market_share_diisi",
                "field_label": "Market Share telah diisi lengkap",
                "field_type": "checkbox",
                "width": "half",
                "order": 41,
                "step_number": 3,
                "required": False,
            },
            {
                "field_name": "chk_lampiran_umum",
                "field_label": "Lampiran Umum tersedia",
                "field_type": "checkbox",
                "width": "half",
                "order": 42,
                "step_number": 3,
                "required": False,
            },
            {
                "field_name": "chk_konfirmasi_data",
                "field_label": "Saya telah memeriksa seluruh data pengajuan permohonan kontrak dengan benar.",
                "field_type": "checkbox",
                "width": "full",
                "order": 43,
                "step_number": 3,
                "required": True,
            },
            {
                "field_name": "chk_konfirmasi_preview",
                "field_label": "Saya telah memeriksa draft klausul Surat Perjanjian Kerjasama (SPK).",
                "field_type": "checkbox",
                "width": "full",
                "order": 44,
                "step_number": 3,
                "required": True,
            },
        ]
        return fields
