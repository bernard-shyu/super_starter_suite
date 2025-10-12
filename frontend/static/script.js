// Initialize legacy support for status bar (handled by global-state.js)
try {
    if (typeof statusBarStruct === 'undefined') {
        statusBarStruct = {
            status_message: 'Ready',
            current_model_provider: '',
            current_model_id: '',
            current_workflow: ''
        };
    }
} catch (error) {
    console.error('Error during initialization:', error);
}

// Global utility functions
function generateUUID() {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
        return crypto.randomUUID();
    }
    // Simple fallback UUID generation
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

// Theme management - legacy fallback support
if (typeof currentTheme === 'undefined') {
    currentTheme = 'light_classic';
}
if (typeof availableThemes === 'undefined') {
    availableThemes = [];
}

// Theme management functions
async function loadAvailableThemes() {
    try {
        const response = await fetch('/api/themes');
        if (response.ok) {
            const data = await response.json();
            availableThemes = data.themes || [];
        } else {
            console.warn('Failed to load available themes from API');
            availableThemes = [];
        }
    } catch (error) {
        console.error('Error loading themes:', error);
        availableThemes = [];
    }
}

async function loadCurrentTheme() {
    try {
        const response = await fetch('/api/themes/current');
        if (response.ok) {
            const data = await response.json();
            currentTheme = data.theme || 'light_classic';
        } else {
            console.warn('Failed to load current theme, using default');
            currentTheme = 'light_classic';
        }
    } catch (error) {
        console.error('Error loading current theme:', error);
        currentTheme = 'light_classic';
    }
    // Note: applyTheme is now handled by main-ui-manager.js
}

    // Theme management functions removed - now handled by MainUIManager.applyTheme(), switchTheme(), etc.

// Make theme functions globally available
window.switchTheme = switchTheme;
window.getCurrentTheme = () => currentTheme;
window.getAvailableThemes = () => availableThemes;

// All global state now managed by global-state.js

// Enhanced Session Management - Phase 4.6 Implementation
// ======================================================

/**
 * Session Management Functions for Cross-Workflow Persistence
 */

// Save current session state to localStorage for persistence
function saveCurrentSessionState() {
    if (!window.globalState.currentWorkflow || !window.globalState.currentChatSessionId) return;

    // Only save session state with actual messages (not just workflow selection)
    const messageCount = document.getElementById('message-container')?.children.length || 0;
    if (messageCount === 0) {
        console.log('[SessionManager] Skipping session save - no messages yet');
        return;
    }

    const sessionState = {
        workflow: window.globalState.currentWorkflow,
        sessionId: window.globalState.currentChatSessionId,
        view: window.globalState.currentView,
        timestamp: Date.now(),
        messageCount: messageCount
    };

    try {
        localStorage.setItem('super_starter_current_session', JSON.stringify(sessionState));
        localStorage.setItem('super_starter_last_update', Date.now().toString());
        console.log('[SessionManager] Saved current session state:', sessionState);
    } catch (error) {
        console.warn('[SessionManager] Failed to save session state:', error);
    }
}

// Load session state from localStorage
function loadPreviousSessionState() {
    try {
        const sessionData = localStorage.getItem('super_starter_current_session');
        const lastUpdate = localStorage.getItem('super_starter_last_update');

        if (!sessionData) return null;

        // Check if session is recent (within 24 hours) to avoid stale sessions
        const updateTime = parseInt(lastUpdate);
        const hoursSinceUpdate = (Date.now() - updateTime) / (1000 * 60 * 60);

        if (hoursSinceUpdate > 24) {
            console.log('[SessionManager] Session state too old, clearing');
            clearSessionState();
            return null;
        }

        const sessionState = JSON.parse(sessionData);
        console.log('[SessionManager] Loaded previous session state:', sessionState);
        return sessionState;

    } catch (error) {
        console.warn('[SessionManager] Failed to load session state:', error);
        clearSessionState();
        return null;
    }
}

// Clear session state (on logout, etc.)
function clearSessionState() {
    try {
        localStorage.removeItem('super_starter_current_session');
        localStorage.removeItem('super_starter_last_update');
        console.log('[SessionManager] Cleared session state');
    } catch (error) {
        console.warn('[SessionManager] Failed to clear session state:', error);
    }
}

// Workflow-aware session resumption
async function resumeWorkflowSession(sessionState) {
    const { workflow, sessionId, view } = sessionState;
    console.log(`[SessionManager] Attempting to resume workflow: ${workflow}, session: ${sessionId}, view: ${view}`);

    try {
        // First, select the workflow
        window.globalState.currentWorkflow = workflow;

        // Then show the appropriate view with session resumption
        switch (view) {
            case 'chat':
                await showChatInterface(sessionId);
                break;
            case 'welcome':
            default:
                showWelcomePage();
                // Set currentWorkflow for reference
                window.globalState.currentWorkflow = workflow;
                break;
        }

        // Verify session exists and is valid
        const sessionValid = await validateSession(workflow, sessionId);
        if (!sessionValid) {
            console.warn(`[SessionManager] Session ${sessionId} for workflow ${workflow} is invalid`);
            addMessage('system', `Session ${sessionId.substring(0, 8)} not found. Starting new conversation.`, 'system');
            return false;
        }

        console.log(`[SessionManager] Successfully resumed session for ${workflow}`);
        return true;

    } catch (error) {
        console.error(`[SessionManager] Failed to resume session:`, error);
        // Clear stale session state on resume failure
        clearSessionState();
        showWelcomePage();
        addMessage('system', `Failed to resume previous session with ${workflow}.`, 'error');
        return false;
    }
}

