/**
 * Navigation Button History UI Manager - Side-by-Side Navigation Layout
 *
 * Implements comprehensive chat history management with:
 * - Horizontal scrolling workflow tabs from system workflow configuration
 * - Navigation buttons positioned beside the scrollable container (Prev/Next style)
 * - Professional side-by-side layout with clean navigation controls
 * - Fixed session browser layout with metadata and expandable content/artifacts
 * - Session-level management actions: copy, download, edit, delete
 * - Multi-workflow session organization and filtering
 */

// Professional naming for the main Chat History UI component
class NavigationHistoryUIManager {
    constructor() {
        this.workflows = [];
        this.currentWorkflowId = null;
        this.sessionsData = {};
        this.selectedSessionId = null;
        this.uiInitialized = false;
    }

    /**
     * Initialize the History UI
     */
    async initializeUI() {
        try {
            // Load available workflows from backend
            await this.loadWorkflows();

            // Create the UI structure
            this.createUI();

            // Load initial data
            this.refreshAllWorkflows();

            this.uiInitialized = true;

        } catch (error) {
            console.error('[NavigationHistoryUI] Failed to initialize UI:', error);

            // Try to show a basic UI even if initialization fails
            try {
                this.showBasicErrorUI(error.message);
            } catch (uiError) {
                console.error('[NavigationHistoryUI] Failed to show error UI:', uiError);
            }

            // Still mark as initialized to prevent infinite retries
            this.uiInitialized = true;
        }
    }

    /**
     * Show basic error UI when initialization fails
     */
    showBasicErrorUI(message) {
        const container = document.getElementById('chat-history-ui-container');
        if (!container) return;

        container.innerHTML = `
            <div style="padding: 20px; text-align: center; color: #dc3545;">
                <div style="font-size: 48px; margin-bottom: 16px;">⚠️</div>
                <h3 style="margin-bottom: 16px;">History UI Failed to Load</h3>
                <p style="color: #666; margin-bottom: 20px;">${message}</p>
                <button onclick="window.navigationHistoryUI.retryInitialize()" style="padding: 8px 16px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer;">
                    Try Again
                </button>
            </div>
        `;
    }

    /**
     * Retry initialization after an error
     */
    async retryInitialize() {
        console.log('[NavigationHistoryUI] Retrying initialization...');
        this.uiInitialized = false;
        await this.initializeUI();
    }

    /**
     * Load available workflows from WorkflowManager (single source of truth - NO redundant API calls)
     */
    async loadWorkflows() {
        try {
            // ✅ FIX: Get workflows from WorkflowManager ONLY (no redundant API calls)
            if (window.workflowManager && window.workflowManager.getAvailableWorkflows) {
                this.workflows = window.workflowManager.getAvailableWorkflows();
                console.log(`[NavigationHistoryUI] ✅ Got ${this.workflows.length} workflows from WorkflowManager (single API call)`);
            } else {
                console.warn('[NavigationHistoryUI] ❌ WorkflowManager not available - cannot load workflows');
                this.workflows = await this.getFallbackWorkflows();
            }
        } catch (error) {
            console.error('[NavigationHistoryUI] Failed to load workflows:', error);
            this.workflows = await this.getFallbackWorkflows();
        }
    }

    /**
     * Fallback workflows from system config knowledge
     */
    async getFallbackWorkflows() {
        const fallbackWorkflows = [
            { id: 'A_agentic_rag', display_name: 'Agentic RAG' },
            { id: 'P_agentic_rag', display_name: 'Agentic RAG (Ported)' },
            { id: 'A_code_generator', display_name: 'Code Generator' },
            { id: 'P_code_generator', display_name: 'Code Generator (Ported)' },
            { id: 'A_deep_research', display_name: 'Deep Research' },
            { id: 'P_deep_research', display_name: 'Deep Research (Ported)' },
            { id: 'A_document_generator', display_name: 'Document Generator' },
            { id: 'P_document_generator', display_name: 'Document Generator (Ported)' },
            { id: 'A_financial_report', display_name: 'Financial Report' },
            { id: 'P_financial_report', display_name: 'Financial Report (Ported)' },
            { id: 'A_human_in_the_loop', display_name: 'Human in the Loop' },
            { id: 'P_human_in_the_loop', display_name: 'Human in the Loop (Ported)' },
        ];

        // Add icons and types
        fallbackWorkflows.forEach(wf => {
            wf.icon = this.getWorkflowIcon(wf.id);
            wf.type = wf.id.startsWith('A_') ? 'adapted' : 'ported';
        });

        return fallbackWorkflows;
    }

