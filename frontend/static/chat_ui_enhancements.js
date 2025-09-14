/**
 * Chat UI Enhancements
 * Advanced UI features for the main chat interface
 */
class ChatUIEnhancements {
    constructor() {
        this.typingTimeouts = new Map();
        this.messageStatuses = new Map();
        this.copyTimeouts = new Map();

        this.init();
    }

    init() {
        console.log('[ChatUI] Initializing Chat UI Enhancements');
        this.enhanceMessageContainer();
        this.enhanceInputArea();
        this.addGlobalEventListeners();
    }

    /**
     * Enhance the message container with advanced features
     */
    enhanceMessageContainer() {
        const messageContainer = document.getElementById('message-container');
        if (!messageContainer) return;

        // Add scroll-to-bottom button
        this.addScrollToBottomButton(messageContainer);

        // Add message actions (copy, timestamp, status)
        this.enhanceExistingMessages(messageContainer);

        // Add auto-scroll functionality
        this.addAutoScroll(messageContainer);
    }

    /**
     * Add scroll-to-bottom button for long conversations
     */
    addScrollToBottomButton(container) {
        const scrollButton = document.createElement('button');
        scrollButton.id = 'scroll-to-bottom-btn';
        scrollButton.className = 'scroll-to-bottom-btn';
        scrollButton.innerHTML = '⬇️';
        scrollButton.title = 'Scroll to bottom';
        scrollButton.style.cssText = `
            position: fixed;
            bottom: 120px;
            right: 30px;
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: linear-gradient(45deg, #00d4ff, #0099cc);
            border: none;
            color: white;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(0, 212, 255, 0.3);
            opacity: 0;
            transform: translateY(20px);
            transition: all 0.3s ease;
            z-index: 1000;
            display: none;
        `;

        scrollButton.addEventListener('click', () => {
            container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
        });

        document.body.appendChild(scrollButton);

        // Show/hide button based on scroll position
        container.addEventListener('scroll', () => {
            const isNearBottom = container.scrollTop + container.clientHeight >= container.scrollHeight - 100;
            const shouldShow = container.scrollTop > 200 && !isNearBottom;

            if (shouldShow) {
                scrollButton.style.display = 'block';
                setTimeout(() => {
                    scrollButton.style.opacity = '1';
                    scrollButton.style.transform = 'translateY(0)';
                }, 10);
            } else {
                scrollButton.style.opacity = '0';
                scrollButton.style.transform = 'translateY(20px)';
                setTimeout(() => {
                    scrollButton.style.display = 'none';
                }, 300);
            }
        });
    }

