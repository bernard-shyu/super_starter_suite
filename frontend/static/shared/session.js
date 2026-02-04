/**
 * SRR Session Management - Single Registry Responsibility
 *
 * Implements the Single Registry Responsibility (SRR) pattern to solve:
 * 1. Frontend-Backend Coupling: Clear session scope separation
 * 2. Session Class Architecture: Proper inheritance hierarchy
 * 3. MVC Principle Violations: Clean View/Model separation
 * 4. Race Condition Prevention: Centralized atomic operations
 */

// ============================================================================
// SESSION REGISTRY - SINGLE SOURCE OF TRUTH
// ============================================================================

/**
 * Session Registry - Single Source of Truth for all session information
 * Solves race conditions by providing atomic operations on session state
 */
window.sessionRegistry = {
    // Infrastructure sessions (workflow-level, persistent across UI changes)
    // These represent workflow execution infrastructure that survives UI navigation
    infrastructure: {
        // workflowId → infrastructureSessionId mapping
    },

    // Active chat sessions (user-level, current conversation context)
    // These represent the user's current conversational context that changes with focus
    active: {
        // userId → activeChatSessionId mapping
    },

    // Session objects cache (in-memory instances for complex operations)
    // Provides direct access to session class instances with proper lifecycle
    objects: {
        // sessionId → sessionObject mapping
    }
};

// ============================================================================
// SESSION MANAGER API - SINGLE ACCESS POINT
// ============================================================================

/**
 * Session Manager - Single API for all session operations
 * Provides centralized access patterns and prevents direct registry manipulation
 */
window.sessionManager = {
    // Infrastructure session management (workflow-level)
    getInfrastructureSession(workflowId) {
        return window.sessionRegistry.infrastructure[workflowId];
    },

    setInfrastructureSession(workflowId, sessionId, sessionObject) {
        window.sessionRegistry.infrastructure[workflowId] = sessionId;
        if (sessionObject) {
            window.sessionRegistry.objects[sessionId] = sessionObject;
        }
    },

    // Session object access (direct instance operations)
    getSessionObject(sessionId) {
        return window.sessionRegistry.objects[sessionId];
    },

    // Registry utilities
    clearAll() {
        window.sessionRegistry.infrastructure = {};
        window.sessionRegistry.active = {};
        window.sessionRegistry.objects = {};
    },

    getRegistryStatus() {
        return {
            infrastructureCount: Object.keys(window.sessionRegistry.infrastructure).length,
            activeCount: Object.keys(window.sessionRegistry.active).length,
            objectsCount: Object.keys(window.sessionRegistry.objects).length,
            infrastructure: { ...window.sessionRegistry.infrastructure },
            active: { ...window.sessionRegistry.active }
        };
    }
};

// ============================================================================
// SESSION CLASS HIERARCHY - FOLLOWING BACKEND PATTERNS
// ============================================================================

/**
 * ChatBotSession - Abstract Base Class
 * Common session functionality following backend patterns
 */
class ChatBotSession extends EventTarget {
    constructor(workflowId, sessionId = null) {
        super();
        this.workflowId = workflowId;
        this.sessionId = sessionId;
        this.messages = [];
        this.metadata = {};
        this.isActive = false;
        this.createdAt = new Date();
        this.lastActivity = new Date();
    }

    // Event emission helper
    emit(eventName, data) {
        const event = new CustomEvent(eventName, { detail: data });
        this.dispatchEvent(event);
    }

    // COMMON METHODS - Used by all session types
    async loadFromBackend() {
        const endpoint = this.sessionId
            ? `/${this.workflowId}/chat_history/${this.sessionId}`
            : `/${this.workflowId}/chat_history`;

        try {
            const response = await fetch(endpoint);
            const data = await response.json();

            if (this.sessionId) {
                // Loading specific session
                this.messages = data.messages || [];
                this.metadata = data.metadata || {};
            } else {
                // Loading session list for workflow
                return data; // Return list for browsing
            }

            this.emit('loaded', data);
            return data;
        } catch (error) {
            console.error(`[ChatBotSession] Failed to load from backend:`, error);
            this.emit('error', { type: 'load_failed', error });
            throw error;
        }
    }

