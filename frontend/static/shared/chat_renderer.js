/**
 * Unified Chat Renderer - Single Rendering Path for History and Live Chat
 *
 * This module provides a unified interface for rendering chat messages,
 * whether they come from live chat sessions or chat history. It ensures
 * consistent UI styling and behavior across all entry points.
 */

class UnifiedChatRenderer {
    constructor() {
        this.messageContainer = null;
        this.currentSessionId = null;
        this.currentWorkflow = null;
        this.messageCache = new Map(); // Cache rendered messages to avoid duplicates

        this.init();
    }

    init() {
        this.setupMessageContainer();
        this.bindEvents();
    }

    /**
     * Setup the message container
     */
    setupMessageContainer() {
        this.messageContainer = document.getElementById('message-container');
        if (!this.messageContainer) {
            console.warn('[UnifiedChatRenderer] Message container not found');
            return;
        }

        // Ensure proper styling
        this.messageContainer.className = 'message-container';
    }

    /**
     * Bind event listeners
     */
    bindEvents() {
        // Listen for workflow changes
        if (window.globalState) {
            // Observe global state changes
            this.observeGlobalState();
        }
    }

    /**
     * Observe global state changes
     */
    observeGlobalState() {
        // Simple polling for global state changes (could be enhanced with proper observers)
        setInterval(() => {
            if (window.globalState) {
                if (this.currentWorkflow !== window.globalState.currentWorkflow) {
                    this.currentWorkflow = window.globalState.currentWorkflow;
                    this.clearMessages();
                }

                if (this.currentSessionId !== window.globalState.currentChatSessionId) {
                    this.currentSessionId = window.globalState.currentChatSessionId;
                    this.clearMessages();
                }
            }
        }, 100);
    }

    /**
     * Render messages for a session (unified for history and live chat)
     */
    async renderSessionMessages(sessionId, workflow = null, options = {}) {
        if (!this.messageContainer) {
            console.warn('[UnifiedChatRenderer] Cannot render messages - container not found');
            return;
        }

        const {
            showLoading = true,
            clearExisting = true,
            addSystemMessage = true,
            source = 'unknown'
        } = options;

        try {
            // Show loading if requested
            if (showLoading && window.updateStatus) {
                window.updateStatus('Loading messages...', 'in-progress');
            }

            // Clear existing messages if requested
            if (clearExisting) {
                this.clearMessages();
                this.messageCache.clear();
            }

            // Fetch session data
            const sessionData = await this.fetchSessionData(sessionId, workflow);

            if (!sessionData || !sessionData.messages) {
                console.warn(`[UnifiedChatRenderer] No messages found for session ${sessionId}`);
                if (addSystemMessage) {
                    await this.addSystemMessage(`No messages found for session ${sessionId.substring(0, 8)}`, 'warning');
                }
                return;
            }

            // Render messages
            const renderedCount = await this.renderMessages(sessionData.messages, {
                sessionId,
                workflow: workflow || sessionData.workflow_name,
                source
            });

            // Add system message if requested
            if (addSystemMessage && renderedCount > 0) {
                const workflowName = workflow || sessionData.workflow_name || 'Unknown';
                const sessionShortId = sessionId.substring(0, 8);
                await this.addSystemMessage(`Loaded ${renderedCount} messages from ${workflowName} session (${sessionShortId})`, 'info');
            }

            // Update status
            if (window.updateStatus) {
                window.updateStatus(`Loaded ${renderedCount} messages`, 'success');
            }

        } catch (error) {
            console.error(`[UnifiedChatRenderer] Failed to render session ${sessionId}:`, error);

            if (addSystemMessage) {
                await this.addSystemMessage(`Failed to load messages: ${error.message}`, 'error');
            }

            if (window.updateStatus) {
                window.updateStatus('Failed to load messages', 'error');
            }
        }
    }