    /**
     * Enhance existing messages with advanced features
     */
    enhanceExistingMessages(container) {
        // Use MutationObserver to enhance new messages as they're added
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (node.classList && node.classList.contains('message')) {
                        this.enhanceMessageElement(node);
                    }
                });
            });
        });

        observer.observe(container, { childList: true });

        // Enhance existing messages
        container.querySelectorAll('.message').forEach(message => {
            this.enhanceMessageElement(message);
        });
    }

    /**
     * Enhance individual message elements
     */
    enhanceMessageElement(messageElement) {
        // Add message actions (copy, etc.)
        this.addMessageActions(messageElement);

        // Add message status indicator
        this.addMessageStatus(messageElement);

        // Add timestamp if not present
        this.addMessageTimestamp(messageElement);

        // Enhance message content formatting
        this.enhanceMessageContent(messageElement);
    }

    /**
     * Add action buttons to messages (copy, share, etc.)
     */
    addMessageActions(messageElement) {
        if (messageElement.querySelector('.message-actions')) return;

        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'message-actions';
        actionsDiv.style.cssText = `
            opacity: 0;
            transition: opacity 0.2s ease;
            position: absolute;
            top: 5px;
            right: 10px;
            display: flex;
            gap: 5px;
        `;

        // Copy button
        const copyBtn = document.createElement('button');
        copyBtn.innerHTML = '📋';
        copyBtn.title = 'Copy message';
        copyBtn.className = 'message-action-btn';
        copyBtn.style.cssText = `
            background: rgba(255, 255, 255, 0.2);
            border: none;
            border-radius: 50%;
            width: 24px;
            height: 24px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s ease;
        `;

        copyBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.copyMessageToClipboard(messageElement);
        });

        actionsDiv.appendChild(copyBtn);

        // Position the actions
        messageElement.style.position = 'relative';
        messageElement.appendChild(actionsDiv);

        // Show/hide actions on hover
        messageElement.addEventListener('mouseenter', () => {
            actionsDiv.style.opacity = '1';
        });

        messageElement.addEventListener('mouseleave', () => {
            actionsDiv.style.opacity = '0';
        });
    }

    /**
     * Copy message content to clipboard
     */
    async copyMessageToClipboard(messageElement) {
        const contentElement = messageElement.querySelector('.message-content');
        if (!contentElement) return;

        try {
            // Get text content without HTML formatting
            const textContent = contentElement.textContent || contentElement.innerText;

            await navigator.clipboard.writeText(textContent);

            // Show success feedback
            this.showCopyFeedback(messageElement, 'Copied!');

        } catch (error) {
            console.error('[ChatUI] Failed to copy message:', error);
            this.showCopyFeedback(messageElement, 'Failed to copy');
        }
    }

    /**
     * Show copy feedback on message
     */
    showCopyFeedback(messageElement, message) {
        const feedback = document.createElement('div');
        feedback.textContent = message;
        feedback.style.cssText = `
            position: absolute;
            top: -30px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            white-space: nowrap;
            z-index: 1000;
        `;

        messageElement.appendChild(feedback);

        setTimeout(() => {
            if (feedback.parentNode) {
                feedback.parentNode.removeChild(feedback);
            }
        }, 2000);
    }

    /**
     * Add message status indicator
     */
    addMessageStatus(messageElement) {
        const statusDiv = document.createElement('div');
        statusDiv.className = 'message-status';
        statusDiv.style.cssText = `
            position: absolute;
            bottom: 5px;
            right: 10px;
            font-size: 10px;
            opacity: 0.6;
        `;

        // Default status
        const isUserMessage = messageElement.classList.contains('user-message');
        statusDiv.textContent = isUserMessage ? '✓' : '●';

        messageElement.appendChild(statusDiv);
    }

    /**
     * Add timestamp to message if not present
     */
    addMessageTimestamp(messageElement) {
        if (messageElement.querySelector('.message-timestamp')) return;

        const timestamp = document.createElement('div');
        timestamp.className = 'message-timestamp';
        timestamp.textContent = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        timestamp.style.cssText = `
            font-size: 10px;
            opacity: 0.6;
            margin-top: 2px;
        `;

        const contentElement = messageElement.querySelector('.message-content');
        if (contentElement) {
            contentElement.appendChild(timestamp);
        }
    }

    /**
     * Enhance message content with better formatting
     */
    enhanceMessageContent(messageElement) {
        const contentElement = messageElement.querySelector('.message-content');
        if (!contentElement) return;

        let content = contentElement.innerHTML;

        // Enhanced formatting
        content = content
            // Code blocks
            .replace(/```(\w+)?\n?([\s\S]*?)```/g, '<pre class="code-block"><code class="language-$1">$2</code></pre>')
            // Inline code
            .replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
            // Bold
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
            // Italic
            .replace(/\*([^*]+)\*/g, '<em>$1</em>')
            // Links
            .replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>')
            // Line breaks
            .replace(/\n/g, '<br>');

        contentElement.innerHTML = content;

        // Add syntax highlighting for code blocks
        this.addSyntaxHighlighting(contentElement);
    }

    /**
     * Add basic syntax highlighting for code blocks
     */
    addSyntaxHighlighting(contentElement) {
        const codeBlocks = contentElement.querySelectorAll('code');
        codeBlocks.forEach(code => {
            code.style.cssText = `
                background: rgba(0, 0, 0, 0.3);
                padding: 2px 4px;
                border-radius: 3px;
                font-family: 'Courier New', monospace;
                font-size: 0.9em;
            `;
        });

        const codePreBlocks = contentElement.querySelectorAll('pre code');
        codePreBlocks.forEach(code => {
            code.style.cssText = `
                background: #1e1e1e;
                color: #d4d4d4;
                padding: 10px;
                border-radius: 6px;
                font-family: 'Courier New', monospace;
                font-size: 0.85em;
                overflow-x: auto;
                white-space: pre;
                display: block;
            `;
        });
    }

    /**
     * Add auto-scroll functionality
     */
    addAutoScroll(container) {
        let autoScrollEnabled = true;
        let userScrolledUp = false;

        container.addEventListener('scroll', () => {
            const isNearBottom = container.scrollTop + container.clientHeight >= container.scrollHeight - 50;
            userScrolledUp = !isNearBottom;
        });

        // Override the global addMessage function to include auto-scroll
        const originalAddMessage = window.addMessage;
        if (originalAddMessage) {
            window.addMessage = (sender, content, messageType) => {
                originalAddMessage(sender, content, messageType);

                // Auto-scroll if enabled and user hasn't scrolled up
                if (autoScrollEnabled && !userScrolledUp) {
                    setTimeout(() => {
                        container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
                    }, 100);
                }
            };
        }
    }

    /**
     * Enhance the input area with advanced features
     */
    enhanceInputArea() {
        const input = document.getElementById('user-input');
        const sendButton = document.getElementById('send-button');

        if (!input || !sendButton) return;

        // Add typing indicator
        this.addTypingIndicator(input);

        // Add input enhancements
        this.addInputEnhancements(input, sendButton);

        // Add keyboard shortcuts
        this.addKeyboardShortcuts(input, sendButton);
    }

    /**
     * Add typing indicator for user input
     */
    addTypingIndicator(input) {
        const indicator = document.createElement('div');
        indicator.id = 'typing-indicator';
        indicator.className = 'typing-indicator';
        indicator.innerHTML = '<span class="typing-dots">Typing<span>.</span><span>.</span><span>.</span></span>';
        indicator.style.cssText = `
            display: none;
            position: absolute;
            bottom: 80px;
            left: 20px;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 8px 12px;
            border-radius: 20px;
            font-size: 12px;
            z-index: 100;
        `;

        // Add animation for typing dots
        const style = document.createElement('style');
        style.textContent = `
            .typing-dots span:nth-child(1) { animation: typing 1.4s infinite; }
            .typing-dots span:nth-child(2) { animation: typing 1.4s infinite 0.2s; }
            .typing-dots span:nth-child(3) { animation: typing 1.4s infinite 0.4s; }
            @keyframes typing {
                0%, 60%, 100% { opacity: 0; }
                30% { opacity: 1; }
            }
        `;
        document.head.appendChild(style);

        document.body.appendChild(indicator);

        // Show/hide indicator based on input
        let typingTimeout;
        input.addEventListener('input', () => {
            clearTimeout(typingTimeout);

            if (input.value.trim()) {
                indicator.style.display = 'block';

                typingTimeout = setTimeout(() => {
                    indicator.style.display = 'none';
                }, 1000);
            } else {
                indicator.style.display = 'none';
            }
        });

        input.addEventListener('blur', () => {
            indicator.style.display = 'none';
        });
    }

    /**
     * Add input enhancements (character count, etc.)
     */
    addInputEnhancements(input, sendButton) {
        // Character counter
        const counter = document.createElement('div');
        counter.id = 'input-counter';
        counter.style.cssText = `
            position: absolute;
            bottom: 60px;
            right: 120px;
            font-size: 10px;
            color: rgba(255, 255, 255, 0.6);
            background: rgba(0, 0, 0, 0.5);
            padding: 2px 6px;
            border-radius: 10px;
        `;

        // Position relative to input area
        const inputArea = input.parentElement;
        inputArea.style.position = 'relative';
        inputArea.appendChild(counter);

        input.addEventListener('input', () => {
            const length = input.value.length;
            counter.textContent = `${length}/2000`;

            if (length > 1800) {
                counter.style.color = '#ff9800';
            } else if (length > 1900) {
                counter.style.color = '#f44336';
            } else {
                counter.style.color = 'rgba(255, 255, 255, 0.6)';
            }

            // Enable/disable send button based on content
            sendButton.disabled = !input.value.trim();
            sendButton.style.opacity = input.value.trim() ? '1' : '0.5';
        });

        // Initial state
        sendButton.disabled = true;
        sendButton.style.opacity = '0.5';
    }

    /**
     * Add keyboard shortcuts
     */
    addKeyboardShortcuts(input, sendButton) {
        input.addEventListener('keydown', (e) => {
            // Ctrl+Enter to send
            if (e.ctrlKey && e.key === 'Enter') {
                e.preventDefault();
                if (input.value.trim()) {
                    sendButton.click();
                }
            }

            // Escape to clear
            if (e.key === 'Escape') {
                input.value = '';
                input.dispatchEvent(new Event('input'));
            }
        });
    }

    /**
     * Add global event listeners
     */
    addGlobalEventListeners() {
        // Handle window resize
        window.addEventListener('resize', () => {
            this.adjustLayoutForScreenSize();
        });

        // Handle online/offline status
        window.addEventListener('online', () => {
            this.showConnectionStatus('Connected', 'success');
        });

        window.addEventListener('offline', () => {
            this.showConnectionStatus('Offline', 'error');
        });
    }

    /**
     * Adjust layout for different screen sizes
     */
    adjustLayoutForScreenSize() {
        const isMobile = window.innerWidth < 768;
        const scrollButton = document.getElementById('scroll-to-bottom-btn');

        if (scrollButton) {
            if (isMobile) {
                scrollButton.style.right = '15px';
                scrollButton.style.bottom = '100px';
            } else {
                scrollButton.style.right = '30px';
                scrollButton.style.bottom = '120px';
            }
        }
    }

    /**
     * Show connection status notifications
     */
    showConnectionStatus(message, type) {
        const notification = document.createElement('div');
        notification.className = `connection-notification ${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 10px 20px;
            border-radius: 20px;
            color: white;
            font-weight: bold;
            z-index: 10000;
            animation: slideIn 0.3s ease;
        `;

        if (type === 'success') {
            notification.style.background = 'linear-gradient(45deg, #4CAF50, #45a049)';
        } else {
            notification.style.background = 'linear-gradient(45deg, #f44336, #d32f2f)';
        }

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, 3000);
    }

    /**
     * Show typing indicator for AI responses
     */
    showTypingIndicator() {
        const messageContainer = document.getElementById('message-container');
        if (!messageContainer) return;

        const typingDiv = document.createElement('div');
        typingDiv.id = 'ai-typing-indicator';
        typingDiv.className = 'message ai-message typing';
        typingDiv.innerHTML = `
            <div class="message-header">
                <span class="message-sender">AI</span>
            </div>
            <div class="message-content">
                <div class="typing-animation">
                    <span></span><span></span><span></span>
                </div>
            </div>
        `;

        messageContainer.appendChild(typingDiv);
        messageContainer.scrollTop = messageContainer.scrollHeight;

        return typingDiv;
    }

    /**
     * Hide typing indicator
     */
    hideTypingIndicator() {
        const typingDiv = document.getElementById('ai-typing-indicator');
        if (typingDiv) {
            typingDiv.remove();
        }
    }

    /**
     * Show error message with retry option
     */
    showErrorWithRetry(message, retryCallback) {
        const messageContainer = document.getElementById('message-container');
        if (!messageContainer) return;

        const errorDiv = document.createElement('div');
        errorDiv.className = 'message error-message';
        errorDiv.innerHTML = `
            <div class="message-header">
                <span class="message-sender">System</span>
            </div>
            <div class="message-content">
                <div class="error-content">
                    <div class="error-icon">⚠️</div>
                    <div class="error-text">${message}</div>
                    ${retryCallback ? '<button class="retry-btn" onclick="this.closest(\'.error-message\').remove(); window.chatUIEnhancements.retryLastMessage();">Retry</button>' : ''}
                </div>
            </div>
        `;

        messageContainer.appendChild(errorDiv);
        messageContainer.scrollTop = messageContainer.scrollHeight;
    }

    /**
     * Retry last message (placeholder for implementation)
     */
    retryLastMessage() {
        console.log('[ChatUI] Retry functionality not implemented yet');
        // This would need to be connected to the main chat functionality
    }
}

