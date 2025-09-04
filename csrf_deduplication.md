# CSRF Token Consolidation Plan

After analyzing the codebase, I found **10 different CSRF token retrieval implementations** across the JavaScript files. This creates maintenance issues and potential security risks.

## Current CSRF Token Patterns Found:

1. **`document.querySelector('meta[name="csrf-token"]').content`** (4 files)
   - admin_manage_users.js
   - admin_manage_filters.js 
   - admin/discovery_sections.js
   - admin_manage_igdb_settings.js

2. **`document.querySelector('meta[name="csrf-token"]').getAttribute('content')`** (7 files)
   - library_pagination.js
   - user_invites.js
   - admin_manage_scanjobs_backup.js
   - admin_manage_extensions.js
   - admin_manage_libs.js
   - game_details.js
   - delete_game_modal.html

3. **`document.querySelector('input[name="csrf_token"]').value`** (2 files)
   - admin_manage_discord_settings.js
   - downloads_manager.js

4. **`document.getElementById('csrf_token').textContent`** (1 file)
   - admin_manage_server_settings.js

5. **`csrfToken.content` (stored variable)** (1 file)
   - admin_manage_smtp_settings.js

## The Solution:

### 1. Create a Central CSRF Utility Module
**File:** `modules/static/library/themes/default/js/csrf-utils.js`

```javascript
// CSRF Token Management Utility
const CSRFUtils = {
    // Cache the token after first retrieval
    _token: null,
    
    // Get CSRF token with fallback methods
    getToken() {
        if (this._token) return this._token;
        
        // Try meta tag first (most common)
        const metaTag = document.querySelector('meta[name="csrf-token"]');
        if (metaTag) {
            this._token = metaTag.content || metaTag.getAttribute('content');
            return this._token;
        }
        
        // Fallback to input field
        const inputField = document.querySelector('input[name="csrf_token"]');
        if (inputField) {
            this._token = inputField.value;
            return this._token;
        }
        
        // Fallback to element with ID
        const element = document.getElementById('csrf_token');
        if (element) {
            this._token = element.textContent || element.value;
            return this._token;
        }
        
        console.error('CSRF token not found');
        return null;
    },
    
    // Get headers with CSRF token included
    getHeaders(additionalHeaders = {}) {
        return {
            'X-CSRFToken': this.getToken(),
            ...additionalHeaders
        };
    }
};

// Make it globally available
window.CSRFUtils = CSRFUtils;
```

### 2. Update Each File to Use the Utility

Replace all different CSRF implementations with:
```javascript
const csrfToken = CSRFUtils.getToken();
```

Or for fetch requests:
```javascript
fetch(url, {
    headers: CSRFUtils.getHeaders({ 'Content-Type': 'application/json' }),
    // ... rest of options
})
```

### 3. Implementation Steps:

1. **Create the csrf-utils.js file** with the utility module
2. **Include it in base.html** before other JavaScript files
3. **Update all 18 JavaScript files** to use `CSRFUtils.getToken()`
4. **Test each module** to ensure CSRF tokens are properly retrieved

## Benefits:

- **Single source of truth** for CSRF token retrieval
- **Consistent implementation** across all files
- **Cached retrieval** for better performance
- **Easier maintenance** - update logic in one place
- **Better error handling** with fallback methods
- **Reduced code duplication** (~100 lines saved)

## Files That Need Updates:

### JavaScript Files:
1. `admin_manage_users.js` - lines 22, 65, 147, 171
2. `admin_manage_filters.js` - line 25
3. `admin/discovery_sections.js` - lines 35, 61
4. `admin_manage_igdb_settings.js` - lines 38, 67
5. `library_pagination.js` - lines 75, 332, 491, 572
6. `user_invites.js` - line 22
7. `admin_manage_scanjobs_backup.js` - lines 28, 176, 319, 511
8. `admin_manage_extensions.js` - lines 45, 72
9. `admin_manage_libs.js` - lines 15, 44, 87
10. `game_details.js` - (needs verification)
11. `admin_manage_discord_settings.js` - line 28
12. `downloads_manager.js` - lines 88-89
13. `admin_manage_server_settings.js` - line 59
14. `admin_manage_smtp_settings.js` - lines 4, 19, 62
15. `favorites_manager.js` - lines 10-15

### HTML Templates with Embedded JavaScript:
16. `templates/partials/delete_game_modal.html` - line 40

## Implementation Priority:
1. High - Admin management files (security critical)
2. Medium - Library and user-facing files
3. Low - Downloads and utility files