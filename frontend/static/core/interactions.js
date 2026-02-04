/**
 * UI Interaction Manager - Core UI interaction functionality
 *
 * Handles menu toggle, panel resizer, and group toggle functionality.
 * Extracted from script.js during Phase 2 light-touch extractions.
 */

// UI Interaction Manager Class
class UIInteractionManager {
    constructor() {
        this.lastWidth = 0;
        this.initializeEventListeners();
    }

    /**
     * Initialize all UI interaction event listeners
     */
    initializeEventListeners() {
        this.initializeMenuToggle();
        this.initializeResizer();
        this.initializeGroupToggles();
        this.initializeDynamicWorkflowsGroup();
    }

    /**
     * Initialize menu toggle functionality
     */
    initializeMenuToggle() {
        const menuToggle = document.getElementById('menu-toggle');
        const leftPanel = document.getElementById('left-panel');

        if (!menuToggle || !leftPanel) {
            console.error('[UIInteractionManager] Menu toggle elements not found');
            return;
        }

        menuToggle.addEventListener('click', () => {
            const isCollapsed = leftPanel.classList.toggle('collapsed');

            const dynamicWorkflowsContent = document.getElementById('dynamic-workflows-content');
            const groupToggle = document.querySelector('.group-toggle[data-group="dynamic-workflows"]');

            if (isCollapsed) {
                this.lastWidth = leftPanel.getBoundingClientRect().width;
                leftPanel.style.width = '60px';

                if (dynamicWorkflowsContent) {
                    dynamicWorkflowsContent.style.display = 'none';
                }
            } else {
                if (this.lastWidth > 0) {
                    leftPanel.style.width = `${this.lastWidth}px`;
                }
                if (dynamicWorkflowsContent) {
                    dynamicWorkflowsContent.style.display = 'block';
                }

                // Ensure group toggle shows expanded state when left panel is expanded
                if (groupToggle && dynamicWorkflowsContent.style.display === 'block') {
                    groupToggle.innerHTML = '<span class="icon">▼</span>';
                }
            }
        });
    }

    /**
     * Initialize panel resizer functionality
     */
    initializeResizer() {
        const resizer = document.getElementById('resizer');
        const leftPanel = document.getElementById('left-panel');

        if (!resizer || !leftPanel) {
            console.error('[UIInteractionManager] Resizer elements not found');
            return;
        }

        let startX = 0;
        let startWidth = 0;

        const onMouseMove = (e) => {
            const dx = e.clientX - startX;
            const newWidth = startWidth + dx;
            leftPanel.style.width = `${Math.min(Math.max(newWidth, 60), 500)}px`;
        };

        const onMouseUp = () => {
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
            this.lastWidth = leftPanel.getBoundingClientRect().width;
        };

        resizer.addEventListener('mousedown', (e) => {
            if (leftPanel.classList.contains('collapsed')) {
                return;
            }

            startX = e.clientX;
            startWidth = leftPanel.getBoundingClientRect().width;
            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
        });
    }

    /**
     * Initialize group toggle functionality
     */
    initializeGroupToggles() {
        document.querySelectorAll('.group-toggle').forEach(toggle => {
            toggle.addEventListener('click', function () {
                const group = this.getAttribute('data-group');
                const content = document.getElementById(`${group}-content`);
                if (content) {
                    const computedStyle = window.getComputedStyle(content);
                    const currentDisplay = computedStyle.display;
                    if (currentDisplay === 'none') {
                        content.style.display = 'block';
                        this.innerHTML = '<span class="icon">▼</span>'; // Down arrow when expanded
                    } else {
                        content.style.display = 'none';
                        this.innerHTML = '<span class="icon">▶</span>'; // Right arrow when collapsed
                    }
                } else {
                    console.warn(`[GroupToggle] Content element not found for group: ${group}`);
                }
            });
        });
    }

    /**
     * Initialize special handling for Dynamic Workflows group button
     */
    initializeDynamicWorkflowsGroup() {
        const dynamicWorkflowsGroupBtn = document.getElementById('dynamic-workflows-group-btn');

        if (!dynamicWorkflowsGroupBtn) {
            console.warn('[UIInteractionManager] Dynamic workflows group button not found');
            return;
        }

        dynamicWorkflowsGroupBtn.addEventListener('click', function () {
            const leftPanel = document.getElementById('left-panel');
            if (leftPanel && leftPanel.classList.contains('collapsed')) {
                // When collapsed, clicking Dynamic Workflows should activate current workflow
                if (window.globalState.currentWorkflow) {
                    // Use the same logic as workflow button click
                    if (window.selectWorkflow) {
                        window.selectWorkflow(window.globalState.currentWorkflow);
                    }
                    return;
                }
            }
            // If not collapsed, let the normal group toggle behavior work
        });

    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.uiInteractionManager = new UIInteractionManager();
});

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = UIInteractionManager;
}
