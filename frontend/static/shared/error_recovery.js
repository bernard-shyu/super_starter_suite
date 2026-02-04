/**
 * Error Recovery Manager - Phase 6: Error Recovery Interfaces
 *
 * Provides comprehensive error recovery UI and functionality:
 * - Error diagnostics and display
 * - Retry mechanisms with different strategies
 * - Alternative workflow suggestions
 * - Recovery action tracking
 * - Integration with WebSocket for real-time error handling
 */

let errorRecoveryManagerInitialized = false;

class ErrorRecoveryManager {
    constructor() {
        this.activeErrors = new Map(); // Store active error recovery sessions
        this.recoveryHistory = []; // Track recovery attempts
        this.initializeErrorRecoveryManager();
    }

    /**
     * Initialize the error recovery manager
     */
    async initializeErrorRecoveryManager() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setupUI());
        } else {
            this.setupUI();
        }
    }

    /**
     * Setup error recovery UI
     */
    setupUI() {
        // Create error recovery container
        this.createErrorRecoveryContainer();

        // Setup event listeners for error recovery
        this.setupEventListeners();

        errorRecoveryManagerInitialized = true;

        // Listen for workflow errors
        window.addEventListener('workflow-error', (event) => {
            this.handleWorkflowError(event.detail);
        });
    }

    /**
     * Create error recovery container
     */
    createErrorRecoveryContainer() {
        // Check if container already exists
        if (document.getElementById('error-recovery-container')) {
            return;
        }

        const container = document.createElement('div');
        container.id = 'error-recovery-container';
        container.className = 'error-recovery-container';
        container.innerHTML = '';

        // Insert into chat interface
        const chatInterface = document.getElementById('chat-interface') ||
            document.querySelector('.main-content') ||
            document.body;

        // Position it prominently in the chat area
        const messageContainer = chatInterface.querySelector('#message-container');
        if (messageContainer) {
            messageContainer.appendChild(container);
        } else {
            chatInterface.appendChild(container);
        }

        // Add CSS styles
        this.addErrorRecoveryStyles();
    }

    /**
     * Add CSS styles for error recovery components
     */
    addErrorRecoveryStyles() {
        const style = document.createElement('style');
        style.textContent = `
            /* Error Recovery Container */
            .error-recovery-container {
                position: relative;
                width: 100%;
                max-width: 800px;
                margin: 1rem auto;
                display: none; /* Hidden by default */
                animation: errorSlideIn 0.3s ease-out;
            }

            .error-recovery-container.visible {
                display: block;
            }

            @keyframes errorSlideIn {
                from {
                    opacity: 0;
                    transform: translateY(-10px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }

            /* Error Alert */
            .error-alert {
                background: linear-gradient(135deg, #fef2f2, #fee2e2);
                border: 1px solid #fecaca;
                border-radius: 0.75rem;
                padding: 1.5rem;
                margin-bottom: 1rem;
                box-shadow: 0 4px 20px 0 rgba(239, 68, 68, 0.1);
            }

            .error-header {
                display: flex;
                align-items: center;
                gap: 0.75rem;
                margin-bottom: 1rem;
            }

            .error-icon {
                width: 2rem;
                height: 2rem;
                background: #ef4444;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-weight: bold;
                font-size: 1.25rem;
                flex-shrink: 0;
            }

            .error-title {
                font-size: 1.125rem;
                font-weight: 600;
                color: #dc2626;
                margin: 0;
            }

            .error-message {
                color: #991b1b;
                font-size: 0.875rem;
                line-height: 1.5;
                margin-bottom: 1rem;
            }

            .error-details {
                background: #ffffff;
                border: 1px solid #fecaca;
                border-radius: 0.5rem;
                padding: 1rem;
                font-family: 'SF Mono', Monaco, monospace;
                font-size: 0.75rem;
                color: #7f1d1d;
                max-height: 150px;
                overflow-y: auto;
                margin-bottom: 1rem;
            }

            /* Recovery Options */
            .recovery-options {
                display: flex;
                flex-direction: column;
                gap: 0.75rem;
            }

            .recovery-section {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 0.5rem;
                padding: 1rem;
            }

            .recovery-section-title {
                font-size: 0.875rem;
                font-weight: 600;
                color: #374151;
                margin-bottom: 0.75rem;
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }

            .recovery-actions {
                display: flex;
                gap: 0.5rem;
                flex-wrap: wrap;
            }

            .recovery-btn {
                padding: 0.5rem 1rem;
                border: 1px solid #d1d5db;
                border-radius: 0.375rem;
                background: white;
                color: #374151;
                font-size: 0.875rem;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s ease;
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }

            .recovery-btn:hover {
                background: #f9fafb;
                border-color: #9ca3af;
            }

            .recovery-btn.primary {
                background: #3b82f6;
                color: white;
                border-color: #3b82f6;
            }

            .recovery-btn.primary:hover {
                background: #2563eb;
                border-color: #2563eb;
            }

            .recovery-btn.success {
                background: #10b981;
                color: white;
                border-color: #10b981;
            }

            .recovery-btn.success:hover {
                background: #059669;
                border-color: #059669;
            }

            .recovery-btn.warning {
                background: #f59e0b;
                color: white;
                border-color: #f59e0b;
            }

            .recovery-btn.warning:hover {
                background: #d97706;
                border-color: #d97706;
            }

            /* Alternative Workflows */
            .alternative-workflows {
                margin-top: 0.5rem;
            }

            .workflow-suggestion {
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 0.75rem;
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 0.375rem;
                margin-bottom: 0.5rem;
                transition: all 0.2s ease;
            }

            .workflow-suggestion:hover {
                background: #f1f5f9;
                border-color: #cbd5e1;
            }

            .workflow-info {
                flex: 1;
            }

            .workflow-name {
                font-weight: 600;
                color: #1e293b;
                font-size: 0.875rem;
            }

            .workflow-reason {
                color: #64748b;
                font-size: 0.75rem;
                margin-top: 0.25rem;
            }

            .workflow-select-btn {
                padding: 0.375rem 0.75rem;
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 0.25rem;
                font-size: 0.75rem;
                font-weight: 500;
                cursor: pointer;
                transition: background 0.2s ease;
            }

            .workflow-select-btn:hover {
                background: #2563eb;
            }

            /* Recovery History */
            .recovery-history {
                margin-top: 1rem;
                padding-top: 1rem;
                border-top: 1px solid #e5e7eb;
            }

            .history-title {
                font-size: 0.75rem;
                font-weight: 600;
                color: #6b7280;
                margin-bottom: 0.5rem;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }

            .history-item {
                display: flex;
                align-items: center;
                gap: 0.5rem;
                padding: 0.5rem 0;
                font-size: 0.75rem;
                color: #6b7280;
                border-bottom: 1px solid #f3f4f6;
            }

            .history-item:last-child {
                border-bottom: none;
            }

            .history-status {
                width: 0.5rem;
                height: 0.5rem;
                border-radius: 50%;
                background: #d1d5db;
            }

            .history-status.success {
                background: #10b981;
            }

            .history-status.failed {
                background: #ef4444;
            }

            .history-status.pending {
                background: #f59e0b;
            }

            /* Loading States */
            .recovery-loading {
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 2rem;
                gap: 0.75rem;
            }

            .recovery-spinner {
                width: 1.5rem;
                height: 1.5rem;
                border: 2px solid #e5e7eb;
                border-top: 2px solid #3b82f6;
                border-radius: 50%;
                animation: spin 1s linear infinite;
            }

            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }

            /* Responsive Design */
            @media (max-width: 640px) {
                .recovery-actions {
                    flex-direction: column;
                }

                .recovery-btn {
                    width: 100%;
                    justify-content: center;
                }

                .error-header {
                    flex-direction: column;
                    align-items: flex-start;
                    gap: 0.5rem;
                }
            }
        `;

        document.head.appendChild(style);
    }

    /**
     * Setup event listeners for error recovery communication
     * Uses EventDispatcher instead of direct WebSocket connections
     */
    setupEventListeners() {
        console.log('[ErrorRecoveryManager] Setting up event listeners via EventDispatcher');

        // Register with EventDispatcher for error recovery events
        if (window.getEventDispatcher) {
            const dispatcher = window.getEventDispatcher();
            dispatcher.registerHandler('recovery_ack_event', this);
            dispatcher.registerHandler('recovery_result_event', this);
        } else {
            console.warn('[ErrorRecoveryManager] EventDispatcher not available');
        }
    }

    /**
     * Handle events through EventDispatcher interface
     */
    handleEvent(eventType, data, workflowId) {
        console.log(`[ErrorRecoveryManager] Handling ${eventType} event`);

        try {
            switch (eventType) {
                case 'recovery_ack_event':
                    this.handleRecoveryAcknowledgment(data);
                    break;
                case 'recovery_result_event':
                    this.handleRecoveryResult(data);
                    break;
                default:
                    console.warn(`[ErrorRecoveryManager] Unknown event type: ${eventType}`);
            }
        } catch (error) {
            console.error(`[ErrorRecoveryManager] Error handling ${eventType}:`, error);
        }
    }

    /**
     * Handle workflow error event
     */
    async handleWorkflowError(errorData) {
        console.log('[ErrorRecoveryManager] Handling workflow error:', errorData);

        const { workflowId, error, context, timestamp } = errorData;

        // Create error recovery session
        const recoverySession = {
            id: `recovery-${Date.now()}`,
            workflowId: workflowId,
            error: error,
            context: context,
            timestamp: timestamp || new Date().toISOString(),
            attempts: [],
            status: 'analyzing'
        };

        this.activeErrors.set(recoverySession.id, recoverySession);

        // Show error recovery UI
        await this.showErrorRecoveryUI(recoverySession);

        // Analyze error and suggest recovery options
        await this.analyzeErrorAndSuggestRecovery(recoverySession);
    }

    /**
     * Show error recovery UI
     */
    async showErrorRecoveryUI(recoverySession) {
        const container = document.getElementById('error-recovery-container');
        if (!container) return;

        // Generate recovery UI HTML
        container.innerHTML = this.generateErrorRecoveryHTML(recoverySession);
        container.classList.add('visible');

        // Setup event listeners
        this.attachRecoveryEventListeners(recoverySession.id);

        console.log(`[ErrorRecoveryManager] Showing error recovery UI for session: ${recoverySession.id}`);
    }

    /**
     * Generate HTML for error recovery UI
     */
    generateErrorRecoveryHTML(recoverySession) {
        const { error, context } = recoverySession;

        return `
            <div class="error-alert" data-recovery-id="${recoverySession.id}">
                <div class="error-header">
                    <div class="error-icon">⚠️</div>
                    <h3 class="error-title">Workflow Error Occurred</h3>
                </div>

                <div class="error-message">
                    ${error.message || 'An unexpected error occurred during workflow execution.'}
                </div>

                ${error.details ? `
                    <div class="error-details">
                        <strong>Error Details:</strong><br>
                        ${error.details}
                    </div>
                ` : ''}

                <div class="recovery-options">
                    <div class="recovery-section">
                        <div class="recovery-section-title">
                            🔄 Recovery Actions
                        </div>
                        <div class="recovery-actions">
                            <button class="recovery-btn primary" onclick="window.errorRecoveryManager.retryLastStep('${recoverySession.id}')">
                                🔄 Retry Last Step
                            </button>
                            <button class="recovery-btn success" onclick="window.errorRecoveryManager.retryWorkflow('${recoverySession.id}')">
                                ✅ Restart Workflow
                            </button>
                            <button class="recovery-btn warning" onclick="window.errorRecoveryManager.modifyAndRetry('${recoverySession.id}')">
                                ✏️ Modify & Retry
                            </button>
                            <button class="recovery-btn" onclick="window.errorRecoveryManager.skipStep('${recoverySession.id}')">
                                ⏭️ Skip Step
                            </button>
                        </div>
                    </div>

                    <div class="recovery-section">
                        <div class="recovery-section-title">
                            🔄 Alternative Approaches
                        </div>
                        <div class="alternative-workflows" id="alternative-workflows-${recoverySession.id}">
                            <div class="recovery-loading">
                                <div class="recovery-spinner"></div>
                                <span>Analyzing alternative workflows...</span>
                            </div>
                        </div>
                    </div>

                    <div class="recovery-history">
                        <div class="history-title">Recovery History</div>
                        <div id="recovery-history-${recoverySession.id}">
                            <div class="history-item">
                                <div class="history-status pending"></div>
                                <span>Error occurred - analyzing recovery options</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Analyze error and suggest recovery options
     */
    async analyzeErrorAndSuggestRecovery(recoverySession) {
        try {
            // Simulate error analysis (in real implementation, this would call backend API)
            const suggestions = await this.generateAlternativeWorkflows(recoverySession);

            // Update UI with suggestions
            this.updateAlternativeWorkflows(recoverySession.id, suggestions);

        } catch (error) {
            console.error('[ErrorRecoveryManager] Error analyzing recovery options:', error);
            this.updateAlternativeWorkflows(recoverySession.id, []);
        }
    }

    /**
     * Generate alternative workflow suggestions
     */
    async generateAlternativeWorkflows(recoverySession) {
        const { error, workflowId } = recoverySession;

        // Mock suggestions based on error type (in real implementation, this would be AI-powered)
        const suggestions = [];

        if (error.type === 'timeout' || error.message?.includes('timeout')) {
            suggestions.push({
                workflowId: 'deep_research',
                name: 'Deep Research Workflow',
                reason: 'More thorough analysis with better timeout handling'
            });
        }

        if (error.type === 'api_error' || error.message?.includes('API')) {
            suggestions.push({
                workflowId: 'agentic_rag',
                name: 'Agentic RAG Workflow',
                reason: 'Alternative data sources and error recovery'
            });
        }

        if (error.type === 'validation_error' || error.message?.includes('validation')) {
            suggestions.push({
                workflowId: 'document_generator',
                name: 'Document Generator',
                reason: 'Structured document creation with validation'
            });
        }

        // Add fallback suggestions
        if (suggestions.length === 0) {
            suggestions.push({
                workflowId: 'code_generator',
                name: 'Code Generator',
                reason: 'Alternative approach for code-related tasks'
            });
        }

        return suggestions;
    }

    /**
     * Update alternative workflows UI
     */
    updateAlternativeWorkflows(recoverySessionId, suggestions) {
        const container = document.getElementById(`alternative-workflows-${recoverySessionId}`);
        if (!container) return;

        if (suggestions.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; color: #6b7280; padding: 1rem;">
                    No alternative workflows available for this error type.
                </div>
            `;
            return;
        }

        const suggestionsHTML = suggestions.map(suggestion => `
            <div class="workflow-suggestion">
                <div class="workflow-info">
                    <div class="workflow-name">${suggestion.name}</div>
                    <div class="workflow-reason">${suggestion.reason}</div>
                </div>
                <button class="workflow-select-btn" onclick="window.errorRecoveryManager.selectAlternativeWorkflow('${recoverySessionId}', '${suggestion.workflowId}')">
                    Try This
                </button>
            </div>
        `).join('');

        container.innerHTML = suggestionsHTML;
    }

    /**
     * Attach event listeners for recovery actions
     */
    attachRecoveryEventListeners(recoverySessionId) {
        // Event listeners are attached via onclick attributes in HTML
        // Additional dynamic listeners can be added here if needed
    }

    // Recovery Actions

    /**
     * Send recovery command through EventDispatcher
     */
    async sendRecoveryCommand(recoverySessionId, action) {
        console.log(`[ErrorRecoveryManager] Sending ${action} command for session: ${recoverySessionId}`);

        const session = this.activeErrors.get(recoverySessionId);
        if (!session) return;

        // Add to recovery history
        this.addRecoveryAttempt(session, action, 'pending');

        if (window.getEventDispatcher) {
            const dispatcher = window.getEventDispatcher();

            // Send command through EventDispatcher
            const success = dispatcher.dispatchEvent('recovery_action_command', {
                recoverySessionId: recoverySessionId,
                action: action,
                workflowId: session.workflowId,
                timestamp: new Date().toISOString()
            }, session.workflowId);

            if (!success) {
                console.error(`[ErrorRecoveryManager] Failed to dispatch ${action} command`);
                this.addRecoveryAttempt(session, action, 'failed');
                this.showError(`Failed to ${action.replace('_', ' ')}`);
            }
        } else {
            console.error('[ErrorRecoveryManager] EventDispatcher not available');
            this.addRecoveryAttempt(session, action, 'failed');
            this.showError('Recovery system unavailable');
        }
    }

    /**
     * Retry the last failed step
     */
    async retryLastStep(recoverySessionId) {
        await this.sendRecoveryCommand(recoverySessionId, 'retry_last_step');
    }

    /**
     * Retry the entire workflow
     */
    async retryWorkflow(recoverySessionId) {
        await this.sendRecoveryCommand(recoverySessionId, 'retry_workflow');
    }

    /**
     * Modify parameters and retry
     */
    async modifyAndRetry(recoverySessionId) {
        console.log(`[ErrorRecoveryManager] Modifying and retrying for session: ${recoverySessionId}`);

        const session = this.activeErrors.get(recoverySessionId);
        if (!session) return;

        // For now, just retry with same parameters
        // In a full implementation, this would show a parameter modification UI
        await this.retryWorkflow(recoverySessionId);
    }

    /**
     * Skip the failed step
     */
    async skipStep(recoverySessionId) {
        await this.sendRecoveryCommand(recoverySessionId, 'skip_step');
    }

    /**
     * Select alternative workflow
     */
    async selectAlternativeWorkflow(recoverySessionId, alternativeWorkflowId) {
        console.log(`[ErrorRecoveryManager] Selecting alternative workflow: ${alternativeWorkflowId} for session: ${recoverySessionId}`);

        const session = this.activeErrors.get(recoverySessionId);
        if (!session) return;

        // Add to recovery history
        this.addRecoveryAttempt(session, `switch_to_${alternativeWorkflowId}`, 'pending');

        // Switch to alternative workflow
        if (window.workflowManager) {
            try {
                await window.workflowManager.selectWorkflow(alternativeWorkflowId);
                this.addRecoveryAttempt(session, `switch_to_${alternativeWorkflowId}`, 'success');
                this.hideErrorRecovery(recoverySessionId);
            } catch (error) {
                console.error('[ErrorRecoveryManager] Failed to switch workflow:', error);
                this.addRecoveryAttempt(session, `switch_to_${alternativeWorkflowId}`, 'failed');
                this.showError('Failed to switch to alternative workflow');
            }
        }
    }

    /**
     * Handle recovery acknowledgment
     */
    handleRecoveryAcknowledgment(ackData) {
        const { recoverySessionId, action, status } = ackData;

        const session = this.activeErrors.get(recoverySessionId);
        if (!session) return;

        console.log(`[ErrorRecoveryManager] Recovery acknowledged: ${action} - ${status}`);

        // Update recovery attempt status
        this.updateRecoveryAttempt(session, action, status);

        if (status === 'success') {
            // Hide error recovery UI on successful recovery
            setTimeout(() => {
                this.hideErrorRecovery(recoverySessionId);
            }, 2000);
        }
    }

    /**
     * Handle recovery result
     */
    handleRecoveryResult(resultData) {
        const { recoverySessionId, action, success, message } = resultData;

        const session = this.activeErrors.get(recoverySessionId);
        if (!session) return;

        console.log(`[ErrorRecoveryManager] Recovery result: ${action} - ${success ? 'success' : 'failed'}`);

        // Update recovery attempt status
        this.updateRecoveryAttempt(session, action, success ? 'success' : 'failed');

        if (success) {
            // Hide error recovery UI on successful recovery
            setTimeout(() => {
                this.hideErrorRecovery(recoverySessionId);
            }, 2000);
        } else {
            // Show error message for failed recovery
            this.showError(message || 'Recovery attempt failed');
        }
    }

    /**
     * Add recovery attempt to history
     */
    addRecoveryAttempt(session, action, status) {
        const attempt = {
            action: action,
            status: status,
            timestamp: new Date().toISOString()
        };

        session.attempts.push(attempt);
        this.updateRecoveryHistoryUI(session.id);
    }

    /**
     * Update recovery attempt status
     */
    updateRecoveryAttempt(session, action, status) {
        const attempt = session.attempts.find(a => a.action === action);
        if (attempt) {
            attempt.status = status;
            this.updateRecoveryHistoryUI(session.id);
        }
    }

    /**
     * Update recovery history UI
     */
    updateRecoveryHistoryUI(recoverySessionId) {
        const session = this.activeErrors.get(recoverySessionId);
        if (!session) return;

        const historyContainer = document.getElementById(`recovery-history-${recoverySessionId}`);
        if (!historyContainer) return;

        const historyHTML = session.attempts.map(attempt => {
            const statusClass = attempt.status === 'success' ? 'success' :
                attempt.status === 'failed' ? 'failed' : 'pending';
            const actionLabel = this.getActionLabel(attempt.action);

            return `
                <div class="history-item">
                    <div class="history-status ${statusClass}"></div>
                    <span>${actionLabel} - ${attempt.status}</span>
                </div>
            `;
        }).join('');

        historyContainer.innerHTML = historyHTML;
    }

    /**
     * Get human-readable action label
     */
    getActionLabel(action) {
        const labels = {
            'retry_last_step': 'Retry Last Step',
            'retry_workflow': 'Restart Workflow',
            'modify_and_retry': 'Modify & Retry',
            'skip_step': 'Skip Step'
        };

        if (action.startsWith('switch_to_')) {
            return `Switch to ${action.replace('switch_to_', '')}`;
        }

        return labels[action] || action;
    }

    /**
     * Hide error recovery UI
     */
    hideErrorRecovery(recoverySessionId) {
        const container = document.getElementById('error-recovery-container');
        if (container) {
            container.classList.remove('visible');
        }

        // Remove from active errors
        this.activeErrors.delete(recoverySessionId);

        console.log(`[ErrorRecoveryManager] Hidden error recovery UI for session: ${recoverySessionId}`);
    }

    /**
     * Show error message
     */
    showError(message) {
        console.error('[ErrorRecoveryManager] Error:', message);
        if (window.updateStatus) {
            window.updateStatus(message, 'error');
        }
    }

    /**
     * Show success message
     */
    showSuccess(message) {
        console.log('[ErrorRecoveryManager] Success:', message);
        if (window.updateStatus) {
            window.updateStatus(message, 'success');
        }
    }

    /**
     * Check if error recovery is active
     */
    isRecoveryActive() {
        return this.activeErrors.size > 0;
    }

    /**
     * Get active recovery sessions
     */
    getActiveRecoveries() {
        return Array.from(this.activeErrors.values());
    }
}

// Initialize Error Recovery Manager
document.addEventListener('DOMContentLoaded', () => {
    window.errorRecoveryManager = new ErrorRecoveryManager();
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ErrorRecoveryManager;
}
