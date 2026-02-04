/**
 * DTO classes and API utilities for Generate UI data encapsulation
 */

// StatusData DTO for data status information
class StatusData {
    constructor(data) {
        this.totalFiles = data.total_files || 0;
        this.totalSize = data.total_size || 0;
        this.dataNewestTime = data.data_newest_time;
        this.storageCreation = data.storage_creation;
        this.storageStatus = data.storage_status || 'empty';
        this.comparisonData = data.comparison_data || {};
        this.dataFiles = data.data_files || [];
        this.fromCache = data.from_cache || false;

        // Validation
        this._validated = this._validate();
    }

    _validate() {
        console.log('[StatusData] Validating:', {
            totalFiles: this.totalFiles,
            totalSize: this.totalSize,
            totalFilesType: typeof this.totalFiles,
            totalSizeType: typeof this.totalSize,
            totalFilesValid: this.totalFiles >= 0,
            totalSizeValid: this.totalSize >= 0
        });

        return (
            typeof this.totalFiles === 'number' && this.totalFiles >= 0 &&
            typeof this.totalSize === 'number' && this.totalSize >= 0
        );
    }

    shouldRefresh() {
        // Simple refresh logic - could be enhanced
        return !this.fromCache;
    }

    toDict() {
        return {
            total_files: this.totalFiles,
            total_size: this.totalSize,
            data_newest_time: this.dataNewestTime,
            storage_creation: this.storageCreation,
            storage_status: this.storageStatus,
            comparison_data: this.comparisonData,
            data_files: this.dataFiles,
            from_cache: this.fromCache
        };
    }

    markRendered() {
        // Mark as rendered - could be used for caching logic
        this.rendered = true;
    }
}

/**
 * API Utilities for Generate UI - Maps frontend methods to backend endpoints
 */
window.apiUtils = {
    /**
     * Get RAG data status
     * @param {string} sessionId - Session ID
     * @param {string} ragType - RAG type
     * @returns {Promise<Object>} Data status
     */
    async getRAGDataStatus(sessionId, ragType) {
        const response = await fetch(`/api/generate/${sessionId}/data/status?rag_type=${encodeURIComponent(ragType)}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return await response.json();
    },

    /**
     * Get RAG storage status
     * @param {string} sessionId - Session ID
     * @param {string} ragType - RAG type
     * @returns {Promise<Object>} RAG status
     */
    async getRAGStatus(sessionId, ragType) {
        const response = await fetch(`/api/generate/${sessionId}/rag/status?rag_type=${encodeURIComponent(ragType)}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return await response.json();
    },

    /**
     * Get RAG type options
     * @param {string} sessionId - Session ID
     * @returns {Promise<Object>} RAG type options
     */
    async getRAGTypeOptions(sessionId) {
        const response = await fetch(`/api/generate/${sessionId}/rag_types`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return await response.json();
    },

    /**
     * Get detailed RAG data status
     * @param {string} sessionId - Session ID
     * @param {string} ragType - RAG type
     * @returns {Promise<Object>} Detailed data status
     */
    async getDetailedRAGDataStatus(sessionId, ragType) {
        const response = await fetch(`/api/generate/${sessionId}/data/detailed?rag_type=${encodeURIComponent(ragType)}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return await response.json();
    },

    /**
     * Load generate cache
     * @param {string} sessionId - Session ID
     * @returns {Promise<Object>} Cache data
     */
    async loadGenerateCache(sessionId) {
        const response = await fetch(`/api/generate/${sessionId}/cache/load`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return await response.json();
    },

    /**
     * Save generate cache
     * @param {string} sessionId - Session ID
     * @returns {Promise<Object>} Save result
     */
    async saveGenerateCache(sessionId) {
        const response = await fetch(`/api/generate/${sessionId}/cache/save`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return await response.json();
    },

    /**
     * Get generate cache status
     * @param {string} sessionId - Session ID
     * @returns {Promise<Object>} Cache status
     */
    async getGenerateCacheStatus(sessionId) {
        const response = await fetch(`/api/generate/${sessionId}/cache/status`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return await response.json();
    },

    /**
     * Start RAG generation
     * @param {string} sessionId - Session ID
     * @param {Object} payload - Generation payload
     * @returns {Promise<Object>} Generation result
     */
    async startRAGGeneration(sessionId, payload) {
        const response = await fetch(`/api/generate/${sessionId}/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return await response.json();
    }
};

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        StatusData,
        apiUtils: window.apiUtils
    };
}