// Validate session exists and is accessible
async function validateSession(workflow, sessionId) {
    if (!workflow || !sessionId) return false;

    try {
        const response = await fetch(`/api/chat_history/sessions/${sessionId}`);
        return response.ok;
    } catch (error) {
        console.warn(`[SessionManager] Failed to validate session ${sessionId}:`, error);
        return false;
    }
}

// LEFT-PANEL SESSION MENU: Option B - Expanded group under Chat History button
let sessionMenuInitialized = false;

function initializeSessionMenu() {
    if (sessionMenuInitialized) return;
    sessionMenuInitialized = true;

    // Insert session menu group after Chat History button
    const chatHistoryBtn = document.querySelector('#chat-history-btn');
    if (chatHistoryBtn) {
        const sessionMenuHTML = `
            <li class="menu-group-title session-menu-group" data-group="current-workflow-sessions" style="display: none;">
                <div class="group-header">
                    <button class="menu-button group-session" data-group="current-workflow-sessions">
                        <span class="inline-icon">💬</span>
                        <span id="session-menu-title">Current Workflow Sessions</span>
                    </button>
                    <button class="menu-button group-toggle session-toggle" data-group="current-workflow-sessions">
                        <span class="icon">▶</span>
                    </button>
                </div>
                <div class="group-content session-group-content" id="current-workflow-sessions-content" style="display: none;">
                    <div class="session-menu" id="current-workflow-session-menu">
                        <div class="session-loading">Loading sessions...</div>
                    </div>
                </div>
            </li>
        `;

        chatHistoryBtn.closest('li').insertAdjacentHTML('afterend', sessionMenuHTML);

        // Attach event handlers
        attachSessionMenuHandlers();

        console.log('[SessionMenu] Session menu initialized');
    }
}

function attachSessionMenuHandlers() {
    // Toggle session menu
    document.querySelectorAll('.session-toggle').forEach(toggle => {
        toggle.addEventListener('click', function() {
            const group = this.getAttribute('data-group');
            const content = document.getElementById(`${group}-content`);
            const isExpanded = content.style.display !== 'none';

            if (isExpanded) {
                content.style.display = 'none';
                this.innerHTML = '<span class="icon">▶</span>';
            } else {
                content.style.display = 'block';
                this.innerHTML = '<span class="icon">▼</span>';
            }
        });
    });
}

async function updateSessionMenu(workflow) {
    const sessionMenuGroup = document.querySelector('.session-menu-group');
    const sessionMenuTitle = document.getElementById('session-menu-title');
    const sessionMenu = document.getElementById('current-workflow-session-menu');

    if (!sessionMenuGroup || !sessionMenu) return;

    if (!workflow) {
        // Hide session menu when no workflow active
        sessionMenuGroup.style.display = 'none';
        return;
    }

    // Show session menu for active workflow
    sessionMenuGroup.style.display = 'list-item';
    sessionMenuTitle.textContent = `${workflow.replace('_', ' ').toUpperCase()} Sessions`;

    try {
        // Load sessions for current workflow
        const response = await fetch(`/api/${workflow}/chat_history`);
        const data = await response.json();

        if (data.sessions && data.sessions.length > 0) {
            const sessionHTML = data.sessions.map(session => {
                const isActive = window.globalState.currentChatSessionId === session.session_id;
                const timeAgo = formatTimeAgo(session.updated_at);
                const activeClass = isActive ? 'active-session' : '';
                const sessionIcon = isActive ? '🔥' : '📄';
                const displayTitle = session.title || `Session ${session.session_id.substring(0, 8)}`;
                const safeTitle = displayTitle.replace(/ /g, '&nbsp;'); // Preserve spaces

                return `
                    <li class="workflows session-item">
                        <button class="menu-button session-menu-button ${activeClass}" data-session-id="${session.session_id}" title="${displayTitle}" style="white-space: nowrap; display: flex; align-items: center; width: 100%;">
                            <span class="inline-icon">${sessionIcon}</span>
                            <span style="text-overflow: ellipsis; white-space: nowrap; overflow: hidden; flex: 1; font-size: 11px;">${safeTitle}</span>
                        </button>
                    </li>
                `;
            }).join('');

            sessionMenu.innerHTML = sessionHTML;
        } else {
            sessionMenu.innerHTML = '<div class="session-menu-empty">No sessions yet</div>';
        }

        // Attach event handlers
        attachSessionItemHandlers();

    } catch (error) {
        console.error('[SessionMenu] Failed to load sessions:', error);
        sessionMenu.innerHTML = '<div class="session-menu-error">Failed to load sessions</div>';
    }
}

function attachSessionItemHandlers() {
    // Resume session buttons (now links to menu-button click)
    document.querySelectorAll('.session-menu-button').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const sessionId = e.target.closest('button').dataset.sessionId;
            await resumeSessionFromMenu(sessionId);
        });
    });

    // Show all sessions button (opens full session manager)
    const showAllBtn = document.getElementById('show-all-sessions-btn');
    if (showAllBtn) {
        showAllBtn.addEventListener('click', () => {
            if (window.showSessionsUI) {
                window.showSessionsUI();
            } else {
                console.error('[SessionMenu] Session manager not available');
            }
        });
    }
}

// Updated: Pass workflow context when resuming sessions from menu
async function resumeSessionFromMenu(sessionId) {
    console.log(`[SessionMenu] Resuming session: ${sessionId} for workflow: ${window.globalState.currentWorkflow}`);

    if (window.showChatInterface) {
        // ShowChatInterface should now use workflow-specific endpoint
        await window.showChatInterface(sessionId);
        updateStatus('Session resumed from menu', 'success');
    }
}

