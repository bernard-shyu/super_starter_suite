/**
 * Data Transfer Objects for MVC Pattern Implementation - JavaScript
 *
 * This module contains encapsulated data objects that carry similar/same structure
 * data across MVC boundaries, with essential properties (always carried) and
 * meta-properties (internal control). Only essential changes are visible at control points.
 */

// ============================================================================
// ENUMS
// ============================================================================

/**
 * Generation state enumeration - UPDATED with COMPLETION state
 */
const GenerationState = {
    READY: "ST_READY",
    PARSER: "ST_PARSER",
    GENERATION: "ST_GENERATION",
    COMPLETED: "ST_COMPLETED",
    ERROR: "ST_ERROR"
};

// ============================================================================
// PROGRESS DATA DTO
// ============================================================================

/**
 * Encapsulated progress data across MVC boundaries.
 *
 * Essential properties are always carried across boundaries.
 * Meta-properties provide internal control and are not carried.
 */
class ProgressData {
    constructor(data = {}) {
        // Essential Properties (Always Carried Across Boundaries)
        this.type = data.type || "progress_update";
        this.state = data.state || GenerationState.READY;
        this.progress = data.progress || 0;
        this.message = data.message || "";
        this.metadata = data.metadata || {};

        // Essential Context Properties
        this.taskId = data.taskId || data.task_id || null;
        this.timestamp = data.timestamp ? new Date(data.timestamp) : new Date();
        this.ragType = data.ragType || data.rag_type || "RAG";

        // Meta-Properties (Internal Control - Not Carried Across Boundaries)
        this._source = data._source || "controller";        // "model", "controller", "view"
        this._validated = data._validated || false;        // Has data been validated?
        this._transformed = data._transformed || false;    // Has data been transformed by controller?
        this._rendered = data._rendered || false;          // Has data been rendered by view?
        this._fromCache = data._fromCache || data._from_cache || false; // Was data loaded from cache?
    }

    /**
     * Control Point: Validate data before processing
     */
    validate() {
        if (this.progress >= 0 && this.progress <= 100 &&
            Object.values(GenerationState).includes(this.state)) {
            this._validated = true;
            return true;
        }
        return false;
    }

    /**
     * Control Point: Mark data as transformed by controller
     */
    markTransformed() {
        this._transformed = true;
        this._source = "controller";
    }

    /**
     * Control Point: Mark data as rendered by view
     */
    markRendered() {
        this._rendered = true;
        this._source = "view";
    }

    /**
     * Control Point: Update progress (only if validated)
     */
    updateProgress(newProgress, newMessage) {
        if (this._validated && newProgress >= 0 && newProgress <= 100) {
            this.progress = newProgress;
            this.message = newMessage;
            this._rendered = false; // Mark for re-render
            this.timestamp = new Date(); // Update timestamp
            return true;
        }
        return false;
    }

    /**
     * Convert to plain object for JSON serialization (essential properties only)
     */
    toDict() {
        return {
            type: this.type,
            state: this.state,
            progress: this.progress,
            message: this.message,
            metadata: this.metadata,
            taskId: this.taskId,
            timestamp: this.timestamp.toISOString(),
            ragType: this.ragType,
            // Include meta-properties for debugging (but mark as internal)
            _source: this._source,
            _validated: this._validated,
            _transformed: this._transformed,
            _rendered: this._rendered
        };
    }
}

// ============================================================================
// STATUS DATA DTO
// ============================================================================

/**
 * Encapsulated status data with caching metadata.
 *
 * Essential properties are always carried across boundaries.
 * Meta-properties provide internal control and cache awareness.
 */
class StatusData {
    constructor(data = {}) {
        // Essential Properties (Always Carried Across Boundaries)
        this.dataNewestTime = data.dataNewestTime || data.data_newest_time || null;
        this.totalFiles = data.totalFiles || data.total_files || 0;
        this.totalSize = data.totalSize || data.total_size || 0;
        this.dataFiles = data.dataFiles || data.data_files || [];
        this.hasNewerFiles = data.hasNewerFiles || data.has_newer_files || false;

        // Essential Context Properties
        this.ragType = data.ragType || data.rag_type || "RAG";
        this.lastUpdated = data.lastUpdated || (data.meta_last_update ? new Date(data.meta_last_update) : new Date());

        // Storage Status Properties
        this.storageCreation = data.storageCreation || data.storage_creation || null;
        this.storageFilesCount = data.storageFilesCount || data.storage_files_count || 0;
        this.storageHash = data.storageHash || data.storage_hash || null;
        this.storageStatus = data.storageStatus || data.storage_status || "empty"; // "healthy", "empty", "corrupted"

        // Meta-Properties (Internal Control - Not Carried Across Boundaries)
        this._fromCache = data._fromCache || data._from_cache || false;
        this._cacheKey = data._cacheKey || data._cache_key || null;
        this._staleThreshold = data._staleThreshold || 5 * 60 * 1000; // 5 minutes
        this._source = data._source || "controller";
        this._validated = data._validated || false;

        // Auto-validate on construction if not explicitly set
        if (!this._validated) {
            this.validate();
        }
    }

