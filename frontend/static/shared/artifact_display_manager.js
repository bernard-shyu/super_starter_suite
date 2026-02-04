/**
 * Artifact Display Manager - Professional Code Display with Resizing
 */

function ArtifactDisplayManager() {
    this.currentArtifact = null;
    this.lastArtifacts = null; // Store last artifacts for reopening
    this.workflowProgress = null; // Store current workflow progress data
    this.currentTab = 'progress'; // 'progress' or 'results'

    // State tracking for automatic reset
    this.currentWorkflow = window.globalState ? window.globalState.currentWorkflow : null;
    this.currentSessionId = window.globalState ? window.globalState.currentChatSessionId : null;

    this.initializeContainer();
    this.initializeResizer();
    this.initializeEventHandlers();

    // Start observing global state
    this.observeGlobalState();
}

ArtifactDisplayManager.prototype.initializeContainer = function () {
    this.artifactContainer = document.getElementById('artifact-panel');
    this.panelContent = document.getElementById('artifact-display-area');
    this.resizer = document.getElementById('artifact-resizer');
    this.closeBtn = document.getElementById('artifact-panel-close');
};

ArtifactDisplayManager.prototype.initializeResizer = function () {
    if (!this.resizer || !this.artifactContainer) return;

    let isResizing = false;
    let startX = 0;
    let startWidth = 0;

    const startResize = (e) => {
        isResizing = true;
        startX = e.clientX;
        startWidth = this.artifactContainer.offsetWidth;
        document.body.style.cursor = 'ew-resize';
        document.body.style.userSelect = 'none';
        e.preventDefault();
    };

    const doResize = (e) => {
        if (!isResizing) return;

        const dx = startX - e.clientX; // Note: inverted for right-side panel
        const newWidth = Math.max(300, Math.min(800, startWidth + dx));

        this.artifactContainer.style.flexBasis = newWidth + 'px';
        e.preventDefault();
    };

    const stopResize = () => {
        if (isResizing) {
            isResizing = false;
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
        }
    };

    this.resizer.addEventListener('mousedown', startResize);
    document.addEventListener('mousemove', doResize);
    document.addEventListener('mouseup', stopResize);
};

ArtifactDisplayManager.prototype.initializeEventHandlers = function () {
    // Close button
    if (this.closeBtn) {
        this.closeBtn.addEventListener('click', () => {
            this.hidePanel();
        });
    }

    // Click outside to close
    if (this.artifactContainer) {
        this.artifactContainer.addEventListener('click', (e) => {
            if (e.target === this.artifactContainer) {
                this.hidePanel();
            }
        });
    }

    // Register with EventDispatcher for workflow events
    this.registerWithEventDispatcher();
};

ArtifactDisplayManager.prototype.observeGlobalState = function () {
    // Polling for global state changes to trigger UI resets
    setInterval(() => {
        if (window.globalState) {
            let stateChanged = false;

            if (this.currentWorkflow !== window.globalState.currentWorkflow) {
                this.currentWorkflow = window.globalState.currentWorkflow;
                stateChanged = true;
            }

            if (this.currentSessionId !== window.globalState.currentChatSessionId) {
                this.currentSessionId = window.globalState.currentChatSessionId;
                stateChanged = true;
            }

            if (stateChanged) {
                this.hidePanel();
                this.clearArtifacts();
            }
        }
    }, 100);
};

ArtifactDisplayManager.prototype.registerWithEventDispatcher = function () {
    if (window.getEventDispatcher) {
        const dispatcher = window.getEventDispatcher();

        // Register for progressive and artifact events
        dispatcher.registerHandler('progressive_event', this);
        dispatcher.registerHandler('artifact_event', this);
    } else {
        console.warn('[ArtifactDisplayManager] EventDispatcher not available - using legacy event handling');
    }
};

/**
 * Handle workflow events through EventDispatcher interface
 * @param {string} eventType - Event type (progressive_event, artifact_event)
 * @param {Object} data - Event data payload
 * @param {string} workflowId - Associated workflow ID
 */
ArtifactDisplayManager.prototype.handleEvent = function (eventType, data, workflowId) {
    try {
        switch (eventType) {
            case 'progressive_event':
                this.handleProgressiveEvent(data);
                break;

            case 'artifact_event':
                this.handleArtifactEvent(data);
                break;

            default:
                console.warn(`[ArtifactDisplayManager] Unknown event type: ${eventType}`, { data, workflowId });
        }
    } catch (error) {
        console.error(`[ArtifactDisplayManager] Error handling ${eventType}:`, error, { data, workflowId });
    }
};

