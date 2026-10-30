"""
Custom template tags and filters for django_forms_workflows.
"""

from django import template
from django.utils.safestring import mark_safe
from django.utils.html import escape

register = template.Library()


@register.filter
def is_boolean_value(value):
    """Return True if value represents a boolean (bool, or string boolean 'true'/'false')."""
    if isinstance(value, bool):
        return True
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "false"):
            return True
    return False


@register.filter(is_safe=True)
def render_boolean_badge(value, label=""):
    """
    Render boolean / checklist values as professional corporate badges:
    - True: Emerald pill with checkmark (Ya / Terpenuhi, or Terkonfirmasi for statements)
    - False: Neutral muted pill (Tidak)
    """
    is_true = False
    if isinstance(value, bool):
        is_true = value
    elif isinstance(value, str):
        v = value.strip().lower()
        if v == "true":
            is_true = True
        elif v == "false":
            is_true = False
        else:
            return escape(value)
    elif isinstance(value, (int, float)):
        if value == 1:
            is_true = True
        elif value == 0:
            is_true = False
        else:
            return escape(str(value))
    else:
        is_true = bool(value)

    label_str = str(label or "").lower()
    is_confirmation = any(w in label_str for w in [
        "saya telah", "memeriksa", "konfirmasi", "pernyataan", "chk_konfirmasi", "draft klausul"
    ])

    if is_true:
        text = "Terkonfirmasi" if is_confirmation else "Ya / Terpenuhi"
        return mark_safe(
            '<span class="badge rounded-pill text-bg-success-subtle border border-success-subtle text-success-emphasis '
            'd-inline-flex align-items-center gap-1 px-2.5 py-1.5 font-monospace-normal" '
            'style="background-color: #ecfdf5 !important; color: #065f46 !important; border-color: #a7f3d0 !important; '
            'font-size: 0.85rem; font-weight: 500;">'
            f'<i class="bi bi-check-lg" style="font-size: 0.95rem;"></i> {text}'
            '</span>'
        )
    else:
        return mark_safe(
            '<span class="badge rounded-pill text-bg-light border border-secondary-subtle text-secondary '
            'd-inline-flex align-items-center gap-1 px-2.5 py-1.5" '
            'style="background-color: #f8fafc !important; color: #64748b !important; border-color: #e2e8f0 !important; '
            'font-size: 0.85rem; font-weight: 500;">'
            '<i class="bi bi-dash" style="font-size: 0.95rem;"></i> Tidak'
            '</span>'
        )


@register.filter
def is_signature(value):
    """Return True if *value* looks like a signature data-URI (PNG)."""
    return isinstance(value, str) and value.startswith("data:image/png;base64,")


@register.filter
def is_callout_note(value):
    """Return True if string contains markdown callout/alert syntax like > [!NOTE] or Status Kontrak note."""
    if not isinstance(value, str):
        return False
    v = value.strip()
    return (
        any(tag in v for tag in ["[!NOTE]", "[!TIP]", "[!WARNING]", "[!IMPORTANT]", "[!CAUTION]", "[!INFO]"])
        or v.startswith(">")
        or "Status Kontrak:" in v
    )


@register.filter(is_safe=True)
def render_callout_note(value):
    """Render a GitHub-style alert callout block as an enterprise Bootstrap alert card."""
    if not value:
        return ""
    import re

    raw = str(value).replace("\r\n", "\n").replace("\r", "\n")

    icon_cls = "bi-info-circle-fill text-info"
    border_cls = "border-info-subtle"

    if "[!WARNING]" in raw or "[!CAUTION]" in raw:
        icon_cls = "bi-exclamation-triangle-fill text-warning"
        border_cls = "border-warning-subtle"
    elif "[!TIP]" in raw:
        icon_cls = "bi-lightbulb-fill text-success"
        border_cls = "border-success-subtle"

    lines = []
    for line in raw.split("\n"):
        stripped = line.strip()
        if stripped.startswith(">"):
            stripped = stripped.lstrip("> ").strip()
        if re.match(r"^\[!(NOTE|TIP|WARNING|IMPORTANT|CAUTION|INFO)\]", stripped, re.IGNORECASE):
            continue
        if stripped:
            lines.append(stripped)

    content = " ".join(lines)
    html = re.sub(r"\*\*(.+?)\*\*", r'<strong class="text-dark">\1</strong>', content)
    html = re.sub(r"\*(.+?)\*", r'<em>\1</em>', html)

    if "Status Kontrak:" in html and '<strong class="text-dark">Status Kontrak:</strong>' not in html:
        html = html.replace("Status Kontrak:", '<strong class="text-dark">Status Kontrak:</strong>')

    card = (
        f'<div class="alert alert-light border {border_cls} d-flex align-items-center gap-2 p-3 my-2 rounded-2">'
        f'<i class="bi {icon_cls} fs-5 flex-shrink-0"></i>'
        f'<div class="text-secondary small mb-0">{html}</div>'
        f'</div>'
    )
    return mark_safe(card)


