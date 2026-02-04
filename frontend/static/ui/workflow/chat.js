/**
 * Chat UI Manager - Frontend Modularization
 *
 * Handles chat functionality, message handling, and UI enhancements for live conversations.
 * Integrates with WorkflowSession for proper session management and WebSocket communication.
 * Separated from monolithic script.js for better maintainability and testability.
 *
 * Architecture:
 * - Uses WorkflowSession class for session lifecycle and WebSocket management
 * - Focuses on UI rendering, user interaction, and event handling
 * - Delegates session management and backend communication to WorkflowSession
 * - Supports rich text rendering, artifact display, and workflow progress tracking
 */
let chatUIEnhancements = null;

// Core Chat UI Manager Class
class ChatUIManager {
    constructor() {
        // Phase 3: Use WorkflowSession for session management
        this.workflowSession = null;  // WorkflowSession instance

        this.initializeChatElements();
        this.initializeEventListeners();
        this.setupTypingIndicator();
        this.registerWithEventDispatcher();
    }

    /**
     * Register with EventDispatcher for chat events
     */
    registerWithEventDispatcher() {
        if (window.getEventDispatcher) {
            const dispatcher = window.getEventDispatcher();

            // Register chat and error events
            dispatcher.registerHandler('chat_response_event', this);
            dispatcher.registerHandler('error_event', this);
        } else {
            console.warn('[ChatUIManager] EventDispatcher not available - using legacy WebSocket handling');
        }
    }

    /**
     * Initialize chat DOM elements
     */
    initializeChatElements() {
        this.messageContainer = document.getElementById('message-container');
        this.userInput = document.getElementById('user-input');
        this.sendButton = document.getElementById('send-button');
    }

