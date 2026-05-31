/**
 * StockX Pro — Market Search & Real-time Filtering
 * Provides client-side search and debounced industry filtering.
 */

document.addEventListener('DOMContentLoaded', function() {
    // Look for the search form and add live filtering if present
    const searchInput = document.querySelector('.search-form-inline input[name="q"]');
    const industrySelect = document.querySelector('.search-form-inline select[name="industry"]');

    // Auto-submit on industry change for better UX
    if (industrySelect) {
        industrySelect.addEventListener('change', function() {
            this.form.submit();
        });
    }

    // Debounced search: submit after user stops typing for 500ms
    if (searchInput) {
        let debounceTimer;
        const originalForm = searchInput.closest('form');

        searchInput.addEventListener('input', function() {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(function() {
                originalForm.submit();
            }, 500);
        });

        // Prevent normal form submit to avoid page reload during debounce
        originalForm.addEventListener('submit', function(e) {
            clearTimeout(debounceTimer);
        });
    }

    // ===== Table Row Click: Navigate to Stock Detail =====
    const marketTable = document.querySelector('.stockx-table');
    if (marketTable) {
        marketTable.addEventListener('click', function(e) {
            const row = e.target.closest('tr');
            if (!row) return;

            // Find the detail link in the row
            const detailLink = row.querySelector('a[href*="/stock/"]');
            if (detailLink) {
                // Don't navigate if user clicked the button itself
                if (e.target.closest('a')) return;
                window.location.href = detailLink.href;
            }
        });

        // Add cursor pointer to table rows with links
        const rows = marketTable.querySelectorAll('tbody tr');
        rows.forEach(function(row) {
            if (row.querySelector('a[href*="/stock/"]')) {
                row.style.cursor = 'pointer';
            }
        });
    }
});