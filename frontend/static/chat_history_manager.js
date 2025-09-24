/**
 * Chat History Manager
 * Handles the chat history interface functionality
 */
class ChatHistoryManager {
    constructor() {
        this.currentSession = null;
        this.sessions = [];
        this.filteredSessions = [];
        this.currentFilter = 'all';
        this.searchQuery = '';

        this.init();
    }

    async init() {
        console.log('[ChatHistory] Initializing Chat History Manager');
        this.bindEvents();
        await this.loadSessions();
        this.updateStats();
    }

    bindEvents() {
        // Search functionality
        const searchInput = document.getElementById('session-search');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.searchQuery = e.target.value.toLowerCase();
                this.filterSessions();
            });
        }

        // Filter buttons
        const filterButtons = document.querySelectorAll('.filter-btn[data-filter]');
        filterButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const filter = e.target.dataset.filter;
                this.setFilter(filter);
            });
        });

        // Action buttons
        document.getElementById('new-session-btn')?.addEventListener('click', () => this.createNewSession());
        document.getElementById('resume-chat-btn')?.addEventListener('click', () => this.resumeChat());
        document.getElementById('export-chat-btn')?.addEventListener('click', () => this.exportChat());
        document.getElementById('delete-session-btn')?.addEventListener('click', () => this.deleteSession());
    }

    async loadSessions() {
        try {
            console.log('[ChatHistory] Loading chat sessions');
            const response = await fetch('/api/chat_history/sessions');

            if (!response.ok) {
                throw new Error(`Failed to load sessions: ${response.status}`);
            }

            const data = await response.json();
            this.sessions = data.sessions || [];
            this.filteredSessions = [...this.sessions];

            console.log(`[ChatHistory] Loaded ${this.sessions.length} sessions`);
            this.renderSessions();

        } catch (error) {
            console.error('[ChatHistory] Error loading sessions:', error);
            this.showError('Failed to load chat sessions');
        }
    }

    renderSessions() {
        const container = document.getElementById('sessions-list');
        if (!container) return;

        if (this.filteredSessions.length === 0) {
            if (this.sessions.length === 0) {
                container.innerHTML = '<div class="empty-state"><h3>📭 No Chat Sessions</h3><p>Your chat history will appear here</p></div>';
            } else {
                container.innerHTML = '<div class="empty-state"><h3>🔍 No Results</h3><p>No sessions match your search</p></div>';
            }
            return;
        }

        const sessionsHtml = this.filteredSessions.map(session => this.createSessionHtml(session)).join('');
        container.innerHTML = sessionsHtml;

        // Bind click events to session items
        container.querySelectorAll('.session-item').forEach(item => {
            item.addEventListener('click', () => {
                const sessionId = item.dataset.sessionId;
                this.selectSession(sessionId);
            });
        });
    }

    createSessionHtml(session) {
        const date = new Date(session.created_at).toLocaleDateString();
        const time = new Date(session.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        // Use title in preview instead of non-existent messages array
        const preview = session.title || 'Untitled Conversation';

        return `
            <div class="session-item" data-session-id="${session.session_id}">
                <div class="session-header">
                    <span class="session-workflow">${this.formatWorkflowName(session.workflow_type)}</span>
                    <span class="session-date">${date} ${time}</span>
                </div>
                <div class="session-preview">${this.truncateText(preview, 60)}</div>
                <div class="session-meta">
                    <span>${session.message_count || 0} messages</span>
                    <span>${session.session_id.substring(0, 8)}</span>
                </div>
            </div>
        `;
    }

    formatWorkflowName(workflowType) {
        return workflowType.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    truncateText(text, maxLength) {
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }

    selectSession(sessionId) {
        // Update UI selection
        document.querySelectorAll('.session-item').forEach(item => {
            item.classList.remove('selected');
        });
        document.querySelector(`[data-session-id="${sessionId}"]`)?.classList.add('selected');

        // Find and set current session
        this.currentSession = this.sessions.find(s => s.session_id === sessionId);

        if (this.currentSession) {
            this.renderChatMessages();
            this.updateSessionTitle();
        }
    }

    renderChatMessages() {
        const container = document.getElementById('chat-content');
        if (!container || !this.currentSession) return;

        if (!this.currentSession.messages || this.currentSession.messages.length === 0) {
            container.innerHTML = '<div class="empty-state"><h3>💬 Empty Session</h3><p>This chat session has no messages yet</p></div>';
            return;
        }

        const messagesHtml = this.currentSession.messages.map(message => this.createMessageHtml(message)).join('');

        container.innerHTML = `
            <div class="messages-container">
                ${messagesHtml}
            </div>
            <div class="resume-chat">
                <h3>🔄 Resume This Conversation</h3>
                <p>Continue chatting with ${this.formatWorkflowName(this.currentSession.workflow_type)}</p>
                <button class="resume-btn" onclick="window.chatHistoryManager.resumeChat()">▶️ Resume Chat</button>
            </div>
        `;

        // Scroll to bottom
        const messagesContainer = container.querySelector('.messages-container');
        if (messagesContainer) {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    }

    createMessageHtml(message) {
        const timestamp = new Date(message.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        const isUser = message.role === 'user';

        return `
            <div class="message ${isUser ? 'user' : 'ai'}">
                <div class="message-header">
                    <span class="message-sender">${isUser ? 'You' : 'AI'}</span>
                    <span class="message-timestamp">${timestamp}</span>
                </div>
                <div class="message-content">${this.formatMessageContent(message.content)}</div>
            </div>
        `;
    }

    formatMessageContent(content) {
        // Basic HTML sanitization and formatting
        return content
            .replace(/\n/g, '<br>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/```(.*?)```/gs, '<pre><code>$1</code></pre>')
            .replace(/`(.*?)`/g, '<code>$1</code>');
    }

    updateSessionTitle() {
        const titleElement = document.getElementById('current-session-title');
        if (titleElement && this.currentSession) {
            const workflowName = this.formatWorkflowName(this.currentSession.workflow_type);
            const date = new Date(this.currentSession.created_at).toLocaleDateString();
            titleElement.textContent = `${workflowName} - ${date}`;
        }
    }

    setFilter(filter) {
        this.currentFilter = filter;

        // Update button states
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-filter="${filter}"]`)?.classList.add('active');

        this.filterSessions();
    }

    filterSessions() {
        let filtered = [...this.sessions];

        // Apply time filter
        if (this.currentFilter !== 'all') {
            const now = new Date();
            filtered = filtered.filter(session => {
                const sessionDate = new Date(session.created_at);
                switch (this.currentFilter) {
                    case 'today':
                        return sessionDate.toDateString() === now.toDateString();
                    case 'week':
                        const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
                        return sessionDate >= weekAgo;
                    case 'month':
                        const monthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
                        return sessionDate >= monthAgo;
                    default:
                        return true;
                }
            });
        }

        // Apply search filter
        if (this.searchQuery) {
            filtered = filtered.filter(session => {
                const workflowMatch = session.workflow_type.toLowerCase().includes(this.searchQuery);
                const messageMatch = session.messages?.some(msg =>
                    msg.content.toLowerCase().includes(this.searchQuery)
                );
                return workflowMatch || messageMatch;
            });
        }

        this.filteredSessions = filtered;
        this.renderSessions();
    }

    updateStats() {
        const totalSessions = this.sessions.length;
        const totalMessages = this.sessions.reduce((sum, session) => sum + (session.messages?.length || 0), 0);

        document.getElementById('total-sessions').textContent = `${totalSessions} Sessions`;
        document.getElementById('total-messages').textContent = `${totalMessages} Messages`;
    }

    async createNewSession() {
        // Navigate back to main chat interface
        if (window.showChatInterface) {
            window.showChatInterface();
        } else {
            // Fallback: navigate to main page
            window.location.href = '/';
        }
    }

    resumeChat() {
        if (!this.currentSession) return;

        // Use the enhanced workflow-aware session resumption
        console.log(`[ChatHistory] Resuming session ${this.currentSession.session_id} for workflow ${this.currentSession.workflow_type}`);

        // Store session info for potential cross-tab resumption
        sessionStorage.setItem('resumeSession', JSON.stringify({
            sessionId: this.currentSession.session_id,
            workflowType: this.currentSession.workflow_type
        }));

        // Use workflow-aware resumption that includes workflow context
        if (window.resumeWorkflowSession) {
            window.resumeWorkflowSession(this.currentSession.session_id, this.currentSession.workflow_type);
        } else {
            // Fallback to basic chat interface (should not happen with Phase 4.6)
            console.warn('[ChatHistory] resumeWorkflowSession not available, using fallback');
            if (window.showChatInterface) {
                window.showChatInterface(this.currentSession.session_id);
            } else {
                window.location.href = '/';
            }
        }
    }

    async exportChat() {
        if (!this.currentSession) return;

        try {
            const exportData = {
                session: this.currentSession,
                exported_at: new Date().toISOString(),
                format: 'json'
            };

            const blob = new Blob([JSON.stringify(exportData, null, 2)], {type: 'application/json'});
            const url = URL.createObjectURL(blob);

            const a = document.createElement('a');
            a.href = url;
            a.download = `chat-session-${this.currentSession.session_id.substring(0, 8)}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

        } catch (error) {
            console.error('[ChatHistory] Export failed:', error);
            this.showError('Failed to export chat session');
        }
    }

    async deleteSession() {
        if (!this.currentSession) return;

        if (!confirm(`Are you sure you want to delete this chat session? This action cannot be undone.`)) {
            return;
        }

        try {
            const response = await fetch(`/api/chat_history/sessions/${this.currentSession.session_id}`, {
                method: 'DELETE'
            });

            if (!response.ok) {
                throw new Error(`Failed to delete session: ${response.status}`);
            }

            // Remove from local arrays
            this.sessions = this.sessions.filter(s => s.session_id !== this.currentSession.session_id);
            this.filteredSessions = this.filteredSessions.filter(s => s.session_id !== this.currentSession.session_id);

            // Clear current session
            this.currentSession = null;

            // Update UI
            this.renderSessions();
            this.updateStats();
            document.getElementById('chat-content').innerHTML = '<div class="empty-state"><h3>🗑️ Session Deleted</h3><p>The chat session has been permanently removed</p></div>';

        } catch (error) {
            console.error('[ChatHistory] Delete failed:', error);
            this.showError('Failed to delete chat session');
        }
    }

    showError(message) {
        // Create error notification
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-notification';
        errorDiv.innerHTML = `
            <div style="background: rgba(244, 67, 54, 0.9); color: white; padding: 10px; border-radius: 5px; margin: 10px;">
                ❌ ${message}
            </div>
        `;

        document.body.appendChild(errorDiv);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.parentNode.removeChild(errorDiv);
            }
        }, 5000);
    }

    // Refresh sessions - alias for loadSessions that also updates stats
    async refreshSessions() {
        console.log('[ChatHistory] Refreshing sessions');
        await this.loadSessions();
        this.updateStats();
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // The ChatHistoryManager will be initialized when the chat history UI is loaded
    console.log('[ChatHistory] Chat History Manager ready');
});
