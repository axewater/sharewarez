/**
 * Access Management Master-Detail Interface
 * Handles all interactions for the unified access management system
 */

class AccessManagementUI {
    constructor() {
        this.selectedUserId = null;
        this.selectedUsers = new Set();
        this.isResizing = false;
        this.csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');

        // Initialize components
        this.initEventListeners();
        this.initKeyboardNav();
        this.initResizeHandle();
        this.initSearch();
        this.initBulkActions();

        console.log('Access Management UI initialized');
    }

    initEventListeners() {
        // User selection in master panel
        document.addEventListener('click', (e) => {
            const userItem = e.target.closest('.user-item');
            if (userItem && !e.target.closest('.user-checkbox')) {
                this.selectUser(parseInt(userItem.dataset.userId));
            }
        });

        // Checkbox selection for bulk actions
        document.addEventListener('change', (e) => {
            if (e.target.classList.contains('user-select-checkbox')) {
                this.toggleUserSelection(parseInt(e.target.value), e.target.checked);
            }
        });

        // Detail panel interactions
        document.addEventListener('click', (e) => {
            if (e.target.id === 'editAccountBtn') {
                this.toggleAccountEdit();
            } else if (e.target.id === 'editInvitesBtn') {
                this.toggleInviteEdit();
            } else if (e.target.id === 'saveInviteQuota') {
                this.saveInviteQuota();
            } else if (e.target.id === 'cancelInviteEdit') {
                this.cancelInviteEdit();
            }
        });

        // Whitelist toggle
        document.addEventListener('change', (e) => {
            if (e.target.id === 'whitelistToggle') {
                this.toggleWhitelist(e.target.checked);
            }
        });

        // Form submissions
        document.addEventListener('submit', (e) => {
            if (e.target.id === 'userEditForm') {
                e.preventDefault();
                this.saveUserDetails();
            }
        });
    }

    initKeyboardNav() {
        document.addEventListener('keydown', (e) => {
            // Only handle if not typing in input fields
            if (e.target.matches('input, textarea, select')) return;

            switch (e.key) {
                case 'ArrowUp':
                    e.preventDefault();
                    this.navigateUsers(-1);
                    break;
                case 'ArrowDown':
                    e.preventDefault();
                    this.navigateUsers(1);
                    break;
                case 'Enter':
                    if (this.selectedUserId) {
                        const editBtn = document.getElementById('editAccountBtn');
                        if (editBtn) editBtn.click();
                    }
                    break;
                case 'Escape':
                    this.cancelAllEdits();
                    break;
                case '/':
                    e.preventDefault();
                    document.getElementById('userSearch')?.focus();
                    break;
            }
        });
    }

    initResizeHandle() {
        const resizeHandle = document.getElementById('resizeHandle');
        const masterPanel = document.getElementById('masterPanel');
        const container = document.querySelector('.split-view-container');

        if (!resizeHandle || !masterPanel || !container) return;

        resizeHandle.addEventListener('mousedown', (e) => {
            this.isResizing = true;
            document.addEventListener('mousemove', this.handleResize.bind(this));
            document.addEventListener('mouseup', this.stopResize.bind(this));
            e.preventDefault();
        });
    }

    handleResize(e) {
        if (!this.isResizing) return;

        const container = document.querySelector('.split-view-container');
        const rect = container.getBoundingClientRect();
        const newWidth = ((e.clientX - rect.left) / rect.width) * 100;

        // Constrain between 20% and 50%
        const constrainedWidth = Math.max(20, Math.min(50, newWidth));

        document.getElementById('masterPanel').style.width = `${constrainedWidth}%`;

        // Save preference
        localStorage.setItem('accessManagement.masterPanelWidth', constrainedWidth);
    }

    stopResize() {
        this.isResizing = false;
        document.removeEventListener('mousemove', this.handleResize);
        document.removeEventListener('mouseup', this.stopResize);
    }

