/**
 * Workflow Manager - SRR Session Management Integration
 *
 * Handles workflow selection, loading, and management using SRR session registry.
 * Separated from monolithic script.js for better maintainability.
 * Now uses sessionManager for all session operations instead of direct state management.
 */

// Global workflow state
let availableWorkflows = [];
let workflowUIConfigs = {}; // Store UI configurations per workflow

// Core Workflow Manager Class
class WorkflowManager {
    constructor() {
        this.currentWorkflow = null;
        this.sessionManagementEnabled = true;
        this.currentSubPanelOperation = false; // 🛡️ Prevent concurrent sub-panel operations
        this.initializeWorkflowSystem();
    }

    /**
     * Initialize the workflow system
     */
    async initializeWorkflowSystem() {
        try {
            await this.loadAvailableWorkflows();
            this.renderWelcomePage();
            this.renderLeftPanelMenu();
            this.attachEventHandlers();
        } catch (error) {
            console.error('[WorkflowManager] Failed to initialize workflow system:', error);
        }
    }

    /**
     * Load available workflows from API
     */
    async loadAvailableWorkflows() {
        try {
            const workflowsData = await window.apiUtils.getAvailableWorkflows();

            // Assign to global variable
            availableWorkflows = workflowsData.workflows || [];

            // Store UI configurations for each workflow
            workflowUIConfigs = {};
            availableWorkflows.forEach(workflow => {
                if (workflow.ui_config) {
                    workflowUIConfigs[workflow.id] = workflow.ui_config;
                }
            });
            return availableWorkflows;
        } catch (error) {
            console.error('[WorkflowManager] Error loading workflows:', error);
            availableWorkflows = [];
            return [];
        }
    }

    /**
     * Get workflow by ID
     */
    getWorkflowById(workflowId) {
        return availableWorkflows.find(w => w.id === workflowId);
    }

    /**
     * Render welcome page workflow grid
     */
    renderWelcomePage() {
        const workflowGrid = document.getElementById('dynamic-workflow-grid');
        if (!workflowGrid) {
            console.warn('[WorkflowManager] Dynamic workflow grid not found');
            return;
        }

        if (availableWorkflows.length > 0) {
            // Generate dynamic workflow cards from API data
            const workflowCards = availableWorkflows.map(workflow =>
                this.generateWorkflowCard(workflow)
            ).join('');
            workflowGrid.innerHTML = workflowCards;
        } else {
            workflowGrid.innerHTML = `
                <div class="error-message">
                    <strong>No workflows available</strong><br>
                    Please check your system configuration and try refreshing the page.
                </div>
            `;
        }
    }

    /**
     * Render left panel workflow menu
     */
    renderLeftPanelMenu() {
        const dynamicWorkflowsContent = document.getElementById('dynamic-workflows-content');
        if (!dynamicWorkflowsContent) {
            console.warn('[WorkflowManager] Dynamic workflows content element not found');
            return;
        }

        const workflowsList = dynamicWorkflowsContent.querySelector('.workflows-list');
        if (!workflowsList) {
            console.warn('[WorkflowManager] Workflows list element not found');
            return;
        }

        if (!workflowsList) {
            console.warn('[WorkflowManager] Workflows list element not found');
            return;
        }

        if (availableWorkflows.length > 0) {
            // Clear existing workflow items
            workflowsList.querySelectorAll('.workflows').forEach(li => li.remove());

            // Add new workflow items
            availableWorkflows.forEach(workflow => {
                const menuItem = this.generateWorkflowMenuItem(workflow);
                workflowsList.insertAdjacentHTML('beforeend', menuItem);
            });

        } else {
            console.warn('[WorkflowManager] No workflows available to display in left panel');
        }
    }

