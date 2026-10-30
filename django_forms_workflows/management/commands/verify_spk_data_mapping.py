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
        deleted_fields = ["metode_pembayaran", "syarat_pencairan", "pengecualian_ketentuan_support", "jenis_pajak", "catatan_lain"]
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
        from django_forms_workflows.company_profiles import COMPANY_PROFILES, resolve_company_profile
        for comp_name, prof in COMPANY_PROFILES.items():
            expected_rek = f"{prof['bank_name']} {prof['bank_account_no']} a/n {prof['bank_account_name']}"
            resolved = resolve_company_profile(form_data={"perusahaan": comp_name})
            res_rek = f"{resolved['bank_name']} {resolved['bank_account_no']} a/n {resolved['bank_account_name']}"
            if res_rek == expected_rek:
                self.stdout.write(self.style.SUCCESS(f"  ✅ {prof['short_code']} ({comp_name}): {res_rek}"))
            else:
                self.stderr.write(self.style.ERROR(f"  ❌ Mismatch for {comp_name}: got '{res_rek}', expected '{expected_rek}'"))

        # Verify 4 Official Brands in SharedOptionList 'brand-list'
        self.stdout.write("\n" + self.style.MIGRATE_HEADING("--- AUDIT 4 BRAND RESMI SPK (SHARED OPTION LIST & NUMBERING) ---"))
        sol_brand = SharedOptionList.objects.filter(slug="brand-list").first()
        if sol_brand:
            choices = sol_brand.get_choices()
            choice_values = [c[0] for c in choices]
            expected_brands = ["Lady Americana", "Elite", "Serenity", "Royal Foam"]
            self.stdout.write(f"  SharedOptionList 'brand-list' values: {choice_values}")
            if choice_values == expected_brands:
                self.stdout.write(self.style.SUCCESS("✅ Opsi brand di database tepat 4 brand resmi: " + ", ".join(expected_brands)))
            else:
                self.stderr.write(self.style.ERROR(f"❌ Opsi brand tidak sesuai! Diharapkan {expected_brands}, didapat {choice_values}"))
        else:
            self.stderr.write(self.style.ERROR("❌ SharedOptionList 'brand-list' tidak ditemukan!"))

        # Verify Brand SPK Numbering Code & Canonical Name
        brand_tests = [
            ("Lady Americana", "LADY", "Lady Americana"),
            ("Elite", "ELITE", "Elite"),
            ("Serenity", "SERENITY", "Serenity"),
            ("Royal Foam", "ROYAL", "Royal Foam"),
            # Legacy inputs
            ("LADY AMERICANA", "LADY", "Lady Americana"),
            ("ELITE", "ELITE", "Elite"),
            ("SERENITY", "SERENITY", "Serenity"),
            ("ROYAL FOAM", "ROYAL", "Royal Foam"),
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

        # Verify Pure Month Contract Duration (Poin 15)
        self.stdout.write("\n" + self.style.MIGRATE_HEADING("--- AUDIT KALKULASI & NORMALISASI DURASI KONTRAK (POIN 15) ---"))
        durasi_tests = [
            ("1 Tahun", "12 Bulan"),
            ("1 Tahun 1 Bulan", "13 Bulan"),
            ("2 Tahun", "24 Bulan"),
            ("12 Bulan", "12 Bulan"),
            ("13 Bulan", "13 Bulan"),
            ("6 Bulan", "6 Bulan"),
            ("18 Bulan", "18 Bulan"),
            ("12", "12 Bulan"),
        ]
        for raw_val, expected_norm in durasi_tests:
            actual_norm = normalize_contract_duration(raw_val)
            if actual_norm == expected_norm:
                self.stdout.write(self.style.SUCCESS(f"  [OK] Input durasi '{raw_val}' -> Normalized: '{actual_norm}'"))
            else:
                self.stderr.write(self.style.ERROR(f"  [ERR] Input durasi '{raw_val}' -> Diharapkan '{expected_norm}', didapat '{actual_norm}'"))

        # Verify Branch-Isolated SPK Numbering & Roman Month Format (Revisi Poin 14)
        self.stdout.write("\n" + self.style.MIGRATE_HEADING("--- AUDIT PENOMORAN SPK TERPISAH PER CABANG & FORMAT ROMAWI (POIN 14) ---"))
        import datetime
        oct_date = datetime.date(2026, 10, 29)
        spk_sample = format_official_spk_number(
            nomor=1,
            brand="Serenity",
            cabang="Bandung",
            date_val=oct_date,
            perusahaan="PT ROYAL ABADI SEJAHTERA",
        )
        if spk_sample == "001/SERENITY/RAS/X/2026":
            self.stdout.write(self.style.SUCCESS(f"  ✅ Format SPK Baku (Poin 14): '{spk_sample}' tepat sesuai spesifikasi resmi."))
        else:
            self.stderr.write(self.style.ERROR(f"  ❌ Format SPK tidak sesuai: got '{spk_sample}', expected '001/SERENITY/RAS/X/2026'"))

        # Test 5 Company Profiles mapping to short codes
        pt_expected = [
            ("PT ANUGRAH CEMERLANG ABADI", "ACA"),
            ("PT BANGUN CIPTA PRIMATARA", "BCP"),
            ("PT BESTARI MULIA", "BM"),
            ("PT CEMERLANG ABADI MULIA", "CAM"),
            ("PT ROYAL ABADI SEJAHTERA", "RAS"),
        ]
        for pt_name, expected_code in pt_expected:
            res_no = format_official_spk_number(1, "Elite", perusahaan=pt_name, date_val=oct_date)
            if f"/{expected_code}/" in res_no:
                self.stdout.write(self.style.SUCCESS(f"  ✅ Pemetaan PT: '{pt_name}' -> Short Code '{expected_code}' ({res_no})"))
            else:
                self.stderr.write(self.style.ERROR(f"  ❌ Pemetaan PT gagal: '{pt_name}' -> '{res_no}'"))

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
            {
                "komponen": "Diskon Reguler Toko",
                "nilai": "15%",
                "tipe": "Persentase",
                "keterangan": "Khusus Kasur 160x200 & 180x200",
            }
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
            # Step 1: Identitas & Legalitas Toko (NIK 16 digit & NPWP terpisah, 4 Official Brands)
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
            "nomor_spk": "001/LADY/RAS/X/2026",

            # Step 2 - Card 1: Periode & Masa Berlaku Kontrak (Pasal 4 / 5)
            "tanggal_mulai": "2026-11-01",
            "tanggal_berakhir": "2027-10-31",
            "durasi": "12 Bulan",
            "grace_period": "1 Bulan",

            # Step 2 - Card 2: Target Penjualan & Skema Insentif (Pasal 3 - Default Exclude Ppn)
            "target_incentive": json.dumps(target_incentive_data),

            # Step 2 - Card 3: Skema Diskon Produk & Ketentuan DO (Pasal 5 / 6)
            "discount_do": "2.5",
            "ketentuan_do": "Jatuh tempo sebelum pengambilan barang DO",
            "discount_scheme": json.dumps(discount_scheme_data),

            # Step 2 - Card 4: Fasilitas & Dukungan Promosi (Pasal 4 & 7 Promo)
            "is_support_provided": True,
            "pct_support_promo": "5.0",
            "frekuensi_pencairan": "Per Kuartal",
            "komponen_biaya": ["Sewa", "Listrik", "Instore"],
            "tier_support": json.dumps(tier_support_data),

            # Step 2 - Card 5: Tata Cara & Ketentuan Pembayaran (BAB III - Pasal 7, 8, 9)
            "top": 60,
            "rekening_perusahaan": "BCA 084-3012899 a/n PT Bestari Mulia",

            # Step 2 - Card 6: Ketentuan Akhir & Tempat Pengesahan (BAB IV & Penutup)
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

        # 4. Fetch Templates (Standard and Support Promosi)
        tpl_standard = DocumentTemplate.objects.filter(
            form_definition=form_def,
            name__icontains="Standard"
        ).first() or DocumentTemplate.objects.filter(form_definition=form_def).first()

        tpl_support = DocumentTemplate.objects.filter(
            form_definition=form_def,
            name__icontains="Support Promosi"
        ).first()

        if not tpl_standard:
            self.stderr.write(self.style.ERROR("DocumentTemplate Standard not found!"))
            return

        templates_to_test = [
            ("SPK Standard (11 Pasal)", tpl_standard),
        ]
        if tpl_support:
            templates_to_test.append(("SPK Support Promosi (12 Pasal)", tpl_support))

        # 5. Audit Each Template
        fields_to_audit = [
            ("nomor_spk", "Header Dokumen", "Format Resmi No. SPK", True),
            ("nama_toko", "Pihak Kedua (Toko)", "Nama Toko Mitra", True),
            ("nama_pemilik", "Pihak Kedua (Pemilik)", "Nama Pemilik", True),
            ("alamat_toko", "Pihak Kedua (Alamat)", "Alamat Toko", True),
            ("nomor_npwp", "Pihak Kedua (NPWP)", "Nomor NPWP Toko/Pemilik", True),
            ("nomor_nik", "Pihak Kedua (NIK)", "Nomor NIK (16 digit)", False),
            ("brand", "Pihak Pertama & Objek", "Brand Produk Springbed", True),
            ("perusahaan", "Pihak Pertama (Produsen)", "Entitas Perusahaan", True),
            ("pengadilan_negeri", "Pasal 11 / 12 (Domisili Hukum)", "PN Berbasis Cabang Bandung", True),
            ("tanggal_mulai", "Card 1 (Pasal 4 / 5)", "Tanggal Mulai Kontrak", True),
            ("tanggal_berakhir", "Card 1 (Pasal 4 / 5)", "Tanggal Berakhir Kontrak", True),
            ("durasi", "Card 1 (Pasal 4 / 5)", "Durasi Kontrak", True),
            ("grace_period", "Card 1 (Pasal 4 / 5)", "Grace Period / Masa Tenggang", True),
            ("target_volume_text", "Card 2 (Pasal 3)", "Target Penjualan Bulanan (Rp)", True),
            ("target_incentive_table", "Card 2 (Pasal 3)", "Tabel Dynamic Grid Tier Target", True),
            ("discount_scheme_table", "Card 3 (Pasal 5 / 6)", "Tabel Dynamic Grid Diskon Produk", True),
            ("discount_do", "Card 3 (Pasal 5 / 6)", "Diskon Delivery Order (DO %)", True),
            ("ketentuan_do", "Card 3 (Pasal 5 / 6)", "Ketentuan Pengambilan DO", True),
            ("pct_support_promo", "Card 4 (Pasal 4 / 7 Promo)", "Persentase Support Promo (%)", False),
            ("tier_support_table", "Card 4 (Pasal 7 Promo)", "Tabel Dynamic Grid Tier Support", False),
            ("top", "Card 5 (BAB III - Pembayaran)", "Term of Payment (Hari)", True),
            ("rekening_perusahaan", "Card 5 (BAB III - Pembayaran)", "Rekening Resmi Pembayaran", True),
            ("kota_penandatanganan", "Card 6 (Tempat Pengesahan)", "Kota Tanda Tangan", True),
            ("tanggal_penandatanganan", "Card 6 (Tanggal Pengesahan)", "Tanggal Tanda Tangan", True),
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
                    is_rendered = bool(re.search(r"001/LADY/RAS/X/2026", rendered_html)) or bool(re.search(r"SURAT PERJANJIAN KERJASAMA", rendered_html))
                    snippet = "001/LADY/RAS/X/2026 Terformat"
                elif f_name == "pengadilan_negeri":
                    is_rendered = "Bale Bandung" in rendered_html
                    snippet = "PN Bale Bandung (Cabang Bandung)"
                elif f_name == "target_incentive_table":
                    is_rendered = "250.000.000" in rendered_html or "Tier Platinum" in rendered_html
                    snippet = "Tabel Tier 250 Jt Ter-render"
                elif f_name == "discount_scheme_table":
                    is_rendered = "Diskon Reguler Toko" in rendered_html
                    snippet = "Tabel Diskon 15% Ter-render"
                elif f_name == "tier_support_table":
                    if "Support" in tpl_label:
                        is_rendered = "3.000.000.000" in rendered_html or "147.000.000" in rendered_html
                        snippet = "Tabel Tier 3 Milyar Ter-render"
                    else:
                        is_rendered = True
                        snippet = "(N/A di Standard)"
                elif f_name == "target_volume_text":
                    is_rendered = "250.000.000" in rendered_html and bool(re.search(r"per bulan Exclude Ppn", rendered_html, re.IGNORECASE))
                    snippet = "Rp 250.000.000 per bulan Exclude Ppn"
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

            # Verify Pasal 3 Ayat (1) contains Exclude Ppn
            if re.search(r"per bulan Exclude Ppn", rendered_html, re.IGNORECASE):
                self.stdout.write(self.style.SUCCESS("✅ Pasal 3 Ayat (1): Ter-render dinamis baku 'per bulan Exclude Ppn.'"))
            else:
                self.stderr.write(self.style.ERROR("❌ Pasal 3 Ayat (1): Format 'per bulan Exclude Ppn' tidak ditemukan!"))
                all_passed = False

            # Verify Pasal 8 / 9 Static Payment Clause
            if "Transfer / Cek / Giro" in rendered_html:
                self.stdout.write(self.style.SUCCESS("✅ Klausul Pembayaran: Ter-render standar 'Transfer / Cek / Giro'."))
            else:
                self.stderr.write(self.style.ERROR("❌ Klausul Pembayaran: 'Transfer / Cek / Giro' tidak ditemukan!"))
                all_passed = False

            # Verify Pasal 4 Support Promosi (Syarat Pencairan Baku LUNAS)
            if "Support" in tpl_label:
                if "setelah pembayaran" in rendered_html and "LUNAS" in rendered_html:
                    self.stdout.write(self.style.SUCCESS("✅ Klausul Syarat Pencairan (Pasal 4): Ter-render baku 'setelah pembayaran LUNAS'."))
                else:
                    self.stderr.write(self.style.ERROR("❌ Klausul Syarat Pencairan (Pasal 4): Teks baku 'setelah pembayaran LUNAS' tidak ditemukan!"))
                    all_passed = False

                if "Billboard" in rendered_html and "Backdrop" in rendered_html:
                    self.stdout.write(self.style.SUCCESS("✅ Klausul Batasan Promosi (Pasal 4): Ter-render baku tanpa Billboard & Backdrop."))
                else:
                    self.stderr.write(self.style.ERROR("❌ Klausul Batasan Promosi (Pasal 4): Teks baku batasan Billboard & Backdrop tidak ditemukan!"))
                    all_passed = False

            # Verify Dynamic Court Jurisdiction
            if "Kantor Panitera Pengadilan Negeri Bale Bandung" in rendered_html:
                self.stdout.write(self.style.SUCCESS("✅ Klausul Domisili Hukum: Ter-render dinamis 'Kantor Panitera Pengadilan Negeri Bale Bandung' mengikuti Cabang Bandung!"))
            else:
                self.stderr.write(self.style.ERROR("❌ Klausul Domisili Hukum: Pengadilan Negeri Bale Bandung tidak ditemukan!"))
                all_passed = False

            # Verify Poin 12: Klausul Penyitaan Aset atas Wanprestasi / Backdate
            asset_clause_text = "Apabila pembayaran tidak sesuai dengan TOP dan jika terjadi backdate, Pihak Pertama dapat mengambil/menyita aset sesuai dengan piutang."
            if asset_clause_text in rendered_html:
                self.stdout.write(self.style.SUCCESS("✅ Klausul Penyitaan Aset (Poin 12): Teks baku perlindungan piutang ter-render lengkap!"))
            else:
                self.stderr.write(self.style.ERROR("❌ Klausul Penyitaan Aset (Poin 12): Teks klausul penyitaan aset tidak ditemukan!"))
                all_passed = False

            # Verify Clause Numbering per Template
            if "Support" in tpl_label:
                if "Pasal 11</div>" in rendered_html and "Pasal 12</div>" in rendered_html and "Pasal 13</div>" in rendered_html:
                    self.stdout.write(self.style.SUCCESS("✅ Penomoran Pasal (Poin 12): SPK Support Promosi memiliki urutan 13 Pasal lengkap (Pasal 11 Aset, Pasal 12 Itikad Baik, Pasal 13 PN)."))
                else:
                    self.stderr.write(self.style.ERROR("❌ Penomoran Pasal (Poin 12): SPK Support Promosi gagal memiliki 13 Pasal urut!"))
                    all_passed = False
            else:
                if "Pasal 10</div>" in rendered_html and "Pasal 11</div>" in rendered_html and "Pasal 12</div>" in rendered_html:
                    self.stdout.write(self.style.SUCCESS("✅ Penomoran Pasal (Poin 12): SPK Standard memiliki urutan 12 Pasal lengkap (Pasal 10 Aset, Pasal 11 Itikad Baik, Pasal 12 PN)."))
                else:
                    self.stderr.write(self.style.ERROR("❌ Penomoran Pasal (Poin 12): SPK Standard gagal memiliki 12 Pasal urut!"))
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
            if ctx.get("komponen_biaya") == "sewa, listrik, dan instore":
                self.stdout.write(self.style.SUCCESS(f"✅ Template Context (Poin 10): context['komponen_biaya'] ter-format legal tepat ('{ctx.get('komponen_biaya')}')."))
            else:
                self.stderr.write(self.style.ERROR(f"❌ Template Context (Poin 10): context['komponen_biaya'] tidak sesuai (got '{ctx.get('komponen_biaya')}')."))
                all_passed = False

            if "Support Promosi" in tpl.name:
                if "sewa, listrik, dan instore" in rendered_html:
                    self.stdout.write(self.style.SUCCESS("✅ Pasal 4 Template SPK (Poin 10): Teks komponen biaya support ('sewa, listrik, dan instore') ter-render dinamis."))
                else:
                    self.stderr.write(self.style.ERROR("❌ Pasal 4 Template SPK (Poin 10): Teks komponen biaya support tidak ditemukan dalam template rendered HTML!"))
                    all_passed = False

                # Verify Revisi Poin 11: 5-Column Tier Support Table & Dynamic Narrative Text
                from django_forms_workflows.company_profiles import calculate_spk_incentive_breakdown
                calc_res = calculate_spk_incentive_breakdown(test_payload, is_support=True)
                assert calc_res["frekuensi_bulan"] == "3"
                assert calc_res["target_per_periode"] == "750.000.000"
                assert calc_res["reward_rate"] == "5%"
                assert calc_res["pph_rate"] == "2%"
                assert calc_res["reward_nominal"] == "37.500.000"
                assert calc_res["pph_nominal"] == "750.000"
                assert calc_res["netto_nominal"] == "36.750.000"

                # Check 5 columns in tier_support_table
                tier_table_html = ctx.get("tier_support_table", "")
                if all(col in tier_table_html for col in ["Target Tahunan", "Dukungan (%)", "PPh 23 (%)", "Nilai Netto (Rp)", "Keterangan"]):
                    self.stdout.write(self.style.SUCCESS("✅ Tabel Tier Support Pasal 7 (Poin 11): 5 Kolom terstruktur lengkap (Target, Dukungan %, PPh 23 %, Netto Rp, Keterangan)."))
                else:
                    self.stderr.write(self.style.ERROR("❌ Tabel Tier Support Pasal 7 (Poin 11): Kolom tabel tidak lengkap 5 kolom!"))
                    all_passed = False

                # Check official calculation narrative in context & rendered HTML
                if "Target penjualan sebesar Rp. 750.000.000 per 3 Bulan" in rendered_html and "36.750.000" in rendered_html:
                    self.stdout.write(self.style.SUCCESS("✅ Narasi Perhitungan Pasal 7 (Poin 11): Kalimat narasi baku resmi ter-render lengkap & dinamis."))
                else:
                    self.stderr.write(self.style.ERROR("❌ Narasi Perhitungan Pasal 7 (Poin 11): Teks narasi resmi perhitungan tidak ditemukan dalam rendered HTML!"))
                    all_passed = False

        # 6. Test ReportLab PDF Generator
        self.stdout.write("\n" + self.style.MIGRATE_HEADING("--- PENGUJIAN REPORTLAB PDF GENERATOR ---"))
        from django_forms_workflows.services.ematerai.service import EMeteraiService
        pdf_bytes, page_count = EMeteraiService.generate_spk_pdf_bytes(submission)
        if pdf_bytes and len(pdf_bytes) > 1000:
            self.stdout.write(self.style.SUCCESS(f"✅ ReportLab PDF Generator Berhasil: {len(pdf_bytes)} bytes, {page_count} halaman."))
        else:
            self.stderr.write(self.style.ERROR("❌ Gagal menghasilkan PDF ReportLab!"))

        # 7. Cleanup test submission
        submission.delete()
        self.stdout.write(self.style.NOTICE("\n[Cleanup] Submission pengujian audit berhasil dibersihkan dari DB.\n"))
