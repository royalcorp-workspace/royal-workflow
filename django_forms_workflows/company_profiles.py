import os
import re
import datetime
import base64
from pathlib import Path
from typing import Any, Optional
from django.conf import settings

ROMAN_MONTHS = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]

CABANG_CODES = {
    "bali": "DPS",
    "bandung": "BDG",
    "banyumas": "BMS",
    "cirebon": "CRB",
    "jakarta": "JKT",
    "kediri": "KDR",
    "lampung": "LMP",
    "makassar": "MKS",
    "manado": "MND",
    "medan": "MDN",
    "palembang": "PLB",
    "pekanbaru": "PKU",
    "pusat": "PST",
    "r1": "R1",
    "r2": "R2",
    "semarang": "SMG",
    "surabaya": "SBY",
    "tangerang": "TGR",
}

BRANCH_COURT_JURISDICTIONS = {
    "bali": "Kantor Panitera Pengadilan Negeri Denpasar",
    "denpasar": "Kantor Panitera Pengadilan Negeri Denpasar",
    "bandung": "Kantor Panitera Pengadilan Negeri Bale Bandung",
    "banyumas": "Kantor Panitera Pengadilan Negeri Banyumas",
    "cirebon": "Kantor Panitera Pengadilan Negeri Cirebon",
    "jakarta": "Kantor Panitera Pengadilan Negeri Tangerang",
    "kediri": "Kantor Panitera Pengadilan Negeri Kediri",
    "lampung": "Kantor Panitera Pengadilan Negeri Tanjung Karang",
    "makassar": "Kantor Panitera Pengadilan Negeri Makassar",
    "manado": "Kantor Panitera Pengadilan Negeri Manado",
    "medan": "Kantor Panitera Pengadilan Negeri Medan",
    "palembang": "Kantor Panitera Pengadilan Negeri Palembang",
    "pekanbaru": "Kantor Panitera Pengadilan Negeri Pekanbaru",
    "pusat": "Kantor Panitera Pengadilan Negeri Tangerang",
    "r1": "Kantor Panitera Pengadilan Negeri Tangerang",
    "r2": "Kantor Panitera Pengadilan Negeri Tangerang",
    "semarang": "Kantor Panitera Pengadilan Negeri Semarang",
    "surabaya": "Kantor Panitera Pengadilan Negeri Surabaya",
    "tangerang": "Kantor Panitera Pengadilan Negeri Tangerang",
}


def resolve_court_jurisdiction(cabang=None, kota=None, default=None) -> str:
    """
    Resolve legal court jurisdiction (Pengadilan Negeri) dynamically based on Cabang / Kota Pengaju:
    - Bali -> Kantor Panitera Pengadilan Negeri Denpasar
    - Bandung -> Kantor Panitera Pengadilan Negeri Bale Bandung
    - Surabaya / Jatim -> Kantor Panitera Pengadilan Negeri Surabaya
    - Tangerang / Jakarta / Pusat -> Kantor Panitera Pengadilan Negeri Tangerang
    - etc.
    """
    candidates = []
    if cabang:
        candidates.append(str(cabang).strip().lower())
    if kota:
        candidates.append(str(kota).strip().lower())
        
    for cand in candidates:
        for k, v in BRANCH_COURT_JURISDICTIONS.items():
            if k in cand or cand in k:
                return v
                
    if cabang:
        c_title = str(cabang).strip().title()
        return f"Kantor Panitera Pengadilan Negeri {c_title}"
    if kota:
        k_title = str(kota).strip().title()
        return f"Kantor Panitera Pengadilan Negeri {k_title}"
        
    return default or "Kantor Panitera Pengadilan Negeri Tangerang"


OFFICIAL_BRANDS = {
    "LADY": "Lady Americana",
    "ELITE": "Elite Springbed",
    "SERENITY": "Serenity",
    "ROYAL": "Royal Foam",
    "CLASSIC": "Classic",
}


def format_canonical_brand_name(brand_val: str) -> str:
    """Format any brand input into its canonical official uppercase display name:
    - LADY AMERICANA
    - ELITE SPRINGBED
    - SERENITY
    - ROYAL FOAM
    - CLASSIC
    """
    b = str(brand_val or "").strip().upper()
    if "LADY" in b:
        return "LADY AMERICANA"
    if "ELITE" in b:
        return "ELITE SPRINGBED"
    if "SERENITY" in b:
        return "SERENITY"
    if "ROYAL" in b or "FOAM" in b:
        return "ROYAL FOAM"
    if "CLASSIC" in b:
        return "CLASSIC"
    return str(brand_val or "").strip().upper()