    /**
     * Generate workflow card HTML from configuration
     */
    generateWorkflowCard(workflow) {
        return `
            <div class="workflow-card" data-workflow="${workflow.id}">
                <div class="workflow-icon">${workflow.icon}</div>
                <div class="workflow-info">
                    <strong>${workflow.display_name}</strong>
                    <small>${workflow.description}</small>
                </div>
                <button class="select-workflow-btn" data-workflow="${workflow.id}">Select</button>
            </div>
        `;
    }

    /**
     * Generate workflow menu item HTML from configuration
     */
    generateWorkflowMenuItem(workflow) {
        const displayName = workflow.display_name.replace(/ /g, '&nbsp;'); // Preserve spaces in button text

        return `
            <li class="workflows">
                <button class="menu-button workflow-button" data-workflow="${workflow.id}" title="${workflow.display_name}">
                    <span class="inline-icon">${workflow.icon}</span>
                    <span>${displayName}</span>
                </button>
            </li>
        `;
    }

    /**
     * Attach event handlers for workflow interactions
     * ULTRA-SIMPLIFIED: All buttons use single entry function
     */
    attachEventHandlers() {
        // Remove existing event handlers first to prevent duplicates
        document.querySelectorAll('.workflow-button').forEach(button => {
            const newButton = button.cloneNode(true);
            button.parentNode.replaceChild(newButton, button);
        });

        // Welcome page workflow selection - ENTRY: workflowId only, use active session
        document.querySelectorAll('.select-workflow-btn').forEach(button => {
            button.addEventListener('click', async (event) => {
                event.preventDefault();
                const workflowId = event.target.getAttribute('data-workflow');

                if (workflowId) {
                    console.log(`[WorkflowManager] Welcome page workflow selection: ${workflowId}`);
                    // Get active session and call single entry function
                    const sessions = await this.createWorkflowSessionAndGetSessions(workflowId);
                    const activeSessionId = sessions.length > 0 ? sessions[0].session_id : null;
                    await this.selectWorkflowSession(activeSessionId, workflowId);
                }
            });
        });

        // Left panel workflow selection - ENTRY: workflowId only, use active session
        document.querySelectorAll('.workflow-button').forEach(button => {
            button.addEventListener('click', async (event) => {
                const target = event.target.closest('button[data-workflow]');
                if (!target) return;

                const workflowId = target.dataset.workflow;
                if (workflowId) {
                    console.log(`[WorkflowManager] Left panel workflow selection: ${workflowId}`);
                    // Get active session and call single entry function
                    const sessions = await this.createWorkflowSessionAndGetSessions(workflowId);
                    const activeSessionId = sessions.length > 0 ? sessions[0].session_id : null;
                    await this.selectWorkflowSession(activeSessionId, workflowId);
                }
            });
        });
    }



    /**
     * RENDER BACKEND WORKFLOW DECISIONS (PURE VIEW METHOD)
     * Backend enhanced endpoint returns session context - frontend renders UI
     */
    renderBackendWorkflowDecision(workflowId, sessionData) {
        if (sessionData && sessionData.session_id && sessionData.should_resume) {
            // Case 1: Backend recommends resuming an existing session
            this.renderResumeWorkflowSession(workflowId, sessionData);
        } else {
            // Case 2: Backend recommends starting a fresh workflow
            this.renderStartFreshWorkflow(workflowId);
        }
    }

    /**
     * RENDER: Resume existing workflow session (Pure View)
     * PRESERVES SESSION CONTEXT for ACTION 1→2 continuity
     */
    renderResumeWorkflowSession(workflowId, sessionData) {
        // 🎯 CRITICAL: PRESERVE SESSION CONTEXT for ACTION 2 message sending
        if (window.chatUIManager) {
            window.chatUIManager.setSessionContext(sessionData, workflowId);
        } else {
            console.warn(`[WorkflowManager] ⚠️ chatUIManager not available - session context not passed`);
        }

        // Start workflow with existing session (backend already created/validated it)
        this.selectWorkflow(workflowId, sessionData.session_id);
    }

    /**
     * RENDER: Start fresh workflow (Pure View)
     */
    renderStartFreshWorkflow(workflowId) {
        // Start workflow without session (backend handles creation)
        this.selectWorkflow(workflowId);
    }