@register.filter(is_safe=True)
def render_markdown(value):
    """Convert a Markdown string to HTML.

    Uses the ``markdown`` library when installed (with tables, fenced-code
    and nl2br extensions).  Falls back to escaped text with ``<br>`` tags.
    """
    if not value:
        return ""
    if is_callout_note(value):
        return render_callout_note(value)
    try:
        import markdown

        return mark_safe(
            markdown.markdown(
                str(value),
                extensions=["tables", "fenced_code", "nl2br"],
            )
        )
    except ImportError:
        from django.utils.html import escape

        return mark_safe(escape(str(value)).replace("\n", "<br>"))


@register.filter
def get_item(dictionary, key):
    """
    Get an item from a dictionary by key.

    Usage in templates:
        {{ my_dict|get_item:key_variable }}

    This is useful when you need to access a dictionary value
    using a variable as the key, which isn't possible with
    standard Django template syntax.
    """
    if dictionary is None:
        return None
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None


COLUMN_CONFIG = {
    # Data Asset Toko
    "no": {"label": "No", "align": "center", "type": "number", "width": "50px"},
    "keterangan": {"label": "Keterangan", "align": "start", "type": "text"},
    "alamat": {"label": "Alamat", "align": "start", "type": "text"},
    "status": {"label": "Status", "align": "center", "type": "badge", "width": "110px"},

    # Data Market Share
    "bulan": {"label": "Bulan", "align": "start", "type": "text", "width": "110px"},
    "serenity": {"label": "Royal / SERENITY (Rp)", "align": "end", "type": "currency"},
    "kompetitor_1": {"label": "Kompetitor 1 (Rp)", "align": "end", "type": "currency"},
    "kompetitor_2": {"label": "Kompetitor 2 (Rp)", "align": "end", "type": "currency"},
    "kompetitor_3": {"label": "Kompetitor 3 (Rp)", "align": "end", "type": "currency"},
    "kompetitor_4": {"label": "Kompetitor 4 (Rp)", "align": "end", "type": "currency"},

    # Tabel Pasal 3 (Target & Incentive Scheme)
    "target_bulanan": {"label": "Target Bulanan", "align": "end", "type": "currency"},
    "exclude_ppn": {"label": "Ketentuan Pajak", "align": "center", "type": "ppn_boolean", "width": "130px"},
    "incentive_pct": {"label": "Insentif (%)", "align": "center", "type": "percentage", "width": "120px"},

    # Tabel Pasal 6 (Discount Scheme)
    "komponen": {"label": "Komponen", "align": "start", "type": "text"},
    "nilai": {"label": "Nilai", "align": "center", "type": "discount_value", "width": "110px"},
    "tipe": {"label": "Tipe", "align": "center", "type": "discount_type", "width": "110px"},

    # Tabel Pasal 7 (Tier Support Tahunan / Biaya Sewa)
    "target_tahunan": {"label": "Target Tahunan", "align": "end", "type": "currency"},
    "support_pct": {"label": "Dukungan (%)", "align": "center", "type": "percentage", "width": "120px"},
    "pph_pct": {"label": "PPh (%)", "align": "center", "type": "percentage", "width": "100px"},
    "netto": {"label": "Nilai Netto (Rp)", "align": "end", "type": "currency"},
}