def calculate_contract_duration(start_val, end_val) -> str:
    """Calculate inclusive contract duration between two dates:
    - 01/01/2025 to 31/12/2025 -> '1 Tahun'
    - 01/01/2025 to 31/01/2026 -> '1 Tahun 1 Bulan'
    - 01/01/2025 to 28/02/2026 -> '1 Tahun 2 Bulan'
    - 01/01/2025 to 31/01/2025 -> '1 Bulan'
    """
    import datetime
    if not start_val or not end_val:
        return ""

    d1 = None
    d2 = None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        if not d1:
            try:
                d1 = datetime.datetime.strptime(str(start_val).strip(), fmt).date()
            except ValueError:
                pass
        if not d2:
            try:
                d2 = datetime.datetime.strptime(str(end_val).strip(), fmt).date()
            except ValueError:
                pass

    if not d1 or not d2 or d2 < d1:
        return ""

    # Inclusive end date: add 1 day
    d2_next = d2 + datetime.timedelta(days=1)

    years = d2_next.year - d1.year
    months = d2_next.month - d1.month
    days = d2_next.day - d1.day

    if days < 0:
        months -= 1
    if months < 0:
        years -= 1
        months += 12

    if years > 0 and months > 0:
        return f"{years} Tahun {months} Bulan"
    elif years > 0:
        return f"{years} Tahun"
    elif months > 0:
        return f"{months} Bulan"
    else:
        return "1 Bulan"


def normalize_contract_duration(durasi_val: str, start_val=None, end_val=None) -> str:
    """Format and normalize contract duration into standard Indonesian legal text:
    - '1 Tahun'
    - '1 Tahun 1 Bulan'
    - '1 Tahun 2 Bulan'
    - '1 Bulan', '6 Bulan', etc.
    """
    if start_val and end_val:
        calc = calculate_contract_duration(start_val, end_val)
        if calc:
            return calc

    d_str = str(durasi_val or "").strip()
    if not d_str or d_str in ("—", "-", "None", "null"):
        return "1 Tahun"

    import re

    # Check for 'X Tahun Y Bulan' or 'X Tahun'
    m_yt_bl = re.match(r"^(\d+)\s*Tahun(?:\s*(\d+)\s*Bulan)?$", d_str, re.IGNORECASE)
    if m_yt_bl:
        y = int(m_yt_bl.group(1))
        b = int(m_yt_bl.group(2)) if m_yt_bl.group(2) else 0
        if y > 0 and b > 0:
            return f"{y} Tahun {b} Bulan"
        elif y > 0:
            return f"{y} Tahun"
        elif b > 0:
            return f"{b} Bulan"

    # Check for pure month 'X Bulan'
    m_bl = re.match(r"^(\d+)\s*Bulan$", d_str, re.IGNORECASE)
    if m_bl:
        total_m = int(m_bl.group(1))
        y = total_m // 12
        rem_m = total_m % 12
        if y > 0 and rem_m > 0:
            return f"{y} Tahun {rem_m} Bulan"
        elif y > 0:
            return f"{y} Tahun"
        else:
            return f"{rem_m} Bulan"

    # Numeric only
    if d_str.isdigit():
        total_m = int(d_str)
        y = total_m // 12
        rem_m = total_m % 12
        if y > 0 and rem_m > 0:
            return f"{y} Tahun {rem_m} Bulan"
        elif y > 0:
            return f"{y} Tahun"
        else:
            return f"{rem_m} Bulan"

    return d_str

OFFICIAL_SUPPORT_COMPONENTS = ["Sewa", "Listrik", "Instore", "Pameran", "Asuransi"]


def parse_komponen_biaya_list(komponen_val) -> list:
    """Parse raw form value (JSON list, Python list, or comma-separated string)
    into a clean list of official support components.
    Only allows 5 official components: Sewa, Listrik, Instore, Pameran, Asuransi.
    """
    if not komponen_val:
        return []

    import json
    raw_items = []
    if isinstance(komponen_val, list):
        raw_items = komponen_val
    elif isinstance(komponen_val, str):
        trimmed = komponen_val.strip()
        if trimmed.startswith("[") and trimmed.endswith("]"):
            try:
                parsed = json.loads(trimmed)
                if isinstance(parsed, list):
                    raw_items = parsed
            except Exception:
                raw_items = [s.strip().strip("'\"") for s in trimmed.strip("[]").split(",") if s.strip()]
        else:
            raw_items = [s.strip().strip("'\"") for s in trimmed.split(",") if s.strip()]

    OFFICIAL_MAP = {
        "sewa": "Sewa",
        "listrik": "Listrik",
        "instore": "Instore",
        "pameran": "Pameran",
        "pajak billboard": "Pajak Billboard",
        "pajak_billboard": "Pajak Billboard",
        "asuransi": "Asuransi",
    }

    clean_items = []
    for item in raw_items:
        key = str(item).strip().lower()
        if key in OFFICIAL_MAP and OFFICIAL_MAP[key] not in clean_items:
            clean_items.append(OFFICIAL_MAP[key])

    return clean_items