    /**
     * Select workflow and coordinate with chat interface
     * ENHANCED: Now checks for and loads existing sessions automatically
     * @param {string} workflowId - The workflow ID to select
     * @param {string|null} forcedSessionId - Optional session ID to force resume
     */
    async selectWorkflow(workflowId, forcedSessionId = null) {
        // 🛡️ CRITICAL: Clear previous workflow UI state before starting new workflow
        // Pass keepSubPanelVisible to preserve sub-panel for session switching
        await this.clearWorkflowUI(false); // Always clear sub-panel when selecting a new workflow

        // Set current workflow in both manager and global state
        this.currentWorkflow = workflowId;
        window.globalState.currentWorkflow = workflowId;

        // Update chat UI manager context
        if (window.chatUIManager) {
            window.chatUIManager.setCurrentWorkflow(workflowId);
        }

        // Clear workflow progress and hide artifact panel when switching workflows
        if (window.artifactDisplayManager) {
            if (window.artifactDisplayManager.clearWorkflowProgress) {
                window.artifactDisplayManager.clearWorkflowProgress();
            }
            if (window.artifactDisplayManager.hidePanel) {
                window.artifactDisplayManager.hidePanel();
            }
        }

        // STATUS BAR UPDATE: Always show current workflow in status bar
        const workflowDisplayName = workflowId.replace('_', ' ').toUpperCase();
        if (window.mainUIManager?.setStatusBar) {
            window.mainUIManager.setStatusBar('current_workflow', workflowDisplayName);
        } else if (window.setStatusBar) {
            window.setStatusBar('current_workflow', workflowDisplayName);
        } else {
            console.warn(`[WorkflowManager] No status bar update function available`);
        }

        // PERSIST WORKFLOW: Update user_state.toml with current workflow selection
        try {
            const response = await fetch('/api/user_state/workflow', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ workflow: workflowId })
            });

            if (response.ok) {
                console.log(`[WorkflowManager] ✅ Persisted workflow ${workflowId} to user_state.toml`);
            } else {
                console.warn(`[WorkflowManager] ⚠️ Failed to persist workflow to user_state.toml: ${response.status}`);
            }
        } catch (error) {
            console.warn(`[WorkflowManager] ⚠️ Error persisting workflow to user_state.toml:`, error);
        }

        // 🎯 MVC CORRECT: Backend creates real session immediately
        // No frontend placeholder logic - backend provides real session context
        let existingSessionId = forcedSessionId;

        // Show loading page with session context
        if (window.showLoadingPage) {
            const workflowName = workflowId.replace('-', ' ').toUpperCase();
            const statusMsg = existingSessionId ? 'Resuming your previous conversation...' : 'Loading RAG indexes...';
            window.showLoadingPage(`${workflowName} Workflow`, statusMsg);
        }

        // Navigate to CHAT interface with potential session resumption
        setTimeout(async () => {
            try {
                // 🗑️ LEGACY SESSION MANAGEMENT REMOVED - Now pure MVC View
                // Session creation and management moved to backend (WorkflowSession.create_for_workflow())
                // Frontend is now pure View layer - no session creation logic

                // Switch to chat interface view
                if (window.mainUIManager) {
                    window.mainUIManager.showView('chat');
                }

                // ATTEMPT TO RESUME EXISTING SESSION
                if (existingSessionId) {
                    try {
                        const resumeSuccess = await window.chatUIManager.resumeWorkflowSession(existingSessionId);
                        if (resumeSuccess) {
                            // 🎯 CRITICAL: Set session context for chat UI manager after successful resumption
                            // This enables message sending for single-session workflows
                            const sessionData = {
                                session_id: existingSessionId,
                                websocket_url: `/api/workflow/${existingSessionId}/stream` // Use session_id for WebSocket URL
                            };

                            try {
                                window.chatUIManager.setSessionContext(sessionData, workflowId);
                            } catch (contextError) {
                                console.error(`[WorkflowManager] ❌ Failed to set session context for resumed session:`, contextError);
                            }

                            if (window.updateStatus) {
                                window.updateStatus('Previous conversation resumed', 'success');
                            }
                        } else {
                            existingSessionId = null; // Reset to force fresh session creation
                        }
                    } catch (resumeError) {
                        console.error(`[WorkflowManager] ❌ Error resuming session:`, resumeError);
                        existingSessionId = null; // Reset for fresh session
                    }
                }

                // Show workflow controls in chat interface
                if (window.workflowControlsManager) {
                    const status = existingSessionId ? 'active' : 'idle';
                    window.workflowControlsManager.showWorkflowControls(workflowId, status);
                }

            } catch (error) {
                console.error('[WorkflowManager] Error during workflow selection:', error);
                if (window.updateStatus) {
                    window.updateStatus('Error loading workflow', 'error');
                }
            }
        }, 1500);
    }

    /**
     * Get current workflow
     */
    getCurrentWorkflow() {
        return this.currentWorkflow;
    }

    /**
     * Set current workflow
     */
    setCurrentWorkflow(workflowId) {
        this.currentWorkflow = workflowId;
        if (window.chatUIManager) {
            window.chatUIManager.setCurrentWorkflow(workflowId);
        }
    }

    /**
     * Get available workflows
     */
    getAvailableWorkflows() {
        return availableWorkflows;
    }

    /**
     * Refresh workflows list
     */
    async refreshWorkflows() {
        await this.loadAvailableWorkflows();
        this.renderWelcomePage();
        this.renderLeftPanelMenu();
        console.log('[WorkflowManager] Workflows refreshed');
    }

    /**
     * Clear workflow UI state before switching workflows
     * FIXES: UI keeping content from previous workflow
     * @param {boolean} keepSubPanelVisible - Whether to keep workflow sub-panel visible for session switching
     */
    async clearWorkflowUI(keepSubPanelVisible = false) {

        try {
            // Clear chat interface messages
            const messageContainer = document.getElementById('message-container');
            if (messageContainer) {
                messageContainer.innerHTML = '';
            }

            // Clear any workflow-specific UI components
            if (window.chatUIManager) {
                if (window.chatUIManager.clearMessages) {
                    window.chatUIManager.clearMessages();
                }
                if (window.chatUIManager.clearCurrentWorkflow) {
                    window.chatUIManager.clearCurrentWorkflow();
                }
            }

            // Clear artifact display if present
            if (window.artifactDisplayManager) {
                if (window.artifactDisplayManager.clearAll) {
                    window.artifactDisplayManager.clearAll();
                }
            }

            // Handle session panels based on keepSubPanelVisible flag
            if (!keepSubPanelVisible) {
                // Hide any existing session panels that might be lingering
                // BUT DON'T hide if we just created an enhanced sub-panel for user selection
                const hasPendingSubPanel = document.querySelector('[id^="current-workflow-sessions-content-"]');
                if (!hasPendingSubPanel) {
                    this.hideWorkflowSessions();
                } else {
                    console.log(`[WorkflowManager] 🛡️ Preserving newly created sub-panel for user selection: ${hasPendingSubPanel.id}`);
                }
            } else {
                console.log(`[WorkflowManager] 🔄 Keeping sub-panel visible for session switching within workflow`);
            }

            // Reset workflow controls to idle state
            if (window.workflowControlsManager) {
                if (window.workflowControlsManager.showWorkflowControls) {
                    window.workflowControlsManager.showWorkflowControls(null, 'idle');
                }
            }

            // Clear the loading page state if shown
            if (window.hideLoadingPage) {
                window.hideLoadingPage();
            }

            console.log(`[WorkflowManager] ✅ Workflow UI state cleared successfully`);

        } catch (error) {
            console.error(`[WorkflowManager] ❌ Error clearing workflow UI state:`, error);
        }
    }

    /**
     * CREATE WORKFLOW SESSION INFRASTRUCTURE AND GET SESSIONS
     * Consolidated single operation that creates infrastructure and returns sessions
     * This prevents the multiple session creation issue
     */
    async createWorkflowSessionAndGetSessions(workflowId) {
        console.log(`[WorkflowManager] 🔧 Creating session infrastructure and getting sessions for ${workflowId}`);

        try {
            // Use the consolidated backend endpoint that creates infrastructure AND returns sessions
            const response = await fetch('/api/workflow/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    workflow_id: workflowId,
                    include_sessions: true
                })
            });

            if (!response.ok) {
                console.error(`[WorkflowManager] Failed to create infrastructure and get sessions for ${workflowId}: ${response.status}`);
                throw new Error(`HTTP ${response.status}: Failed to create workflow infrastructure`);
            }

            const data = await response.json();
            const sessions = data.sessions || [];

            // Store the infrastructure session ID using SRR session manager
            if (data.infrastructure_session_id) {
                // 🆕 SRR: Register infrastructure session in session registry
                if (window.sessionManager?.setInfrastructureSession) {
                    window.sessionManager.setInfrastructureSession(workflowId, data.infrastructure_session_id);
                    console.log(`[WorkflowManager] ✅ SRR: Registered infrastructure session: ${data.infrastructure_session_id} for workflow ${workflowId}`);
                } else {
                    console.warn(`[WorkflowManager] SessionManager.setInfrastructureSession not available - skipping registration`);
                }
            }

            console.log(`[WorkflowManager] ✅ Infrastructure created and ${sessions.length} sessions retrieved for ${workflowId}:`, {
                infrastructure_session: data.session_id,
                total: sessions.length,
                first_session: sessions[0]?.session_id || 'none'
            });

            return sessions;

        } catch (error) {
            console.error(`[WorkflowManager] ❌ Failed to create infrastructure and get sessions for ${workflowId}:`, error);
            throw error;
        }
    }


    /**
     * Hide workflow sessions sub-panel and show main workflow list
     * RESPECTS protection flag to prevent hiding during active user selection
     */
    hideWorkflowSessions() {
        // 🛡️ RESPECT PROTECTION: Don't hide if protection is active (user making selection)
        if (window.sessionPanelProtectionActive) {
            return false; // Return false to indicate hiding was cancelled
        }

        // Remove session panels
        document.querySelectorAll('.workflow-session-content').forEach(panel => {
            panel.remove();
        });

        // Remove back buttons
        document.querySelectorAll('.group-back-btn').forEach(btn => {
            btn.remove();
        });

        // Show group toggle button again
        document.querySelectorAll('.group-toggle').forEach(btn => {
            btn.style.display = '';
        });

        // Show main workflow list
        const workflowsList = document.querySelector('#dynamic-workflows-content .workflows-list');
        if (workflowsList) {
            workflowsList.style.display = '';
        }

        return true; // Return true to indicate successful hiding
    }



    /**
     * SINGLE ENTRY FUNCTION: Setup workflow with session on CHAT-UI
     * Called by ALL 3 entry buttons with sessionId (ACTIVE or selected)
     */
    async selectWorkflowSession(sessionId, workflowId) {
        console.log(`[WorkflowManager] 🎯 Single entry: workflow=${workflowId}, session=${sessionId}`);

        // 🛡️ CRITICAL: Hide artifact panel when switching workflows or sessions
        if (window.artifactDisplayManager) {
            if (window.artifactDisplayManager.clearWorkflowProgress) {
                window.artifactDisplayManager.clearWorkflowProgress();
            }
            if (window.artifactDisplayManager.hidePanel) {
                window.artifactDisplayManager.hidePanel();
            }
        }

        try {
            // Create infrastructure bound to sessionId (ACTIVE or selected)
            const sessionData = await window.apiUtils.createWorkflowSession(workflowId, {
                chat_session_id: sessionId
            });

            console.log(`[WorkflowManager] ✅ Infrastructure created: ${sessionData.session_id} bound to ${sessionId}`);

            // Register infrastructure session
            if (window.sessionManager?.setInfrastructureSession) {
                window.sessionManager.setInfrastructureSession(workflowId, sessionData.session_id);
            }

            // Setup CHAT-UI on "chat-content-area"
            await this.setupChatInterface(workflowId, sessionData.session_id, sessionId);

            // SIMPLE SUB-PANEL LOGIC: sessions >= 2 ? show : hide
            const sessions = await this.createWorkflowSessionAndGetSessions(workflowId);
            if (sessions.length >= 2) {
                this.showSimpleSessionPanel(workflowId, sessions, sessionId);
            } else {
                this.hideWorkflowSessions();
            }

        } catch (error) {
            console.error(`[WorkflowManager] ❌ Failed to setup workflow session:`, error);
            // Fallback to fresh workflow
            await this.selectWorkflow(workflowId);
        }
    }



    /**
     * Setup CHAT-UI on "chat-content-area" with workflow and session
     */
    async setupChatInterface(workflowId, infraSessionId, chatSessionId) {
        console.log(`[WorkflowManager] 🎨 Setting up chat UI: workflow=${workflowId}, infra=${infraSessionId}, chat=${chatSessionId}`);

        // Switch to chat view
        if (window.mainUIManager) {
            window.mainUIManager.showView('chat');
        }

        // Set current workflow
        this.currentWorkflow = workflowId;
        window.globalState.currentWorkflow = workflowId;
        window.globalState.currentChatSessionId = chatSessionId;

        // Set session context
        const sessionData = {
            session_id: chatSessionId,
            websocket_url: `/api/workflow/${infraSessionId}/stream`
        };

        if (window.chatUIManager) {
            window.chatUIManager.setSessionContext(sessionData, workflowId);
            window.chatUIManager.setCurrentWorkflow(workflowId);
        }

        // Resume session if it exists
        if (chatSessionId && window.chatUIManager) {
            try {
                await window.chatUIManager.resumeWorkflowSession(chatSessionId);
                console.log(`[WorkflowManager] ✅ Session ${chatSessionId} resumed`);
            } catch (error) {
                console.log(`[WorkflowManager] ⚠️ Could not resume session ${chatSessionId}`);
            }
        }

        // Show workflow controls
        if (window.workflowControlsManager) {
            const status = chatSessionId ? 'active' : 'idle';
            window.workflowControlsManager.showWorkflowControls(workflowId, status);
        }

        // STATUS BAR UPDATE: Ensure status bar shows the selected workflow
        const workflowDisplayName = workflowId.replace(/_/g, ' ').toUpperCase();
        if (window.mainUIManager?.setStatusBar) {
            window.mainUIManager.setStatusBar('current_workflow', workflowDisplayName);
        } else if (window.setStatusBar) {
            window.setStatusBar('current_workflow', workflowDisplayName);
        }

        console.log(`[WorkflowManager] ✅ Chat UI setup complete for ${workflowId}`);
    }

    /**
     * Show simple session panel for multi-session workflows
     */
    showSimpleSessionPanel(workflowId, sessions, currentSessionId) {
        console.log(`[WorkflowManager] 📋 Showing simple session panel for ${workflowId} (${sessions.length} sessions)`);

        const workflowButton = document.querySelector(`button[data-workflow="${workflowId}"]`);
        if (!workflowButton) return;

        const workflowLi = workflowButton.closest('li.workflows');
        if (!workflowLi) return;

        const sessionItemsHTML = sessions.map((session, index) => {
            // Enhanced icon logic: ACTIVE 🔥 → BOOKMARKED ⭐ → REMAINING 📄
            let icon = '📄'; // Default for remaining sessions
            if (index === 0) {
                icon = '🔥'; // First session is always ACTIVE
            } else if (session.metadata && session.metadata.bookmarked) {
                icon = '⭐'; // Bookmarked sessions
            }
            const isCurrent = session.session_id === currentSessionId;
            const title = (session.first_message || session.title || session.session_id.substring(0, 8));

            return `
                <li class="workflows session-item">
                    <button class="menu-button session-menu-button ${isCurrent ? 'active-session' : ''}"
                            data-session-id="${session.session_id}"
                            title="${title}"
                            style="white-space: nowrap; display: flex; align-items: center; width: 100%;">
                        <span class="inline-icon">${icon}</span>
                        <span style="text-overflow: ellipsis; white-space: nowrap; overflow: hidden; flex: 1; font-size: 11px;">${title.substring(0, 30)}${title.length > 30 ? '...' : ''}</span>
                    </button>
                </li>
            `;
        }).join('');

        const panelHTML = `
            <div class="group-content session-group-content workflow-session-content" id="current-workflow-sessions-content-${workflowId}">
                <div class="session-menu" id="current-workflow-session-menu-${workflowId}">
                    ${sessionItemsHTML}
                </div>
            </div>
        `;

        workflowLi.insertAdjacentHTML('afterend', panelHTML);

        // Simple event handlers - just call the single entry function again
        const panel = document.getElementById(`current-workflow-sessions-content-${workflowId}`);
        if (panel) {
            panel.querySelectorAll('.session-menu-button').forEach(button => {
                button.addEventListener('click', async () => {
                    const sessionId = button.dataset.sessionId;
                    await this.selectWorkflowSession(sessionId, workflowId);
                });
            });
        }

        console.log(`[WorkflowManager] ✅ Simple session panel shown`);
    }

    /**
     * Detect existing sessions for a workflow
     * UPDATED: Uses SRR infrastructure session from session registry
     */
    async detectExistingWorkflowSession(workflowId) {
        try {
            // Check if sessionManager is available
            if (!window.sessionManager || !window.sessionManager.getInfrastructureSession) {
                console.log(`[WorkflowManager] SessionManager not available yet for ${workflowId} - cannot detect existing sessions`);
                return null;
            }

            // Check if we already have infrastructure for this workflow using SRR
            const infrastructureSessionId = window.sessionManager.getInfrastructureSession(workflowId);

            if (!infrastructureSessionId) {
                console.log(`[WorkflowManager] No infrastructure session available for ${workflowId} - cannot detect existing sessions`);
                return null;
            }

            console.log(`[WorkflowManager] 🔍 Checking for existing sessions using SRR infrastructure ${infrastructureSessionId}`);

            // Check if apiUtils is available
            if (!window.apiUtils || !window.apiUtils.getWorkflowSessions) {
                console.log(`[WorkflowManager] apiUtils not available yet for ${workflowId} - cannot detect existing sessions`);
                return null;
            }

            // Query sessions using existing infrastructure
            const sessions = await window.apiUtils.getWorkflowSessions(infrastructureSessionId);

            console.log(`[WorkflowManager] 📊 Retrieved ${sessions.length} sessions for SRR infrastructure ${infrastructureSessionId}`);

            // Backend sorts sessions by recency, so first session is most recent
            if (sessions.length > 0) {
                const mostRecentSessionId = sessions[0].session_id;
                console.log(`[WorkflowManager] Found most recent session for ${workflowId}: ${mostRecentSessionId}`);
                return mostRecentSessionId;
            }

            console.log(`[WorkflowManager] No sessions found for ${workflowId}`);
            return null;

        } catch (error) {
            console.warn(`[WorkflowManager] Failed to detect existing session for ${workflowId}:`, error);
            return null;
        }
    }
}

// Initialize when DOM is ready and export globally
document.addEventListener('DOMContentLoaded', () => {
    window.workflowManager = new WorkflowManager();
});

// Export globally available workflow functions
window.selectWorkflow = (workflowId) =>
    window.workflowManager?.selectWorkflow(workflowId);

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WorkflowManager;
}