    /**
     * Fetch session data from appropriate endpoint
     */
    async fetchSessionData(sessionId, workflow = null) {
        if (!sessionId) {
            throw new Error('Session ID is required');
        }

        // Determine which endpoint to use based on context
        let endpoint;
        if (workflow) {
            // For workflow UI: Use workflow API with infrastructure session + chat session
            // Need infrastructure session ID from session registry
            const infrastructureSessionId = window.sessionManager?.getInfrastructureSession(workflow);
            if (infrastructureSessionId) {
                // Use workflow API: /api/workflow/{infra_session}/chat_session/{chat_session}
                endpoint = `/api/workflow/${infrastructureSessionId}/chat_session/${sessionId}`;
            } else {
                // Fallback to history API if no infrastructure session
                endpoint = `/api/history/workflow/${workflow}/${sessionId}`;
            }
        } else {
            // Fallback to general chat history endpoint
            endpoint = `/api/history/sessions/${sessionId}`;
        }

        const response = await fetch(endpoint);
        if (!response.ok) {
            let errorDetail = response.statusText;
            try {
                const errorData = await response.json();
                errorDetail = errorData.detail || JSON.stringify(errorData);
            } catch (e) {
                // Could not parse JSON, use status text
            }
            throw new Error(`Failed to fetch session data: ${response.status} ${errorDetail}`);
        }

        const data = await response.json();

        // Handle different response formats
        if (data.messages) {
            // Direct session data
            return data;
        } else if (data.session && data.session.messages) {
            // Wrapped in session object
            return data.session;
        } else {
            throw new Error('Unexpected response format');
        }
    }

    /**
     * Render an array of messages
     */
    async renderMessages(messages, context = {}) {
        if (!Array.isArray(messages)) {
            console.warn('[UnifiedChatRenderer] Messages is not an array:', messages);
            return 0;
        }

        let renderedCount = 0;

        // Use for loop instead of forEach to properly handle async/await
        for (const message of messages) {
            if (await this.renderMessage(message, context)) {
                renderedCount++;
            }
        }

        // Scroll to bottom after rendering
        this.scrollToBottom();

        return renderedCount;
    }

    /**
     * Render a single message
     */
    async renderMessage(message, context = {}) {
        if (!message || !this.messageContainer) {
            return false;
        }

        // Check cache to avoid duplicates
        const messageKey = `${message.message_id || message.id || 'unknown'}_${message.timestamp || Date.now()}`;
        if (this.messageCache.has(messageKey)) {
            return false;
        }

        // Create message element (now async)
        const messageElement = await this.createMessageElement(message, context);

        // Add to container
        this.messageContainer.appendChild(messageElement);

        // Cache the message
        this.messageCache.set(messageKey, message);

        // Apply enhancements if available
        if (window.chatUIEnhancements && window.chatUIEnhancements.enhanceMessageElement) {
            window.chatUIEnhancements.enhanceMessageElement(messageElement);
        }

        return true;
    }

    /**
     * Create a message element from message data
     */
    async createMessageElement(message, context = {}) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message');

        // Store message metadata
        if (message.message_id || message.id) {
            messageElement.setAttribute('data-message-id', message.message_id || message.id);
        }
        if (context.sessionId) {
            messageElement.setAttribute('data-session-id', context.sessionId);
        }
        if (context.workflow) {
            messageElement.setAttribute('data-workflow', context.workflow);
        }

        // Determine message type and styling
        const messageType = this.determineMessageType(message);
        messageElement.classList.add(messageType);

        // Create message header
        const headerElement = this.createMessageHeader(message, messageType);
        messageElement.appendChild(headerElement);

        // Create message content (now async)
        const contentElement = await this.createMessageContent(message, context);
        messageElement.appendChild(contentElement);

