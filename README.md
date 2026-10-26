# Royal Workflow

<p align="center">
  <strong>Platform Manajemen Formulir Dinamis, Alur Kerja Persetujuan Bertingkat (Approval Workflow), dan Integrasi Enterprise</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Django-5.2+-092E20?style=for-the-badge&logo=django&logoColor=white" alt="Django" />
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Bootstrap-5-7952B3?style=for-the-badge&logo=bootstrap&logoColor=white" alt="Bootstrap 5" />
  <img src="https://img.shields.io/badge/Celery-Task%20Queue-37814A?style=for-the-badge&logo=celery&logoColor=white" alt="Celery" />
  <img src="https://img.shields.io/badge/License-LGPL--3.0-blue?style=for-the-badge" alt="License" />
</p>

---

## 📌 Tentang Proyek

**Royal Workflow** adalah sistem enterprise berbasis web yang dirancang untuk mengotomasi seluruh siklus hidup formulir bisnis perusahaan, permohonan kontrak (SPK), dan alur persetujuan bertingkat (*multi-stage approval workflow*).

Sistem ini mengintegrasikan struktur organisasi perusahaan, data ERP, dan portal publik untuk penandatanganan digital secara terpusat, fleksibel, dan terukur.

### 🌟 Fitur Utama

1. **Dynamic Form & Multi-Step Wizard Engine**
   - Pembuatan dan pengelolaan skema formulir dinamis langsung dari basis data tanpa *hardcoding*.
   - Mendukung berbagai tipe input data, *universal choices parser*, *conditional logic* (bidang muncul/hilang berdasarkan input sebelumnya), serta *dynamic grid widget* (tabel input interaktif).
   - Wizard formulir bertahap (*multi-step wizard*) dengan validasi reaktif sebelum dikirimkan.

2. **Mesin Alur Kerja Persetujuan (Workflow Engine)**
   - **Multi-Stage Approval**: Alur persetujuan bertahap (misal: 4-5 tahap verifikasi mulai dari Supervisor, Dept Head, Legal, hingga Direksi).
   - **Dynamic Supervisor Routing**: Penugasan tugas persetujuan secara otomatis ke atasan langsung (Level 1 dan Level 2) berdasarkan data hierarki karyawan.
   - **Conditional Stage Triggers & Auto-Skip**: Tahapan persetujuan dapat dilewati secara otomatis jika kriteria nilai atau cabang tertentu tidak terpenuhi.
   - **In-Place Revision Lifecycle**: Dukungan siklus revisi dokumen di tempat (*Request Revision*, *Resubmit*, *Withdraw*, *Reassign*).
   - **Audit Trail & Diff Viewer**: Riwayat lengkap setiap aksi persetujuan beserta tampilan pembanding perubahan (*diff viewer*) antar revisi.

3. **Integrasi Enterprise**
   - **HRIS REST API Integration**: Sinkronisasi otomatis data karyawan, departemen, dan rantai manajerial dari API eksternal Royal Corp HRIS, termasuk penyusunan *Role-Based Access Control* (RBAC).
   - **JDE ERP Customer Lookup**: Pencarian data mitra/pelanggan secara langsung dari sistem ERP JDE dengan fitur *autofill* ke formulir permohonan.
   - **LDAP / Corporate SSO Backend**: Autentikasi dan sinkronisasi direktori pengguna perusahaan.

4. **Portal Penandatanganan Digital Eksternal (Public SPK E-Sign Portal)**
   - Akses portal aman berbasis tautan dengan token UUID unik tanpa perlu akun login internal (`/spk/sign/<token>/`).
   - Dilengkapi masa berlaku tautan (*token expiration*), kanvas tanda tangan interaktif (layar sentuh / mouse), opsi persetujuan/penolakan oleh pihak toko/mitra, dan audit status penandatanganan.

5. **Pencetakan Dokumen & Dasbor Analitik**
   - **Ekspor PDF Otomatis**: Integrasi **WeasyPrint** untuk merender draf kontrak SPK resmi dan lembar pengesahan ke format PDF berstandar cetak.
   - **Analytics Dashboard**: Monitoring metrik formulir, waktu rata-rata proses persetujuan (SLA), volume pengajuan per kategori, dan status antrean secara visual.
   - **Form Schema Synchronization**: Perintah bawaan `push_forms` dan `pull_forms` untuk mendistribusikan definisi formulir antar lingkungan (*development*, *staging*, *production*).

---

## 🏗️ Struktur Direktori Proyek

