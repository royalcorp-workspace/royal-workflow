"""
High-level Orchestrator Service for e-Meterai single stamping.
Generates in-memory SPK PDF, calculates last-page coordinates, interacts with provider,
saves the stamped PDF to storage, and updates StampedContractDocument metadata.
"""

from __future__ import annotations

import io
import logging
import os
import threading
from typing import Any, Dict, Optional, Tuple

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone

from .base import BaseMeteraiProvider, StampingResult, UploadResult
from django_forms_workflows.company_profiles import (
    format_komponen_biaya_legal_text,
    calculate_spk_incentive_breakdown,
)

from reportlab.pdfgen import canvas
from reportlab.lib import colors

logger = logging.getLogger(__name__)


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass dynamic canvas:
    1. Collects page states on first pass.
    2. In save(), calculates total pages and renders dynamic footers ('Halaman X dari Y').
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        # Footer: Halaman X dari Y on bottom right
        self.setFont("Times-Roman", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        page_text = f"Halaman {self._pageNumber} dari {page_count}"
        self.drawRightString(595.27 - 36, 15, page_text)
        self.restoreState()


class EMeteraiService:
    """
    High-level orchestrator service for e-Meterai stamping workflow.
    """

    @classmethod
    def get_provider(cls, provider_name: Optional[str] = None) -> BaseMeteraiProvider:
        from . import get_meterai_provider
        return get_meterai_provider(provider_name)

    @classmethod
    def get_stamping_coordinates(cls, pdf_bytes: Optional[bytes] = None) -> Tuple[float, float, float, float]:
        """
        Return (llx, lly, urx, ury) in standard PDF points.
        Default A4 placement centered symmetrically between PIHAK PERTAMA and PIHAK KEDUA:
        A4 width: 595.28 pt -> Center: 297.64 pt.
        e-Meterai dimensions: 54.0pt width x 52.0pt height.
        llx = 297.64 - 27.0 = 270.64
        urx = 297.64 + 27.0 = 324.64
        Default signature row height: lly = 119.0, ury = 171.0.

        If pdf_bytes is provided, dynamically resolves the exact Y coordinate
        of the e-meterai table slot from the PDF stream to ensure pixel-perfect
        alignment regardless of page content height / grid table variations.
        """
        llx = float(getattr(settings, "EMATERAI_POS_LLX", 270.64))
        lly = float(getattr(settings, "EMATERAI_POS_LLY", 119.0))
        urx = float(getattr(settings, "EMATERAI_POS_URX", 324.64))
        ury = float(getattr(settings, "EMATERAI_POS_URY", 171.0))

        if pdf_bytes:
            try:
                import io
                import re
                from pypdf import PdfReader
                r = PdfReader(io.BytesIO(pdf_bytes))
                p_last = r.pages[-1]
                content = p_last.get_contents().get_data().decode('latin-1')
                # Look for anchor or table transform in stream
                idx_slot = content.find('1 0 0 1 215')
                if idx_slot != -1:
                    prefix = content[:idx_slot]
                    m = re.findall(r'1 0 0 1 36\.1378 ([\d\.]+) cm', prefix)
                    if m:
                        y_table = float(m[-1])
                        dynamic_lly = round(y_table + 26.0, 1)
                        dynamic_ury = round(dynamic_lly + 52.0, 1)
                        return (llx, dynamic_lly, urx, dynamic_ury)
            except Exception as e:
                logger.warning("Could not dynamically resolve stamping coordinates: %s", e)

        return (llx, lly, urx, ury)

    @classmethod
    def generate_spk_pdf_bytes(cls, submission, for_stamping: bool = False) -> Tuple[bytes, int]:
        """
        Generate in-memory PDF bytes of the SPK contract and return (pdf_bytes, page_count).
        First attempts WeasyPrint; if WeasyPrint has OS library constraints, falls back
        to ReportLab PDF generation.
        """
        from django_forms_workflows.models import DocumentTemplate

        form_def = submission.form_definition
        if form_def.slug == "permohonan-kontrak":
            from django_forms_workflows.company_profiles import resolve_spk_document_template
            custom_template = resolve_spk_document_template(form_def, submission=submission)
        else:
            custom_template = DocumentTemplate.objects.filter(
                form_definition=form_def, is_default=True, is_active=True
            ).first()

        html_content = ""
        if custom_template:
            html_content = custom_template.render(submission)
        else:
            html_content = f"<h1>Surat Perjanjian Kerjasama #{submission.id}</h1><p>Form: {form_def.name}</p>"

        # 1. Try WeasyPrint
        try:
            from weasyprint import HTML
            pdf_bytes = HTML(string=html_content).write_pdf()
            page_count = cls._get_pdf_page_count(pdf_bytes)
            return pdf_bytes, page_count
        except Exception as wp_exc:
            logger.warning(
                "WeasyPrint unavailable (%s). Falling back to ReportLab engine for submission #%s",
                wp_exc,
                submission.id,
            )

        # 2. Fallback to ReportLab pure python generator
        pdf_bytes = cls._generate_reportlab_spk_pdf(submission, for_stamping=for_stamping)
        page_count = cls._get_pdf_page_count(pdf_bytes)
        return pdf_bytes, page_count

    @classmethod
    def _get_pdf_page_count(cls, pdf_bytes: bytes) -> int:
        """Parse total page count from PDF bytes using pypdf."""
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(pdf_bytes))
            return len(reader.pages) or 1
        except Exception as exc:
            logger.warning("Could not parse page count via pypdf (%s), defaulting to 1", exc)
            return 1

    @classmethod
    def _generate_reportlab_spk_pdf(cls, submission, for_stamping: bool = False) -> bytes:
        """
        High-fidelity corporate ReportLab generator for SPK document.
        Produces an official multi-page A4 PDF matching DocumentTemplate ID 1:
        - Kop Surat resmi dan Nomor SPK cabang
        - Data Para Pihak (Pihak Pertama & Kedua lengkap)
        - Bab I (Penunjukan & Periode), Bab II (Target & Insentif), Bab III (Display & Promo)
        - Bab IV (Tabel Tier Support), Bab V (TOP, Diskon DO, Pajak PPh)
        - Render tabel dinamis dari payload submission (target_incentive, discount_scheme, tier_support)
        - Blok tanda tangan proporsional 3 kolom dengan slot e-meterai presisi [45, 75, 145, 175]
        """
        import base64
        import json
        import re
        import os
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle,
            KeepTogether,
            Image as RLImage,
            HRFlowable,
            PageBreak,
        )
        from reportlab.lib import colors
        from django.utils import timezone
        from django_forms_workflows.company_profiles import (
            resolve_company_profile,
            get_company_logo_abs_path,
            format_official_spk_number,
            format_date_indonesia,
        )

        form_data = submission.form_data or {}
        comp_prof = resolve_company_profile(form_data=form_data, submission=submission, user=submission.submitter)
        perusahaan = comp_prof["display_name"]

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=26,
            bottomMargin=26,
            title=f"SPK_Submission_{submission.id}",
            author=perusahaan or "PT Royal Abadi Sejahtera",
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "SPKTitle",
            parent=styles["Heading1"],
            fontName="Times-Bold",
            fontSize=13,
            leading=16,
            alignment=1,  # Center
            textColor=colors.HexColor("#111827"),
            spaceAfter=2,
        )
        subtitle_style = ParagraphStyle(
            "SPKSubtitle",
            parent=styles["Normal"],
            fontName="Times-Bold",
            fontSize=10.5,
            leading=13,
            alignment=1,  # Center
            textColor=colors.HexColor("#111827"),
            spaceAfter=10,
        )
        bab_heading_style = ParagraphStyle(
            "SPKBabHeading",
            parent=styles["Normal"],
            fontName="Times-Bold",
            fontSize=9.5,
            leading=11.5,
            alignment=1,  # Center
            textColor=colors.HexColor("#111827"),
            spaceBefore=6,
            spaceAfter=2,
        )
        pasal_heading_style = ParagraphStyle(
            "SPKPasalHeading",
            parent=styles["Normal"],
            fontName="Times-Bold",
            fontSize=9.5,
            leading=11.5,
            alignment=1,  # Center
            textColor=colors.HexColor("#111827"),
            spaceBefore=3.5,
            spaceAfter=1.5,
        )
        body_style = ParagraphStyle(
            "SPKBody",
            parent=styles["Normal"],
            fontName="Times-Roman",
            fontSize=9,
            leading=12,
            alignment=4,  # Justified
            textColor=colors.HexColor("#111827"),
            spaceAfter=2.5,
        )
        body_center_style = ParagraphStyle(
            "SPKBodyCenter",
            parent=styles["Normal"],
            fontName="Times-Roman",
            fontSize=9,
            leading=12,
            alignment=1,  # Center
            textColor=colors.HexColor("#111827"),
            spaceAfter=2.5,
        )
        th_style = ParagraphStyle(
            "SPKTableHeader",
            parent=styles["Normal"],
            fontName="Times-Bold",
            fontSize=8,
            leading=10,
            alignment=1,  # Center
            textColor=colors.HexColor("#111827"),
        )
        cell_style = ParagraphStyle(
            "SPKCell",
            parent=styles["Normal"],
            fontName="Times-Roman",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#111827"),
        )
        cell_bold_style = ParagraphStyle(
            "SPKCellBold",
            parent=styles["Normal"],
            fontName="Times-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#111827"),
        )
        cell_center_style = ParagraphStyle(
            "SPKCellCenter",
            parent=styles["Normal"],
            fontName="Times-Roman",
            fontSize=8,
            leading=10,
            alignment=1,  # Center
            textColor=colors.HexColor("#111827"),
        )

        def format_rupiah(val):
            if val is None or val == "":
                return "-"
            try:
                cleaned = re.sub(r"[^\d.-]", "", str(val))
                if cleaned:
                    num = float(cleaned)
                    return f"Rp {int(round(num)):,}".replace(",", ".")
            except Exception:
                pass
            return str(val)

        def parse_grid_data(raw):
            if not raw:
                return []
            if isinstance(raw, list):
                return [r for r in raw if isinstance(r, dict)]
            if isinstance(raw, str) and raw.strip().startswith("[") and raw.strip().endswith("]"):
                try:
                    parsed = json.loads(raw.strip())
                    if isinstance(parsed, list):
                        return [r for r in parsed if isinstance(r, dict)]
                except Exception:
                    pass
            return []

        pihak_1_nama = comp_prof["director_name"]
        pihak_1_jabatan = f"{comp_prof['director_title']} {perusahaan}"
        pihak_1_alamat = comp_prof["factory_address"]
        rekening_bank = comp_prof["bank_name"]
        rekening_no = comp_prof["bank_account_no"]
        rekening_an = comp_prof["bank_account_name"]
        rekening_display = form_data.get("rekening_perusahaan") or f"{rekening_bank} {rekening_no} a/n {rekening_an}"
        domisili_pn = comp_prof["court_jurisdiction"]
        logo_path = get_company_logo_abs_path(company_name=perusahaan, submission=submission, user=submission.submitter)

        nama_toko = form_data.get("nama_toko") or "Mitra Toko"
        nama_pemilik = form_data.get("nama_pemilik") or "Pemilik Toko"
        alamat_toko = form_data.get("alamat_toko") or "-"
        kota_toko = form_data.get("kota") or form_data.get("cabang") or "Bandung"
        no_npwp = form_data.get("nomor_npwp") or "—"
        no_nik = form_data.get("nomor_nik") or form_data.get("nomor_identitas") or "—"
        jenis_pajak = form_data.get("jenis_pajak") or "Exclude PPN"

        brand = form_data.get("brand") or "LADY"
        cabang = form_data.get("cabang") or "TANGERANG"
        tgl_mulai = format_date_indonesia(form_data.get("tanggal_mulai") or "01/10/2026")
        tgl_akhir = format_date_indonesia(form_data.get("tanggal_berakhir") or "30/09/2027")
        durasi = form_data.get("durasi") or "12 Bulan"
        grace_period = form_data.get("grace_period") or "1 Bulan"

        spk_raw = form_data.get("nomor_spk") or ""
        if not spk_raw or "OTOMATIS" in spk_raw.upper() or spk_raw.startswith("SPK-") or "{" in spk_raw or "/" not in spk_raw:
            no_spk = format_official_spk_number(submission.id, brand, cabang, submission.submitted_at or timezone.now(), company_profile=comp_prof, perusahaan=form_data.get("perusahaan"))
        else:
            no_spk = spk_raw

        raw_target = form_data.get("nilai_target")
        target_rp = format_rupiah(raw_target) if raw_target else "-"

        pct_promo = form_data.get("pct_support_promo") or "5"
        top = form_data.get("top") or "30"

        tgl_ttd = format_date_indonesia(form_data.get("tanggal_penandatanganan") or timezone.now().date())
        kota_ttd = form_data.get("kota_penandatanganan") or cabang or "Bandung"

        # Check Support Promosi vs Standard
        has_support = form_data.get("is_support_provided") in (True, "True", "true", "1", 1, "on")

        elements = []

        # Header Logo Flowable Helper (Centered with clean vertical spacing)
        def get_page_header_logo():
            if not logo_path or not os.path.exists(logo_path):
                return []
            try:
                from PIL import Image as PILImage
                with PILImage.open(logo_path) as pil_im:
                    img_w, img_h = pil_im.size
                max_w, max_h = 92.0, 34.0
                aspect = img_w / float(img_h) if img_h else 1.0
                if aspect > (max_w / max_h):
                    fit_w = max_w
                    fit_h = max_w / aspect
                else:
                    fit_h = max_h
                    fit_w = max_h * aspect

                with open(logo_path, "rb") as lf:
                    raw_stream = io.BytesIO(lf.read())
                rl_logo = RLImage(raw_stream, width=fit_w, height=fit_h)
                t_logo = Table([[rl_logo]], colWidths=[523], style=[
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 0),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                    ('TOPPADDING', (0, 0), (-1, -1), 0),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                ])
                return [t_logo, Spacer(1, 6)]
            except Exception as e:
                logger.warning("Failed to construct logo flowable: %s", e)
                return []

        # ==================== HALAMAN 1 ====================
        elements.extend(get_page_header_logo())

        elements.append(Paragraph("SURAT PERJANJIAN KERJASAMA", title_style))
        elements.append(Paragraph(f"<b>{no_spk}</b>", subtitle_style))

        # Preamble
        elements.append(Paragraph("Yang bertanda tangan di bawah ini :", body_style))

        # Identitas Para Pihak Table
        parties_data = [
            [Paragraph("Nama", cell_style), Paragraph(":", cell_center_style), Paragraph(f"<b>{pihak_1_nama}</b>", cell_bold_style)],
            [Paragraph("Jabatan", cell_style), Paragraph(":", cell_center_style), Paragraph(f"<b>{pihak_1_jabatan}</b>", cell_bold_style)],
            [Paragraph("Alamat", cell_style), Paragraph(":", cell_center_style), Paragraph(pihak_1_alamat, cell_style)],
            [Paragraph(f"Selanjutnya disebut sebagai <b>PIHAK PERTAMA</b> selaku Produsen produk Springbed merk <b>“{brand}”</b>", body_style), Paragraph("", cell_style), Paragraph("", cell_style)],
            [Paragraph("Nama", cell_style), Paragraph(":", cell_center_style), Paragraph(f"<b>{nama_pemilik}</b>", cell_bold_style)],
            [Paragraph("Pemilik Tk.", cell_style), Paragraph(":", cell_center_style), Paragraph(f"<b>{nama_toko}</b>", cell_bold_style)],
            [Paragraph("Alamat", cell_style), Paragraph(":", cell_center_style), Paragraph(f"{alamat_toko}, {kota_toko}", cell_style)],
            [Paragraph("NPWP", cell_style), Paragraph(":", cell_center_style), Paragraph(no_npwp, cell_style)],
            [Paragraph("NIK", cell_style), Paragraph(":", cell_center_style), Paragraph(no_nik, cell_style)],
            [Paragraph(f"Selanjutnya disebut sebagai <b>PIHAK KEDUA</b> Dealer produk Springbed merk <b>“{brand}”</b>", body_style), Paragraph("", cell_style), Paragraph("", cell_style)],
        ]
        t_parties = Table(parties_data, colWidths=[90, 12, 421])
        t_parties.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0, colors.transparent),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("SPAN", (0, 3), (2, 3)),
                    ("SPAN", (0, 9), (2, 9)),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 3), (-1, 3), 3),
                    ("BOTTOMPADDING", (0, 9), (-1, 9), 3),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        elements.append(t_parties)

        elements.append(
            Paragraph(
                f"Dalam upaya meningkatkan kerjasama dalam penjualan produk <b>{brand}</b>, kedua belah pihak di atas sepakat untuk "
                f"menandatangani kontrak perjanjian kerja sama dengan mengikuti syarat – syarat dan ketentuan – ketentuan sebagai berikut :",
                body_style,
            )
        )

        # BAB I
        elements.append(Paragraph("<b>BAB I<br/>OBJEK PERJANJIAN</b>", bab_heading_style))
        elements.append(Paragraph("<u><b>Pasal 1</b></u>", pasal_heading_style))
        elements.append(
            Paragraph(
                f"<b>Pihak Pertama</b> menitipkan/menjual kepada <b>Pihak Kedua</b> Produk Springbed dengan merk “ <b>{brand}</b> “ untuk dijual oleh <b>Pihak Kedua</b> "
                f"pada tempat yang telah diberitahukan dan disetujui oleh <b>Pihak Pertama</b> dengan mengacu pada ketentuan Volume dan Harga Penjualan yang telah di sepakati.",
                body_style,
            )
        )
        elements.append(Paragraph("<u><b>Pasal 2</b></u>", pasal_heading_style))
        elements.append(
            Paragraph(
                f"Omzet penjualan {brand} PIHAK KEDUA dihitung berdasarkan harga setelah dikurangi potongan retur, discount dan potongan – potongan lainnya (harga netto), "
                f"berdasarkan price list yang berlaku mulai tanggal 1 Februari 2023 dan mengikuti perubahannya. (Harga tidak mengikat)",
                body_style,
            )
        )

        # BAB II (Pasal 3 & Tabel Target)
        elements.append(Paragraph("<b>BAB II<br/>VOLUME PENJUALAN dan PENGHARGAAN – PERIODE KONTRAK - SKEMA DISCOUNT</b>", bab_heading_style))
        elements.append(Paragraph("<u><b>Pasal 3</b></u>", pasal_heading_style))
        p3_text = (
            f"(1) Para Pihak sepakat bahwa Target Volume Penjualan produk selama jangka waktu perjanjian ini <b>{target_rp}</b> per bulan {jenis_pajak}.<br/>"
            f"(2) Pihak Kedua wajib memenuhi Volume Penjualan yang telah ditentukan dalam perjanjian ini."
        )
        elements.append(Paragraph(p3_text, body_style))

        grid_target = parse_grid_data(form_data.get("target_incentive"))
        target_table_data = [
            [
                Paragraph("Target Bulanan", th_style),
                Paragraph("Ketentuan Pajak", th_style),
                Paragraph("Insentif (%)", th_style),
                Paragraph("Keterangan", th_style),
            ]
        ]
        if grid_target:
            for r in grid_target:
                t_bln = format_rupiah(r.get("target_bulanan"))
                pajak_str = "Exclude PPN"
                inc_val = f"{r.get('incentive_pct', 0)}%"
                ket = r.get("keterangan") or "-"
                target_table_data.append([
                    Paragraph(t_bln, cell_center_style),
                    Paragraph(pajak_str, cell_center_style),
                    Paragraph(inc_val, cell_center_style),
                    Paragraph(ket, cell_center_style),
                ])
        else:
            target_table_data.append([
                Paragraph(target_rp if target_rp != "-" else "Target Bulanan Sesuai Kesepakatan", cell_center_style),
                Paragraph("Exclude PPN", cell_center_style),
                Paragraph("Sesuai Skema", cell_center_style),
                Paragraph("Diverifikasi setiap akhir bulan kalender", cell_style),
            ])
        t_target = Table(target_table_data, colWidths=[130, 95, 80, 218])
        t_target.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )

        # Discount Scheme Table Shared Builder
        grid_disc = parse_grid_data(form_data.get("discount_scheme"))
        disc_table_data = [
            [
                Paragraph("Komponen", th_style),
                Paragraph("Nilai", th_style),
                Paragraph("Tipe", th_style),
                Paragraph("Keterangan", th_style),
            ]
        ]
        if grid_disc:
            for r in grid_disc:
                komp = r.get("komponen") or "Diskon Khusus"
                val = str(r.get("nilai") or "-")
                tip = str(r.get("tipe") or "Persentase")
                ket = r.get("keterangan") or "-"
                disc_table_data.append([
                    Paragraph(komp, cell_style),
                    Paragraph(val, cell_center_style),
                    Paragraph(tip, cell_center_style),
                    Paragraph(ket, cell_center_style),
                ])
        else:
            disc_table_data.append([
                Paragraph("Diskon Reguler / Promo Display", cell_style),
                Paragraph(f"{pct_promo}%", cell_center_style),
                Paragraph("Persentase", cell_center_style),
                Paragraph("Diberikan berdasarkan pencapaian target", cell_style),
            ])
        t_disc = Table(disc_table_data, colWidths=[130, 80, 95, 218])
        t_disc.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )

        def build_rek_block(perusahaan_name, rek_an, rek_bank, rek_no):
            rek_intro = Paragraph(
                f"Pembayaran dianggap sah apabila dana telah masuk ke rekening {perusahaan_name}, dengan nomer rekening sbb :",
                body_style,
            )
            rek_table_data = [
                [Paragraph("<b>AN</b>", cell_bold_style), Paragraph("<b>:</b>", cell_center_style), Paragraph(f"<b>{rek_an}</b>", cell_bold_style)],
                [Paragraph("<b>BANK</b>", cell_bold_style), Paragraph("<b>:</b>", cell_center_style), Paragraph(f"<b>{rek_bank}</b>", cell_bold_style)],
                [Paragraph("<b>NO REK</b>", cell_bold_style), Paragraph("<b>:</b>", cell_center_style), Paragraph(f"<b>{rek_no}</b>", cell_bold_style)],
            ]
            t_rek = Table(rek_table_data, colWidths=[65, 12, 240], hAlign='CENTER')
            t_rek.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0, colors.transparent),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 1),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                        ("LEFTPADDING", (0, 0), (-1, -1), 2),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ]
                )
            )
            rek_outro = Paragraph(
                "Walaupun nota asli sudah di serahkan / dititipkan oleh salesman maka belum dianggap sebagai pembayaran.",
                body_style,
            )
            return [rek_intro, Spacer(1, 4), t_rek, Spacer(1, 4), rek_outro]

        # BRANCHING: STANDARD (11 PASAL) VS SUPPORT PROMOSI (12 PASAL)
        inc_calc = calculate_spk_incentive_breakdown(form_data, is_support=has_support)

        if not has_support:
            # === DRAFT STANDARD (11 PASAL) ===
            # HALAMAN 1 (PASAL 4, 5)
            elements.append(Paragraph("<u><b>Pasal 4</b></u>", pasal_heading_style))
            elements.append(
                Paragraph(f"Perjanjian berlaku untuk Jangka Waktu <b>{durasi}</b> terhitung dari sejak tanggal <b>{tgl_mulai}</b> dan akan berakhir pada tanggal <b>{tgl_akhir}</b>.", body_style)
            )

            elements.append(Paragraph("<u><b>Pasal 5</b></u>", pasal_heading_style))
            elements.append(Paragraph("Skema discount untuk penjualan Produk yang berlaku untuk Pihak Kedua dalam Perjanjian ini adalah sebagai berikut :", body_style))
            elements.append(t_disc)

            # BATAS RESMI HALAMAN 1 -> PINDAH KE HALAMAN 2
            elements.append(PageBreak())

            # ==================== HALAMAN 2 (STANDARD) ====================
            elements.extend(get_page_header_logo())

            elements.append(Paragraph("<u><b>Pasal 6</b></u>", pasal_heading_style))
            p6_std = (
                "Pihak Pertama memberikan kompensasi Insentive Reward kepada Pihak Kedua saat perjanjian ini berakhir dan seluruh kewajiban "
                "Pihak Kedua kepada Pihak Pertama telah selesai atau LUNAS.<br/>"
                "Adapun perhitungan insentif adalah sebagai berikut :<br/>"
                f"• Target Rp. {inc_calc['target_per_periode']} per {inc_calc['frekuensi_bulan']} Bulan mendapatkan insentif reward {inc_calc['reward_rate']}<br/>"
                f"&nbsp; &nbsp; Insentive Reward = Rp. {inc_calc['reward_nominal']} ( {inc_calc['reward_rate']} x Pencapaian Omzet )<br/>"
                f"&nbsp; &nbsp; Pph 23 Untuk Insentive Kontrak = Rp. {inc_calc['pph_nominal']} ( Insentive x {inc_calc['pph_rate']} )<br/>"
                f"&nbsp; &nbsp; Netto Reward = Rp. {inc_calc['netto_nominal']} (Total Insentive – Pph 23)<br/>"
                f"Maka insentive yang dibayarkan adalah sebesar Rp. {inc_calc['netto_nominal']}."
            )
            elements.append(KeepTogether([Paragraph(p6_std, body_style)]))

            # BAB III (Pasal 7, 8, 9, 10)
            elements.append(Paragraph("<b>BAB III<br/>TATA CARA PEMBAYARAN</b>", bab_heading_style))
            elements.append(Paragraph("<u><b>Pasal 7</b></u>", pasal_heading_style))
            elements.append(Paragraph(f"Wajib melaksanakan Pembayaran kepada Pihak Pertama paling lambat <b>{top}</b> hari setelah tanggal pengiriman ( selanjutnya disebut “ Jangka Waktu Pembayaran” ).", body_style))

            elements.append(Paragraph("<u><b>Pasal 8</b></u>", pasal_heading_style))
            elements.append(
                Paragraph(
                    f"Sistem pembayaran melalui Transfer / Cek / Giro yang telah di tulis nama <b>{perusahaan}</b> dengan Nomer Rekening ({rekening_display}) sesuai "
                    f"yang ada pada Faktur dan kontrabon. Serta <b>TIDAK DIPERKENANKAN</b> membayar secara TUNAI kepada Salesman/Collector/Kepala Depo/ASM/BM "
                    f"atau menitip pembayaran kepada Supir maupun Karyawan lainnya.",
                    body_style,
                )
            )

            elements.append(Paragraph("<u><b>Pasal 9</b></u>", pasal_heading_style))
            elements.append(KeepTogether(build_rek_block(perusahaan, rekening_an, rekening_bank, rekening_no)))

            elements.append(Paragraph("<u><b>Pasal 10</b></u>", pasal_heading_style))
            elements.append(
                Paragraph(
                    "Apabila pembayaran tidak sesuai dengan TOP dan jika terjadi backdate, Pihak Pertama dapat mengambil/menyita aset sesuai dengan piutang.",
                    body_style,
                )
            )

            # BAB IV (Pasal 11, 12)
            elements.append(Paragraph("<b>BAB IV<br/>ITIKAD BAIK DAN PERSELISIHAN</b>", bab_heading_style))
            elements.append(Paragraph("<u><b>Pasal 11</b></u>", pasal_heading_style))
            elements.append(Paragraph("Para pihak dengan itikad baik dan penuh tanggung jawab menjalankan tugas, hak dan kewajibannya dengan mengindahkan peraturan perundangan yang berlaku.", body_style))

            elements.append(Paragraph("<u><b>Pasal 12</b></u>", pasal_heading_style))
            elements.append(
                Paragraph(
                    f"Apabila terjadi perselisihan/sengketa diantara Para Pihak terkait dengan isi dan/atau Pelaksanaan Perjanjian ini maka perselisihan tersebut "
                    f"akan di selesaikan terlebih dahulu melalui musyawarah mufakat diantara Para Pihak. Apabila dengan cara musyawarah mufakat tidak dapat dilakukan "
                    f"atau tidak tercapai sesuatu penyelesaian yang baik bagi Para Pihak maka Para Pihak sepakat untuk memilih <b>{domisili_pn}</b> "
                    f"sebagai satu satunya domisili hukum yang tetap bagi Para Pihak.",
                    body_style,
                )
            )

        else:
            # === DRAFT SUPPORT PROMOSI (12 PASAL) ===
            # HALAMAN 1 (PASAL 4, 5, 6)
            elements.append(Paragraph("<u><b>Pasal 4</b></u>", pasal_heading_style))
            komp_biaya_text = format_komponen_biaya_legal_text(form_data.get("komponen_biaya"))
            p4_supp = (
                f"1. Pihak Pertama memberikan support promosi yang meliputi biaya ({komp_biaya_text}) kepada Pihak Kedua sebesar <b>{pct_promo}%</b>. "
                f"Support promosi tersebut <b>TIDAK</b> meliputi biaya Billboard, Pajak Billboard, dan Backdrop apabila Pihak Kedua membuka cabang baru atau toko baru.<br/>"
                f"2. Support promosi ini dapat dicairkan setelah pembayaran <b>LUNAS</b>.<br/>"
                f"3. Grace period selama 1 (satu) bulan dari masa kontrak berakhir, apabila Pihak Kedua belum mencapai target."
            )
            elements.append(Paragraph(p4_supp, body_style))

            elements.append(Paragraph("<u><b>Pasal 5</b></u>", pasal_heading_style))
            elements.append(
                Paragraph(f"Perjanjian berlaku untuk Jangka Waktu <b>{durasi}</b> terhitung dari sejak tanggal <b>{tgl_mulai}</b> dan akan berakhir pada tanggal <b>{tgl_akhir}</b>.", body_style)
            )

            elements.append(Paragraph("<u><b>Pasal 6</b></u>", pasal_heading_style))
            elements.append(Paragraph("Skema discount untuk penjualan Produk yang berlaku untuk Pihak Kedua dalam Perjanjian ini adalah sebagai berikut :", body_style))
            elements.append(t_disc)

            # BATAS RESMI HALAMAN 1 -> PINDAH KE HALAMAN 2
            elements.append(PageBreak())

            # ==================== HALAMAN 2 (SUPPORT PROMOSI) ====================
            elements.extend(get_page_header_logo())

            elements.append(Paragraph("<u><b>Pasal 7</b></u>", pasal_heading_style))
            narasi_p7_text = (
                f"<b>Rincian Perhitungan Resmi:</b> {inc_calc['narasi_perhitungan_paragraf']}"
            )
            p7_supp = (
                "Pihak Pertama memberikan kompensasi Insentive Reward kepada Pihak Kedua saat perjanjian ini berakhir dan seluruh kewajiban "
                "Pihak Kedua kepada Pihak Pertama telah selesai atau LUNAS.<br/>"
                f"{narasi_p7_text}<br/>"
                "Adapun rincian perhitungan insentif adalah sebagai berikut :<br/>"
                f"• Target Rp. {inc_calc['target_per_periode']} per {inc_calc['frekuensi_bulan']} Bulan mendapatkan reward (support promosi) {inc_calc['reward_rate']}<br/>"
                f"&nbsp; &nbsp; Insentive Reward = Rp. {inc_calc['reward_nominal']} ( {inc_calc['reward_rate']} x Pencapaian Omzet )<br/>"
                f"&nbsp; &nbsp; Pph 23 Untuk Insentive Kontrak = Rp. {inc_calc['pph_nominal']} ( Reward x {inc_calc['pph_rate']} )<br/>"
                f"&nbsp; &nbsp; Netto Reward = Rp. {inc_calc['netto_nominal']} (Total Insentive – Pph 23)<br/>"
                f"Maka insentive yang dibayarkan adalah sebesar Rp. {inc_calc['netto_nominal']}."
            )
            elements.append(KeepTogether([Paragraph(p7_supp, body_style)]))

            # Tier Support Grid if present (5 Kolom Lengkap Sesuai Poin 11)
            grid_tier = parse_grid_data(form_data.get("tier_support"))
            if grid_tier:
                tier_table_data = [
                    [
                        Paragraph("Target Tahunan", th_style),
                        Paragraph("Dukungan (%)", th_style),
                        Paragraph("PPh 23 (%)", th_style),
                        Paragraph("Nilai Netto (Rp)", th_style),
                        Paragraph("Keterangan", th_style),
                    ]
                ]
                for r in grid_tier:
                    raw_netto = r.get("netto", 0)
                    try:
                        netto_num = float(re.sub(r"[^\d.-]", "", str(raw_netto)) or 0)
                        netto_str = format_rupiah(netto_num)
                    except Exception:
                        netto_str = str(raw_netto) if raw_netto else "—"
                    tier_table_data.append([
                        Paragraph(format_rupiah(r.get("target_tahunan")), cell_center_style),
                        Paragraph(f"{r.get('support_pct', 0)}%", cell_center_style),
                        Paragraph(f"{r.get('pph_pct', 2)}%", cell_center_style),
                        Paragraph(netto_str, cell_center_style),
                        Paragraph(str(r.get("keterangan") or "—"), cell_style),
                    ])
                t_tier = Table(tier_table_data, colWidths=[120, 75, 75, 110, 143])
                t_tier.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("TOPPADDING", (0, 0), (-1, -1), 2),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                            ("LEFTPADDING", (0, 0), (-1, -1), 4),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ]
                    )
                )
                elements.append(t_tier)

            # BAB III (Pasal 8, 9, 10)
            elements.append(Paragraph("<b>BAB III<br/>TATA CARA PEMBAYARAN</b>", bab_heading_style))
            elements.append(Paragraph("<u><b>Pasal 8</b></u>", pasal_heading_style))
            elements.append(Paragraph(f"Wajib melaksanakan Pembayaran kepada Pihak Pertama paling lambat <b>{top}</b> hari setelah tanggal pengiriman ( selanjutnya disebut “ Jangka Waktu Pembayaran” ).", body_style))

            elements.append(Paragraph("<u><b>Pasal 9</b></u>", pasal_heading_style))
            elements.append(
                Paragraph(
                    f"Sistem pembayaran melalui Transfer / Cek / Giro yang telah di tulis nama <b>{perusahaan}</b> dengan Nomer Rekening ({rekening_display}) sesuai "
                    f"yang ada pada Faktur dan kontrabon. Serta <b>TIDAK DIPERKENANKAN</b> membayar secara TUNAI kepada Salesman/Collector/Kepala Depo/ASM/BM "
                    f"atau menitip pembayaran kepada Supir maupun Karyawan lainnya.",
                    body_style,
                )
            )

            elements.append(Paragraph("<u><b>Pasal 10</b></u>", pasal_heading_style))
            elements.append(KeepTogether(build_rek_block(perusahaan, rekening_an, rekening_bank, rekening_no)))

            elements.append(Paragraph("<u><b>Pasal 11</b></u>", pasal_heading_style))
            elements.append(
                Paragraph(
                    "Apabila pembayaran tidak sesuai dengan TOP dan jika terjadi backdate, Pihak Pertama dapat mengambil/menyita aset sesuai dengan piutang.",
                    body_style,
                )
            )

            # BAB IV (Pasal 12, 13)
            elements.append(Paragraph("<b>BAB IV<br/>ITIKAD BAIK DAN PERSELISIHAN</b>", bab_heading_style))
            elements.append(Paragraph("<u><b>Pasal 12</b></u>", pasal_heading_style))
            elements.append(Paragraph("Para pihak dengan itikad baik dan penuh tanggung jawab menjalankan tugas, hak dan kewajibannya dengan mengindahkan peraturan perundangan yang berlaku.", body_style))

            elements.append(Paragraph("<u><b>Pasal 13</b></u>", pasal_heading_style))
            elements.append(
                Paragraph(
                    f"Apabila terjadi perselisihan/sengketa diantara Para Pihak terkait dengan isi dan/atau Pelaksanaan Perjanjian ini maka perselisihan tersebut "
                    f"akan di selesaikan terlebih dahulu melalui musyawarah mufakat diantara Para Pihak. Apabila dengan cara musyawarah mufakat tidak dapat dilakukan "
                    f"atau tidak tercapai sesuatu penyelesaian yang baik bagi Para Pihak maka Para Pihak sepakat untuk memilih <b>{domisili_pn}</b> "
                    f"sebagai satu satunya domisili hukum yang tetap bagi Para Pihak.",
                    body_style,
                )
            )

        # Blok Penutup & Tanda Tangan: 2 Kolom Bersih Dilindungi KeepTogether
        direksi_approved_time = timezone.now().strftime("%d/%m/%Y")

        # Slot e-meterai: area transparan bersih tempat e-meterai resmi dibubuhkan
        has_ematerai = False
        if hasattr(submission, "stamped_document") and getattr(submission.stamped_document, "status", "") == "stamped":
            has_ematerai = True
        elif hasattr(submission, "approval_tasks"):
            has_ematerai = submission.approval_tasks.filter(
                workflow_stage__order=3,
                status="approved",
            ).exists()

        mockup_img_path = os.path.join(settings.BASE_DIR, "static", "images", "ematerai_mockup.png")
        if has_ematerai and not for_stamping and os.path.exists(mockup_img_path):
            meterai_slot_p = RLImage(mockup_img_path, width=54, height=52)
        else:
            meterai_slot_p = Spacer(54, 52)

        direksi_ttd_flowable = None
        ttd_direksi_b64 = form_data.get("ttd_direksi_image") or form_data.get("signature_direksi")
        if ttd_direksi_b64 and isinstance(ttd_direksi_b64, str) and "base64," in ttd_direksi_b64:
            try:
                raw_b64 = ttd_direksi_b64.split("base64,", 1)[1]
                img_data = base64.b64decode(raw_b64)
                img_buf = io.BytesIO(img_data)
                direksi_ttd_flowable = RLImage(img_buf, width=120, height=48)
            except Exception:
                direksi_ttd_flowable = None

        if not direksi_ttd_flowable:
            st_direksi_approved = None
            if hasattr(submission, "approval_tasks"):
                st_direksi_approved = (
                    submission.approval_tasks.filter(
                        workflow_stage__name__icontains="direksi",
                        status="approved",
                    ).first()
                    or submission.approval_tasks.filter(
                        workflow_stage__name__icontains="final",
                        status="approved",
                    ).first()
                    or submission.approval_tasks.filter(
                        workflow_stage__order__in=[4, 5],
                        status="approved",
                    ).first()
                )
            is_direksi_approved = bool(st_direksi_approved or getattr(submission, "status", "") == "approved")

            if is_direksi_approved:
                approved_time_str = (
                    timezone.localtime(st_direksi_approved.completed_at).strftime("%d/%m/%Y")
                    if st_direksi_approved and st_direksi_approved.completed_at
                    else direksi_approved_time
                )
                direksi_ttd_flowable = Paragraph(
                    "<font color='#15803d' size='7.5'><b>[DISETUJUI DIGITAL]</b></font><br/>"
                    f"<font size='6.5' color='#166534'>Direksi PT Royal Corp<br/>&bull; {approved_time_str} &bull;</font>",
                    cell_center_style,
                )
            else:
                # Fresh / draft / unapproved document: leave blank space for signature
                direksi_ttd_flowable = Spacer(1, 52)

        # Area Tanda Tangan Pihak Pertama
        direksi_mid_table = Table(
            [[direksi_ttd_flowable]],
            colWidths=[205],
            rowHeights=[52],
            hAlign='CENTER',
        )
        direksi_mid_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )

        direksi_cell_content = [
            Paragraph(f"<b>PIHAK PERTAMA</b><br/><font color='#111827'>{perusahaan}</font>", cell_center_style),
            Spacer(1, 4),
            direksi_mid_table,
            Spacer(1, 4),
            Paragraph(f"<u><b>{pihak_1_nama}</b></u>", cell_center_style),
            Paragraph(f"<font size='7' color='#475569'>{pihak_1_jabatan}</font>", cell_center_style),
        ]

        # Area Posisi Materai Tengah (Kolom 2)
        # Placeholder / Slot Visual e-Meterai Rp 10.000 tepat di tengah
        meterai_slot_table = Table(
            [[meterai_slot_p]],
            colWidths=[85],
            rowHeights=[52],
            hAlign='CENTER',
        )
        meterai_slot_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )

        meterai_cell_content = [
            Paragraph("&nbsp;<br/>&nbsp;", cell_center_style),  # Spacer sejajar dengan header PIHAK
            Spacer(1, 4),
            meterai_slot_table,
            Spacer(1, 4),
            Paragraph("&nbsp;", cell_center_style),
            Paragraph("&nbsp;", cell_center_style),
        ]

        toko_ttd_flowable = None
        ttd_toko_b64 = form_data.get("ttd_toko_image") or form_data.get("signature_toko")
        if not ttd_toko_b64 and hasattr(submission, "signing_tokens"):
            st_token = submission.signing_tokens.filter(status="signed").order_by("-signed_at").first()
            if st_token and st_token.signature_image:
                ttd_toko_b64 = st_token.signature_image

        if ttd_toko_b64 and isinstance(ttd_toko_b64, str) and "base64," in ttd_toko_b64:
            try:
                raw_b64 = ttd_toko_b64.split("base64,", 1)[1]
                img_data = base64.b64decode(raw_b64)
                img_buf = io.BytesIO(img_data)
                toko_ttd_flowable = RLImage(img_buf, width=120, height=48)
            except Exception:
                toko_ttd_flowable = None

        if not toko_ttd_flowable:
            has_toko_signed = False
            token_signed_at_str = tgl_ttd
            if hasattr(submission, "signing_tokens"):
                st_token = submission.signing_tokens.filter(status="signed").order_by("-signed_at").first()
                if st_token:
                    has_toko_signed = True
                    if st_token.signed_at:
                        token_signed_at_str = timezone.localtime(st_token.signed_at).strftime("%d/%m/%Y")

            if has_toko_signed:
                toko_ttd_content = Paragraph(
                    "<font color='#0284c7' size='7.5'><b>[TERTANDA TANGAN]</b></font><br/>"
                    f"<font size='6.5' color='#64748b'>Mitra Toko &bull; {token_signed_at_str}</font>",
                    cell_center_style,
                )
            else:
                # Fresh / draft / unsigned document: leave blank space for signature
                toko_ttd_content = Spacer(1, 52)
        else:
            toko_ttd_content = toko_ttd_flowable

        # Area Tanda Tangan Pihak Kedua (Bersih tanpa border)
        toko_mid_table = Table(
            [[toko_ttd_content]],
            colWidths=[205],
            rowHeights=[52],
            hAlign='CENTER',
        )
        toko_mid_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )

        toko_cell_content = [
            Paragraph(f"<b>PIHAK KEDUA</b><br/><font color='#111827'>{nama_toko}</font>", cell_center_style),
            Spacer(1, 4),
            toko_mid_table,
            Spacer(1, 4),
            Paragraph(f"<u><b>{nama_pemilik}</b></u>", cell_center_style),
            Paragraph("<font size='7' color='#475569'>Pemilik Toko</font>", cell_center_style),
        ]

        # Tabel Penandatanganan 3 Kolom Simetris: Pihak Pertama (215) | Posisi Materai (93) | Pihak Kedua (215) = 523pt
        sig_table_data = [
            [direksi_cell_content, meterai_cell_content, toko_cell_content]
        ]

        t_sig = Table(sig_table_data, colWidths=[215, 93, 215], hAlign='CENTER')
        t_sig.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )

        # Seluruh blok penutup hukum dan tanda tangan dibungkus atomik dalam KeepTogether
        closing_block = [
            Paragraph(
                "<b>DENGAN DEMIKIAN</b>, Para Pihak telah menandatangani Perjanjian ini dalam 2 (dua) rangkap yang masing-masing berlaku sebagai asli, "
                "bermeterai cukup dan berkekuatan hukum yang sama yang dapat dipergunakan secara sah sebagai bukti adanya kesepakatan diantara Para Pihak.",
                body_style,
            ),
            Spacer(1, 10),
            Paragraph(
                f"<b>{kota_ttd}, {tgl_ttd}</b>",
                body_style,
            ),
            Spacer(1, 6),
            t_sig,
        ]
        elements.append(KeepTogether(closing_block))

        NumberedCanvas._later_logo_path = logo_path
        NumberedCanvas._later_logo_w = fit_w if 'fit_w' in locals() else 65.0
        NumberedCanvas._later_logo_h = fit_h if 'fit_h' in locals() else 24.0

        doc.build(elements, canvasmaker=NumberedCanvas)
        buffer.seek(0)
        return buffer.getvalue()

    @classmethod
    def stamp_submission(
        cls,
        submission,
        provider_name: Optional[str] = None,
        force_retry: bool = False,
        user=None,
    ):
        """
        Execute full single-stamping pipeline for a FormSubmission:
        1. Ensure or update StampedContractDocument record (status='in_progress').
        2. Generate raw SPK PDF bytes in-memory.
        3. Upload to provider (POST /v2/doc/upload).
        4. Stamp at target coordinates on the last page (POST /v1/doc/stamp).
        5. Download final stamped PDF bytes (GET /v2/doc/{id}/download).
        6. Save stamped PDF to media storage and mark status='stamped'.
        7. Audit log the execution.
        """
        from django_forms_workflows.models import AuditLog, StampedContractDocument

        stamped_doc, _created = StampedContractDocument.objects.get_or_create(
            submission=submission,
            defaults={
                "status": "pending",
                "provider": provider_name or getattr(settings, "EMATERAI_PROVIDER", "mock"),
            },
        )

        if stamped_doc.status == "stamped" and not force_retry and stamped_doc.stamped_file:
            logger.info("Submission #%s is already officially stamped. Skipping.", submission.id)
            return stamped_doc

        provider = cls.get_provider(provider_name)
        active_provider_name = provider.__class__.__name__

        stamped_doc.status = "in_progress"
        stamped_doc.provider = active_provider_name
        stamped_doc.error_message = ""
        stamped_doc.save(update_fields=["status", "provider", "error_message", "updated_at"])

        try:
            # 1. Generate clean SPK PDF bytes (leaving slot open for provider stamping)
            pdf_bytes, page_count = cls.generate_spk_pdf_bytes(submission, for_stamping=True)
            target_page = page_count  # Always stamp on the last page
            llx, lly, urx, ury = cls.get_stamping_coordinates(pdf_bytes=pdf_bytes)

            filename = f"spk_raw_sub_{submission.id}.pdf"

            # 2. Upload to Provider
            upload_res: UploadResult = provider.upload_document(pdf_bytes, filename)
            if not upload_res.success or not upload_res.file_key:
                raise RuntimeError(f"Provider Upload Failed: {upload_res.message}")

            file_key = upload_res.file_key

            # 3. Request Stamping
            stamp_res: StampingResult = provider.stamp_document(
                file_key=file_key,
                page_number=target_page,
                llx=llx,
                lly=lly,
                urx=urx,
                ury=ury,
            )
            if not stamp_res.success:
                raise RuntimeError(f"Provider Stamping Failed: {stamp_res.message}")

            doc_id = stamp_res.document_id or file_key

            # 4. Download Stamped Document
            if stamp_res.stamped_pdf_bytes:
                stamped_bytes = stamp_res.stamped_pdf_bytes
            else:
                stamped_bytes = provider.download_stamped_document(doc_id)

            if not stamped_bytes or not stamped_bytes.startswith(b"%PDF"):
                raise ValueError("Downloaded file is empty or not a valid PDF")

            # 5. Save to Media Storage
            clean_filename = f"spk_stamped_{submission.id}_{int(timezone.now().timestamp())}.pdf"
            relative_storage_path = f"stamped_contracts/{clean_filename}"

            saved_path = default_storage.save(
                relative_storage_path, ContentFile(stamped_bytes)
            )

            # 6. Update Model Record
            stamped_doc.stamped_file.name = saved_path
            stamped_doc.file_name = clean_filename
            stamped_doc.file_size = len(stamped_bytes)
            stamped_doc.provider_document_id = doc_id
            stamped_doc.page_number = target_page
            stamped_doc.coordinates = {"llx": llx, "lly": lly, "urx": urx, "ury": ury}
            stamped_doc.status = "stamped"
            stamped_doc.stamped_at = timezone.now()
            stamped_doc.error_message = ""
            stamped_doc.save()

            # 7. Record Audit Log
            AuditLog.objects.create(
                action="update",
                object_type="FormSubmission",
                object_id=submission.id,
                user=user if (user and user.is_authenticated) else None,
                changes={
                    "event": "ematerai_stamped_success",
                    "provider": active_provider_name,
                    "document_id": doc_id,
                    "page": target_page,
                    "file_path": saved_path,
                },
                comments=f"e-Meterai resmi berhasil dibubuhkan via {active_provider_name}.",
            )

            logger.info("Successfully stamped e-Meterai on submission #%s (saved to %s)", submission.id, saved_path)
            return stamped_doc

        except Exception as exc:
            err_msg = str(exc)
            logger.error("e-Meterai stamping failed for submission #%s: %s", submission.id, err_msg)
            stamped_doc.status = "failed"
            stamped_doc.error_message = err_msg
            stamped_doc.save(update_fields=["status", "error_message", "updated_at"])

            try:
                AuditLog.objects.create(
                    action="update",
                    object_type="FormSubmission",
                    object_id=submission.id,
                    user=user if (user and user.is_authenticated) else None,
                    changes={
                        "event": "ematerai_stamped_failed",
                        "provider": active_provider_name,
                        "error": err_msg,
                    },
                    comments=f"Gagal membubuhkan e-Meterai: {err_msg}",
                )
            except Exception:
                pass

            return stamped_doc

    @classmethod
    def stamp_submission_async(
        cls,
        submission_id: int,
        provider_name: Optional[str] = None,
        force_retry: bool = False,
        user_id: Optional[int] = None,
    ) -> None:
        """
        Execute stamping in a background daemon thread so HTTP response is returned immediately.
        """
        def _worker():
            from django.contrib.auth import get_user_model
            from django_forms_workflows.models import FormSubmission

            try:
                submission = FormSubmission.objects.filter(id=submission_id).first()
                if not submission:
                    return

                user = None
                if user_id:
                    user = get_user_model().objects.filter(id=user_id).first()

                cls.stamp_submission(
                    submission=submission,
                    provider_name=provider_name,
                    force_retry=force_retry,
                    user=user,
                )
            except Exception as e:
                logger.error("Error in async e-meterai worker for sub #%s: %s", submission_id, e)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