/**
 * Handle progressive UI events from backend
 * @param {Object} eventData - Progressive event data
 */
ArtifactDisplayManager.prototype.handleProgressiveEvent = function (eventData) {
    if (!eventData || !eventData.action) {
        console.warn('[ArtifactDisplayManager] Invalid progressive event data:', eventData);
        return;
    }

    const { action, panel_id, status, message } = eventData;

    // Convert backend event data to display format
    this.showWorkflowProgress(action, panel_id, status, message);
};

/**
 * Handle artifact events from backend
 * @param {Object} eventData - Artifact event data
 */
ArtifactDisplayManager.prototype.handleArtifactEvent = function (eventData) {
    if (!eventData) {
        console.warn('[ArtifactDisplayManager] Invalid artifact event data:', eventData);
        return;
    }

    // Display the artifact
    this.displayArtifacts([eventData]);
};

ArtifactDisplayManager.prototype.displayArtifacts = async function (artifacts) {
    if (!this.artifactContainer) {
        console.error('[ArtifactDisplayManager] No container found');
        return;
    }

    if (!artifacts || artifacts.length === 0) {
        console.warn('[ArtifactDisplayManager] No artifacts to display');
        this.showError('Unable to load artifacts');
        return;
    }

    // Store artifacts for reopening
    this.lastArtifacts = artifacts;

    // Show the panel
    this.artifactContainer.classList.remove('hidden');
    this.artifactContainer.style.display = 'block';

    // Switch to results tab and render with tabs preserved
    this.currentTab = 'results';
    await this.renderWorkflowProgressTabs();

    console.log('[ArtifactDisplayManager] Artifacts displayed with tabs preserved');
};

ArtifactDisplayManager.prototype.renderArtifact = async function (artifact) {
    console.log('[ArtifactDisplayManager] renderArtifact called with:', artifact);

    if (!artifact) {
        console.warn('[ArtifactDisplayManager] No artifact provided');
        return '';
    }

    this.currentArtifact = artifact;

    const title = this.escapeHtml(artifact.title || artifact.file_name || 'Generated Content');
    const content = artifact.code || artifact.content || '';
    const language = artifact.language || this.detectLanguage(content);
    const artifactType = artifact.type || 'unknown';

    console.log(`[ArtifactDisplayManager] Rendering artifact: type=${artifactType}, language=${language}, contentLength=${content.length}`);

    // Handle different artifact types
    let html;
    if (artifactType === 'document' || artifactType === 'report' || artifactType === 'analysis') {
        // Use unified markdown rendering for document-type artifacts
        console.log('[ArtifactDisplayManager] Using markdown rendering for document-type artifact');
        try {
            html = await this.renderMarkdownArtifact(content);
            console.log(`[ArtifactDisplayManager] Markdown rendering result length: ${html.length}`);
        } catch (error) {
            console.error('[ArtifactDisplayManager] Markdown rendering failed:', error);
            html = `<div class="markdown-content"><pre>${this.escapeHtml(content)}</pre></div>`;
        }
    } else {
        // Render as code for code-type artifacts
        console.log('[ArtifactDisplayManager] Using code rendering for code-type artifact');
        html = `<pre class="language-${language} artifact-code"><code class="language-${language}">${this.escapeHtml(content)}</code></pre>`;
    }

    console.log(`[ArtifactDisplayManager] Initial HTML length: ${html.length}`);

    // Apply syntax highlighting if Prism is available
    if (window.Prism && typeof window.Prism.highlightElement === 'function') {
        // Create a temporary element to apply highlighting
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = html;

        const preElements = tempDiv.querySelectorAll('pre');
        console.log('[ArtifactDisplayManager] Applying Prism highlighting to', preElements.length, 'elements');

        for (const preElement of preElements) {
            // Ensure the pre element has the correct language class
            if (!preElement.className.includes('language-')) {
                preElement.className = `language-${language}`;
            }

            // Ensure the code element inside has the language class too
            const codeElement = preElement.querySelector('code');
            if (codeElement && !codeElement.className.includes('language-')) {
                codeElement.className = `language-${language}`;
            }

            try {
                // Get the raw text content (not HTML-encoded)
                const rawContent = preElement.textContent || preElement.innerText || '';
                console.log(`[ArtifactDisplayManager] Raw content length: ${rawContent.length}`);

                // Check if the language grammar is available
                const grammar = window.Prism.languages[language];
                console.log(`[ArtifactDisplayManager] Grammar available for ${language}:`, !!grammar);

                if (grammar) {
                    // Use Prism.highlight() directly for more control
                    const highlightedHtml = window.Prism.highlight(rawContent, grammar, language);
                    console.log(`[ArtifactDisplayManager] Highlighted HTML length: ${highlightedHtml.length}`);

                    // Replace the content with highlighted HTML
                    preElement.innerHTML = `<code class="language-${language}">${highlightedHtml}</code>`;
                    console.log(`[ArtifactDisplayManager] Applied highlighted HTML to pre element`);

                    // Verify tokens were created
                    const tokenCount = preElement.querySelectorAll('.token').length;
                    console.log(`[ArtifactDisplayManager] Token spans created: ${tokenCount}`);

                    if (tokenCount > 0) {
                        console.log(`[ArtifactDisplayManager] SUCCESS: Syntax highlighting applied with ${tokenCount} tokens!`);
                    } else {
                        console.warn(`[ArtifactDisplayManager] WARNING: No tokens created, but highlighting completed`);
                    }
                } else {
                    console.warn(`[ArtifactDisplayManager] No grammar available for language: ${language}, using fallback`);
                    // Fallback: basic code styling
                    preElement.style.fontFamily = 'Monaco, Menlo, Ubuntu Mono, monospace';
                    preElement.style.backgroundColor = '#f8f9fa';
                    preElement.style.padding = '16px';
                    preElement.style.border = '1px solid #e9ecef';
                    preElement.style.borderRadius = '6px';
                }
            } catch (error) {
                console.error(`[ArtifactDisplayManager] Prism highlighting failed:`, error);
                // Fallback: at least make it look like code
                preElement.style.fontFamily = 'Monaco, Menlo, Ubuntu Mono, monospace';
                preElement.style.backgroundColor = '#f8f9fa';
                preElement.style.padding = '16px';
                preElement.style.border = '1px solid #e9ecef';
                preElement.style.borderRadius = '6px';
            }
        }

        // Get the final HTML after highlighting
        html = tempDiv.innerHTML;
    } else {
        console.warn('[ArtifactDisplayManager] Prism.js not available, using basic styling');
    }

    console.log(`[ArtifactDisplayManager] Final HTML length: ${html.length}`);
    console.log(`[ArtifactDisplayManager] Final HTML preview:`, html.substring(0, 100));

    return html;
};

