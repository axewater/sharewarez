// Admin Attract Mode Settings JavaScript
// Handles the attract mode configuration form

document.addEventListener('DOMContentLoaded', function() {
    // Initialize form with settings from server
    loadSettingsIntoForm();

    // Set up event listeners
    setupEventListeners();

    // Initialize tooltips
    if (typeof $ !== 'undefined' && $.fn.tooltip) {
        $('[data-toggle="tooltip"]').tooltip();
    }
});

function loadSettingsIntoForm() {
    const settings = window.attractModeSettings;

    if (!settings) {
        console.error('No attract mode settings provided');
        return;
    }

    // Load general settings
    document.getElementById('attractModeEnabled').checked = settings.enabled || false;
    document.getElementById('idleTimeout').value = settings.idle_timeout || 60;
    updateTimeoutDisplay();

    // Load filter settings
    if (settings.settings && settings.settings.filters) {
        const filters = settings.settings.filters;

        // Library
        if (filters.library_uuid) {
            document.getElementById('filterLibrary').value = filters.library_uuid;
        }

        // Genres (multi-select)
        if (filters.genres && filters.genres.length > 0) {
            const genreSelect = document.getElementById('filterGenres');
            Array.from(genreSelect.options).forEach(option => {
                if (filters.genres.includes(parseInt(option.value))) {
                    option.selected = true;
                }
            });
        }

        // Themes (multi-select)
        if (filters.themes && filters.themes.length > 0) {
            const themeSelect = document.getElementById('filterThemes');
            Array.from(themeSelect.options).forEach(option => {
                if (filters.themes.includes(parseInt(option.value))) {
                    option.selected = true;
                }
            });
        }

        // Date range
        if (filters.date_from) {
            document.getElementById('filterDateFrom').value = filters.date_from;
        }
        if (filters.date_to) {
            document.getElementById('filterDateTo').value = filters.date_to;
        }
    }

    // Load autoplay settings
    if (settings.settings && settings.settings.autoplay) {
        const autoplay = settings.settings.autoplay;
        document.getElementById('autoplayEnabled').checked = autoplay.enabled !== false;
        document.getElementById('skipFirst').value = autoplay.skipFirst || 0;
        document.getElementById('skipAfter').value = autoplay.skipAfter || 0;
    }
}

function setupEventListeners() {
    // Idle timeout slider
    const idleTimeoutSlider = document.getElementById('idleTimeout');
    if (idleTimeoutSlider) {
        idleTimeoutSlider.addEventListener('input', updateTimeoutDisplay);
    }

    // Form submission
    const form = document.getElementById('attractModeForm');
    if (form) {
        form.addEventListener('submit', handleFormSubmit);
    }
}

function updateTimeoutDisplay() {
    const timeout = document.getElementById('idleTimeout').value;
    document.getElementById('timeoutDisplay').textContent = `${timeout} seconds`;
    document.getElementById('previewTimeout').textContent = timeout;
}

async function handleFormSubmit(event) {
    event.preventDefault();

    // Collect form data
    const formData = collectFormData();

    // Show loading state
    const submitButton = event.target.querySelector('button[type="submit"]');
    const originalText = submitButton.innerHTML;
    submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
    submitButton.disabled = true;

    try {
        // Get CSRF token
        const csrfToken = getCSRFToken();

        // Send data to server
        const response = await fetch('/admin/attract_mode_settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify(formData)
        });

        const result = await response.json();

        if (response.ok && result.success) {
            // Show success message
            showSuccessNotification();
        } else {
            // Show error message
            showErrorNotification(result.errors || [result.message || 'Failed to save settings']);
        }
    } catch (error) {
        console.error('Error saving attract mode settings:', error);
        showErrorNotification(['Network error: Failed to save settings']);
    } finally {
        // Restore button state
        submitButton.innerHTML = originalText;
        submitButton.disabled = false;
    }
}

function collectFormData() {
    // General settings
    const enabled = document.getElementById('attractModeEnabled').checked;
    const idleTimeout = parseInt(document.getElementById('idleTimeout').value);

    // Filter settings
    const libraryUuid = document.getElementById('filterLibrary').value || null;

    const genreSelect = document.getElementById('filterGenres');
    const genres = Array.from(genreSelect.selectedOptions).map(opt => parseInt(opt.value));

    const themeSelect = document.getElementById('filterThemes');
    const themes = Array.from(themeSelect.selectedOptions).map(opt => parseInt(opt.value));

    const dateFrom = document.getElementById('filterDateFrom').value ?
                     parseInt(document.getElementById('filterDateFrom').value) : null;
    const dateTo = document.getElementById('filterDateTo').value ?
                   parseInt(document.getElementById('filterDateTo').value) : null;

    // Autoplay settings
    const autoplayEnabled = document.getElementById('autoplayEnabled').checked;
    const skipFirst = parseInt(document.getElementById('skipFirst').value) || 0;
    const skipAfter = parseInt(document.getElementById('skipAfter').value) || 0;

    return {
        enabled: enabled,
        idle_timeout: idleTimeout,
        filters: {
            library_uuid: libraryUuid,
            genres: genres,
            themes: themes,
            date_from: dateFrom,
            date_to: dateTo
        },
        autoplay: {
            enabled: autoplayEnabled,
            skipFirst: skipFirst,
            skipAfter: skipAfter
        }
    };
}

function showSuccessNotification() {
    const notification = document.getElementById('settingsSavedNotification');
    const errorNotification = document.getElementById('settingsErrorNotification');

    // Hide error notification
    errorNotification.style.display = 'none';

    // Show success notification
    notification.style.display = 'block';

    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });

    // Hide after 5 seconds
    setTimeout(() => {
        notification.style.display = 'none';
    }, 5000);
}

function showErrorNotification(errors) {
    const notification = document.getElementById('settingsErrorNotification');
    const successNotification = document.getElementById('settingsSavedNotification');
    const errorList = document.getElementById('errorList');

    // Hide success notification
    successNotification.style.display = 'none';

    // Build error list
    errorList.innerHTML = '';
    errors.forEach(error => {
        const li = document.createElement('li');
        li.textContent = error;
        errorList.appendChild(li);
    });

    // Show error notification
    notification.style.display = 'block';

    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function getCSRFToken() {
    // Try to get CSRF token from meta tag
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    if (metaTag) {
        return metaTag.getAttribute('content');
    }

    // Try to get from cookie
    const cookieValue = document.cookie
        .split('; ')
        .find(row => row.startsWith('csrf_token='));

    if (cookieValue) {
        return cookieValue.split('=')[1];
    }

    // If no token found, return empty string (server will handle error)
    return '';
}
