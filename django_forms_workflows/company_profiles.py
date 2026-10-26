import os
import base64
from pathlib import Path
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

COMPANY_PROFILES = {
    "PT ANUGRAH CEMERLANG ABADI": {
        "short_code": "ACA",
        "display_name": "PT. ANUGRAH CEMERLANG ABADI",
        "director_name": "Alvin Steven",
        "director_title": "Direktur",
        "factory_address": "Jl. Industri Raya No.8 RT.003 RW.004 Budi Mulya Cikupa Kab.Tangerang, Banten",
        "bank_name": "BCA CIMAHI – BANDUNG",
        "bank_account_no": "139.9183.888 (IDR)",
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
        "bank_name": "BCA KCU CIMAHI",
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
        "factory_address": "Kawasan Industri Gandasari, Jl. Raya Industri No. 12, Tangerang",
        "bank_name": "BCA KCU CIMAHI",
        "bank_account_no": "139.9888.777 (IDR)",
        "bank_account_name": "PT. BESTARI MULIA",
        "court_jurisdiction": "Kantor Panitera Pengadilan Negeri Tangerang",
        "logo_filename": "bm.png",
    },
    "PT CEMERLANG ABADI MULIA": {
        "short_code": "CAM",
        "display_name": "PT. CEMERLANG ABADI MULIA",
        "director_name": "Alvin Steven",
        "director_title": "Direktur",
        "factory_address": "Jl. Industri Raya No.8 RT.003 RW.004 Budi Mulya Cikupa Kab.Tangerang, Banten",
        "bank_name": "BCA CIMAHI – BANDUNG",
        "bank_account_no": "139.9183.888 (IDR)",
        "bank_account_name": "PT. CEMERLANG ABADI MULIA",
        "court_jurisdiction": "Kantor Panitera Pengadilan Negeri Bale Bandung",
        "logo_filename": "cam.png",
    },
    "PT ROYAL ABADI SEJAHTERA": {
        "short_code": "RAS",
        "display_name": "PT. ROYAL ABADI SEJAHTERA",
        "director_name": "Alvin Steven",
        "director_title": "Direktur",
        "factory_address": "Kawasan Industri Gandasari, Jl. Raya Industri No. 12, Tangerang",
        "bank_name": "BCA KCU CIMAHI",
        "bank_account_no": "139.9888.777 (IDR)",
        "bank_account_name": "PT. ROYAL ABADI SEJAHTERA",
        "court_jurisdiction": "Kantor Panitera Pengadilan Negeri Tangerang",
        "logo_filename": "ras.png",
    },
}


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

    # Check RAS / Royal Abadi Sejahtera / Royal Foam
    if any(k in joined for k in ["SEJAHTERA", "RAS", "ROYAL", "FOAM"]):
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
    return COMPANY_PROFILES.get(key, COMPANY_PROFILES["PT ANUGRAH CEMERLANG ABADI"])


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


def format_official_spk_number(nomor, brand, cabang=None, date_val=None, company_profile=None) -> str:
    """
    Format official SPK number:
    No. {nomor:04d}/{BRAND}/{CABANG}/{BULAN}/{TAHUN}
    Example: No. 0001/LADY/TANGERANG/10/2026 or No. 0073/ROYAL/TANGERANG/10/2026
    """
    import datetime
    if not date_val:
        date_val = datetime.date.today()
    elif isinstance(date_val, datetime.datetime):
        date_val = date_val.date()
    
    # Nomor SPK 4 digit (0001, 0073)
    try:
        n_int = int(nomor)
        nomor_str = f"{n_int:04d}"
    except (ValueError, TypeError):
        nomor_str = str(nomor or "____").replace("No.", "").strip()
        if not nomor_str:
            nomor_str = "____"
        elif nomor_str.isdigit():
            nomor_str = f"{int(nomor_str):04d}"

    prof = company_profile or get_company_profile(brand)
    brand_str = str(brand or "").strip().upper()
    
    # Clean Brand Code (LADY, ROYAL, SERENITY, ELITE, GRAND)
    if "LADY" in brand_str:
        brand_clean = "LADY"
    elif "ROYAL" in brand_str or "FOAM" in brand_str:
        brand_clean = "ROYAL"
    elif "SERENITY" in brand_str:
        brand_clean = "SERENITY"
    elif "ELITE" in brand_str:
        brand_clean = "ELITE"
    elif "GRAND" in brand_str:
        brand_clean = "GRAND"
    else:
        brand_clean = brand_str.split()[0] if brand_str else "LADY"

    # Cabang in full uppercase (default TANGERANG if none provided)
    cabang_str = str(cabang or "").strip().upper()
    if not cabang_str:
        cabang_str = "TANGERANG"

    # Month as 2 digits (e.g. 10) and year (2026)
    m_str = f"{date_val.month:02d}"
    y_str = str(date_val.year)

    return f"No. {nomor_str}/{brand_clean}/{cabang_str}/{m_str}/{y_str}"


def resolve_spk_document_template(form_def, submission=None, form_data=None):
    """
    Select appropriate DocumentTemplate:
    - If is_support_provided is True -> 'Surat Perjanjian Kerjasama (Support Promosi)' (12 Pasal)
    - If is_support_provided is False -> 'Surat Perjanjian Kerjasama (Standard)' (11 Pasal)
    Falls back to is_default=True template.
    """
    data = form_data or (submission.form_data if submission else {}) or {}
    val = data.get("is_support_provided")
    is_support = val in (True, "True", "true", "1", 1, "on")
    
    target_name = (
        "Surat Perjanjian Kerjasama (Support Promosi)"
        if is_support
        else "Surat Perjanjian Kerjasama (Standard)"
    )
    tpl = form_def.document_templates.filter(name=target_name, is_active=True).first()
    if not tpl:
        tpl = form_def.document_templates.filter(is_default=True, is_active=True).first()
    return tpl

