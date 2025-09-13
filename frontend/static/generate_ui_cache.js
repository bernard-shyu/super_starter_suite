/**
 * Generate UI Cache Manager - Frontend
 *
 * This module handles client-side caching for the Generate UI.
 * It provides utilities for managing metadata cache state and
 * coordinating with the backend cache management.
 */

// Generate UI Cache Manager Class
class GenerateUICacheManager {
    constructor() {
        this.cache = {};
        this.isInitialized = false;
        this.currentRAGType = 'RAG';
        this.eventListeners = [];
    }

    /**
     * Initialize the cache manager
     */
    async initialize() {
        try {
            console.log('[CacheManager] Initializing...');

            // Load cache from backend
            const response = await fetch('/api/generate/cache/load', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            if (response.ok) {
                const result = await response.json();
                console.log('[CacheManager] Cache loaded:', result.message);
                this.isInitialized = true;
                this.notifyListeners('cacheLoaded', { success: true });
                return true;
            } else {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
        } catch (error) {
            console.error('[CacheManager] Failed to initialize:', error);
            this.notifyListeners('cacheLoaded', { success: false, error: error.message });
            return false;
        }
    }

    /**
     * Save cache to backend
     */
    async save() {
        if (!this.isInitialized) {
            console.warn('[CacheManager] Cache not initialized, cannot save');
            return false;
        }

        try {
            console.log('[CacheManager] Saving cache...');

            const response = await fetch('/api/generate/cache/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            if (response.ok) {
                const result = await response.json();
                console.log('[CacheManager] Cache saved:', result.message);
                this.notifyListeners('cacheSaved', { success: true });
                return true;
            } else {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
        } catch (error) {
            console.error('[CacheManager] Failed to save cache:', error);
            this.notifyListeners('cacheSaved', { success: false, error: error.message });
            return false;
        }
    }

    /**
     * Get cached data for a specific key
     */
    get(key) {
        return this.cache[key];
    }

    /**
     * Set cached data for a specific key
     */
    set(key, value) {
        this.cache[key] = value;
        this.notifyListeners('cacheUpdated', { key, value });
    }

    /**
     * Check if cache contains a specific key
     */
    has(key) {
        return key in this.cache;
    }

    /**
     * Remove a key from cache
     */
    remove(key) {
        if (key in this.cache) {
            delete this.cache[key];
            this.notifyListeners('cacheRemoved', { key });
            return true;
        }
        return false;
    }

    /**
     * Clear all cache data
     */
    clear() {
        this.cache = {};
        this.notifyListeners('cacheCleared', {});
    }

    /**
     * Get cache size (number of keys)
     */
    size() {
        return Object.keys(this.cache).length;
    }

    /**
     * Add event listener
     */
    addEventListener(event, callback) {
        if (!this.eventListeners[event]) {
            this.eventListeners[event] = [];
        }
        this.eventListeners[event].push(callback);
    }

    /**
     * Remove event listener
     */
    removeEventListener(event, callback) {
        if (this.eventListeners[event]) {
            const index = this.eventListeners[event].indexOf(callback);
            if (index > -1) {
                this.eventListeners[event].splice(index, 1);
            }
        }
    }

    /**
     * Notify event listeners
     */
    notifyListeners(event, data) {
        if (this.eventListeners[event]) {
            this.eventListeners[event].forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error('[CacheManager] Error in event listener:', error);
                }
            });
        }
    }

    /**
     * Set current RAG type and notify listeners
     */
    setCurrentRAGType(ragType) {
        if (this.currentRAGType !== ragType) {
            const oldType = this.currentRAGType;
            this.currentRAGType = ragType;
            this.notifyListeners('ragTypeChanged', { oldType, newType: ragType });
        }
    }

    /**
     * Get current RAG type
     */
    getCurrentRAGType() {
        return this.currentRAGType;
    }

    /**
     * Get cache statistics
     */
    getStats() {
        return {
            size: this.size(),
            isInitialized: this.isInitialized,
            currentRAGType: this.currentRAGType,
            keys: Object.keys(this.cache)
        };
    }
}

// Global cache manager instance
let cacheManagerInstance = null;

/**
 * Get the global cache manager instance
 */
function getCacheManager() {
    if (!cacheManagerInstance) {
        cacheManagerInstance = new GenerateUICacheManager();
    }
    return cacheManagerInstance;
}

/**
 * Initialize cache manager (call this when page loads)
 */
async function initializeCacheManager() {
    const manager = getCacheManager();
    return await manager.initialize();
}

/**
 * Save cache manager (call this when page unloads)
 */
async function saveCacheManager() {
    const manager = getCacheManager();
    return await manager.save();
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        GenerateUICacheManager,
        getCacheManager,
        initializeCacheManager,
        saveCacheManager
    };
}

// Auto-initialize when DOM is ready if this script is loaded
if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', async () => {
        // Only initialize if we're on the generate UI page
        if (window.location.pathname.includes('generate') ||
            document.querySelector('.generate-container')) {
            console.log('[CacheManager] Auto-initializing for Generate UI...');
            await initializeCacheManager();
        }
    });

    // Auto-save when page unloads
    window.addEventListener('beforeunload', async () => {
        if (cacheManagerInstance && cacheManagerInstance.isInitialized) {
            console.log('[CacheManager] Auto-saving cache...');
            // Use sendBeacon for more reliable delivery during page unload
            if (navigator.sendBeacon) {
                const data = JSON.stringify({ action: 'save' });
                navigator.sendBeacon('/api/generate/cache/save', data);
            } else {
                // Fallback to fetch with keepalive
                fetch('/api/generate/cache/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({}),
                    keepalive: true
                }).catch(error => {
                    console.warn('[CacheManager] Failed to save cache on unload:', error);
                });
            }
        }
    });
}
