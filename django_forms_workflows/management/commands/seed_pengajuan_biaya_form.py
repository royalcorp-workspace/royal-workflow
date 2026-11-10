"""
Management command: seed_pengajuan_biaya_form

Registers the official Form Definition and Multi-Stage Workflow for:
- Form: 'Pengajuan Biaya & Anggaran Operasional'
- Slug: 'pengajuan-biaya'
- Category: 'Keuangan & Anggaran Operasional'

Alur Kerja Multi-Stage Approval Operasional Cabang:
1. Pemohon (Kasir Cabang): Mengajukan Form Biaya & Lampiran Bukti
2. Review Atasan Cabang: Menyetujui urgensi operasional cabang
3. Verifikasi PIC Pusat: Memverifikasi kesesuaian anggaran & teknis
4. Persetujuan Head of Division: Memberikan otorisasi approval anggaran
5. Pencairan Dana (Finance): Menyalurkan dana via transfer/kasbon
6. Pelaporan Realisasi Biaya: Kasir mengunggah bukti nota belanja riil
7. Verifikasi Closing (Finance): Validasi nota dan penyelesaian status akhir

Usage:
    python manage.py seed_pengajuan_biaya_form
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django_forms_workflows.models import (
    EmployeeProfile,
    FormCategory,
    FormDefinition,
    FormField,
    FormSubmission,
    NotificationRule,
    PrefillSource,
    SharedOptionList,
    StageApprovalGroup,
    WorkflowDefinition,
    WorkflowStage,
)

User = get_user_model()


class Command(BaseCommand):
    help = "Seed the 'Pengajuan Biaya & Anggaran Operasional' form & 6-stage workflow definition."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("=================================================================")
        self.stdout.write("Seeding Form: 'Pengajuan Biaya & Anggaran Operasional'")
        self.stdout.write("=================================================================")

        # 1. Pastikan Approval Groups (Kasir, Atasan Cabang, PIC, Atasan PIC, Finance)
        group_maker, _ = Group.objects.get_or_create(name="Kasir Cabang (Pemohon)")
        group_atasan_cabang, _ = Group.objects.get_or_create(name="Atasan Cabang (Manager Cabang)")
        group_pic_pusat, _ = Group.objects.get_or_create(name="PIC Pusat (Operasional & Umum)")
        group_atasan_pic, _ = Group.objects.get_or_create(name="Atasan PIC Pusat (Head of Division)")
        group_finance_transfer, _ = Group.objects.get_or_create(name="Finance (Transfer & Pencairan)")
        group_finance_closing, _ = Group.objects.get_or_create(name="Finance (Verifikasi Realisasi Closing)")

        # Assign user admin ke seluruh grup agar siap digunakan untuk peninjauan di inbox
        admin_user = User.objects.filter(username="admin").first()
        if admin_user:
            admin_user.groups.add(
                group_maker,
                group_atasan_cabang,
                group_pic_pusat,
                group_atasan_pic,
                group_finance_transfer,
                group_finance_closing,
            )

        # 1.b Akun Pengujian Per-Peran & Hierarki HRMS (Dedicated Role-Based Testing Accounts)
        default_pwd = "Bandung*123#"
        test_users_config = [
            ("kasir.cabang", "Kasir", "Cabang", "kasir.cabang@royalcorp.co.id", [group_maker], "ROYAL-KSR-001", "Kasir Cabang", "Operasional Cabang", "Cabang Bandung"),
            ("atasan.cabang", "Atasan", "Cabang", "atasan.cabang@royalcorp.co.id", [group_atasan_cabang], "ROYAL-MGR-001", "Atasan Cabang", "Operasional Cabang", "Cabang Bandung"),
            ("staff.operasional", "Staff", "Operasional Pusat", "staff.operasional@royalcorp.co.id", [group_pic_pusat], "ROYAL-STF-001", "Staff Operasional Pusat", "Divisi Operasional & Logistik", "Kantor Pusat Bandung"),
            ("pic.pusat", "PIC", "Pusat", "pic.pusat@royalcorp.co.id", [group_pic_pusat], "ROYAL-PIC-001", "PIC Pusat", "Divisi Operasional & Logistik", "Kantor Pusat Bandung"),
            ("head.division", "Atasan", "PIC Pusat", "head.division@royalcorp.co.id", [group_atasan_pic], "ROYAL-GM-001", "Atasan PIC Pusat", "Divisi Operasional & Logistik", "Kantor Pusat Bandung"),
            ("finance.ops", "Finance", "Pusat", "finance.ops@royalcorp.co.id", [group_finance_transfer, group_finance_closing], "ROYAL-FIN-001", "Finance Pusat", "Finance & Accounting", "Kantor Pusat Bandung"),
        ]

        created_user_objs = {}
        for uname, fname, lname, email, grps, nik, pos, dept, branch in test_users_config:
            u, _ = User.objects.get_or_create(
                username=uname,
                defaults={
                    "first_name": fname,
                    "last_name": lname,
                    "email": email,
                    "is_active": True,
                    "is_staff": True,
                },
            )
            u.set_password(default_pwd)
            u.first_name = fname
            u.last_name = lname
            u.email = email
            u.is_active = True
            u.is_staff = True
            u.save()
            u.groups.set(grps)
            created_user_objs[uname] = u

            EmployeeProfile.objects.update_or_create(
                user=u,
                defaults={
                    "nik": nik,
                    "full_name": f"{fname} {lname}".strip(),
                    "position": pos,
                    "department": dept,
                    "company": "PT Royal Abadi Sejahtera",
                    "branch": branch,
                    "work_email": email,
                },
            )

        # Wire up HRMS supervisor relationships (GM -> PIC -> Staff, GM -> BOM -> Kasir)
        u_gm = created_user_objs.get("head.division")
        u_pic = created_user_objs.get("pic.pusat")
        u_staff = created_user_objs.get("staff.operasional")
        u_mgr = created_user_objs.get("atasan.cabang")
        u_kasir = created_user_objs.get("kasir.cabang")

        if u_staff and u_pic and u_gm:
            EmployeeProfile.objects.filter(user=u_staff).update(supervisor_1=u_pic, supervisor_2=u_gm)
        if u_pic and u_gm:
            EmployeeProfile.objects.filter(user=u_pic).update(supervisor_1=u_gm)
        if u_kasir and u_mgr:
            EmployeeProfile.objects.filter(user=u_kasir).update(
                supervisor_1=u_mgr,
                supervisor_1_name="Atasan Cabang",
                supervisor_1_position="Atasan Cabang",
            )
        if u_mgr and u_gm:
            EmployeeProfile.objects.filter(user=u_mgr).update(
                supervisor_1=u_gm,
                supervisor_1_name="Atasan PIC Pusat",
                supervisor_1_position="Head of Division",
            )

        self.stdout.write("Created/updated 6 dedicated testing users & HRMS EmployeeProfiles (password: Bandung*123#).")

        # 2. Form Category
        category, _ = FormCategory.objects.get_or_create(
            slug="keuangan-operasional",
            defaults={
                "name": "Keuangan & Anggaran Operasional",
                "description": "Layanan permohonan pengajuan biaya, anggaran cabang, dan pencairan kas korporat.",
                "icon": "bi-cash-coin",
                "order": 15,
            },
        )
        self.stdout.write(f"Category: {category.name}")

        # 3. Form Definition
        form_slug = "pengajuan-biaya"
        form, created = FormDefinition.objects.get_or_create(
            slug=form_slug,
            defaults={
                "name": "Pengajuan Biaya & Anggaran Operasional",
                "category": category,
                "description": "Formulir permohonan pengajuan biaya operasional cabang dan alur persetujuan bertingkat.",
                "instructions": (
                    "Isi formulir pengajuan biaya operasional cabang/unit kerja dengan lengkap beserta "
                    "rincian item kebutuhan dan lampiran dokumen pendukung."
                ),
                "is_active": True,
                "is_listed": True,
                "allow_save_draft": True,
                "allow_resubmit": True,
            },
        )

        if not created:
            form.name = "Pengajuan Biaya & Anggaran Operasional"
            form.description = "Formulir permohonan pengajuan biaya operasional cabang dan alur persetujuan bertingkat."
            form.instructions = (
                "Isi formulir pengajuan biaya operasional cabang/unit kerja dengan lengkap beserta "
                "rincian item kebutuhan dan lampiran dokumen pendukung."
            )
            form.category = category
            form.is_active = True
            form.is_listed = True
            form.save()
            form.fields.all().delete()
            self.stdout.write("Updated existing FormDefinition and refreshed fields.")
        else:
            self.stdout.write("Created new FormDefinition.")

        # 4. Master Data Terpusat & Prefill Dinamis (HRMS / EmployeeProfile)
        prefill_date, _ = PrefillSource.objects.update_or_create(
            source_key="current_date",
            defaults={
                "name": "Current Date (YYYY-MM-DD)",
                "source_type": "system",
                "description": "Tanggal hari ini otomatis dari sistem",
                "order": 200,
                "is_active": True,
            },
        )
        prefill_branch, _ = PrefillSource.objects.update_or_create(
            source_key="user.branch",
            defaults={
                "name": "Current User - Branch / Cabang",
                "source_type": "user",
                "description": "Branch / Cabang pemohon otomatis dari EmployeeProfile",
                "order": 60,
                "is_active": True,
            },
        )
        prefill_dept_pembuat, _ = PrefillSource.objects.update_or_create(
            source_key="user.department_pembuat",
            defaults={
                "name": "Current User - Department Pembuat",
                "source_type": "user",
                "description": "Department pembuat dari profil karyawan pemohon",
                "order": 97,
                "is_active": True,
            },
        )
        prefill_bagian_pembuat, _ = PrefillSource.objects.update_or_create(
            source_key="user.bagian_pembuat",
            defaults={
                "name": "Current User - Bagian Pembuat",
                "source_type": "user",
                "description": "Bagian / Posisi pembuat dari profil karyawan pemohon",
                "order": 98,
                "is_active": True,
            },
        )
        prefill_nama_atasan, _ = PrefillSource.objects.update_or_create(
            source_key="user.supervisor_name",
            defaults={
                "name": "Current User - Supervisor / Atasan",
                "source_type": "user",
                "description": "Supervisor / Atasan langsung pemohon",
                "order": 96,
                "is_active": True,
            },
        )
        prefill_nama_kasir, _ = PrefillSource.objects.update_or_create(
            source_key="user.nama_kasir",
            defaults={
                "name": "Current User - Nama Kasir",
                "source_type": "user",
                "description": "Nama Kasir / Pemohon yang sedang membuat pengajuan",
                "order": 99,
                "is_active": True,
            },
        )

        shared_branch_list, _ = SharedOptionList.objects.update_or_create(
            slug="daftar-cabang-perusahaan",
            defaults={
                "name": "Daftar Cabang Perusahaan",
                "items": [
                    {"value": "Cabang Jakarta Pusat", "label": "Cabang Jakarta Pusat"},
                    {"value": "Cabang Bandung", "label": "Cabang Bandung"},
                    {"value": "Cabang Surabaya", "label": "Cabang Surabaya"},
                    {"value": "Cabang Denpasar", "label": "Cabang Denpasar"},
                    {"value": "Cabang Medan", "label": "Cabang Medan"},
                    {"value": "Kantor Pusat / Holding", "label": "Kantor Pusat / Holding"},
                ],
                "is_active": True,
            },
        )

        # 4. Form Fields Specification (Harmonized with Wireframe refferense-wf.jpeg & PRD v1.2)
        field_specs = [
            # ── KOLOM A: IDENTITAS PENGAJUAN & INFORMASI PEMBUAT (100% Prefilled & Locked) ──
            {
                "field_name": "tanggal_pengajuan",
                "field_label": "Tanggal Pengajuan",
                "field_type": "date",
                "required": False,
                "readonly": True,
                "order": 1,
                "width": "half",
                "prefill_source_config": prefill_date,
                "help_text": "Otomatis terisi tanggal hari ini.",
            },
            {
                "field_name": "nomor_pengajuan",
                "field_label": "Nomor Pengajuan",
                "field_type": "text",
                "required": False,
                "readonly": True,
                "order": 2,
                "width": "half",
                "default_value": "Auto Number",
                "help_text": "Nomor registrasi pengajuan otomatis dari sistem workflow.",
            },
            {
                "field_name": "cabang",
                "field_label": "Cabang / Unit Kerja",
                "field_type": "select",
                "required": False,
                "readonly": True,
                "order": 3,
                "width": "full",
                "shared_option_list": shared_branch_list,
                "prefill_source_config": prefill_branch,
                "choices": [
                    {"value": "Cabang Jakarta Pusat", "label": "Cabang Jakarta Pusat"},
                    {"value": "Cabang Bandung", "label": "Cabang Bandung"},
                    {"value": "Cabang Surabaya", "label": "Cabang Surabaya"},
                    {"value": "Cabang Denpasar", "label": "Cabang Denpasar"},
                    {"value": "Cabang Medan", "label": "Cabang Medan"},
                    {"value": "Kantor Pusat / Holding", "label": "Kantor Pusat / Holding"},
                ],
                "help_text": "Terkunci otomatis sesuai cabang profil karyawan.",
            },
            {
                "field_name": "department_pembuat",
                "field_label": "Department Pembuat",
                "field_type": "text",
                "required": False,
                "readonly": True,
                "order": 4,
                "width": "half",
                "prefill_source_config": prefill_dept_pembuat,
                "default_value": "Operasional Cabang",
                "help_text": "Otomatis terisi dari profil user pembuat.",
            },
            {
                "field_name": "bagian_pembuat",
                "field_label": "Bagian Pembuat",
                "field_type": "text",
                "required": False,
                "readonly": True,
                "order": 5,
                "width": "half",
                "prefill_source_config": prefill_bagian_pembuat,
                "default_value": "Kasir Cabang",
                "help_text": "Otomatis terisi dari profil user pembuat.",
            },
            {
                "field_name": "nama_atasan",
                "field_label": "Nama Atasan Langsung",
                "field_type": "text",
                "required": False,
                "readonly": True,
                "order": 6,
                "width": "half",
                "prefill_source_config": prefill_nama_atasan,
                "default_value": "Atasan Cabang",
                "help_text": "Atasan penanggung jawab pemohon (Reviewer Tahap 1).",
            },
            {
                "field_name": "inisiator_nama",
                "field_label": "Nama Kasir / Pemohon",
                "field_type": "text",
                "required": False,
                "readonly": True,
                "order": 7,
                "width": "half",
                "prefill_source_config": prefill_nama_kasir,
                "default_value": "Kasir Cabang",
                "help_text": "User aktif yang membuat pengajuan biaya operasional.",
            },

            # ── KOLOM A: TUJUAN PENGAJUAN (Divisi Penerima & Klasifikasi Biaya PRD v1.2) ──
            {
                "field_name": "nama_kegiatan",
                "field_label": "Nama / Judul Pengajuan Biaya",
                "field_type": "text",
                "required": True,
                "order": 8,
                "width": "full",
                "placeholder": "",
                "help_text": "Ringkasan judul kebutuhan pengajuan biaya operasional cabang.",
            },
            {
                "field_name": "department_penerima",
                "field_label": "Department Penerima",
                "field_type": "select",
                "required": True,
                "order": 9,
                "width": "half",
                "choices": [
                    {"value": "Divisi Umum & PGA", "label": "Divisi Umum & PGA"},
                    {"value": "Divisi IT & Komunikasi", "label": "Divisi IT & Komunikasi"},
                    {"value": "Divisi Operasional & Logistik", "label": "Divisi Operasional & Logistik"},
                    {"value": "Divisi Sales & Marketing", "label": "Divisi Sales & Marketing"},
                    {"value": "Divisi Finance & Accounting", "label": "Divisi Finance & Accounting"},
                    {"value": "Divisi Human Capital (HRD)", "label": "Divisi Human Capital (HRD)"},
                ],
                "default_value": "Divisi Umum & PGA",
            },
            {
                "field_name": "bagian_penerima",
                "field_label": "Bagian Penerima",
                "field_type": "text",
                "required": False,
                "order": 10,
                "width": "half",
                "default_value": "PGA / Operasional Pusat",
                "placeholder": "",
            },
            {
                "field_name": "nama_pic",
                "field_label": "Nama PIC Penerima",
                "field_type": "text",
                "required": False,
                "order": 11,
                "width": "half",
                "default_value": "PIC Pusat",
                "placeholder": "",
            },
            {
                "field_name": "tembusan",
                "field_label": "Tembusan",
                "field_type": "text",
                "required": False,
                "order": 12,
                "width": "half",
                "default_value": "Atasan PIC Pusat",
                "placeholder": "",
                "help_text": "Minimal nama atasan PIC kantor pusat.",
            },
            {
                "field_name": "nomor_petty_cash",
                "field_label": "No. Dokumen Petty Cash / Kasbon Cabang",
                "field_type": "text",
                "required": True,
                "order": 13,
                "width": "full",
                "placeholder": "",
                "help_text": "Nomor voucher petty cash fisik cabang (Wajib diisi sesuai PRD FR-04).",
            },
            {
                "field_name": "kategori_biaya",
                "field_label": "Kategori Pengeluaran Biaya",
                "field_type": "select",
                "required": True,
                "order": 14,
                "width": "half",
                "choices": [
                    {"value": "ATK & Perlengkapan Kantor", "label": "ATK & Perlengkapan Kantor"},
                    {"value": "Service Umum & Pemeliharaan Gedung/Aset", "label": "Service Umum & Pemeliharaan Gedung/Aset"},
                    {"value": "Operasional Kendaraan & Transportasi", "label": "Operasional Kendaraan & Transportasi"},
                    {"value": "IT, Komunikasi & Peralatan Kantor", "label": "IT, Komunikasi & Peralatan Kantor"},
                    {"value": "Sales, Pemasaran & Operasional Cabang", "label": "Sales, Pemasaran & Operasional Cabang"},
                ],
                "default_value": "ATK & Perlengkapan Kantor",
                "help_text": "5 Kategori Pengeluaran Biaya MVP sesuai PRD v1.2 FR-01.",
            },
            {
                "field_name": "tipe_transaksi",
                "field_label": "Tipe Transaksi",
                "field_type": "select",
                "required": True,
                "order": 15,
                "width": "half",
                "choices": [
                    {"value": "Pengajuan", "label": "Pengajuan (Kasbon di muka sebelum belanja)"},
                    {"value": "Reimburse", "label": "Reimburse (Klaim penggantian dana yang sudah keluar)"},
                ],
                "default_value": "Pengajuan",
                "help_text": "Reimburse mewajibkan unggah bukti nota belanja riil saat submit (FR-05).",
            },
            {
                "field_name": "urgensi_pengajuan",
                "field_label": "Tingkat Urgensi",
                "field_type": "select",
                "required": True,
                "order": 16,
                "width": "full",
                "choices": [
                    {"value": "Normal (Sesuai SLA Standar)", "label": "Normal (Sesuai SLA Standar)"},
                    {"value": "Prioritas Tinggi", "label": "Prioritas Tinggi"},
                    {"value": "Mendesak / Urgent", "label": "Mendesak / Urgent"},
                ],
                "default_value": "Normal (Sesuai SLA Standar)",
            },

            # ── KOLOM A: LAMPIRAN BERKAS ──
            {
                "field_name": "dokumen_pendukung",
                "field_label": "Lampiran Pengajuan / Bukti Nota / Penawaran",
                "field_type": "file",
                "required": False,
                "order": 17,
                "width": "full",
                "help_text": "Unggah nota, kuitansi, proforma invoice, atau foto kebutuhan (Wajib untuk Reimburse).",
            },
            {
                "field_name": "lampiran_realisasi",
                "field_label": "Lampiran Realisasi / Bukti Beresan (Closing)",
                "field_type": "file",
                "required": False,
                "readonly": True,
                "order": 18,
                "width": "full",
                "help_text": "Diupload saat tahap Pelaporan Realisasi Biaya oleh Kasir (Tahap 6 Closing).",
            },

            # ── KOLOM B: DETAIL ITEM DAN LIMIT BUDGET GUARDRAIL ──
            {
                "field_name": "sisa_limit_pengajuan_lalu",
                "field_label": "Sisa Limit Pengajuan Lalu (Rp)",
                "field_type": "number",
                "required": False,
                "readonly": True,
                "order": 19,
                "width": "third",
                "default_value": "1000000",
                "help_text": "Sisa saldo limit operasional periode sebelumnya.",
            },
            {
                "field_name": "total_nominal",
                "field_label": "Total Nominal Biaya (Rp)",
                "field_type": "number",
                "required": True,
                "order": 20,
                "width": "third",
                "placeholder": "",
                "help_text": "Total akumulasi nominal pengajuan dihitung otomatis dari rincian item.",
            },
            {
                "field_name": "sisa_limit_saat_ini",
                "field_label": "Sisa Limit Saat Ini (Rp)",
                "field_type": "number",
                "required": False,
                "readonly": True,
                "order": 21,
                "width": "third",
                "default_value": "1000000",
                "help_text": "Sisa limit setelah dikurangi total pengajuan ini.",
            },
            {
                "field_name": "items_data",
                "field_label": "Data Rincian Multi-Item (JSON)",
                "field_type": "textarea",
                "required": False,
                "order": 22,
                "width": "full",
                "default_value": "[]",
                "help_text": "Data terstruktur multi-item barang/jasa disinkronkan otomatis.",
            },
            {
                "field_name": "rincian_item",
                "field_label": "Daftar Rincian Item Barang / Jasa",
                "field_type": "textarea",
                "required": True,
                "order": 23,
                "width": "full",
                "placeholder": "",
                "help_text": "Ringkasan teks rincian item kebutuhan operasional.",
            },

            # ── KOLOM B: PENCAIRAN DANA & JUSTIFIKASI ──
            {
                "field_name": "metode_pencairan",
                "field_label": "Metode Pencairan Dana",
                "field_type": "select",
                "required": True,
                "order": 24,
                "width": "half",
                "choices": [
                    {"value": "Kas Kecil / Kasbon (Petty Cash)", "label": "Kas Kecil / Kasbon Tunai (Petty Cash)"},
                    {"value": "Transfer Rekening Bank", "label": "Transfer Rekening Bank (Cabang / Vendor)"},
                    {"value": "Klaim Reimbursement Karyawan", "label": "Klaim Reimbursement Karyawan"},
                ],
                "default_value": "Kas Kecil / Kasbon (Petty Cash)",
            },
            {
                "field_name": "nama_bank",
                "field_label": "Nama Bank Tujuan",
                "field_type": "text",
                "required": False,
                "order": 25,
                "width": "half",
                "placeholder": "",
                "help_text": "Isi jika memilih metode transfer rekening bank.",
            },
            {
                "field_name": "nomor_rekening",
                "field_label": "Nomor Rekening Tujuan",
                "field_type": "text",
                "required": False,
                "order": 26,
                "width": "half",
                "placeholder": "",
            },
            {
                "field_name": "atas_nama_rekening",
                "field_label": "Atas Nama Rekening",
                "field_type": "text",
                "required": False,
                "order": 27,
                "width": "half",
                "placeholder": "",
            },
            {
                "field_name": "catatan_justifikasi",
                "field_label": "Catatan Justifikasi & Rencana Penggunaan",
                "field_type": "textarea",
                "required": False,
                "order": 28,
                "width": "full",
                "placeholder": "",
                "help_text": "Uraian justifikasi kebutuhan operasional dan urgensi pemakaian dana.",
            },
        ]

        for spec in field_specs:
            FormField.objects.create(
                form_definition=form,
                field_name=spec["field_name"],
                field_label=spec["field_label"],
                field_type=spec["field_type"],
                order=spec["order"],
                width=spec.get("width", "full"),
                required=spec.get("required", False),
                readonly=spec.get("readonly", False),
                choices=spec.get("choices", None),
                shared_option_list=spec.get("shared_option_list", None),
                prefill_source_config=spec.get("prefill_source_config", None),
                default_value=spec.get("default_value", ""),
                placeholder=spec.get("placeholder", ""),
                help_text=spec.get("help_text", ""),
            )
        self.stdout.write(f"Created {len(field_specs)} form fields.")

        # 5. Workflow Definition & Multi-Stage Approval Flow
        workflow, _ = WorkflowDefinition.objects.get_or_create(
            form_definition=form,
            defaults={
                "name_label": "Alur Persetujuan Pengajuan Biaya & Anggaran Operasional",
                "requires_approval": True,
                "approval_deadline_days": 3,
                "send_reminder_after_days": 1,
            },
        )
        workflow.name_label = "Alur Persetujuan Pengajuan Biaya & Anggaran Operasional"
        workflow.requires_approval = True
        workflow.approval_deadline_days = 3
        workflow.send_reminder_after_days = 1
        workflow.save()

        # Definisikan 6 Tahap Alur Persetujuan Operasional
        stages_config = [
            (1, "Review Atasan Cabang", group_atasan_cabang),
            (2, "Verifikasi PIC Pusat", group_pic_pusat),
            (3, "Persetujuan Head of Division (Atasan PIC)", group_atasan_pic),
            (4, "Pencairan Dana (Finance)", group_finance_transfer),
            (5, "Pelaporan Realisasi Biaya (Kasir Cabang)", group_maker),
            (6, "Verifikasi Closing (Finance)", group_finance_closing),
        ]

        created_stages = []
        for order, stage_name, group_obj in stages_config:
            stage, _ = WorkflowStage.objects.get_or_create(
                workflow=workflow,
                order=order,
                defaults={
                    "name": stage_name,
                    "approval_logic": "any",
                },
            )
            stage.name = stage_name
            stage.approval_logic = "any"
            stage.allow_send_back = True
            stage.allow_reassign = True
            stage.save()
            StageApprovalGroup.objects.update_or_create(
                stage=stage,
                group=group_obj,
                role="approval",
                defaults={"position": 1},
            )
            created_stages.append(stage)

        self.stdout.write("Configured 6-Stage Approval Workflow (Atasan Cabang -> PIC Pusat -> Atasan PIC -> Finance Transfer -> Realisasi Kasir -> Finance Closing).")

        # 6. Notification Rules
        html_email_style = """
        <style>
          body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 24px 12px; color: #0f172a; }
          .email-card { max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06); }
          .email-header { background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%); color: #ffffff; padding: 24px 28px; }
          .email-brand { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: #93c5fd; margin-bottom: 6px; }
          .email-title { font-size: 19px; font-weight: 700; margin: 0; line-height: 1.35; color: #ffffff; }
          .email-body { padding: 28px; }
          .badge-pill { display: inline-block; padding: 4px 10px; font-size: 11.5px; font-weight: 600; border-radius: 9999px; }
          .badge-pending { background-color: #fef3c7; color: #92400e; border: 1px solid #fde68a; }
          .badge-approved { background-color: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }
          .info-table { width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 13px; }
          .info-table td { padding: 9px 8px; border-bottom: 1px solid #f1f5f9; vertical-align: top; }
          .info-label { color: #64748b; font-weight: 600; width: 170px; }
          .info-value { color: #0f172a; font-weight: 500; }
          .code-pill { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; background: #f8fafc; border: 1px solid #cbd5e1; padding: 2px 7px; border-radius: 4px; font-size: 12px; color: #0f172a; }
          .btn-cta { display: inline-block; background-color: #1e3a8a; color: #ffffff !important; padding: 12px 28px; font-size: 13.5px; font-weight: 600; border-radius: 6px; text-decoration: none; margin: 18px 0; text-align: center; }
          .email-footer { background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 16px 24px; font-size: 12px; color: #64748b; text-align: center; }
        </style>
        """

        approval_request_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  {html_email_style}
</head>
<body>
  <div class="email-card">
    <div class="email-header">
      <div class="email-brand">&#128176; ROYAL WORKFLOW &bull; ALUR PERSETUJUAN BIAYA</div>
      <h1 class="email-title">Tindakan Diperlukan: {{{{ stage.name|default:"Persetujuan Pengajuan Biaya" }}}}</h1>
    </div>
    <div class="email-body">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 16px;">
        <span class="badge-pill badge-pending">&bull; Menunggu Tindakan Anda</span>
        <span style="font-size: 12px; color: #64748b; font-family: monospace;">Ref: #{{{{ submission.id }}}}</span>
      </div>
      <p style="font-size: 14px; color: #334155; line-height: 1.6; margin-top: 0;">
        Halo <strong>{{{{ approver.get_full_name|default:approver.username|default:"Tim Reviewer" }}}}</strong>,
      </p>
      <p style="font-size: 13.5px; color: #475569; line-height: 1.6;">
        Terdapat permohonan pengajuan biaya operasional pada tahap <strong>{{{{ stage.name }}}}</strong> yang memerlukan evaluasi Anda:
      </p>

      <table class="info-table">
        <tr>
          <td class="info-label">Nama Kegiatan</td>
          <td class="info-value"><strong>{{{{ form_data.nama_kegiatan|default:"Pengajuan Biaya Operasional" }}}}</strong></td>
        </tr>
        <tr>
          <td class="info-label">Total Nominal</td>
          <td class="info-value" style="color: #1e3a8a; font-size: 15px; font-weight: 700;">Rp {{{{ form_data.total_nominal|default:"0" }}}}</td>
        </tr>
        <tr>
          <td class="info-label">Kategori Biaya</td>
          <td class="info-value">{{{{ form_data.kategori_biaya|default:"Operasional Cabang" }}}}</td>
        </tr>
        <tr>
          <td class="info-label">Cabang / Tipe</td>
          <td class="info-value">{{{{ form_data.cabang|default:"Cabang Bandung" }}}} ({{{{ form_data.tipe_transaksi|default:"Pengajuan" }}}})</td>
        </tr>
        <tr>
          <td class="info-label">Metode Pencairan</td>
          <td class="info-value">{{{{ form_data.metode_pencairan|default:"Transfer Rekening Bank" }}}}</td>
        </tr>
        <tr>
          <td class="info-label">Tanggal Kebutuhan</td>
          <td class="info-value">{{{{ form_data.tanggal_kebutuhan|default:"-" }}}}</td>
        </tr>
      </table>

      <div style="background-color: #f8fafc; border-left: 3px solid #1e3a8a; padding: 12px 14px; border-radius: 4px; font-size: 12.5px; color: #475569; margin: 16px 0;">
        <strong>Rincian Kebutuhan:</strong><br>
        <span style="white-space: pre-wrap;">{{{{ form_data.rincian_item|default:"-" }}}}</span>
      </div>

      <div style="text-align: center; margin: 24px 0 16px;">
        <a href="{{{{ approval_url }}}}" class="btn-cta">&#10148; Review &amp; Otorisasi di Sistem Web</a>
      </div>
      <p style="font-size: 12px; color: #94a3b8; text-align: center; margin: 0;">
        Tautan langsung: <a href="{{{{ approval_url }}}}" style="color: #1e3a8a;">{{{{ approval_url }}}}</a>
      </p>
    </div>
    <div class="email-footer">
      Email ini dikirim otomatis oleh sistem <strong>Royal Workflow</strong> &bull; PT Royal Abadi Sejahtera
    </div>
  </div>
</body>
</html>"""

        submission_received_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  {html_email_style}
</head>
<body>
  <div class="email-card">
    <div class="email-header">
      <div class="email-brand">&#128176; ROYAL WORKFLOW &bull; KONFIRMASI PENGAJUAN</div>
      <h1 class="email-title">Pengajuan Biaya Berhasil Diajukan</h1>
    </div>
    <div class="email-body">
      <div style="margin-bottom: 16px;">
        <span class="badge-pill badge-pending">&bull; Memulai Alur: Review Atasan Cabang</span>
      </div>
      <p style="font-size: 14px; color: #334155; line-height: 1.6; margin-top: 0;">
        Halo <strong>{{{{ submission.submitter.get_full_name|default:submission.submitter.username }}}}</strong>,
      </p>
      <p style="font-size: 13.5px; color: #475569; line-height: 1.6;">
        Pengajuan biaya Anda untuk <strong>{{{{ form_data.nama_kegiatan|default:"Pengajuan Biaya Operasional" }}}}</strong> telah berhasil dicatat dan masuk ke antrean alur persetujuan.
      </p>

      <table class="info-table">
        <tr>
          <td class="info-label">Nomor Pengajuan</td>
          <td class="info-value"><strong>#{{{{ submission.id }}}}</strong></td>
        </tr>
        <tr>
          <td class="info-label">Total Nominal</td>
          <td class="info-value" style="color: #1e3a8a; font-weight: 700;">Rp {{{{ form_data.total_nominal|default:"0" }}}}</td>
        </tr>
        <tr>
          <td class="info-label">Cabang &amp; Divisi</td>
          <td class="info-value">{{{{ form_data.cabang|default:"Cabang Bandung" }}}} &bull; {{{{ form_data.department_pembuat|default:"Operasional Cabang" }}}}</td>
        </tr>
      </table>

      <div style="text-align: center; margin: 24px 0 16px;">
        <a href="{{{{ submission_url }}}}" class="btn-cta">Pantau Progress Pengajuan di Web</a>
      </div>
    </div>
    <div class="email-footer">
      Email ini dikirim otomatis oleh sistem <strong>Royal Workflow</strong> &bull; PT Royal Abadi Sejahtera
    </div>
  </div>
</body>
</html>"""

        workflow_approved_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  {html_email_style}
</head>
<body>
  <div class="email-card">
    <div class="email-header" style="background: linear-gradient(135deg, #065f46 0%, #047857 100%);">
      <div class="email-brand" style="color: #a7f3d0;">&#9989; ROYAL WORKFLOW &bull; ALUR SELESAI</div>
      <h1 class="email-title">Pengajuan Biaya Telah Disahkan Penuh &amp; Selesai</h1>
    </div>
    <div class="email-body">
      <div style="margin-bottom: 16px;">
        <span class="badge-pill badge-approved">&#10004; CLOSED &amp; VERIFIED (Selesai Penuh)</span>
      </div>
      <p style="font-size: 14px; color: #334155; line-height: 1.6; margin-top: 0;">
        Halo <strong>{{{{ submission.submitter.get_full_name|default:submission.submitter.username }}}}</strong>,
      </p>
      <p style="font-size: 13.5px; color: #475569; line-height: 1.6;">
        Seluruh tahapan persetujuan untuk <strong>{{{{ form_data.nama_kegiatan|default:"Pengajuan Biaya Operasional" }}}}</strong>, termasuk pencairan transfer dana dan verifikasi closing bukti realisasi telah disahkan penuh oleh Finance.
      </p>

      <table class="info-table">
        <tr>
          <td class="info-label">Nomor Pengajuan</td>
          <td class="info-value"><strong>#{{{{ submission.id }}}}</strong></td>
        </tr>
        <tr>
          <td class="info-label">Total Anggaran</td>
          <td class="info-value" style="color: #059669; font-size: 16px; font-weight: 700;">Rp {{{{ form_data.total_nominal|default:"0" }}}}</td>
        </tr>
        <tr>
          <td class="info-label">Status Akhir</td>
          <td class="info-value" style="color: #16a34a; font-weight: 600;">&#10004; Selesai / Closed</td>
        </tr>
      </table>

      <div style="text-align: center; margin: 24px 0 16px;">
        <a href="{{{{ submission_url }}}}" class="btn-cta" style="background-color: #059669;">Lihat Dokumen Final di Web</a>
      </div>
    </div>
    <div class="email-footer">
      Email ini dikirim otomatis oleh sistem <strong>Royal Workflow</strong> &bull; PT Royal Abadi Sejahtera
    </div>
  </div>
</body>
</html>"""

        approval_reminder_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  {html_email_style}
</head>
<body>
  <div class="email-card">
    <div class="email-header" style="background: linear-gradient(135deg, #78350f 0%, #b45309 100%);">
      <div class="email-brand" style="color: #fde68a;">&#9200; ROYAL WORKFLOW &bull; REMINDER PERSETUJUAN</div>
      <h1 class="email-title">PENGINGAT: Tindakan pada Tahap {{{{ stage.name|default:"Review" }}}} Tertunda</h1>
    </div>
    <div class="email-body">
      <div style="margin-bottom: 16px;">
        <span class="badge-pill badge-pending" style="background-color: #fef3c7; color: #b45309; border-color: #fde68a;">&#9888; Action Required: Approval Reminder</span>
      </div>
      <p style="font-size: 14px; color: #334155; line-height: 1.6; margin-top: 0;">
        Halo <strong>{{{{ approver.get_full_name|default:approver.username|default:"Tim Reviewer" }}}}</strong>,
      </p>
      <p style="font-size: 13.5px; color: #475569; line-height: 1.6;">
        Ini adalah pengingat ramah bahwa pengajuan biaya pada tahap <strong>{{{{ stage.name }}}}</strong> masih <strong>menunggu tindakan</strong> Anda:
      </p>

      <table class="info-table">
        <tr>
          <td class="info-label">Nama Kegiatan</td>
          <td class="info-value"><strong>{{{{ form_data.nama_kegiatan|default:"Pengajuan Biaya Operasional" }}}}</strong></td>
        </tr>
        <tr>
          <td class="info-label">Total Nominal</td>
          <td class="info-value" style="color: #b45309; font-weight: 700;">Rp {{{{ form_data.total_nominal|default:"0" }}}}</td>
        </tr>
        <tr>
          <td class="info-label">Cabang</td>
          <td class="info-value">{{{{ form_data.cabang|default:"Cabang Bandung" }}}}</td>
        </tr>
      </table>

      <div style="text-align: center; margin: 24px 0 16px;">
        <a href="{{{{ approval_url }}}}" class="btn-cta" style="background-color: #b45309;">&#10148; Review &amp; Selesaikan Sekarang</a>
      </div>
    </div>
    <div class="email-footer">
      Email ini dikirim otomatis oleh sistem <strong>Royal Workflow</strong> &bull; PT Royal Abadi Sejahtera
    </div>
  </div>
</body>
</html>"""

        NotificationRule.objects.update_or_create(
            workflow=workflow,
            event="submission_received",
            stage=None,
            defaults={
                "notify_submitter": True,
                "subject_template": "[Royal Workflow] Pengajuan Biaya '{nama_kegiatan}' Masuk ke Alur Persetujuan (#{submission_id})",
                "body_template": submission_received_html.strip(),
            },
        )
        NotificationRule.objects.update_or_create(
            workflow=workflow,
            event="workflow_approved",
            stage=None,
            defaults={
                "notify_submitter": True,
                "subject_template": "[Disetujui Penuh] Pengajuan Biaya '{nama_kegiatan}' Selesai",
                "body_template": workflow_approved_html.strip(),
            },
        )

        for st in created_stages:
            NotificationRule.objects.update_or_create(
                workflow=workflow,
                event="approval_request",
                stage=st,
                defaults={
                    "notify_stage_groups": True,
                    "notify_stage_assignees": True,
                    "subject_template": f"[Action Required] {st.name}: {{nama_kegiatan}}",
                    "body_template": approval_request_html.strip(),
                },
            )
            NotificationRule.objects.update_or_create(
                workflow=workflow,
                event="approval_reminder",
                stage=st,
                defaults={
                    "notify_stage_groups": True,
                    "notify_stage_assignees": True,
                    "subject_template": f"[Reminder] Tindakan Tertunda pada {st.name}: {{nama_kegiatan}}",
                    "body_template": approval_reminder_html.strip(),
                },
            )

        self.stdout.write("Configured NotificationRules for Submission, 6-Stage Approvals, Reminders, and Final Approval.")

        # 7. Bersihkan submission lama jika ada agar bersih (Clean Slate)
        deleted_count, _ = FormSubmission.objects.filter(form_definition=form).delete()
        if deleted_count > 0:
            self.stdout.write(f"Membersihkan {deleted_count} submission data lama.")

        self.stdout.write(
            self.style.SUCCESS(
                f"[SUCCESS] Form Definition 'Pengajuan Biaya & Anggaran Operasional' siap!\n"
                f"  • Slug: {form.slug}\n"
                f"  • URL Form: /forms/{form.slug}/\n"
                f"  • Alur Persetujuan: 6 Tahapan Operasional Aktif!\n"
            )
        )
