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
        const storeFields = ['kode_customer_jde', 'nama_toko', 'nama_pemilik', 'alamat_toko', 'no_telepon', 'email', 'kota', 'nomor_nik', 'nomor_npwp', 'nomor_identitas', 'komponen_biaya', 'nomor_spk'];
        storeFields.forEach(name => {
            const el = form.querySelector(`[name="${name}"]`);
            if (el) el.value = '';
        });
        form.querySelectorAll('input[name="komponen_biaya"]').forEach(chk => { chk.checked = false; });

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
            if (!draftData || typeof draftData !== 'object') return;
            console.log('[KontrakGridWidget] Applying candidate draft data to form fields...', draftData);

            // Backward compatibility for nomor_identitas -> nomor_nik / nomor_npwp
            if (draftData.nomor_identitas && (!draftData.nomor_nik || !draftData.nomor_npwp)) {
                const digitsOnly = String(draftData.nomor_identitas).replace(/\D/g, '');
                if (digitsOnly.length === 15) {
                    if (!draftData.nomor_npwp) draftData.nomor_npwp = digitsOnly;
                } else if (digitsOnly.length === 16) {
                    const jenis = String(draftData.jenis_identitas || '').toUpperCase();
                    if (jenis.includes('NPWP')) {
                        if (!draftData.nomor_npwp) draftData.nomor_npwp = digitsOnly;
                    } else {
                        if (!draftData.nomor_nik) draftData.nomor_nik = digitsOnly;
                    }
                } else {
                    if (!draftData.nomor_nik) draftData.nomor_nik = digitsOnly;
                }
            }

            // Handle komponen_biaya checkboxes restoration
            if (draftData.komponen_biaya !== undefined) {
                let items = [];
                if (Array.isArray(draftData.komponen_biaya)) {
                    items = draftData.komponen_biaya;
                } else if (typeof draftData.komponen_biaya === 'string') {
                    try {
                        const parsed = JSON.parse(draftData.komponen_biaya);
                        if (Array.isArray(parsed)) items = parsed;
                        else items = draftData.komponen_biaya.split(',').map(s => s.trim());
                    } catch (e) {
                        items = draftData.komponen_biaya.split(',').map(s => s.trim());
                    }
                }
                const chks = form.querySelectorAll('input[name="komponen_biaya"]');
                chks.forEach(chk => {
                    chk.checked = items.some(item => String(item).trim().toLowerCase() === chk.value.toLowerCase());
                });
            }

            Object.keys(draftData).forEach(name => {
                if (name === 'komponen_biaya' || name === 'komponen_biaya_support') return;
                let val = draftData[name];

                // Normalisasi array untuk persen_support (misal dari format multi-value)
                if (name === 'persen_support' && Array.isArray(val)) {
                    val = val[0] || '5';
                }

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

            // Handle Card 0 (Tipe Kontrak) Switch & Drawer Sales Support restoration
            const isSupport = (
                draftData.is_sales_support === true || draftData.is_sales_support === 'true' ||
                draftData.tipe_kontrak_selector === 'true' || draftData.tipe_kontrak_selector === true ||
                Boolean(draftData.is_support_provided)
            );

            const toggleSwitch = form.querySelector('#toggleSalesSupportSwitch');
            if (toggleSwitch) {
                toggleSwitch.checked = isSupport;
            }

            const badgeStatus = form.querySelector('#badgeSupportStatus');
            if (badgeStatus) {
                if (isSupport) {
                    badgeStatus.className = 'badge bg-primary-subtle text-primary border border-primary-subtle px-2.5 py-1.5 small fw-semibold';
                    badgeStatus.innerHTML = '<i class="bi bi-stars me-1"></i> Sales Support (13 Pasal: Pasal 4 Aktif)';
                } else {
                    badgeStatus.className = 'badge bg-light text-secondary border px-2.5 py-1.5 small fw-medium';
                    badgeStatus.innerHTML = '<i class="bi bi-shield-check me-1 text-success"></i> Standar (12 Pasal Baku)';
                }
            }

            // Restore persen_support in Card 0 if present
            const inputPersen = form.querySelector('#input_persen_support');
            if (inputPersen && draftData.persen_support !== undefined) {
                const pVal = Array.isArray(draftData.persen_support) ? draftData.persen_support[0] : draftData.persen_support;
                if (pVal !== undefined && pVal !== null && pVal !== '') {
                    inputPersen.value = pVal;
                }
            }

            // Restore komponen_biaya_support checkboxes
            if (draftData.komponen_biaya_support !== undefined && draftData.komponen_biaya_support !== null) {
                let kompItems = [];
                if (Array.isArray(draftData.komponen_biaya_support)) {
                    kompItems = draftData.komponen_biaya_support;
                } else if (typeof draftData.komponen_biaya_support === 'string' && draftData.komponen_biaya_support.trim()) {
                    try {
                        const parsed = JSON.parse(draftData.komponen_biaya_support);
                        if (Array.isArray(parsed)) kompItems = parsed;
                        else kompItems = draftData.komponen_biaya_support.split(',').map(s => s.trim());
                    } catch (e) {
                        kompItems = draftData.komponen_biaya_support.split(',').map(s => s.trim());
                    }
                }
                const kompChks = form.querySelectorAll('input[name="komponen_biaya_support_chk"]');
                kompChks.forEach(chk => {
                    chk.checked = kompItems.some(item => String(item).trim().toLowerCase() === chk.value.toLowerCase());
                });
            }

            // Sync sales support visual drawer and badges
            const drawer = form.querySelector('#kontrak-sales-support-drawer');
            if (drawer) drawer.style.display = isSupport ? 'block' : 'none';

            const hiddenIsSalesSupport = form.querySelector('input[type="hidden"][name="is_sales_support"]') || form.querySelector('input[name="is_sales_support"]');
            if (hiddenIsSalesSupport) hiddenIsSalesSupport.value = isSupport ? 'true' : 'false';

            const hiddenKompSupport = form.querySelector('input[type="hidden"][name="komponen_biaya_support"]') || form.querySelector('input[name="komponen_biaya_support"]');
            if (hiddenKompSupport) {
                const selectedKomponen = Array.from(form.querySelectorAll('input[name="komponen_biaya_support_chk"]:checked')).map(c => c.value);
                hiddenKompSupport.value = JSON.stringify(selectedKomponen);
            }

            // Update badges if cards exist
            const card1 = form.querySelector('#wizardStepPane2 .spk-clause-card:nth-of-type(2)');
            const card3 = form.querySelector('#wizardStepPane2 .spk-clause-card:nth-of-type(4)');
            const card4 = form.querySelector('#wizardStepPane2 .spk-clause-card:nth-of-type(5)');
            const card5 = form.querySelector('#wizardStepPane2 .spk-clause-card:nth-of-type(6)');
            if (card1) {
                const badge1 = card1.querySelector('.spk-clause-badge');
                if (badge1) badge1.textContent = isSupport ? 'Pasal 5' : 'Pasal 4';
            }
            if (card3) {
                const badge3 = card3.querySelector('.spk-clause-badge');
                if (badge3) badge3.textContent = isSupport ? 'Pasal 6' : 'Pasal 5';
            }
            if (card4) {
                const badge4 = card4.querySelector('.spk-clause-badge');
                if (badge4) badge4.textContent = isSupport ? 'BAB III (Pasal 8 - 11)' : 'BAB III (Pasal 7 - 10)';
            }
            if (card5) {
                const badge5 = card5.querySelector('.spk-clause-badge');
                if (badge5) badge5.textContent = isSupport ? 'BAB IV (Pasal 12 - 13)' : 'BAB IV (Pasal 11 - 12)';
            }

            hasRestoredDraft = true;
            if (typeof form._syncRekeningPerusahaan === 'function') {
                form._syncRekeningPerusahaan();
            }
            try { renderSummaryTab(form); } catch (e) {}
            try { renderSPKTab(form); } catch (e) {}
        }

        // 0. Lock Readonly Fields & Force Slate-200 Tone
        try { lockReadonlyFields(form); } catch (e) { console.error('[KontrakGridWidget] lockReadonlyFields failed:', e); }

        // 1. Setup Wizard Step Panes (Client-side view isolation)
        try { setupWizardPanes(form); } catch (e) { console.error('[KontrakGridWidget] setupWizardPanes failed:', e); }

        // 2. Setup JDE Lookup
        try { setupJDELookup(form); } catch (e) { console.error('[KontrakGridWidget] setupJDELookup failed:', e); }

        // 2b. Setup NIK & NPWP Validation
        try { setupIdentitasValidation(form); } catch (e) { console.error('[KontrakGridWidget] setupIdentitasValidation failed:', e); }

        // 2c. Setup Email Validation (Revisi Poin 16)
        try { setupEmailValidation(form); } catch (e) { console.error('[KontrakGridWidget] setupEmailValidation failed:', e); }

        // 3. Setup Durasi Calculation
        try { setupDurasiCalculation(form); } catch (e) { console.error('[KontrakGridWidget] setupDurasiCalculation failed:', e); }

        // 4. Setup Auto SPK Preview
        try { setupSPKAutoNumber(form); } catch (e) { console.error('[KontrakGridWidget] setupSPKAutoNumber failed:', e); }

        // 5. Setup Dynamic Grids
        try { setupAssetTokoGrid(form); } catch (e) { console.error('[KontrakGridWidget] setupAssetTokoGrid failed:', e); }
        try { setupMarketShareGrid(form); } catch (e) { console.error('[KontrakGridWidget] setupMarketShareGrid failed:', e); }
        try { setupTargetIncentiveGrid(form); } catch (e) { console.error('[KontrakGridWidget] setupTargetIncentiveGrid failed:', e); }
        try { setupDiscountSchemeGrid(form); } catch (e) { console.error('[KontrakGridWidget] setupDiscountSchemeGrid failed:', e); }
        try { setupTierSupportGrid(form); } catch (e) { console.error('[KontrakGridWidget] setupTierSupportGrid failed:', e); }

        // 5b. Setup Support Facility Conditional Logic (Toggle Show/Hide)
        try { setupSupportConditionalLogic(form); } catch (e) { console.error('[KontrakGridWidget] setupSupportConditionalLogic failed:', e); }

        // 5c. Setup Step 2 SPK Legal Clause Section Cards
        try { setupStep2ClauseCards(form); } catch (e) { console.error('[KontrakGridWidget] setupStep2ClauseCards failed:', e); }

        // 6. Setup Step 3 Preview & Tabs
        try { setupStep3Preview(form); } catch (e) { console.error('[KontrakGridWidget] setupStep3Preview failed:', e); }

        // 7. Setup Wizard Footer Actions & Stepper Navigation
        try { setupWizardFooter(form); } catch (e) { console.error('[KontrakGridWidget] setupWizardFooter failed:', e); }

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

            if (typeof form._validateNomorIdentitas === 'function') {
                form._validateNomorIdentitas(false);
            }
            if (typeof form._validateEmail === 'function') {
                const emVal = (form.querySelector('[name="email"]')?.value || '').trim();
                const EMAIL_RX = /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$/;
                if (emVal && EMAIL_RX.test(emVal)) {
                    form._validateEmail(false);
                }
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
                    let draftInput = form.querySelector('input[name="draft_id"]');
                    if (!draftInput) {
                        draftInput = document.createElement('input');
                        draftInput.type = 'hidden';
                        draftInput.name = 'draft_id';
                        form.appendChild(draftInput);
                    }
                    draftInput.value = serverDraftMeta.dataset.draftId;
                }
                refreshAllGridsAndHeaders();
            } else {
                // User clicked "+ Buat Pengajuan Baru": Show interactive modal prompt!
                showDraftPromptModal(form, candidateDraftData, serverDraftMeta, () => {
                    applyDraftData(candidateDraftData);
                    if (serverDraftMeta && serverDraftMeta.dataset.draftId) {
                        form.dataset.currentDraftId = serverDraftMeta.dataset.draftId;
                        let draftInput = form.querySelector('input[name="draft_id"]');
                        if (!draftInput) {
                            draftInput = document.createElement('input');
                            draftInput.type = 'hidden';
                            draftInput.name = 'draft_id';
                            form.appendChild(draftInput);
                        }
                        draftInput.value = serverDraftMeta.dataset.draftId;
                    }
                    refreshAllGridsAndHeaders();
                });
                updateAutoSaveStatus('idle');
            }
        } else {
            updateAutoSaveStatus('idle');
        }

        // 9. Setup Client-side Draft Persistence & Auto-save
        setupFormPersistence(form, hasRestoredDraft);
    }

    /* --------------------------------------------------------------------------
     * 0. Force Readonly & Slate-200 Lock
     * -------------------------------------------------------------------------- */
    function lockReadonlyFields(form) {
        const targetReadonlyFields = ['nama_toko', 'nama_pemilik', 'alamat_toko', 'no_telepon', 'kota', 'nomor_spk'];
        const cabangSelect = form.querySelector('[name="cabang"]');
        if (cabangSelect) {
            cabangSelect.classList.add('jde-readonly-locked', 'field-readonly');
            cabangSelect.style.setProperty('background-color', '#e2e8f0', 'important');
            cabangSelect.style.setProperty('cursor', 'not-allowed', 'important');
            cabangSelect.style.setProperty('pointer-events', 'none', 'important');
            cabangSelect.setAttribute('tabindex', '-1');
        }

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
        if (!form) return;
        const wrapper = form.querySelector('.form-fields-wrapper');
        if (!wrapper) {
            console.warn('[KontrakGridWidget] .form-fields-wrapper not found in form.');
            return;
        }

        // Ensure Stepper Wizard Progress Bar container exists at top of form
        let progressContainer = document.getElementById('kontrakWizardProgress') || form.querySelector('.form-progress');
        if (!progressContainer) {
            progressContainer = document.createElement('div');
            progressContainer.id = 'kontrakWizardProgress';
            progressContainer.className = 'form-progress mb-4';
            progressContainer.innerHTML = `
                <div class="d-flex align-items-center justify-content-between mb-2">
                    <span class="text-muted small fw-medium" id="stepperStepCounter">Langkah 1 dari 3</span>
                    <span class="badge bg-primary-subtle text-primary border border-primary-subtle px-2.5 py-1 small fw-semibold" id="stepperStepTitle">Informasi Toko & Partner</span>
                </div>
                <div class="progress" style="height: 8px; border-radius: 4px; background-color: #f1f5f9; overflow: hidden;">
                    <div class="progress-bar progress-bar-striped progress-bar-animated bg-primary" role="progressbar"
                         style="width: 33.33%;" id="formProgressBar">
                    </div>
                </div>
                <div class="step-indicators mt-3 d-flex justify-content-between">
                    <div class="step-indicator active" data-step="0">
                        <div class="step-number">1</div>
                        <div class="step-title">Informasi Toko & Partner</div>
                    </div>
                    <div class="step-indicator" data-step="1">
                        <div class="step-number">2</div>
                        <div class="step-title">Detail Kontrak & Klausul</div>
                    </div>
                    <div class="step-indicator" data-step="2">
                        <div class="step-number">3</div>
                        <div class="step-title">Preview SPK & Konfirmasi</div>
                    </div>
                </div>
            `;
            wrapper.parentNode.insertBefore(progressContainer, wrapper);
        }

        // Prevent double wrapping - but ensure pane1 active state
        if (wrapper.querySelector('.wizard-step-pane')) {
            const p1 = wrapper.querySelector('#wizardStepPane1, #step1Pane, .wizard-step-pane[data-step="0"]');
            if (p1) {
                p1.classList.add('active');
                p1.style.setProperty('display', 'block', 'important');
            }
            return;
        }

        const STEP1_FIELDS = new Set([
            'nomor_spk', 'cabang', 'channel', 'brand', 'perusahaan',
            'kode_customer_jde', 'nama_toko', 'nama_pemilik', 'alamat_toko',
            'no_telepon', 'email', 'kota', 'nomor_nik', 'nomor_npwp', 'jenis_identitas', 'nomor_identitas',
            'asset_toko', 'market_share'
        ]);

        const STEP2_FIELDS = new Set([
            'is_sales_support', 'komponen_biaya_support', 'persen_support',
            'info_kontrak_lama', 'tanggal_mulai', 'tanggal_berakhir', 'durasi', 'grace_period',
            'top', 'target_incentive', 'jenis_pencairan_insentif',
            'discount_scheme',
            'kota_penandatanganan', 'tanggal_penandatanganan', 'rekening_perusahaan', 'bank_perusahaan', 'nomor_rekening_perusahaan', 'atas_nama_rekening'
        ]);

        const STEP3_FIELDS = new Set([
            'preview_contract_tab',
            'chk_konfirmasi_data', 'chk_konfirmasi_preview'
        ]);

        const pane1 = document.createElement('div');
        pane1.id = 'wizardStepPane1';
        pane1.className = 'wizard-step-pane active step1Pane';
        pane1.dataset.step = '0';
        pane1.dataset.alias = 'step1Pane';
        pane1.style.setProperty('display', 'block', 'important');

        const pane2 = document.createElement('div');
        pane2.id = 'wizardStepPane2';
        pane2.className = 'wizard-step-pane step2Pane';
        pane2.dataset.step = '1';
        pane2.dataset.alias = 'step2Pane';
        pane2.style.setProperty('display', 'none', 'important');

        const pane3 = document.createElement('div');
        pane3.id = 'wizardStepPane3';
        pane3.className = 'wizard-step-pane step3Pane';
        pane3.dataset.step = '2';
        pane3.dataset.alias = 'step3Pane';
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
                    assignedPane = currentTargetPane || pane1;
                }
            }

            // Remove any inline display:none that might have been applied before partition
            if (assignedPane === pane1) {
                child.style.removeProperty('display');
                child.querySelectorAll('.field-wrapper, .fields-aligned-row, .mb-3').forEach(el => {
                    if (el.tagName !== 'INPUT') el.style.removeProperty('display');
                });
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

        // Ensure nomor_nik, nomor_npwp, email, and legacy identity fields are strictly editable
        const editableFieldNames = ['nomor_nik', 'nomor_npwp', 'email', 'jenis_identitas', 'nomor_identitas'];
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
                    if (c.nomor_nik || c.nik) {
                        setFieldValue(form, 'nomor_nik', c.nomor_nik || c.nik);
                    } else if (c.nomor_identitas || c.no_identitas) {
                        const rawId = String(c.nomor_identitas || c.no_identitas).replace(/\D/g, '');
                        if (rawId.length === 16) {
                            setFieldValue(form, 'nomor_nik', rawId);
                        } else if (rawId.length === 15) {
                            setFieldValue(form, 'nomor_npwp', rawId);
                        } else {
                            setFieldValue(form, 'nomor_nik', rawId);
                        }
                    }
                    if (c.nomor_npwp || c.npwp) {
                        setFieldValue(form, 'nomor_npwp', c.nomor_npwp || c.npwp);
                    }
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
                    if (typeof form._validateNomorNik === 'function') {
                        form._validateNomorNik(false);
                    }
                    if (typeof form._validateNomorNpwp === 'function') {
                        form._validateNomorNpwp(false);
                    }
                    if (typeof form._validateNomorIdentitas === 'function') {
                        form._validateNomorIdentitas(false);
                    }
                    if (c.email) {
                        setFieldValue(form, 'email', c.email);
                        if (typeof form._validateEmail === 'function') form._validateEmail(false);
                    }
                    // JDE lookup HANYA mengisi data toko, TIDAK BOLEH menimpa Cabang pemohon maupun nomor SPK
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
     * 1b. Setup NIK (16 digit) & NPWP Validation (Dedicated Step 1 Fields)
     * -------------------------------------------------------------------------- */
    function setupIdentitasValidation(form) {
        const nikInput = form.querySelector('[name="nomor_nik"]');
        const npwpInput = form.querySelector('[name="nomor_npwp"]');
        const legacyNomorInput = form.querySelector('[name="nomor_identitas"]');
        const legacyJenisSelect = form.querySelector('[name="jenis_identitas"]');

        function setupFieldFeedback(inputEl, className) {
            if (!inputEl) return null;
            const wrapper = inputEl.closest('.field-wrapper') || inputEl.closest('.mb-3') || inputEl.parentElement;
            let feedback = wrapper ? wrapper.querySelector(`.${className}`) : null;
            if (!feedback && wrapper) {
                feedback = document.createElement('div');
                feedback.className = `${className} mt-1 small`;
                if (inputEl.nextSibling) {
                    inputEl.parentNode.insertBefore(feedback, inputEl.nextSibling);
                } else {
                    inputEl.parentNode.appendChild(feedback);
                }
            }
            return feedback;
        }

        // --- 1. SETUP NOMOR NPWP (Wajib 15 atau 16 digit angka) ---
        let validateNomorNpwp = function (showErrorIfEmpty = false) { return true; };
        if (npwpInput) {
            npwpInput.setAttribute('inputmode', 'numeric');
            npwpInput.setAttribute('autocomplete', 'off');
            npwpInput.setAttribute('maxlength', '16');
            const npwpFeedback = setupFieldFeedback(npwpInput, 'nomor-npwp-feedback');

            // Visual Label synchronization for NPWP (Wajib *)
            const npwpWrapper = npwpInput.closest('.field-wrapper') || npwpInput.closest('.mb-3') || npwpInput.parentElement;
            if (npwpWrapper) {
                const npwpLabel = npwpWrapper.querySelector('label');
                if (npwpLabel && !npwpLabel.querySelector('.text-danger')) {
                    npwpLabel.innerHTML = 'Nomor NPWP Toko / Pemilik <span class="text-danger">*</span>';
                }
            }

            validateNomorNpwp = function (showErrorIfEmpty = false) {
                const raw = npwpInput.value || '';
                const digits = raw.replace(/\D/g, '').slice(0, 16);
                if (raw !== digits) npwpInput.value = digits;

                const val = npwpInput.value.trim();
                npwpInput.classList.remove('is-valid', 'is-invalid');
                if (npwpFeedback) {
                    npwpFeedback.className = 'nomor-npwp-feedback mt-1 small';
                    npwpFeedback.innerHTML = '';
                }

                if (!val) {
                    if (showErrorIfEmpty) {
                        npwpInput.classList.add('is-invalid');
                        if (npwpFeedback) {
                            npwpFeedback.className = 'nomor-npwp-feedback mt-1 small text-danger';
                            npwpFeedback.innerHTML = '<i class="bi bi-exclamation-circle me-1"></i> Nomor NPWP Toko / Pemilik wajib 15 atau 16 digit angka.';
                        }
                        return false;
                    }
                    return false;
                }

                if (val.length === 15 || val.length === 16) {
                    npwpInput.classList.add('is-valid');
                    if (npwpFeedback) {
                        npwpFeedback.className = 'nomor-npwp-feedback mt-1 small text-success';
                        npwpFeedback.innerHTML = `<i class="bi bi-check-circle me-1"></i> Format NPWP ${val.length} digit valid.`;
                    }
                    return true;
                } else {
                    npwpInput.classList.add('is-invalid');
                    if (npwpFeedback) {
                        npwpFeedback.className = 'nomor-npwp-feedback mt-1 small text-danger';
                        npwpFeedback.innerHTML = `<i class="bi bi-exclamation-triangle me-1"></i> NPWP harus 15 atau 16 digit angka (saat ini: ${val.length} digit).`;
                    }
                    return false;
                }
            };

            npwpInput.addEventListener('keydown', function (e) {
                const allowedKeys = ['Backspace', 'Delete', 'Tab', 'Escape', 'Enter', 'ArrowLeft', 'ArrowRight', 'Home', 'End'];
                if (allowedKeys.includes(e.key) || e.ctrlKey || e.metaKey) return;
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
            npwpInput.addEventListener('input', () => validateNomorNpwp(false));
            npwpInput.addEventListener('blur', () => validateNomorNpwp(true));
            if (npwpInput.value) validateNomorNpwp(false);
        }

        // --- 2. SETUP NOMOR NIK (Opsional, jika diisi wajib 16 digit angka) ---
        let validateNomorNik = function (showErrorIfEmpty = false) { return true; };
        if (nikInput) {
            nikInput.setAttribute('inputmode', 'numeric');
            nikInput.setAttribute('autocomplete', 'off');
            nikInput.setAttribute('maxlength', '16');
            const nikFeedback = setupFieldFeedback(nikInput, 'nomor-nik-feedback');

            // Visual Label synchronization for NIK (Opsional, remove red *)
            const nikWrapper = nikInput.closest('.field-wrapper') || nikInput.closest('.mb-3') || nikInput.parentElement;
            if (nikWrapper) {
                const nikLabel = nikWrapper.querySelector('label');
                if (nikLabel) {
                    nikLabel.innerHTML = 'Nomor NIK (KTP) <span class="text-muted small fw-normal">(Opsional)</span>';
                }
            }

            validateNomorNik = function (showErrorIfEmpty = false) {
                const raw = nikInput.value || '';
                const digits = raw.replace(/\D/g, '').slice(0, 16);
                if (raw !== digits) nikInput.value = digits;

                const val = nikInput.value.trim();
                nikInput.classList.remove('is-valid', 'is-invalid');
                if (nikFeedback) {
                    nikFeedback.className = 'nomor-nik-feedback mt-1 small';
                    nikFeedback.innerHTML = '';
                }

                if (!val) {
                    // NIK is optional, valid when empty
                    return true;
                }

                if (val.length === 16) {
                    nikInput.classList.add('is-valid');
                    if (nikFeedback) {
                        nikFeedback.className = 'nomor-nik-feedback mt-1 small text-success';
                        nikFeedback.innerHTML = '<i class="bi bi-check-circle me-1"></i> Format NIK 16 digit valid.';
                    }
                    return true;
                } else {
                    nikInput.classList.add('is-invalid');
                    if (nikFeedback) {
                        nikFeedback.className = 'nomor-nik-feedback mt-1 small text-danger';
                        nikFeedback.innerHTML = `<i class="bi bi-exclamation-triangle me-1"></i> NIK harus tepat 16 digit angka (saat ini: ${val.length} digit).`;
                    }
                    return false;
                }
            };

            nikInput.addEventListener('keydown', function (e) {
                const allowedKeys = ['Backspace', 'Delete', 'Tab', 'Escape', 'Enter', 'ArrowLeft', 'ArrowRight', 'Home', 'End'];
                if (allowedKeys.includes(e.key) || e.ctrlKey || e.metaKey) return;
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
            nikInput.addEventListener('input', () => validateNomorNik(false));
            nikInput.addEventListener('blur', () => validateNomorNik(false));
            if (nikInput.value) validateNomorNik(false);
        }

        // --- 3. LEGACY BACKWARD COMPATIBILITY (nomor_identitas fallback) ---
        if (!nikInput && legacyNomorInput) {
            legacyNomorInput.setAttribute('inputmode', 'numeric');
            legacyNomorInput.setAttribute('autocomplete', 'off');
            legacyNomorInput.setAttribute('maxlength', '16');
            const legFeedback = setupFieldFeedback(legacyNomorInput, 'nomor-identitas-feedback');

            validateNomorNik = function (showErrorIfEmpty = false) {
                const raw = legacyNomorInput.value || '';
                const digits = raw.replace(/\D/g, '').slice(0, 16);
                if (raw !== digits) legacyNomorInput.value = digits;

                const val = legacyNomorInput.value.trim();
                legacyNomorInput.classList.remove('is-valid', 'is-invalid');
                if (legFeedback) {
                    legFeedback.className = 'nomor-identitas-feedback mt-1 small';
                    legFeedback.innerHTML = '';
                }

                if (!val) {
                    if (showErrorIfEmpty) {
                        legacyNomorInput.classList.add('is-invalid');
                        if (legFeedback) {
                            legFeedback.className = 'nomor-identitas-feedback mt-1 small text-danger';
                            legFeedback.innerHTML = '<i class="bi bi-exclamation-circle me-1"></i> Nomor Identitas wajib diisi.';
                        }
                        return false;
                    }
                    return false;
                }

                if (val.length === 15 || val.length === 16) {
                    legacyNomorInput.classList.add('is-valid');
                    if (legFeedback) {
                        legFeedback.className = 'nomor-identitas-feedback mt-1 small text-success';
                        legFeedback.innerHTML = `<i class="bi bi-check-circle me-1"></i> Format identitas ${val.length} digit valid.`;
                    }
                    return true;
                } else {
                    legacyNomorInput.classList.add('is-invalid');
                    if (legFeedback) {
                        legFeedback.className = 'nomor-identitas-feedback mt-1 small text-danger';
                        legFeedback.innerHTML = `<i class="bi bi-exclamation-triangle me-1"></i> Harus 15 atau 16 digit angka (saat ini: ${val.length} digit).`;
                    }
                    return false;
                }
            };

            legacyNomorInput.addEventListener('input', () => validateNomorNik(false));
            legacyNomorInput.addEventListener('blur', () => validateNomorNik(true));
        }

        form._validateNomorNik = validateNomorNik;
        form._validateNomorNpwp = validateNomorNpwp;
        form._validateNomorIdentitas = validateNomorNik;
    }

    /* --------------------------------------------------------------------------
     * 1c. Setup Email Validation (Wajib & Format RFC) - Revisi Poin 16
     * -------------------------------------------------------------------------- */
    function setupEmailValidation(form) {
        const emailInput = form.querySelector('[name="email"]');
        if (!emailInput) return;

        // 1. Nonaktifkan validasi bubble HTML5 bawaan browser yang bertabrakan dengan layout custom
        if (form) {
            form.setAttribute('novalidate', 'novalidate');
        }
        emailInput.setAttribute('novalidate', 'novalidate');
        emailInput.setAttribute('type', 'email');
        emailInput.setAttribute('autocomplete', 'email');
        emailInput.addEventListener('invalid', function (e) {
            e.preventDefault();
        });

        // 2. Setup feedback container rapi (tepat setelah input dan sebelum .form-text / help_text)
        const wrapper = emailInput.closest('.field-wrapper') || emailInput.closest('.mb-3') || emailInput.parentElement;
        let feedback = wrapper ? (wrapper.querySelector('.email-feedback') || wrapper.querySelector('.invalid-feedback')) : null;
        if (!feedback && wrapper) {
            feedback = document.createElement('div');
            feedback.className = 'email-feedback invalid-feedback mt-1 mb-1 small';
            feedback.style.display = 'none';
            feedback.style.position = 'static';
            feedback.style.clear = 'both';

            const helpText = wrapper.querySelector('.form-text, .help-block, small');
            if (helpText && helpText.parentNode === emailInput.parentNode) {
                emailInput.parentNode.insertBefore(feedback, helpText);
            } else if (emailInput.nextSibling) {
                emailInput.parentNode.insertBefore(feedback, emailInput.nextSibling);
            } else {
                emailInput.parentNode.appendChild(feedback);
            }
        }
        if (feedback) {
            feedback.classList.add('email-feedback');
            feedback.style.position = 'static';
            feedback.style.clear = 'both';
            feedback.style.display = 'none';
        }

        // 3. Visual Label synchronization for Email (Wajib *)
        if (wrapper) {
            const emailLabel = wrapper.querySelector('label');
            if (emailLabel && !emailLabel.querySelector('.text-danger')) {
                emailLabel.innerHTML = 'Email Toko / Pemilik <span class="text-danger">*</span>';
            }
        }

        const EMAIL_REGEX = /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$/;

        const clearError = function () {
            emailInput.classList.remove('is-invalid');
            if (feedback) {
                feedback.innerHTML = '';
                feedback.style.display = 'none';
                feedback.classList.add('d-none');
            }
        };

        const validateEmail = function (showErrorIfEmpty = false) {
            const rawVal = emailInput.value || '';
            const val = rawVal.trim();
            if (rawVal !== val) {
                emailInput.value = val;
            }
            emailInput.classList.remove('is-valid', 'is-invalid');
            if (feedback) {
                feedback.innerHTML = '';
                feedback.style.display = 'none';
                feedback.classList.add('d-none');
            }

            if (!val) {
                if (showErrorIfEmpty) {
                    emailInput.classList.add('is-invalid');
                    if (feedback) {
                        feedback.className = 'invalid-feedback email-feedback mt-1 mb-1 small text-danger d-block';
                        feedback.innerHTML = '<i class="bi bi-exclamation-circle me-1"></i> Email Toko / Pemilik wajib diisi untuk korespondensi resmi kontrak.';
                        feedback.style.display = 'block';
                    }
                    return false;
                }
                return false;
            }

            const isFormatValid = EMAIL_REGEX.test(val) || (typeof emailInput.checkValidity === 'function' ? emailInput.checkValidity() : true);
            if (isFormatValid) {
                emailInput.classList.add('is-valid');
                if (feedback) {
                    feedback.className = 'valid-feedback email-feedback mt-1 mb-1 small text-success d-block';
                    feedback.innerHTML = '<i class="bi bi-check-circle me-1"></i> Format email valid.';
                    feedback.style.display = 'block';
                }
                return true;
            } else {
                emailInput.classList.add('is-invalid');
                if (feedback) {
                    feedback.className = 'invalid-feedback email-feedback mt-1 mb-1 small text-danger d-block';
                    feedback.innerHTML = '<i class="bi bi-exclamation-triangle me-1"></i> Format email tidak valid (contoh: toko@gmail.com).';
                    feedback.style.display = 'block';
                }
                return false;
            }
        };

        // 4. Saat pengguna mengetik: HANYA bersihkan status error lama, JANGAN evaluasi regex error baru
        emailInput.addEventListener('input', function () {
            if (emailInput.classList.contains('is-invalid') || (feedback && feedback.style.display !== 'none')) {
                clearError();
            }
        });

        // 5. Evaluasi format email HANYA saat kehilangan fokus (blur)
        emailInput.addEventListener('blur', function () {
            const val = (emailInput.value || '').trim();
            if (val) {
                validateEmail(false);
            } else {
                clearError();
            }
        });

        // 6. Jika sudah ada email valid dari server draf / JDE lookup, tandai is-valid halus
        if (emailInput.value && EMAIL_REGEX.test(emailInput.value.trim())) {
            emailInput.classList.add('is-valid');
        }

        form._validateEmail = validateEmail;
    }

    /* --------------------------------------------------------------------------
     * 1c. Setup Metode Pembayaran (No-Op: Static standard clause)
     * -------------------------------------------------------------------------- */
    function setupMetodePembayaran(form) {
        // Metode Pembayaran is now standardized and static in SPK contract clauses (Transfer / Cek / Giro)
    }

    /* --------------------------------------------------------------------------
     * 2. Durasi Calculation
     * -------------------------------------------------------------------------- */
    function setupDurasiCalculation(form) {
        const startInput = form.querySelector('[name="tanggal_mulai"]');
        const endInput = form.querySelector('[name="tanggal_berakhir"]');
        const durasiInput = form.querySelector('[name="durasi"]');

        if (!startInput || !endInput || !durasiInput) return;

        durasiInput.readOnly = true;
        durasiInput.classList.add('field-readonly', 'bg-light');

        function calc() {
            const startVal = startInput.value;
            const endVal = endInput.value;
            if (!startVal || !endVal) return;

            const start = new Date(startVal);
            const end = new Date(endVal);
            if (isNaN(start) || isNaN(end) || end < start) {
                durasiInput.value = '0 Bulan';
                durasiInput.dispatchEvent(new Event('change', { bubbles: true }));
                durasiInput.dispatchEvent(new Event('input', { bubbles: true }));
                return;
            }

            // Formula Selisih Bulan Kalender:
            let months = (end.getFullYear() - start.getFullYear()) * 12 + (end.getMonth() - start.getMonth());

            // Penyesuaian Hari (Inklusif Periode Kontrak):
            // - Jika tanggal awal = hari ke-1 dan tanggal akhir = akhir bulan (misal 01/01 s/d 31/12) -> +1 bulan
            // - Jika tanggal akhir >= tanggal awal (misal 01/01 s/d 31/01) -> +1 bulan
            const isStartFirstDay = (start.getDate() === 1);
            const isEndLastDay = (new Date(end.getFullYear(), end.getMonth() + 1, 0).getDate() === end.getDate());

            if (isStartFirstDay && isEndLastDay) {
                months += 1;
            } else if (end.getDate() >= start.getDate()) {
                months += 1;
            }
            const totalMonths = Math.max(1, months);
            const years = Math.floor(totalMonths / 12);
            const remMonths = totalMonths % 12;

            let result = '';
            if (years > 0 && remMonths > 0) {
                result = `${years} Tahun ${remMonths} Bulan`;
            } else if (years > 0) {
                result = `${years} Tahun`;
            } else {
                result = `${remMonths} Bulan`;
            }

            durasiInput.value = result;
            durasiInput.dispatchEvent(new Event('change', { bubbles: true }));
            durasiInput.dispatchEvent(new Event('input', { bubbles: true }));
        }

        startInput.addEventListener('change', calc);
        startInput.addEventListener('input', calc);
        endInput.addEventListener('change', calc);
        endInput.addEventListener('input', calc);
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

        let branchSeqCache = {};
        let isFetchingSeq = false;

        async function fetchBranchSequence(cabVal, brandVal) {
            const cleanCab = (cabVal || 'PUSAT').trim().toUpperCase().replace(/[^A-Z0-9]/g, '');
            if (branchSeqCache[cleanCab]) {
                return branchSeqCache[cleanCab];
            }
            if (isFetchingSeq) return null;
            isFetchingSeq = true;
            try {
                const res = await fetch(`/forms/${formSlug}/next-spk-number/?cabang=${encodeURIComponent(cleanCab)}&brand=${encodeURIComponent(brandVal || 'LADY')}`);
                if (res.ok) {
                    const data = await res.json();
                    if (data.success && data.sequence_str) {
                        branchSeqCache[cleanCab] = data.sequence_str;
                        return data.sequence_str;
                    }
                }
            } catch (err) {
                console.warn('[updateSPK] Gagal mengambil nomor urut SPK dari server:', err);
            } finally {
                isFetchingSeq = false;
            }
            return null;
        }

        function updateSPK() {
            const brandVal = (brandSelect && brandSelect.value ? brandSelect.value : '').trim();
            const cabangVal = (cabangSelect && cabangSelect.value ? cabangSelect.value : '').trim();
            const compVal = (perusahaanSelect && perusahaanSelect.value ? perusahaanSelect.value : '').trim();

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
            
            let brandCode = 'LADY';
            if (bUpper.includes('LADY')) {
                brandCode = 'LADY';
            } else if (bUpper.includes('ROYAL') || bUpper.includes('FOAM')) {
                brandCode = 'ROYAL';
            } else if (bUpper.includes('SERENITY')) {
                brandCode = 'SERENITY';
            } else if (bUpper.includes('ELITE')) {
                brandCode = 'ELITE';
            } else if (bUpper.includes('CLASSIC')) {
                brandCode = 'CLASSIC';
            } else {
                brandCode = brandVal.split(' ')[0].toUpperCase().replace(/[^A-Z0-9]/g, '') || 'LADY';
            }

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

            const ROMAN_MONTHS = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"];
            const monthRoman = ROMAN_MONTHS[month] || String(month);

            const cabClean = (cabangVal || 'PUSAT').toUpperCase().replace(/[^A-Z0-9]/g, '') || 'PUSAT';

            // Check if current spkInput already has a valid sequence (excluding default 001 if cache exists)
            let seq = branchSeqCache[cabClean] || null;
            if (!seq) {
                const match = (spkInput.value || '').match(/^(?:No\.\s*)?(\d{1,4})\//i) || (spkInput.value || '').match(/No\.\s*(\d+)/i) || (spkInput.value || '').match(/-(\d+)$/);
                if (match) {
                    const n = parseInt(match[1], 10);
                    if (n > 1) {
                        seq = String(n).padStart(3, '0');
                        branchSeqCache[cabClean] = seq;
                    }
                }
            }

            if (!seq) {
                seq = '001';
                fetchBranchSequence(cabangVal, brandVal).then(srvSeq => {
                    if (srvSeq && srvSeq !== '001') {
                        spkInput.value = `${srvSeq}/SK-${ptCode}/${cabClean}/${brandCode}/${monthRoman}/${year}`;
                        spkInput.dispatchEvent(new Event('input', { bubbles: true }));
                        spkInput.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                });
            }

            spkInput.value = `${seq}/SK-${ptCode}/${cabClean}/${brandCode}/${monthRoman}/${year}`;
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

        const kotaTtdInput = form.querySelector('[name="kota_penandatanganan"]');
        if (kotaTtdInput) {
            kotaTtdInput.readOnly = true;
            kotaTtdInput.classList.add('field-readonly', 'bg-light');
            kotaTtdInput.style.cursor = 'not-allowed';
            kotaTtdInput.setAttribute('title', 'Kota penandatanganan terisi otomatis sesuai cabang pengaju (readonly)');
            const wrapper = kotaTtdInput.closest('.field-wrapper') || kotaTtdInput.closest('.mb-3') || kotaTtdInput.parentElement;
            if (wrapper) {
                let helpText = wrapper.querySelector('.form-text');
                if (!helpText) {
                    helpText = document.createElement('div');
                    helpText.className = 'form-text text-muted small mt-1';
                    kotaTtdInput.parentNode.appendChild(helpText);
                }
                helpText.textContent = 'Terisi otomatis mengikuti cabang pengaju (readonly).';
            }
        }

        function syncKotaPenandatanganan() {
            if (!cabangSelect || !kotaTtdInput) return;
            const currentCab = (cabangSelect.value || '').trim();
            if (currentCab) {
                let targetCity = currentCab;
                if (currentCab.toLowerCase() === 'pusat') {
                    targetCity = 'Tangerang';
                }
                kotaTtdInput.value = targetCity;
                kotaTtdInput.dataset.autoFilled = 'true';
                kotaTtdInput.dispatchEvent(new Event('input', { bubbles: true }));
                kotaTtdInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
        if (cabangSelect && kotaTtdInput) {
            cabangSelect.addEventListener('change', syncKotaPenandatanganan);
            cabangSelect.addEventListener('input', syncKotaPenandatanganan);
            if (cabangSelect.value) {
                syncKotaPenandatanganan();
            }
        }

        // --- Rekening Perusahaan: Readonly & Autofill Master Profil Perusahaan ---
        function resolveCompanyBankDetails(compName, brandName) {
            const c = (compName || '').toUpperCase();
            const b = (brandName || '').toUpperCase();

            if (c.includes('PRIMATARA') || c.includes('BANGUN CIPTA') || c === 'BCP') {
                return {
                    bank_name: 'BCA Cimahi – Bandung',
                    bank_account_no: '139.9888.777 (IDR)',
                    bank_account_name: 'PT. BANGUN CIPTA PRIMATARA',
                    full_text: 'BCA Cimahi – Bandung 139.9888.777 (IDR) a/n PT. BANGUN CIPTA PRIMATARA'
                };
            }
            if (c.includes('BESTARI') || c === 'BM') {
                return {
                    bank_name: 'BCA Cimahi – Bandung',
                    bank_account_no: '139 8075 888 (IDR)',
                    bank_account_name: 'PT. BESTARI MULIA',
                    full_text: 'BCA Cimahi – Bandung 139 8075 888 (IDR) a/n PT. BESTARI MULIA'
                };
            }
            if (c.includes('CEMERLANG ABADI MULIA') || c.includes('ABADI MULIA') || c === 'CAM') {
                return {
                    bank_name: 'BCA Cimahi – Bandung',
                    bank_account_no: '139 9183 888 (IDR)',
                    bank_account_name: 'PT. CEMERLANG ABADI MULIA',
                    full_text: 'BCA Cimahi – Bandung 139 9183 888 (IDR) a/n PT. CEMERLANG ABADI MULIA'
                };
            }
            if (c.includes('ANUGRAH') || c === 'ACA' || (!c && (b.includes('LADY') || b.includes('ELITE') || b.includes('SERENITY')))) {
                return {
                    bank_name: 'BCA Cimahi – Bandung',
                    bank_account_no: '139 9183 888 (IDR)',
                    bank_account_name: 'PT. ANUGRAH CEMERLANG ABADI',
                    full_text: 'BCA Cimahi – Bandung 139 9183 888 (IDR) a/n PT. ANUGRAH CEMERLANG ABADI'
                };
            }
            // Default RAS
            return {
                bank_name: 'BCA Cimahi – Bandung',
                bank_account_no: '139 8826 999 (IDR)',
                bank_account_name: 'PT. ROYAL ABADI SEJAHTERA',
                full_text: 'BCA Cimahi – Bandung 139 8826 999 (IDR) a/n PT. ROYAL ABADI SEJAHTERA'
            };
        }

        function resolveRekeningPerusahaan(compName, brandName) {
            return resolveCompanyBankDetails(compName, brandName).full_text;
        }

        function syncRekeningPerusahaan() {
            const compVal = (perusahaanSelect && perusahaanSelect.value) ? perusahaanSelect.value.trim() : '';
            const brandVal = (brandSelect && brandSelect.value) ? brandSelect.value.trim() : '';
            const details = resolveCompanyBankDetails(compVal, brandVal);

            // 1. Sinkronisasi hidden / full string rekening_perusahaan
            form.querySelectorAll('[name="rekening_perusahaan"]').forEach(inp => {
                inp.value = details.full_text;
                inp.dataset.autoFilled = 'true';
            });

            // 2. Sinkronisasi 3 input box terpisah di Card 4 (bank_perusahaan, nomor_rekening_perusahaan, atas_nama_rekening)
            form.querySelectorAll('[name="bank_perusahaan"]').forEach(inp => {
                inp.value = details.bank_name;
                inp.title = details.bank_name;
                inp.dataset.autoFilled = 'true';
                inp.dispatchEvent(new Event('input', { bubbles: true }));
                inp.dispatchEvent(new Event('change', { bubbles: true }));
            });

            form.querySelectorAll('[name="nomor_rekening_perusahaan"]').forEach(inp => {
                inp.value = details.bank_account_no;
                inp.title = details.bank_account_no;
                inp.dataset.autoFilled = 'true';
                inp.dispatchEvent(new Event('input', { bubbles: true }));
                inp.dispatchEvent(new Event('change', { bubbles: true }));
            });

            form.querySelectorAll('[name="atas_nama_rekening"]').forEach(inp => {
                inp.value = details.bank_account_name;
                inp.title = details.bank_account_name;
                inp.dataset.autoFilled = 'true';
                inp.dispatchEvent(new Event('input', { bubbles: true }));
                inp.dispatchEvent(new Event('change', { bubbles: true }));
            });
        }
        form._syncRekeningPerusahaan = syncRekeningPerusahaan;
        form._resolveCompanyBankDetails = resolveCompanyBankDetails;

        function setSelectValue(selectEl, targetText) {
            if (!selectEl || !selectEl.options) return;
            const norm = targetText.toLowerCase().replace(/[^a-z0-9]/g, '');
            for (let i = 0; i < selectEl.options.length; i++) {
                const optText = (selectEl.options[i].text || '').toLowerCase().replace(/[^a-z0-9]/g, '');
                const optVal = (selectEl.options[i].value || '').toLowerCase().replace(/[^a-z0-9]/g, '');
                if (optText.includes(norm) || optVal.includes(norm) || norm.includes(optText) || norm.includes(optVal)) {
                    selectEl.selectedIndex = i;
                    selectEl.dispatchEvent(new Event('change', { bubbles: true }));
                    selectEl.dispatchEvent(new Event('input', { bubbles: true }));
                    break;
                }
            }
        }

        function autoSelectPerusahaanFromBrand() {
            if (!perusahaanSelect || !brandSelect) return;
            const currentComp = (perusahaanSelect.value || '').trim();
            const b = (brandSelect.value || '').toUpperCase();
            if (!currentComp || currentComp === '—') {
                if (b.includes('ROYAL') || b.includes('FOAM') || b.includes('CLASSIC')) {
                    setSelectValue(perusahaanSelect, 'PT Royal Abadi Sejahtera');
                } else if (b.includes('BESTARI')) {
                    setSelectValue(perusahaanSelect, 'PT Bestari Mulia');
                } else if (b.includes('LADY') || b.includes('ELITE') || b.includes('SERENITY')) {
                    setSelectValue(perusahaanSelect, 'PT Anugrah Cemerlang Abadi');
                }
            }
        }

        

        if (perusahaanSelect) {
            perusahaanSelect.addEventListener('change', () => {
                syncRekeningPerusahaan();
                updateSPK();
            });
            perusahaanSelect.addEventListener('input', () => {
                syncRekeningPerusahaan();
                updateSPK();
            });
        }
        if (brandSelect) {
            const onBrandChanged = () => {
                autoSelectPerusahaanFromBrand();
                syncRekeningPerusahaan();
                updateSPK();
                if (typeof form._syncDiscountSchemeWithBrand === 'function') {
                    form._syncDiscountSchemeWithBrand(brandSelect.value);
                }
            };
            brandSelect.addEventListener('change', onBrandChanged);
            brandSelect.addEventListener('input', onBrandChanged);
        }
                // Defensive check: if #companyBankContainer is missing in DOM, inject it into Card 4 immediately
        let bankContainer = document.getElementById('companyBankContainer');
        if (!bankContainer) {
            const card4Body = form.querySelector('[data-card-id="card-4"] .spk-clause-body') ||
                              form.querySelector('.card-tata-cara-pembayaran .spk-clause-body') ||
                              Array.from(form.querySelectorAll('.spk-clause-card')).find(cardEl => (cardEl.textContent || '').includes('Tata Cara'))?.querySelector('.spk-clause-body');
            if (card4Body) {
                const fallbackWrap = document.createElement('div');
                fallbackWrap.className = 'mt-1';
                fallbackWrap.innerHTML = `
                    <label class="form-label fw-semibold text-dark mb-1">Rekening Perusahaan</label>
                    <div class="row g-2" id="companyBankContainer">
                        <div class="col-12 col-md-4">
                            <label class="form-label small fw-semibold text-secondary mb-1">Nama Bank</label>
                            <input type="text" class="form-control form-control-sm bg-light" name="bank_perusahaan" readonly style="cursor: not-allowed;" placeholder="Bank">
                        </div>
                        <div class="col-12 col-md-3">
                            <label class="form-label small fw-semibold text-secondary mb-1">Nomor Rekening</label>
                            <input type="text" class="form-control form-control-sm bg-light" name="nomor_rekening_perusahaan" readonly style="cursor: not-allowed;" placeholder="No. Rekening">
                        </div>
                        <div class="col-12 col-md-5">
                            <label class="form-label small fw-semibold text-secondary mb-1">Atas Nama (A/N)</label>
                            <input type="text" class="form-control form-control-sm bg-light" name="atas_nama_rekening" readonly style="cursor: not-allowed;" placeholder="Atas Nama">
                        </div>
                    </div>
                `;
                card4Body.appendChild(fallbackWrap);
            }
        }
        syncRekeningPerusahaan();


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

            function validateTargetTierScheme(showWarning = true) {
                const curRows = getRows();
                let hasValid = false;

                if (Array.isArray(curRows)) {
                    for (let i = 0; i < curRows.length; i++) {
                        const r = curRows[i];
                        const tbRaw = String(r.target_bulanan || '').replace(/[^0-9]/g, '');
                        const tbNum = parseInt(tbRaw, 10) || 0;
                        const incNum = parseFloat(String(r.incentive_pct || '').replace(',', '.')) || 0;
                        if (tbNum > 0 && incNum > 0) {
                            hasValid = true;
                            break;
                        }
                    }
                }

                let errBox = container.querySelector('#targetTierError');
                const firstTr = container.querySelector('tbody tr');
                const firstTbInput = firstTr ? firstTr.querySelector('[data-key="target_bulanan"]') : null;
                const firstIncInput = firstTr ? firstTr.querySelector('[data-key="incentive_pct"]') : null;

                if (!hasValid) {
                    if (showWarning) {
                        if (!errBox) {
                            errBox = document.createElement('div');
                            errBox.id = 'targetTierError';
                            errBox.className = 'alert alert-danger py-2 px-3 small mt-2 d-flex align-items-center mb-0';
                            errBox.innerHTML = '<i class="bi bi-exclamation-triangle-fill me-2 fs-6"></i> <span><strong>Wajib Diisi:</strong> Wajib mengisi minimal 1 tier target penjualan bulanan dan reward insentif dengan nilai lebih dari 0.</span>';
                            container.appendChild(errBox);
                        }
                        if (firstTbInput) firstTbInput.classList.add('is-invalid');
                        if (firstIncInput) firstIncInput.classList.add('is-invalid');
                    }
                    return false;
                } else {
                    if (errBox) errBox.remove();
                    container.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
                    return true;
                }
            }
            form._validateTargetTierScheme = validateTargetTierScheme;

            // Trigger real-time re-validation if warning is active
            container.querySelectorAll('input').forEach(inp => {
                inp.addEventListener('input', () => {
                    if (container.querySelector('#targetTierError')) {
                        validateTargetTierScheme(true);
                    }
                });
            });

            container.querySelectorAll('.btn-delete-row').forEach(btn => {
                btn.addEventListener('click', () => {
                    const idx = parseInt(btn.closest('tr').dataset.index);
                    rows.splice(idx, 1);
                    saveRows(rows);
                    render();
                    if (container.querySelector('#targetTierError') || (typeof form._validateTargetTierScheme === 'function')) {
                        form._validateTargetTierScheme(true);
                    }
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
                return 'LADY (RP)';
            }
            const b = brandName.trim().toUpperCase();

            // 5 Brand Resmi SPK:
            if (b.includes('LADY')) {
                return 'LADY (RP)';
            }
            if (b.includes('ELITE')) {
                return 'ELITE (RP)';
            }
            if (b.includes('SERENITY')) {
                return 'SERENITY (RP)';
            }
            if (b.includes('ROYAL') || b.includes('FOAM')) {
                return 'ROYAL FOAM (RP)';
            }
            if (b.includes('CLASSIC')) {
                return 'CLASSIC (RP)';
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

        // Clean obsolete jenis_pajak dropdown wrapper from DOM if still present
        const oldJenisPajak = form.querySelector('[name="jenis_pajak"]');
        if (oldJenisPajak) {
            const wrap = oldJenisPajak.closest('.field-wrapper') || oldJenisPajak.closest('.mb-3') || oldJenisPajak.parentElement;
            if (wrap) wrap.style.display = 'none';
        }

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
            // Strictly enforce exclude_ppn: true on every row before JSON serialization
            if (Array.isArray(rows)) {
                rows.forEach(r => {
                    r.exclude_ppn = true;
                });
            }
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
            } else {
                rows.forEach(r => {
                    r.exclude_ppn = true;
                });
                saveRows(rows);
            }

            let html = `
                <div class="alert alert-light border border-info-subtle py-2 px-3 small mb-2 d-flex align-items-center text-muted">
                    <i class="bi bi-info-circle-fill text-info me-2 fs-6"></i>
                    <span><strong>Ketentuan Pajak Standar SPK:</strong> Seluruh tier target penjualan bulanan mengacu pada ketentuan <strong>Exclude PPN</strong>.</span>
                </div>
                <div class="table-responsive">
                    <table class="table table-bordered kontrak-grid-table" data-grid="target_incentive">
                        <thead>
                            <tr>
                                <th>Target Bulanan (Rp)</th>
                                <th style="width: 130px;" class="text-center">Exclude PPN</th>
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
                            <input type="checkbox" class="form-check-input" data-key="exclude_ppn" checked disabled style="cursor: not-allowed;" title="Standar baku kontrak SPK: Exclude PPN">
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
                rows.push({ target_bulanan: 0, exclude_ppn: true, incentive_pct: 0, keterangan: '' });
                saveRows(rows);
                render();
            });
        }

        window.renderTargetGrid = render;
        render();
    }

    // --- Grid 4: Discount Scheme (MD1, MD2, MD3 Fixed + Checkbox MTHT, MPRTO, MLCD) ---
    function setupDiscountSchemeGrid(form) {
        const field = form.querySelector('[name="discount_scheme"]');
        if (!field) return;

        field.style.display = 'none';
        const container = createGridContainer(field, 'Discount Scheme (Pasal 5 / 6)', 'Rincian komponen potongan harga reguler dan program diskon khusus.', 'discount_scheme');

        const FIXED_KOMPONEN = ['MD1', 'MD2', 'MTOP'];
        const DISC_ORDER = { 'md1': 1, 'md2': 2, 'mtop': 3, 'md3': 3, 'md4': 4, 'mthmt': 5, 'thematic': 5, 'mtht': 5, 'mprto': 6, 'mlcd': 7 };

        const BRAND_DISCOUNT_RULES = {
            'lady americana': { md1: '40%', md2: '10%',  mtop: '5%', mtop_ket: 'TOP' },
            'elite springbed': { md1: '40%', md2: '10%',  mtop: '5%', mtop_ket: 'TOP' },
            'elite':          { md1: '40%', md2: '10%',  mtop: '5%', mtop_ket: 'TOP' },
            'serenity':       { md1: '40%', md2: '5.5%', mtop: '5%', mtop_ket: 'TOP' },
            'classic':        { md1: '40%', md2: '5.5%', mtop: '5%', mtop_ket: 'TOP' },
            'royal foam':     { md1: '30%', md2: '40%',  mtop: '—',  mtop_ket: '—' },
            'royal':          { md1: '30%', md2: '40%',  mtop: '—',  mtop_ket: '—' },
        };

        function getBrandRule(brandVal) {
            const b = String(brandVal || '').trim().toLowerCase();
            if (b.includes('royal') || b.includes('foam')) return BRAND_DISCOUNT_RULES['royal foam'];
            if (b.includes('serenity')) return BRAND_DISCOUNT_RULES['serenity'];
            if (b.includes('classic')) return BRAND_DISCOUNT_RULES['classic'];
            if (b.includes('elite')) return BRAND_DISCOUNT_RULES['elite'];
            if (b.includes('lady')) return BRAND_DISCOUNT_RULES['lady americana'];
            return BRAND_DISCOUNT_RULES['lady americana'];
        }

        function getFixedRowsForBrand(brandVal) {
            const rule = getBrandRule(brandVal);
            return [
                { komponen: 'MD1', nilai: rule.md1, tipe: 'Persentase', keterangan: '—' },
                { komponen: 'MD2', nilai: rule.md2, tipe: 'Persentase', keterangan: '—' },
                { komponen: 'MTOP', nilai: rule.mtop, tipe: 'Persentase', keterangan: rule.mtop_ket }
            ];
        }

        function sortDiscountRows(rList) {
            return [...rList].sort((a, b) => {
                const oa = DISC_ORDER[String(a.komponen || '').trim().toLowerCase()] || 99;
                const ob = DISC_ORDER[String(b.komponen || '').trim().toLowerCase()] || 99;
                return oa - ob;
            });
        }

        const DYNAMIC_DISCOUNTS = {
            md4: {
                komponen: 'MD4',
                nilai: '5%',
                tipe: 'Persentase',
                keterangan: '(Special Price)',
                matches: (k) => String(k || '').trim().toUpperCase() === 'MD4'
            },
            mthmt: {
                komponen: 'MTHMT',
                nilai: '0%',
                tipe: 'Persentase',
                keterangan: 'Program Thematic Yang Berlaku',
                matches: (k) => ['thematic', 'mtht', 'mthmt'].includes(String(k || '').trim().toLowerCase())
            },
            mprto: {
                komponen: 'MPRTO',
                nilai: '5%',
                tipe: 'Persentase',
                keterangan: '(Pareto)',
                matches: (k) => String(k || '').trim().toUpperCase() === 'MPRTO'
            },
            mlcd: {
                komponen: 'MLCD',
                nilai: '5%',
                tipe: 'Persentase',
                keterangan: '(Tambahan)',
                matches: (k) => String(k || '').trim().toUpperCase() === 'MLCD'
            }
        };

        function getRows() {
            const brandVal = form.querySelector('[name="brand"]')?.value || '';
            const defaultFixed = getFixedRowsForBrand(brandVal);

            try {
                let parsed = JSON.parse(field.value || '[]');
                if (Array.isArray(parsed) && parsed.length > 0) {
                    // Normalize legacy MD3 to MTOP and Thematic to MTHMT
                    parsed = parsed.map(r => {
                        const kompUpper = String(r.komponen || '').trim().toUpperCase();
                        if (kompUpper === 'MD3') {
                            return { ...r, komponen: 'MTOP', keterangan: (r.keterangan === '—' || !r.keterangan) ? 'TOP' : r.keterangan };
                        }
                        if (['THEMATIC', 'MTHT'].includes(kompUpper)) {
                            return {
                                ...r,
                                komponen: 'MTHMT',
                                nilai: (r.nilai !== undefined && r.nilai !== null && r.nilai !== '—' && r.nilai !== '') ? r.nilai : '0%',
                                tipe: (r.tipe && r.tipe !== '—') ? r.tipe : 'Persentase',
                                keterangan: (r.keterangan && r.keterangan !== '—') ? r.keterangan : 'Program Thematic Yang Berlaku'
                            };
                        }
                        if (kompUpper === 'MTHMT') {
                            return {
                                ...r,
                                nilai: (r.nilai !== undefined && r.nilai !== null && r.nilai !== '—' && r.nilai !== '') ? r.nilai : '0%',
                                tipe: (r.tipe && r.tipe !== '—') ? r.tipe : 'Persentase',
                                keterangan: (r.keterangan && r.keterangan !== '—') ? r.keterangan : 'Program Thematic Yang Berlaku'
                            };
                        }
                        return r;
                    });
                    return sortDiscountRows(parsed);
                }
            } catch (e) {}

            return defaultFixed;
        }

        function saveRows(rows) {
            const sorted = sortDiscountRows(rows);
            field.value = JSON.stringify(sorted);
            field.dispatchEvent(new Event('change', { bubbles: true }));
        }

        function syncDiscountSchemeWithBrand(brandVal) {
            const fixedRows = getFixedRowsForBrand(brandVal);
            let currentRows = getRows();

            // Separate optional / dynamic / custom rows (anything that is NOT MD1, MD2, MTOP)
            const nonFixedRows = currentRows.filter(r => {
                const k = String(r.komponen || '').trim().toUpperCase();
                return !['MD1', 'MD2', 'MTOP', 'MD3'].includes(k);
            });

            // Combine new fixed rows with preserved non-fixed rows
            const merged = [...fixedRows, ...nonFixedRows];
            saveRows(merged);
            render();
        }

        form._syncDiscountSchemeWithBrand = syncDiscountSchemeWithBrand;

        function render() {
            let rows = getRows();
            if (!rows.length) {
                const brandVal = form.querySelector('[name="brand"]')?.value || '';
                rows = getFixedRowsForBrand(brandVal);
                saveRows(rows);
            }

            const hasMd4 = rows.some(r => DYNAMIC_DISCOUNTS.md4.matches(r.komponen));
            const hasMthmt = rows.some(r => DYNAMIC_DISCOUNTS.mthmt.matches(r.komponen));
            const hasMprto = rows.some(r => DYNAMIC_DISCOUNTS.mprto.matches(r.komponen));
            const hasMlcd = rows.some(r => DYNAMIC_DISCOUNTS.mlcd.matches(r.komponen));

            let html = `
                <div class="kontrak-discount-toggles p-3 mb-3 bg-light rounded border">
                    <div class="fw-semibold text-dark small mb-2">
                        <i class="bi bi-tags-fill text-primary me-1"></i> Program Diskon Tambahan / Khusus (Centang untuk menambahkan baris ke tabel):
                    </div>
                    <div class="d-flex flex-wrap gap-4 align-items-center">
                        <div class="form-check m-0">
                            <input class="form-check-input chk-diskon-toggle" type="checkbox" id="chk_toggle_md4" data-type="md4" ${hasMd4 ? 'checked' : ''}>
                            <label class="form-check-label small fw-medium text-dark" for="chk_toggle_md4">
                                <strong>MD4</strong> <span class="text-secondary small">(5% - Special Price)</span>
                            </label>
                        </div>
                        <div class="form-check m-0">
                            <input class="form-check-input chk-diskon-toggle" type="checkbox" id="chk_toggle_mthmt" data-type="mthmt" ${hasMthmt ? 'checked' : ''}>
                            <label class="form-check-label small fw-medium text-dark" for="chk_toggle_mthmt">
                                <strong>MTHMT</strong> <span class="text-secondary small">(Sesuai Program Thematic yang berlaku)</span>
                            </label>
                        </div>
                        <div class="form-check m-0">
                            <input class="form-check-input chk-diskon-toggle" type="checkbox" id="chk_toggle_mprto" data-type="mprto" ${hasMprto ? 'checked' : ''}>
                            <label class="form-check-label small fw-medium text-dark" for="chk_toggle_mprto">
                                <strong>MPRTO</strong> <span class="text-secondary small">(5% - Pareto)</span>
                            </label>
                        </div>
                        <div class="form-check m-0">
                            <input class="form-check-input chk-diskon-toggle" type="checkbox" id="chk_toggle_mlcd" data-type="mlcd" ${hasMlcd ? 'checked' : ''}>
                            <label class="form-check-label small fw-medium text-dark" for="chk_toggle_mlcd">
                                <strong>MLCD</strong> <span class="text-secondary small">(5% - Tambahan)</span>
                            </label>
                        </div>
                    </div>
                </div>

                <div class="table-responsive">
                    <table class="table table-bordered kontrak-grid-table align-middle" data-grid="discount_scheme" style="table-layout: fixed !important; width: 100% !important;">
                        <colgroup>
                            <col style="width: 26%;">
                            <col style="width: 18%;">
                            <col style="width: 20%;">
                            <col style="width: 28%;">
                            <col style="width: 8%;">
                        </colgroup>
                        <thead>
                            <tr class="table-light">
                                <th>Komponen</th>
                                <th class="text-center">Nilai</th>
                                <th class="text-center">Tipe</th>
                                <th>Keterangan</th>
                                <th class="text-center">Aksi</th>
                            </tr>
                        </thead>
                        <tbody>
            `;

            rows.forEach((r, idx) => {
                const kompClean = String(r.komponen || '').trim();
                const kompUpper = kompClean.toUpperCase();
                const isFixed = FIXED_KOMPONEN.some(fk => fk.toLowerCase() === kompClean.toLowerCase());
                const isMthmt = ['THEMATIC', 'MTHT', 'MTHMT'].includes(kompUpper);
                const isNominal = (r.tipe === 'Nominal');
                let displayVal = (r.nilai !== undefined && r.nilai !== null) ? r.nilai : '';
                if (isNominal) {
                    displayVal = formatRupiah(parseRupiah(r.nilai));
                }

                html += `
                    <tr data-index="${idx}">
                        <td>
                            ${isFixed ? `
                                <div class="d-flex align-items-center gap-1 w-100">
                                    <input type="text" class="cell-input border-0 bg-light text-dark fw-bold" data-key="komponen" value="${escapeHtml(r.komponen || '')}" readonly tabindex="-1" style="cursor: not-allowed; background-color: #f1f5f9 !important; width: calc(100% - 22px);" title="Komponen standar baku">
                                    <i class="bi bi-shield-lock-fill text-primary flex-shrink-0" title="Komponen standar baku terkunci" style="font-size: 0.85rem;"></i>
                                </div>
                            ` : (isMthmt ? `
                                <input type="text" class="cell-input border-0 bg-light text-dark fw-bold" data-key="komponen" value="${escapeHtml(r.komponen || 'MTHMT')}" readonly tabindex="-1" style="cursor: not-allowed; background-color: #f1f5f9 !important;" title="Komponen Thematic khusus">
                            ` : `
                                <input type="text" class="cell-input" data-key="komponen" value="${escapeHtml(r.komponen || '')}" placeholder="Komponen diskon">
                            `)}
                        </td>
                        <td>
                            ${isFixed ? `
                                <input type="text"
                                       class="cell-input text-center bg-light text-dark fw-bold border-0"
                                       data-key="nilai"
                                       data-tipe="Persentase"
                                       value="${escapeHtml(String(displayVal))}"
                                       readonly
                                       tabindex="-1"
                                       style="cursor: not-allowed; background-color: #f1f5f9 !important;"
                                       title="Nilai diskon baku terkunci">
                            ` : `
                                <input type="text"
                                       inputmode="${isNominal ? 'numeric' : 'decimal'}"
                                       class="cell-input text-center ${isNominal ? 'cell-num cell-nilai-nominal' : 'cell-nilai-persen'}"
                                       data-key="nilai"
                                       data-tipe="${isNominal ? 'Nominal' : 'Persentase'}"
                                       value="${escapeHtml(String(displayVal))}"
                                       placeholder="${isNominal ? 'Misal: 50.000' : 'Misal: 10%'}">
                            `}
                        </td>
                        <td>
                            ${isFixed ? `
                                <input type="text"
                                       class="cell-input text-center bg-light text-dark border-0"
                                       data-key="tipe"
                                       value="Persentase"
                                       readonly
                                       tabindex="-1"
                                       style="cursor: not-allowed; background-color: #f1f5f9 !important;"
                                       title="Tipe diskon baku terkunci">
                            ` : `
                                <select class="cell-input select-tipe-diskon text-center" data-key="tipe">
                                    <option value="Persentase" ${!isNominal ? 'selected' : ''}>Persentase</option>
                                    <option value="Nominal" ${isNominal ? 'selected' : ''}>Nominal</option>
                                </select>
                            `}
                        </td>
                        <td>
                            ${isFixed ? `
                                <input type="text"
                                       class="cell-input text-center bg-light text-muted border-0"
                                       data-key="keterangan"
                                       value="${escapeHtml(r.keterangan || '—')}"
                                       readonly
                                       tabindex="-1"
                                       style="cursor: not-allowed; background-color: #f1f5f9 !important;"
                                       title="Keterangan diskon baku terkunci">
                            ` : `
                                <input type="text" class="cell-input" data-key="keterangan" value="${escapeHtml(r.keterangan || (isMthmt ? 'Program Thematic Yang Berlaku' : ''))}" placeholder="Catatan syarat">
                            `}
                        </td>
                        <td class="text-center">
                            ${isFixed ? `
                                <span class="badge bg-light text-secondary border px-2 py-1 small" title="Baris standar baku"><i class="bi bi-lock-fill"></i> Baku</span>
                            ` : `
                                <button type="button" class="btn-delete-row" title="Hapus"><i class="bi bi-trash"></i></button>
                            `}
                        </td>
                    </tr>
                `;
            });

            html += `
                        </tbody>
                    </table>
                </div>
                <div class="mt-2">
                    <button type="button" class="btn-add-row"><i class="bi bi-plus-circle"></i> Tambah Discount Lain</button>
                </div>
            `;

            container.innerHTML = html;

            container.querySelectorAll('.chk-diskon-toggle').forEach(chk => {
                chk.addEventListener('change', () => {
                    const type = chk.dataset.type;
                    const def = DYNAMIC_DISCOUNTS[type];
                    if (!def) return;

                    let currentRows = getRows();
                    if (chk.checked) {
                        const exists = currentRows.some(r => def.matches(r.komponen));
                        if (!exists) {
                            currentRows.push({
                                komponen: def.komponen,
                                nilai: def.nilai,
                                tipe: def.tipe,
                                keterangan: def.keterangan
                            });
                        }
                    } else {
                        currentRows = currentRows.filter(r => !def.matches(r.komponen));
                    }
                    saveRows(currentRows);
                    render();
                });
            });

            container.querySelectorAll('tr[data-index]').forEach(tr => {
                const idx = parseInt(tr.dataset.index);
                const r = rows[idx];
                const kompClean = String(r.komponen || '').trim();
                const isFixed = FIXED_KOMPONEN.some(fk => fk.toLowerCase() === kompClean.toLowerCase());
                if (isFixed) {
                    return; // Baris fixed (MD1, MD2, MTOP) terkunci dari edit nilai/tipe
                }

                const nilaiInput = tr.querySelector('[data-key="nilai"]');
                const tipeSelect = tr.querySelector('[data-key="tipe"]');
                const komponenInput = tr.querySelector('[data-key="komponen"]');
                const ketInput = tr.querySelector('[data-key="keterangan"]');

                if (komponenInput && !komponenInput.readOnly) {
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
        window.syncDiscountSchemeWithBrand = syncDiscountSchemeWithBrand;
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

        let origToggleInput = form.querySelector('[name="is_support_provided"]');
        if (!origToggleInput) {
            origToggleInput = form.querySelector('[name="is_sales_support"]');
        }
        if (!origToggleInput) {
            origToggleInput = document.createElement('input');
            origToggleInput.type = 'hidden';
            origToggleInput.name = 'is_support_provided';
            origToggleInput.value = 'false';
            form.appendChild(origToggleInput);
        }
        // If form uses modern clause cards system, don't overwrite with legacy toggle
        if (form.querySelector('#cardSalesSupport') || form.querySelector('#toggleSalesSupportSwitch') || form.dataset.formSlug === 'permohonan-kontrak') {
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

        // Row 2: 5 Official Support Checkboxes (komponen_biaya)
        const biayaWrap = form.querySelector('#id_komponen_biaya') || form.querySelector('.field-komponen_biaya');
        let biayaBlock = null;
        if (biayaWrap) {
            const container = form.querySelector('#id_komponen_biaya');
            if (container) {
                container.className = 'd-flex flex-wrap gap-3 align-items-center mt-2 p-2.5 rounded-2 bg-light border border-slate-200';
                container.querySelectorAll(':scope > div').forEach(div => {
                    div.className = 'form-check form-check-inline mb-0 d-flex align-items-center gap-2';
                    const inp = div.querySelector('input[type="checkbox"]');
                    const lbl = div.querySelector('label');
                    if (inp) {
                        inp.className = 'form-check-input mt-0';
                        inp.style.cursor = 'pointer';
                        inp.style.width = '1.1em';
                        inp.style.height = '1.1em';
                    }
                    if (lbl) {
                        lbl.className = 'form-check-label text-dark fw-medium mb-0';
                        lbl.style.cursor = 'pointer';
                        lbl.style.fontSize = '13.5px';
                    }
                });
            }
            biayaBlock = biayaWrap.closest('.field-wrapper') || biayaWrap.closest('.mb-3') || biayaWrap.parentElement;
            if (biayaBlock) {
                biayaBlock.classList.add('w-100');
                facilityWrapper.appendChild(biayaBlock);
            }
        }

        // Row 3: Dynamic Table Tier Support Tahunan / Biaya Sewa (Pasal 7)
        const tierEl = form.querySelector('[name="tier_support"]');
        const tierBlock = tierEl ? (tierEl.closest('.field-wrapper') || tierEl.closest('.mb-3') || tierEl.parentElement) : null;
        if (tierBlock) facilityWrapper.appendChild(tierBlock);

        // Ensure all child blocks and containers inside facilityWrapper have display:none cleared
        [row1, biayaBlock, tierBlock].forEach(block => {
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
                ['support_promosi', 'pct_support_promo', 'frekuensi_pencairan'].forEach(fn => {
                    const el = form.querySelector(`[name="${fn}"]`);
                    if (el) el.value = '';
                });
                form.querySelectorAll('input[name="komponen_biaya"]').forEach(chk => {
                    chk.checked = false;
                });
                const biayaHidden = form.querySelector('input[type="hidden"][name="komponen_biaya"], input[type="text"][name="komponen_biaya"]');
                if (biayaHidden) biayaHidden.value = '';
            }
        }

        // Setup live validation for Support Tambahan fields (pct_support_promo, komponen_biaya)
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

        // 2. komponen_biaya: attach change listeners to 5 official checkboxes
        const biayaChks = form.querySelectorAll('input[name="komponen_biaya"]');
        biayaChks.forEach(chk => {
            if (!chk.dataset.validationAttached) {
                chk.dataset.validationAttached = 'true';
                chk.addEventListener('change', function () {
                    if (window.renderSPKTab) window.renderSPKTab(form);
                    if (window.renderSummaryTab) window.renderSummaryTab(form);
                });
            }
        });
    }

    /* --------------------------------------------------------------------------
     * 5c. Setup Step 2 SPK Legal Clause Section Cards
     * -------------------------------------------------------------------------- */
    function setupStep2ClauseCards(form) {
        const pane2 = form.querySelector('#wizardStepPane2');
        if (!pane2) return;
        if (pane2.querySelector('.spk-clause-card')) return; // Already partitioned

        console.log('[KontrakGridWidget] Structuring Step 2 into SPK Legal Clause Cards...');

        function createClauseCard(badgeText, badgeClass, titleText, subtitleText) {
            const card = document.createElement('div');
            card.className = 'spk-clause-card card mb-4';
            card.innerHTML = `
                <div class="spk-clause-header">
                    <div>
                        <div class="spk-clause-header-left">
                            <span class="spk-clause-badge ${badgeClass}">${badgeText}</span>
                            <h5 class="spk-clause-title">${titleText}</h5>
                        </div>
                        <p class="spk-clause-subtitle">${subtitleText}</p>
                    </div>
                </div>
                <div class="spk-clause-body"></div>
            `;
            return {
                card: card,
                body: card.querySelector('.spk-clause-body')
            };
        }

        function extractFieldElement(name) {
            const input = pane2.querySelector(`[name="${name}"]`) || form.querySelector(`[name="${name}"]`);
            if (!input) {
                const displayEl = pane2.querySelector(`.field-${name}`) || form.querySelector(`.field-${name}`);
                if (displayEl) return displayEl;
                return null;
            }
            const wrapper = input.closest(`.field-${name}`) || input.closest('.field-wrapper') || input.closest('.mb-3') || input.parentElement;
            return wrapper;
        }

        // 0. Card 0: Toggle Sales Support (Support Promosi) Switch
        const card0 = document.createElement('div');
        card0.className = 'spk-clause-card card mb-4';
        card0.id = 'cardSalesSupport';
        card0.innerHTML = `
            <div class="spk-clause-header py-3 px-3">
                <div class="d-flex align-items-center justify-content-between flex-wrap gap-2 w-100">
                    <div class="form-check form-switch mb-0 d-flex align-items-center" style="min-height: 28px;">
                        <input class="form-check-input" type="checkbox" role="switch" id="toggleSalesSupportSwitch" name="tipe_kontrak_switch" style="width: 2.7em; height: 1.4em; cursor: pointer;">
                        <label class="form-check-label fw-bold text-dark mb-0 ms-2" for="toggleSalesSupportSwitch" style="cursor: pointer; font-size: 14.5px;">
                            Sertakan Klausul Sales Support (Support Promosi)
                        </label>
                    </div>
                    <div>
                        <span class="badge bg-light text-secondary border px-2.5 py-1.5 small fw-medium" id="badgeSupportStatus">
                            <i class="bi bi-shield-check me-1 text-success"></i> Standar (12 Pasal Baku)
                        </span>
                    </div>
                </div>
                <div class="form-text text-muted mb-0 mt-1" style="font-size: 12px; margin-left: 3.8em;">
                    Aktifkan jika perjanjian mencakup kontribusi support promosi / operasional toko (otomatis menyisipkan Pasal 4).
                </div>
            </div>
            <div class="spk-clause-body" id="kontrak-sales-support-drawer" style="display: none; background: #f8fafc; border-top: 1px dashed #cbd5e1; padding: 20px 22px;">
                <!-- Baris 1: Input Persentase Support & Info Kontekstual Seimbang -->
                <div class="row align-items-center mb-3 g-3">
                    <div class="col-md-4 col-sm-6">
                        <label class="form-label fw-bold small text-dark mb-1 text-nowrap" for="input_persen_support">
                            Persentase Support (%) <span class="text-danger">*</span>
                        </label>
                        <div class="input-group input-group-sm">
                            <input type="number" class="form-control fw-semibold text-primary" name="persen_support" id="input_persen_support" value="5" min="0" max="100" step="0.5" placeholder="5">
                            <span class="input-group-text bg-white fw-bold text-muted">%</span>
                        </div>
                        <div class="form-text text-muted mt-1" style="font-size: 11px;">Nilai support promo toko (default 5%).</div>
                    </div>
                    <div class="col-md-8 col-sm-6">
                        <div class="alert alert-light border border-info-subtle text-muted small p-2 px-3 mb-0 rounded-2 d-flex align-items-center gap-2" style="background-color: #f0f9ff !important;">
                            <i class="bi bi-info-circle text-primary fs-5 flex-shrink-0"></i>
                            <div style="font-size: 11.5px; line-height: 1.4;">
                                Besaran persentase yang disepakati akan diterapkan pada klausul <strong>Pasal 4 Support Promosi</strong> dalam draf resmi SPK.
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Baris 2: Komponen Biaya Support Promosi (Selectable Chips Full-Width) -->
                <div class="pt-3 border-top">
                    <div class="d-flex align-items-center justify-content-between mb-2">
                        <label class="form-label fw-bold small text-dark mb-0">
                            Komponen Biaya Support Promosi <span class="text-danger">*</span>
                        </label>
                        <span class="text-muted small" style="font-size: 11.5px;">Klik untuk memilih komponen</span>
                    </div>
                    <div class="support-chips-wrapper" id="containerKomponenBiaya">
                        <!-- Populated by JavaScript Chips -->
                    </div>
                    <div class="form-text text-muted mt-2" style="font-size: 11px;">
                        Pilih satu atau lebih komponen biaya operasional/promosi yang dicover Pihak Pertama (misal: Sewa, Listrik, Instore, dll).
                    </div>
                </div>
            </div>
        `;

        // Populate 6 official components as Modern Selectable Chips
        const containerKomponen = card0.querySelector('#containerKomponenBiaya');
        const OFFICIAL_KOMPONEN = ['Sewa', 'Listrik', 'Instore', 'Pameran', 'Pajak Billboard', 'Asuransi'];
        OFFICIAL_KOMPONEN.forEach(komp => {
            const safeId = 'chk_biaya_' + komp.toLowerCase().replace(/\s+/g, '_');
            const chipItem = document.createElement('div');
            chipItem.className = 'support-chip-item';
            chipItem.innerHTML = `
                <input class="btn-check support-chip-input" type="checkbox" name="komponen_biaya_support_chk" value="${komp}" id="${safeId}" autocomplete="off">
                <label class="support-chip-label" for="${safeId}">
                    <i class="bi bi-plus-lg chip-icon-add me-1.5"></i>
                    <i class="bi bi-check2 chip-icon-check me-1.5 d-none"></i>
                    <span>${komp}</span>
                </label>
            `;
            containerKomponen.appendChild(chipItem);
        });

        // Ensure real hidden input is_sales_support exists
        let hiddenIsSalesSupport = form.querySelector('input[type="hidden"][name="is_sales_support"]');
        if (!hiddenIsSalesSupport) {
            hiddenIsSalesSupport = document.createElement('input');
            hiddenIsSalesSupport.type = 'hidden';
            hiddenIsSalesSupport.name = 'is_sales_support';
            form.appendChild(hiddenIsSalesSupport);
        }
        hiddenIsSalesSupport.value = 'false';

        // Ensure real hidden input is_support_provided exists
        let hiddenIsSupportProvided = form.querySelector('input[name="is_support_provided"]');
        if (!hiddenIsSupportProvided) {
            hiddenIsSupportProvided = document.createElement('input');
            hiddenIsSupportProvided.type = 'hidden';
            hiddenIsSupportProvided.name = 'is_support_provided';
            form.appendChild(hiddenIsSupportProvided);
        }
        hiddenIsSupportProvided.value = 'false';

        // Ensure real hidden input persen_support exists
        let hiddenPersenSupport = form.querySelector('input[type="hidden"][name="persen_support"]');
        if (!hiddenPersenSupport) {
            hiddenPersenSupport = document.createElement('input');
            hiddenPersenSupport.type = 'hidden';
            hiddenPersenSupport.name = 'persen_support';
            form.appendChild(hiddenPersenSupport);
        }
        hiddenPersenSupport.value = '0';

        // Ensure real hidden input komponen_biaya_support exists
        let hiddenKompSupport = form.querySelector('input[type="hidden"][name="komponen_biaya_support"]');
        if (!hiddenKompSupport) {
            hiddenKompSupport = document.createElement('input');
            hiddenKompSupport.type = 'hidden';
            hiddenKompSupport.name = 'komponen_biaya_support';
            form.appendChild(hiddenKompSupport);
        }

        // 1. Card 1: Periode & Masa Berlaku Kontrak (Pasal 4 / 5)
        const card1 = createClauseCard('Pasal 4', '', 'Periode & Masa Berlaku Kontrak', 'Masa berlaku perjanjian kerjasama dan tenggang waktu pemenuhan target.');
        
        const infoBlock = extractFieldElement('info_kontrak_lama');
        if (infoBlock) card1.body.appendChild(infoBlock);

        // Default Grace Period if empty
        const graceInput = form.querySelector('[name="grace_period"]');
        if (graceInput && !graceInput.value.trim()) {
            graceInput.value = '1 Bulan';
        }

        const rowDates = document.createElement('div');
        rowDates.className = 'row g-3 mb-2';
        ['tanggal_mulai', 'tanggal_berakhir', 'durasi', 'grace_period'].forEach(fn => {
            const el = extractFieldElement(fn);
            if (el) {
                const col = document.createElement('div');
                col.className = 'col-md-6 col-12';
                el.classList.remove('col-md-3', 'col-md-4', 'col-md-6', 'col-md-12');
                col.appendChild(el);
                rowDates.appendChild(col);
            }
        });
        card1.body.appendChild(rowDates);

        // 2. Card 2: Target Penjualan & Skema Insentif (Pasal 3)
        const card2 = createClauseCard('Pasal 3', '', 'Target Penjualan & Skema Insentif', 'Komitmen volume penjualan bulanan toko dan skema reward insentif.');
        
        const colPajakInfo = document.createElement('div');
        colPajakInfo.className = 'mb-3';
        colPajakInfo.innerHTML = `
            <div class="alert alert-light border border-info-subtle text-muted small p-2.5 mb-0 rounded-2 d-flex align-items-center gap-2">
                <i class="bi bi-info-circle text-info fs-5 flex-shrink-0"></i>
                <div>Target volume penjualan bulanan dan skema reward insentif toko dibakukan dengan ketentuan <strong>Exclude PPN</strong> sesuai price list resmi yang berlaku.</div>
            </div>
        `;
        card2.body.appendChild(colPajakInfo);

        const targetGridBlock = pane2.querySelector('.kontrak-target-incentive-wrapper') || extractFieldElement('target_incentive');
        if (targetGridBlock) card2.body.appendChild(targetGridBlock);

        // Field Jenis Pencairan Insentif (Poin 7)
        const rowPencairan = document.createElement('div');
        rowPencairan.className = 'row g-3 mt-1 mb-2';
        const pencairanEl = extractFieldElement('jenis_pencairan_insentif');
        if (pencairanEl) {
            const col = document.createElement('div');
            col.className = 'col-12 col-md-12';
            pencairanEl.classList.remove('col-md-3', 'col-md-4', 'col-md-6', 'col-md-12');
            col.appendChild(pencairanEl);
            rowPencairan.appendChild(col);
            card2.body.appendChild(rowPencairan);
        }

        // 3. Card 3: Skema Diskon Produk (Pasal 5 / 6)
        const card3 = createClauseCard('Pasal 5 / 6', '', 'Skema Diskon Produk', 'Rincian komponen potongan harga penjualan produk toko.');

        // Remove any obsolete legacy discount checkbox wrappers completely from DOM
        pane2.querySelectorAll('[name^="chk_diskon_"], [class*="field-chk_diskon"]').forEach(el => {
            const wrapper = el.closest('.field-wrapper') || el.closest('.mb-3') || el.closest('.row');
            if (wrapper && !wrapper.classList.contains('spk-clause-card')) {
                wrapper.remove();
            } else {
                el.remove();
            }
        });

        const discountGridBlock = pane2.querySelector('.kontrak-discount-scheme-wrapper') || extractFieldElement('discount_scheme');
        if (discountGridBlock) card3.body.appendChild(discountGridBlock);

        // 4. Card 4: Tata Cara & Ketentuan Pembayaran (BAB III - Pasal 7, 8, 9, 10)
        const card4 = createClauseCard('BAB III', 'badge-bab3', 'Tata Cara & Ketentuan Pembayaran (Pasal 7, 8, 9, 10)', '');
        card4.card.dataset.cardId = 'card-4';
        card4.card.classList.add('card-tata-cara-pembayaran');
        
        const rowBayar = document.createElement('div');
        rowBayar.className = 'row g-3 mb-2 align-items-start';

        // 1. TOP (Term of Payment) - Flex cerdas & sejajar sempurna dengan Rekening Perusahaan
        const elTop = extractFieldElement('top');
        if (elTop) {
            const colTop = document.createElement('div');
            colTop.className = 'col-12 col-md-3';
            colTop.style.cssText = 'min-width: 180px; max-width: 240px;';
            elTop.classList.remove('col-md-3', 'col-md-4', 'col-md-6', 'col-md-12');

            // Header Utama Level 1: sejajar dengan "Rekening Perusahaan"
            const topHeader = document.createElement('div');
            topHeader.className = 'form-label fw-semibold text-dark mb-1 text-nowrap';
            topHeader.innerHTML = 'TOP (Term of Payment) <span class="text-danger">*</span>';

            // Sub-label Level 2: sejajar dengan "Nama Bank", "Nomor Rekening", "Atas Nama (A/N)"
            let topLabel = elTop.querySelector('label');
            if (topLabel) {
                topLabel.className = 'form-label small fw-semibold text-secondary mb-1 text-nowrap';
                topLabel.textContent = 'Hari Kerja';
            } else {
                topLabel = document.createElement('label');
                topLabel.className = 'form-label small fw-semibold text-secondary mb-1 text-nowrap';
                topLabel.textContent = 'Hari Kerja';
                elTop.prepend(topLabel);
            }

            // Input Level 3: selebar 100% kolom (tanpa batas 160px) & placeholder ringkas "60"
            const topInput = elTop.querySelector('input');
            if (topInput) {
                topInput.classList.add('form-control-sm', 'w-100');
                topInput.placeholder = '60';
                topInput.style.removeProperty('max-width');
                topInput.style.width = '100%';
            }

            // Hapus helper text bawah agar bersih & tidak duplikat dengan sub-label
            const topHelp = elTop.querySelector('.form-text');
            if (topHelp) topHelp.remove();

            colTop.appendChild(topHeader);
            colTop.appendChild(elTop);
            rowBayar.appendChild(colTop);
        }

        // 2. Rekening Perusahaan - mengisi seluruh sisa ruang (col-12 col-md-9 flex-grow-1)
        const colRek = document.createElement('div');
        colRek.className = 'col-12 col-md-9 flex-grow-1';

        // Pastikan input hidden untuk rekening_perusahaan ada di form untuk payload backend
        let hiddenRek = form.querySelector('input[type="hidden"][name="rekening_perusahaan"]');
        if (!hiddenRek) {
            hiddenRek = document.createElement('input');
            hiddenRek.type = 'hidden';
            hiddenRek.name = 'rekening_perusahaan';
            form.appendChild(hiddenRek);
        }

        // HAPUS total wrapper Django untuk rekening_perusahaan dan 3 field bank dari DOM agar label Django tidak pernah muncul ganda
        ['rekening_perusahaan', 'bank_perusahaan', 'nomor_rekening_perusahaan', 'atas_nama_rekening'].forEach(fName => {
            const el = extractFieldElement(fName);
            if (el && !el.closest('#companyBankContainer')) {
                const inp = el.querySelector(`input[name="${fName}"]`);
                if (inp && fName === 'rekening_perusahaan' && inp !== hiddenRek) {
                    inp.type = 'hidden';
                    form.appendChild(inp);
                }
                el.remove();
            }
        });

        // Satu label utama tunggal yang bersih: "Rekening Perusahaan"
        // Proporsi kolom: Bank (4), No. Rekening (3), Atas Nama (5) untuk memberi ruang maksimal pada nama PT panjang
        const bankBlock = document.createElement('div');
        bankBlock.className = 'mb-1';
        bankBlock.innerHTML = `
            <label class="form-label fw-semibold text-dark mb-1">Rekening Perusahaan</label>
            <div class="row g-2" id="companyBankContainer">
                <div class="col-12 col-md-4">
                    <label class="form-label small fw-semibold text-secondary mb-1">Nama Bank</label>
                    <input type="text" class="form-control form-control-sm bg-light" name="bank_perusahaan" readonly style="cursor: not-allowed;" placeholder="Bank" title="">
                </div>
                <div class="col-12 col-md-3">
                    <label class="form-label small fw-semibold text-secondary mb-1">Nomor Rekening</label>
                    <input type="text" class="form-control form-control-sm bg-light" name="nomor_rekening_perusahaan" readonly style="cursor: not-allowed;" placeholder="No. Rekening" title="">
                </div>
                <div class="col-12 col-md-5">
                    <label class="form-label small fw-semibold text-secondary mb-1">Atas Nama (A/N)</label>
                    <input type="text" class="form-control form-control-sm bg-light" name="atas_nama_rekening" readonly style="cursor: not-allowed;" placeholder="Atas Nama" title="">
                </div>
            </div>
        `;
        colRek.appendChild(bankBlock);
        rowBayar.appendChild(colRek);
        card4.body.appendChild(rowBayar);

        // 5. Card 5: Ketentuan Akhir & Tempat Pengesahan (BAB IV & Penutup)
        const card5 = createClauseCard('BAB IV & Penutup', 'badge-bab4', 'Ketentuan Akhir & Tempat Pengesahan', 'Lokasi dan tanggal resmi pengesahan Surat Perjanjian Kerjasama (SPK).');
        
        const rowTtd = document.createElement('div');
        rowTtd.className = 'row g-3 mb-2';
        ['kota_penandatanganan', 'tanggal_penandatanganan'].forEach(fn => {
            const el = extractFieldElement(fn);
            if (el) {
                const col = document.createElement('div');
                col.className = 'col-md-6';
                el.classList.remove('col-md-3', 'col-md-4', 'col-md-6', 'col-md-12');
                col.appendChild(el);
                rowTtd.appendChild(col);
            }
        });
        card5.body.appendChild(rowTtd);

        function updateClauseCardBadges(isSupport) {
            const badge1 = card1.card.querySelector('.spk-clause-badge');
            const badge3 = card3.card.querySelector('.spk-clause-badge');
            const badge4 = card4.card.querySelector('.spk-clause-badge');
            const badge5 = card5.card.querySelector('.spk-clause-badge');

            if (isSupport) {
                if (badge1) badge1.textContent = 'Pasal 5';
                if (badge3) badge3.textContent = 'Pasal 6';
                if (badge4) badge4.textContent = 'BAB III (Pasal 8 - 11)';
                if (badge5) badge5.textContent = 'BAB IV (Pasal 12 - 13)';
            } else {
                if (badge1) badge1.textContent = 'Pasal 4';
                if (badge3) badge3.textContent = 'Pasal 5';
                if (badge4) badge4.textContent = 'BAB III (Pasal 7 - 10)';
                if (badge5) badge5.textContent = 'BAB IV (Pasal 11 - 12)';
            }
        }

        function syncSalesSupportState() {
            const toggleSwitch = card0.querySelector('#toggleSalesSupportSwitch');
            const isSupport = Boolean(toggleSwitch && toggleSwitch.checked);
            const drawer = card0.querySelector('#kontrak-sales-support-drawer');
            if (drawer) drawer.style.display = isSupport ? 'block' : 'none';

            hiddenIsSalesSupport.value = isSupport ? 'true' : 'false';
            if (hiddenIsSupportProvided) {
                hiddenIsSupportProvided.value = isSupport ? 'true' : 'false';
                hiddenIsSupportProvided.checked = isSupport;
            }

            const inputPersen = card0.querySelector('#input_persen_support');
            if (hiddenPersenSupport) {
                if (isSupport) {
                    hiddenPersenSupport.value = (inputPersen && inputPersen.value) ? inputPersen.value : '5';
                    if (inputPersen && !inputPersen.value) inputPersen.value = '5';
                } else {
                    hiddenPersenSupport.value = '0';
                }
            }

            const badgeStatus = card0.querySelector('#badgeSupportStatus');
            if (badgeStatus) {
                if (isSupport) {
                    badgeStatus.className = 'badge bg-primary-subtle text-primary border border-primary-subtle px-2.5 py-1.5 small fw-semibold';
                    badgeStatus.innerHTML = '<i class="bi bi-stars me-1"></i> Sales Support (13 Pasal: Pasal 4 Aktif)';
                } else {
                    badgeStatus.className = 'badge bg-light text-secondary border px-2.5 py-1.5 small fw-medium';
                    badgeStatus.innerHTML = '<i class="bi bi-shield-check me-1 text-success"></i> Standar (12 Pasal Baku)';
                }
            }
            
            // Backward compatibility toggle
            const legacyToggle = form.querySelector('input[name="is_support_provided"]');
            if (legacyToggle) {
                legacyToggle.checked = isSupport;
                legacyToggle.value = isSupport ? 'true' : 'false';
            }

            const selectedKomponen = Array.from(card0.querySelectorAll('.support-chip-input:checked, input[name="komponen_biaya_support_chk"]:checked')).map(c => c.value);
            hiddenKompSupport.value = JSON.stringify(selectedKomponen);

            // Synchronize frontend required attributes to prevent blocking submit when OFF
            if (!isSupport) {
                if (inputPersen) {
                    inputPersen.removeAttribute('required');
                    inputPersen.setCustomValidity?.('');
                }
                if (hiddenPersenSupport) hiddenPersenSupport.removeAttribute('required');
                if (hiddenKompSupport) hiddenKompSupport.removeAttribute('required');
            }

            updateClauseCardBadges(isSupport);

            if (typeof window.fetchAndRenderPdf === 'function') {
                window.fetchAndRenderPdf(true);
            }
            if (typeof window.renderSummaryTab === 'function') {
                window.renderSummaryTab(form);
            }
        }
        window.syncSalesSupportState = syncSalesSupportState;

        const mainSwitch = card0.querySelector('#toggleSalesSupportSwitch');
        if (mainSwitch) {
            mainSwitch.addEventListener('change', syncSalesSupportState);
        }

        card0.querySelectorAll('input[name="komponen_biaya_support_chk"]').forEach(chk => {
            chk.addEventListener('change', syncSalesSupportState);
        });

        const inputPersen = card0.querySelector('#input_persen_support');
        if (inputPersen) {
            inputPersen.addEventListener('input', () => {
                if (typeof window.fetchAndRenderPdf === 'function') {
                    window.fetchAndRenderPdf(true);
                }
            });
        }

        // Initial default state (Standar 12 Pasal)
        updateClauseCardBadges(false);

        // Append cards to pane2
        pane2.appendChild(card0);
        pane2.appendChild(card1.card);
        pane2.appendChild(card2.card);
        pane2.appendChild(card3.card);
        pane2.appendChild(card4.card);
        pane2.appendChild(card5.card);

        // Remove leftover unpartitioned elements/wrappers from pane2 so Card 0 is the immediate first child
        Array.from(pane2.children).forEach(child => {
            if (!child.classList.contains('spk-clause-card') && child.tagName !== 'SCRIPT') {
                child.remove();
            }
        });

        console.log('[KontrakGridWidget] Step 2 successfully structured into Tipe Kontrak selector + 5 SPK Legal Clause Cards.');
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

    function formatIndonesianDate(dateStr) {
        if (!dateStr || dateStr === '—' || dateStr === '-' || dateStr === 'None' || dateStr === 'null' || dateStr === 'undefined') return '—';
        const s = String(dateStr).trim();
        const months = [
            'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
            'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
        ];

        // 1. Check ISO format YYYY-MM-DD
        const mIso = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
        if (mIso) {
            const y = mIso[1];
            const m = parseInt(mIso[2], 10);
            const d = String(parseInt(mIso[3], 10)).padStart(2, '0');
            if (m >= 1 && m <= 12) {
                return `${d} ${months[m - 1]} ${y}`;
            }
        }

        // 2. Check Slash format DD/MM/YYYY or D/M/YYYY
        const mSlash = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
        if (mSlash) {
            const d = String(parseInt(mSlash[1], 10)).padStart(2, '0');
            const m = parseInt(mSlash[2], 10);
            const y = mSlash[3];
            if (m >= 1 && m <= 12) {
                return `${d} ${months[m - 1]} ${y}`;
            }
        }

        // 3. Check Dash format DD-MM-YYYY or D-M-YYYY
        const mDash = s.match(/^(\d{1,2})-(\d{1,2})-(\d{4})/);
        if (mDash) {
            const d = String(parseInt(mDash[1], 10)).padStart(2, '0');
            const m = parseInt(mDash[2], 10);
            const y = mDash[3];
            if (m >= 1 && m <= 12) {
                return `${d} ${months[m - 1]} ${y}`;
            }
        }

        // 4. Check Text format: e.g. "1 November 2026" or "01 November 2026"
        const mText = s.match(/^(\d{1,2})\s+([a-zA-Z]+)\s+(\d{4})$/);
        if (mText) {
            const d = String(parseInt(mText[1], 10)).padStart(2, '0');
            const monthInput = mText[2].toLowerCase();
            const y = mText[3];
            const enIdMap = {
                'january': 0, 'jan': 0, 'januari': 0,
                'february': 1, 'feb': 1, 'februari': 1,
                'march': 2, 'mar': 2, 'maret': 2,
                'april': 3, 'apr': 3,
                'may': 4, 'mei': 4,
                'june': 5, 'jun': 5, 'juni': 5,
                'july': 6, 'jul': 6, 'juli': 6,
                'august': 7, 'aug': 7, 'agustus': 7,
                'september': 8, 'sep': 8,
                'october': 9, 'oct': 9, 'oktober': 9,
                'november': 10, 'nov': 10,
                'december': 11, 'dec': 11, 'desember': 11
            };
            if (enIdMap[monthInput] !== undefined) {
                return `${d} ${months[enIdMap[monthInput]]} ${y}`;
            }
        }

        return s;
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
                <div class="small text-muted">Brand, Cabang & Channel</div>
                <div class="fw-medium">${getV('brand') || '-'} / ${getV('cabang') || '-'} / ${getV('channel') || '-'}</div>
            </div>
            <div class="col-md-4">
                <div class="small text-muted">Pemilik / Pihak Kedua</div>
                <div class="fw-medium">${getV('nama_pemilik') || '-'}</div>
            </div>
            <div class="col-md-4">
                <div class="small text-muted">Kota & Kontak</div>
                <div class="fw-medium">${getV('kota') || '-'} (${getV('no_telepon') || '-'})</div>
                <div class="text-muted small font-monospace">${getV('email') || ''}</div>
            </div>
            <div class="col-md-4">
                <div class="small text-muted">Periode Kontrak</div>
                <div class="fw-medium">${formatIndonesianDate(getV('tanggal_mulai'))} s/d ${formatIndonesianDate(getV('tanggal_berakhir'))} (${getV('durasi') || '-'})</div>
            </div>
            <div class="col-md-4">
                <div class="small text-muted">Pencairan Insentif</div>
                <div class="fw-medium">${getV('jenis_pencairan_insentif') || 'Transfer/Giro'}</div>
            </div>
            <div class="col-md-4">
                <div class="small text-muted">Jangka Waktu Pembayaran (TOP)</div>
                <div class="fw-medium">${getV('top') || '-'} Hari setelah tanggal pengiriman</div>
            </div>
            <div class="col-md-4">
                <div class="small text-muted">Ketentuan Pajak</div>
                <div class="fw-medium">Exclude PPN</div>
            </div>
        `;
    }

    function renderSPKTab(form) {
        const container = document.getElementById('spkDocumentPreview');
        if (!container) return;

        try {
            // Setup modern PDF viewer container if not already initialized
            let toolbar = container.querySelector('.spk-pdf-toolbar');
            let loadingEl = container.querySelector('#spkPdfLoading');
            let viewerFrame = container.querySelector('#spkPdfViewerFrame');
            let errorEl = container.querySelector('#spkPdfError');

            if (!toolbar) {
                container.innerHTML = `
                    <div class="spk-pdf-preview-wrapper w-100" style="max-width: 1000px; margin: 0 auto;">
                        <div class="spk-pdf-toolbar d-flex flex-wrap justify-content-between align-items-center mb-3 p-2.5 px-3 bg-light border rounded-3 w-100 gap-2">
                            <!-- Sisi Kiri: Info Dokumen Bersih -->
                            <div class="spk-pdf-toolbar-left d-flex align-items-center gap-2">
                                <i class="bi bi-file-earmark-pdf text-danger fs-5"></i>
                                <span class="fw-semibold text-dark" style="font-size: 13.5px;">Pratinjau Surat Perjanjian Kerjasama (SPK)</span>
                                <span class="badge bg-secondary-subtle text-secondary-emphasis border px-2 py-1 ms-1 d-none" id="spkPageBadge" style="font-size: 11.5px; font-weight: 500;">
                                    2 Halaman
                                </span>
                            </div>
                            <!-- Sisi Kanan: Grup Tombol Aksi Compact -->
                            <div class="spk-pdf-toolbar-right d-flex align-items-center gap-2 ms-md-auto">
                                <button type="button" class="btn btn-sm btn-outline-secondary" id="btnRefreshPdfPreview" title="Muat ulang pratinjau data formulir">
                                    <i class="bi bi-arrow-clockwise me-1"></i>Perbarui
                                </button>
                                <a href="#" target="_blank" class="btn btn-sm btn-outline-secondary disabled" id="btnOpenPdfNewTab" title="Buka pratinjau di tab baru">
                                    <i class="bi bi-box-arrow-up-right me-1"></i>Buka Tab Baru
                                </a>
                                <a href="#" download="SPK-Draft.pdf" class="btn btn-sm btn-primary disabled" id="btnDownloadDraftPdf" title="Unduh berkas PDF">
                                    <i class="bi bi-download me-1"></i>Unduh PDF
                                </a>
                            </div>
                        </div>
                        <div id="spkPdfLoading" class="text-center py-5 bg-light rounded-3 border my-2" style="min-height: 480px; display: flex; flex-direction: column; justify-content: center; align-items: center;">
                            <div class="spinner-border text-primary mb-3" style="width: 2.2rem; height: 2.2rem;" role="status"></div>
                            <h6 class="fw-semibold text-dark mb-1">Menyiapkan Dokumen PDF SPK...</h6>
                            <p class="small text-muted mb-0">Sedang memuat pratinjau dokumen resmi</p>
                        </div>
                        <div id="spkPdfError" class="alert alert-warning my-3 p-3 d-none">
                            <div class="d-flex align-items-center mb-1">
                                <i class="bi bi-exclamation-triangle-fill fs-5 me-2 text-warning"></i>
                                <strong class="text-dark">Gagal Memuat Pratinjau PDF</strong>
                            </div>
                            <div class="small text-muted mb-2" id="spkPdfErrorMessage"></div>
                            <button type="button" class="btn btn-sm btn-outline-warning" id="btnRetryPdfPreview">Coba Lagi</button>
                        </div>
                        <iframe id="spkPdfViewerFrame" style="width: 100%; height: 920px; border: 1px solid #cbd5e1; border-radius: 8px; display: none; background: #525659;" title="Pratinjau Dokumen SPK"></iframe>
                    </div>
                `;
                toolbar = container.querySelector('.spk-pdf-toolbar');
                loadingEl = container.querySelector('#spkPdfLoading');
                viewerFrame = container.querySelector('#spkPdfViewerFrame');
                errorEl = container.querySelector('#spkPdfError');

                const btnRefresh = container.querySelector('#btnRefreshPdfPreview');
                const btnRetry = container.querySelector('#btnRetryPdfPreview');
                if (btnRefresh) btnRefresh.addEventListener('click', () => fetchAndRenderPdf(true));
                if (btnRetry) btnRetry.addEventListener('click', () => fetchAndRenderPdf(true));
            }

            function fetchAndRenderPdf(force) {
                if (!form) return;
                const btnOpen = container.querySelector('#btnOpenPdfNewTab');
                const btnDownload = container.querySelector('#btnDownloadDraftPdf');
                const pageBadge = container.querySelector('#spkPageBadge');
                const errorMsg = container.querySelector('#spkPdfErrorMessage');

                // Show loading spinner
                if (loadingEl) loadingEl.style.display = 'flex';
                if (errorEl) errorEl.classList.add('d-none');
                if (viewerFrame) viewerFrame.style.display = 'none';

                const formSlug = (() => {
                    const match = window.location.pathname.match(/\/forms\/([^\/]+)/);
                    return match ? match[1] : 'permohonan-kontrak';
                })();
                const previewPdfUrl = `/forms/${formSlug}/preview-pdf/`;

                // Build FormData from current form inputs
                const fd = new FormData(form);

                // CSRF Token
                const tokenInput = form.querySelector('[name="csrfmiddlewaretoken"]');
                let csrfToken = tokenInput ? tokenInput.value : '';
                if (!csrfToken) {
                    csrfToken = document.cookie
                        .split('; ')
                        .find(row => row.startsWith('csrftoken='))
                        ?.split('=')[1] || '';
                }

                fetch(previewPdfUrl, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken,
                    },
                    body: fd,
                })
                .then(resp => {
                    if (!resp.ok) {
                        return resp.text().then(t => { throw new Error(t || `HTTP error ${resp.status}`); });
                    }
                    const totalPages = resp.headers.get('X-Page-Count');
                    if (pageBadge) {
                        pageBadge.textContent = `${totalPages || 2} Halaman`;
                        pageBadge.classList.remove('d-none');
                    }

                    // Extract filename from header
                    let filename = 'SPK-Preview.pdf';
                    const disp = resp.headers.get('Content-Disposition');
                    if (disp && disp.includes('filename=')) {
                        const m = disp.match(/filename="?([^"]+)"?/);
                        if (m && m[1]) filename = m[1];
                    }
                    return resp.blob().then(blob => ({ blob, filename }));
                })
                .then(({ blob, filename }) => {
                    if (container._activeBlobUrl) {
                        URL.revokeObjectURL(container._activeBlobUrl);
                    }
                    const blobUrl = URL.createObjectURL(blob);
                    container._activeBlobUrl = blobUrl;

                    if (viewerFrame) {
                        viewerFrame.src = blobUrl + '#toolbar=0&navpanes=0';
                        viewerFrame.style.display = 'block';
                    }
                    if (loadingEl) loadingEl.style.display = 'none';

                    if (btnOpen) {
                        btnOpen.href = blobUrl;
                        btnOpen.classList.remove('disabled');
                    }
                    if (btnDownload) {
                        btnDownload.href = blobUrl;
                        btnDownload.download = filename;
                        btnDownload.classList.remove('disabled');
                    }
                })
                .catch(err => {
                    console.error('Error fetching preview PDF:', err);
                    if (loadingEl) loadingEl.style.display = 'none';
                    if (errorEl) {
                        errorEl.classList.remove('d-none');
                        if (errorMsg) errorMsg.textContent = err.message || String(err);
                    }
                });
            }

            // Expose globally so external triggers (like Tipe Kontrak toggle) can re-fetch
            window.fetchAndRenderPdf = fetchAndRenderPdf;

            // Execute PDF preview loading
            fetchAndRenderPdf();

        } catch (err) {
            console.error('Error in renderSPKTab:', err);
            container.innerHTML = `
                <div class="alert alert-warning my-3 p-3 text-start">
                    <div class="d-flex align-items-center mb-1">
                        <i class="bi bi-exclamation-triangle-fill fs-5 me-2 text-warning"></i>
                        <strong class="text-dark">Pratinjau SPK Belum Dapat Ditampilkan</strong>
                    </div>
                    <p class="small text-muted mb-0">
                        ${escapeHtml(err.message || String(err))}
                    </p>
                </div>
            `;
        }
    }

    /* --------------------------------------------------------------------------
     * 7. Wizard Footer Actions & Interactive Stepper Header Navigation
     * -------------------------------------------------------------------------- */
            function setupWizardFooter(form) {
        // Ambil elemen seluruh tombol yang relevan di form
        const btnBackToForms = form.querySelector('#btnBackToForms') || Array.from(form.querySelectorAll('a, button')).find(el => (el.textContent || '').includes('Kembali ke Riwayat'));
        const btnPrev = form.querySelector('#btnWizardPrev') || document.getElementById('btnWizardPrev') || form.querySelector('.btn-wizard-prev') || document.querySelector('.btn-wizard-prev');
        const btnNext = form.querySelector('#btnWizardNext') || document.getElementById('btnWizardNext') || form.querySelector('.btn-wizard-next') || document.querySelector('.btn-wizard-next');
        const btnNextText = form.querySelector('#btnWizardNextText') || document.getElementById('btnWizardNextText');
        const btnPreviewSPK = form.querySelector('#btnPreviewSPK') || document.getElementById('btnPreviewSPK');
        const btnSubmit = form.querySelector('#btnSubmitApplication') || document.getElementById('btnSubmitApplication') || form.querySelector('button[type="submit"][value="submit"]');

        const serverDiscardBtn = form.querySelector('#btnDiscardDraft');
        const localDiscardBtn = form.querySelector('#btnLocalDiscardDraft');
        const btnDiscard = serverDiscardBtn || localDiscardBtn;
        const btnSaveDraft = form.querySelector('#btnSaveDraft') || form.querySelector('.btn-save-draft') || form.querySelector('button[value="draft"]');

        // Hapus kontainer footer lama / wrapper bawaan Django yang rusak
        form.querySelectorAll('#unifiedWizardFooter, .unified-wizard-footer, .form-wizard-footer, .step-navigation').forEach(el => el.remove());

        // Buat kontainer tunggal baru dengan inline-style defensif (agar tidak bisa ditimpa CSS lain)
        const footerContainer = document.createElement('div');
        footerContainer.id = 'unifiedWizardFooter';
        footerContainer.className = 'unified-wizard-footer form-wizard-footer';
        footerContainer.setAttribute('style', `
            display: flex !important;
            flex-direction: row !important;
            justify-content: space-between !important;
            align-items: center !important;
            flex-wrap: wrap !important;
            gap: 12px !important;
            width: 100% !important;
            margin-top: 24px !important;
            padding-top: 16px !important;
            border-top: 1px solid #e2e8f0 !important;
            box-sizing: border-box !important;
            clear: both !important;
        `);

        const leftGroup = document.createElement('div');
        leftGroup.className = 'footer-group-left footer-left-actions';
        leftGroup.setAttribute('style', 'display: inline-flex !important; align-items: center !important; gap: 8px !important; flex-wrap: wrap !important;');

        const rightGroup = document.createElement('div');
        rightGroup.className = 'footer-group-right footer-right-actions';
        rightGroup.setAttribute('style', 'display: inline-flex !important; align-items: center !important; gap: 8px !important; flex-wrap: wrap !important; margin-left: auto !important;');

        // Masukkan tombol ke group masing-masing:
        if (btnBackToForms) leftGroup.appendChild(btnBackToForms);
        if (btnPrev) leftGroup.appendChild(btnPrev);

        if (btnDiscard) rightGroup.appendChild(btnDiscard);
        if (btnSaveDraft) rightGroup.appendChild(btnSaveDraft);
        if (btnNext) rightGroup.appendChild(btnNext);
        if (btnPreviewSPK) rightGroup.appendChild(btnPreviewSPK);
        if (btnSubmit) rightGroup.appendChild(btnSubmit);

        // Bersihkan inline style disruptif dari masing-masing tombol:
        [btnBackToForms, btnPrev, btnDiscard, btnSaveDraft, btnNext, btnPreviewSPK, btnSubmit].forEach(el => {
            if (el) {
                el.style.float = 'none';
                el.style.position = 'static';
                el.style.margin = '0';
                if (!el.classList.contains('d-none')) {
                    el.style.display = 'inline-flex';
                }
            }
        });

        footerContainer.appendChild(leftGroup);
        footerContainer.appendChild(rightGroup);
        form.appendChild(footerContainer);

        // Ensure form and buttons have HTML5 native validation disabled to prevent silent aborts
        if (form) {
            form.setAttribute('novalidate', 'novalidate');
            form.noValidate = true;
        }
        if (btnNext) {
            btnNext.setAttribute('type', 'button');
            btnNext.setAttribute('formnovalidate', 'formnovalidate');
        }
        if (btnPrev) {
            btnPrev.setAttribute('type', 'button');
            btnPrev.setAttribute('formnovalidate', 'formnovalidate');
        }

        function getCurrentStepIndex() {
            let activeIdx = 0;
            const activePane = form.querySelector('.wizard-step-pane.active') || document.querySelector('.wizard-step-pane.active');
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
                el.style.display = 'inline-flex';
            } else {
                el.classList.add('d-none');
                el.style.setProperty('display', 'none', 'important');
            }
        }

        function showWizardValidationAlert(formElement, errorMessages, targetPane) {
            // Remove previous validation alerts
            formElement.querySelectorAll('.wizard-validation-alert, .validation-alert').forEach(el => el.remove());
            const globalErr = document.getElementById('form-error-summary');
            if (globalErr) globalErr.style.display = 'none';

            const alert = document.createElement('div');
            alert.className = 'alert alert-danger alert-dismissible fade show wizard-validation-alert w-100 mb-3 shadow-sm border-0 border-start border-danger border-4';
            alert.setAttribute('role', 'alert');

            let listHtml = '';
            if (Array.isArray(errorMessages) && errorMessages.length > 0) {
                listHtml = `<ul class="mb-0 mt-2 ps-3 small">${errorMessages.map(m => `<li>${m}</li>`).join('')}</ul>`;
            }

            alert.innerHTML = `
                <div class="d-flex align-items-start gap-2">
                    <i class="bi bi-exclamation-triangle-fill fs-5 text-danger flex-shrink-0 mt-1"></i>
                    <div class="flex-grow-1">
                        <strong>Mohon lengkapi field wajib sebelum melanjutkan:</strong>
                        ${listHtml}
                    </div>
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                </div>
            `;

            // Insert alert before footer button bar (.form-wizard-footer) so user immediately sees what went wrong without breaking footer buttons layout
            const wizardFooter = formElement.querySelector('.form-wizard-footer') || formElement.querySelector('.form-footer-actions');
            if (wizardFooter && wizardFooter.parentNode) {
                wizardFooter.parentNode.insertBefore(alert, wizardFooter);
            } else if (targetPane) {
                targetPane.appendChild(alert);
            } else {
                formElement.prepend(alert);
            }

            try {
                alert.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            } catch (e) {}

            // Also synchronize with window.formEnhancements if available
            if (window.formEnhancements && typeof window.formEnhancements.showValidationAlert === 'function') {
                try {
                    window.formEnhancements.showValidationAlert('Mohon lengkapi seluruh field wajib sebelum melanjutkan.');
                } catch (e) {}
            }

            setTimeout(() => {
                if (alert.parentNode) {
                    alert.classList.remove('show');
                    setTimeout(() => alert.remove(), 300);
                }
            }, 8000);
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
            console.log(`[Wizard Navigation] switchWizardStep dipanggil: targetStep=${targetStep}, validate=${validate}`);
            if (targetStep < 0 || targetStep > 2) return false;

            const panes = form.querySelectorAll('.wizard-step-pane');
            const currentStep = getCurrentStepIndex();
            console.log(`[Wizard Navigation] Current step: ${currentStep}, Target step: ${targetStep}`);

            // Validation if moving forward
            if (validate && targetStep > currentStep) {
                console.log("[Wizard Navigation] ========================================");
                console.log("[Wizard Navigation] Tombol Lanjut diklik. Evaluasi validasi Step 1...");
                console.log(`[Wizard Navigation] Current Step Index: ${currentStep} -> Target Step: ${targetStep}`);

                let hasError = false;
                let firstInvalid = null;
                const errorDetails = [];
                const currentPane = panes[currentStep] || form.querySelector(`.wizard-step-pane[data-step="${currentStep}"]`) || form.querySelector('.wizard-step-pane.active') || document.getElementById(`wizardStepPane${currentStep + 1}`);

                if (currentStep === 0) {
                    console.log("[Wizard Navigation] Memulai evaluasi field wajib Step 1 (Strict Whitelist Mode)...");

                    // 1. Brand validation (Wajib)
                    const brandSelect = form.querySelector('[name="brand"]');
                    const brandVal = (brandSelect?.value || '').trim();
                    if (!brandVal) {
                        if (brandSelect) brandSelect.classList.add('is-invalid');
                        hasError = true;
                        if (!firstInvalid) firstInvalid = brandSelect;
                        errorDetails.push('<strong>Brand Produk</strong> wajib dipilih.');
                        console.warn("[Wizard Navigation] Validation: Brand Produk KOSONG");
                    } else {
                        if (brandSelect) brandSelect.classList.remove('is-invalid');
                        console.log(`[Wizard Navigation] Validation: Brand Produk OK ('${brandVal}')`);
                    }

                    // 2. Cabang validation (Wajib jika dapat dipilih)
                    const cabangSelect = form.querySelector('[name="cabang"]');
                    if (cabangSelect && cabangSelect.tagName === 'SELECT' && !cabangSelect.classList.contains('field-readonly')) {
                        const cabangVal = (cabangSelect.value || '').trim();
                        if (!cabangVal) {
                            cabangSelect.classList.add('is-invalid');
                            hasError = true;
                            if (!firstInvalid) firstInvalid = cabangSelect;
                            errorDetails.push('<strong>Cabang / Area</strong> wajib dipilih.');
                            console.warn("[Wizard Navigation] Validation: Cabang KOSONG");
                        } else {
                            cabangSelect.classList.remove('is-invalid');
                            console.log(`[Wizard Navigation] Validation: Cabang OK ('${cabangVal}')`);
                        }
                    }

                    // 2b. Channel validation (Wajib)
                    const channelSelect = form.querySelector('[name="channel"]');
                    const channelVal = (channelSelect?.value || '').trim();
                    if (!channelVal) {
                        if (channelSelect) channelSelect.classList.add('is-invalid');
                        hasError = true;
                        if (!firstInvalid) firstInvalid = channelSelect;
                        errorDetails.push('<strong>Channel Distribusi</strong> wajib dipilih.');
                        console.warn("[Wizard Navigation] Validation: Channel KOSONG");
                    } else {
                        if (channelSelect) channelSelect.classList.remove('is-invalid');
                        console.log(`[Wizard Navigation] Validation: Channel OK ('${channelVal}')`);
                    }

                    // 3. Kode Customer JDE validation (Wajib)
                    const jdeInput = form.querySelector('[name="kode_customer_jde"]');
                    const jdeVal = (jdeInput?.value || '').trim();
                    if (!jdeVal) {
                        if (jdeInput) jdeInput.classList.add('is-invalid');
                        hasError = true;
                        if (!firstInvalid) firstInvalid = jdeInput;
                        errorDetails.push('<strong>Kode Customer JDE</strong> wajib diisi.');
                        console.warn("[Wizard Navigation] Validation: Kode Customer JDE KOSONG");
                    } else {
                        if (jdeInput) jdeInput.classList.remove('is-invalid');
                        console.log(`[Wizard Navigation] Validation: Kode Customer JDE OK ('${jdeVal}')`);
                    }

                    // 4. Email validation (Wajib & Format RFC)
                    const emailInput = form.querySelector('[name="email"]');
                    const emailVal = (emailInput?.value || '').trim();
                    if (!emailVal) {
                        if (emailInput) emailInput.classList.add('is-invalid');
                        hasError = true;
                        if (!firstInvalid) firstInvalid = emailInput;
                        errorDetails.push('<strong>Email Toko / Pemilik</strong> wajib diisi.');
                        console.warn("[Wizard Navigation] Validation: Email KOSONG");
                    } else {
                        let isEmailValid = false;
                        if (typeof form._validateEmail === 'function') {
                            isEmailValid = form._validateEmail(true);
                        } else {
                            const EMAIL_RX = /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$/;
                            isEmailValid = EMAIL_RX.test(emailVal);
                        }
                        if (!isEmailValid) {
                            if (emailInput) emailInput.classList.add('is-invalid');
                            hasError = true;
                            if (!firstInvalid) firstInvalid = emailInput;
                            errorDetails.push('<strong>Format Email</strong> tidak valid (contoh: toko@gmail.com).');
                            console.warn(`[Wizard Navigation] Validation: Format Email '${emailVal}' TIDAK VALID`);
                        } else {
                            if (emailInput) {
                                emailInput.classList.remove('is-invalid');
                                emailInput.classList.add('is-valid');
                            }
                            console.log(`[Wizard Navigation] Validation: Email OK ('${emailVal}')`);
                        }
                    }

                    // 5. Nomor NPWP validation (Wajib 15/16 digit)
                    const npwpInput = form.querySelector('[name="nomor_npwp"]');
                    const npwpDigits = (npwpInput?.value || '').trim().replace(/\D/g, '');
                    if (!npwpDigits) {
                        if (npwpInput) npwpInput.classList.add('is-invalid');
                        hasError = true;
                        if (!firstInvalid) firstInvalid = npwpInput;
                        errorDetails.push('<strong>Nomor NPWP Toko / Pemilik</strong> wajib diisi.');
                        console.warn("[Wizard Navigation] Validation: Nomor NPWP KOSONG");
                    } else if (npwpDigits.length !== 15 && npwpDigits.length !== 16) {
                        if (npwpInput) npwpInput.classList.add('is-invalid');
                        hasError = true;
                        if (!firstInvalid) firstInvalid = npwpInput;
                        errorDetails.push(`<strong>Nomor NPWP</strong> harus 15 atau 16 digit angka (saat ini: ${npwpDigits.length} digit).`);
                        console.warn(`[Wizard Navigation] Validation: Nomor NPWP '${npwpDigits}' panjang ${npwpDigits.length} bukan 15/16 digit`);
                    } else {
                        if (npwpInput) {
                            npwpInput.classList.remove('is-invalid');
                            npwpInput.classList.add('is-valid');
                        }
                        console.log(`[Wizard Navigation] Validation: Nomor NPWP OK ('${npwpDigits}')`);
                    }

                    // 6. Nomor NIK validation (Opsional, jika diisi tepat 16 digit)
                    const nikInput = form.querySelector('[name="nomor_nik"]');
                    const nikDigits = (nikInput?.value || '').trim().replace(/\D/g, '');
                    if (nikDigits) {
                        if (nikDigits.length !== 16) {
                            if (nikInput) nikInput.classList.add('is-invalid');
                            hasError = true;
                            if (!firstInvalid) firstInvalid = nikInput;
                            errorDetails.push(`<strong>Nomor NIK</strong> harus tepat 16 digit angka (saat ini: ${nikDigits.length} digit).`);
                            console.warn(`[Wizard Navigation] Validation: Nomor NIK '${nikDigits}' bukan 16 digit`);
                        } else {
                            if (nikInput) {
                                nikInput.classList.remove('is-invalid');
                                nikInput.classList.add('is-valid');
                            }
                            console.log(`[Wizard Navigation] Validation: Nomor NIK OK ('${nikDigits}')`);
                        }
                    }

                    // CATATAN: Repeatable grid Asset Toko & Market Share sepenuhnya opsional dan diabaikan dari validasi blocking!
                    console.log("[Wizard Navigation] Tabel grid Asset Toko & Market Share dilewati (opsional).");
                } else if (currentStep === 1) {
                    // Validasi Step 2 jika diperlukan saat maju ke Step 3
                    const pane2 = panes[1] || document.getElementById('wizardStepPane2');
                    if (pane2) {
                        const reqs = pane2.querySelectorAll('input[required], select[required], textarea[required]');
                        reqs.forEach(input => {
                            if (input.type === 'hidden' || input.disabled || input.style.display === 'none') return;
                            if (input.offsetParent === null && input.type !== 'checkbox' && input.type !== 'radio') return;
                            const val = (input.value || '').trim();
                            if (!val) {
                                input.classList.add('is-invalid');
                                hasError = true;
                                if (!firstInvalid) firstInvalid = input;
                                const lbl = input.closest('.field-wrapper, .mb-3')?.querySelector('label');
                                errorDetails.push(`<strong>${lbl ? lbl.textContent.replace('*', '').trim() : input.name}</strong> wajib diisi.`);
                            }
                        });
                    }

                    // Validasi Wajib Minimal 1 Tier Valid pada Target & Incentive Scheme (Pasal 3)
                    if (typeof form._validateTargetTierScheme === 'function') {
                        const isTierValid = form._validateTargetTierScheme(true);
                        if (!isTierValid) {
                            hasError = true;
                            errorDetails.push('<strong>Target & Incentive Scheme (Pasal 3)</strong> wajib memiliki minimal 1 tier valid (Target Bulanan > 0 dan Incentive > 0%).');
                            const targetContainer = form.querySelector('.kontrak-target-incentive-wrapper') || form.querySelector('[data-grid="target_incentive"]');
                            if (targetContainer && !firstInvalid) {
                                firstInvalid = targetContainer.querySelector('[data-key="target_bulanan"]') || targetContainer;
                            }
                        }
                    }
                }

                if (hasError) {
                    console.warn("[Wizard Navigation] Validasi memblokir navigasi. Field bermasalah:", errorDetails);
                    if (firstInvalid) {
                        firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        firstInvalid.focus();
                    }
                    showWizardValidationAlert(form, errorDetails, currentPane);
                    return false;
                }

                console.log("[Wizard Navigation] Validasi BERHASIL! Mengeksekusi transisi pane...");
            }

            // 1. Toggle Panes & Clean Target Pane Error States
            panes.forEach((pane, idx) => {
                if (idx === targetStep) {
                    pane.classList.remove('d-none');
                    pane.classList.add('active');
                    pane.style.removeProperty('display');
                    pane.style.setProperty('display', 'block', 'important');

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
                    pane.classList.add('d-none');
                    pane.style.setProperty('display', 'none', 'important');
                }
            });

            // Explicit Pane Toggle by ID (Guarantee #wizardStepPane2 is displayed and #wizardStepPane1 is hidden)
            const p1 = document.getElementById('wizardStepPane1') || form.querySelector('#wizardStepPane1, #step1Pane, .step1Pane');
            const p2 = document.getElementById('wizardStepPane2') || form.querySelector('#wizardStepPane2, #step2Pane, .step2Pane');
            const p3 = document.getElementById('wizardStepPane3') || form.querySelector('#wizardStepPane3, #step3Pane, .step3Pane');
            [p1, p2, p3].forEach((p, idx) => {
                if (!p) return;
                if (idx === targetStep) {
                    p.classList.remove('d-none');
                    p.classList.add('active');
                    p.style.removeProperty('display');
                    p.style.setProperty('display', 'block', 'important');
                    // Unhide any fields or aligned rows inside the active pane
                    p.querySelectorAll('.field-wrapper, .fields-aligned-row, .mb-3').forEach(el => {
                        if (el.tagName !== 'INPUT') el.style.removeProperty('display');
                    });
                } else {
                    p.classList.remove('active');
                    p.classList.add('d-none');
                    p.style.setProperty('display', 'none', 'important');
                }
            });

            // 2. Remove any global validation alert banners
            const existingAlert = form.querySelector('.wizard-validation-alert, .validation-alert');
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

            // 5. Update Progress Bar & Stepper Title
            const progressBar = document.getElementById('formProgressBar');
            if (progressBar) {
                const pct = ((targetStep + 1) / 3) * 100;
                progressBar.style.width = `${pct}%`;
            }
            const stepTitles = [
                'Informasi Toko & Partner',
                'Detail Kontrak & Klausul',
                'Preview SPK & Konfirmasi'
            ];
            const counterEl = document.getElementById('stepperStepCounter');
            const titleEl = document.getElementById('stepperStepTitle');
            if (counterEl) counterEl.textContent = `Langkah ${targetStep + 1} dari 3`;
            if (titleEl) titleEl.textContent = stepTitles[targetStep] || '';

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
            console.log(`[Wizard Navigation] Berhasil berpindah ke Step ${targetStep + 1}.`);
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
        function onNextClicked(e) {
            if (e) {
                e.preventDefault();
                e.stopImmediatePropagation();
            }
            console.log("[Wizard Navigation] Tombol Lanjut diklik. Evaluasi validasi Step 1...");
            const current = getCurrentStepIndex();
            console.log(`[Wizard Navigation] onNextClicked triggered, current step index: ${current}`);
            if (current < 2) {
                switchWizardStep(current + 1, true);
            }
        }

        function onPrevClicked(e) {
            if (e) {
                e.preventDefault();
                e.stopImmediatePropagation();
            }
            console.log("[Wizard Navigation] Tombol Kembali diklik.");
            const current = getCurrentStepIndex();
            if (current > 0) {
                switchWizardStep(current - 1, false);
            }
        }

        if (btnNext) {
            btnNext.dataset.wizardBound = 'true';
            btnNext.addEventListener('click', onNextClicked);
            console.log("[Wizard Navigation] Event listener direct berhasil terpasang pada btnNext:", btnNext);
        }

        if (btnPrev) {
            btnPrev.dataset.wizardBound = 'true';
            btnPrev.addEventListener('click', onPrevClicked);
        }

        // Fallback: Event delegation on document to ensure button clicks are NEVER lost even after DOM re-renders
        if (!document.body.dataset.wizardNavDelegated) {
            document.body.dataset.wizardNavDelegated = 'true';
            document.addEventListener('click', function(e) {
                const targetNext = e.target.closest('#btnWizardNext, .btn-wizard-next');
                if (targetNext) {
                    e.preventDefault();
                    console.log("[Wizard Navigation] Delegated click captured on Next button:", targetNext);
                    const current = getCurrentStepIndex();
                    if (current < 2) {
                        switchWizardStep(current + 1, true);
                    }
                    return;
                }
                const targetPrev = e.target.closest('#btnWizardPrev, .btn-wizard-prev');
                if (targetPrev) {
                    e.preventDefault();
                    console.log("[Wizard Navigation] Delegated click captured on Prev button:", targetPrev);
                    const current = getCurrentStepIndex();
                    if (current > 0) {
                        switchWizardStep(current - 1, false);
                    }
                }
            });
        }

        // Hook Preview SPK button to jump to SPK tab
        if (btnPreviewSPK && !btnPreviewSPK.dataset.wizardBound) {
            btnPreviewSPK.dataset.wizardBound = 'true';
            btnPreviewSPK.addEventListener('click', function(e) {
                e.preventDefault();
                if (typeof form._validateTargetTierScheme === 'function') {
                    const isTierValid = form._validateTargetTierScheme(true);
                    if (!isTierValid) {
                        if (window.switchWizardStep) {
                            window.switchWizardStep(1, false);
                        }
                        const targetContainer = form.querySelector('.kontrak-target-incentive-wrapper') || form.querySelector('[data-grid="target_incentive"]');
                        if (targetContainer) {
                            const firstTb = targetContainer.querySelector('[data-key="target_bulanan"]');
                            if (firstTb) {
                                firstTb.focus();
                                firstTb.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            }
                        }
                        return;
                    }
                }
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

        // 1. Primary check: Substantive customer identification fields
        const substantiveKeys = [
            'kode_customer_jde',
            'nama_toko',
            'nama_pemilik',
            'email',
            'nomor_nik',
            'nomor_npwp',
            'nomor_identitas',
            'no_telepon',
            'alamat_toko'
        ];
        for (const key of substantiveKeys) {
            if (data[key] && typeof data[key] === 'string' && data[key].trim().length > 0) {
                return true;
            }
        }

        // 2. Secondary check: Grid data with non-zero user inputs
        if (data.target_omset_toko && typeof data.target_omset_toko === 'string') {
            try {
                const rows = JSON.parse(data.target_omset_toko);
                if (Array.isArray(rows) && rows.some(r => (r.bulan && r.bulan.trim() !== '') || r.serenity > 0 || r.kompetitor_1 > 0 || r.kompetitor_2 > 0 || r.kompetitor_3 > 0 || r.kompetitor_4 > 0)) {
                    return true;
                }
            } catch (e) {}
        }

        if (data.skema_incentive && typeof data.skema_incentive === 'string') {
            try {
                const rows = JSON.parse(data.skema_incentive);
                if (Array.isArray(rows) && rows.some(r => r.target_bulanan > 0 || r.incentive_pct > 0 || (r.keterangan && r.keterangan.trim() !== ''))) {
                    return true;
                }
            } catch (e) {}
        }

        if (data.support_facility && typeof data.support_facility === 'string') {
            try {
                const rows = JSON.parse(data.support_facility);
                if (Array.isArray(rows) && rows.some(r => r.target_tahunan > 0 || r.support_pct > 0 || (r.keterangan && r.keterangan.trim() !== ''))) {
                    return true;
                }
            } catch (e) {}
        }

        if (data.cabang_toko_alamat && typeof data.cabang_toko_alamat === 'string') {
            try {
                const rows = JSON.parse(data.cabang_toko_alamat);
                if (Array.isArray(rows) && rows.length > 0) {
                    const hasUserContent = rows.some(r => (r.keterangan && r.keterangan.trim() !== '') || (r.alamat && r.alamat.trim() !== ''));
                    if (hasUserContent) return true;
                }
            } catch (e) {}
        }

        return false;
    }

    function collectFormData(form) {
        if (typeof window.syncSalesSupportState === 'function') {
            window.syncSalesSupportState();
        }
        const data = {};
        const elements = form.querySelectorAll('input, select, textarea');
        elements.forEach(el => {
            const name = el.name;
            if (!name || name === 'csrfmiddlewaretoken' || name === 'action') return;
            if (name === 'komponen_biaya_support_chk' || name === 'tipe_kontrak_switch') return;
            if (name === 'komponen_biaya') {
                if (!Array.isArray(data.komponen_biaya)) {
                    data.komponen_biaya = [];
                }
                if (el.checked) {
                    data.komponen_biaya.push(el.value);
                }
                return;
            }
            if (el.type === 'checkbox') {
                data[name] = el.checked;
            } else if (el.type === 'radio') {
                if (el.checked) data[name] = el.value;
            } else {
                data[name] = el.value;
            }
        });

        const toggleSwitch = form.querySelector('#toggleSalesSupportSwitch');
        if (toggleSwitch) {
            const isSupport = Boolean(toggleSwitch.checked);
            data.is_sales_support = isSupport ? 'true' : 'false';
            data.is_support_provided = isSupport;
            data.has_support = isSupport;
            const inputPersen = form.querySelector('#input_persen_support');
            data.persen_support = isSupport ? (inputPersen?.value || '5') : '0';
            const selectedChips = Array.from(form.querySelectorAll('.support-chip-input:checked, input[name="komponen_biaya_support_chk"]:checked')).map(c => c.value);
            data.komponen_biaya_support = JSON.stringify(selectedChips);
        }

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

        btnDiscard.onclick = async function () {
            btnDiscard.disabled = true;
            btnContinue.disabled = true;
            btnDiscard.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span> Menyiapkan formulir baru...';
            await discardDraft(form, true);
        };

        bsModal.show();
    }

    function showDiscardDraftButton(form, show) {
        const rightGroup = form.querySelector('.footer-group-right') || form.querySelector('.footer-right-actions') || form.querySelector('#unifiedWizardFooter');
        if (!rightGroup) return;

        const serverDiscardBtn = form.querySelector('#btnDiscardDraft');
        if (serverDiscardBtn) {
            if (serverDiscardBtn.parentNode !== rightGroup) {
                const btnSaveDraft = rightGroup.querySelector('#btnSaveDraft') || rightGroup.querySelector('#btnWizardNext');
                if (btnSaveDraft) {
                    rightGroup.insertBefore(serverDiscardBtn, btnSaveDraft);
                } else {
                    rightGroup.prepend(serverDiscardBtn);
                }
            }
            return;
        }

        let btnDiscard = form.querySelector('#btnLocalDiscardDraft');
        if (!btnDiscard) {
            btnDiscard = document.createElement('button');
            btnDiscard.type = 'button';
            btnDiscard.id = 'btnLocalDiscardDraft';
            btnDiscard.className = 'btn btn-outline-danger btn-sm btn-discard-draft' + (show ? '' : ' d-none');
            btnDiscard.innerHTML = '<i class="bi bi-trash3 me-1"></i> Discard Draft';
            btnDiscard.addEventListener('click', async function(e) {
                e.preventDefault();
                await discardDraft(form);
            });
            const btnSaveDraft = rightGroup.querySelector('#btnSaveDraft') || rightGroup.querySelector('#btnWizardNext');
            if (btnSaveDraft) {
                rightGroup.insertBefore(btnDiscard, btnSaveDraft);
            } else {
                rightGroup.prepend(btnDiscard);
            }
        } else {
            if (btnDiscard.parentNode !== rightGroup) {
                const btnSaveDraft = rightGroup.querySelector('#btnSaveDraft') || rightGroup.querySelector('#btnWizardNext');
                if (btnSaveDraft) {
                    rightGroup.insertBefore(btnDiscard, btnSaveDraft);
                } else {
                    rightGroup.prepend(btnDiscard);
                }
            }
            if (show) {
                btnDiscard.classList.remove('d-none');
            } else {
                btnDiscard.classList.add('d-none');
            }
        }
    }

    async function discardDraft(form, skipConfirm) {
        if (skipConfirm || confirm('Apakah Anda yakin ingin membuang draft dan mengosongkan seluruh formulir?')) {
            try {
                localStorage.removeItem(STORAGE_KEY);
            } catch (e) {}

            const serverDraftMeta = document.getElementById('activeServerDraftMeta');
            const serverDraftId = form.dataset.currentDraftId 
                || form.querySelector('input[name="draft_id"]')?.value
                || serverDraftMeta?.dataset?.draftId;

            if (serverDraftId) {
                const tokenInput = form.querySelector('[name="csrfmiddlewaretoken"]');
                let csrfToken = tokenInput ? tokenInput.value : '';
                if (!csrfToken) {
                    csrfToken = document.cookie
                        .split('; ')
                        .find(row => row.startsWith('csrftoken='))
                        ?.split('=')[1] || '';
                }
                try {
                    await fetch(`/forms/submissions/${serverDraftId}/discard/`, {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': csrfToken,
                            'X-Requested-With': 'XMLHttpRequest'
                        }
                    });
                } catch (e) {
                    console.warn('[KontrakDraft] Failed to discard server draft:', e);
                }
            }

            if (serverDraftMeta) {
                serverDraftMeta.remove();
            }
            const scriptData = document.getElementById('active_server_draft_data');
            if (scriptData) {
                scriptData.remove();
            }

            window.location.href = window.location.pathname;
        }
    }

    function setupFormPersistence(form, hasRestoredDraft) {
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
                    if (resData.ignored) {
                        updateAutoSaveStatus('idle');
                        return;
                    }
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

            const hasExistingDraftId = Boolean(form.dataset.currentDraftId || form.querySelector('input[name="draft_id"]')?.value);
            const currentData = collectFormData(form);
            const isMeaningful = hasMeaningfulData(currentData);

            if (!isMeaningful && !hasExistingDraftId) {
                // Completely empty or default-only form without existing draft: don't save
                updateAutoSaveStatus('idle');
                showDiscardDraftButton(form, false);
                return;
            }

            updateAutoSaveStatus('saving');

            autoSaveTimeout = setTimeout(() => {
                try {
                    const data = collectFormData(form);
                    const meaningfulNow = hasMeaningfulData(data);
                    if (meaningfulNow || hasExistingDraftId) {
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
            if (typeof window.syncSalesSupportState === 'function') {
                window.syncSalesSupportState();
            }
            const submitter = e.submitter || document.activeElement;
            const isDraftAction = submitter && (
                submitter.value === 'draft' || 
                submitter.name === 'save_draft' || 
                submitter.id === 'btnSaveDraft' ||
                submitter.classList.contains('btn-save-draft')
            );

            // If user is explicitly saving a draft, do NOT run mandatory field validation
            if (isDraftAction) {
                return true;
            }

            if (typeof form._validateEmail === 'function') {
                const isEmailValid = form._validateEmail(true);
                if (!isEmailValid) {
                    e.preventDefault();
                    const overlay = document.getElementById('loadingOverlay');
                    if (overlay) overlay.classList.remove('active');
                    if (window.switchWizardStep) {
                        window.switchWizardStep(0, false);
                    }
                    const emailInput = form.querySelector('[name="email"]');
                    if (emailInput) {
                        emailInput.focus();
                        emailInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                    return false;
                }
            }

            if (typeof form._validateNomorNik === 'function') {
                const isNikValid = form._validateNomorNik(true);
                if (!isNikValid) {
                    e.preventDefault();
                    const overlay = document.getElementById('loadingOverlay');
                    if (overlay) overlay.classList.remove('active');
                    if (window.switchWizardStep) {
                        window.switchWizardStep(0, false);
                    }
                    const nikInput = form.querySelector('[name="nomor_nik"]');
                    if (nikInput) {
                        nikInput.focus();
                        nikInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                    return false;
                }
            } else if (typeof form._validateNomorIdentitas === 'function') {
                const isIdValid = form._validateNomorIdentitas(true);
                if (!isIdValid) {
                    e.preventDefault();
                    const overlay = document.getElementById('loadingOverlay');
                    if (overlay) overlay.classList.remove('active');
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
            if (typeof form._validateNomorNpwp === 'function') {
                const isNpwpValid = form._validateNomorNpwp(false);
                if (!isNpwpValid) {
                    e.preventDefault();
                    const overlay = document.getElementById('loadingOverlay');
                    if (overlay) overlay.classList.remove('active');
                    if (window.switchWizardStep) {
                        window.switchWizardStep(0, false);
                    }
                    const npwpInput = form.querySelector('[name="nomor_npwp"]');
                    if (npwpInput) {
                        npwpInput.focus();
                        npwpInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                    return false;
                }
            }
            if (typeof form._validateTargetTierScheme === 'function') {
                const isTierValid = form._validateTargetTierScheme(true);
                if (!isTierValid) {
                    e.preventDefault();
                    const overlay = document.getElementById('loadingOverlay');
                    if (overlay) overlay.classList.remove('active');
                    if (window.switchWizardStep) {
                        window.switchWizardStep(1, false);
                    }
                    const targetContainer = form.querySelector('.kontrak-target-incentive-wrapper') || form.querySelector('[data-grid="target_incentive"]');
                    if (targetContainer) {
                        const firstTb = targetContainer.querySelector('[data-key="target_bulanan"]');
                        if (firstTb) {
                            firstTb.focus();
                            firstTb.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        }
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
