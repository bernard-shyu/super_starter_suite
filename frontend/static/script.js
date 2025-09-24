// Global status bar structure
const statusBarStruct = {
    status_message: 'Ready',
    current_model_provider: '',
    current_model_id: '',
    current_workflow: ''
};

// Global utility functions
function generateUUID() {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
        return crypto.randomUUID();
    }
    // Simple fallback UUID generation
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

// Theme management
let currentTheme = 'light_classic';
let availableThemes = [];

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
    await applyTheme(currentTheme);
}

async function applyTheme(themeName) {
    if (!themeName) return;

    console.log(`[DEBUG] Starting theme application: ${themeName}`);

    try {
        // Parse theme into color and style
        const [color, style] = themeName.split('_');

        console.log(`[DEBUG] Parsed theme components - Color: ${color}, Style: ${style}`);

        // Remove old style CSS files before loading new ones
        // This ensures clean switching between Classic and Modern styles
        removeOldStyleCSS();

        // Load style-specific CSS files FIRST (main CSS)
        console.log(`[DEBUG] Loading style-specific CSS files first`);
        await loadThemeCSS(`/static/config_ui.${style}.css`);
        await loadThemeCSS(`/static/main_style.${style}.css`);

        // Load color-specific CSS LAST (theme CSS) - so theme variables take precedence
        console.log(`[DEBUG] Loading color theme CSS last: /static/themes/${color}.css`);
        await loadThemeCSS(`/static/themes/${color}.css`);

        // Apply theme class to body for additional styling
        document.body.className = document.body.className.replace(/theme-\w+/g, '');
        document.body.classList.add(`theme-${color}`, `style-${style}`);

        console.log(`[DEBUG] Applied theme ${themeName} classes to body: theme-${color}, style-${style}`);
    } catch (error) {
        console.error('Error applying theme:', error);
    }
}

// Function to remove old style CSS files
function removeOldStyleCSS() {
    // Remove any existing style-specific CSS files
    const styleCSSFiles = [
        'config_ui.classic.css',
        'config_ui.modern.css',
        'main_style.classic.css',
        'main_style.modern.css'
    ];

    styleCSSFiles.forEach(filename => {
        const existingLink = document.querySelector(`link[href*="${filename}"]`);
        if (existingLink) {
            existingLink.remove();
            console.log(`Removed old CSS file: ${filename}`);
        }
    });
}

async function loadThemeCSS(href) {
    return new Promise((resolve, reject) => {
        console.log(`[DEBUG] Starting CSS load for: ${href}`);

        // Check if CSS is already loaded
        let existingLink = document.querySelector(`link[href="${href}"]`);

        if (existingLink) {
            console.log(`[DEBUG] Removing existing CSS link for: ${href}`);
            // For theme switching, we need to ensure the CSS is reloaded
            // Remove the existing link and create a new one to force reload
            existingLink.remove();
        }

        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = href + '?v=' + Date.now(); // Add timestamp to prevent caching

        link.onload = () => {
            // console.log(`[DEBUG] Successfully loaded CSS: ${href}`);
            resolve();
        };

        link.onerror = (event) => {
            console.error(`[DEBUG] Failed to load CSS: ${href}`, event);
            reject(new Error(`Failed to load CSS: ${href}`));
        };

        document.head.appendChild(link);
        // console.log(`[DEBUG] Added CSS link to head for: ${href}`);
    });
}

async function switchTheme(themeName) {
    if (!availableThemes.includes(themeName)) {
        console.error(`Theme '${themeName}' is not available`);
        return false;
    }

    try {
        const response = await fetch('/api/themes/current', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ theme: themeName })
        });

        if (response.ok) {
            const data = await response.json();
            currentTheme = themeName;
            await applyTheme(themeName);
            console.log(`Theme switched to: ${themeName}`);
            return true;
        } else {
            const error = await response.json();
            console.error('Failed to switch theme:', error.detail);
            return false;
        }
    } catch (error) {
        console.error('Error switching theme:', error);
        return false;
    }
}

