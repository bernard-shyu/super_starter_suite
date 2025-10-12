/**
 * Chat UI Manager - Phase 5.6D Frontend Modularization
 *
 * Handles chat functionality, message handling, and UI enhancements.
 * Separated from monolithic script.js for better maintainability.
 */

// Chat state management - now managed by global-state.js

// Chat UI enhancements object
let chatUIEnhancements = null;

// Core Chat UI Manager Class
class ChatUIManager {
    constructor() {
        this.initializeChatElements();
        this.initializeEventListeners();
        this.setupTypingIndicator();
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

        console.log('[ChatUIManager] Showing typing indicator');
        return this.currentTypingIndicator;
    }

    /**
     * Hide typing indicator from chat
     */
    hideTypingIndicator() {
        if (!this.isTyping || !this.currentTypingIndicator) return;

        this.isTyping = false;
        if (this.currentTypingIndicator.parentNode) {
            this.currentTypingIndicator.parentNode.removeChild(this.currentTypingIndicator);
        }
        this.currentTypingIndicator = null;

        console.log('[ChatUIManager] Hiding typing indicator');
    }

    /**
     * Add message to chat interface
     */
    addMessage(sender, content, messageType = 'normal', messageId = null) {
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
        // Convert line breaks to <br> tags for proper HTML display
        const formattedContent = content.replace(/\n/g, '<br>');
        contentElement.innerHTML = formattedContent;

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
     * Enhanced send message to workflow API
     */
    async sendMessage() {
        if (!this.userInput || !window.globalState.currentWorkflow) {
            if (!window.globalState.currentWorkflow) {
                this.addMessage('system', 'Please select a workflow first.', 'system');
            }
            return;
        }

        const message = this.userInput.value.trim();
        if (!message) return;

        // Add user message
        this.addMessage('user', message);
        this.userInput.value = '';

        window.updateStatus && window.updateStatus(`Sending message to ${window.globalState.currentWorkflow}...`, 'in-progress');

        // Show typing indicator for AI response
        let typingIndicator = this.showTypingIndicator();

        try {
            const payload = { question: message };
            if (window.globalState.currentChatSessionId) {
                payload.session_id = window.globalState.currentChatSessionId;
            }

            // Use unified workflow execution endpoint
            const response = await fetch(`/api/chat/${window.globalState.currentWorkflow}/session/${window.globalState.currentChatSessionId || 'new'}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            console.log('[ChatUIManager] Backend response received:', data);
            console.log('[ChatUIManager] Response keys:', Object.keys(data));
            console.log('[ChatUIManager] Has artifacts?', data.artifacts ? 'YES' : 'NO');
            if (data.artifacts) {
                console.log('[ChatUIManager] Artifacts type:', typeof data.artifacts);
                console.log('[ChatUIManager] Artifacts isArray?', Array.isArray(data.artifacts));
                console.log('[ChatUIManager] Artifacts length:', data.artifacts ? data.artifacts.length : 'undefined');
                if (data.artifacts && data.artifacts.length > 0) {
                    console.log('[ChatUIManager] First artifact sample:', JSON.stringify(data.artifacts[0]).substring(0, 200) + '...');
                }
            }

            // Hide typing indicator and add AI response
            this.hideTypingIndicator();

            // Check if response includes artifacts (Phase 5.6 new feature)
            if (data.artifacts && Array.isArray(data.artifacts) && data.artifacts.length > 0) {
                // Use artifact display manager if available
                if (window.artifactDisplayManager) {
                    window.artifactDisplayManager.displayArtifacts(data.artifacts);
                }

                // Show response with artifact notification
                const artifactCount = data.artifacts.length;
                const enhancedContent = `${data.response}<br><br><small><em>📎 ${artifactCount} artifact${artifactCount > 1 ? 's' : ''} generated</em></small>`;
                this.addMessage('ai', enhancedContent);
            } else {
                // Standard response without artifacts
                this.addMessage('ai', data.response || 'No response generated');
            }

            // Update session ID if new session was created
            if (data.session_id && !window.globalState.currentChatSessionId) {
                window.globalState.currentChatSessionId = data.session_id;
                console.log(`[ChatUIManager] New session created: ${window.globalState.currentChatSessionId}`);
            }

            window.updateStatus && window.updateStatus(`Message sent to ${window.globalState.currentWorkflow}.`, 'success');

        } catch (error) {
            console.error('[ChatUIManager] Error sending message:', error);

            // Hide typing indicator
            this.hideTypingIndicator();

            // Use enhanced error handling if available
            if (chatUIEnhancements && chatUIEnhancements.showErrorWithRetry) {
                chatUIEnhancements.showErrorWithRetry(
                    `Failed to send message: ${error.message}`,
                    () => this.sendMessage() // Retry function
                );
            } else {
                // Fallback to basic error message
                this.addMessage('ai', `<p style="color: red;">Error: ${error.message}</p>`);
            }

            window.updateStatus && window.updateStatus(`Error sending message.`, 'error');
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
            window.globalState.currentChatSessionId = sessionIdToResume;
            // Fetch and display existing messages for the session
            try {
                const response = await fetch(`/api/chat_history/sessions/${sessionIdToResume}`);
                if (response.ok) {
                    const sessionData = await response.json();
                    sessionData.messages.forEach(msg => {
                        this.addMessage(msg.role, msg.content);
                    });
                    this.addMessage('system', `Resumed chat with ${window.globalState.currentWorkflow} workflow (Session: ${window.globalState.currentChatSessionId.substring(0, 8)})`, 'system');
                } else {
                    console.error('[ChatUIManager] Failed to load session for resumption:', sessionIdToResume);
                    this.addMessage('system', `Failed to resume chat session ${sessionIdToResume.substring(0, 8)}. Starting new conversation.`, 'error');
                    // Clear stale session state when resumption fails
                    if (window.clearSessionState) window.clearSessionState();
                    window.globalState.currentChatSessionId = generateUUID();
                    this.addMessage('system', `Ready to chat with ${window.globalState.currentWorkflow} workflow (New Session: ${window.globalState.currentChatSessionId.substring(0, 8)})`, 'system');
                }
            } catch (error) {
                console.error('[ChatUIManager] Error loading session for resumption:', error);
                this.addMessage('system', `Error resuming chat session. Starting new conversation.`, 'error');
                if (window.clearSessionState) window.clearSessionState();
                window.globalState.currentChatSessionId = generateUUID();
                this.addMessage('system', `Ready to chat with ${window.globalState.currentWorkflow} workflow (New Session: ${window.globalState.currentChatSessionId.substring(0, 8)})`, 'system');
            }
        } else {
            // Start a new session
            window.globalState.currentChatSessionId = generateUUID();
            if (window.globalState.currentWorkflow) {
                this.addMessage('system', `Ready to chat with ${window.globalState.currentWorkflow} workflow (New Session: ${window.globalState.currentChatSessionId.substring(0, 8)})`, 'system');
            }
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
     * Get current session ID
     */
    getCurrentSessionId() {
        return window.globalState.currentChatSessionId;
    }

    /**
     * Set current session ID
     */
    setCurrentSessionId(sessionId) {
        window.globalState.currentChatSessionId = sessionId;
    }
}

// Utility function for UUID generation
function generateUUID() {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
        return crypto.randomUUID();
    }
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
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
