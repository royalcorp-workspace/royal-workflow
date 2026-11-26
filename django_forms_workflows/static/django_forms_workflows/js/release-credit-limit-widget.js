/**
 * Release Credit Limit Widget
 * Harmonized with Royal Workflow Design System (pengajuan-biaya-form.css .wf-panel-box cards)
 */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        const formEl = document.getElementById('form_release-credit-limit');
        if (!formEl) return;

        const fieldsWrapper = formEl.querySelector('.form-fields-wrapper');
        if (!fieldsWrapper) return;

        function getFieldGroup(name) {
            const input = formEl.querySelector(`[name="${name}"]`);
            if (!input) return null;
            return input.closest('.mb-3, .form-group, [id^="div_id_"]') || input.parentElement;
        }

        function createPanel(num, title, rightHint) {
            const box = document.createElement('div');
            box.className = 'wf-panel-box mb-4';

            const header = document.createElement('div');
            header.className = 'wf-panel-header';

            const titleEl = document.createElement('div');
            titleEl.className = 'wf-panel-title';
            titleEl.innerHTML = `<span class="wf-panel-badge me-1">${num}</span> <span>${title}</span>`;
            header.appendChild(titleEl);

            if (rightHint) {
                const hintEl = document.createElement('span');
                hintEl.className = 'text-muted small';
                hintEl.style.fontSize = '12px';
                hintEl.textContent = rightHint;
                header.appendChild(hintEl);
            }

            const body = document.createElement('div');
            body.className = 'p-3 p-md-4';

            box.appendChild(header);
            box.appendChild(body);
            return { box, body };
        }

        function appendRow(parent, items) {
            const row = document.createElement('div');
            row.className = 'row g-3 mb-2';
            items.forEach(({ name, colClass }) => {
                const grp = getFieldGroup(name);
                if (!grp) return;
                grp.classList.remove('mb-3');
                const col = document.createElement('div');
                col.className = colClass;
                col.appendChild(grp);
                row.appendChild(col);
            });
            parent.appendChild(row);
        }

        // Build 4 Numbered Panels
        const container = document.createElement('div');
        container.className = 'rcl-panels-container';

        // Helper to find an input whether it is still in formEl or already moved into detached container
        function getFieldInput(name) {
            return container.querySelector(`[name="${name}"]`) || formEl.querySelector(`[name="${name}"]`);
        }

        // 01 — Informasi Dasar
        const p1 = createPanel('01', 'Informasi Dasar', '* Field wajib');
        appendRow(p1.body, [
            { name: 'no_pengajuan', colClass: 'col-12 col-md-5' },
            { name: 'cabang', colClass: 'col-12 col-md-3' },
            { name: 'brand', colClass: 'col-12 col-md-4' },
        ]);
        const noPengajuanInput = getFieldInput('no_pengajuan');
        const cabangSelect = getFieldInput('cabang');
        const brandSelect = getFieldInput('brand');
        if (noPengajuanInput) {
            noPengajuanInput.readOnly = true;
            noPengajuanInput.classList.add('bg-light', 'fw-semibold', 'font-monospace');
            noPengajuanInput.style.fontSize = '0.84rem';
            noPengajuanInput.style.paddingLeft = '0.6rem';
            noPengajuanInput.style.paddingRight = '0.6rem';
            if (noPengajuanInput.value) {
                noPengajuanInput.title = noPengajuanInput.value;
            } else {
                noPengajuanInput.placeholder = 'Dibuat otomatis saat submit';
            }
        }

        // Live Preview No Pengajuan ({NNN}/CL-{PT}/{CABANG}/{BRAND}/{ROMAWI}/{TAHUN})
        function getControlValue(el) {
            if (!el) return '';
            if (el.tagName === 'SELECT') {
                const v = (el.value || '').trim();
                if (v) return v;
                const opt = el.options && el.selectedIndex >= 0 ? el.options[el.selectedIndex] : null;
                return opt ? (opt.value || opt.text || '').trim() : '';
            }
            return (el.value || '').trim();
        }

        function getCanonicalBrandCode(brd) {
            const b = String(brd || '').trim().toUpperCase();
            if (!b) return '';
            if (b.includes('LADY')) return 'LADY';
            if (b.includes('ROYAL') || b.includes('FOAM')) return 'ROYAL';
            if (b.includes('SERENITY')) return 'SERENITY';
            if (b.includes('ELITE')) return 'ELITE';
            if (b.includes('CLASSIC')) return 'CLASSIC';
            if (b.includes('GRAND')) return 'GRAND';
            return b.split(/\s+/)[0] || '';
        }

        function matchesCurrentSelection(curVal, cab, brd) {
            const valUpper = String(curVal || '').trim().toUpperCase();
            if (!valUpper || valUpper.indexOf('/CL-') === -1) return false;
            const cabCode = String(cab || '').trim().toUpperCase().replace(/\s+/g, '');
            const brdCode = getCanonicalBrandCode(brd);
            if (!cabCode || !brdCode) return false;
            return valUpper.includes(`/${cabCode}/`) && valUpper.includes(`/${brdCode}/`);
        }

        let clAbortController = null;
        let clLatestSeq = 0;
        let lastPreviewKey = '';
        async function refreshClNumberPreview(force = false) {
            const noEl = getFieldInput('no_pengajuan');
            const cabEl = getFieldInput('cabang');
            const brdEl = getFieldInput('brand');
            if (!noEl || !cabEl || !brdEl) return;
            const cab = getControlValue(cabEl);
            const brd = getControlValue(brdEl);
            if (!cab || !brd) return;

            const key = `${cab}||${brd}`;
            const curVal = (noEl.value || '').trim();
            if (!force && matchesCurrentSelection(curVal, cab, brd) && lastPreviewKey === key) {
                return;
            }

            if (clAbortController) clAbortController.abort();
            clAbortController = new AbortController();
            const seq = ++clLatestSeq;

            const params = new URLSearchParams({ cabang: cab, brand: brd });
            const draftIdInput = formEl.querySelector('input[name="draft_id"]');
            const serverDraftMeta = document.getElementById('activeServerDraftMeta');
            const activeDraftId = (draftIdInput && draftIdInput.value)
                || (serverDraftMeta && serverDraftMeta.getAttribute('data-draft-id'))
                || '';
            if (activeDraftId) {
                params.set('draft_id', activeDraftId);
            }
            try {
                const resp = await fetch(`/forms/release-credit-limit/next-spk-number/?${params.toString()}`, {
                    signal: clAbortController.signal,
                });
                if (!resp.ok) return;
                const data = await resp.json();
                if (seq !== clLatestSeq) return;
                if (data && data.success && data.nomor_spk) {
                    const changed = noEl.value !== data.nomor_spk;
                    noEl.value = data.nomor_spk;
                    noEl.title = data.nomor_spk;
                    lastPreviewKey = key;
                    if (changed) {
                        noEl.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }
            } catch (err) {
                if (err && err.name === 'AbortError') return;
            }
        }

        function refreshClNumberPreviewIfNeeded() {
            const noEl = getFieldInput('no_pengajuan');
            const cabEl = getFieldInput('cabang');
            const brdEl = getFieldInput('brand');
            const cab = getControlValue(cabEl);
            const brd = getControlValue(brdEl);
            if (!cab || !brd) return;
            const curVal = ((noEl && noEl.value) || '').trim();
            const key = `${cab}||${brd}`;
            if (!curVal || !matchesCurrentSelection(curVal, cab, brd) || (lastPreviewKey && lastPreviewKey !== key)) {
                refreshClNumberPreview(true);
            }
        }

        // Delegated listeners on formEl so brand/cabang changes always trigger live preview
        formEl.addEventListener('change', function (e) {
            if (e.target && e.target.matches('[name="brand"], [name="cabang"]')) {
                refreshClNumberPreview(true);
            }
        });
        formEl.addEventListener('input', function (e) {
            if (e.target && e.target.matches('[name="brand"], [name="cabang"]')) {
                refreshClNumberPreview(true);
            }
        });

        // Observe programmatic value/attribute changes on cabang (e.g., user-profile auto-lock script)
        if (cabangSelect && typeof MutationObserver !== 'undefined') {
            const cabObserver = new MutationObserver(function () {
                refreshClNumberPreviewIfNeeded();
            });
            cabObserver.observe(cabangSelect, {
                attributes: true,
                attributeFilter: ['value', 'readonly', 'disabled'],
            });
        }

        // Initial check + delayed retries for async/post-load branch auto-fill scripts
        refreshClNumberPreviewIfNeeded();
        setTimeout(refreshClNumberPreviewIfNeeded, 150);
        setTimeout(refreshClNumberPreviewIfNeeded, 500);
        let pollTicks = 0;
        const clPollTimer = setInterval(function () {
            pollTicks += 1;
            refreshClNumberPreviewIfNeeded();
            const curNo = ((noPengajuanInput && noPengajuanInput.value) || '').trim();
            const curCab = getControlValue(getFieldInput('cabang'));
            const curBrd = getControlValue(getFieldInput('brand'));
            if (matchesCurrentSelection(curNo, curCab, curBrd) || pollTicks >= 12) {
                clearInterval(clPollTimer);
            }
        }, 250);
        container.appendChild(p1.box);

        // 02 — Informasi Toko
        const p2 = createPanel('02', 'Informasi Toko', 'Data customer dari JDE dapat diisi otomatis');
        appendRow(p2.body, [
            { name: 'kode_customer_jde', colClass: 'col-12' },
        ]);
        appendRow(p2.body, [
            { name: 'nama_customer', colClass: 'col-12 col-md-6' },
            { name: 'nama_toko', colClass: 'col-12 col-md-6' },
        ]);
        appendRow(p2.body, [
            { name: 'nama_toko_parent', colClass: 'col-12 col-md-6' },
            { name: 'nama_pemilik', colClass: 'col-12 col-md-6' },
        ]);
        appendRow(p2.body, [
            { name: 'email', colClass: 'col-12 col-md-6' },
            { name: 'no_telepon', colClass: 'col-12 col-md-6' },
        ]);
        appendRow(p2.body, [
            { name: 'keterangan', colClass: 'col-12' },
        ]);
        const ketInput = getFieldInput('keterangan');
        if (ketInput) ketInput.rows = 3;
        container.appendChild(p2.box);

        // Wire JDE Customer Lookup on kode_customer_jde (matching Kontrak Toko UX & triggers)
        const jdeInput = getFieldInput('kode_customer_jde');
        if (jdeInput) {
            const ig = document.createElement('div');
            ig.className = 'jde-lookup-wrap';
            ig.style.display = 'flex';
            ig.style.gap = '8px';
            ig.style.alignItems = 'center';
            jdeInput.style.flex = '1 1 auto';
            jdeInput.parentNode.insertBefore(ig, jdeInput);
            ig.appendChild(jdeInput);

            const lookupBtn = document.createElement('button');
            lookupBtn.type = 'button';
            lookupBtn.className = 'btn btn-primary jde-lookup-btn';
            lookupBtn.id = 'btnRclJdeLookup';
            lookupBtn.innerHTML = '<i class="bi bi-search"></i> Cari';
            ig.appendChild(lookupBtn);

            const statusEl = document.createElement('div');
            statusEl.id = 'rclJdeStatus';
            statusEl.className = 'jde-lookup-alert alert small mt-2 mb-0 py-1.5 px-2.5';
            statusEl.style.display = 'none';
            ig.parentNode.appendChild(statusEl);

            let activeJdeAbort = null;
            let latestJdeSeq = 0;
            let lastLookedUpCode = '';

            function formatIndonesianMobile(val) {
                if (!val) return '';
                let digits = String(val).trim().replace(/[^0-9]/g, '');
                if (digits.startsWith('62')) {
                    digits = '0' + digits.slice(2);
                }
                return digits || String(val).trim();
            }

            function setFieldVal(fieldName, val) {
                const el = getFieldInput(fieldName);
                if (!el) return;
                const cleanVal = String(val || '').trim();
                if (!cleanVal || cleanVal === '-' || cleanVal === '—') return;
                el.value = cleanVal;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }

            async function performJdeLookup(force = false) {
                const code = (jdeInput.value || '').trim();
                if (!code) {
                    if (force) {
                        statusEl.style.display = 'block';
                        statusEl.className = 'jde-lookup-alert alert alert-warning small mt-2 mb-0 py-1.5 px-2.5';
                        statusEl.innerHTML = '<i class="bi bi-exclamation-triangle me-1"></i> Silakan masukkan Kode Customer JDE (contoh: 100228).';
                    }
                    return;
                }
                if (!force && code === lastLookedUpCode) return;

                if (activeJdeAbort) {
                    activeJdeAbort.abort();
                }
                activeJdeAbort = new AbortController();
                const seq = ++latestJdeSeq;
                lastLookedUpCode = code;

                lookupBtn.disabled = true;
                lookupBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Mencari...';
                statusEl.style.display = 'block';
                statusEl.className = 'jde-lookup-alert alert alert-light border small mt-2 mb-0 py-1.5 px-2.5 text-muted';
                statusEl.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Mencari data customer di JDE...';

                try {
                    const resp = await fetch(`/api/lookup/jde-customer/?code=${encodeURIComponent(code)}`, {
                        signal: activeJdeAbort.signal,
                    });
                    const data = await resp.json();
                    if (seq !== latestJdeSeq) return;

                    if (resp.ok && data.success && data.customer) {
                        const c = data.customer;
                        setFieldVal('nama_customer', c.nama_customer || c.nama_toko);
                        setFieldVal('nama_toko', c.nama_toko);
                        setFieldVal('nama_toko_parent', c.nama_toko_parent);
                        setFieldVal('nama_pemilik', c.nama_pemilik);
                        setFieldVal('email', c.email);
                        if (c.no_telepon) {
                            setFieldVal('no_telepon', formatIndonesianMobile(c.no_telepon));
                        }
                        statusEl.className = 'jde-lookup-alert alert alert-success small mt-2 mb-0 py-1.5 px-2.5';
                        statusEl.innerHTML = `<i class="bi bi-check-circle-fill me-1"></i> Data JDE ditemukan: <strong>${c.nama_toko || code}</strong>${c.kota ? ' (' + c.kota + ')' : ''}`;
                    } else {
                        statusEl.className = 'jde-lookup-alert alert alert-warning small mt-2 mb-0 py-1.5 px-2.5';
                        statusEl.innerHTML = `<i class="bi bi-info-circle me-1"></i> ${data.message || 'Customer tidak ditemukan di JDE, silakan isi manual.'}`;
                    }
                } catch (err) {
                    if (err && err.name === 'AbortError') return;
                    if (seq !== latestJdeSeq) return;
                    statusEl.className = 'jde-lookup-alert alert alert-danger small mt-2 mb-0 py-1.5 px-2.5';
                    statusEl.innerHTML = '<i class="bi bi-x-circle me-1"></i> Gagal menghubungi layanan JDE. Silakan isi manual.';
                } finally {
                    if (seq === latestJdeSeq) {
                        lookupBtn.disabled = false;
                        lookupBtn.innerHTML = '<i class="bi bi-search me-1"></i> Cari';
                    }
                }
            }

            lookupBtn.addEventListener('click', function () {
                performJdeLookup(true);
            });

            jdeInput.addEventListener('keydown', function (e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    performJdeLookup(true);
                }
            });
        }

        // 03 — Informasi Sales Order
        const p3 = createPanel('03', 'Informasi Sales Order', '');
        appendRow(p3.body, [
            { name: 'nomor_so', colClass: 'col-12 col-md-6' },
            { name: 'jenis_so', colClass: 'col-12 col-md-6' },
        ]);
        appendRow(p3.body, [
            { name: 'total_so', colClass: 'col-12 col-md-6' },
            { name: 'jenis_hold', colClass: 'col-12 col-md-6' },
        ]);

        // Rp prefix & thousand separator formatting for total_so
        const totalSoInput = getFieldInput('total_so');
        if (totalSoInput) {
            const igSo = document.createElement('div');
            igSo.className = 'input-group';
            totalSoInput.parentNode.insertBefore(igSo, totalSoInput);
            const rpPrefix = document.createElement('span');
            rpPrefix.className = 'input-group-text bg-light fw-semibold text-secondary';
            rpPrefix.textContent = 'Rp';
            igSo.appendChild(rpPrefix);
            igSo.appendChild(totalSoInput);

            function formatRupiahDigits(val) {
                const digits = String(val || '').replace(/[^\d]/g, '');
                if (!digits) return '';
                return digits.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
            }
            if (totalSoInput.value) {
                totalSoInput.value = formatRupiahDigits(totalSoInput.value);
            }
            totalSoInput.addEventListener('input', function () {
                this.value = formatRupiahDigits(this.value);
            });
        }

        // Helper info bar below Section 03
        const holdHelper = document.createElement('div');
        holdHelper.className = 'alert alert-light border small text-secondary mb-0 mt-2 py-2 px-3';
        holdHelper.innerHTML =
            '<i class="bi bi-info-circle text-primary me-1"></i> ' +
            '<strong>C1</strong> = Credit Limit Hold &nbsp;|&nbsp; ' +
            '<strong>C2</strong> = TOP Hold &nbsp;|&nbsp; ' +
            '<strong>C1 + C2</strong> = Kedua jenis hold';
        p3.body.appendChild(holdHelper);
        container.appendChild(p3.box);

        // 04 — Lampiran (Dynamic Repeater Table)
        const p4 = createPanel('04', 'Lampiran', 'Unggah file pendukung pengajuan');
        const hiddenLampiran = getFieldInput('lampiran_dokumen');
        const hiddenGrp = getFieldGroup('lampiran_dokumen');
        if (hiddenGrp) {
            hiddenGrp.style.display = 'none';
            p4.body.appendChild(hiddenGrp);
        }

        let initialRows = [];
        const serverDraftScript =
            document.getElementById('active_server_revision_data') ||
            document.getElementById('active_server_draft_data');
        if (serverDraftScript && serverDraftScript.textContent) {
            try {
                const parsedData = JSON.parse(serverDraftScript.textContent);
                if (Array.isArray(parsedData && parsedData.lampiran_dokumen)) {
                    initialRows = parsedData.lampiran_dokumen;
                }
            } catch (_) {
                initialRows = [];
            }
        }
        if (!initialRows.length && hiddenLampiran && hiddenLampiran.value && hiddenLampiran.value.trim().startsWith('[')) {
            try {
                initialRows = JSON.parse(hiddenLampiran.value);
            } catch (_) {
                initialRows = [];
            }
        }
        if (!initialRows.length) {
            initialRows = [{ nama_lampiran: '' }, { nama_lampiran: '' }];
        }

        const tableWrap = document.createElement('div');
        tableWrap.className = 'table-responsive';
        tableWrap.innerHTML = `
            <table class="table wf-table-dynamic align-middle mb-2" id="rclLampiranTable">
                <thead>
                    <tr>
                        <th style="width: 46%;">Nama Lampiran</th>
                        <th style="width: 44%;">Upload File</th>
                        <th style="width: 10%; text-align: right;">Aksi</th>
                    </tr>
                </thead>
                <tbody></tbody>
            </table>
            <button type="button" class="btn btn-sm btn-wf-add" id="btnAddRclLampiran">
                <i class="bi bi-plus-lg me-1"></i> + Lampiran
            </button>
        `;
        p4.body.appendChild(tableWrap);
        container.appendChild(p4.box);

        // Mount panels inside form-fields-wrapper (remove leftover empty Crispy row wrappers)
        Array.from(fieldsWrapper.children).forEach((child) => {
            if (child.tagName === 'INPUT' && child.type === 'hidden') return;
            child.remove();
        });
        container.style.marginTop = '0';
        fieldsWrapper.appendChild(container);

        const tbody = p4.body.querySelector('#rclLampiranTable tbody');
        const addBtn = p4.body.querySelector('#btnAddRclLampiran');

        function syncLampiranJson() {
            if (!hiddenLampiran) return;
            const rowsData = [];
            tbody.querySelectorAll('tr').forEach((tr, idx) => {
                const nameInput = tr.querySelector('.rcl-lampiran-nama');
                const fileInput = tr.querySelector('.rcl-lampiran-file');
                if (fileInput) {
                    fileInput.name = `rcl_lampiran_file_${idx}`;
                }
                const existingPath = tr.dataset.existingPath || '';
                const existingFilename = tr.dataset.existingFilename || '';
                const fileObj = fileInput && fileInput.files && fileInput.files[0];
                rowsData.push({
                    index: idx,
                    nama_lampiran: nameInput ? nameInput.value.trim() : '',
                    filename: fileObj ? fileObj.name : existingFilename,
                    path: fileObj ? '' : existingPath,
                });
            });
            hiddenLampiran.value = JSON.stringify(rowsData);
        }

        function addLampiranRow(item = {}) {
            const tr = document.createElement('tr');
            if (item.path) tr.dataset.existingPath = item.path;
            if (item.filename) tr.dataset.existingFilename = item.filename;

            const existingBadge = item.filename
                ? `<div class="small text-success mt-1"><i class="bi bi-paperclip me-1"></i>${item.filename}</div>`
                : '';

            tr.innerHTML = `
                <td>
                    <input type="text" class="form-control form-control-sm rcl-lampiran-nama"
                           placeholder="Contoh: PO Customer / History Pembayaran"
                           value="${(item.nama_lampiran || '').replace(/"/g, '&quot;')}">
                </td>
                <td>
                    <input type="file" class="form-control form-control-sm rcl-lampiran-file">
                    ${existingBadge}
                </td>
                <td class="text-end">
                    <button type="button" class="btn btn-sm btn-outline-danger rcl-lampiran-del" title="Hapus baris">
                        <i class="bi bi-trash3"></i>
                    </button>
                </td>
            `;

            tr.querySelector('.rcl-lampiran-nama').addEventListener('input', syncLampiranJson);
            tr.querySelector('.rcl-lampiran-file').addEventListener('change', syncLampiranJson);
            tr.querySelector('.rcl-lampiran-del').addEventListener('click', function () {
                if (tbody.querySelectorAll('tr').length <= 1) {
                    tr.querySelector('.rcl-lampiran-nama').value = '';
                    tr.querySelector('.rcl-lampiran-file').value = '';
                    delete tr.dataset.existingPath;
                    delete tr.dataset.existingFilename;
                } else {
                    tr.remove();
                }
                syncLampiranJson();
            });

            tbody.appendChild(tr);
            syncLampiranJson();
        }

        initialRows.forEach((r) => addLampiranRow(r));
        addBtn.addEventListener('click', () => addLampiranRow({}));

        formEl.addEventListener('submit', function () {
            syncLampiranJson();
        });
    });
})();