ArtifactDisplayManager.prototype.detectLanguage = function (content) {
    // Simple language detection based on content patterns
    const sample = content.substring(0, 200).toLowerCase();

    if (sample.includes('function') && sample.includes('{')) return 'javascript';
    if (sample.includes('def ') && sample.includes(':')) return 'python';
    if (sample.includes('class ') && sample.includes('{')) return 'java';
    if (sample.includes('interface ') || sample.includes('class ') && sample.includes(':')) return 'typescript';
    if (sample.includes('<') && sample.includes('>') && sample.includes('/')) return 'html';
    if (sample.includes('#include') || sample.includes('int main')) return 'cpp';
    if (sample.includes('package ') && sample.includes('import ')) return 'java';
    if (sample.includes('return') && sample.includes('string')) return 'typescript';

    return 'plaintext';
};

ArtifactDisplayManager.prototype.formatLanguageName = function (language) {
    // Format language names for display (capitalize first letter)
    if (!language) return 'Code';

    // Handle common cases
    const formatted = language.charAt(0).toUpperCase() + language.slice(1).toLowerCase();

    // Special cases
    if (language.toLowerCase() === 'typescript') return 'TypeScript';
    if (language.toLowerCase() === 'javascript') return 'JavaScript';

    return formatted;
};

ArtifactDisplayManager.prototype.formatArtifactType = function (artifactType) {
    // Format artifact types for display
    if (!artifactType) return 'Content';

    // Handle common cases
    const formatted = artifactType.charAt(0).toUpperCase() + artifactType.slice(1).toLowerCase();

    // Special cases
    if (artifactType.toLowerCase() === 'document') return 'Document';
    if (artifactType.toLowerCase() === 'report') return 'Report';
    if (artifactType.toLowerCase() === 'analysis') return 'Analysis';

    return formatted;
};

