/**
 * HistoryManager - UI Manager for Chat History Sessions
 *
 * Manages the UI for browsing and displaying chat history sessions.
 * Delegates session management operations to HistorySession from session.js.
 * Provides workflow selection, session browsing, and content display.
 */

// IMMEDIATE EXECUTION CHECK - Log as soon as script starts
if (typeof window !== 'undefined' && typeof document !== 'undefined') {

    // Prevent duplicate initialization
    if (window.historyUI) {
        console.warn('[HistoryUI] window.historyUI already exists');
    }
}

/**
 * HistoryManager - Manages UI for chat history browsing
 * Delegates to HistorySession from session.js for data operations
 */
class HistoryManager {
    constructor() {
        // Initialize all properties
        this.workflows = [];
        this.currentWorkflowId = null;
        this.historySession = null;  // HistorySession instance from session.js
        this.selectedSessionId = null;
        this.selectedSessionData = null;  // Store session data for metadata
        this.uiInitialized = false;
    }

    /**
     * Initialize the History UI
     */
    async initializeUI() {

        try {
            // ✅ Workflows are already provided by createHistorySession() in activateHistoryUI()
            // No need to load them separately - they come from backend system config

            // Create UI structure
            this.createUI();

            this.uiInitialized = true;
        } catch (error) {
            console.error('[HistoryUI] Failed to initialize UI:', error);
            throw error;
        }
    }