def _get_column_info(key):
    if key in COLUMN_CONFIG:
        return COLUMN_CONFIG[key]
    k_lower = key.lower()
    label = key.replace("_", " ").title()
    if any(x in k_lower for x in ["rp", "rupiah", "harga", "biaya", "omset", "target", "netto"]):
        return {"label": label, "align": "end", "type": "currency"}
    elif any(x in k_lower for x in ["pct", "persen", "percent"]):
        return {"label": label, "align": "center", "type": "percentage"}
    elif k_lower in ("no", "nomor", "idx"):
        return {"label": label, "align": "center", "type": "number", "width": "50px"}
    return {"label": label, "align": "start", "type": "text"}


def get_market_share_brand_label(brand_name):
    if not brand_name:
        return "Royal / SERENITY (Rp)"
    b = str(brand_name).strip().upper()
    if "LADY" in b:
        return "LADY (Rp)"
    if "SERENITY" in b:
        return "SERENITY (Rp)"
    if "ROYAL" in b or "FOAM" in b:
        return "ROYAL FOAM (Rp)"
    if "GRAND" in b:
        return "GRAND EXCLUSIVE (Rp)"
    if "ELITE" in b:
        return "ELITE (Rp)"
@register.filter
def whatsapp_phone(val):
    """Normalize Indonesian phone number to WhatsApp international standard (e.g. 6281234567890)."""
    if not val:
        return ""
    import re
    digits = re.sub(r"[^0-9]", "", str(val))
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    elif digits.startswith("62"):
        pass
    elif digits:
        digits = "62" + digits
    return digits


def _is_empty_template(rows):
    """Check if all rows are default templates with no meaningful user input."""
    for r in rows:
        if not isinstance(r, dict):
            continue
        for k, v in r.items():
            if k in ("no", "status", "tipe", "exclude_ppn"):
                continue
            if isinstance(v, (int, float)) and v != 0:
                return False
            if isinstance(v, str) and v.strip() not in ("", "0", "0%"):
                return False
    return True


@register.filter
def is_grid_data(value):
    """Return True if value represents a structured grid (list of dicts or JSON array)."""
    import json
    if value is None or value == "":
        return False
    if isinstance(value, list):
        if not value:
            return True
        return isinstance(value[0], dict)
    if isinstance(value, str):
        v = value.strip()
        if v in ("[]", "[ ]"):
            return True
        if v.startswith("[") and v.endswith("]"):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    if len(parsed) == 0:
                        return True
                    return isinstance(parsed[0], dict)
            except Exception:
                return False
    return False