ArtifactDisplayManager.prototype.renderMarkdownArtifact = async function (content) {
    // Use the unified markdown rendering engine for document-type artifacts

    if (!content) return '<div class="markdown-content">No content available</div>';

    try {
        // Use the existing markdown unification engine
        if (window.markdownUnificationEngine && typeof window.markdownUnificationEngine.processMarkdown === 'function') {
            const html = await window.markdownUnificationEngine.processMarkdown(content, {});
            return `<div class="markdown-content">${html}</div>`;
        } else {
            // Fallback if markdown engine is not available
            console.warn('[ArtifactDisplayManager] Markdown unification engine not available, using basic rendering');
            return `<div class="markdown-content"><pre>${this.escapeHtml(content)}</pre></div>`;
        }
    } catch (error) {
        console.error('[ArtifactDisplayManager] Error rendering markdown artifact:', error);
        // Fallback to escaped text
        return `<div class="markdown-content"><pre>${this.escapeHtml(content)}</pre></div>`;
    }
};

ArtifactDisplayManager.prototype.escapeHtml = function (text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
};

ArtifactDisplayManager.prototype.copyArtifact = function (index) {
    if (!this.currentArtifact) return;

    const content = this.currentArtifact.code || this.currentArtifact.content || '';
    navigator.clipboard.writeText(content).then(() => {
        console.log('[ArtifactDisplayManager] Artifact copied to clipboard');
        // Could show a toast notification here
    }).catch(err => {
        console.error('[ArtifactDisplayManager] Failed to copy:', err);
    });
};

ArtifactDisplayManager.prototype.downloadArtifact = function (index) {
    if (!this.currentArtifact) return;

    const content = this.currentArtifact.code || this.currentArtifact.content || '';
    const filename = this.currentArtifact.file_name || 'artifact.txt';

    // Create blob and download
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    console.log('[ArtifactDisplayManager] Artifact downloaded:', filename);
};

/**
 * Save current artifact as Raw Text
 */
ArtifactDisplayManager.prototype.saveAsRawText = function (index) {
    console.log('[ArtifactDisplayManager] saveAsRawText called', { index, currentArtifact: !!this.currentArtifact });

    // Ensure we have an artifact to save
    if (!this.currentArtifact && this.lastArtifacts && this.lastArtifacts.length > 0) {
        this.currentArtifact = this.lastArtifacts[index || 0];
    }

    this.downloadArtifact(index);
};

/**
 * Save current artifact as Rich Text (Markdown/HTML)
 */
ArtifactDisplayManager.prototype.saveAsRichText = function (index) {
    console.log('[ArtifactDisplayManager] saveAsRichText called', { index, currentArtifact: !!this.currentArtifact });

    // Ensure we have an artifact to save
    if (!this.currentArtifact && this.lastArtifacts && this.lastArtifacts.length > 0) {
        this.currentArtifact = this.lastArtifacts[index || 0];
    }

    if (!this.currentArtifact) {
        console.warn('[ArtifactDisplayManager] No current artifact to save as rich text');
        return;
    }

    const content = this.currentArtifact.code || this.currentArtifact.content || '';
    const isDocument = this.currentArtifact.type === 'document' ||
        this.currentArtifact.type === 'report' ||
        this.currentArtifact.type === 'analysis';

    let markdownContent = content;
    if (!isDocument) {
        // Wrap code in markdown block for "Rich Text" export of code
        const lang = this.currentArtifact.language || '';
        const title = this.currentArtifact.title || this.currentArtifact.file_name || 'Generated Content';
        markdownContent = `# ${title}\n\n\`\`\`${lang}\n${content}\n\`\`\``;
    }

    const filename = (this.currentArtifact.file_name || 'artifact').split('.')[0] + '.md';
    const type = 'text/markdown';

    const blob = new Blob([markdownContent], { type: type });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    console.log('[ArtifactDisplayManager] Artifact saved as Markdown:', filename);
};

/**
 * Save current artifact as PDF using jspdf and html2canvas
 */
