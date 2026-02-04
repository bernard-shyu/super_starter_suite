/**
 * Global State Manager - Phase 5.6D Frontend Modularization
 *
 * Centralized state management for all global variables across modules.
 * Loads FIRST to prevent variable declaration conflicts.
 * All modules should access state via window.globalState.[property]
 */

// Initialize global state object
window.globalState = {
    // Workflow state management
    currentWorkflow: null,                    // Workflow ID (A_agentic_rag)

    // UI state management
    currentView: 'chat', // 'chat', 'settings', 'config', 'generate', 'welcome'
    pendingSessionResume: null,

    // Status bar structure
    statusBarStruct: {
        status_message: 'Ready',
        current_user_id: '',
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

// Export for module use (if needed)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = window.globalState;
}
