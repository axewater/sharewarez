document.addEventListener("DOMContentLoaded", function() {
    console.log("Document loaded.");

    // Existing function to close all submenus
    function closeAllSubmenus() {
        document.querySelectorAll('.submenu').forEach(submenu => {
            submenu.style.display = 'none';
        });
        document.querySelectorAll('.has-submenu').forEach(item => {
            item.classList.remove('open');
        });
    }

    closeAllSubmenus();

    // Toggle sidebar
    const toggleSidebar = document.getElementById("toggleSidebar");
    if (toggleSidebar) {
        toggleSidebar.addEventListener("click", function() {
            console.log("Sidebar toggle clicked.");
            document.getElementById("sidebar").classList.toggle("collapsed");
            document.getElementById("content").classList.toggle("collapsed");
            closeAllSubmenus();
        });
    }

    // User account icon click event
    const userAccountIcon = document.getElementById('userAccountIcon');
    if (userAccountIcon) {
        userAccountIcon.addEventListener('click', function() {
            console.log("User account icon clicked.");

            var menu = document.getElementById('userAccountMenu');
            var icon = document.querySelector('.user-expand-icon');
        
            if (menu.classList.contains('hide')) {
                console.log("Menu is hidden, showing now.");
                menu.classList.remove('hide');
                menu.classList.add('show');
                icon.style.transform = 'rotate(180deg)';
            } else {
                console.log("Menu is shown, hiding now.");
                menu.classList.remove('show');
                menu.classList.add('hide');
                icon.style.transform = 'rotate(0deg)';
            }
        });
    }

    document.addEventListener('click', function(event) {
        const userAccountIcon = document.getElementById('userAccountIcon');
        const userAccountMenu = document.getElementById('userAccountMenu');
        const userExpandIcon = document.querySelector('.user-expand-icon');
        
        if (userAccountIcon && userAccountMenu && userExpandIcon) {
            var isClickInsideIcon = userAccountIcon.contains(event.target);
            var isClickInsideMenu = userAccountMenu.contains(event.target);

            if (!isClickInsideIcon && !isClickInsideMenu) {
                // If the click is outside the userAccountIcon and userAccountMenu, close the menu
                userAccountMenu.classList.add('hide');
                userAccountMenu.classList.remove('show');
                userExpandIcon.style.transform = 'rotate(0deg)';
            }
        }
    });
    

    // Handling click events on sidebar links with submenu
    document.querySelectorAll('.sidebar-link.has-submenu').forEach(item => {
        item.addEventListener('click', function(e) {
            console.log("Submenu item clicked.");
            closeAllSubmenus();
            
            e.preventDefault();

            let nextElement = this.nextElementSibling;
            if (nextElement && nextElement.classList.contains('submenu')) {
                this.classList.toggle('open');
                nextElement.style.display = nextElement.style.display === 'block' ? 'none' : 'block';
            }

            e.stopPropagation();
        });
    });
});

// Additional checks for visibility of elements based on URL
if (window.location.pathname !== '/library') {
    console.log("Not on '/library' page, adjusting visibility.");
    const filterContainer = document.querySelector('.container-filtersandsort');
    if (filterContainer) {
        filterContainer.style.visibility = 'hidden';
    }
}

// Preferences modal loading functionality
const prefsToggle = document.querySelector('[data-bs-toggle="modal"][data-bs-target="#preferencesModal"]');
if (prefsToggle) {
    prefsToggle.addEventListener('click', function(e) {
        e.preventDefault();
        
        fetch(prefsToggle.dataset.preferencesUrl)
            .then(response => response.text())
            .then(html => {
                document.getElementById('preferencesModalContainer').innerHTML = html;
                new bootstrap.Modal(document.getElementById('preferencesModal')).show();
            })
            .catch(error => {
                console.error('Error:', error);
                $.notify("Error loading preferences", "error");
            });
    });
}