# Plan: Clean Up Duplicate Routes for `/admin/settings`

## Problem
Three routes are registered for the same URL `/admin/settings`:
- `get_settings()` (GET only) 
- `update_settings()` (POST only)
- `manage_settings()` (GET/POST wrapper) - **redundant legacy route**

## Solution
Remove the legacy `manage_settings()` wrapper route and update HTML templates to use the specific route names.

## Steps
1. **Remove legacy route**: Delete the `manage_settings()` function and its `@admin2_bp.route` decorator (lines 224-232 in `modules/routes_admin_ext/settings.py`)

2. **Update template references**: Replace `url_for('admin2.manage_settings')` calls with `url_for('admin2.get_settings')` in:
   - `modules/templates/admin/admin_manage_discord_settings.html:22`
   - `modules/templates/admin/admin_dashboard.html:59`

3. **Update tests**: Modify test class `TestLegacyRouteHandler` to remove legacy route tests and update any test methods that reference the old route

## Benefits
- Eliminates routing ambiguity
- Reduces code duplication
- Clearer separation of GET/POST handling
- Maintains all functionality through explicit routes

## Risk Assessment
- **Low risk**: Legacy route was just a dispatcher
- **No breaking changes**: All functionality preserved through explicit GET/POST routes
- **Templates updated**: Ensures no broken links

## Files to Modify
1. `modules/routes_admin_ext/settings.py` - Remove legacy route function
2. `modules/templates/admin/admin_manage_discord_settings.html` - Update url_for call
3. `modules/templates/admin/admin_dashboard.html` - Update url_for call
4. `tests/test_routes_admin_ext_settings.py` - Update/remove legacy route tests

---

# Plan: Fix IDOR Security Vulnerability in Game API

## Problem - CONFIRMED SECURITY ISSUE
The `move_game_to_library` function at `modules/routes_apis/game.py:35` has an **Insecure Direct Object Reference (IDOR) vulnerability**:
- Only has `@login_required` decorator
- Missing `@admin_required` decorator  
- Any authenticated user can move ANY game to ANY library

## Solution
Add proper authorization controls to restrict game library operations to admin users only.

## Steps
1. **Add admin_required import**: Import `admin_required` from `modules.utils_auth` 
2. **Add authorization decorator**: Add `@admin_required` decorator to the `move_game_to_library` function
3. **Update tests**: Modify tests to verify admin-only access and add test for non-admin rejection

## Security Impact
- **HIGH RISK**: Current vulnerability allows privilege escalation
- **IDOR Attack**: Regular users can manipulate any game's library assignment
- **Data Integrity**: Unauthorized game organization changes

## Files to Modify
1. `modules/routes_apis/game.py` - Add admin_required import and decorator
2. `tests/test_routes_apis_game.py` - Update tests for admin-only access