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
     * Add action buttons to messages (copy, artifacts, share, etc.)
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

        // Only show buttons on AI messages (where artifacts are generated)
        const isAIMessage = messageElement.classList.contains('ai-message');
        const isArtifactMessage = messageElement.querySelector('.message-content')?.textContent?.includes('artifact');

        // Copy button (always available)
        const copyBtn = document.createElement('button');
        copyBtn.innerHTML = '📋';
        copyBtn.title = 'Copy message';
        copyBtn.className = 'message-action-btn larger';
        copyBtn.style.cssText = `
            background: rgba(255, 255, 255, 0.2);
            border: none;
            border-radius: 50%;
            width: 32px;
            height: 32px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s ease;
        `;

        copyBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.copyMessageToClipboard(messageElement);
        });

        actionsDiv.appendChild(copyBtn);

        // Artifact viewer button (only on AI messages, especially those with artifacts)
        if (isAIMessage && (isArtifactMessage || true)) { // Show on all AI messages for now
            const artifactBtn = document.createElement('button');
            artifactBtn.innerHTML = '📎';
            artifactBtn.title = 'View Artifacts from This Message';
            artifactBtn.className = 'message-action-btn larger artifact-viewer';
            artifactBtn.style.cssText = `
                background: rgba(255, 255, 255, 0.2);
                border: none;
                border-radius: 50%;
                width: 32px;
                height: 32px;
                cursor: pointer;
                font-size: 14px;
                transition: all 0.2s ease;
            `;

            // Store message_id for filtering artifacts
            const messageId = messageElement.dataset.messageId ||
                             messageElement.getAttribute('data-message-id') ||
                             this.extractMessageId(messageElement);

            artifactBtn.addEventListener('click', async (e) => {
                e.stopPropagation();
                console.log('[ChatUI] Artifact viewer clicked - opening artifacts for message:', messageId);

                // Show immediate feedback
                this.showCopyFeedback(messageElement, 'Opening artifacts...');

                try {
                    // Pass message_id to filter artifacts from this specific message
                    await this.showMessageArtifacts(messageId);
                    // Show success with delay
                    setTimeout(() => {
                        this.showCopyFeedback(messageElement, '✅ Message artifacts opened');
                    }, 1000);
                } catch (error) {
                    console.error('[ChatUI] Failed to open artifacts:', error);
                    this.showCopyFeedback(messageElement, '❌ Could not open artifacts');
                }
            });

            actionsDiv.appendChild(artifactBtn);
        }

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

            console.log('[ChatUI] Attempting to copy text:', textContent.substring(0, 50) + '...');

            // Try modern clipboard API first (requires HTTPS or localhost)
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(textContent);
                console.log('[ChatUI] Used modern clipboard API');
            } else {
                console.log('[ChatUI] Modern clipboard API not available, using fallback');

                // Fallback for non-secure contexts or older browsers
                const textArea = document.createElement('textarea');
                textArea.value = textContent;
                textArea.style.position = 'fixed';
                textArea.style.left = '-9999px';
                textArea.style.top = '-9999px';
                document.body.appendChild(textArea);
                textArea.select();
                textArea.setSelectionRange(0, textContent.length);

                // Try multiple methods
                let success = false;
                if (document.execCommand) {
                    try {
                        success = document.execCommand('copy');
                        console.log('[ChatUI] Used execCommand fallback, success:', success);
                    } catch (e) {
                        console.warn('[ChatUI] execCommand fallback failed:', e);
                    }
                }

                document.body.removeChild(textArea);

                if (!success) {
                    throw new Error('Fallback copy methods failed');
                }
            }

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
     * Load and display artifacts from multiple messages (shared core logic)
     */
    async _loadAndDisplayArtifactCollection(sessionId, messageIdFilter = null) {
        console.log(`[ChatUI] Loading artifact collection${messageIdFilter ? ` for message ${messageIdFilter}` : ' for entire session'}`);

        try {
            // Load artifacts with optional message_id filtering
            const artifacts = await this.loadArtifactsFromSessionHistory(sessionId, messageIdFilter);

            // Handle empty results
            if (!artifacts || artifacts.length === 0) {
                const emptyArtifacts = [{
                    type: 'info',
                    title: messageIdFilter ? 'No artifacts for this message' : 'No artifacts yet for this session',
                    content: messageIdFilter
                        ? 'This message did not generate any artifacts.\n\nArtifacts are typically code files, documents, or analysis results produced by workflows.'
                        : 'Artifacts generated during workflow execution will appear here.\n\nStart a conversation to see generated content such as code, documents, or analysis results.',
                    language: 'text'
                }];

                if (window.artifactDisplayManager) {
                    window.artifactDisplayManager.clearArtifacts();
                    window.artifactDisplayManager.displayArtifacts(emptyArtifacts);

                    const statusMsg = messageIdFilter ? 'No artifacts for this message' : 'No artifacts for this session';
                    window.updateStatus && window.updateStatus(statusMsg, 'info');
                }
                return;
            }

            // Display artifacts
            if (window.artifactDisplayManager) {
                window.artifactDisplayManager.clearArtifacts();
                window.artifactDisplayManager.displayArtifacts(artifacts);

                const realArtifactCount = artifacts.filter(art =>
                    art.type !== 'info' &&
                    !art.title?.includes('No artifacts')
                ).length;

                const scopeText = messageIdFilter ? 'from this message' : 'for this session';
                const statusMsg = realArtifactCount > 0
                    ? `Showing ${realArtifactCount} artifacts ${scopeText}`
                    : `No artifacts ${scopeText}`;
                window.updateStatus && window.updateStatus(statusMsg, 'info');
            }

        } catch (error) {
            console.error('[ChatUI] Failed to load artifact collection:', error);
            this.showErrorFallback();
        }
    }

    /**
     * Show artifacts from the current session in the sliding artifact panel
     */
    async showSessionArtifacts() {
        console.log('[ChatUI] Showing session artifacts in sliding panel');

        try {
            const currentSessionId = window.globalState?.currentChatSessionId;
            const currentWorkflow = window.globalState?.currentWorkflow;

            console.log(`[ChatUI] Current session: ${currentSessionId}, workflow: ${currentWorkflow}`);

            if (!currentSessionId) {
                console.log('[ChatUI] No active session to show artifacts');
                return;
            }

            // Reuse core logic with no message filter (shows entire session)
            await this._loadAndDisplayArtifactCollection(currentSessionId);

        } catch (error) {
            console.error('[ChatUI] Failed to show session artifacts:', error);
            this.showErrorFallback();
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
     * Load artifacts from session API with optional message_id filtering
     * Fetches current session data and extracts artifacts from it
     */
    async loadArtifactsFromSessionHistory(sessionId, messageId = null) {
        console.log(`[ChatUI] Loading artifacts for session: ${sessionId}${messageId ? `, message: ${messageId}` : ''}`);

        try {
            // Get current workflow to construct API URL
            const currentWorkflow = window.globalState?.currentWorkflow;
            if (!currentWorkflow) {
                console.warn('[ChatUI] No current workflow available');
                return null;
            }

            // Build session URL with optional message_id query param for filtering
            let sessionUrl = `/api/${currentWorkflow}/chat_history/${sessionId}`;
            if (messageId) {
                sessionUrl += `?message_id=${encodeURIComponent(messageId)}`;
            }
            console.log(`[ChatUI] Fetching session data from: ${sessionUrl}`);

            const sessionResponse = await fetch(sessionUrl);
            if (!sessionResponse.ok) {
                console.warn(`[ChatUI] Session API error: ${sessionResponse.status} - ${sessionResponse.statusText}`);
                return null;
            }

            const sessionData = await sessionResponse.json();
            const sessionArtifacts = sessionData.artifacts || [];

            console.log(`[ChatUI] Retrieved session with ${sessionArtifacts.length} artifacts${messageId ? ` for message ${messageId}` : ''}`);

            // Validate content to prevent garbage artifacts
            if (sessionArtifacts.length > 0) {
                const garbageCount = sessionArtifacts.filter(art =>
                    art.content && this.looksLikeTaskDescription(art.content)
                ).length;

                if (garbageCount > 0) {
                    console.warn(`[ChatUI] ${garbageCount}/${sessionArtifacts.length} artifacts contain task descriptions - filtering out`);
                    // Filter out task descriptions instead of rejecting all artifacts
                    const validArtifacts = sessionArtifacts.filter(art =>
                        !art.content || !this.looksLikeTaskDescription(art.content)
                    );
                    console.log(`[ChatUI] Keeping ${validArtifacts.length} valid artifacts`);
                    return validArtifacts;
                }

                return sessionArtifacts;
            }

            console.log(`[ChatUI] No artifacts in session ${sessionId}${messageId ? ` for message ${messageId}` : ''} (this is normal for new sessions)`);
            return null; // No artifacts (expected for fresh sessions)

        } catch (error) {
            console.error('[ChatUI] Failed to load artifacts from session API:', error);
            return null;
        }
    }

    /**
     * Check if content looks like task description garbage
     */
    looksLikeTaskDescription(content) {
        if (!content) return false;

        const lowerContent = content.toLowerCase();
        const taskPatterns = [
            /\bshould include\b/,
            /\bneed to.*?:/,
            /\bmust have\b/,
            /\bwill create\b/,
            /\bwill implement\b/,
            /\bcreate a\b.*?:\s*$/i,
            /\bthe component.*should\b/i,
            /\bthe code.*should\b/i,
            /\btypescript interface\b/i,
            /\blocal.*state.*management\b/i,
            /^[-*•]\s*implement\s/i,
            /^[-*•]\s*build\s/i
        ];

        return taskPatterns.some(pattern => pattern.test(lowerContent));
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
     * Show error fallback for artifact display
     */
    showErrorFallback() {
        const errorArtifacts = [{
            type: 'error',
            title: 'Unable to load artifacts',
            content: 'There was an error loading artifacts for this session.\nPlease try refreshing the page.',
            language: 'text'
        }];

        if (window.artifactDisplayManager) {
            window.artifactDisplayManager.displayArtifacts(errorArtifacts);
        }

        // Find last AI message for feedback
        const lastAIMessage = document.querySelector('.message.ai-message:last-child');
        if (lastAIMessage) {
            this.showCopyFeedback(lastAIMessage, '❌ Failed to load artifacts');
        }
    }

    /**
     * Retry last message (placeholder for implementation)
     */
    retryLastMessage() {
        console.log('[ChatUI] Retry functionality not implemented yet');
        // This would need to be connected to the main chat functionality
    }

    /**
     * Extract code blocks and content from message text
     */
    extractCodeFromContent(content) {
        const results = [];

        // Look for code blocks first (highest priority)
        const codeBlockRegex = /```(\w+)?\n([\s\S]*?)```/g;
        let match;
        while ((match = codeBlockRegex.exec(content)) !== null) {
            const codeContent = match[2].trim();
            // Skip empty blocks or very short blocks (likely not real code)
            if (codeContent.length < 10) {
                console.log('[ArtifactExtract] Skipping empty/short code block');
                continue;
            }
            results.push({
                type: 'code',
                language: match[1] || 'text',
                content: codeContent
            });
        }

        console.log(`[ArtifactExtract] Found ${results.length} code blocks in content`);

        // If no code blocks, look for structured content patterns (lists, structured text)
        if (results.length === 0) {
            // Look for well-formatted lists or instructions that aren't just template text
            const listRegex = /\n\s*[-*•]\s[^\n]{10,}|\d+\.\s[^\n]{20,}/g;
            const listMatches = content.match(listRegex);
            if (listMatches && listMatches.length > 2 && listMatches.join('').length > 100) {
                results.push({
                    type: 'document',
                    language: 'text',
                    content: listMatches.join('\n').trim()
                });
                console.log('[ArtifactExtract] Found substantial list content');
            }
        }

        console.log(`[ArtifactExtract] Extracted ${results.length} artifacts from content`);
        return results;
    }





    /**
     * Add message status indicator (placeholder implementation)
     */
    addMessageStatus(messageElement) {
        // Placeholder - status indicator not implemented yet
        // This could be used for delivery status, read status, etc.
    }

    /**
     * Add timestamp if not present (placeholder implementation)
     */
    addMessageTimestamp(messageElement) {
        // Placeholder - timestamp display not implemented yet
        // This could show message send/receive time
    }

    /**
     * Enhance message content formatting (placeholder implementation)
     */
    enhanceMessageContent(messageElement) {
        // Placeholder - content formatting not implemented yet
        // This could handle link previews, emoji parsing, etc.
    }

    /**
     * Add auto-scroll functionality (placeholder implementation)
     */
    addAutoScroll(container) {
        // Placeholder - auto-scroll not implemented yet
        // This could auto-scroll during message updates
    }

    /**
     * Show artifacts filtered by specific message_id
     */
    async showMessageArtifacts(messageId) {
        console.log('[ChatUI] Showing message artifacts for message_id:', messageId);

        try {
            const currentSessionId = window.globalState?.currentChatSessionId;

            if (!currentSessionId || !messageId) {
                console.warn('[ChatUI] Missing session_id or message_id');
                return;
            }

            // Reuse core logic with message_id filter
            await this._loadAndDisplayArtifactCollection(currentSessionId, messageId);

        } catch (error) {
            console.error('[ChatUI] Failed to show message artifacts:', error);
            this.showErrorFallback();
        }
    }

    /**
     * Extract message_id from message element (simplified - expects proper assignment)
     */
    extractMessageId(messageElement) {
        // Expects message_id to be set on DOM during session resumption and message creation
        return messageElement.dataset.messageId ||
               messageElement.getAttribute('data-message-id') ||
               null; // No synthetic fallback needed
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
