/**
 * Main UI Manager - Phase 5.6D Frontend Modularization
 *
 * Handles view management, theme system, and status bar functionality.
 * Separated from monolithic script.js for better maintainability.
 */

// All state now managed by global-state.js

// Core UI Manager Class
class MainUIManager {
    constructor() {
        this.initializeEventListeners();
        this.initializeThemeSystem();
        this.fetchAndUpdateStaticStatus(); // Initialize status bar immediately
    }

    /**
     * Initialize theme system with available themes
     */
    async initializeThemeSystem() {
        try {
            window.globalState.availableThemes = await fetchAvailableThemes();
            const savedTheme = await loadCurrentTheme();
            if (savedTheme) {
                window.globalState.currentTheme = savedTheme;
                await this.applyTheme(window.globalState.currentTheme);
            }
        } catch (error) {
            console.error('[MainUIManager] Failed to initialize theme system:', error);
        }
    }

    /**
     * Apply theme and load associated CSS files
     */
    async applyTheme(themeName) {
        if (!themeName) return;

        console.log(`[MainUIManager] Starting theme application: ${themeName}`);

        try {
            // Parse theme into color and style
            const [color, style] = themeName.split('_');

            // Remove old style CSS files before loading new ones
            this.removeOldStyleCSS();

            // Load style-specific CSS files FIRST (main CSS)
            // Loading style-specific CSS files first
            await loadThemeCSS(`/static/assets/themes/classic/config_ui.css`);
            await loadThemeCSS(`/static/assets/themes/classic/main_style.css`);

            // Load color-specific CSS LAST (theme CSS) - so theme variables take precedence
            // Loading color theme CSS last
            await loadThemeCSS(`/static/assets/themes/${color}.css`);

            // Apply theme class to body for additional styling
            document.body.className = document.body.className.replace(/theme-\w+/g, '');
            document.body.classList.add(`theme-${color}`, `style-${style}`);
        } catch (error) {
            console.error('[MainUIManager] Error applying theme:', error);
        }
    }

