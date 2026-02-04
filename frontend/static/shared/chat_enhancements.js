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

            console.log('[ChatUI] Setting up artifact button for message element:', messageElement, 'messageId:', messageId);

            artifactBtn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const currentMessageId = messageElement.dataset.messageId ||
                    messageElement.getAttribute('data-message-id') ||
                    this.extractMessageId(messageElement);
                console.log('[ChatUI] Artifact viewer clicked - opening artifacts for message:', currentMessageId);
                console.log('[ChatUI] Message element attributes:', messageElement.attributes);
                console.log('[ChatUI] Message element dataset:', messageElement.dataset);

                // Show immediate feedback
                this.showCopyFeedback(messageElement, 'Opening artifacts...');

                try {
                    // Pass message_element to retrieve proper session context
                    await this.showMessageArtifacts(messageElement);
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

        // Edit button
        const editBtn = document.createElement('button');
        editBtn.innerHTML = '✏️';
        editBtn.title = 'Edit this message';
        editBtn.className = 'message-action-btn larger edit-message';
        editBtn.style.cssText = `
            background: rgba(255, 255, 255, 0.2);
            border: none;
            border-radius: 50%;
            width: 32px;
            height: 32px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s ease;
        `;

        editBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleMessageEdit(messageElement);
        });

        actionsDiv.appendChild(editBtn);

        // Delete button
        const deleteBtn = document.createElement('button');
        deleteBtn.innerHTML = '🗑️';
        deleteBtn.title = 'Delete this message';
        deleteBtn.className = 'message-action-btn larger delete-message';
        deleteBtn.style.cssText = `
            background: rgba(255, 255, 255, 0.2);
            border: none;
            border-radius: 50%;
            width: 32px;
            height: 32px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s ease;
        `;

        deleteBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.deleteIndividualMessage(messageElement);
        });

        actionsDiv.appendChild(deleteBtn);

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
     * Toggle message edit mode (simple inline edit)
     */
    toggleMessageEdit(messageElement) {
        const contentElement = messageElement.querySelector('.message-content');
        if (!contentElement) return;

        // If already editing, save it
        if (contentElement.contentEditable === 'true') {
            this.saveMessageEdit(messageElement);
            return;
        }

        // Enter edit mode
        contentElement.contentEditable = 'true';
        contentElement.classList.add('editing');
        contentElement.style.cssText += `
            outline: 2px solid #00d4ff;
            background: rgba(0, 212, 255, 0.1);
            border-radius: 8px;
            padding: 8px;
            min-height: 2em;
        `;
        contentElement.focus();

        // Update button appearance
        const editBtn = messageElement.querySelector('.edit-message');
        if (editBtn) {
            editBtn.innerHTML = '✅';
            editBtn.title = 'Save changes';
            editBtn.style.background = 'rgba(0, 255, 0, 0.3)';
        }

        // Add escape to cancel
        const handleKeys = (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.saveMessageEdit(messageElement);
                contentElement.removeEventListener('keydown', handleKeys);
            }
            if (e.key === 'Escape') {
                contentElement.textContent = contentElement.dataset.originalContent || contentElement.textContent;
                this.exitEditMode(messageElement);
                contentElement.removeEventListener('keydown', handleKeys);
            }
        };

        // Store original content
        if (!contentElement.dataset.originalContent) {
            contentElement.dataset.originalContent = contentElement.textContent;
        }

        contentElement.addEventListener('keydown', handleKeys);
    }

    /**
     * Exit edit mode without saving
     */
    exitEditMode(messageElement) {
        const contentElement = messageElement.querySelector('.message-content');
        if (!contentElement) return;

        contentElement.contentEditable = 'false';
        contentElement.classList.remove('editing');
        contentElement.style.outline = '';
        contentElement.style.background = '';
        contentElement.style.padding = '';

        const editBtn = messageElement.querySelector('.edit-message');
        if (editBtn) {
            editBtn.innerHTML = '✏️';
            editBtn.title = 'Edit this message';
            editBtn.style.background = 'rgba(255, 255, 255, 0.2)';
        }
    }

    /**
     * Internal helper to determine session IDs for message operations (edit/delete)
     * Handles both History and Workflow UI contexts.
     */
    _determineSessionIds(messageElement) {
        const workflowId = messageElement.dataset.workflow ||
            (window.globalState && window.globalState.currentWorkflow);

        const chatSessionId = messageElement.dataset.sessionId ||
            window.selectedSessionId ||
            (window.globalState && window.globalState.currentChatSessionId);

        let historySessionId = window.historySessionId;

        // Fallback for Workflow mode where historySessionId might not be globally set
        if (!historySessionId && workflowId && window.sessionManager) {
            historySessionId = window.sessionManager.getInfrastructureSession(workflowId);
        }

        console.log(`[ChatUI] Determined session IDs for operation:`, {
            workflowId,
            chatSessionId,
            historySessionId
        });

        return { historySessionId, chatSessionId, workflowId };
    }

    /**
     * Save message edit to backend
     */
    async saveMessageEdit(messageElement) {
        const contentElement = messageElement.querySelector('.message-content');
        if (!contentElement) return;

        const newContent = contentElement.textContent.trim();
        const messageId = messageElement.dataset.messageId ||
            messageElement.getAttribute('data-message-id') ||
            this.extractMessageId(messageElement);

        if (!newContent) {
            this.showCopyFeedback(messageElement, '❌ Content cannot be empty');
            return;
        }

        this.showCopyFeedback(messageElement, 'Saving...');

        try {
            const { historySessionId, chatSessionId } = this._determineSessionIds(messageElement);

            if (!historySessionId || !chatSessionId) {
                console.error('[ChatUI] Missing session IDs:', { historySessionId, chatSessionId, messageId });
                throw new Error('Could not determine session IDs for saving');
            }

            // Reuse history manager's save logic if available, or fetch directly
            if (window.historyManager && window.historyManager.saveMessageEdit) {
                await window.historyManager.saveMessageEdit(chatSessionId, messageId, newContent);
            } else {
                const response = await fetch(`/api/history/${historySessionId}/chat_session/${chatSessionId}/message/${messageId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content: newContent })
                });
                if (!response.ok) throw new Error('Failed to update message');
            }

            this.showCopyFeedback(messageElement, '✅ Saved');
            contentElement.dataset.originalContent = newContent;
            this.exitEditMode(messageElement);

        } catch (error) {
            console.error('[ChatUI] Failed to save message edit:', error);
            this.showCopyFeedback(messageElement, '❌ Failed to save');

            // If we have updateStatus, use it for clearer error reporting
            if (window.updateStatus) {
                window.updateStatus(`Failed to save message: ${error.message}`, 'error');
            }
        }
    }

    /**
     * Delete an individual message
     */
    async deleteIndividualMessage(messageElement) {
        if (!(await window.showConfirm('Delete Message', 'Are you sure you want to delete this message? This action cannot be undone.', { type: 'danger', confirmText: 'Delete' }))) {
            return;
        }

        const messageId = messageElement.dataset.messageId ||
            messageElement.getAttribute('data-message-id') ||
            this.extractMessageId(messageElement);

        this.showCopyFeedback(messageElement, 'Deleting...');

        try {
            const { historySessionId, chatSessionId } = this._determineSessionIds(messageElement);

            if (!historySessionId || !chatSessionId) {
                console.error('[ChatUI] Missing session IDs for deletion:', { historySessionId, chatSessionId, messageId });
                throw new Error('Could not determine session IDs for deletion');
            }

            await window.apiUtils.deleteMessage(historySessionId, chatSessionId, messageId);

            // Animate removal
            messageElement.style.opacity = '0';
            messageElement.style.transform = 'translateX(20px)';
            messageElement.style.transition = 'all 0.3s ease';

            setTimeout(() => {
                messageElement.remove();
                if (window.updateStatus) {
                    window.updateStatus('Message deleted successfully', 'success');
                }
            }, 300);

        } catch (error) {
            console.error('[ChatUI] Failed to delete message:', error);
            this.showCopyFeedback(messageElement, '❌ Failed to delete');

            if (window.updateStatus) {
                window.updateStatus(`Failed to delete message: ${error.message}`, 'error');
            }
        }
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

            // Display artifacts - check if panel is already open to avoid reloading
            if (window.artifactDisplayManager) {
                const isPanelOpen = window.artifactDisplayManager.isPanelOpen();

                if (isPanelOpen && window.artifactDisplayManager.lastArtifacts) {
                    // Panel is already open, just refresh with new data
                    window.artifactDisplayManager.displayArtifacts(artifacts);
                } else {
                    // Panel is closed or no previous artifacts, open it
                    window.artifactDisplayManager.displayArtifacts(artifacts);
                }

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
            const currentSessionId = window.sessionManager.getInfrastructureSession(window.globalState?.currentWorkflow);
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

            // ✅ SESSION-CENTRIC: Use centralized session utility
            console.log(`[ChatUI] Fetching session data for session: ${sessionId}${messageId ? `, message: ${messageId}` : ''}`);

            const sessionData = await window.apiUtils.getChatSessionDetails(window.sessionManager.getInfrastructureSession(window.globalState?.currentWorkflow), sessionId);
            console.log(`[ChatUI] Full session data received:`, sessionData);

            const sessionArtifacts = sessionData.artifacts || [];
            console.log(`[ChatUI] Retrieved session with ${sessionArtifacts.length} artifacts${messageId ? ` for message ${messageId}` : ''}`);
            console.log(`[ChatUI] Artifact details:`, sessionArtifacts);

            // If filtering by message_id, only return artifacts from that message
            let filteredArtifacts = sessionArtifacts;
            if (messageId) {
                console.log(`[ChatUI] Filtering artifacts for message_id: ${messageId}`);
                filteredArtifacts = sessionArtifacts.filter(art => {
                    const matches = art.message_id === messageId;
                    console.log(`[ChatUI] Artifact ${art.id} message_id: ${art.message_id}, matches: ${matches}`);
                    return matches;
                });
                console.log(`[ChatUI] After filtering: ${filteredArtifacts.length} artifacts for message ${messageId}`);
            }

            // Validate content to prevent garbage artifacts
            if (filteredArtifacts.length > 0) {
                const garbageCount = filteredArtifacts.filter(art =>
                    art.content && this.looksLikeTaskDescription(art.content)
                ).length;

                if (garbageCount > 0) {
                    console.warn(`[ChatUI] ${garbageCount}/${filteredArtifacts.length} artifacts contain task descriptions - filtering out`);
                    // Filter out task descriptions instead of rejecting all artifacts
                    const validArtifacts = filteredArtifacts.filter(art =>
                        !art.content || !this.looksLikeTaskDescription(art.content)
                    );
                    console.log(`[ChatUI] Keeping ${validArtifacts.length} valid artifacts`);
                    return validArtifacts;
                }

                return filteredArtifacts;
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
     * Updated to use robust session ID discovery
     */
    async showMessageArtifacts(messageElement) {
        const messageId = messageElement.dataset.messageId ||
            messageElement.getAttribute('data-message-id') ||
            this.extractMessageId(messageElement);

        console.log('[ChatUI] Showing message artifacts for message_id:', messageId);

        try {
            const { historySessionId, chatSessionId } = this._determineSessionIds(messageElement);

            if (!chatSessionId || !messageId) {
                console.warn('[ChatUI] Missing session_id or message_id', { chatSessionId, messageId });
                return;
            }

            // Reuse core logic with message_id filter
            // Note: _loadAndDisplayArtifactCollection expects the "chat session id" as its first argument
            // which it then passes to loadArtifactsFromSessionHistory
            await this._loadAndDisplayArtifactCollection(chatSessionId, messageId);

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

    /**
     * Adjust layout for different screen sizes
     */
    adjustLayoutForScreenSize() {
        const isMobile = window.innerWidth < 768;
        const isTablet = window.innerWidth >= 768 && window.innerWidth < 1024;

        // Adjust message container height for mobile
        const messageContainer = document.getElementById('message-container');
        if (messageContainer) {
            if (isMobile) {
                messageContainer.style.maxHeight = 'calc(100vh - 200px)';
            } else {
                messageContainer.style.maxHeight = 'calc(100vh - 160px)';
            }
        }

        // Adjust input area for mobile
        const inputArea = document.querySelector('.input-area');
        if (inputArea) {
            if (isMobile) {
                inputArea.style.padding = '8px';
            } else {
                inputArea.style.padding = '12px 20px';
            }
        }

        // Adjust sidebar visibility for tablet/mobile
        const sidebar = document.getElementById('sidebar');
        if (sidebar) {
            if (isMobile) {
                sidebar.style.width = '280px'; // Slightly narrower on mobile
            } else {
                sidebar.style.width = '320px'; // Default width
            }
        }

        console.log(`[ChatUI] Layout adjusted for screen size: ${window.innerWidth}px (${isMobile ? 'mobile' : isTablet ? 'tablet' : 'desktop'})`);
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
});

// Export for global access
window.ChatUIEnhancements = ChatUIEnhancements;