        return messageElement;
    }

    /**
     * Determine message type for styling
     */
    determineMessageType(message) {
        if (message.role === 'system' || message.type === 'system') {
            return 'system-message';
        } else if (message.role === 'error' || message.type === 'error') {
            return 'error-message';
        } else if (message.role === 'user') {
            return 'user-message';
        } else {
            return 'ai-message';
        }
    }

    /**
     * Create message header
     */
    createMessageHeader(message, messageType) {
        const headerElement = document.createElement('div');
        headerElement.classList.add('message-sender');

        let senderText;
        if (messageType === 'system-message') {
            senderText = 'System';
        } else if (messageType === 'error-message') {
            senderText = 'Error';
        } else if (messageType === 'user-message') {
            senderText = 'You';
        } else {
            senderText = 'AI';
        }

        headerElement.textContent = senderText;
        return headerElement;
    }

    /**
     * Create message content
     */
    async createMessageContent(message, context = {}) {
        const contentElement = document.createElement('div');
        contentElement.classList.add('message-content');

        let content = message.content || '';

        // Use rich text renderer if available
        if (window.richTextRenderer && context.workflow) {
            // Prepare metadata for enhanced rendering
            const metadata = {
                workflowId: context.workflow,
                sessionId: context.sessionId,
                source: context.source
            };

            // Include enhanced metadata if available
            if (message.enhanced_metadata) {
                metadata.enhanced_metadata = message.enhanced_metadata;
            }

            try {
                // Await the async renderMessage call
                content = await window.richTextRenderer.renderMessage(content, metadata);
            } catch (error) {
                console.warn('[UnifiedChatRenderer] Rich text rendering failed, using plain text:', error);
                console.warn('[UnifiedChatRenderer] Error details:', error);
                content = this.escapeHtml(content).replace(/\n/g, '<br>');
            }
        } else {
            // Fallback to basic HTML escaping
            content = this.escapeHtml(content).replace(/\n/g, '<br>');
        }

        contentElement.innerHTML = content;
        return contentElement;
    }

    /**
     * Add a system message
     */
    async addSystemMessage(content, type = 'info') {
        const message = {
            role: 'system',
            type: type,
            content: content,
            timestamp: new Date().toISOString()
        };

        return await this.renderMessage(message, { source: 'system' });
    }

    /**
     * Add a live message (for real-time chat)
     */
    async addLiveMessage(message, context = {}) {
        // Ensure context includes current session/workflow
        const fullContext = {
            sessionId: this.currentSessionId || context.sessionId,
            workflow: this.currentWorkflow || context.workflow,
            source: 'live',
            ...context
        };

        const rendered = await this.renderMessage(message, fullContext);

        if (rendered) {
            this.scrollToBottom();
        }

        return rendered;
    }

    /**
     * Clear all messages
     */
    clearMessages() {
        if (this.messageContainer) {
            this.messageContainer.innerHTML = '';
        }
        this.messageCache.clear();
    }

    /**
     * Scroll to bottom of message container
     */
    scrollToBottom() {
        if (this.messageContainer) {
            this.messageContainer.scrollTop = this.messageContainer.scrollHeight;
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
     * Get current session info
     */
    getCurrentSessionInfo() {
        return {
            sessionId: this.currentSessionId,
            workflow: this.currentWorkflow
        };
    }

    /**
     * Set current session context
     */
    setCurrentSession(sessionId, workflow) {
        this.currentSessionId = sessionId;
        this.currentWorkflow = workflow;
    }

    /**
     * Check if message container is visible
     */
    isVisible() {
        return this.messageContainer &&
            this.messageContainer.offsetParent !== null &&
            window.getComputedStyle(this.messageContainer).display !== 'none';
    }

    /**
     * Get message count
     */
    getMessageCount() {
        return this.messageCache.size;
    }

    /**
     * Export messages for debugging
     */
    exportMessages() {
        const messages = Array.from(this.messageCache.values());
        return {
            count: messages.length,
            sessionId: this.currentSessionId,
            workflow: this.currentWorkflow,
            messages: messages
        };
    }
}

// Global instance
let unifiedChatRenderer = null;

/**
 * Initialize the unified chat renderer
 */
function initializeUnifiedChatRenderer() {
    if (!unifiedChatRenderer) {
        unifiedChatRenderer = new UnifiedChatRenderer();
        window.unifiedChatRenderer = unifiedChatRenderer;
    }
    return unifiedChatRenderer;
}

/**
 * Get the unified chat renderer instance
 */
function getUnifiedChatRenderer() {
    if (!unifiedChatRenderer) {
        return initializeUnifiedChatRenderer();
    }
    return unifiedChatRenderer;
}

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    initializeUnifiedChatRenderer();
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        UnifiedChatRenderer,
        initializeUnifiedChatRenderer,
        getUnifiedChatRenderer
    };
}