    initSearch() {
        const searchInput = document.getElementById('userSearch');
        const roleFilter = document.getElementById('roleFilter');
        const statusFilter = document.getElementById('statusFilter');

        if (!searchInput) return;

        // Debounced search
        let searchTimeout;
        const performSearch = () => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                this.filterUsers();
            }, 300);
        };

        searchInput.addEventListener('input', performSearch);
        roleFilter?.addEventListener('change', () => this.filterUsers());
        statusFilter?.addEventListener('change', () => this.filterUsers());
    }

    initBulkActions() {
        // Bulk action buttons
        document.getElementById('bulkWhitelistBtn')?.addEventListener('click', () => {
            this.performBulkWhitelist();
        });

        document.getElementById('bulkInviteBtn')?.addEventListener('click', () => {
            this.showBulkInviteModal();
        });

        document.getElementById('bulkDeleteBtn')?.addEventListener('click', () => {
            this.showBulkDeleteModal();
        });

        // Modal confirmations
        document.getElementById('confirmBulkInvites')?.addEventListener('click', () => {
            this.performBulkInvites();
        });

        document.getElementById('confirmBulkDelete')?.addEventListener('click', () => {
            this.performBulkDelete();
        });
    }

    async selectUser(userId) {
        if (this.selectedUserId === userId) return;

        // Update UI selection
        document.querySelectorAll('.user-item').forEach(item => {
            item.classList.remove('active');
        });

        const userItem = document.querySelector(`[data-user-id="${userId}"]`);
        if (userItem) {
            userItem.classList.add('active');
            this.selectedUserId = userId;
        }

        // Load user details
        await this.loadUserDetails(userId);
    }

    async loadUserDetails(userId) {
        this.showLoading();

        try {
            const response = await fetch(`/admin/api/access_management/user/${userId}/details`, {
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            if (data.success) {
                this.renderUserDetails(data.user);
            } else {
                this.showError(data.message || 'Failed to load user details');
            }
        } catch (error) {
            console.error('Error loading user details:', error);
            this.showError('Failed to load user details');
        } finally {
            this.hideLoading();
        }
    }

    renderUserDetails(user) {
        const detailPanel = document.getElementById('detailPanel');
        if (!detailPanel) return;

        // Create detail content HTML
        const detailHTML = this.generateDetailHTML(user);
        detailPanel.innerHTML = detailHTML;

        // Re-attach event listeners for new content
        this.attachDetailEventListeners(user);
    }

    generateDetailHTML(user) {
        return `
            <div class="detail-content" data-user-id="${user.id}">
                <div class="detail-header">
                    <div class="detail-avatar-section">
                        <img src="${user.avatar}" alt="Avatar" class="detail-avatar">
                        <div class="status-badge ${user.status ? 'active' : 'inactive'}">
                            <i class="fas ${user.status ? 'fa-check-circle' : 'fa-ban'}"></i>
                            ${user.status ? 'Active' : 'Inactive'}
                        </div>
                    </div>
                    <div class="detail-user-info">
                        <h3 class="detail-user-name">${this.escapeHtml(user.name)}</h3>
                        <p class="detail-user-email">${this.escapeHtml(user.email)}</p>
                        <div class="detail-user-meta">
                            <span class="role-badge role-${user.role}">
                                <i class="fas ${user.role === 'admin' ? 'fa-crown' : 'fa-user'}"></i>
                                ${user.role === 'admin' ? 'Administrator' : 'User'}
                            </span>
                            <span class="verification-badge ${user.email_verified ? 'verified' : 'unverified'}">
                                <i class="fas ${user.email_verified ? 'fa-check-circle' : 'fa-exclamation-triangle'}"></i>
                                ${user.email_verified ? 'Verified' : 'Unverified'}
                            </span>
                        </div>
                    </div>
                    <div class="detail-actions">
                        <button class="btn btn-sm btn-primary" id="editAccountBtn">
                            <i class="fas fa-edit"></i> Edit
                        </button>
                        ${user.id !== 1 ? `
                            <button class="btn btn-sm btn-danger" id="deleteUserBtn">
                                <i class="fas fa-trash"></i> Delete
                            </button>
                        ` : ''}
                    </div>
                </div>

                <div class="access-sections">
                    ${this.generateAccountSection(user)}
                    ${this.generateWhitelistSection(user)}
                    ${this.generateInviteSection(user)}
                    ${this.generateActivitySection(user)}
                </div>
            </div>
        `;
    }

    generateAccountSection(user) {
        return `
            <div class="glass-card" id="accountSection">
                <div class="card-header">
                    <h4><i class="fas fa-user-cog"></i> Account Settings</h4>
                    <div class="card-actions">
                        <button class="btn btn-sm btn-outline-light" id="editAccountBtn">
                            <i class="fas fa-edit"></i>
                        </button>
                    </div>
                </div>
                <div class="card-content">
                    <div class="info-grid" id="accountInfo">
                        <div class="info-item">
                            <label>Username:</label>
                            <span class="editable-field">${this.escapeHtml(user.name)}</span>
                        </div>
                        <div class="info-item">
                            <label>Email:</label>
                            <span class="editable-field">${this.escapeHtml(user.email)}</span>
                        </div>
                        <div class="info-item">
                            <label>Role:</label>
                            <span class="editable-field">${user.role}</span>
                        </div>
                        <div class="info-item">
                            <label>Status:</label>
                            <span class="editable-field">${user.status ? 'Active' : 'Inactive'}</span>
                        </div>
                        <div class="info-item">
                            <label>About:</label>
                            <span class="editable-field">${this.escapeHtml(user.about || 'No description')}</span>
                        </div>
                    </div>
                    <div class="edit-form" id="accountEditForm" style="display: none;">
                        <!-- Edit form will be inserted here -->
                    </div>
                </div>
            </div>
        `;
    }

    generateWhitelistSection(user) {
        return `
            <div class="glass-card" id="whitelistSection">
                <div class="card-header">
                    <h4><i class="fas fa-user-shield"></i> Whitelist Status</h4>
                    <div class="card-actions">
                        <div class="toggle-switch">
                            <input type="checkbox" id="whitelistToggle" ${user.whitelist_status ? 'checked' : ''}>
                            <label for="whitelistToggle" class="toggle-label"></label>
                        </div>
                    </div>
                </div>
                <div class="card-content">
                    <div class="whitelist-info">
                        <div class="status-indicator ${user.whitelist_status ? 'whitelisted' : 'not-whitelisted'}">
                            <i class="fas ${user.whitelist_status ? 'fa-check-circle' : 'fa-times-circle'}"></i>
                            <span>${user.whitelist_status ? 'This user is whitelisted and can self-register' : 'This user is not whitelisted and requires an invite'}</span>
                        </div>
                    </div>
                    <div class="whitelist-description">
                        <p>Whitelisted users can register on the platform without requiring an invitation.</p>
                    </div>
                </div>
            </div>
        `;
    }

    generateInviteSection(user) {
        const recentInvitesHTML = user.recent_invites && user.recent_invites.length > 0 ? `
            <div class="recent-invites">
                <h5>Recent Invites</h5>
                <div class="invite-list">
                    ${user.recent_invites.map(invite => `
                        <div class="invite-item">
                            <div class="invite-info">
                                <span class="invite-token">${invite.token}</span>
                                ${invite.recipient_email ? `<span class="invite-recipient">→ ${this.escapeHtml(invite.recipient_email)}</span>` : ''}
                            </div>
                            <div class="invite-status">
                                <span class="badge ${invite.used ? 'bg-success' : 'bg-warning'}">${invite.used ? 'Used' : 'Pending'}</span>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        ` : '';

        return `
            <div class="glass-card" id="inviteSection">
                <div class="card-header">
                    <h4><i class="fas fa-envelope-open-text"></i> Invite Management</h4>
                    <div class="card-actions">
                        <button class="btn btn-sm btn-outline-light" id="editInvitesBtn">
                            <i class="fas fa-edit"></i>
                        </button>
                    </div>
                </div>
                <div class="card-content">
                    <div class="invite-stats">
                        <div class="stat-item">
                            <div class="stat-value">${user.invite_quota}</div>
                            <div class="stat-label">Total Quota</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value">${user.invites_available}</div>
                            <div class="stat-label">Available</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value">${user.invites_used}</div>
                            <div class="stat-label">Used</div>
                        </div>
                    </div>
                    <div class="invite-quota-edit" id="inviteQuotaEdit" style="display: none;">
                        <div class="form-group">
                            <label for="newInviteQuota">New Invite Quota:</label>
                            <div class="input-group">
                                <input type="number" class="form-control" id="newInviteQuota" value="${user.invite_quota}" min="0" max="1000">
                                <div class="input-group-append">
                                    <button class="btn btn-primary" id="saveInviteQuota">Save</button>
                                    <button class="btn btn-secondary" id="cancelInviteEdit">Cancel</button>
                                </div>
                            </div>
                        </div>
                    </div>
                    ${recentInvitesHTML}
                </div>
            </div>
        `;
    }

    generateActivitySection(user) {
        return `
            <div class="glass-card" id="activitySection">
                <div class="card-header">
                    <h4><i class="fas fa-history"></i> Account Activity</h4>
                </div>
                <div class="card-content">
                    <div class="activity-info">
                        ${user.last_login ? `
                            <div class="activity-item">
                                <i class="fas fa-sign-in-alt"></i>
                                <span>Last login: ${user.last_login}</span>
                            </div>
                        ` : ''}
                        ${user.created_at ? `
                            <div class="activity-item">
                                <i class="fas fa-user-plus"></i>
                                <span>Account created: ${user.created_at}</span>
                            </div>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
    }

    attachDetailEventListeners(user) {
        // Store current user data for reference
        this.currentUser = user;
    }

    async toggleWhitelist(isWhitelisted) {
        if (!this.selectedUserId) return;

        try {
            const response = await fetch(`/admin/api/access_management/user/${this.selectedUserId}/whitelist`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                }
            });

            const data = await response.json();
            if (data.success) {
                this.showSuccess(data.message);
                // Update the status indicator
                this.updateWhitelistIndicator(data.whitelisted);
                // Update master panel indicator
                this.updateMasterPanelIndicator(this.selectedUserId, 'whitelist', data.whitelisted);
            } else {
                this.showError(data.message);
                // Revert toggle
                document.getElementById('whitelistToggle').checked = !isWhitelisted;
            }
        } catch (error) {
            console.error('Error toggling whitelist:', error);
            this.showError('Failed to update whitelist status');
            document.getElementById('whitelistToggle').checked = !isWhitelisted;
        }
    }

    async saveInviteQuota() {
        const quotaInput = document.getElementById('newInviteQuota');
        if (!quotaInput || !this.selectedUserId) return;

        const newQuota = parseInt(quotaInput.value);
        if (isNaN(newQuota) || newQuota < 0 || newQuota > 1000) {
            this.showError('Quota must be between 0 and 1000');
            return;
        }

        try {
            const response = await fetch(`/admin/api/access_management/user/${this.selectedUserId}/invites`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({ quota: newQuota })
            });

            const data = await response.json();
            if (data.success) {
                this.showSuccess(data.message);
                this.toggleInviteEdit(); // Hide edit form
                // Refresh user details to show updated stats
                await this.loadUserDetails(this.selectedUserId);
            } else {
                this.showError(data.message);
            }
        } catch (error) {
            console.error('Error updating invite quota:', error);
            this.showError('Failed to update invite quota');
        }
    }

    toggleAccountEdit() {
        const infoGrid = document.getElementById('accountInfo');
        const editForm = document.getElementById('accountEditForm');

        if (!infoGrid || !editForm) return;

        if (editForm.style.display === 'none') {
            // Show edit form
            infoGrid.style.display = 'none';
            editForm.style.display = 'block';
            editForm.innerHTML = this.generateEditForm();
        } else {
            // Hide edit form
            infoGrid.style.display = 'block';
            editForm.style.display = 'none';
        }
    }

    toggleInviteEdit() {
        const editSection = document.getElementById('inviteQuotaEdit');
        if (!editSection) return;

        editSection.style.display = editSection.style.display === 'none' ? 'block' : 'none';
    }

    cancelInviteEdit() {
        const editSection = document.getElementById('inviteQuotaEdit');
        if (editSection) {
            editSection.style.display = 'none';
        }
    }

    async saveUserDetails() {
        const form = document.getElementById('userEditForm');
        if (!form || !this.selectedUserId) return;

        const formData = new FormData(form);
        const userData = {
            name: document.getElementById('editUserName')?.value,
            email: document.getElementById('editUserEmail')?.value,
            role: document.getElementById('editUserRole')?.value,
            status: document.getElementById('editUserStatus')?.value,
            about: document.getElementById('editUserAbout')?.value
        };

        try {
            const response = await fetch(`/admin/api/access_management/user/${this.selectedUserId}/update`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify(userData)
            });

            const data = await response.json();
            if (data.success) {
                this.showSuccess(data.message);
                this.toggleAccountEdit(); // Hide edit form
                // Refresh user details to show updated info
                await this.loadUserDetails(this.selectedUserId);
                // Update master panel display
                this.updateMasterPanelUserInfo(this.selectedUserId, userData);
            } else {
                this.showError(data.message);
            }
        } catch (error) {
            console.error('Error saving user details:', error);
            this.showError('Failed to save user details');
        }
    }

    generateEditForm() {
        if (!this.currentUser) return '';

        return `
            <form id="userEditForm">
                <div class="form-group">
                    <label for="editUserName">Username:</label>
                    <input type="text" class="form-control" id="editUserName" value="${this.escapeHtml(this.currentUser.name)}" required>
                </div>
                <div class="form-group">
                    <label for="editUserEmail">Email:</label>
                    <input type="email" class="form-control" id="editUserEmail" value="${this.escapeHtml(this.currentUser.email)}" required>
                </div>
                <div class="form-group">
                    <label for="editUserRole">Role:</label>
                    <select class="form-control" id="editUserRole">
                        <option value="user" ${this.currentUser.role === 'user' ? 'selected' : ''}>User</option>
                        <option value="admin" ${this.currentUser.role === 'admin' ? 'selected' : ''}>Admin</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="editUserStatus">Status:</label>
                    <select class="form-control" id="editUserStatus">
                        <option value="true" ${this.currentUser.status ? 'selected' : ''}>Active</option>
                        <option value="false" ${!this.currentUser.status ? 'selected' : ''}>Inactive</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="editUserAbout">About:</label>
                    <textarea class="form-control" id="editUserAbout" rows="2">${this.escapeHtml(this.currentUser.about || '')}</textarea>
                </div>
                <div class="form-actions">
                    <button type="submit" class="btn btn-primary">Save Changes</button>
                    <button type="button" class="btn btn-secondary" id="cancelAccountEdit">Cancel</button>
                </div>
            </form>
        `;
    }

    // Utility methods
    navigateUsers(direction) {
        const userItems = Array.from(document.querySelectorAll('.user-item:not([style*="display: none"])'));
        const currentIndex = userItems.findIndex(item => item.classList.contains('active'));

        let newIndex = currentIndex + direction;
        newIndex = Math.max(0, Math.min(userItems.length - 1, newIndex));

        if (userItems[newIndex]) {
            this.selectUser(parseInt(userItems[newIndex].dataset.userId));
            userItems[newIndex].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }

    filterUsers() {
        const searchTerm = document.getElementById('userSearch')?.value.toLowerCase() || '';
        const roleFilter = document.getElementById('roleFilter')?.value || '';
        const statusFilter = document.getElementById('statusFilter')?.value || '';

        document.querySelectorAll('.user-item').forEach(item => {
            const name = item.querySelector('.user-name')?.textContent.toLowerCase() || '';
            const email = item.querySelector('.user-email')?.textContent.toLowerCase() || '';
            const role = item.dataset.role || '';
            const status = item.dataset.status || '';

            const matchesSearch = !searchTerm || name.includes(searchTerm) || email.includes(searchTerm);
            const matchesRole = !roleFilter || role === roleFilter;
            const matchesStatus = !statusFilter || status === statusFilter;

            const shouldShow = matchesSearch && matchesRole && matchesStatus;
            item.style.display = shouldShow ? 'flex' : 'none';
        });
    }

    toggleUserSelection(userId, isSelected) {
        if (isSelected) {
            this.selectedUsers.add(userId);
        } else {
            this.selectedUsers.delete(userId);
        }

        // Show/hide bulk actions
        const bulkActions = document.getElementById('bulkActions');
        if (bulkActions) {
            bulkActions.style.display = this.selectedUsers.size > 0 ? 'flex' : 'none';
        }
    }

    updateWhitelistIndicator(isWhitelisted) {
        const statusIndicator = document.querySelector('.status-indicator');
        if (statusIndicator) {
            statusIndicator.className = `status-indicator ${isWhitelisted ? 'whitelisted' : 'not-whitelisted'}`;
            statusIndicator.innerHTML = `
                <i class="fas ${isWhitelisted ? 'fa-check-circle' : 'fa-times-circle'}"></i>
                <span>${isWhitelisted ? 'This user is whitelisted and can self-register' : 'This user is not whitelisted and requires an invite'}</span>
            `;
        }
    }

    updateMasterPanelIndicator(userId, type, value) {
        const userItem = document.querySelector(`[data-user-id="${userId}"]`);
        if (!userItem) return;

        const indicators = userItem.querySelector('.user-indicators');
        if (!indicators) return;

        if (type === 'whitelist') {
            const whitelistIndicator = indicators.querySelector('.whitelist-indicator');
            if (value && !whitelistIndicator) {
                // Add whitelist indicator
                const indicator = document.createElement('span');
                indicator.className = 'indicator whitelist-indicator';
                indicator.title = 'Whitelisted';
                indicator.innerHTML = '<i class="fas fa-check-circle"></i>';
                indicators.insertBefore(indicator, indicators.firstChild);
            } else if (!value && whitelistIndicator) {
                // Remove whitelist indicator
                whitelistIndicator.remove();
            }
        }
    }

    updateMasterPanelUserInfo(userId, userData) {
        const userItem = document.querySelector(`[data-user-id="${userId}"]`);
        if (!userItem) return;

        // Update name and email in the user item
        const nameElement = userItem.querySelector('.user-name');
        const emailElement = userItem.querySelector('.user-email');

        if (nameElement && userData.name) {
            nameElement.textContent = userData.name;
        }

        if (emailElement && userData.email) {
            emailElement.textContent = userData.email;
        }

        // Update role indicator
        const roleIndicator = userItem.querySelector('.role-indicator');
        if (userData.role === 'admin' && !roleIndicator) {
            // Add admin crown
            const indicators = userItem.querySelector('.user-indicators');
            const indicator = document.createElement('span');
            indicator.className = 'indicator role-indicator';
            indicator.title = 'Administrator';
            indicator.innerHTML = '<i class="fas fa-crown"></i>';
            indicators.appendChild(indicator);
        } else if (userData.role === 'user' && roleIndicator) {
            // Remove admin crown
            roleIndicator.remove();
        }

        // Update status overlay
        const statusOverlay = userItem.querySelector('.status-overlay');
        if (userData.status === 'false' && !statusOverlay) {
            // Add inactive overlay
            const avatarContainer = userItem.querySelector('.user-avatar-container');
            const overlay = document.createElement('div');
            overlay.className = 'status-overlay inactive';
            overlay.innerHTML = '<i class="fas fa-ban"></i>';
            avatarContainer.appendChild(overlay);
        } else if (userData.status === 'true' && statusOverlay) {
            // Remove inactive overlay
            statusOverlay.remove();
        }

        // Update dataset attributes
        userItem.dataset.role = userData.role;
        userItem.dataset.status = userData.status === 'true' ? 'active' : 'inactive';
    }

    // UI feedback methods
    showLoading() {
        document.getElementById('loadingOverlay')?.style.setProperty('display', 'flex');
    }

    hideLoading() {
        document.getElementById('loadingOverlay')?.style.setProperty('display', 'none');
    }

    showSuccess(message) {
        // You could implement a toast notification system here
        console.log('Success:', message);
    }

    showError(message) {
        // You could implement a toast notification system here
        console.error('Error:', message);
        alert(message); // Temporary - replace with better notification
    }

    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return String(text).replace(/[&<>"']/g, (m) => map[m]);
    }

    cancelAllEdits() {
        // Cancel any active edits
        const editForm = document.getElementById('accountEditForm');
        const inviteEdit = document.getElementById('inviteQuotaEdit');

        if (editForm && editForm.style.display !== 'none') {
            this.toggleAccountEdit();
        }

        if (inviteEdit && inviteEdit.style.display !== 'none') {
            this.cancelInviteEdit();
        }
    }

    // Bulk action methods (placeholder implementations)
    performBulkWhitelist() {
        console.log('Bulk whitelist:', Array.from(this.selectedUsers));
    }

    showBulkInviteModal() {
        console.log('Show bulk invite modal:', Array.from(this.selectedUsers));
    }

    showBulkDeleteModal() {
        console.log('Show bulk delete modal:', Array.from(this.selectedUsers));
    }

    performBulkInvites() {
        console.log('Perform bulk invites');
    }

    performBulkDelete() {
        console.log('Perform bulk delete');
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new AccessManagementUI();
});