ArtifactDisplayManager.prototype.saveAsPDF = async function (index) {
    console.log('[ArtifactDisplayManager] saveAsPDF called', { index, currentArtifact: !!this.currentArtifact });

    // Ensure we have an artifact to save
    if (!this.currentArtifact && this.lastArtifacts && this.lastArtifacts.length > 0) {
        this.currentArtifact = this.lastArtifacts[index || 0];
    }

    if (!this.currentArtifact) {
        console.warn('[ArtifactDisplayManager] No current artifact to save as PDF');
        return;
    }
    if (!window.jspdf || !window.html2canvas) {
        console.error('[ArtifactDisplayManager] PDF export libraries not loaded');
        alert('PDF export libraries are still loading. Please wait a moment.');
        return;
    }

    const element = this.panelContent;
    const filename = (this.currentArtifact.file_name || 'artifact').split('.')[0] + '.pdf';

    // Show loading status
    const statusMsg = 'Generating PDF...';
    window.updateStatus && window.updateStatus(statusMsg, 'info');

    try {
        const { jsPDF } = window.jspdf;

        // 🛡️ CRITICAL: To capture the FULL content, we need to temporarily disable overflow and height constraints
        const originalStyle = element.getAttribute('style') || '';
        const originalHeight = element.style.height;
        const originalMaxHeight = element.style.maxHeight;
        const originalOverflow = element.style.overflow;

        element.style.height = 'auto';
        element.style.maxHeight = 'none';
        element.style.overflow = 'visible';

        const canvas = await html2canvas(element, {
            scale: 1.5, // Slightly lower scale for better performance on large files
            useCORS: true,
            logging: true,
            backgroundColor: '#ffffff',
            scrollY: -window.scrollY // Fix for scrolled pages
        });

        // Restore original styles
        element.style.height = originalHeight;
        element.style.maxHeight = originalMaxHeight;
        element.style.overflow = originalOverflow;

        const imgData = canvas.toDataURL('image/png');
        const pdf = new jsPDF('p', 'mm', 'a4');
        const pdfWidth = pdf.internal.pageSize.getWidth();
        const pdfHeight = (canvas.height * pdfWidth) / canvas.width;

        const pageHeight = pdf.internal.pageSize.getHeight();
        let heightLeft = pdfHeight;
        let position = 0;

        // Add first page
        pdf.addImage(imgData, 'PNG', 0, position, pdfWidth, pdfHeight);
        heightLeft -= pageHeight;

        // Add additional pages if needed
        while (heightLeft > 0) {
            position = heightLeft - pdfHeight;
            pdf.addPage();
            pdf.addImage(imgData, 'PNG', 0, position, pdfWidth, pdfHeight);
            heightLeft -= pageHeight;
        }

        pdf.save(filename);
        window.updateStatus && window.updateStatus('PDF saved successfully', 'success');

    } catch (error) {
        console.error('[ArtifactDisplayManager] PDF export failed:', error);
        window.updateStatus && window.updateStatus('PDF export failed', 'error');
        alert('Failed to generate PDF. Please try again.');
    }
};

ArtifactDisplayManager.prototype.hidePanel = function () {
    if (this.artifactContainer) {
        this.artifactContainer.classList.add('hidden');
        this.artifactContainer.style.display = 'none';
    }
    this.currentArtifact = null;
};

ArtifactDisplayManager.prototype.clearArtifacts = function () {
    this.lastArtifacts = null;
    this.currentArtifact = null;
    if (this.panelContent) {
        this.panelContent.innerHTML = '';
    }
};

ArtifactDisplayManager.prototype.isPanelOpen = function () {
    return this.artifactContainer &&
        !this.artifactContainer.classList.contains('hidden') &&
        this.artifactContainer.style.display !== 'none';
};

ArtifactDisplayManager.prototype.showPanel = async function () {
    if (!this.artifactContainer) {
        console.error('[ArtifactDisplayManager] No container found');
        return;
    }

    // Show the panel
    this.artifactContainer.classList.remove('hidden');
    this.artifactContainer.style.display = 'block';

    // Check if we have artifacts to show
    if (this.lastArtifacts && this.lastArtifacts.length > 0) {
        // Display first artifact
        const artifact = this.lastArtifacts[0];
        this.currentArtifact = artifact;
        const html = await this.renderArtifact(artifact);
        if (html) {
            this.panelContent.innerHTML = html;
        } else {
            this.showError('Unable to render artifact');
        }
        console.log('[ArtifactDisplayManager] Panel reopened with last artifacts');
    } else {
        // Show empty state for new workflow context
        this.showEmptyState();
        console.log('[ArtifactDisplayManager] Panel shown with empty state for new workflow context');
    }
};

ArtifactDisplayManager.prototype.showError = function (message) {
    if (!this.panelContent) return;

    this.panelContent.innerHTML = `
        <div class="artifact-error">
            <div class="error-message">${this.escapeHtml(message)}</div>
        </div>
    `;

    // Show the panel even with error
    if (this.artifactContainer) {
        this.artifactContainer.classList.remove('hidden');
        this.artifactContainer.style.display = 'block';
    }
};

/**
 * Show empty state when no artifacts are available for current workflow
 */