    /**
     * Control Point: Check if data is stale
     */
    isStale() {
        return Date.now() - this.lastUpdated > this._staleThreshold;
    }

    /**
     * Control Point: Determine if data needs refresh
     */
    shouldRefresh() {
        return this.isStale() || !this._fromCache;
    }

    /**
     * Control Point: Mark data as loaded from cache
     */
    markFromCache(cacheKey) {
        this._fromCache = true;
        this._cacheKey = cacheKey;
        this._source = "cache";
    }

    /**
     * Control Point: Validate data integrity
     */
    validate() {
        console.log('[StatusData] Validating:', {
            totalFiles: this.totalFiles,
            totalSize: this.totalSize,
            totalFilesType: typeof this.totalFiles,
            totalSizeType: typeof this.totalSize,
            totalFilesValid: this.totalFiles >= 0,
            totalSizeValid: this.totalSize >= 0
        });

        if (this.totalFiles >= 0 && this.totalSize >= 0) {
            this._validated = true;
            console.log('[StatusData] Validation passed');
            return true;
        }

        console.log('[StatusData] Validation failed');
        return false;
    }

    /**
     * Control Point: Update storage status information
     */
    updateStorageStatus(storageInfo) {
        if (!this._validated) {
            return false;
        }

        this.storageCreation = storageInfo.lastModified || storageInfo.last_modified;
        this.storageFilesCount = (storageInfo.storageFiles || storageInfo.storage_files || []).length;
        this.storageHash = storageInfo.hash;

        // Determine storage status
        if (this.storageFilesCount === 0) {
            this.storageStatus = "empty";
        } else if (storageInfo.isCorrupted || storageInfo.is_corrupted) {
            this.storageStatus = "corrupted";
        } else {
            this.storageStatus = "healthy";
        }

        this.lastUpdated = new Date();
        return true;
    }

    /**
     * Convert to plain object for JSON serialization (essential properties only)
     */
    toDict() {
        return {
            dataNewestTime: this.dataNewestTime,
            totalFiles: this.totalFiles,
            totalSize: this.totalSize,
            data_files: this.dataFiles,
            hasNewerFiles: this.hasNewerFiles,
            ragType: this.ragType,
            lastUpdated: this.lastUpdated.toISOString(),
            storageCreation: this.storageCreation,
            storageFilesCount: this.storageFilesCount,
            storageHash: this.storageHash,
            storageStatus: this.storageStatus,
            // Include meta-properties for debugging (but mark as internal)
            _fromCache: this._fromCache,
            _cacheKey: this._cacheKey,
            _source: this._source,
            _validated: this._validated
        };
    }
}

// ============================================================================
// FACTORY FUNCTIONS
// ============================================================================

/**
 * Factory function to create validated ProgressData instances.
 *
 * Control Point: Ensures all created instances are validated.
 */
function createProgressData(options = {}) {
    const data = new ProgressData(options);

    // Control Point: Always validate on creation
    if (!data.validate()) {
        throw new Error(`Invalid progress data: progress=${data.progress}, state=${data.state}`);
    }

    return data;
}

/**
 * Factory function to create validated StatusData instances.
 *
 * Control Point: Ensures all created instances are validated.
 */
function createStatusData(options = {}) {
    const data = new StatusData(options);

    // Control Point: Always validate on creation
    if (!data.validate()) {
        throw new Error(`Invalid status data: totalFiles=${data.totalFiles}, totalSize=${data.totalSize}`);
    }

    return data;
}

// ============================================================================
// GLOBAL INSTANCES
// ============================================================================

// Global instances for type checking and validation
const PROGRESS_DATA_TEMPLATE = new ProgressData();
const STATUS_DATA_TEMPLATE = new StatusData();

// ============================================================================
// EXPORTS
// ============================================================================

// Export classes and functions for use in other modules
window.ProgressData = ProgressData;
window.StatusData = StatusData;
window.GenerationState = GenerationState;
window.createProgressData = createProgressData;
window.createStatusData = createStatusData;
window.PROGRESS_DATA_TEMPLATE = PROGRESS_DATA_TEMPLATE;
window.STATUS_DATA_TEMPLATE = STATUS_DATA_TEMPLATE;

// For module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        ProgressData,
        StatusData,
        GenerationState,
        createProgressData,
        createStatusData,
        PROGRESS_DATA_TEMPLATE,
        STATUS_DATA_TEMPLATE
    };
}
