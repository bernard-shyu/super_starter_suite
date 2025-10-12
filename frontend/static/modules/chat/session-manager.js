/**
 * Session Manager - Comprehensive Session Management UI
 *
 * Provides complete session lifecycle management:
 * - Session listing with workflow grouping
 * - New session creation with topic-based naming
 * - Session title editing and management
 * - Artifact-data persistence and alignment
 */

// Session Manager State
let allSessions = [];
let currentWorkflowFilter = null;
let sessionManagerInitialized = false;

// Session Manager Class
class SessionManager {
    constructor() {
        this.sessionListContainer = null;
        this.workflowFilter = null;
        this.newSessionDialog = null;
        this.sessionTitleEditor = null;
        this.initializeSessionManager();
    }

    /**
     * Initialize the session manager - register global availability only
     */
    async initializeSessionManager() {
        console.log('[SessionManager] Initializing session manager...');

        // Just register ourselves globally - don't create UI yet
        sessionManagerInitialized = true;

        // Notify other modules
        if (window.dispatchEvent) {
            window.dispatchEvent(new CustomEvent('sessionManagerReady', {
                detail: { sessionManager: this }
            }));
        }

        console.log('[SessionManager] Session manager ready for on-demand UI creation');
    }

    /**
     * Setup the session manager UI components
     */
    setupUI() {
        console.log('[SessionManager] Setting up UI components...');

        // Create session management UI
        this.createSessionManagementUI();

        // Attach event handlers
        this.attachEventHandlers();

        // Load initial sessions
        this.loadAllSessions();

        sessionManagerInitialized = true;
        console.log('[SessionManager] Session manager initialized');

        // Notify other modules
        if (window.dispatchEvent) {
            window.dispatchEvent(new CustomEvent('sessionManagerReady', {
                detail: { sessionManager: this }
            }));
        }
    }

    /**
     * Create the session management UI structure
     */
    createSessionManagementUI() {
        // Get the existing container from HTML (same one used by MainUIManager)
        const sessionContainer = document.getElementById('chat-history-ui-container');
        if (!sessionContainer) {
            console.error('[SessionManager] Chat history UI container not found in HTML!');
            return;
        }

        // Clear any existing content
        sessionContainer.innerHTML = '';

        // Add session management UI to the existing container
        sessionContainer.innerHTML = `
            <div class="session-manager-header">
                <h2>💬 Chat Sessions</h2>
                <div class="session-manager-actions">
                    <button id="new-session-btn" class="btn-primary">
                        🆕 New Session
                    </button>
                    <button id="export-artifacts-btn" class="btn-secondary" title="Export all artifacts">
                        📦 Export All
                    </button>
                    <select id="workflow-filter" class="workflow-filter">
                        <option value="">All Workflows</option>
                    </select>
                </div>
            </div>

            <div class="session-manager-content">
                <!-- Tab Navigation -->
                <div class="session-tabs">
                    <button class="session-tab active" data-tab="sessions">
                        <span class="tab-icon">💬</span>
                        <span class="tab-label">Sessions</span>
                    </button>
                    <button class="session-tab" data-tab="artifacts">
                        <span class="tab-icon">📎</span>
                        <span class="tab-label">Artifacts</span>
                        <span class="artifact-count" id="artifact-count">(0)</span>
                    </button>
                </div>

                <div class="session-quick-actions">
                    <div id="continue-last-session" class="quick-action-card hidden">
                        <h3>🔄 Continue Last Session</h3>
                        <p id="last-session-info">Loading...</p>
                        <button id="continue-last-btn" class="btn-secondary">Resume</button>
                    </div>
                </div>

                <!-- Tab Content -->
                <div id="sessions-tab" class="tab-content active">
                    <div id="session-list" class="session-list">
                        <div class="session-loading">
                            <p>Loading sessions...</p>
                        </div>
                    </div>
                </div>

                <div id="artifacts-tab" class="tab-content">
                    <div id="artifact-list" class="artifact-list">
                        <div class="artifact-loading">
                            <p>Loading artifacts...</p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- New Session Dialog -->
            <div id="new-session-dialog" class="modal-overlay hidden">
                <div class="modal-content">
                    <h3>🆕 Create New Session</h3>
                    <form id="new-session-form">
                        <div class="form-group">
                            <label for="session-topic">Conversation Topic:</label>
                            <input type="text" id="session-topic" placeholder="e.g., Financial Analysis, Code Optimization..."
                                   maxlength="100" required>
                            <small class="form-hint">Describe what you want to discuss or work on</small>
                        </div>
                        <div class="form-group">
                            <label for="session-workflow">Workflow:</label>
                            <select id="session-workflow" required>
                                <option value="">Select workflow...</option>
                            </select>
                        </div>
                        <div class="modal-actions">
                            <button type="button" id="cancel-new-session" class="btn-secondary">Cancel</button>
                            <button type="submit" class="btn-primary">Create Session</button>
                        </div>
                    </form>
                </div>
            </div>

            <!-- Session Title Editor -->
            <div id="session-title-editor" class="inline-editor hidden">
                <input type="text" id="title-input" maxlength="100">
                <button id="save-title-btn" class="btn-small">💾</button>
                <button id="cancel-title-btn" class="btn-small">✕</button>
            </div>
        `;

        // Cache DOM elements
        this.sessionListContainer = document.getElementById('session-list');
        this.workflowFilter = document.getElementById('workflow-filter');
        this.newSessionDialog = document.getElementById('new-session-dialog');
        this.sessionTitleEditor = document.getElementById('session-title-editor');

        console.log('[SessionManager] Session management UI created');
    }