    /**
     * Remove old style CSS files from DOM
     */
    removeOldStyleCSS() {
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
            }
        });
    }

    /**
     * Switch theme and persist the change
     */
    async switchTheme(themeName) {
        if (!window.globalState.availableThemes.includes(themeName)) {
            console.error(`[MainUIManager] Theme '${themeName}' is not available`);
            return false;
        }

        try {
            const response = await fetch('/api/system/themes/current', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ theme: themeName })
            });

            if (response.ok) {
                const data = await response.json();
                window.globalState.currentTheme = themeName;
                await this.applyTheme(themeName);
                console.log(`[MainUIManager] Theme switched to: ${themeName}`);
                return true;
            } else {
                const error = await response.json();
                console.error('[MainUIManager] Failed to switch theme:', error.detail);
                return false;
            }
        } catch (error) {
            console.error('[MainUIManager] Error switching theme:', error);
            return false;
        }
    }

    /**
     * Update status and render status bar
     */
    updateStatus(message, statusType = 'info') {
        this.setStatusBar('status_message', String(message));
        this.setStatusBar('status_type', statusType);

        const dynamicMessageElement = document.getElementById('status-dynamic-message');
        if (!dynamicMessageElement) return;

        dynamicMessageElement.className = '';

        if (dynamicMessageElement.dataset.intervalId) {
            clearInterval(parseInt(dynamicMessageElement.dataset.intervalId));
            delete dynamicMessageElement.dataset.intervalId;
        }

        // Add appropriate status class
        switch (statusType) {
            case 'success':
                dynamicMessageElement.classList.add('status-success');
                break;
            case 'error':
                dynamicMessageElement.classList.add('status-error');
                break;
            case 'in-progress':
                dynamicMessageElement.classList.add('status-in-progress');
                // Add animated dots for in-progress status
                this.startProgressAnimation(dynamicMessageElement, message);
                break;
            case 'info':
            default:
                dynamicMessageElement.classList.add('status-info');
                break;
        }

        this.renderStatusBar();
    }

    /**
     * Start animated progress indicator
     */
    startProgressAnimation(element, originalMessage) {
        let smileyIndex = 0;
        const smileys = ['😊', '😀', '😎'];
        const intervalId = setInterval(() => {
            smileyIndex = (smileyIndex + 1) % smileys.length;
            this.setStatusBar('status_message', originalMessage + ' ' + smileys[smileyIndex]);
        }, 1000);
        element.dataset.intervalId = intervalId;
    }

    /**
     * Set status bar property and re-render
     */
    setStatusBar(key, value) {
        if (key in window.globalState.statusBarStruct) {
            window.globalState.statusBarStruct[key] = value;
        }
        this.renderStatusBar();
    }

    /**
     * Render status bar in UI
     */
    renderStatusBar() {
        const userElement = document.getElementById('status-user');
        const providerElement = document.getElementById('status-provider');
        const modelElement = document.getElementById('status-model');
        const workflowElement = document.getElementById('status-workflow');
        const dynamicMessageElement = document.getElementById('status-dynamic-message');

        if (userElement) {
            userElement.textContent = window.globalState.statusBarStruct.current_user_id
                ? `User: ${window.globalState.statusBarStruct.current_user_id}`
                : 'User: (anonymous)';
        }

        if (providerElement) {
            providerElement.textContent = window.globalState.statusBarStruct.current_model_provider
                ? `Provider: ${window.globalState.statusBarStruct.current_model_provider}`
                : 'Provider: Loading...';
        }

        if (modelElement) {
            modelElement.textContent = window.globalState.statusBarStruct.current_model_id
                ? `Model: ${window.globalState.statusBarStruct.current_model_id}`
                : 'Model: Loading...';
        }

        if (workflowElement) {
            workflowElement.textContent = window.globalState.statusBarStruct.current_workflow
                ? `Workflow: ${window.globalState.statusBarStruct.current_workflow}`
                : 'Workflow: Loading...';
        }

        if (dynamicMessageElement) {
            dynamicMessageElement.textContent = window.globalState.statusBarStruct.status_message;
        }
    }

    /**
     * Escape HTML helper
     */
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Show specific view and hide others
     */
    showView(viewName) {
        window.globalState.currentView = viewName;

        // Hide all views
        const views = ['welcome-page', 'loading-page', 'chat-interface', 'settings-ui-container', 'config-ui-container', 'chat-history-ui-container', 'sessions-ui-container'];
        views.forEach(view => {
            const element = document.getElementById(view);
            if (element) element.style.display = 'none';
        });

        // FIX: Also hide workflow sub-panels when switching to main UI views
        // This ensures workflow session panels disappear when user navigates to Settings, Config, etc.
        if (window.workflowManager && window.workflowManager.hideWorkflowSessions) {
            window.workflowManager.hideWorkflowSessions();
        }

        // Show requested view
        let targetViewId;
        if (viewName === 'sessions' || viewName === 'chat_history') {
            // Special case: sessions view uses chat-history-ui-container
            targetViewId = 'chat-history-ui-container';
        } else {
            targetViewId = viewName.replace('-', '-') + (viewName === 'chat' ? '-interface' : viewName.includes('-') ? '-container' : '-page');
        }

        const targetView = document.getElementById(targetViewId);
        if (targetView) {
            targetView.style.display = viewName === 'chat' ? 'flex' : 'block';
        }

    }

    /**
     * Show loading page with title and message
     */
    showLoadingPage(title, message) {
        window.globalState.currentView = 'loading';
        this.showView('loading-page');

        const titleElement = document.getElementById('loading-title');
        const messageElement = document.getElementById('loading-message');

        if (titleElement) titleElement.textContent = title;
        if (messageElement) messageElement.textContent = message;
    }

    /**
     * Hide all views (utility function)
     */
    hideAllViews() {
        const views = ['welcome-page', 'loading-page', 'chat-interface', 'settings-ui-container', 'config-ui-container', 'chat-history-ui-container'];
        views.forEach(view => {
            const element = document.getElementById(view);
            if (element) element.style.display = 'none';
        });
    }

    /**
     * Show welcome page
     */
    showWelcomePage() {
        window.globalState.currentView = 'welcome';
        this.hideAllViews();
        const welcomePage = document.getElementById('welcome-page');
        if (welcomePage) welcomePage.style.display = 'block';
    }

    /**
     * Show settings UI
     */
    showSettingsUI() {
        window.globalState.currentView = 'settings';
        this.hideAllViews();
        const settingsContainer = document.getElementById('settings-ui-container');
        if (settingsContainer) settingsContainer.style.display = 'block';
    }

    /**
     * Show config UI
     */
    showConfigUI() {
        window.globalState.currentView = 'config';
        this.hideAllViews();
        const configContainer = document.getElementById('config-ui-container');
        if (configContainer) configContainer.style.display = 'block';
    }

    /**
     * Initialize DOM event listeners
     */
    initializeEventListeners() {
        // Menu toggle and panel resizer functionality - REMOVED: Now handled by script.js for better state management

        // Menu button event handlers
        this.initializeMenuButtonHandlers();

        // Initialize status bar fetch
        this.fetchAndUpdateStaticStatus();
    }

    /**
     * Initialize menu button event handlers
     */
    initializeMenuButtonHandlers() {
        // Sessions button removed as requested

        // Settings button
        const settingsBtn = document.getElementById('settings-btn');
        if (settingsBtn) {
            settingsBtn.addEventListener('click', () => {
                this.showView('settings');
            });
        }

        // Configuration button
        const configBtn = document.getElementById('config-btn');
        if (configBtn) {
            configBtn.addEventListener('click', () => {
                this.showView('config');
            });
        }

        // Generate button
        const generateBtn = document.getElementById('generate-btn');
        if (generateBtn) {
            generateBtn.addEventListener('click', () => {
                this.showView('welcome'); // Show welcome page with workflows
            });
        }

        // Chat History button - MVC fix: backend-first session creation
        const chatHistoryBtn = document.getElementById('chat-history-btn');
        if (chatHistoryBtn) {
            chatHistoryBtn.addEventListener('click', async () => {
                // Use new activateHistoryUI function for proper MVC pattern
                await window.activateHistoryUI();
            });
        }
    }

    /**
     * Fetch and update static status information
     */
    async fetchAndUpdateStaticStatus() {
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

                const userId = userState.current_user || 'anonymous';

                this.setStatusBar('current_user_id', userId);
                this.setStatusBar('current_model_provider', userState.current_model_provider || '');
                this.setStatusBar('current_model_id', userState.current_model_id || '');
                this.setStatusBar('current_workflow', userState.current_workflow || '');
            }
        } catch (error) {
            console.error('[MainUIManager] Failed to fetch user state:', error);
        }
    }
}