// Global styles for enhancements
const enhancementStyles = `
    .scroll-to-bottom-btn:hover {
        transform: translateY(-2px) scale(1.05);
        box-shadow: 0 6px 20px rgba(0, 212, 255, 0.4);
    }

    .message-action-btn:hover {
        background: rgba(255, 255, 255, 0.3);
        transform: scale(1.1);
    }

    .message-actions:hover {
        opacity: 1 !important;
    }

    .typing-animation {
        display: flex;
        gap: 4px;
        padding: 8px 0;
    }

    .typing-animation span {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.6);
        animation: typingBounce 1.4s infinite;
    }

    .typing-animation span:nth-child(2) { animation-delay: 0.2s; }
    .typing-animation span:nth-child(3) { animation-delay: 0.4s; }

    @keyframes typingBounce {
        0%, 80%, 100% { transform: scale(0.8); opacity: 0.6; }
        40% { transform: scale(1); opacity: 1; }
    }

    .error-content {
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .error-icon {
        font-size: 1.2em;
    }

    .error-text {
        flex: 1;
    }

    .retry-btn {
        padding: 6px 12px;
        background: linear-gradient(45deg, #ff9800, #f57c00);
        border: none;
        border-radius: 15px;
        color: white;
        cursor: pointer;
        font-size: 0.8em;
        transition: all 0.3s ease;
    }

    .retry-btn:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 15px rgba(255, 152, 0, 0.3);
    }

    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }

    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }

    .connection-notification {
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
    }
`;

// Add styles to document
const styleSheet = document.createElement('style');
styleSheet.textContent = enhancementStyles;
document.head.appendChild(styleSheet);

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.chatUIEnhancements = new ChatUIEnhancements();
    console.log('[ChatUI] Chat UI Enhancements loaded and ready');
});

// Export for global access
window.ChatUIEnhancements = ChatUIEnhancements;
