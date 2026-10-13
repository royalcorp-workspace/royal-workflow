/**
 * Kontrak Grid Widget & Dynamic Interactive Enhancements
 * Royal Workflow - Permohonan Kontrak Module
 */

(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        initKontrakFormWidgets();
    });

    function initKontrakFormWidgets() {
        const form = document.querySelector('form[data-form-enhancements="true"]') || document.querySelector('form');
        if (!form) return;

        // Check if any of the target fields exist
        const hasAsset = form.querySelector('[name="asset_toko"]');
        const hasMarket = form.querySelector('[name="market_share"]');
        const hasTarget = form.querySelector('[name="target_incentive"]');
        const hasDiscount = form.querySelector('[name="discount_scheme"]');
        const hasTier = form.querySelector('[name="tier_support"]');
        const hasJDE = form.querySelector('[name="kode_customer_jde"]');

        if (!hasAsset && !hasMarket && !hasTarget && !hasDiscount && !hasTier && !hasJDE) {
            return;
        }

        console.log('[KontrakGridWidget] Initializing Permohonan Kontrak widgets...');

        const STORAGE_KEY = 'royal_kontrak_form_draft';
        let hasRestoredDraft = false;

        // Try restoring draft from localStorage (client-side form persistence)
        try {
            const rawDraft = localStorage.getItem(STORAGE_KEY);
            if (rawDraft) {
                const draftData = JSON.parse(rawDraft);
                if (draftData && typeof draftData === 'object' && hasMeaningfulData(draftData)) {
                    Object.keys(draftData).forEach(name => {
                        const val = draftData[name];
                        const el = form.querySelector(`[name="${name}"]`);
                        if (!el) return;

                        if (el.type === 'checkbox') {
                            el.checked = Boolean(val);
                        } else if (el.type === 'radio') {
                            const radio = form.querySelector(`[name="${name}"][value="${val}"]`);
                            if (radio) radio.checked = true;
                        } else {
                            if (val !== undefined && val !== null) {
                                el.value = val;
                            }
                        }
                    });
                    hasRestoredDraft = true;
                    console.log('[KontrakDraft] Draft successfully restored from localStorage');
                }
            }
        } catch (e) {
            console.warn('[KontrakDraft] Error parsing saved draft:', e);
        }

        if (!hasRestoredDraft) {
            // Clean initial state for fresh new submissions
            const storeFields = ['kode_customer_jde', 'nama_toko', 'nama_pemilik', 'alamat_toko', 'no_telepon', 'kota', 'nomor_identitas', 'komponen_biaya', 'nomor_spk'];
            storeFields.forEach(name => {
                const el = form.querySelector(`[name="${name}"]`);
                if (el) el.value = '';
            });

            // Ensure grid fields start empty
            ['asset_toko', 'market_share', 'target_incentive', 'discount_scheme', 'tier_support'].forEach(name => {
                const f = form.querySelector(`[name="${name}"]`);
                if (f) f.value = '[]';
            });
        }

        // 0. Lock Readonly Fields & Force Slate-200 Tone
        lockReadonlyFields(form);

        // 1. Setup Wizard Step Panes (Client-side view isolation)
        setupWizardPanes(form);

        // 2. Setup JDE Lookup
        setupJDELookup(form);

        // 3. Setup Durasi Calculation
        setupDurasiCalculation(form);

        // 4. Setup Auto SPK Preview
        setupSPKAutoNumber(form);

        // 5. Setup Dynamic Grids
        setupAssetTokoGrid(form);
        setupMarketShareGrid(form);
        setupTargetIncentiveGrid(form);
        setupDiscountSchemeGrid(form);
        setupTierSupportGrid(form);

        // 6. Setup Step 3 Preview & Tabs
        setupStep3Preview(form);

        // 7. Setup Wizard Footer Actions & Stepper Navigation
        setupWizardFooter(form);

        // Re-render grids and trigger dynamic updates if draft was restored
        if (hasRestoredDraft) {
            if (window.renderAssetGrid) window.renderAssetGrid();
            if (window.renderMarketGrid) window.renderMarketGrid();
            if (window.renderTargetGrid) window.renderTargetGrid();
            if (window.renderDiscountGrid) window.renderDiscountGrid();
            if (window.renderTierGrid) window.renderTierGrid();

            // Trigger updates on Brand & Cabang to recalculate Nomor SPK
            const brandSelect = form.querySelector('[name="brand"]');
            const cabangSelect = form.querySelector('[name="cabang"]');
            if (brandSelect && brandSelect.value) {
                brandSelect.dispatchEvent(new Event('change', { bubbles: true }));
                brandSelect.dispatchEvent(new Event('input', { bubbles: true }));
            }
            if (cabangSelect && cabangSelect.value) {
                cabangSelect.dispatchEvent(new Event('change', { bubbles: true }));
                cabangSelect.dispatchEvent(new Event('input', { bubbles: true }));
            }

            // Display restored notification banner
            showDraftRestoredAlert(form);
            updateAutoSaveStatus('saved');
        }

        // 8. Setup Client-side Draft Persistence & Auto-save
        setupFormPersistence(form, hasRestoredDraft);
    }

    /* --------------------------------------------------------------------------
     * 0. Force Readonly & Slate-200 Lock
     * -------------------------------------------------------------------------- */
    function lockReadonlyFields(form) {
        const targetReadonlyFields = ['nama_toko', 'nama_pemilik', 'alamat_toko', 'no_telepon', 'kota', 'nomor_spk'];
        targetReadonlyFields.forEach(fieldName => {
            const el = form.querySelector(`[name="${fieldName}"]`);
            if (el) {
                el.setAttribute('readonly', 'readonly');
                el.classList.add('jde-readonly-locked');
                el.classList.add('jde-autofill-readonly');
                // Set inline style sebagai fallback mutlak agar tidak bisa ditimpa CSS Bootstrap:
                el.style.setProperty('background-color', '#e2e8f0', 'important');
                el.style.setProperty('border-color', '#94a3b8', 'important');
                el.style.setProperty('color', '#0f172a', 'important');
                el.style.setProperty('cursor', 'not-allowed', 'important');
                el.style.setProperty('font-weight', fieldName === 'nomor_spk' ? '600' : '500', 'important');
                if (fieldName === 'nomor_spk') {
                    el.style.setProperty('letter-spacing', '0.025em', 'important');
                    el.setAttribute('tabindex', '-1');
                }

                // Block keyboard changes while allowing Tab navigation
                if (!el.dataset.readonlyBound) {
                    el.dataset.readonlyBound = 'true';
                    el.addEventListener('keydown', function (e) {
                        if (e.key !== 'Tab') {
                            e.preventDefault();
                        }
                    });
                    el.addEventListener('paste', function (e) {
                        e.preventDefault();
                    });
                }
            }
        });
    }

    /* --------------------------------------------------------------------------
     * 1. Multi-Step Wizard View Isolation (.wizard-step-pane)
     * -------------------------------------------------------------------------- */
    function setupWizardPanes(form) {
        const wrapper = form.querySelector('.form-fields-wrapper');
        if (!wrapper) return;

        // Prevent double wrapping
        if (wrapper.querySelector('.wizard-step-pane')) return;

        const STEP1_FIELDS = new Set([
            'nomor_spk', 'cabang', 'brand', 'perusahaan',
            'kode_customer_jde', 'nama_toko', 'nama_pemilik', 'alamat_toko',
            'no_telepon', 'kota', 'jenis_identitas', 'nomor_identitas',
            'asset_toko', 'market_share'
        ]);

        const STEP2_FIELDS = new Set([
            'info_kontrak_lama', 'tanggal_mulai', 'tanggal_berakhir', 'durasi', 'grace_period',
            'jenis_pajak', 'top', 'support_promosi',
            'target_incentive', 'pct_support_promo', 'frekuensi_pencairan', 'syarat_pencairan',
            'komponen_biaya', 'pengecualian_ketentuan_support', 'discount_scheme',
            'tier_support', 'metode_pembayaran', 'discount_do', 'ketentuan_do',
            'kota_penandatanganan', 'tanggal_penandatanganan', 'rekening_perusahaan', 'catatan_lain'
        ]);

        const STEP3_FIELDS = new Set([
            'preview_contract_tab',
            'chk_lampiran_spk_lalu', 'chk_asset_toko_diisi', 'chk_market_share_diisi', 'chk_lampiran_umum',
            'chk_konfirmasi_data', 'chk_konfirmasi_preview'
        ]);

        const pane1 = document.createElement('div');
        pane1.id = 'wizardStepPane1';
        pane1.className = 'wizard-step-pane active';
        pane1.dataset.step = '0';

        const pane2 = document.createElement('div');
        pane2.id = 'wizardStepPane2';
        pane2.className = 'wizard-step-pane';
        pane2.dataset.step = '1';
        pane2.style.setProperty('display', 'none', 'important');

        const pane3 = document.createElement('div');
        pane3.id = 'wizardStepPane3';
        pane3.className = 'wizard-step-pane';
        pane3.dataset.step = '2';
        pane3.style.setProperty('display', 'none', 'important');

        // Distribute direct children of wrapper
        const children = Array.from(wrapper.children);
        let currentTargetPane = pane1;

        children.forEach(child => {
            const inputs = Array.from(child.querySelectorAll('input, select, textarea'));
            const names = inputs.map(i => i.name).filter(Boolean);
            const className = child.className || '';

            let assignedPane = null;

            if (names.some(n => STEP1_FIELDS.has(n)) || Array.from(STEP1_FIELDS).some(n => className.includes('field-' + n))) {
                assignedPane = pane1;
                currentTargetPane = pane1;
            } else if (names.some(n => STEP2_FIELDS.has(n)) || Array.from(STEP2_FIELDS).some(n => className.includes('field-' + n))) {
                assignedPane = pane2;
                currentTargetPane = pane2;
            } else if (names.some(n => STEP3_FIELDS.has(n)) || Array.from(STEP3_FIELDS).some(n => className.includes('field-' + n)) || child.querySelector('[name="preview_contract_tab"]') || className.includes('field-preview_contract_tab')) {
                assignedPane = pane3;
                currentTargetPane = pane3;
            } else {
                if (child.querySelector('button[type="submit"]') || child.classList.contains('mt-4')) {
                    child.style.setProperty('display', 'none', 'important');
                    assignedPane = pane3;
                } else {
                    assignedPane = currentTargetPane;
                }
            }

            assignedPane.appendChild(child);
        });

        wrapper.appendChild(pane1);
        wrapper.appendChild(pane2);
        wrapper.appendChild(pane3);
        console.log('[KontrakGridWidget] Form fields successfully partitioned into 3 isolated wizard step panes.');
    }

    /* --------------------------------------------------------------------------
     * Helper: Number & Currency Formatter
     * -------------------------------------------------------------------------- */
    function formatRupiah(num) {
        if (num === null || num === undefined || isNaN(num)) return '0';
        return Number(num).toLocaleString('id-ID');
    }

    function parseRupiah(val) {
        if (!val) return 0;
        const cleaned = String(val).replace(/[^0-9.-]/g, '');
        return parseFloat(cleaned) || 0;
    }

    /* --------------------------------------------------------------------------
     * 1. JDE Customer Lookup
     * -------------------------------------------------------------------------- */
    function setupJDELookup(form) {
        const jdeInput = form.querySelector('[name="kode_customer_jde"]');
        if (!jdeInput) return;

        const parent = jdeInput.parentElement;
        if (!parent || parent.querySelector('.jde-lookup-btn')) return;

        // Wrapper
        const wrap = document.createElement('div');
        wrap.className = 'jde-lookup-wrap mt-1';

        jdeInput.parentNode.insertBefore(wrap, jdeInput);
        wrap.appendChild(jdeInput);

        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'btn btn-primary jde-lookup-btn';
        btn.innerHTML = '<i class="bi bi-search"></i> Cari Customer JDE';
        wrap.appendChild(btn);

        const alertBox = document.createElement('div');
        alertBox.className = 'jde-lookup-alert alert';
        parent.appendChild(alertBox);

        // Enforce readonly lock & styling on target fields
        lockReadonlyFields(form);

        // Ensure jenis_identitas & nomor_identitas are strictly editable
        const editableFieldNames = ['jenis_identitas', 'nomor_identitas'];
        editableFieldNames.forEach(fieldName => {
            const el = form.querySelector(`[name="${fieldName}"]`);
            if (el) {
                el.removeAttribute('readonly');
                el.classList.remove('jde-autofill-readonly');
                el.style.cursor = 'auto';
            }
        });

        async function doLookup() {
            const code = jdeInput.value.trim();
            if (!code) {
                alertBox.className = 'jde-lookup-alert alert alert-warning d-block';
                alertBox.innerHTML = '<i class="bi bi-exclamation-triangle me-1"></i> Silakan masukkan Kode Customer JDE (contoh: 150731).';
                return;
            }

            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Mencari...';

            try {
                const res = await fetch(`/api/lookup/jde-customer/?code=${encodeURIComponent(code)}`);
                const data = await res.json();

                if (res.ok && data.success && data.customer) {
                    const c = data.customer;
                    setFieldValue(form, 'nama_toko', c.nama_toko);
                    setFieldValue(form, 'nama_pemilik', c.nama_pemilik);
                    setFieldValue(form, 'alamat_toko', c.alamat_toko);
                    setFieldValue(form, 'no_telepon', c.no_telepon);
                    setFieldValue(form, 'kota', c.kota);
                    if (c.nomor_identitas || c.no_identitas) {
                        setFieldValue(form, 'nomor_identitas', c.nomor_identitas || c.no_identitas);
                    }
                    if (c.jenis_identitas) {
                        setFieldValue(form, 'jenis_identitas', c.jenis_identitas);
                    }
                    if (c.cabang) setFieldValue(form, 'cabang', c.cabang);
                    lockReadonlyFields(form);

                    alertBox.className = 'jde-lookup-alert alert alert-success d-block';
                    alertBox.innerHTML = `<i class="bi bi-check-circle me-1"></i> Data JDE Ditemukan: <strong>${c.nama_toko}</strong> (${c.nama_pemilik}) - ${c.kota}`;

                    // Also prepopulate asset_toko first row if empty
                    const assetField = form.querySelector('[name="asset_toko"]');
                    if (assetField && (!assetField.value || assetField.value === '[]')) {
                        const initAsset = [{
                            no: 1,
                            keterangan: c.nama_toko,
                            alamat: c.alamat_toko,
                            status: 'Pribadi'
                        }];
                        assetField.value = JSON.stringify(initAsset);
                        if (window.renderAssetGrid) window.renderAssetGrid();
                    }
                } else {
                    alertBox.className = 'jde-lookup-alert alert alert-danger d-block';
                    alertBox.innerHTML = `<i class="bi bi-x-circle me-1"></i> ${data.message || 'Customer JDE tidak ditemukan.'}`;
                }
            } catch (err) {
                console.error('Error lookup JDE:', err);
                alertBox.className = 'jde-lookup-alert alert alert-danger d-block';
                alertBox.innerHTML = '<i class="bi bi-x-circle me-1"></i> Gagal menghubungi layanan JDE Lookup.';
            } finally {
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-search"></i> Cari Customer JDE';
            }
        }

        btn.addEventListener('click', doLookup);
        jdeInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                doLookup();
            }
        });
    }

    function setFieldValue(form, fieldName, value) {
        if (!value) return;
        const el = form.querySelector(`[name="${fieldName}"]`);
        if (el) {
            el.value = value;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            if (window.jQuery) {
                try {
                    window.jQuery(el).trigger('input').trigger('change');
                } catch (e) {}
            }
        }
    }

    /* --------------------------------------------------------------------------
     * 2. Durasi Calculation
     * -------------------------------------------------------------------------- */
    function setupDurasiCalculation(form) {
        const startInput = form.querySelector('[name="tanggal_mulai"]');
        const endInput = form.querySelector('[name="tanggal_berakhir"]');
        const durasiInput = form.querySelector('[name="durasi"]');

        if (!startInput || !endInput || !durasiInput) return;

        function calc() {
            const startVal = startInput.value;
            const endVal = endInput.value;
            if (!startVal || !endVal) return;

            const start = new Date(startVal);
            const end = new Date(endVal);
            if (isNaN(start) || isNaN(end) || end < start) {
                durasiInput.value = '0 Bulan';
                return;
            }

            let months = (end.getFullYear() - start.getFullYear()) * 12 + (end.getMonth() - start.getMonth());
            // Add 1 month if ends at end of month or days cover whole month
            if (end.getDate() >= start.getDate()) {
                months += 1;
            }

            const years = Math.floor(months / 12);
            const remMonths = months % 12;

            let result = '';
            if (years > 0 && remMonths > 0) {
                result = `${years} Tahun ${remMonths} Bulan`;
            } else if (years > 0) {
                result = `${years} Tahun`;
            } else {
                result = `${months} Bulan`;
            }

            durasiInput.value = result;
            durasiInput.dispatchEvent(new Event('change', { bubbles: true }));
        }

        startInput.addEventListener('change', calc);
        endInput.addEventListener('change', calc);
        calc();
    }

    /* --------------------------------------------------------------------------
     * 3. Auto SPK Number Preview & Readonly Lock
     * -------------------------------------------------------------------------- */
    function setupSPKAutoNumber(form) {
        const spkInput = form.querySelector('[name="nomor_spk"]');
        const brandSelect = form.querySelector('[name="brand"]');
        const cabangSelect = form.querySelector('[name="cabang"]');

        if (!spkInput) return;

        lockReadonlyFields(form);

        function updateSPK() {
            const brandVal = (brandSelect && brandSelect.value ? brandSelect.value : '').trim();
            const cabangVal = (cabangSelect && cabangSelect.value ? cabangSelect.value : '').trim();

            // If Brand or Cabang has not been selected, keep Nomor SPK blank
            if (!brandVal || !cabangVal) {
                spkInput.value = '';
                spkInput.placeholder = '—';
                return;
            }

            const now = new Date();
            const month = now.getMonth() + 1;
            const year = now.getFullYear();

            let brandCode = 'LADY';
            const bUpper = brandVal.toUpperCase();
            if (bUpper.includes('LADY')) brandCode = 'LADY';
            else if (bUpper.includes('SERENITY')) brandCode = 'SERENITY';
            else if (bUpper.includes('ROYAL')) brandCode = 'ROYAL';
            else if (bUpper.includes('GRAND')) brandCode = 'GRAND';
            else brandCode = brandVal.split(' ')[0].toUpperCase().replace(/[^A-Z0-9]/g, '') || 'LADY';

            let cabangCode = cabangVal ? (cabangVal.charAt(0).toUpperCase() + cabangVal.slice(1).toLowerCase()) : 'Tangerang';

            // Extract existing 4-digit sequence if present, otherwise default to 0001
            let seq = '0001';
            const match = (spkInput.value || '').match(/No\.\s*(\d{4})/i) || (spkInput.value || '').match(/-(\d{4})$/);
            if (match) {
                seq = match[1];
            }

            spkInput.value = `No. ${seq}/${brandCode}/${cabangCode}/${month}/${year}`;
            spkInput.dispatchEvent(new Event('input', { bubbles: true }));
            spkInput.dispatchEvent(new Event('change', { bubbles: true }));
        }

        if (brandSelect) {
            brandSelect.addEventListener('change', updateSPK);
            brandSelect.addEventListener('input', updateSPK);
        }
        if (cabangSelect) {
            cabangSelect.addEventListener('change', updateSPK);
            cabangSelect.addEventListener('input', updateSPK);
        }

        // Run immediately to generate official SPK number
        updateSPK();
    }

    /* --------------------------------------------------------------------------
     * 4. Dynamic Grids (Asset, Market Share, Target, Discount, Tier Support)
     * -------------------------------------------------------------------------- */

    // --- Grid 1: Asset Toko ---
    function setupAssetTokoGrid(form) {
        const field = form.querySelector('[name="asset_toko"]');
        if (!field) return;

        field.style.display = 'none';
        const container = createGridContainer(field, 'Data Asset Toko', 'Daftar kepemilikan aset display & papan nama toko.');

        function getRows() {
            try {
                return JSON.parse(field.value || '[]');
            } catch (e) {
                return [];
            }
        }

        function saveRows(rows) {
            field.value = JSON.stringify(rows);
            field.dispatchEvent(new Event('change', { bubbles: true }));
        }

        window.renderAssetGrid = function render() {
            let rows = getRows();
            if (!rows.length) {
                rows = [{ no: 1, keterangan: '', alamat: '', status: 'Pribadi' }];
                saveRows(rows);
            }

            let html = `
                <div class="table-responsive">
                    <table class="table table-bordered kontrak-grid-table">
                        <thead>
                            <tr>
                                <th style="width: 60px;">No</th>
                                <th>Keterangan Aset / Toko</th>
                                <th>Alamat</th>
                                <th style="width: 140px;">Status</th>
                                <th style="width: 60px;" class="text-center">Aksi</th>
                            </tr>
                        </thead>
                        <tbody>
            `;

            rows.forEach((r, idx) => {
                html += `
                    <tr data-index="${idx}">
                        <td class="text-center fw-bold">${idx + 1}</td>
                        <td><input type="text" class="cell-input" data-key="keterangan" value="${escapeHtml(r.keterangan || '')}" placeholder="Nama aset / papan nama"></td>
                        <td><input type="text" class="cell-input" data-key="alamat" value="${escapeHtml(r.alamat || '')}" placeholder="Alamat lokasi aset"></td>
                        <td>
                            <select class="cell-input" data-key="status">
                                <option value="Pribadi" ${r.status === 'Pribadi' ? 'selected' : ''}>Pribadi</option>
                                <option value="Sewa" ${r.status === 'Sewa' ? 'selected' : ''}>Sewa</option>
                            </select>
                        </td>
                        <td class="text-center">
                            <button type="button" class="btn-delete-row" title="Hapus"><i class="bi bi-trash"></i></button>
                        </td>
                    </tr>
                `;
            });

            html += `
                        </tbody>
                    </table>
                </div>
                <div class="mt-2">
                    <button type="button" class="btn-add-row"><i class="bi bi-plus-circle"></i> Tambah Asset</button>
                </div>
            `;

            container.innerHTML = html;

            // Wire listeners
            container.querySelectorAll('.cell-input').forEach(input => {
                input.addEventListener('input', () => {
                    const idx = parseInt(input.closest('tr').dataset.index);
                    const key = input.dataset.key;
                    rows[idx][key] = input.value;
                    saveRows(rows);
                });
            });

            container.querySelectorAll('.btn-delete-row').forEach(btn => {
                btn.addEventListener('click', () => {
                    const idx = parseInt(btn.closest('tr').dataset.index);
                    rows.splice(idx, 1);
                    saveRows(rows);
                    render();
                });
            });

            container.querySelector('.btn-add-row').addEventListener('click', () => {
                rows.push({ no: rows.length + 1, keterangan: '', alamat: '', status: 'Pribadi' });
                saveRows(rows);
                render();
            });
        };

        window.renderAssetGrid();
    }

    // --- Grid 2: Market Share ---
    function setupMarketShareGrid(form) {
        const field = form.querySelector('[name="market_share"]');
        if (!field) return;

        field.style.display = 'none';
        const container = createGridContainer(field, 'Data Market Share', 'Estimasi omset bulanan toko vs kompetitor.');

        function getRows() {
            try {
                return JSON.parse(field.value || '[]');
            } catch (e) {
                return [];
            }
        }

        function saveRows(rows) {
            field.value = JSON.stringify(rows);
            field.dispatchEvent(new Event('change', { bubbles: true }));
        }

        function render() {
            let rows = getRows();
            if (!rows.length) {
                rows = [
                    { bulan: '', serenity: 0, kompetitor_1: 0, kompetitor_2: 0, kompetitor_3: 0, kompetitor_4: 0 }
                ];
                saveRows(rows);
            }

            let html = `
                <div class="table-responsive">
                    <table class="table table-bordered kontrak-grid-table">
                        <thead>
                            <tr>
                                <th style="width: 120px;">Bulan</th>
                                <th>Royal / SERENITY (Rp)</th>
                                <th>Kompetitor 1 (Rp)</th>
                                <th>Kompetitor 2 (Rp)</th>
                                <th>Kompetitor 3 (Rp)</th>
                                <th>Kompetitor 4 (Rp)</th>
                                <th style="width: 50px;" class="text-center">Aksi</th>
                            </tr>
                        </thead>
                        <tbody>
            `;

            rows.forEach((r, idx) => {
                html += `
                    <tr data-index="${idx}">
                        <td><input type="text" class="cell-input" data-key="bulan" value="${escapeHtml(r.bulan || '')}" placeholder="Bulan"></td>
                        <td><input type="text" class="cell-input cell-num" data-key="serenity" value="${formatRupiah(r.serenity)}"></td>
                        <td><input type="text" class="cell-input cell-num" data-key="kompetitor_1" value="${formatRupiah(r.kompetitor_1)}"></td>
                        <td><input type="text" class="cell-input cell-num" data-key="kompetitor_2" value="${formatRupiah(r.kompetitor_2)}"></td>
                        <td><input type="text" class="cell-input cell-num" data-key="kompetitor_3" value="${formatRupiah(r.kompetitor_3)}"></td>
                        <td><input type="text" class="cell-input cell-num" data-key="kompetitor_4" value="${formatRupiah(r.kompetitor_4)}"></td>
                        <td class="text-center">
                            <button type="button" class="btn-delete-row" title="Hapus"><i class="bi bi-trash"></i></button>
                        </td>
                    </tr>
                `;
            });

            html += `
                        </tbody>
                    </table>
                </div>
                <div class="mt-2">
                    <button type="button" class="btn-add-row"><i class="bi bi-plus-circle"></i> Tambah Bulan</button>
                </div>
            `;

            container.innerHTML = html;

            container.querySelectorAll('.cell-input').forEach(input => {
                input.addEventListener('change', () => {
                    const idx = parseInt(input.closest('tr').dataset.index);
                    const key = input.dataset.key;
                    if (key === 'bulan') {
                        rows[idx][key] = input.value;
                    } else {
                        rows[idx][key] = parseRupiah(input.value);
                        input.value = formatRupiah(rows[idx][key]);
                    }
                    saveRows(rows);
                });
            });

            container.querySelectorAll('.btn-delete-row').forEach(btn => {
                btn.addEventListener('click', () => {
                    const idx = parseInt(btn.closest('tr').dataset.index);
                    rows.splice(idx, 1);
                    saveRows(rows);
                    render();
                });
            });

            container.querySelector('.btn-add-row').addEventListener('click', () => {
                rows.push({ bulan: '', serenity: 0, kompetitor_1: 0, kompetitor_2: 0, kompetitor_3: 0, kompetitor_4: 0 });
                saveRows(rows);
                render();
            });
        }

        window.renderMarketGrid = render;
        render();
    }

    // --- Grid 3: Target & Incentive Scheme ---
    function setupTargetIncentiveGrid(form) {
        const field = form.querySelector('[name="target_incentive"]');
        if (!field) return;

        field.style.display = 'none';
        const container = createGridContainer(field, 'Target & Incentive Scheme (Pasal 3)', 'Skema tier target penjualan bulanan dan reward insentif.');

        function getRows() {
            try {
                return JSON.parse(field.value || '[]');
            } catch (e) {
                return [];
            }
        }

        function saveRows(rows) {
            field.value = JSON.stringify(rows);
            field.dispatchEvent(new Event('change', { bubbles: true }));
        }

        function render() {
            let rows = getRows();
            if (!rows.length) {
                rows = [
                    { target_bulanan: 0, exclude_ppn: true, incentive_pct: 0, keterangan: '' }
                ];
                saveRows(rows);
            }

            let html = `
                <div class="table-responsive">
                    <table class="table table-bordered kontrak-grid-table">
                        <thead>
                            <tr>
                                <th>Target Bulanan (Rp)</th>
                                <th style="width: 120px;" class="text-center">Exclude PPN</th>
                                <th style="width: 130px;">Incentive (%)</th>
                                <th>Keterangan</th>
                                <th style="width: 50px;" class="text-center">Aksi</th>
                            </tr>
                        </thead>
                        <tbody>
            `;

            rows.forEach((r, idx) => {
                html += `
                    <tr data-index="${idx}">
                        <td><input type="text" class="cell-input cell-num" data-key="target_bulanan" value="${formatRupiah(r.target_bulanan)}"></td>
                        <td class="text-center">
                            <input type="checkbox" class="form-check-input" data-key="exclude_ppn" ${r.exclude_ppn ? 'checked' : ''}>
                        </td>
                        <td><input type="number" step="0.1" class="cell-input cell-num" data-key="incentive_pct" value="${r.incentive_pct || 0}"></td>
                        <td><input type="text" class="cell-input" data-key="keterangan" value="${escapeHtml(r.keterangan || '')}" placeholder="Catatan reward"></td>
                        <td class="text-center">
                            <button type="button" class="btn-delete-row" title="Hapus"><i class="bi bi-trash"></i></button>
                        </td>
                    </tr>
                `;
            });

            html += `
                        </tbody>
                    </table>
                </div>
                <div class="mt-2">
                    <button type="button" class="btn-add-row"><i class="bi bi-plus-circle"></i> Tambah Tier</button>
                </div>
            `;

            container.innerHTML = html;

            container.querySelectorAll('input').forEach(input => {
                input.addEventListener('change', () => {
                    const idx = parseInt(input.closest('tr').dataset.index);
                    const key = input.dataset.key;
                    if (key === 'exclude_ppn') {
                        rows[idx][key] = input.checked;
                    } else if (key === 'target_bulanan') {
                        rows[idx][key] = parseRupiah(input.value);
                        input.value = formatRupiah(rows[idx][key]);
                    } else if (key === 'incentive_pct') {
                        rows[idx][key] = parseFloat(input.value) || 0;
                    } else {
                        rows[idx][key] = input.value;
                    }
                    saveRows(rows);
                });
            });

            container.querySelectorAll('.btn-delete-row').forEach(btn => {
                btn.addEventListener('click', () => {
                    const idx = parseInt(btn.closest('tr').dataset.index);
                    rows.splice(idx, 1);
                    saveRows(rows);
                    render();
                });
            });

            container.querySelector('.btn-add-row').addEventListener('click', () => {
                rows.push({ target_bulanan: 0, exclude_ppn: true, incentive_pct: 0, keterangan: '' });
                saveRows(rows);
                render();
            });
        }

        window.renderTargetGrid = render;
        render();
    }

    // --- Grid 4: Discount Scheme ---
    function setupDiscountSchemeGrid(form) {
        const field = form.querySelector('[name="discount_scheme"]');
        if (!field) return;

        field.style.display = 'none';
        const container = createGridContainer(field, 'Discount Scheme (Pasal 6)', 'Rincian komponen potongan harga dan diskon khusus.');

        function getRows() {
            try {
                return JSON.parse(field.value || '[]');
            } catch (e) {
                return [];
            }
        }

        function saveRows(rows) {
            field.value = JSON.stringify(rows);
            field.dispatchEvent(new Event('change', { bubbles: true }));
        }

        function render() {
            let rows = getRows();
            if (!rows.length) {
                rows = [
                    { komponen: '', nilai: '', tipe: 'Persentage', keterangan: '' }
                ];
                saveRows(rows);
            }

            let html = `
                <div class="table-responsive">
                    <table class="table table-bordered kontrak-grid-table">
                        <thead>
                            <tr>
                                <th>Komponen</th>
                                <th style="width: 140px;">Nilai</th>
                                <th style="width: 150px;">Tipe</th>
                                <th>Keterangan</th>
                                <th style="width: 50px;" class="text-center">Aksi</th>
                            </tr>
                        </thead>
                        <tbody>
            `;

            rows.forEach((r, idx) => {
                html += `
                    <tr data-index="${idx}">
                        <td><input type="text" class="cell-input" data-key="komponen" value="${escapeHtml(r.komponen || '')}" placeholder="Komponen diskon"></td>
                        <td><input type="text" class="cell-input" data-key="nilai" value="${escapeHtml(r.nilai || '')}" placeholder="Misal: 10%"></td>
                        <td>
                            <select class="cell-input" data-key="tipe">
                                <option value="Persentage" ${r.tipe === 'Persentage' ? 'selected' : ''}>Persentage</option>
                                <option value="Nominal" ${r.tipe === 'Nominal' ? 'selected' : ''}>Nominal</option>
                            </select>
                        </td>
                        <td><input type="text" class="cell-input" data-key="keterangan" value="${escapeHtml(r.keterangan || '')}" placeholder="Catatan syarat"></td>
                        <td class="text-center">
                            <button type="button" class="btn-delete-row" title="Hapus"><i class="bi bi-trash"></i></button>
                        </td>
                    </tr>
                `;
            });

            html += `
                        </tbody>
                    </table>
                </div>
                <div class="mt-2">
                    <button type="button" class="btn-add-row"><i class="bi bi-plus-circle"></i> Tambah Discount</button>
                </div>
            `;

            container.innerHTML = html;

            container.querySelectorAll('.cell-input').forEach(input => {
                input.addEventListener('input', () => {
                    const idx = parseInt(input.closest('tr').dataset.index);
                    const key = input.dataset.key;
                    rows[idx][key] = input.value;
                    saveRows(rows);
                });
            });

            container.querySelectorAll('.btn-delete-row').forEach(btn => {
                btn.addEventListener('click', () => {
                    const idx = parseInt(btn.closest('tr').dataset.index);
                    rows.splice(idx, 1);
                    saveRows(rows);
                    render();
                });
            });

            container.querySelector('.btn-add-row').addEventListener('click', () => {
                rows.push({ komponen: '', nilai: '0%', tipe: 'Persentage', keterangan: '' });
                saveRows(rows);
                render();
            });
        }

        window.renderDiscountGrid = render;
        render();
    }

    // --- Grid 5: Tier Support Tahunan / Biaya Sewa (Auto Calculate Netto) ---
    function setupTierSupportGrid(form) {
        const field = form.querySelector('[name="tier_support"]');
        if (!field) return;

        field.style.display = 'none';
        const container = createGridContainer(field, 'Tier Support Tahunan / Biaya Sewa (Pasal 7)', 'Target, support %, dan PPh % diinput. Netto dihitung otomatis oleh sistem.');

        function getRows() {
            try {
                return JSON.parse(field.value || '[]');
            } catch (e) {
                return [];
            }
        }

        function saveRows(rows) {
            field.value = JSON.stringify(rows);
            field.dispatchEvent(new Event('change', { bubbles: true }));
        }

        function calculateNetto(target, supportPct, pphPct) {
            return Math.round(target * (supportPct / 100) * (1 - pphPct / 100));
        }

        function render() {
            let rows = getRows();
            if (!rows.length) {
                rows = [
                    { target_tahunan: 0, support_pct: 0, pph_pct: 0, netto: 0, keterangan: '' }
                ];
                saveRows(rows);
            }

            let html = `
                <div class="table-responsive">
                    <table class="table table-bordered kontrak-grid-table">
                        <thead>
                            <tr>
                                <th>Target Tahunan (Rp)</th>
                                <th style="width: 110px;">Support (%)</th>
                                <th style="width: 100px;">PPh (%)</th>
                                <th style="width: 170px;">Netto (Rp - Otomatis)</th>
                                <th>Keterangan</th>
                                <th style="width: 50px;" class="text-center">Aksi</th>
                            </tr>
                        </thead>
                        <tbody>
            `;

            let totalNetto = 0;

            rows.forEach((r, idx) => {
                const target = Number(r.target_tahunan) || 0;
                const supp = Number(r.support_pct) || 0;
                const pph = Number(r.pph_pct) || 0;
                const netto = calculateNetto(target, supp, pph);
                r.netto = netto;
                totalNetto += netto;

                html += `
                    <tr data-index="${idx}">
                        <td><input type="text" class="cell-input cell-num" data-key="target_tahunan" value="${formatRupiah(r.target_tahunan)}"></td>
                        <td><input type="number" step="0.1" class="cell-input cell-num" data-key="support_pct" value="${r.support_pct || 0}"></td>
                        <td><input type="number" step="0.1" class="cell-input cell-num" data-key="pph_pct" value="${r.pph_pct || 0}"></td>
                        <td><input type="text" class="cell-input cell-num cell-readonly" data-key="netto" value="${formatRupiah(netto)}" readonly></td>
                        <td><input type="text" class="cell-input" data-key="keterangan" value="${escapeHtml(r.keterangan || '')}" placeholder="Keterangan"></td>
                        <td class="text-center">
                            <button type="button" class="btn-delete-row" title="Hapus"><i class="bi bi-trash"></i></button>
                        </td>
                    </tr>
                `;
            });

            html += `
                        </tbody>
                        <tfoot>
                            <tr class="grid-summary-footer">
                                <td colspan="3" class="text-end">Total Netto Tier:</td>
                                <td class="text-end fw-bold text-primary">${formatRupiah(totalNetto)}</td>
                                <td colspan="2"><span class="badge bg-info text-dark">Formula: Target × Support% × (1 - PPh%)</span></td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
                <div class="mt-2">
                    <button type="button" class="btn-add-row"><i class="bi bi-plus-circle"></i> Tambah Tier Support</button>
                </div>
            `;

            container.innerHTML = html;

            container.querySelectorAll('input').forEach(input => {
                input.addEventListener('change', () => {
                    const rowEl = input.closest('tr');
                    const idx = parseInt(rowEl.dataset.index);
                    const key = input.dataset.key;

                    if (key === 'target_tahunan') {
                        rows[idx][key] = parseRupiah(input.value);
                        input.value = formatRupiah(rows[idx][key]);
                    } else if (key === 'support_pct' || key === 'pph_pct') {
                        rows[idx][key] = parseFloat(input.value) || 0;
                    } else if (key === 'keterangan') {
                        rows[idx][key] = input.value;
                    }

                    // Recalculate Netto
                    const target = Number(rows[idx].target_tahunan) || 0;
                    const supp = Number(rows[idx].support_pct) || 0;
                    const pph = Number(rows[idx].pph_pct) || 0;
                    const netto = calculateNetto(target, supp, pph);
                    rows[idx].netto = netto;

                    const nettoInput = rowEl.querySelector('[data-key="netto"]');
                    if (nettoInput) nettoInput.value = formatRupiah(netto);

                    saveRows(rows);
                    render(); // Re-render to update summary footer
                });
            });

            container.querySelectorAll('.btn-delete-row').forEach(btn => {
                btn.addEventListener('click', () => {
                    const idx = parseInt(btn.closest('tr').dataset.index);
                    rows.splice(idx, 1);
                    saveRows(rows);
                    render();
                });
            });

            container.querySelector('.btn-add-row').addEventListener('click', () => {
                rows.push({ target_tahunan: 0, support_pct: 0, pph_pct: 2, netto: 0, keterangan: '' });
                saveRows(rows);
                render();
            });
        }

        window.renderTierGrid = render;
        render();
    }

    function createGridContainer(field, title, hint) {
        const wrapper = field.closest('.field-wrapper') || field.parentElement;
        const container = document.createElement('div');
        container.className = 'kontrak-grid-container';

        const header = document.createElement('div');
        header.className = 'kontrak-grid-header';
        header.innerHTML = `
            <div>
                <h5 class="kontrak-grid-title"><i class="bi bi-table text-primary"></i> ${title}</h5>
                <div class="kontrak-grid-hint">${hint}</div>
            </div>
        `;

        wrapper.appendChild(header);
        wrapper.appendChild(container);
        return container;
    }

    /* --------------------------------------------------------------------------
     * 5. Step 3 Preview & Tabs
     * -------------------------------------------------------------------------- */
    function setupStep3Preview(form) {
        const previewPlaceholder = form.querySelector('[name="preview_contract_tab"]');
        if (!previewPlaceholder) return;

        const parent = previewPlaceholder.closest('.field-wrapper') || previewPlaceholder.parentElement;
        if (parent.querySelector('.kontrak-tabs-nav')) return;

        // De-slop: Hide unnecessary introductory text boxes, labels, and callouts
        const oldDesc = parent.querySelectorAll('.display-text-content, .alert, .card-body, label');
        oldDesc.forEach(el => { el.style.display = 'none'; });

        const tabWrap = document.createElement('div');
        tabWrap.className = 'mt-1 mb-4';

        tabWrap.innerHTML = `
            <div class="kontrak-tabs-nav">
                <button type="button" class="kontrak-tab-btn active" data-target="tab-ringkasan">
                    <i class="bi bi-card-checklist"></i> Ringkasan Pengajuan
                </button>
                <button type="button" class="kontrak-tab-btn" data-target="tab-spk">
                    <i class="bi bi-file-earmark-text"></i> Preview Surat Perjanjian Kerjasama
                </button>
            </div>
            <div id="tab-ringkasan" class="kontrak-tab-content active">
                <div class="card bg-light border-0 mb-3">
                    <div class="card-body">
                        <h6 class="fw-bold mb-3"><i class="bi bi-info-circle text-primary me-2"></i>Ringkasan Data Kontrak</h6>
                        <div class="row g-3" id="summaryFieldsContainer">
                            <!-- Populated on tab click -->
                        </div>
                    </div>
                </div>
            </div>
            <div id="tab-spk" class="kontrak-tab-content">
                <div class="spk-paper-preview" id="spkDocumentPreview">
                    <!-- Populated on tab click -->
                </div>
            </div>
        `;

        parent.appendChild(tabWrap);

        const tabBtns = tabWrap.querySelectorAll('.kontrak-tab-btn');
        const tabContents = tabWrap.querySelectorAll('.kontrak-tab-content');

        tabBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                tabBtns.forEach(b => b.classList.remove('active'));
                tabContents.forEach(c => c.classList.remove('active'));

                btn.classList.add('active');
                const targetId = btn.dataset.target;
                const targetEl = tabWrap.querySelector(`#${targetId}`);
                if (targetEl) targetEl.classList.add('active');

                if (targetId === 'tab-ringkasan') {
                    renderSummaryTab(form);
                } else if (targetId === 'tab-spk') {
                    renderSPKTab(form);
                }
            });
        });

        // Initial render
        renderSummaryTab(form);
    }

    function renderSummaryTab(form) {
        const container = document.getElementById('summaryFieldsContainer');
        if (!container) return;

        const getV = (name) => {
            const el = form.querySelector(`[name="${name}"]`);
            return el ? el.value : '';
        };

        container.innerHTML = `
            <div class="col-md-6">
                <div class="small text-muted">Nomor SPK</div>
                <div class="fw-bold text-dark">${getV('nomor_spk') || '—'}</div>
            </div>
            <div class="col-md-6">
                <div class="small text-muted">Customer / Toko JDE</div>
                <div class="fw-bold text-dark">${getV('nama_toko') || '-'} (${getV('kode_customer_jde') || '-'})</div>
            </div>
            <div class="col-md-4">
                <div class="small text-muted">Brand & Cabang</div>
                <div class="fw-medium">${getV('brand') || '-'} / ${getV('cabang') || '-'}</div>
            </div>
            <div class="col-md-4">
                <div class="small text-muted">Pemilik / Pihak Kedua</div>
                <div class="fw-medium">${getV('nama_pemilik') || '-'}</div>
            </div>
            <div class="col-md-4">
                <div class="small text-muted">Kota & Kontak</div>
                <div class="fw-medium">${getV('kota') || '-'} (${getV('no_telepon') || '-'})</div>
            </div>
            <div class="col-md-4">
                <div class="small text-muted">Periode Kontrak</div>
                <div class="fw-medium">${getV('tanggal_mulai') || '-'} s/d ${getV('tanggal_berakhir') || '-'} (${getV('durasi') || '-'})</div>
            </div>
            <div class="col-md-4">
                <div class="small text-muted">Ketentuan Pembayaran & TOP</div>
                <div class="fw-medium">${getV('metode_pembayaran') || '-'} (TOP: ${getV('top') || '-'} Hari)</div>
            </div>
            <div class="col-md-4">
                <div class="small text-muted">Jenis Pajak</div>
                <div class="fw-medium">${getV('jenis_pajak') || '-'}</div>
            </div>
        `;
    }

    function renderSPKTab(form) {
        const container = document.getElementById('spkDocumentPreview');
        if (!container) return;

        const getV = (name) => {
            const el = form.querySelector(`[name="${name}"]`);
            return el ? el.value : '';
        };

        const nomorSPK = getV('nomor_spk') || '—';
        const toko = getV('nama_toko') || '[Nama Toko / Dealer]';
        const pemilik = getV('nama_pemilik') || '[Nama Pemilik]';
        const alamat = getV('alamat_toko') || '[Alamat Lengkap Toko]';
        const identitas = getV('nomor_identitas') || '[NIK / NPWP]';
        const brand = getV('brand') || '[Brand Produk]';
        const tglMulai = getV('tanggal_mulai') || '[Tanggal Mulai]';
        const tglAkhir = getV('tanggal_berakhir') || '[Tanggal Berakhir]';
        const durasi = getV('durasi') || '[Durasi Kontrak]';
        const top = getV('top') || '0';
        const bayar = getV('metode_pembayaran') || 'Transfer / Cek / Giro';
        const kota = getV('kota_penandatanganan') || getV('kota') || 'Tangerang';
        const tglTtd = getV('tanggal_penandatanganan') || 'Tanggal Submit';

        container.innerHTML = `
            <div style="text-align: center; margin-bottom: 24px;">
                <h3 style="font-size: 18px; margin-bottom: 4px; text-decoration: underline;">SURAT PERJANJIAN KERJASAMA</h3>
                <p style="font-size: 14px; margin: 0;">Nomor: <strong>${nomorSPK}</strong></p>
            </div>

            <p>Pada hari ini, tanggal <strong>${tglTtd}</strong>, bertempat di <strong>${kota}</strong>, dibuat dan ditandatangani perjanjian kerjasama oleh dan antara:</p>

            <table style="margin-bottom: 16px;">
                <tr>
                    <td style="width: 140px; font-weight: bold;">I. PIHAK PERTAMA</td>
                    <td style="width: 10px;">:</td>
                    <td><strong>PT BESTARI MULIA</strong></td>
                </tr>
                <tr>
                    <td>Alamat</td>
                    <td>:</td>
                    <td>Jl. Industri Raya Blok A No. 10, Tangerang, Banten</td>
                </tr>
                <tr>
                    <td>Diwakili Oleh</td>
                    <td>:</td>
                    <td>Direktur Komersial (bertindak atas nama PT Bestari Mulia)</td>
                </tr>
            </table>

            <table style="margin-bottom: 24px;">
                <tr>
                    <td style="width: 140px; font-weight: bold;">II. PIHAK KEDUA</td>
                    <td style="width: 10px;">:</td>
                    <td><strong>${pemilik}</strong> (Pemilik / Penanggung Jawab)</td>
                </tr>
                <tr>
                    <td>Nama Toko / Usaha</td>
                    <td>:</td>
                    <td><strong>${toko}</strong></td>
                </tr>
                <tr>
                    <td>Alamat Toko</td>
                    <td>:</td>
                    <td>${alamat}</td>
                </tr>
                <tr>
                    <td>NIK / NPWP</td>
                    <td>:</td>
                    <td>${identitas}</td>
                </tr>
            </table>

            <h5 style="font-size: 14px; border-bottom: 1px solid #000; padding-bottom: 4px; margin-top: 20px;">BAB I - RUANG LINGKUP & PERIODE KERJASAMA</h5>
            <p><strong>Pasal 1:</strong> PIHAK PERTAMA menunjuk PIHAK KEDUA sebagai dealer/mitra resmi produk dengan merek <strong>${brand}</strong>.</p>
            <p><strong>Pasal 2:</strong> Perjanjian kerjasama ini berlaku efektif terhitung sejak tanggal <strong>${tglMulai}</strong> sampai dengan <strong>${tglAkhir}</strong> (Durasi: <strong>${durasi}</strong>).</p>

            <h5 style="font-size: 14px; border-bottom: 1px solid #000; padding-bottom: 4px; margin-top: 20px;">BAB II - TARGET VOLUME PENJUALAN & DUKUNGAN PROMOSI</h5>
            <p><strong>Pasal 3:</strong> PIHAK KEDUA berkewajiban mencapai target volume penjualan sesuai dengan Skema Target & Incentive yang telah disepakati bersama.</p>
            <p><strong>Pasal 4:</strong> Segala bentuk dukungan promosi, biaya sewa, atau listing fee akan dicairkan berdasarkan verifikasi pencapaian target dan kelunasan kewajiban pembayaran.</p>

            <h5 style="font-size: 14px; border-bottom: 1px solid #000; padding-bottom: 4px; margin-top: 20px;">BAB III - SYARAT PEMBAYARAN</h5>
            <p><strong>Pasal 5:</strong> Pembayaran pesanan barang dilakukan dengan metode <strong>${bayar}</strong> dengan Term of Payment (TOP) selama <strong>${top} Hari</strong> terhitung sejak tanggal faktur/pengiriman.</p>

            <div style="margin-top: 40px;">
                <table style="width: 100%; text-align: center;">
                    <tr>
                        <td style="width: 50%;">
                            <strong>PIHAK PERTAMA</strong><br>
                            PT Bestari Mulia<br><br><br><br>
                            <u>Direktur Komersial</u>
                        </td>
                        <td style="width: 50%;">
                            <strong>PIHAK KEDUA</strong><br>
                            ${toko}<br><br><br><br>
                            <u>${pemilik}</u><br>
                            Pemilik / Penanggung Jawab
                        </td>
                    </tr>
                </table>
            </div>
        `;
    }

    /* --------------------------------------------------------------------------
     * 7. Wizard Footer Actions & Interactive Stepper Header Navigation
     * -------------------------------------------------------------------------- */
    function setupWizardFooter(form) {
        const btnPrev = form.querySelector('#btnWizardPrev');
        const btnNext = form.querySelector('#btnWizardNext');
        const btnNextText = form.querySelector('#btnWizardNextText');
        const btnBackToForms = form.querySelector('#btnBackToForms');
        const btnPreviewSPK = form.querySelector('#btnPreviewSPK');
        const btnSubmit = form.querySelector('#btnSubmitApplication');

        function getCurrentStepIndex() {
            let activeIdx = 0;
            const activePane = form.querySelector('.wizard-step-pane.active');
            if (activePane && activePane.dataset.step !== undefined) {
                activeIdx = parseInt(activePane.dataset.step, 10);
            } else if (window.formEnhancements && typeof window.formEnhancements.currentStep === 'number') {
                activeIdx = window.formEnhancements.currentStep;
            } else {
                const ind = document.querySelector('.step-indicators .step-indicator.active');
                if (ind && ind.dataset.step) activeIdx = parseInt(ind.dataset.step, 10);
            }
            return activeIdx;
        }

        function setElVisible(el, visible) {
            if (!el) return;
            if (visible) {
                el.classList.remove('d-none');
                el.style.removeProperty('display');
            } else {
                el.classList.add('d-none');
                el.style.setProperty('display', 'none', 'important');
            }
        }

        // Handle Confirmation Checkboxes in Step 3
        function updateSubmitButtonState() {
            if (!btnSubmit) return;
            const chkData = form.querySelector('[name="chk_konfirmasi_data"]');
            const chkPreview = form.querySelector('[name="chk_konfirmasi_preview"]');

            if (chkData && chkPreview) {
                const isReady = chkData.checked && chkPreview.checked;
                btnSubmit.disabled = !isReady;
                if (!isReady) {
                    btnSubmit.classList.add('disabled');
                    btnSubmit.style.opacity = '0.65';
                    btnSubmit.title = 'Silakan centang persetujuan kebenaran data & preview SPK terlebih dahulu.';
                } else {
                    btnSubmit.disabled = false;
                    btnSubmit.classList.remove('disabled');
                    btnSubmit.style.opacity = '1';
                    btnSubmit.title = '';
                }
            } else if (chkData) {
                btnSubmit.disabled = !chkData.checked;
                btnSubmit.style.opacity = chkData.checked ? '1' : '0.65';
            }
        }

        const chkData = form.querySelector('[name="chk_konfirmasi_data"]');
        const chkPreview = form.querySelector('[name="chk_konfirmasi_preview"]');
        if (chkData) chkData.addEventListener('change', updateSubmitButtonState);
        if (chkPreview) chkPreview.addEventListener('change', updateSubmitButtonState);

        // Core Step Switching Function
        function switchWizardStep(targetStep, validate) {
            if (targetStep < 0 || targetStep > 2) return false;

            const panes = form.querySelectorAll('.wizard-step-pane');
            const currentStep = getCurrentStepIndex();

            // Validation if moving forward
            if (validate && targetStep > currentStep) {
                const currentPane = panes[currentStep] || form.querySelector(`.wizard-step-pane[data-step="${currentStep}"]`) || form.querySelector('.wizard-step-pane.active');
                if (currentPane) {
                    const requiredInputs = currentPane.querySelectorAll('input[required], select[required], textarea[required]');
                    let hasError = false;
                    let firstInvalid = null;

                    requiredInputs.forEach(input => {
                        if (input.type === 'hidden' || input.disabled || input.style.display === 'none') return;
                        if (input.offsetParent === null && input.type !== 'checkbox' && input.type !== 'radio') return;

                        const val = (input.value || '').trim();
                        if (!val) {
                            input.classList.add('is-invalid');
                            hasError = true;
                            if (!firstInvalid) firstInvalid = input;
                        } else {
                            input.classList.remove('is-invalid');
                        }
                    });

                    if (hasError && firstInvalid) {
                        firstInvalid.focus();
                        firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        if (window.formEnhancements && typeof window.formEnhancements.showValidationAlert === 'function') {
                            window.formEnhancements.showValidationAlert('Please fill in all required fields before continuing.');
                        }
                        return false;
                    }
                }
            }

            // 1. Toggle Panes & Clean Target Pane Error States
            panes.forEach((pane, idx) => {
                if (idx === targetStep) {
                    pane.classList.add('active');
                    pane.style.removeProperty('display');
                    pane.style.display = 'block';

                    // Ensure all field elements inside active pane are visible
                    pane.querySelectorAll('.field-wrapper, .fields-aligned-row, .mb-3').forEach(el => {
                        if (el.tagName !== 'INPUT') {
                            el.style.removeProperty('display');
                        }
                    });

                    // Reset errors on the newly activated pane so it opens clean and neutral
                    pane.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
                    pane.querySelectorAll('.invalid-feedback').forEach(el => {
                        el.style.display = 'none';
                        el.textContent = '';
                    });
                } else {
                    pane.classList.remove('active');
                    pane.style.setProperty('display', 'none', 'important');
                }
            });

            // 2. Remove any global validation alert banners
            const existingAlert = form.querySelector('.validation-alert');
            if (existingAlert) existingAlert.remove();
            const errSummary = document.getElementById('form-error-summary');
            if (errSummary) errSummary.style.display = 'none';

            // 3. Synchronize FormEnhancements instance
            if (window.formEnhancements) {
                window.formEnhancements.currentStep = targetStep;
            }

            // 4. Update Stepper Indicators Header
            document.querySelectorAll('.step-indicators .step-indicator').forEach((indicator, i) => {
                indicator.classList.remove('active', 'completed');
                if (i < targetStep) {
                    indicator.classList.add('completed');
                } else if (i === targetStep) {
                    indicator.classList.add('active');
                }
            });

            // 5. Update Progress Bar
            const progressBar = document.getElementById('formProgressBar');
            if (progressBar) {
                const pct = ((targetStep + 1) / 3) * 100;
                progressBar.style.width = `${pct}%`;
                progressBar.textContent = `Step ${targetStep + 1} of 3`;
            }

            // 6. Update Footer Action Buttons
            const isFirst = (targetStep === 0);
            const isLast = (targetStep === 2);

            setElVisible(btnBackToForms, isFirst);
            setElVisible(btnPrev, !isFirst);
            setElVisible(btnNext, !isLast);
            if (btnNextText) {
                btnNextText.textContent = (targetStep === 0) ? 'Lanjut Detail Kontrak' : 'Lanjut Preview';
            }
            setElVisible(btnPreviewSPK, isLast);
            setElVisible(btnSubmit, isLast);

            // If entering Step 3: Refresh summary & SPK document preview and checkbox state
            if (isLast) {
                renderSummaryTab(form);
                renderSPKTab(form);
                updateSubmitButtonState();
            }

            // 7. Smooth Scroll to top of form
            const formCard = form.closest('.card') || form;
            if (formCard) {
                const rect = formCard.getBoundingClientRect();
                const topY = window.pageYOffset + rect.top - 80;
                window.scrollTo({ top: Math.max(0, topY), behavior: 'smooth' });
            }

            return true;
        }

        // Wire Stepper Header Items
        function wireStepperHeader() {
            const indicators = document.querySelectorAll('.step-indicators .step-indicator');
            indicators.forEach((indicator, i) => {
                indicator.dataset.step = String(i);
                indicator.style.cursor = 'pointer';
                indicator.title = `Beralih ke Step ${i + 1}`;

                if (!indicator.dataset.tabBound) {
                    indicator.dataset.tabBound = 'true';
                    indicator.addEventListener('click', function(e) {
                        e.preventDefault();
                        e.stopImmediatePropagation();
                        const target = parseInt(this.dataset.step, 10);
                        const current = getCurrentStepIndex();
                        if (target === current) return;
                        switchWizardStep(target, target > current);
                    });
                }
            });
        }

        // Hook Next & Prev buttons
        if (btnNext && !btnNext.dataset.wizardBound) {
            btnNext.dataset.wizardBound = 'true';
            btnNext.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopImmediatePropagation();
                const current = getCurrentStepIndex();
                if (current < 2) {
                    switchWizardStep(current + 1, true);
                }
            });
        }

        if (btnPrev && !btnPrev.dataset.wizardBound) {
            btnPrev.dataset.wizardBound = 'true';
            btnPrev.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopImmediatePropagation();
                const current = getCurrentStepIndex();
                if (current > 0) {
                    switchWizardStep(current - 1, false);
                }
            });
        }

        // Hook Preview SPK button to jump to SPK tab
        if (btnPreviewSPK && !btnPreviewSPK.dataset.wizardBound) {
            btnPreviewSPK.dataset.wizardBound = 'true';
            btnPreviewSPK.addEventListener('click', function(e) {
                e.preventDefault();
                const spkTabBtn = form.querySelector('.kontrak-tab-btn[data-target="tab-spk"]');
                if (spkTabBtn) {
                    spkTabBtn.click();
                    const spkPreview = document.getElementById('spkDocumentPreview');
                    if (spkPreview) {
                        spkPreview.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }
                }
            });
        }

        // Listen for custom stepChanged event from form-enhancements.js
        form.addEventListener('stepChanged', function(e) {
            const stepIdx = (e.detail && typeof e.detail.stepIndex === 'number') ? e.detail.stepIndex : getCurrentStepIndex();
            switchWizardStep(stepIdx, false);
        });

        // Observer to detect step-indicator changes and bind click listeners
        wireStepperHeader();
        const stepContainer = document.querySelector('.step-indicators');
        if (stepContainer) {
            const obs = new MutationObserver(wireStepperHeader);
            obs.observe(stepContainer, { childList: true, subtree: true });
        } else {
            const bodyObs = new MutationObserver((mutations, observer) => {
                const sc = document.querySelector('.step-indicators');
                if (sc) {
                    wireStepperHeader();
                    const obs = new MutationObserver(wireStepperHeader);
                    obs.observe(sc, { childList: true, subtree: true });
                    observer.disconnect();
                }
            });
            bodyObs.observe(document.body, { childList: true, subtree: true });
        }

        // Initial UI synchronization (ensure Step 1 is isolated on load)
        switchWizardStep(0, false);
    }

    /* --------------------------------------------------------------------------
     * 8. Client-Side Form Persistence & Auto-Save
     * -------------------------------------------------------------------------- */
    function hasMeaningfulData(data) {
        if (!data || typeof data !== 'object') return false;
        return Object.entries(data).some(([k, v]) => {
            if (k === 'nomor_spk' || k === 'csrfmiddlewaretoken' || k === 'action') return false;
            if (typeof v === 'boolean') return v;
            if (typeof v === 'string') {
                const trimmed = v.trim();
                if (!trimmed) return false;
                if (trimmed === '[]' || trimmed === '[{"no":1,"keterangan":"","alamat":"","status":"Pribadi"}]') return false;
                return true;
            }
            return Boolean(v);
        });
    }

    function collectFormData(form) {
        const data = {};
        const elements = form.querySelectorAll('input, select, textarea');
        elements.forEach(el => {
            const name = el.name;
            if (!name || name === 'csrfmiddlewaretoken' || name === 'action') return;
            if (el.type === 'checkbox') {
                data[name] = el.checked;
            } else if (el.type === 'radio') {
                if (el.checked) data[name] = el.value;
            } else {
                data[name] = el.value;
            }
        });
        return data;
    }

    function updateAutoSaveStatus(state) {
        const slot = document.getElementById('autoSaveSlot');
        if (!slot) return;
        let indicator = document.getElementById('autoSaveIndicator');
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.id = 'autoSaveIndicator';
            indicator.className = 'auto-save-indicator';
            slot.appendChild(indicator);
        }
        if (state === 'saving') {
            indicator.className = 'auto-save-indicator saving';
            indicator.innerHTML = '<i class="bi bi-arrow-repeat spin me-1"></i> Menyimpan draf...';
        } else if (state === 'saved') {
            indicator.className = 'auto-save-indicator saved';
            indicator.innerHTML = '<i class="bi bi-cloud-check text-success me-1"></i> Draf tersimpan di browser';
        } else if (state === 'error') {
            indicator.className = 'auto-save-indicator error';
            indicator.innerHTML = '<i class="bi bi-exclamation-circle text-danger me-1"></i> Gagal menyimpan draf';
        } else {
            indicator.className = 'auto-save-indicator';
            indicator.innerHTML = '<i class="bi bi-cloud text-muted me-1"></i> Draf otomatis aktif';
        }
    }

    function showDraftRestoredAlert(form) {
        if (document.getElementById('draftRestoredAlert')) return;
        const alertBox = document.createElement('div');
        alertBox.id = 'draftRestoredAlert';
        alertBox.className = 'alert alert-light border border-info-subtle d-flex justify-content-between align-items-center py-2 px-3 mb-3';
        alertBox.innerHTML = `
            <div class="d-flex align-items-center gap-2 text-info-emphasis small">
                <i class="bi bi-info-circle-fill text-info"></i>
                <span><strong>Draf Dipulihkan</strong>: Isian formulir berhasil dipulihkan dari sesi sebelumnya.</span>
            </div>
            <button type="button" class="btn btn-outline-danger btn-sm py-0 px-2" id="btnAlertDiscardDraft" style="font-size: 0.8rem;">
                <i class="bi bi-trash3 me-1"></i> Buang Draf
            </button>
        `;
        const wrapper = form.querySelector('.form-fields-wrapper') || form;
        form.insertBefore(alertBox, wrapper);

        const btnAlertDiscard = alertBox.querySelector('#btnAlertDiscardDraft');
        if (btnAlertDiscard) {
            btnAlertDiscard.addEventListener('click', function() {
                discardDraft(form);
            });
        }
    }

    function showDiscardDraftButton(form, show) {
        let btnDiscard = form.querySelector('#btnLocalDiscardDraft');
        const footerActions = form.querySelector('.footer-right-actions') || form.querySelector('.form-wizard-footer');
        if (!footerActions) return;

        if (!btnDiscard) {
            btnDiscard = document.createElement('button');
            btnDiscard.type = 'button';
            btnDiscard.id = 'btnLocalDiscardDraft';
            btnDiscard.className = 'btn btn-outline-danger btn-sm btn-discard-draft' + (show ? '' : ' d-none');
            btnDiscard.innerHTML = '<i class="bi bi-trash3 me-1"></i> Discard Draft';
            btnDiscard.addEventListener('click', function(e) {
                e.preventDefault();
                discardDraft(form);
            });
            const btnSaveDraft = footerActions.querySelector('#btnSaveDraft') || footerActions.querySelector('#btnWizardNext');
            if (btnSaveDraft) {
                footerActions.insertBefore(btnDiscard, btnSaveDraft);
            } else {
                footerActions.prepend(btnDiscard);
            }
        } else {
            if (show) {
                btnDiscard.classList.remove('d-none');
            } else {
                btnDiscard.classList.add('d-none');
            }
        }
    }

    function discardDraft(form) {
        if (confirm('Apakah Anda yakin ingin membuang draft dan mengosongkan seluruh formulir?')) {
            try {
                localStorage.removeItem(STORAGE_KEY);
            } catch (e) {}
            window.location.href = window.location.pathname;
        }
    }

    function setupFormPersistence(form, hasRestoredDraft) {
        let autoSaveTimeout = null;

        function scheduleSave() {
            clearTimeout(autoSaveTimeout);
            updateAutoSaveStatus('saving');
            autoSaveTimeout = setTimeout(() => {
                try {
                    const data = collectFormData(form);
                    if (hasMeaningfulData(data)) {
                        localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
                        updateAutoSaveStatus('saved');
                        showDiscardDraftButton(form, true);
                    } else {
                        localStorage.removeItem(STORAGE_KEY);
                        updateAutoSaveStatus('idle');
                        showDiscardDraftButton(form, false);
                    }
                } catch (e) {
                    console.warn('[KontrakDraft] Error saving draft:', e);
                    updateAutoSaveStatus('error');
                }
            }, 400);
        }

        form.addEventListener('input', scheduleSave);
        form.addEventListener('change', scheduleSave);

        // Clear on successful form submission
        form.addEventListener('submit', function (e) {
            if (!e.defaultPrevented) {
                try {
                    localStorage.removeItem(STORAGE_KEY);
                } catch (err) {}
            }
        });

        // Initialize discard button in footer
        showDiscardDraftButton(form, Boolean(hasRestoredDraft));
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }
})();