    /**
     * Attach event handlers to UI elements
     */
    attachEventHandlers() {
        // Tab switching
        document.querySelectorAll('.session-tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                const tabName = e.target.closest('.session-tab').dataset.tab;
                this.switchTab(tabName);
            });
        });

        // New session button
        const newSessionBtn = document.getElementById('new-session-btn');
        if (newSessionBtn) {
            newSessionBtn.addEventListener('click', () => this.showNewSessionDialog());
        }

        // New session form
        const newSessionForm = document.getElementById('new-session-form');
        if (newSessionForm) {
            newSessionForm.addEventListener('submit', (e) => this.handleNewSessionSubmit(e));
        }

        // Cancel new session
        const cancelBtn = document.getElementById('cancel-new-session');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => this.hideNewSessionDialog());
        }

        // Workflow filter
        if (this.workflowFilter) {
            this.workflowFilter.addEventListener('change', (e) => this.filterSessions(e.target.value));
        }

        // Continue last session
        const continueLastBtn = document.getElementById('continue-last-btn');
        if (continueLastBtn) {
            continueLastBtn.addEventListener('click', () => this.continueLastSession());
        }

        // Export artifacts button
        const exportArtifactsBtn = document.getElementById('export-artifacts-btn');
        if (exportArtifactsBtn) {
            exportArtifactsBtn.addEventListener('click', () => this.exportAllArtifacts());
        }

        // Session title editor
        const saveTitleBtn = document.getElementById('save-title-btn');
        const cancelTitleBtn = document.getElementById('cancel-title-btn');
        if (saveTitleBtn) {
            saveTitleBtn.addEventListener('click', () => this.saveSessionTitle());
        }
        if (cancelTitleBtn) {
            cancelTitleBtn.addEventListener('click', () => this.cancelSessionTitleEdit());
        }

        // Close modal on overlay click
        if (this.newSessionDialog) {
            this.newSessionDialog.addEventListener('click', (e) => {
                if (e.target === this.newSessionDialog) {
                    this.hideNewSessionDialog();
                }
            });
        }
    }

    /**
     * Load all sessions from backend
     */
    async loadAllSessions() {
        try {
            console.log('[SessionManager] Loading sessions...');
            const response = await fetch('/api/chat_history/sessions');

            if (!response.ok) {
                throw new Error(`Failed to load sessions: ${response.status}`);
            }

            const data = await response.json();
            allSessions = data.sessions || [];

            console.log(`[SessionManager] Loaded ${allSessions.length} sessions`);
            this.renderSessions();
            this.updateWorkflowFilter();
            this.updateLastSession();

        } catch (error) {
            console.error('[SessionManager] Failed to load sessions:', error);
            this.showError('Failed to load sessions. Please refresh the page.');
        }
    }

    /**
     * Render the session list UI
     */
    renderSessions() {
        if (!this.sessionListContainer) return;

        if (allSessions.length === 0) {
            this.sessionListContainer.innerHTML = `
                <div class="empty-state">
                    <h3>💭 No sessions yet</h3>
                    <p>Create your first conversation session to get started!</p>
                    <button id="create-first-session" class="btn-primary">🆕 Create Session</button>
                </div>
            `;

            // Attach handler for empty state button
            const createBtn = document.getElementById('create-first-session');
            if (createBtn) {
                createBtn.addEventListener('click', () => this.showNewSessionDialog());
            }
            return;
        }

        // Group sessions by workflow
        const sessionsByWorkflow = this.groupSessionsByWorkflow(allSessions);
        const filteredSessions = currentWorkflowFilter ?
            sessionsByWorkflow[currentWorkflowFilter] || [] :
            allSessions;

        let html = '';

        // Show Continue Last Session card if available
        if (this.shouldShowLastSession()) {
            // Already handled by updateLastSession()
        }

        // Session groups
        for (const [workflow, sessions] of Object.entries(sessionsByWorkflow)) {
            if (currentWorkflowFilter && currentWorkflowFilter !== workflow) continue;

            const workflowDisplayName = this.getWorkflowDisplayName(workflow);
            const sessionCount = sessions.length;

            html += `
                <div class="session-group">
                    <h3 class="session-group-title">
                        <span class="workflow-icon">${this.getWorkflowIcon(workflow)}</span>
                        ${workflowDisplayName}
                        <span class="session-count">(${sessionCount})</span>
                    </h3>
                    <div class="session-group-content">
                        ${sessions.map(session => this.renderSessionCard(session)).join('')}
                    </div>
                </div>
            `;
        }

        this.sessionListContainer.innerHTML = html;

        // Attach event handlers to session cards
        this.attachSessionCardHandlers();
    }

    /**
     * Group sessions by workflow type
     */
    groupSessionsByWorkflow(sessions) {
        const groups = {};

        sessions.forEach(session => {
            const workflow = session.workflow_name || 'unknown';
            if (!groups[workflow]) {
                groups[workflow] = [];
            }
            groups[workflow].push(session);
        });

        // Sort sessions within each group by updated_at (most recent first)
        Object.values(groups).forEach(group => {
            group.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));
        });

        return groups;
    }

    /**
     * Render a single session card
     */
    renderSessionCard(session) {
        const lastActivity = this.formatRelativeTime(session.updated_at);
        const messageCount = session.messages?.length || 0;
        const title = session.title || 'Untitled Session';

        // Escape HTML in title and preview
        const safeTitle = this.escapeHtml(title);
        const previewText = this.getSessionPreview(session);

        return `
            <div class="session-card" data-session-id="${session.session_id}" data-workflow="${session.workflow_name}">
                <div class="session-card-header">
                    <h4 class="session-title" data-session-id="${session.session_id}">${safeTitle}</h4>
                    <div class="session-actions">
                        <button class="session-action-btn edit-title" data-session-id="${session.session_id}" title="Edit title">
                            ✏️
                        </button>
                        <button class="session-action-btn delete-session" data-session-id="${session.session_id}" title="Delete session">
                            🗑️
                        </button>
                    </div>
                </div>
                <div class="session-meta">
                    <span class="session-time">🕒 ${lastActivity}</span>
                    <span class="session-messages">💬 ${messageCount} messages</span>
                </div>
                <div class="session-preview">
                    ${previewText}
                </div>
                <div class="session-card-actions">
                    <button class="btn-secondary resume-session" data-session-id="${session.session_id}">
                        Resume Chat
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * Get session preview text
     */
    getSessionPreview(session) {
        if (!session.messages || session.messages.length === 0) {
            return '<em>No messages yet</em>';
        }

        // Get the last user message as preview
        const lastUserMessage = [...session.messages]
            .reverse()
            .find(msg => msg.role === 'user');

        if (lastUserMessage && lastUserMessage.content) {
            const preview = lastUserMessage.content.substring(0, 150);
            return this.escapeHtml(preview) + (lastUserMessage.content.length > 150 ? '...' : '');
        }

        // Fallback to last message
        const lastMessage = session.messages[session.messages.length - 1];
        if (lastMessage && lastMessage.content) {
            const preview = lastMessage.content.substring(0, 150);
            return this.escapeHtml(preview) + (lastMessage.content.length > 150 ? '...' : '');
        }

        return '<em>No preview available</em>';
    }

    /**
     * Attach event handlers to session cards
     */
    attachSessionCardHandlers() {
        // Resume session buttons
        document.querySelectorAll('.resume-session').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const sessionId = e.target.closest('.session-card').dataset.sessionId;
                this.resumeSession(sessionId);
            });
        });

        // Edit title buttons
        document.querySelectorAll('.edit-title').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const sessionId = btn.dataset.sessionId;
                this.startSessionTitleEdit(sessionId);
            });
        });

        // Delete session buttons
        document.querySelectorAll('.delete-session').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const sessionId = btn.dataset.sessionId;
                this.confirmDeleteSession(sessionId);
            });
        });

        // Title click for editing
        document.querySelectorAll('.session-title').forEach(title => {
            title.addEventListener('click', (e) => {
                e.stopPropagation();
                const sessionId = title.dataset.sessionId;
                this.startSessionTitleEdit(sessionId);
            });
        });
    }

    /**
     * Show new session dialog
     */
    showNewSessionDialog() {
        console.log('[SessionManager] Showing new session dialog');

        // Load available workflows
        this.loadWorkflowsForDialog();

        if (this.newSessionDialog) {
            this.newSessionDialog.classList.remove('hidden');
        }
    }

    /**
     * Hide new session dialog
     */
    hideNewSessionDialog() {
        if (this.newSessionDialog) {
            this.newSessionDialog.classList.add('hidden');
        }

        // Clear form
        const form = document.getElementById('new-session-form');
        if (form) {
            form.reset();
        }
    }

    /**
     * Load workflows for the new session dialog
     */
    async loadWorkflowsForDialog() {
        try {
            // Load workflows from API or use predefined list
            const workflows = await this.getAvailableWorkflows();

            const workflowSelect = document.getElementById('session-workflow');
            if (!workflowSelect) return;

            // Clear existing options except the default
            const defaultOption = workflowSelect.querySelector('option[value=""]');
            workflowSelect.innerHTML = '';
            if (defaultOption) {
                workflowSelect.appendChild(defaultOption);
            }

            // Add workflow options
            workflows.forEach(workflow => {
                const option = document.createElement('option');
                option.value = workflow.id;
                option.textContent = workflow.display_name;
                workflowSelect.appendChild(option);
            });

        } catch (error) {
            console.error('[SessionManager] Failed to load workflows:', error);
        }
    }

    /**
     * Get available workflows
     */
    async getAvailableWorkflows() {
        try {
            const response = await fetch('/api/workflows');
            if (response.ok) {
                const data = await response.json();
                return data.workflows || [];
            }
        } catch (error) {
            console.warn('[SessionManager] API workflows not available, using defaults');
        }

        // Fallback: return hardcoded list based on system config
        return [
            { id: 'A_agentic_rag', display_name: 'Agentic RAG (Adapted)' },
            { id: 'P_agentic_rag', display_name: 'Agentic RAG (Ported)' },
            { id: 'A_code_generator', display_name: 'Code Generator (Adapted)' },
            { id: 'P_code_generator', display_name: 'Code Generator (Ported)' },
            { id: 'A_deep_research', display_name: 'Deep Research (Adapted)' },
            { id: 'P_deep_research', display_name: 'Deep Research (Ported)' }
        ];
    }

    /**
     * Handle new session form submission
     */
    async handleNewSessionSubmit(e) {
        e.preventDefault();

        const topicInput = document.getElementById('session-topic');
        const workflowSelect = document.getElementById('session-workflow');

        const topic = topicInput.value.trim();
        const workflowId = workflowSelect.value;

        if (!topic || !workflowId) {
            this.showError('Please fill in all fields');
            return;
        }

        try {
            console.log(`[SessionManager] Creating new session for workflow ${workflowId} with topic: ${topic}`);

            // Hide dialog
            this.hideNewSessionDialog();

            // Show loading
            if (window.updateStatus) {
                window.updateStatus('Creating new session...', 'in-progress');
            }

            // Navigate to workflow chat with new session creation
            // The workflow will handle session creation
            this.startNewWorkflowSession(workflowId, topic);

        } catch (error) {
            console.error('[SessionManager] Failed to create session:', error);
            this.showError('Failed to create session. Please try again.');
        }
    }

    /**
     * Start a new workflow session
     */
    async startNewWorkflowSession(workflowId, topic) {
        console.log(`[SessionManager] Starting new workflow session: ${workflowId} with topic: ${topic}`);

        // Set the workflow
        if (window.workflowManager) {
            await window.workflowManager.selectWorkflow(workflowId);
        }

        // Navigate to chat interface - the system will create a new session
        // Pass topic information via URL or local storage for session title generation
        localStorage.setItem('pending_session_topic', topic);

        if (window.showChatInterface) {
            // Pass empty session ID to create new session
            window.showChatInterface(null);
        }

        // Update status
        if (window.updateStatus) {
            window.updateStatus(`Started new ${workflowId.replace('_', ' ')} session`, 'success');
        }
    }

    /**
     * Resume an existing session
     */
    async resumeSession(sessionId) {
        console.log(`[SessionManager] Resuming session: ${sessionId}`);

        try {
            // Show loading
            if (window.updateStatus) {
                window.updateStatus('Loading session...', 'in-progress');
            }

            // Get session details to determine workflow
            const session = allSessions.find(s => s.session_id === sessionId);
            if (!session) {
                throw new Error('Session not found');
            }

        // Set workflow - use full workflow ID directly (no normalization)
        if (window.workflowManager) {
            window.workflowManager.setCurrentWorkflow(session.workflow_name);
        }

            if (window.showChatInterface) {
                window.showChatInterface(sessionId);
            }

            if (window.updateStatus) {
                window.updateStatus('Session resumed successfully', 'success');
            }

        } catch (error) {
            console.error('[SessionManager] Failed to resume session:', error);
            this.showError('Failed to resume session. Please try again.');
        }
    }

    /**
     * Continue the last active session
     */
    continueLastSession() {
        const lastSession = this.getLastActiveSession();
        if (lastSession) {
            this.resumeSession(lastSession.session_id);
        }
    }

    /**
     * Start editing session title
     */
    startSessionTitleEdit(sessionId) {
        const session = allSessions.find(s => s.session_id === sessionId);
        if (!session) return;

        const titleElement = document.querySelector(`.session-title[data-session-id="${sessionId}"]`);
        if (!titleElement) return;

        // Create inline editor
        const currentTitle = session.title || 'Untitled Session';

        if (this.sessionTitleEditor) {
            this.sessionTitleEditor.dataset.sessionId = sessionId;
            const input = this.sessionTitleEditor.querySelector('#title-input');
            if (input) {
                input.value = currentTitle;
            }

            // Position editor
            titleElement.parentNode.insertBefore(this.sessionTitleEditor, titleElement.nextSibling);
            this.sessionTitleEditor.classList.remove('hidden');

            // Hide original title
            titleElement.style.display = 'none';

            // Focus input
            setTimeout(() => input.focus(), 100);
        }
    }

    /**
     * Save session title edit
     */
    async saveSessionTitle() {
        const sessionId = this.sessionTitleEditor?.dataset.sessionId;
        if (!sessionId) return;

        const input = document.getElementById('title-input');
        if (!input) return;

        const newTitle = input.value.trim();
        if (!newTitle) return;

        try {
            // Update session title via API
            const response = await fetch(`/api/chat_history/sessions/${sessionId}/title`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ title: newTitle })
            });

            if (response.ok) {
                // Update local session data
                const session = allSessions.find(s => s.session_id === sessionId);
                if (session) {
                    session.title = newTitle;
                }

                // Refresh UI
                this.renderSessions();

                console.log(`[SessionManager] Updated session ${sessionId} title`);
            } else {
                throw new Error('Failed to update title');
            }

        } catch (error) {
            console.error('[SessionManager] Failed to save session title:', error);
            this.showError('Failed to update session title');
        } finally {
            this.cancelSessionTitleEdit();
        }
    }

    /**
     * Cancel session title edit
     */
    cancelSessionTitleEdit() {
        if (this.sessionTitleEditor) {
            this.sessionTitleEditor.classList.add('hidden');
            delete this.sessionTitleEditor.dataset.sessionId;
        }

        // Show original titles
        document.querySelectorAll('.session-title').forEach(el => {
            el.style.display = '';
        });
    }

    /**
     * Confirm and delete session
     */
    async confirmDeleteSession(sessionId) {
        const session = allSessions.find(s => s.session_id === sessionId);
        if (!session) return;

        const confirmed = confirm(`Delete session "${session.title || 'Untitled'}"? This action cannot be undone.`);

        if (confirmed) {
            await this.deleteSession(sessionId);
        }
    }

    /**
     * Delete session via API
     */
    async deleteSession(sessionId) {
        try {
            const response = await fetch(`/api/chat_history/sessions/${sessionId}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                // Remove from local data
                allSessions = allSessions.filter(s => s.session_id !== sessionId);

                // Refresh UI
                this.renderSessions();

                console.log(`[SessionManager] Deleted session ${sessionId}`);
                this.showSuccess('Session deleted successfully');
            } else {
                throw new Error('Failed to delete session');
            }

        } catch (error) {
            console.error('[SessionManager] Failed to delete session:', error);
            this.showError('Failed to delete session');
        }
    }

    // Utility Methods

    /**
     * Update workflow filter options
     */
    updateWorkflowFilter() {
        if (!this.workflowFilter) return;

        const workflows = [...new Set(allSessions.map(s => s.workflow_name))].filter(Boolean);
        console.log('[SessionManager] Updating workflow filter with workflows:', workflows);

        // Clear existing options except "All Workflows"
        const allOption = this.workflowFilter.querySelector('option[value=""]');
        this.workflowFilter.innerHTML = '';
        if (allOption) {
            this.workflowFilter.appendChild(allOption);
        }

        // Add workflow options
        workflows.forEach(workflow => {
            const option = document.createElement('option');
            option.value = workflow;
            option.textContent = this.getWorkflowDisplayName(workflow);
            this.workflowFilter.appendChild(option);
        });

        console.log('[SessionManager] Workflow filter updated');
    }

    /**
     * Filter sessions and reload artifacts
     */
    filterSessions(workflowType) {
        currentWorkflowFilter = workflowType || null;
        this.renderSessions();

        // Reload artifacts when workflow filter changes
        if (document.getElementById('artifacts-tab').classList.contains('active')) {
            this.loadArtifacts();
        }
    }

    /**
     * Update last session info
     */
    updateLastSession() {
        const lastSession = this.getLastActiveSession();
        const container = document.getElementById('continue-last-session');

        if (!lastSession || !container) return;

        const timeAgo = this.formatRelativeTime(lastSession.updated_at);
        const lastMsgContainer = document.getElementById('last-session-info');

        if (lastMsgContainer) {
            lastMsgContainer.textContent =
                `"${lastSession.title || 'Untitled'}" - Last active ${timeAgo}`;
        }

        container.classList.remove('hidden');
    }

    /**
     * Get last active session
     */
    getLastActiveSession() {
        if (allSessions.length === 0) return null;

        return allSessions.reduce((latest, current) =>
            new Date(current.updated_at) > new Date(latest.updated_at) ? current : latest
        );
    }

    /**
     * Switch between tabs (sessions/artifacts)
     */
    switchTab(tabName) {
        console.log(`[SessionManager] Switching to tab: ${tabName}`);

        // Update tab buttons
        document.querySelectorAll('.session-tab').forEach(tab => {
            tab.classList.remove('active');
        });

        const activeTabBtn = document.querySelector(`.session-tab[data-tab="${tabName}"]`);
        if (activeTabBtn) {
            activeTabBtn.classList.add('active');
        }

        // Update tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });

        const activeTabContent = document.getElementById(`${tabName}-tab`);
        if (activeTabContent) {
            activeTabContent.classList.add('active');
        }

        // Load content for the active tab
        if (tabName === 'artifacts') {
            this.loadArtifacts();
        }

        console.log(`[SessionManager] Tab switched to: ${tabName}`);
    }

    /**
     * Load artifacts for display
     */
    async loadArtifacts() {
        console.log('[SessionManager] Loading artifacts...');

        const artifactContainer = document.getElementById('artifact-list');
        if (!artifactContainer) return;

        artifactContainer.innerHTML = '<div class="artifact-loading">Loading artifacts...</div>';

        try {
            // Get artifacts from different sources:
            // 1. From artifact display manager if available
            // 2. From chat history API
            // 3. Generate sample artifacts for demo

            let artifacts = [];

            // Try to get from artifact display manager, filtered by current workflow if set
            if (window.artifactDisplayManager && window.artifactDisplayManager.getCurrentArtifacts) {
                artifacts = window.artifactDisplayManager.getCurrentArtifacts();

                // Filter by current workflow if one is selected
                if (currentWorkflowFilter) {
                    artifacts = artifacts.filter(art => art.workflow_type === currentWorkflowFilter || art.workflow_name === currentWorkflowFilter);
                    console.log(`[SessionManager] Filtered artifacts to ${artifacts.length} for workflow: ${currentWorkflowFilter}`);
                }

                console.log(`[SessionManager] Found ${artifacts.length} artifacts from artifact manager`);
            }

            // If no artifacts, try to fetch from chat history
            if (artifacts.length === 0) {
                artifacts = await this.loadArtifactsFromHistory();
            }

            // If still no artifacts, show sample data (for development/testing)
            if (artifacts.length === 0) {
                artifacts = this.getSampleArtifacts();
            }

            this.renderArtifacts(artifacts);

            // Update artifact count in tab
            this.updateArtifactCount(artifacts.length);

        } catch (error) {
            console.error('[SessionManager] Failed to load artifacts:', error);
            artifactContainer.innerHTML = '<div class="artifact-error">Failed to load artifacts</div>';
            this.updateArtifactCount(0);
        }
    }

    /**
     * Load artifacts from chat history
     */
    async loadArtifactsFromHistory() {
        const artifacts = [];

        try {
            // Try to load artifacts from recent sessions
            for (const session of allSessions.slice(0, 5)) { // Check last 5 sessions
                if (session.messages && session.messages.length > 0) {
                    for (const message of session.messages) {
                        if (message.role === 'assistant' && message.content) {
                            // Look for code blocks in assistant responses
                            const codeMatches = this.extractCodeBlocks(message.content);
                            if (codeMatches.length > 0) {
                                for (const codeMatch of codeMatches) {
                                    artifacts.push({
                                        id: `${session.session_id}_${Math.random()}`,
                                        type: codeMatch.language || 'code',
                                        title: `Code from ${session.title || 'Session'}`,
                                        content: codeMatch.code,
                                        language: codeMatch.language,
                                        session_id: session.session_id,
                                        created_at: session.updated_at
                                    });
                                }
                            }
                        }
                    }
                }
            }
        } catch (error) {
            console.warn('[SessionManager] Failed to extract artifacts from history:', error);
        }

        return artifacts;
    }

    /**
     * Extract code blocks from text content
     */
    extractCodeBlocks(text) {
        const codeBlocks = [];
        const codeRegex = /```(\w+)?\n?([\s\S]*?)```/g;

        let match;
        while ((match = codeRegex.exec(text)) !== null) {
            codeBlocks.push({
                language: match[1] || 'text',
                code: match[2].trim()
            });
        }

        return codeBlocks;
    }

    /**
     * Get sample artifacts for demonstration
     */
    getSampleArtifacts() {
        return [
            {
                id: 'sample_1',
                type: 'python',
                title: 'Sample Python Function',
                content: `def calculate_fibonacci(n):
    \"\"\"Calculate the nth Fibonacci number.\"\"\"
    if n <= 1:
        return n
    return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)

# Example usage
result = calculate_fibonacci(10)
print(f"Fibonacci(10) = {result}")`,
                language: 'python',
                created_at: new Date().toISOString()
            },
            {
                id: 'sample_2',
                type: 'javascript',
                title: 'Sample JavaScript Array Method',
                content: `const users = [
    { name: 'Alice', age: 25 },
    { name: 'Bob', age: 30 },
    { name: 'Charlie', age: 35 }
];

// Filter users over 28 and map their names
const filteredNames = users
    .filter(user => user.age > 28)
    .map(user => user.name.toUpperCase());

console.log(filteredNames); // ['BOB', 'CHARLIE']`,
                language: 'javascript',
                created_at: new Date().toISOString()
            },
            {
                id: 'sample_3',
                type: 'markdown',
                title: 'Sample Documentation',
                content: `# Project Overview

This project implements an AI-powered chat system with multiple workflow capabilities.

## Key Features

- **Session Management**: Persistent, isolated chat sessions
- **Artifact Generation**: Automatic code and document generation
- **Workflow Integration**: Pluggable workflow system
- **Human-in-the-Loop**: Approval and feedback mechanisms

## Getting Started

1. Select a workflow
2. Start a new session or resume an existing one
3. Interact with the AI assistant
4. Review generated artifacts`,
                language: 'markdown',
                created_at: new Date().toISOString()
            }
        ];
    }

    /**
     * Render artifacts in the artifacts tab
     */
    renderArtifacts(artifacts) {
        const artifactContainer = document.getElementById('artifact-list');
        if (!artifactContainer) return;

        if (artifacts.length === 0) {
            artifactContainer.innerHTML = `
                <div class="empty-artifacts">
                    <div class="artifact-icon-large">📎</div>
                    <h3>No artifacts yet</h3>
                    <p>Create sessions and interact with workflows to generate artifacts</p>
                </div>
            `;
            return;
        }

        // Group artifacts by session if they have session_id
        const groupedArtifacts = this.groupArtifactsBySession(artifacts);

        let html = '';

        for (const group of groupedArtifacts) {
            if (group.sessionTitle) {
                html += `<h3 class="artifact-session-title">${group.sessionTitle}</h3>`;
            }

            html += '<div class="artifact-grid">';
            for (const artifact of group.artifacts) {
                html += this.renderArtifactCard(artifact);
            }
            html += '</div>';
        }

        artifactContainer.innerHTML = html;

        // Attach event handlers to artifact buttons
        this.attachArtifactEventHandlers();

        // Apply syntax highlighting after rendering
        this.applySyntaxHighlightingToArtifacts();

        console.log(`[SessionManager] Rendered ${artifacts.length} artifacts with rich formatting`);
    }

    /**
     * Group artifacts by session
     */
    groupArtifactsBySession(artifacts) {
        const grouped = new Map();
        const unsessioned = [];

        for (const artifact of artifacts) {
            if (artifact.session_id) {
                if (!grouped.has(artifact.session_id)) {
                    const session = allSessions.find(s => s.session_id === artifact.session_id);
                    grouped.set(artifact.session_id, {
                        sessionTitle: session ? session.title || 'Unnamed Session' : 'Unknown Session',
                        artifacts: []
                    });
                }
                grouped.get(artifact.session_id).artifacts.push(artifact);
            } else {
                unsessioned.push(artifact);
            }
        }

        const result = [];
        for (const [sessionId, group] of grouped) {
            result.push(group);
        }

        if (unsessioned.length > 0) {
            result.push({
                sessionTitle: 'Miscellaneous',
                artifacts: unsessioned
            });
        }

        return result;
    }

    /**
     * Render a single artifact card
     */
    renderArtifactCard(artifact) {
        const typeIcon = this.getArtifactIcon(artifact.type);
        const language = artifact.language || 'text';
        const size = this.getArtifactSize(artifact.content);

        let contentDisplay;
        if (language === 'markdown' || artifact.type === 'markdown' || artifact.type === 'document') {
            // Render markdown for document artifacts - NO highlighting needed
            contentDisplay = `<div class="markdown-content">${this.renderMarkdownContent(artifact.content)}</div>`;
        } else {
            // Code artifacts with rich syntax highlighting applied directly
            const preview = this.getArtifactPreview(artifact.content, language);
            const highlightedPreview = this.applyArtifactHighlighting(preview, language);
            // highlighting already creates safe HTML, don't double-escape
            contentDisplay = `<pre><code class="artifact-code language-${language}">${highlightedPreview}</code></pre>`;
        }

        return `
            <div class="artifact-card" data-artifact-id="${artifact.id}">
                <div class="artifact-card-header">
                    <span class="artifact-type-icon">${typeIcon}</span>
                    <h4 class="artifact-title">${artifact.title || 'Untitled Artifact'}</h4>
                    <div class="artifact-meta">
                        <span class="artifact-language">${language.toUpperCase()}</span>
                        <span class="artifact-size">${size}</span>
                    </div>
                </div>
                <div class="artifact-content-preview">
                    ${contentDisplay}
                </div>
                <div class="artifact-card-actions">
                    <button class="btn-secondary artifact-copy" data-artifact-id="${artifact.id}">📋 Copy</button>
                    <button class="btn-secondary artifact-download" data-artifact-id="${artifact.id}">💾 Download</button>
                    <button class="btn-secondary artifact-view-full" data-artifact-id="${artifact.id}">👁️ View</button>
                </div>
            </div>
        `;
    }

    /**
     * Get appropriate icon for artifact type
     */
    getArtifactIcon(type) {
        const iconMap = {
            'python': '🐍',
            'javascript': '🟨',
            'code': '💻',
            'markdown': '📝',
            'document': '📄',
            'text': '📄',
            'json': '🎯',
            'html': '🌐',
            'css': '🎨',
            'sql': '🗄️'
        };
        return iconMap[type] || '📎';
    }

    /**
     * Get artifact size information
     */
    getArtifactSize(content) {
        if (!content) return '';

        const size = content.length;

        if (size < 1000) {
            return `${size} chars`;
        } else {
            return `${Math.round(size / 1000)}K chars`;
        }
    }

    /**
     * Get preview of artifact content
     */
    getArtifactPreview(content, language) {
        if (!content) return 'No content available';

        // For code artifacts, limit to first 15 lines
        const lines = content.split('\n');
        const previewLines = lines.slice(0, 15);

        let preview = previewLines.join('\n');

        if (lines.length > 15) {
            preview += '\n\n... (content truncated)';
        }

        return preview;
    }

    /**
     * Render markdown content for document artifacts
     */
    renderMarkdownContent(content) {
        if (!content) return '<em>No content available</em>';

        // Simple markdown parser - converts basic markdown to HTML
        let html = content
            // Convert headers
            .replace(/^### (.*$)/gim, '<h3>$1</h3>')
            .replace(/^## (.*$)/gim, '<h2>$1</h2>')
            .replace(/^# (.*$)/gim, '<h1>$1</h1>')

            // Convert bold and italic
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\_(.*?)\_/g, '<em>$1</em>')

            // Convert links
            .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')

            // Convert line breaks
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>')

            // Wrap in paragraph tags if not already wrapped
            .replace(/^/, '<p>')
            .replace(/$/, '</p>')

            // Fix nested tags
            .replace(/<p><\/p>/g, '')
            .replace(/(<p>)+/g, '<p>')
            .replace(/(<\/p>)+/g, '</p>');

        // Wrap in document class for styling
        return `<div class="markdown-content">${html}</div>`;
    }

    /**
     * Apply syntax highlighting to artifact content
     */
    applyArtifactHighlighting(content, language) {
        if (!content || language === 'text' || language === 'markdown') {
            return content; // Don't escape for text/markdown
        }

        // Create a text node from content and return HTML highlighting
        if (language === 'python') {
            // Basic Python highlighting
            return content
                .replace(/\b(def|class|if|elif|else|for|while|try|except|import|from|return|print)\b/g, '<span class="token keyword">$1</span>')
                .replace(/(['"`])(.*?)\1/g, '<span class="token string">$1$2$1</span>')
                .replace(/(#.*$)/gm, '<span class="token comment">$1</span>');
        }

        if (language === 'javascript') {
            return content
                .replace(/\b(function|const|let|var|if|else|for|while|try|catch|return|console)\b/g, '<span class="token keyword">$1</span>')
                .replace(/('.*?'|".*?"|`.*?`)/g, '<span class="token string">$1</span>')
                .replace(/(\/\/.*$|\/\*[\s\S]*?\*\/)/gm, '<span class="token comment">$1</span>');
        }

        // For unsupported languages, just escape HTML
        return this.escapeHtml(content);
    }

    /**
     * Update artifact count in tab
     */
    updateArtifactCount(count) {
        const countElement = document.getElementById('artifact-count');
        if (countElement) {
            countElement.textContent = `(${count})`;
        }

        // Update tab appearance based on count
        const artifactTab = document.querySelector('.session-tab[data-tab="artifacts"]');
        if (artifactTab) {
            if (count > 0) {
                artifactTab.classList.add('has-content');
            } else {
                artifactTab.classList.remove('has-content');
            }
        }
    }

    /**
     * Handle artifact actions (copy, download, view)
     */
    handleArtifactAction(action, artifactId) {
        const artifact = this.findArtifactById(artifactId);
        if (!artifact) return;

        switch (action) {
            case 'copy':
                this.copyArtifact(artifact);
                break;
            case 'download':
                this.downloadArtifact(artifact);
                break;
            case 'view':
                this.viewArtifact(artifact);
                break;
        }
    }

    /**
     * Find artifact by ID
     */
    findArtifactById(artifactId) {
        // This is a simplified implementation - in a full system,
        // you'd maintain a local artifacts array
        const sampleArtifacts = this.getSampleArtifacts();
        return sampleArtifacts.find(a => a.id === artifactId);
    }

    /**
     * Copy artifact content
     */
    async copyArtifact(artifact) {
        const content = artifact.content || '';

        try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(content);
                if (window.updateStatus) {
                    window.updateStatus('Artifact copied to clipboard', 'success');
                }
            } else {
                // Fallback method
                const textArea = document.createElement('textarea');
                textArea.value = content;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
                if (window.updateStatus) {
                    window.updateStatus('Artifact copied to clipboard', 'success');
                }
            }

            // Visual feedback
            this.showCopyFeedback();

        } catch (error) {
            console.error('[SessionManager] Copy failed:', error);
            if (window.updateStatus) {
                window.updateStatus('Failed to copy artifact', 'error');
            }
        }
    }

    /**
     * Download artifact
     */
    downloadArtifact(artifact) {
        const content = artifact.content || '';
        const filename = this.generateArtifactFilename(artifact);

        try {
            const blob = new Blob([content], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);

            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            if (window.updateStatus) {
                window.updateStatus(`Downloaded ${filename}`, 'success');
            }
        } catch (error) {
            console.error('[SessionManager] Download failed:', error);
            if (window.updateStatus) {
                window.updateStatus('Download failed', 'error');
            }
        }
    }

    /**
     * View artifact in new window/tab with rich formatting
     */
    viewArtifact(artifact) {
        const content = artifact.content || '';
        const title = artifact.title || 'Artifact';
        const language = artifact.language || 'text';

        try {
            const previewWindow = window.open('', '_blank', 'width=900,height=700');
            if (previewWindow) {
                let formattedContent;
                if (language === 'markdown' || artifact.type === 'markdown' || artifact.type === 'document') {
                    formattedContent = this.renderMarkdownContent(content);
                } else if (language === 'python' || language === 'javascript') {
                    formattedContent = this.applyArtifactHighlighting(content, language);
                } else {
                    formattedContent = this.escapeHtml(content);
                }

                previewWindow.document.write(`
                    <html>
                        <head>
                            <title>${title} - Artifact Preview</title>
                            <style>
                                body {
                                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                                    padding: 20px;
                                    margin: 0;
                                    background: #f8f9fa;
                                }
                                h1 {
                                    color: #333;
                                    margin-bottom: 10px;
                                    border-bottom: 2px solid #007bff;
                                    padding-bottom: 8px;
                                }
                                .meta-info {
                                    display: flex;
                                    gap: 20px;
                                    margin-bottom: 20px;
                                    font-size: 14px;
                                    color: #666;
                                }
                                .content-area {
                                    background: white;
                                    border: 1px solid #e0e0e0;
                                    border-radius: 8px;
                                    padding: 20px;
                                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                                }
                                .markdown-content p:first-child { margin-top: 0; }
                                .markdown-content p:last-child { margin-bottom: 0; }
                                h2 { color: #333; border-bottom: 1px solid #ccc; padding-bottom: 5px; }
                                pre {
                                    background: #f8f9fa;
                                    border: 1px solid #dee2e6;
                                    border-radius: 4px;
                                    padding: 15px;
                                    overflow-x: auto;
                                    margin: 10px 0;
                                }
                                code {
                                    font-family: 'Monaco', 'Consolas', monospace;
                                    background: #f1f3f4;
                                    padding: 2px 4px;
                                    border-radius: 3px;
                                }
                                pre code { background: none; padding: 0; }
                                .token.keyword { color: #0000ff; font-weight: bold; }
                                .token.string { color: #008000; }
                                .token.comment { color: #808080; font-style: italic; }
                            </style>
                        </head>
                        <body>
                            <h1>${this.escapeHtml(title)}</h1>
                            <div class="meta-info">
                                <span><strong>Type:</strong> ${language.toUpperCase()}</span>
                                <span><strong>Size:</strong> ${this.getArtifactSize(content)}</span>
                                <span><strong>Date:</strong> ${new Date(artifact.created_at).toLocaleString()}</span>
                            </div>
                            <div class="content-area">
                                ${language === 'markdown' || artifact.type === 'markdown' || artifact.type === 'document'
                                    ? formattedContent
                                    : `<pre><code class="language-${language}">${formattedContent}</code></pre>`}
                            </div>
                        </body>
                    </html>
                `);
                previewWindow.document.close();

                if (window.updateStatus) {
                    window.updateStatus('Artifact opened in preview', 'info');
                }
            }
        } catch (error) {
            console.error('[SessionManager] Preview failed:', error);
            if (window.updateStatus) {
                window.updateStatus('Failed to open preview', 'error');
            }
        }
    }

    /**
     * Generate filename for artifact download
     */
    generateArtifactFilename(artifact) {
        const base = artifact.title || 'artifact';
        const sanitized = base.replace(/[^a-z0-9\-_]/gi, '_').toLowerCase();

        const extension = this.getArtifactFileExtension(artifact.type, artifact.language);
        return `${sanitized}.${extension}`;
    }

    /**
     * Get file extension for artifact type
     */
    getArtifactFileExtension(type, language) {
        if (language === 'python') return 'py';
        if (language === 'javascript') return 'js';
        if (language === 'markdown') return 'md';
        if (language === 'json') return 'json';
        if (language === 'html') return 'html';
        if (language === 'css') return 'css';
        if (language === 'sql') return 'sql';

        return 'txt';
    }

    /**
     * Apply syntax highlighting to rendered artifact content
     */
    applySyntaxHighlightingToArtifacts() {
        // Apply syntax highlighting to all code blocks in artifacts
        document.querySelectorAll('.artifact-card pre code').forEach(codeBlock => {
            const language = codeBlock.className.match(/language-(\w+)/)?.[1];
            if (language) {
                const rawText = codeBlock.textContent;
                const highlighted = this.applyArtifactHighlighting(rawText, language);
                codeBlock.innerHTML = highlighted;
            }
        });

        // Apply markdown rendering to document artifacts
        document.querySelectorAll('.markdown-content').forEach(container => {
            if (container.innerHTML && !container.innerHTML.includes('<h1>')) {
                const rawText = container.textContent;
                const rendered = this.renderMarkdownContent(rawText);
                container.innerHTML = rendered;
            }
        });
    }

    /**
     * Attach event handlers to artifact buttons after rendering
     */
    attachArtifactEventHandlers() {
        // Copy buttons
        document.querySelectorAll('.artifact-copy').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const artifactId = e.target.dataset.artifactId;
                this.handleArtifactAction('copy', artifactId);
            });
        });

        // Download buttons
        document.querySelectorAll('.artifact-download').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const artifactId = e.target.dataset.artifactId;
                this.handleArtifactAction('download', artifactId);
            });
        });

        // View buttons
        document.querySelectorAll('.artifact-view-full').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const artifactId = e.target.dataset.artifactId;
                this.handleArtifactAction('view', artifactId);
            });
        });
    }

    /**
     * Show copy feedback
     */
    showCopyFeedback() {
        // Simple visual feedback - could be enhanced with toast notifications
        console.log('[SessionManager] Artifact copied successfully');
    }

    /**
     * Check if we should show the last session card
     */
    shouldShowLastSession() {
        return allSessions.length > 0;
    }

    /**
     * Normalize workflow type for frontend use
     */
    normalizeWorkflowForFrontend(workflowType) {
        // Remove prefix before first underscore
        if (workflowType && workflowType.includes('_')) {
            return workflowType.substring(workflowType.indexOf('_') + 1);
        }
        return workflowType;
    }

    /**
     * Get workflow display name
     */
    getWorkflowDisplayName(workflow) {
        const displayNames = {
            'agentic-rag': 'Agentic RAG',
            'code-generator': 'Code Generator',
            'deep-research': 'Deep Research',
            'document-generator': 'Document Generator',
            'financial-report': 'Financial Report',
            'human-in-the-loop': 'Human in the Loop',
            'multi-agent': 'Multi-Agent Orchestration'
        };
        return displayNames[workflow] || workflow.replace('-', ' ').replace('_', ' ');
    }

    /**
     * Get workflow icon
     */
    getWorkflowIcon(workflow) {
        const icons = {
            'agentic-rag': '🧠',
            'code-generator': '💻',
            'deep-research': '🔍',
            'document-generator': '📄',
            'financial-report': '📊',
            'human-in-the-loop': '👥',
            'multi-agent': '🔗'
        };
        return icons[workflow] || '💬';
    }

    /**
     * Format relative time
     */
    formatRelativeTime(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffHours = diffMs / (1000 * 60 * 60);

        if (diffHours < 1) {
            const diffMins = Math.floor(diffMs / (1000 * 60));
            return diffMins <= 1 ? 'Just now' : `${diffMins} minutes ago`;
        } else if (diffHours < 24) {
            return `${Math.floor(diffHours)} hours ago`;
        } else {
            const diffDays = Math.floor(diffHours / 24);
            return `${diffDays} days ago`;
        }
    }

    /**
     * Escape HTML characters
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Show error message
     */
    showError(message) {
        console.error('[SessionManager]', message);
        // Implement toast notification or status update
        if (window.updateStatus) {
            window.updateStatus(message, 'error');
        }
    }

    /**
     * Show success message
     */
    showSuccess(message) {
        console.log('[SessionManager]', message);
        if (window.updateStatus) {
            window.updateStatus(message, 'success');
        }
    }

    /**
     * Export all artifacts as a ZIP file
     */
    async exportAllArtifacts() {
        try {
            // Get all current artifacts
            let artifacts = this.getCurrentArtifacts();

            if (artifacts.length === 0) {
                this.showError('No artifacts available to export');
                return;
            }

            // Show loading status
            if (window.updateStatus) {
                window.updateStatus('Preparing artifact export...', 'in-progress');
            }

            // Generate ZIP file with all artifacts
            const zipBlob = await this.generateArtifactsZip(artifacts);

            // Download the ZIP file
            const url = URL.createObjectURL(zipBlob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `artifacts_export_${new Date().toISOString().slice(0, 10)}.zip`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            if (window.updateStatus) {
                window.updateStatus(`Exported ${artifacts.length} artifacts successfully`, 'success');
            }

        } catch (error) {
            console.error('[SessionManager] Export failed:', error);
            this.showError('Failed to export artifacts');
        }
    }

    /**
     * Get current artifacts from various sources
     */
    getCurrentArtifacts() {
        let artifacts = [];

        // Try to get from artifact display manager
        if (window.artifactDisplayManager && window.artifactDisplayManager.getCurrentArtifacts) {
            artifacts = window.artifactDisplayManager.getCurrentArtifacts();
        }

        // If no artifacts, generate from sample data (for demo)
        if (artifacts.length === 0) {
            artifacts = this.getSampleArtifacts();
        }

        return artifacts;
    }

    /**
     * Generate ZIP file containing all artifacts
     */
    async generateArtifactsZip(artifacts) {
        // For this frontend implementation, we'll create a simple text file
        // In a real implementation with ZIP support, you'd use libraries like JSZip

        const exportContent = this.generateExportContent(artifacts);

        // For now, return a single text file (in production, use proper ZIP)
        // Note: Full ZIP implementation would require additional JS libraries
        return new Blob([exportContent], { type: 'text/plain' });
    }

    /**
     * Generate export content for artifacts
     */
    generateExportContent(artifacts) {
        const timestamp = new Date().toISOString();
        let exportContent = `# Artifact Export - ${timestamp}\n`;
        exportContent += `Total Artifacts: ${artifacts.length}\n\n`;

        artifacts.forEach((artifact, index) => {
            exportContent += `=== Artifact ${index + 1} ===\n`;
            exportContent += `Title: ${artifact.title || 'Untitled'}\n`;
            exportContent += `Type: ${artifact.language || artifact.type || 'unknown'}\n`;
            exportContent += `Created: ${artifact.created_at || 'Unknown'}\n`;
            if (artifact.session_id) {
                exportContent += `Session: ${artifact.session_id}\n`;
            }
            exportContent += `\n--- Content ---\n`;

            // Include the content
            const content = artifact.content || 'No content available';
            exportContent += content;
            exportContent += `\n\n--- End Artifact ---\n\n`;
        });

        return exportContent;
    }

    /**
     * Toggle session manager visibility
     */
    toggleSessions() {
        console.log('[SessionManager] Toggling sessions view...');

        // Check if UI exists, create if needed
        if (!this.sessionListContainer) {
            console.log('[SessionManager] Creating on-demand UI...');
            this.setupUI();
        }

        // Use the main UI manager to show/hide
        if (window.mainUIManager) {
            window.mainUIManager.showView('sessions');
        } else {
            console.error('[SessionManager] MainUIManager not available');
        }
    }

    /**
     * Public API methods
     */
    refreshSessions() {
        if (this.sessionListContainer) {
            this.loadAllSessions();
        } else {
            console.log('[SessionManager] UI not created yet, refresh will happen on show');
        }
    }

    getSessionsForWorkflow(workflowType) {
        return allSessions.filter(s => s.workflow_name === workflowType);
    }

    getSessionById(sessionId) {
        return allSessions.find(s => s.session_id === sessionId);
    }
}