    /**
     * Create the complete UI structure
     */
    createUI() {
        const container = document.getElementById('chat-history-ui-container');
        if (!container) {
            console.error('[HistoryUI] Chat history container not found');
            return;
        }

        container.innerHTML = `
            <!-- Workflow Tabs Section -->
            <div class="history-workflow-tabs-container" id="history-tabs-container">
                <div class="history-workflow-tabs" id="history-workflow-tabs">
                    <!-- Workflow tabs will be populated here -->
                </div>
            </div>

            <!-- Main Content Area -->
            <div class="history-main-content">
                <!-- Left Panel: Session List -->
                <div class="history-session-list-panel">
                    <div class="history-session-list-header">
                        <h4 id="history-current-workflow-title">Select a Workflow</h4>
                    </div>
                    <div class="history-session-list" id="history-session-list">
                        <div class="history-no-workflow-selected">
                            <div class="history-placeholder-content">
                                <div class="history-workflow-icon-large">📋</div>
                                <h3>Select a Workflow</h3>
                                <p>Choose a workflow tab above to view its chat sessions</p>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Right Panel: Expandable Metadata + Content/Artifacts -->
                <div class="history-content-panel" id="history-content-panel">
                    <!-- Session Metadata Expandable -->
                    <div class="history-metadata-section" id="history-metadata-section">
                        <div class="history-metadata-header">
                            <span class="history-metadata-toggle" id="history-metadata-toggle">▶</span>
                            <h4>Session Information</h4>
                            <div class="history-session-actions" id="history-session-actions">
                                <!-- Management buttons will be populated here -->
                            </div>
                        </div>
                        <div class="history-metadata-content" id="history-metadata-content" style="display: none;">
                            <!-- Metadata details will be populated here -->
                        </div>
                    </div>

                    <!-- Scrollable Content/Artifacts Area -->
                    <div class="history-content-area" id="history-content-area">
                        <div class="history-content-placeholder">
                            <div class="history-content-icon">💬</div>
                            <h3>Select a session to view content</h3>
                            <p>Choose a session from the list to see messages and artifacts</p>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Create workflow tabs
        this.createWorkflowTabs();

        // FORCE CONTAINER CONSTRAINT - JavaScript override
        const containerDiv = document.getElementById('history-tabs-container');
        if (!containerDiv) return;

        // Ensure container has horizontal scrolling
        const viewportWidth = window.innerWidth;
        const constrainedWidth = Math.max(800, viewportWidth - 200);

        containerDiv.style.width = `${constrainedWidth}px`;
        containerDiv.style.maxWidth = `${constrainedWidth}px`;
        containerDiv.style.overflowX = 'auto';
        containerDiv.style.overflowY = 'hidden';

        // Attach event handlers - only mouse wheel
        this.attachEventHandlers();
    }

    /**
     * Create horizontal scrolling workflow tabs
     */
    createWorkflowTabs() {
        const tabsContainer = document.getElementById('history-workflow-tabs');
        if (!tabsContainer) {
            console.error('[HistoryUI] Tabs container not found, cannot create workflow tabs');
            return;
        }

        tabsContainer.innerHTML = '';

        this.workflows.forEach((workflow) => {
            const tabElement = document.createElement('button');
            tabElement.className = 'history-workflow-tab';
            tabElement.dataset.workflowId = workflow.id;
            tabElement.innerHTML = `
                <span class="history-tab-icon">${workflow.icon}</span>
                <span class="history-tab-label">${workflow.display_name}</span>
                <span class="history-tab-badge" id="history-tab-badge-${workflow.id}">${workflow.session_count || 0}</span>
            `;

            tabsContainer.appendChild(tabElement);
        });

        // Select first tab by default if available
    }

    /**
     * Attach event handlers for UI interactions
     */
    attachEventHandlers() {
        // Mouse wheel scrolling
        const tabsContainer = document.getElementById('history-workflow-tabs');
        const containerDiv = document.getElementById('history-tabs-container');

        if (containerDiv && tabsContainer) {
            // Mouse wheel on tabs
            tabsContainer.addEventListener('wheel', (e) => {
                e.preventDefault();
                const scrollAmount = e.deltaY > 0 ? 100 : -100;
                // Scroll the container
                containerDiv.scrollLeft += scrollAmount;
            });
        }

        // Tab selection
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('history-workflow-tab') ||
                e.target.closest('.history-workflow-tab')) {
                const tabElement = e.target.classList.contains('history-workflow-tab') ?
                    e.target : e.target.closest('.history-workflow-tab');
                this.selectWorkflow(tabElement.dataset.workflowId, true);
            }
        });

        // Metadata toggle
        const metadataToggle = document.getElementById('history-metadata-toggle');
        if (metadataToggle) {
            metadataToggle.addEventListener('click', () => this.toggleMetadata());
        }
    }

    /**
     * Scroll workflow tabs horizontally
     */
    scrollTabs(amount) {
        const containerDiv = document.getElementById('history-tabs-container');
        if (containerDiv) {
            const newScrollLeft = Math.max(0, Math.min(containerDiv.scrollWidth - containerDiv.clientWidth, containerDiv.scrollLeft + amount));

            containerDiv.scrollTo({
                left: newScrollLeft,
                behavior: 'smooth'
            });
        } else {
            console.error('[ScrollTabs] Container div not found for scrolling');
        }
    }

    /**
     * Update workflow tab badge with session count
     */
    updateWorkflowTabBadge(workflowId, count) {
        const badge = document.getElementById(`history-tab-badge-${workflowId}`);
        if (badge) {
            if (count > 0) {
                badge.textContent = count > 99 ? '99+' : count.toString();
                badge.style.display = 'inline-block';
            } else {
                badge.style.display = 'none';
            }
        }
    }

    /**
     * Show session load error in the UI
     */
    showSessionLoadError(message) {
        const sessionList = document.getElementById('history-session-list');
        if (sessionList) {
            sessionList.innerHTML = `
                <div class="history-error-display">
                    <div class="history-error-icon">⚠️</div>
                    <h3>Failed to Load Sessions</h3>
                    <p>${message}</p>
                    <button onclick="window.historyUI.selectWorkflow('${this.currentWorkflowId}', true)" style="padding: 8px 16px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer;">
                        Retry
                    </button>
                </div>
            `;
        }
    }

    /**
     * Toggle metadata section visibility
     */
    toggleMetadata() {
        const metadataContent = document.getElementById('history-metadata-content');
        const metadataToggle = document.getElementById('history-metadata-toggle');

        if (metadataContent && metadataToggle) {
            const isVisible = metadataContent.style.display !== 'none';
            metadataContent.style.display = isVisible ? 'none' : 'block';
            metadataToggle.textContent = isVisible ? '▶' : '▼';
        }
    }


    /**
     * Render session list for current workflow using infrastructure session
     */
    async renderSessionListForWorkflow(workflowId) {

        const sessionList = document.getElementById('history-session-list');
        if (!sessionList) {
            console.error('[HistoryUI] Session list element not found');
            return;
        }

        // ✅ Use infrastructure session for all operations
        if (!window.historySessionId) {
            console.warn('[HistoryUI] No infrastructure session available for rendering');
            this.showNoSessionsPlaceholder();
            return;
        }

        // Get real sessions from backend using infrastructure session
        let sessions = [];
        try {
            // ✅ Use infrastructure session for API calls
            const data = await window.apiUtils.getWorkflowHistoryStats(window.historySessionId, workflowId);
            sessions = data.sessions || [];
        } catch (error) {
            console.warn('[HistoryUI] Failed to load sessions from backend:', error);
            this.showSessionLoadError(error.message);
            return;
        }

        if (sessions.length === 0) {
            console.log('[HistoryUI] No sessions available for workflow');
            this.showNoSessionsPlaceholder();
            return;
        }

        // Sort sessions by last updated (most recent first)
        const sortedSessions = [...sessions].sort((a, b) =>
            new Date(b.updated_at) - new Date(a.updated_at)
        );

        // Render session list
        sessionList.innerHTML = '';

        sortedSessions.forEach(session => {
            const sessionElement = this.createSessionListItem(session);
            sessionList.appendChild(sessionElement);
        });

        // Initialize search functionality for this list
        this.attachSessionSelectionHandlers();
    }

    /**
     * Simulate workflow sessions (delegate to HistorySession when available)
     */
    simulateWorkflowSessions(workflowId) {
        // Simulate some sessions for the workflow
        const sessions = [];
        const baseTime = new Date();
        const sessionCount = Math.floor(Math.random() * 8) + 3; // 3-10 sessions

        for (let i = 1; i <= sessionCount; i++) {
            sessions.push({
                session_id: `session_${workflowId}_${i}`,
                title: `Chat Session ${i} - ${workflowId}`,
                message_count: Math.floor(Math.random() * 20) + 5,
                created_at: new Date(baseTime.getTime() - (i * 24 * 60 * 60 * 1000)).toISOString(),
                updated_at: new Date(baseTime.getTime() - (i * 2 * 60 * 60 * 1000)).toISOString()
            });
        }

        return sessions;
    }

    /**
     * Create a session list item element with message preview and action menu
     */
    createSessionListItem(session) {
        const itemElement = document.createElement('div');
        itemElement.className = 'history-session-item';
        itemElement.dataset.sessionId = session.session_id;

        const lastActive = this.formatSessionTime(session.updated_at);

        // Check if session is bookmarked
        const isBookmarked = session.bookmarked || (session.metadata && session.metadata.bookmarked);

        // Generate message preview from session data
        let messagePreview = this.generateMessagePreview(session);

        // session.title is now the user-editable friendly name
        const displayTitle = session.title || messagePreview.title;

        itemElement.innerHTML = `
            <div class="history-session-item-content">
                <div class="history-session-title">
                    ${isBookmarked ? '<span class="bookmark-indicator">⭐</span>' : ''}
                    <span class="session-title-text">${displayTitle}</span>
                </div>
                <div class="history-session-preview">${messagePreview.preview}</div>
                <div class="history-session-meta">
                    <span class="history-session-messages">${session.message_count} messages</span>
                    <span class="history-session-time">• ${lastActive}</span>
                </div>
            </div>
            <div class="history-session-actions">
                <button class="history-session-action-btn" data-action="menu" title="Session actions">⚙️</button>
                <button class="history-session-action-btn" data-action="select" title="Select session">👁️</button>
            </div>
        `;

        // Add click handler for the main content (select session)
        const contentArea = itemElement.querySelector('.history-session-item-content');
        if (contentArea) {
            contentArea.addEventListener('click', (e) => {
                // Don't select if clicking on title (for editing)
                if (!e.target.closest('.session-title-text')) {
                    this.selectSession(session.session_id);
                }
            });
        }

        // Add click handler for title editing
        const titleText = itemElement.querySelector('.session-title-text');
        if (titleText) {
            titleText.addEventListener('click', (e) => {
                e.stopPropagation();
                this.startTitleEdit(session.session_id, titleText);
            });
        }

        return itemElement;
    }

    /**
     * Generate human-readable message preview for session list
     */
    generateMessagePreview(session) {
        let title = session.title || 'Untitled Session';
        let preview = '';

        // If we have messages, show the first user message or first message
        if (session.messages && session.messages.length > 0) {
            // Find the first user message
            const firstUserMessage = session.messages.find(msg => msg.role === 'user');
            const firstMessage = firstUserMessage || session.messages[0];

            if (firstMessage && firstMessage.content) {
                // Clean up the message content for preview
                let content = firstMessage.content.trim();

                // Remove excessive whitespace and newlines
                content = content.replace(/\s+/g, ' ').substring(0, 80);

                // Create preview with sender indicator
                const sender = firstMessage.role === 'user' ? 'You' : 'AI';
                preview = `${sender}: ${content}${content.length >= 80 ? '...' : ''}`;
            }
        }

        // If no messages or no content, show fallback
        if (!preview) {
            preview = `${session.message_count || 0} messages`;
        }

        return { title, preview };
    }

    /**
     * Attach session selection event handlers
     */
    attachSessionSelectionHandlers() {
        // Event delegation for session actions
        document.addEventListener('click', (e) => {
            const actionBtn = e.target.closest('.history-session-action-btn');
            if (actionBtn) {
                e.stopPropagation(); // Prevent session selection
                const sessionItem = actionBtn.closest('.history-session-item');
                if (sessionItem) {
                    const sessionId = sessionItem.dataset.sessionId;
                    const action = actionBtn.dataset.action;

                    if (action === 'select') {
                        this.selectSession(sessionId);
                    } else if (action === 'menu') {
                        this.showSessionActionMenu(sessionId, actionBtn);
                    }
                }
            }
        });

        // Close action menu when clicking elsewhere
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.history-session-action-menu') && !e.target.closest('.history-session-action-btn')) {
                this.closeAllActionMenus();
            }
        });
    }

    /**
     * Show action menu for a session
     */
    showSessionActionMenu(sessionId, buttonElement) {
        // Close any existing menus
        this.closeAllActionMenus();

        // Create menu element
        const menu = document.createElement('div');
        menu.className = 'history-session-action-menu';
        menu.dataset.sessionId = sessionId;

        menu.innerHTML = `
            <div class="action-menu-item" data-action="bookmark">
                <span class="action-icon">⭐</span>
                <span class="action-text">Toggle Bookmark</span>
            </div>
            <div class="action-menu-item" data-action="edit_title">
                <span class="action-icon">✏️</span>
                <span class="action-text">Edit Title</span>
            </div>
            <div class="action-menu-item" data-action="clear_messages">
                <span class="action-icon">🗑️</span>
                <span class="action-text">Delete Messages Only</span>
            </div>
            <div class="action-menu-item" data-action="delete_session">
                <span class="action-icon">🗑️</span>
                <span class="action-text">Delete Entire Session</span>
            </div>
            <div class="action-menu-item" data-action="edit_messages">
                <span class="action-icon">✏️</span>
                <span class="action-text">Edit Messages</span>
            </div>
        `;

        // Position menu
        const rect = buttonElement.getBoundingClientRect();
        menu.style.position = 'fixed';
        menu.style.top = `${rect.bottom + 5}px`;
        menu.style.left = `${rect.left}px`;
        menu.style.zIndex = '1000';

        // Add menu event handlers
        menu.addEventListener('click', (e) => {
            const menuItem = e.target.closest('.action-menu-item');
            if (menuItem) {
                const action = menuItem.dataset.action;
                this.handleSessionAction(action, sessionId);
                this.closeAllActionMenus();
            }
        });

        // Add to document
        document.body.appendChild(menu);

        // Store reference for cleanup
        this.activeActionMenu = menu;
    }

    /**
     * Close all open action menus
     */
    closeAllActionMenus() {
        if (this.activeActionMenu) {
            document.body.removeChild(this.activeActionMenu);
            this.activeActionMenu = null;
        }
    }

    /**
     * Handle session action from menu
     */
    async handleSessionAction(action, sessionId) {

        try {
            switch (action) {
                case 'bookmark':
                    await this.toggleSessionBookmark(sessionId);
                    break;
                case 'edit_title':
                    await this.startTitleEdit(sessionId);
                    break;
                case 'clear_messages':
                    await this.confirmAndClearMessages(sessionId);
                    break;
                case 'delete_session':
                    await this.confirmAndDeleteSession(sessionId);
                    break;
                case 'edit_messages':
                    await this.showMessageEditor(sessionId);
                    break;
                default:
                    console.warn(`[HistoryUI] Unknown action: ${action}`);
            }
        } catch (error) {
            console.error(`[HistoryUI] Error handling action ${action}:`, error);
            this.showActionError(`Failed to ${action.replace('_', ' ')}: ${error.message}`);
        }
    }

    /**
     * Toggle bookmark status for a session
     */
    async toggleSessionBookmark(sessionId) {
        if (!window.historySessionId) {
            throw new Error('No history session available');
        }

        const response = await fetch(`/api/history/${window.historySessionId}/chat_session/${sessionId}/bookmark`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to toggle bookmark');
        }

        const result = await response.json();

        // Update UI
        await this.refreshSessionList();

        // Show feedback
        this.showActionFeedback(result.bookmarked ? 'Session bookmarked' : 'Bookmark removed');
    }

    /**
     * Start inline title editing
     */
    async startTitleEdit(sessionId, titleElement = null) {
        // Find the session item
        const sessionItem = document.querySelector(`[data-session-id="${sessionId}"]`);
        if (!sessionItem) return;

        const titleText = titleElement || sessionItem.querySelector('.session-title-text');
        if (!titleText) return;

        // Get the current display title (might include emoji)
        const displayTitle = titleText.textContent.trim();

        // Get the actual title from session data (without emoji prefix)
        let actualTitle = displayTitle;
        if (displayTitle.startsWith('📝 ')) {
            actualTitle = displayTitle.substring(2);
        } else if (displayTitle.startsWith('⭐ ')) {
            // If it starts with bookmark, remove that too
            const withoutBookmark = displayTitle.substring(2);
            if (withoutBookmark.startsWith('📝 ')) {
                actualTitle = withoutBookmark.substring(2);
            } else {
                actualTitle = withoutBookmark;
            }
        }

        // Create input element with the clean title
        const input = document.createElement('input');
        input.type = 'text';
        input.value = actualTitle;
        input.className = 'title-edit-input';
        input.style.width = '100%';
        input.style.padding = '4px';
        input.style.border = '1px solid #007bff';
        input.style.borderRadius = '4px';
        input.style.fontSize = '14px';

        // Replace text with input
        titleText.innerHTML = '';
        titleText.appendChild(input);
        input.focus();
        input.select();

        // Handle save/cancel
        const saveEdit = async () => {
            const newTitle = input.value.trim();
            if (newTitle && newTitle !== actualTitle) {
                await this.saveTitleEdit(sessionId, newTitle);
            } else {
                // Restore original display
                titleText.innerHTML = displayTitle;
            }
        };

        const cancelEdit = () => {
            titleText.innerHTML = displayTitle;
        };

        input.addEventListener('blur', saveEdit);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                saveEdit();
            } else if (e.key === 'Escape') {
                e.preventDefault();
                cancelEdit();
            }
        });
    }

    /**
     * Save title edit to backend
     */
    async saveTitleEdit(sessionId, newTitle) {
        if (!window.historySessionId) {
            throw new Error('No history session available');
        }

        const response = await fetch(`/api/history/${window.historySessionId}/chat_session/${sessionId}/title`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: newTitle })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to update title');
        }

        const result = await response.json();

        // Refresh the session list to show updated title
        await this.refreshSessionList();

        this.showActionFeedback('Title updated successfully');
    }

    /**
     * Confirm and clear messages from session
     */
    async confirmAndClearMessages(sessionId) {
        if (!(await window.showConfirm('Clear Messages', 'Are you sure you want to clear all messages from this session? This action cannot be undone.', { type: 'danger', confirmText: 'Clear All' }))) {
            return;
        }

        if (!window.historySessionId) {
            throw new Error('No history session available');
        }

        const response = await fetch(`/api/history/${window.historySessionId}/chat_session/${sessionId}/messages`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to clear messages');
        }

        const result = await response.json();

        // Refresh session list and content
        await this.refreshSessionList();
        if (this.selectedSessionId === sessionId) {
            await this.renderSessionContent(sessionId);
        }

        this.showActionFeedback(`${result.messages_cleared} messages cleared from session`);
    }

    /**
     * Confirm and delete entire session
     */
    async confirmAndDeleteSession(sessionId) {
        if (!(await window.showConfirm('Delete Session', 'Are you sure you want to permanently delete this entire session? This action cannot be undone.', { type: 'danger', confirmText: 'Delete Session' }))) {
            return;
        }

        if (!window.historySessionId) {
            throw new Error('No history session available');
        }

        const response = await fetch(`/api/history/${window.historySessionId}/chat_session/${sessionId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to delete session');
        }

        // Refresh session list and clear selection if this session was selected
        await this.refreshSessionList();
        if (this.selectedSessionId === sessionId) {
            this.selectedSessionId = null;
            this.showContentPlaceholder();
        }

        this.showActionFeedback('Session deleted successfully');
    }