// Utility functions (extracted from original script.js)

/**
 * Fetch available themes from API
 */
async function fetchAvailableThemes() {
    try {
        const response = await fetch('/api/system/themes');
        if (response.ok) {
            const data = await response.json();
            return data.themes || [];
        }
        console.warn('[MainUIManager] Failed to load available themes from API');
        return [];
    } catch (error) {
        console.error('[MainUIManager] Error loading themes:', error);
        return [];
    }
}

/**
 * Load current theme from API
 */
async function loadCurrentTheme() {
    try {
        const response = await fetch('/api/system/themes/current');
        if (response.ok) {
            const data = await response.json();
            return data.theme || 'light_classic';
        }
        console.warn('[MainUIManager] Failed to load current theme, using default');
        return 'light_classic';
    } catch (error) {
        console.error('[MainUIManager] Error loading current theme:', error);
        return 'light_classic';
    }
}

/**
 * Load theme CSS dynamically
 */
async function loadThemeCSS(href) {
    return new Promise((resolve, reject) => {
        // Check if CSS is already loaded
        let existingLink = document.querySelector(`link[href="${href}"]`);

        if (existingLink) {
            existingLink.remove();
        }

        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = href + '?v=' + Date.now();

        link.onload = () => {
            resolve();
        };

        link.onerror = (event) => {
            console.error(`[MainUIManager] Failed to load CSS: ${href}`, event);
            reject(new Error(`Failed to load CSS: ${href}`));
        };

        document.head.appendChild(link);
    });
}

// Export globally available functions
window.switchTheme = (themeName) => window.mainUIManager?.switchTheme(themeName);
window.getCurrentTheme = () => window.globalState.currentTheme;
window.getAvailableThemes = () => window.globalState.availableThemes;
window.updateStatus = (message, type) => window.mainUIManager?.updateStatus(message, type);
window.showLoadingPage = (title, message) => window.mainUIManager?.showLoadingPage(title, message);
window.setStatusBar = (key, value) => window.mainUIManager?.setStatusBar(key, value);
window.showWelcomePage = () => window.mainUIManager?.showWelcomePage();
window.showSettingsUI = () => window.mainUIManager?.showSettingsUI();
window.showConfigUI = () => window.mainUIManager?.showConfigUI();
window.showChatHistoryUI = () => window.mainUIManager?.showView('chat_history');
window.showSessionsUI = () => window.mainUIManager?.showView('sessions');
window.hideAllViews = () => window.mainUIManager?.hideAllViews();
window.fetchAndUpdateStaticStatus = () => window.mainUIManager?.fetchAndUpdateStaticStatus();

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.mainUIManager = new MainUIManager();
});

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = MainUIManager;
}