ArtifactDisplayManager.prototype.showEmptyState = function () {
    if (!this.panelContent) return;

    this.panelContent.innerHTML = `
        <div class="artifact-empty-state">
            <div class="empty-state-icon">📄</div>
            <div class="empty-state-title">No Artifacts Yet</div>
            <div class="empty-state-message">
                Artifacts will appear here once you start a conversation with this workflow.
                Ask a question to begin generating content.
            </div>
        </div>
    `;

    console.log('[ArtifactDisplayManager] Showing empty state for new workflow context');
};

/**
 * Handle progressive UI events (message-driven)
 */
ArtifactDisplayManager.prototype.showWorkflowProgress = function (action, panelId, status, message) {
    console.log(`[ArtifactDisplayManager] Showing workflow progress: ${action} on ${panelId}`, { status, message });

    if (!this.artifactContainer) {
        console.error('[ArtifactDisplayManager] No container found for workflow progress');
        return;
    }

    // Initialize workflow progress data if not exists
    if (!this.workflowProgress) {
        this.workflowProgress = {
            panels: {}
        };
    }

    // Handle different action types
    if (action === 'create_panel') {
        // Simple panel creation
        this.workflowProgress.panels[panelId] = {
            id: panelId,
            action: action,
            title: panelId.charAt(0).toUpperCase() + panelId.slice(1),
            message: message || '',
            status: status || 'unknown'
        };
    } else if (action === 'create_nested') {
        // Nested panel creation (supports sub-panels)
        this.workflowProgress.panels[panelId] = {
            id: panelId,
            action: action,
            title: panelId.charAt(0).toUpperCase() + panelId.slice(1),
            message: message || '',
            status: status || 'unknown',
            subpanels: {}
        };
    } else if (action === 'update_nested') {
        // Hierarchical sub-panel update
        const [parentId, subId] = panelId.split('.');
        if (this.workflowProgress.panels[parentId]?.action === 'create_nested') {
            this.workflowProgress.panels[parentId].subpanels[subId] = {
                message: message || '',
                status: status || 'unknown'
            };
        }
    }

    // Show the panel
    this.artifactContainer.classList.remove('hidden');
    this.artifactContainer.style.display = 'block';

    // Set current tab to progress
    this.currentTab = 'progress';

    // Render the tabbed interface
    this.renderWorkflowProgressTabs();

    console.log(`[ArtifactDisplayManager] Workflow progress displayed for panel: ${action} completed on ${panelId}`);
};

/**
 * Add a question to workflow progress
 */
ArtifactDisplayManager.prototype.addWorkflowQuestion = function (panelId, questionId, questionText, status) {
    console.log(`[ArtifactDisplayManager] Adding question ${questionId} to panel ${panelId}`);

    if (!this.workflowProgress || !this.workflowProgress.panels[panelId]) {
        console.warn(`[ArtifactDisplayManager] Panel ${panelId} not found for question`);
        return;
    }

    // Store question data
    this.workflowProgress.questions[questionId] = {
        id: questionId,
        panelId: panelId,
        text: questionText,
        status: status,
        answer: null
    };

    // Add to panel's questions list
    if (!this.workflowProgress.panels[panelId].questions) {
        this.workflowProgress.panels[panelId].questions = [];
    }
    this.workflowProgress.panels[panelId].questions.push(questionId);

    // Re-render if currently showing progress tab
    if (this.currentTab === 'progress') {
        this.renderWorkflowProgressTabs();
    }
};

/**
 * Generic sub-panel update (language/workflow agnostic)
 */
ArtifactDisplayManager.prototype.updateSubPanel = function (subPanelId, status, message, parentPanelId = null) {
    console.log(`[ArtifactDisplayManager] Updating sub-panel ${subPanelId} in ${parentPanelId || 'any nested panel'}`);

    if (parentPanelId) {
        // Update specific nested panel
        const parentPanel = this.workflowProgress.panels[parentPanelId];
        if (parentPanel?.action === 'create_nested' && parentPanel.subpanels) {
            parentPanel.subpanels[subPanelId] = {
                message: message || '',
                status: status || 'unknown'
            };
        }
    } else {
        // Find any nested panel containing this sub-panel
        const parentPanel = Object.values(this.workflowProgress.panels)
            .find(panel => panel.action === 'create_nested' && panel.subpanels?.[subPanelId]);

        if (parentPanel) {
            parentPanel.subpanels[subPanelId] = {
                message: message || '',
                status: status || 'unknown'
            };
        }
    }

    // Re-render if currently showing progress tab
    if (this.currentTab === 'progress') {
        this.renderWorkflowProgressTabs();
    }
};