@register.filter(is_safe=True)
def render_grid_table(value, brand=None):
    """Render structured grid data (list of dicts or JSON array) as a clean corporate table."""
    import json
    import re
    from django.utils.html import escape

    if value is None or value == "":
        return mark_safe('<span class="text-muted">—</span>')

    rows = value
    if isinstance(value, str):
        v_str = value.strip()
        if v_str in ("[]", "[ ]"):
            return mark_safe('<span class="text-muted">—</span>')
        try:
            rows = json.loads(v_str)
        except Exception:
            return escape(str(value))

    if not isinstance(rows, list):
        return escape(str(value))

    if not rows or _is_empty_template(rows):
        return mark_safe('<span class="text-muted">—</span>')

    if not isinstance(rows[0], dict):
        return escape(str(value))

    headers = list(rows[0].keys())

    out = [
        '<div class="table-responsive my-1 border rounded bg-white shadow-sm">'
        '<table class="table table-sm table-hover align-middle mb-0" style="border-collapse: collapse; width: 100%; font-size: 0.85rem;">'
        '<thead>'
        '<tr>'
    ]
    for h in headers:
        cinfo = _get_column_info(h)
        col_label = cinfo["label"]
        if h == "serenity" and brand:
            col_label = get_market_share_brand_label(brand)
        align_class = f"text-{cinfo.get('align', 'start')}"
        width_style = f"width: {cinfo['width']};" if 'width' in cinfo else ""
        out.append(
            f'<th class="text-nowrap {align_class}" '
            f'style="background-color: #f1f5f9; color: #1e293b; padding: 8px 10px; font-size: 0.85rem; '
            f'border: 1px solid #cbd5e1; font-weight: 600; {width_style}">'
            f'{escape(col_label)}</th>'
        )

    out.append('</tr></thead><tbody>')

    for r in rows:
        out.append('<tr>')
        for h in headers:
            cinfo = _get_column_info(h)
            align_class = f"text-{cinfo.get('align', 'start')}"
            col_type = cinfo.get("type", "text")
            val = r.get(h)

            num_style = ""
            if col_type in ("currency", "number"):
                num_style = "font-variant-numeric: tabular-nums;"

            if val is None or val == "":
                cell_html = '<span class="text-muted">—</span>'
            elif col_type == "ppn_boolean":
                if val in (True, "True", "true", 1, "1"):
                    cell_html = '<span class="badge bg-warning-subtle text-dark border border-warning-subtle px-2 py-1">Exclude PPN</span>'
                else:
                    cell_html = '<span class="badge bg-info-subtle text-primary border border-info-subtle px-2 py-1">Include PPN</span>'
            elif col_type == "discount_type":
                s_low = str(val).strip().lower()
                lbl = "Persentase" if s_low in ("percentage", "persentage", "persentase") else ("Nominal" if s_low == "nominal" else str(val))
                cell_html = f'<span class="badge bg-light text-dark border px-2 py-1">{escape(lbl)}</span>'
            elif col_type == "discount_value":
                s = str(val).strip()
                row_tipe = str(r.get("tipe", "")).strip().lower()
                if row_tipe in ("percentage", "persentage", "persentase") or s.endswith("%"):
                    if not s.endswith("%"):
                        try:
                            n = float(s)
                            s = f"{int(n)}%" if n.is_integer() else f"{n:g}%"
                        except (ValueError, TypeError):
                            s = f"{s}%"
                    cell_html = f'<span class="font-monospace fw-semibold">{escape(s)}</span>'
                else:
                    try:
                        n = float(re.sub(r"[^\d.-]", "", s))
                        if n >= 1000:
                            cell_html = f'<span class="font-monospace fw-semibold">Rp {int(round(n)):,}</span>'.replace(",", ".")
                        else:
                            cell_html = escape(s)
                    except Exception:
                        cell_html = escape(s)
            elif col_type == "boolean":
                if val:
                    cell_html = '<span class="badge bg-success-subtle text-success border border-success-subtle px-2 py-1">Ya</span>'
                else:
                    cell_html = '<span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle px-2 py-1">Tidak</span>'
            elif col_type == "badge":
                cell_html = f'<span class="badge bg-light text-dark border px-2 py-1">{escape(str(val))}</span>'
            elif col_type == "currency":
                try:
                    cleaned = re.sub(r"[^\d.-]", "", str(val))
                    num = float(cleaned) if cleaned else 0.0
                    if num == 0:
                        cell_html = '<span class="text-muted">Rp 0</span>'
                    else:
                        cell_html = f'<span class="font-monospace fw-semibold text-dark">Rp {int(round(num)):,}</span>'.replace(",", ".")
                except (ValueError, TypeError):
                    cell_html = escape(str(val))
            elif col_type == "percentage":
                s = str(val).strip()
                if s.endswith("%"):
                    cell_html = f'<span class="font-monospace fw-semibold">{escape(s)}</span>'
                else:
                    try:
                        num = float(s)
                        if num == 0:
                            cell_html = '<span class="text-muted">0%</span>'
                        elif num.is_integer():
                            cell_html = f'<span class="font-monospace fw-semibold">{int(num)}%</span>'
                        else:
                            cell_html = f'<span class="font-monospace fw-semibold">{num:g}%</span>'
                    except (ValueError, TypeError):
                        cell_html = f'<span class="font-monospace fw-semibold">{escape(s)}</span>'
            elif col_type == "number":
                cell_html = f'<span class="fw-semibold text-secondary">{escape(str(val))}</span>'
            else:
                if isinstance(val, (int, float)) and val >= 10000:
                    cell_html = f'<span class="font-monospace">Rp {int(round(val)):,}</span>'.replace(",", ".")
                else:
                    cell_html = escape(str(val))

            out.append(
                f'<td class="py-2 px-3 {align_class}" '
                f'style="padding: 7px 10px; font-size: 0.85rem; border: 1px solid #e2e8f0; vertical-align: middle; {num_style}">'
                f'{cell_html}</td>'
            )
        out.append('</tr>')

    out.append('</tbody></table></div>')

    return mark_safe("".join(out))


