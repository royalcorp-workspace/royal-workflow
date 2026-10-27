/**
 * Kontrak Grid Widget & Dynamic Interactive Enhancements
 * Royal Workflow - Permohonan Kontrak Module
 */

(function () {
    'use strict';

    const STORAGE_KEY = 'royal_kontrak_form_draft';

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

        let hasRestoredDraft = false;

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

        // Ensure support toggle starts OFF (unchecked) for fresh new submissions
        const suppToggleInit = form.querySelector('input[name="is_support_provided"]');
        if (suppToggleInit) {
            suppToggleInit.checked = false;
        }

        function applyDraftData(draftData) {
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
                        let finalVal = val;
                        if (name === 'metode_pembayaran') {
                            const u = String(val).trim().toUpperCase();
                            if (u.includes('TRANSFER')) finalVal = 'Transfer';
                            else if (u.includes('GIRO')) finalVal = 'Giro';
                            else if (u.includes('CEK')) finalVal = 'Cek';
                        }
                        el.value = finalVal;
                    }
                }
            });
            hasRestoredDraft = true;
            // Refresh summary and preview tabs if currently rendered
            renderSummaryTab(form);
            renderSPKTab(form);
        }

        // 0. Lock Readonly Fields & Force Slate-200 Tone
        lockReadonlyFields(form);

        // 1. Setup Wizard Step Panes (Client-side view isolation)
        setupWizardPanes(form);

        // 2. Setup JDE Lookup
        setupJDELookup(form);

        // 2b. Setup Jenis Identitas & Nomor Identitas Validation
        setupIdentitasValidation(form);

        // 2c. Setup Metode Pembayaran (Transfer, Cek, Giro)
        setupMetodePembayaran(form);

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

        // 5b. Setup Support Facility Conditional Logic (Toggle Show/Hide)
        setupSupportConditionalLogic(form);

        // 6. Setup Step 3 Preview & Tabs
        setupStep3Preview(form);

        // 7. Setup Wizard Footer Actions & Stepper Navigation
        setupWizardFooter(form);

        function refreshAllGridsAndHeaders() {
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
            const jpSelect = form.querySelector('[name="jenis_pajak"]');
            if (jpSelect && jpSelect.value) {
                jpSelect.dispatchEvent(new Event('change', { bubbles: true }));
            }

            if (typeof form._validateNomorIdentitas === 'function') {
                form._validateNomorIdentitas(false);
            }

            updateAutoSaveStatus('saved_server');
        }

        // 8. Auto-restore or Prompt for Existing Draft
        const urlParams = new URLSearchParams(window.location.search);
        const isExplicitDraftUrl = urlParams.has('draft') || urlParams.has('draft_id');
        const isPageReload = (window.performance && window.performance.getEntriesByType && window.performance.getEntriesByType('navigation')[0]?.type === 'reload');

        // Check for server draft data embedded in template
        let serverDraftData = null;
        const serverDraftMeta = document.getElementById('activeServerDraftMeta');
        const scriptEl = document.getElementById('active_server_draft_data');
        if (scriptEl && scriptEl.textContent) {
            try {
                serverDraftData = JSON.parse(scriptEl.textContent);
            } catch (e) {}
        }

        // Check for local draft data in localStorage
        let localDraftData = null;
        try {
            const rawDraft = localStorage.getItem(STORAGE_KEY);
            if (rawDraft) {
                localDraftData = JSON.parse(rawDraft);
            }
        } catch (e) {}

        const candidateDraftData = (localDraftData && hasMeaningfulData(localDraftData)) ? localDraftData : (serverDraftData && hasMeaningfulData(serverDraftData) ? serverDraftData : null);

        if (candidateDraftData) {
            if (isExplicitDraftUrl || isPageReload) {
                // User explicitly clicked "Lanjutkan Draft" from hub or refreshed the page (F5)
                applyDraftData(candidateDraftData);
                if (serverDraftMeta && serverDraftMeta.dataset.draftId) {
                    form.dataset.currentDraftId = serverDraftMeta.dataset.draftId;
                }
                refreshAllGridsAndHeaders();
            } else {
                // User clicked "+ Buat Pengajuan Baru": Show interactive modal prompt!
                showDraftPromptModal(form, candidateDraftData, serverDraftMeta, () => {
                    applyDraftData(candidateDraftData);
                    if (serverDraftMeta && serverDraftMeta.dataset.draftId) {
                        form.dataset.currentDraftId = serverDraftMeta.dataset.draftId;
                    }
                    refreshAllGridsAndHeaders();
                });
                updateAutoSaveStatus('idle');
            }
        } else {
            updateAutoSaveStatus('idle');
        }

        // 9. Setup Client-side Draft Persistence & Auto-save
        setupFormPersistence(form);
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
            'jenis_pajak', 'top', 'is_support_provided', 'support_promosi',
            'target_incentive', 'pct_support_promo', 'frekuensi_pencairan', 'syarat_pencairan',
            'komponen_biaya', 'pengecualian_ketentuan_support', 'discount_scheme',
            'tier_support', 'metode_pembayaran', 'discount_do', 'ketentuan_do',
            'kota_penandatanganan', 'tanggal_penandatanganan', 'rekening_perusahaan', 'catatan_lain'
        ]);

        const STEP3_FIELDS = new Set([
            'preview_contract_tab',
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
        return Math.round(Number(num)).toLocaleString('id-ID');
    }

    function parseRupiah(val) {
        if (!val) return 0;
        // In Indonesian locale, '.' is thousands separator. Remove dots, normalize comma to dot.
        const s = String(val).trim().replace(/\./g, '').replace(/,/g, '.').replace(/[^0-9.-]/g, '');
        return Math.round(parseFloat(s)) || 0;
    }

    /**
     * Attach currency input behavior to an input element
     * - Real-time keystroke blocking (digits 0-9 only, blocks letters & symbols)
     * - Live thousands separator formatting (e.g. 1.000.000)
     * - Auto-select content on focus when current value is '0'
     * - Restores '0' on blur if field is left completely empty
     */
    function attachCurrencyInputBehavior(input, onValueChange) {
        if (!input || input.readOnly || input.dataset.currencyAttached) return;
        input.dataset.currencyAttached = 'true';
        input.setAttribute('inputmode', 'numeric');
        input.setAttribute('autocomplete', 'off');

        // 1. Auto-select text on focus if current value is '0'
        input.addEventListener('focus', function () {
            if (this.value.trim() === '0') {
                this.select();
            }
        });

        // 2. Keydown: directly block non-numeric characters before they appear
        input.addEventListener('keydown', function (e) {
            // Control keys: backspace, delete, tab, escape, enter, arrows, home, end
            const allowedKeys = ['Backspace', 'Delete', 'Tab', 'Escape', 'Enter', 'ArrowLeft', 'ArrowRight', 'Home', 'End'];
            if (allowedKeys.includes(e.key)) return;

            // Allow Ctrl / Meta combinations (Ctrl+A, Ctrl+C, Ctrl+V, Ctrl+X, Ctrl+Z, Ctrl+Y)
            if (e.ctrlKey || e.metaKey) return;

            // Reject anything not digit 0-9
            if (!/^[0-9]$/.test(e.key)) {
                e.preventDefault();
            }
        });

        // 3. Live input: filter digits, live format with dot thousands separator, preserve cursor
        input.addEventListener('input', function () {
            const raw = this.value;
            const digits = raw.replace(/\D/g, '');
            const cursorPosition = this.selectionStart;
            const oldLength = raw.length;

            if (!digits) {
                this.value = '';
            } else {
                const num = parseInt(digits, 10);
                const formatted = Number(num).toLocaleString('id-ID');
                this.value = formatted;

                // Adjust cursor position gracefully
                const newLength = formatted.length;
                const diff = newLength - oldLength;
                const newCursor = Math.max(0, cursorPosition + diff);
                this.setSelectionRange(newCursor, newCursor);
            }

            if (typeof onValueChange === 'function') {
                onValueChange(parseRupiah(this.value));
            }
        });

        // 4. Blur: if empty, restore '0' and format properly
        input.addEventListener('blur', function () {
            if (this.value.trim() === '') {
                this.value = '0';
                if (typeof onValueChange === 'function') {
                    onValueChange(0);
                }
            } else {
                const val = parseRupiah(this.value);
                this.value = formatRupiah(val);
                if (typeof onValueChange === 'function') {
                    onValueChange(val);
                }
            }
        });

        // 5. Change event fallback
        input.addEventListener('change', function () {
            const val = parseRupiah(this.value);
            this.value = formatRupiah(val);
            if (typeof onValueChange === 'function') {
                onValueChange(val);
            }
        });
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
                        let cleanJenis = c.jenis_identitas;
                        if (cleanJenis.includes('/') || cleanJenis.includes('KTP')) {
                            cleanJenis = 'NIK';
                        }
                        setFieldValue(form, 'jenis_identitas', cleanJenis);
                    }
                    if (typeof form._validateNomorIdentitas === 'function') {
                        form._validateNomorIdentitas(false);
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

    function formatIndonesianMobile(val) {
        if (!val) return '';
        let s = String(val).trim();
        let digits = s.replace(/[^0-9]/g, '');
        if (digits.startsWith('62')) {
            digits = '0' + digits.slice(2);
        }
        if (digits.startsWith('08')) {
            if (digits.length <= 4) return digits;
            if (digits.length <= 8) return digits.slice(0, 4) + '-' + digits.slice(4);
            if (digits.length <= 12) return digits.slice(0, 4) + '-' + digits.slice(4, 8) + '-' + digits.slice(8);
            return digits.slice(0, 4) + '-' + digits.slice(4, 8) + '-' + digits.slice(8, 12) + (digits.length > 12 ? '-' + digits.slice(12) : '');
        }
        return s;
    }

    function setFieldValue(form, fieldName, value) {
        if (!value) return;
        if (fieldName === 'no_telepon') {
            value = formatIndonesianMobile(value);
        }
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
     * 1b. Setup Jenis Identitas & Nomor Identitas Validation
     * -------------------------------------------------------------------------- */
    function setupIdentitasValidation(form) {
        const jenisSelect = form.querySelector('[name="jenis_identitas"]');
        const nomorInput = form.querySelector('[name="nomor_identitas"]');
        if (!jenisSelect && !nomorInput) return;

        // 1. Bersihkan pilihan dropdown: hanya sediakan NIK dan NPWP (hapus NIK / NPWP)
        if (jenisSelect) {
            const options = Array.from(jenisSelect.options);
            let hasNIK = false;
            let hasNPWP = false;

            options.forEach(opt => {
                const val = (opt.value || '').trim();
                const text = (opt.text || '').trim();

                // Hapus opsi kombinasi "NIK / NPWP"
                if (val.includes('/') || text.includes('/')) {
                    opt.remove();
                } else if (val.toUpperCase().includes('NIK') || text.toUpperCase().includes('NIK')) {
                    opt.value = 'NIK';
                    opt.textContent = 'NIK';
                    hasNIK = true;
                } else if (val.toUpperCase().includes('NPWP') || text.toUpperCase().includes('NPWP')) {
                    opt.value = 'NPWP';
                    opt.textContent = 'NPWP';
                    hasNPWP = true;
                }
            });

            if (!hasNIK) {
                const optNIK = document.createElement('option');
                optNIK.value = 'NIK';
                optNIK.textContent = 'NIK';
                jenisSelect.appendChild(optNIK);
            }
            if (!hasNPWP) {
                const optNPWP = document.createElement('option');
                optNPWP.value = 'NPWP';
                optNPWP.textContent = 'NPWP';
                jenisSelect.appendChild(optNPWP);
            }
        }

        if (!nomorInput) return;

        // 2. Setup atribut input
        nomorInput.setAttribute('inputmode', 'numeric');
        nomorInput.setAttribute('autocomplete', 'off');
        nomorInput.setAttribute('maxlength', '16');

        // Wrapper label dinamis
        const wrapper = nomorInput.closest('.field-wrapper') || nomorInput.closest('.mb-3') || nomorInput.parentElement;
        const labelEl = wrapper ? wrapper.querySelector('label.form-label, label') : null;

        function updateLabel(jenis) {
            if (!labelEl) return;
            if (jenis === 'NIK') {
                labelEl.innerHTML = 'Nomor NIK <span class="text-danger">*</span>';
                nomorInput.placeholder = '16 digit NIK (KTP)';
            } else if (jenis === 'NPWP') {
                labelEl.innerHTML = 'Nomor NPWP <span class="text-danger">*</span>';
                nomorInput.placeholder = '15 atau 16 digit NPWP';
            } else {
                labelEl.innerHTML = 'Nomor Identitas (NIK / NPWP) <span class="text-danger">*</span>';
                nomorInput.placeholder = 'Nomor NIK atau NPWP';
            }
        }

        // Feedback container
        let feedbackEl = wrapper ? wrapper.querySelector('.nomor-identitas-feedback') : null;
        if (!feedbackEl) {
            feedbackEl = document.createElement('div');
            feedbackEl.className = 'nomor-identitas-feedback mt-1 small';
            if (nomorInput.nextSibling) {
                nomorInput.parentNode.insertBefore(feedbackEl, nomorInput.nextSibling);
            } else {
                nomorInput.parentNode.appendChild(feedbackEl);
            }
        }

        function validateNomorIdentitas(showErrorIfEmpty = false) {
            const rawVal = nomorInput.value || '';
            const digits = rawVal.replace(/\D/g, '');
            if (rawVal !== digits) {
                nomorInput.value = digits.slice(0, 16);
            }

            const val = nomorInput.value.trim();
            const jenis = (jenisSelect ? jenisSelect.value : '').trim().toUpperCase();
            updateLabel(jenis);

            nomorInput.classList.remove('is-valid', 'is-invalid');
            feedbackEl.className = 'nomor-identitas-feedback mt-1 small';
            feedbackEl.innerHTML = '';

            if (!val) {
                if (showErrorIfEmpty) {
                    nomorInput.classList.add('is-invalid');
                    feedbackEl.className = 'nomor-identitas-feedback mt-1 small text-danger';
                    feedbackEl.innerHTML = '<i class="bi bi-exclamation-circle me-1"></i> Nomor Identitas wajib diisi.';
                    return false;
                }
                return false;
            }

            if (jenis === 'NIK') {
                if (val.length === 16) {
                    nomorInput.classList.add('is-valid');
                    feedbackEl.className = 'nomor-identitas-feedback mt-1 small text-success';
                    feedbackEl.innerHTML = '<i class="bi bi-check-circle me-1"></i> Format NIK 16 digit valid.';
                    return true;
                } else {
                    nomorInput.classList.add('is-invalid');
                    feedbackEl.className = 'nomor-identitas-feedback mt-1 small text-danger';
                    feedbackEl.innerHTML = `<i class="bi bi-exclamation-triangle me-1"></i> Nomor NIK harus tepat 16 digit angka (saat ini: ${val.length} digit).`;
                    return false;
                }
            } else if (jenis === 'NPWP') {
                if (val.length === 15 || val.length === 16) {
                    nomorInput.classList.add('is-valid');
                    feedbackEl.className = 'nomor-identitas-feedback mt-1 small text-success';
                    feedbackEl.innerHTML = `<i class="bi bi-check-circle me-1"></i> Format NPWP ${val.length} digit valid.`;
                    return true;
                } else {
                    nomorInput.classList.add('is-invalid');
                    feedbackEl.className = 'nomor-identitas-feedback mt-1 small text-danger';
                    feedbackEl.innerHTML = `<i class="bi bi-exclamation-triangle me-1"></i> Nomor NPWP harus 15 atau 16 digit angka (saat ini: ${val.length} digit).`;
                    return false;
                }
            } else {
                nomorInput.classList.add('is-invalid');
                feedbackEl.className = 'nomor-identitas-feedback mt-1 small text-warning';
                feedbackEl.innerHTML = '<i class="bi bi-info-circle me-1"></i> Silakan pilih Jenis Identitas (NIK atau NPWP) terlebih dahulu.';
                return false;
            }
        }

        form._validateNomorIdentitas = validateNomorIdentitas;

        // Keydown filter
        nomorInput.addEventListener('keydown', function (e) {
            const allowedKeys = ['Backspace', 'Delete', 'Tab', 'Escape', 'Enter', 'ArrowLeft', 'ArrowRight', 'Home', 'End'];
            if (allowedKeys.includes(e.key)) return;
            if (e.ctrlKey || e.metaKey) return;

            if (!/^[0-9]$/.test(e.key)) {
                e.preventDefault();
                return;
            }

            const selStart = this.selectionStart;
            const selEnd = this.selectionEnd;
            if (selStart === selEnd && this.value.length >= 16) {
                e.preventDefault();
            }
        });

        nomorInput.addEventListener('input', function () {
            validateNomorIdentitas(false);
        });

        nomorInput.addEventListener('blur', function () {
            validateNomorIdentitas(true);
        });

        if (jenisSelect) {
            jenisSelect.addEventListener('change', function () {
                validateNomorIdentitas(nomorInput.value.length > 0);
            });
        }

        if (nomorInput.value) {
            validateNomorIdentitas(false);
        }
    }

    /* --------------------------------------------------------------------------
     * 1c. Setup Metode Pembayaran Dropdown & Migration
     * -------------------------------------------------------------------------- */
    function setupMetodePembayaran(form) {
        const select = form.querySelector('[name="metode_pembayaran"]');
        if (!select) return;

        const STANDAR_OPSI = ['Transfer', 'Cek', 'Giro'];

        function normalizeMetode(val) {
            if (!val) return '';
            const u = String(val).trim().toUpperCase();
            if (u.includes('TRANSFER')) return 'Transfer';
            if (u.includes('GIRO')) return 'Giro';
            if (u.includes('CEK')) return 'Cek';
            return val;
        }

        const currentVal = normalizeMetode(select.value);

        const existingOptions = Array.from(select.options);
        const placeholderOpt = existingOptions.find(o => !o.value || o.value === '');
        const placeholderText = placeholderOpt ? placeholderOpt.textContent : '-- Pilih Metode Pembayaran --';

        select.innerHTML = '';
        const emptyOpt = document.createElement('option');
        emptyOpt.value = '';
        emptyOpt.textContent = placeholderText;
        select.appendChild(emptyOpt);

        STANDAR_OPSI.forEach(item => {
            const opt = document.createElement('option');
            opt.value = item;
            opt.textContent = item;
            if (currentVal === item) {
                opt.selected = true;
            }
            select.appendChild(opt);
        });

        if (currentVal && STANDAR_OPSI.includes(currentVal)) {
            select.value = currentVal;
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
        const perusahaanSelect = form.querySelector('[name="perusahaan"]');

        if (!spkInput) return;

        lockReadonlyFields(form);

        function updateSPK() {
            const brandVal = (brandSelect && brandSelect.value ? brandSelect.value : '').trim();
            const cabangVal = (cabangSelect && cabangSelect.value ? cabangSelect.value : '').trim();
            const compVal = (perusahaanSelect && perusahaanSelect.value ? perusahaanSelect.value : '').trim();

            // If Brand or Cabang has not been selected, keep Nomor SPK blank
            if (!brandVal || !cabangVal) {
                spkInput.value = '';
                spkInput.placeholder = '—';
                return;
            }

            const now = new Date();
            const month = now.getMonth() + 1;
            const year = now.getFullYear();

            const bUpper = brandVal.toUpperCase();
            const cUpper = compVal.toUpperCase();
            
            // Clean Brand Code (LADY, ROYAL, SERENITY, ELITE, GRAND)
            let brandCode = 'LADY';
            if (bUpper.includes('LADY')) {
                brandCode = 'LADY';
            } else if (bUpper.includes('ROYAL') || bUpper.includes('FOAM')) {
                brandCode = 'ROYAL';
            } else if (bUpper.includes('SERENITY')) {
                brandCode = 'SERENITY';
            } else if (bUpper.includes('ELITE')) {
                brandCode = 'ELITE';
            } else if (bUpper.includes('GRAND')) {
                brandCode = 'GRAND';
            } else {
                brandCode = brandVal.split(' ')[0].toUpperCase().replace(/[^A-Z0-9]/g, '') || 'LADY';
            }

            // PT Code (RAS, ACA, BCP, BM, CAM)
            let ptCode = 'RAS';
            if (cUpper.includes('PRIMATARA') || cUpper.includes('BANGUN CIPTA') || cUpper === 'BCP') {
                ptCode = 'BCP';
            } else if (cUpper.includes('BESTARI') || cUpper === 'BM') {
                ptCode = 'BM';
            } else if (cUpper.includes('CEMERLANG ABADI MULIA') || cUpper.includes('ABADI MULIA') || cUpper === 'CAM') {
                ptCode = 'CAM';
            } else if (cUpper.includes('SEJAHTERA') || cUpper.includes('RAS') || cUpper.includes('ROYAL')) {
                ptCode = 'RAS';
            } else if (cUpper.includes('ACA') || cUpper.includes('ANUGRAH')) {
                ptCode = 'ACA';
            }

            const monthStr = month < 10 ? `0${month}` : String(month);

            // Extract existing sequence if present, otherwise default to 001
            let seq = '001';
            const match = (spkInput.value || '').match(/No\.\s*(\d+)/i) || (spkInput.value || '').match(/-(\d+)$/);
            if (match) {
                const n = parseInt(match[1], 10);
                seq = String(n).padStart(3, '0');
            }

            spkInput.value = `No. ${seq}/${brandCode}/${ptCode}/${monthStr}/${year}`;
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
        if (perusahaanSelect) {
            perusahaanSelect.addEventListener('change', updateSPK);
            perusahaanSelect.addEventListener('input', updateSPK);
        }
        if (perusahaanSelect) {
            perusahaanSelect.addEventListener('change', updateSPK);
            perusahaanSelect.addEventListener('input', updateSPK);
        }

        const kotaTtdInput = form.querySelector('[name="kota_penandatanganan"]');
        function syncKotaPenandatanganan() {
            if (!cabangSelect || !kotaTtdInput) return;
            const currentCab = (cabangSelect.value || '').trim();
            if (currentCab && currentCab.toLowerCase() !== 'pusat') {
                if (!kotaTtdInput.value || kotaTtdInput.dataset.autoFilled === 'true') {
                    kotaTtdInput.value = currentCab;
                    kotaTtdInput.dataset.autoFilled = 'true';
                    kotaTtdInput.dispatchEvent(new Event('input', { bubbles: true }));
                    kotaTtdInput.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }
        }
        if (cabangSelect && kotaTtdInput) {
            cabangSelect.addEventListener('change', syncKotaPenandatanganan);
            kotaTtdInput.addEventListener('input', function () {
                kotaTtdInput.dataset.autoFilled = 'false';
            });
            if (!kotaTtdInput.value && cabangSelect.value) {
                syncKotaPenandatanganan();
            }
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
        const container = createGridContainer(field, 'Data Asset Toko', 'Daftar kepemilikan aset display & papan nama toko.', 'asset_toko');

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
                    <table class="table table-bordered kontrak-grid-table" data-grid="asset_toko">
                        <thead>
                            <tr>
                                <th style="width: 50px;" class="text-center">No</th>
                                <th>Keterangan Aset / Toko</th>
                                <th>Alamat</th>
                                <th style="width: 130px;">Status</th>
                                <th style="width: 50px;" class="text-center">Aksi</th>
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
        const container = createGridContainer(field, 'Data Market Share', 'Estimasi omset bulanan toko vs kompetitor.', 'market_share');

        const STANDAR_BULAN = [
            'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
            'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
        ];

        function getCurrentBrand() {
            const brandSelect = form.querySelector('[name="brand"]');
            return (brandSelect && brandSelect.value) ? brandSelect.value : '';
        }

        function getMarketShareBrandHeader(brandName) {
            if (!brandName || typeof brandName !== 'string') {
                return 'ROYAL / SERENITY (RP)';
            }
            const b = brandName.trim().toUpperCase();

            // Aturan Khusus: LADY AMERICANA -> LADY (RP)
            if (b.includes('LADY')) {
                return 'LADY (RP)';
            }
            if (b.includes('ROYAL') || b.includes('FOAM')) {
                return 'ROYAL FOAM (RP)';
            }
            if (b.includes('SERENITY')) {
                return 'SERENITY (RP)';
            }
            if (b.includes('GRAND')) {
                return 'GRAND EXCLUSIVE (RP)';
            }
            if (b.includes('ELITE')) {
                return 'ELITE (RP)';
            }

            return `${b} (RP)`;
        }

        function renderMonthSelectOptions(selectedValue) {
            const valClean = (selectedValue || '').trim().toLowerCase();
            let optionsHtml = '<option value="">-- Pilih Bulan --</option>';
            let isMatched = false;

            STANDAR_BULAN.forEach(b => {
                const isSelected = (valClean === b.toLowerCase());
                if (isSelected) isMatched = true;
                optionsHtml += `<option value="${b}" ${isSelected ? 'selected' : ''}>${b}</option>`;
            });

            // Pertahankan nilai lama jika ada input kustom di data draft sebelumnya
            if (selectedValue && !isMatched && selectedValue.trim() !== '') {
                optionsHtml += `<option value="${escapeHtml(selectedValue)}" selected>${escapeHtml(selectedValue)}</option>`;
            }

            return optionsHtml;
        }

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

            const brandHeader = getMarketShareBrandHeader(getCurrentBrand());

            let html = `
                <div class="table-responsive">
                    <table class="table table-bordered kontrak-grid-table" data-grid="market_share">
                        <thead>
                            <tr>
                                <th style="width: 140px;">Bulan</th>
                                <th id="thMarketShareBrand" style="min-width: 170px;">${brandHeader}</th>
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
                        <td>
                            <select class="cell-input form-select form-select-sm" data-key="bulan" style="min-width: 130px; font-size: 0.85rem;">
                                ${renderMonthSelectOptions(r.bulan)}
                            </select>
                        </td>
                        <td><input type="text" inputmode="numeric" class="cell-input cell-num" data-key="serenity" value="${formatRupiah(r.serenity)}"></td>
                        <td><input type="text" inputmode="numeric" class="cell-input cell-num" data-key="kompetitor_1" value="${formatRupiah(r.kompetitor_1)}"></td>
                        <td><input type="text" inputmode="numeric" class="cell-input cell-num" data-key="kompetitor_2" value="${formatRupiah(r.kompetitor_2)}"></td>
                        <td><input type="text" inputmode="numeric" class="cell-input cell-num" data-key="kompetitor_3" value="${formatRupiah(r.kompetitor_3)}"></td>
                        <td><input type="text" inputmode="numeric" class="cell-input cell-num" data-key="kompetitor_4" value="${formatRupiah(r.kompetitor_4)}"></td>
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
                const key = input.dataset.key;
                if (key === 'bulan') {
                    input.addEventListener('change', () => {
                        const idx = parseInt(input.closest('tr').dataset.index);
                        rows[idx].bulan = input.value;
                        saveRows(rows);
                    });
                } else {
                    attachCurrencyInputBehavior(input, (newVal) => {
                        const idx = parseInt(input.closest('tr').dataset.index);
                        rows[idx][key] = newVal;
                        saveRows(rows);
                    });
                }
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

        function updateBrandHeader() {
            const th = container.querySelector('#thMarketShareBrand');
            if (th) {
                th.textContent = getMarketShareBrandHeader(getCurrentBrand());
            }
        }

        const brandSelect = form.querySelector('[name="brand"]');
        if (brandSelect) {
            brandSelect.addEventListener('change', updateBrandHeader);
            brandSelect.addEventListener('input', updateBrandHeader);
        }

        window.renderMarketGrid = render;
        render();
    }

    // --- Grid 3: Target & Incentive Scheme ---
    function setupTargetIncentiveGrid(form) {
        const field = form.querySelector('[name="target_incentive"]');
        if (!field) return;

        field.style.display = 'none';
        const container = createGridContainer(field, 'Target & Incentive Scheme (Pasal 3)', 'Skema tier target penjualan bulanan dan reward insentif.', 'target_incentive');

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

        function isExcludePPNSelected() {
            const jpInput = form.querySelector('[name="jenis_pajak"]');
            const val = (jpInput ? jpInput.value : '').trim().toLowerCase();
            return val.includes('exclude');
        }

        function render() {
            let rows = getRows();
            const currentExclude = isExcludePPNSelected();

            if (!rows.length) {
                rows = [
                    { target_bulanan: 0, exclude_ppn: currentExclude, incentive_pct: 0, keterangan: '' }
                ];
                saveRows(rows);
            } else {
                rows.forEach(r => {
                    r.exclude_ppn = currentExclude;
                });
                saveRows(rows);
            }

            let html = `
                <div class="table-responsive">
                    <table class="table table-bordered kontrak-grid-table" data-grid="target_incentive">
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
                        <td><input type="text" inputmode="numeric" class="cell-input cell-num" data-key="target_bulanan" value="${formatRupiah(r.target_bulanan)}"></td>
                        <td class="text-center">
                            <input type="checkbox" class="form-check-input" data-key="exclude_ppn" ${currentExclude ? 'checked' : ''} disabled title="Mengikuti pilihan Jenis Pajak (${currentExclude ? 'Exclude PPN' : 'Include PPN'})">
                        </td>
                        <td><input type="text" inputmode="decimal" class="cell-input cell-num" data-key="incentive_pct" value="${r.incentive_pct !== undefined ? r.incentive_pct : 0}" placeholder="0"></td>
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
                const key = input.dataset.key;
                if (key === 'target_bulanan') {
                    attachCurrencyInputBehavior(input, (newVal) => {
                        const idx = parseInt(input.closest('tr').dataset.index);
                        rows[idx][key] = newVal;
                        saveRows(rows);
                    });
                } else if (key === 'incentive_pct') {
                    input.addEventListener('focus', function () {
                        if (this.value.trim() === '0') {
                            this.select();
                        }
                    });

                    input.addEventListener('keydown', (e) => {
                        const allowedKeys = ['Backspace', 'Delete', 'Tab', 'Escape', 'Enter', 'ArrowLeft', 'ArrowRight', 'Home', 'End'];
                        if (allowedKeys.includes(e.key)) return;
                        if (e.ctrlKey || e.metaKey) return;
                        // Prevent negative sign, signs, letters
                        if (!/^[0-9.,]$/.test(e.key)) {
                            e.preventDefault();
                            return;
                        }
                        if ((e.key === '.' || e.key === ',') && (input.value.includes('.') || input.value.includes(','))) {
                            e.preventDefault();
                        }
                    });

                    const handleIncentive = () => {
                        let clean = input.value.replace(/[^0-9.,]/g, '').replace(',', '.');
                        const parts = clean.split('.');
                        if (parts.length > 2) {
                            clean = parts[0] + '.' + parts.slice(1).join('');
                        }
                        let num = parseFloat(clean);
                        if (!isNaN(num) && num > 100) {
                            num = 100;
                            clean = '100';
                        }
                        input.value = clean;
                        const idx = parseInt(input.closest('tr').dataset.index);
                        rows[idx][key] = isNaN(num) ? 0 : num;
                        saveRows(rows);
                    };

                    input.addEventListener('input', handleIncentive);
                    input.addEventListener('blur', () => {
                        let clean = input.value.replace(/[^0-9.,]/g, '').replace(',', '.');
                        let num = parseFloat(clean);
                        if (isNaN(num) || num < 0) num = 0;
                        if (num > 100) num = 100;
                        input.value = num;
                        const idx = parseInt(input.closest('tr').dataset.index);
                        rows[idx][key] = num;
                        saveRows(rows);
                    });
                } else if (key === 'keterangan') {
                    input.addEventListener('input', () => {
                        const idx = parseInt(input.closest('tr').dataset.index);
                        rows[idx][key] = input.value;
                        saveRows(rows);
                    });
                }
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
                rows.push({ target_bulanan: 0, exclude_ppn: isExcludePPNSelected(), incentive_pct: 0, keterangan: '' });
                saveRows(rows);
                render();
            });
        }

        // Listener for Jenis Pajak change to automatically update all rows
        const jenisPajakSelect = form.querySelector('[name="jenis_pajak"]');
        if (jenisPajakSelect && !jenisPajakSelect.dataset.syncTargetIncentive) {
            jenisPajakSelect.dataset.syncTargetIncentive = 'true';
            const handleJPChange = () => {
                const isExclude = isExcludePPNSelected();
                let currentRows = getRows();
                currentRows.forEach(r => {
                    r.exclude_ppn = isExclude;
                });
                saveRows(currentRows);
                render();
            };
            jenisPajakSelect.addEventListener('change', handleJPChange);
            jenisPajakSelect.addEventListener('input', handleJPChange);
        }

        window.renderTargetGrid = render;
        render();
    }

    // --- Grid 4: Discount Scheme ---
    function setupDiscountSchemeGrid(form) {
        const field = form.querySelector('[name="discount_scheme"]');
        if (!field) return;

        field.style.display = 'none';
        const container = createGridContainer(field, 'Discount Scheme (Pasal 6)', 'Rincian komponen potongan harga dan diskon khusus.', 'discount_scheme');

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
                    { komponen: '', nilai: '0%', tipe: 'Persentase', keterangan: '' }
                ];
                saveRows(rows);
            }

            let html = `
                <div class="table-responsive">
                    <table class="table table-bordered kontrak-grid-table" data-grid="discount_scheme">
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
                const isNominal = (r.tipe === 'Nominal');
                let displayVal = r.nilai || '';
                if (isNominal) {
                    displayVal = formatRupiah(parseRupiah(r.nilai));
                }

                html += `
                    <tr data-index="${idx}">
                        <td><input type="text" class="cell-input" data-key="komponen" value="${escapeHtml(r.komponen || '')}" placeholder="Komponen diskon"></td>
                        <td>
                            <input type="text"
                                   inputmode="${isNominal ? 'numeric' : 'decimal'}"
                                   class="cell-input ${isNominal ? 'cell-num cell-nilai-nominal' : 'cell-nilai-persen'}"
                                   data-key="nilai"
                                   data-tipe="${isNominal ? 'Nominal' : 'Persentase'}"
                                   value="${escapeHtml(String(displayVal))}"
                                   placeholder="${isNominal ? 'Misal: 50.000' : 'Misal: 10%'}">
                        </td>
                        <td>
                            <select class="cell-input select-tipe-diskon" data-key="tipe">
                                <option value="Persentase" ${!isNominal ? 'selected' : ''}>Persentase</option>
                                <option value="Nominal" ${isNominal ? 'selected' : ''}>Nominal</option>
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

            container.querySelectorAll('tr[data-index]').forEach(tr => {
                const idx = parseInt(tr.dataset.index);
                const r = rows[idx];
                const nilaiInput = tr.querySelector('[data-key="nilai"]');
                const tipeSelect = tr.querySelector('[data-key="tipe"]');
                const komponenInput = tr.querySelector('[data-key="komponen"]');
                const ketInput = tr.querySelector('[data-key="keterangan"]');

                if (komponenInput) {
                    komponenInput.addEventListener('input', () => {
                        rows[idx].komponen = komponenInput.value;
                        saveRows(rows);
                    });
                }

                if (ketInput) {
                    ketInput.addEventListener('input', () => {
                        rows[idx].keterangan = ketInput.value;
                        saveRows(rows);
                    });
                }

                if (tipeSelect) {
                    tipeSelect.addEventListener('change', () => {
                        const newTipe = tipeSelect.value;
                        rows[idx].tipe = newTipe;
                        if (newTipe === 'Nominal') {
                            const rawNum = parseRupiah(rows[idx].nilai);
                            rows[idx].nilai = rawNum || 0;
                        } else {
                            let clean = String(rows[idx].nilai || '').replace(/[^0-9.,]/g, '').replace(',', '.');
                            let p = parseFloat(clean) || 0;
                            if (p > 100) p = 100;
                            rows[idx].nilai = p + '%';
                        }
                        saveRows(rows);
                        render();
                    });
                }

                if (nilaiInput) {
                    const isNominal = (r.tipe === 'Nominal');
                    if (isNominal) {
                        attachCurrencyInputBehavior(nilaiInput, (newVal) => {
                            rows[idx].nilai = newVal;
                            saveRows(rows);
                        });
                    } else {
                        // Persentase behavior: block letters, allow 0-9, dot, comma, %
                        nilaiInput.addEventListener('focus', function () {
                            if (this.value.trim() === '0%' || this.value.trim() === '0') {
                                this.select();
                            }
                        });

                        nilaiInput.addEventListener('keydown', (e) => {
                            const allowedKeys = ['Backspace', 'Delete', 'Tab', 'Escape', 'Enter', 'ArrowLeft', 'ArrowRight', 'Home', 'End'];
                            if (allowedKeys.includes(e.key)) return;
                            if (e.ctrlKey || e.metaKey) return;
                            if (!/^[0-9.,%]$/.test(e.key)) {
                                e.preventDefault();
                                return;
                            }
                            if ((e.key === '.' || e.key === ',') && (nilaiInput.value.includes('.') || nilaiInput.value.includes(','))) {
                                e.preventDefault();
                            }
                        });

                        nilaiInput.addEventListener('input', () => {
                            let clean = nilaiInput.value.replace(/[^0-9.,%]/g, '');
                            let numStr = clean.replace('%', '').replace(',', '.');
                            let num = parseFloat(numStr) || 0;
                            if (num > 100) {
                                num = 100;
                                clean = '100%';
                            }
                            nilaiInput.value = clean;
                            rows[idx].nilai = clean;
                            saveRows(rows);
                        });

                        nilaiInput.addEventListener('blur', () => {
                            let raw = nilaiInput.value.trim();
                            let numStr = raw.replace(/[^0-9.,]/g, '').replace(',', '.');
                            let num = parseFloat(numStr);
                            if (isNaN(num) || num < 0) num = 0;
                            if (num > 100) num = 100;
                            const formatted = num + '%';
                            nilaiInput.value = formatted;
                            rows[idx].nilai = formatted;
                            saveRows(rows);
                        });
                    }
                }
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
                rows.push({ komponen: '', nilai: '0%', tipe: 'Persentase', keterangan: '' });
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
        const container = createGridContainer(field, 'Tier Support Tahunan / Biaya Sewa (Pasal 7)', 'Target, support %, dan PPh % diinput. Netto dihitung otomatis oleh sistem.', 'tier_support');

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
            const t = Math.max(0, Number(target) || 0);
            const s = Math.min(100, Math.max(0, Number(supportPct) || 0));
            const p = Math.min(100, Math.max(0, Number(pphPct) || 0));
            return Math.round(t * (s / 100) * (1 - p / 100));
        }

        function render() {
            let rows = getRows();
            const suppToggle = form.querySelector('input[name="is_support_provided"]');
            const isSuppEnabled = Boolean(suppToggle && suppToggle.checked);
            if (!rows.length && isSuppEnabled) {
                rows = [
                    { target_tahunan: 0, support_pct: 0, pph_pct: 0, netto: 0, keterangan: '' }
                ];
                saveRows(rows);
            }

            let html = `
                <div class="table-responsive">
                    <table class="table table-bordered kontrak-grid-table" data-grid="tier_support">
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
                        <td><input type="text" inputmode="numeric" class="cell-input cell-num" data-key="target_tahunan" value="${formatRupiah(r.target_tahunan)}"></td>
                        <td><input type="text" inputmode="decimal" class="cell-input cell-num" data-key="support_pct" value="${r.support_pct !== undefined ? r.support_pct : 0}" placeholder="0"></td>
                        <td><input type="text" inputmode="decimal" class="cell-input cell-num" data-key="pph_pct" value="${r.pph_pct !== undefined ? r.pph_pct : 0}" placeholder="0"></td>
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
                                <td class="text-end fw-bold text-primary total-netto-cell">${formatRupiah(totalNetto)}</td>
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
                const key = input.dataset.key;
                if (key === 'target_tahunan') {
                    attachCurrencyInputBehavior(input, (newVal) => {
                        const rowEl = input.closest('tr');
                        const idx = parseInt(rowEl.dataset.index);
                        rows[idx][key] = newVal;

                        // Recalculate Netto
                        const target = Number(rows[idx].target_tahunan) || 0;
                        const supp = Number(rows[idx].support_pct) || 0;
                        const pph = Number(rows[idx].pph_pct) || 0;
                        const netto = calculateNetto(target, supp, pph);
                        rows[idx].netto = netto;

                        const nettoInput = rowEl.querySelector('[data-key="netto"]');
                        if (nettoInput) nettoInput.value = formatRupiah(netto);

                        // Recalculate Total Netto footer without re-rendering the whole table
                        const currentTotalNetto = rows.reduce((sum, r) => sum + (Number(r.netto) || 0), 0);
                        const footerNetto = container.querySelector('.total-netto-cell');
                        if (footerNetto) footerNetto.textContent = formatRupiah(currentTotalNetto);

                        saveRows(rows);
                    });
                } else if (key === 'support_pct' || key === 'pph_pct') {
                    input.addEventListener('focus', function () {
                        if (this.value.trim() === '0') {
                            this.select();
                        }
                    });

                    input.addEventListener('keydown', function (e) {
                        const allowedKeys = ['Backspace', 'Delete', 'Tab', 'Escape', 'Enter', 'ArrowLeft', 'ArrowRight', 'Home', 'End'];
                        if (allowedKeys.includes(e.key)) return;
                        if (e.ctrlKey || e.metaKey) return;
                        // Block negative signs, +, letters, symbols
                        if (!/^[0-9.,]$/.test(e.key)) {
                            e.preventDefault();
                            return;
                        }
                        if ((e.key === '.' || e.key === ',') && (this.value.includes('.') || this.value.includes(','))) {
                            e.preventDefault();
                        }
                    });

                    const handlePct = () => {
                        let clean = input.value.replace(/[^0-9.,]/g, '').replace(',', '.');
                        const parts = clean.split('.');
                        if (parts.length > 2) {
                            clean = parts[0] + '.' + parts.slice(1).join('');
                        }
                        let num = parseFloat(clean);
                        if (!isNaN(num) && num > 100) {
                            num = 100;
                            clean = '100';
                        }
                        input.value = clean;
                        const rowEl = input.closest('tr');
                        const idx = parseInt(rowEl.dataset.index);
                        rows[idx][key] = isNaN(num) ? 0 : num;

                        // Recalculate Netto
                        const target = Number(rows[idx].target_tahunan) || 0;
                        const supp = Number(rows[idx].support_pct) || 0;
                        const pph = Number(rows[idx].pph_pct) || 0;
                        const netto = calculateNetto(target, supp, pph);
                        rows[idx].netto = netto;

                        const nettoInput = rowEl.querySelector('[data-key="netto"]');
                        if (nettoInput) nettoInput.value = formatRupiah(netto);

                        const currentTotalNetto = rows.reduce((sum, r) => sum + (Number(r.netto) || 0), 0);
                        const footerNetto = container.querySelector('.total-netto-cell');
                        if (footerNetto) footerNetto.textContent = formatRupiah(currentTotalNetto);

                        saveRows(rows);
                    };

                    input.addEventListener('input', handlePct);
                    input.addEventListener('blur', () => {
                        let clean = input.value.replace(/[^0-9.,]/g, '').replace(',', '.');
                        let num = parseFloat(clean);
                        if (isNaN(num) || num < 0) num = 0;
                        if (num > 100) num = 100;
                        input.value = num;
                        const rowEl = input.closest('tr');
                        const idx = parseInt(rowEl.dataset.index);
                        rows[idx][key] = num;

                        const target = Number(rows[idx].target_tahunan) || 0;
                        const supp = Number(rows[idx].support_pct) || 0;
                        const pph = Number(rows[idx].pph_pct) || 0;
                        const netto = calculateNetto(target, supp, pph);
                        rows[idx].netto = netto;

                        const nettoInput = rowEl.querySelector('[data-key="netto"]');
                        if (nettoInput) nettoInput.value = formatRupiah(netto);

                        const currentTotalNetto = rows.reduce((sum, r) => sum + (Number(r.netto) || 0), 0);
                        const footerNetto = container.querySelector('.total-netto-cell');
                        if (footerNetto) footerNetto.textContent = formatRupiah(currentTotalNetto);

                        saveRows(rows);
                    });
                } else if (key === 'keterangan') {
                    input.addEventListener('input', () => {
                        const rowEl = input.closest('tr');
                        const idx = parseInt(rowEl.dataset.index);
                        rows[idx][key] = input.value;
                        saveRows(rows);
                    });
                }
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

    function createGridContainer(field, title, hint, gridKey) {
        const wrapper = field.closest('.field-wrapper') || field.closest('.mb-3') || field.parentElement;

        // Hide redundant default Django label and help text
        if (wrapper) {
            const origLabel = wrapper.querySelector('label.form-label, label');
            if (origLabel) origLabel.style.display = 'none';
            const origHelp = wrapper.querySelector('.form-text, .help-block');
            if (origHelp) origHelp.style.display = 'none';
        }

        const container = document.createElement('div');
        const gridClass = gridKey ? `table-${gridKey.replace(/_/g, '-')}` : '';
        container.className = `kontrak-grid-container ${gridClass}`.trim();

        const header = document.createElement('div');
        header.className = 'kontrak-grid-header';
        header.innerHTML = `
            <div class="w-100">
                <div class="d-flex align-items-center justify-content-between flex-wrap gap-2">
                    <h5 class="kontrak-grid-title"><i class="bi bi-table text-primary"></i> ${title}</h5>
                    <span class="scroll-hint-mobile"><i class="bi bi-arrows-expand-vertical-horizontal"></i> Geser tabel untuk input</span>
                </div>
                <div class="kontrak-grid-hint">${hint}</div>
            </div>
        `;

        wrapper.appendChild(header);
        wrapper.appendChild(container);
        return container;
    }

    /* --------------------------------------------------------------------------
     * 4b. Setup Support Facility Conditional Logic (Clean Minimalist Toggle)
     * -------------------------------------------------------------------------- */
    function setupSupportConditionalLogic(form) {
        if (form.dataset.supportConditionalSetup) return;
        form.dataset.supportConditionalSetup = 'true';

        const origToggleInput = form.querySelector('[name="is_support_provided"]');
        if (!origToggleInput) {
            console.warn('[KontrakSupportToggle] is_support_provided not found in form.');
            return;
        }

        const origToggleWrapper = origToggleInput.closest('.field-wrapper') || origToggleInput.closest('.mb-3') || origToggleInput.parentElement;
        if (!origToggleWrapper) return;

        // 1. Clean switch toggle: replace wrapper content with a single clean Bootstrap switch
        origToggleWrapper.className = 'mb-4 pt-2 border-top';
        origToggleWrapper.style.removeProperty('background-color');
        origToggleWrapper.style.removeProperty('border-color');
        origToggleWrapper.innerHTML = `
            <div class="form-check form-switch d-flex align-items-center gap-2">
                <input class="form-check-input" type="checkbox" role="switch" id="toggleSupportFacility" name="is_support_provided" style="width: 2.5em; height: 1.3em; cursor: pointer;">
                <label class="form-check-label fw-bold text-dark mb-0" for="toggleSupportFacility" style="cursor: pointer;">
                    Terdapat Fasilitas / Bentuk Support Tambahan?
                </label>
            </div>
            <div class="form-text text-muted" style="font-size: 12px; margin-left: 3.2em;">
                Aktifkan jika kontrak memiliki fasilitas support promosi atau biaya sewa (Pasal 4 & Pasal 7). Jika tidak, kontrak berlaku reguler.
            </div>
        `;

        const toggleSwitch = origToggleWrapper.querySelector('#toggleSupportFacility');

        // 2. Create or find #kontrak-support-facility-wrapper
        let facilityWrapper = document.getElementById('kontrak-support-facility-wrapper');
        if (!facilityWrapper) {
            facilityWrapper = document.createElement('div');
            facilityWrapper.id = 'kontrak-support-facility-wrapper';
            origToggleWrapper.parentNode.insertBefore(facilityWrapper, origToggleWrapper.nextSibling);
        }
        facilityWrapper.className = 'kontrak-support-facility-wrapper mb-3';
        facilityWrapper.style.display = 'none';
        facilityWrapper.innerHTML = ''; // Clean out any previous gimmick headers or cards

        // 3. Move and organize the 5 rows into facilityWrapper in exact sequence
        // Row 1: Grid 3 kolom (support_promosi, pct_support_promo, frekuensi_pencairan)
        const suppPromo = form.querySelector('[name="support_promosi"]');
        const pctPromo = form.querySelector('[name="pct_support_promo"]');
        const frekPencairan = form.querySelector('[name="frekuensi_pencairan"]');

        let row1 = suppPromo ? suppPromo.closest('.fields-aligned-row') : null;
        if (row1) {
            facilityWrapper.appendChild(row1);
        } else {
            row1 = document.createElement('div');
            row1.className = 'row fields-aligned-row';
            [suppPromo, pctPromo, frekPencairan].forEach(input => {
                if (input) {
                    const block = input.closest('.field-wrapper') || input.closest('.mb-3') || input.closest('.col-md-4') || input.parentElement;
                    if (block) {
                        if (!block.classList.contains('col-md-4')) block.classList.add('col-md-4');
                        row1.appendChild(block);
                    }
                }
            });
            facilityWrapper.appendChild(row1);
        }

        // Row 2: Input syarat_pencairan
        const syaratEl = form.querySelector('[name="syarat_pencairan"]');
        const syaratBlock = syaratEl ? (syaratEl.closest('.field-wrapper') || syaratEl.closest('.mb-3') || syaratEl.parentElement) : null;
        if (syaratBlock) facilityWrapper.appendChild(syaratBlock);

        // Row 3: Input komponen_biaya
        const biayaEl = form.querySelector('[name="komponen_biaya"]');
        const biayaBlock = biayaEl ? (biayaEl.closest('.field-wrapper') || biayaEl.closest('.mb-3') || biayaEl.parentElement) : null;
        if (biayaBlock) facilityWrapper.appendChild(biayaBlock);

        // Row 4: Textarea pengecualian_ketentuan_support
        const pengecualianEl = form.querySelector('[name="pengecualian_ketentuan_support"]');
        const pengecualianBlock = pengecualianEl ? (pengecualianEl.closest('.field-wrapper') || pengecualianEl.closest('.mb-3') || pengecualianEl.parentElement) : null;
        if (pengecualianBlock) facilityWrapper.appendChild(pengecualianBlock);

        // Row 5: Dynamic Table Tier Support Tahunan / Biaya Sewa (Pasal 7)
        const tierEl = form.querySelector('[name="tier_support"]');
        const tierBlock = tierEl ? (tierEl.closest('.field-wrapper') || tierEl.closest('.mb-3') || tierEl.parentElement) : null;
        if (tierBlock) facilityWrapper.appendChild(tierBlock);

        // Ensure all child blocks and containers inside facilityWrapper have display:none cleared
        [row1, syaratBlock, biayaBlock, pengecualianBlock, tierBlock].forEach(block => {
            if (block) {
                block.style.removeProperty('display');
                block.classList.remove('d-none');
                block.querySelectorAll('.field-wrapper, .fields-aligned-row, .mb-3, .col-md-4, select, input, textarea').forEach(child => {
                    if (child.name === 'tier_support' || child.type === 'hidden') {
                        return;
                    }
                    child.style.removeProperty('display');
                    child.classList.remove('d-none');
                });
            }
        });
        if (tierEl) tierEl.style.setProperty('display', 'none', 'important');
        if (tierBlock) {
            const lbl = tierBlock.querySelector('label[for="id_tier_support"]');
            if (lbl) lbl.style.display = 'none';
            const hlp = tierBlock.querySelector('#id_tier_support_helptext');
            if (hlp) hlp.style.display = 'none';
        }

        // 4. Backward Compatibility Check
        const suppSelect = form.querySelector('[name="support_promosi"]');
        const pctSupp = form.querySelector('[name="pct_support_promo"]');
        const tierField = form.querySelector('[name="tier_support"]');
        let hasExistingSupportData = false;

        if (tierField && tierField.value) {
            try {
                const parsed = JSON.parse(tierField.value);
                if (Array.isArray(parsed) && parsed.length > 0) {
                    hasExistingSupportData = parsed.some(r => Number(r.target_tahunan) > 0 || Number(r.support_pct) > 0 || (r.keterangan && r.keterangan.trim()));
                }
            } catch (e) {}
        }

        if ((suppSelect && suppSelect.value) || (pctSupp && parseFloat(pctSupp.value) > 0) || hasExistingSupportData) {
            toggleSwitch.checked = true;
        }

        // 5. Visibility Controller
        function updateSupportVisibility() {
            const isChecked = Boolean(toggleSwitch && toggleSwitch.checked);
            console.log('[KontrakSupportToggle] Visibility updated. isChecked =', isChecked);

            if (facilityWrapper) {
                facilityWrapper.style.display = isChecked ? 'block' : 'none';
                if (isChecked) {
                    // Force-clear any inline display:none or d-none that may have been applied by step transitions
                    facilityWrapper.querySelectorAll('.field-wrapper, .fields-aligned-row, .mb-3, .col-md-4, select, input, textarea').forEach(el => {
                        if (el.name === 'tier_support' || el.type === 'hidden') {
                            return;
                        }
                        el.style.removeProperty('display');
                        el.classList.remove('d-none');
                    });
                    if (tierEl) tierEl.style.setProperty('display', 'none', 'important');
                    if (tierBlock) {
                        const lbl = tierBlock.querySelector('label[for="id_tier_support"]');
                        if (lbl) lbl.style.display = 'none';
                        const hlp = tierBlock.querySelector('#id_tier_support_helptext');
                        if (hlp) hlp.style.display = 'none';
                    }
                }
            }

            if (isChecked) {
                if (tierField) {
                    try {
                        const parsed = JSON.parse(tierField.value || '[]');
                        if (!parsed.length) {
                            tierField.value = JSON.stringify([{ target_tahunan: 0, support_pct: 0, pph_pct: 2, netto: 0, keterangan: '' }]);
                            if (window.renderTierGrid) window.renderTierGrid();
                        }
                    } catch (e) {}
                }
            } else {
                if (tierField) {
                    tierField.value = '[]';
                    if (window.renderTierGrid) window.renderTierGrid();
                }
                ['support_promosi', 'pct_support_promo', 'frekuensi_pencairan', 'syarat_pencairan', 'komponen_biaya', 'pengecualian_ketentuan_support'].forEach(fn => {
                    const el = form.querySelector(`[name="${fn}"]`);
                    if (el) el.value = '';
                });
            }
        }

        // Setup live validation for Support Tambahan fields (pct_support_promo, syarat_pencairan, komponen_biaya)
        setupSupportFieldsValidation(form);

        window.updateSupportVisibility = updateSupportVisibility;

        toggleSwitch.addEventListener('change', updateSupportVisibility);
        updateSupportVisibility();
    }

    function setupSupportFieldsValidation(form) {
        // 1. pct_support_promo: strictly positive percentage (0 - 100%)
        const pctInput = form.querySelector('[name="pct_support_promo"]');
        if (pctInput && !pctInput.dataset.validationAttached) {
            pctInput.dataset.validationAttached = 'true';
            pctInput.setAttribute('type', 'text');
            pctInput.setAttribute('inputmode', 'decimal');
            pctInput.setAttribute('autocomplete', 'off');

            pctInput.addEventListener('focus', function () {
                if (this.value.trim() === '0') {
                    this.select();
                }
            });

            pctInput.addEventListener('keydown', function (e) {
                const allowedKeys = ['Backspace', 'Delete', 'Tab', 'Escape', 'Enter', 'ArrowLeft', 'ArrowRight', 'Home', 'End'];
                if (allowedKeys.includes(e.key)) return;
                if (e.ctrlKey || e.metaKey) return;
                // Reject negative signs, +, letters, symbols
                if (!/^[0-9.,]$/.test(e.key)) {
                    e.preventDefault();
                    return;
                }
                if ((e.key === '.' || e.key === ',') && (this.value.includes('.') || this.value.includes(','))) {
                    e.preventDefault();
                }
            });

            pctInput.addEventListener('input', function () {
                let clean = this.value.replace(/[^0-9.,]/g, '').replace(',', '.');
                const parts = clean.split('.');
                if (parts.length > 2) {
                    clean = parts[0] + '.' + parts.slice(1).join('');
                }
                let num = parseFloat(clean);
                if (!isNaN(num) && num > 100) {
                    num = 100;
                    clean = '100';
                }
                this.value = clean;
            });

            pctInput.addEventListener('blur', function () {
                let clean = this.value.replace(/[^0-9.,]/g, '').replace(',', '.');
                let num = parseFloat(clean);
                if (isNaN(num) || num < 0) {
                    this.value = '';
                } else {
                    if (num > 100) num = 100;
                    this.value = num;
                }
            });
        }

        // 2. syarat_pencairan: reject disallowed symbols like * and #
        const syaratInput = form.querySelector('[name="syarat_pencairan"]');
        if (syaratInput && !syaratInput.dataset.validationAttached) {
            syaratInput.dataset.validationAttached = 'true';
            syaratInput.addEventListener('input', function () {
                const cleaned = this.value.replace(/[^\w\s.,/\-()'"&]/gi, '');
                if (this.value !== cleaned) {
                    this.value = cleaned;
                }
            });
        }

        // 3. komponen_biaya: reject disallowed symbols like * and #
        const biayaInput = form.querySelector('[name="komponen_biaya"]');
        if (biayaInput && !biayaInput.dataset.validationAttached) {
            biayaInput.dataset.validationAttached = 'true';
            biayaInput.addEventListener('input', function () {
                const cleaned = this.value.replace(/[^\w\s.,/\-()]/gi, '');
                if (this.value !== cleaned) {
                    this.value = cleaned;
                }
            });
        }
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

        const isSupport = form.querySelector('[name="is_support_provided"]')?.checked;
        const tipeKontrakBadge = isSupport
            ? '<span class="badge bg-primary text-white py-1 px-2"><i class="bi bi-award me-1"></i>Dengan Fasilitas Support Promosi & Sewa</span>'
            : '<span class="badge bg-secondary text-white py-1 px-2"><i class="bi bi-shield-check me-1"></i>Kontrak Reguler (Murni Target & Diskon DO)</span>';

        container.innerHTML = `
            <div class="col-md-6">
                <div class="small text-muted">Nomor SPK</div>
                <div class="fw-bold text-dark">${getV('nomor_spk') || '—'}</div>
            </div>
            <div class="col-md-6">
                <div class="small text-muted">Customer / Toko JDE</div>
                <div class="fw-bold text-dark">${getV('nama_toko') || '-'} (${getV('kode_customer_jde') || '-'})</div>
            </div>
            <div class="col-md-12">
                <div class="small text-muted">Tipe Pengajuan Kontrak</div>
                <div class="mt-1">${tipeKontrakBadge}</div>
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

        const formatRupiahAccounting = (val) => {
            if (val === null || val === undefined || val === '') return '—';
            const clean = String(val).replace(/[^0-9.-]/g, '');
            const num = parseFloat(clean);
            if (isNaN(num)) return escapeHtml(String(val));
            if (num === 0) return 'Rp 0';
            return 'Rp ' + Math.round(num).toLocaleString('id-ID');
        };

        const formatPercent = (val) => {
            if (val === null || val === undefined || val === '') return '—';
            const s = String(val).trim();
            if (s.endsWith('%')) return escapeHtml(s);
            const num = parseFloat(s);
            if (isNaN(num)) return escapeHtml(s) + '%';
            return (Number.isInteger(num) ? num : parseFloat(num.toFixed(2))) + '%';
        };

        const formatPPN = (val) => {
            if (val === true || val === 'true' || val === 1 || val === '1') return 'Exclude PPN';
            return 'Include PPN';
        };

        const formatDiscountType = (val) => {
            const s = String(val || '').trim().toLowerCase();
            if (s === 'persentage' || s === 'percentage' || s === 'persentase') return 'Persentase';
            if (s === 'nominal') return 'Nominal';
            return escapeHtml(String(val || 'Persentase'));
        };

        const getGridRows = (name) => {
            const el = form.querySelector(`[name="${name}"]`);
            if (!el || !el.value) return [];
            try {
                const parsed = JSON.parse(el.value);
                return Array.isArray(parsed) ? parsed : [];
            } catch (e) {
                return [];
            }
        };

        const nomorSPK = getV('nomor_spk') || '—';
        const toko = getV('nama_toko') || '—';
        const pemilik = getV('nama_pemilik') || '—';
        const alamat = getV('alamat_toko') || '—';
        const identitas = getV('nomor_identitas') || '—';
        const jenisIdentitas = getV('jenis_identitas') || 'KTP / NPWP';
        const noTelepon = getV('no_telepon') || '—';
        const brand = getV('brand') || '—';
        const cabang = getV('cabang') || '—';
        const perusahaan = getV('perusahaan') || '—';
        const rekening = getV('rekening_perusahaan') || '—';
        const jdeCode = getV('kode_customer_jde') || '—';
        const tglMulai = getV('tanggal_mulai') || '—';
        const tglAkhir = getV('tanggal_berakhir') || '—';
        const durasi = getV('durasi') || '—';
        const gracePeriod = getV('grace_period') || '—';
        const pctSupportPromo = getV('pct_support_promo') || '0';
        const frekuensiPencairan = getV('frekuensi_pencairan') || '—';
        const syaratPencairan = getV('syarat_pencairan') || '—';
        const komponenBiaya = getV('komponen_biaya') || '—';
        const pengecualianSupport = getV('pengecualian_ketentuan_support') || '—';
        const top = getV('top') || '—';
        const bayar = getV('metode_pembayaran') || 'Transfer / Cek / Giro';
        const discountDO = getV('discount_do') || '0';
        const ketentuanDO = getV('ketentuan_do') || '—';
        const jenisPajak = getV('jenis_pajak') || 'Exclude PPN';
        const catatanLain = getV('catatan_lain') || '';
        const kota = getV('kota_penandatanganan') || getV('cabang') || getV('kota') || '—';
        const tglTtd = getV('tanggal_penandatanganan') || '—';

        const targetRows = getGridRows('target_incentive');
        const discountRows = getGridRows('discount_scheme');
        const tierRows = getGridRows('tier_support');

        let targetTableHtml = '';
        if (targetRows.length > 0) {
            targetTableHtml = `
                <div class="table-responsive w-100 my-2">
                    <table class="clause-table" style="width: 100%; border-collapse: collapse; margin: 10px 0 16px 0; border: 1px solid #cbd5e1;">
                        <thead>
                            <tr>
                                <th style="background-color: #f1f5f9; color: #1e293b; padding: 8px 10px; font-size: 0.85rem; border: 1px solid #cbd5e1; font-weight: 600; text-align: center;">Target Bulanan</th>
                                <th style="background-color: #f1f5f9; color: #1e293b; padding: 8px 10px; font-size: 0.85rem; border: 1px solid #cbd5e1; font-weight: 600; text-align: center; width: 140px;">Ketentuan Pajak</th>
                                <th style="background-color: #f1f5f9; color: #1e293b; padding: 8px 10px; font-size: 0.85rem; border: 1px solid #cbd5e1; font-weight: 600; text-align: center; width: 120px;">Insentif (%)</th>
                                <th style="background-color: #f1f5f9; color: #1e293b; padding: 8px 10px; font-size: 0.85rem; border: 1px solid #cbd5e1; font-weight: 600; text-align: center;">Keterangan</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${targetRows.map(r => `
                                <tr>
                                    <td style="padding: 7px 10px; font-size: 0.85rem; border: 1px solid #e2e8f0; vertical-align: middle; text-align: center; font-variant-numeric: tabular-nums; font-weight: 500;">${formatRupiahAccounting(r.target_bulanan)}</td>
                                    <td style="padding: 7px 10px; font-size: 0.85rem; border: 1px solid #e2e8f0; vertical-align: middle; text-align: center;">${formatPPN(r.exclude_ppn)}</td>
                                    <td style="padding: 7px 10px; font-size: 0.85rem; border: 1px solid #e2e8f0; vertical-align: middle; text-align: center;">${formatPercent(r.incentive_pct)}</td>
                                    <td style="padding: 7px 10px; font-size: 0.85rem; border: 1px solid #e2e8f0; vertical-align: middle; text-align: center;">${escapeHtml(r.keterangan || '—')}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;
        }

        let discountTableHtml = '';
        if (discountRows.length > 0) {
            discountTableHtml = `
                <div class="table-responsive w-100 my-2">
                    <table class="clause-table" style="width: 100%; border-collapse: collapse; margin: 10px 0 16px 0; border: 1px solid #cbd5e1;">
                        <thead>
                            <tr>
                                <th style="background-color: #f1f5f9; color: #1e293b; padding: 8px 10px; font-size: 0.85rem; border: 1px solid #cbd5e1; font-weight: 600; text-align: center;">Komponen</th>
                                <th style="background-color: #f1f5f9; color: #1e293b; padding: 8px 10px; font-size: 0.85rem; border: 1px solid #cbd5e1; font-weight: 600; text-align: center; width: 120px;">Nilai</th>
                                <th style="background-color: #f1f5f9; color: #1e293b; padding: 8px 10px; font-size: 0.85rem; border: 1px solid #cbd5e1; font-weight: 600; text-align: center; width: 120px;">Tipe</th>
                                <th style="background-color: #f1f5f9; color: #1e293b; padding: 8px 10px; font-size: 0.85rem; border: 1px solid #cbd5e1; font-weight: 600; text-align: center;">Keterangan</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${discountRows.map(r => {
                                const isPct = String(r.tipe || '').toLowerCase().includes('persen') || String(r.nilai || '').includes('%');
                                const valFormatted = isPct ? formatPercent(r.nilai) : formatRupiahAccounting(r.nilai);
                                return `
                                    <tr>
                                        <td style="padding: 7px 10px; font-size: 0.85rem; border: 1px solid #e2e8f0; vertical-align: middle; text-align: left;">${escapeHtml(r.komponen || '—')}</td>
                                        <td style="padding: 7px 10px; font-size: 0.85rem; border: 1px solid #e2e8f0; vertical-align: middle; text-align: center; font-variant-numeric: tabular-nums;">${valFormatted}</td>
                                        <td style="padding: 7px 10px; font-size: 0.85rem; border: 1px solid #e2e8f0; vertical-align: middle; text-align: center;">${formatDiscountType(r.tipe)}</td>
                                        <td style="padding: 7px 10px; font-size: 0.85rem; border: 1px solid #e2e8f0; vertical-align: middle; text-align: center;">${escapeHtml(r.keterangan || '—')}</td>
                                    </tr>
                                `;
                            }).join('')}
                        </tbody>
                    </table>
                </div>
            `;
        }

        let tierTableHtml = '';
        if (tierRows.length > 0) {
            tierTableHtml = `
                <div class="table-responsive w-100 my-2">
                    <table class="clause-table" style="width: 100%; border-collapse: collapse; margin: 10px 0 16px 0; border: 1px solid #cbd5e1;">
                        <thead>
                            <tr>
                                <th style="background-color: #f1f5f9; color: #1e293b; padding: 8px 10px; font-size: 0.85rem; border: 1px solid #cbd5e1; font-weight: 600; text-align: center;">Target Tahunan</th>
                                <th style="background-color: #f1f5f9; color: #1e293b; padding: 8px 10px; font-size: 0.85rem; border: 1px solid #cbd5e1; font-weight: 600; text-align: center; width: 120px;">Dukungan (%)</th>
                                <th style="background-color: #f1f5f9; color: #1e293b; padding: 8px 10px; font-size: 0.85rem; border: 1px solid #cbd5e1; font-weight: 600; text-align: center; width: 100px;">PPh (%)</th>
                                <th style="background-color: #f1f5f9; color: #1e293b; padding: 8px 10px; font-size: 0.85rem; border: 1px solid #cbd5e1; font-weight: 600; text-align: center;">Nilai Netto (Rp)</th>
                                <th style="background-color: #f1f5f9; color: #1e293b; padding: 8px 10px; font-size: 0.85rem; border: 1px solid #cbd5e1; font-weight: 600; text-align: center;">Keterangan</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${tierRows.map(r => `
                                <tr>
                                    <td style="padding: 7px 10px; font-size: 0.85rem; border: 1px solid #e2e8f0; vertical-align: middle; text-align: center; font-variant-numeric: tabular-nums; font-weight: 500;">${formatRupiahAccounting(r.target_tahunan)}</td>
                                    <td style="padding: 7px 10px; font-size: 0.85rem; border: 1px solid #e2e8f0; vertical-align: middle; text-align: center;">${formatPercent(r.support_pct)}</td>
                                    <td style="padding: 7px 10px; font-size: 0.85rem; border: 1px solid #e2e8f0; vertical-align: middle; text-align: center;">${formatPercent(r.pph_pct)}</td>
                                    <td style="padding: 7px 10px; font-size: 0.85rem; border: 1px solid #e2e8f0; vertical-align: middle; text-align: center; font-variant-numeric: tabular-nums; font-weight: 500;">${formatRupiahAccounting(r.netto)}</td>
                                    <td style="padding: 7px 10px; font-size: 0.85rem; border: 1px solid #e2e8f0; vertical-align: middle; text-align: center;">${escapeHtml(r.keterangan || '—')}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;
        }

        const chkSupport = form.querySelector('[name="is_support_provided"]');
        const isSupport = chkSupport ? chkSupport.checked : false;

        const compVal = getV('perusahaan') || '';
        const brandVal = getV('brand') || '';
        const compUpper = compVal.toUpperCase();
        const brandUpper = brandVal.toUpperCase();

        let prof = {
            shortCode: '',
            name: '—',
            director: '—',
            jabatan: '—',
            alamat: '—',
            bankName: '—',
            rekNo: '—',
            rekAn: '—',
            pn: 'Kantor Panitera Pengadilan Negeri —',
            logoUrl: ''
        };

        if (compUpper.includes('PRIMATARA') || compUpper.includes('BANGUN CIPTA') || compUpper === 'BCP') {
            prof = {
                shortCode: 'BCP',
                name: 'PT. BANGUN CIPTA PRIMATARA',
                director: 'Alvin Steven',
                jabatan: 'Direktur PT. BANGUN CIPTA PRIMATARA',
                alamat: 'Kawasan Industri Gandasari, Jl. Raya Industri No. 12, Tangerang',
                bankName: 'BCA KCU CIMAHI',
                rekNo: '139.9888.777 (IDR)',
                rekAn: 'PT. BANGUN CIPTA PRIMATARA',
                pn: 'Kantor Panitera Pengadilan Negeri Tangerang',
                logoUrl: '/static/images/logos/bcp.png'
            };
        } else if (compUpper.includes('BESTARI') || compUpper === 'BM') {
            prof = {
                shortCode: 'BM',
                name: 'PT. BESTARI MULIA',
                director: 'Alvin Steven',
                jabatan: 'Direktur PT. BESTARI MULIA',
                alamat: 'Kawasan Industri Gandasari, Jl. Raya Industri No. 12, Tangerang',
                bankName: 'BCA KCU CIMAHI',
                rekNo: '139.9888.777 (IDR)',
                rekAn: 'PT. BESTARI MULIA',
                pn: 'Kantor Panitera Pengadilan Negeri Tangerang',
                logoUrl: '/static/images/logos/bm.png'
            };
        } else if (compUpper.includes('CEMERLANG ABADI MULIA') || compUpper.includes('ABADI MULIA') || compUpper === 'CAM') {
            prof = {
                shortCode: 'CAM',
                name: 'PT. CEMERLANG ABADI MULIA',
                director: 'Alvin Steven',
                jabatan: 'Direktur PT. CEMERLANG ABADI MULIA',
                alamat: 'Jl. Industri Raya No.8 RT.003 RW.004 Budi Mulya Cikupa Kab.Tangerang, Banten',
                bankName: 'BCA CIMAHI – BANDUNG',
                rekNo: '139.9183.888 (IDR)',
                rekAn: 'PT. CEMERLANG ABADI MULIA',
                pn: 'Kantor Panitera Pengadilan Negeri Bale Bandung',
                logoUrl: '/static/images/logos/cam.png'
            };
        } else if (compUpper.includes('ANUGRAH') || compUpper.includes('ACA')) {
            prof = {
                shortCode: 'ACA',
                name: 'PT. ANUGRAH CEMERLANG ABADI',
                director: 'Alvin Steven',
                jabatan: 'Direktur PT. ANUGRAH CEMERLANG ABADI',
                alamat: 'Jl. Industri Raya No.8 RT.003 RW.004 Budi Mulya Cikupa Kab.Tangerang, Banten',
                bankName: 'BCA CIMAHI – BANDUNG',
                rekNo: '139.9183.888 (IDR)',
                rekAn: 'PT. ANUGRAH CEMERLANG ABADI',
                pn: 'Kantor Panitera Pengadilan Negeri Bale Bandung',
                logoUrl: '/static/images/logos/aca.png'
            };
        } else if (compUpper.includes('SEJAHTERA') || compUpper.includes('RAS') || compUpper.includes('ROYAL') || brandUpper.includes('ROYAL') || brandUpper.includes('FOAM')) {
            prof = {
                shortCode: 'RAS',
                name: 'PT. ROYAL ABADI SEJAHTERA',
                director: 'Alvin Steven',
                jabatan: 'Direktur PT. ROYAL ABADI SEJAHTERA',
                alamat: 'Kawasan Industri Gandasari, Jl. Raya Industri No. 12, Tangerang',
                bankName: 'BCA KCU CIMAHI',
                rekNo: '139.9888.777 (IDR)',
                rekAn: 'PT. ROYAL ABADI SEJAHTERA',
                pn: 'Kantor Panitera Pengadilan Negeri Tangerang',
                logoUrl: '/static/images/logos/ras.png'
            };
        }

        // Calculate Target per 3 Bulan and Incentives
        let targetNum = 0;
        if (targetRows.length > 0 && targetRows[0].target_bulanan) {
            targetNum = parseFloat(String(targetRows[0].target_bulanan).replace(/[^0-9.-]/g, '')) || 0;
        }
        if (!targetNum && getV('nilai_target')) {
            targetNum = parseFloat(String(getV('nilai_target')).replace(/[^0-9.-]/g, '')) || 0;
        }
        const targetPer3Bulan = targetNum ? targetNum * 3 : 0;
        const targetVolText = targetNum ? formatRupiahAccounting(targetNum) : 'Rp —';

        let rewardRateStr = '2.5%';
        let rewardPct = 0.025;
        let pph23Pct = 0.15;
        let pph23Label = '15%';

        if (isSupport) {
            const p = parseFloat(pctSupportPromo) || 5;
            rewardPct = p / 100;
            rewardRateStr = `${p}%`;
            pph23Pct = 0.02;
            pph23Label = '2%';
        } else if (targetRows.length > 0 && targetRows[0].incentive_pct) {
            const p = parseFloat(String(targetRows[0].incentive_pct).replace(/[^0-9.-]/g, '')) || 2.5;
            rewardPct = p / 100;
            rewardRateStr = `${p}%`;
        }

        const insentiveNominal = targetPer3Bulan * rewardPct;
        const pph23Nominal = insentiveNominal * pph23Pct;
        const nettoNominal = insentiveNominal - pph23Nominal;

        let targetPer3BulanText = 'Rp —';
        let insentiveNominalText = 'Rp —';
        let pph23NominalText = 'Rp —';
        let nettoNominalText = 'Rp —';

        if (targetPer3Bulan > 0) {
            targetPer3BulanText = formatRupiahAccounting(targetPer3Bulan);
            insentiveNominalText = formatRupiahAccounting(insentiveNominal);
            pph23NominalText = formatRupiahAccounting(pph23Nominal);
            nettoNominalText = formatRupiahAccounting(nettoNominal);
        } else {
            rewardRateStr = '—';
        }

        let displayNomorSPK = getV('nomor_spk') || '';
        if (!displayNomorSPK || displayNomorSPK === '—' || displayNomorSPK.includes('OTOMATIS') || displayNomorSPK.startsWith('SPK-') || !displayNomorSPK.includes('/')) {
            if (brand && brand !== '—' && cabang && cabang !== '—') {
                const now = new Date();
                const mStr = String(now.getMonth() + 1).padStart(2, '0');
                const yStr = String(now.getFullYear());
                const cleanBrand = (brandUpper.includes('LADY') ? 'LADY' : (brandUpper.includes('ROYAL') || brandUpper.includes('FOAM') ? 'ROYAL' : (brandUpper.includes('SERENITY') ? 'SERENITY' : (brandUpper.includes('ELITE') ? 'ELITE' : (brandUpper.split(' ')[0] || 'BRAND')))));
                const cleanCabang = cabang.toUpperCase();
                displayNomorSPK = `No. [Otomatis]/${cleanBrand}/${prof.shortCode || 'RAS'}/${mStr}/${yStr}`;
            } else {
                displayNomorSPK = 'No. — / — / — / — / —';
            }
        }

        container.innerHTML = `
        <div class="spk-paper-preview contract-paper-pages" style="font-family: 'Times New Roman', Times, serif; font-size: 13.5px; line-height: 1.5; color: #111827; max-width: 820px; margin: 0 auto;">
            <!-- ==================== HALAMAN 1 ==================== -->
            <div class="spk-page-sheet">
                <div class="spk-page-content">
                    <!-- KOP SURAT RESMI -->
                    <div style="text-align: center; margin-bottom: 25px;">
                        <div style="margin-bottom: 8px;">
                            <img src="${prof.logoUrl}" alt="${prof.name}" style="max-height: 48px; width: auto; object-fit: contain; display: inline-block; margin: 0 auto 6px auto;" onerror="this.style.display='none'" />
                        </div>
                        <h2 style="font-size: 16px; font-weight: bold; margin: 0; text-transform: uppercase; letter-spacing: 0.5px;">SURAT PERJANJIAN KERJASAMA</h2>
                        <div style="font-size: 14px; font-weight: bold; margin-top: 4px;">${displayNomorSPK}</div>
                    </div>

                    <!-- IDENTITAS PARA PIHAK -->
                    <p style="margin-bottom: 8px;">Yang bertanda tangan di bawah ini :</p>
                    
                    <table style="width: 100%; border-collapse: collapse; margin-bottom: 8px; margin-left: 20px;">
                        <tr><td style="width: 130px; vertical-align: top;">Nama</td><td style="width: 15px; vertical-align: top;">:</td><td style="font-weight: bold;">${prof.director}</td></tr>
                        <tr><td style="vertical-align: top;">Jabatan</td><td style="vertical-align: top;">:</td><td style="font-weight: bold;">${prof.jabatan}</td></tr>
                        <tr><td style="vertical-align: top;">Alamat</td><td style="vertical-align: top;">:</td><td>${prof.alamat}</td></tr>
                    </table>
                    
                    <p style="margin-bottom: 12px;">Selanjutnya disebut sebagai <strong>PIHAK PERTAMA</strong> selaku Produsen produk Springbed merk <strong>“${brand}”</strong></p>

                    <table style="width: 100%; border-collapse: collapse; margin-bottom: 8px; margin-left: 20px;">
                        <tr><td style="width: 130px; vertical-align: top;">Nama</td><td style="width: 15px; vertical-align: top;">:</td><td style="font-weight: bold;">${pemilik}</td></tr>
                        <tr><td style="vertical-align: top;">Pemilik Tk.</td><td style="vertical-align: top;">:</td><td style="font-weight: bold;">${toko}</td></tr>
                        <tr><td style="vertical-align: top;">Alamat</td><td style="vertical-align: top;">:</td><td>${alamat}</td></tr>
                        <tr><td style="vertical-align: top;">NIK / NPWP</td><td style="vertical-align: top;">:</td><td>${identitas}</td></tr>
                    </table>

                    <p style="margin-bottom: 12px;">Selanjutnya disebut sebagai <strong>PIHAK KEDUA</strong> Dealer produk Springbed merk <strong>“${brand}”</strong></p>

                    <p style="text-align: justify; margin-bottom: 16px;">
                        Dalam upaya meningkatkan kerjasama dalam penjualan produk <strong>${brand}</strong>, kedua belah pihak di atas sepakat untuk menandatangani kontrak perjanjian kerja sama dengan mengikuti syarat – syarat dan ketentuan – ketentuan sebagai berikut :
                    </p>

                    <!-- BAB I -->
                    <div style="text-align: center; font-weight: bold; margin-top: 18px; margin-bottom: 8px;">
                        BAB I<br>OBJEK PERJANJIAN
                    </div>
                    <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 1</div>
                    <p style="text-align: justify; margin-bottom: 12px;">
                        <strong>Pihak Pertama</strong> menitipkan/menjual kepada <strong>Pihak Kedua</strong> Produk Springbed dengan merk “ <strong>${brand}</strong> “ untuk dijual oleh <strong>Pihak Kedua</strong> pada tempat yang telah diberitahukan dan disetujui oleh <strong>Pihak Pertama</strong> dengan mengacu pada ketentuan Volume dan Harga Penjualan yang telah di sepakati.
                    </p>

                    <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 2</div>
                    <p style="text-align: justify; margin-bottom: 16px;">
                        Omzet penjualan ${brand} PIHAK KEDUA dihitung berdasarkan harga setelah dikurangi potongan retur, discount dan potongan – potongan lainnya (harga netto), berdasarkan price list yang berlaku mulai tanggal 1 Februari 2023 dan mengikuti perubahannya. (Harga tidak mengikat)
                    </p>

                    <!-- BAB II -->
                    <div style="text-align: center; font-weight: bold; margin-top: 18px; margin-bottom: 8px;">
                        BAB II<br>VOLUME PENJUALAN dan PENGHARGAAN – PERIODE KONTRAK - SKEMA DISCOUNT
                    </div>
                    
                    <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 3</div>
                    <div style="margin-top: 0; margin-bottom: 12px;">
                        <p style="text-align: justify; margin-bottom: 4px; text-indent: -24px; padding-left: 24px;">(1) Para Pihak sepakat bahwa Target Volume Penjualan produk selama jangka waktu perjanjian ini <strong>${targetVolText}</strong> per bulan Exclude Ppn.</p>
                        <p style="text-align: justify; margin-bottom: 0; text-indent: -24px; padding-left: 24px;">(2) Pihak Kedua wajib memenuhi Volume Penjualan yang telah ditentukan dalam perjanjian ini.</p>
                    </div>
                    ${targetTableHtml || '<p class="text-muted fst-italic">Belum ada tier target bulanan yang ditambahkan.</p>'}

                    ${isSupport ? `
                    <!-- PASAL 4 KHUSUS SUPPORT PROMOSI -->
                    <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 4</div>
                    <ol style="margin-top: 0; margin-bottom: 12px; padding-left: 20px;">
                        <li style="text-align: justify; margin-bottom: 4px;">Pihak Pertama memberikan support promosi yang meliputi biaya (sewa, instore, pameran, listrik, dan asuransi) kepada Pihak Kedua sebesar <strong>${pctSupportPromo}%</strong>. Support promosi tersebut <strong>TIDAK</strong> meliputi biaya Billboard, Pajak Billboard, dan Backdrop apabila Pihak Kedua membuka cabang baru atau toko baru.</li>
                        <li style="text-align: justify; margin-bottom: 4px;">Support promosi ini dapat dicairkan setelah pembayaran <strong>LUNAS</strong>.</li>
                        <li style="text-align: justify;">Grace period selama 1 (satu) bulan dari masa kontrak berakhir, apabila Pihak Kedua belum mencapai target.</li>
                    </ol>

                    <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 5</div>
                    <p style="text-align: justify; margin-bottom: 12px;">
                        Perjanjian berlaku untuk Jangka Waktu <strong>${durasi}</strong> terhitung dari sejak tanggal <strong>${tglMulai}</strong> dan akan berakhir pada tanggal <strong>${tglAkhir}</strong>.
                    </p>

                    <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 6</div>
                    <p style="text-align: justify; margin-bottom: 6px;">
                        Skema discount untuk penjualan Produk yang berlaku untuk Pihak Kedua dalam Perjanjian ini adalah sebagai berikut :
                    </p>
                    ${discountTableHtml || '<p class="text-muted fst-italic">Belum ada skema diskon yang ditambahkan.</p>'}
                    ` : `
                    <!-- STANDARD REGULER -->
                    <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 4</div>
                    <p style="text-align: justify; margin-bottom: 12px;">
                        Perjanjian berlaku untuk Jangka Waktu <strong>${durasi}</strong> terhitung dari sejak tanggal <strong>${tglMulai}</strong> dan akan berakhir pada tanggal <strong>${tglAkhir}</strong>.
                    </p>

                    <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 5</div>
                    <p style="text-align: justify; margin-bottom: 6px;">
                        Skema discount untuk penjualan Produk yang berlaku untuk Pihak Kedua dalam Perjanjian ini adalah sebagai berikut :
                    </p>
                    ${discountTableHtml || '<p class="text-muted fst-italic">Belum ada skema diskon yang ditambahkan.</p>'}
                    `}
                </div>
                <div class="spk-page-footer">Halaman 1 dari 2</div>
            </div>

            <!-- ==================== HALAMAN 2 ==================== -->
            <div class="spk-page-sheet">
                <div class="spk-page-content">
                    <div style="text-align: center; margin-bottom: 15px;">
                        <img src="${prof.logoUrl}" alt="${prof.name}" style="max-height: 44px; width: auto; object-fit: contain; display: inline-block; margin: 0 auto 6px auto;" onerror="this.style.display='none'" />
                    </div>

                    ${!isSupport ? `
                    <!-- STANDARD: 11 PASAL (HALAMAN 2: PASAL 6 S/D 11) -->
                    <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 6</div>
                    <p style="text-align: justify; margin-bottom: 6px;">
                        Pihak Pertama memberikan kompensasi Insentive Reward kepada Pihak Kedua saat perjanjian ini berakhir dan seluruh kewajiban Pihak Kedua kepada Pihak Pertama telah selesai atau LUNAS<br>
                        Adapun perhitungan insentif adalah sebagai berikut :
                    </p>
                    <div style="margin-left: 15px; margin-bottom: 16px;">
                        <p style="margin: 3px 0;">• Target ${targetPer3BulanText} per 3 Bulan mendapatkan insentif reward ${rewardRateStr}</p>
                        <table style="width: 100%; border-collapse: collapse; margin-top: 4px;">
                            <tr><td style="width: 250px;">Insentive Reward</td><td style="width: 15px;">=</td><td>${insentiveNominalText} &nbsp; &nbsp; ( ${rewardRateStr} x Pencapaian Omzet )</td></tr>
                            <tr><td>Pph 23 Untuk Insentive Kontrak</td><td>=</td><td>${pph23NominalText} &nbsp; &nbsp; ( Insentive x 15% )</td></tr>
                            <tr><td>Netto Reward</td><td>=</td><td>${nettoNominalText} &nbsp; &nbsp; (Total Insentive – Pph 23)</td></tr>
                        </table>
                        <p style="margin-top: 6px; font-weight: bold;">Maka insentive yang dibayarkan adalah sebesar ${nettoNominalText}.</p>
                    </div>

                    <!-- BAB III (STANDARD: PASAL 7, 8, 9) -->
                    <div style="text-align: center; font-weight: bold; margin-top: 18px; margin-bottom: 8px;">
                        BAB III<br>TATA CARA PEMBAYARAN
                    </div>
                    
                    <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 7</div>
                    <p style="text-align: justify; margin-bottom: 12px;">
                        Wajib melaksanakan Pembayaran kepada Pihak Pertama paling lambat <strong>${top}</strong> hari setelah tanggal pengiriman ( selanjutnya disebut “ Jangka Waktu Pembayaran” ).
                    </p>

                    <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 8</div>
                    <p style="text-align: justify; margin-bottom: 12px;">
                        Sistem pembayaran melalui Transfer atau buka Cek/Giro yang telah di tulis nama <strong>${prof.name}</strong> dengan Nomer Rekening sesuai yang ada pada Faktur dan kontrabon. Serta <strong>TIDAK DIPERKENANKAN</strong> membayar secara TUNAI kepada Salesman/Collector/Kepala Depo/ASM/BM atau menitip pembayaran kepada Supir maupun Karyawan lainnya.
                    </p>

                    <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 9</div>
                    <p style="text-align: justify; margin-bottom: 6px;">
                        Pembayaran dianggap sah apabila dana telah masuk ke rekening ${prof.name}, dengan nomer rekening sbb :
                    </p>
                    <div style="text-align: center; margin: 8px 0;">
                        <table style="margin: 0 auto; border-collapse: collapse; border: none; font-size: 13.5px; font-weight: bold;">
                            <tr>
                                <td style="padding: 1px 4px; text-align: left; width: 75px; border: none;">AN</td>
                                <td style="padding: 1px 4px; text-align: center; width: 15px; border: none;">:</td>
                                <td style="padding: 1px 4px; text-align: left; border: none;">${prof.rekAn}</td>
                            </tr>
                            <tr>
                                <td style="padding: 1px 4px; text-align: left; border: none;">BANK</td>
                                <td style="padding: 1px 4px; text-align: center; border: none;">:</td>
                                <td style="padding: 1px 4px; text-align: left; border: none;">${prof.bankName}</td>
                            </tr>
                            <tr>
                                <td style="padding: 1px 4px; text-align: left; border: none;">NO REK</td>
                                <td style="padding: 1px 4px; text-align: center; border: none;">:</td>
                                <td style="padding: 1px 4px; text-align: left; border: none;">${prof.rekNo}</td>
                            </tr>
                        </table>
                    </div>
                    <p style="text-align: justify; margin-bottom: 16px;">
                        Walaupun nota asli sudah di serahkan / dititipkan oleh salesman maka belum dianggap sebagai pembayaran.
                    </p>

                    <!-- BAB IV (STANDARD: PASAL 10, 11) -->
                    <div style="text-align: center; font-weight: bold; margin-top: 18px; margin-bottom: 8px;">
                        BAB IV<br>ITIKAD BAIK DAN PERSELISIHAN
                    </div>
                    
                    <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 10</div>
                    <p style="text-align: justify; margin-bottom: 12px;">
                        Para pihak dengan itikad baik dan penuh tanggung jawab menjalankan tugas, hak dan kewajibannya dengan mengindahkan peraturan perundangan yang berlaku.
                    </p>

                    <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 11</div>
                    <p style="text-align: justify; margin-bottom: 14px;">
                        Apabila terjadi perselisihan/sengketa diantara Para Pihak terkait dengan isi dan/atau Pelaksanaan Perjanjian ini maka perselisihan tersebut akan di selesaikan terlebih dahulu melalui musyawarah mufakat diantara Para Pihak. Apabila dengan cara musyawarah mufakat tidak dapat dilakukan atau tidak tercapai sesuatu penyelesaian yang baik bagi Para Pihak maka Para Pihak sepakat untuk memilih <strong>${prof.pn}</strong> sebagai satu satunya domisili hukum yang tetap bagi Para Pihak.
                    </p>
                    ` : `
                    <!-- SUPPORT PROMOSI: 12 PASAL (HALAMAN 2: PASAL 7 S/D 12) -->
                    <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 7</div>
                    <p style="text-align: justify; margin-bottom: 6px;">
                        Pihak Pertama memberikan kompensasi Insentive Reward kepada Pihak Kedua saat perjanjian ini berakhir dan seluruh kewajiban Pihak Kedua kepada Pihak Pertama telah selesai atau LUNAS<br>
                        Adapun perhitungan insentif adalah sebagai berikut :
                    </p>
                    <div style="margin-left: 15px; margin-bottom: 16px;">
                        <p style="margin: 3px 0;">• Target ${targetPer3BulanText} per 3 Bulan mendapatkan reward (support promosi) ${pctSupportPromo}%</p>
                        <table style="width: 100%; border-collapse: collapse; margin-top: 4px;">
                            <tr><td style="width: 250px;">Insentive Reward</td><td style="width: 15px;">=</td><td>${insentiveNominalText} &nbsp; &nbsp; ( ${pctSupportPromo}% x Pencapaian Omzet )</td></tr>
                            <tr><td>Pph 23 Untuk Insentive Kontrak</td><td>=</td><td>${pph23NominalText} &nbsp; &nbsp; ( Reward x 2% )</td></tr>
                            <tr><td>Netto Reward</td><td>=</td><td>${nettoNominalText} &nbsp; &nbsp; (Total Insentive – Pph 23)</td></tr>
                        </table>
                        <p style="margin-top: 6px; font-weight: bold;">Maka insentive yang dibayarkan adalah sebesar ${nettoNominalText}.</p>
                    </div>
                    ${tierTableHtml || ''}

                    <!-- BAB III (SUPPORT PROMOSI: PASAL 8, 9, 10) -->
                    <div style="text-align: center; font-weight: bold; margin-top: 18px; margin-bottom: 8px;">
                        BAB III<br>TATA CARA PEMBAYARAN
                    </div>
                    
                    <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 8</div>
                    <p style="text-align: justify; margin-bottom: 12px;">
                        Wajib melaksanakan Pembayaran kepada Pihak Pertama paling lambat <strong>${top}</strong> hari setelah tanggal pengiriman ( selanjutnya disebut “ Jangka Waktu Pembayaran” ).
                    </p>

                    <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 9</div>
                    <p style="text-align: justify; margin-bottom: 12px;">
                        Sistem pembayaran melalui Transfer atau buka Cek/Giro yang telah di tulis nama <strong>${prof.name}</strong> dengan Nomer Rekening sesuai yang ada pada Faktur dan kontrabon. Serta <strong>TIDAK DIPERKENANKAN</strong> membayar secara TUNAI kepada Salesman/Collector/Kepala Depo/ASM/BM atau menitip pembayaran kepada Supir maupun Karyawan lainnya.
                    </p>

                    <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 10</div>
                    <p style="text-align: justify; margin-bottom: 6px;">
                        Pembayaran dianggap sah apabila dana telah masuk ke rekening ${prof.name}, dengan nomer rekening sbb :
                    </p>
                    <div style="text-align: center; margin: 8px 0;">
                        <table style="margin: 0 auto; border-collapse: collapse; border: none; font-size: 13.5px; font-weight: bold;">
                            <tr>
                                <td style="padding: 1px 4px; text-align: left; width: 75px; border: none;">AN</td>
                                <td style="padding: 1px 4px; text-align: center; width: 15px; border: none;">:</td>
                                <td style="padding: 1px 4px; text-align: left; border: none;">${prof.rekAn}</td>
                            </tr>
                            <tr>
                                <td style="padding: 1px 4px; text-align: left; border: none;">BANK</td>
                                <td style="padding: 1px 4px; text-align: center; border: none;">:</td>
                                <td style="padding: 1px 4px; text-align: left; border: none;">${prof.bankName}</td>
                            </tr>
                            <tr>
                                <td style="padding: 1px 4px; text-align: left; border: none;">NO REK</td>
                                <td style="padding: 1px 4px; text-align: center; border: none;">:</td>
                                <td style="padding: 1px 4px; text-align: left; border: none;">${prof.rekNo}</td>
                            </tr>
                        </table>
                    </div>
                    <p style="text-align: justify; margin-bottom: 16px;">
                        Walaupun nota asli sudah di serahkan / dititipkan oleh salesman maka belum dianggap sebagai pembayaran.
                    </p>

                    <!-- BAB IV (SUPPORT PROMOSI: PASAL 11, 12) -->
                    <div style="text-align: center; font-weight: bold; margin-top: 18px; margin-bottom: 8px;">
                        BAB IV<br>ITIKAD BAIK DAN PERSELISIHAN
                    </div>
                    
                    <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 11</div>
                    <p style="text-align: justify; margin-bottom: 12px;">
                        Para pihak dengan itikad baik dan penuh tanggung jawab menjalankan tugas, hak dan kewajibannya dengan mengindahkan peraturan perundangan yang berlaku.
                    </p>

                    <div style="text-align: center; font-weight: bold; margin-bottom: 4px; text-decoration: underline;">Pasal 12</div>
                    <p style="text-align: justify; margin-bottom: 14px;">
                        Apabila terjadi perselisihan/sengketa diantara Para Pihak terkait dengan isi dan/atau Pelaksanaan Perjanjian ini maka perselisihan tersebut akan di selesaikan terlebih dahulu melalui musyawarah mufakat diantara Para Pihak. Apabila dengan cara musyawarah mufakat tidak dapat dilakukan atau tidak tercapai sesuatu penyelesaian yang baik bagi Para Pihak maka Para Pihak sepakat untuk memilih <strong>${prof.pn}</strong> sebagai satu satunya domisili hukum yang tetap bagi Para Pihak.
                    </p>
                    `}

                    <p style="text-align: justify; margin-bottom: 24px;">
                        DENGAN DEMIKIAN,Para Pihak telah menandatangani Perjanjian ini dalam 2 (dua) rangkap yang masing-masing berlaku sebagai asli, bermaterai cukup dan berkekuatan hukum yang sama yang dapat dipergunakan secara sah sebagai bukti adanya kesepakatan diantara Para Pihak.
                    </p>

                    <div style="margin-top: 25px;">
                        <div style="text-align: left; margin-bottom: 15px; font-weight: bold;">
                            ${kota}, ${tglTtd}
                        </div>
                        <table class="spk-signatures-table" style="width: 100%; border-collapse: collapse; text-align: center; font-size: 14px;">
                            <tr>
                                <td style="width: 50%; font-weight: bold; vertical-align: top;">
                                    PIHAK PERTAMA<br>
                                    ${prof.name}
                                </td>
                                <td style="width: 50%; font-weight: bold; vertical-align: top;">
                                    PIHAK KEDUA<br>
                                    ${toko}
                                </td>
                            </tr>
                            <tr>
                                <td style="height: 65px; vertical-align: middle;">
                                    <div style="color: #94a3b8; font-size: 11px; font-style: italic;">
                                        (Tanda Tangan &amp; Pengesahan)
                                    </div>
                                </td>
                                <td style="height: 65px; vertical-align: middle;">
                                    <div style="color: #94a3b8; font-size: 11px; font-style: italic;">
                                        (Tanda Tangan Mitra Toko)
                                    </div>
                                </td>
                            </tr>
                            <tr>
                                <td style="vertical-align: top;">
                                    <div style="border-bottom: 1px solid #111; display: inline-block; min-width: 180px; font-weight: bold;">${prof.director}</div><br>
                                    ${prof.director !== '—' ? (prof.jabatan || 'Direktur') : '—'}
                                </td>
                                <td style="vertical-align: top;">
                                    <div style="border-bottom: 1px solid #111; display: inline-block; min-width: 180px; font-weight: bold;">${pemilik}</div><br>
                                    ${pemilik !== '—' ? 'Pemilik Toko' : '—'}
                                </td>
                            </tr>
                        </table>
                    </div>
                </div>
                <div class="spk-page-footer">Halaman 2 dari 2</div>
            </div>
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

                    // Custom validation for Nomor Identitas when leaving Step 1
                    if (currentStep === 0 && typeof form._validateNomorIdentitas === 'function') {
                        const isIdValid = form._validateNomorIdentitas(true);
                        if (!isIdValid) {
                            hasError = true;
                            const nomorInput = form.querySelector('[name="nomor_identitas"]');
                            if (!firstInvalid && nomorInput) firstInvalid = nomorInput;
                        }
                    }

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

                    // Ensure all field elements inside active pane are visible (except support facility if unchecked)
                    pane.querySelectorAll('.field-wrapper, .fields-aligned-row, .mb-3').forEach(el => {
                        if (el.tagName !== 'INPUT') {
                            if (el.id === 'kontrak-support-facility-wrapper' || el.closest('#kontrak-support-facility-wrapper')) {
                                return; // Do not touch support facility elements in this loop
                            }
                            el.style.removeProperty('display');
                        }
                    });

                    // Ensure support facility visibility is synchronized if on Step 2
                    if (idx === 1 && typeof window.updateSupportVisibility === 'function') {
                        window.updateSupportVisibility(true);
                    }

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

            window.switchWizardStep = switchWizardStep;
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
            if (k === 'cabang' || k === 'perusahaan') return false;
            if (typeof v === 'boolean') return v;
            if (typeof v === 'string') {
                const trimmed = v.trim();
                if (!trimmed) return false;
                if (trimmed === '[]') return false;
                if (trimmed === '[{"no":1,"keterangan":"","alamat":"","status":"Pribadi"}]') return false;
                if (trimmed.includes('"bulan":""') && trimmed.includes('"serenity":0')) {
                    try {
                        const parsed = JSON.parse(trimmed);
                        const hasVal = parsed.some(r => (r.bulan && r.bulan.trim() !== '') || r.serenity > 0 || r.kompetitor_1 > 0 || r.kompetitor_2 > 0 || r.kompetitor_3 > 0 || r.kompetitor_4 > 0);
                        if (!hasVal) return false;
                    } catch (e) {
                        return false;
                    }
                }
                if (trimmed.includes('"target_bulanan":0') && trimmed.includes('"incentive_pct":0')) {
                    try {
                        const parsed = JSON.parse(trimmed);
                        const hasVal = parsed.some(r => r.target_bulanan > 0 || r.incentive_pct > 0 || (r.keterangan && r.keterangan.trim() !== ''));
                        if (!hasVal) return false;
                    } catch (e) {
                        return false;
                    }
                }
                if (trimmed.includes('"target_tahunan":0') && trimmed.includes('"support_pct":0')) {
                    try {
                        const parsed = JSON.parse(trimmed);
                        const hasVal = parsed.some(r => r.target_tahunan > 0 || r.support_pct > 0 || (r.keterangan && r.keterangan.trim() !== ''));
                        if (!hasVal) return false;
                    } catch (e) {
                        return false;
                    }
                }
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
        } else if (state === 'saved_server' || state === 'saved') {
            indicator.className = 'auto-save-indicator saved';
            indicator.innerHTML = '<i class="bi bi-cloud-check text-success me-1"></i> Draf tersimpan di server';
        } else if (state === 'saved_local') {
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

    function showDraftPromptModal(form, draftData, serverDraftMeta, onContinue) {
        const tokoName = draftData.nama_toko || serverDraftMeta?.dataset.toko || 'Toko Belum Diisi';
        const spkNo = draftData.nomor_spk || serverDraftMeta?.dataset.spk || 'Nomor SPK Otomatis';
        const brand = draftData.brand || serverDraftMeta?.dataset.brand || 'SERENITY';
        const dateStr = serverDraftMeta?.dataset.createdAt || 'tersimpan sebelumnya';

        let modalEl = document.getElementById('kontrakDraftDetectedModal');
        if (!modalEl) {
            modalEl = document.createElement('div');
            modalEl.id = 'kontrakDraftDetectedModal';
            modalEl.className = 'modal fade';
            modalEl.setAttribute('tabindex', '-1');
            modalEl.setAttribute('data-bs-backdrop', 'static');
            modalEl.setAttribute('data-bs-keyboard', 'false');

            modalEl.innerHTML = `
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content border-0 shadow-lg rounded-4 overflow-hidden">
                        <div class="modal-header bg-light border-0 py-3 px-4">
                            <h5 class="modal-title fw-bold text-dark d-flex align-items-center gap-2 mb-0" style="font-size: 1.1rem;">
                                <i class="bi bi-clock-history text-primary fs-5"></i> Draf Pengajuan Ditemukan
                            </h5>
                        </div>
                        <div class="modal-body p-4">
                            <p class="text-secondary mb-3" style="font-size: 14px;">
                                Anda memiliki draf pengajuan yang belum selesai tersimpan di sistem:
                            </p>
                            <div class="p-3 bg-light rounded-3 border mb-3">
                                <div class="d-flex align-items-center justify-content-between mb-1">
                                    <span class="badge bg-primary-subtle text-primary fw-semibold px-2 py-1" style="font-size: 11px;" id="modalDraftBrand">${escapeHtml(brand)}</span>
                                    <span class="text-muted small" style="font-size: 11.5px;" id="modalDraftDate">${escapeHtml(dateStr)}</span>
                                </div>
                                <div class="fw-bold text-dark fs-6 mt-2" id="modalDraftToko">${escapeHtml(tokoName)}</div>
                                <div class="text-muted small mt-1" style="font-family: monospace; font-size: 12px;" id="modalDraftSPK">${escapeHtml(spkNo)}</div>
                            </div>
                            <p class="text-secondary small mb-0">
                                Apakah Anda ingin melanjutkan pengisian draf ini atau membuat pengajuan baru dari awal?
                            </p>
                        </div>
                        <div class="modal-footer border-0 bg-light py-3 px-4 d-flex justify-content-between">
                            <button type="button" class="btn btn-outline-danger btn-sm px-3" id="btnModalDiscardDraft">
                                <i class="bi bi-trash me-1"></i> Buat Pengajuan Baru
                            </button>
                            <button type="button" class="btn btn-primary btn-sm px-4 fw-semibold" id="btnModalContinueDraft">
                                <i class="bi bi-pencil-square me-1"></i> Lanjutkan Draf
                            </button>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(modalEl);
        }

        const bsModal = new bootstrap.Modal(modalEl);

        const btnContinue = modalEl.querySelector('#btnModalContinueDraft');
        const btnDiscard = modalEl.querySelector('#btnModalDiscardDraft');

        btnContinue.onclick = function () {
            bsModal.hide();
            if (typeof onContinue === 'function') {
                onContinue();
            }
        };

        btnDiscard.onclick = function () {
            bsModal.hide();
            discardDraft(form, true);
        };

        bsModal.show();
    }

    function showDiscardDraftButton(form, show) {
        const footerActions = form.querySelector('.footer-right-actions') || form.querySelector('.form-wizard-footer');
        if (!footerActions) return;

        const serverDiscardBtn = footerActions.querySelector('#btnDiscardDraft');
        if (serverDiscardBtn) {
            // Server button already exists, no need to add duplicate
            return;
        }

        let btnDiscard = form.querySelector('#btnLocalDiscardDraft');
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

    function discardDraft(form, skipConfirm) {
        if (skipConfirm || confirm('Apakah Anda yakin ingin membuang draft dan mengosongkan seluruh formulir?')) {
            try {
                localStorage.removeItem(STORAGE_KEY);
            } catch (e) {}

            const serverDraftId = form.dataset.currentDraftId || form.querySelector('input[name="draft_id"]')?.value;
            if (serverDraftId) {
                const tokenInput = form.querySelector('[name="csrfmiddlewaretoken"]');
                const csrfToken = tokenInput ? tokenInput.value : '';
                fetch(`/forms/submissions/${serverDraftId}/discard/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken,
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                }).catch(e => console.warn('[KontrakDraft] Failed to discard server draft:', e));
            }

            window.location.href = window.location.pathname;
        }
    }

    function setupFormPersistence(form) {
        let autoSaveTimeout = null;
        let serverSaveTimeout = null;

        function saveDraftToServer(data) {
            const autoSaveUrl = '/forms/permohonan-kontrak/auto-save/';
            const tokenInput = form.querySelector('[name="csrfmiddlewaretoken"]');
            let csrfToken = tokenInput ? tokenInput.value : '';
            if (!csrfToken) {
                csrfToken = document.cookie
                    .split('; ')
                    .find(row => row.startsWith('csrftoken='))
                    ?.split('=')[1] || '';
            }

            fetch(autoSaveUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify(data)
            })
            .then(res => {
                if (!res.ok) throw new Error('HTTP ' + res.status);
                return res.json();
            })
            .then(resData => {
                if (resData.success) {
                    updateAutoSaveStatus('saved_server');
                    if (resData.draft_id) {
                        form.dataset.currentDraftId = resData.draft_id;
                        let draftIdInput = form.querySelector('input[name="draft_id"]');
                        if (!draftIdInput) {
                            draftIdInput = document.createElement('input');
                            draftIdInput.type = 'hidden';
                            draftIdInput.name = 'draft_id';
                            form.appendChild(draftIdInput);
                        }
                        draftIdInput.value = resData.draft_id;
                    }
                } else {
                    updateAutoSaveStatus('saved_local');
                }
            })
            .catch(err => {
                console.warn('[KontrakDraft] Server auto-save failed, saved in browser:', err);
                updateAutoSaveStatus('saved_local');
            });
        }

        function scheduleSave() {
            clearTimeout(autoSaveTimeout);
            clearTimeout(serverSaveTimeout);
            updateAutoSaveStatus('saving');

            autoSaveTimeout = setTimeout(() => {
                try {
                    const data = collectFormData(form);
                    if (hasMeaningfulData(data)) {
                        localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
                        updateAutoSaveStatus('saved_local');
                        showDiscardDraftButton(form, true);

                        serverSaveTimeout = setTimeout(() => {
                            saveDraftToServer(data);
                        }, 500);
                    } else {
                        localStorage.removeItem(STORAGE_KEY);
                        updateAutoSaveStatus('idle');
                        showDiscardDraftButton(form, false);
                    }
                } catch (e) {
                    console.warn('[KontrakDraft] Error saving draft:', e);
                    updateAutoSaveStatus('error');
                }
            }, 300);
        }

        form.addEventListener('input', scheduleSave);
        form.addEventListener('change', scheduleSave);

        // Clear on successful form submission
        form.addEventListener('submit', function (e) {
            if (typeof form._validateNomorIdentitas === 'function') {
                const isIdValid = form._validateNomorIdentitas(true);
                if (!isIdValid) {
                    e.preventDefault();
                    if (window.switchWizardStep) {
                        window.switchWizardStep(0, false);
                    }
                    const nomorInput = form.querySelector('[name="nomor_identitas"]');
                    if (nomorInput) {
                        nomorInput.focus();
                        nomorInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                    return false;
                }
            }
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