/**
 * Switch to results tab when workflow completes
 */
ArtifactDisplayManager.prototype.switchToResultsTab = function () {
    console.log('[ArtifactDisplayManager] Switching to results tab');
    this.currentTab = 'results';
    this.renderWorkflowProgressTabs();
};

/**
 * Render the tabbed interface for workflow progress/results
 */
ArtifactDisplayManager.prototype.renderWorkflowProgressTabs = function () {
    if (!this.panelContent) return;

    // Create tab navigation in the artifact-item compact div
    const compactDiv = document.querySelector('.artifact-item.compact');
    if (compactDiv) {
        compactDiv.innerHTML = `
                <div class="artifact-tabs">
                    <button class="artifact-tab ${this.currentTab === 'progress' ? 'active' : ''}" onclick="window.artifactDisplayManager.switchTab('progress')">
                        🔄 Progress
                    </button>
                    <button class="artifact-tab ${this.currentTab === 'results' ? 'active' : ''}" onclick="window.artifactDisplayManager.switchTab('results')">
                        📄 Results
                    </button>
                </div>
            `;
    }

    let contentHtml = '';

    if (this.currentTab === 'progress') {
        // Render progress content
        contentHtml = '<div class="workflow-progress-content">';

        if (this.workflowProgress) {
            const panels = Object.values(this.workflowProgress.panels);
            const questions = this.workflowProgress.questions;

            panels.forEach(panel => {
                contentHtml += `
                        <div class="progress-panel workflow-panel">
                            <div class="panel-main">
                                <div class="panel-header">
                                    <div class="content">
                                        <div class="title">${this.escapeHtml(panel.title)}</div>
                                        <div class="description">${this.escapeHtml(panel.message || panel.description || '')}</div>
                                    </div>
                                    <div class="status">${this.getStatusDisplay(panel.status)}</div>
                                </div>
                    `;

                // Render nested sub-panels for message-driven UI
                if (panel.action === 'create_nested' && panel.subpanels && Object.keys(panel.subpanels).length > 0) {
                    contentHtml += '<div class="sub-panels-container"><div class="sub-panels">';
                    Object.entries(panel.subpanels).forEach(([subId, subPanel]) => {
                        const content = subPanel.message || '';
                        const displayText = content.length > 60 ?
                            content.substring(0, 57) + '...' :
                            content.substring(0, content.length);

                        contentHtml += `
                                <div class="sub-panel workflow-sub-panel">
                                    <div class="content">
                                        <div class="title">${this.escapeHtml(displayText)}</div>
                                        <div class="description">Status: ${this.getStatusDisplay(subPanel.status)}</div>
                                    </div>
                                </div>
                            `;
                    });
                    contentHtml += '</div></div>';
                }

                contentHtml += '</div>';

                contentHtml += '</div></div>';
            });
        } else {
            contentHtml += '<div class="no-progress">No workflow progress available.</div>';
        }

        contentHtml += '</div>';
    } else if (this.currentTab === 'results') {
        // Render results content (artifacts)
        if (this.lastArtifacts && this.lastArtifacts.length > 0) {
            // Use existing artifact rendering - handle async properly
            this.renderArtifact(this.lastArtifacts[0]).then(html => {
                if (html) {
                    // Remove the tabs from the artifact HTML and add our own
                    const artifactHtml = html.replace(/<div class="workflow-tabs">[\s\S]*?<\/div>/, '');
                    const contentHtml = '<div class="workflow-results-content">';
                    this.panelContent.innerHTML = contentHtml + artifactHtml;
                } else {
                    // Fallback if no HTML returned
                    this.panelContent.innerHTML = `
                            <div class="workflow-results-content">
                                <div class="no-results">Unable to render artifacts.</div>
                            </div>
                        `;
                }
            }).catch(error => {
                console.error('[ArtifactDisplayManager] Error rendering artifact:', error);
                this.panelContent.innerHTML = `
                        <div class="workflow-results-content">
                            <div class="no-results">Error rendering artifacts: ${error.message}</div>
                        </div>
                    `;
            });
            return; // Async rendering handled above
        } else {
            contentHtml = `
                    <div class="workflow-results-content">
                        <div class="no-results">No results available yet. Workflow is still in progress.</div>
                    </div>
                `;
        }
    }

    this.panelContent.innerHTML = contentHtml;
};

/**
 * Switch between tabs
 */
