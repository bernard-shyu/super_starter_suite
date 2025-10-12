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
            console.log('[MainUIManager] Theme system initialized successfully');
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

            console.log(`[MainUIManager] Parsed theme components - Color: ${color}, Style: ${style}`);

            // Remove old style CSS files before loading new ones
            this.removeOldStyleCSS();

            // Load style-specific CSS files FIRST (main CSS)
            console.log('[MainUIManager] Loading style-specific CSS files first');
            await loadThemeCSS(`/static/config_ui.${style}.css`);
            await loadThemeCSS(`/static/main_style.${style}.css`);

            // Load color-specific CSS LAST (theme CSS) - so theme variables take precedence
            console.log(`[MainUIManager] Loading color theme CSS last: /static/themes/${color}.css`);
            await loadThemeCSS(`/static/themes/${color}.css`);

            // Apply theme class to body for additional styling
            document.body.className = document.body.className.replace(/theme-\w+/g, '');
            document.body.classList.add(`theme-${color}`, `style-${style}`);

            console.log(`[MainUIManager] Applied theme ${themeName} classes to body: theme-${color}, style-${style}`);
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
                console.log(`[MainUIManager] Removed old CSS file: ${filename}`);
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
            const response = await fetch('/api/themes/current', {
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
        this.setStatusBar('status_message', message);

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
        const staticInfoElement = document.getElementById('status-static-info');
        const dynamicMessageElement = document.getElementById('status-dynamic-message');

        if (!staticInfoElement || !dynamicMessageElement) return;

        const staticParts = [];
        if (window.globalState.statusBarStruct.current_model_provider) {
            staticParts.push(`Provider: ${window.globalState.statusBarStruct.current_model_provider}`);
        }
        if (window.globalState.statusBarStruct.current_model_id) {
            staticParts.push(`Model: ${window.globalState.statusBarStruct.current_model_id}`);
        }
        if (window.globalState.statusBarStruct.current_workflow) {
            staticParts.push(`Workflow: ${window.globalState.statusBarStruct.current_workflow}`);
        }

        staticInfoElement.textContent = staticParts.length > 0 ? staticParts.join(' | ') : 'Loading user state...';
        dynamicMessageElement.textContent = window.globalState.statusBarStruct.status_message;
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

        // Show requested view
        let targetViewId;
        if (viewName === 'sessions') {
            // Special case: sessions view uses chat-history-ui-container
            targetViewId = 'chat-history-ui-container';
        } else {
            targetViewId = viewName.replace('-', '-') + (viewName === 'chat' ? '-interface' : viewName.includes('-') ? '-container' : '-page');
        }

        const targetView = document.getElementById(targetViewId);
        if (targetView) {
            targetView.style.display = viewName === 'chat' ? 'flex' : 'block';
            console.log(`[MainUIManager] Showing view element: ${targetView.id}`);
        }

        // Special handling for sessions view - delegate to session manager
        if (viewName === 'sessions') {
            if (window.sessionManager) {
                // Ensure session manager creates UI if not already done
                if (!window.sessionManager.sessionListContainer) {
                    console.log('[MainUIManager] Creating session manager UI for first time...');
                    window.sessionManager.setupUI();
                }
                window.sessionManager.refreshSessions();
            } else {
                console.error('[MainUIManager] Session manager not available');
            }
        }

        console.log(`[MainUIManager] Switched to view: ${viewName}`);
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
     * Initialize DOM event listeners
     */
    initializeEventListeners() {
        // Menu toggle functionality
        const menuToggle = document.getElementById('menu-toggle');
        const leftPanel = document.getElementById('left-panel');
        const resizer = document.getElementById('resizer');
        let lastWidth = 0;

        if (menuToggle && leftPanel) {
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

        // Panel resizer functionality
        if (resizer && leftPanel) {
            let startX = 0, startWidth = 0;

            const onMouseMove = (e) => {
                const dx = e.clientX - startX;
                const newWidth = startWidth + dx;
                leftPanel.style.width = `${Math.min(Math.max(newWidth, 60), 500)}px`;
            };

            const onMouseUp = () => {
                document.removeEventListener('mousemove', onMouseMove);
                document.removeEventListener('mouseup', onMouseUp);
                lastWidth = leftPanel.getBoundingClientRect().width;
            };

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
                    const isExpanded = content.style.display !== 'none';
                    content.style.display = isExpanded ? 'none' : 'block';
                    this.innerHTML = isExpanded ? '&#9776;' : '&#9776;';
                }
            });
        });

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
                console.log('[MainUIManager] Settings button clicked');
                this.showView('settings');
            });
        }

        // Configuration button
        const configBtn = document.getElementById('config-btn');
        if (configBtn) {
            configBtn.addEventListener('click', () => {
                console.log('[MainUIManager] Configuration button clicked');
                this.showView('config');
            });
        }

        // Generate button
        const generateBtn = document.getElementById('generate-btn');
        if (generateBtn) {
            generateBtn.addEventListener('click', () => {
                console.log('[MainUIManager] Generate button clicked');
                this.showView('welcome'); // Show welcome page with workflows
            });
        }

        // Chat History button - now uses session manager
        const chatHistoryBtn = document.getElementById('chat-history-btn');
        if (chatHistoryBtn) {
            chatHistoryBtn.addEventListener('click', () => {
                console.log('[MainUIManager] Chat History button clicked');
                // Instead of old chat_history view, use session manager
                if (window.sessionManager) {
                    // Ensure session manager creates UI if not already done
                    if (!window.sessionManager.sessionListContainer) {
                        console.log('[MainUIManager] Creating session manager UI for Chat History...');
                        window.sessionManager.setupUI();
                    }
                    // Show sessions view which contains organized workflow/session history
                    this.showView('sessions');
                } else {
                    console.error('[MainUIManager] Session manager not available for chat history');
                }
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
        const response = await fetch('/api/themes');
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
        const response = await fetch('/api/themes/current');
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
        console.log(`[MainUIManager] Starting CSS load for: ${href}`);

        // Check if CSS is already loaded
        let existingLink = document.querySelector(`link[href="${href}"]`);

        if (existingLink) {
            console.log(`[MainUIManager] Removing existing CSS link for: ${href}`);
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

/**
 * Generate UUID utility
 */
function generateUUID() {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
        return crypto.randomUUID();
    }
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

// Export globally available functions
window.switchTheme = (themeName) => window.mainUIManager?.switchTheme(themeName);
window.getCurrentTheme = () => window.globalState.currentTheme;
window.getAvailableThemes = () => window.globalState.availableThemes;
window.updateStatus = (message, type) => window.mainUIManager?.updateStatus(message, type);
window.showLoadingPage = (title, message) => window.mainUIManager?.showLoadingPage(title, message);
window.setStatusBar = (key, value) => window.mainUIManager?.setStatusBar(key, value);
window.showWelcomePage = () => window.mainUIManager?.showView('welcome');
window.showSettingsUI = () => window.mainUIManager?.showView('settings');
window.showConfigUI = () => window.mainUIManager?.showView('config');
window.showChatHistoryUI = () => window.mainUIManager?.showView('chat_history');
window.showSessionsUI = () => window.mainUIManager?.showView('sessions');

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.mainUIManager = new MainUIManager();
});

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = MainUIManager;
}