def format_komponen_biaya_legal_text(komponen_val) -> str:
    """Format array/string komponen biaya into natural Indonesian legal prose for Pasal 4:
    - 1 item: "sewa"
    - 2 items: "sewa dan listrik"
    - 3+ items: "sewa, listrik, dan instore"
    - All 5 / default: "sewa, listrik, instore, pameran, dan asuransi"
    """
    clean_items = parse_komponen_biaya_list(komponen_val)
    if not clean_items:
        clean_items = ["Sewa", "Listrik", "Instore", "Pameran", "Asuransi"]

    lower_items = [item.lower() for item in clean_items]
    if len(lower_items) == 1:
        return lower_items[0]
    elif len(lower_items) == 2:
        return f"{lower_items[0]} dan {lower_items[1]}"
    else:
        return f"{', '.join(lower_items[:-1])}, dan {lower_items[-1]}"


def calculate_spk_incentive_breakdown(form_data: dict, is_support: bool = False) -> dict:
    """
    Calculate dynamic sales target, reward percentages, PPh 23 deductions, and
    construct the official Indonesian narrative text for SPK Pasal 6 / Pasal 7.
    """
    import json

    if not isinstance(form_data, dict):
        form_data = {}

    # 1. Parse duration & frequency
    durasi_str = str(form_data.get("durasi") or "1 Tahun")
    durasi_num = 12
    m_yt = re.search(r"(\d+)\s*Tahun", durasi_str, re.IGNORECASE)
    m_bl = re.search(r"(\d+)\s*Bulan", durasi_str, re.IGNORECASE)
    if m_yt or m_bl:
        years = int(m_yt.group(1)) if m_yt else 0
        months = int(m_bl.group(1)) if m_bl else 0
        durasi_num = (years * 12) + months
    elif durasi_str.isdigit():
        durasi_num = int(durasi_str)
    elif re.search(r"(\d+)", durasi_str):
        durasi_num = int(re.search(r"(\d+)", durasi_str).group(1))

    freq_bulan = 3 if durasi_num >= 3 else 1

    # 2. Extract monthly target
    target_val = 0.0
    parsed_target = form_data.get("target_incentive")
    if isinstance(parsed_target, str) and parsed_target.strip().startswith("["):
        try:
            parsed_target = json.loads(parsed_target.strip())
        except Exception:
            parsed_target = []

    if isinstance(parsed_target, list) and parsed_target and isinstance(parsed_target[0], dict):
        raw_t = parsed_target[0].get("target_bulanan")
        if raw_t:
            try:
                target_val = float(re.sub(r"[^\d.-]", "", str(raw_t)))
            except Exception:
                pass

    if not target_val and form_data.get("nilai_target"):
        try:
            target_val = float(re.sub(r"[^\d.-]", "", str(form_data.get("nilai_target"))))
        except Exception:
            pass

    target_per_periode = target_val * freq_bulan if target_val else 100000000.0

    # 3. Check tier_support if support promosi
    parsed_tier = form_data.get("tier_support")
    if isinstance(parsed_tier, str) and parsed_tier.strip().startswith("["):
        try:
            parsed_tier = json.loads(parsed_tier.strip())
        except Exception:
            parsed_tier = []

    if is_support:
        # PPh 23 rate for Support Promosi is 2%
        pph_rate_num = 2.0
        pph_rate_str = "2%"

        # Determine reward rate
        pct_num = 5.0
        pct_raw = form_data.get("pct_support_promo")
        if pct_raw is not None and str(pct_raw).strip() != "":
            try:
                pct_num = float(re.sub(r"[^\d.-]", "", str(pct_raw)))
            except Exception:
                pct_num = 5.0
        elif isinstance(parsed_tier, list) and parsed_tier and isinstance(parsed_tier[0], dict):
            raw_sp = parsed_tier[0].get("support_pct")
            if raw_sp is not None:
                try:
                    pct_num = float(re.sub(r"[^\d.-]", "", str(raw_sp)))
                except Exception:
                    pct_num = 5.0

        reward_rate_str = f"{pct_num:g}%"
        reward_nominal = target_per_periode * (pct_num / 100.0)
        pph_nominal = reward_nominal * (pph_rate_num / 100.0)
        netto_nominal = reward_nominal - pph_nominal
    else:
        # PPh 23 rate for Standard is 15%
        pph_rate_num = 15.0
        pph_rate_str = "15%"

        pct_num = 2.5
        if isinstance(parsed_target, list) and parsed_target and isinstance(parsed_target[0], dict) and parsed_target[0].get("incentive_pct"):
            try:
                pct_num = float(re.sub(r"[^\d.-]", "", str(parsed_target[0].get("incentive_pct"))))
            except Exception:
                pass

        reward_rate_str = f"{pct_num:g}%"
        reward_nominal = target_per_periode * (pct_num / 100.0)
        pph_nominal = reward_nominal * (pph_rate_num / 100.0)
        netto_nominal = reward_nominal - pph_nominal

    t_periode_fmt = f"{int(round(target_per_periode)):,}".replace(",", ".")
    rew_nom_fmt = f"{int(round(reward_nominal)):,}".replace(",", ".")
    pph_nom_fmt = f"{int(round(pph_nominal)):,}".replace(",", ".")
    net_nom_fmt = f"{int(round(netto_nominal)):,}".replace(",", ".")

    narasi_paragraf = (
        f"Target penjualan sebesar Rp. {t_periode_fmt} per {freq_bulan} Bulan mendapatkan insentif reward {reward_rate_str} "
        f"dengan estimasi reward sebesar Rp. {rew_nom_fmt} dipotong PPh 23 sebesar {pph_rate_str} (Rp. {pph_nom_fmt}) "
        f"sehingga total netto reward yang diterima sebesar Rp. {net_nom_fmt}."
    )

    return {
        "frekuensi_bulan": str(freq_bulan),
        "target_per_periode": t_periode_fmt,
        "reward_rate": reward_rate_str,
        "reward_rate_num": pct_num,
        "pph_rate": pph_rate_str,
        "pph_rate_num": pph_rate_num,
        "reward_nominal": rew_nom_fmt,
        "pph_nominal": pph_nom_fmt,
        "netto_nominal": net_nom_fmt,
        "narasi_perhitungan_paragraf": narasi_paragraf,
    }


