/**
 * EventDispatcher - Central Event Routing System
 *
 * PHASE 2: Complete Event System Overhaul
 * Eliminates fragmented event handling and provides centralized routing.
 *
 * Features:
 * - Single entry point for all WebSocket events
 * - Automatic routing to appropriate UI managers
 * - Pluggable architecture for new event types
 * - Comprehensive error handling and logging
 */

class EventDispatcher {
    /**
     * Initialize the central event dispatcher
     */
    constructor() {
        this.handlers = new Map();
        this.eventStats = new Map(); // Track event processing statistics
        this.setupWebSocketListener();
        this.setupErrorHandling();
    }

    /**
     * Register an event handler for specific event types
     * @param {string} eventType - Event type to handle (e.g., 'hie_command_event')
     * @param {Object} handlerInstance - Handler instance with handleEvent method
     */
    registerHandler(eventType, handlerInstance) {
        if (!handlerInstance || typeof handlerInstance.handleEvent !== 'function') {
            console.error(`[EventDispatcher] Invalid handler for ${eventType}: must have handleEvent method`);
            return false;
        }

        // Store multiple handlers in an array for each event type
        if (!this.handlers.has(eventType)) {
            this.handlers.set(eventType, []);
        }
        this.handlers.get(eventType).push(handlerInstance);
        return true;
    }

    /**
     * Unregister an event handler
     * @param {string} eventType - Event type to remove handler for
     */
    unregisterHandler(eventType) {
        const removed = this.handlers.delete(eventType);
        if (removed) {
            console.log(`[EventDispatcher] Unregistered handler for ${eventType}`);
        }
        return removed;
    }

    /**
     * Get handler for event type
     * @param {string} eventType - Event type to lookup
     * @returns {Object|null} Handler instance or null
     */
    getHandler(eventType) {
        return this.handlers.get(eventType) || null;
    }

    /**
     * Dispatch event to appropriate handler
     * @param {string} eventType - The event type
     * @param {Object} data - Event data payload
     * @param {string} workflowId - Associated workflow ID
     */
    dispatchEvent(eventType, data, workflowId) {
        const startTime = performance.now();

        try {
            // Update event statistics
            this.updateEventStats(eventType);

            const handlers = this.handlers.get(eventType) || [];

            if (handlers.length === 0) {
                console.warn(`[EventDispatcher] No handlers registered for event type: ${eventType}`);
                console.warn(`[EventDispatcher] Available handlers:`, Array.from(this.handlers.keys()));
                return;
            }

            // Dispatch to ALL handlers (support multiple handlers per event type)
            handlers.forEach(handler => {
                if (typeof handler.handleEvent !== 'function') {
                    console.error(`[EventDispatcher] Handler for ${eventType} missing handleEvent method:`, handler);
                    return;
                }

                // Dispatch to handler
                const result = handler.handleEvent(eventType, data, workflowId);

                // Handle async results if needed
                if (result && typeof result.catch === 'function') {
                    result.catch(error => {
                        console.error(`[EventDispatcher] Async handler error for ${eventType}:`, error);
                    });
                }
            });

            // Log performance
            const duration = performance.now() - startTime;
            if (duration > 100) { // Log slow handlers
                console.warn(`[EventDispatcher] Slow handler ${eventType}: ${duration.toFixed(2)}ms`);
            }

        } catch (error) {
            console.error(`[EventDispatcher] Error dispatching ${eventType}:`, error);
            console.error(`[EventDispatcher] Event data:`, data);

            // Update error statistics
            this.updateEventStats(eventType, true);
        }
    }

    /**
     * Setup WebSocket message listener
     * Intercepts all WebSocket messages and routes them through the dispatcher
     */
    setupWebSocketListener() {
        // Listen for WebSocket messages from any source
        document.addEventListener('websocket-message', (event) => {
            try {
                const { type, data, workflow_id, timestamp } = event.detail;

                if (!type) {
                    console.warn('[EventDispatcher] Received WebSocket message without type:', event.detail);
                    return;
                }

                this.dispatchEvent(type, data || {}, workflow_id);

            } catch (error) {
                console.error('[EventDispatcher] Error processing WebSocket message:', error);
                console.error('[EventDispatcher] Raw event:', event.detail);
            }
        });
    }

