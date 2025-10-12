/**
 * Workflow Manager - Phase 5.6D Frontend Modularization
 *
 * Handles workflow selection, loading, and management.
 * Separated from monolithic script.js for better maintainability.
 */

// Global workflow state
let availableWorkflows = [];

// Core Workflow Manager Class
class WorkflowManager {
    constructor() {
        this.currentWorkflow = null;
        this.sessionManagementEnabled = true;
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

            console.log('[WorkflowManager] Workflow system initialized with', availableWorkflows.length, 'workflows');
        } catch (error) {
            console.error('[WorkflowManager] Failed to initialize workflow system:', error);
        }
    }

    /**
     * Load available workflows from API
     */
    async loadAvailableWorkflows() {
        try {
            console.log('[WorkflowManager] Loading workflows from API...');
            const response = await fetch('/api/workflows');

            if (!response.ok) {
                console.error('[WorkflowManager] Failed to load workflows from API:', response.status);
                console.warn('[WorkflowManager] Falling back to empty workflow list');
                availableWorkflows = [];
                return [];
            }

            const data = await response.json();
            availableWorkflows = data.workflows || [];

            console.log('[WorkflowManager] Loaded workflows:', availableWorkflows.length);
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

        console.log('[WorkflowManager] Updating welcome page with dynamic workflows...');

        if (availableWorkflows.length > 0) {
            // Generate dynamic workflow cards from API data
            const workflowCards = availableWorkflows.map(workflow =>
                this.generateWorkflowCard(workflow)
            ).join('');

            workflowGrid.innerHTML = workflowCards;
            console.log(`[WorkflowManager] Successfully loaded ${availableWorkflows.length} workflows in welcome page`);

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

        console.log('[WorkflowManager] Updating left panel workflows...', 'availableWorkflows:', availableWorkflows.length);

        if (availableWorkflows.length > 0) {
            // Clear existing workflow items
            workflowsList.querySelectorAll('.workflows').forEach(li => li.remove());

            // Add new workflow items
            availableWorkflows.forEach(workflow => {
                const menuItem = this.generateWorkflowMenuItem(workflow);
                workflowsList.insertAdjacentHTML('beforeend', menuItem);
            });

            console.log('[WorkflowManager] Added', availableWorkflows.length, 'workflow menu items');

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
     */
    attachEventHandlers() {
        // Welcome page workflow selection
        document.querySelectorAll('.select-workflow-btn').forEach(button => {
            button.addEventListener('click', async (event) => {
                event.preventDefault();
                const workflowId = event.target.getAttribute('data-workflow');

                if (workflowId) {
                    console.log(`[WorkflowManager] Welcome page workflow selection: ${workflowId}`);
                    await this.selectWorkflow(workflowId);
                }
            });
        });

        // Left panel workflow selection
        document.querySelectorAll('.workflow-button').forEach(button => {
            button.addEventListener('click', (event) => {
                const target = event.target.closest('button[data-workflow]');
                if (!target) return;

                const workflowId = target.dataset.workflow;
                if (workflowId) {
                    this.enhancedWorkflowButtonHandler(event, workflowId);
                }
            });
        });
    }

    /**
     * Enhanced workflow button handler with session management
     */
    enhancedWorkflowButtonHandler(event, workflowId) {
        event.preventDefault();
        event.stopPropagation();

        console.log(`[WorkflowManager] Selecting workflow: ${workflowId}`);
        this.selectWorkflow(workflowId);
    }

    /**
     * Select workflow and start session (enhanced with session management)
     */
    async selectWorkflow(workflowId) {
        console.log(`[WorkflowManager] Selecting workflow: ${workflowId}`);

        // Set current workflow
        this.currentWorkflow = workflowId;

        if (window.chatUIManager) {
            window.chatUIManager.setCurrentWorkflow(workflowId);
        }

        // Enhanced workflow selection with session management
        await this.selectWorkflowWithSessionManagement(workflowId);
    }

    /**
     * Enhanced workflow selection with persistent session lifecycle management
     */
    async selectWorkflowWithSessionManagement(workflow) {
        console.log(`[WorkflowManager] Selecting workflow with session management: ${workflow}`);

        // Save current session state before switching
        if (this.sessionManagementEnabled && window.saveCurrentSessionState) {
            window.saveCurrentSessionState();
        }

        this.currentWorkflow = workflow;

        // Get backend session ID for workflow (persistent session per workflow type)
        const backendSessionId = await this.getBackendWorkflowSessionId(workflow);

        // Show loading page
        if (window.showLoadingPage) {
            const workflowName = workflow.replace('-', ' ').toUpperCase();
            window.showLoadingPage(`${workflowName} Workflow`, 'Loading RAG indexes...');
        }

        // Navigate to chat interface after brief loading
        setTimeout(() => {
            if (window.showChatInterface) {
                window.showChatInterface(backendSessionId);
            }

            if (window.updateStatus) {
                window.updateStatus(`Ready to chat with ${workflow} workflow.`, 'success');
            }
        }, 1500);
    }

    /**
     * Get backend session ID for workflow (calls server endpoint)
     */
    async getBackendWorkflowSessionId(workflow) {
        console.log(`[WorkflowManager] Requesting backend session ID for ${workflow}`);

        try {
            const response = await fetch(`/api/workflow_sessions/${workflow}/id`);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                console.error(`[WorkflowManager] Backend session request failed: ${response.status} ${response.statusText}`, errorData);
                throw new Error(`Failed to get session from backend: ${response.status}`);
            }

            const data = await response.json();
            const sessionId = data.session_id;

            console.log(`[WorkflowManager] Backend returned session ${sessionId} for ${workflow}`);
            return sessionId;

        } catch (error) {
            console.error(`[WorkflowManager] Failed to get backend session for ${workflow}:`, error);

            // Fallback to local session management if backend fails
            console.warn(`[WorkflowManager] Falling back to local session management for ${workflow}`);
            return this.getWorkflowPersistentSessionId(workflow);
        }
    }

    /**
     * Get persistent session ID for workflow (browser-based fallback)
     */
    getWorkflowPersistentSessionId(workflow) {
        const storageKey = `workflow_sessions`;
        let workflowSessions = {};

        // Load existing workflow sessions from localStorage
        try {
            const stored = localStorage.getItem(storageKey);
            if (stored) {
                workflowSessions = JSON.parse(stored);
            }
        } catch (e) {
            console.warn('[WorkflowManager] Failed to load workflow sessions from localStorage');
        }

        // Get or create session ID for this workflow
        if (!workflowSessions[workflow]) {
            workflowSessions[workflow] = this.generateUUID();
            console.log(`[WorkflowManager] Created new persistent session for ${workflow}: ${workflowSessions[workflow]}`);
        } else {
            console.log(`[WorkflowManager] Reusing persistent session for ${workflow}: ${workflowSessions[workflow]}`);
        }

        // Save back to localStorage
        try {
            localStorage.setItem(storageKey, JSON.stringify(workflowSessions));
        } catch (e) {
            console.warn('[WorkflowManager] Failed to save workflow sessions to localStorage');
        }

        return workflowSessions[workflow];
    }

    /**
     * Generate UUID utility
     */
    generateUUID() {
        if (typeof crypto !== 'undefined' && crypto.randomUUID) {
            return crypto.randomUUID();
        }
        return Date.now().toString(36) + Math.random().toString(36).substr(2);
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
     * Detect existing sessions for a workflow
     */
    async detectExistingWorkflowSession(workflowId) {
        try {
            const response = await fetch('/api/chat_history/sessions');
            if (!response.ok) return null;

            const data = await response.json();
            const sessions = data.sessions || [];

            // Find most recent session for this workflow
            const workflowSessions = sessions
                .filter(session => session.workflow_name === workflowId)
                .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

            return workflowSessions.length > 0 ? workflowSessions[0].session_id : null;

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

// Export globally available functions and objects
window.selectWorkflowWithSessionManagement = (workflowId) =>
    window.workflowManager?.selectWorkflowWithSessionManagement(workflowId);

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WorkflowManager;
}