def build_spk_incentive_matrix_data(form_data: dict) -> list:
    """
    Build multi-tier incentive calculation matrix for SPK Pasal 6.
    Extracts tiers from target_incentive grid (or fallback to nilai_target).
    Returns list of dicts with 6 columns data:
    [
        {
            "target_tahunan_fmt": "Rp 3.000.000.000",
            "target_tahunan_num": 3000000000.0,
            "incentive_pct_str": "7%",
            "incentive_pct_num": 7.0,
            "incentive_val_fmt": "210.000.000",
            "incentive_val_num": 210000000.0,
            "pph_pct_str": "15%",
            "pph_pct_num": 15.0,
            "pph_val_fmt": "31.500.000",
            "pph_val_num": 31500000.0,
            "netto_val_fmt": "178.500.000",
            "netto_val_num": 178500000.0,
        },
        ...
    ]
    """
    import json
    if not isinstance(form_data, dict):
        form_data = {}

    parsed_target = form_data.get("target_incentive")
    if isinstance(parsed_target, str) and parsed_target.strip().startswith("["):
        try:
            parsed_target = json.loads(parsed_target.strip())
        except Exception:
            parsed_target = []

    rows_data = []
    if isinstance(parsed_target, list) and parsed_target:
        for r in parsed_target:
            if not isinstance(r, dict):
                continue
            raw_tb = r.get("target_bulanan", 0)
            try:
                t_bln = float(re.sub(r"[^\d.-]", "", str(raw_tb)) or 0)
            except Exception:
                t_bln = 0.0

            raw_inc = r.get("incentive_pct", 0)
            try:
                inc_pct = float(re.sub(r"[^\d.-]", "", str(raw_inc)) or 0)
            except Exception:
                inc_pct = 0.0

            # Annual target = monthly * 12
            target_tahunan = t_bln * 12.0
            inc_val = target_tahunan * (inc_pct / 100.0)
            pph_pct = 15.0
            pph_val = inc_val * (pph_pct / 100.0)
            netto_val = inc_val - pph_val

            rows_data.append({
                "target_tahunan_fmt": f"Rp {int(round(target_tahunan)):,}".replace(",", "."),
                "target_tahunan_num": target_tahunan,
                "incentive_pct_str": f"{inc_pct:g}%",
                "incentive_pct_num": inc_pct,
                "incentive_val_fmt": f"{int(round(inc_val)):,}".replace(",", "."),
                "incentive_val_num": inc_val,
                "pph_pct_str": f"{pph_pct:g}%",
                "pph_pct_num": pph_pct,
                "pph_val_fmt": f"{int(round(pph_val)):,}".replace(",", "."),
                "pph_val_num": pph_val,
                "netto_val_fmt": f"{int(round(netto_val)):,}".replace(",", "."),
                "netto_val_num": netto_val,
            })

    # Fallback if no target rows available
    if not rows_data:
        raw_nt = form_data.get("nilai_target", 250000000.0)
        try:
            t_bln = float(re.sub(r"[^\d.-]", "", str(raw_nt)) or 250000000.0)
        except Exception:
            t_bln = 250000000.0
        target_tahunan = t_bln * 12.0
        inc_pct = 7.0
        inc_val = target_tahunan * (inc_pct / 100.0)
        pph_pct = 15.0
        pph_val = inc_val * (pph_pct / 100.0)
        netto_val = inc_val - pph_val

        rows_data.append({
            "target_tahunan_fmt": f"Rp {int(round(target_tahunan)):,}".replace(",", "."),
            "target_tahunan_num": target_tahunan,
            "incentive_pct_str": f"{inc_pct:g}%",
            "incentive_pct_num": inc_pct,
            "incentive_val_fmt": f"{int(round(inc_val)):,}".replace(",", "."),
            "incentive_val_num": inc_val,
            "pph_pct_str": f"{pph_pct:g}%",
            "pph_pct_num": pph_pct,
            "pph_val_fmt": f"{int(round(pph_val)):,}".replace(",", "."),
            "pph_val_num": pph_val,
            "netto_val_fmt": f"{int(round(netto_val)):,}".replace(",", "."),
            "netto_val_num": netto_val,
        })

    return rows_data