    /**
     * Setup error handling and recovery
     */
    setupErrorHandling() {
        // Handle unhandled promise rejections from event handlers
        window.addEventListener('unhandledrejection', (event) => {
            if (event.reason && event.reason.message && event.reason.message.includes('EventDispatcher')) {
                console.error('[EventDispatcher] Unhandled promise rejection:', event.reason);
                event.preventDefault(); // Prevent default browser handling
            }
        });

        // Handle global errors from event handlers
        window.addEventListener('error', (event) => {
            if (event.message && event.message.includes('EventDispatcher')) {
                console.error('[EventDispatcher] Global error:', event.error);
                // Don't prevent default - let other error handlers process
            }
        });
    }

    /**
     * Update event processing statistics
     * @param {string} eventType - Event type
     * @param {boolean} isError - Whether this was an error
     */
    updateEventStats(eventType, isError = false) {
        const stats = this.eventStats.get(eventType) || { count: 0, errors: 0, lastSeen: null };
        stats.count++;
        if (isError) stats.errors++;
        stats.lastSeen = new Date().toISOString();
        this.eventStats.set(eventType, stats);
    }

    /**
     * Get event processing statistics
     * @returns {Object} Statistics for all event types
     */
    getEventStats() {
        const stats = {};
        for (const [eventType, eventStats] of this.eventStats) {
            stats[eventType] = { ...eventStats };
        }
        return stats;
    }

    /**
     * Reset event statistics
     */
    resetEventStats() {
        this.eventStats.clear();
    }

    /**
     * List all registered handlers
     * @returns {Array} List of registered event types
     */
    listHandlers() {
        return Array.from(this.handlers.keys());
    }

    /**
     * Check if handler is registered for event type
     * @param {string} eventType - Event type to check
     * @returns {boolean} True if handler is registered
     */
    hasHandler(eventType) {
        return this.handlers.has(eventType);
    }

    /**
     * Get system health status
     * @returns {Object} Health status information
     */
    getHealthStatus() {
        const handlerCount = this.handlers.size;
        const totalEvents = Array.from(this.eventStats.values()).reduce((sum, stats) => sum + stats.count, 0);
        const totalErrors = Array.from(this.eventStats.values()).reduce((sum, stats) => sum + stats.errors, 0);

        return {
            healthy: handlerCount > 0,
            handlerCount,
            totalEvents,
            totalErrors,
            errorRate: totalEvents > 0 ? (totalErrors / totalEvents * 100).toFixed(2) + '%' : '0%',
            handlers: this.listHandlers(),
            stats: this.getEventStats()
        };
    }

    /**
     * Test event dispatching (for debugging)
     * @param {string} eventType - Event type to test
     * @param {Object} testData - Test data payload
     */
    async testDispatch(eventType, testData = {}) {
        try {
            this.dispatchEvent(eventType, testData, 'test-workflow');
            return true;
        } catch (error) {
            console.error(`[EventDispatcher] Test dispatch failed for ${eventType}:`, error);
            return false;
        }
    }
}

// Global EventDispatcher instance
let eventDispatcherInstance = null;

/**
 * Get or create the global EventDispatcher instance
 * @returns {EventDispatcher} The global event dispatcher
 */
function getEventDispatcher() {
    if (!eventDispatcherInstance) {
        eventDispatcherInstance = new EventDispatcher();
    }
    return eventDispatcherInstance;
}

/**
 * Initialize the event dispatcher system
 * Called during application startup
 */
function initializeEventDispatcher() {
    const dispatcher = getEventDispatcher();

    // Register core event handlers
    // Note: Actual registration happens in individual manager initialization
    // This function ensures the dispatcher is ready for registration

    return dispatcher;
}

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { EventDispatcher, getEventDispatcher, initializeEventDispatcher };
}

// Auto-initialize when loaded as global script
if (typeof window !== 'undefined') {
    window.EventDispatcher = EventDispatcher;
    window.getEventDispatcher = getEventDispatcher;
    window.initializeEventDispatcher = initializeEventDispatcher;

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeEventDispatcher);
    } else {
        initializeEventDispatcher();
    }
}
