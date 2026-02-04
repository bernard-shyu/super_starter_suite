/**
 * Main Application Script - Handles UI interaction and menu functionality
 * Phase 5.6D: Modularized version with proper delegation to modules
 */

// Global variables - simplified after extractions

// Import addMessage function from chat UI
function addMessage(sender, content, type = 'normal') {
    if (window.chatUIManager) {
        window.chatUIManager.addMessage(sender, content, type);
    } else {
        console.warn('[Script.js] Chat UI Manager not available for addMessage');
    }
}

// Main updateStatus function - delegates to MainUIManager
function updateStatus(message, type = 'info') {
    if (window.mainUIManager && window.mainUIManager.updateStatus) {
        window.mainUIManager.updateStatus(message, type);
    } else {
        console.warn('[Script.js] MainUIManager not available for updateStatus');
    }
}

// Utility function for error display
function showError(message) {
    addMessage('system', message, 'error');
    updateStatus(message, 'error');
}

// Initialize when DOM is ready and export globally
document.addEventListener('DOMContentLoaded', () => {
    // Initialize DOM elements
    const chatArea = document.getElementById('chat-area');
    const welcomePage = document.getElementById('welcome-page');
    const chatInterface = document.getElementById('chat-interface');
    const messageContainer = document.getElementById('message-container');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const menuToggle = document.getElementById('menu-toggle');
    const leftPanel = document.getElementById('left-panel');
    const resizer = document.getElementById('resizer');

    // View management functions - now delegated to main_ui_manager.js

    async function showChatInterface(sessionIdToResume = null) {
        // currentView is now managed by main_ui_manager
        if (window.mainUIManager && window.mainUIManager.hideAllViews) {
            window.mainUIManager.hideAllViews();
        } else {
            // Fallback if main_ui_manager not loaded yet
            document.getElementById('welcome-page').style.display = 'none';
            document.getElementById('loading-page').style.display = 'none';
            document.getElementById('settings-ui-container').style.display = 'none';
            document.getElementById('config-ui-container').style.display = 'none';
            document.getElementById('chat-history-ui-container').style.display = 'none';
        }
        document.getElementById('chat-interface').style.display = 'flex';

        // Update unified chat renderer context - use InfrastructureSession
        if (window.unifiedChatRenderer) {
            const infrastructureSessionId = window.sessionManager.getInfrastructureSession(window.globalState.currentWorkflow);
            window.unifiedChatRenderer.setCurrentSession(
                sessionIdToResume || infrastructureSessionId,
                window.globalState.currentWorkflow
            );
        }

        if (sessionIdToResume) {
            // For session resumption, session context is already set by workflow manager

            // Use unified chat renderer to load session messages
            if (window.unifiedChatRenderer) {
                await window.unifiedChatRenderer.renderSessionMessages(
                    sessionIdToResume,
                    window.globalState.currentWorkflow,
                    {
                        showLoading: true,
                        clearExisting: true,
                        addSystemMessage: true,
                        source: 'session_resume'
                    }
                );
            } else {
                console.warn('[showChatInterface] Unified chat renderer not available, using fallback');
                // Fallback logic would go here if needed
            }
        } else {
            // Start a new session - let SRR manage session state
            // No need to set global workflow session ID - SRR handles this

            // Clear messages for new session
            if (window.unifiedChatRenderer) {
                window.unifiedChatRenderer.clearMessages();
            }

            // Add welcome message for new session (session ID will be set by backend later)
            if (window.globalState.currentWorkflow && window.unifiedChatRenderer) {
                window.unifiedChatRenderer.addSystemMessage(
                    `Ready to chat with ${window.globalState.currentWorkflow.replace(/[_\-]/g, ' ')} workflow`,
                    'info'
                );
            }
        }
    }

    // Make updateStatus globally available for session management functions
    window.updateStatus = updateStatus;

    // Make showChatInterface globally available for session management functions
    window.showChatInterface = showChatInterface;

    function showSettingsUI() {
        currentView = 'settings';
        if (window.mainUIManager && window.mainUIManager.showSettingsUI) {
            window.mainUIManager.showSettingsUI();
        } else {
            // Fallback
            document.getElementById('welcome-page').style.display = 'none';
            document.getElementById('loading-page').style.display = 'none';
            document.getElementById('chat-interface').style.display = 'none';
            document.getElementById('config-ui-container').style.display = 'none';
            document.getElementById('chat-history-ui-container').style.display = 'none';
            document.getElementById('settings-ui-container').style.display = 'block';
        }
    }

    function showConfigUI() {
        currentView = 'config';
        if (window.mainUIManager && window.mainUIManager.showConfigUI) {
            window.mainUIManager.showConfigUI();
        } else {
            // Fallback
            document.getElementById('welcome-page').style.display = 'none';
            document.getElementById('loading-page').style.display = 'none';
            document.getElementById('chat-interface').style.display = 'none';
            document.getElementById('settings-ui-container').style.display = 'none';
            document.getElementById('chat-history-ui-container').style.display = 'none';
            document.getElementById('config-ui-container').style.display = 'block';
        }
    }

    // Message handling now delegated to chat-ui-manager.js
    // New Session button handler - creates NEW workflow infrastructure for fresh session
    const newSessionBtn = document.getElementById('new-session-btn');
    if (newSessionBtn) {
        newSessionBtn.addEventListener('click', async () => {
            if (!window.globalState.currentWorkflow) {
                addMessage('system', 'Please select a workflow first.', 'error');
                return;
            }

            console.log(`[NewSession] Creating new session infrastructure for workflow: ${window.globalState.currentWorkflow}`);

            try {
                // Clear existing session state - infrastructure will be replaced by new one

                // CREATE NEW WORKFLOW INFRASTRUCTURE (unbound to any chat session)
                // This ensures new messages create a new chat session, not continue the old one
                const sessionData = await window.apiUtils.createWorkflowSession(window.globalState.currentWorkflow, {
                    include_sessions: false,  // Don't need sessions list for fresh infrastructure
                    chat_session_id: null     // SIGNAL: Explicitly unbind from existing sessions
                });

                console.log(`[NewSession] ✅ Created fresh infrastructure: ${sessionData.session_id}`);

                // Register the new infrastructure in session manager
                if (window.sessionManager?.setInfrastructureSession) {
                    window.sessionManager.setInfrastructureSession(window.globalState.currentWorkflow, sessionData.session_id);
                }

                // Clear the chat interface UI for fresh start
                const messageContainer = document.getElementById('message-container');
                if (messageContainer) {
                    messageContainer.innerHTML = '';
                }

                // Set session context for the new infrastructure
                const freshSessionData = {
                    session_id: null,  // No chat session yet - will be created on first message
                    websocket_url: `/api/workflow/${sessionData.session_id}/stream`
                };

                if (window.chatUIManager) {
                    window.chatUIManager.setSessionContext(freshSessionData, window.globalState.currentWorkflow);
                    console.log(`[NewSession] ✅ Session context set for fresh infrastructure: ${sessionData.session_id}`);
                }

                // Add system message indicating ready for new session
                addMessage('system', `✨ Fresh session ready with ${window.globalState.currentWorkflow.replace(/[_\-]/g, ' ')} workflow`);
                addMessage('system', '💬 Send your first message to start the new conversation', 'system');

                updateStatus(`New ${window.globalState.currentWorkflow} session ready`, 'success');

            } catch (error) {
                updateStatus('Failed to create new session', 'error');
                addMessage('system', '❌ Failed to create new session infrastructure', 'error');
            }
        });
    } else {
        console.warn('[EventHandler] New Session button not found');
    }

    // ✅ MVC SIMPLIFICATION: Workflow buttons now use backend MVC endpoints
    // Frontend delegates to backend for workflow state management
    // No more local session creation or complex workflow logic

    // UI interaction functionality moved to ui_interaction_manager.js

    // Other button handlers
    document.getElementById('login-btn').addEventListener('click', async () => {
        const userId = await window.loginModal.show();
        if (userId) {
            updateStatus(`Associating user ${userId}...`);
            try {
                const response = await fetch('/api/user_state/associate_user', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: userId })
                });
                const data = await response.json();
                if (response.ok) {
                    // REMOVED: redundant window.showAlert since user already accepted in Login Modal
                    // HARD REFRESH: Reload the page to ensure complete user context switch
                    window.location.reload();
                } else {
                    await window.showAlert('Error', `Error: ${data.detail || data.message}`, { type: 'danger' });
                    updateStatus(`Failed to associate user.`);
                }
            } catch (error) {
                console.error('Error associating user:', error);
                await window.showAlert('Error', 'An error occurred while associating user.', { type: 'danger' });
                updateStatus(`Error associating user.`);
            }
        }
    });

    document.getElementById('settings-btn').addEventListener('click', async () => {
        showLoadingPage('User Settings', 'Loading configuration interface...');

        setTimeout(async () => {
            showSettingsUI();
            const settingsContainer = document.getElementById('settings-ui-container');
            settingsContainer.innerHTML = ''; // Clear previous content

            // config_ui.js is already loaded statically in HTML, no need to load dynamically
            if (typeof initConfigUI === 'function') {
                const success = await initConfigUI(settingsContainer); // Pass container to init function
                if (success) {
                    updateStatus('User settings loaded successfully.', 'success');
                } else {
                    updateStatus('Failed to load user settings.', 'error');
                }
            } else {
                console.error('Configuration UI not available');
                showError('Configuration UI not available');
                updateStatus('Configuration UI not available.', 'error');
            }
        }, 1000);
    });

    document.getElementById('config-btn').addEventListener('click', async () => {
        showLoadingPage('System Configuration', 'Loading system settings...');

        setTimeout(async () => {
            showConfigUI();
            const configContainer = document.getElementById('config-ui-container');
            configContainer.innerHTML = ''; // Clear previous content

            // config_ui.js is already loaded statically in HTML, no need to load dynamically
            if (typeof initSystemConfigUI === 'function') {
                const success = await initSystemConfigUI(configContainer); // Pass container to init function
                if (success) {
                    updateStatus('System configuration loaded successfully.', 'success');
                } else {
                    updateStatus('Failed to load system configuration.', 'error');
                }
            } else {
                console.error('System configuration UI not available');
                showError('System configuration UI not available');
                updateStatus('System configuration UI not available.', 'error');
            }
        }, 1000);
    });

    document.getElementById('generate-btn').addEventListener('click', async () => {
        // Navigate to the new RAG generation UI page
        window.location.href = '/static/ui/generate/generate.html';
    });

    // ✅ WORKFLOW SELECTION: Now delegated to modular workflowManager
    // The new ui/workflow/workflow.js handles all workflow selection logic
    // with proper SRR session management integration

    // Global workflow selection function - delegates to modular system
    window.selectWorkflow = (workflowId) => {
        if (window.workflowManager?.selectWorkflow) {
            return window.workflowManager.selectWorkflow(workflowId);
        } else {
            console.warn('[Script.js] WorkflowManager not available, cannot select workflow');
        }
    };

    // Chat History button is now handled by main-ui-manager.js
    // with integrated Chat History UI

    // Initialize with welcome page
    if (window.mainUIManager && window.mainUIManager.showWelcomePage) {
        window.mainUIManager.showWelcomePage();
    } else {
        // Fallback
        document.getElementById('welcome-page').style.display = 'block';
        document.getElementById('loading-page').style.display = 'none';
        document.getElementById('chat-interface').style.display = 'none';
        document.getElementById('settings-ui-container').style.display = 'none';
        document.getElementById('config-ui-container').style.display = 'none';
        document.getElementById('chat-history-ui-container').style.display = 'none';
    }
});
