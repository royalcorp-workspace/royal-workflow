/**
 * pengajuan-biaya-widget.js
 * 
 * Specialized UI/UX Controller for "Pengajuan Biaya & Anggaran Operasional"
 * Harmonizes the form with Wireframe (refferense-wf.jpeg) and PRD v1.2:
 * 1. 2-Column Responsive Layout (Col A: Informasi Pengajuan & Col B: Detail Item dan Lampiran)
 * 2. Automatic prefilled & locked applicant fields (Kasir, Atasan, Dept, Bagian, Cabang, Tgl, No Pengajuan)
 * 3. Top 3 Metric Budget Cards (Sisa Limit Pengajuan Lalu, Sisa Limit Saat Ini, Total Biaya)
 * 4. Interactive Multi-Item Repeater (1-10 items with Nama, Tujuan, Qty, Satuan, Tgl, Harga, Subtotal)
 * 5. Real-time budget calculation & live synchronization to items_data, total_nominal, and rincian_item
 * 6. Conditional validation: Bukti struk mandatory for Reimburse (FR-05)
 */

(function () {
    'use strict';

    function formatRupiah(num) {
        var n = parseInt(num, 10);
        if (isNaN(n)) n = 0;
        return 'Rp ' + n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    }

    function initPengajuanBiayaForm() {
        var form = document.querySelector('form[data-form-slug="pengajuan-biaya"]') || 
                   document.querySelector('#form_pengajuan-biaya');
        if (!form) {
            // Check if fields specific to pengajuan-biaya are present
            if (!document.querySelector('[name="nomor_petty_cash"]') || 
                !document.querySelector('[name="kategori_biaya"]')) {
                return;
            }
            form = document.querySelector('form');
        }

        if (!form || form.dataset.wfInitialized === 'true') return;
        form.dataset.wfInitialized = 'true';

        console.log('[PengajuanBiayaWidget] Initializing 2-column layout and interactive repeater...');

        // 1. Locate fields
        var fieldsWrapper = form.querySelector('.form-fields-wrapper');
        if (!fieldsWrapper) return;

        function getFieldWrapper(fieldName) {
            var el = form.querySelector('.field-' + fieldName) || 
                     form.querySelector('[name="' + fieldName + '"]')?.closest('.field-wrapper') ||
                     form.querySelector('[name="' + fieldName + '"]')?.closest('.mb-3');
            return el;
        }

        // Applicant & Identity fields
        var fTanggal = getFieldWrapper('tanggal_pengajuan');
        var fNomor = getFieldWrapper('nomor_pengajuan');
        var fCabang = getFieldWrapper('cabang');
        var fDeptPembuat = getFieldWrapper('department_pembuat');
        var fBagianPembuat = getFieldWrapper('bagian_pembuat');
        var fNamaAtasan = getFieldWrapper('nama_atasan');
        var fNamaKasir = getFieldWrapper('inisiator_nama') || getFieldWrapper('nama_kasir');

        // Destination & Purpose fields
        var fNamaKegiatan = getFieldWrapper('nama_kegiatan');
        var fDeptPenerima = getFieldWrapper('department_penerima');
        var fBagianPenerima = getFieldWrapper('bagian_penerima');
        var fNamaPic = getFieldWrapper('nama_pic');
        var fTembusan = getFieldWrapper('tembusan');
        var fPettyCash = getFieldWrapper('nomor_petty_cash');
        var fKategori = getFieldWrapper('kategori_biaya');
        var fTipeTransaksi = getFieldWrapper('tipe_transaksi');
        var fUrgensi = getFieldWrapper('urgensi_pengajuan');

        // Attachment fields
        var fDokPendukung = getFieldWrapper('dokumen_pendukung');
        var fLampReal = getFieldWrapper('lampiran_realisasi');

        // Budget & Item fields
        var fLimitLalu = getFieldWrapper('sisa_limit_pengajuan_lalu');
        var fTotalNominal = getFieldWrapper('total_nominal');
        var fLimitSaatIni = getFieldWrapper('sisa_limit_saat_ini');
        var fItemsData = getFieldWrapper('items_data');
        var fRincianItem = getFieldWrapper('rincian_item');

        // Disbursement & Justification fields
        var fMetodePencairan = getFieldWrapper('metode_pencairan');
        var fNamaBank = getFieldWrapper('nama_bank');
        var fNoRekening = getFieldWrapper('nomor_rekening');
        var fAtasNama = getFieldWrapper('atas_nama_rekening');
        var fCatatan = getFieldWrapper('catatan_justifikasi');

        // Hide original generic section headers if any exist
        form.querySelectorAll('h3, .field-section_info_pemohon, .field-section_rincian_anggaran, .field-section_dokumen_lampiran').forEach(function(el) {
            el.style.display = 'none';
        });

        // Ensure no placeholders exist anywhere in the form (user requirement)
        form.querySelectorAll('[placeholder]').forEach(function(el) {
            el.removeAttribute('placeholder');
        });

        // Hide backing data fields from direct view (managed by repeater widget)
        if (fItemsData) fItemsData.style.display = 'none';
        if (fRincianItem) fRincianItem.style.display = 'none';
        if (fTotalNominal) fTotalNominal.style.display = 'none';
        if (fLimitLalu) fLimitLalu.style.display = 'none';
        if (fLimitSaatIni) fLimitSaatIni.style.display = 'none';

        // 2. Build the Wireframe Two-Column Skeleton
        var twocolWrapper = document.createElement('div');
        twocolWrapper.className = 'wf-twocol-wrapper';

        // --- Column Left (Informasi Pengajuan) ---
        var colLeft = document.createElement('div');
        colLeft.className = 'wf-col-left';

        // Panel 1: Identitas Pengajuan
        var panelIdentitas = document.createElement('div');
        panelIdentitas.className = 'wf-panel-box';
        panelIdentitas.innerHTML = 
            '<div class="wf-panel-header">' +
                '<h5 class="wf-panel-title"><i class="bi bi-file-earmark-text"></i> Identitas Pengajuan</h5>' +
                '<span class="wf-panel-badge">Sistem</span>' +
            '</div>' +
            '<div class="wf-panel-body" id="body_identitas"></div>';
        colLeft.appendChild(panelIdentitas);

        // Panel 2: Informasi Pembuat (100% Otomatis)
        var panelPembuat = document.createElement('div');
        panelPembuat.className = 'wf-panel-box';
        panelPembuat.innerHTML = 
            '<div class="wf-panel-header">' +
                '<h5 class="wf-panel-title"><i class="bi bi-person-badge"></i> Informasi Pembuat</h5>' +
                '<span class="wf-panel-badge wf-auto-badge"><i class="bi bi-lock-fill"></i> Terisi Otomatis</span>' +
            '</div>' +
            '<div class="wf-panel-body" id="body_pembuat"></div>';
        colLeft.appendChild(panelPembuat);

        // Panel 3: Tujuan Pengajuan
        var panelTujuan = document.createElement('div');
        panelTujuan.className = 'wf-panel-box';
        panelTujuan.innerHTML = 
            '<div class="wf-panel-header">' +
                '<h5 class="wf-panel-title"><i class="bi bi-send-check"></i> Tujuan Pengajuan</h5>' +
                '<span class="wf-panel-badge">Unit &amp; Divisi</span>' +
            '</div>' +
            '<div class="wf-panel-body" id="body_tujuan"></div>';
        colLeft.appendChild(panelTujuan);

        // Panel 4: Lampiran Dokumen
        var panelLampiran = document.createElement('div');
        panelLampiran.className = 'wf-panel-box';
        panelLampiran.innerHTML = 
            '<div class="wf-panel-header">' +
                '<h5 class="wf-panel-title"><i class="bi bi-paperclip"></i> Lampiran Dokumen</h5>' +
                '<span class="wf-panel-badge">Berkas</span>' +
            '</div>' +
            '<div class="wf-panel-body" id="body_lampiran"></div>';
        colLeft.appendChild(panelLampiran);

        // --- Column Right (Detail Item dan Lampiran) ---
        var colRight = document.createElement('div');
        colRight.className = 'wf-col-right';

        // Top 3 Limit & Budget Cards
        var metricGrid = document.createElement('div');
        metricGrid.className = 'wf-metric-grid';
        metricGrid.innerHTML = 
            '<div class="wf-metric-card" id="card_limit_lalu">' +
                '<div class="wf-metric-label">Sisa Limit Pengajuan Lalu</div>' +
                '<div class="wf-metric-value" id="val_limit_lalu">Rp 1.000.000</div>' +
                '<div class="small text-muted mt-1" style="font-size: 11.5px;">Saldo Operasional Lalu</div>' +
            '</div>' +
            '<div class="wf-metric-card limit-sisa" id="card_limit_saat_ini">' +
                '<div class="wf-metric-label">Sisa Limit Saat Ini</div>' +
                '<div class="wf-metric-value" id="val_limit_saat_ini">Rp 1.000.000</div>' +
                '<div class="small text-muted mt-1" id="sub_limit_saat_ini" style="font-size: 11.5px;">Tersedia Minggu Ini</div>' +
            '</div>' +
            '<div class="wf-metric-card total-biaya" id="card_total_biaya">' +
                '<div class="wf-metric-label">Total Biaya Pengajuan</div>' +
                '<div class="wf-metric-value" id="val_total_biaya">Rp 0</div>' +
                '<div class="small text-primary-emphasis mt-1" style="font-size: 11.5px;">Akumulasi Seluruh Item</div>' +
            '</div>';
        colRight.appendChild(metricGrid);

        // Panel: Detail Item Pengajuan (Repeater)
        var panelItems = document.createElement('div');
        panelItems.className = 'wf-panel-box';
        panelItems.innerHTML = 
            '<div class="wf-panel-header">' +
                '<h5 class="wf-panel-title"><i class="bi bi-card-checklist"></i> Detail Item Pengajuan</h5>' +
                '<span class="wf-panel-badge" id="badge_item_count">1 Item</span>' +
            '</div>' +
            '<div class="wf-panel-body">' +
                '<div class="wf-items-container" id="wf_items_container"></div>' +
                '<button type="button" class="wf-add-item-btn mt-3" id="btn_add_item">' +
                    '<i class="bi bi-plus-circle-fill"></i> Tambah Item Kebutuhan (Maks. 10)' +
                '</button>' +
                '<div class="small text-muted mt-2" id="guardrail_msg" style="display:none; color: #b91c1c !important;">' +
                    '<i class="bi bi-exclamation-triangle-fill me-1"></i> Perhatian: Total nominal melebihi sisa limit mingguan cabang!' +
                '</div>' +
            '</div>';
        colRight.appendChild(panelItems);

        // Panel: Pencairan Dana
        var panelPencairan = document.createElement('div');
        panelPencairan.className = 'wf-panel-box';
        panelPencairan.innerHTML = 
            '<div class="wf-panel-header">' +
                '<h5 class="wf-panel-title"><i class="bi bi-cash-stack"></i> Pencairan Dana</h5>' +
                '<span class="wf-panel-badge">Metode Bayar</span>' +
            '</div>' +
            '<div class="wf-panel-body" id="body_pencairan"></div>';
        colRight.appendChild(panelPencairan);

        // Panel: Catatan Justifikasi
        var panelCatatan = document.createElement('div');
        panelCatatan.className = 'wf-panel-box';
        panelCatatan.innerHTML = 
            '<div class="wf-panel-header">' +
                '<h5 class="wf-panel-title"><i class="bi bi-chat-left-quote"></i> Catatan Justifikasi</h5>' +
            '</div>' +
            '<div class="wf-panel-body" id="body_catatan"></div>';
        colRight.appendChild(panelCatatan);

        twocolWrapper.appendChild(colLeft);
        twocolWrapper.appendChild(colRight);

        // Insert new layout inside fieldsWrapper
        fieldsWrapper.insertBefore(twocolWrapper, fieldsWrapper.firstChild);

        // Helper to append field wrapper
        function placeField(fieldWrapper, targetId) {
            if (!fieldWrapper) return;
            var target = document.getElementById(targetId);
            if (target) {
                target.appendChild(fieldWrapper);
            }
        }

        // Place fields into panels
        var bIdentitas = document.getElementById('body_identitas');
        var rowId1 = document.createElement('div');
        rowId1.className = 'row g-3.5 mb-2.5';
        if (fTanggal) {
            fTanggal.classList.add('col-md-6');
            rowId1.appendChild(fTanggal);
        }
        if (fNomor) {
            fNomor.classList.add('col-md-6');
            rowId1.appendChild(fNomor);
        }
        bIdentitas.appendChild(rowId1);
        if (fCabang) bIdentitas.appendChild(fCabang);

        // Panel Pembuat
        var bPembuat = document.getElementById('body_pembuat');
        var rowPb1 = document.createElement('div');
        rowPb1.className = 'row g-3.5 mb-2.5';
        if (fDeptPembuat) {
            fDeptPembuat.classList.add('col-md-6');
            rowPb1.appendChild(fDeptPembuat);
        }
        if (fBagianPembuat) {
            fBagianPembuat.classList.add('col-md-6');
            rowPb1.appendChild(fBagianPembuat);
        }
        bPembuat.appendChild(rowPb1);

        var rowPb2 = document.createElement('div');
        rowPb2.className = 'row g-3.5 mb-2.5';
        if (fNamaAtasan) {
            fNamaAtasan.classList.add('col-md-6');
            rowPb2.appendChild(fNamaAtasan);
        }
        if (fNamaKasir) {
            fNamaKasir.classList.add('col-md-6');
            rowPb2.appendChild(fNamaKasir);
        }
        bPembuat.appendChild(rowPb2);

        // Add auto badges to applicant fields
        [fTanggal, fNomor, fCabang, fDeptPembuat, fBagianPembuat, fNamaAtasan, fNamaKasir].forEach(function(fw) {
            if (!fw) return;
            var lbl = fw.querySelector('label');
            if (lbl && !lbl.querySelector('.wf-auto-badge')) {
                var badge = document.createElement('span');
                badge.className = 'wf-auto-badge';
                badge.innerHTML = '<i class="bi bi-lock-fill"></i> Otomatis';
                lbl.appendChild(badge);
            }
            // Ensure input has readonly styling
            var inp = fw.querySelector('input, select');
            if (inp) {
                inp.setAttribute('readonly', 'readonly');
                inp.classList.add('field-readonly');
                if (inp.tagName.toLowerCase() === 'select') {
                    inp.addEventListener('mousedown', function(e) { e.preventDefault(); });
                }
            }
        });

        // Panel Tujuan
        var bTujuan = document.getElementById('body_tujuan');
        if (fNamaKegiatan) bTujuan.appendChild(fNamaKegiatan);

        var rowTj1 = document.createElement('div');
        rowTj1.className = 'row g-3.5 mb-2.5';
        if (fDeptPenerima) {
            fDeptPenerima.classList.add('col-md-6');
            rowTj1.appendChild(fDeptPenerima);
        }
        if (fBagianPenerima) {
            fBagianPenerima.classList.add('col-md-6');
            rowTj1.appendChild(fBagianPenerima);
        }
        bTujuan.appendChild(rowTj1);

        var rowTj2 = document.createElement('div');
        rowTj2.className = 'row g-3.5 mb-2.5';
        if (fNamaPic) {
            fNamaPic.classList.add('col-md-6');
            rowTj2.appendChild(fNamaPic);
        }
        if (fTembusan) {
            fTembusan.classList.add('col-md-6');
            rowTj2.appendChild(fTembusan);
        }
        bTujuan.appendChild(rowTj2);

        if (fPettyCash) bTujuan.appendChild(fPettyCash);

        var rowTj3 = document.createElement('div');
        rowTj3.className = 'row g-3.5 mb-2.5';
        if (fKategori) {
            fKategori.classList.add('col-md-6');
            rowTj3.appendChild(fKategori);
        }
        if (fTipeTransaksi) {
            fTipeTransaksi.classList.add('col-md-6');
            rowTj3.appendChild(fTipeTransaksi);
        }
        bTujuan.appendChild(rowTj3);

        if (fUrgensi) bTujuan.appendChild(fUrgensi);

        // Panel Lampiran
        var bLampiran = document.getElementById('body_lampiran');
        if (fDokPendukung) bLampiran.appendChild(fDokPendukung);
        if (fLampReal) {
            bLampiran.appendChild(fLampReal);
            var inpReal = fLampReal.querySelector('input');
            if (inpReal) inpReal.setAttribute('disabled', 'disabled');
            var helpReal = fLampReal.querySelector('.form-text, .help-block');
            if (helpReal) {
                helpReal.innerHTML = '<span class="badge bg-secondary me-1">Tahap 6 Closing</span> Diunggah oleh Kasir saat Pelaporan Realisasi Biaya riil';
            }
        }

        // Panel Pencairan
        var bPencairan = document.getElementById('body_pencairan');
        if (fMetodePencairan) bPencairan.appendChild(fMetodePencairan);

        var rowPc1 = document.createElement('div');
        rowPc1.className = 'row g-3.5 mb-2.5';
        if (fNamaBank) {
            fNamaBank.classList.add('col-md-6');
            rowPc1.appendChild(fNamaBank);
        }
        if (fNoRekening) {
            fNoRekening.classList.add('col-md-6');
            rowPc1.appendChild(fNoRekening);
        }
        bPencairan.appendChild(rowPc1);
        if (fAtasNama) bPencairan.appendChild(fAtasNama);

        // Panel Catatan
        var bCatatan = document.getElementById('body_catatan');
        if (fCatatan) bCatatan.appendChild(fCatatan);

        // 3. Multi-Item Interactive Repeater Logic
        var itemsContainer = document.getElementById('wf_items_container');
        var btnAddItem = document.getElementById('btn_add_item');
        var badgeItemCount = document.getElementById('badge_item_count');
        var valLimitLalu = document.getElementById('val_limit_lalu');
        var valLimitSaatIni = document.getElementById('val_limit_saat_ini');
        var valTotalBiaya = document.getElementById('val_total_biaya');
        var cardLimitSaatIni = document.getElementById('card_limit_saat_ini');
        var guardrailMsg = document.getElementById('guardrail_msg');

        var inputTotal = form.querySelector('[name="total_nominal"]');
        var inputItemsData = form.querySelector('[name="items_data"]');
        var inputRincian = form.querySelector('[name="rincian_item"]');
        var inputLimitLalu = form.querySelector('[name="sisa_limit_pengajuan_lalu"]');
        var inputLimitSaatIni = form.querySelector('[name="sisa_limit_saat_ini"]');

        var limitLaluNominal = 1000000;
        if (inputLimitLalu && inputLimitLalu.value) {
            var parsed = parseInt(inputLimitLalu.value, 10);
            if (!isNaN(parsed) && parsed > 0) limitLaluNominal = parsed;
        } else if (inputLimitLalu) {
            inputLimitLalu.value = limitLaluNominal;
        }
        valLimitLalu.textContent = formatRupiah(limitLaluNominal);

        var itemsList = [];

        // Parse existing items_data if available (e.g. from draft or server)
        if (inputItemsData && inputItemsData.value && inputItemsData.value.trim().startsWith('[')) {
            try {
                var parsedItems = JSON.parse(inputItemsData.value);
                if (Array.isArray(parsedItems) && parsedItems.length > 0) {
                    itemsList = parsedItems;
                }
            } catch (e) {
                console.warn('[PengajuanBiayaWidget] Error parsing existing items_data:', e);
            }
        }

        // If itemsList is empty, default to 1 empty item
        if (itemsList.length === 0) {
            itemsList.push({
                nama: '',
                tujuan: '',
                qty: 1,
                satuan: 'Pcs',
                tgl: '',
                harga: 0,
                subtotal: 0
            });
        }

        function renderItems() {
            itemsContainer.innerHTML = '';
            var total = 0;

            itemsList.forEach(function (item, idx) {
                var subtotal = (parseInt(item.qty, 10) || 0) * (parseInt(item.harga, 10) || 0);
                item.subtotal = subtotal;
                total += subtotal;

                var card = document.createElement('div');
                card.className = 'wf-item-card';
                card.dataset.index = idx;

                var deleteBtnHtml = itemsList.length > 1
                    ? '<button type="button" class="wf-item-del-btn" title="Hapus Item" data-del="' + idx + '"><i class="bi bi-trash3"></i></button>'
                    : '';

                card.innerHTML = 
                    '<div class="wf-item-header">' +
                        '<div class="d-flex align-items-center gap-2">' +
                            '<div class="wf-item-number-box">' + (idx + 1) + '</div>' +
                            '<div class="wf-item-subtotal-badge" id="disp_subtotal_' + idx + '">' + formatRupiah(subtotal) + '</div>' +
                        '</div>' +
                        deleteBtnHtml +
                    '</div>' +
                    '<div class="row g-3.5 mb-3">' +
                        '<div class="col-12">' +
                            '<label class="form-label fw-semibold mb-1">Nama Item Barang / Jasa <span class="text-danger">*</span></label>' +
                            '<input type="text" class="form-control inp-item-nama" data-field="nama" value="' + (item.nama || '') + '" required>' +
                        '</div>' +
                    '</div>' +
                    '<div class="row g-3.5 mb-3">' +
                        '<div class="col-12">' +
                            '<label class="form-label fw-semibold mb-1">Tujuan / Keperluan <span class="text-danger">*</span></label>' +
                            '<input type="text" class="form-control inp-item-tujuan" data-field="tujuan" value="' + (item.tujuan || '') + '" required>' +
                        '</div>' +
                    '</div>' +
                    '<div class="row g-3.5 mb-3">' +
                        '<div class="col-4 col-sm-4">' +
                            '<label class="form-label fw-semibold mb-1">Qty <span class="text-danger">*</span></label>' +
                            '<input type="number" min="1" class="form-control inp-item-qty" data-field="qty" value="' + (item.qty || 1) + '" required>' +
                        '</div>' +
                        '<div class="col-4 col-sm-4">' +
                            '<label class="form-label fw-semibold mb-1">Satuan</label>' +
                            '<select class="form-select inp-item-satuan" data-field="satuan">' +
                                '<option value="Pcs"' + (item.satuan === 'Pcs' ? ' selected' : '') + '>Pcs</option>' +
                                '<option value="Rim"' + (item.satuan === 'Rim' ? ' selected' : '') + '>Rim</option>' +
                                '<option value="Box"' + (item.satuan === 'Box' ? ' selected' : '') + '>Box</option>' +
                                '<option value="Pack"' + (item.satuan === 'Pack' ? ' selected' : '') + '>Pack</option>' +
                                '<option value="Unit"' + (item.satuan === 'Unit' ? ' selected' : '') + '>Unit</option>' +
                                '<option value="Liter"' + (item.satuan === 'Liter' ? ' selected' : '') + '>Liter</option>' +
                                '<option value="Kali"' + (item.satuan === 'Kali' ? ' selected' : '') + '>Kali</option>' +
                                '<option value="Bulan"' + (item.satuan === 'Bulan' ? ' selected' : '') + '>Bulan</option>' +
                            '</select>' +
                        '</div>' +
                        '<div class="col-4 col-sm-4">' +
                            '<label class="form-label fw-semibold mb-1">Tgl Butuh</label>' +
                            '<input type="date" class="form-control inp-item-tgl" data-field="tgl" value="' + (item.tgl || '') + '">' +
                        '</div>' +
                    '</div>' +
                    '<div class="row g-3.5">' +
                        '<div class="col-6">' +
                            '<label class="form-label fw-semibold mb-1">Harga Satuan (Rp) <span class="text-danger">*</span></label>' +
                            '<input type="number" min="0" step="100" class="form-control inp-item-harga" data-field="harga" value="' + (item.harga || 0) + '" required>' +
                        '</div>' +
                        '<div class="col-6">' +
                            '<label class="form-label fw-semibold mb-1">Nominal Biaya / Subtotal</label>' +
                            '<input type="text" class="form-control bg-light fw-bold inp-item-subtotal text-primary" value="' + formatRupiah(subtotal) + '" readonly>' +
                        '</div>' +
                    '</div>';

                itemsContainer.appendChild(card);
            });

            badgeItemCount.textContent = itemsList.length + ' Item' + (itemsList.length > 1 ? 's' : '');
            if (btnAddItem) {
                btnAddItem.style.display = itemsList.length >= 10 ? 'none' : 'flex';
            }

            // Sync Totals & Limits
            syncTotalsAndLimits(total);
        }

        function syncTotalsAndLimits(total) {
            valTotalBiaya.textContent = formatRupiah(total);
            var sisaSaatIni = limitLaluNominal - total;
            valLimitSaatIni.textContent = formatRupiah(sisaSaatIni);

            if (inputTotal) inputTotal.value = total;
            if (inputLimitSaatIni) inputLimitSaatIni.value = sisaSaatIni;

            // Guardrail Visual Styling
            if (sisaSaatIni < 0) {
                cardLimitSaatIni.className = 'wf-metric-card limit-sisa danger';
                if (guardrailMsg) guardrailMsg.style.display = 'block';
            } else if (sisaSaatIni < 200000) {
                cardLimitSaatIni.className = 'wf-metric-card limit-sisa warning';
                if (guardrailMsg) guardrailMsg.style.display = 'none';
            } else {
                cardLimitSaatIni.className = 'wf-metric-card limit-sisa';
                if (guardrailMsg) guardrailMsg.style.display = 'none';
            }

            // Serialize structured JSON to items_data
            var cleanItems = itemsList.map(function (it) {
                return {
                    "Nama Item": it.nama || '',
                    "Tujuan": it.tujuan || '',
                    "Qty": parseInt(it.qty, 10) || 1,
                    "Satuan": it.satuan || 'Pcs',
                    "Tgl Dibutuhkan": it.tgl || '',
                    "Harga Satuan": parseInt(it.harga, 10) || 0,
                    "Subtotal": (parseInt(it.qty, 10) || 1) * (parseInt(it.harga, 10) || 0)
                };
            });
            if (inputItemsData) inputItemsData.value = JSON.stringify(cleanItems);

            // Generate clean human-readable summary for rincian_item
            var summaryLines = itemsList.map(function (it, idx) {
                var sub = (parseInt(it.qty, 10) || 1) * (parseInt(it.harga, 10) || 0);
                var line = (idx + 1) + '. ' + (it.nama || 'Item') + ' - ' + (it.qty || 1) + ' ' + (it.satuan || 'Pcs') + 
                           ' @ ' + formatRupiah(it.harga || 0) + ' = ' + formatRupiah(sub);
                if (it.tujuan) line += ' (Tujuan: ' + it.tujuan + ')';
                return line;
            });
            if (inputRincian) inputRincian.value = summaryLines.join('\n');
        }

        // Add Item Click
        if (btnAddItem) {
            btnAddItem.addEventListener('click', function () {
                if (itemsList.length >= 10) return;
                itemsList.push({
                    nama: '',
                    tujuan: '',
                    qty: 1,
                    satuan: 'Pcs',
                    tgl: '',
                    harga: 0,
                    subtotal: 0
                });
                renderItems();
                // Focus on the new item nama field
                var inputs = itemsContainer.querySelectorAll('.inp-item-nama');
                if (inputs.length > 0) inputs[inputs.length - 1].focus();
            });
        }

        // Event delegation for item card inputs & delete button
        itemsContainer.addEventListener('input', function (e) {
            var target = e.target;
            var card = target.closest('.wf-item-card');
            if (!card) return;
            var idx = parseInt(card.dataset.index, 10);
            if (isNaN(idx) || !itemsList[idx]) return;

            var field = target.dataset.field;
            if (field) {
                itemsList[idx][field] = target.value;
                if (field === 'qty' || field === 'harga') {
                    var sub = (parseInt(itemsList[idx].qty, 10) || 0) * (parseInt(itemsList[idx].harga, 10) || 0);
                    itemsList[idx].subtotal = sub;
                    var badge = document.getElementById('disp_subtotal_' + idx);
                    if (badge) badge.textContent = formatRupiah(sub);
                    var inpSub = card.querySelector('.inp-item-subtotal');
                    if (inpSub) inpSub.value = formatRupiah(sub);

                    var currentTotal = itemsList.reduce(function (acc, it) {
                        return acc + ((parseInt(it.qty, 10) || 0) * (parseInt(it.harga, 10) || 0));
                    }, 0);
                    syncTotalsAndLimits(currentTotal);
                } else {
                    syncTotalsAndLimits(itemsList.reduce(function (acc, it) { return acc + (it.subtotal || 0); }, 0));
                }
            }
        });

        itemsContainer.addEventListener('change', function (e) {
            var target = e.target;
            var card = target.closest('.wf-item-card');
            if (!card) return;
            var idx = parseInt(card.dataset.index, 10);
            if (isNaN(idx) || !itemsList[idx]) return;

            var field = target.dataset.field;
            if (field) {
                itemsList[idx][field] = target.value;
                syncTotalsAndLimits(itemsList.reduce(function (acc, it) { return acc + (it.subtotal || 0); }, 0));
            }
        });

        itemsContainer.addEventListener('click', function (e) {
            var btn = e.target.closest('.wf-item-del-btn');
            if (!btn) return;
            var idx = parseInt(btn.dataset.del, 10);
            if (isNaN(idx) || itemsList.length <= 1) return;
            itemsList.splice(idx, 1);
            renderItems();
        });

        // 4. Conditional Logic: Tipe Transaksi & Bukti Struk (FR-05)
        var selectTipeTransaksi = form.querySelector('[name="tipe_transaksi"]');
        function updateTipeTransaksiRules() {
            if (!selectTipeTransaksi || !fDokPendukung) return;
            var isReimburse = selectTipeTransaksi.value === 'Reimburse';
            var lbl = fDokPendukung.querySelector('label');
            var help = fDokPendukung.querySelector('.form-text, .help-block');
            var inp = fDokPendukung.querySelector('input[type="file"]');

            if (isReimburse) {
                if (lbl && !lbl.querySelector('.reimburse-badge')) {
                    var b = document.createElement('span');
                    b.className = 'badge bg-danger ms-2 reimburse-badge';
                    b.textContent = 'Wajib untuk Reimburse (FR-05)';
                    lbl.appendChild(b);
                }
                if (help) {
                    help.innerHTML = '<span class="text-danger fw-semibold"><i class="bi bi-asterisk"></i> Wajib melampirkan nota riil / bukti pembayaran yang telah dikeluarkan saat pengajuan reimbursement.</span>';
                }
                if (inp) inp.setAttribute('required', 'required');
            } else {
                var b = lbl ? lbl.querySelector('.reimburse-badge') : null;
                if (b) b.remove();
                if (help) {
                    help.innerHTML = 'Unggah berkas penawaran vendor, proforma invoice, kuitansi, atau proposal kebutuhan (PDF/JPG/PNG).';
                }
                if (inp) inp.removeAttribute('required');
            }
        }
        if (selectTipeTransaksi) {
            selectTipeTransaksi.addEventListener('change', updateTipeTransaksiRules);
            updateTipeTransaksiRules();
        }

        // 5. Initial Repeater Render
        renderItems();
        console.log('[PengajuanBiayaWidget] Initialization complete.');
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPengajuanBiayaForm);
    } else {
        initPengajuanBiayaForm();
    }
})();