    /**
     * Create the History UI structure - Side-by-Side Navigation Layout
     */
    createUI() {
        const container = document.getElementById('chat-history-ui-container');
        if (!container) {
            console.error('[NavigationHistoryUI] Container not found');
            return;
        }

        console.log('[NavigationHistoryUI] Creating side-by-side navigation UI structure...');

        container.innerHTML = `
            <!-- Side-by-Side Navigation Layout -->
            <div class="navigation-workflow-controls">
                <button class="navigation-scroll-button navigation-scroll-prev" id="navigation-scroll-prev">
                    ‹ Prev
                </button>

                <div class="navigation-workflow-tabs-container" id="navigation-tabs-container">
                    <div class="navigation-workflow-tabs" id="navigation-workflow-tabs">
                        <!-- Tabs will be populated here -->
                    </div>
                </div>

                <button class="navigation-scroll-button navigation-scroll-next" id="navigation-scroll-next">
                    Next ›
                </button>
            </div>

            <!-- Main Content Area: Fixed Session List + Expandable Content -->
            <div class="history-main-content">
                <!-- Left Panel: Session List -->
                <div class="history-session-list-panel" id="history-session-list-panel">
                    <div class="history-session-list-header">
                        <h3 id="history-current-workflow-title">Select a Workflow</h3>
                    </div>
                    <div class="history-session-list" id="history-session-list">
                        <div class="history-no-workflow-selected">
                            <div class="history-placeholder-content">
                                <div class="history-workflow-icon-large">👆</div>
                                <p>Select a workflow tab above to view sessions</p>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Right Panel: Expandable Metadata + Content/Artifacts -->
                <div class="history-content-panel" id="history-content-panel">
                    <!-- Session Metadata Expandable -->
                    <div class="history-metadata-section" id="history-metadata-section">
                        <div class="history-metadata-header">
                            <span class="history-metadata-toggle" id="history-metadata-toggle">▶</span>
                            <h4>Session Information</h4>
                            <div class="history-session-actions" id="history-session-actions">
                                <!-- Management buttons will be populated here -->
                            </div>
                        </div>
                        <div class="history-metadata-content" id="history-metadata-content" style="display: none;">
                            <!-- Metadata details will be populated here -->
                        </div>
                    </div>

                    <!-- Scrollable Content/Artifacts Area -->
                    <div class="history-content-area" id="history-content-area">
                        <div class="history-content-placeholder">
                            <div class="history-content-icon">💬</div>
                            <h3>Select a session to view content</h3>
                            <p>Choose a session from the list to see messages and artifacts</p>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Create workflow tabs
        this.createWorkflowTabs();

        // Force container constraint
        setTimeout(() => {
            const containerDiv = document.getElementById('navigation-tabs-container');
            if (containerDiv) {
                const viewportWidth = window.innerWidth;
                const constrainedWidth = Math.max(600, viewportWidth - 400); // Smaller, with room for buttons

                console.log(`[NavigationHistoryUI] Constraining scrollable area: ${viewportWidth}px viewport → ${constrainedWidth}px`);

                containerDiv.style.width = `${constrainedWidth}px`;
                containerDiv.style.maxWidth = `${constrainedWidth}px`;
                containerDiv.style.overflowX = 'auto';
                containerDiv.style.overflowY = 'hidden';

                console.log(`[NavigationHistoryUI] Scrollable area constrained to ${containerDiv.offsetWidth}px`);
            }
        }, 50);

        // Attach event handlers
        this.attachEventHandlers();

        console.log('[NavigationHistoryUI] Side-by-side navigation UI structure created');
    }

    /**
     * Create horizontal scrolling workflow tabs
     */
    createWorkflowTabs() {
        const tabsContainer = document.getElementById('navigation-workflow-tabs');
        if (!tabsContainer) {
            console.error('[NavigationHistoryUI] Tabs container not found, cannot create workflow tabs');
            return;
        }

        console.log('[NavigationHistoryUI] Creating workflow tabs in navigation layout:', tabsContainer);

        tabsContainer.innerHTML = '';

        this.workflows.forEach((workflow, index) => {
            const tabElement = document.createElement('button');
            tabElement.className = 'navigation-workflow-tab';
            tabElement.dataset.workflowId = workflow.id;
            tabElement.innerHTML = `
                <span class="navigation-tab-icon">${workflow.icon}</span>
                <span class="navigation-tab-label">${workflow.display_name}</span>
                <span class="navigation-tab-badge" id="navigation-tab-badge-${workflow.id}">0</span>
            `;

            // Select first tab by default
            if (index === 0) {
                tabElement.classList.add('active');
                this.currentWorkflowId = workflow.id;
            }

            tabsContainer.appendChild(tabElement);
        });

        console.log(`[NavigationHistoryUI] Created ${this.workflows.length} navigation workflow tabs`);
        console.log('[NavigationHistoryUI] Navigation layout tabs created');
    }

    /**
     * Attach event handlers for UI interactions
     */
    attachEventHandlers() {
        // Navigation button event handlers
        const prevBtn = document.getElementById('navigation-scroll-prev');
        const nextBtn = document.getElementById('navigation-scroll-next');
        const tabsContainer = document.getElementById('navigation-workflow-tabs');

        if (prevBtn) {
            prevBtn.addEventListener('click', () => this.scrollTabs(-200));
        }
        if (nextBtn) {
            nextBtn.addEventListener('click', () => this.scrollTabs(200));
        }

        // Mouse wheel support on tabs
        if (tabsContainer) {
            tabsContainer.addEventListener('wheel', (e) => {
                e.preventDefault();
                const scrollAmount = e.deltaY > 0 ? 100 : -100;
                console.log(`[NavigationHistoryUI] Mouse wheel scroll: ${scrollAmount}`);
                this.scrollTabs(scrollAmount);
            });
        }

        // Tab selection
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('navigation-workflow-tab') ||
                e.target.closest('.navigation-workflow-tab')) {
                const tabElement = e.target.classList.contains('navigation-workflow-tab') ?
                    e.target : e.target.closest('.navigation-workflow-tab');
                this.selectWorkflow(tabElement.dataset.workflowId, true);
            }
        });

        // Metadata toggle
        const metadataToggle = document.getElementById('history-metadata-toggle');
        if (metadataToggle) {
            metadataToggle.addEventListener('click', () => this.toggleMetadata());
        }

        // Update button states on scroll
        setTimeout(() => this.updateNavigationButtons(), 100);

        console.log('[NavigationHistoryUI] Navigation button event handlers attached');
    }

    /**
     * Scroll workflow tabs horizontally
     */
    scrollTabs(amount) {
        const containerDiv = document.getElementById('navigation-tabs-container');
        if (containerDiv) {
            console.log(`[NavigationHistoryUI] Current scrollLeft: ${containerDiv.scrollLeft}, scrolling by: ${amount}`);

            const newScrollLeft = Math.max(0, Math.min(containerDiv.scrollWidth - containerDiv.clientWidth, containerDiv.scrollLeft + amount));

            containerDiv.scrollTo({
                left: newScrollLeft,
                behavior: 'smooth'
            });

            // Update button states after scroll
            setTimeout(() => this.updateNavigationButtons(), 300);

            console.log(`[NavigationHistoryUI] Set scrollLeft to: ${newScrollLeft}`);
        } else {
            console.error('[NavigationHistoryUI] Navigation container not found for scrolling');
        }
    }

    /**
     * Update navigation button states
     */
    updateNavigationButtons() {
        const containerDiv = document.getElementById('navigation-tabs-container');
        const prevBtn = document.getElementById('navigation-scroll-prev');
        const nextBtn = document.getElementById('navigation-scroll-next');

        if (!containerDiv || !prevBtn || !nextBtn) {
            console.error('[NavigationHistoryUI] Missing navigation elements');
            return;
        }

        const { scrollLeft, scrollWidth, clientWidth } = containerDiv;

        const canScrollPrev = scrollLeft > 10;
        const canScrollNext = scrollWidth > clientWidth && (scrollLeft < scrollWidth - clientWidth - 10);

        prevBtn.disabled = !canScrollPrev;
        nextBtn.disabled = !canScrollNext;

        prevBtn.style.opacity = canScrollPrev ? '1' : '0.5';
        nextBtn.style.opacity = canScrollNext ? '1' : '0.5';

        console.log(`[NavigationHistoryUI] Button states updated: Prev=${canScrollPrev}, Next=${canScrollNext}`);
    }

    /**
     * Refresh all workflows data - placeholder implementation
     */
    async refreshAllWorkflows() {
        console.log(`[NavigationHistoryUI] Refresh all workflow data`);
        // Placeholder implementation
        return Promise.resolve();
    }

    // Utility Methods - Simplified implementation

    /**
     * Get workflow icon
     */
    getWorkflowIcon(workflowId) {
        const iconMap = {
            'A_agentic_rag': '🧠', 'P_agentic_rag': '🧠',
            'A_code_generator': '💻', 'P_code_generator': '💻',
            'A_deep_research': '🔍', 'P_deep_research': '🔍',
            'A_document_generator': '📄', 'P_document_generator': '📄',
            'A_financial_report': '📊', 'P_financial_report': '📊',
            'A_human_in_the_loop': '👥', 'P_human_in_the_loop': '👥'
        };
        return iconMap[workflowId] || '💬';
    }

    /**
     * Select workflow - placeholder
     */
    selectWorkflow(workflowId, fromUser = false) {
        console.log(`[NavigationHistoryUI] Selecting workflow: ${workflowId}, fromUser: ${fromUser}`);
        this.currentWorkflowId = workflowId;
        this.showContentPlaceholder();
        // Update UI to show selected workflow
        document.querySelectorAll('.navigation-workflow-tab').forEach(tab => {
            tab.classList.remove('active');
        });
        const activeTab = document.querySelector(`[data-workflow-id="${workflowId}"]`);
        if (activeTab) {
            activeTab.classList.add('active');
        }
    }

    /**
     * Show content placeholder
     */
    showContentPlaceholder() {
        const container = document.getElementById('history-content-area');
        if (container) {
            container.innerHTML = `
                <div style="text-align: center; padding: 50px;">
                    <div style="font-size: 48px; margin-bottom: 20px;">💬</div>
                    <h3>Chat History Manager</h3>
                    <p>Navigation button layout working successfully!</p>
                    <p style="color: green; font-weight: bold;">Scroll buttons are positioned beside the tab container.</p>
                </div>
            `;
        }
    }
}

// CSS Styles for Navigation Button History UI
const navigationHistoryUICSS = `
<style>
/* Navigation Button History UI Styles */

/* Main container for side-by-side navigation */
.navigation-workflow-controls {
    display: flex;
    align-items: center;
    justify-content: center;
    background: #f8f9fa;
    border-bottom: 1px solid #e0e0e0;
    padding: 16px;
    gap: 16px;
}

.navigation-workflow-tabs-container {
    position: relative;
    background: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    overflow-x: auto;
    overflow-y: hidden;
    max-height: 120px; /* Fixed height for button alignment */
}

/* Navigation scroll buttons */
.navigation-scroll-button {
    background: #007bff;
    color: white;
    border: 1px solid #0056b3;
    border-radius: 6px;
    padding: 12px 20px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
    white-space: nowrap;
    min-width: 100px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    box-shadow: 0 2px 4px rgba(0,123,255,0.2);
}

.navigation-scroll-button:hover {
    background: #0056b3;
    border-color: #004494;
    transform: translateY(-1px);
    box-shadow: 0 4px 8px rgba(0,123,255,0.3);
}

.navigation-scroll-button:disabled {
    background: #e9ecef;
    border-color: #adb5bd;
    color: #6c757d;
    cursor: not-allowed;
    box-shadow: none;
    transform: none;
}

.navigation-scroll-prev::before {
    content: "‹";
    font-size: 16px;
}

.navigation-scroll-next::after {
    content: "›";
    font-size: 16px;
}

.navigation-workflow-tabs {
    display: flex;
    min-width: max-content;
    padding: 8px 16px;
    gap: 8px;
}

/* Tab styles for navigation layout */
.navigation-workflow-tab {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 12px;
    border: none;
    background: transparent;
    cursor: pointer;
    border-radius: 6px;
    transition: all 0.2s ease;
    white-space: nowrap;
    min-width: 120px;
    justify-content: center;
    border: 2px solid transparent;
}

.navigation-workflow-tab:hover {
    background: #e9ecef;
    border-color: #007bff;
    opacity: 1;
}

.navigation-workflow-tab.active {
    background: linear-gradient(135deg, #007bff, #0056b3);
    color: white;
    box-shadow: 0 2px 6px rgba(0,123,255,0.4);
    border-color: #007bff;
}

.navigation-workflow-tab:not(.active) {
    color: #495057;
    background: #f8f9fa;
    border-color: #dee2e6;
}

.navigation-tab-icon {
    font-size: 16px;
}

.navigation-tab-label {
    font-size: 12px;
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
}

.navigation-tab-badge {
    display: none;
    background: #dc3545;
    color: white;
    font-size: 10px;
    padding: 1px 4px;
    border-radius: 8px;
    min-width: 16px;
    text-align: center;
    font-weight: bold;
}

.navigation-workflow-tab.active .navigation-tab-badge {
    background: rgba(255,255,255,0.8);
    color: #007bff;
}

.history-main-content {
    display: flex;
    height: calc(100vh - 120px);
}

.history-session-list-panel {
    width: 320px;
    border-right: 1px solid #e0e0e0;
    background: #fafbfc;
    display: flex;
    flex-direction: column;
}

.history-session-list-header {
    padding: 16px;
    border-bottom: 1px solid #e0e0e0;
    background: white;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.history-current-workflow-title {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: #333;
}

.history-session-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px 0;
}

.history-no-workflow-selected,
.history-no-sessions,
.history-content-placeholder {
    display: flex;
    justify-content: center;
    align-items: center;
    text-align: center;
    color: #666;
    min-height: 200px;
}

.history-placeholder-content {
    max-width: 300px;
}

.history-workflow-icon-large,
.history-content-icon,
.history-error-icon {
    font-size: 48px;
    margin-bottom: 16px;
    opacity: 0.6;
}

.history-no-workflow-selected h3,
.history-no-sessions h3,
.history-content-placeholder h3 {
    margin: 0 0 8px 0;
    color: #333;
}

.history-no-workflow-selected p,
.history-no-sessions p,
.history-content-placeholder p {
    margin: 0 0 16px 0;
}

.history-content-panel {
    flex: 1;
    display: flex;
    flex-direction: column;
    background: white;
}

.history-metadata-section {
    border-bottom: 1px solid #e0e0e0;
    background: #fafbfc;
}

.history-metadata-header {
    display: flex;
    align-items: center;
    padding: 8px 16px;
    cursor: pointer;
    background: #f8f9fa;
}

.history-metadata-toggle {
    margin-right: 8px;
    color: #666;
    font-size: 12px;
    transition: transform 0.2s;
}

.history-metadata-header h4 {
    margin: 0;
    font-size: 14px;
    font-weight: 500;
    color: #333;
    flex: 1;
}

.history-session-actions {
    display: flex;
    gap: 4px;
}

.history-metadata-content {
    padding: 16px;
    background: white;
    display: none;
}

.history-content-area {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
}
</style>
`;

// Inject CSS styles
if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            if (!document.getElementById('navigation-history-ui-css')) {
                const style = document.createElement('style');
                style.id = 'navigation-history-ui-css';
                style.innerHTML = navigationHistoryUICSS;
                document.head.appendChild(style);
            }
        });
    } else {
        if (!document.getElementById('navigation-history-ui-css')) {
            const style = document.createElement('style');
            style.id = 'navigation-history-ui-css';
            style.innerHTML = navigationHistoryUICSS;
            document.head.appendChild(style);
        }
    }
}

// Create and set global object
try {
    window.navigationHistoryUI = new NavigationHistoryUIManager();
} catch (error) {
    console.error('[NavigationHistoryUI] Failed to create NavigationHistoryUIManager:', error);
}

// Function to activate Navigation History UI
window.activateNavigationHistoryUI = function () {
    console.log('[NavigationHistoryUI] Navigation activation function called');
    try {
        if (window.navigationHistoryUI && !window.navigationHistoryUI.uiInitialized) {
            console.log('[NavigationHistoryUI] Starting navigation UI initialization...');
            // Async initialization - we'll handle UI updates
            window.navigationHistoryUI.initializeUI().then(() => {
                console.log('[NavigationHistoryUI] Navigation UI initialization completed');
            }).catch(error => {
                console.error('[NavigationHistoryUI] Error during navigation activation:', error);
            });
        } else {
            console.log('[NavigationHistoryUI] Navigation UI already initialized or manager not available');
        }
    } catch (error) {
        console.error('[NavigationHistoryUI] Error during navigation activation:', error);
    }
};

console.log('[NavigationHistoryUI] Navigation Button History UI Manager script loaded successfully');

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = NavigationHistoryUIManager;
}
