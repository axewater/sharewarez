/**
 * Integrations Tabs Controller
 *
 * Minimal controller for handling tab switching in the integrations page.
 * All form functionality is handled by individual integration JS files.
 */

$(document).ready(function() {
    console.log('Integrations tabs controller loaded');

    // Initialize Bootstrap tabs - mostly handled by Bootstrap itself
    const triggerTabList = [].slice.call(document.querySelectorAll('#integrationTabs button[data-bs-toggle="tab"]'));

    triggerTabList.forEach(function (triggerEl) {
        triggerEl.addEventListener('shown.bs.tab', function (event) {
            const activeTab = event.target;
            const targetPaneId = activeTab.getAttribute('data-bs-target');

            console.log('Tab switched to:', targetPaneId);

            // Optional: Add any tab-specific initialization here if needed
            // All form functionality is handled by individual JS files
        });
    });

    // Handle active tab state on page load
    const activeTab = document.querySelector('#integrationTabs .nav-link.active');
    if (activeTab) {
        console.log('Active tab on load:', activeTab.getAttribute('data-bs-target'));
    }
});