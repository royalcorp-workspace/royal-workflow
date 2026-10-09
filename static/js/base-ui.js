/**
 * Royal Workflow: Base UI Helper Scripts
 */
document.addEventListener('DOMContentLoaded', function() {
    // Form submission loading overlay handler
    document.querySelectorAll('form[method="post"]').forEach(function(form) {
        form.addEventListener('submit', function() {
            if (form.hasAttribute('data-no-spinner')) return;
            var overlay = document.getElementById('loadingOverlay');
            var msg = document.getElementById('loadingMessage');
            if (overlay) {
                overlay.classList.add('active');
                if (msg && form.dataset.loadingMessage) {
                    msg.textContent = form.dataset.loadingMessage;
                }
            }
        });
    });

    // Mobile sidebar drawer toggle handler
    var sidebarToggle = document.getElementById('mobileSidebarToggle');
    var sidebarWrapper = document.querySelector('.sidebar-wrapper');
    var sidebarBackdrop = document.getElementById('sidebarBackdrop');

    if (sidebarToggle && sidebarWrapper) {
        sidebarToggle.addEventListener('click', function(e) {
            e.stopPropagation();
            sidebarWrapper.classList.toggle('show');
            if (sidebarBackdrop) {
                sidebarBackdrop.classList.toggle('show');
            }
        });
    }

    if (sidebarBackdrop && sidebarWrapper) {
        sidebarBackdrop.addEventListener('click', function() {
            sidebarWrapper.classList.remove('show');
            sidebarBackdrop.classList.remove('show');
        });
    }
});