```plaintext
royal-workflow/
├── config/                         # Konfigurasi inti proyek Django
│   ├── settings.py                 # Konfigurasi aplikasi, database, dan middleware
│   ├── urls.py                     # Routing URL utama & override routing formulir
│   ├── views.py                    # Custom views (JDE lookup, dashboard filter, custom submission)
│   ├── celery.py                   # Inisialisasi background task runner Celery
│   ├── context_processors.py       # Context processor global (notifikasi topbar, preferensi)
│   └── management/commands/        # Custom management commands aplikasi utama
│
├── django_forms_workflows/         # Core Engine Formulir & Alur Kerja Persetujuan
│   ├── models.py                   # Model data (FormDefinition, FormField, Workflow, Submissions)
│   ├── workflow_engine.py          # Logika eksekusi transisi status & auto-routing workflow
│   ├── views.py                    # Handler tampilan katalog form, submission, dan aksi approval
│   ├── signing_views.py            # Portal publik tanda tangan digital mitra eksternal
│   ├── diff_views.py               # Visualisasi diff perbandingan versi revisi pengajuan
│   ├── reporting_views.py          # Logika analitik dan metrik ringkasan
│   ├── services/                   # Service layer (sinkronisasi HRIS, JDE ERP integration)
│   ├── templates/                  # Template bawaan komponen workflow
│   └── management/commands/        # Perintah CLI (seed SPK, sync HRIS, purge form, push/pull)
│
├── static/                         # Aset statis (CSS, JS, Web Fonts, Vendor Scripts)
├── templates/                      # Template kustom UI aplikasi & layout Bootstrap 5
│   └── django_forms_workflows/     # Override template tampilan (wizard, detail, signing portal)
│
├── .env.example                    # Contoh template variabel lingkungan
├── manage.py                       # Skrip eksekusi manajemen Django
└── requirements.txt                # Daftar paket dependensi Python
```

---

## 💻 Prasyarat Sistem

Sebelum memulai instalasi, pastikan sistem Anda telah memiliki:

- **Python**: Versi `3.10`, `3.11`, atau `3.12`.
- **pip** & **virtualenv** terbaru.
- **Git** untuk *version control*.
- *(Opsional untuk WeasyPrint PDF)*: Pustaka grafis sistem seperti **Pango**, **cairo**, dan **gdk-pixbuf** (tersedia melalui paket GTK+ untuk Windows atau pustaka distribusi Linux).

---

## 🚀 Panduan Instalasi & Menjalankan Lokal

### 1. Clone Repositori

```bash
git clone <URL_REPOSITORI_ANDA>
cd royal-workflow
```

### 2. Buat dan Aktifkan Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Pasang Dependensi Python

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Konfigurasi File Environment (`.env`)

Salin file contoh konfigurasi `.env.example` menjadi `.env`:

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

**Linux / macOS:**
```bash
cp .env.example .env
```

Buka file `.env` dan sesuaikan parameter berikut:
```env
# Django Core Settings
SECRET_KEY=kunci-rahasia-keamanan-django-anda
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost

# Database Configuration (Default SQLite untuk development)
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=db.sqlite3

# HRIS Employee API
HRIS_API_URL=https://dev-api.royalcorp.co.id/api/v1/externalapi/employeesV2
HRIS_API_TOKEN=your_hris_token_here
HRIS_DEFAULT_PASSWORD=Bandung*123#

# Enterprise & ERP Integration
JDE_API_BASE_URL=https://jde-api.corporate.local/
JDE_API_TOKEN=your_jde_token_here
```

### 5. Jalankan Migrasi Database

```bash
python manage.py migrate
```

### 6. Buat Akun Administrator (Superuser)

```bash
python manage.py createsuperuser
```

---

## ⚙️ Perintah Manajemen Data (CLI Commands)

Aplikasi dilengkapi dengan serangkaian perintah CLI `manage.py` untuk mempermudah inisialisasi dan pengujian sistem:

### 1. Sinkronisasi Karyawan dari API HRIS
Mengambil data karyawan, struktur departemen, dan memetakan atasan langsung (*supervisor hierarchy*) secara otomatis:

```bash
# Simulasi tanpa menyimpan ke database
python manage.py sync_employees --dry-run

# Sinkronisasi penuh
python manage.py sync_employees --from=2020-01-01 --to=2026-12-31
```

### 2. Inisialisasi Form Permohonan Kontrak (SPK)
Membuat skema formulir lengkap, opsi pilihan, dan workflow 4-5 tahap:

```bash
python manage.py seed_permohonan_kontrak
```

### 3. Inisialisasi Akun Simulasi Alur Kerja (Dummy Users)
Membuat akun uji coba simulasi alur approval (`dummy.01` s/d `dummy.07`) dengan kata sandi bawaan `Bandung*123#`:

```bash
# Buat akun dummy testing
python manage.py seed_dummy_spk

# Bersihkan akun dummy setelah pengujian selesai
python manage.py rollback_dummy_spk
```