function formatTimeAgo(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffHours = diffMs / (1000 * 60 * 60);

    if (diffHours < 1) {
        const diffMins = Math.floor(diffMs / (1000 * 60));
        return diffMins <= 1 ? 'Just now' : `${diffMins}m ago`;
    } else if (diffHours < 24) {
        return `${Math.floor(diffHours)}h ago`;
    } else {
        const diffDays = Math.floor(diffHours / 24);
        return `${diffDays}d ago`;
    }
}

// Enhanced workflow selection with persistent SESSION LIFECYCLE MANAGEMENT
async function selectWorkflowWithSessionManagement(workflow) {
    console.log(`[SessionManager] Selecting workflow: ${workflow}`);

    // Save current session state before switching
    saveCurrentSessionState();

    window.globalState.currentWorkflow = workflow;

    // STATUS BAR UPDATE: Always show current workflow in status bar
    const workflowDisplayName = workflow.replace('_', ' ').toUpperCase();
    console.log(`[StatusBar] Setting current_workflow to: ${workflowDisplayName}`);

    if (window.mainUIManager?.setStatusBar) {
        window.mainUIManager.setStatusBar('current_workflow', workflowDisplayName);
        console.log(`[StatusBar] Updated status bar via MainUIManager`);
    } else if (window.setStatusBar) {
        window.setStatusBar('current_workflow', workflowDisplayName);
        console.log(`[StatusBar] Updated status bar via global function`);
    } else {
        console.warn(`[StatusBar] No status bar update function available`, {
            mainUIManager: !!window.mainUIManager,
            setStatusBar: !!window.setStatusBar
        });
    }

    // WORKFLOW LIFECYCLE: Backend manages session IDs for workflows
    const backendSessionId = await getBackendWorkflowSessionId(workflow);
    console.log(`[SessionManager] Using backend session ${backendSessionId} for ${workflow}`);

    showLoadingPage(`${workflow.replace('-', ' ').toUpperCase()} Workflow`, 'Loading RAG indexes...');

    // AUTO-COLLAPSE DYNAMIC WORKFLOWS: When workflow active, collapse workflow selection
    setTimeout(async () => {
        // Critical: Ensure workflow context is properly set BEFORE showing chat interface
        window.globalState.currentWorkflow = workflow;
        window.globalState.currentChatSessionId = backendSessionId;

        // Backend SessionLifecycleManager ensures ONE session per workflow
        await showChatInterface(backendSessionId);
        updateStatus(`Ready to chat with ${workflow} workflow.`, 'success');

        // UPDATE SESSION MENU: Show sessions for active workflow
        initializeSessionMenu();
        await updateSessionMenu(workflow);

        console.log(`[SessionManager] Workflow context set: ${workflow} with session ${backendSessionId}`);
    }, 1500);
}

// Get persistent session ID for workflow (one session per workflow, persisted in localStorage)
function getWorkflowPersistentSessionId(workflow) {
    const storageKey = `workflow_sessions`;
    let workflowSessions = {};

    // Load existing workflow sessions from localStorage
    try {
        const stored = localStorage.getItem(storageKey);
        if (stored) {
            workflowSessions = JSON.parse(stored);
        }
    } catch (e) {
        console.warn('[SessionManager] Failed to load workflow sessions from localStorage');
    }

    // Get or create session ID for this workflow
    if (!workflowSessions[workflow]) {
        workflowSessions[workflow] = generateUUID();
        console.log(`[SessionManager] Created new persistent session for ${workflow}: ${workflowSessions[workflow]}`);
    } else {
        console.log(`[SessionManager] Reusing persistent session for ${workflow}: ${workflowSessions[workflow]}`);
    }

    // Save back to localStorage
    try {
        localStorage.setItem(storageKey, JSON.stringify(workflowSessions));
    } catch (e) {
        console.warn('[SessionManager] Failed to save workflow sessions to localStorage');
    }

    return workflowSessions[workflow];
}

// Get backend-managed session ID for workflow (calls server endpoint)
async function getBackendWorkflowSessionId(workflow) {
    console.log(`[SessionManager] Requesting backend session ID for ${workflow}`);

    try {
        const response = await fetch(`/api/workflow_sessions/${workflow}/id`);

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            console.error(`[SessionManager] Backend session request failed: ${response.status} ${response.statusText}`, errorData);
            throw new Error(`Failed to get session from backend: ${response.status}`);
        }

        const data = await response.json();
        const sessionId = data.session_id;

        console.log(`[SessionManager] Backend returned session ${sessionId} for ${workflow}`);
        return sessionId;

    } catch (error) {
        console.error(`[SessionManager] Failed to get backend session for ${workflow}:`, error);

        // Fallback to local session management if backend fails
        console.warn(`[SessionManager] Falling back to local session management for ${workflow}`);
        return getWorkflowPersistentSessionId(workflow);
    }
}

// Detect existing sessions for a specific workflow
async function detectExistingWorkflowSession(workflow) {
    try {
        const response = await fetch('/api/chat_history/sessions');
        if (!response.ok) return null;

        const data = await response.json();
        const sessions = data.sessions || [];

        // Find most recent session for this workflow
        const workflowSessions = sessions
            .filter(session => session.workflow_name === workflow)
            .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

        return workflowSessions.length > 0 ? workflowSessions[0].session_id : null;

    } catch (error) {
        console.warn(`[SessionManager] Failed to detect existing session for ${workflow}:`, error);
        return null;
    }
}

