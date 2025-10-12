/**
 * Artifact Display Manager - Phase 5.6D Frontend Modularization
 *
 * Handles rich UI display and interactions for workflow artifacts.
 * NEW FEATURE: Displays generated content (code, docs, etc.) from JSON workflow responses.
 */

// Artifact display state and configuration
let artifactPanelVisible = false;
let currentArtifacts = [];

// Core Artifact Display Manager Class
class ArtifactDisplayManager {
    constructor() {
        this.initializeContainer();
        this.attachToChatInterface();
        this.setupEventListeners();
    }

    /**
     * Initialize artifact container in DOM
     */
    initializeContainer() {
        // Create artifact panel container
        this.artifactContainer = document.createElement('div');
        this.artifactContainer.id = 'artifact-panel';
        this.artifactContainer.className = 'artifact-panel';
        this.artifactContainer.innerHTML = `
            <div class="artifact-panel-header">
                <h3>Generated Artifacts</h3>
                <button class="artifact-toggle-btn" id="artifact-toggle-btn">
                    <span class="toggle-icon">⬇️</span>
                </button>
                <button class="artifact-close-btn" id="artifact-close-btn">✖</button>
            </div>
            <div class="artifact-panel-content" id="artifact-panel-content">
                <div class="artifact-placeholder">
                    <div class="artifact-icon">📎</div>
                    <p>No artifacts generated yet</p>
                    <small>Artifacts will appear here when workflows generate code, documents, or other content</small>
                </div>
            </div>
        `;

        // Insert artifact panel into chat interface
        const chatInterface = document.getElementById('chat-interface');
        if (chatInterface) {
            chatInterface.appendChild(this.artifactContainer);
        }

        // Get references to panel elements
        this.panelHeader = this.artifactContainer.querySelector('.artifact-panel-header');
        this.panelContent = document.getElementById('artifact-panel-content');
        this.toggleBtn = document.getElementById('artifact-toggle-btn');
        this.closeBtn = document.getElementById('artifact-close-btn');

        console.log('[ArtifactDisplayManager] Artifact panel initialized');
    }

    /**
     * Attach artifact panel to chat interface layout
     */
    attachToChatInterface() {
        // Add CSS for artifact panel (will be added to stylesheets)
        this.addArtifactStyles();

        // Initially collapse the panel
        this.artifactContainer.classList.add('collapsed');
        artifactPanelVisible = false;
    }