| Username | Peran / Jabatan | Cabang / Grup | Posisi Alur Workflow |
| :--- | :--- | :--- | :--- |
| `dummy.01` | Sales Staff | Bali | Pemohon / Inisiator Cabang |
| `dummy.02` | Sales Staff | Pusat | Pemohon / Inisiator Pusat |
| `dummy.03` | Branch Manager / Spv | Bali | Stage 1: Reviewer / Atasan Cabang |
| `dummy.04` | National Sales Manager | Pusat | Stage 2: Verifikator Sales Pusat |
| `dummy.05` | Legal Specialist | Pusat | Stage 3: Legal Review & Draft Kontrak |
| `dummy.06` | Direktur Operasional | Pusat | Stage 4: Approval Direksi |
| `dummy.07` | Mitra Toko (Eksternal) | - | Simulasi Penandatangan Mitra SPK |

### 4. Sinkronisasi Definisi Form Lintas Server
Mentransfer definisi form dan workflow dari satu server ke server lain:

```bash
# Ekspor definisi form lokal ke file JSON
python manage.py push_forms --output=forms_backup.json

# Impor definisi form dari file JSON
python manage.py pull_forms --file=forms_backup.json
```

---

## 🖥️ Menjalankan Server Aplikasi

Jalankan server pengembangan Django:

```bash
python manage.py runserver
```

Akses aplikasi pada peramban web: **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)**

### Rute Navigasi Penting:

- **Dasbor Analitik & SLA**: `http://127.0.0.1:8000/dashboard/`
- **Katalog Formulir**: `http://127.0.0.1:8000/forms/`
- **Pengajuan Saya**: `http://127.0.0.1:8000/forms/submissions/`
- **Kotak Masuk Persetujuan (Approval Inbox)**: `http://127.0.0.1:8000/forms/approvals/`
- **Portal Tanda Tangan Digital Mitra**: `http://127.0.0.1:8000/spk/sign/<token-uuid>/`
- **Panel Administrasi Django**: `http://127.0.0.1:8000/admin/`

---

## 🔄 Siklus Persetujuan Permohonan Kontrak (SPK Flow)

```mermaid
flowchart TD
    A([Inisiator / Sales]):-->|Mengisi Form Multi-Step & JDE Lookup| B[Draft / Submit SPK]
    B --> C{Pemeriksaan Atasan Langsung}
    C -->|Cabang Daerah| D[Stage 1: Branch Manager / Spv]
    C -->|Kantor Pusat / Nilai Tertentu| E[Stage 2: National Sales Manager]
    D -->|Disetujui| E
    D -->|Perlu Revisi| B
    E -->|Disetujui| F[Stage 3: Tim Legal]
    E -->|Perlu Revisi| B
    F -->|Review Draf Kontrak & Verifikasi| G[Stage 4: Direktur Terkait]
    F -->|Perlu Revisi| B
    G -->|Persetujuan Final| H[Generate Token E-Sign Mitra]
    H --> I[Stage 5: Penandatanganan Digital oleh Mitra Toko]
    I -->|Tanda Tangan Diterima| J([Kontrak Sah & Terbit Dokumen Final PDF])
    I -->|Ditolak oleh Mitra| K([Status SPK: Ditolak Mitra])
```

---

## 🔒 Variabel Lingkungan (.env Reference)

| Variabel | Tipe | Default | Keterangan |
| :--- | :--- | :--- | :--- |
| `SECRET_KEY` | String | *django-insecure...* | Kunci enkripsi sesi dan token Django. |
| `DEBUG` | Boolean | `True` | Mode debug (`True` saat dev, `False` saat prod). |
| `ALLOWED_HOSTS` | List | `127.0.0.1,localhost` | Daftar host/domain yang diizinkan mengakses server. |
| `DB_ENGINE` | String | `django.db.backends.sqlite3` | Driver database (`sqlite3`, `postgresql`, `mysql`). |
| `DB_NAME` | String | `db.sqlite3` | Nama database atau path file SQLite. |
| `DB_USER` | String | Kosong | Username pengguna database. |
| `DB_PASSWORD` | String | Kosong | Password database. |
| `DB_HOST` | String | Kosong | Alamat host server database. |
| `DB_PORT` | String | Kosong | Port koneksi server database. |
| `HRIS_API_URL` | String | *dev-api.royalcorp.co.id...* | Endpoint REST API layanan HRIS karyawan. |
| `HRIS_API_TOKEN` | String | Kosong | Token bearer autentikasi API HRIS. |
| `HRIS_DEFAULT_PASSWORD` | String | `Bandung*123#` | Kata sandi default akun hasil sinkronisasi HRIS. |
| `JDE_API_BASE_URL` | String | *https://jde-api...* | URL dasar API ERP JDE untuk pencarian customer. |

---

## 📄 Lisensi

Proyek ini didistribusikan di bawah lisensi **LGPL-3.0**. Silakan lihat berkas lisensi terkait untuk ketentuan hak cipta dan penggunaan.
