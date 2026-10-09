/**
 * submissions-datatable.js
 * Enterprise DataTables Controller for My Submissions.
 * Handles server-side pagination, status filters, search debouncing, and batch exports.
 */

(function($) {
    'use strict';

    // Utility: Debounce function for search input
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

        // 1. Info text
        var infoText = 'Showing ' + (info.recordsTotal > 0 ? (info.start + 1) : 0) + ' to ' + info.end + ' of ' + info.recordsDisplay + ' submissions';
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
    function setupColumnPicker(table, formSlug) {
        var $picker = $('#colPickerDropdown');
        if (!$picker.length) return;

        $('#colPickerSlot').append($picker);
        $picker.removeClass('d-none');

        var colPrefsKey = 'submissions_col_prefs_' + formSlug;
        var colIndexMap = {};
        $('#submissionsTable thead th.extra-form-col').each(function() {
            var idx = $(this).index();
            colIndexMap[$(this).data('field')] = idx;
        });

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

    // Batch Export Setup
    function setupBatchExport(table) {
        function updateExportBtn() {
            var checked = $('.export-check:checked').length;
            $('#exportBtn').prop('disabled', checked === 0);
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

    // Main Initializer
    $(document).ready(function() {
        var $table = $('#submissionsTable');
        if (!$table.length) return;

        var ajaxUrl = $table.data('ajax-url');
        var csrfToken = $table.data('csrf-token');
        var hasExport = String($table.data('has-export')) === 'true';
        var categorySlug = $table.data('category') || '';
        var formSlug = $table.data('form') || '';
        var statusFilter = $table.data('status') || '';
        var pageLenKey = $table.data('page-length-key') || 'my_submissions_page_len';

        var savedPageLen = parseInt(localStorage.getItem(pageLenKey), 10) || 25;

        // Custom extra column mapping if any
        var extraColTargets = [];
        $table.find('thead th.extra-form-col').each(function() {
            extraColTargets.push($(this).index());
        });

        var actionColIdx = hasExport ? (5 + extraColTargets.length + 1) : (4 + extraColTargets.length + 1);
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
                className: 'text-center align-middle'
            });
        }

        columnsConfig.push(
            {
                data: 'id',
                name: 'id',
                className: 'align-middle',
                render: function(data) {
                    return '<span class="font-monospace fw-semibold text-secondary" style="font-size: 13px;">#' + data + '</span>';
                }
            },
            {
                data: 'form',
                name: 'form',
                className: 'align-middle',
                render: function(data, type, row) {
                    var catHtml = row.category || '—';
                    return '<div class="d-flex flex-column py-0.5">' +
                           '<span class="fw-bold text-dark" style="font-size: 14px; line-height: 1.35;">' + data + '</span>' +
                           '<span class="text-muted small mt-0.5 d-inline-flex align-items-center" style="font-size: 12px;">' + catHtml + '</span>' +
                           '</div>';
                }
            },
            {
                data: 'current_step',
                name: 'current_step',
                orderable: false,
                className: 'align-middle'
            },
            {
                data: 'status',
                name: 'status',
                className: 'align-middle'
            },
            {
                data: 'submitted_at',
                name: 'submitted_at',
                className: 'align-middle',
                render: function(data) {
                    return '<span class="small text-secondary" style="font-size: 12.5px;">' + data + '</span>';
                }
            }
        );

        // Dynamic form fields
        $table.find('thead th.extra-form-col').each(function() {
            var fName = $(this).data('field');
            columnsConfig.push({ data: fName, name: '', orderable: false, className: 'align-middle' });
        });

        // Actions column
        columnsConfig.push({
            data: 'actions',
            name: '',
            orderable: false,
            className: 'text-end align-middle'
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
                    if (statusFilter && statusFilter !== 'all') d.status = statusFilter;
                }
            },
            columns: columnsConfig,
            order: [[hasExport ? 5 : 4, 'desc']],
            columnDefs: colDefs,
            pageLength: savedPageLen,
            dom: 'tr',
            language: {
                search: '',
                searchPlaceholder: 'Search submissions...',
                emptyTable: 'No submissions found.',
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

        setupColumnPicker(table, formSlug);
        setupBatchExport(table);
    });

})(jQuery);