    /**
     * Show message editor for the selected session
     */
    async showMessageEditor(sessionId) {
        if (!this.selectedSessionData || !this.selectedSessionData.messages) {
            throw new Error('No messages available for editing');
        }

        // Create message editor modal
        const modal = document.createElement('div');
        modal.className = 'message-editor-modal';
        modal.innerHTML = `
            <div class="message-editor-overlay">
                <div class="message-editor-content">
                    <div class="message-editor-header">
                        <h3>Edit Messages</h3>
                        <button class="message-editor-close" onclick="this.closest('.message-editor-modal').remove()">×</button>
                    </div>
                    <div class="message-editor-body">
                        <div class="message-editor-instructions">
                            Click on any message to edit its content. Changes are saved automatically.
                        </div>
                        <div class="message-editor-list" id="message-editor-list">
                            <!-- Messages will be populated here -->
                        </div>
                    </div>
                    <div class="message-editor-footer">
                        <button class="message-editor-save" onclick="window.historyUI.saveMessageEdits('${sessionId}')">Save All Changes</button>
                        <button class="message-editor-cancel" onclick="this.closest('.message-editor-modal').remove()">Close</button>
                    </div>
                </div>
            </div>
        `;

        // Populate messages
        const messageList = modal.querySelector('#message-editor-list');
        this.selectedSessionData.messages.forEach((message, index) => {
            const messageItem = document.createElement('div');
            messageItem.className = 'message-editor-item';
            messageItem.innerHTML = `
                <div class="message-editor-role">${message.role === 'user' ? 'You' : 'AI'}:</div>
                <div class="message-editor-content" contenteditable="true" data-message-id="${message.message_id || index}" data-original-content="${message.content.replace(/"/g, '"')}">${message.content}</div>
            `;
            messageList.appendChild(messageItem);
        });

        document.body.appendChild(modal);
        this.activeMessageEditor = modal;
    }

