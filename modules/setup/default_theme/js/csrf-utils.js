/**
 * CSRF Token Management Utility
 * 
 * Provides centralized CSRF token retrieval with fallback support
 * for all existing patterns in the SharewareZ application.
 * 
 * Usage:
 *   const token = CSRFUtils.getToken();
 *   fetch(url, { headers: CSRFUtils.getHeaders() })
 */
const CSRFUtils = {
    // Cache the token after first retrieval for performance
    _token: null,
    
    // Enable debug logging for testing (set to false in production)
    _debug: false,
    
    /**
     * Get CSRF token with comprehensive fallback support
     * Supports all existing patterns in the application:
     * 1. Meta tag (base.html - most common)
     * 2. Input field (forms)
     * 3. Script element (admin_manage_server_settings)
     */
    getToken() {
        // Return cached token if available
        if (this._token) {
            if (this._debug) console.log('CSRF: Using cached token');
            return this._token;
        }
        
        // Pattern 1: Meta tag (most common - used in base.html line 9)
        const metaTag = document.querySelector('meta[name="csrf-token"]');
        if (metaTag) {
            // Support both .content and .getAttribute('content') patterns
            this._token = metaTag.content || metaTag.getAttribute('content');
            if (this._token) {
                if (this._debug) console.log('CSRF: Retrieved from meta tag');
                return this._token;
            }
        }
        
        // Pattern 2: Input field (used in forms like admin_manage_discord_settings.html)
        const inputField = document.querySelector('input[name="csrf_token"]');
        if (inputField && inputField.value) {
            this._token = inputField.value;
            if (this._debug) console.log('CSRF: Retrieved from input field');
            return this._token;
        }
        
        // Pattern 3: Script element (used in admin_manage_server_settings.html)
        const scriptElement = document.getElementById('csrf_token');
        if (scriptElement) {
            this._token = scriptElement.textContent;
            if (this._token) {
                if (this._debug) console.log('CSRF: Retrieved from script element');
                return this._token;
            }
        }
        
        // If we get here, no token was found
        console.error('CSRF token not found in any expected location');
        console.error('Checked: meta[name="csrf-token"], input[name="csrf_token"], #csrf_token');
        return null;
    },
    
    /**
     * Get headers object with CSRF token included
     * @param {Object} additionalHeaders - Additional headers to merge
     * @returns {Object} Headers object with X-CSRFToken and any additional headers
     */
    getHeaders(additionalHeaders = {}) {
        const token = this.getToken();
        if (!token) {
            console.warn('CSRF token is null - request may fail with 403 Forbidden');
        }
        
        return {
            'X-CSRFToken': token,
            ...additionalHeaders
        };
    },
    
    /**
     * Reset cached token (useful for testing or when token changes)
     */
    reset() {
        this._token = null;
        if (this._debug) console.log('CSRF: Token cache reset');
    },
    
    /**
     * Enable or disable debug logging
     * @param {boolean} enable - Whether to enable debug logging
     */
    setDebug(enable) {
        this._debug = !!enable;
        console.log('CSRF debug logging:', this._debug ? 'enabled' : 'disabled');
    }
};

// Make CSRFUtils globally available
window.CSRFUtils = CSRFUtils;

// For backwards compatibility, also expose as global function
window.getCSRFToken = function() {
    return CSRFUtils.getToken();
};