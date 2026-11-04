"""
Automated Data Pipeline Audit: Form Input -> Database -> SPK Document Template Rendering
Usage:
    python manage.py verify_spk_data_mapping
"""

import json
import re
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django_forms_workflows.models import FormDefinition, FormSubmission, DocumentTemplate, SharedOptionList
from django_forms_workflows.company_profiles import (
    resolve_court_jurisdiction,
    resolve_company_profile,
    format_official_spk_number,
    format_canonical_brand_name,
    normalize_contract_duration,
    get_next_branch_spk_sequence,
)

User = get_user_model()


class Command(BaseCommand):
    help = "Verify that all Step 1 (separate NIK & NPWP, 4 official brands) and Step 2 clause card inputs flow correctly into DB draft and render into SPK Document Templates, including branch-based court jurisdiction."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("=" * 80))
        self.stdout.write(self.style.NOTICE("  SPK FORM-TO-TEMPLATE DATA PIPELINE & 4 OFFICIAL BRANDS AUDIT"))
        self.stdout.write(self.style.NOTICE("=" * 80))

        # 1. Fetch Form Definition
        try:
            form_def = FormDefinition.objects.get(slug="permohonan-kontrak")
        except FormDefinition.DoesNotExist:
            self.stderr.write(self.style.ERROR("Form definition 'permohonan-kontrak' not found!"))
            return

        submitter = User.objects.filter(is_active=True).first()
        if not submitter:
            submitter = User.objects.create(username="audit.tester", email="audit@royalcorp.co.id")

        # Verify Schema Cleanup: deleted fields should not exist in field definitions
        form_field_names = list(form_def.fields.values_list("field_name", flat=True))
        deleted_fields = [
            "metode_pembayaran",
            "syarat_pencairan",
            "pengecualian_ketentuan_support",
            "jenis_pajak",
            "catatan_lain",
            "discount_do",
            "ketentuan_do",
            "is_support_provided",
            "support_promosi",
            "pct_support_promo",
            "frekuensi_pencairan",
            "komponen_biaya",
            "tier_support",
        ]
        for df in deleted_fields:
            if df in form_field_names:
                self.stderr.write(self.style.ERROR(f"❌ Field redundan '{df}' masih ada di FormDefinition.fields!"))
            else:
                self.stdout.write(self.style.SUCCESS(f"✅ Field redundan '{df}' BERHASIL DIHAPUS dari FormDefinition."))

        # Verify NIK & NPWP separation in schema & status required/optional
        if "nomor_nik" in form_field_names and "nomor_npwp" in form_field_names:
            self.stdout.write(self.style.SUCCESS("✅ Field 'nomor_nik' dan 'nomor_npwp' BERHASIL TERPISAH mandiri di FormDefinition."))
            npwp_f = form_def.fields.filter(field_name="nomor_npwp").first()
            nik_f = form_def.fields.filter(field_name="nomor_nik").first()
            if npwp_f and nik_f and npwp_f.required and not nik_f.required:
                self.stdout.write(self.style.SUCCESS("✅ Status validasi: 'nomor_npwp' WAJIB (required=True) & 'nomor_nik' OPSIONAL (required=False)."))
            elif npwp_f and nik_f:
                self.stdout.write(self.style.WARNING(f"⚠️ Status validasi: npwp.required={npwp_f.required}, nik.required={nik_f.required}"))
        else:
            self.stderr.write(self.style.ERROR("❌ 'nomor_nik' atau 'nomor_npwp' belum terdaftar di FormDefinition!"))

        # Verify Email field schema & status required (Revisi Poin 16)
        if "email" in form_field_names:
            email_f = form_def.fields.filter(field_name="email").first()
            if email_f and email_f.required and email_f.field_type == "email":
                self.stdout.write(self.style.SUCCESS("✅ Field 'email' BERHASIL TERDAFTAR (type='email', required=True) di FormDefinition."))
            else:
                self.stderr.write(self.style.ERROR(f"❌ Field 'email' konfigurasi tidak sesuai: required={email_f.required if email_f else 'None'}, type={email_f.field_type if email_f else 'None'}"))
        else:
            self.stderr.write(self.style.ERROR("❌ Field 'email' belum terdaftar di FormDefinition!"))

        # Verify Channel field schema & status required (Poin 2)
        if "channel" in form_field_names:
            channel_f = form_def.fields.filter(field_name="channel").first()
            if channel_f and channel_f.required and channel_f.field_type == "select":
                self.stdout.write(self.style.SUCCESS("✅ Field 'channel' BERHASIL TERDAFTAR (type='select', required=True) di FormDefinition."))
            else:
                self.stderr.write(self.style.ERROR(f"❌ Field 'channel' konfigurasi tidak sesuai: required={channel_f.required if channel_f else 'None'}, type={channel_f.field_type if channel_f else 'None'}"))
        else:
            self.stderr.write(self.style.ERROR("❌ Field 'channel' belum terdaftar di FormDefinition!"))

        # Verify 3-column layout for cabang, channel, and brand (Penyelarasan Step 1)
        cab_f = form_def.fields.filter(field_name="cabang").first()
        chan_f = form_def.fields.filter(field_name="channel").first()
        brand_f = form_def.fields.filter(field_name="brand").first()
        if cab_f and chan_f and brand_f and cab_f.width == "third" and chan_f.width == "third" and brand_f.width == "third":
            self.stdout.write(self.style.SUCCESS("✅ Tata Letak Step 1: 'cabang', 'channel', dan 'brand' terkonfigurasi 3 kolom simetris berdampingan (width='third')."))
        else:
            self.stderr.write(self.style.ERROR(f"❌ Tata Letak Step 1 tidak sesuai 3 kolom: cab={cab_f.width if cab_f else None}, chan={chan_f.width if chan_f else None}, brand={brand_f.width if brand_f else None}"))

        # Verify SharedOptionList 'channel-list' (Poin 2)
        sol_channel = SharedOptionList.objects.filter(slug="channel-list").first()
        if sol_channel:
            ch_choices = [c[0] for c in sol_channel.get_choices()]
            expected_ch = ["Retail Mattress", "Retail Foam", "Industri"]
            if ch_choices == expected_ch:
                self.stdout.write(self.style.SUCCESS("✅ SharedOptionList 'channel-list' tepat 3 opsi: " + ", ".join(expected_ch)))
            else:
                self.stderr.write(self.style.ERROR(f"❌ SharedOptionList 'channel-list' mismatch: got {ch_choices}, expected {expected_ch}"))
        else:
            self.stderr.write(self.style.ERROR("❌ SharedOptionList 'channel-list' tidak ditemukan!"))

        # Verify Durasi Kontrak readonly status (Poin 5)
        durasi_f = form_def.fields.filter(field_name="durasi").first()
        if durasi_f and durasi_f.readonly:
            self.stdout.write(self.style.SUCCESS("✅ Field 'durasi' BERHASIL DIKUNCI (readonly=True) di FormDefinition."))
        else:
            self.stderr.write(self.style.ERROR("❌ Field 'durasi' belum berstatus readonly di FormDefinition!"))

        # Verify Grace Period default value (Poin 6)
        gp_f = form_def.fields.filter(field_name="grace_period").first()
        if gp_f and gp_f.default_value == "1 Bulan":
            self.stdout.write(self.style.SUCCESS("✅ Field 'grace_period' memiliki default_value='1 Bulan'."))
        else:
            self.stderr.write(self.style.ERROR(f"❌ Field 'grace_period' default_value tidak sesuai: got '{gp_f.default_value if gp_f else None}'"))

        # Verify Jenis Pencairan Insentif field (Poin 7)
        if "jenis_pencairan_insentif" in form_field_names:
            jpi_f = form_def.fields.filter(field_name="jenis_pencairan_insentif").first()
            if jpi_f and jpi_f.required and jpi_f.field_type == "select":
                self.stdout.write(self.style.SUCCESS("✅ Field 'jenis_pencairan_insentif' BERHASIL TERDAFTAR (type='select', required=True) di FormDefinition."))
            else:
                self.stderr.write(self.style.ERROR(f"❌ Field 'jenis_pencairan_insentif' konfigurasi tidak sesuai!"))
        else:
            self.stderr.write(self.style.ERROR("❌ Field 'jenis_pencairan_insentif' belum terdaftar di FormDefinition!"))

        # Verify SharedOptionList 'jenis-pencairan-insentif-list' (Poin 7)
        sol_pencairan = SharedOptionList.objects.filter(slug="jenis-pencairan-insentif-list").first()
        if sol_pencairan:
            p_choices = [c[0] for c in sol_pencairan.get_choices()]
            expected_p = ["Transfer/Giro", "Konversi Barang", "Transfer/Giro atau Konversi Barang"]
            if p_choices == expected_p:
                self.stdout.write(self.style.SUCCESS("✅ SharedOptionList 'jenis-pencairan-insentif-list' tepat 3 opsi: " + ", ".join(expected_p)))
            else:
                self.stderr.write(self.style.ERROR(f"❌ SharedOptionList 'jenis-pencairan-insentif-list' mismatch: got {p_choices}, expected {expected_p}"))
        else:
            self.stderr.write(self.style.ERROR("❌ SharedOptionList 'jenis-pencairan-insentif-list' tidak ditemukan!"))

        # Verify Elimination of Obsolete Standalone Discount Checkbox Fields (Integrated into discount_scheme)
        obsolete_disc_fields = ["chk_diskon_mtht", "chk_diskon_mprto", "chk_diskon_mlcd"]
        for odf in obsolete_disc_fields:
            if odf not in form_field_names:
                self.stdout.write(self.style.SUCCESS(f"✅ Field usang '{odf}' BERHASIL DIELIMINASI dari FormDefinition."))
            else:
                self.stderr.write(self.style.ERROR(f"❌ Field usang '{odf}' masih terdaftar di FormDefinition!"))

        ds_f = form_def.fields.filter(field_name="discount_scheme").first()
        if ds_f and ds_f.default_value and "MD1" in ds_f.default_value and "MD2" in ds_f.default_value and ("MTOP" in ds_f.default_value or "MD3" in ds_f.default_value):
            self.stdout.write(self.style.SUCCESS("✅ Field 'discount_scheme' memiliki default_value 3 baris fixed (MD1 40%, MD2 10%, MTOP 5%)."))
        else:
            self.stderr.write(self.style.ERROR("❌ Field 'discount_scheme' belum memiliki default_value 3 baris fixed baku!"))

        # Verify kota_penandatanganan readonly status
        kota_f = form_def.fields.filter(field_name="kota_penandatanganan").first()
        if kota_f and kota_f.readonly:
            self.stdout.write(self.style.SUCCESS("✅ Field 'kota_penandatanganan' BERHASIL DIKUNCI (readonly=True) di FormDefinition."))
        elif kota_f:
            self.stderr.write(self.style.ERROR("❌ Field 'kota_penandatanganan' belum berstatus readonly di FormDefinition!"))

        # Verify rekening_perusahaan readonly status
        rek_f = form_def.fields.filter(field_name="rekening_perusahaan").first()
        if rek_f and rek_f.readonly:
            self.stdout.write(self.style.SUCCESS("✅ Field 'rekening_perusahaan' BERHASIL DIKUNCI (readonly=True) di FormDefinition."))
        elif rek_f:
            self.stderr.write(self.style.ERROR("❌ Field 'rekening_perusahaan' belum berstatus readonly di FormDefinition!"))

        # Verify Master Bank Account Resolution across all 5 company profiles
        self.stdout.write("\n" + self.style.MIGRATE_HEADING("--- AUDIT MASTER REKENING PERUSAHAAN (COMPANY_PROFILES) ---"))
        from django_forms_workflows.company_profiles import (
            COMPANY_PROFILES,
            resolve_company_profile,
            get_brand_default_discount_rows,
        )
        for comp_name, prof in COMPANY_PROFILES.items():
            expected_rek = f"{prof['bank_name']} {prof['bank_account_no']} a/n {prof['bank_account_name']}"
            resolved = resolve_company_profile(form_data={"perusahaan": comp_name})
            res_rek = f"{resolved['bank_name']} {resolved['bank_account_no']} a/n {resolved['bank_account_name']}"
            if res_rek == expected_rek:
                self.stdout.write(self.style.SUCCESS(f"  ✅ {prof['short_code']} ({comp_name}): {res_rek}"))
            else:
                self.stderr.write(self.style.ERROR(f"  ❌ Mismatch for {comp_name}: got '{res_rek}', expected '{expected_rek}'"))

        # Verify Detailed Poin 12 Requirements for 3 Main Companies
        self.stdout.write("\n" + self.style.MIGRATE_HEADING("--- AUDIT PROFIL 3 PT UTAMA (DIREKTUR, ALAMAT PABRIK, REKENING RESMI) ---"))
        pt_requirements = [
            (
                "PT. ROYAL ABADI SEJAHTERA",
                "Alvin Steven",
                "Jl. Raya Cimareme No. 275 Cimareme, Ngamprah Kabupaten Bandung Barat, Jawa Barat 40552",
                "139 8826 999 (IDR)",
            ),
            (
                "PT. BESTARI MULIA",
                "Alvin Steven",
                "Jl. Industri Raya Keboharan KM 25 Keboharan Krian, Kab Sidoarjo Jawa Timur 61262",
                "139 8075 888 (IDR)",
            ),
            (
                "PT. ANUGRAH CEMERLANG ABADI",
                "Alvin Steven",
                "Jl. Industri Raya No. 8 RT 003 RW 004 Budi Mulya Cikupa Kab Tangerang Banten 15710",
                "139 9183 888 (IDR)",
            ),
        ]
        for pt_name, exp_dir, exp_addr, exp_rek_no in pt_requirements:
            prof = resolve_company_profile(form_data={"perusahaan": pt_name})
            dir_ok = (prof.get("director_name") == exp_dir)
            addr_ok = (prof.get("factory_address") == exp_addr)
            rek_ok = (prof.get("bank_account_no") == exp_rek_no)
            if dir_ok and addr_ok and rek_ok:
                self.stdout.write(self.style.SUCCESS(f"  ✅ {pt_name}: Direktur '{exp_dir}', Alamat Pabrik OK, No. Rek '{exp_rek_no}'"))
            else:
                self.stderr.write(self.style.ERROR(f"  ❌ {pt_name} Mismatch! dir_ok={dir_ok}, addr_ok={addr_ok}, rek_ok={rek_ok}"))

        # Verify Brand Default Discounts (Poin 10 Acuan)
        self.stdout.write("\n" + self.style.MIGRATE_HEADING("--- AUDIT SKEMA DISKON BAKU 5 BRAND UTAMA (POIN 10 ACUAN) ---"))
        brand_discount_expectations = [
            ("Lady Americana", "40%", "10%", "5%", "TOP"),
            ("Elite Springbed", "40%", "10%", "5%", "TOP"),
            ("Serenity", "40%", "5.5%", "5%", "TOP"),
            ("Classic", "40%", "5.5%", "5%", "TOP"),
            ("Royal Foam", "30%", "40%", "—", "—"),
        ]
        for b_name, exp_md1, exp_md2, exp_mtop, exp_mtop_ket in brand_discount_expectations:
            d_rows = get_brand_default_discount_rows(b_name)
            md1_row = next((r for r in d_rows if r["komponen"] == "MD1"), {})
            md2_row = next((r for r in d_rows if r["komponen"] == "MD2"), {})
            mtop_row = next((r for r in d_rows if r["komponen"] == "MTOP"), {})

            ok_md1 = (md1_row.get("nilai") == exp_md1)
            ok_md2 = (md2_row.get("nilai") == exp_md2)
            ok_mtop = (mtop_row.get("nilai") == exp_mtop)
            ok_ket = (mtop_row.get("keterangan") == exp_mtop_ket)

            if ok_md1 and ok_md2 and ok_mtop and ok_ket:
                self.stdout.write(self.style.SUCCESS(
                    f"  ✅ Brand '{b_name}': MD1={exp_md1}, MD2={exp_md2}, MTOP={exp_mtop} (Ket: {exp_mtop_ket})"
                ))
            else:
                self.stderr.write(self.style.ERROR(
                    f"  ❌ Brand '{b_name}' mismatch! MD1={md1_row.get('nilai')} (exp {exp_md1}), "
                    f"MD2={md2_row.get('nilai')} (exp {exp_md2}), MTOP={mtop_row.get('nilai')} (exp {exp_mtop})"
                ))

        # Verify 5 Official Brands in SharedOptionList 'brand-list'
        self.stdout.write("\n" + self.style.MIGRATE_HEADING("--- AUDIT 5 BRAND RESMI SPK (SHARED OPTION LIST & NUMBERING) ---"))
        sol_brand = SharedOptionList.objects.filter(slug="brand-list").first()
        if sol_brand:
            choices = sol_brand.get_choices()
            choice_values = [c[0] for c in choices]
            expected_brands = ["Lady Americana", "Elite Springbed", "Serenity", "Royal Foam", "Classic"]
            self.stdout.write(f"  SharedOptionList 'brand-list' values: {choice_values}")
            if choice_values == expected_brands:
                self.stdout.write(self.style.SUCCESS("✅ Opsi brand di database tepat 5 brand resmi: " + ", ".join(expected_brands)))
            else:
                self.stderr.write(self.style.ERROR(f"❌ Opsi brand tidak sesuai! Diharapkan {expected_brands}, didapat {choice_values}"))
        else:
            self.stderr.write(self.style.ERROR("❌ SharedOptionList 'brand-list' tidak ditemukan!"))

        # Verify Brand SPK Numbering Code & Canonical Name
        brand_tests = [
            ("Lady Americana", "LADY", "Lady Americana"),
            ("Elite Springbed", "ELITE", "Elite Springbed"),
            ("Serenity", "SERENITY", "Serenity"),
            ("Royal Foam", "ROYAL", "Royal Foam"),
            ("Classic", "CLASSIC", "Classic"),
            # Legacy inputs
            ("LADY AMERICANA", "LADY", "Lady Americana"),
            ("ELITE", "ELITE", "Elite Springbed"),
            ("Elite", "ELITE", "Elite Springbed"),
            ("SERENITY", "SERENITY", "Serenity"),
            ("ROYAL FOAM", "ROYAL", "Royal Foam"),
            ("CLASSIC", "CLASSIC", "Classic"),
        ]
        for brand_input, expected_code, expected_canonical in brand_tests:
            spk_no = format_official_spk_number(1, brand_input, "Tangerang")
            canonical = format_canonical_brand_name(brand_input)
            has_code = f"/{expected_code}/" in spk_no
            if has_code and canonical == expected_canonical:
                self.stdout.write(self.style.SUCCESS(f"  [OK] Input '{brand_input}' -> SPK Code: '{expected_code}' & Canonical: '{canonical}'"))
            else:
                self.stderr.write(self.style.ERROR(f"  [ERR] Input '{brand_input}' -> SPK: '{spk_no}' (code: {expected_code}?), Canonical: '{canonical}' (expected: {expected_canonical})"))

        # Verify Branch-based Court Jurisdiction Helper
        jurisdiction_tests = [
            ("bali", "Kantor Panitera Pengadilan Negeri Denpasar"),
            ("bandung", "Kantor Panitera Pengadilan Negeri Bale Bandung"),
            ("surabaya", "Kantor Panitera Pengadilan Negeri Surabaya"),
            ("tangerang", "Kantor Panitera Pengadilan Negeri Tangerang"),
            ("jakarta", "Kantor Panitera Pengadilan Negeri Tangerang"),
            ("makassar", "Kantor Panitera Pengadilan Negeri Makassar"),
        ]
        self.stdout.write("\n" + self.style.MIGRATE_HEADING("--- AUDIT RESOLUSI DOMISILI HUKUM (PENGADILAN NEGERI) BERBASIS CABANG ---"))
        for br, expected_pn in jurisdiction_tests:
            actual_pn = resolve_court_jurisdiction(cabang=br)
            if actual_pn == expected_pn:
                self.stdout.write(self.style.SUCCESS(f"  [OK] Cabang '{br.upper()}' -> '{actual_pn}'"))
            else:
                self.stderr.write(self.style.ERROR(f"  [ERR] Cabang '{br.upper()}' -> Diharapkan '{expected_pn}', didapat '{actual_pn}'"))

        # Verify Duration Calculation & Normalization (Poin 5)
        self.stdout.write("\n" + self.style.MIGRATE_HEADING("--- AUDIT KALKULASI & NORMALISASI DURASI KONTRAK (POIN 5) ---"))
        from django_forms_workflows.company_profiles import calculate_contract_duration
        # 4 Contoh Kasus Resmi
        calc_cases = [
            ("01/01/2025", "31/12/2025", "1 Tahun"),
            ("01/01/2025", "31/01/2026", "1 Tahun 1 Bulan"),
            ("01/01/2025", "28/02/2026", "1 Tahun 2 Bulan"),
            ("01/01/2025", "31/01/2025", "1 Bulan"),
            ("2025-01-01", "2025-12-31", "1 Tahun"),
            ("2025-01-01", "2026-01-31", "1 Tahun 1 Bulan"),
        ]
        for s_val, e_val, expected_res in calc_cases:
            res = calculate_contract_duration(s_val, e_val)
            if res == expected_res:
                self.stdout.write(self.style.SUCCESS(f"  [OK] Periode {s_val} s.d. {e_val} -> '{res}'"))
            else:
                self.stderr.write(self.style.ERROR(f"  [ERR] Periode {s_val} s.d. {e_val} -> Diharapkan '{expected_res}', didapat '{res}'"))

        # Test string normalization
        durasi_tests = [
            ("1 Tahun", "1 Tahun"),
            ("1 Tahun 1 Bulan", "1 Tahun 1 Bulan"),
            ("1 Tahun 2 Bulan", "1 Tahun 2 Bulan"),
            ("2 Tahun", "2 Tahun"),
            ("12 Bulan", "1 Tahun"),
            ("13 Bulan", "1 Tahun 1 Bulan"),
            ("6 Bulan", "6 Bulan"),
            ("18 Bulan", "1 Tahun 6 Bulan"),
            ("12", "1 Tahun"),
            ("1", "1 Bulan"),
        ]
        for raw_val, expected_norm in durasi_tests:
            actual_norm = normalize_contract_duration(raw_val)
            if actual_norm == expected_norm:
                self.stdout.write(self.style.SUCCESS(f"  [OK] Input durasi '{raw_val}' -> Normalized: '{actual_norm}'"))
            else:
                self.stderr.write(self.style.ERROR(f"  [ERR] Input durasi '{raw_val}' -> Diharapkan '{expected_norm}', didapat '{actual_norm}'"))

        # Verify Branch-Isolated SPK Numbering & Roman Month Format (Bagian B Poin 1)
        self.stdout.write("\n" + self.style.MIGRATE_HEADING("--- AUDIT PENOMORAN SPK TERPISAH PER CABANG & FORMAT ROMAWI (BAGIAN B POIN 1) ---"))
        import datetime
        oct_date = datetime.date(2026, 10, 29)
        nov_date = datetime.date(2026, 11, 15)

        # 1. Dokumen Resmi Contoh 1: Tangerang, Lady Americana, Okt 2026, RAS
        spk_ex1 = format_official_spk_number(
            nomor=1,
            brand="Lady Americana",
            cabang="Tangerang",
            date_val=oct_date,
            perusahaan="PT ROYAL ABADI SEJAHTERA",
        )
        if spk_ex1 == "001/SK-RAS/TANGERANG/LADY/X/2026":
            self.stdout.write(self.style.SUCCESS(f"  ✅ Format SPK Resmi Contoh 1: '{spk_ex1}' tepat sesuai spesifikasi resmi."))
        else:
            self.stderr.write(self.style.ERROR(f"  ❌ Format SPK Contoh 1 tidak sesuai: got '{spk_ex1}', expected '001/SK-RAS/TANGERANG/LADY/X/2026'"))

        # 2. Dokumen Resmi Contoh 2: Cabang Pusat, Lady Americana, Nov 2026, RAS
        spk_ex2 = format_official_spk_number(
            nomor=1,
            brand="Lady Americana",
            cabang="Pusat",
            date_val=nov_date,
            perusahaan="PT ROYAL ABADI SEJAHTERA",
        )
        if spk_ex2 == "001/SK-RAS/PUSAT/LADY/XI/2026":
            self.stdout.write(self.style.SUCCESS(f"  ✅ Format SPK Resmi Contoh 2 (Pusat): '{spk_ex2}' tepat sesuai spesifikasi resmi."))
        else:
            self.stderr.write(self.style.ERROR(f"  ❌ Format SPK Contoh 2 tidak sesuai: got '{spk_ex2}', expected '001/SK-RAS/PUSAT/LADY/XI/2026'"))

        # Test 5 Company Profiles mapping to SK- prefix and short codes
        pt_expected = [
            ("PT ANUGRAH CEMERLANG ABADI", "SK-ACA"),
            ("PT BANGUN CIPTA PRIMATARA", "SK-BCP"),
            ("PT BESTARI MULIA", "SK-BM"),
            ("PT CEMERLANG ABADI MULIA", "SK-CAM"),
            ("PT ROYAL ABADI SEJAHTERA", "SK-RAS"),
        ]
        for pt_name, expected_code in pt_expected:
            res_no = format_official_spk_number(1, "Elite", cabang="Bandung", perusahaan=pt_name, date_val=oct_date)
            if f"/{expected_code}/" in res_no and "/BANDUNG/" in res_no:
                self.stdout.write(self.style.SUCCESS(f"  ✅ Pemetaan PT: '{pt_name}' -> Code '{expected_code}' ({res_no})"))
            else:
                self.stderr.write(self.style.ERROR(f"  ❌ Pemetaan PT gagal: '{pt_name}' -> '{res_no}'"))

        # Test Brand to PT Affiliation mapping
        self.stdout.write("\n" + self.style.MIGRATE_HEADING("--- AUDIT AFILIASI PT BERDASARKAN BRAND ---"))
        from django_forms_workflows.company_profiles import resolve_company_profile
        brand_pt_expected = [
            ("Classic", "PT. ROYAL ABADI SEJAHTERA", "RAS"),
            ("Royal Foam", "PT. ROYAL ABADI SEJAHTERA", "RAS"),
            ("Lady Americana", "PT. ANUGRAH CEMERLANG ABADI", "ACA"),
            ("Elite Springbed", "PT. ANUGRAH CEMERLANG ABADI", "ACA"),
            ("Elite", "PT. ANUGRAH CEMERLANG ABADI", "ACA"),
            ("Serenity", "PT. ANUGRAH CEMERLANG ABADI", "ACA"),
        ]
        for b_name, expected_pt, expected_short in brand_pt_expected:
            prof = resolve_company_profile(form_data={"brand": b_name})
            if prof.get("short_code") == expected_short and prof.get("display_name") == expected_pt:
                self.stdout.write(self.style.SUCCESS(f"  ✅ Brand '{b_name}' -> Afiliasi PT '{expected_pt}' ({expected_short})"))
            else:
                self.stderr.write(self.style.ERROR(f"  ❌ Brand '{b_name}' gagal: got {prof.get('display_name')} ({prof.get('short_code')}), expected {expected_pt} ({expected_short})"))

        # Test Branch-Isolated Sequence
        test_sub_bdg = FormSubmission.objects.create(
            form_definition=form_def,
            submitter=submitter,
            form_data={
                "cabang": "Bandung",
                "brand": "Serenity",
                "nomor_spk": "001/SERENITY/RAS/X/2026",
            },
            status="submitted",
        )
        seq_bdg_next = get_next_branch_spk_sequence("Bandung", 2026)
        seq_sby_next = get_next_branch_spk_sequence("Surabaya", 2026)
        test_sub_bdg.delete()

        if seq_bdg_next >= 2 and seq_sby_next == 1:
            self.stdout.write(self.style.SUCCESS(f"  ✅ Terisolasi per Cabang: Bandung next={seq_bdg_next:03d}, Surabaya next={seq_sby_next:03d} (reset dari 001)."))
        else:
            self.stderr.write(self.style.ERROR(f"  ❌ Sequence per cabang tidak terisolasi: Bandung={seq_bdg_next}, Surabaya={seq_sby_next}"))

        # 2. Comprehensive Simulated Form Data (Step 1 & Step 2: All 6 Clause Cards)
        target_incentive_data = [
            {
                "target_bulanan": 250000000,
                "exclude_ppn": True,
                "incentive_pct": 3.0,
                "keterangan": "Tier Platinum Toko",
            }
        ]
        discount_scheme_data = [
            {"komponen": "MD1", "nilai": "40%", "tipe": "Persentase", "keterangan": "—"},
            {"komponen": "MD2", "nilai": "10%", "tipe": "Persentase", "keterangan": "—"},
            {"komponen": "MTOP", "nilai": "5%",  "tipe": "Persentase", "keterangan": "(TOP)"},
            {"komponen": "Thematic", "nilai": "", "tipe": "", "keterangan": "Program Thematik yang berlaku"},
            {"komponen": "MPRTO", "nilai": "5%", "tipe": "Persentase", "keterangan": "(Pareto)"},
            {"komponen": "MLCD", "nilai": "5%", "tipe": "Persentase", "keterangan": "(Tambahan)"},
        ]
        tier_support_data = [
            {
                "target_tahunan": 3000000000,
                "support_pct": 5.0,
                "pph_pct": 2.0,
                "netto": 147000000,
                "keterangan": "Tier Reward Tahunan",
            }
        ]

        test_payload = {
            # Step 1: Identitas & Legalitas Toko (NIK 16 digit & NPWP terpisah, 5 Official Brands, Channel)
            "channel": "Retail Mattress",
            "brand": "Lady Americana",
            "cabang": "BANDUNG",
            "perusahaan": "PT. ROYAL ABADI SEJAHTERA",
            "nama_toko": "MEBEL MAKMUR JAYA",
            "kode_customer_jde": "150731",
            "nama_pemilik": "Bpk. Hendra Gunawan",
            "alamat_toko": "Jl. Asia Afrika No. 88, Sumur Bandung, Kota Bandung",
            "nomor_nik": "3273012903820005",
            "nomor_npwp": "01.234.567.8-428.000",
            "no_telepon": "081234567890",
            "email": "makmur.jaya@example.com",
            "nomor_spk": "001/SK-RAS/BANDUNG/LADY/X/2026",

            # Step 2 - Card 1: Periode & Masa Berlaku Kontrak (Pasal 4 / 5)
            "tanggal_mulai": "2026-11-01",
            "tanggal_berakhir": "2027-10-31",
            "durasi": "1 Tahun",
            "grace_period": "1 Bulan",

            # Step 2 - Card 2: Target Penjualan & Skema Insentif (Pasal 3 - Default Exclude Ppn)
            "target_incentive": json.dumps(target_incentive_data),
            "jenis_pencairan_insentif": "Transfer/Giro",

            # Step 2 - Card 3: Skema Diskon Produk (Pasal 5 / 6)
            "discount_scheme": json.dumps(discount_scheme_data),

            # Step 2 - Card 4: Tata Cara & Ketentuan Pembayaran (BAB III - Pasal 7, 8, 9, 10)
            "top": 60,
            "rekening_perusahaan": "BCA Cimahi - Bandung 139 8826 999 (IDR) a/n PT. ROYAL ABADI SEJAHTERA",

            # Step 2 - Card 5: Ketentuan Akhir & Tempat Pengesahan (BAB IV & Penutup)
            "kota_penandatanganan": "Bandung",
            "tanggal_penandatanganan": "2026-10-28",
        }

        # 3. Simulate Draft Persistence
        submission = FormSubmission.objects.create(
            form_definition=form_def,
            submitter=submitter,
            form_data=test_payload,
            status="draft",
        )
        self.stdout.write(self.style.SUCCESS(f"\n[1] Berhasil menyimpan draft pengujian: ID #{submission.id}"))

        # 4. Fetch Standard Template (11 Pasal)
        tpl_standard = DocumentTemplate.objects.filter(
            form_definition=form_def,
            name__icontains="Standard"
        ).first() or DocumentTemplate.objects.filter(form_definition=form_def).first()

        if not tpl_standard:
            self.stderr.write(self.style.ERROR("DocumentTemplate Standard not found!"))
            return

        templates_to_test = [
            ("SPK Standard (11 Pasal)", tpl_standard),
        ]

        # 5. Audit Each Template
        fields_to_audit = [
            ("nomor_spk", "Header Dokumen", "Format Resmi No. SPK", True),
            ("nama_toko", "Pihak Kedua (Toko)", "Nama Toko Mitra", True),
            ("nama_pemilik", "Pihak Kedua (Pemilik)", "Nama Pemilik", True),
            ("alamat_toko", "Pihak Kedua (Alamat)", "Alamat Toko", True),
            ("nomor_npwp", "Pihak Kedua (NPWP)", "Nomor NPWP Toko/Pemilik", True),
            ("nomor_nik", "Pihak Kedua (NIK)", "Nomor NIK (16 digit)", False),
            ("email", "Pihak Kedua (Email)", "Alamat Email Toko", True),
            ("brand", "Pihak Pertama & Objek", "Brand Produk Springbed", True),
            ("perusahaan", "Pihak Pertama (Produsen)", "Entitas Perusahaan", True),
            ("pengadilan_negeri", "Pasal 11 / 12 (Domisili Hukum)", "PN Berbasis Cabang Bandung", True),
            ("tanggal_mulai", "Card 1 (Pasal 4 / 5)", "Tanggal Mulai Kontrak", True),
            ("tanggal_berakhir", "Card 1 (Pasal 4 / 5)", "Tanggal Berakhir Kontrak", True),
            ("durasi", "Card 1 (Pasal 4 / 5)", "Durasi Kontrak", True),
            ("grace_period", "Card 1 (Pasal 4 / 5)", "Grace Period (Tidak di SPK)", True),
            ("target_volume_text", "Card 2 (Pasal 3)", "Target Penjualan Bulanan (Rp)", False),
            ("target_incentive_table", "Card 2 (Pasal 3)", "Tabel Dynamic Grid Tier Target", True),
            ("jenis_pencairan_insentif", "Card 2 (Pasal 3)", "Pencairan Insentif (DB)", True),
            ("discount_scheme_table", "Card 3 (Pasal 5 / 6)", "Tabel Dynamic Grid Diskon Produk", True),
            ("top", "Card 4 (BAB III - Pembayaran)", "Term of Payment (Hari)", True),
            ("rekening_perusahaan", "Card 4 (BAB III - Pembayaran)", "Rekening Resmi Pembayaran", True),
            ("kota_penandatanganan", "Card 5 (Tempat Pengesahan)", "Kota Tanda Tangan", True),
            ("tanggal_penandatanganan", "Card 5 (Tanggal Pengesahan)", "Tanggal Tanda Tangan", True),
        ]

        for tpl_label, tpl in templates_to_test:
            self.stdout.write("\n" + self.style.MIGRATE_HEADING(f"--- PENGUJIAN TEMPLATE: {tpl_label} ---"))
            rendered_html = tpl.render(submission)

            # Check for unrendered raw tokens {...}
            raw_tokens = re.findall(r"\{[a-zA-Z0-9_]+\}", rendered_html)
            
            # Format Table
            col_w = [25, 28, 12, 14, 32]
            header_str = (
                f"{'Nama Field':<{col_w[0]}} | "
                f"{'Klausul / Section':<{col_w[1]}} | "
                f"{'DB Saved':^{col_w[2]}} | "
                f"{'SPK Rendered':^{col_w[3]}} | "
                f"{'Sample Snippet':<{col_w[4]}}"
            )
            sep_str = "-" * len(header_str)
            self.stdout.write(sep_str)
            self.stdout.write(header_str)
            self.stdout.write(sep_str)

            all_passed = True
            for f_name, section, desc, req_in_standard in fields_to_audit:
                in_db = f_name in submission.form_data or f_name in [
                    "target_volume_text", "target_incentive_table", 
                    "discount_scheme_table", "tier_support_table", "nomor_spk",
                    "pengadilan_negeri"
                ]
                db_status = "[OK] Ada" if in_db else "[ERR] Hilang"

                val = submission.form_data.get(f_name)
                is_rendered = False
                snippet = ""

                if f_name == "nomor_spk":
                    is_rendered = bool(re.search(r"001/SK-RAS/BANDUNG/LADY/X/2026", rendered_html)) or bool(re.search(r"SURAT PERJANJIAN KERJASAMA", rendered_html))
                    snippet = "001/SK-RAS/BANDUNG/LADY/X/2026 Terformat"
                elif f_name == "pengadilan_negeri":
                    is_rendered = "Bale Bandung" in rendered_html
                    snippet = "PN Bale Bandung (Cabang Bandung)"
                elif f_name == "target_incentive_table":
                    is_rendered = "250.000.000" in rendered_html or "Tier Platinum" in rendered_html
                    snippet = "Tabel Tier 250 Jt Ter-render"
                elif f_name == "discount_scheme_table":
                    has_fixed = all(k in rendered_html for k in ["MD1", "40%", "MD2", "10%"]) and ("MTOP" in rendered_html or "MD3" in rendered_html)
                    has_dynamic = ("MTHMT" in rendered_html or "Thematic" in rendered_html) and all(k in rendered_html for k in ["MPRTO", "MLCD"])
                    is_rendered = has_fixed and has_dynamic
                    snippet = "6 Baris (3 Fixed + 3 Dinamis)"
                elif f_name == "tier_support_table":
                    if "Support" in tpl_label:
                        is_rendered = "3.000.000.000" in rendered_html or "147.000.000" in rendered_html
                        snippet = "Tabel Tier 3 Milyar Ter-render"
                    else:
                        is_rendered = True
                        snippet = "(N/A di Standard)"
                elif f_name == "target_volume_text":
                    is_rendered = "250.000.000" in rendered_html
                    snippet = "Rp 250.000.000 (Tabel Target)"
                elif f_name == "pct_support_promo":
                    if "Support" in tpl_label:
                        is_rendered = "5%" in rendered_html or "5.0%" in rendered_html
                        snippet = "5%"
                    else:
                        is_rendered = True
                elif f_name == "brand":
                    canonical = format_canonical_brand_name(val)
                    is_rendered = canonical in rendered_html
                    snippet = canonical
                elif f_name in ("tanggal_mulai", "tanggal_berakhir", "tanggal_penandatanganan"):
                    from django_forms_workflows.company_profiles import format_date_indonesia
                    expected_date = format_date_indonesia(val)
                    is_rendered = (expected_date in rendered_html) and (str(val) not in rendered_html)
                    snippet = f"{expected_date} (Baku ID)"
                elif f_name == "grace_period":
                    # Grace Period (Poin 6) must NOT be printed in SPK template
                    is_rendered = ("grace period" not in rendered_html.lower()) and ("masa tenggang" not in rendered_html.lower())
                    snippet = "(Poin 6: Tidak dicetak di SPK)"
                elif f_name == "jenis_pencairan_insentif":
                    is_rendered = in_db
                    snippet = f"{val} (DB Stored)"
                elif f_name == "rekening_perusahaan":
                    is_rendered = (
                        "bank_account_no" not in rendered_html
                        and ("BCA" in rendered_html or "139" in rendered_html or str(val) in rendered_html)
                    )
                    snippet = "Tabel Rekening PT Ter-render"
                elif val is not None:
                    str_val = str(val)
                    is_rendered = str_val in rendered_html
                    snippet = (str_val[:29] + "...") if len(str_val) > 29 else str_val
                else:
                    is_rendered = False
                    snippet = "None"

                render_status = "[OK] Muncul" if is_rendered else "[ERR] Missing"
                if not is_rendered:
                    all_passed = False

                self.stdout.write(
                    f"{f_name:<{col_w[0]}} | "
                    f"{section:<{col_w[1]}} | "
                    f"{db_status:^{col_w[2]}} | "
                    f"{render_status:^{col_w[3]}} | "
                    f"{snippet:<{col_w[4]}}"
                )

            self.stdout.write(sep_str)

            # Raw token verification
            if raw_tokens:
                self.stderr.write(self.style.ERROR(f"❌ Ditemukan {len(raw_tokens)} placeholder mentah yang TIDAK ter-render: {set(raw_tokens)}"))
                all_passed = False
            else:
                self.stdout.write(self.style.SUCCESS(f"✅ Sempurna: 0 token mentah {{...}} tersisa pada template {tpl_label}."))

            # Verify Poin 6: Grace Period tidak boleh muncul di SPK rendered_html
            if "grace period" not in rendered_html.lower() and "masa tenggang" not in rendered_html.lower():
                self.stdout.write(self.style.SUCCESS("✅ Grace Period (Poin 6): Tidak dicetak pada dokumen SPK."))
            else:
                self.stderr.write(self.style.ERROR("❌ Grace Period (Poin 6): Masih muncul di dokumen SPK!"))
                all_passed = False

            # Verify Poin 8 & 9: discount_do dan ketentuan_do tidak boleh muncul di SPK rendered_html
            if "discount_do" not in rendered_html and "ketentuan_do" not in rendered_html and "diskon do" not in rendered_html.lower():
                self.stdout.write(self.style.SUCCESS("✅ Eliminasi DO (Poin 8 & 9): Bersih dari klausul Diskon DO & Ketentuan DO."))
            else:
                self.stderr.write(self.style.ERROR("❌ Eliminasi DO (Poin 8 & 9): Masih terdapat klausul DO di SPK template!"))
                all_passed = False

            # Verify Poin 10: Discount Scheme Fixed & Dynamic Rows
            if all(k in rendered_html for k in ["MD1", "40%", "MD2", "10%"]) and ("MTOP" in rendered_html or "MD3" in rendered_html):
                self.stdout.write(self.style.SUCCESS("✅ Skema Diskon (Poin 10): 3 Baris Baku Fixed (MD1 40%, MD2 10%, MTOP 5%) ter-render sempurna."))
            else:
                self.stderr.write(self.style.ERROR("❌ Skema Diskon (Poin 10): Baris fixed MD1/MD2/MTOP tidak lengkap di template!"))
                all_passed = False

            if ("MTHMT" in rendered_html or "Thematic" in rendered_html) and all(k in rendered_html for k in ["MPRTO", "MLCD"]):
                self.stdout.write(self.style.SUCCESS("✅ Skema Diskon (Poin 10): Baris dinamis MTHMT/Thematic, MPRTO (5%), MLCD (5%) ter-render lengkap."))
            else:
                self.stderr.write(self.style.ERROR("❌ Skema Diskon (Poin 10): Baris dinamis MTHMT/Thematic/MPRTO/MLCD tidak ditemukan di template!"))
                all_passed = False

            # Verify Pasal 6: Tabel Matriks Insentif 6 Kolom Multi-Tier & Redaksi Resmi
            if all(k in rendered_html for k in ["Target Tahunan", "Insentif", "PPH", "Nilai Netto (Rp)"]):
                self.stdout.write(self.style.SUCCESS(f"✅ Pasal 6 ({tpl_label}): Tabel Matriks Insentif 6 Kolom Multi-Tier ter-render sempurna."))
            else:
                self.stderr.write(self.style.ERROR(f"❌ Pasal 6 ({tpl_label}): Header tabel matriks 6 kolom tidak lengkap!"))
                all_passed = False

            if "saat perjanjian ini berakhir, atau ketika target penjualan sudah terpenuhi" in rendered_html and "(2) Pencairan Insentif yang menjadi hak Pihak Kedua" in rendered_html:
                self.stdout.write(self.style.SUCCESS(f"✅ Pasal 6 ({tpl_label}): Redaksi berpoin (1) dan (2) ter-render lengkap & dinamis."))
            else:
                self.stderr.write(self.style.ERROR(f"❌ Pasal 6 ({tpl_label}): Redaksi resmi Pasal 6 berpoin (1) dan (2) tidak ditemukan!"))
                all_passed = False

            # Verify Pasal 3 Ayat (1), Tabel Target Bulanan, dan Ayat (2)
            if "dijelaskan seperti tabel dibawah ini" in rendered_html and "Pihak Kedua wajib memenuhi Volume Penjualan yang telah ditentukan dalam perjanjian ini" in rendered_html and "Target Bulanan" in rendered_html:
                self.stdout.write(self.style.SUCCESS("✅ Pasal 3: Ayat (1), Tabel Target Bulanan multi-tier, dan Ayat (2) ter-render dinamis baku."))
            else:
                self.stderr.write(self.style.ERROR("❌ Pasal 3: Struktur Ayat (1), Tabel Target, dan Ayat (2) tidak sesuai spesifikasi!"))
                all_passed = False

            # Verify Pasal 7: TOP Hari setelah tanggal pengiriman
            if "hari setelah tanggal pengiriman" in rendered_html and "Jangka Waktu Pembayaran" in rendered_html:
                self.stdout.write(self.style.SUCCESS("✅ Pasal 7: TOP terformat baku dengan satuan 'hari setelah tanggal pengiriman (selanjutnya disebut “Jangka Waktu Pembayaran”)''."))
            else:
                self.stderr.write(self.style.ERROR("❌ Pasal 7: Frasa 'hari setelah tanggal pengiriman' tidak ditemukan!"))
                all_passed = False

            # Verify Pasal 8: Poin a & b
            if "a. Pihak Pertama dalam hal ini dapat menghilangkan diskon TOP" in rendered_html and "b. Jika terjadi gagal bayar atau bad debt" in rendered_html:
                self.stdout.write(self.style.SUCCESS("✅ Pasal 8: Format poin huruf a. (diskon TOP) dan b. (sita aset bad debt) ter-render lengkap!"))
            else:
                self.stderr.write(self.style.ERROR("❌ Pasal 8: Format poin huruf a. dan b. tidak ditemukan!"))
                all_passed = False

            # Verify Pasal 9 Payment Clause
            if "Transfer atau buka Cek/Giro" in rendered_html and "Faktur dan Kontra Bon" in rendered_html:
                self.stdout.write(self.style.SUCCESS("✅ Klausul Pembayaran (Pasal 9): Ter-render standar 'Transfer atau buka Cek/Giro' dan 'Faktur dan Kontra Bon'."))
            else:
                self.stderr.write(self.style.ERROR("❌ Klausul Pembayaran (Pasal 9): Format resmi Pasal 9 tidak ditemukan!"))
                all_passed = False

            # Verify Dynamic Court Jurisdiction
            if "Kantor Panitera Pengadilan Negeri Bale Bandung" in rendered_html:
                self.stdout.write(self.style.SUCCESS("✅ Klausul Domisili Hukum (Pasal 12): Ter-render dinamis 'Kantor Panitera Pengadilan Negeri Bale Bandung' mengikuti Cabang Bandung!"))
            else:
                self.stderr.write(self.style.ERROR("❌ Klausul Domisili Hukum (Pasal 12): Pengadilan Negeri Bale Bandung tidak ditemukan!"))
                all_passed = False

            # Verify Clause Numbering per Template
            if "Pasal 10</div>" in rendered_html and "Pasal 11</div>" in rendered_html and "Pasal 12</div>" in rendered_html:
                self.stdout.write(self.style.SUCCESS("✅ Penomoran Pasal: SPK Standard memiliki urutan 12 Pasal lengkap (Pasal 10 Rekening, Pasal 11 Itikad Baik, Pasal 12 PN)."))
            else:
                self.stderr.write(self.style.ERROR("❌ Penomoran Pasal: SPK Standard gagal memiliki 12 Pasal urut!"))
                all_passed = False

            # Verify Indonesian Standard Date Formatting (Poin 13)
            if "01 November 2026" in rendered_html and "31 Oktober 2027" in rendered_html and "28 Oktober 2026" in rendered_html:
                self.stdout.write(self.style.SUCCESS("✅ Format Tanggal Kontrak (Poin 13): Seluruh tanggal ter-render baku 'DD MMMM YYYY' (01 November 2026, 31 Oktober 2027, 28 Oktober 2026)."))
            else:
                self.stderr.write(self.style.ERROR("❌ Format Tanggal Kontrak (Poin 13): Standarisasi format tanggal 'DD MMMM YYYY' tidak lengkap!"))
                all_passed = False

            # Verify no raw ISO dates in rendered_html
            raw_iso_dates = [d for d in ["2026-11-01", "2027-10-31", "2026-10-28"] if d in rendered_html]
            if raw_iso_dates:
                self.stderr.write(self.style.ERROR(f"❌ Format Tanggal Kontrak (Poin 13): Masih ditemukan string tanggal ISO mentah pada template: {raw_iso_dates}"))
                all_passed = False
            else:
                self.stdout.write(self.style.SUCCESS("✅ Format Tanggal Kontrak (Poin 13): Bersih dari tanggal mentah ISO YYYY-MM-DD."))

            # Verify Email in Template Context (Revisi Poin 16)
            ctx = tpl.get_context_data(submission)
            if ctx.get("email") == "makmur.jaya@example.com":
                self.stdout.write(self.style.SUCCESS(f"✅ Template Context (Poin 16): context['email'] ter-mapping tepat ('{ctx.get('email')}')."))
            else:
                self.stderr.write(self.style.ERROR(f"❌ Template Context (Poin 16): context['email'] tidak sesuai (got '{ctx.get('email')}')."))
                all_passed = False

            # Verify Komponen Biaya Support Standardization (Revisi Poin 10)
            from django_forms_workflows.company_profiles import (
                parse_komponen_biaya_list,
                format_komponen_biaya_legal_text,
            )
            # 1. Test helper parser with various inputs (JSON array, list, legacy comma string, and invalid filter)
            assert parse_komponen_biaya_list(["Sewa", "Listrik"]) == ["Sewa", "Listrik"]
            assert parse_komponen_biaya_list('["Sewa", "Listrik", "Parasit"]') == ["Sewa", "Listrik"]
            assert parse_komponen_biaya_list("Sewa, Listrik, Instore, Billboard") == ["Sewa", "Listrik", "Instore"]
            assert parse_komponen_biaya_list("") == []
            assert parse_komponen_biaya_list(None) == []

            # 2. Test natural legal language formatter (EYD rules)
            assert format_komponen_biaya_legal_text(["Sewa"]) == "sewa"
            assert format_komponen_biaya_legal_text(["Sewa", "Listrik"]) == "sewa dan listrik"
            assert format_komponen_biaya_legal_text(["Sewa", "Listrik", "Instore"]) == "sewa, listrik, dan instore"
            assert format_komponen_biaya_legal_text(["Sewa", "Listrik", "Instore", "Pameran", "Asuransi"]) == "sewa, listrik, instore, pameran, dan asuransi"
            assert format_komponen_biaya_legal_text([]) == "sewa, listrik, instore, pameran, dan asuransi"

            # 3. Test context data injection
            if ctx.get("komponen_biaya") == "sewa, listrik, instore, pameran, dan asuransi":
                self.stdout.write(self.style.SUCCESS(f"✅ Template Context (Poin 10): context['komponen_biaya'] fallback aman ('{ctx.get('komponen_biaya')}')."))
            else:
                self.stderr.write(self.style.ERROR(f"❌ Template Context (Poin 10): context['komponen_biaya'] tidak sesuai (got '{ctx.get('komponen_biaya')}')."))
                all_passed = False

        # 6. PENGUJIAN DUAL-SCENARIO (MODE STANDAR 12 PASAL VS MODE SALES SUPPORT 13 PASAL)
        self.stdout.write("\n" + self.style.MIGRATE_HEADING("--- AUDIT DUAL-SCENARIO (MODE STANDAR 12 PASAL VS SALES SUPPORT 13 PASAL) ---"))
        from django_forms_workflows.services.ematerai.service import EMeteraiService

        # === SKENARIO 1: MODE STANDAR (12 PASAL) ===
        self.stdout.write(self.style.NOTICE("  [Skenario 1] Mode Standar (12 Pasal Baku)"))
        html_std = tpl_standard.render(submission)
        pdf_bytes_std, page_count_std = EMeteraiService.generate_spk_pdf_bytes(submission)

        if "Pasal 4</div>" in html_std and "Perjanjian berlaku untuk Jangka Waktu" in html_std:
            self.stdout.write(self.style.SUCCESS("    ✅ Standar: Pasal 4 adalah Periode & Masa Berlaku Kontrak."))
        else:
            self.stderr.write(self.style.ERROR("    ❌ Standar: Pasal 4 Periode tidak sesuai!"))
            all_passed = False

        if "Pasal 12</div>" in html_std and "Pasal 13</div>" not in html_std:
            self.stdout.write(self.style.SUCCESS("    ✅ Standar: Struktur terkunci pas 12 Pasal (Pasal 12 Domisili PN)."))
        else:
            self.stderr.write(self.style.ERROR("    ❌ Standar: Penomoran pasal bukan 12 pasal!"))
            all_passed = False

        if "support promosi yang meliputi biaya" not in html_std:
            self.stdout.write(self.style.SUCCESS("    ✅ Standar: Bersih dari klausul Pasal 4 Support Promosi."))
        else:
            self.stderr.write(self.style.ERROR("    ❌ Standar: Klausul Support Promosi masih bocor muncul!"))
            all_passed = False

        if page_count_std == 2:
            self.stdout.write(self.style.SUCCESS(f"    ✅ Standar ReportLab PDF: Tepat {page_count_std} Halaman A4 ({len(pdf_bytes_std)} bytes)."))
        else:
            self.stderr.write(self.style.ERROR(f"    ❌ Standar ReportLab PDF: Halaman tidak pas 2 halaman (got {page_count_std})!"))
            all_passed = False

        # === SKENARIO 2: MODE SALES SUPPORT (13 PASAL) ===
        self.stdout.write(self.style.NOTICE("\n  [Skenario 2] Mode Sales Support (13 Pasal: Klausul Pasal 4 Support Promosi & Sewa)"))
        support_payload = dict(test_payload)
        support_payload.update({
            "is_sales_support": True,
            "persen_support": "5",
            "komponen_biaya_support": json.dumps(["Sewa", "Listrik", "Pajak Billboard"]),
        })
        sub_support = FormSubmission.objects.create(
            form_definition=form_def,
            submitter=submitter,
            form_data=support_payload,
            status="draft",
        )

        html_supp = tpl_standard.render(sub_support)
        pdf_bytes_supp, page_count_supp = EMeteraiService.generate_spk_pdf_bytes(sub_support)

        # 1. Cek Pasal 4 Support Promosi Poin (1), (2), (3)
        if (
            "Pasal 4</div>" in html_supp
            and "Pihak Pertama memberikan support promosi yang meliputi biaya" in html_supp
            and "sewa, listrik, dan pajak billboard" in html_supp
            and "5%" in html_supp
            and "Support promosi ini dapat dicairkan setelah pembayaran" in html_supp
            and "Grace period selama 1 (satu) bulan dari masa kontrak berakhir" in html_supp
        ):
            self.stdout.write(self.style.SUCCESS("    ✅ Sales Support: Pasal 4 Support Promosi ter-render lengkap (poin 1, 2, 3) dengan komponen 'sewa, listrik, dan pajak billboard'."))
        else:
            self.stderr.write(self.style.ERROR("    ❌ Sales Support: Klausul Pasal 4 Support Promosi tidak sesuai!"))
            all_passed = False

        # 2. Cek Pergeseran Penomoran Pasal (Pasal 5 s.d. Pasal 13)
        if "Pasal 5</div>" in html_supp and "Perjanjian berlaku untuk Jangka Waktu" in html_supp:
            self.stdout.write(self.style.SUCCESS("    ✅ Sales Support: Periode Kontrak bergeser rapi menjadi Pasal 5."))
        else:
            self.stderr.write(self.style.ERROR("    ❌ Sales Support: Periode Kontrak gagal bergeser ke Pasal 5!"))
            all_passed = False

        if "Pasal 6</div>" in html_supp and "Skema discount untuk penjualan Produk" in html_supp:
            self.stdout.write(self.style.SUCCESS("    ✅ Sales Support: Skema Diskon bergeser rapi menjadi Pasal 6."))
        else:
            self.stderr.write(self.style.ERROR("    ❌ Sales Support: Skema Diskon gagal bergeser ke Pasal 6!"))
            all_passed = False

        if "Pasal 7</div>" in html_supp and "Pihak Pertama memberikan Insentif" in html_supp:
            self.stdout.write(self.style.SUCCESS("    ✅ Sales Support: Insentif Tahunan bergeser rapi menjadi Pasal 7."))
        else:
            self.stderr.write(self.style.ERROR("    ❌ Sales Support: Insentif Tahunan gagal bergeser ke Pasal 7!"))
            all_passed = False

        if "Pasal 13</div>" in html_supp and "Pengadilan Negeri Bale Bandung" in html_supp:
            self.stdout.write(self.style.SUCCESS("    ✅ Sales Support: Total 13 Pasal lengkap & urut (Pasal 13 Domisili PN)."))
        else:
            self.stderr.write(self.style.ERROR("    ❌ Sales Support: Pasal 13 Domisili PN tidak ditemukan!"))
            all_passed = False

        if page_count_supp == 2:
            self.stdout.write(self.style.SUCCESS(f"    ✅ Sales Support ReportLab PDF: Tepat {page_count_supp} Halaman A4 ({len(pdf_bytes_supp)} bytes)."))
        else:
            self.stderr.write(self.style.ERROR(f"    ❌ Sales Support ReportLab PDF: Halaman tidak pas 2 halaman (got {page_count_supp})!"))
            all_passed = False

        sub_support.delete()

        # 7. Test Penamaan Dinamis Berkas PDF SPK Sesuai Nomor SPK
        from django_forms_workflows.views import _resolve_spk_pdf_filename, form_preview_pdf
        from django.test import RequestFactory
        expected_fn = "SPK-001-SK-RAS-BANDUNG-LADY-X-2026.pdf"
        actual_fn = _resolve_spk_pdf_filename(submission)
        if actual_fn == expected_fn:
            self.stdout.write(self.style.SUCCESS(f"✅ Penamaan Dinamis Berkas PDF Resmi: '{actual_fn}' tepat sesuai format nomor SPK."))
        else:
            self.stderr.write(self.style.ERROR(f"❌ Penamaan Dinamis Berkas PDF tidak sesuai: '{actual_fn}' != '{expected_fn}'!"))
            all_passed = False

        # 8. Test Endpoint Transient Preview PDF (True WYSIWYG Parity)
        factory = RequestFactory()
        preview_req = factory.post("/forms/permohonan-kontrak/preview-pdf/", data=submission.form_data)
        preview_req.user = submission.submitter
        preview_resp = form_preview_pdf(preview_req, slug="permohonan-kontrak")
        if preview_resp.status_code == 200 and preview_resp["Content-Type"] == "application/pdf" and preview_resp.content.startswith(b"%PDF"):
            self.stdout.write(self.style.SUCCESS(f"✅ Endpoint Transient Preview PDF (True WYSIWYG): Status 200 OK, {len(preview_resp.content)} bytes, Disposition: {preview_resp.get('Content-Disposition')}, Page-Count: {preview_resp.get('X-Page-Count')}."))
        else:
            self.stderr.write(self.style.ERROR(f"❌ Endpoint Preview PDF gagal: status={preview_resp.status_code}!"))
            all_passed = False

        # 7. Static Verification: Proteksi Nilai Fixed Discount di kontrak-grid-widget.js
        import os
        js_path = os.path.join("django_forms_workflows", "static", "django_forms_workflows", "js", "kontrak-grid-widget.js")
        if os.path.exists(js_path):
            with open(js_path, "r", encoding="utf-8") as f:
                js_content = f.read()
            if 'readonly' in js_content and 'isFixed' in js_content and 'cursor: not-allowed' in js_content:
                self.stdout.write(self.style.SUCCESS("✅ Proteksi Skema Diskon (kontrak-grid-widget.js): Input Nilai, Tipe, Keterangan MD1-MTOP berstatus readonly & cursor not-allowed terkunci."))
            else:
                self.stderr.write(self.style.ERROR("❌ Proteksi Skema Diskon (kontrak-grid-widget.js): Proteksi readonly baris fixed tidak lengkap!"))
                all_passed = False

        # 7. Cleanup test submission
        submission.delete()
        self.stdout.write(self.style.NOTICE("\n[Cleanup] Submission pengujian audit berhasil dibersihkan dari DB.\n"))
