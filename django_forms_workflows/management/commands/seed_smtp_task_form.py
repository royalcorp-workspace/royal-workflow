"""
Management command: seed_smtp_task_form

Registers the official Form Definition and Workflow for:
- Task: 'Konfigurasi Service SMTP & Environment Variables'
- Description: 'Menghubungkan Django core dengan mail provider perusahaan.'
Complete with sections, parameters, and 2-stage workflow approval rules.

Usage:
    python manage.py seed_smtp_task_form
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django_forms_workflows.models import (
    FormCategory,
    FormDefinition,
    FormField,
    WorkflowDefinition,
    WorkflowStage,
    StageApprovalGroup,
    NotificationRule,
    FormSubmission,
)

User = get_user_model()


class Command(BaseCommand):
    help = "Seed the 'Konfigurasi Service SMTP & Environment Variables' form & workflow definition."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("=================================================================")
        self.stdout.write("Seeding Form: 'Konfigurasi Service SMTP & Environment Variables'")
        self.stdout.write("=================================================================")

        # 1. Pastikan Groups untuk Approver
        group_it_lead, _ = Group.objects.get_or_create(name="IT Lead & DevOps")
        group_it_head, _ = Group.objects.get_or_create(name="Head of IT & System Security")

        # Assign user admin ke grup approver agar siap digunakan
        admin_user = User.objects.filter(username="admin").first()
        if admin_user:
            admin_user.groups.add(group_it_lead, group_it_head)

        # 2. Form Category
        category, _ = FormCategory.objects.get_or_create(
            slug="it-infrastructure",
            defaults={
                "name": "IT & Infrastructure",
                "description": "Layanan konfigurasi server, integrasi core, dan infrastruktur IT perusahaan.",
                "icon": "bi-hdd-network",
                "order": 20,
            },
        )
        self.stdout.write(f"Category: {category.name}")

        # 3. Form Definition
        form_slug = "konfigurasi-service-smtp"
        form, created = FormDefinition.objects.get_or_create(
            slug=form_slug,
            defaults={
                "name": "Konfigurasi Service SMTP & Environment Variables",
                "category": category,
                "description": "Menghubungkan Django core dengan mail provider perusahaan.",
                "instructions": (
                    "Formulir pencatatan, pengujian, dan validasi konfigurasi service SMTP serta "
                    "environment variables untuk menghubungkan Django core dengan mail provider perusahaan."
                ),
                "is_active": True,
                "is_listed": True,
                "allow_save_draft": True,
                "allow_resubmit": True,
            },
        )

        if not created:
            form.name = "Konfigurasi Service SMTP & Environment Variables"
            form.description = "Menghubungkan Django core dengan mail provider perusahaan."
            form.instructions = (
                "Formulir pencatatan, pengujian, dan validasi konfigurasi service SMTP serta "
                "environment variables untuk menghubungkan Django core dengan mail provider perusahaan."
            )
            form.category = category
            form.is_active = True
            form.is_listed = True
            form.save()
            # Hapus fields lama untuk update skema bersih jika diperlukan
            form.fields.all().delete()
            self.stdout.write("Updated existing FormDefinition.")
        else:
            self.stdout.write("Created new FormDefinition.")

        # 4. Form Fields
        field_specs = [
            # ── SECTION 1: Informasi Task & Target Environment ──
            {
                "field_name": "section_task_info",
                "field_label": "1. Informasi Task & Target Environment",
                "field_type": "section",
                "order": 1,
                "width": "full",
            },
            {
                "field_name": "nama_task",
                "field_label": "Nama Task",
                "field_type": "text",
                "required": True,
                "order": 2,
                "width": "full",
                "placeholder": "contoh: Konfigurasi Service SMTP Microsoft 365",
                "help_text": "Judul identifikasi task integrasi email pada sistem.",
            },
            {
                "field_name": "deskripsi_task",
                "field_label": "Deskripsi Task",
                "field_type": "textarea",
                "required": True,
                "order": 3,
                "width": "full",
                "placeholder": "Uraian lingkup pekerjaan menghubungkan Django core dengan mail provider...",
                "help_text": "Uraian lingkup pekerjaan menghubungkan Django core dengan mail provider.",
            },
            {
                "field_name": "target_environment",
                "field_label": "Target Environment",
                "field_type": "select",
                "required": True,
                "order": 4,
                "width": "half",
                "choices": [
                    {"value": "Development", "label": "Development / Local Sandbox"},
                    {"value": "Staging", "label": "Staging (UAT Server)"},
                    {"value": "Production", "label": "Production (Live System)"},
                ],
                "default_value": "Production",
            },
            {
                "field_name": "inisiator_task",
                "field_label": "Inisiator / Penanggung Jawab Task",
                "field_type": "text",
                "required": True,
                "order": 5,
                "width": "half",
                "placeholder": "contoh: IT DevOps & Infrastructure Team",
            },

            # ── SECTION 2: Parameter SMTP & Environment Variables ──
            {
                "field_name": "section_smtp_params",
                "field_label": "2. Parameter Konfigurasi SMTP & Environment Variables",
                "field_type": "section",
                "order": 6,
                "width": "full",
            },
            {
                "field_name": "mail_provider",
                "field_label": "Mail Provider Perusahaan",
                "field_type": "select",
                "required": True,
                "order": 7,
                "width": "half",
                "choices": [
                    {"value": "Microsoft 365 / Office 365", "label": "Microsoft 365 / Office 365 Exchange"},
                    {"value": "Google Workspace", "label": "Google Workspace (Gmail Enterprise)"},
                    {"value": "Internal Postfix / Zimbra Relay", "label": "Internal Postfix / Zimbra Relay"},
                    {"value": "Amazon SES", "label": "Amazon Simple Email Service (SES)"},
                    {"value": "Mailgun / SendGrid", "label": "Mailgun / SendGrid Transactional API"},
                ],
                "default_value": "Microsoft 365 / Office 365",
            },
            {
                "field_name": "email_host",
                "field_label": "EMAIL_HOST",
                "field_type": "text",
                "required": True,
                "order": 8,
                "width": "half",
                "placeholder": "contoh: smtp.office365.com",
                "help_text": "Hostname FQDN server SMTP mail provider.",
            },
            {
                "field_name": "email_port",
                "field_label": "EMAIL_PORT",
                "field_type": "number",
                "required": True,
                "order": 9,
                "width": "half",
                "default_value": "587",
                "placeholder": "587",
                "help_text": "Port SMTP (587 untuk TLS STARTTLS, 465 untuk SSL).",
            },
            {
                "field_name": "email_security",
                "field_label": "Protokol Keamanan (TLS / SSL)",
                "field_type": "select",
                "required": True,
                "order": 10,
                "width": "half",
                "choices": [
                    {"value": "TLS", "label": "STARTTLS (Port 587 - Direkomendasikan)"},
                    {"value": "SSL", "label": "Implicit SSL/TLS (Port 465)"},
                    {"value": "Plain", "label": "Plain Text (Port 25 - Internal Relay Only)"},
                ],
                "default_value": "TLS",
            },
            {
                "field_name": "email_host_user",
                "field_label": "EMAIL_HOST_USER",
                "field_type": "text",
                "required": True,
                "order": 11,
                "width": "half",
                "placeholder": "contoh: notifications@royalcorp.co.id",
                "help_text": "Username / email autentikasi akun pengirim di mail server.",
            },
            {
                "field_name": "default_from_email",
                "field_label": "DEFAULT_FROM_EMAIL",
                "field_type": "text",
                "required": True,
                "order": 12,
                "width": "half",
                "placeholder": "contoh: Royal Workflow <notifications@royalcorp.co.id>",
                "help_text": "Header From default pada seluruh email notifikasi sistem.",
            },
            {
                "field_name": "server_email",
                "field_label": "SERVER_EMAIL (Notifikasi Error/Alerts)",
                "field_type": "text",
                "required": False,
                "order": 13,
                "width": "half",
                "placeholder": "contoh: it-alerts@royalcorp.co.id",
                "help_text": "Alamat email pengirim laporan error internal Django.",
            },
            {
                "field_name": "email_timeout",
                "field_label": "EMAIL_TIMEOUT (Detik)",
                "field_type": "number",
                "required": False,
                "order": 14,
                "width": "half",
                "default_value": "10",
                "placeholder": "10",
                "help_text": "Batas waktu tunggu koneksi soket SMTP (default 10 detik).",
            },

            # ── SECTION 3: Verifikasi Pengujian & Dokumentasi ──
            {
                "field_name": "section_verification",
                "field_label": "3. Verifikasi Pengujian & Catatan Keamanan",
                "field_type": "section",
                "order": 15,
                "width": "full",
            },
            {
                "field_name": "test_recipient_email",
                "field_label": "Email Penerima Uji Coba (Test Recipient)",
                "field_type": "email",
                "required": False,
                "order": 16,
                "width": "half",
                "placeholder": "contoh: admin@royalcorp.co.id",
                "help_text": "Email tujuan untuk membuktikan pengiriman pesan uji coba.",
            },
            {
                "field_name": "test_status",
                "field_label": "Status Pengujian Koneksi SMTP",
                "field_type": "select",
                "required": True,
                "order": 17,
                "width": "half",
                "choices": [
                    {"value": "Verified", "label": "Berhasil Terverifikasi (Connection & Handshake OK)"},
                    {"value": "Pending", "label": "Menunggu Uji Coba di Server Tujuan"},
                    {"value": "Failed", "label": "Gagal Terhubung (Periksa Kredensial / Firewall)"},
                ],
                "default_value": "Pending",
            },
            {
                "field_name": "catatan_implementasi",
                "field_label": "Catatan Teknis Implementasi & Keamanan",
                "field_type": "textarea",
                "required": False,
                "order": 18,
                "width": "full",
                "placeholder": "Catatan teknis implementasi, konfigurasi firewall, atau pengaturan SPF/DKIM...",
                "help_text": "Catatan dokumentasi, konfigurasi firewall, atau pengaturan SPF/DKIM.",
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
                choices=spec.get("choices", None),
                default_value=spec.get("default_value", ""),
                placeholder=spec.get("placeholder", ""),
                help_text=spec.get("help_text", ""),
            )
        self.stdout.write(f"Created {len(field_specs)} form fields.")

        # 5. Workflow Definition & Stages
        workflow, _ = WorkflowDefinition.objects.get_or_create(
            form_definition=form,
            defaults={
                "name_label": "Workflow Persetujuan Konfigurasi SMTP",
                "requires_approval": True,
                "approval_deadline_days": 3,
                "send_reminder_after_days": 1,
            },
        )
        workflow.requires_approval = True
        workflow.approval_deadline_days = 3
        workflow.save()

        # Stage 1: Review IT Lead / DevOps
        stage_1, _ = WorkflowStage.objects.get_or_create(
            workflow=workflow,
            order=1,
            defaults={
                "name": "Review IT Lead & DevOps",
                "approval_logic": "any",
            },
        )
        stage_1.name = "Review IT Lead & DevOps"
        stage_1.approval_logic = "any"
        stage_1.save()
        StageApprovalGroup.objects.update_or_create(
            stage=stage_1,
            group=group_it_lead,
            role="approval",
            defaults={"position": 1},
        )

        # Stage 2: Verifikasi & Pengesahan Head of IT
        stage_2, _ = WorkflowStage.objects.get_or_create(
            workflow=workflow,
            order=2,
            defaults={
                "name": "Verifikasi & Pengesahan Head of IT",
                "approval_logic": "any",
            },
        )
        stage_2.name = "Verifikasi & Pengesahan Head of IT"
        stage_2.approval_logic = "any"
        stage_2.save()
        StageApprovalGroup.objects.update_or_create(
            stage=stage_2,
            group=group_it_head,
            role="approval",
            defaults={"position": 1},
        )

        self.stdout.write("Configured 2-Stage Approval Workflow (IT Lead -> Head of IT).")

        # 6. Notification Rules (Email triggers with Rich Enterprise HTML Layout)
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
      <div class="email-brand"><i class="bi bi-hdd-network"></i> ROYAL WORKFLOW &bull; IT SERVICE MANAGEMENT</div>
      <h1 class="email-title">Persetujuan Diperlukan: Konfigurasi Service SMTP</h1>
    </div>
    <div class="email-body">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 16px;">
        <span class="badge-pill badge-pending">&bull; Menunggu Review IT Lead &amp; DevOps</span>
        <span style="font-size: 12px; color: #64748b; font-family: monospace;">Ref: #{{{{ submission.id }}}}</span>
      </div>
      <p style="font-size: 14px; color: #334155; line-height: 1.6; margin-top: 0;">
        Halo <strong>{{{{ approver.get_full_name|default:approver.username|default:"Tim Reviewer" }}}}</strong>,
      </p>
      <p style="font-size: 13.5px; color: #475569; line-height: 1.6;">
        Terdapat pengajuan task integrasi mail provider yang membutuhkan evaluasi dan persetujuan Anda:
      </p>

      <table class="info-table">
        <tr>
          <td class="info-label">Nama Task</td>
          <td class="info-value"><strong>{{{{ form_data.nama_task|default:"Konfigurasi Service SMTP &amp; Environment Variables" }}}}</strong></td>
        </tr>
        <tr>
          <td class="info-label">Target Server</td>
          <td class="info-value"><span class="code-pill">{{{{ form_data.target_environment|default:"Production" }}}}</span></td>
        </tr>
        <tr>
          <td class="info-label">Inisiator Task</td>
          <td class="info-value">{{{{ form_data.inisiator_task|default:submission.submitter.get_full_name|default:submission.submitter.username }}}}</td>
        </tr>
        <tr>
          <td class="info-label">Mail Provider</td>
          <td class="info-value">{{{{ form_data.mail_provider|default:"Microsoft 365 / Office 365" }}}}</td>
        </tr>
        <tr>
          <td class="info-label">EMAIL_HOST</td>
          <td class="info-value"><span class="code-pill">{{{{ form_data.email_host|default:"smtp.office365.com" }}}}</span></td>
        </tr>
        <tr>
          <td class="info-label">EMAIL_PORT</td>
          <td class="info-value"><span class="code-pill">Port {{{{ form_data.email_port|default:"587" }}}}</span> ({{{{ form_data.email_security|default:"TLS" }}}})</td>
        </tr>
        <tr>
          <td class="info-label">EMAIL_HOST_USER</td>
          <td class="info-value"><span class="code-pill">{{{{ form_data.email_host_user|default:"-" }}}}</span></td>
        </tr>
        <tr>
          <td class="info-label">DEFAULT_FROM_EMAIL</td>
          <td class="info-value">{{{{ form_data.default_from_email|default:"Royal Workflow <notifications@royalcorp.co.id>" }}}}</td>
        </tr>
        <tr>
          <td class="info-label">Status Uji Coba</td>
          <td class="info-value" style="color: #16a34a; font-weight: 600;">&#10004; {{{{ form_data.test_status|default:"Verified" }}}}</td>
        </tr>
      </table>

      <div style="background-color: #f8fafc; border-left: 3px solid #1e3a8a; padding: 12px 14px; border-radius: 4px; font-size: 12.5px; color: #475569; margin: 16px 0;">
        <strong>Deskripsi:</strong><br>
        {{{{ form_data.deskripsi_task|default:"Menghubungkan Django core dengan mail provider perusahaan." }}}}
      </div>

      <div style="text-align: center; margin: 24px 0 16px;">
        <a href="{{{{ approval_url }}}}" class="btn-cta">&#10148; Review &amp; Approve di Sistem Web</a>
      </div>
      <p style="font-size: 12px; color: #94a3b8; text-align: center; margin: 0;">
        Atau buka langsung via tautan: <a href="{{{{ approval_url }}}}" style="color: #1e3a8a;">{{{{ approval_url }}}}</a>
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
      <div class="email-brand">ROYAL WORKFLOW &bull; KONFIRMASI PENGAJUAN</div>
      <h1 class="email-title">Pengajuan Task Berhasil Diterima</h1>
    </div>
    <div class="email-body">
      <div style="margin-bottom: 16px;">
        <span class="badge-pill badge-pending">&bull; Sedang Diproses (Tahap Review IT Lead)</span>
      </div>
      <p style="font-size: 14px; color: #334155; line-height: 1.6; margin-top: 0;">
        Halo <strong>{{{{ submission.submitter.get_full_name|default:submission.submitter.username }}}}</strong>,
      </p>
      <p style="font-size: 13.5px; color: #475569; line-height: 1.6;">
        Pengajuan task <strong>{{{{ form_data.nama_task|default:"Konfigurasi Service SMTP &amp; Environment Variables" }}}}</strong> telah berhasil masuk ke antrean sistem.
      </p>

      <table class="info-table">
        <tr>
          <td class="info-label">Nomor Pengajuan</td>
          <td class="info-value"><strong>#{{{{ submission.id }}}}</strong></td>
        </tr>
        <tr>
          <td class="info-label">Target Server</td>
          <td class="info-value">{{{{ form_data.target_environment|default:"Production" }}}}</td>
        </tr>
        <tr>
          <td class="info-label">Mail Provider</td>
          <td class="info-value">{{{{ form_data.mail_provider|default:"Microsoft 365" }}}}</td>
        </tr>
        <tr>
          <td class="info-label">Host &amp; Port</td>
          <td class="info-value"><span class="code-pill">{{{{ form_data.email_host }}}}</span> : <span class="code-pill">{{{{ form_data.email_port }}}}</span></td>
        </tr>
      </table>

      <div style="text-align: center; margin: 24px 0 16px;">
        <a href="{{{{ submission_url }}}}" class="btn-cta">Lihat Status Pengajuan di Web</a>
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
      <div class="email-brand" style="color: #a7f3d0;">ROYAL WORKFLOW &bull; PENGESAHAN SELESAI</div>
      <h1 class="email-title">Konfigurasi SMTP Telah Disetujui Penuh</h1>
    </div>
    <div class="email-body">
      <div style="margin-bottom: 16px;">
        <span class="badge-pill badge-approved">&#10004; APPROVED (Disetujui Penuh)</span>
      </div>
      <p style="font-size: 14px; color: #334155; line-height: 1.6; margin-top: 0;">
        Halo <strong>{{{{ submission.submitter.get_full_name|default:submission.submitter.username }}}}</strong>,
      </p>
      <p style="font-size: 13.5px; color: #475569; line-height: 1.6;">
        Task <strong>{{{{ form_data.nama_task|default:"Konfigurasi Service SMTP &amp; Environment Variables" }}}}</strong> telah diverifikasi dan disetujui penuh oleh tim Head of IT &amp; System Security.
      </p>

      <table class="info-table">
        <tr>
          <td class="info-label">Target Server</td>
          <td class="info-value"><strong>{{{{ form_data.target_environment|default:"Production" }}}}</strong></td>
        </tr>
        <tr>
          <td class="info-label">Status Koneksi</td>
          <td class="info-value" style="color:#16a34a; font-weight:bold;">&#10004; Aktif &amp; Terverifikasi</td>
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
      <div class="email-brand" style="color: #fde68a;">&#9200; ROYAL WORKFLOW &bull; REMINDER SISTEM</div>
      <h1 class="email-title">PENGINGAT: Persetujuan Menunggu Tindakan Anda</h1>
    </div>
    <div class="email-body">
      <div style="margin-bottom: 16px;">
        <span class="badge-pill badge-pending" style="background-color: #fef3c7; color: #b45309; border-color: #fde68a;">&#9888; Action Required: Approval Reminder</span>
      </div>
      <p style="font-size: 14px; color: #334155; line-height: 1.6; margin-top: 0;">
        Halo <strong>{{{{ approver.get_full_name|default:approver.username|default:"Tim Reviewer" }}}}</strong>,
      </p>
      <p style="font-size: 13.5px; color: #475569; line-height: 1.6;">
        Ini adalah pengingat ramah bahwa pengajuan task integrasi mail server berikut masih <strong>menunggu evaluasi dan persetujuan</strong> Anda:
      </p>

      <table class="info-table">
        <tr>
          <td class="info-label">Nama Task</td>
          <td class="info-value"><strong>{{{{ form_data.nama_task|default:"Konfigurasi Service SMTP &amp; Environment Variables" }}}}</strong></td>
        </tr>
        <tr>
          <td class="info-label">Target Server</td>
          <td class="info-value"><span class="code-pill">{{{{ form_data.target_environment|default:"Production" }}}}</span></td>
        </tr>
        <tr>
          <td class="info-label">Mail Provider</td>
          <td class="info-value">{{{{ form_data.mail_provider|default:"Microsoft 365 / Office 365" }}}}</td>
        </tr>
        <tr>
          <td class="info-label">Diajukan Pada</td>
          <td class="info-value">{{{{ submission.submitted_at|date:"d M Y H:i" }}}}</td>
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
                "subject_template": "[Royal Workflow] Task {nama_task} Berhasil Diajukan",
                "body_template": submission_received_html.strip(),
            },
        )
        NotificationRule.objects.update_or_create(
            workflow=workflow,
            event="approval_request",
            stage=stage_1,
            defaults={
                "notify_stage_groups": True,
                "notify_stage_assignees": True,
                "subject_template": "[Action Required] Persetujuan Konfigurasi SMTP: {nama_task}",
                "body_template": approval_request_html.strip(),
            },
        )
        NotificationRule.objects.update_or_create(
            workflow=workflow,
            event="approval_reminder",
            stage=stage_1,
            defaults={
                "notify_stage_groups": True,
                "notify_stage_assignees": True,
                "subject_template": "[Reminder] Persetujuan Tertunda: {nama_task} (ID #{submission_id})",
                "body_template": approval_reminder_html.strip(),
            },
        )
        NotificationRule.objects.update_or_create(
            workflow=workflow,
            event="workflow_approved",
            stage=None,
            defaults={
                "notify_submitter": True,
                "subject_template": "[Approved] Konfigurasi SMTP & Env Vars Telah Disetujui Penuh",
                "body_template": workflow_approved_html.strip(),
            },
        )
        self.stdout.write("Configured NotificationRules for Submission, Approval, Reminder, and Final.")

        # 7. Bersihkan submission lama jika ada
        deleted_count, _ = FormSubmission.objects.filter(form_definition=form).delete()
        if deleted_count > 0:
            self.stdout.write(f"Membersihkan {deleted_count} submission data lama.")

        self.stdout.write(
            self.style.SUCCESS(
                f"[SUCCESS] Form Definition 'Konfigurasi Service SMTP & Environment Variables' siap!\n"
                f"  • Slug: {form.slug}\n"
                f"  • URL Form: /forms/{form.slug}/\n"
                f"  • Workflow: Stage 1 (Review IT Lead & DevOps) -> Stage 2 (Head of IT)\n"
            )
        )
