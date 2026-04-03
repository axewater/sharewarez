/**
 * Integrations Tabs Controller
 *
 * Handles tab switching with URL fragment support for persistent tab state.
 * All form functionality is handled by individual integration JS files.
 */

$(document).ready(function() {
    console.log('Integrations tabs controller loaded');

    // Map fragments to tab IDs
    const fragmentTabMap = {
        '#email': 'email-tab',
        '#igdb': 'igdb-tab',
        '#discord': 'discord-tab'
    };

    // Initialize Bootstrap tabs
    const triggerTabList = [].slice.call(document.querySelectorAll('#integrationTabs button[data-bs-toggle="tab"]'));

    triggerTabList.forEach(function (triggerEl) {
        triggerEl.addEventListener('shown.bs.tab', function (event) {
            const activeTab = event.target;
            const targetPaneId = activeTab.getAttribute('data-bs-target');

            console.log('Tab switched to:', targetPaneId);

            // Update URL fragment when user manually switches tabs
            const newFragment = targetPaneId; // e.g. "#email", "#discord"
            if (window.location.hash !== newFragment) {
                history.replaceState(null, null, newFragment);
            }
        });
    });

    // Activate tab based on URL fragment
    function activateTabFromFragment() {
        const hash = window.location.hash || '#email'; // Default to email tab
        const tabId = fragmentTabMap[hash];

        if (tabId) {
            const tabElement = document.getElementById(tabId);
            if (tabElement) {
                // Use Bootstrap's tab API to activate the tab
                const tab = new bootstrap.Tab(tabElement);
                tab.show();
                console.log('Activated tab from fragment:', hash, '-> tab:', tabId);
                return true;
            }
        }

        // Fallback to email tab if fragment is invalid or missing
        const defaultTab = document.getElementById('email-tab');
        if (defaultTab) {
            const tab = new bootstrap.Tab(defaultTab);
            tab.show();
            console.log('Activated default email tab');
        }

        return false;
    }

    // Activate the correct tab on page load
    activateTabFromFragment();

    // Handle browser back/forward navigation
    window.addEventListener('hashchange', function() {
        console.log('Hash changed to:', window.location.hash);
        activateTabFromFragment();
    });

    console.log('Tab controller initialized with fragment support');
});