// Make theme functions globally available
window.switchTheme = switchTheme;
window.getCurrentTheme = () => currentTheme;
window.getAvailableThemes = () => availableThemes;

// Chat functionality
let currentWorkflow = null;
let currentChatSessionId = null; // Current chat session ID
let currentView = 'chat'; // 'chat', 'settings', 'config', 'generate'
let pendingSessionResume = null; // Store session to resume on page load

// Enhanced Session Management - Phase 4.6 Implementation
// ======================================================

/**
 * Session Management Functions for Cross-Workflow Persistence
 */

// Save current session state to localStorage for persistence
function saveCurrentSessionState() {
    if (!currentWorkflow || !currentChatSessionId) return;

    // Only save session state with actual messages (not just workflow selection)
    const messageCount = document.getElementById('message-container')?.children.length || 0;
    if (messageCount === 0) {
        console.log('[SessionManager] Skipping session save - no messages yet');
        return;
    }

    const sessionState = {
        workflow: currentWorkflow,
        sessionId: currentChatSessionId,
        view: currentView,
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
        currentWorkflow = workflow;

        // Then show the appropriate view with session resumption
        switch (view) {
            case 'chat':
                await showChatInterface(sessionId);
                break;
            case 'welcome':
            default:
                showWelcomePage();
                // Set currentWorkflow for reference
                currentWorkflow = workflow;
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

// Enhanced workflow selection with persistent SESSION LIFECYCLE MANAGEMENT
async function selectWorkflowWithSessionManagement(workflow) {
    console.log(`[SessionManager] Selecting workflow: ${workflow}`);

    // Save current session state before switching
    saveCurrentSessionState();

    currentWorkflow = workflow;

    // WORKFLOW LIFECYCLE: Backend manages session IDs for workflows
    const backendSessionId = await getBackendWorkflowSessionId(workflow);
    console.log(`[SessionManager] Using backend session ${backendSessionId} for ${workflow}`);

    showLoadingPage(`${workflow.replace('-', ' ').toUpperCase()} Workflow`, 'Loading RAG indexes...');

    setTimeout(() => {
        // Backend SessionLifecycleManager ensures ONE session per workflow
        showChatInterface(backendSessionId);
        updateStatus(`Ready to chat with ${workflow} workflow.`, 'success');
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
            .filter(session => session.workflow_type === workflow)
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
    currentWorkflow = workflowType;

    // Store for potential cross-tab resumption
    pendingSessionResume = { sessionId, workflowType };

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
    // Initialize elements
    const leftPanel = document.getElementById('left-panel');
    const menuToggle = document.getElementById('menu-toggle');
    const resizer = document.getElementById('resizer');
    const chatArea = document.getElementById('chat-area');
    const welcomePage = document.getElementById('welcome-page');
    const chatInterface = document.getElementById('chat-interface');
    const messageContainer = document.getElementById('message-container');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
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
            // Fetch and display existing messages for the session
            try {
                const response = await fetch(`/api/chat_history/sessions/${sessionIdToResume}`);
                if (response.ok) {
                    const sessionData = await response.json();
                    sessionData.messages.forEach(msg => {
                        addMessage(msg.role, msg.content);
                    });
                    addMessage('system', `Resumed chat with ${currentWorkflow} workflow (Session: ${currentChatSessionId.substring(0, 8)})`, 'system');
                } else {
                    console.error('Failed to load session for resumption:', sessionIdToResume);
                    addMessage('system', `Failed to resume chat session ${sessionIdToResume.substring(0, 8)}. Starting new conversation.`, 'error');
                    // Clear stale session state when resumption fails
                    clearSessionState();
                    currentChatSessionId = generateUUID(); // Start a new one if resume fails
                    addMessage('system', `Ready to chat with ${currentWorkflow} workflow (New Session: ${currentChatSessionId.substring(0, 8)})`, 'system');
                }
            } catch (error) {
                console.error('Error loading session for resumption:', error);
                addMessage('system', `Error resuming chat session. Starting new conversation.`, 'error');
                // Clear stale session state when resumption fails
                clearSessionState();
                currentChatSessionId = generateUUID(); // Start a new one if error
                addMessage('system', `Ready to chat with ${currentWorkflow} workflow (New Session: ${currentChatSessionId.substring(0, 8)})`, 'system');
            }
        } else {
            // Start a new session
            currentChatSessionId = generateUUID();
            if (currentWorkflow) {
                addMessage('system', `Ready to chat with ${currentWorkflow} workflow (New Session: ${currentChatSessionId.substring(0, 8)})`, 'system');
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
        if (!message || !currentWorkflow) {
            if (!currentWorkflow) {
                addMessage('system', 'Please select a workflow first.', 'system');
            }
            return;
        }

        // Add user message
        addMessage('user', message);
        userInput.value = '';

        updateStatus(`Sending message to ${currentWorkflow}...`, 'in-progress');

        // Show typing indicator for AI response
        let typingIndicator = null;
        if (window.chatUIEnhancements) {
            typingIndicator = window.chatUIEnhancements.showTypingIndicator();
        }

        try {
            const workflowType = document.querySelector(`.workflow-button[data-workflow="${currentWorkflow}"]`).closest('.adapted-workflows') ? 'adapted' : 'ported';
            
            const payload = { question: message };
            if (currentChatSessionId) {
                payload.session_id = currentChatSessionId;
            }

            const response = await fetch(`/api/${workflowType}/${currentWorkflow}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const htmlContent = await response.text();

            // Hide typing indicator and add AI response
            if (window.chatUIEnhancements && typingIndicator) {
                window.chatUIEnhancements.hideTypingIndicator();
            }
            addMessage('ai', htmlContent);
            updateStatus(`Message sent to ${currentWorkflow}.`, 'success');

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

    // Enhanced Workflow button handling with session management
    document.querySelectorAll('.workflow-button').forEach((button) => {
        button.addEventListener('click', enhancedWorkflowButtonHandler);
    });

    // Menu toggle functionality
    menuToggle.addEventListener('click', () => {
        const isCollapsed = leftPanel.classList.toggle('collapsed');

        const adaptedContent = document.getElementById('adapted-content');
        const portedContent = document.getElementById('ported-content');

        if (isCollapsed) {
            lastWidth = leftPanel.getBoundingClientRect().width;
            leftPanel.style.width = '60px';

            if (adaptedContent) adaptedContent.style.display = 'none';
            if (portedContent) portedContent.style.display = 'none';
        } else {
            if (lastWidth > 0) {
                leftPanel.style.width = `${lastWidth}px`;
            }
            if (adaptedContent) adaptedContent.style.display = 'block';
            if (portedContent) portedContent.style.display = 'block';
        }
    });

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

    function renderStatusBar() {
        const staticInfoElement = document.getElementById('status-static-info');
        const dynamicMessageElement = document.getElementById('status-dynamic-message');

        const staticParts = [];
        if (statusBarStruct.current_model_provider) {
            staticParts.push(`Provider: ${statusBarStruct.current_model_provider}`);
        }
        if (statusBarStruct.current_model_id) {
            staticParts.push(`Model: ${statusBarStruct.current_model_id}`);
        }
        if (statusBarStruct.current_workflow) {
            staticParts.push(`Workflow: ${statusBarStruct.current_workflow}`);
        }

        if (staticParts.length > 0) {
            staticInfoElement.textContent = staticParts.join(' | ');
        } else {
            staticInfoElement.textContent = 'Loading user state...';
        }

        dynamicMessageElement.textContent = statusBarStruct.status_message;
        dynamicMessageElement.className = '';
    }

    function updateStatus(message, statusType = 'info') {
        setStatusBar('status_message', message);

        const dynamicMessageElement = document.getElementById('status-dynamic-message');
        dynamicMessageElement.className = '';

        if (dynamicMessageElement.dataset.intervalId) {
            clearInterval(parseInt(dynamicMessageElement.dataset.intervalId));
            delete dynamicMessageElement.dataset.intervalId;
        }

        switch (statusType) {
            case 'success':
                dynamicMessageElement.classList.add('status-success');
                break;
            case 'error':
                dynamicMessageElement.classList.add('status-error');
                break;
            case 'in-progress':
                dynamicMessageElement.classList.add('status-in-progress');
                let smileyIndex = 0;
                const smileys = ['😊', '😀', '😎'];
                const originalMessage = message;
                const intervalId = setInterval(() => {
                    smileyIndex = (smileyIndex + 1) % smileys.length;
                    setStatusBar('status_message', originalMessage + ' ' + smileys[smileyIndex]);
                }, 1000);
                dynamicMessageElement.dataset.intervalId = intervalId;
                break;
            case 'info':
            default:
                dynamicMessageElement.classList.add('status-info');
                break;
        }
    }



    function setStatusBar(key, val) {
        if (key in statusBarStruct) {
            statusBarStruct[key] = val;
        }
        renderStatusBar();
    }

    // Initialize status bar
    fetchAndUpdateStaticStatus();

    // Make fetchAndUpdateStaticStatus globally available
    window.fetchAndUpdateStaticStatus = fetchAndUpdateStaticStatus;

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

    resizer.addEventListener('mousedown', (e) => {
        if (leftPanel.classList.contains('collapsed')) return;

        startX = e.clientX;
        startWidth = leftPanel.getBoundingClientRect().width;
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    });

    // Group toggle functionality
    document.querySelectorAll('.group-toggle').forEach(toggle => {
        toggle.addEventListener('click', function() {
            const group = this.getAttribute('data-group');
            const content = document.getElementById(`${group}-content`);

            if (content.style.display === 'none' || content.style.display === '') {
                content.style.display = 'block';
                this.innerHTML = '<span class="icon">&#9776;</span>';
            } else {
                content.style.display = 'none';
                this.innerHTML = '<span class="icon">&#9776;</span>';
            }
        });
    });

    // Workflow selection button handlers
    document.querySelectorAll('.select-workflow-btn').forEach((button) => {
        button.addEventListener('click', (event) => {
            event.preventDefault();
            event.stopPropagation();

            const workflow = event.target.getAttribute('data-workflow');
            currentWorkflow = workflow;

            // Show loading page for selected workflow
            showLoadingPage(workflow);

            // Simulate workflow loading time
            setTimeout(() => {
                showChatInterface();
                updateStatus(`Switched to ${workflow} workflow.`, 'success');
            }, 1500); // 1.5 second loading simulation
        });
    });

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
        window.location.href = '/static/generate_ui.html';
    });

    const chatHistoryBtn = document.getElementById('chat-history-btn');
    if (chatHistoryBtn) {
        chatHistoryBtn.addEventListener('click', async () => {
            console.log('[DEBUG] Chat History button clicked');
            showLoadingPage('Chat History', 'Loading chat history interface...');

            setTimeout(async () => {
                showChatHistoryUI();
                updateStatus('Chat history loaded successfully.', 'success');
            }, 1000);
        });
        console.log('[DEBUG] Chat History button event listener attached');
    } else {
        console.error('[DEBUG] Chat History button not found!');
    }

    // Initialize theme system
    async function initializeThemeSystem() {
        try {
            await loadAvailableThemes();
            await loadCurrentTheme();
            console.log('Theme system initialized successfully');
        } catch (error) {
            console.error('Failed to initialize theme system:', error);
        }
    }

    // Initialize theme system and other components
    initializeThemeSystem();

    // Initialize session recovery on page load
    initializeSessionRecovery();

    // Initial state - Show welcome page by default (will be overridden if session recovery finds something)
    showWelcomePage();
    document.getElementById('adapted-content').style.display = 'block';
    document.getElementById('ported-content').style.display = 'block';
    lastWidth = leftPanel.getBoundingClientRect().width;
});