    /**
     * Add CSS styles for artifact panel
     */
    addArtifactStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .artifact-panel {
                position: absolute;
                right: 10px;
                bottom: 80px;
                width: 400px;
                max-height: 400px;
                background: var(--panel-bg, white);
                border: 1px solid var(--border-color, #ddd);
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                display: flex;
                flex-direction: column;
                z-index: 1000;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }

            .artifact-panel.collapsed .artifact-panel-content {
                display: none;
            }

            .artifact-panel-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 12px 16px;
                border-bottom: 1px solid var(--border-color, #eee);
                background: var(--header-bg, #f8f9fa);
                border-radius: 8px 8px 0 0;
            }

            .artifact-panel-header h3 {
                margin: 0;
                font-size: 14px;
                font-weight: 600;
                color: var(--text-color, #333);
            }

            .artifact-toggle-btn, .artifact-close-btn {
                background: none;
                border: none;
                cursor: pointer;
                padding: 4px;
                border-radius: 4px;
                color: var(--text-muted, #666);
                transition: background-color 0.2s;
            }

            .artifact-toggle-btn:hover, .artifact-close-btn:hover {
                background: var(--hover-bg, #e9ecef);
            }

            .artifact-panel-content {
                flex: 1;
                overflow-y: auto;
                max-height: 300px;
            }

            .artifact-placeholder {
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                padding: 40px 20px;
                text-align: center;
                color: var(--text-muted, #666);
            }

            .artifact-icon {
                font-size: 32px;
                margin-bottom: 12px;
                opacity: 0.6;
            }

            .artifact-list {
                padding: 0;
                margin: 0;
            }

            .artifact-item {
                border-bottom: 1px solid var(--border-color, #f0f0f0);
                padding: 12px 16px;
                transition: background-color 0.2s;
            }

            .artifact-item:hover {
                background: var(--hover-bg, #f8f9fa);
            }

            .artifact-item-header {
                display: flex;
                align-items: center;
                margin-bottom: 8px;
            }

            .artifact-type-icon {
                margin-right: 8px;
                font-size: 16px;
            }

            .artifact-title {
                font-weight: 600;
                font-size: 14px;
                color: var(--text-color, #333);
                flex: 1;
            }

            .artifact-meta {
                font-size: 12px;
                color: var(--text-muted, #666);
                margin-bottom: 8px;
            }

            .artifact-content {
                background: var(--code-bg, #f6f8fa);
                border: 1px solid var(--border-color, #e1e4e8);
                border-radius: 6px;
                padding: 12px;
                font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
                font-size: 13px;
                line-height: 1.4;
                white-space: pre-wrap;
                word-wrap: break-word;
                max-height: 200px;
                overflow-y: auto;
                margin-bottom: 8px;
            }

            .artifact-actions {
                display: flex;
                gap: 8px;
            }

            .artifact-action-btn {
                padding: 4px 8px;
                font-size: 12px;
                border: 1px solid var(--border-color, #ddd);
                background: var(--btn-bg, white);
                color: var(--text-color, #333);
                border-radius: 4px;
                cursor: pointer;
                transition: background-color 0.2s;
            }

            .artifact-action-btn:hover {
                background: var(--hover-bg, #f0f0f0);
            }

            .artifact-action-btn.primary {
                background: var(--primary-color, #007bff);
                color: white;
                border-color: var(--primary-color, #007bff);
            }

            .toggle-icon {
                transition: transform 0.2s;
            }

            .artifact-panel.collapsed .toggle-icon {
                transform: rotate(180deg);
            }

            /* Code syntax highlighting (basic) */
            .artifact-content .keyword { color: #0000ff; font-weight: bold; }
            .artifact-content .string { color: #008000; }
            .artifact-content .comment { color: #808080; font-style: italic; }
            .artifact-content .number { color: #ff6600; }

            /* Responsive adjustments */
            @media (max-width: 768px) {
                .artifact-panel {
                    width: calc(100vw - 20px);
                    right: 10px;
                    bottom: 10px;
                }
            }
        `;

        document.head.appendChild(style);
    }

    /**
     * Setup event listeners for panel controls
     */
    setupEventListeners() {
        // Toggle panel collapse/expand
        if (this.toggleBtn) {
            this.toggleBtn.addEventListener('click', () => this.togglePanel());
        }

        // Close panel
        if (this.closeBtn) {
            this.closeBtn.addEventListener('click', () => this.hidePanel());
        }

        console.log('[ArtifactDisplayManager] Event listeners attached');
    }

    /**
     * Toggle panel visibility (collapse/expand)
     */
    togglePanel() {
        if (!this.artifactContainer || !this.panelContent) return;

        artifactPanelVisible = !artifactPanelVisible;

        if (artifactPanelVisible) {
            this.artifactContainer.classList.remove('collapsed');
            this.panelContent.style.display = 'block';
        } else {
            this.artifactContainer.classList.add('collapsed');
            this.panelContent.style.display = 'none';
        }

        // Update toggle icon
        const toggleIcon = this.toggleBtn?.querySelector('.toggle-icon');
        if (toggleIcon) {
            toggleIcon.textContent = artifactPanelVisible ? '⬇️' : '⬆️';
        }

        console.log(`[ArtifactDisplayManager] Panel ${artifactPanelVisible ? 'expanded' : 'collapsed'}`);
    }

    /**
     * Show artifact panel
     */
    showPanel() {
        if (!this.artifactContainer) return;

        this.artifactContainer.style.display = 'flex';
        artifactPanelVisible = true;
        this.artifactContainer.classList.remove('collapsed');
        this.panelContent.style.display = 'block';

        console.log('[ArtifactDisplayManager] Panel shown');

        // Add visual indicator in status bar
        window.updateStatus && window.updateStatus('Artifacts ready for review', 'success');
    }

    /**
     * Hide artifact panel
     */
    hidePanel() {
        if (!this.artifactContainer) return;

        this.artifactContainer.style.display = 'none';
        artifactPanelVisible = false;

        console.log('[ArtifactDisplayManager] Panel hidden');
    }

    /**
     * Main function: Display artifacts from workflow response
     */
    displayArtifacts(artifacts) {
        if (!Array.isArray(artifacts) || artifacts.length === 0) {
            console.warn('[ArtifactDisplayManager] No artifacts to display');
            return;
        }

        currentArtifacts = artifacts;
        this.renderArtifacts(artifacts);
        this.showPanel();

        console.log(`[ArtifactDisplayManager] Displaying ${artifacts.length} artifacts`);
    }

    /**
     * Render artifacts in the panel (using string concatenation to avoid template literal conflicts)
     */
    renderArtifacts(artifacts) {
        if (!this.panelContent) return;

        // Clear placeholder and render artifacts
        const artifactHTML = artifacts.map((artifact, index) =>
            this.createArtifactElement(artifact, index)
        ).join('');

        // Use string concatenation to avoid template literal evaluation issues with curly braces in code
        this.panelContent.innerHTML = '<div class="artifact-list">' + artifactHTML + '</div>';
    }

    /**
     * Create HTML element for a single artifact
     */
    createArtifactElement(artifact, index) {
        const type = artifact.type || 'unknown';
        const title = artifact.title || artifact.filename || `Generated ${type}`;
        const language = artifact.language || '';
        const content = artifact.code || artifact.content || artifact.data || '';

        // Determine appropriate icon based on type
        const icon = this.getTypeIcon(type);

        // Format content based on type
        const formattedContent = this.formatArtifactContent(content, language, type);

        // Calculate size information
        const sizeInfo = this.getSizeInfo(content, type);

        return `
            <div class="artifact-item" data-artifact-index="${index}">
                <div class="artifact-item-header">
                    <span class="artifact-type-icon">${icon}</span>
                    <span class="artifact-title">${title}</span>
                </div>
                <div class="artifact-meta">
                    Type: ${type}${language ? ` (${language})` : ''}${sizeInfo ? ` • ${sizeInfo}` : ''}
                </div>
                <div class="artifact-content" data-content-type="${type}" data-language="${language}">
                    ${formattedContent}
                </div>
                <div class="artifact-actions">
                    <button class="artifact-action-btn primary" onclick="window.artifactDisplayManager.copyArtifact(${index})">
                        📋 Copy
                    </button>
                    <button class="artifact-action-btn" onclick="window.artifactDisplayManager.downloadArtifact(${index})">
                        💾 Download
                    </button>
                    <button class="artifact-action-btn" onclick="window.artifactDisplayManager.previewArtifact(${index})">👁️ Preview</button>
                </div>
            </div>
        `;
    }

    /**
     * Get appropriate icon for artifact type
     */
    getTypeIcon(type) {
        const iconMap = {
            'code': '💻',
            'python': '🐍',
            'javascript': '🟨',
            'html': '🌐',
            'css': '🎨',
            'json': '📄',
            'document': '📝',
            'text': '📄',
            'markdown': '📝',
            'yaml': '📋',
            'xml': '🏗️',
            'sql': '🗄️'
        };

        // Match exact type or check if type contains keywords
        for (const [key, icon] of Object.entries(iconMap)) {
            if (type.toLowerCase().includes(key)) {
                return icon;
            }
        }

        return '📎'; // Default attachment icon
    }

    /**
     * Format artifact content based on type and language
     */
    formatArtifactContent(content, language, type) {
        console.log('[ArtifactDisplayManager] formatArtifactContent called with content length:', content?.length || 0);

        if (!content) return '<em>No content available</em>';

        let formattedContent = content;
        console.log('[ArtifactDisplayManager] Original content sample:', content.substring(0, 100));

        // VERIFICATION: Ensure we're working with plain text (no existing HTML encoding)
        // Test for HTML entity markers - these should NOT be present
        const hasHtmlEntities = /<|>|&|&#x27;|&#x2f;/i.test(formattedContent.substring(0, 100));
        console.log('[ArtifactDisplayManager] Content has HTML entities:', hasHtmlEntities);

        // DEBUG: Disable ALL formatting temporarily to test if basic HTML works
        try {
            // Simple HTML escaping to prevent injection issues
            formattedContent = this.escapeHtml(formattedContent);
        } catch (e) {
            console.error('[ArtifactDisplayManager] HTML escaping failed:', e);
            // Return original content if escaping fails
            return '<pre>' + content.substring(0, 500) + (content.length > 500 ? '...' : '') + '</pre>';
        }

        console.log('[ArtifactDisplayManager] Final formatted content length:', formattedContent.length);
        return formattedContent;
    }

    /**
     * HTML escape function to prevent HTML entity interpretation
     */
    escapeHtml(text) {
        if (!text) return text;

        console.log('[ArtifactDisplayManager] escapeHtml input sample:', text.substring(0, 50));

        // Convert HTML entities to prevent interpretation as HTML tags
        text = text.replace(/&/g, '&');
        text = text.replace(/</g, '<');
        text = text.replace(/>/g, '>');
        text = text.replace(/"/g, '"');
        text = text.replace(/'/g, '&#039;');

        // Double escape backslashes so \" becomes \\"
        text = text.replace(/\\/g, '\\\\');

        console.log('[ArtifactDisplayManager] escapeHtml output sample:', text.substring(0, 50));

        return text;
    }

    /**
     * Apply basic syntax highlighting with proper HTML escaping
     */
    applyBasicSyntaxHighlighting(content, language) {
        // First, HTML-escape the entire content to prevent HTML entity conflicts
        let highlighted = this.escapeHtml(content);

        if (language === 'python') {
            // Apply HTML un-escaping just for our span tags, since we need raw HTML
            const keywordSpan = '<span class="keyword">';
            const stringSpan = '<span class="string">';
            const commentSpan = '<span class="comment">';
            const spanClose = '</span>';

            // Python keywords
            const keywords = ['def', 'class', 'if', 'else', 'elif', 'for', 'while', 'try', 'except', 'import', 'from', 'return', 'print'];
            keywords.forEach(keyword => {
                // Word boundary regex to avoid partial matches
                const regex = new RegExp(`\\b${keyword}\\b`, 'g');
                const replacement = keywordSpan + keyword + spanClose;
                highlighted = highlighted.replace(regex, replacement);
            });

            // Strings (single and double quotes) - match entire quoted string
            highlighted = highlighted.replace(/(['"])((?:\\.|(?!\1)[^\\\n])*?)\1/g, stringSpan + '$&' + spanClose);

            // Comments (everything after # until end of line)
            highlighted = highlighted.replace(/(#.*)$/gm, commentSpan + '$1' + spanClose);
        }

        if (language === 'javascript') {
            const keywordSpan = '<span class="keyword">';
            const stringSpan = '<span class="string">';
            const spanClose = '</span>';

            const keywords = ['function', 'const', 'let', 'var', 'if', 'else', 'for', 'while', 'try', 'catch', 'return', 'console'];
            keywords.forEach(keyword => {
                const regex = new RegExp(`\\b${keyword}\\b`, 'g');
                const replacement = keywordSpan + keyword + spanClose;
                highlighted = highlighted.replace(regex, replacement);
            });

            // Strings
            highlighted = highlighted.replace(/(['"])((?:\\.|(?!\1)[^\\\n])*?)\1/g, stringSpan + '$&' + spanClose);
        }

        return highlighted;
    }

    /**
     * Get size information for artifact
     */
    getSizeInfo(content, type) {
        if (!content) return '';

        const size = content.length;

        if (type.includes('code') || type.includes('script')) {
            const lines = content.split('\n').length;
            return `${lines} lines, ${size} chars`;
        }

        return `${size} characters`;
    }

    /**
     * Copy artifact content to clipboard
     */
    async copyArtifact(index) {
        if (index < 0 || index >= currentArtifacts.length) return;

        const artifact = currentArtifacts[index];
        const content = artifact.code || artifact.content || artifact.data || '';

        try {
            // Check if Clipboard API is available (secure contexts only)
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(content);
                window.updateStatus && window.updateStatus('Artifact copied to clipboard', 'success');
            } else {
                // Fallback to older document.execCommand for non-secure contexts
                const textArea = document.createElement('textarea');
                textArea.value = content;
                document.body.appendChild(textArea);
                textArea.select();

                const successful = document.execCommand('copy');
                document.body.removeChild(textArea);

                if (successful) {
                    window.updateStatus && window.updateStatus('Artifact copied to clipboard', 'success');
                } else {
                    throw new Error('Fallback copy failed');
                }
            }

            // Add temporary success styling
            const copyBtn = this.panelContent.querySelector(`[data-artifact-index="${index}"] .artifact-action-btn.primary`);
            if (copyBtn) {
                const originalText = copyBtn.innerHTML;
                copyBtn.innerHTML = '✅ Copied!';
                setTimeout(() => copyBtn.innerHTML = originalText, 2000);
            }

        } catch (error) {
            console.error('[ArtifactDisplayManager] Failed to copy artifact:', error);
            // Show user-friendly error
            const errorMsg = navigator.clipboard ?
                'Failed to copy artifact' :
                'Copy not supported in this browser context';
            window.updateStatus && window.updateStatus(errorMsg, 'error');
        }
    }

    /**
     * Download artifact as file
     */
    downloadArtifact(index) {
        if (index < 0 || index >= currentArtifacts.length) return;

        const artifact = currentArtifacts[index];
        const content = artifact.code || artifact.content || artifact.data || '';
        const type = artifact.type || 'unknown';

        // Build filename safely - avoid modifying artifact properties
        let filename = artifact.filename || `artifact_${index + 1}`;
        const extension = this.getFileExtension(type, artifact.language);

        // Convert to string and ensure proper extension
        filename = String(filename);
        if (!filename.includes('.')) {
            filename = filename + extension;
        }

        try {
            const blob = new Blob([content], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);

            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            window.updateStatus && window.updateStatus(`Downloaded ${filename}`, 'success');
        } catch (error) {
            console.error('[ArtifactDisplayManager] Download failed:', error);
            window.updateStatus && window.updateStatus('Download failed', 'error');
        }
    }

    /**
     * Get appropriate file extension
     */
    getFileExtension(type, language) {
        if (language === 'python') return '.py';
        if (language === 'javascript') return '.js';
        if (language === 'html') return '.html';
        if (language === 'css') return '.css';
        if (language === 'json') return '.json';
        if (language === 'markdown') return '.md';
        if (language === 'yaml') return '.yml';
        if (language === 'xml') return '.xml';
        if (language === 'sql') return '.sql';

        if (type === 'document') return '.txt';
        if (type === 'code') return '.txt';

        return '.txt';
    }

    /**
     * Preview artifact (for code artifacts)
     */
    previewArtifact(index) {
        if (index < 0 || index >= currentArtifacts.length) return;

        const artifact = currentArtifacts[index];
        const content = artifact.code || artifact.content || artifact.data || '';
        const title = artifact.title || artifact.filename || `Artifact ${index + 1}`;

        // Open in a simple modal or new window
        const previewWindow = window.open('', '_blank', 'width=800,height=600');
        if (previewWindow) {
            previewWindow.document.write(`
                <html>
                    <head>
                        <title>${title}</title>
                        <style>
                            body { font-family: monospace; padding: 20px; margin: 0; }
                            pre { white-space: pre-wrap; word-wrap: break-word; }
                        </style>
                    </head>
                    <body>
                        <h2>${title}</h2>
                        <pre>${content}</pre>
                    </body>
                </html>
            `);
        }

        window.updateStatus && window.updateStatus('Artifact opened in preview', 'info');
    }

    /**
     * Clear all artifacts and hide panel
     */
    clearArtifacts() {
        currentArtifacts = [];
        this.panelContent.innerHTML = `
            <div class="artifact-placeholder">
                <div class="artifact-icon">📎</div>
                <p>No artifacts available</p>
                <small>Artifacts will appear here when workflows generate content</small>
            </div>
        `;
        this.hidePanel();
    }

    /**
     * Get current artifacts
     */
    getCurrentArtifacts() {
        return currentArtifacts;
    }

    /**
     * Check if panel is visible
     */
    isVisible() {
        return artifactPanelVisible && this.artifactContainer && this.artifactContainer.style.display !== 'none';
    }
}

// Initialize when DOM is ready and export globally
document.addEventListener('DOMContentLoaded', () => {
    window.artifactDisplayManager = new ArtifactDisplayManager();
});

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ArtifactDisplayManager;
}
