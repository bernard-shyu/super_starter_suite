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
        // Wait for DOM to be read
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setupUI());
        } else {
            this.setupUI();
        }
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
                max-width: 100%;
                overflow-x: auto;
                display: block;
                box-sizing: border-box;
            }

            /* Also constrain code block containers to prevent overflow */
            .code-block-container,
            .code-block-container pre,
            .code-block-container code {
                max-width: 100% !important;
                overflow-x: auto !important;
                word-wrap: break-word !important;
                white-space: pre-wrap !important;
                box-sizing: border-box !important;
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
     * NOTE: Event listening is now handled by EventDispatcher registration
     */
    setupWorkflowEventListeners() {
        // Listen for direct function calls from chat interface
        window.addEventListener('workflow-human-input-required', (event) => {
            this.handleHumanInputRequired(event.detail);
        });
    }

    /**
     * Setup UI components
     */
    setupUI() {
        if (this.uiSetup) return;

        // Add CSS styles first
        this.addHITLStyles();

        // Create HITL modal container
        this.createHITLContainer();

        // Listen for workflow events that require human input
        this.setupWorkflowEventListeners();

        // Register with EventDispatcher for HIE events
        this.registerWithEventDispatcher();

        this.uiSetup = true;

        // Notify other modules
        if (window.dispatchEvent) {
            window.dispatchEvent(new CustomEvent('hitlManagerReady', {
                detail: { hitlManager: this }
            }));
        }
    }

    /**
     * Register with EventDispatcher for HIE events
     */
    registerWithEventDispatcher() {
        if (window.getEventDispatcher) {
            const dispatcher = window.getEventDispatcher();

            // Register all HIE event types
            dispatcher.registerHandler('hie_command_event', this);
            dispatcher.registerHandler('hie_text_event', this);
            dispatcher.registerHandler('hie_confirm_event', this);
            dispatcher.registerHandler('hie_feedback_event', this);
            dispatcher.registerHandler('hie_session_protection', this);
        } else {
            console.warn('[HITLManager] EventDispatcher not available - using legacy event listeners');
        }
    }

    createHITLContainer() {
        // Check if container already exists
        let container = document.getElementById('hitl-container');
        if (container) {
            return true;
        }

        // Create container element with guaranteed visibility
        container = document.createElement('div');
        container.id = 'hitl-container';
        container.className = 'hitl-container';
        container.style.cssText = `
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            width: 100% !important;
            height: 100% !important;
            pointer-events: none !important;
            z-index: 2000 !important;
            display: block !important;
        `;

        // Insert into document body first (most reliable attachment point)
        try {
            document.body.appendChild(container);

            // Verify the container is accessible
            const verifyContainer = document.getElementById('hitl-container');
            if (verifyContainer) {
                this.hitlContainerReady = true;
                return true;
            } else {
                console.error('[HITLManager] HITL container verification failed');
                return false;
            }
        } catch (error) {
            console.error('[HITLManager] Failed to create HITL container:', error);
            return false;
        }
    }



    /**
     * Send message via WebSocket if available, fallback to HTTP
     */
    sendWebSocketMessage(message) {
        if (this.workflowWebSocket && this.workflowWebSocket.readyState === WebSocket.OPEN) {
            this.workflowWebSocket.send(JSON.stringify(message));
            return true;
        }
        return false;
    }

    /**
     * Handle human input required event from workflow
     */
    async handleHumanInputRequired(eventData) {
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
     * Handle HIE events through EventDispatcher interface
     */
    handleEvent(eventType, data, workflowId) {

        try {
            switch (eventType) {
                case 'hie_command_event':
                    this.showCLICommandApproval({
                        command: data.command,
                        session_id: data.session_id,
                        workflow_id: data.workflow_id
                    });
                    break;

                case 'hie_text_event':
                    this.showTextInputPrompt({
                        prompt: data.prompt || 'Input required',
                        placeholder: data.placeholder || 'Enter your response...',
                        defaultValue: data.defaultValue || ''
                    });
                    break;

                case 'hie_confirm_event':
                    console.log('[HITLManager] Processing hie_confirm_event for confirmation');
                    this.showConfirmationDialog(data);
                    break;

                case 'hie_feedback_event':
                    console.log('[HITLManager] Processing hie_feedback_event for feedback');
                    this.showFeedbackForm(data);
                    break;

                case 'hie_session_protection':
                    // Session protection snapshot stored - informational only, no UI action needed
                    console.log('[HITLManager] 📦 Session protection snapshot stored - no UI action required');
                    break;

                default:
                    console.warn(`[HITLManager] Unknown HIE event type: ${eventType}`, { data, workflowId });
            }
        } catch (error) {
            console.error(`[HITLManager] Error handling ${eventType}:`, error, { data, workflowId });
        }
    }

    /**
     * Show CLI command approval modal
     */
    async showCLICommandApproval(cliCommand) {
        const modalId = `cli-approval-${Date.now()}`;

        // Escape command for safe HTML/JS insertion
        const escapedCommand = this.escapeCommandForHTML(cliCommand.command);

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
${this.escapeCommandForHTML(cliCommand.command)}
                        </div>

                        <div class="cli-actions">
                            <button class="btn-reject" data-modal-id="${modalId}" onclick="window.hitlManager.rejectCLICommand(this)">
                                ❌ Reject
                            </button>
                            <button class="btn-modify" data-modal-id="${modalId}" onclick="window.hitlManager.modifyCLICommand(this)">
                                ✏️ Modify
                            </button>
                            <button class="btn-approve" data-modal-id="${modalId}" onclick="window.hitlManager.approveCLICommand(this)">
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

        // Store modal reference WITH SESSION CONTEXT
        this.pendingInteractions.set(modalId, {
            type: 'cli_approval',
            command: cliCommand.command,
            session_id: cliCommand.session_id,  // Fix: Store session ID from HIE event
            workflow_id: cliCommand.workflow_id  // And store workflow ID too
        });

        // Make container interactive
        container.style.pointerEvents = 'auto';
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
                        <button class="btn-reject" onclick="window.hitlManager.cancelModification('${modalId}')">
                            Cancel
                        </button>
                        <button class="btn-approve" onclick="window.hitlManager.submitModifiedCommand(this)">
                            Execute Modified Command
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
    }

    /**
     * Show confirmation dialog
     */
    async showConfirmationDialog(confirmation) {
        const result = await window.showConfirm(confirmation.title || 'Confirmation Required', confirmation.message || 'Do you want to proceed with this action?', {
            type: 'acceptReject',
            confirmText: 'Accept',
            cancelText: 'Reject'
        });

        if (result) {
            this.confirmAction(null, confirmation); // null because we don't need modalId if using window.showConfirm
        } else {
            this.rejectConfirmation(null, confirmation);
        }
    }

    // CLI Command Actions

    /**
     * Escape command string for safe HTML insertion
     */
    escapeCommandForHTML(command) {
        return command
            .replace(/&/g, '&')
            .replace(/</g, '<')
            .replace(/>/g, '>')
            .replace(/"/g, '"')
            .replace(/'/g, '&#39;');
    }

    /**
     * Approve CLI command execution - show progress and close modal after response sent
     */
    async approveCLICommand(buttonElement) {
        const modalId = buttonElement.getAttribute('data-modal-id');

        // Get command and session context from stored modal data
        const modalData = this.pendingInteractions.get(modalId);
        const command = modalData?.command;
        const session_id = modalData?.session_id;
        const workflow_id = modalData?.workflow_id;

        if (!command) {
            console.error('[HITLManager] No command found for modal:', modalId);
            return;
        }

        // Show execution progress instead of immediately closing
        this._showExecutionProgress(modalId, command);

        try {
            // Send approval with complete session context
            const response = await this.sendWorkflowResponse({
                event_type: 'CLIHumanResponseEvent',
                execute: true,
                command: command,
                session_id: session_id,
                workflow_id: workflow_id
            });

            // Check if response is valid
            if (!response) {
                console.error('[HITLManager] No response received from sendWorkflowResponse');
                this._showExecutionError(modalId, command, 'No response from server');
                setTimeout(() => {
                    this.closeModal(modalId);
                }, 3000);
                return;
            }

            // Handle different response types (Response object or error object)
            let result;
            if (response && typeof response.json === 'function') {
                // It's a Response object from fetch
                result = await response.json().catch((error) => {
                    console.error('[HITLManager] Failed to parse JSON response:', error);
                    return {};
                });
            } else if (response && response.error) {
                // It's an error object from sendWorkflowResponse
                console.error('[HITLManager] Error response received:', response);
                result = response;
            } else if (response && typeof response === 'object' && response.status) {
                // It's already a parsed response object (from sendWorkflowResponse success case)
                console.log('[HITLManager] Parsed response object received:', response);
                result = response;
            } else {
                // Unexpected response format
                console.error('[HITLManager] Unexpected response format:', response);
                result = { error: 'unknown', message: 'Unexpected response format' };
            }
            console.log('[HITLManager] CLI approval response received:', result);

            // Handle execution results from backend response
            if (result && result.execution_result) {
                console.log('[HITLManager] Execution results received:', result.execution_result);

                // Update modal with execution results
                const executionResult = result.execution_result;
                this._showExecutionResults(modalId, executionResult);

                // Generate completion response for successful command execution
                if (executionResult.success) {
                    await this.generateHITLCompletionResponse(executionResult);
                }

                // Add execution results to chat
                await this._addCommandExecutionMessage(session_id, workflow_id, executionResult);

                // Close modal after showing results
                setTimeout(() => {
                    this.closeModal(modalId, true);
                }, 5000); // Give user time to see results

            } else {
                console.log('[HITLManager] No execution results in response, keeping progress indicator');

                // Close modal after delay if no results received
                setTimeout(() => {
                    this.closeModal(modalId, true);
                }, 3000);
            }

        } catch (error) {
            console.error('[HITLManager] Failed to send CLI approval response:', error);
            // Show error and close modal
            this._showExecutionError(modalId, command, error.message);
            setTimeout(() => {
                this.closeModal(modalId);
            }, 3000);
        }
    }

    /**
     * Reject CLI command execution
     */
    async rejectCLICommand(buttonElement) {
        console.log('[HITLManager] rejectCLICommand called with buttonElement:', buttonElement);
        const modalId = buttonElement.getAttribute('data-modal-id');
        console.log('[HITLManager] Extracted modalId:', modalId);

        // Get command and session context from stored modal data
        const modalData = this.pendingInteractions.get(modalId);
        console.log('[HITLManager] Modal data retrieved:', modalData);
        const command = modalData?.command;
        const session_id = modalData?.session_id;
        const workflow_id = modalData?.workflow_id;

        if (!command) {
            console.error('[HITLManager] No command found for modal:', modalId);
            return;
        }

        console.log('[HITLManager] CLI command rejected:', command, 'session:', session_id);

        try {
            // Send rejection response to backend
            console.log('[HITLManager] About to send rejection response to backend');
            await this.sendWorkflowResponse({
                event_type: 'CLIHumanResponseEvent',
                execute: false,
                command: command,
                session_id: session_id,  // Include session context
                workflow_id: workflow_id
            });
            console.log('[HITLManager] Rejection response sent successfully');
        } catch (responseError) {
            console.error('[HITLManager] Failed to send rejection response:', responseError);
            // Continue with modal close even if response fails
        }

        try {
            // Add rejection message to chat UI
            console.log('[HITLManager] Adding rejection message to chat');
            await this._addHITLResponseMessage(session_id, workflow_id, 'rejected', command);
            console.log('[HITLManager] Rejection message added to chat');
        } catch (messageError) {
            console.error('[HITLManager] Failed to add rejection message to chat:', messageError);
            // Continue with modal close even if message addition fails
        }

        try {
            // Refresh chat UI to show new HITL messages
            console.log('[HITLManager] About to refresh chat history');
            await this._refreshChatHistory(session_id);
            console.log('[HITLManager] Chat history refresh completed');
        } catch (refreshError) {
            console.error('[HITLManager] Failed to refresh chat history:', refreshError);
            // Continue with modal close even if refresh fails
        }

        // Preserve session context for continued messaging after HITL rejection
        try {
            if (session_id && workflow_id && window.chatUIManager && window.chatUIManager.preserveSessionContextAfterHITL) {
                console.log('[HITLManager] 🔄 Preserving session context after HITL rejection:', session_id, workflow_id);
                window.chatUIManager.preserveSessionContextAfterHITL(session_id, workflow_id);
            } else {
                console.warn('[HITLManager] ⚠️ Could not preserve session context after HITL rejection - chatUIManager not available');
            }
        } catch (contextError) {
            console.error('[HITLManager] ❌ Failed to preserve session context after HITL rejection:', contextError);
        }

        // Always close the modal, even if other operations failed
        console.log('[HITLManager] About to close modal after rejection');
        this.closeModal(modalId);
    }

    /**
     * Modify CLI command before approval
     */
    async modifyCLICommand(buttonElement) {
        const modalId = buttonElement.getAttribute('data-modal-id');

        // Get command from stored modal data instead of button attributes
        const modalData = this.pendingInteractions.get(modalId);
        const originalCommand = modalData?.command;

        if (!originalCommand) {
            console.error('[HITLManager] No command found for modal:', modalId);
            return;
        }

        console.log('[HITLManager] Modifying CLI command:', originalCommand);

        // Replace modal content with modification form
        const modal = document.getElementById(modalId);
        if (modal) {
            const body = modal.querySelector('.cli-approval-body');
            if (body) {
                const escapedCommand = this.escapeCommandForHTML(originalCommand);
                body.innerHTML = `
                    <h4>Modify Command</h4>
                    <textarea class="feedback-textarea" id="modified-command-${modalId}" rows="4">${escapedCommand}</textarea>

                    <div class="cli-actions" style="margin-top: 20px;">
                        <button class="btn-reject" onclick="window.hitlManager.cancelModification('${modalId}')">
                            Cancel
                        </button>
                        <button class="btn-approve" onclick="window.hitlManager.submitModifiedCommand(this)">
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
    async submitModifiedCommand(buttonElement) {
        const modalId = buttonElement.getAttribute('data-modal-id');
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
    async confirmAction(modalId, contextData = {}) {
        console.log('[HITLManager] Action confirmed');

        await this.sendWorkflowResponse({
            event_type: 'ConfirmationResponseEvent',
            confirmed: true,
            modalId: modalId,
            session_id: contextData.session_id,
            workflow_id: contextData.workflow_id
        });

        if (modalId) {
            this.closeModal(modalId);
        }
    }

    /**
     * Reject confirmation
     */
    async rejectConfirmation(modalId, contextData = {}) {
        console.log('[HITLManager] Action rejected');

        await this.sendWorkflowResponse({
            event_type: 'ConfirmationResponseEvent',
            confirmed: false,
            modalId: modalId,
            session_id: contextData.session_id,
            workflow_id: contextData.workflow_id
        });

        if (modalId) {
            this.closeModal(modalId);
        }
    }

    /**
     * Send workflow response to backend
     */
    async sendWorkflowResponse(response) {
        // Get workflow_id from response data
        const workflow_id = response.workflow_id || window.globalState?.currentWorkflow;
        console.log('[HITLManager] Using workflow_id:', workflow_id);
        if (!workflow_id) {
            console.error('[HITLManager] No workflow_id available for response');
            this.showError('Cannot send response - no workflow context');
            return;
        }

        // Try WebSocket first, fallback to HTTP
        const wsMessage = {
            type: 'hitl_response',
            data: response
        };

        console.log('[HITLManager] Attempting WebSocket message send');
        if (this.sendWebSocketMessage(wsMessage)) {
            console.log('[HITLManager] HITL response sent via WebSocket');
            // For WebSocket, we don't have a response to return, so return a success indicator
            return { success: true, method: 'websocket' };
        }

        // Fallback to HTTP with timeout and better error handling
        try {
            console.log('[HITLManager] WebSocket not available, using HTTP fallback');
            // Get session_id from response data (should be provided by HIE event)
            const session_id = response.session_id;
            if (!session_id) {
                console.error('[HITLManager] No session_id available for HITL response');
                return { error: 'no_session_id', message: 'Session ID required for HITL response' };
            }

            console.log('[HITLManager] Making fetch request to:', `/api/workflow/${session_id}/response`);

            // Create AbortController for timeout handling
            const controller = new AbortController();
            const timeoutId = setTimeout(() => {
                console.warn('[HITLManager] Request timed out after 10 seconds');
                controller.abort();
            }, 10000); // 10 second timeout

            const fetchOptions = {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(response),
                signal: controller.signal
            };

            console.log('[HITLManager] Fetch options prepared, initiating request...');
            const result = await fetch(`/api/workflow/${session_id}/response`, fetchOptions);
            clearTimeout(timeoutId); // Clear timeout on success

            console.log('[HITLManager] Fetch completed with result:', {
                ok: result.ok,
                status: result.status,
                statusText: result.statusText,
                headers: Object.fromEntries(result.headers.entries())
            });

            if (!result.ok) {
                const errorText = await result.text().catch(() => 'Unable to read error response');
                console.error('[HITLManager] HTTP error response:', {
                    status: result.status,
                    statusText: result.statusText,
                    body: errorText
                });
                this.showError(`Failed to send response to workflow: ${result.status} ${result.statusText}`);
            } else {
                const responseData = await result.json().catch(() => ({}));
                console.log('[HITLManager] Workflow response sent successfully via HTTP:', responseData);
                // Return the parsed response data
                return responseData;
            }

        } catch (error) {
            if (error.name === 'AbortError') {
                console.error('[HITLManager] Request timed out - backend may be unresponsive');
                this.showError('Request timed out - workflow may be unresponsive');
                return { error: 'timeout', message: 'Request timed out' };
            } else {
                console.error('[HITLManager] Error sending workflow response via HTTP:', {
                    name: error.name,
                    message: error.message,
                    stack: error.stack
                });
                this.showError('Error communicating with workflow');
                return { error: 'communication_error', message: 'Failed to send response to workflow' };
            }
        }
        return { error: 'unknown_error', message: 'Unknown error occurred' };
    }

    /**
     * Close modal and clean up
     */
    async closeModal(modalId, needsSessionRecovery = false) {
        console.log('[HITLManager] Attempting to close modal:', modalId);

        const modal = document.getElementById(modalId);
        if (modal) {
            console.log('[HITLManager] Found modal, removing from DOM');
            modal.remove();
        } else {
            console.error('[HITLManager] Modal not found in DOM:', modalId);
            // Try to find any modal that might match
            const allModals = document.querySelectorAll('[id^="cli-approval-"], [id^="text-input-"], [id^="confirmation-"], [id^="feedback-"]');
            console.log('[HITLManager] Found', allModals.length, 'total modals in DOM');
            allModals.forEach(m => console.log('  - Modal ID:', m.id));
        }

        // Remove from pending interactions
        const wasInPending = this.pendingInteractions.has(modalId);
        this.pendingInteractions.delete(modalId);
        console.log('[HITLManager] Removed from pending interactions:', wasInPending);

        // 🔄 SESSION RECOVERY: Only reconnect workflow session after successful HIE execution
        if (needsSessionRecovery) {
            await this._recoverHIESSession();
        }

        // Check if any modals remain
        const container = document.getElementById('hitl-container');
        if (container) {
            console.log('[HITLManager] Container has', container.children.length, 'remaining children');
            if (container.children.length === 0) {
                container.style.pointerEvents = 'none';
                console.log('[HITLManager] Disabled container pointer events');
            }
        } else {
            console.warn('[HITLManager] HITL container not found');
        }

        console.log('[HITLManager] Modal close process completed for:', modalId);
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
     * Show execution error in modal
     */
    _showExecutionError(modalId, command, errorMessage) {
        const modal = document.getElementById(modalId);
        if (!modal) return;

        const body = modal.querySelector('.cli-approval-body');
        if (!body) return;

        // Update modal content to show execution error
        body.innerHTML = `
            <div style="text-align: center; padding: 40px 20px;">
                <h4 style="color: #dc3545; margin: 0 0 16px 0;">❌ Execution Failed</h4>
                <p style="margin: 0 0 16px 0; color: #666;">Command execution encountered an error.</p>
                <div style="background: var(--code-bg, #f6f8fa); border: 1px solid var(--border-color, #e1e4e8); border-radius: 8px; padding: 16px; margin: 16px 0; font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace; font-size: 14px; text-align: left;">
${this.escapeCommandForHTML(command)}
                </div>
                <div style="background: #f8d7da; border: 1px solid #f5c6cb; border-radius: 4px; padding: 12px; margin-top: 16px; text-align: left;">
                    <strong>Error:</strong> ${this.escapeCommandForHTML(errorMessage)}
                </div>
            </div>
        `;

        console.log('[HITLManager] Execution error displayed in modal:', modalId);
    }

    /**
     * Show execution progress in modal
     */
    _showExecutionProgress(modalId, command) {
        const modal = document.getElementById(modalId);
        if (!modal) return;

        const body = modal.querySelector('.cli-approval-body');
        if (!body) return;

        // Update modal content to show execution progress
        body.innerHTML = `
            <div style="text-align: center; padding: 40px 20px;">
                <div class="hitl-spinner" style="margin: 0 auto 20px;"></div>
                <h4 style="color: #28a745; margin: 0 0 16px 0;">⚡ Executing Command</h4>
                <p style="margin: 0 0 16px 0; color: #666;">Please wait while the command is executed...</p>
                <div style="background: var(--code-bg, #f6f8fa); border: 1px solid var(--border-color, #e1e4e8); border-radius: 8px; padding: 16px; margin: 16px 0; font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace; font-size: 14px; text-align: left;">
${this.escapeCommandForHTML(command)}
                </div>
                <div id="execution-status-${modalId}" style="margin-top: 16px; font-style: italic; color: #666;">
                    Executing...
                </div>
            </div>
        `;

        console.log('[HITLManager] Execution progress shown for modal:', modalId);
    }

    /**
     * Handle successful execution result
     */
    handleExecutionResult(data) {
        console.log('[HITLManager] Handling execution result:', data);

        const command = data.command || 'Unknown command';
        const exitCode = data.exit_code || 0;
        const stdout = data.stdout || '';
        const stderr = data.stderr || '';
        const success = data.success !== false;

        // Find and update any modal showing this command
        const allModals = document.querySelectorAll('[id^="cli-approval-"], [id^="text-input-"], [id^="confirmation-"], [id^="feedback-"]');
        allModals.forEach(modal => {
            const modalId = modal.id;
            const statusDiv = document.getElementById(`execution-status-${modalId}`);
            if (statusDiv) {
                // Update status to show results
                let statusHTML = '';

                if (success) {
                    statusHTML = `
                        <h4 style="color: #28a745; margin: 16px 0 8px 0;">✅ Command Executed Successfully</h4>
                        <div style="margin: 16px 0;">
                            <strong>Exit Code:</strong> ${exitCode}
                        </div>
                    `;

                    if (stdout) {
                        statusHTML += `
                            <div style="margin: 16px 0;">
                                <strong>Output:</strong>
                                <div style="background: var(--code-bg, #f6f8fa); border: 1px solid var(--border-color, #e1e4e8); border-radius: 4px; padding: 8px; margin-top: 8px; font-family: monospace; font-size: 12px; max-height: 150px; overflow-y: auto;">${this.escapeCommandForHTML(stdout)}</div>
                            </div>
                        `;
                    }

                    if (stderr) {
                        statusHTML += `
                            <div style="margin: 16px 0;">
                                <strong>Warnings/Errors:</strong>
                                <div style="background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 4px; padding: 8px; margin-top: 8px; font-family: monospace; font-size: 12px; max-height: 150px; overflow-y: auto;">${this.escapeCommandForHTML(stderr)}</div>
                            </div>
                        `;
                    }
                } else {
                    statusHTML = `
                        <h4 style="color: #dc3545; margin: 16px 0 8px 0;">❌ Command Failed</h4>
                        <div style="margin: 16px 0;">
                            <strong>Exit Code:</strong> ${exitCode}
                        </div>
                    `;

                    if (stderr) {
                        statusHTML += `
                            <div style="margin: 16px 0;">
                                <strong>Error Output:</strong>
                                <div style="background: #f8d7da; border: 1px solid #f5c6cb; border-radius: 4px; padding: 8px; margin-top: 8px; font-family: monospace; font-size: 12px; max-height: 150px; overflow-y: auto;">${this.escapeCommandForHTML(stderr)}</div>
                            </div>
                        `;
                    }
                }

                statusDiv.innerHTML = statusHTML;

                // Auto-close modal after 5 seconds with session recovery for successful execution
                setTimeout(() => {
                    window.hitlManager.closeModal(modalId, true);  // Session recovery needed after execution
                }, 5000);
            }
        });
    }

    /**
     * Show execution results in modal
     */
    _showExecutionResults(modalId, executionResult) {
        const modal = document.getElementById(modalId);
        if (!modal) return;

        const body = modal.querySelector('.cli-approval-body');
        if (!body) return;

        const command = executionResult.command || 'Unknown command';
        const exitCode = executionResult.exit_code || 0;
        const stdout = executionResult.stdout || '';
        const stderr = executionResult.stderr || '';
        const success = executionResult.success !== false;

        let resultsHTML = '';

        if (success) {
            resultsHTML = `
                <h4 style="color: #28a745; margin: 16px 0 8px 0;">✅ Command Executed Successfully</h4>
                <div style="margin: 16px 0;">
                    <strong>Exit Code:</strong> ${exitCode}
                </div>
            `;

            if (stdout) {
                resultsHTML += `
                    <div style="margin: 16px 0;">
                        <strong>Output:</strong>
                        <div style="background: var(--code-bg, #f6f8fa); border: 1px solid var(--border-color, #e1e4e8); border-radius: 4px; padding: 8px; margin-top: 8px; font-family: monospace; font-size: 12px; max-height: 150px; overflow-y: auto;">${this.escapeCommandForHTML(stdout)}</div>
                    </div>
                `;
            }

            if (stderr) {
                resultsHTML += `
                    <div style="margin: 16px 0;">
                        <strong>Warnings/Errors:</strong>
                        <div style="background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 4px; padding: 8px; margin-top: 8px; font-family: monospace; font-size: 12px; max-height: 150px; overflow-y: auto;">${this.escapeCommandForHTML(stderr)}</div>
                    </div>
                `;
            }
        } else {
            resultsHTML = `
                <h4 style="color: #dc3545; margin: 16px 0 8px 0;">❌ Command Failed</h4>
                <div style="margin: 16px 0;">
                    <strong>Exit Code:</strong> ${exitCode}
                </div>
            `;

            if (stderr) {
                resultsHTML += `
                    <div style="margin: 16px 0;">
                        <strong>Error Output:</strong>
                        <div style="background: #f8d7da; border: 1px solid #f5c6cb; border-radius: 4px; padding: 8px; margin-top: 8px; font-family: monospace; font-size: 12px; max-height: 150px; overflow-y: auto;">${this.escapeCommandForHTML(stderr)}</div>
                    </div>
                `;
            }
        }

        // Update modal content
        body.innerHTML = `
            <div style="text-align: center; padding: 20px;">
                ${resultsHTML}
            </div>
        `;

        console.log('[HITLManager] Execution results displayed in modal:', modalId);
    }

    /**
     * Handle execution timeout
     */
    handleExecutionTimeout(data) {
        console.log('[HITLManager] Handling execution timeout:', data);

        const command = data.command || 'Unknown command';

        // Find and update any modal showing this command
        const allModals = document.querySelectorAll('[id^="cli-approval-"], [id^="text-input-"], [id^="confirmation-"], [id^="feedback-"]');
        allModals.forEach(modal => {
            const modalId = modal.id;
            const statusDiv = document.getElementById(`execution-status-${modalId}`);
            if (statusDiv) {
                // Update status to show timeout
                statusDiv.innerHTML = `
                    <h4 style="color: #ffc107; margin: 16px 0 8px 0;">⏰ Command Timed Out</h4>
                    <div style="margin: 16px 0;">
                        <strong>Timeout:</strong> Command execution exceeded the maximum allowed time (30 seconds).
                    </div>
                    <div style="margin: 16px 0; padding: 8px; background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 4px;">
                        <strong>Security Policy:</strong> Commands are limited to 30 seconds of execution time to prevent system lockup.
                        Consider breaking long-running commands into smaller steps or using background execution if available.
                    </div>
                `;

                // Auto-close modal after 8 seconds for timeout
                setTimeout(() => {
                    window.hitlManager.closeModal(modalId);
                }, 8000);
            }
        });
    }

    /**
     * Handle execution error
     */
    handleExecutionError(data) {
        console.log('[HITLManager] Handling execution error:', data);

        const command = data.command || 'Unknown command';
        const error = data.error || 'Unknown execution error';

        // Find and update any modal showing this command
        const allModals = document.querySelectorAll('[id^="cli-approval-"], [id^="text-input-"], [id^="confirmation-"], [id^="feedback-"]');
        allModals.forEach(modal => {
            const modalId = modal.id;
            const statusDiv = document.getElementById(`execution-status-${modalId}`);
            if (statusDiv) {
                // Update status to show error
                statusDiv.innerHTML = `
                    <h4 style="color: #dc3545; margin: 16px 0 8px 0;">💥 Command Execution Failed</h4>
                    <div style="margin: 16px 0;">
                        <strong>Error:</strong> ${this.escapeCommandForHTML(error)}
                    </div>
                    <div style="margin: 16px 0; padding: 8px; background: #f8d7da; border: 1px solid #f5c6cb; border-radius: 4px;">
                        <strong>Possible Causes:</strong>
                        <ul style="margin: 8px 0 0 20px; padding: 0;">
                            <li>Command syntax error</li>
                            <li>Missing required programs/files</li>
                            <li>Permission issues</li>
                            <li>Security policy rejection</li>
                        </ul>
                    </div>
                `;

                // Auto-close modal after 8 seconds for error
                setTimeout(() => {
                    window.hitlManager.closeModal(modalId);
                }, 8000);
            }
        });
    }

    /**
     * Refresh chat history to show new HITL messages
     */
    async _refreshChatHistory(sessionId = null) {
        try {
            console.log('[HITLManager] Refreshing chat history after HITL response...');

            // Always use the current infrastructure session ID
            const chatSessionId = window.sessionManager.getInfrastructureSession(window.globalState?.currentWorkflow);
            if (!chatSessionId) {
                console.log('[HITLManager] No infrastructure session ID available, skipping refresh');
                return;
            }

            // Fetch latest messages from chat history API
            console.log(`[HITLManager] Fetching messages for chat session: ${chatSessionId}`);

            // Get workflow context for scoped API call
            const workflowId = window.globalState?.currentWorkflow || 'default';
            try {
                // Get workflow session details using centralized utility
                const sessionId = chatSessionId; // chatSessionId should be the session_id
                const sessionData = await window.apiUtils.getChatSessionDetails(window.sessionManager.getInfrastructureSession(window.globalState?.currentWorkflow), sessionId);
                console.log(`[HITLManager] Received ${sessionData.messages?.length || 0} messages from API`);

                // Add any messages that are not already displayed
                // We need to keep track of already displayed messages to avoid duplicates
                const displayedMessageIds = new Set();

                // Get current messages from container to check what's already displayed
                const messageContainer = document.getElementById('message-container');
                if (messageContainer) {
                    const existingMessages = messageContainer.querySelectorAll('[data-message-id]');
                    existingMessages.forEach(msg => {
                        const msgId = msg.getAttribute('data-message-id');
                        if (msgId) displayedMessageIds.add(msgId);
                    });
                }

                console.log(`[HITLManager] Found ${displayedMessageIds.size} already displayed messages`);

                // Add new messages that aren't already displayed
                let newMessagesAdded = 0;
                for (const msg of (sessionData.messages || [])) {
                    const msgId = msg.message_id || this._generateTempMsgId(msg);
                    if (!displayedMessageIds.has(msgId)) {
                        console.log(`[HITLManager] Adding new message: ${msg.role} (${msgId.substring(0, 8)}...)`);

                        // Use chat manager to add message with proper formatting
                        const messageType = msg.enhanced_metadata?.HIE_intercepted ? 'system' : 'normal';
                        const message = {
                            role: msg.role,
                            content: msg.content,
                            message_id: msgId,
                            enhanced_metadata: msg.enhanced_metadata || {}
                        };

                        if (window.unifiedChatRenderer) {
                            window.unifiedChatRenderer.addLiveMessage(message, { source: 'hie_refresh' });
                        } else if (window.chatUIManager) {
                            window.chatUIManager.addMessage(msg.role, msg.content, messageType, msgId, msg.enhanced_metadata);
                        }

                        newMessagesAdded++;
                    }
                }

                console.log(`[HITLManager] Added ${newMessagesAdded} new messages to chat UI`);

                if (newMessagesAdded > 0) {
                    // Scroll to bottom for new messages
                    setTimeout(() => {
                        if (messageContainer) {
                            messageContainer.scrollTop = messageContainer.scrollHeight;
                        }
                    }, 100);
                }

            } catch (fetchError) {
                console.error('[HITLManager] Error fetching chat history:', fetchError);
                // Fall back to manual page refresh prompt
                if (await window.showConfirm('Refresh Required', 'New messages available. Refresh page to see HITL responses?', { confirmText: 'Refresh Now' })) {
                    window.location.reload();
                }
            }

        } catch (error) {
            console.error('[HITLManager] Failed to refresh chat history:', error);
            // Fallback prompt
            setTimeout(async () => {
                if (await window.showConfirm('Update Available', 'Chat update available. Refresh page?', { confirmText: 'Refresh' })) {
                    window.location.reload();
                }
            }, 1000);
        }
    }

    /**
     * Add HITL response message to chat UI and save to session
     */
    async _addHITLResponseMessage(sessionId, workflowId, action, command) {
        try {
            console.log(`[HITLManager] Adding ${action} message to chat for session:`, sessionId);

            // Create response message based on action
            let messageContent = '';
            let messageRole = 'assistant';

            switch (action) {
                case 'rejected':
                    messageContent = `❌ **Command Rejected by User**\n\nThe following command was rejected:\n\`\`\`bash\n${command}\n\`\`\`\n\nThe workflow will continue with alternative approaches.`;
                    messageRole = 'system';
                    break;
                case 'approved':
                    messageContent = `✅ **Command Approved by User**\n\nExecuting:\n\`\`\`bash\n${command}\n\`\`\``;
                    messageRole = 'system';
                    break;
                case 'modified':
                    messageContent = `✏️ **Command Modified by User**\n\nNew command:\n\`\`\`bash\n${command}\n\`\`\``;
                    messageRole = 'system';
                    break;
                default:
                    messageContent = `🤖 **HITL Response**: ${action}`;
                    messageRole = 'system';
            }

            // Generate unique message ID
            const messageId = `hitl_response_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

            // Create message object
            const message = {
                role: messageRole,
                content: messageContent,
                message_id: messageId,
                enhanced_metadata: {
                    HITL_response: true,
                    action: action,
                    workflow_id: workflowId,
                    session_id: sessionId,
                    timestamp: new Date().toISOString()
                }
            };

            console.log('[HITLManager] Created HITL response message:', message);

            // Save message to session immediately
            try {
                const sessionIdToUse = sessionId;

                if (window.chatSessionManager && sessionIdToUse) {
                    const messageData = {
                        role: messageRole,
                        content: messageContent,
                        message_id: messageId,
                        timestamp: new Date().toISOString(),
                        enhanced_metadata: message.enhanced_metadata
                    };

                    // Make sure chatSessionManager is properly initialized
                    if (typeof window.chatSessionManager.saveMessageToCurrentSession === 'function') {
                        await window.chatSessionManager.saveMessageToCurrentSession(messageData);
                        console.log('[HITLManager] ✅ HITL response message saved to session:', messageId, 'session:', sessionIdToUse);
                    } else {
                        console.warn('[HITLManager] ⚠️ chatSessionManager.saveMessageToCurrentSession not available');
                    }
                } else {
                    console.warn('[HITLManager] ⚠️ Could not save HITL response to session - chatSessionManager:', !!window.chatSessionManager, 'sessionId:', sessionIdToUse);
                }
            } catch (saveError) {
                console.error('[HITLManager] ❌ Failed to save HITL response message to session:', saveError);
            }

            // Add to chat UI using unified chat renderer
            if (window.unifiedChatRenderer) {
                console.log('[HITLManager] Adding message via unifiedChatRenderer');
                window.unifiedChatRenderer.addLiveMessage(message, { source: 'hitl_response' });
            } else if (window.chatUIManager) {
                console.log('[HITLManager] Adding message via chatUIManager');
                window.chatUIManager.addMessage(messageRole, messageContent, 'system', messageId, message.enhanced_metadata);
            } else {
                console.warn('[HITLManager] No chat renderer available to add HITL response message');
            }

            // Scroll to bottom to show new message
            setTimeout(() => {
                const messageContainer = document.getElementById('message-container');
                if (messageContainer) {
                    messageContainer.scrollTop = messageContainer.scrollHeight;
                }
            }, 100);

        } catch (error) {
            console.error('[HITLManager] Failed to add HITL response message:', error);
        }
    }

    /**
     * Add command execution message to chat
     */
    async _addCommandExecutionMessage(sessionId, workflowId, executionResult) {
        try {
            console.log('[HITLManager] Adding command execution message to chat:', executionResult);

            const command = executionResult.command || 'Unknown command';
            const exitCode = executionResult.exit_code || 0;
            const stdout = executionResult.stdout || '';
            const stderr = executionResult.stderr || '';
            const success = executionResult.success !== false;

            let messageContent = '';

            if (success) {
                messageContent = `✅ **Command Executed Successfully**\n\n**Command:**\n\`\`\`bash\n${command}\n\`\`\`\n\n**Exit Code:** ${exitCode}`;

                if (stdout) {
                    messageContent += `\n\n**Output:**\n\`\`\`\n${stdout}\n\`\`\``;
                }

                if (stderr) {
                    messageContent += `\n\n**Warnings/Errors:**\n\`\`\`\n${stderr}\n\`\`\``;
                }
            } else {
                messageContent = `❌ **Command Execution Failed**\n\n**Command:**\n\`\`\`bash\n${command}\n\`\`\`\n\n**Exit Code:** ${exitCode}`;

                if (stderr) {
                    messageContent += `\n\n**Error Output:**\n\`\`\`\n${stderr}\n\`\`\``;
                }
            }

            // Generate unique message ID
            const messageId = `command_execution_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

            // Create message object
            const message = {
                role: 'system',
                content: messageContent,
                message_id: messageId,
                enhanced_metadata: {
                    command_execution: true,
                    execution_result: executionResult,
                    workflow_id: workflowId,
                    session_id: sessionId,
                    timestamp: new Date().toISOString()
                }
            };

            console.log('[HITLManager] Created command execution message:', message);

            // Add to chat UI using unified chat renderer
            if (window.unifiedChatRenderer) {
                console.log('[HITLManager] Adding message via unifiedChatRenderer');
                window.unifiedChatRenderer.addLiveMessage(message, { source: 'command_execution' });
            } else if (window.chatUIManager) {
                console.log('[HITLManager] Adding message via chatUIManager');
                window.chatUIManager.addMessage('system', messageContent, 'system', messageId, message.enhanced_metadata);
            } else {
                console.warn('[HITLManager] No chat renderer available to add command execution message');
            }

            // Scroll to bottom to show new message
            setTimeout(() => {
                const messageContainer = document.getElementById('message-container');
                if (messageContainer) {
                    messageContainer.scrollTop = messageContainer.scrollHeight;
                }
            }, 100);

        } catch (error) {
            console.error('[HITLManager] Failed to add command execution message:', error);
        }
    }

    /**
     * Generate temporary message ID for messages without one
     */
    _generateTempMsgId(msg) {
        // Create deterministic ID from message content and timestamp
        const content = msg.content || '';
        const timestamp = msg.timestamp || '';
        const hash = [...(content + timestamp)].reduce((a, b) => {
            a = ((a << 5) - a) + b.charCodeAt(0);
            return a & a;
        }, 0);
        return `temp_${Math.abs(hash).toString(36)}`;
    }

    /**
     * 🔄 Recover HIE session after modal close
     */
    async _recoverHIESSession() {
        try {
            // Get current workflow from global state or pending interactions
            let workflowId = window.globalState?.currentWorkflow;
            let sessionId = window.sessionManager?.getInfrastructureSession(workflowId);

            // Fallback: try to get workflow ID and session ID from any pending interactions
            if (!workflowId || !sessionId) {
                for (const [modalId, interaction] of this.pendingInteractions) {
                    if (!workflowId && interaction.workflow_id) {
                        workflowId = interaction.workflow_id;
                    }
                    if (!sessionId && interaction.session_id) {
                        sessionId = interaction.session_id;
                    }
                    if (workflowId && sessionId) break;
                }
            }

            if (!workflowId || !sessionId) {
                console.log('[HITLManager] No workflow ID or session ID available, skipping session recovery');
                return;
            }

            console.log('[HITLManager] Starting HIE session recovery for workflow:', workflowId, 'session:', sessionId);

            // Use centralized session utility for recovery
            const result = await window.apiUtils.recoverWorkflowSession(sessionId, {
                reason: 'hie_completion'
            });

            if (result.success) {
                console.log('[HITLManager] Session recovered after HIE completion:', result.session_id);
                this.showSuccess('Workflow session recovered');
                return;
            }

            throw new Error('Session recovery failed');

        } catch (error) {
            console.error('[HITLManager] Session recovery failed:', error);
            this.showError('Session recovery issues - workflow operations may be limited');

            // Fallback: Force page reload if critical session corruption detected
            setTimeout(async () => {
                if (await window.showConfirm('Recovery Needed', 'Workflow session needs recovery. Reload page?', { type: 'danger', confirmText: 'Reload Page' })) {
                    window.location.reload();
                }
            }, 3000);
        }
    }

    /**
     * Generate completion response after successful HITL command execution
     * Since workflow execution stops at HIE interception, we need to generate synthetic completion
     */
    async generateHITLCompletionResponse(executionResult) {
        try {
            console.log('[HITLManager] Generating completion response after successful HITL execution:', executionResult);

            const command = executionResult.command || 'Unknown command';
            const success = executionResult.success !== false;
            const workflowId = executionResult.workflow_id || window.globalState?.currentWorkflow;

            let completionMessage = '';

            if (success) {
                completionMessage = `🎉 **Workflow Completed Successfully!**\n\nThe requested task has been accomplished through the following command execution:\n\n**Executed Command:**\n\`\`\`bash\n${command}\n\`\`\`\n\n**Result:** ✅ Command completed successfully\n\nThe workflow has finished processing your request. You can now continue with additional queries or start a new workflow.`;
            } else {
                completionMessage = `⚠️ **Workflow Completed with Issues**\n\nThe workflow attempted to execute the following command but encountered problems:\n\n**Executed Command:**\n\`\`\`bash\n${command}\n\`\`\`\n\n**Status:** ❌ Command execution failed\n\nThe workflow has finished processing, but the requested task may not have been fully completed. You can try again with a modified approach or start a new workflow.`;
            }

            // Generate unique message ID
            const messageId = `hitl_completion_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

            // Create completion message
            const message = {
                role: 'assistant',
                content: completionMessage,
                message_id: messageId,
                enhanced_metadata: {
                    workflow_completion: true,
                    hitl_execution: true,
                    execution_result: executionResult,
                    workflow_id: workflowId,
                    timestamp: new Date().toISOString()
                }
            };

            console.log('[HITLManager] Created HITL completion message:', message);

            // Add to chat UI using unified chat renderer
            if (window.unifiedChatRenderer) {
                console.log('[HITLManager] Adding completion message via unifiedChatRenderer');
                window.unifiedChatRenderer.addLiveMessage(message, { source: 'hitl_completion' });
            } else if (window.chatUIManager) {
                console.log('[HITLManager] Adding completion message via chatUIManager');
                window.chatUIManager.addMessage('assistant', completionMessage, 'normal', messageId, message.enhanced_metadata);
            } else {
                console.warn('[HITLManager] No chat renderer available to add HITL completion message');
            }

            // Scroll to bottom to show completion message
            setTimeout(() => {
                const messageContainer = document.getElementById('message-container');
                if (messageContainer) {
                    messageContainer.scrollTop = messageContainer.scrollHeight;
                }
            }, 100);

            // Update status
            if (success) {
                this.showSuccess('Workflow completed successfully');
            } else {
                this.showError('Workflow completed with issues');
            }

        } catch (error) {
            console.error('[HITLManager] Failed to generate HITL completion response:', error);
        }
    }

    /**
     * Queue HIE (Human Input Event) approval and process immediately
     * Triggered when HIE interception happens in chat responses
     */
    queueHIEApproval(hieData) {
        console.log('[HITLManager] Processing HIE approval immediately:', hieData);

        try {
            // Process immediately instead of queuing
            this.showCLICommandApproval({
                command: hieData.command || 'Unknown command',
                workflowId: hieData.workflowId
            });
            console.log('[HITLManager] HIE modal shown successfully');
        } catch (error) {
            console.error('[HITLManager] Error processing HIE approval:', error);
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
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = HumanInTheLoopManager;
}
