/**
 * Global State Manager - Phase 5.6D Frontend Modularization
 *
 * Centralized state management for all global variables across modules.
 * Loads FIRST to prevent variable declaration conflicts.
 * All modules should access state via window.globalState.[property]
 */

// Initialize global state object
window.globalState = {
    // Chat state management
    currentWorkflow: null,
    currentChatSessionId: null,

    // UI state management
    currentView: 'chat', // 'chat', 'settings', 'config', 'generate', 'welcome'
    pendingSessionResume: null,

    // Status bar structure
    statusBarStruct: {
        status_message: 'Ready',
        current_model_provider: '',
        current_model_id: '',
        current_workflow: ''
    },

    // Theme management
    currentTheme: 'light_classic',
    availableThemes: [],

    // Workflow management
    availableWorkflows: []
};

console.log('[GlobalState] Initialized global state manager with', Object.keys(window.globalState).length, 'properties');

// Export for module use (if needed)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = window.globalState;
}
