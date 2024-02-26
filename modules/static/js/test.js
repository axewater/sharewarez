document.addEventListener("DOMContentLoaded", function() {
    var activeTab = "{{ active_tab }}";
    
    console.log("Active tab:", activeTab);
    if (activeTab === 'manual') {
        console.log("manual tab active");
        var manualTab = new bootstrap.Tab(document.querySelector('#manualScan-tab'));
        manualTab.show();
    } else if (activeTab === 'unmatched') {
        console.log("unmatched tab active");
        var unmatchedTab = new bootstrap.Tab(document.querySelector('#unmatchedFolders-tab'));
        unmatchedTab.show();
    } else {
        console.log("auto tab active");
        // Ensure the Auto Scan tab is shown by default or when 'auto' is the active tab
        var autoTab = new bootstrap.Tab(document.querySelector('#autoScan-tab'));
        autoTab.show();
    }
});