COMPANY_PROFILES = {
    "PT ANUGRAH CEMERLANG ABADI": {
        "short_code": "ACA",
        "display_name": "PT. ANUGRAH CEMERLANG ABADI",
        "director_name": "Alvin Steven",
        "director_title": "Direktur",
        "factory_address": "Jl. Industri Raya No. 8 RT 003 RW 004 Budi Mulya Cikupa Kab Tangerang Banten 15710",
        "bank_name": "BCA Cimahi – Bandung",
        "bank_account_no": "139 9183 888 (IDR)",
        "bank_account_name": "PT. ANUGRAH CEMERLANG ABADI",
        "court_jurisdiction": "Kantor Panitera Pengadilan Negeri Bale Bandung",
        "logo_filename": "aca.png",
    },
    "PT BANGUN CIPTA PRIMATARA": {
        "short_code": "BCP",
        "display_name": "PT. BANGUN CIPTA PRIMATARA",
        "director_name": "Alvin Steven",
        "director_title": "Direktur",
        "factory_address": "Kawasan Industri Gandasari, Jl. Raya Industri No. 12, Tangerang",
        "bank_name": "BCA Cimahi – Bandung",
        "bank_account_no": "139.9888.777 (IDR)",
        "bank_account_name": "PT. BANGUN CIPTA PRIMATARA",
        "court_jurisdiction": "Kantor Panitera Pengadilan Negeri Tangerang",
        "logo_filename": "bcp.png",
    },
    "PT BESTARI MULIA": {
        "short_code": "BM",
        "display_name": "PT. BESTARI MULIA",
        "director_name": "Alvin Steven",
        "director_title": "Direktur",
        "factory_address": "Jl. Industri Raya Keboharan KM 25 Keboharan Krian, Kab Sidoarjo Jawa Timur 61262",
        "bank_name": "BCA Cimahi – Bandung",
        "bank_account_no": "139 8075 888 (IDR)",
        "bank_account_name": "PT. BESTARI MULIA",
        "court_jurisdiction": "Kantor Panitera Pengadilan Negeri Surabaya",
        "logo_filename": "bm.png",
    },
    "PT CEMERLANG ABADI MULIA": {
        "short_code": "CAM",
        "display_name": "PT. CEMERLANG ABADI MULIA",
        "director_name": "Alvin Steven",
        "director_title": "Direktur",
        "factory_address": "Jl. Industri Raya No. 8 RT 003 RW 004 Budi Mulya Cikupa Kab Tangerang Banten 15710",
        "bank_name": "BCA Cimahi – Bandung",
        "bank_account_no": "139 9183 888 (IDR)",
        "bank_account_name": "PT. CEMERLANG ABADI MULIA",
        "court_jurisdiction": "Kantor Panitera Pengadilan Negeri Bale Bandung",
        "logo_filename": "cam.png",
    },
    "PT ROYAL ABADI SEJAHTERA": {
        "short_code": "RAS",
        "display_name": "PT. ROYAL ABADI SEJAHTERA",
        "director_name": "Alvin Steven",
        "director_title": "Direktur",
        "factory_address": "Jl. Raya Cimareme No. 275 Cimareme, Ngamprah Kabupaten Bandung Barat, Jawa Barat 40552",
        "bank_name": "BCA Cimahi – Bandung",
        "bank_account_no": "139 8826 999 (IDR)",
        "bank_account_name": "PT. ROYAL ABADI SEJAHTERA",
        "court_jurisdiction": "Kantor Panitera Pengadilan Negeri Bale Bandung",
        "logo_filename": "ras.png",
    },
}

BRAND_DISCOUNT_RULES = {
    "LADY": {"md1": "40%", "md2": "10%", "mtop": "5%", "mtop_ket": "TOP"},
    "ELITE": {"md1": "40%", "md2": "10%", "mtop": "5%", "mtop_ket": "TOP"},
    "SERENITY": {"md1": "40%", "md2": "5.5%", "mtop": "5%", "mtop_ket": "TOP"},
    "CLASSIC": {"md1": "40%", "md2": "5.5%", "mtop": "5%", "mtop_ket": "TOP"},
    "ROYAL": {"md1": "30%", "md2": "40%", "mtop": "—", "mtop_ket": "—"},
}


