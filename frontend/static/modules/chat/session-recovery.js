/**
 * Session Recovery Manager - Phase 5.6D Frontend Modularization
 *
 * Handles session recovery across page refreshes and cross-tab navigation.
 * Separated from monolithic script.js for better maintainability.
 */

// Session recovery state
let pendingSessionResume = null;

// Session Recovery Manager Class
class SessionRecoveryManager {
    constructor() {
        this.initializeSessionRecovery();
    }

    /**
     * Initialize session recovery mechanisms
     */
    async initializeSessionRecovery() {
        console.log('[SessionRecoveryManager] Initializing session recovery...');

        // Handle URL-based session resumption (cross-tab navigation)
        await this.handleURLSessionResumption();

        // Handle localStorage-based session recovery (page refresh)
        await this.handleLocalSessionRecovery();
    }

    /**
     * Handle URL parameters for cross-tab session resumption
     */
    async handleURLSessionResumption() {
        const urlParams = new URLSearchParams(window.location.search);
        const resumeSessionId = urlParams.get('resume_session');
        const resumeWorkflow = urlParams.get('resume_workflow');

        if (resumeSessionId && resumeWorkflow) {
            console.log(`[SessionRecoveryManager] URL-based session resumption: ${resumeSessionId} for ${resumeWorkflow}`);

            // Clear URL parameters after processing
            const newUrl = window.location.pathname;
            window.history.replaceState({}, document.title, newUrl);

            await this.resumeWorkflowSession(resumeWorkflow, resumeSessionId);
        }
    }

    /**
     * Handle localStorage session recovery on page load
     */
    async handleLocalSessionRecovery() {
        const savedSession = this.loadPreviousSessionState();

        if (savedSession) {
            console.log('[SessionRecoveryManager] Found saved session, attempting recovery');

            if (window.updateStatus) {
                window.updateStatus('Restoring previous session...', 'in-progress');
            }

            try {
                const success = await this.resumeWorkflowSession(savedSession.workflow, savedSession.sessionId);

                if (success) {
                    if (window.updateStatus) {
                        window.updateStatus('Session restored successfully.', 'success');
                    }
                } else {
                    if (window.updateStatus) {
                        window.updateStatus('Could not restore session.', 'error');
                    }
                }
            } catch (error) {
                console.error('[SessionRecoveryManager] Session recovery failed:', error);
                if (window.updateStatus) {
                    window.updateStatus('Session recovery failed.', 'error');
                }
                this.clearSessionState();
            }
        } else {
            console.log('[SessionRecoveryManager] No session recovery needed');
        }
    }

    /**
     * Resume workflow session with validation
     */
    async resumeWorkflowSession(workflowType, sessionId) {
        console.log(`[SessionRecoveryManager] Attempting to resume workflow: ${workflowType}, session: ${sessionId}`);

        // Set current workflow first
        if (window.workflowManager) {
            window.workflowManager.setCurrentWorkflow(workflowType);
        }

        // Validate session exists and is accessible
        const sessionValid = await this.validateSession(workflowType, sessionId);
        if (!sessionValid) {
            console.warn(`[SessionRecoveryManager] Session ${sessionId} for workflow ${workflowType} is invalid`);
            if (window.chatUIManager) {
                window.chatUIManager.addMessage('system',
                    `Session ${sessionId.substring(0, 8)} not found. Starting new conversation.`,
                    'system');
            }
            return false;
        }

        // Navigate to chat interface
        if (window.chatUIManager) {
            await window.chatUIManager.showChatInterface(sessionId);
        }

        // Navigate to appropriate view
        switch (workflowType) {
            case 'chat':
                if (window.showChatInterface) {
                    window.showChatInterface(sessionId);
                }
                break;
            default:
                if (window.showWelcomePage) {
                    window.showWelcomePage();
                }
                break;
        }

        console.log(`[SessionRecoveryManager] Successfully resumed session for ${workflowType}`);
        return true;
    }

