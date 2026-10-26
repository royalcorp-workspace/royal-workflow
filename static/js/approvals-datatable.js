/**
 * approvals-datatable.js
 * Enterprise DataTables Controller for Approvals Inbox and Approval History.
 * Handles server-side pagination, search debouncing, custom columns, and batch operations.
 */

(function($) {
    'use strict';

    // Utility: Format date and time
    function formatDateTime(data, type) {
        if (type === 'sort' || type === 'type' || !data || data === '—') return data;
        try {
            var parts = data.split(' ');
            if (parts.length === 2) {
                var dateParts = parts[0].split('-');
                if (dateParts.length === 3) {
                    var year = dateParts[0];
                    var monthIdx = parseInt(dateParts[1], 10) - 1;
                    var day = dateParts[2];
                    var months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
                    var monthName = months[monthIdx] || dateParts[1];
                    return '<span class="text-nowrap text-secondary" style="font-size: 12.5px;">' + day + ' ' + monthName + ' ' + year + ', <span class="text-muted">' + parts[1] + '</span></span>';
                }
            }
        } catch(e) {}
        return '<span class="text-nowrap text-secondary" style="font-size: 12.5px;">' + data + '</span>';
    }

    // Utility: Debounce function for input events
    function debounce(func, wait) {
        var timeout;
        return function() {
            var context = this, args = arguments;
            clearTimeout(timeout);
            timeout = setTimeout(function() {
                func.apply(context, args);
            }, wait);
        };
    }

    // Custom Pagination Renderer
    function renderCustomPagination(table, pageLenKey) {
        var info = table.page.info();
        var entityName = table.table().node().id === 'completedTable' ? 'submissions' : 'approvals';

        // 1. Info text
        var infoText = 'Showing ' + (info.recordsTotal > 0 ? (info.start + 1) : 0) + ' to ' + info.end + ' of ' + info.recordsDisplay + ' ' + entityName;
        if (info.recordsTotal !== info.recordsDisplay) {
            infoText += ' (filtered from ' + info.recordsTotal + ' total)';
        }
        $('#footerInfoSlot').html('<span class="dataTables_info">' + infoText + '</span>');

        // 2. Length Selector + Page Buttons
        var $controls = $('<div class="d-flex align-items-center gap-3"></div>');

        var lengthHtml = '<div class="d-flex align-items-center gap-2 me-1">' +
            '<label class="text-muted small mb-0" style="font-size: 12px;">Show:</label>' +
            '<select class="form-select form-select-sm page-len-select" id="customLengthSelect">' +
            '<option value="10">10</option>' +
            '<option value="25">25</option>' +
            '<option value="50">50</option>' +
            '<option value="100">100</option>' +
            '</select>' +
            '</div>';
        var $lengthSelect = $(lengthHtml);
        $lengthSelect.find('select').val(table.page.len());
        $lengthSelect.find('select').on('change', function() {
            var len = parseInt($(this).val(), 10);
            table.page.len(len).draw();
            try { localStorage.setItem(pageLenKey, len); } catch(e) {}
        });
        $controls.append($lengthSelect);

        // Pagination buttons
        var totalPages = info.pages;
        var currentPage = info.page;
        var $ul = $('<ul class="pagination pagination-sm mb-0"></ul>');

        // Previous button
        var $prevLi = $('<li class="page-item ' + (currentPage === 0 ? 'disabled' : '') + '"><a class="page-link" href="#">&lsaquo;</a></li>');
        $prevLi.find('a').on('click', function(e) {
            e.preventDefault();
            if (currentPage > 0) table.page('previous').draw('page');
        });
        $ul.append($prevLi);

        // Page numbers window
        var startP = Math.max(0, currentPage - 2);
        var endP = Math.min(totalPages, startP + 5);
        if (endP - startP < 5) {
            startP = Math.max(0, endP - 5);
        }

        for (var p = startP; p < endP; p++) {
            var activeClass = p === currentPage ? 'active' : '';
            var $pLi = $('<li class="page-item ' + activeClass + '"><a class="page-link" href="#">' + (p + 1) + '</a></li>');
            (function(pageIdx) {
                $pLi.find('a').on('click', function(e) {
                    e.preventDefault();
                    table.page(pageIdx).draw('page');
                });
            })(p);
            $ul.append($pLi);
        }

        // Next button
        var $nextLi = $('<li class="page-item ' + (currentPage >= totalPages - 1 || totalPages === 0 ? 'disabled' : '') + '"><a class="page-link" href="#">&rsaquo;</a></li>');
        $nextLi.find('a').on('click', function(e) {
            e.preventDefault();
            if (currentPage < totalPages - 1) table.page('next').draw('page');
        });
        $ul.append($nextLi);

        $controls.append($ul);
        $('#footerControlsSlot').empty().append($controls);
    }

    // Column Picker Setup
    function setupColumnPicker(table, colIndexMap, colPrefsKey) {
        var $picker = $('#colPickerDropdown');
        if (!$picker.length) return;

        $('#colPickerSlot').append($picker);
        $picker.removeClass('d-none');

        var savedCols = [];
        try {
            var stored = localStorage.getItem(colPrefsKey);
            if (stored) savedCols = JSON.parse(stored);
        } catch(e) { savedCols = []; }

        function adjustTable() {
            table.table().node().style.width = '';
            table.columns.adjust().draw(false);
        }

        var anyRestored = false;
        savedCols.forEach(function(fieldName) {
            if (colIndexMap[fieldName] !== undefined) {
                table.column(colIndexMap[fieldName]).visible(true, false);
                $('#col_chk_' + fieldName).prop('checked', true);
                anyRestored = true;
            }
        });
        if (anyRestored) {
            adjustTable();
        }

        function updateToggleAllLabel() {
            var total = $('.col-toggle-chk').length;
            var checked = $('.col-toggle-chk:checked').length;
            $('#colToggleAll').text(checked === total ? 'Deselect all' : 'Select all');
        }
        updateToggleAllLabel();

        $('#colToggleAll').on('click', function() {
            var allChecked = $('.col-toggle-chk:checked').length === $('.col-toggle-chk').length;
            $('.col-toggle-chk').each(function() {
                var fieldName = $(this).data('field');
                if (colIndexMap[fieldName] !== undefined) {
                    $(this).prop('checked', !allChecked);
                    table.column(colIndexMap[fieldName]).visible(!allChecked, false);
                }
            });
            adjustTable();
            var visible = !allChecked
                ? $('.col-toggle-chk').map(function() { return $(this).data('field'); }).get()
                : [];
            try { localStorage.setItem(colPrefsKey, JSON.stringify(visible)); } catch(e) {}
            updateToggleAllLabel();
        });

        $(document).on('change', '.col-toggle-chk', function() {
            var fieldName = $(this).data('field');
            if (colIndexMap[fieldName] !== undefined) {
                table.column(colIndexMap[fieldName]).visible(this.checked, false);
                adjustTable();
            }
            var visible = [];
            $('.col-toggle-chk:checked').each(function() { visible.push($(this).data('field')); });
            try { localStorage.setItem(colPrefsKey, JSON.stringify(visible)); } catch(e) {}
            updateToggleAllLabel();
        });
    }

    // Batch Selection Setup
    function setupBatchSelection(table) {
        function updateExportBtn() {
            var checked = $('.export-check:checked').length;
            $('#exportBtn').prop('disabled', checked === 0);
            $('#pdfExportBtn').prop('disabled', checked === 0);
            $('#selectedCount').text(checked > 0 ? '(' + checked + ' selected)' : '');
            var $drawer = $('#bulkDrawer');
            if ($drawer.length) {
                if (checked > 0) {
                    $drawer.addClass('visible');
                    $('#drawerSelectedBadge').text(checked);
                } else {
                    $drawer.removeClass('visible');
                }
            }
        }

        $('#selectAll').on('change', function() {
            var checked = $(this).prop('checked');
            if (table) {
                table.$('.export-check').prop('checked', checked);
            } else {
                $('.export-check').prop('checked', checked);
            }
            $('.export-check').trigger('change');
        });

        $(document).on('change', '.export-check', function() {
            updateExportBtn();
            if (!$(this).prop('checked')) {
                $('#selectAll').prop('checked', false);
            }
        });
    }

    // Initialization on DOM Ready
    $(document).ready(function() {
        var $approvalsTable = $('#approvalsTable');
        var $completedTable = $('#completedTable');

        if ($approvalsTable.length) {
            initApprovalsInboxTable($approvalsTable);
        } else if ($completedTable.length) {
            initCompletedApprovalsTable($completedTable);
        }
    });

    // ── Table 1: Approvals Inbox Table (#approvalsTable) ──
    function initApprovalsInboxTable($table) {
        var ajaxUrl = $table.data('ajax-url');
        var csrfToken = $table.data('csrf-token');
        var hasExport = String($table.data('has-export')) === 'true';
        var categorySlug = $table.data('category') || '';
        var formSlug = $table.data('form') || '';
        var activeRole = $table.data('role') || '';
        var pageLenKey = $table.data('page-length-key') || 'approvals_page_len';
        var colPrefsKey = $table.data('col-prefs-key') || ('approvals_col_prefs_' + formSlug);

        var savedPageLen = parseInt(localStorage.getItem(pageLenKey), 10) || 25;

        // Custom columns index map
        var colIndexMap = {};
        var extraColTargets = [];
        $table.find('thead th.extra-form-col').each(function() {
            var idx = $(this).index();
            extraColTargets.push(idx);
            colIndexMap[$(this).data('field')] = idx;
        });

        var actionColIdx = hasExport ? (6 + extraColTargets.length) : (5 + extraColTargets.length);
        var colDefs = [
            { orderable: false, targets: [actionColIdx] }
        ];
        if (hasExport) {
            colDefs.push({ orderable: false, targets: 0 });
        }
        if (extraColTargets.length) {
            colDefs.push({ visible: false, targets: extraColTargets, orderable: false });
        }

        var columnsConfig = [];
        if (hasExport) {
            columnsConfig.push({
                data: 'checkbox',
                name: '',
                orderable: false,
                className: 'text-center align-middle',
                render: function(data) {
                    return data ? data.replace('class="export-check"', 'class="form-check-input export-check"') : '';
                }
            });
        }

        columnsConfig.push(
            {
                data: 'form',
                name: 'submission__form_definition__name',
                className: 'align-middle',
                render: function(data, type, row) {
                    var catHtml = row.category || '—';
                    return '<div class="d-flex flex-column py-0.5">' +
                           '<span class="fw-semibold text-dark" style="font-size: 14px; line-height: 1.35;">' + data + '</span>' +
                           '<span class="text-muted small mt-1 d-inline-flex align-items-center" style="font-size: 12px;">' + catHtml + '</span>' +
                           '</div>';
                }
            },
            {
                data: 'submitter',
                name: 'submission__submitter__last_name',
                className: 'align-middle',
                render: function(data) {
                    return '<div class="d-flex align-items-center gap-2">' +
                           '<div class="bg-light text-secondary border rounded-circle d-flex align-items-center justify-content-center flex-shrink-0" style="width: 26px; height: 26px; font-size: 12px;">' +
                           '<i class="bi bi-person-fill"></i>' +
                           '</div>' +
                           '<span class="text-dark fw-medium" style="font-size: 13px;">' + data + '</span>' +
                           '</div>';
                }
            },
            {
                data: 'step_num',
                name: 'workflow_stage__name',
                className: 'align-middle',
                render: function(data) {
                    var cleaned = data ? data.replace(/^(Step \d+:\s*)(Step \d+:\s*)+/i, '$1') : '—';
                    return '<span class="text-dark fw-medium" style="font-size: 13px;">' + cleaned + '</span>';
                }
            },
            {
                data: 'assigned',
                name: 'assigned_group__name',
                className: 'align-middle',
                render: function(data) {
                    if (!data || data === '—') return '<span class="text-muted">—</span>';
                    return '<span class="badge bg-light text-dark border border-secondary-subtle px-2.5 py-1.5 fw-medium" style="font-size: 12px; letter-spacing: 0.1px;">' + data + '</span>';
                }
            },
            {
                data: 'submitted_at',
                name: 'submission__submitted_at',
                className: 'align-middle',
                render: formatDateTime
            }
        );

        // Append custom dynamic field columns
        $table.find('thead th.extra-form-col').each(function() {
            var fName = $(this).data('field');
            columnsConfig.push({ data: fName, name: '', orderable: false, className: 'align-middle' });
        });

        // Actions column
        columnsConfig.push({
            data: 'actions',
            name: '',
            orderable: false,
            className: 'text-end align-middle',
            render: function(data) {
                if (!data) return '';
                var reviewMatch = data.match(/href="([^"]+)"[^>]*>\s*<i[^>]*><\/i>\s*Review/i);
                var reviewUrl = reviewMatch ? reviewMatch[1] : '';
                if (!reviewUrl) {
                    var anyHref = data.match(/href="([^"]+)"/i);
                    reviewUrl = anyHref ? anyHref[1] : '#';
                }

                return '<div class="d-inline-flex align-items-center justify-content-end text-nowrap">' +
                       '<a href="' + reviewUrl + '" class="btn-action-review"><i class="bi bi-check-circle"></i> Review</a>' +
                       '</div>';
            }
        });

        var table = $table.DataTable({
            serverSide: true,
            processing: true,
            searchDelay: 400,
            ajax: {
                url: ajaxUrl,
                type: 'POST',
                data: function(d) {
                    d.csrfmiddlewaretoken = csrfToken;
                    if (categorySlug) d.category = categorySlug;
                    if (formSlug) d.form = formSlug;
                    if (activeRole && activeRole !== 'mine') d.role = activeRole;
                }
            },
            columns: columnsConfig,
            order: [[hasExport ? 5 : 4, 'desc']],
            columnDefs: colDefs,
            pageLength: savedPageLen,
            dom: 'tr',
            language: {
                search: '',
                searchPlaceholder: 'Search approvals...',
                emptyTable: 'No pending approvals found.',
                zeroRecords: 'No matching approvals found.',
                info: 'Showing _START_ to _END_ of _TOTAL_ approvals',
                infoEmpty: 'Showing 0 to 0 of 0 approvals',
                infoFiltered: '(filtered from _MAX_ total approvals)',
                processing: '<div class="text-center py-3"><div class="spinner-border spinner-border-sm text-secondary" role="status"></div> <span class="ms-1 small text-muted">Loading…</span></div>',
                paginate: {
                    first: '&laquo;',
                    last: '&raquo;',
                    next: '&rsaquo;',
                    previous: '&lsaquo;'
                }
            },
            drawCallback: function() {
                renderCustomPagination(table, pageLenKey);
            }
        });

        // Search Input listener with debounce
        $('#customSearchInput').on('keyup change', debounce(function() {
            table.search(this.value).draw();
        }, 400));

        setupColumnPicker(table, colIndexMap, colPrefsKey);
        setupBatchSelection(table);
    }

    // ── Table 2: Completed Approvals Table (#completedTable) ──
    function initCompletedApprovalsTable($table) {
        var ajaxUrl = $table.data('ajax-url');
        var csrfToken = $table.data('csrf-token');
        var hasExport = String($table.data('has-export')) === 'true';
        var categorySlug = $table.data('category') || '';
        var formSlug = $table.data('form') || '';
        var statusFilter = $table.data('status') || '';
        var pageLenKey = $table.data('page-length-key') || 'completed_page_len';
        var colPrefsKey = $table.data('col-prefs-key') || ('completed_col_prefs_' + formSlug);

        var savedPageLen = parseInt(localStorage.getItem(pageLenKey), 10) || 25;

        var colIndexMap = {};
        var extraColTargets = [];
        $table.find('thead th.extra-form-col').each(function() {
            var idx = $(this).index();
            extraColTargets.push(idx);
            colIndexMap[$(this).data('field')] = idx;
        });

        var actionColIdx = hasExport ? (6 + extraColTargets.length) : (5 + extraColTargets.length);
        var colDefs = [
            { orderable: false, targets: [actionColIdx] }
        ];
        if (hasExport) {
            colDefs.push({ orderable: false, targets: 0 });
        }
        if (extraColTargets.length) {
            colDefs.push({ visible: false, targets: extraColTargets, orderable: false });
        }

        var columnsConfig = [];
        if (hasExport) {
            columnsConfig.push({
                data: 'checkbox',
                name: '',
                orderable: false,
                className: 'text-center align-middle',
                render: function(data) {
                    return data ? data.replace('class="export-check"', 'class="form-check-input export-check"') : '';
                }
            });
        }

        columnsConfig.push(
            {
                data: 'form',
                name: 'form_definition__name',
                className: 'align-middle',
                render: function(data, type, row) {
                    var catHtml = row.category || '—';
                    return '<div class="d-flex flex-column py-0.5">' +
                           '<span class="fw-semibold text-dark" style="font-size: 14px; line-height: 1.35;">' + data + '</span>' +
                           '<span class="text-muted small mt-1 d-inline-flex align-items-center" style="font-size: 12px;">' + catHtml + '</span>' +
                           '</div>';
                }
            },
            {
                data: 'submitter',
                name: 'submitter__last_name',
                className: 'align-middle',
                render: function(data) {
                    return '<div class="d-flex align-items-center gap-2">' +
                           '<div class="bg-light text-secondary border rounded-circle d-flex align-items-center justify-content-center flex-shrink-0" style="width: 26px; height: 26px; font-size: 12px;">' +
                           '<i class="bi bi-person-fill"></i>' +
                           '</div>' +
                           '<span class="text-dark fw-medium" style="font-size: 13px;">' + data + '</span>' +
                           '</div>';
                }
            },
            {
                data: 'status',
                name: 'status',
                orderable: false,
                className: 'align-middle'
            },
            {
                data: 'submitted_at',
                name: 'submitted_at',
                className: 'align-middle',
                render: formatDateTime
            },
            {
                data: 'completed_at',
                name: 'completed_at',
                className: 'align-middle',
                render: formatDateTime
            }
        );

        // Custom extra field columns
        $table.find('thead th.extra-form-col').each(function() {
            var fName = $(this).data('field');
            columnsConfig.push({ data: fName, name: '', orderable: false, className: 'align-middle' });
        });

        // Actions column
        columnsConfig.push({
            data: 'actions',
            name: '',
            orderable: false,
            className: 'text-end align-middle',
            render: function(data) {
                if (!data) return '';
                var viewMatch = data.match(/href="([^"]+)"[^>]*>\s*<i[^>]*><\/i>\s*View/i);
                var viewUrl = viewMatch ? viewMatch[1] : '';
                if (!viewUrl) {
                    var anyHref = data.match(/href="([^"]+)"/i);
                    viewUrl = anyHref ? anyHref[1] : '#';
                }
                return '<div class="d-inline-flex align-items-center justify-content-end gap-2 text-nowrap">' +
                       '<a href="' + viewUrl + '" class="btn-action-view"><i class="bi bi-eye"></i> View</a>' +
                       '</div>';
            }
        });

        var completedColIdx = -1;
        for (var c = 0; c < columnsConfig.length; c++) {
            if (columnsConfig[c].name === 'completed_at' || columnsConfig[c].data === 'completed_at') {
                completedColIdx = c;
                break;
            }
        }
        if (completedColIdx === -1) {
            completedColIdx = hasExport ? 5 : 4;
        }

        var table = $table.DataTable({
            serverSide: true,
            processing: true,
            searchDelay: 400,
            ajax: {
                url: ajaxUrl,
                type: 'POST',
                data: function(d) {
                    d.csrfmiddlewaretoken = csrfToken;
                    if (categorySlug) d.category = categorySlug;
                    if (formSlug) d.form = formSlug;
                    if (statusFilter) d.status = statusFilter;
                }
            },
            columns: columnsConfig,
            order: [[completedColIdx, 'desc']],
            columnDefs: colDefs,
            pageLength: savedPageLen,
            dom: 'tr',
            language: {
                search: '',
                searchPlaceholder: 'Search submissions...',
                emptyTable: 'No completed submissions found.',
                zeroRecords: 'No matching submissions found.',
                info: 'Showing _START_ to _END_ of _TOTAL_ submissions',
                infoEmpty: 'Showing 0 to 0 of 0 submissions',
                infoFiltered: '(filtered from _MAX_ total submissions)',
                processing: '<div class="text-center py-3"><div class="spinner-border spinner-border-sm text-secondary" role="status"></div> <span class="ms-1 small text-muted">Loading…</span></div>',
                paginate: {
                    first: '&laquo;',
                    last: '&raquo;',
                    next: '&rsaquo;',
                    previous: '&lsaquo;'
                }
            },
            drawCallback: function() {
                renderCustomPagination(table, pageLenKey);
            }
        });

        // Search Input listener with debounce
        $('#customSearchInput').on('keyup change', debounce(function() {
            table.search(this.value).draw();
        }, 400));

        setupColumnPicker(table, colIndexMap, colPrefsKey);
        setupBatchSelection(table);
    }

    // ── Global Handlers for Bulk PDF Export ──
    window.submitBulkPdfMerged = function() {
        var pdfForm = document.getElementById('bulkPdfExportForm');
        var container = document.getElementById('pdfSubmissionIds');
        if (!pdfForm || !container) return;

        container.innerHTML = '';
        document.querySelectorAll('.export-check:checked').forEach(function(cb) {
            var inp = document.createElement('input');
            inp.type = 'hidden';
            inp.name = 'submission_ids';
            inp.value = cb.value;
            container.appendChild(inp);
        });
        pdfForm.requestSubmit();
    };

    window.submitBulkPdfSequential = function() {
        var ids = [];
        document.querySelectorAll('.export-check:checked').forEach(function(cb) {
            ids.push(cb.value);
        });
        if (!ids.length) return;

        var total = ids.length;
        var index = 0;
        var overlay = document.getElementById('loadingOverlay');
        var msg = document.getElementById('loadingMessage');
        if (overlay) overlay.classList.add('active');

        var tableEl = document.getElementById('approvalsTable') || document.getElementById('completedTable');
        var singleUrlPattern = (tableEl && tableEl.dataset.bulkPdfSingleUrl) ? tableEl.dataset.bulkPdfSingleUrl : '/forms/submissions/0/pdf/';

        function downloadNext() {
            if (index >= ids.length) {
                if (overlay) overlay.classList.remove('active');
                return;
            }
            var id = ids[index++];
            if (msg) msg.textContent = 'Downloading PDF ' + index + ' of ' + total + '…';
            var url = singleUrlPattern.replace('/0/', '/' + id + '/');
            if (url.indexOf('?') === -1) {
                url += '?download=1';
            } else {
                url += '&download=1';
            }
            fetch(url)
                .then(function(resp) {
                    if (!resp.ok) throw new Error('HTTP ' + resp.status);
                    var cd = resp.headers.get('Content-Disposition') || '';
                    var m = cd.match(/filename[^;=\n]*=["']?([^"';\n]+)["']?/i);
                    var filename = (m && m[1]) ? m[1].replace(/["']/g, '').trim() : ('SPK_Submission_' + id + '.pdf');
                    if (!filename.toLowerCase().endsWith('.pdf')) {
                        filename += '.pdf';
                    }
                    return resp.blob().then(function(blob) { return { blob: blob, name: filename }; });
                })
                .then(function(data) {
                    var blobUrl = window.URL.createObjectURL(data.blob);
                    var link = document.createElement('a');
                    link.href = blobUrl;
                    link.setAttribute('download', data.name);
                    link.download = data.name;
                    document.body.appendChild(link);
                    link.click();
                    link.remove();
                    setTimeout(function() { window.URL.revokeObjectURL(blobUrl); }, 10000);
                    setTimeout(downloadNext, 800);
                })
                .catch(function(err) {
                    console.error('PDF download failed for submission ' + id + ':', err);
                    setTimeout(downloadNext, 800);
                });
        }
        downloadNext();
    };

})(jQuery);