def get_brand_default_discount_rows(brand_name: str) -> list:
    """Return default 3 fixed discount rows (MD1, MD2, MTOP) for a given brand."""
    b = str(brand_name or "").strip().upper()
    rule = BRAND_DISCOUNT_RULES["LADY"]
    if "ROYAL" in b or "FOAM" in b:
        rule = BRAND_DISCOUNT_RULES["ROYAL"]
    elif "SERENITY" in b:
        rule = BRAND_DISCOUNT_RULES["SERENITY"]
    elif "CLASSIC" in b:
        rule = BRAND_DISCOUNT_RULES["CLASSIC"]
    elif "ELITE" in b:
        rule = BRAND_DISCOUNT_RULES["ELITE"]
    elif "LADY" in b:
        rule = BRAND_DISCOUNT_RULES["LADY"]

    return [
        {"komponen": "MD1", "nilai": rule["md1"], "tipe": "Persentase", "keterangan": "—"},
        {"komponen": "MD2", "nilai": rule["md2"], "tipe": "Persentase", "keterangan": "—"},
        {"komponen": "MTOP", "nilai": rule["mtop"], "tipe": "Persentase", "keterangan": rule["mtop_ket"]},
    ]



def normalize_company_key(company_name: str, brand: str = "", user=None) -> str:
    """Normalize user, form input, brand, or user profile to canonical company key."""
    candidates = []
    if company_name:
        candidates.append(str(company_name))
    if brand:
        candidates.append(str(brand))

    # Check user or submitter profile & groups
    if user:
        ep = getattr(user, "employee_profile", None)
        if ep and getattr(ep, "company", None):
            candidates.append(str(ep.company))
        if hasattr(user, "groups"):
            try:
                for g in user.groups.all():
                    candidates.append(str(g.name))
            except Exception:
                pass

    joined = " ".join(candidates).strip().upper()

    # Check BCP / Bangun Cipta Primatara
    if any(k in joined for k in ["PRIMATARA", "BANGUN CIPTA", "BCP"]):
        return "PT BANGUN CIPTA PRIMATARA"

    # Check BM / Bestari Mulia
    if any(k in joined for k in ["BESTARI", "BESTARI MULIA", "BM"]):
        return "PT BESTARI MULIA"

    # Check CAM / Cemerlang Abadi Mulia
    if any(k in joined for k in ["ABADI MULIA", "CEMERLANG ABADI MULIA", "CAM"]):
        return "PT CEMERLANG ABADI MULIA"

    # Check RAS / Royal Abadi Sejahtera / Royal Foam / Classic
    if any(k in joined for k in ["SEJAHTERA", "RAS", "ROYAL", "FOAM", "CLASSIC"]):
        return "PT ROYAL ABADI SEJAHTERA"

    # Check ACA / Anugrah / Elite / Lady Americana / Serenity
    if any(k in joined for k in ["ANUGRAH", "ANUGERAH", "ACA", "CEMERLAH", "LADY", "ELITE", "SERENITY"]):
        return "PT ANUGRAH CEMERLANG ABADI"

    return "PT ROYAL ABADI SEJAHTERA"


def resolve_company_profile(form_data=None, submission=None, user=None) -> dict:
    """
    Resolve corporate profile comprehensively:
    1. Check submission.form_data['perusahaan']
    2. Check submission.form_data['brand']
    3. Check submission.submitter or user employee_profile & groups
    """
    fd = form_data or (submission.form_data if submission else {}) or {}
    company_val = fd.get("perusahaan", "")
    brand_val = fd.get("brand", "")
    active_user = user or (submission.submitter if submission else None)

    key = normalize_company_key(company_val, brand=brand_val, user=active_user)
    base_prof = COMPANY_PROFILES.get(key, COMPANY_PROFILES["PT ANUGRAH CEMERLANG ABADI"])
    prof = dict(base_prof)
    cabang_val = fd.get("cabang")
    kota_val = fd.get("kota") or fd.get("kota_penandatanganan")
    prof["court_jurisdiction"] = resolve_court_jurisdiction(
        cabang=cabang_val,
        kota=kota_val,
        default=prof.get("court_jurisdiction")
    )
    return prof


def get_company_profile(company_name: str = "", submission=None, user=None) -> dict:
    """Get company profile dictionary with fallback to ACA."""
    if submission or user:
        fd = {"perusahaan": company_name} if company_name else None
        return resolve_company_profile(form_data=fd, submission=submission, user=user)
    key = normalize_company_key(company_name)
    return COMPANY_PROFILES.get(key, COMPANY_PROFILES["PT ANUGRAH CEMERLANG ABADI"])