    async saveToBackend() {
        if (!this.sessionId) {
            throw new Error('Cannot save session without sessionId');
        }

        const endpoint = `/api/session/${this.sessionId}`;
        const data = this.getData();

        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const result = await response.json();
            this.lastActivity = new Date();
            this.emit('saved', result);
            return result;
        } catch (error) {
            console.error(`[ChatBotSession] Failed to save to backend:`, error);
            this.emit('error', { type: 'save_failed', error });
            throw error;
        }
    }

    addMessage(message) {
        this.messages.push({
            ...message,
            timestamp: message.timestamp || new Date().toISOString()
        });
        this.lastActivity = new Date();

        // Auto-save for active sessions
        if (this.isActive) {
            this.saveToBackend().catch(error => {
                console.warn('[ChatBotSession] Auto-save failed:', error);
            });
        }

        this.emit('messageAdded', message);
    }

    validatePermissions(operation) {
        const permissions = this.getPermissions();
        return permissions[operation] || false;
    }

    getHealthStatus() {
        return {
            sessionId: this.sessionId,
            workflowId: this.workflowId,
            messageCount: this.messages.length,
            isActive: this.isActive,
            createdAt: this.createdAt,
            lastActivity: this.lastActivity,
            permissions: this.getPermissions()
        };
    }

    // ABSTRACT METHODS - Implemented by subclasses
    getPermissions() {
        throw new Error('Subclasses must implement getPermissions()');
    }

    handleMessage(message) {
        throw new Error('Subclasses must implement handleMessage()');
    }

    getData() {
        return {
            sessionId: this.sessionId,
            workflowId: this.workflowId,
            messages: this.messages,
            metadata: this.metadata,
            permissions: this.getPermissions()
        };
    }

    dispose() {
        this.messages = [];
        this.metadata = {};
        this.removeAllListeners();
    }
}

// ============================================================================
// WORKFLOW SESSION - ACTIVE CONVERSATION MANAGEMENT
// ============================================================================

/**
 * WorkflowSession - Active conversation management
 * Handles live workflow conversations with real-time updates
 */
class WorkflowSession extends ChatBotSession {
    constructor(workflowId, sessionId) {
        super(workflowId, sessionId);
        this.isActive = true;
        this.websocket = null;
        this.workflowState = {}; // Current workflow execution state
        this.setupWebSocketHandlers();
    }

    getPermissions() {
        return {
            read: true,       // Can read messages
            write: true,      // Can send messages
            delete: true,     // Can delete session
            execute: true     // Can run workflows
        };
    }

    // Override loadFromBackend for workflow-specific logic
    async loadFromBackend() {
        try {
            if (this.sessionId) {
                // Loading specific session - use api.js method
                const data = await window.apiUtils.getChatSessionDetails(this.sessionId, this.sessionId);
                this.messages = data.messages || [];
                this.metadata = data.metadata || {};
                this.emit('loaded', data);
                return data;
            } else {
                // Loading session list for workflow - use api.js method
                const data = await window.apiUtils.getWorkflowSessions(this.sessionId);
                return data; // Return list for browsing
            }
        } catch (error) {
            console.error(`[WorkflowSession] Failed to load from backend:`, error);
            this.emit('error', { type: 'load_failed', error });
            throw error;
        }
    }

    async connectWebSocket() {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            return; // Already connected
        }

        const wsUrl = `/api/workflow/${this.sessionId}/stream`;

        return new Promise((resolve, reject) => {
            this.websocket = new WebSocket(wsUrl);

            this.websocket.onopen = () => {
                console.log(`[WorkflowSession] WebSocket connected for ${this.sessionId}`);
                this.emit('websocketConnected');
                resolve();
            };

            this.websocket.onerror = (error) => {
                console.error(`[WorkflowSession] WebSocket error for ${this.sessionId}:`, error);
                this.emit('websocketError', error);
                reject(error);
            };

            this.websocket.onclose = () => {
                console.log(`[WorkflowSession] WebSocket closed for ${this.sessionId}`);
                this.emit('websocketDisconnected');
            };

            this.websocket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                } catch (error) {
                    console.error('[WorkflowSession] Failed to parse WebSocket message:', error);
                }
            };
        });
    }

    async sendMessage(userMessage) {
        if (!this.validatePermissions('write')) {
            throw new Error('Insufficient permissions to send messages');
        }

        const message = {
            role: 'user',
            content: userMessage,
            timestamp: new Date().toISOString()
        };

        this.addMessage(message);

        // Send via WebSocket for real-time processing
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify(message));
        } else {
            console.warn('[WorkflowSession] WebSocket not available, message stored locally only');
        }
    }

    handleMessage(message) {
        // Handle real-time workflow messages
        switch (message.type) {
            case 'workflow_progress':
                this.workflowState = { ...this.workflowState, ...message.data };
                this.emit('workflowProgress', message.data);
                break;

            case 'ai_response':
                this.addMessage({
                    role: 'ai',
                    content: message.content,
                    timestamp: new Date().toISOString()
                });
                break;

            case 'workflow_complete':
                this.emit('workflowComplete', message.data);
                break;

            case 'error':
                this.emit('error', message.data);
                break;

            default:
                console.log(`[WorkflowSession] Unhandled message type: ${message.type}`);
        }
    }

    setupWebSocketHandlers() {
        // WebSocket setup is handled in connectWebSocket()
        // This method can be extended for additional setup if needed
    }

    async disconnect() {
        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
        }
        await super.destroy();
    }

    getWorkflowState() {
        return { ...this.workflowState };
    }
}

