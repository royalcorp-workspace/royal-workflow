/**
 * pengajuan-biaya-widget.js
 * 
 * Specialized UI/UX Controller for "Pengajuan Biaya & Anggaran Operasional"
 * Restructured into 5 explicit standard sections:
 * 1. Informasi Pengajuan (Nomor, Tanggal, Cabang, Kategori Barang, PIC, Catatan Pengajuan)
 * 2. Informasi Limit (4 Card dalam 1 Row: Limit, Terpakai, Sisa Limit, Nominal Pengajuan Estimasi)
 * 3. Detail Item Pengajuan (Tabel No, Deskripsi, Qty, Satuan, Harga Satuan, Subtotal, + Item Pengajuan)
 * 4. Informasi Pencairan Dana (Metode Pembayaran, Nama Bank, Nomor Rekening Opsional)
 * 5. Lampiran (Struktur [Nama Dokumen] [Upload File] + Tambah Lampiran)
 */

(function () {
    'use strict';

    function formatRupiah(num) {
        var n = parseInt(num, 10);
        if (isNaN(n) || n < 0) n = 0;
        return 'Rp ' + n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    }

    function parseRupiah(str) {
        if (typeof str === 'number') return Math.max(0, Math.floor(str));
        if (!str) return 0;
        var clean = str.toString().replace(/[^0-9]/g, '');
        var n = parseInt(clean, 10);
        return isNaN(n) ? 0 : n;
    }

    var KATEGORI_MAPPING = {
        'ATK': {
            pic: 'General Affair (GA)',
            items: [
                'Kertas HVS A4 75/80 gr',
                'Kertas HVS F4 75/80 gr',
                'Pulpen Gel Hitam/Biru',
                'Binder Clip & Paper Clip',
                'Buku Ekspedisi / Agenda',
                'Tinta / Toner Printer',
                'Spidol Boardmarker',
                'Map Folio / Stopmap / Bantex',
                'Lakban Bening / Coklat',
                'Gunting / Cutter / Penggaris',
                'Lainnya (Ketik Manual)'
            ],
            defaultSatuan: 'Rim'
        },
        'Perlengkapan Kantor & RT': {
            pic: 'General Affair (GA)',
            items: [
                'Air Minum Galon',
                'Paket Kopi, Teh, Gula Karyawan & Tamu',
                'Tissue Roll / Facial Tissue',
                'Sabun Cuci Tangan & Piring',
                'Pembersih Lantai & Karbol',
                'Kantong Sampah Plastik Hitam',
                'Sapu, Pel & Kain Lap Microfiber',
                'Pengharum Ruangan',
                'Tempat Sampah Pedal',
                'Lainnya (Ketik Manual)'
            ],
            defaultSatuan: 'Galon'
        },
        'IT & Komunikasi': {
            pic: 'IT Support / Infrastructure',
            items: [
                'Kabel LAN Cat6 + RJ45',
                'Mouse USB Standard',
                'Keyboard USB Standard',
                'Flashdisk USB 32GB / 64GB',
                'Adaptor / Charger Laptop / PC',
                'Kabel HDMI / VGA Converter',
                'Router / Switch Hub',
                'Biaya Paket Internet Cabang',
                'Headset / Web Camera',
                'Lainnya (Ketik Manual)'
            ],
            defaultSatuan: 'Unit'
        },
        'Pemeliharaan & Gedung (Maintenance)': {
            pic: 'Building & Facility Management',
            items: [
                'Cuci & Servis Berkala AC Cabang',
                'Tambah / Isi Freon AC',
                'Lampu LED Downlight / Tube',
                'Perbaikan Kran, Pipa Air & Sanitasi',
                'Kunci Pintu / Gembok / Engsel',
                'Cat Tembok / Plafon & Kuas',
                'Servis Rolling Door / Kaca Toko',
                'Perbaikan Stop Kontak / Kelistrikan',
                'Lainnya (Ketik Manual)'
            ],
            defaultSatuan: 'Unit'
        },
        'Operasional Kendaraan & Transportasi': {
            pic: 'Logistik & Operasional',
            items: [
                'BBM Operasional Kendaraan',
                'Ganti Oli Mesin Kendaraan Operasional',
                'Servis Berkala & Tune Up Kendaraan',
                'Tambal Ban & Perawatan Ban',
                'Biaya Parkir & Tol Operasional',
                'Cuci Kendaraan Operasional',
                'Lainnya (Ketik Manual)'
            ],
            defaultSatuan: 'Liter'
        },
        'Sales, Marketing & Promosi': {
            pic: 'Marketing & Promo Support',
            items: [
                'Cetak Spanduk / Banner / X-Banner',
                'Cetak Brosur / Flyer Penjualan',
                'Konsumsi Event Pameran Cabang',
                'Seragam / Rompi / Kaos Sales Event',
                'Perlengkapan Display / Brosur Holder',
                'Sewa Tenda / Booth Promosi',
                'Merchandise / Hadiah Konsumen',
                'Lainnya (Ketik Manual)'
            ],
            defaultSatuan: 'Pcs'
        }
    };

    var SATUAN_OPTIONS = [
        'Pcs', 'Rim', 'Box', 'Pack', 'Unit', 'Set', 'Roll', 'Galon', 'Botol', 'Liter', 'Bulan', 'Kegiatan', 'Lusin', 'Meter'
    ];

    function initPengajuanBiayaForm() {
        var form = document.querySelector('form[data-form-slug="pengajuan-biaya"]') || 
                   document.querySelector('#form_pengajuan-biaya');
        if (!form) {
            if (!document.querySelector('[name="kategori_barang"]') && 
                !document.querySelector('[name="kategori_biaya"]')) {
                return;
            }
            form = document.querySelector('form');
        }

        if (!form || form.dataset.wfBiayaInitialized === 'true') return;
        form.dataset.wfBiayaInitialized = 'true';

        console.log('[PengajuanBiayaWidget] Initializing 5-section restructured form...');

        var fieldsWrapper = form.querySelector('.form-fields-wrapper');
        if (!fieldsWrapper) return;

        function getFieldWrapper(fieldName) {
            return form.querySelector('.field-' + fieldName) || 
                   form.querySelector('[name="' + fieldName + '"]')?.closest('.field-wrapper') ||
                   form.querySelector('[name="' + fieldName + '"]')?.closest('.mb-3');
        }

        // 1. Locate Section 1 fields
        var fNomor = getFieldWrapper('nomor_pengajuan');
        var fTanggal = getFieldWrapper('tanggal_pengajuan');
        var fCabang = getFieldWrapper('cabang');
        var fKategori = getFieldWrapper('kategori_barang') || getFieldWrapper('kategori_biaya');
        var fPic = getFieldWrapper('pic') || getFieldWrapper('nama_pic');
        var fCatatan = getFieldWrapper('catatan_pengajuan') || getFieldWrapper('catatan_justifikasi');

        // Locate Section 2 fields (Informasi Limit)
        var fLimitAnggaran = getFieldWrapper('limit_anggaran');
        var fLimitTerpakai = getFieldWrapper('limit_terpakai');
        var fSisaLimit = getFieldWrapper('sisa_limit') || getFieldWrapper('sisa_limit_saat_ini');
        var fTotalNominal = getFieldWrapper('total_nominal');

        // Locate Section 3 fields (Detail Item)
        var fItemsData = getFieldWrapper('items_data');
        var fRincianItem = getFieldWrapper('rincian_item');

        // Locate Section 4 fields (Pencairan Dana)
        var fMetodeBayar = getFieldWrapper('metode_pembayaran') || getFieldWrapper('metode_pencairan');
        var fNamaBank = getFieldWrapper('nama_bank');
        var fNomorRekening = getFieldWrapper('nomor_rekening');

        // Locate Section 5 fields (Lampiran)
        var fDokPendukung = getFieldWrapper('dokumen_pendukung');
        var fLampiranData = getFieldWrapper('lampiran_data');

        // Hide downstream & non-initial submission fields
        var downstreamNames = [
            'perlu_proses_manual', 'status_transfer_dana', 'tanggal_transfer_dana',
            'nomor_referensi_transfer', 'nomor_ppvm', 'realisasi_nominal',
            'catatan_realisasi', 'lampiran_realisasi', 'atas_nama_rekening',
            'department_pembuat', 'bagian_pembuat', 'nama_atasan', 'inisiator_nama',
            'department_penerima', 'bagian_penerima', 'tembusan', 'nomor_petty_cash',
            'tipe_transaksi', 'urgensi_pengajuan', 'sisa_limit_pengajuan_lalu'
        ];
        downstreamNames.forEach(function (name) {
            var fw = getFieldWrapper(name);
            if (fw) fw.style.display = 'none';
        });

        // Hide original generic headers if any
        form.querySelectorAll('h3, .field-section_info_pemohon, .field-section_rincian_anggaran, .field-section_dokumen_lampiran').forEach(function (el) {
            el.style.display = 'none';
        });

        // Hide data backing fields & redundant single upload
        [fLimitAnggaran, fLimitTerpakai, fSisaLimit, fTotalNominal, fItemsData, fRincianItem, fLampiranData, fDokPendukung].forEach(function (fw) {
            if (fw) fw.style.display = 'none';
        });

        // Target inputs
        var inputKategori = form.querySelector('[name="kategori_barang"]') || form.querySelector('[name="kategori_biaya"]');
        var inputPic = form.querySelector('[name="pic"]') || form.querySelector('[name="nama_pic"]');
        var inputTotalNominal = form.querySelector('[name="total_nominal"]');
        var inputItemsData = form.querySelector('[name="items_data"]');
        var inputRincianItem = form.querySelector('[name="rincian_item"]');
        var inputDokPendukung = form.querySelector('[name="dokumen_pendukung"]');
        var inputLampiranData = form.querySelector('[name="lampiran_data"]');

        // Budget numbers
        var valLimit = parseRupiah(form.querySelector('[name="limit_anggaran"]')?.value || '10000000');
        var valTerpakai = parseRupiah(form.querySelector('[name="limit_terpakai"]')?.value || '4500000');
        var valSisaLimit = parseRupiah(form.querySelector('[name="sisa_limit"]')?.value || '5500000');
        if (valLimit === 0) valLimit = 10000000;
        if (valTerpakai === 0) valTerpakai = 4500000;
        if (valSisaLimit === 0) valSisaLimit = valLimit - valTerpakai;

        // Ensure PIC field is readonly and styled nicely
        if (inputPic) {
            inputPic.readOnly = true;
            inputPic.style.backgroundColor = '#f8fafc';
            inputPic.style.cursor = 'not-allowed';
            inputPic.style.fontWeight = '600';
            inputPic.style.color = '#1e3a8a';
        }

        // Autofill Tanggal Transfer Dana with current date as default if field exists
        var inputTransfer = form.querySelector('[name="tanggal_transfer_dana"]');
        if (inputTransfer && !inputTransfer.value) {
            var today = new Date();
            var yyyy = today.getFullYear();
            var mm = String(today.getMonth() + 1).padStart(2, '0');
            var dd = String(today.getDate()).padStart(2, '0');
            inputTransfer.value = yyyy + '-' + mm + '-' + dd;
        }
        var inputTanggal = form.querySelector('[name="tanggal_pengajuan"]');
        if (inputTanggal) {
            if (!inputTanggal.value) {
                var today = new Date();
                var yyyy = today.getFullYear();
                var mm = String(today.getMonth() + 1).padStart(2, '0');
                var dd = String(today.getDate()).padStart(2, '0');
                inputTanggal.value = yyyy + '-' + mm + '-' + dd;
            }
            inputTanggal.readOnly = false;
            inputTanggal.removeAttribute('readonly');
            inputTanggal.removeAttribute('tabindex');
            inputTanggal.classList.remove('field-readonly');
            inputTanggal.style.backgroundColor = '#ffffff';
            inputTanggal.style.cursor = 'pointer';
            inputTanggal.style.fontWeight = '500';
            inputTanggal.style.color = '#1e293b';
        }

        // =========================================================================
        // BUILD THE 5-SECTION RESTRUCTURED CONTAINER
        // =========================================================================
        var mainContainer = document.createElement('div');
        mainContainer.className = 'pengajuan-biaya-restructured-flow mb-4';

        // ─────────────────────────────────────────────────────────────────────────
        // 1. INFORMASI PENGAJUAN
        // ─────────────────────────────────────────────────────────────────────────
        var sec1Card = document.createElement('div');
        sec1Card.className = 'card border shadow-sm mb-4';
        sec1Card.innerHTML = 
            '<div class="card-header bg-white py-3 border-bottom d-flex align-items-center justify-content-between">' +
                '<h5 class="mb-0 fw-bold text-dark fs-6 d-flex align-items-center gap-2">' +
                    '<i class="bi bi-file-earmark-text text-primary fs-5"></i> 1. Informasi Pengajuan' +
                '</h5>' +
                '<span class="badge bg-light text-secondary border px-2.5 py-1 font-monospace" style="font-size: 11px;">' +
                    '<i class="bi bi-check-circle me-1 text-success"></i>Form Standar' +
                '</span>' +
            '</div>' +
            '<div class="card-body p-3 p-md-4" id="sec1_body"></div>';
        mainContainer.appendChild(sec1Card);

        // ─────────────────────────────────────────────────────────────────────────
        // 2. INFORMASI LIMIT (4 Card dalam 1 Row)
        // ─────────────────────────────────────────────────────────────────────────
        var sec2Card = document.createElement('div');
        sec2Card.className = 'card border shadow-sm mb-4';
        sec2Card.innerHTML = 
            '<div class="card-header bg-white py-3 border-bottom d-flex align-items-center justify-content-between">' +
                '<h5 class="mb-0 fw-bold text-dark fs-6 d-flex align-items-center gap-2">' +
                    '<i class="bi bi-speedometer2 text-primary fs-5"></i> 2. Informasi Limit' +
                '</h5>' +
                '<span class="badge bg-info-subtle text-info-emphasis border border-info-subtle px-2 py-1" style="font-size: 11px;">' +
                    '<i class="bi bi-info-circle me-1"></i>Informatif' +
                '</span>' +
            '</div>' +
            '<div class="card-body p-3 p-md-4">' +
                '<div class="row g-3 row-cols-2 row-cols-md-4">' +
                    '<div class="col">' +
                        '<div class="p-3 rounded border bg-light h-100">' +
                            '<div class="text-uppercase text-muted fw-bold" style="font-size: 11px; letter-spacing: 0.04em;">Limit</div>' +
                            '<div class="fs-4 fw-bolder text-dark mt-1 font-monospace" id="card_val_limit">' + formatRupiah(valLimit) + '</div>' +
                            '<div class="text-muted small mt-1" style="font-size: 11px;">Plafon Operasional Cabang</div>' +
                        '</div>' +
                    '</div>' +
                    '<div class="col">' +
                        '<div class="p-3 rounded border bg-light h-100">' +
                            '<div class="text-uppercase text-muted fw-bold" style="font-size: 11px; letter-spacing: 0.04em;">Terpakai</div>' +
                            '<div class="fs-4 fw-bolder text-secondary mt-1 font-monospace" id="card_val_terpakai">' + formatRupiah(valTerpakai) + '</div>' +
                            '<div class="text-muted small mt-1" style="font-size: 11px;">Realisasi Berjalan</div>' +
                        '</div>' +
                    '</div>' +
                    '<div class="col">' +
                        '<div class="p-3 rounded border bg-light h-100">' +
                            '<div class="text-uppercase text-muted fw-bold" style="font-size: 11px; letter-spacing: 0.04em;">Sisa Limit</div>' +
                            '<div class="fs-4 fw-bolder text-success mt-1 font-monospace" id="card_val_sisa">' + formatRupiah(valSisaLimit) + '</div>' +
                            '<div class="text-muted small mt-1" style="font-size: 11px;">Sisa Plafon Anggaran</div>' +
                        '</div>' +
                    '</div>' +
                    '<div class="col">' +
                        '<div class="p-3 rounded border bg-primary-subtle border-primary-subtle h-100" id="box_val_estimasi">' +
                            '<div class="text-uppercase text-primary fw-bold" style="font-size: 11px; letter-spacing: 0.04em;">Nominal Pengajuan (Estimasi)</div>' +
                            '<div class="fs-4 fw-bolder text-primary mt-1 font-monospace" id="card_val_estimasi">Rp 0</div>' +
                            '<div class="text-primary-emphasis small mt-1" style="font-size: 11px;">Akumulasi Seluruh Item</div>' +
                        '</div>' +
                    '</div>' +
                '</div>' +
                '<div class="mt-2.5 pt-2 border-top d-flex align-items-center justify-content-between flex-wrap gap-2" id="row_limit_flowchart">' +
                    '<div class="d-flex align-items-center gap-2">' +
                        '<span class="fw-semibold text-secondary small">Limit Pengajuan Mencukupi?</span>' +
                        '<span class="badge bg-success-subtle text-success border border-success-subtle font-monospace px-2 py-1" id="badge_limit_status">' +
                            '<i class="bi bi-check-circle-fill me-1"></i>Ya (Mencukupi)' +
                        '</span>' +
                    '</div>' +
                    '<div id="limit_warning_text" class="text-danger small fw-semibold" style="display: none;">' +
                        '<i class="bi bi-exclamation-triangle-fill me-1"></i>Informasi: Limit pengajuan saat ini tidak mencukupi (melebihi sisa plafon anggaran)!' +
                    '</div>' +
                '</div>' +
            '</div>';
        mainContainer.appendChild(sec2Card);

        // ─────────────────────────────────────────────────────────────────────────
        // 3. DETAIL ITEM PENGAJUAN (Struktur Tabel)
        // ─────────────────────────────────────────────────────────────────────────
        var sec3Card = document.createElement('div');
        sec3Card.className = 'card border shadow-sm mb-4';
        sec3Card.innerHTML = 
            '<div class="card-header bg-white py-3 border-bottom d-flex align-items-center justify-content-between flex-wrap gap-2">' +
                '<h5 class="mb-0 fw-bold text-dark fs-6 d-flex align-items-center gap-2">' +
                    '<i class="bi bi-table text-primary fs-5"></i> 3. Detail Item Pengajuan' +
                '</h5>' +
                '<span class="badge bg-primary-subtle text-primary border border-primary-subtle px-2.5 py-1 fw-semibold font-monospace" id="table_badge_item_count">' +
                    '1 Item' +
                '</span>' +
            '</div>' +
            '<div class="card-body p-3 p-md-4">' +
                '<div class="table-responsive">' +
                    '<table class="table table-bordered table-hover align-middle mb-2" id="table_item_pengajuan">' +
                        '<thead class="table-light">' +
                            '<tr>' +
                                '<th style="width: 50px;" class="text-center">No</th>' +
                                '<th style="min-width: 250px;">Deskripsi</th>' +
                                '<th style="width: 100px;">Qty</th>' +
                                '<th style="width: 130px;">Satuan</th>' +
                                '<th style="width: 180px;">Harga Satuan</th>' +
                                '<th style="width: 190px;">Subtotal</th>' +
                                '<th style="width: 60px;" class="text-center">Aksi</th>' +
                            '</tr>' +
                        '</thead>' +
                        '<tbody id="tbody_item_pengajuan"></tbody>' +
                        '<tfoot class="table-light fw-bold">' +
                            '<tr>' +
                                '<td colspan="5" class="text-end py-2.5">Total Pengajuan:</td>' +
                                '<td class="text-primary fs-5 font-monospace py-2.5" id="table_total_nominal">Rp 0</td>' +
                                '<td></td>' +
                            '</tr>' +
                        '</tfoot>' +
                    '</table>' +
                '</div>' +
                '<div class="d-flex justify-content-between align-items-center mt-3 flex-wrap gap-2">' +
                    '<button type="button" class="btn btn-outline-primary d-inline-flex align-items-center gap-2 px-3 py-1.5 shadow-sm fw-semibold" id="btn_add_item_row">' +
                        '<i class="bi bi-plus-circle-fill"></i> + Item Pengajuan' +
                    '</button>' +
                    '<span class="text-muted small">' +
                        '<i class="bi bi-calculator me-1"></i>Subtotal dihitung otomatis (Qty &times; Harga Satuan)' +
                    '</span>' +
                '</div>' +
            '</div>';
        mainContainer.appendChild(sec3Card);

        // ─────────────────────────────────────────────────────────────────────────
        // 4. INFORMASI PENCAIRAN DANA
        // ─────────────────────────────────────────────────────────────────────────
        var sec4Card = document.createElement('div');
        sec4Card.className = 'card border shadow-sm mb-4';
        sec4Card.innerHTML = 
            '<div class="card-header bg-white py-3 border-bottom">' +
                '<h5 class="mb-0 fw-bold text-dark fs-6 d-flex align-items-center gap-2">' +
                    '<i class="bi bi-bank text-primary fs-5"></i> 4. Informasi Pencairan Dana' +
                '</h5>' +
            '</div>' +
            '<div class="card-body p-3 p-md-4" id="sec4_body">' +
                '<div class="row g-3" id="sec4_row"></div>' +
                '<div class="small text-muted mt-2 pt-1" style="font-size: 12px;">' +
                    '<i class="bi bi-info-circle me-1 text-primary"></i>Informasi rekening digunakan sebagai tujuan transfer pengajuan biaya. Nomor Rekening bersifat opsional.' +
                '</div>' +
            '</div>';
        mainContainer.appendChild(sec4Card);

        // ─────────────────────────────────────────────────────────────────────────
        // 5. LAMPIRAN
        // ─────────────────────────────────────────────────────────────────────────
        var sec5Card = document.createElement('div');
        sec5Card.className = 'card border shadow-sm mb-4';
        sec5Card.innerHTML = 
            '<div class="card-header bg-white py-3 border-bottom d-flex align-items-center justify-content-between">' +
                '<h5 class="mb-0 fw-bold text-dark fs-6 d-flex align-items-center gap-2">' +
                    '<i class="bi bi-paperclip text-primary fs-5"></i> 5. Lampiran' +
                '</h5>' +
                '<span class="badge bg-light text-secondary border px-2 py-1" style="font-size: 11px;">' +
                    '<i class="bi bi-files me-1"></i>Multi-Lampiran' +
                '</span>' +
            '</div>' +
            '<div class="card-body p-3 p-md-4">' +
                '<div class="lampiran-rows-container" id="lampiran_rows_container"></div>' +
                '<div class="d-flex justify-content-between align-items-center mt-3 flex-wrap gap-2">' +
                    '<button type="button" class="btn btn-outline-primary d-inline-flex align-items-center gap-2 px-3 py-1.5 shadow-sm fw-semibold" id="btn_add_lampiran_row">' +
                        '<i class="bi bi-plus-circle-fill"></i> + Tambah Lampiran' +
                    '</button>' +
                    '<span class="text-muted small">' +
                        '<i class="bi bi-file-earmark-arrow-up me-1"></i>Format yang didukung: PDF, JPG, PNG, DOCX' +
                    '</span>' +
                '</div>' +
            '</div>';
        mainContainer.appendChild(sec5Card);

        // Place mainContainer inside fieldsWrapper at top
        fieldsWrapper.insertBefore(mainContainer, fieldsWrapper.firstChild);

        // =========================================================================
        // POPULATE SECTION 1: INFORMASI PENGAJUAN
        // =========================================================================
        var sec1Body = document.getElementById('sec1_body');
        var row1_1 = document.createElement('div');
        row1_1.className = 'row g-3 mb-2';
        if (fNomor) {
            fNomor.className = 'col-md-6 mb-3';
            row1_1.appendChild(fNomor);
        }
        if (fTanggal) {
            fTanggal.className = 'col-md-6 mb-3';
            row1_1.appendChild(fTanggal);
        }
        sec1Body.appendChild(row1_1);

        var row1_2 = document.createElement('div');
        row1_2.className = 'row g-3 mb-2';
        if (fCabang) {
            fCabang.className = 'col-md-6 mb-3';
            row1_2.appendChild(fCabang);
        }
        if (fKategori) {
            fKategori.className = 'col-md-6 mb-3';
            row1_2.appendChild(fKategori);
        }
        sec1Body.appendChild(row1_2);

        var row1_3 = document.createElement('div');
        row1_3.className = 'row g-3';
        if (fPic) {
            fPic.className = 'col-md-6 mb-3';
            row1_3.appendChild(fPic);
        }
        if (fCatatan) {
            fCatatan.className = 'col-md-6 mb-3';
            row1_3.appendChild(fCatatan);
        }
        sec1Body.appendChild(row1_3);

        // Synchronize Kategori Barang -> PIC Mapping
        function syncPicMapping() {
            var selectedKat = inputKategori ? inputKategori.value : 'ATK';
            var mapInfo = KATEGORI_MAPPING[selectedKat] || KATEGORI_MAPPING['ATK'];
            if (inputPic) {
                inputPic.value = mapInfo.pic;
            }
        }
        if (inputKategori) {
            inputKategori.addEventListener('change', function () {
                syncPicMapping();
            });
            syncPicMapping();
        }

        // =========================================================================
        // POPULATE SECTION 4: INFORMASI PENCAIRAN DANA
        // =========================================================================
        var sec4Row = document.getElementById('sec4_row');
        if (fMetodeBayar) {
            fMetodeBayar.className = 'col-md-4 mb-3';
            sec4Row.appendChild(fMetodeBayar);
        }
        if (fNamaBank) {
            fNamaBank.className = 'col-md-4 mb-3';
            sec4Row.appendChild(fNamaBank);
        }
        if (fNomorRekening) {
            fNomorRekening.className = 'col-md-4 mb-3';
            var rekLabel = fNomorRekening.querySelector('label');
            if (rekLabel && !rekLabel.querySelector('.badge-opsional')) {
                var badge = document.createElement('span');
                badge.className = 'badge bg-secondary-subtle text-secondary ms-1 badge-opsional font-monospace';
                badge.style.fontSize = '10px';
                badge.textContent = 'Opsional';
                rekLabel.appendChild(badge);
            }
            sec4Row.appendChild(fNomorRekening);
        }

        // =========================================================================
        // SECTION 3: DETAIL ITEM PENGAJUAN (TABLE REPEATER)
        // =========================================================================
        var tbodyItems = document.getElementById('tbody_item_pengajuan');
        var btnAddItemRow = document.getElementById('btn_add_item_row');
        var lblBadgeCount = document.getElementById('table_badge_item_count');
        var lblTableTotal = document.getElementById('table_total_nominal');
        var cardValEstimasi = document.getElementById('card_val_estimasi');

        var itemsList = [];
        // Attempt to load existing items from JSON
        if (inputItemsData && inputItemsData.value) {
            try {
                var parsed = JSON.parse(inputItemsData.value);
                if (Array.isArray(parsed) && parsed.length > 0) {
                    itemsList = parsed;
                }
            } catch (e) {
                console.warn('Failed to parse existing items_data:', e);
            }
        }
        if (itemsList.length === 0) {
            itemsList.push({
                deskripsi: '',
                qty: 1,
                satuan: 'Pcs',
                harga_satuan: 0,
                subtotal: 0
            });
        }

        function getCategoryItems(categoryName) {
            var cat = KATEGORI_MAPPING[categoryName] || KATEGORI_MAPPING['ATK'];
            return cat.items;
        }

        function createItemRow(itemData, index) {
            var tr = document.createElement('tr');
            tr.className = 'item-pengajuan-row';

            var satuanOptionsHtml = '';
            SATUAN_OPTIONS.forEach(function (sat) {
                var isSelected = (itemData.satuan === sat);
                satuanOptionsHtml += '<option value="' + sat + '"' + (isSelected ? ' selected' : '') + '>' + sat + '</option>';
            });

            var descVal = (itemData.deskripsi || itemData.nama || '').replace(/"/g, '&quot;');
            var qtyVal = parseInt(itemData.qty, 10) || 1;
            var hargaVal = parseInt(itemData.harga_satuan || itemData.harga, 10) || 0;
            var subtotalVal = qtyVal * hargaVal;

            tr.innerHTML = 
                '<td class="text-center fw-bold row-index-cell">' + (index + 1) + '</td>' +
                '<td>' +
                    '<input type="text" class="form-control form-control-sm item-input-desc" placeholder="Ketik deskripsi / nama item yang diajukan..." value="' + descVal + '" required>' +
                '</td>' +
                '<td>' +
                    '<input type="number" class="form-control form-control-sm text-center item-input-qty" min="1" value="' + qtyVal + '">' +
                '</td>' +
                '<td>' +
                    '<select class="form-select form-select-sm item-select-satuan">' + satuanOptionsHtml + '</select>' +
                '</td>' +
                '<td>' +
                    '<div class="input-group input-group-sm">' +
                        '<span class="input-group-text bg-light">Rp</span>' +
                        '<input type="number" class="form-control form-control-sm text-end font-monospace item-input-harga" min="0" step="500" value="' + hargaVal + '">' +
                    '</div>' +
                '</td>' +
                '<td>' +
                    '<div class="fw-bold font-monospace text-end text-dark item-val-subtotal">' + formatRupiah(subtotalVal) + '</div>' +
                '</td>' +
                '<td class="text-center">' +
                    '<button type="button" class="btn btn-outline-danger btn-sm p-1 btn-delete-item-row" title="Hapus Item">' +
                        '<i class="bi bi-trash"></i>' +
                    '</button>' +
                '</td>';

            // Event bindings
            var inputDesc = tr.querySelector('.item-input-desc');
            var inputQty = tr.querySelector('.item-input-qty');
            var selectSatuan = tr.querySelector('.item-select-satuan');
            var inputHarga = tr.querySelector('.item-input-harga');
            var btnDelete = tr.querySelector('.btn-delete-item-row');

            inputDesc.addEventListener('input', function () {
                recalculateItemTable();
            });

            selectSatuan.addEventListener('change', function () {
                recalculateItemTable();
            });

            inputQty.addEventListener('input', function () {
                if (parseInt(inputQty.value, 10) < 1 || isNaN(parseInt(inputQty.value, 10))) {
                    inputQty.value = 1;
                }
                recalculateItemTable();
            });

            inputHarga.addEventListener('input', function () {
                if (parseInt(inputHarga.value, 10) < 0 || isNaN(parseInt(inputHarga.value, 10))) {
                    inputHarga.value = 0;
                }
                recalculateItemTable();
            });

            btnDelete.addEventListener('click', function () {
                var allRows = tbodyItems.querySelectorAll('tr.item-pengajuan-row');
                if (allRows.length > 1) {
                    tr.remove();
                } else {
                    // Reset single row
                    inputDesc.value = '';
                    inputQty.value = 1;
                    inputHarga.value = 0;
                }
                reindexTableRows();
                recalculateItemTable();
            });

            return tr;
        }

        function reindexTableRows() {
            var rows = tbodyItems.querySelectorAll('tr.item-pengajuan-row');
            rows.forEach(function (row, idx) {
                var cell = row.querySelector('.row-index-cell');
                if (cell) cell.textContent = idx + 1;
            });
            if (lblBadgeCount) {
                lblBadgeCount.textContent = rows.length + ' Item';
            }
        }

        function recalculateItemTable() {
            var rows = tbodyItems.querySelectorAll('tr.item-pengajuan-row');
            var totalSum = 0;
            var serializedItems = [];
            var rincianLines = [];

            rows.forEach(function (row, idx) {
                var inputDesc = row.querySelector('.item-input-desc');
                var inputQty = row.querySelector('.item-input-qty');
                var selectSatuan = row.querySelector('.item-select-satuan');
                var inputHarga = row.querySelector('.item-input-harga');
                var subtotalCell = row.querySelector('.item-val-subtotal');

                var desc = inputDesc ? inputDesc.value.trim() : '';
                if (!desc) {
                    desc = 'Item #' + (idx + 1);
                }

                var qty = parseInt(inputQty ? inputQty.value : 1, 10) || 1;
                var satuan = selectSatuan ? selectSatuan.value : 'Pcs';
                var harga = parseInt(inputHarga ? inputHarga.value : 0, 10) || 0;
                var subtotal = qty * harga;

                if (subtotalCell) {
                    subtotalCell.textContent = formatRupiah(subtotal);
                }

                totalSum += subtotal;

                serializedItems.push({
                    no: idx + 1,
                    deskripsi: desc,
                    nama: desc,
                    qty: qty,
                    satuan: satuan,
                    harga_satuan: harga,
                    harga: harga,
                    subtotal: subtotal
                });

                rincianLines.push((idx + 1) + '. ' + desc + ' (' + qty + ' ' + satuan + ' @ ' + formatRupiah(harga) + ') = ' + formatRupiah(subtotal));
            });

            // Update UI
            if (lblTableTotal) lblTableTotal.textContent = formatRupiah(totalSum);
            if (cardValEstimasi) cardValEstimasi.textContent = formatRupiah(totalSum);

            // Flowchart node validation: Limit pengajuan mencukupi?
            var badgeLimit = document.getElementById('badge_limit_status');
            var warnLimit = document.getElementById('limit_warning_text');
            var boxEstimasi = document.getElementById('box_val_estimasi');
            if (valSisaLimit > 0 && totalSum > valSisaLimit) {
                if (badgeLimit) {
                    badgeLimit.className = 'badge bg-danger-subtle text-danger border border-danger-subtle font-monospace px-2 py-1';
                    badgeLimit.innerHTML = '<i class="bi bi-x-circle-fill me-1"></i>Tidak (Melebihi Limit)';
                }
                if (warnLimit) {
                    var selisih = totalSum - valSisaLimit;
                    warnLimit.style.display = 'block';
                    warnLimit.innerHTML = '<i class="bi bi-exclamation-triangle-fill me-1"></i>Informasi limit tidak mencukupi: Total nominal melebihi sisa plafon sebesar ' + formatRupiah(selisih) + '.';
                }
                if (boxEstimasi) {
                    boxEstimasi.className = 'p-3 rounded border bg-danger-subtle border-danger-subtle h-100';
                }
            } else {
                if (badgeLimit) {
                    badgeLimit.className = 'badge bg-success-subtle text-success border border-success-subtle font-monospace px-2 py-1';
                    badgeLimit.innerHTML = '<i class="bi bi-check-circle-fill me-1"></i>Ya (Mencukupi)';
                }
                if (warnLimit) {
                    warnLimit.style.display = 'none';
                }
                if (boxEstimasi) {
                    boxEstimasi.className = 'p-3 rounded border bg-primary-subtle border-primary-subtle h-100';
                }
            }

            // Sync hidden inputs
            if (inputTotalNominal) {
                inputTotalNominal.value = totalSum;
                inputTotalNominal.dispatchEvent(new Event('change', { bubbles: true }));
            }
            if (inputItemsData) {
                inputItemsData.value = JSON.stringify(serializedItems);
            }
            if (inputRincianItem) {
                inputRincianItem.value = rincianLines.join('\n');
            }
        }

        // Render initial rows
        tbodyItems.innerHTML = '';
        itemsList.forEach(function (item, idx) {
            tbodyItems.appendChild(createItemRow(item, idx));
        });
        reindexTableRows();
        recalculateItemTable();

        btnAddItemRow.addEventListener('click', function () {
            var currentCategory = inputKategori ? inputKategori.value : 'ATK';
            var catInfo = KATEGORI_MAPPING[currentCategory] || KATEGORI_MAPPING['ATK'];
            var defaultSatuan = catInfo.defaultSatuan || 'Pcs';
            var newIdx = tbodyItems.querySelectorAll('tr.item-pengajuan-row').length;

            tbodyItems.appendChild(createItemRow({
                deskripsi: '',
                qty: 1,
                satuan: defaultSatuan,
                harga_satuan: 0,
                subtotal: 0
            }, newIdx));

            reindexTableRows();
            recalculateItemTable();
        });

        // =========================================================================
        // SECTION 5: LAMPIRAN (MULTI-ATTACHMENT REPEATER)
        // =========================================================================
        var containerLampiran = document.getElementById('lampiran_rows_container');
        var btnAddLampiran = document.getElementById('btn_add_lampiran_row');

        function createLampiranRow(docName) {
            var row = document.createElement('div');
            row.className = 'row g-2 align-items-center lampiran-input-row mb-2';

            row.innerHTML = 
                '<div class="col-12 col-md-5">' +
                    '<input type="text" name="lampiran_nama" class="form-control form-control-sm lampiran-name-input" placeholder="Nama Dokumen (misal: Bukti Nota, Penawaran, Kuitansi)" value="' + (docName || '').replace(/"/g, '&quot;') + '">' +
                '</div>' +
                '<div class="col-10 col-md-6">' +
                    '<input type="file" name="lampiran_file" class="form-control form-control-sm lampiran-file-input">' +
                '</div>' +
                '<div class="col-2 col-md-1 text-center">' +
                    '<button type="button" class="btn btn-outline-danger btn-sm p-1 btn-delete-lampiran" title="Hapus Lampiran">' +
                        '<i class="bi bi-trash"></i>' +
                    '</button>' +
                '</div>';

            var btnDel = row.querySelector('.btn-delete-lampiran');
            var inputName = row.querySelector('.lampiran-name-input');
            var inputFile = row.querySelector('.lampiran-file-input');

            btnDel.addEventListener('click', function () {
                var allRows = containerLampiran.querySelectorAll('.lampiran-input-row');
                if (allRows.length > 1) {
                    row.remove();
                } else {
                    inputName.value = '';
                    inputFile.value = '';
                }
                syncLampiranData();
            });

            inputName.addEventListener('input', syncLampiranData);
            inputFile.addEventListener('change', syncLampiranData);

            return row;
        }

        function syncLampiranData() {
            var rows = containerLampiran.querySelectorAll('.lampiran-input-row');
            var lampiranMeta = [];
            rows.forEach(function (r, idx) {
                var nameInput = r.querySelector('.lampiran-name-input');
                var fileInput = r.querySelector('.lampiran-file-input');
                var valName = nameInput ? nameInput.value.trim() : '';
                var hasFile = Boolean(fileInput && fileInput.files && fileInput.files.length > 0);
                lampiranMeta.push({
                    index: idx,
                    nama: valName || ('Dokumen Lampiran #' + (idx + 1)),
                    file_selected: hasFile
                });
            });
            if (inputLampiranData) {
                inputLampiranData.value = JSON.stringify(lampiranMeta);
            }
        }

        // Initialize lampiran rows (empty by default, user fills document name freely)
        containerLampiran.innerHTML = '';
        containerLampiran.appendChild(createLampiranRow(''));
        syncLampiranData();

        btnAddLampiran.addEventListener('click', function () {
            containerLampiran.appendChild(createLampiranRow(''));
            syncLampiranData();
        });

        // =========================================================================
        // FORM SUBMISSION VALIDATION & DATA SYNC
        // =========================================================================
        form.addEventListener('submit', function (e) {
            recalculateItemTable();
            syncLampiranData();
        });

        console.log('[PengajuanBiayaWidget] 5-section restructuring initialized successfully.');
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPengajuanBiayaForm);
    } else {
        initPengajuanBiayaForm();
    }
})();