// Workflow-aware session resumption from chat history - make it globally available
window.resumeWorkflowSession = function(sessionState) {
    // Handle both object and individual parameter calls
    let sessionId, workflowType;
    if (typeof sessionState === 'object' && sessionState.sessionId) {
        sessionId = sessionState.sessionId;
        workflowType = sessionState.workflow;
    } else {
        // Deprecated: Fallback for old individual parameter calls
        sessionId = arguments[0];
        workflowType = arguments[1];
    }

    console.log(`[SessionManager] Resuming session ${sessionId} for workflow ${workflowType}`);

    // Set current workflow
    window.globalState.currentWorkflow = workflowType;

    // Store for potential cross-tab resumption
    window.globalState.pendingSessionResume = { sessionId, workflowType };

    // Navigate to chat interface with workflow-specific session
    if (window.showChatInterface) {
        window.showChatInterface(sessionId);
    } else {
        // Fallback navigation
        window.location.href = '/';
    }
};

// Initialize session recovery on page load
async function initializeSessionRecovery() {
    console.log('[SessionManager] Initializing session recovery...');

    // Check for URL parameters (cross-tab session resumption)
    const urlParams = new URLSearchParams(window.location.search);
    const resumeSessionId = urlParams.get('resume_session');
    const resumeWorkflow = urlParams.get('resume_workflow');

    if (resumeSessionId && resumeWorkflow) {
        console.log(`[SessionManager] URL-based session resumption: ${resumeSessionId} for ${resumeWorkflow}`);
        // Clear URL parameters after processing
        const newUrl = window.location.pathname;
        window.history.replaceState({}, document.title, newUrl);

        const sessionState = {
            workflow: resumeWorkflow,
            sessionId: resumeSessionId,
            view: 'chat'
        };

        await resumeWorkflowSession(sessionState);
        return;
    }

    // Check for localStorage session recovery (browser refresh)
    const savedSession = loadPreviousSessionState();
    if (savedSession) {
        console.log('[SessionManager] Found saved session, attempting recovery');
        updateStatus('Restoring previous session...', 'in-progress');

        const success = await resumeWorkflowSession(savedSession);
        if (success) {
            updateStatus('Session restored successfully.', 'success');
        } else {
            updateStatus('Could not restore session.', 'error');
        }
        return;
    }

    console.log('[SessionManager] No session recovery needed, showing welcome page');
}

// Update workflow button handlers to use enhanced session management
async function enhancedWorkflowButtonHandler(event) {
    event.preventDefault();
    event.stopPropagation();

    // Better workflow detection for left-panel buttons (which have multiple classes)
    const target = event.target.closest('button[data-workflow]');
    const workflow = target?.dataset?.workflow;

    if (!workflow) {
        console.warn('[SessionManager] Could not find workflow from button click');
        return;
    }

    await selectWorkflowWithSessionManagement(workflow);
}

// Make functions globally available for chat history manager
window.saveCurrentSessionState = saveCurrentSessionState;
window.resumeWorkflowSession = window.resumeWorkflowSession;
window.initializeSessionRecovery = initializeSessionRecovery;