@register.inclusion_tag(
    "django_forms_workflows/form_categories.html",
    takes_context=True,
)
def render_form_categories(
    context, grouped_forms, form_url_name="forms_workflows:form_submit"
):
    """
    Render a Bootstrap 5 accordion of forms grouped by category, with support
    for arbitrarily nested sub-categories.

    Usage::

        {% load forms_workflows_tags %}
        {% render_form_categories grouped_forms %}

        {# Override the submit URL name for projects that use a different namespace: #}
        {% render_form_categories grouped_forms form_url_name="form_submit" %}

    ``grouped_forms`` must be a list of category-tree node dicts as produced by
    ``_build_grouped_forms()`` in the ``form_list`` view.  Each node has the shape::

        {
            "category": FormCategory | None,   # None = uncategorised bucket
            "forms":    [FormDefinition, ...], # forms directly under this category
            "children": [node, ...],           # nested sub-category nodes
        }

    ``form_url_name`` is the Django URL name used to build the "Fill Out Form" link.
    Defaults to ``forms_workflows:form_submit`` (the package's own namespace).
    """
    return {
        "grouped_forms": grouped_forms,
        "form_url_name": form_url_name,
        # Forward request so the inclusion template can call {% url %} correctly
        "request": context.get("request"),
    }


@register.filter(name="rupiah_format")
def rupiah_format(value):
    """
    Format scalar integer, float, or numeric string to Indonesian Rupiah accounting standard.
    Example: 80000000 -> 'Rp 80.000.000', '80000000.00' -> 'Rp 80.000.000'
    """
    import re
    if value is None or str(value).strip() in ("", "None", "—", "-"):
        return mark_safe('<span class="text-muted">—</span>')
    s = str(value).strip()
    if s.startswith("Rp ") and "." in s:
        return s
    try:
        cleaned = re.sub(r"[^\d.-]", "", s)
        if not cleaned:
            return escape(s)
        num = float(cleaned)
        if num == 0:
            return "Rp 0"
        return f"Rp {int(round(num)):,}".replace(",", ".")
    except (ValueError, TypeError):
        return escape(s)


@register.filter(name="format_rupiah")
def format_rupiah(value):
    """Alias for rupiah_format."""
    return rupiah_format(value)


@register.filter(name="format_date_indonesia")
def format_date_indonesia(value):
    """Format any date representation into official Indonesian format: 'DD MMMM YYYY'."""
    from django_forms_workflows.company_profiles import format_date_indonesia as _fmt
    return _fmt(value)


@register.filter(name="render_komponen_biaya_badges", is_safe=True)
def render_komponen_biaya_badges(value):
    """
    Render standardized 5-component support checklist as clean enterprise badges.
    Supports JSON array, list, or legacy comma-separated text.
    """
    from django_forms_workflows.company_profiles import parse_komponen_biaya_list
    items = parse_komponen_biaya_list(value)
    if not items:
        return mark_safe('<span class="text-muted">—</span>')

    badges = []
    for item in items:
        badges.append(
            f'<span class="badge bg-slate-100 text-dark border border-slate-300 fw-medium px-2.5 py-1" '
            f'style="background-color: #f1f5f9; color: #1e293b; font-size: 12px; border-color: #cbd5e1 !important;">'
            f'<i class="bi bi-check2 text-primary me-1"></i>{escape(item)}</span>'
        )
    return mark_safe(f'<div class="d-flex flex-wrap gap-2 mt-1">{"".join(badges)}</div>')