    /**
     * Validate session exists and is accessible
     */
    async validateSession(workflow, sessionId) {
        if (!workflow || !sessionId) return false;

        try {
            const response = await fetch(`/api/chat_history/sessions/${sessionId}`);
            return response.ok;
        } catch (error) {
            console.warn(`[SessionRecoveryManager] Failed to validate session ${sessionId}:`, error);
            return false;
        }
    }

    /**
     * Load previous session state from localStorage
     */
    loadPreviousSessionState() {
        try {
            const sessionData = localStorage.getItem('super_starter_current_session');
            const lastUpdate = localStorage.getItem('super_starter_last_update');

            if (!sessionData) return null;

            // Check if session is recent (within 24 hours)
            const updateTime = parseInt(lastUpdate);
            const hoursSinceUpdate = (Date.now() - updateTime) / (1000 * 60 * 60);

            if (hoursSinceUpdate > 24) {
                console.log('[SessionRecoveryManager] Session state too old, clearing');
                this.clearSessionState();
                return null;
            }

            const sessionState = JSON.parse(sessionData);
            console.log('[SessionRecoveryManager] Loaded previous session state:', sessionState);
            return sessionState;

        } catch (error) {
            console.warn('[SessionRecoveryManager] Failed to load session state:', error);
            this.clearSessionState();
            return null;
        }
    }

    /**
     * Save current session state to localStorage
     */
    saveCurrentSessionState() {
        // Save basic session state for recovery
        try {
            const sessionState = {
                workflow: window.workflowManager?.getCurrentWorkflow(),
                sessionId: window.chatUIManager?.getCurrentSessionId(),
                timestamp: new Date().toISOString()
            };

            if (sessionState.workflow) {
                localStorage.setItem('super_starter_current_session', JSON.stringify(sessionState));
                localStorage.setItem('super_starter_last_update', Date.now().toString());
                console.log('[SessionRecoveryManager] Session state saved:', sessionState);
            }
        } catch (error) {
            console.warn('[SessionRecoveryManager] Failed to save session state:', error);
        }
    }

    /**
     * Clear session state
     */
    clearSessionState() {
        try {
            localStorage.removeItem('super_starter_current_session');
            localStorage.removeItem('super_starter_last_update');
            console.log('[SessionRecoveryManager] Cleared session state');
        } catch (error) {
            console.warn('[SessionRecoveryManager] Failed to clear session state:', error);
        }
    }

    /**
     * Set pending session to resume
     */
    setPendingSessionResume(workflowType, sessionId) {
        pendingSessionResume = { workflowType, sessionId };
    }

    /**
     * Get pending session resume
     */
    getPendingSessionResume() {
        return pendingSessionResume;
    }

    /**
     * Clear pending session resume
     */
    clearPendingSessionResume() {
        pendingSessionResume = null;
    }

    /**
     * Workflow-aware session resumption from chat history
     */
    resumeWorkflowSessionGlobal(sessionId, workflowType) {
        console.log(`[SessionRecoveryManager] Resuming session ${sessionId} for workflow ${workflowType}`);

        // Handle both argument orders for backward compatibility
        if (typeof sessionId === 'object' && sessionId.sessionId) {
            workflowType = sessionId.workflow;
            sessionId = sessionId.sessionId;
        }

        this.setPendingSessionResume(workflowType, sessionId);

        if (window.chatUIManager) {
            window.chatUIManager.showChatInterface(sessionId);
        }
    }
}

// Initialize when DOM is ready and export globally
document.addEventListener('DOMContentLoaded', () => {
    window.sessionRecoveryManager = new SessionRecoveryManager();
});

// Export globally available functions
window.resumeWorkflowSession = (sessionId, workflowType) =>
    window.sessionRecoveryManager?.resumeWorkflowSessionGlobal(sessionId, workflowType);
window.saveCurrentSessionState = () =>
    window.sessionRecoveryManager?.saveCurrentSessionState();
window.initializeSessionRecovery = () =>
    window.sessionRecoveryManager?.initializeSessionRecovery();

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SessionRecoveryManager;
}
