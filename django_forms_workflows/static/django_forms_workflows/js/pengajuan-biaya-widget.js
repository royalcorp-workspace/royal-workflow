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

        // Hide data backing fields
        [fLimitAnggaran, fLimitTerpakai, fSisaLimit, fTotalNominal, fItemsData, fRincianItem, fLampiranData].forEach(function (fw) {
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
                        '<div class="p-3 rounded border bg-primary-subtle border-primary-subtle h-100">' +
                            '<div class="text-uppercase text-primary fw-bold" style="font-size: 11px; letter-spacing: 0.04em;">Nominal Pengajuan (Estimasi)</div>' +
                            '<div class="fs-4 fw-bolder text-primary mt-1 font-monospace" id="card_val_estimasi">Rp 0</div>' +
                            '<div class="text-primary-emphasis small mt-1" style="font-size: 11px;">Akumulasi Seluruh Item</div>' +
                        '</div>' +
                    '</div>' +
                '</div>' +
                '<div class="small text-muted mt-2 pt-1 fst-italic" style="font-size: 12px;">' +
                    '<i class="bi bi-info-circle me-1 text-primary"></i>Informasi Limit bersifat informatif. Tidak terdapat aturan yang melarang pengajuan melebihi limit.' +
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
                // Refresh description dropdown items for rows that are not custom
                refreshTableCategoryItems(inputKategori.value);
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

            var currentCategory = inputKategori ? inputKategori.value : 'ATK';
            var catItems = getCategoryItems(currentCategory);

            var isCustom = Boolean(itemData.deskripsi && catItems.indexOf(itemData.deskripsi) === -1 && itemData.deskripsi !== 'Lainnya (Ketik Manual)');

            var optionsHtml = '<option value="">-- Pilih Item --</option>';
            catItems.forEach(function (it) {
                var isSelected = (itemData.deskripsi === it) || (isCustom && it === 'Lainnya (Ketik Manual)');
                optionsHtml += '<option value="' + it.replace(/"/g, '&quot;') + '"' + (isSelected ? ' selected' : '') + '>' + it + '</option>';
            });

            var satuanOptionsHtml = '';
            SATUAN_OPTIONS.forEach(function (sat) {
                var isSelected = (itemData.satuan === sat);
                satuanOptionsHtml += '<option value="' + sat + '"' + (isSelected ? ' selected' : '') + '>' + sat + '</option>';
            });

            var qtyVal = parseInt(itemData.qty, 10) || 1;
            var hargaVal = parseInt(itemData.harga_satuan || itemData.harga, 10) || 0;
            var subtotalVal = qtyVal * hargaVal;

            tr.innerHTML = 
                '<td class="text-center fw-bold row-index-cell">' + (index + 1) + '</td>' +
                '<td>' +
                    '<select class="form-select form-select-sm item-select-desc mb-1">' + optionsHtml + '</select>' +
                    '<input type="text" class="form-control form-control-sm item-custom-desc" placeholder="Ketik nama item kebutuhan..." value="' + (isCustom ? (itemData.deskripsi || '').replace(/"/g, '&quot;') : '') + '" style="display: ' + (isCustom ? 'block' : 'none') + ';">' +
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
            var selectDesc = tr.querySelector('.item-select-desc');
            var inputCustom = tr.querySelector('.item-custom-desc');
            var inputQty = tr.querySelector('.item-input-qty');
            var inputHarga = tr.querySelector('.item-input-harga');
            var btnDelete = tr.querySelector('.btn-delete-item-row');

            selectDesc.addEventListener('change', function () {
                if (selectDesc.value === 'Lainnya (Ketik Manual)') {
                    inputCustom.style.display = 'block';
                    inputCustom.focus();
                } else {
                    inputCustom.style.display = 'none';
                    inputCustom.value = '';
                }
                recalculateItemTable();
            });

            inputCustom.addEventListener('input', function () {
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
                    selectDesc.value = '';
                    inputCustom.style.display = 'none';
                    inputCustom.value = '';
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

        function refreshTableCategoryItems(categoryName) {
            var catItems = getCategoryItems(categoryName);
            var rows = tbodyItems.querySelectorAll('tr.item-pengajuan-row');
            rows.forEach(function (row) {
                var selectDesc = row.querySelector('.item-select-desc');
                var inputCustom = row.querySelector('.item-custom-desc');
                if (!selectDesc) return;
                var currentVal = selectDesc.value;
                var isCustom = (selectDesc.value === 'Lainnya (Ketik Manual)' || Boolean(inputCustom && inputCustom.style.display === 'block'));

                var optionsHtml = '<option value="">-- Pilih Item --</option>';
                catItems.forEach(function (it) {
                    var isSelected = (currentVal === it) || (isCustom && it === 'Lainnya (Ketik Manual)');
                    optionsHtml += '<option value="' + it.replace(/"/g, '&quot;') + '"' + (isSelected ? ' selected' : '') + '>' + it + '</option>';
                });
                selectDesc.innerHTML = optionsHtml;
            });
        }

        function recalculateItemTable() {
            var rows = tbodyItems.querySelectorAll('tr.item-pengajuan-row');
            var totalSum = 0;
            var serializedItems = [];
            var rincianLines = [];

            rows.forEach(function (row, idx) {
                var selectDesc = row.querySelector('.item-select-desc');
                var inputCustom = row.querySelector('.item-custom-desc');
                var inputQty = row.querySelector('.item-input-qty');
                var selectSatuan = row.querySelector('.item-select-satuan');
                var inputHarga = row.querySelector('.item-input-harga');
                var subtotalCell = row.querySelector('.item-val-subtotal');

                var desc = selectDesc ? selectDesc.value : '';
                if (desc === 'Lainnya (Ketik Manual)' && inputCustom) {
                    desc = inputCustom.value.trim() || 'Item Kebutuhan Operasional';
                }
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

        function createLampiranRow(docName, isFirstRow) {
            var row = document.createElement('div');
            row.className = 'row g-2 align-items-center lampiran-input-row mb-2';

            var fileInputName = isFirstRow ? 'dokumen_pendukung' : 'lampiran_file';

            row.innerHTML = 
                '<div class="col-12 col-md-5">' +
                    '<input type="text" name="lampiran_nama" class="form-control form-control-sm lampiran-name-input" placeholder="Nama Dokumen (misal: Bukti Nota, Penawaran, Kuitansi)" value="' + (docName || '').replace(/"/g, '&quot;') + '">' +
                '</div>' +
                '<div class="col-10 col-md-6">' +
                    '<input type="file" name="' + fileInputName + '" class="form-control form-control-sm lampiran-file-input">' +
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

        // Initialize lampiran rows
        containerLampiran.innerHTML = '';
        containerLampiran.appendChild(createLampiranRow('Dokumen Lampiran Utama', true));
        syncLampiranData();

        btnAddLampiran.addEventListener('click', function () {
            containerLampiran.appendChild(createLampiranRow('', false));
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