// ============================================================================
// HISTORY SESSION - STATIC HISTORY BROWSING
// ============================================================================

/**
 * HistorySession - Static history browsing
 * Handles read-only access to historical conversation data
 */
class HistorySession extends ChatBotSession {
    constructor(workflowId) {
        super(workflowId, null); // No specific session for browsing
        this.isActive = false; // Static browsing only
        this.selectedSessionId = null;
        this.allSessions = [];
    }

    getPermissions() {
        return {
            read: true,       // Can read history
            write: false,     // Cannot add new messages
            delete: false,    // Cannot delete historical sessions
            execute: false    // Cannot run workflows
        };
    }

    // Override loadFromBackend for history-specific logic
    async loadFromBackend() {
        // For history sessions, we need a history session first
        if (!this.historySessionId) {
            await this.createHistorySession();
        }

        try {
            if (this.sessionId) {
                // ✅ SRR FIX: Use centralized API utilities for session data
                const data = await window.apiUtils.getHistorySessionData(this.historySessionId, this.sessionId);
                this.messages = data.messages || [];
                this.metadata = data.metadata || {};
                this.emit('loaded', data);
                return data;
            } else {
                // ✅ SRR FIX: Use centralized API utilities for workflow stats
                const data = await window.apiUtils.getWorkflowHistoryStats(this.historySessionId, this.workflowId);
                this.allSessions = data.sessions || [];
                console.log(`[HistorySession] Loaded ${this.allSessions.length} sessions from backend`);
                return this.allSessions;
            }
        } catch (error) {
            console.error(`[HistorySession] Failed to load from backend:`, error);
            this.emit('error', { type: 'load_failed', error });
            throw error;
        }
    }

    async createHistorySession() {
        try {
            // ✅ SRR FIX: Use centralized API utilities instead of direct fetch
            const data = await window.apiUtils.createHistorySession();
            this.historySessionId = data.session_id;

            console.log(`[HistorySession] Created history session: ${this.historySessionId}`);
            return this.historySessionId;
        } catch (error) {
            console.error('[HistorySession] Failed to create history session:', error);
            throw error;
        }
    }

    async loadAllSessions() {
        if (!this.validatePermissions('read')) {
            throw new Error('Insufficient permissions to read history');
        }

        this.allSessions = await this.loadFromBackend(); // Will call overridden method
        this.emit('sessionsLoaded', this.allSessions);
        return this.allSessions;
    }

    async selectSession(sessionId) {
        if (!this.validatePermissions('read')) {
            throw new Error('Insufficient permissions to select session');
        }

        this.selectedSessionId = sessionId;
        this.sessionId = sessionId; // Set for loading
        await this.loadFromBackend(); // Load the specific session data

        this.emit('sessionSelected', {
            sessionId,
            messages: this.messages,
            metadata: this.metadata
        });

        return {
            sessionId,
            messages: this.messages,
            metadata: this.metadata
        };
    }

    handleMessage(message) {
        // History sessions don't handle dynamic messages
        // They only load static historical data
        console.warn('[HistorySession] Ignoring dynamic message in history context:', message);
    }

    getCurrentSessionData() {
        if (!this.selectedSessionId) {
            return null;
        }
        return {
            selectedSessionId: this.selectedSessionId,
            messages: this.messages,
            metadata: this.metadata
        };
    }

    async clearSelection() {
        this.selectedSessionId = null;
        this.sessionId = null;
        this.messages = [];
        this.metadata = {};
        this.emit('selectionCleared');
    }

    getAllSessions() {
        return [...this.allSessions];
    }
}

// ============================================================================
// SESSION LIFECYCLE MANAGEMENT
// ============================================================================

/**
 * Session Factory - Creates appropriate session types
 */
window.sessionFactory = {
    createWorkflowSession(workflowId, sessionId) {
        const session = new WorkflowSession(workflowId, sessionId);
        // Register in session manager
        window.sessionManager.setInfrastructureSession(workflowId, sessionId, session);
        return session;
    },

    createHistorySession(workflowId) {
        return new HistorySession(workflowId);
    }
};

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        ChatBotSession,
        WorkflowSession,
        HistorySession
    };
}
