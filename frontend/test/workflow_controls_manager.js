/**
 * Workflow Controls Manager - Phase 6: Interactive Workflow Controls
 *
 * Provides UI controls for workflow interaction: pause/resume/stop/step viewing
 * Integrates with WebSocket system for real-time control and status updates
 */

let workflowControlsManagerInitialized = false;

class WorkflowControlsManager {
    constructor() {
        this.controlsContainer = null;
        this.currentWorkflow = null;
        this.workflowState = 'idle'; // idle, running, paused, stopped, error
        this.stepDetails = [];
        this.initializeControlsManager();
    }

    /**
     * Initialize the workflow controls manager
     */
    async initializeControlsManager() {
        console.log('[WorkflowControlsManager] Initializing workflow controls manager...');

        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setupUI());
        } else {
            this.setupUI();
        }
    }

    /**
     * Setup workflow controls UI
     */
    setupUI() {
        console.log('[WorkflowControlsManager] Setting up workflow controls UI...');

        // Create controls container
        this.createControlsContainer();

        // Setup event listeners for control communication
        this.setupEventListeners();

        workflowControlsManagerInitialized = true;
        console.log('[WorkflowControlsManager] Workflow controls manager initialized');

        // Listen for workflow state changes
        window.addEventListener('workflow-state-changed', (event) => {
            this.updateWorkflowState(event.detail);
        });
    }

    /**
     * Create workflow controls container
     */
    createControlsContainer() {
        // Check if container already exists
        if (document.getElementById('workflow-controls-container')) {
            return;
        }

        const container = document.createElement('div');
        container.id = 'workflow-controls-container';
        container.className = 'workflow-controls-container';
        container.innerHTML = '';

        // Insert into chat interface
        const chatInterface = document.getElementById('chat-interface') ||
                             document.querySelector('.main-content') ||
                             document.body;

        // Position it above the input area
        const inputArea = chatInterface.querySelector('.input-area');
        if (inputArea) {
            chatInterface.insertBefore(container, inputArea);
        } else {
            chatInterface.appendChild(container);
        }

        // Add CSS styles
        this.addControlsStyles();

        console.log('[WorkflowControlsManager] Workflow controls container created');
    }

    /**
     * Add CSS styles for workflow controls
     */
    addControlsStyles() {
        const style = document.createElement('style');
        style.textContent = `
            /* Workflow Controls Container */
            .workflow-controls-container {
                position: relative;
                width: 100%;
                max-width: 800px;
                margin: 0 auto;
                padding: 0.75rem 1rem;
                background: #ffffff;
                border-top: 1px solid #e5e7eb;
                display: none; /* Hidden by default */
                transition: all 0.3s ease;
            }

            .workflow-controls-container.visible {
                display: block;
            }

            /* Controls Header */
            .controls-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 0.75rem;
            }

            .controls-title {
                font-size: 0.875rem;
                font-weight: 600;
                color: #374151;
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }

            .workflow-status-indicator {
                width: 0.5rem;
                height: 0.5rem;
                border-radius: 50%;
                background: #6b7280;
                transition: all 0.3s ease;
            }

            .workflow-status-indicator.running {
                background: #10b981;
                box-shadow: 0 0 6px rgba(16, 185, 129, 0.4);
            }

            .workflow-status-indicator.paused {
                background: #f59e0b;
                box-shadow: 0 0 6px rgba(245, 158, 11, 0.4);
            }

            .workflow-status-indicator.stopped {
                background: #ef4444;
            }

            .workflow-status-indicator.error {
                background: #ef4444;
                box-shadow: 0 0 6px rgba(239, 68, 68, 0.4);
            }

            /* Control Buttons */
            .control-buttons {
                display: flex;
                gap: 0.5rem;
                align-items: center;
            }

            .control-btn {
                padding: 0.375rem 0.75rem;
                border: 1px solid #d1d5db;
                border-radius: 0.375rem;
                background: white;
                color: #374151;
                font-size: 0.75rem;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s ease;
                display: flex;
                align-items: center;
                gap: 0.25rem;
            }

            .control-btn:hover {
                background: #f9fafb;
                border-color: #9ca3af;
            }

            .control-btn:active {
                transform: translateY(1px);
            }

            .control-btn:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }

            .control-btn.primary {
                background: #3b82f6;
                color: white;
                border-color: #3b82f6;
            }

            .control-btn.primary:hover {
                background: #2563eb;
                border-color: #2563eb;
            }

            .control-btn.danger {
                background: #ef4444;
                color: white;
                border-color: #ef4444;
            }

            .control-btn.danger:hover {
                background: #dc2626;
                border-color: #dc2626;
            }

            /* Progress Section */
            .controls-progress {
                margin-bottom: 0.75rem;
            }

            .progress-bar-container {
                width: 100%;
                height: 6px;
                background: #e5e7eb;
                border-radius: 3px;
                overflow: hidden;
                margin-bottom: 0.25rem;
            }

            .progress-bar-fill {
                height: 100%;
                background: linear-gradient(90deg, #3b82f6, #60a5fa);
                border-radius: 3px;
                transition: width 0.3s ease;
                width: 0%;
            }

            .progress-text {
                font-size: 0.75rem;
                color: #6b7280;
                text-align: center;
            }

            /* Steps Section */
            .controls-steps {
                border-top: 1px solid #e5e7eb;
                padding-top: 0.75rem;
            }

            .steps-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 0.5rem;
            }

            .steps-title {
                font-size: 0.75rem;
                font-weight: 600;
                color: #374151;
            }

            .steps-toggle {
                font-size: 0.75rem;
                color: #6b7280;
                cursor: pointer;
                user-select: none;
            }

            .steps-list {
                max-height: 0;
                overflow: hidden;
                transition: max-height 0.3s ease;
            }

            .steps-list.expanded {
                max-height: 200px;
                overflow-y: auto;
            }

            .step-item {
                display: flex;
                align-items: center;
                gap: 0.5rem;
                padding: 0.375rem 0;
                border-bottom: 1px solid #f3f4f6;
            }

            .step-item:last-child {
                border-bottom: none;
            }

            .step-indicator {
                width: 0.5rem;
                height: 0.5rem;
                border-radius: 50%;
                background: #d1d5db;
                flex-shrink: 0;
            }

            .step-indicator.completed {
                background: #10b981;
            }

            .step-indicator.current {
                background: #3b82f6;
                box-shadow: 0 0 4px rgba(59, 130, 246, 0.4);
            }

            .step-indicator.pending {
                background: #d1d5db;
            }

            .step-content {
                flex: 1;
                font-size: 0.75rem;
            }

            .step-name {
                font-weight: 500;
                color: #374151;
            }

            .step-description {
                color: #6b7280;
                font-size: 0.6875rem;
                margin-top: 0.125rem;
            }

            .step-time {
                font-size: 0.6875rem;
                color: #9ca3af;
            }

            /* Responsive Design */
            @media (max-width: 640px) {
                .control-buttons {
                    flex-wrap: wrap;
                }

                .control-btn {
                    padding: 0.25rem 0.5rem;
                    font-size: 0.6875rem;
                }

                .controls-header {
                    flex-direction: column;
                    align-items: flex-start;
                    gap: 0.5rem;
                }
            }
        `;

        document.head.appendChild(style);
    }

    /**
     * Setup event listeners for workflow control communication
     * Uses EventDispatcher instead of direct WebSocket connections
     */
    setupEventListeners() {
        console.log('[WorkflowControlsManager] Setting up event listeners via EventDispatcher');

        // Register with EventDispatcher for workflow control events
        if (window.getEventDispatcher) {
            const dispatcher = window.getEventDispatcher();
            dispatcher.registerHandler('workflow_control_ack_event', this);
            dispatcher.registerHandler('workflow_progress_event', this);
            dispatcher.registerHandler('workflow_step_event', this);
            console.log('[WorkflowControlsManager] Registered with EventDispatcher');
        } else {
            console.warn('[WorkflowControlsManager] EventDispatcher not available');
        }
    }

    /**
     * Handle events through EventDispatcher interface
     */
    handleEvent(eventType, data, workflowId) {
        console.log(`[WorkflowControlsManager] Handling ${eventType} event`);

        try {
            switch (eventType) {
                case 'workflow_control_ack_event':
                    this.handleControlAcknowledgment(data);
                    break;
                case 'workflow_progress_event':
                    this.updateProgress(data);
                    break;
                case 'workflow_step_event':
                    this.updateStepInfo(data);
                    break;
                default:
                    console.warn(`[WorkflowControlsManager] Unknown event type: ${eventType}`);
            }
        } catch (error) {
            console.error(`[WorkflowControlsManager] Error handling ${eventType}:`, error);
        }
    }

    /**
     * Show workflow controls for active workflow
     */
    showWorkflowControls(workflowId, initialState = 'running') {
        this.currentWorkflow = workflowId;
        this.workflowState = initialState;

        const container = document.getElementById('workflow-controls-container');
        if (!container) return;

        // Update container content
        container.innerHTML = this.generateControlsHTML();
        container.classList.add('visible');

        // Setup event listeners
        this.attachControlEventListeners();

        console.log(`[WorkflowControlsManager] Showing controls for workflow: ${workflowId}`);
    }

    /**
     * Hide workflow controls
     */
    hideWorkflowControls() {
        const container = document.getElementById('workflow-controls-container');
        if (container) {
            container.classList.remove('visible');
        }
        this.currentWorkflow = null;
        this.workflowState = 'idle';
        this.stepDetails = [];
    }

    /**
     * Generate HTML for workflow controls
     */
    generateControlsHTML() {
        const stateLabels = {
            idle: 'Idle',
            running: 'Running',
            paused: 'Paused',
            stopped: 'Stopped',
            error: 'Error'
        };

        const statusClass = this.workflowState.toLowerCase();

        return `
            <div class="controls-header">
                <div class="controls-title">
                    <div class="workflow-status-indicator ${statusClass}"></div>
                    Workflow Controls
                    <span style="font-weight: normal; color: #6b7280;">•</span>
                    <span style="font-weight: normal; color: #6b7280;">${stateLabels[this.workflowState] || 'Unknown'}</span>
                </div>
                <div class="control-buttons">
                    ${this.generateControlButtons()}
                </div>
            </div>

            <div class="controls-progress">
                <div class="progress-bar-container">
                    <div class="progress-bar-fill" id="workflow-progress-fill"></div>
                </div>
                <div class="progress-text" id="workflow-progress-text">Initializing...</div>
            </div>

            <div class="controls-steps">
                <div class="steps-header">
                    <div class="steps-title">Execution Steps</div>
                    <div class="steps-toggle" onclick="window.workflowControlsManager?.toggleStepsView()">
                        ${this.stepsExpanded ? '▼' : '▶'} Show Details
                    </div>
                </div>
                <div class="steps-list ${this.stepsExpanded ? 'expanded' : ''}" id="steps-list">
                    ${this.generateStepsHTML()}
                </div>
            </div>
        `;
    }

    /**
     * Generate control buttons based on current state
     */
    generateControlButtons() {
        const buttons = [];

        switch (this.workflowState) {
            case 'running':
                buttons.push(
                    `<button class="control-btn" onclick="window.workflowControlsManager?.pauseWorkflow()">
                        ⏸️ Pause
                    </button>`
                );
                buttons.push(
                    `<button class="control-btn danger" onclick="window.workflowControlsManager?.stopWorkflow()">
                        ⏹️ Stop
                    </button>`
                );
                break;

            case 'paused':
                buttons.push(
                    `<button class="control-btn primary" onclick="window.workflowControlsManager?.resumeWorkflow()">
                        ▶️ Resume
                    </button>`
                );
                buttons.push(
                    `<button class="control-btn danger" onclick="window.workflowControlsManager?.stopWorkflow()">
                        ⏹️ Stop
                    </button>`
                );
                break;

            case 'stopped':
            case 'error':
                buttons.push(
                    `<button class="control-btn primary" onclick="window.workflowControlsManager?.restartWorkflow()">
                        🔄 Restart
                    </button>`
                );
                break;

            default:
                // No buttons for idle state
                break;
        }

        return buttons.join('');
    }

    /**
     * Generate HTML for execution steps
     */
    generateStepsHTML() {
        if (!this.stepDetails || this.stepDetails.length === 0) {
            return `
                <div class="step-item">
                    <div class="step-indicator pending"></div>
                    <div class="step-content">
                        <div class="step-name">Initializing workflow...</div>
                        <div class="step-description">Preparing execution environment</div>
                    </div>
                </div>
            `;
        }

        return this.stepDetails.map((step, index) => {
            const statusClass = step.status || 'pending';
            const isCurrent = step.isCurrent ? 'current' : statusClass;

            return `
                <div class="step-item">
                    <div class="step-indicator ${isCurrent}"></div>
                    <div class="step-content">
                        <div class="step-name">${step.name || `Step ${index + 1}`}</div>
                        <div class="step-description">${step.description || 'Executing...'}</div>
                        ${step.duration ? `<div class="step-time">${step.duration}ms</div>` : ''}
                    </div>
                </div>
            `;
        }).join('');
    }

    /**
     * Attach event listeners to control buttons
     */
    attachControlEventListeners() {
        // Event listeners are attached via onclick attributes in HTML
        // This method can be used for additional dynamic listeners if needed
    }

    /**
     * Update workflow state
     */
    updateWorkflowState(stateData) {
        const { state, workflowId } = stateData;

        if (workflowId !== this.currentWorkflow) return;

        this.workflowState = state;
        this.updateControlsDisplay();

        console.log(`[WorkflowControlsManager] Workflow state updated: ${state}`);
    }

    /**
     * Update controls display
     */
    updateControlsDisplay() {
        const container = document.getElementById('workflow-controls-container');
        if (!container) return;

        // Update status indicator
        const indicator = container.querySelector('.workflow-status-indicator');
        if (indicator) {
            indicator.className = `workflow-status-indicator ${this.workflowState.toLowerCase()}`;
        }

        // Update control buttons
        const buttonsContainer = container.querySelector('.control-buttons');
        if (buttonsContainer) {
            buttonsContainer.innerHTML = this.generateControlButtons();
        }
    }

    /**
     * Update progress information
     */
    updateProgress(progressData) {
        const { progress, stage, message } = progressData;

        // Update progress bar
        const progressFill = document.getElementById('workflow-progress-fill');
        if (progressFill) {
            progressFill.style.width = `${Math.min(100, Math.max(0, progress || 0))}%`;
        }

        // Update progress text
        const progressText = document.getElementById('workflow-progress-text');
        if (progressText) {
            progressText.textContent = message || `${stage || 'Processing'}... ${progress || 0}%`;
        }
    }

    /**
     * Update step information
     */
    updateStepInfo(stepData) {
        const { stepId, name, description, status, duration } = stepData;

        // Update or add step
        const existingStepIndex = this.stepDetails.findIndex(s => s.id === stepId);
        const stepInfo = {
            id: stepId,
            name: name || `Step ${stepId}`,
            description: description || 'Executing...',
            status: status || 'pending',
            duration: duration,
            isCurrent: status === 'running'
        };

        if (existingStepIndex >= 0) {
            this.stepDetails[existingStepIndex] = stepInfo;
        } else {
            this.stepDetails.push(stepInfo);
        }

        // Update steps display
        const stepsList = document.getElementById('steps-list');
        if (stepsList) {
            stepsList.innerHTML = this.generateStepsHTML();
        }
    }

    /**
     * Handle control command acknowledgment
     */
    handleControlAcknowledgment(ackData) {
        const { command, status } = ackData;

        if (status === 'acknowledged') {
            console.log(`[WorkflowControlsManager] Control command acknowledged: ${command}`);

            // Update local state based on command
            switch (command) {
                case 'pause':
                    this.workflowState = 'paused';
                    break;
                case 'resume':
                    this.workflowState = 'running';
                    break;
                case 'stop':
                    this.workflowState = 'stopped';
                    break;
            }

            this.updateControlsDisplay();
        }
    }

    // Control Actions

    /**
     * Send workflow control command through EventDispatcher
     */
    async sendWorkflowControlCommand(command) {
        console.log(`[WorkflowControlsManager] Sending ${command} command`);

        if (window.getEventDispatcher) {
            const dispatcher = window.getEventDispatcher();

            // Send command through EventDispatcher (backend will handle it)
            // Commands are sent to backend via existing WebSocket connections
            const success = dispatcher.dispatchEvent('workflow_control_command', {
                command: command,
                workflow_id: this.currentWorkflow,
                timestamp: new Date().toISOString()
            }, this.currentWorkflow);

            if (!success) {
                console.error(`[WorkflowControlsManager] Failed to dispatch ${command} command`);
                this.showError(`Failed to ${command} workflow`);
            }
        } else {
            console.error('[WorkflowControlsManager] EventDispatcher not available');
            this.showError('Workflow control system unavailable');
        }
    }

    /**
     * Pause workflow execution
     */
    async pauseWorkflow() {
        await this.sendWorkflowControlCommand('pause');
    }

    /**
     * Resume workflow execution
     */
    async resumeWorkflow() {
        await this.sendWorkflowControlCommand('resume');
    }

    /**
     * Stop workflow execution
     */
    async stopWorkflow() {
        await this.sendWorkflowControlCommand('stop');
    }

    /**
     * Restart workflow execution
     */
    async restartWorkflow() {
        console.log('[WorkflowControlsManager] Sending restart command');

        // For restart, we need to trigger a new workflow execution
        // This would typically involve calling the chat API again
        if (window.chatUIManager) {
            // Get the last message and resend it
            const lastMessage = window.chatUIManager.getLastUserMessage();
            if (lastMessage) {
                window.chatUIManager.sendMessage(lastMessage);
                this.workflowState = 'running';
                this.updateControlsDisplay();
            }
        }
    }

    /**
     * Toggle steps view expansion
     */
    toggleStepsView() {
        this.stepsExpanded = !this.stepsExpanded;

        const stepsList = document.getElementById('steps-list');
        const toggleBtn = document.querySelector('.steps-toggle');

        if (stepsList) {
            stepsList.classList.toggle('expanded', this.stepsExpanded);
        }

        if (toggleBtn) {
            toggleBtn.innerHTML = `${this.stepsExpanded ? '▼' : '▶'} ${this.stepsExpanded ? 'Hide' : 'Show'} Details`;
        }
    }

    /**
     * Show error message
     */
    showError(message) {
        console.error('[WorkflowControlsManager] Error:', message);
        if (window.updateStatus) {
            window.updateStatus(message, 'error');
        }
    }

    /**
     * Show success message
     */
    showSuccess(message) {
        console.log('[WorkflowControlsManager] Success:', message);
        if (window.updateStatus) {
            window.updateStatus(message, 'success');
        }
    }

    /**
     * Check if controls are visible
     */
    isControlsVisible() {
        const container = document.getElementById('workflow-controls-container');
        return container && container.classList.contains('visible');
    }

    /**
     * Get current workflow state
     */
    getCurrentWorkflowState() {
        return {
            workflowId: this.currentWorkflow,
            state: this.workflowState,
            stepCount: this.stepDetails.length,
            stepsExpanded: this.stepsExpanded
        };
    }
}

// Initialize Workflow Controls Manager
document.addEventListener('DOMContentLoaded', () => {
    window.workflowControlsManager = new WorkflowControlsManager();
    console.log('[WorkflowControlsManager] Workflow controls manager module loaded');
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WorkflowControlsManager;
}
