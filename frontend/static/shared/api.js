/**
 * Centralized API Utilities
 *
 * Provides unified session creation and management across the frontend for
 * History and RAG/Generate APIs. Eliminates duplicate fetch calls and ensures
 * consistent error handling.
 */

// Global API utilities namespace
window.apiUtils = window.apiUtils || {};

/**
 * HISTORY API UTILITIES
 */

/**
 * Create a new history session for browsing chat history
 *
 * @returns {Promise<object>} History session data with session_id
 */
window.apiUtils.createHistorySession = async function () {
    try {
        const response = await fetch('/api/history/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({})
        });

        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            throw new Error(`History session creation failed: ${response.status} ${response.statusText} - ${errorText}`);
        }

        const sessionData = await response.json();

        if (!sessionData.session_id) {
            throw new Error('History session creation response missing session_id');
        }

        return sessionData;

    } catch (error) {
        console.error(`History session creation failed:`, error);
        throw error;
    }
};

/**
 * Get workflow sessions list for Workflow UI
 *
 * @param {string} infrastructureSessionId - Workflow infrastructure session ID
 * @returns {Promise<array>} List of chat sessions for the workflow
 */
window.apiUtils.getWorkflowSessions = async function (infrastructureSessionId) {
    if (!infrastructureSessionId) {
        throw new Error('Infrastructure session ID is required');
    }

    try {
        const response = await fetch(`/api/workflow/${infrastructureSessionId}/sessions`);

        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            throw new Error(`Workflow sessions retrieval failed: ${response.status} ${response.statusText} - ${errorText}`);
        }

        const sessionsData = await response.json();
        return sessionsData.sessions || [];

    } catch (error) {
        console.error(`Workflow sessions retrieval failed:`, error);
        throw error;
    }
};

/**
 * Get history session data for a specific chat session
 *
 * @param {string} historySessionId - History infrastructure session ID
 * @param {string} chatSessionId - Chat session ID to retrieve
 * @returns {Promise<object>} Chat session data with messages and artifacts
 */
window.apiUtils.getHistorySessionData = async function (historySessionId, chatSessionId) {
    if (!historySessionId || !chatSessionId) {
        throw new Error('Both history session ID and chat session ID are required');
    }

    try {
        const response = await fetch(`/api/history/${historySessionId}/chat_session/${chatSessionId}`);

        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            throw new Error(`History session data retrieval failed: ${response.status} ${response.statusText} - ${errorText}`);
        }

        const sessionData = await response.json();
        return sessionData;

    } catch (error) {
        console.error(`History session data retrieval failed for ${chatSessionId}:`, error);
        throw error;
    }
};

/**
 * Get workflow-specific history statistics
 *
 * @param {string} sessionId - History session ID
 * @param {string} workflowId - Workflow ID to get stats for
 * @returns {Promise<object>} Workflow history statistics
 */
window.apiUtils.getWorkflowHistoryStats = async function (sessionId, workflowId) {
    if (!sessionId || !workflowId) {
        throw new Error('Session ID and workflow ID are required for workflow history stats');
    }

    try {
        // ✅ SESSION CONTEXT PROPAGATION: Include session_id in header for backend middleware
        const headers = {};
        if (window.historySessionId) {
            headers['X-History-Session-ID'] = window.historySessionId;
        }

        const response = await fetch(`/api/history/${sessionId}/workflow/${workflowId}/stats`, { headers });

        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            throw new Error(`Workflow history stats retrieval failed: ${response.status} ${response.statusText} - ${errorText}`);
        }

        const statsData = await response.json();
        return statsData;

    } catch (error) {
        console.error(`Workflow history stats retrieval failed for ${workflowId}:`, error);
        throw error;
    }
};

/**
 * Delete a specific message from a chat session
 *
 * @param {string} historySessionId - History infrastructure session ID
 * @param {string} chatSessionId - Chat session ID
 * @param {string} messageId - ID of the message to delete
 * @returns {Promise<object>} Deletion result
 */