    /**
     * Save message edits from the editor modal
     */
    async saveMessageEdits(sessionId) {
        if (!this.activeMessageEditor) return;

        const messageItems = this.activeMessageEditor.querySelectorAll('.message-editor-content');
        const edits = [];

        messageItems.forEach(item => {
            const messageId = item.dataset.messageId;
            const newContent = item.textContent.trim();
            const originalContent = item.dataset.originalContent;

            if (newContent !== originalContent) {
                edits.push({
                    message_id: messageId,
                    content: newContent
                });
            }
        });

        if (edits.length === 0) {
            this.activeMessageEditor.remove();
            this.activeMessageEditor = null;
            return;
        }

        // Save edits to backend
        try {
            for (const edit of edits) {
                await this.saveMessageEdit(sessionId, edit.message_id, edit.content);
            }

            // Refresh content
            if (this.selectedSessionId === sessionId) {
                await this.renderSessionContent(sessionId);
            }

            this.showActionFeedback(`${edits.length} message(s) updated successfully`);

        } catch (error) {
            console.error('Error saving message edits:', error);
            this.showActionError(`Failed to save message edits: ${error.message}`);
        }

        // Close modal
        this.activeMessageEditor.remove();
        this.activeMessageEditor = null;
    }

    /**
     * Save individual message edit
     */
    async saveMessageEdit(sessionId, messageId, content) {
        if (!window.historySessionId) {
            throw new Error('No history session available');
        }

        const response = await fetch(`/api/history/${window.historySessionId}/chat_session/${sessionId}/message/${messageId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: content })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to update message');
        }

        const result = await response.json();
        return result;
    }

    /**
     * Refresh the session list
     */
    async refreshSessionList() {
        if (this.currentWorkflowId) {
            await this.renderSessionListForWorkflow(this.currentWorkflowId);
        }
    }

    /**
     * Show action feedback message
     */
    showActionFeedback(message) {
        this.showToast(message, 'success');
    }

    /**
     * Show action error message
     */
    showActionError(message) {
        this.showToast(message, 'error');
    }

    /**
     * Show toast notification
     */
    showToast(message, type = 'info') {
        // Remove existing toasts
        const existingToasts = document.querySelectorAll('.history-toast');
        existingToasts.forEach(toast => toast.remove());

        // Create new toast
        const toast = document.createElement('div');
        toast.className = `history-toast history-toast-${type}`;
        toast.textContent = message;

        // Style the toast
        Object.assign(toast.style, {
            position: 'fixed',
            top: '20px',
            right: '20px',
            padding: '12px 20px',
            borderRadius: '6px',
            color: 'white',
            fontSize: '14px',
            fontWeight: '500',
            zIndex: '10000',
            opacity: '0',
            transition: 'opacity 0.3s ease',
            boxShadow: '0 4px 12px rgba(0,0,0,0.3)'
        });

        if (type === 'success') {
            toast.style.backgroundColor = '#28a745';
        } else if (type === 'error') {
            toast.style.backgroundColor = '#dc3545';
        } else {
            toast.style.backgroundColor = '#007bff';
        }

        document.body.appendChild(toast);

        // Animate in
        setTimeout(() => {
            toast.style.opacity = '1';
        }, 10);

        // Auto remove after 3 seconds
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        }, 3000);
    }

    /**
     * Show placeholder when no sessions are available
     */
    showNoSessionsPlaceholder() {
        const sessionList = document.getElementById('history-session-list');
        if (sessionList) {
            sessionList.innerHTML = `
                <div class="history-no-sessions">
                    <div class="history-placeholder-content">
                        <div class="history-session-icon">📝</div>
                        <h3>No Chat Sessions</h3>
                        <p>No sessions found for this workflow. Start chatting to create your first session!</p>
                    </div>
                </div>
            `;
        }
    }

    /**
     * Select and display a session using infrastructure session API calls
     */
    async selectSession(sessionId) {

        if (!window.historySessionId) {
            console.error('[HistoryUI] No infrastructure session available');
            return;
        }

        try {
            this.selectedSessionId = sessionId;

            // Update session selection in UI
            this.updateSessionSelectionUI(sessionId);

            // Render session content using API call
            this.renderSessionContent(sessionId);

            // Update metadata section
            this.updateSessionMetadata();

        } catch (error) {
            console.error(`[HistoryUI] Failed to select session ${sessionId}:`, error);
            this.showSessionContentError(error.message);
        }
    }

    /**
     * Update session selection UI to show selected state
     */
    updateSessionSelectionUI(sessionId) {
        // Clear previous selection
        document.querySelectorAll('.history-session-item').forEach(item => {
            item.classList.remove('selected');
        });

        // Mark selected session
        const selectedItem = document.querySelector(`[data-session-id="${sessionId}"]`);
        if (selectedItem) {
            selectedItem.classList.add('selected');
        }
    }

    /**
     * Render session content (messages and artifacts) in the content area using API call
     */
    async renderSessionContent(sessionId) {
        const contentArea = document.getElementById('history-content-area');
        if (!contentArea || !window.historySessionId) return;

        try {
            // Get session data from backend using infrastructure session
            const sessionData = await window.apiUtils.getHistorySessionData(window.historySessionId, sessionId);
            this.selectedSessionData = sessionData;  // Store for metadata use
            const messages = sessionData?.messages || [];
            const artifacts = sessionData?.artifacts || [];

            // Check if session has any content
            const hasMessages = messages.length > 0;
            const hasArtifacts = artifacts.length > 0;

            if (!hasMessages && !hasArtifacts) {
                contentArea.innerHTML = `<div style="text-align: center; padding: 50px; color: #666;"><div style="font-size: 48px; margin-bottom: 16px;">📝</div><h3>Empty Session</h3><p>This session contains no messages or artifacts.</p></div>`;
                return;
            }

            // Render content using the same approach as chat UI
            contentArea.innerHTML = '';

            // Render artifacts section first (if any)
            if (hasArtifacts) {
                // Create artifacts section header
                const artifactsHeader = document.createElement('div');
                artifactsHeader.className = 'history-artifacts-header';
                artifactsHeader.innerHTML = `
                    <h3 style="margin: 20px 0 10px 0; color: #333; border-bottom: 2px solid #007bff; padding-bottom: 8px;">
                        📎 Generated Artifacts (${artifacts.length})
                    </h3>
                `;
                contentArea.appendChild(artifactsHeader);

                // Use ArtifactDisplayManager to render artifacts
                if (window.artifactDisplayManager) {
                    try {
                        // Create a temporary container for artifacts
                        const artifactsContainer = document.createElement('div');
                        artifactsContainer.id = 'history-artifacts-container';
                        artifactsContainer.style.marginBottom = '30px';

                        contentArea.appendChild(artifactsContainer);

                        // Render artifacts using the same manager as chat
                        window.artifactDisplayManager.displayArtifacts(artifacts, artifactsContainer);

                        console.log(`[HistoryUI] Successfully rendered ${artifacts.length} artifacts`);
                    } catch (artifactError) {
                        console.error('[HistoryUI] Failed to render artifacts:', artifactError);
                        // Fallback: Show simple artifact list
                        this.renderSimpleArtifactsList(artifacts, contentArea);
                    }
                } else {
                    // Fallback if ArtifactDisplayManager not available
                    this.renderSimpleArtifactsList(artifacts, contentArea);
                }
            }

            // Render messages section
            if (hasMessages) {
                // Create messages section header
                const messagesHeader = document.createElement('div');
                messagesHeader.className = 'history-messages-header';
                messagesHeader.innerHTML = `
                    <h3 style="margin: 20px 0 10px 0; color: #333; border-bottom: 2px solid #28a745; padding-bottom: 8px;">
                        💬 Chat Messages (${messages.length})
                    </h3>
                `;
                contentArea.appendChild(messagesHeader);

                // Render messages using the same approach as chat UI
                for (const message of messages) {
                    const messageElement = document.createElement('div');
                    messageElement.classList.add('message', message.role === 'user' ? 'user-message' : 'ai-message');

                    let content = message.content;

                    // FIX: Await the async renderMessage call for proper rich text rendering
                    if (window.richTextRenderer && message.enhanced_metadata) {
                        content = await window.richTextRenderer.renderMessage(message.content, {
                            enhanced_metadata: message.enhanced_metadata,
                            workflowId: this.currentWorkflowId
                        });
                    }

                    let modelInfoHtml = '';
                    if (message.role !== 'user' && message.enhanced_metadata && message.enhanced_metadata.model_id) {
                        const provider = message.enhanced_metadata.model_provider || 'AI';
                        modelInfoHtml = `<div class="message-model-info">${provider}: ${message.enhanced_metadata.model_id}</div>`;
                    }

                    messageElement.innerHTML = `
                        <div class="message-sender">${message.role === 'user' ? 'You' : 'AI'}</div>
                        <div class="message-content">
                            ${modelInfoHtml}
                            ${content}
                        </div>
                    `;

                    contentArea.appendChild(messageElement);
                }
            }

            // Scroll to top to show latest content
            contentArea.scrollTop = 0;

            console.log(`[HistoryUI] Successfully rendered session with ${messages.length} messages and ${artifacts.length} artifacts`);

        } catch (error) {
            console.error(`[HistoryUI] Failed to load session content for ${sessionId}:`, error);
            this.showSessionContentError(error.message);
        }
    }

    /**
     * Render simple artifacts list as fallback
     */
    renderSimpleArtifactsList(artifacts, container) {
        const artifactsList = document.createElement('div');
        artifactsList.className = 'history-simple-artifacts';
        artifactsList.innerHTML = '<h4>Generated Files:</h4>';

        const list = document.createElement('ul');
        artifacts.forEach(artifact => {
            const item = document.createElement('li');
            item.innerHTML = `<strong>${artifact.file_name || artifact.title || 'Unknown'}</strong> (${artifact.type || 'file'})`;
            list.appendChild(item);
        });

        artifactsList.appendChild(list);
        container.appendChild(artifactsList);
    }

    /**
     * Update session metadata section with current session info
     */
    updateSessionMetadata() {
        const metadataContent = document.getElementById('history-metadata-content');
        const actionsContainer = document.getElementById('history-session-actions');

        if (!metadataContent || !actionsContainer || !this.selectedSessionData) {
            return;
        }

        const sessionData = this.selectedSessionData;

        if (sessionData) {
            metadataContent.innerHTML = `
                <div class="session-metadata-item">
                    <strong>Session ID:</strong> ${this.selectedSessionId.substring(0, 8)}...
                </div>
                <div class="session-metadata-item">
                    <strong>Title:</strong> ${sessionData.title || 'Unknown'}
                </div>
                <div class="session-metadata-item">
                    <strong>Messages:</strong> ${sessionData.messages?.length || 0}
                </div>
                <div class="session-metadata-item">
                    <strong>Created:</strong> ${sessionData.created_at ? new Date(sessionData.created_at).toLocaleString() : 'Unknown'}
                </div>
                <div class="session-metadata-item">
                    <strong>Last Updated:</strong> ${sessionData.updated_at ? new Date(sessionData.updated_at).toLocaleString() : 'Unknown'}
                </div>
            `;

            // Simple action buttons (can be extended)
            actionsContainer.innerHTML = `
                <button class="history-action-btn" onclick="console.log('Export session')" title="Export Session">📄</button>
                <button class="history-action-btn" onclick="console.log('Copy session')" title="Copy to Clipboard">📋</button>
            `;
        }
    }

    /**
     * Show error when session content loading fails
     */
    showSessionContentError(message) {
        const contentArea = document.getElementById('history-content-area');
        if (contentArea) {
            contentArea.innerHTML = `
                <div style="text-align: center; padding: 50px; color: #dc3545;">
                    <div style="font-size: 48px; margin-bottom: 16px;">⚠️</div>
                    <h3>Failed to Load Session</h3>
                    <p>${message}</p>
                    <button onclick="window.historyUI.selectSession('${this.selectedSessionId}')" style="padding: 8px 16px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer;">
                        Retry
                    </button>
                </div>
            `;
        }
    }

    /**
     * Show content placeholder
     */
    showContentPlaceholder() {
        const container = document.getElementById('history-content-area');
        if (container) {
            container.innerHTML = `
                <div style="text-align: center; padding: 50px;">
                    <div style="font-size: 48px; margin-bottom: 20px;">💬</div>
                    <h3>Chat History Manager</h3>
                    <p>Navigation of workflows history conversations</p>
                    <p style="color: green; font-weight: bold;">Choose a workflow tab above, then select a session to view its content.</p>
                </div>
            `;
        }
    }

    /**
     * Select workflow - uses infrastructure session for all operations
     */
    async selectWorkflow(workflowId, fromUser = false) {

        // Clear selected session
        this.selectedSessionId = null;
        this.currentWorkflowId = workflowId;

        // Update UI to show selected workflow
        document.querySelectorAll('.history-workflow-tab').forEach(tab => {
            tab.classList.remove('active');
        });
        const activeTab = document.querySelector(`[data-workflow-id="${workflowId}"]`);
        if (activeTab) {
            activeTab.classList.add('active');
        }

        // Update workflow title
        const titleElement = document.getElementById('history-current-workflow-title');
        const workflow = this.workflows.find(w => w.id === workflowId);
        if (titleElement) {
            titleElement.textContent = workflow ? workflow.display_name : 'Unknown Workflow';
        }

        try {
            // ✅ Use infrastructure session for all operations - no additional session creation
            console.log(`[HistoryUI] Using infrastructure session ${window.historySessionId} for workflow ${workflowId}`);

            // Render session list using infrastructure session
            this.renderSessionListForWorkflow(workflowId);

            // Show placeholder in content area
            this.showContentPlaceholder();

            console.log(`[HistoryUI] Successfully selected workflow ${workflowId} with infrastructure session`);

        } catch (error) {
            console.error(`[HistoryUI] Failed to load sessions for workflow ${workflowId}:`, error);
            this.showSessionLoadError(error.message);
        }
    }

    /**
     * Format session time for display
     */
    formatSessionTime(dateString) {
        try {
            const date = new Date(dateString);
            const now = new Date();
            const diffMs = now - date;
            const diffHours = diffMs / (1000 * 60 * 60);

            if (diffHours < 24) {
                return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            } else if (diffHours < 168) { // 7 days
                return `${Math.floor(diffHours / 24)} days ago`;
            } else {
                return date.toLocaleDateString();
            }
        } catch (error) {
            return 'Unknown';
        }
    }
}

// CSS Styles for History UI (minimal)
const historyUICSS = `
<style>
/* History UI Styles */

.history-workflow-tabs-container {
    position: relative;
    background: #f8f9fa;
    border-bottom: 1px solid #e0e0e0;
    /* KEY FIX: Force width constraint with !important */
    width: calc(100vw - 200px) !important;
    max-width: calc(100vw - 200px) !important;
    min-width: 800px !important;
    margin: 0 auto;
    overflow-x: auto !important;
    overflow-y: hidden !important;
}

@media (max-width: 1200px) {
    .history-workflow-tabs-container {
        width: calc(100vw - 100px); /* Smaller screens, still leave space for buttons */
        min-width: 600px;
    }
}

@media (max-width: 800px) {
    .history-workflow-tabs-container {
        width: calc(100vw - 50px); /* Very small screens */
        min-width: 400px;
    }
}

.history-workflow-tabs {
    display: flex;
    /* Remove overflow-x: scrolling moved to parent container */
    min-width: max-content; /* Allow natural width expansion for flex items */
}

/* OPTION 5: Styled Native Scrollbar */
.history-workflow-tabs-container::-webkit-scrollbar {
    height: 8px; /* Horizontal scrollbar height */
}

.history-workflow-tabs-container::-webkit-scrollbar-track {
    background: #f1f1f1; /* Track color */
    border-radius: 4px;
}

.history-workflow-tabs-container::-webkit-scrollbar-thumb {
    background: #007bff; /* Thumb color */
    border-radius: 4px;
    transition: background 0.2s ease;
}

.history-workflow-tabs-container::-webkit-scrollbar-thumb:hover {
    background: #0056b3; /* Thumb hover color */
}

/* Firefox scrollbar styling */
.history-workflow-tabs-container {
    scrollbar-width: thin; /* Thin scrollbar for Firefox */
    scrollbar-color: #007bff #f1f1f1; /* Thumb color Track color for Firefox */
}

.history-workflow-tab {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 12px;
    border: none;
    background: transparent;
    cursor: pointer;
    border-radius: 6px;
    transition: all 0.2s ease;
    white-space: nowrap;
    min-width: 120px;
    justify-content: center;
}

.history-workflow-tab:hover {
    background: #e9ecef;
    border-color: #007bff;
    opacity: 1;
}

.history-workflow-tab.active {
    background: #007bff;
    color: white;
    box-shadow: 0 2px 4px rgba(0,123,255,0.3);
}

.history-workflow-tab:not(.active) {
    color: #495057;
    border: 1px solid #dee2e6;
    background: #f8f9fa;
    opacity: 0.8;
}

.history-tab-icon {
    font-size: 16px;
}

.history-tab-label {
    font-size: 12px;
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
}

.history-tab-badge {
    display: none;
    background: #dc3545;
    color: white;
    font-size: 10px;
    padding: 1px 4px;
    border-radius: 8px;
    min-width: 16px;
    text-align: center;
    font-weight: bold;
}

.history-workflow-tab.active .history-tab-badge {
    background: rgba(255,255,255,0.8);
    color: #007bff;
}

.history-main-content {
    display: flex;
    height: calc(100vh - 120px);
}

.history-session-list-panel {
    width: 320px;
    border-right: 1px solid #e0e0e0;
    background: #fafbfc;
    display: flex;
    flex-direction: column;
}

.history-session-list-header {
    padding: 16px;
    border-bottom: 1px solid #e0e0e0;
    background: white;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.history-current-workflow-title {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: #333;
}

.history-session-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px 0;
}

.history-no-workflow-selected,
.history-no-sessions,
.history-content-placeholder {
    display: flex;
    justify-content: center;
    align-items: center;
    text-align: center;
    color: #666;
    min-height: 200px;
}

.history-placeholder-content {
    max-width: 300px;
}

.history-workflow-icon-large,
.history-content-icon,
.history-error-icon {
    font-size: 48px;
    margin-bottom: 16px;
    opacity: 0.6;
}

.history-no-workflow-selected h3,
.history-no-sessions h3,
.history-content-placeholder h3 {
    margin: 0 0 8px 0;
    color: #333;
}

.history-no-workflow-selected p,
.history-no-sessions p,
.history-content-placeholder p {
    margin: 0 0 16px 0;
}

.history-content-panel {
    flex: 1;
    display: flex;
    flex-direction: column;
    background: white;
}

.history-metadata-section {
    border-bottom: 1px solid #e0e0e0;
    background: #fafbfc;
}

.history-metadata-header {
    display: flex;
    align-items: center;
    padding: 8px 16px;
    cursor: pointer;
    background: #f8f9fa;
}

.history-metadata-toggle {
    margin-right: 8px;
    color: #666;
    font-size: 12px;
    transition: transform 0.2s;
}

.history-metadata-header h4 {
    margin: 0;
    font-size: 14px;
    font-weight: 500;
    color: #333;
    flex: 1;
}

.history-session-actions {
    display: flex;
    gap: 4px;
}

.history-metadata-content {
    padding: 16px;
    background: white;
    display: none;
}

.history-content-area {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
}

/* Session item styles */
.history-session-item {
    padding: 12px 16px;
    margin: 4px 8px;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s ease;
    border: 1px solid #e0e0e0;
    background: white;
}

.history-session-item:hover {
    background: #f8f9fa;
    border-color: #007bff;
}

.history-session-item.selected {
    background: #e3f2fd;
    border-color: #007bff;
    box-shadow: 0 2px 4px rgba(0,123,255,0.2);
}

.history-session-item-content {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.history-session-title {
    font-size: 14px;
    font-weight: 500;
    color: #333;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.history-session-preview {
    font-size: 12px;
    color: #666;
    font-style: italic;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    margin-bottom: 2px;
}

.history-session-meta {
    display: flex;
    gap: 8px;
    font-size: 12px;
    color: #666;
}

.history-session-actions {
    margin-top: 8px;
    display: flex;
    justify-content: flex-end;
}

.history-session-action-btn {
    background: none;
    border: none;
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;
    transition: background 0.2s ease;
    font-size: 14px;
}

.history-session-action-btn:hover {
    background: #e9ecef;
}

.history-action-btn {
    background: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 4px;
    padding: 4px 8px;
    cursor: pointer;
    font-size: 12px;
    transition: all 0.2s ease;
}

.history-action-btn:hover {
    background: #e9ecef;
    border-color: #007bff;
}

.session-metadata-item {
    margin-bottom: 8px;
    font-size: 13px;
}

.session-metadata-item strong {
    color: #333;
}

/* Session Actions Menu */
.history-session-action-menu {
    background: white;
    border: 1px solid #dee2e6;
    border-radius: 6px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    padding: 4px 0;
    min-width: 160px;
    z-index: 1000;
}

.action-menu-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    cursor: pointer;
    transition: background 0.2s ease;
    font-size: 14px;
    border: none;
    background: transparent;
    width: 100%;
    text-align: left;
}

.action-menu-item:hover {
    background: #f8f9fa;
}

.action-icon {
    font-size: 16px;
    width: 20px;
    text-align: center;
}

.action-text {
    flex: 1;
}

/* Bookmark indicator */
.bookmark-indicator {
    color: #ffc107;
    margin-right: 4px;
}

/* Title editing */
.session-title-text {
    cursor: pointer;
    transition: background 0.2s ease;
    padding: 2px 4px;
    border-radius: 3px;
}

.session-title-text:hover {
    background: rgba(0,123,255,0.1);
}

/* Message Editor Modal */
.message-editor-modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10000;
}

.message-editor-overlay {
    background: white;
    border-radius: 8px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    max-width: 800px;
    max-height: 80vh;
    width: 90%;
    display: flex;
    flex-direction: column;
}

.message-editor-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    border-bottom: 1px solid #e0e0e0;
}

.message-editor-header h3 {
    margin: 0;
    color: #333;
}

.message-editor-close {
    background: none;
    border: none;
    font-size: 24px;
    cursor: pointer;
    color: #666;
    padding: 0;
    width: 30px;
    height: 30px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.message-editor-body {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
}

.message-editor-instructions {
    background: #f8f9fa;
    padding: 12px;
    border-radius: 6px;
    margin-bottom: 16px;
    font-size: 14px;
    color: #666;
}

.message-editor-list {
    max-height: 400px;
    overflow-y: auto;
}

.message-editor-item {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 12px;
    margin-bottom: 8px;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    background: #fafbfc;
}

.message-editor-role {
    font-weight: 600;
    color: #495057;
    min-width: 40px;
    font-size: 14px;
    padding-top: 2px;
}

.message-editor-content {
    flex: 1;
    padding: 8px;
    border: 1px solid #dee2e6;
    border-radius: 4px;
    background: white;
    font-size: 14px;
    line-height: 1.4;
    min-height: 60px;
    outline: none;
}

.message-editor-content:focus {
    border-color: #007bff;
    box-shadow: 0 0 0 2px rgba(0,123,255,0.25);
}

.message-editor-footer {
    display: flex;
    gap: 12px;
    justify-content: flex-end;
    padding: 16px 20px;
    border-top: 1px solid #e0e0e0;
    background: #f8f9fa;
}

.message-editor-save,
.message-editor-cancel {
    padding: 8px 16px;
    border-radius: 4px;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.2s ease;
}

.message-editor-save {
    background: #28a745;
    color: white;
    border: 1px solid #28a745;
}

.message-editor-save:hover {
    background: #218838;
    border-color: #1e7e34;
}

.message-editor-cancel {
    background: #6c757d;
    color: white;
    border: 1px solid #6c757d;
}

.message-editor-cancel:hover {
    background: #5a6268;
    border-color: #545b62;
}

/* Toast notifications */
.history-toast {
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 12px 20px;
    border-radius: 6px;
    color: white;
    font-size: 14px;
    font-weight: 500;
    z-index: 10000;
    opacity: 0;
    transition: opacity 0.3s ease;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}

.history-toast-success {
    background-color: #28a745;
}

.history-toast-error {
    background-color: #dc3545;
}

.history-toast-info {
    background-color: #007bff;
}
</style>
`;

// Inject CSS styles
if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            if (!document.getElementById('history-ui-css')) {
                const style = document.createElement('style');
                style.id = 'history-ui-css';
                style.innerHTML = historyUICSS;
                document.head.appendChild(style);
            }
        });
    } else {
        if (!document.getElementById('history-ui-css')) {
            const style = document.createElement('style');
            style.id = 'history-ui-css';
            style.innerHTML = historyUICSS;
            document.head.appendChild(style);
        }
    }
}

// Create and set global object
try {
    window.historyUI = new HistoryManager();
} catch (error) {
    console.error('[HistoryUI] Failed to create HistoryManager:', error);
    console.error('[HistoryUI] Error details:', error.message, error.stack);
}

// FOLLOW WORKFLOW PATTERN: History activation handled by HistoryManager class
window.activateHistoryUI = async function () {
    console.log('[HistoryUI] 🚀 activateHistoryUI called - following Workflow pattern');

    try {
        // Check if already activated AND currently visible
        const historyContainer = document.getElementById('chat-history-ui-container');
        const isCurrentlyVisible = historyContainer && historyContainer.style.display !== 'none';

        if (window.historyUI && window.historyUI.uiInitialized && window.historySessionId && isCurrentlyVisible) {
            console.log('[HistoryUI] Already fully activated and visible, skipping');
            return;
        }

        // ✅ FOLLOW WORKFLOW PATTERN: Create session infrastructure first
        console.log('[HistoryUI] 🔧 Creating history session infrastructure (following workflow pattern)');

        const sessionData = await window.apiUtils.createHistorySession();

        // ✅ STORE BACKEND SESSION ID globally for History UI
        window.historySessionId = sessionData.session_id;
        window.historySessionReady = true;

        // ✅ FOLLOW WORKFLOW PATTERN: Store infrastructure session in sessionManager
        if (window.sessionManager?.setInfrastructureSession) {
            window.sessionManager.setInfrastructureSession('history', sessionData.session_id);
            console.log('[HistoryUI] ✅ SRR: Registered history infrastructure session:', sessionData.session_id);
        }

        // ✅ STORE WORKFLOW LIST for UI tabs - History UI gets complete workflow info from backend
        window.availableWorkflows = sessionData.workflows || [];

        // ✅ SET WORKFLOWS DIRECTLY IN HISTORY UI - no need for separate loadWorkflows() call
        if (window.historyUI) {
            window.historyUI.workflows = window.availableWorkflows.map(workflow => ({
                id: workflow.id,
                display_name: workflow.display_name,
                icon: workflow.icon,
                session_count: 0 // Will be updated when tabs are created
            }));
            console.log('[HistoryUI] History UI workflows set directly from session creation:', window.historyUI.workflows);
        }

        console.log('[HistoryUI] History session ready with workflows:', window.availableWorkflows);

        // ✅ FOLLOW WORKFLOW PATTERN: Initialize UI after session infrastructure
        if (window.historyUI) {
            await window.historyUI.initializeUI();
            console.log('[HistoryUI] ✅ History UI initialized successfully');

            // ✅ FOLLOW WORKFLOW PATTERN: Show history view after initialization
            if (window.mainUIManager?.showView) {
                window.mainUIManager.showView('chat_history');
                console.log('[HistoryUI] ✅ History view shown');
            } else {
                console.error('[HistoryUI] ❌ MainUIManager not available to show history view');
            }
        } else {
            console.error('[HistoryUI] ❌ HistoryManager not available for UI initialization');
        }

    } catch (error) {
        console.error('[HistoryUI] ❌ Failed to activate History UI:', error);
        throw error;
    }
};

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = HistoryManager;
}