document.addEventListener('DOMContentLoaded', () => {
    // Initialize UI components and event handlers

    // Initialize elements
    const chatArea = document.getElementById('chat-area');
    const welcomePage = document.getElementById('welcome-page');
    const chatInterface = document.getElementById('chat-interface');
    const messageContainer = document.getElementById('message-container');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const menuToggle = document.getElementById('menu-toggle');
    const leftPanel = document.getElementById('left-panel');
    const resizer = document.getElementById('resizer');
    let lastWidth = 0;

    // View management functions
    function hideAllViews() {
        document.getElementById('welcome-page').style.display = 'none';
        document.getElementById('loading-page').style.display = 'none';
        document.getElementById('chat-interface').style.display = 'none';
        document.getElementById('settings-ui-container').style.display = 'none';
        document.getElementById('config-ui-container').style.display = 'none';
        document.getElementById('chat-history-ui-container').style.display = 'none';
    }

    function showWelcomePage() {
        currentView = 'welcome';
        hideAllViews();
        document.getElementById('welcome-page').style.display = 'block';
    }

    function showLoadingPage(title, message) {
        currentView = 'loading';
        hideAllViews();
        document.getElementById('loading-page').style.display = 'flex';
        document.getElementById('loading-title').textContent = title;
        document.getElementById('loading-message').textContent = message;
    }

    // Make showLoadingPage globally available for session management functions
    window.showLoadingPage = showLoadingPage;

    async function showChatInterface(sessionIdToResume = null) {
        currentView = 'chat';
        hideAllViews();
        document.getElementById('chat-interface').style.display = 'flex';
        const messageContainer = document.getElementById('message-container');
        if (messageContainer) {
            messageContainer.innerHTML = ''; // Clear messages when switching to chat
        }



        if (sessionIdToResume) {
            currentChatSessionId = sessionIdToResume;
            window.globalState.currentChatSessionId = sessionIdToResume;

            // Fetch and display existing messages for the session using workflow-specific endpoint
            try {
                const response = await fetch(`/api/${window.globalState.currentWorkflow}/chat_history/${sessionIdToResume}`);
                if (response.ok) {
                    const sessionData = await response.json();
                    sessionData.messages.forEach(msg => {
                        const messageId = msg.message_id || msg.id;
                        if (window.chatUIManager?.addMessage) {
                            window.chatUIManager.addMessage(msg.role, msg.content, 'normal', messageId);
                        } else {
                            addMessage(msg.role, msg.content); // Fallback for old system
                        }
                    });
                    addMessage('system', `Resumed chat with ${window.globalState.currentWorkflow} workflow (Session: ${currentChatSessionId.substring(0, 8)})`, 'system');
                } else {
                    console.error('Failed to load session for resumption:', sessionIdToResume);
                    addMessage('system', `Failed to resume chat session ${sessionIdToResume.substring(0, 8)}. Starting new conversation.`, 'error');
                    // Clear stale session state when resumption fails
                    clearSessionState();
                    currentChatSessionId = generateUUID(); // Start a new one if resume fails
                    window.globalState.currentChatSessionId = currentChatSessionId; // Also set global
                    addMessage('system', `Ready to chat with ${window.globalState.currentWorkflow} workflow (New Session: ${currentChatSessionId.substring(0, 8)})`, 'system');
                }
            } catch (error) {
                console.error('Error loading session for resumption:', error);
                addMessage('system', `Error resuming chat session. Starting new conversation.`, 'error');
                // Clear stale session state when resumption fails
                clearSessionState();
                currentChatSessionId = generateUUID(); // Start a new one if error
                window.globalState.currentChatSessionId = currentChatSessionId; // Also set global
                    addMessage('system', `Ready to chat with ${window.globalState.currentWorkflow} workflow (New Session: ${currentChatSessionId.substring(0, 8)})`, 'system');
            }
        } else {
            // Start a new session
            currentChatSessionId = generateUUID();
            window.globalState.currentChatSessionId = currentChatSessionId; // Also set global
            if (window.globalState.currentWorkflow) {
                addMessage('system', `Ready to chat with ${window.globalState.currentWorkflow} workflow (New Session: ${currentChatSessionId.substring(0, 8)})`, 'system');
            }
        }
    }

    // Make updateStatus globally available for session management functions
    window.updateStatus = updateStatus;

    // Make showChatInterface globally available for session management functions
    window.showChatInterface = showChatInterface;

    function showSettingsUI() {
        currentView = 'settings';
        hideAllViews();
        document.getElementById('settings-ui-container').style.display = 'block';
    }

    function showConfigUI() {
        currentView = 'config';
        hideAllViews();
        document.getElementById('config-ui-container').style.display = 'block';
    }

    function showChatHistoryUI() {
        currentView = 'chat_history';
        hideAllViews();
        document.getElementById('chat-history-ui-container').style.display = 'block';

        // Load chat history UI content if not already loaded
        const container = document.getElementById('chat-history-ui-container');
        if (container && container.children.length === 0) {
            // Load chat history HTML content
            fetch('/static/chat_history_ui.html')
                .then(response => response.text())
                .then(html => {
                    container.innerHTML = html;
                    // Initialize chat history manager after loading
                    if (typeof ChatHistoryManager !== 'undefined') {
                        window.chatHistoryManager = new ChatHistoryManager();
                    }
                    updateStatus('Chat history loaded successfully.', 'success');
                })
                .catch(error => {
                    console.error('Failed to load chat history UI:', error);
                    container.innerHTML = '<div class="error-message">Failed to load chat history interface</div>';
                    updateStatus('Failed to load chat history.', 'error');
                });
        } else if (container && container.children.length > 0) {
            // UI already loaded, just refresh if manager exists
            if (typeof ChatHistoryManager !== 'undefined' && window.chatHistoryManager) {
                window.chatHistoryManager.refreshSessions();
            }
        }
    }

    // Enhanced chat message handling with UI enhancements
    function addMessage(sender, content, messageType = 'normal') {
        const messageContainer = document.getElementById('message-container');
        // Ensure messageContainer exists before trying to add messages
        if (!messageContainer) {
            console.warn('Message container not found, cannot add message. Current view:', currentView);
            return;
        }

        const messageElement = document.createElement('div');
        messageElement.classList.add('message');

        // Determine message class based on sender and type
        if (messageType === 'system') {
            messageElement.classList.add('system-message');
        } else if (messageType === 'error') {
            messageElement.classList.add('error-message');
        } else {
            messageElement.classList.add(sender === 'user' ? 'user-message' : 'ai-message');
        }

        const senderElement = document.createElement('div');
        senderElement.classList.add('message-sender');

        // Set sender text based on type and sender
        if (messageType === 'system') {
            senderElement.textContent = 'System';
        } else if (messageType === 'error') {
            senderElement.textContent = 'Error';
        } else {
            senderElement.textContent = sender === 'user' ? 'You' : 'AI';
        }

        const contentElement = document.createElement('div');
        contentElement.classList.add('message-content');
        contentElement.innerHTML = content;

        messageElement.appendChild(senderElement);
        messageElement.appendChild(contentElement);
        messageContainer.appendChild(messageElement);

        // Apply UI enhancements if available
        if (window.chatUIEnhancements) {
            window.chatUIEnhancements.enhanceMessageElement(messageElement);
        }

        messageContainer.scrollTop = messageContainer.scrollHeight;
    }

    // Enhanced send message to workflow API with UI enhancements
    async function sendMessage() {
        const userInput = document.getElementById('user-input');
        if (!userInput) {
            console.warn('User input not found');
            return;
        }

        const message = userInput.value.trim();
        if (!message || !window.globalState.currentWorkflow) {
            if (!window.globalState.currentWorkflow) {
                addMessage('system', 'Please select a workflow first.', 'system');
            }
            return;
        }

        // Add user message
        addMessage('user', message);
        userInput.value = '';

        updateStatus(`Sending message to ${window.globalState.currentWorkflow}...`, 'in-progress');

        // Show typing indicator for AI response
        let typingIndicator = null;
        if (window.chatUIEnhancements) {
            typingIndicator = window.chatUIEnhancements.showTypingIndicator();
        }

        try {
            const payload = { question: message };
            if (currentChatSessionId) {
                payload.session_id = currentChatSessionId;
            }

            // Use unified workflow execution endpoint (executor_endpoint.py)
            const response = await fetch(`/api/chat/${window.globalState.currentWorkflow}/session/${currentChatSessionId || 'new'}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            // Hide typing indicator and add AI response
            if (window.chatUIEnhancements && typingIndicator) {
                window.chatUIEnhancements.hideTypingIndicator();
            }

            // Extract response content from unified API response and use message_id if available
            const messageId = data.message_id;
            if (data.response) {
                if (window.chatUIManager?.addMessage) {
                    window.chatUIManager.addMessage('ai', data.response, 'normal', messageId);
                } else {
                    addMessage('ai', data.response);
                }
            } else {
                if (window.chatUIManager?.addMessage) {
                    window.chatUIManager.addMessage('ai', 'No response generated', 'normal', messageId);
                } else {
                    addMessage('ai', 'No response generated');
                }
            }

            // Update session ID if new session was created
            if (data.session_id && !currentChatSessionId) {
                currentChatSessionId = data.session_id;
                console.log(`[sendMessage] New session created: ${currentChatSessionId}`);
            }

            updateStatus(`Message sent to ${window.globalState.currentWorkflow}.`, 'success');

        } catch (error) {
            console.error('Error sending message:', error);

            // Hide typing indicator
            if (window.chatUIEnhancements && typingIndicator) {
                window.chatUIEnhancements.hideTypingIndicator();
            }

            // Use enhanced error handling if available
            if (window.chatUIEnhancements) {
                window.chatUIEnhancements.showErrorWithRetry(
                    `Failed to send message: ${error.message}`,
                    () => sendMessage() // Retry function
                );
            } else {
                // Fallback to basic error message
                addMessage('ai', `<p style="color: red;">Error: ${error.message}</p>`);
            }

            updateStatus(`Error sending message.`, 'error');
        }
    }

    // Event listeners for chat
    sendButton.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });

    // New Session button handler - prepares UI for NEW SESSION creation (SessionAuthority singleton responsibility)
    const newSessionBtn = document.getElementById('new-session-btn');
    if (newSessionBtn) {
        newSessionBtn.addEventListener('click', async () => {
            if (!window.globalState.currentWorkflow) {
                addMessage('system', 'Please select a workflow first.', 'error');
                return;
            }

            console.log(`[NewSession] Preparing for new session with workflow: ${window.globalState.currentWorkflow}`);

            try {
                // Save current session state before preparing for new one
                saveCurrentSessionState();

                // CLEAR local state - DO NOT generate UUID (SessionAuthority singleton is responsible for session creation)
                // Frontend should NOT manage session creation - that's SessionAuthority's single responsibility
                currentChatSessionId = null;  // NULL = let SesisonAuthority create proper session ID
                window.globalState.currentChatSessionId = null;

                // Clear the chat interface UI
                const messageContainer = document.getElementById('message-container');
                if (messageContainer) {
                    messageContainer.innerHTML = '';
                }

                // Add system message indicating ready for new session
                addMessage('system', `✨ Ready for new session with ${window.globalState.currentWorkflow.replace(/[_\-]/g, ' ')} workflow`);
                addMessage('system', '💬 Send your first message to create a new session through SessionAuthority', 'system');

                updateStatus(`Prepared for new ${window.globalState.currentWorkflow} session (send message to create)`, 'info');
                console.log(`[NewSession] UI prepared - session creation delegated to SessionAuthority singleton`);

            } catch (error) {
                console.error('[NewSession] Failed to prepare new session:', error);
                updateStatus('Failed to prepare new session', 'error');
                addMessage('system', '❌ Failed to prepare new session', 'error');
            }
        });
        console.log('[EventHandler] New Session button event handler attached (SessionAuthority design compliant)');
    } else {
        console.warn('[EventHandler] New Session button not found');
    }

    // Enhanced Workflow button handling with session management
    document.querySelectorAll('.workflow-button').forEach((button) => {
        button.addEventListener('click', enhancedWorkflowButtonHandler);
    });

    // Menu toggle functionality
    if (menuToggle) {
        menuToggle.addEventListener('click', () => {
            const isCollapsed = leftPanel.classList.toggle('collapsed');

            const dynamicWorkflowsContent = document.getElementById('dynamic-workflows-content');

            if (isCollapsed) {
                lastWidth = leftPanel.getBoundingClientRect().width;
                leftPanel.style.width = '60px';

                if (dynamicWorkflowsContent) dynamicWorkflowsContent.style.display = 'none';
            } else {
                if (lastWidth > 0) {
                    leftPanel.style.width = `${lastWidth}px`;
                }
                if (dynamicWorkflowsContent) dynamicWorkflowsContent.style.display = 'block';
            }
        });
    }

    // Status bar functions
    async function fetchAndUpdateStaticStatus() {
        try {
            const response = await fetch('/api/user_state', {
                headers: {
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache',
                    'Expires': '0'
                }
            });
            if (response.ok) {
                const userState = await response.json();
                setStatusBar('current_model_provider', userState.current_model_provider || '');
                setStatusBar('current_model_id', userState.current_model_id || '');
                setStatusBar('current_workflow', userState.current_workflow || '');
            }
        } catch (error) {
            console.error('Failed to fetch user state:', error);
        }
    }

    // Status management functions removed - now handled by MainUIManager.updateStatus() and setStatusBar()

    // Initialize status bar
    fetchAndUpdateStaticStatus();

// Workflow Management Functions
// ==============================
// Available workflows loaded from API
let availableWorkflows = [];

// Load workflows from API endpoint
async function loadAvailableWorkflows() {
    try {
        console.log('[WorkflowManager] Loading workflows from API...');
        const response = await fetch('/api/workflows');

        if (!response.ok) {
            console.error('[WorkflowManager] Failed to load workflows from API:', response.status);
            // Fallback to empty list if API fails
            availableWorkflows = [];
            return [];
        }

        const data = await response.json();
        availableWorkflows = data.workflows || [];
        console.log('[WorkflowManager] Loaded workflows:', availableWorkflows.length);
        return availableWorkflows;
    } catch (error) {
        console.error('[WorkflowManager] Error loading workflows:', error);
        availableWorkflows = [];
        return [];
    }
}

// Get workflow by ID
function getWorkflowById(workflowId) {
    return availableWorkflows.find(w => w.id === workflowId);
}

// Generate workflow card HTML from configuration
function generateWorkflowCard(workflow) {
    return `
        <div class="workflow-card" data-workflow="${workflow.id}">
            <div class="workflow-icon">${workflow.icon}</div>
            <div class="workflow-info">
                <strong>${workflow.display_name}</strong>
                <small>${workflow.description}</small>
            </div>
            <button class="select-workflow-btn" data-workflow="${workflow.id}">Select</button>
        </div>
    `;
}

// Generate workflow menu item HTML from configuration
function generateWorkflowMenuItem(workflow) {
    const displayName = workflow.display_name.replace(/ /g, '&nbsp;'); // Preserve spaces in button text

    return `
        <li class="workflows">
            <button class="menu-button workflow-button" data-workflow="${workflow.id}" title="${workflow.display_name}">
                <span class="inline-icon">${workflow.icon}</span>
                <span>${displayName}</span>
            </button>
        </li>
    `;
}

// Update welcome page workflow grid with loaded workflows - Phase 5.3: Dynamic workflow loading
async function updateWelcomePageWorkflows() {
    const workflowGrid = document.getElementById('dynamic-workflow-grid');
    if (!workflowGrid) {
        console.warn('[WorkflowManager] Dynamic workflow grid not found');
        return;
    }

    console.log('[WorkflowManager] Updating welcome page with dynamic workflows...');

    // Show loading state
    workflowGrid.innerHTML = `
        <div class="loading-workflows">
            <div class="loading-spinner"></div>
            Loading available workflows...
        </div>
    `;

    try {
        // Load workflows from API endpoint
        if (availableWorkflows.length === 0) {
            await loadAvailableWorkflows();
        }

        if (availableWorkflows.length > 0) {
            // Generate dynamic workflow cards from API data
            const workflowCards = availableWorkflows.map(generateWorkflowCard).join('');
            workflowGrid.innerHTML = workflowCards;

            // Re-attach event handlers for new buttons
            attachWorkflowSelectionHandlers();

            console.log(`[WorkflowManager] Successfully loaded ${availableWorkflows.length} workflows in welcome page`);
            updateStatus(`Loaded ${availableWorkflows.length} workflows successfully.`, 'success');

            // Phase 5.3 - Critical: Attach event handlers to dynamically loaded workflow buttons
            console.log('[WorkflowManager] Attaching event handlers to dynamic workflow buttons...');
            attachWorkflowSelectionHandlers();
            console.log('[WorkflowManager] Event handlers attached successfully');
        } else {
            workflowGrid.innerHTML = `
                <div class="error-message">
                    <strong>No workflows available</strong><br>
                    Please check your system configuration and try refreshing the page.
                </div>
            `;
        }
    } catch (error) {
        console.error('[WorkflowManager] Error updating welcome page workflows:', error);
        workflowGrid.innerHTML = `
            <div class="error-message">
                <strong>Failed to load workflows</strong><br>
                ${error.message}
            </div>
        `;
        updateStatus('Failed to load workflows.', 'error');
    }
}

// Update left panel menu with loaded workflows
async function updateLeftPanelWorkflows() {
    // For dynamic workflows section
    const dynamicWorkflowsContent = document.getElementById('dynamic-workflows-content');
    if (!dynamicWorkflowsContent) {
        console.warn('[WorkflowManager] Dynamic workflows content element not found');
        return;
    }

    // Find the workflow list container
    let workflowsList = dynamicWorkflowsContent.querySelector('.workflows-list');
    if (!workflowsList) {
        console.warn('[WorkflowManager] Workflows list element not found');
        return;
    }

    console.log('[WorkflowManager] Updating left panel workflows...', 'availableWorkflows:', availableWorkflows.length);

    if (availableWorkflows.length === 0) {
        await loadAvailableWorkflows();
        console.log('[WorkflowManager] After loading availableWorkflows count:', availableWorkflows.length);
    }

    if (availableWorkflows.length > 0) {
        // Clear existing workflow items (but keep header if any)
        workflowsList.querySelectorAll('.workflows').forEach(li => li.remove());

        // Add new workflow items
        availableWorkflows.forEach(workflow => {
            const menuItem = generateWorkflowMenuItem(workflow);
            workflowsList.insertAdjacentHTML('beforeend', menuItem);
        });

        console.log('[WorkflowManager] Added', availableWorkflows.length, 'workflow menu items');

        // Re-attach event handlers for new buttons
        attachLeftPanelWorkflowHandlers();
    } else {
        console.warn('[WorkflowManager] No workflows available to display in left panel');
    }
}

// Attach event handlers to workflow selection buttons
function attachWorkflowSelectionHandlers() {
    document.querySelectorAll('.select-workflow-btn').forEach(button => {
        button.addEventListener('click', async (event) => {
            event.preventDefault();
            const workflowId = event.target.getAttribute('data-workflow');

            // Phase 5.3 - Direct workflow ID usage for dynamic workflows
            if (workflowId) {
                console.log(`[WorkflowManager] Welcome page workflow selection: ${workflowId}`);
                await selectWorkflowWithSessionManagement(workflowId);
            }
        });
    });
}

// Attach event handlers to left panel workflow buttons
function attachLeftPanelWorkflowHandlers() {
    document.querySelectorAll('.workflow-button').forEach(button => {
        button.addEventListener('click', enhancedWorkflowButtonHandler);
    });
}

// Initialize dynamic workflow loading
async function initializeDynamicWorkflows() {
    console.log('[WorkflowManager] Initializing dynamic workflows...');

    try {
        await loadAvailableWorkflows();

        // Update UI components with loaded workflows
        await updateWelcomePageWorkflows();
        await updateLeftPanelWorkflows();

        console.log('[WorkflowManager] Dynamic workflows initialized with', availableWorkflows.length, 'workflows');
        updateStatus(`Loaded ${availableWorkflows.length} workflows successfully.`, 'success');

    } catch (error) {
        console.error('[WorkflowManager] Failed to initialize dynamic workflows:', error);
        updateStatus('Failed to load workflows.', 'error');
    }
}

    // Resizer functionality
    let startX = 0;
    let startWidth = 0;

    function onMouseMove(e) {
        const dx = e.clientX - startX;
        const newWidth = startWidth + dx;
        leftPanel.style.width = `${Math.min(Math.max(newWidth, 60), 500)}px`;
    }

    function onMouseUp() {
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
        lastWidth = leftPanel.getBoundingClientRect().width;
    }

    if (resizer && leftPanel) {
        resizer.addEventListener('mousedown', (e) => {
            if (leftPanel.classList.contains('collapsed')) return;

            startX = e.clientX;
            startWidth = leftPanel.getBoundingClientRect().width;
            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
        });
    }

    // Group toggle functionality
    document.querySelectorAll('.group-toggle').forEach(toggle => {
        toggle.addEventListener('click', function() {
            const group = this.getAttribute('data-group');
            const content = document.getElementById(`${group}-content`);

            if (content) {
                console.log(`[GroupToggle] Toggling group: ${group}`);
                if (content.style.display === 'none' || content.style.display === '') {
                    content.style.display = 'block';
                    this.innerHTML = '<span class="icon">&#9776;</span>';
                    console.log(`[GroupToggle] Expanded group: ${group}`);
                } else {
                    content.style.display = 'none';
                    this.innerHTML = '<span class="icon">&#9776;</span>';
                    console.log(`[GroupToggle] Collapsed group: ${group}`);
                }
            } else {
                console.warn(`[GroupToggle] Content element not found for group: ${group}`);
            }
        });
    });

    // Note: Workflow selection handlers are now managed by attachWorkflowSelectionHandlers()
    // which is called after dynamic workflow loading

    // Other button handlers
    document.getElementById('login-btn').addEventListener('click', async () => {
        const userId = prompt("Enter User ID to associate (e.g., Bernard):");
        if (userId) {
            updateStatus(`Associating user ${userId}...`);
            try {
                const response = await fetch('/api/associate_user', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: userId })
                });
                const data = await response.json();
                if (response.ok) {
                    alert(data.message);
                    updateStatus(`User associated: ${userId}.`);
                } else {
                    alert(`Error: ${data.detail || data.message}`);
                    updateStatus(`Failed to associate user.`);
                }
            } catch (error) {
                console.error('Error associating user:', error);
                alert('An error occurred while associating user.');
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
        window.location.href = '/static/modules/generate/generate_ui.html';
    });

    const chatHistoryBtn = document.getElementById('chat-history-btn');
    if (chatHistoryBtn) {
        chatHistoryBtn.addEventListener('click', async () => {
            console.log('[DEBUG] Chat History button clicked - using SessionManager');
            showLoadingPage('Session Management', 'Loading session management interface...');

            setTimeout(async () => {
                // Use SessionManager for proper Chat History UI with workflow grouping and advanced features
                if (typeof SessionManager !== 'undefined') {
                    // SessionManager creates the sophisticated UI dynamically (matches OK.html structure)
                    if (window.sessionManager && window.sessionManager.toggleSessions) {
                        window.sessionManager.toggleSessions();
                        updateStatus('Session management interface loaded successfully.', 'success');
                    } else {
                        console.warn('[DEBUG] SessionManager class available but instance not ready, creating one...');
                        window.sessionManager = new SessionManager();
                        // Give it a moment to initialize
                        setTimeout(() => {
                            if (window.sessionManager && window.sessionManager.toggleSessions) {
                                window.sessionManager.toggleSessions();
                                updateStatus('Session management interface loaded successfully.', 'success');
                            } else {
                                console.error('[DEBUG] Failed to initialize SessionManager');
                                updateStatus('Failed to load session management interface.', 'error');
                                showWelcomePage();
                            }
                        }, 200);
                    }
                } else {
                    console.error('[DEBUG] SessionManager not available, falling back to basic ChatHistoryManager');
                    // Fallback to old method if SessionManager unavailable
                    await showChatHistoryUI();
                    updateStatus('Basic chat history loaded.', 'info');
                }
            }, 1000);
        });
        console.log('[DEBUG] Chat History (Session Manager) button event listener attached');
    } else {
        console.error('[DEBUG] Chat History button not found!');
    }

    // Session Manager UI is now handled by the Chat History button and session-manager.js
    // The sessions functionality is integrated into the chat history interface
    console.log('[DEBUG] Session management integrated into Chat History UI - no separate sessions button needed');

    // Initialize dynamic workflow loading from configuration
    initializeDynamicWorkflows();



    // Initial state - Show welcome page by default (will be overridden if session recovery finds something)
    showWelcomePage();
    document.getElementById('dynamic-workflows-content').style.display = 'block';
    lastWidth = leftPanel.getBoundingClientRect().width;
});
