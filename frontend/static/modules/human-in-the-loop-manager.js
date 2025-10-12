/**
 * Human In The Loop (HITL) Manager - Phase 5.6D Frontend Modularization
 *
 * Handles human-in-the-loop interactions including:
 * - CLI command approval/rejection UI
 * - Input prompt handling
 * - Feedback forms for workflow corrections
 * - Integration with LlamaIndex workflow events
 */

let hitlManagerInitialized = false;

// Human In The Loop Manager Class
class HumanInTheLoopManager {
    constructor() {
        this.pendingInteractions = new Map(); // Store active interaction modals
        this.initializeHITLManager();
    }

    /**
     * Initialize the HITL manager
     */
    async initializeHITLManager() {
        console.log('[HITLManager] Initializing human-in-the-loop manager...');

        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setupUI());
        } else {
            this.setupUI();
        }
    }

    /**
     * Setup HITL UI components
     */
    setupUI() {
        console.log('[HITLManager] Setting up HITL UI components...');

        // Create HITL modal container
        this.createHITLContainer();

        // Listen for workflow events that require human input
        this.setupWorkflowEventListeners();

        hitlManagerInitialized = true;
        console.log('[HITLManager] HITL manager initialized');

        // Notify other modules
        if (window.dispatchEvent) {
            window.dispatchEvent(new CustomEvent('hitlManagerReady', {
                detail: { hitlManager: this }
            }));
        }
    }

    /**
     * Create HITL interaction container
     */
    createHITLContainer() {
        // Check if container already exists
        if (document.getElementById('hitl-container')) {
            return;
        }

        const hitlContainer = document.createElement('div');
        hitlContainer.id = 'hitl-container';
        hitlContainer.className = 'hitl-container';
        hitlContainer.innerHTML = '';

        // Insert into page
        const chatInterface = document.getElementById('chat-interface') ||
                             document.querySelector('.main-content') ||
                             document.querySelector('#main-container') ||
                             document.body;

        chatInterface.appendChild(hitlContainer);

        // Add CSS styles
        this.addHITLStyles();

        console.log('[HITLManager] HITL container created');
    }

    /**
     * Add CSS styles for HITL components
     */
    addHITLStyles() {
        const style = document.createElement('style');
        style.textContent = `
            /* HITL Container */
            .hitl-container {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                pointer-events: none; /* Only show when modal is active */
                z-index: 2000;
            }

            /* HITL Modal Overlay */
            .hitl-modal-overlay {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.7);
                backdrop-filter: blur(2px);
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 2000;
                animation: hitlFadeIn 0.2s ease-out;
            }

            @keyframes hitlFadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }

            /* HITL Modal Content */
            .hitl-modal-content {
                background: var(--panel-bg, white);
                border-radius: 12px;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
                max-width: 600px;
                width: 90%;
                max-height: 80vh;
                overflow-y: auto;
                animation: hitlSlideIn 0.3s ease-out;
            }

            @keyframes hitlSlideIn {
                from {
                    opacity: 0;
                    transform: translateY(-20px) scale(0.95);
                }
                to {
                    opacity: 1;
                    transform: translateY(0) scale(1);
                }
            }

            /* CLI Command Approval Modal */
            .cli-approval-modal {
                padding: 0;
            }

            .cli-approval-header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 24px;
                border-radius: 12px 12px 0 0;
            }

            .cli-approval-header h3 {
                margin: 0 0 8px 0;
                font-size: 18px;
                font-weight: 600;
            }

            .cli-approval-header .description {
                opacity: 0.9;
                font-size: 14px;
            }

            .cli-approval-body {
                padding: 24px;
            }

            .cli-command-display {
                background: var(--code-bg, #f6f8fa);
                border: 1px solid var(--border-color, #e1e4e8);
                border-radius: 8px;
                padding: 16px;
                margin: 16px 0;
                font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
                font-size: 14px;
                line-height: 1.4;
                white-space: pre-wrap;
                word-wrap: break-word;
            }

            .cli-warning {
                background: #fff3cd;
                border: 1px solid #ffeaa7;
                border-radius: 6px;
                padding: 12px 16px;
                margin: 16px 0;
                color: #856404;
            }

            .cli-warning .warning-icon {
                font-weight: bold;
                margin-right: 8px;
            }

            .cli-actions {
                display: flex;
                gap: 12px;
                justify-content: flex-end;
                margin-top: 24px;
            }

            .cli-actions button {
                padding: 10px 20px;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-size: 14px;
                font-weight: 500;
                transition: all 0.2s ease;
                min-width: 100px;
            }

            .btn-approve {
                background: #28a745;
                color: white;
            }

            .btn-approve:hover {
                background: #218838;
                transform: translateY(-1px);
            }

            .btn-reject {
                background: #dc3545;
                color: white;
            }

            .btn-reject:hover {
                background: #c82333;
                transform: translateY(-1px);
            }

            .btn-modify {
                background: #ffc107;
                color: #212529;
            }

            .btn-modify:hover {
                background: #e0a800;
                transform: translateY(-1px);
            }

            /* Input Prompt Modal */
            .input-prompt-modal {
                padding: 0;
            }

            .input-prompt-header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 24px;
                border-radius: 12px 12px 0 0;
            }

            .input-prompt-body {
                padding: 24px;
            }

            .input-field {
                width: 100%;
                padding: 12px 16px;
                border: 1px solid #ddd;
                border-radius: 6px;
                font-size: 14px;
                margin: 8px 0;
                box-sizing: border-box;
            }

            .input-field:focus {
                outline: none;
                border-color: #007bff;
                box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.25);
            }

            /* Feedback Form Modal */
            .feedback-form-modal {
                padding: 0;
            }

            .feedback-form-body {
                padding: 24px;
            }

            .feedback-textarea {
                width: 100%;
                min-height: 120px;
                padding: 12px 16px;
                border: 1px solid #ddd;
                border-radius: 6px;
                font-size: 14px;
                margin: 8px 0;
                box-sizing: border-box;
                resize: vertical;
            }

            .feedback-textarea:focus {
                outline: none;
                border-color: #007bff;
                box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.25);
            }

            /* Modal Loading State */
            .hitl-modal-loading {
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 40px;
            }

            .hitl-spinner {
                width: 24px;
                height: 24px;
                border: 3px solid #f3f3f3;
                border-top: 3px solid #007bff;
                border-radius: 50%;
                animation: hitlSpin 1s linear infinite;
            }

            @keyframes hitlSpin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }

            /* Responsive Design */
            @media (max-width: 480px) {
                .cli-actions {
                    flex-direction: column;
                }

                .cli-actions button {
                    width: 100%;
                }

                .hitl-modal-content {
                    width: 95%;
                    margin: 20px;
                }
            }
        `;

        document.head.appendChild(style);
    }

    /**
     * Setup workflow event listeners for HITL interactions
     */
    setupWorkflowEventListeners() {
        // Listen for custom workflow events from the backend
        if (window.EventSource) {
            this.setupSSEListener();
        }

        // Listen for direct function calls from chat interface
        window.addEventListener('workflow-human-input-required', (event) => {
            this.handleHumanInputRequired(event.detail);
        });

        console.log('[HITLManager] Workflow event listeners setup');
    }

    /**
     * Setup Server-Sent Events listener for real-time workflow events
     */
    setupSSEListener() {
        // This would typically connect to the workflow server's SSE endpoint
        // For now, we'll rely on direct event dispatching
        console.log('[HITLManager] SSE listener setup (placeholder)');
    }

    /**
     * Handle human input required event from workflow
     */
    async handleHumanInputRequired(eventData) {
        console.log('[HITLManager] Handling human input required:', eventData);

        const { eventType, data, workflowId } = eventData;

        switch (eventType) {
            case 'cli_human_input':
                await this.showCLICommandApproval(data);
                break;
            case 'text_input_required':
                await this.showTextInputPrompt(data);
                break;
            case 'confirmation_required':
                await this.showConfirmationDialog(data);
                break;
            case 'feedback_required':
                await this.showFeedbackForm(data);
                break;
            default:
                console.warn('[HITLManager] Unknown event type:', eventType);
        }
    }

    /**
     * Show CLI command approval modal
     */
    async showCLICommandApproval(cliCommand) {
        const modalId = `cli-approval-${Date.now()}`;

        const modalHTML = `
            <div class="hitl-modal-overlay active" id="${modalId}">
                <div class="hitl-modal-content cli-approval-modal">
                    <div class="cli-approval-header">
                        <h3>🔧 Execute CLI Command</h3>
                        <div class="description">
                            The workflow wants to execute the following command on your system.
                            Please review and approve or reject the execution.
                        </div>
                    </div>

                    <div class="cli-approval-body">
                        <div class="cli-warning">
                            <span class="warning-icon">⚠️</span>
                            Warning: This will execute a command on your system. Only approve commands you trust and understand.
                        </div>

                        <div class="cli-command-display">
$${cliCommand.command}
                        </div>

                        <div class="cli-actions">
                            <button class="btn-reject" onclick="window.hitlManager.rejectCLICommand('${modalId}', '${cliCommand.command}')">
                                ❌ Reject
                            </button>
                            <button class="btn-modify" onclick="window.hitlManager.modifyCLICommand('${modalId}', '${cliCommand.command}')">
                                ✏️ Modify
                            </button>
                            <button class="btn-approve" onclick="window.hitlManager.approveCLICommand('${modalId}', '${cliCommand.command}')">
                                ✅ Execute
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Add modal to container
        const container = document.getElementById('hitl-container');
        container.insertAdjacentHTML('beforeend', modalHTML);

        // Store modal reference
        this.pendingInteractions.set(modalId, {
            type: 'cli_approval',
            command: cliCommand.command
        });

        // Make container interactive
        container.style.pointerEvents = 'auto';

        console.log('[HITLManager] CLI command approval modal shown');
    }

    /**
     * Show text input prompt modal
     */
    async showTextInputPrompt(inputPrompt) {
        const modalId = `text-input-${Date.now()}`;

        const modalHTML = `
            <div class="hitl-modal-overlay active" id="${modalId}">
                <div class="hitl-modal-content input-prompt-modal">
                    <div class="input-prompt-header">
                        <h3>💬 Input Required</h3>
                        <div class="description">
                            The workflow needs additional information to continue.
                        </div>
                    </div>

                    <div class="input-prompt-body">
                        <h4>${inputPrompt.prompt || 'Please provide input'}</h4>

                        <input type="text"
                               class="input-field"
                               id="input-field-${modalId}"
                               placeholder="${inputPrompt.placeholder || 'Enter your response...'}"
                               value="${inputPrompt.defaultValue || ''}">

                        <div class="cli-actions" style="margin-top: 20px;">
                            <button class="btn-reject" onclick="window.hitlManager.cancelTextInput('${modalId}')">
                                Cancel
                            </button>
                            <button class="btn-approve" onclick="window.hitlManager.submitTextInput('${modalId}')">
                                Submit
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        const container = document.getElementById('hitl-container');
        container.insertAdjacentHTML('beforeend', modalHTML);
        container.style.pointerEvents = 'auto';

        // Focus input field
        setTimeout(() => {
            const inputField = document.getElementById(`input-field-${modalId}`);
            if (inputField) inputField.focus();
        }, 100);

        this.pendingInteractions.set(modalId, {
            type: 'text_input',
            prompt: inputPrompt
        });

        console.log('[HITLManager] Text input prompt modal shown');
    }

    /**
     * Show feedback form modal
     */
    async showFeedbackForm(feedbackRequest) {
        const modalId = `feedback-${Date.now()}`;

        const modalHTML = `
            <div class="hitl-modal-overlay active" id="${modalId}">
                <div class="hitl-modal-content feedback-form-modal">
                    <div class="cli-approval-header">
                        <h3>💭 Workflow Feedback</h3>
                        <div class="description">
                            The workflow encountered an issue and needs your guidance to proceed.
                        </div>
                    </div>

                    <div class="feedback-form-body">
                        <h4>${feedbackRequest.title || 'Please provide feedback'}</h4>
                        <p>${feedbackRequest.description || ''}</p>

                        <textarea class="feedback-textarea"
                                  id="feedback-text-${modalId}"
                                  placeholder="${feedbackRequest.placeholder || 'Describe the issue or provide guidance...'}">${feedbackRequest.defaultFeedback || ''}</textarea>

                        <div class="cli-actions" style="margin-top: 20px;">
                            <button class="btn-reject" onclick="window.hitlManager.cancelFeedback('${modalId}')">
                                Skip
                            </button>
                            <button class="btn-modify" onclick="window.hitlManager.editAndResubmit('${modalId}')">
                                ✏️ Edit & Retry
                            </button>
                            <button class="btn-approve" onclick="window.hitlManager.submitFeedback('${modalId}')">
                                Submit Feedback
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        const container = document.getElementById('hitl-container');
        container.insertAdjacentHTML('beforeend', modalHTML);
        container.style.pointerEvents = 'auto';

        setTimeout(() => {
            const textArea = document.getElementById(`feedback-text-${modalId}`);
            if (textArea) textArea.focus();
        }, 100);

        this.pendingInteractions.set(modalId, {
            type: 'feedback',
            request: feedbackRequest
        });

        console.log('[HITLManager] Feedback form modal shown');
    }

    /**
     * Show confirmation dialog
     */
    async showConfirmationDialog(confirmation) {
        const modalId = `confirmation-${Date.now()}`;

        const modalHTML = `
            <div class="hitl-modal-overlay active" id="${modalId}">
                <div class="hitl-modal-content cli-approval-modal">
                    <div class="cli-approval-header">
                        <h3>🤔 Confirmation Required</h3>
                        <div class="description">
                            The workflow needs your confirmation to proceed.
                        </div>
                    </div>

                    <div class="cli-approval-body">
                        <h4>${confirmation.title || 'Confirm Action'}</h4>
                        <p>${confirmation.message || 'Do you want to proceed with this action?'}</p>

                        <div class="cli-actions">
                            <button class="btn-reject" onclick="window.hitlManager.rejectConfirmation('${modalId}')">
                                ❌ No
                            </button>
                            <button class="btn-approve" onclick="window.hitlManager.confirmAction('${modalId}')">
                                ✅ Yes
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        const container = document.getElementById('hitl-container');
        container.insertAdjacentHTML('beforeend', modalHTML);
        container.style.pointerEvents = 'auto';

        this.pendingInteractions.set(modalId, {
            type: 'confirmation',
            confirmation: confirmation
        });

        console.log('[HITLManager] Confirmation dialog shown');
    }

    // CLI Command Actions

    /**
     * Approve CLI command execution
     */
    async approveCLICommand(modalId, command) {
        console.log('[HITLManager] CLI command approved:', command);

        await this.sendWorkflowResponse({
            event_type: 'CLIHumanResponseEvent',
            execute: true,
            command: command
        });

        this.closeModal(modalId);
    }

    /**
     * Reject CLI command execution
     */
    async rejectCLICommand(modalId, command) {
        console.log('[HITLManager] CLI command rejected:', command);

        await this.sendWorkflowResponse({
            event_type: 'CLIHumanResponseEvent',
            execute: false,
            command: command
        });

        this.closeModal(modalId);
    }

    /**
     * Modify CLI command before approval
     */
    async modifyCLICommand(modalId, originalCommand) {
        console.log('[HITLManager] Modifying CLI command:', originalCommand);

        // Replace modal content with modification form
        const modal = document.getElementById(modalId);
        if (modal) {
            const body = modal.querySelector('.cli-approval-body');
            if (body) {
                body.innerHTML = `
                    <h4>Modify Command</h4>
                    <textarea class="feedback-textarea" id="modified-command-${modalId}" rows="4">${originalCommand}</textarea>

                    <div class="cli-actions" style="margin-top: 20px;">
                        <button class="btn-reject" onclick="window.hitlManager.cancelModification('${modalId}')">
                            Cancel
                        </button>
                        <button class="btn-approve" onclick="window.hitlManager.submitModifiedCommand('${modalId}', '${originalCommand}')">
                            Execute Modified Command
                        </button>
                    </div>
                `;

                // Focus textarea
                setTimeout(() => {
                    const textarea = document.getElementById(`modified-command-${modalId}`);
                    if (textarea) textarea.focus();
                }, 100);
            }
        }
    }

    /**
     * Submit modified CLI command
     */
    async submitModifiedCommand(modalId, originalCommand) {
        const textarea = document.getElementById(`modified-command-${modalId}`);
        if (!textarea) return;

        const modifiedCommand = textarea.value.trim();
        if (!modifiedCommand) return;

        console.log('[HITLManager] Modified command submitted:', modifiedCommand);

        await this.sendWorkflowResponse({
            event_type: 'CLIHumanResponseEvent',
            execute: true,
            command: modifiedCommand
        });

        this.closeModal(modalId);
    }

    /**
     * Cancel command modification
     */
    cancelModification(modalId) {
        this.closeModal(modalId);
    }

    // Text Input Actions

    /**
     * Submit text input response
     */
    async submitTextInput(modalId) {
        const inputField = document.getElementById(`input-field-${modalId}`);
        if (!inputField) return;

        const inputValue = inputField.value.trim();
        if (!inputValue) {
            inputField.focus();
            return;
        }

        console.log('[HITLManager] Text input submitted:', inputValue);

        await this.sendWorkflowResponse({
            event_type: 'TextInputResponseEvent',
            input: inputValue,
            modalId: modalId
        });

        this.closeModal(modalId);
    }

    /**
     * Cancel text input
     */
    cancelTextInput(modalId) {
        console.log('[HITLManager] Text input cancelled');

        this.closeModal(modalId);
    }

    // Feedback Actions

    /**
     * Submit feedback response
     */
    async submitFeedback(modalId) {
        const textArea = document.getElementById(`feedback-text-${modalId}`);
        if (!textArea) return;

        const feedback = textArea.value.trim();

        console.log('[HITLManager] Feedback submitted:', feedback);

        await this.sendWorkflowResponse({
            event_type: 'FeedbackResponseEvent',
            feedback: feedback,
            modalId: modalId
        });

        this.closeModal(modalId);
    }

    /**
     * Edit and resubmit (for workflow corrections)
     */
    async editAndResubmit(modalId) {
        const textArea = document.getElementById(`feedback-text-${modalId}`);
        if (!textArea) return;

        const feedback = textArea.value.trim();

        console.log('[HITLManager] Edit and resubmit:', feedback);

        await this.sendWorkflowResponse({
            event_type: 'EditAndResubmitEvent',
            feedback: feedback,
            modalId: modalId
        });

        this.closeModal(modalId);
    }

    /**
     * Cancel feedback
     */
    cancelFeedback(modalId) {
        console.log('[HITLManager] Feedback cancelled');

        this.closeModal(modalId);
    }

    // Confirmation Actions

    /**
     * Confirm action
     */
    async confirmAction(modalId) {
        console.log('[HITLManager] Action confirmed');

        await this.sendWorkflowResponse({
            event_type: 'ConfirmationResponseEvent',
            confirmed: true,
            modalId: modalId
        });

        this.closeModal(modalId);
    }

    /**
     * Reject confirmation
     */
    async rejectConfirmation(modalId) {
        console.log('[HITLManager] Action rejected');

        await this.sendWorkflowResponse({
            event_type: 'ConfirmationResponseEvent',
            confirmed: false,
            modalId: modalId
        });

        this.closeModal(modalId);
    }

    /**
     * Send workflow response to backend
     */
    async sendWorkflowResponse(response) {
        try {
            // Send response to workflow endpoint
            const result = await fetch('/api/workflow/response', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(response)
            });

            if (!result.ok) {
                console.error('[HITLManager] Failed to send workflow response');
                this.showError('Failed to send response to workflow');
            } else {
                console.log('[HITLManager] Workflow response sent successfully');
            }

        } catch (error) {
            console.error('[HITLManager] Error sending workflow response:', error);
            this.showError('Error communicating with workflow');
        }
    }

    /**
     * Close modal and clean up
     */
    closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.remove();
        }

        // Remove from pending interactions
        this.pendingInteractions.delete(modalId);

        // Check if any modals remain
        const container = document.getElementById('hitl-container');
        if (container && container.children.length === 0) {
            container.style.pointerEvents = 'none';
        }

        console.log('[HITLManager] Modal closed:', modalId);
    }

    /**
     * Check if there are active human-in-the-loop interactions
     */
    hasActiveInteractions() {
        return this.pendingInteractions.size > 0;
    }

    /**
     * Get active interaction count
     */
    getActiveInteractionCount() {
        return this.pendingInteractions.size;
    }

    /**
     * Show error message
     */
    showError(message) {
        console.error('[HITLManager] Error:', message);
        if (window.updateStatus) {
            window.updateStatus(message, 'error');
        }
    }

    /**
     * Show success message
     */
    showSuccess(message) {
        console.log('[HITLManager] Success:', message);
        if (window.updateStatus) {
            window.updateStatus(message, 'success');
        }
    }

    /**
     * Public API methods
     */
    handleWorkflowEvent(eventData) {
        this.handleHumanInputRequired(eventData);
    }

    isInitialized() {
        return hitlManagerInitialized;
    }
}

// Initialize Human In The Loop Manager
document.addEventListener('DOMContentLoaded', () => {
    window.hitlManager = new HumanInTheLoopManager();
    console.log('[HITLManager] Human In The Loop manager module loaded');
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = HumanInTheLoopManager;
}