window.apiUtils.deleteMessage = async function (historySessionId, chatSessionId, messageId) {
    if (!historySessionId || !chatSessionId || !messageId) {
        throw new Error('historySessionId, chatSessionId, and messageId are required');
    }

    try {
        const response = await fetch(`/api/history/${historySessionId}/chat_session/${chatSessionId}/message/${messageId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            throw new Error(`Message deletion failed: ${response.status} ${response.statusText} - ${errorText}`);
        }

        const result = await response.json();
        return result;

    } catch (error) {
        console.error(`Message deletion failed for ${messageId}:`, error);
        throw error;
    }
};

/**
 * Get chat session details for Workflow UI (individual session data with messages/artifacts)
 *
 * @param {string} infrastructureSessionId - Workflow infrastructure session ID
 * @param {string} chatSessionId - Chat session ID to retrieve
 * @returns {Promise<object>} Session data with messages and artifacts
 */
window.apiUtils.getChatSessionDetails = async function (infrastructureSessionId, chatSessionId) {
    if (!infrastructureSessionId || !chatSessionId) {
        throw new Error('Both infrastructure session ID and chat session ID are required');
    }

    try {
        const response = await fetch(`/api/workflow/${infrastructureSessionId}/chat_session/${chatSessionId}`);

        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            throw new Error(`Chat session details retrieval failed: ${response.status} ${response.statusText} - ${errorText}`);
        }

        const sessionData = await response.json();
        return sessionData;

    } catch (error) {
        console.error(`Chat session details retrieval failed for ${chatSessionId}:`, error);
        throw error;
    }
};

/**
 * Create a new workflow session infrastructure
 *
 * @param {string} workflowId - Workflow ID to create session for
 * @param {object} options - Additional options (include_sessions, etc.)
 * @returns {Promise<object>} Workflow session creation result
 */
window.apiUtils.createWorkflowSession = async function (workflowId, options = {}) {
    if (!workflowId) {
        throw new Error('Workflow ID is required');
    }

    try {
        const requestBody = {
            workflow_id: workflowId,
            ...options
        };

        const response = await fetch('/api/workflow/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            throw new Error(`Workflow session creation failed: ${response.status} ${response.statusText} - ${errorText}`);
        }

        const sessionData = await response.json();
        return sessionData;

    } catch (error) {
        console.error(`Workflow session creation failed for ${workflowId}:`, error);
        throw error;
    }
};

/**
 * Execute workflow with a user message
 *
 * @param {string} infrastructureSessionId - Workflow infrastructure session ID
 * @param {object} payload - Execution payload (question/message, etc.)
 * @returns {Promise<object>} Workflow execution result
 */
window.apiUtils.executeWorkflow = async function (infrastructureSessionId, payload) {
    if (!infrastructureSessionId) {
        throw new Error('Infrastructure session ID is required');
    }

    if (!payload || typeof payload !== 'object') {
        throw new Error('Execution payload is required');
    }

    try {
        const response = await fetch(`/api/workflow/${infrastructureSessionId}/execute`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            throw new Error(`Workflow execution failed: ${response.status} ${response.statusText} - ${errorText}`);
        }

        const result = await response.json();
        return result;

    } catch (error) {
        console.error(`Workflow execution failed for session ${infrastructureSessionId}:`, error);
        throw error;
    }
};

/**
 * Recover a workflow session after HIE completion
 *
 * @param {string} infrastructureSessionId - Workflow infrastructure session ID
 * @param {object} recoveryData - Recovery metadata (reason, etc.)
 * @returns {Promise<object>} Session recovery result
 */
window.apiUtils.recoverWorkflowSession = async function (infrastructureSessionId, recoveryData = {}) {
    if (!infrastructureSessionId) {
        throw new Error('Infrastructure session ID is required');
    }

    try {
        const response = await fetch(`/api/workflow/${infrastructureSessionId}/recovery`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(recoveryData)
        });

        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            throw new Error(`Workflow session recovery failed: ${response.status} ${response.statusText} - ${errorText}`);
        }

        const recoveryResult = await response.json();
        return recoveryResult;

    } catch (error) {
        console.error(`Workflow session recovery failed for session ${infrastructureSessionId}:`, error);
        throw error;
    }
};



/**
 * RAG/GENERATE API UTILITIES
 */

/**
 * Get RAG data status for a specific session and RAG type
 *
 * @param {string} sessionId - RAG session ID
 * @param {string} ragType - RAG type (defaults to "RAG")
 * @returns {Promise<object>} RAG data status
 */
window.apiUtils.getRAGDataStatus = async function (sessionId, ragType = "RAG") {
    if (!sessionId) {
        throw new Error('Session ID is required for RAG data status');
    }

    try {
        const url = `/api/generate/${sessionId}/data/status?rag_type=${encodeURIComponent(ragType)}`;
        const response = await fetch(url);

        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            throw new Error(`RAG data status retrieval failed: ${response.status} ${response.statusText} - ${errorText}`);
        }

        const statusData = await response.json();
        return statusData;

    } catch (error) {
        console.error(`RAG data status retrieval failed for ${sessionId}:`, error);
        throw error;
    }
};

/**
 * Get RAG storage status for a specific session and RAG type
 *
 * @param {string} sessionId - RAG session ID
 * @param {string} ragType - RAG type (defaults to "RAG")
 * @returns {Promise<object>} RAG storage status
 */
window.apiUtils.getRAGStatus = async function (sessionId, ragType = "RAG") {
    if (!sessionId) {
        throw new Error('Session ID is required for RAG storage status');
    }

    try {
        const url = `/api/generate/${sessionId}/rag/status?rag_type=${encodeURIComponent(ragType)}`;
        const response = await fetch(url);

        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            throw new Error(`RAG storage status retrieval failed: ${response.status} ${response.statusText} - ${errorText}`);
        }

        const statusData = await response.json();
        return statusData;

    } catch (error) {
        console.error(`RAG storage status retrieval failed for ${sessionId}:`, error);
        throw error;
    }
};

/**
 * Get available RAG type options
 *
 * @param {string} sessionId - RAG session ID
 * @returns {Promise<object>} RAG type options
 */
window.apiUtils.getRAGTypeOptions = async function (sessionId) {
    if (!sessionId) {
        throw new Error('Session ID is required for RAG type options');
    }

    try {
        const response = await fetch(`/api/generate/${sessionId}/rag_types`);

        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            throw new Error(`RAG type options retrieval failed: ${response.status} ${response.statusText} - ${errorText}`);
        }

        const optionsData = await response.json();
        return optionsData;

    } catch (error) {
        console.error(`RAG type options retrieval failed:`, error);
        throw error;
    }
};

/**
 * Start RAG generation for a specific session
 *
 * @param {string} sessionId - RAG session ID
 * @param {object} options - Generation options including rag_type
 * @returns {Promise<object>} Generation task response
 */
window.apiUtils.startRAGGeneration = async function (sessionId, options = {}) {
    if (!sessionId) {
        throw new Error('Session ID is required for RAG generation');
    }

    const { rag_type = "RAG" } = options;

    try {
        const response = await fetch(`/api/generate/${sessionId}/run`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ rag_type })
        });

        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            throw new Error(`RAG generation start failed: ${response.status} ${response.statusText} - ${errorText}`);
        }

        const generationData = await response.json();
        return generationData;

    } catch (error) {
        console.error(`RAG generation start failed for ${sessionId}:`, error);
        throw error;
    }
};

/**
 * Get detailed RAG data status for a specific session and RAG type
 *
 * @param {string} sessionId - RAG session ID
 * @param {string} ragType - RAG type (defaults to "RAG")
 * @returns {Promise<object>} Detailed RAG data status
 */
window.apiUtils.getDetailedRAGDataStatus = async function (sessionId, ragType = "RAG") {
    if (!sessionId) {
        throw new Error('Session ID is required for detailed RAG data status');
    }

    try {
        const url = `/api/generate/${sessionId}/data/detailed?rag_type=${encodeURIComponent(ragType)}`;
        const response = await fetch(url);

        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            throw new Error(`Detailed RAG data status retrieval failed: ${response.status} ${response.statusText} - ${errorText}`);
        }

        const statusData = await response.json();
        return statusData;

    } catch (error) {
        console.error(`Detailed RAG data status retrieval failed for ${sessionId}:`, error);
        throw error;
    }
};

/**
 * CACHE MANAGEMENT UTILITIES
 */

/**
 * Load generate cache for a specific session
 *
 * @param {string} sessionId - RAG session ID
 * @returns {Promise<object>} Cache load result
 */
window.apiUtils.loadGenerateCache = async function (sessionId) {
    if (!sessionId) {
        throw new Error('Session ID is required for cache loading');
    }

    try {
        const response = await fetch(`/api/generate/${sessionId}/cache/load`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            throw new Error(`Cache loading failed: ${response.status} ${response.statusText} - ${errorText}`);
        }

        const result = await response.json();
        return result;

    } catch (error) {
        console.error(`Generate cache loading failed for ${sessionId}:`, error);
        throw error;
    }
};

/**
 * Save generate cache for a specific session
 *
 * @param {string} sessionId - RAG session ID
 * @returns {Promise<object>} Cache save result
 */
window.apiUtils.saveGenerateCache = async function (sessionId) {
    if (!sessionId) {
        throw new Error('Session ID is required for cache saving');
    }

    try {
        const response = await fetch(`/api/generate/${sessionId}/cache/save`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            throw new Error(`Cache saving failed: ${response.status} ${response.statusText} - ${errorText}`);
        }

        const result = await response.json();
        return result;

    } catch (error) {
        console.error(`Generate cache saving failed for ${sessionId}:`, error);
        throw error;
    }
};

/**
 * Save generate cache using navigator.sendBeacon (for page unload)
 *
 * @param {string} sessionId - RAG session ID
 * @param {object} data - Data to save
 * @returns {boolean} Success status
 */
window.apiUtils.saveGenerateCacheBeacon = function (sessionId, data = {}) {
    if (!sessionId) {
        console.error('Session ID is required for beacon cache saving');
        return false;
    }

    try {
        const url = `/api/generate/${sessionId}/cache/save`;
        const blob = new Blob([JSON.stringify(data)], { type: 'application/json' });
        const success = navigator.sendBeacon(url, blob);

        if (success) {
            // Success - no need to log
        } else {
            console.warn(`Generate cache beacon save failed for session ${sessionId}`);
        }

        return success;

    } catch (error) {
        console.error(`Generate cache beacon save error for ${sessionId}:`, error);
        return false;
    }
};

/**
 * Get generate cache status for a specific session
 *
 * @param {string} sessionId - RAG session ID
 * @returns {Promise<object>} Cache status
 */
window.apiUtils.getGenerateCacheStatus = async function (sessionId) {
    if (!sessionId) {
        throw new Error('Session ID is required for cache status');
    }

    try {
        const response = await fetch(`/api/generate/${sessionId}/cache/status`);

        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            throw new Error(`Cache status retrieval failed: ${response.status} ${response.statusText} - ${errorText}`);
        }

        const statusData = await response.json();
        return statusData;

    } catch (error) {
        console.error(`Generate cache status retrieval failed for ${sessionId}:`, error);
        throw error;
    }
};

/**
 * SYSTEM API UTILITIES
 */

/**
 * Get list of all available workflow configurations
 *
 * @returns {Promise<array>} List of workflow configurations
 */
window.apiUtils.getAvailableWorkflows = async function () {
    try {
        const response = await fetch('/api/system/workflows');

        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            throw new Error(`Available workflows retrieval failed: ${response.status} ${response.statusText} - ${errorText}`);
        }

        const workflowsData = await response.json();
        return workflowsData;

    } catch (error) {
        console.error('Available workflows retrieval failed:', error);
        throw error;
    }
};

/**
 * USER STATE API UTILITIES
 */

/**
 * Associate user with session
 *
 * @param {object} userData - User association data
 * @returns {Promise<object>} Association result
 */
window.apiUtils.associateUser = async function (userData) {
    if (!userData || typeof userData !== 'object') {
        throw new Error('User data is required');
    }

    try {
        const response = await fetch('/api/user_state/associate_user', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(userData)
        });

        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            throw new Error(`User association failed: ${response.status} ${response.statusText} - ${errorText}`);
        }

        const result = await response.json();
        return result;

    } catch (error) {
        console.error('User association failed:', error);
        throw error;
    }
};

/**
 * Get current user workflow
 *
 * @returns {Promise<object>} Current workflow data
 */
window.apiUtils.getCurrentUserWorkflow = async function () {
    try {
        const response = await fetch('/api/user_state/workflow');

        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            throw new Error(`Current workflow retrieval failed: ${response.status} ${response.statusText} - ${errorText}`);
        }

        const workflowData = await response.json();
        return workflowData;

    } catch (error) {
        console.error('Current workflow retrieval failed:', error);
        throw error;
    }
};

/**
 * CITATION API UTILITIES
 */

/**
 * View source document for a citation
 *
 * @param {string} workflow - Workflow ID
 * @param {string} citationId - Citation ID
 * @returns {Promise<object>} Citation document HTML
 */
window.apiUtils.viewCitation = async function (workflow, citationId) {
    if (!workflow || !citationId) {
        throw new Error('Workflow and citation ID are required');
    }

    try {
        const response = await fetch(`/api/workflow/${workflow}/citations/${citationId}/view`);

        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            throw new Error(`Citation view failed: ${response.status} ${response.statusText} - ${errorText}`);
        }

        const citationData = await response.json();
        return citationData;

    } catch (error) {
        console.error(`Citation view failed for ${citationId}:`, error);
        throw error;
    }
};

/**
 * WORKFLOW HITL API UTILITIES
 */

/**
 * Send HITL response for workflow
 *
 * @param {string} sessionId - Workflow session ID
 * @param {object} responseData - HITL response data
 * @returns {Promise<object>} Response result
 */
window.apiUtils.sendWorkflowResponse = async function (sessionId, responseData) {
    if (!sessionId) {
        throw new Error('Session ID is required');
    }

    if (!responseData || typeof responseData !== 'object') {
        throw new Error('Response data is required');
    }

    try {
        const response = await fetch(`/api/workflow/${sessionId}/response`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(responseData)
        });

        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            throw new Error(`Workflow response failed: ${response.status} ${response.statusText} - ${errorText}`);
        }

        const result = await response.json();
        return result;

    } catch (error) {
        console.error(`Workflow response failed for session ${sessionId}:`, error);
        throw error;
    }
};

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = window.apiUtils;
}