// CSS Styles for Session Manager (embedded)
const sessionManagerStyles = `
<style>
.session-manager-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}

.session-manager-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
    padding-bottom: 16px;
    border-bottom: 1px solid #e0e0e0;
}

.session-manager-header h2 {
    margin: 0;
    color: #333;
}

.session-manager-actions {
    display: flex;
    gap: 12px;
    align-items: center;
}

.workflow-filter {
    padding: 8px 12px;
    border: 1px solid #ccc;
    border-radius: 4px;
    background: white;
}

.session-manager-content {
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.session-loading {
    text-align: center;
    padding: 40px;
    color: #666;
}

.session-group {
    background: #f8f9fa;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 16px;
}

.session-group-title {
    margin: 0 0 12px 0;
    color: #333;
    display: flex;
    align-items: center;
    gap: 8px;
}

.session-count {
    color: #666;
    font-size: 0.9em;
    font-weight: normal;
}

.session-group-content {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 16px;
}

.session-card {
    background: white;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 16px;
    cursor: pointer;
    transition: all 0.2s ease;
    position: relative;
}

.session-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    border-color: #007bff;
}

.session-card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 8px;
}

.session-title {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: #333;
    flex: 1;
    cursor: text;
    padding: 4px;
    border-radius: 4px;
    transition: background-color 0.2s;
}

.session-title:hover {
    background-color: #f8f9fa;
}

.session-actions {
    display: flex;
    gap: 4px;
    opacity: 0;
    transition: opacity 0.2s;
}

.session-card:hover .session-actions {
    opacity: 1;
}

.session-action-btn {
    background: none;
    border: none;
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;
    transition: background-color 0.2s;
    font-size: 14px;
}

.session-action-btn:hover {
    background-color: #f8f9fa;
}

.session-meta {
    display: flex;
    gap: 12px;
    font-size: 12px;
    color: #666;
    margin-bottom: 8px;
}

.session-preview {
    color: #555;
    font-size: 14px;
    line-height: 1.4;
    margin-bottom: 12px;
    max-height: 40px;
    overflow: hidden;
}

.session-card-actions {
    display: flex;
    justify-content: flex-end;
}

.btn-primary, .btn-secondary {
    padding: 8px 16px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
    transition: all 0.2s ease;
}

.btn-primary {
    background: #007bff;
    color: white;
}

.btn-primary:hover {
    background: #0056b3;
}

.btn-secondary {
    background: #6c757d;
    color: white;
}

.btn-secondary:hover {
    background: #545b62;
}

.btn-small {
    padding: 4px 8px;
    font-size: 12px;
}

/* Modal Styles */
.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 1000;
}

.modal-overlay.hidden {
    display: none;
}

.modal-content {
    background: white;
    padding: 24px;
    border-radius: 8px;
    max-width: 500px;
    width: 90%;
    max-height: 80vh;
    overflow-y: auto;
}

.modal-content h3 {
    margin-top: 0;
    color: #333;
}

/* Form Styles */
.form-group {
    margin-bottom: 16px;
}

.form-group label {
    display: block;
    margin-bottom: 4px;
    font-weight: 500;
    color: #333;
}

.form-group input, .form-group select {
    width: 100%;
    padding: 8px 12px;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 14px;
}

.form-hint {
    display: block;
    margin-top: 4px;
    font-size: 12px;
    color: #666;
}

.modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 24px;
}

/* Inline Editor */
.inline-editor {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 4px;
}

.inline-editor input {
    flex: 1;
    padding: 4px 8px;
    border: 1px solid #007bff;
    border-radius: 4px;
    font-size: 14px;
}

/* Quick Action Cards */
.quick-action-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 20px;
    border-radius: 8px;
    text-align: center;
}

.quick-action-card h3 {
    margin-top: 0;
    font-size: 18px;
}

.quick-action-card p {
    margin: 8px 0 16px 0;
    opacity: 0.9;
}

.quick-action-card.hidden {
    display: none;
}

/* Empty State */
.empty-state {
    text-align: center;
    padding: 60px 20px;
    color: #666;
}

.empty-state h3 {
    margin-top: 0;
    color: #333;
}

.empty-state p {
    margin: 16px 0 24px 0;
    max-width: 400px;
    margin-left: auto;
    margin-right: auto;
}

/* Responsive Design */
@media (max-width: 768px) {
    .session-manager-header {
        flex-direction: column;
        gap: 16px;
        align-items: stretch;
    }

    .session-manager-actions {
        justify-content: space-between;
    }

    .session-group-content {
        grid-template-columns: 1fr;
    }

    .session-card-header {
        flex-direction: column;
        gap: 8px;
    }

    .session-actions {
        opacity: 1; /* Always show on mobile */
    }
}

/* Tab Navigation Styles */
.session-tabs {
    display: flex;
    border-bottom: 1px solid #e0e0e0;
    margin-bottom: 20px;
}

.session-tab {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    border: none;
    background: none;
    cursor: pointer;
    border-bottom: 3px solid transparent;
    color: #666;
    font-size: 14px;
    font-weight: 500;
    transition: all 0.2s ease;
}

.session-tab.active {
    color: #007bff;
    border-bottom-color: #007bff;
}

.session-tab.has-content {
    font-weight: 600;
}

.session-tab:hover {
    color: #007bff;
    background: #f8f9fa;
}

.tab-icon {
    font-size: 16px;
}

.tab-label {
    font-weight: inherit;
}

.artifact-count {
    background: #e9ecef;
    color: #495057;
    padding: 2px 6px;
    border-radius: 10px;
    font-size: 12px;
    font-weight: 500;
    transition: background-color 0.2s;
}

.session-tab.has-content .artifact-count {
    background: #cce7ff;
    color: #007bff;
}

/* Tab Content Styles */
.tab-content {
    display: none;
}

.tab-content.active {
    display: block;
}

/* Artifact Styles */
.artifact-list {
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.artifact-loading, .artifact-error {
    text-align: center;
    padding: 40px;
    color: #666;
}

.artifact-error {
    color: #dc3545;
}

.artifact-session-title {
    font-size: 18px;
    color: #333;
    margin: 0 0 12px 0;
    border-bottom: 1px solid #e0e0e0;
    padding-bottom: 8px;
}

.artifact-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
    gap: 16px;
}

.artifact-card {
    background: white;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 16px;
    transition: all 0.2s ease;
}

.artifact-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    border-color: #007bff;
}

.artifact-card-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
}

.artifact-type-icon {
    font-size: 20px;
}

.artifact-title {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: #333;
    flex: 1;
}

.artifact-meta {
    display: flex;
    gap: 8px;
    align-items: center;
}

.artifact-language, .artifact-size {
    font-size: 11px;
    color: #666;
    background: #f8f9fa;
    padding: 2px 6px;
    border-radius: 4px;
    text-transform: uppercase;
    font-weight: 500;
}

.artifact-content-preview {
    margin-bottom: 12px;
}

.artifact-code {
    margin: 0;
    font-size: 13px;
    line-height: 1.4;
    max-height: 150px;
    overflow-y: auto;
}

.artifact-card-actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
}

.artifact-card .btn-secondary {
    font-size: 12px;
    padding: 6px 12px;
}

/* Syntax Highlighting */
.token.keyword {
    color: #0000ff;
    font-weight: bold;
}

.token.string {
    color: #008000;
}

.token.comment {
    color: #808080;
    font-style: italic;
}

/* Empty Artifacts State */
.empty-artifacts {
    text-align: center;
    padding: 60px 20px;
    color: #666;
}

.empty-artifacts .artifact-icon-large {
    font-size: 48px;
    margin-bottom: 16px;
    opacity: 0.6;
}

.empty-artifacts h3 {
    margin-top: 0;
    color: #333;
}

.empty-artifacts p {
    margin: 16px 0 0 0;
    max-width: 400px;
    margin-left: auto;
    margin-right: auto;
}
</style>
`;

// Initialize Session Manager
document.addEventListener('DOMContentLoaded', () => {
    // Inject styles
    document.head.insertAdjacentHTML('beforeend', sessionManagerStyles);

    // Initialize session manager
    window.sessionManager = new SessionManager();

    console.log('[SessionManager] Session manager module loaded');
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SessionManager;
}