ArtifactDisplayManager.prototype.switchTab = function (tabName) {
    console.log(`[ArtifactDisplayManager] Switching to tab: ${tabName}`);
    this.currentTab = tabName;
    this.renderWorkflowProgressTabs();
};

/**
 * Clear workflow progress when switching workflows
 */
ArtifactDisplayManager.prototype.clearWorkflowProgress = function () {
    console.log('[ArtifactDisplayManager] Clearing workflow progress and artifacts for workflow isolation');

    // Clear all workflow-specific data
    this.workflowProgress = null;
    this.lastArtifacts = null;
    this.currentArtifact = null;
    this.currentTab = 'progress';

    // Clear the panel content completely
    if (this.panelContent) {
        this.panelContent.innerHTML = '';
    }

    // Clear the compact DIV tabs
    const compactDiv = document.querySelector('.artifact-item.compact');
    if (compactDiv) {
        compactDiv.innerHTML = '';
    }

    // Hide the panel to ensure clean state
    this.hidePanel();

    console.log('[ArtifactDisplayManager] Workflow data and artifacts cleared for new workflow context');
};

/**
 * Get HTML display for status (shared with chat-ui-manager)
 */
ArtifactDisplayManager.prototype.getStatusDisplay = function (status) {
    switch (status) {
        case 'inprogress':
            return '<div class="spinner"></div><span>In Progress</span>';
        case 'complete':
            return '<span class="checkmark">✓</span><span>Complete</span>';
        case 'pending':
            return '<span>Pending</span>';
        default:
            return `<span>${status || 'Unknown'}</span>`;
    }
};

/**
 * PROPOSAL 3: JavaScript-Controlled Height
 *
 * This function provides dynamic height calculation for the artifact scroll area
 * based on available viewport space. It can be useful for responsive layouts where
 * the artifact panel height needs to adapt to different screen sizes.
 *
 * PURPOSE:
 * - Calculate available height by subtracting header and padding from panel height
 * - Set explicit height on scroll container for consistent scrolling behavior
 * - Handle window resize events to maintain proper dimensions
 *
 * USAGE:
 * - Call this.updateScrollContainerHeight() after displaying artifacts
 * - Add resize event listener: window.addEventListener('resize', () => this.updateScrollContainerHeight())
 *
 * NOTE: This function is currently NOT activated. It can be safely removed if the
 * CSS-based max-height: 70vh approach (Proposal 2) provides sufficient functionality.
 * The CSS approach is simpler and doesn't require JavaScript overhead.
 */
ArtifactDisplayManager.prototype.updateScrollContainerHeight = function () {
    if (!this.artifactContainer || !this.panelContent) return;

    // Get panel dimensions
    const panelRect = this.artifactContainer.getBoundingClientRect();
    const panelHeight = panelRect.height;

    // Calculate header height (if present)
    const header = this.artifactContainer.querySelector('.artifact-header');
    const headerHeight = header ? header.offsetHeight : 0;

    // Calculate padding and other spacing
    const padding = 32; // Account for padding in scroll area

    // Calculate available height for scroll container
    const availableHeight = Math.max(200, panelHeight - headerHeight - padding);

    // Set explicit height on scroll container
    this.panelContent.style.height = availableHeight + 'px';
    this.panelContent.style.overflowY = 'auto';
    this.panelContent.style.overflowX = 'auto';

    console.log(`[ArtifactDisplayManager] Updated scroll container height: ${availableHeight}px`);
};

// Test function for debugging
window.testArtifactPanel = function () {
    console.log('=== ARTIFACT PANEL TEST ===');

    const testArtifact = {
        title: 'Test TypeScript Component',
        file_name: 'TestComponent.tsx',
        language: 'typescript',
        code: `import React, { useState } from 'react';

interface Props {
    title: string;
    onClick?: () => void;
}

const TestComponent: React.FC<Props> = ({ title, onClick }) => {
    const [count, setCount] = useState<number>(0);

    return (
        <div className="test-component">
            <h1>{title}</h1>
            <p>Count: {count}</p>
            <button onClick={() => setCount(count + 1)}>
                Increment
            </button>
            {onClick && (
                <button onClick={onClick}>
                    Custom Action
                </button>
            )}
        </div>
    );
};

export default TestComponent;`
    };

    if (window.artifactDisplayManager) {
        window.artifactDisplayManager.displayArtifacts([testArtifact]);
    } else {
        console.error('ArtifactDisplayManager not initialized');
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function () {
    window.artifactDisplayManager = new ArtifactDisplayManager();
});