def get_company_logo_abs_path(company_name: str = "", submission=None, user=None) -> str:
    """Get absolute file path of company logo PNG."""
    profile = get_company_profile(company_name, submission=submission, user=user)
    fname = profile.get("logo_filename", "aca.png")
    
    # Try static dirs
    candidates = [
        os.path.join(settings.BASE_DIR, "static", "images", "logos", fname),
        os.path.join(settings.BASE_DIR, "django_forms_workflows", "static", "django_forms_workflows", "img", "logos", fname),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return candidates[0]


def get_company_logo_data_uri(company_name: str = "", submission=None, user=None) -> str:
    """Get base64 data URI of company logo for robust HTML/WeasyPrint/preview embedding."""
    abs_path = get_company_logo_abs_path(company_name, submission=submission, user=user)
    if os.path.exists(abs_path):
        try:
            with open(abs_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
                return f"data:image/png;base64,{b64}"
        except Exception:
            pass
    return ""


def get_company_logo_html(company_name: str = "", max_height: int = 50, submission=None, user=None) -> str:
    """Generate high-resolution <img> tag for Kop Surat logo."""
    data_uri = get_company_logo_data_uri(company_name, submission=submission, user=user)
    profile = get_company_profile(company_name, submission=submission, user=user)
    short_code = profile.get("short_code", "Logo")
    if data_uri:
        return (
            f'<img src="{data_uri}" alt="{short_code} Logo" '
            f'style="max-height: {max_height}px; width: auto; object-fit: contain; display: inline-block; margin: 0 auto 6px auto;" />'
        )
    return ""


def format_official_spk_number(
    nomor,
    brand,
    cabang=None,
    date_val=None,
    company_profile=None,
    perusahaan=None,
) -> str:
    """
    Format official SPK number per Bagian B Poin 1:
    {SEQ:3}/SK-{KODE_PT}/{CABANG}/{BRAND}/{BULAN_ROMAWI}/{TAHUN}
    Examples:
      001/SK-RAS/TANGERANG/LADY/X/2026
      001/SK-RAS/PUSAT/LADY/XI/2026
    """
    import datetime
    if not date_val:
        date_val = datetime.date.today()
    elif isinstance(date_val, datetime.datetime):
        date_val = date_val.date()

    # Nomor SPK 3 digit (001, 002, 010)
    try:
        n_int = int(nomor)
        nomor_str = f"{n_int:03d}"
    except (ValueError, TypeError):
        nomor_str = str(nomor or "001").replace("No.", "").strip()
        if not nomor_str or nomor_str == "____":
            nomor_str = "001"
        elif nomor_str.isdigit():
            nomor_str = f"{int(nomor_str):03d}"

    # Resolve company profile / short_code
    prof = company_profile
    if not prof:
        f_data = {}
        if perusahaan:
            f_data["perusahaan"] = perusahaan
        if brand:
            f_data["brand"] = brand
        if cabang:
            f_data["cabang"] = cabang
        prof = resolve_company_profile(form_data=f_data)

    pt_code = prof.get("short_code", "RAS") if isinstance(prof, dict) else "RAS"

    # Clean Brand Code (5 Official Brands: LADY, ROYAL, SERENITY, ELITE, CLASSIC)
    brand_str = str(brand or "").strip().upper()
    if "LADY" in brand_str:
        brand_clean = "LADY"
    elif "ROYAL" in brand_str or "FOAM" in brand_str:
        brand_clean = "ROYAL"
    elif "SERENITY" in brand_str:
        brand_clean = "SERENITY"
    elif "ELITE" in brand_str:
        brand_clean = "ELITE"
    elif "CLASSIC" in brand_str:
        brand_clean = "CLASSIC"
    elif "GRAND" in brand_str:
        brand_clean = "GRAND"
    else:
        brand_clean = brand_str.split()[0] if brand_str else "LADY"

    # Cabang in UPPERCASE (e.g. TANGERANG, BANDUNG, PUSAT)
    cabang_str = str(cabang or "PUSAT").strip().upper().replace(" ", "")
    if not cabang_str or cabang_str == "—" or cabang_str == "-":
        cabang_str = "PUSAT"

    # Month in Roman Numerals (I..XII)
    m_int = date_val.month if 1 <= date_val.month <= 12 else 1
    m_roman = ROMAN_MONTHS[m_int] if m_int < len(ROMAN_MONTHS) else "X"
    y_str = str(date_val.year)

    return f"{nomor_str}/SK-{pt_code}/{cabang_str}/{brand_clean}/{m_roman}/{y_str}"


def get_next_branch_spk_sequence(cabang: str, year: Optional[int] = None, form_slug: str = "permohonan-kontrak") -> int:
    """
    Menghitung nomor urut sequence SPK berikutnya terisolasi per Cabang dan Tahun.
    Setiap cabang memulai nomor urut dari 1 (001) dan tidak melanjutkan cabang lain.
    Nomor urut = MAX(sequence) + 1 berbasis (Cabang Pemohon + Tahun SPK).
    """
    import datetime
    import re
    from django.apps import apps

    if not year:
        year = datetime.date.today().year

    if not cabang:
        cabang = "PUSAT"

    cabang_clean = str(cabang).strip().upper().replace(" ", "")

    try:
        FormSubmission = apps.get_model("django_forms_workflows", "FormSubmission")
        FormDefinition = apps.get_model("django_forms_workflows", "FormDefinition")
    except Exception:
        return 1

    try:
        form_def = FormDefinition.objects.filter(slug=form_slug).first()
        if not form_def:
            return 1
    except Exception:
        return 1

    submissions = FormSubmission.objects.filter(form_definition=form_def)

    max_seq = 0
    for sub in submissions:
        data = sub.form_data or {}
        spk_str = str(data.get("nomor_spk") or "").strip()
        if not spk_str or "OTOMATIS" in spk_str.upper() or "____" in spk_str:
            continue

        created_year = sub.created_at.year if sub.created_at else year
        if str(year) not in spk_str and created_year != year:
            continue

        sub_cabang = str(data.get("cabang") or "").strip().upper().replace(" ", "")
        cabang_matches = (sub_cabang == cabang_clean) or (f"/{cabang_clean}/" in spk_str.upper())
        if not cabang_matches:
            continue

        m = re.match(r"^(?:No\.\s*)?(\d+)/", spk_str)
        if m:
            try:
                seq_num = int(m.group(1))
                if seq_num > max_seq:
                    max_seq = seq_num
            except (ValueError, TypeError):
                pass

    return max_seq + 1


def resolve_spk_document_template(form_def, submission=None, form_data=None):
    """
    Select appropriate DocumentTemplate:
    Defaults to 'Surat Perjanjian Kerjasama (Standard)' (11 Pasal) since support
    promosi facility is eliminated. If historical submission has is_support_provided,
    maintains fallback compatibility.
    """
    data = form_data or (submission.form_data if submission else {}) or {}
    val = data.get("is_support_provided")
    is_support = val in (True, "True", "true", "1", 1, "on")
    
    if is_support:
        tpl_supp = form_def.document_templates.filter(name="Surat Perjanjian Kerjasama (Support Promosi)", is_active=True).first()
        if tpl_supp:
            return tpl_supp

    tpl = form_def.document_templates.filter(name="Surat Perjanjian Kerjasama (Standard)", is_active=True).first()
    if not tpl:
        tpl = form_def.document_templates.filter(is_default=True, is_active=True).first()
    return tpl


# -----------------------------------------------------------------------------
# Standarisasi Format Tanggal Dokumen Legal SPK ("DD MMMM YYYY")
# -----------------------------------------------------------------------------
MONTH_NAMES_ID = {
    1: "Januari",
    2: "Februari",
    3: "Maret",
    4: "April",
    5: "Mei",
    6: "Juni",
    7: "Juli",
    8: "Agustus",
    9: "September",
    10: "Oktober",
    11: "November",
    12: "Desember",
}

MONTH_MAP_LOWER = {
    "januari": 1, "january": 1, "jan": 1,
    "februari": 2, "february": 2, "feb": 2,
    "maret": 3, "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "mei": 5, "may": 5,
    "juni": 6, "june": 6, "jun": 6,
    "juli": 7, "july": 7, "jul": 7,
    "agustus": 8, "august": 8, "agu": 8, "aug": 8,
    "september": 9, "sep": 9,
    "oktober": 10, "october": 10, "okt": 10, "oct": 10,
    "november": 11, "nov": 11,
    "desember": 12, "december": 12, "des": 12, "dec": 12,
}


def format_date_indonesia(val: Any) -> str:
    """
    Standardize various date representations into official Indonesian format:
    'DD MMMM YYYY' (e.g. '01 November 2026', '31 Oktober 2027').
    """
    if val is None:
        return ""

    if isinstance(val, (datetime.date, datetime.datetime)):
        return f"{val.day:02d} {MONTH_NAMES_ID.get(val.month, '')} {val.year}"

    s = str(val).strip()
    if not s or s in ("—", "-", "None", "null", "undefined"):
        return ""

    # Check ISO format YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS
    m_iso = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m_iso:
        y = int(m_iso.group(1))
        m = int(m_iso.group(2))
        d = int(m_iso.group(3))
        if 1 <= m <= 12:
            return f"{d:02d} {MONTH_NAMES_ID.get(m, '')} {y}"

    # Check Slash format DD/MM/YYYY or D/M/YYYY
    m_slash = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m_slash:
        d = int(m_slash.group(1))
        m = int(m_slash.group(2))
        y = int(m_slash.group(3))
        if 1 <= m <= 12:
            return f"{d:02d} {MONTH_NAMES_ID.get(m, '')} {y}"

    # Check Dash format DD-MM-YYYY
    m_dash = re.match(r"^(\d{1,2})-(\d{1,2})-(\d{4})", s)
    if m_dash:
        d = int(m_dash.group(1))
        m = int(m_dash.group(2))
        y = int(m_dash.group(3))
        if 1 <= m <= 12:
            return f"{d:02d} {MONTH_NAMES_ID.get(m, '')} {y}"

    # Check Text format: e.g. "1 November 2026" or "01 November 2026" or "1 Nov 2026"
    m_text = re.match(r"^(\d{1,2})\s+([a-zA-Z]+)\s+(\d{4})$", s)
    if m_text:
        d = int(m_text.group(1))
        m_name = m_text.group(2).lower()
        y = int(m_text.group(3))
        m_num = MONTH_MAP_LOWER.get(m_name)
        if m_num:
            return f"{d:02d} {MONTH_NAMES_ID.get(m_num, '')} {y}"

    return s