    /**
     * Initialize chat event listeners
     */
    initializeEventListeners() {
        if (this.sendButton) {
            this.sendButton.addEventListener('click', () => this.sendMessage());
        }

        if (this.userInput) {
            this.userInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.sendMessage();
                }
            });
        }
    }

    /**
     * Setup typing indicator infrastructure
     */
    setupTypingIndicator() {
        // Create typing indicator element
        this.typingIndicator = document.createElement('div');
        this.typingIndicator.className = 'message ai-message typing-indicator';
        this.typingIndicator.innerHTML = `
            <div class="message-sender">AI</div>
            <div class="message-content">
                <div class="typing-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        `;

        // Typing indicator state
        this.isTyping = false;
        this.currentTypingIndicator = null;
    }

    /**
     * Show typing indicator in chat
     */
    showTypingIndicator() {
        if (this.isTyping || !this.messageContainer) return;

        this.isTyping = true;
        this.currentTypingIndicator = this.typingIndicator.cloneNode(true);
        this.messageContainer.appendChild(this.currentTypingIndicator);
        this.messageContainer.scrollTop = this.messageContainer.scrollHeight;
        return this.currentTypingIndicator;
    }

    /**
     * Add message to chat interface
     */
    addMessage(sender, content, messageType = 'normal', messageId = null, enhancedMetadata = null) {
        if (!this.messageContainer) {
            console.warn('[ChatUIManager] Message container not found, cannot add message. Current view:', window.currentView);
            return;
        }

        const messageElement = document.createElement('div');
        messageElement.classList.add('message');

        // Store message_id if provided for artifact filtering
        if (messageId) {
            messageElement.setAttribute('data-message-id', messageId);
        }

        // Determine message class based on sender and type
        if (messageType === 'system') {
            messageElement.classList.add('system-message');
        } else if (messageType === 'error') {
            messageElement.classList.add('error-message');
        } else {
            messageElement.classList.add(sender === 'user' ? 'user-message' : 'ai-message');
        }

        const senderElement = document.createElement('div');
        senderElement.classList.add('message-sender');

        // Set sender text based on type and sender
        if (messageType === 'system') {
            senderElement.textContent = 'System';
        } else if (messageType === 'error') {
            senderElement.textContent = 'Error';
        } else {
            senderElement.textContent = sender === 'user' ? 'You' : 'AI';
        }

        const contentElement = document.createElement('div');
        contentElement.classList.add('message-content');

        // Add model info for AI messages if available
        if (sender === 'ai' && enhancedMetadata && enhancedMetadata.model_id) {
            const modelInfo = document.createElement('div');
            modelInfo.className = 'message-model-info';
            const provider = enhancedMetadata.model_provider || 'AI';
            modelInfo.textContent = `${provider}: ${enhancedMetadata.model_id}`;
            contentElement.appendChild(modelInfo);
        }

        // Phase 5.8: Use rich text renderer for enhanced message display
        if (window.richTextRenderer && messageType !== 'system') {
            // Prepare metadata for enhanced rendering
            let metadata = {};

            // 🔧 USE REAL ENHANCED METADATA from API response instead of configuration
            if (enhancedMetadata && Object.keys(enhancedMetadata).length > 0) {
                // 🔧 FIX: Handle the async renderMessage call properly without making addMessage async
                window.richTextRenderer.renderMessage(content, metadata).then(formattedContent => {
                    contentElement.innerHTML = formattedContent;
                }).catch(error => {
                    console.error('[ChatUIManager] ❌ Rich text rendering failed:', error);
                    contentElement.innerHTML = content.replace(/\n/g, '<br>'); // Fallback
                });

                // Set placeholder content initially
                contentElement.innerHTML = content.replace(/\n/g, '<br>');
            } else {
                // Fallback: Convert line breaks to <br> tags for plain text
                contentElement.innerHTML = content.replace(/\n/g, '<br>');
            }
        } else {
            // Fallback for system messages or if richTextRenderer is not available
            contentElement.innerHTML = content.replace(/\n/g, '<br>');
        }

        messageElement.appendChild(senderElement);
        messageElement.appendChild(contentElement);
        this.messageContainer.appendChild(messageElement);

        // Apply UI enhancements if available
        if (chatUIEnhancements && chatUIEnhancements.enhanceMessageElement) {
            chatUIEnhancements.enhanceMessageElement(messageElement);
        }

        this.messageContainer.scrollTop = this.messageContainer.scrollHeight;
    }

    /**
     * Clear all messages from chat
     */
    clearMessages() {
        if (this.messageContainer) {
            this.messageContainer.innerHTML = '';
        }
    }

    /**
     * Send message using WorkflowSession architecture
     * Creates session on first message if needed, then uses WorkflowSession for messaging
     */
    async sendMessage() {
        if (!this.userInput) {
            return;
        }

        // Validate workflow context
        if (!window.globalState.currentWorkflow) {
            this.addMessage('system', '❌ No active workflow session. Please select a workflow first.', 'system');
            return;
        }

        const message = this.userInput.value.trim();
        if (!message) return;

        const workflowId = window.globalState.currentWorkflow;
        window.updateStatus && window.updateStatus(`Connecting to ${workflowId}...`, 'in-progress');

        // Add user message to UI immediately for responsive UX
        const userMessage = {
            role: 'user',
            content: message,
            timestamp: new Date().toISOString()
        };
        if (window.unifiedChatRenderer) {
            window.unifiedChatRenderer.addLiveMessage(userMessage, { source: 'user_input' });
        } else {
            this.addMessage('user', message);
        }
        this.userInput.value = '';

        try {
            // Phase 3: Use WorkflowSession for messaging
            await this.sendMessageViaWorkflowSession(message);

        } catch (error) {
            console.error(`[ChatUIManager] ❌ Message sending failed:`, error);
            this.addMessage('ai', `<p style="color: red;">Error: ${error.message}</p>`);

            // Fallback to HTTP if WorkflowSession fails
            await this.fallbackToHttpRequest(message);

            window.updateStatus && window.updateStatus('Error sending message.', 'error');
        }
    }

    /**
     * Send message via WebSocket infrastructure session
     * Uses WebSocket for real-time progressive event streaming
     */
    async sendMessageViaWorkflowSession(message) {
        const workflowId = window.globalState.currentWorkflow;
        const infrastructureSessionId = window.sessionManager.getInfrastructureSession(workflowId);

        if (!infrastructureSessionId) {
            throw new Error('No infrastructure session available for messaging');
        }

        return new Promise((resolve, reject) => {
            try {
                // Create WebSocket connection for workflow execution
                const wsUrl = `/api/workflow/${infrastructureSessionId}/stream`;
                const websocket = new WebSocket(wsUrl);

                websocket.onopen = () => {
                    // Send the chat request
                    const messageData = {
                        type: 'chat_request',
                        data: {
                            question: message,
                            session_id: infrastructureSessionId
                        }
                    };

                    websocket.send(JSON.stringify(messageData));

                    // Initialize workflow progress display
                    this.initializeWorkflowProgressManager();
                };

                websocket.onmessage = (event) => {
                    try {
                        const message = JSON.parse(event.data);

                        // Route message through EventDispatcher
                        if (window.getEventDispatcher) {
                            const dispatcher = window.getEventDispatcher();
                            dispatcher.dispatchEvent(message.type, message.data || {}, workflowId);
                        } else {
                            // Fallback: handle directly
                            this.handleWebSocketMessage(message, workflowId);
                        }

                        // Check if this is the final response
                        if (message.type === 'chat_response_event' || message.type === 'error_event') {
                            websocket.close(1000, 'Workflow completed');
                            resolve(message.data);
                        }

                    } catch (error) {
                        console.error(`[ChatUIManager] Error processing WebSocket message:`, error);
                    }
                };

                websocket.onerror = (error) => {
                    console.error(`[ChatUIManager] WebSocket error:`, error);
                    reject(new Error('WebSocket connection failed'));
                };

                websocket.onclose = (event) => {
                    if (event.code !== 1000) { // Not a normal closure
                        reject(new Error(`WebSocket closed unexpectedly: ${event.code} ${event.reason}`));
                    }
                };

                // Timeout after 5 minutes
                setTimeout(() => {
                    if (websocket.readyState === WebSocket.OPEN) {
                        console.warn(`[ChatUIManager] WebSocket timeout after 5 minutes, closing`);
                        websocket.close(1000, 'Timeout');
                        reject(new Error('WebSocket timeout'));
                    }
                }, 300000); // 5 minutes

            } catch (error) {
                console.error(`[ChatUIManager] Failed to establish WebSocket connection:`, error);
                reject(error);
            }
        });
    }

    /**
     * Handle WebSocket messages directly (fallback when EventDispatcher not available)
     */
    handleWebSocketMessage(message, workflowId) {
        switch (message.type) {
            case 'progressive_event':
                // Forward to ArtifactDisplayManager
                if (window.artifactDisplayManager && window.artifactDisplayManager.handleEvent) {
                    window.artifactDisplayManager.handleEvent('progressive_event', message.data, workflowId);
                }
                break;

            case 'hie_command_event':
            case 'hie_text_event':
            case 'hie_confirm_event':
            case 'hie_feedback_event':
                // Forward to HumanInTheLoopManager
                if (window.hitlManager && window.hitlManager.handleEvent) {
                    window.hitlManager.handleEvent(message.type, message.data, workflowId);
                }
                break;

            case 'artifact_event':
                // Forward to ArtifactDisplayManager
                if (window.artifactDisplayManager && window.artifactDisplayManager.handleEvent) {
                    window.artifactDisplayManager.handleEvent('artifact_event', message.data, workflowId);
                }
                break;

            case 'chat_response_event':
                this.handleChatResponse(message.data);
                break;

            case 'error_event':
                this.handleError(message.data);
                break;

            default:
                console.warn(`[ChatUIManager] Unknown WebSocket message type: ${message.type}`);
        }
    }

    /**
     * Handle chat-specific events through EventDispatcher interface
     */
    handleEvent(eventType, data, workflowId) {
        try {
            switch (eventType) {
                case 'chat_response_event':
                    this.handleChatResponse(data);
                    break;

                case 'error_event':
                    this.handleError(data);
                    break;

                // Forward HIE events to HumanInTheLoopManager
                case 'hie_command_event':
                case 'hie_text_event':
                case 'hie_confirm_event':
                case 'hie_feedback_event':
                    this.handleHIEEvent(eventType, data, workflowId);
                    break;

                default:
                    console.warn(`[ChatUIManager] Unknown event type: ${eventType}`);
                    break;
            }
        } catch (error) {
            console.error(`[ChatUIManager] Error handling ${eventType}:`, error);
        }
    }

    /**
     * Initialize workflow progress manager for real-time display
     */
    initializeWorkflowProgressManager() {
        // Initialize workflow progress manager for live progress
        if (!window.workflowProgressManager) {
            console.warn('[ChatUIManager] WorkflowProgressManager not available - progress display will be limited');
            return;
        }

        try {
            // Start workflow progress display
            window.workflowProgressManager.showWorkflowProgress(window.globalState.currentWorkflow);
        } catch (error) {
            console.error('[ChatUIManager] Failed to initialize workflow progress:', error);
        }
    }

    /**
     * Handle UI events with complete rendering instructions from backend
     * Support for message-driven nested panel actions
     */
    handleUIEvent(eventData) {
        // Wrap in try/catch to prevent UI rendering errors from breaking workflow
        try {
            switch (eventData.action) {
                case 'create_panel':
                    this.createProgressivePanel(eventData);
                    break;
                case 'create_nested':
                    // PHASE 5: Create nested panel structure
                    this.createNestedPanel(eventData.panel_id, eventData.status, eventData.message);
                    break;
                case 'update_panel':
                    this.updateProgressivePanel(eventData.panel_id, eventData.status);
                    break;
                case 'update_nested':
                    // PHASE 5: Update nested sub-panel
                    this.updateNestedPanel(eventData.panel_id, eventData.status, eventData.message);
                    break;
                default:
                    console.warn('[ChatUIManager] Unknown UI action:', eventData.action);
            }

            // Update status message for user feedback
            this.updateStatusFromUIEvent(eventData);
        } catch (uiEventError) {
            console.error('[ChatUIManager] ❌ UI event handling error (non-fatal):', uiEventError);
            // Don't re-throw - UI errors shouldn't break workflow execution
            // Status update might still be useful
            window.updateStatus && window.updateStatus(
                `Workflow running... (UI update failed)`, 'in-progress'
            );
        }
    }

    /**
     * Create a progressive panel in the artifact panel as a tab
     */
    createProgressivePanel(eventData) {
        // Use artifact display manager to show progress in artifact panel
        // FIX: Use message from backend event data (now provides meaningful defaults)
        if (window.artifactDisplayManager && window.artifactDisplayManager.showWorkflowProgress) {
            const message = eventData.message || `${eventData.panel_id.charAt(0).toUpperCase() + eventData.panel_id.slice(1)} in progress...`;
            try {
                window.artifactDisplayManager.showWorkflowProgress('create_panel', eventData.panel_id, eventData.status, message);
            } catch (error) {
                console.error(`[ChatUIManager] ❌ Error in createProgressivePanel:`, error);
                // Fallback: Try direct property access if it's an object
                if (window.artifactDisplayManager.showWorkflowProgress.create_panel) {
                    window.artifactDisplayManager.showWorkflowProgress.create_panel(eventData.panel_id, eventData.status, message);
                }
            }
        } else {
            console.warn(`[ChatUIManager] ❌ artifactDisplayManager.showWorkflowProgress not available`);
        }
    }

    /**
     * Create nested panel structure
     */
    createNestedPanel(panelId, status, message) {
        // Use artifact display manager with new signature
        if (window.artifactDisplayManager && window.artifactDisplayManager.showWorkflowProgress) {
            try {
                window.artifactDisplayManager.showWorkflowProgress('create_nested', panelId, status, message);
            } catch (error) {
                console.error(`[ChatUIManager] ❌ Error in createNestedPanel:`, error);
                // Fallback: Try direct property access if it's an object
                if (window.artifactDisplayManager.showWorkflowProgress.create_nested) {
                    window.artifactDisplayManager.showWorkflowProgress.create_nested(panelId, status, message);
                }
            }
        } else {
            console.warn(`[ChatUIManager] ❌ artifactDisplayManager.showWorkflowProgress not available`);
        }
    }

    /**
     * Update nested sub-panel
     */
    updateNestedPanel(panelId, status, message) {
        // Use artifact display manager with new signature
        if (window.artifactDisplayManager && window.artifactDisplayManager.showWorkflowProgress) {
            try {
                window.artifactDisplayManager.showWorkflowProgress('update_nested', panelId, status, message);
            } catch (error) {
                console.error(`[ChatUIManager] ❌ Error in updateNestedPanel:`, error);
                // Fallback: Try direct property access if it's an object
                if (window.artifactDisplayManager.showWorkflowProgress.update_nested) {
                    window.artifactDisplayManager.showWorkflowProgress.update_nested(panelId, status, message);
                }
            }
        } else {
            console.warn(`[ChatUIManager] ❌ artifactDisplayManager.showWorkflowProgress not available`);
        }
    }

    /**
     * Update an existing progressive panel status
     */
    updateProgressivePanel(panelId, status) {
        const panel = document.getElementById(`${panelId}-panel`);
        if (panel) {
            const statusDiv = panel.querySelector('.status');
            if (statusDiv) {
                statusDiv.innerHTML = this.getStatusDisplay(status);

                // Add complete class for styling
                if (status === 'complete') {
                    panel.classList.add('complete');
                }
            }
        }
    }

    /**
     * Get HTML display for status
     */
    getStatusDisplay(status) {
        switch (status) {
            case 'inprogress':
                return '<div class="spinner"></div><span>In Progress</span>';
            case 'complete':
                return '<span class="checkmark">✓</span><span>Complete</span>';
            case 'pending':
                return '<span>Pending</span>';
            default:
                return `<span>${status || 'Unknown'}</span>`;
        }
    }

    /**
     * Update status message based on UI event
     */
    updateStatusFromUIEvent(eventData) {
        const statusMessages = {
            'create_panel': `Starting ${eventData.title || 'workflow phase'}...`,
            'update_panel': eventData.status === 'complete' ? `${eventData.title || 'Phase'} completed` : `Working on ${eventData.title || 'phase'}...`,
            'add_question': 'Researching question...',
            'update_question': 'Question answered'
        };

        const message = statusMessages[eventData.action];
        if (message) {
            const statusType = eventData.status === 'complete' ? 'success' : 'in-progress';
            window.updateStatus && window.updateStatus(message, statusType);
        }
    }

    /**
     * Handle final chat response from backend
     */
    handleChatResponse(chatData) {
        this.cleanupWorkflowProgress();

        // 🚨 HIE INTERCEPTION CHECK: Check if workflow was paused for human input
        if (chatData.enhanced_metadata && chatData.enhanced_metadata.HIE_intercepted) {
            // Defer HIE processing to ensure all modules are loaded
            setTimeout(() => {
                this.processHIEApproval(chatData.enhanced_metadata);
            }, 100);
            return;
        }

        // 🔄 SESSION RECOVERY CHECK: Check if workflow completed but session state needs recovery
        if (chatData.workflow_complete || chatData.hie_active === false) {
            // Update status bar to signal completion
            if (window.updateStatus) {
                window.updateStatus('Ready', 'success');
            }

            // Check if session state is consistent after workflow completion
            setTimeout(() => {
                this.checkAndRecoverSessionState();
            }, 1000);
        }

        // Update session ID if new session - this is for WORKFLOW session tracking
        if (chatData.session_id && !window.sessionManager.getInfrastructureSession(window.globalState?.currentWorkflow)) {
            window.sessionManager.setInfrastructureSession(window.globalState?.currentWorkflow, chatData.session_id);
        }

        // Use message_id from backend response (now properly set)
        let messageId = chatData.message_id;

        // Display the response with artifacts if present
        if (chatData.artifacts && Array.isArray(chatData.artifacts) && chatData.artifacts.length > 0) {
            // Switch artifact panel to results tab when artifacts are received
            if (window.artifactDisplayManager && window.artifactDisplayManager.switchToResultsTab) {
                window.artifactDisplayManager.switchToResultsTab();
            }

            // Use artifact display manager
            if (window.artifactDisplayManager) {
                window.artifactDisplayManager.displayArtifacts(chatData.artifacts);
            }

            // Add response with artifact notification
            const artifactCount = chatData.artifacts.length;
            const enhancedContent = `${chatData.response}<br><br><small><em>📎 ${artifactCount} artifact${artifactCount > 1 ? 's' : ''} generated</em></small>`;
            const message = {
                role: 'ai',
                content: enhancedContent,
                message_id: messageId,
                enhanced_metadata: chatData.enhanced_metadata
            };
            if (window.unifiedChatRenderer) {
                window.unifiedChatRenderer.addLiveMessage(message, { source: 'chat_response' });
            } else {
                this.addMessage('ai', enhancedContent, 'normal', messageId, chatData.enhanced_metadata);
            }
        } else if (chatData.response) {
            // Standard response - pass enhanced metadata for citation rendering
            const message = {
                role: 'ai',
                content: chatData.response,
                message_id: messageId,
                enhanced_metadata: chatData.enhanced_metadata
            };
            if (window.unifiedChatRenderer) {
                window.unifiedChatRenderer.addLiveMessage(message, { source: 'chat_response' });
            } else {
                this.addMessage('ai', chatData.response, 'normal', messageId, chatData.enhanced_metadata);
            }
        }

        window.updateStatus && window.updateStatus('Workflow completed successfully', 'success');
    }

    /**
     * Handle WebSocket error response
     */
    handleError(errorData) {
        console.error('[ChatUIManager] 💥 Backend error:', errorData);
        this.cleanupWorkflowProgress();

        window.updateStatus && window.updateStatus('Workflow execution failed', 'error');

        // Display error message
        this.addMessage('ai', `<p style="color: red;">Error: ${errorData.message || 'Unknown workflow error'}</p>`);
    }

    /**
     * Clean up workflow progress display
     */
    cleanupWorkflowProgress() {
        if (window.workflowProgressManager && window.workflowProgressManager.hideWorkflowProgress) {
            window.workflowProgressManager.hideWorkflowProgress();
        }
    }

    /**
     * Fallback to HTTP POST if WebSocket fails (maintains compatibility)
     */
    async fallbackToHttpRequest(message) {
        try {
            const payload = { question: message };
            // Use WORKFLOW session ID for workflow messaging operations
            const infrastructureSessionId = window.sessionManager.getInfrastructureSession(window.globalState?.currentWorkflow);
            if (infrastructureSessionId) {
                payload.session_id = infrastructureSessionId;
            }

            // ✅ SESSION-CENTRIC: Create session infrastructure using centralized utility
            const sessionData = await window.apiUtils.createWorkflowSession(window.globalState.currentWorkflow);
            const sessionId = sessionData.session_id;

            // Use centralized utility for workflow execution
            const response = await window.apiUtils.executeWorkflow(sessionId, payload);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            // Handle response as in original implementation
            if (data.artifacts && Array.isArray(data.artifacts) && data.artifacts.length > 0) {
                if (window.artifactDisplayManager) {
                    window.artifactDisplayManager.displayArtifacts(data.artifacts);
                }
                const artifactCount = data.artifacts.length;
                const enhancedContent = `${data.response}<br><br><small><em>📎 ${artifactCount} artifact${artifactCount > 1 ? 's' : ''} generated</em></small>`;
                this.addMessage('ai', enhancedContent, 'normal', data.message_id, data.enhanced_metadata);
            } else {
                this.addMessage('ai', data.response || 'No response generated', 'normal', data.message_id, data.enhanced_metadata);
            }

            // Update WORKFLOW session ID if new session created
            if (data.session_id && !window.sessionManager.getInfrastructureSession(window.globalState?.currentWorkflow)) {
                window.sessionManager.setInfrastructureSession(window.globalState?.currentWorkflow, data.session_id);
            }

            window.updateStatus && window.updateStatus(`Message sent to ${window.globalState.currentWorkflow}.`, 'success');

        } catch (error) {
            console.error('[ChatUIManager] HTTP fallback also failed:', error);
            this.addMessage('ai', `<p style="color: red;">Error: ${error.message}</p>`);
            window.updateStatus && window.updateStatus('Error sending message.', 'error');
        }
    }

    /**
     * Show chat interface with optional session resumption
     */
    async showChatInterface(sessionIdToResume = null) {
        // Hide all views and show chat
        const views = ['welcome-page', 'loading-page', 'settings-ui-container', 'config-ui-container', 'chat-history-ui-container'];
        views.forEach(view => {
            const element = document.getElementById(view);
            if (element) element.style.display = 'none';
        });

        const chatInterface = document.getElementById('chat-interface');
        if (chatInterface) {
            chatInterface.style.display = 'flex';

            // Clear messages when switching to chat
            this.clearMessages();
        }

        if (sessionIdToResume) {
            const infrastructureSessionId = window.sessionManager.getInfrastructureSession(window.globalState.currentWorkflow);
            this.addMessage('system', `Resumed chat with ${window.globalState.currentWorkflow} workflow (Session: ${infrastructureSessionId?.substring(0, 8) || 'none'})`, 'system');
        } else {
            // ❌ ARCHITECTURAL VIOLATION: showChatInterface called without server session
            console.error('[ChatUIManager] 🏗️ CONTRACT VIOLATION: showChatInterface() called without server-provided session ID');
            this.addMessage('system', `❌ Session Error: Please select a workflow from the menu to start chatting.`, 'error');
            return; // Do not continue without proper session
        }

        // Focus input field
        if (this.userInput) {
            setTimeout(() => this.userInput.focus(), 100);
        }
    }

    /**
     * Set chat UI enhancements object
     */
    setUIEnhancements(enhancements) {
        chatUIEnhancements = enhancements;
    }

    /**
     * Set current workflow for chat
     */
    setCurrentWorkflow(workflow) {
        window.globalState.currentWorkflow = workflow;
    }

    /**
     * Get current workflow
     */
    getCurrentWorkflow() {
        return window.globalState.currentWorkflow;
    }

    /**
     * Set session context for WebSocket communication
     * sessionData.session_id is a CHAT session ID, not workflow infrastructure ID
     */
    setSessionContext(sessionData, workflowId) {
        // Store session data for WebSocket communication (chat session ID)
        // Treat null as a valid session ID for new conversations
        const oldSessionId = this.sessionData?.session_id;
        this.sessionData = sessionData;
        this.workflowId = workflowId;

        // Clear messages if switching to a new session (even if null)
        if (sessionData?.session_id !== oldSessionId) {
            this.clearMessages();
        }
    }

    /**
     * Get current session data
     */
    getSessionData() {
        return this.sessionData;
    }

    /**
     * Process HIE (Human Input Event) approval - deferred execution with robust retry mechanism
     * Uses polling to wait for HITL manager to be fully initialized
     */
    processHIEApproval(hieMetadata) {
        const hieData = {
            command: hieMetadata.HIE_command || 'Unknown command',
            workflowId: hieMetadata.workflow_id
        };

        // Robust retry mechanism - keep trying for up to 2 seconds
        let attempts = 0;
        const maxAttempts = 20; // 20 attempts * 100ms = 2 seconds
        const retryInterval = 100;

        const tryQueueHIE = () => {
            attempts++;

            // Use existing HITL manager for CLI approval - it handles queuing internally
            if (window.hitlManager && window.hitlManager.queueHIEApproval) {
                window.updateStatus && window.updateStatus('Please approve or modify the CLI command...', 'pending');
                window.hitlManager.queueHIEApproval(hieData);
                return; // Success - stop retrying
            }

            // Still not available - retry if we haven't exceeded max attempts
            if (attempts < maxAttempts) {
                setTimeout(tryQueueHIE, retryInterval);
            } else {
                // Failed after all attempts - show error
                console.error('[ChatUIManager] ❌ HITL manager unavailable after all retry attempts');
                window.updateStatus && window.updateStatus('Error: CLI approval system unavailable', 'error');
                this.addMessage('system', '❌ Human-in-the-loop approval system unavailable. CLI command was generated but cannot be presented for approval.', 'error');
            }
        };

        // Start the retry mechanism
        tryQueueHIE();
    }

    /**
     * Handle HIE events through EventDispatcher interface
     */
    handleHIEEvent(eventType, data, workflowId) {
        // Forward HIE events to HumanInTheLoopManager
        if (window.hitlManager && window.hitlManager.handleEvent) {
            window.hitlManager.handleEvent(eventType, data, workflowId);
        } else {
            console.error('[ChatUIManager] ❌ HumanInTheLoopManager not available for HIE event handling');
            this.addMessage('system', '❌ Human-in-the-loop system unavailable', 'error');
        }
    }

    /**
     * Handle CLI human event (HITL request)
     * Shows CLI command approval modal for human-in-the-loop workflows
     */
    handleHITLRequest(eventData) {
        // Check if this is a CLI command approval request
        if (eventData.command || (eventData.data && eventData.data.command)) {
            // Show status message that user input is needed
            window.updateStatus && window.updateStatus('Please approve or modify the CLI command...', 'pending');

            // Use HITL manager to show CLI approval modal
            if (window.hitlManager && window.hitlManager.showCLICommandApproval) {
                const cliData = eventData.data || eventData;
                window.hitlManager.showCLICommandApproval(cliData);
            } else {
                console.error('[ChatUIManager] ❌ HITL manager not available');
                this.addMessage('system', '❌ Human-in-the-loop approval system unavailable', 'error');
            }
        }
    }

    /**
     * Resume workflow session automatically when workflow is selected
     * Session data is already verified by backend - switch to chat interface and load messages
     */
    async resumeWorkflowSession(sessionId) {
        if (!sessionId) {
            console.error('[ChatUIManager] Cannot resume session: no sessionId provided');
            return false;
        }

        try {
            // Use the global showChatInterface function which properly loads session messages
            if (window.showChatInterface) {
                await window.showChatInterface(sessionId);
                return true;
            } else {
                console.error('[ChatUIManager] Global showChatInterface not available');
                return false;
            }

        } catch (error) {
            console.error(`[ChatUIManager] ❌ Failed to resume session ${sessionId}:`, error);
            return false;
        }
    }

    /**
     * Check and recover session state after workflow completion
     * Prevents browser popup by ensuring frontend/backend session consistency
     */
    async checkAndRecoverSessionState() {
        try {
            const workflowId = window.globalState.currentWorkflow;
            const sessionId = window.sessionManager.getInfrastructureSession(workflowId);
            if (!workflowId) return;

            // Check if session state is inconsistent
            const stateInconsistent = this.detectSessionStateInconsistency(workflowId, sessionId);

            if (stateInconsistent) {
                // Attempt automatic recovery first
                const recovered = await this.attemptAutomaticSessionRecovery(workflowId, sessionId);

                if (!recovered) {
                    // Show recovery popup as last resort
                    this.showSessionRecoveryPopup(workflowId);
                }
            }

        } catch (error) {
            console.error('[ChatUIManager] ❌ Error during session state check:', error);
            // Don't show popup for errors - let workflow continue normally
        }
    }

    /**
     * REMOVED: Session state inconsistency detection - backend manages ACTIVE status
     * Frontend only uses InfrastructureSession
     */
    detectSessionStateInconsistency(workflowId, sessionId) {
        // REMOVED: No longer checking for ACTIVE session inconsistencies
        // Backend manages ACTIVE status, frontend just uses InfrastructureSession
        return false; // No longer detecting inconsistencies
    }

    /**
     * Attempt automatic session state recovery
     */
    async attemptAutomaticSessionRecovery(workflowId, sessionId) {
        try {
            // Use centralized API utility for recovery
            const result = await window.apiUtils.recoverWorkflowSession(sessionId, {
                reason: 'post_workflow_completion'
            });

            // Update frontend state if recovery successful
            if (result.success) {
                // Update workflow status
                window.updateStatus && window.updateStatus('Session recovered successfully', 'success');
                return true;
            }

            return false;

        } catch (error) {
            console.error('[ChatUIManager] Automatic recovery failed:', error);
            return false;
        }
    }

    /**
     * Show session recovery popup when automatic recovery fails
     */
    showSessionRecoveryPopup(workflowId) {
        // Create modal overlay
        const overlay = document.createElement('div');
        overlay.className = 'recovery-modal-overlay';
        overlay.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.7);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 10000;
            `;

        // Create modal content
        const modal = document.createElement('div');
        modal.className = 'recovery-modal';
        modal.style.cssText = `
                background: white;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
                max-width: 400px;
                text-align: center;
            `;

        modal.innerHTML = `
                <h3 style="margin-top: 0; color: #d32f2f;">⚠️ Session Recovery Needed</h3>
                <p style="margin: 20px 0; line-height: 1.5;">
                    Workflow session needs recovery. This ensures your conversation history is properly saved.
                </p>
                <div style="margin-top: 25px;">
                    <button id="recovery-reload-btn" style="
                        background: #1976d2;
                        color: white;
                        border: none;
                        padding: 10px 20px;
                        border-radius: 4px;
                        cursor: pointer;
                        font-size: 14px;
                        margin-right: 10px;
                    ">Reload Page</button>
                    <button id="recovery-continue-btn" style="
                        background: #757575;
                        color: white;
                        border: none;
                        padding: 10px 20px;
                        border-radius: 4px;
                        cursor: pointer;
                        font-size: 14px;
                    ">Continue</button>
                </div>
            `;

        overlay.appendChild(modal);
        document.body.appendChild(overlay);

        // Handle button clicks
        document.getElementById('recovery-reload-btn').onclick = () => {
            window.location.reload();
        };

        document.getElementById('recovery-continue-btn').onclick = () => {
            document.body.removeChild(overlay);
            window.updateStatus && window.updateStatus('Continuing without session recovery', 'warning');
        };

        // Auto-remove modal after 30 seconds
        setTimeout(() => {
            if (document.body.contains(overlay)) {
                document.body.removeChild(overlay);
            }
        }, 30000);
    }

    /**
     * Show workflow progress UI during message sending (Phase 5.8)
     * Simplifies implementation - Phase 5.8 needs more proper BMDNF (Backend Message Driven Narratives from Files)
     */
    showWorkflowProgress() {
        console.log('[ChatUIManager] Workflow progress UI requested but simplified for Phase 5.8 demo');

        // For demo purposes, just log - full implementation would require:
        // 1. Loading config from API endpoint
        // 2. Real-time streaming from backend
        // 3. Proper BMDNF (Backend Message Driven Narratives from Files)

        // TODO: Phase 5.8 follow-up - implement proper progress loading via API endpoint
        // window.workflowProgressManager.showWorkflowProgress(workflow);
    }
}

// Initialize when DOM is ready and export globally
document.addEventListener('DOMContentLoaded', () => {
    window.chatUIManager = new ChatUIManager();
});

// Export globally available functions and objects
window.addMessage = (sender, content, type) => window.chatUIManager?.addMessage(sender, content, type);
window.sendMessage = () => window.chatUIManager?.sendMessage();
window.showChatInterface = (sessionId) => window.chatUIManager?.showChatInterface(sessionId);

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ChatUIManager;
}
