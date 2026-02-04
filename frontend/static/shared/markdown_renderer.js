/**
 * Markdown Unification Engine - Phase 2.5
 *
 * Unified markdown processing engine that leverages community-proven frameworks
 * while integrating custom citation processing for the Super Starter Suite.
 *
 * Architecture:
 * ├── marked.js (core markdown processing)
 * ├── CitationPreprocessor (converts [citation:uuid] → markdown links)
 * ├── CustomRenderer (handles citation links, code blocks, tables)
 * └── FallbackProcessor (basic markdown when marked.js unavailable)
 */

class MarkdownUnificationEngine {
    constructor() {
        this.marked = null;
        this.isInitialized = false;
        this.citationCounter = 0;
        this.citationMap = new Map(); // Track citation UUIDs to numbers
    }

    /**
     * Initialize the markdown unification engine
     * @returns {Promise<boolean>} Success status
     */
    async initialize() {
        if (this.isInitialized) {
            return true;
        }

        try {
            // Try to load marked.js from CDN
            if (!window.marked) {
                await this.loadMarkedJS();
            }

            if (window.marked) {
                this.marked = window.marked;
                this.configureMarked();
            } else {
                console.warn('[MarkdownUnificationEngine] marked.js not available, using fallback');
            }

            this.isInitialized = true;
            return true;

        } catch (error) {
            console.error('[MarkdownUnificationEngine] Initialization failed:', error);
            this.isInitialized = false;
            return false;
        }
    }

    /**
     * Load marked.js from CDN
     * @returns {Promise<void>}
     */
    async loadMarkedJS() {
        return new Promise((resolve, reject) => {
            // Check if already loaded
            if (window.marked) {
                resolve();
                return;
            }

            // Load marked.js from CDN
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/marked@12.0.0/lib/marked.umd.js';
            script.onload = () => {
                resolve();
            };
            script.onerror = (error) => {
                console.warn('[MarkdownUnificationEngine] Failed to load marked.js from CDN:', error);
                reject(error);
            };

            document.head.appendChild(script);
        });
    }

    /**
     * Configure marked.js with custom renderers and options
     */
    configureMarked() {
        if (!this.marked) return;

        // Configure marked options
        this.marked.setOptions({
            breaks: true,        // Convert \n to <br>
            gfm: true,          // GitHub Flavored Markdown
            headerIds: true,    // Add IDs to headers
            mangle: false,      // Don't mangle email addresses
        });

        // Create custom renderer for citations and enhanced elements
        const renderer = new this.marked.Renderer();

        // Custom link renderer for citations
        renderer.link = (href, title, text) => {
            // Handle citation links specially
            if (href && href.includes('/citations/') && href.includes('/view')) {
                const citationId = href.split('/citations/')[1].split('/view')[0];
                return `<a href="${href}" class="citation-link" data-citation-id="${citationId}" title="${title || 'View source document'}">${text}</a>`;
            }

            // Regular links
            const titleAttr = title ? ` title="${title}"` : '';
            return `<a href="${href}"${titleAttr} target="_blank" rel="noopener noreferrer">${text}</a>`;
        };

        // Enhanced code block renderer with syntax highlighting
        renderer.code = (code, language, escaped) => {
            const validLang = language && language.trim() ? language.trim() : 'text';
            const highlightedCode = this.highlightCode(code, validLang);

            return `<div class="code-block-container">
                <pre class="code-block language-${validLang}"><code>${highlightedCode}</code></pre>
                <button class="copy-button" onclick="this.copyCode()" title="Copy to clipboard">📋</button>
            </div>`;
        };

        // Enhanced table renderer
        renderer.table = (header, body) => {
            return `<div class="markdown-table-container">
                <table class="markdown-table">
                    <thead>${header}</thead>
                    <tbody>${body}</tbody>
                </table>
            </div>`;
        };

        // Set the custom renderer
        this.marked.use({ renderer });
    }

    /**
     * Main processing method - converts markdown to HTML
     * @param {string} markdown - Raw markdown text
     * @param {Object} metadata - Message metadata for enhanced processing
     * @returns {Promise<string>} Processed HTML
     */
    async processMarkdown(markdown, metadata = {}) {
        if (!this.isInitialized) {
            await this.initialize();
        }

        if (!markdown || typeof markdown !== 'string') {
            return '';
        }

        try {
            // Phase 1: Preprocess citations
            const citationProcessed = this.preprocessCitations(markdown, metadata);

            // Phase 2: Process with marked.js or fallback
            let html;
            if (this.marked) {
                html = this.marked.parse(citationProcessed);
            } else {
                html = this.fallbackMarkdownProcessor(citationProcessed);
            }

            // Phase 3: Post-process for any additional enhancements
            html = this.postProcessHTML(html, metadata);
            return html;

        } catch (error) {
            console.error('[MarkdownUnificationEngine] Processing failed:', error);
            return this.escapeHtml(markdown); // Return escaped text as fallback
        }
    }

    /**
     * Preprocess citations: Convert [citation:uuid] to markdown links
     * @param {string} text - Text containing citation markers
     * @param {Object} metadata - Message metadata
     * @returns {string} Text with citations converted to markdown links
     */
    preprocessCitations(text, metadata) {
        if (!text) return text;

        // Reset citation counter for each message to ensure proper numbering in chat history
        this.citationCounter = 0;
        this.citationMap.clear();

        // Get citations from metadata - handle both current and historical message formats
        let citations = [];

        if (metadata?.enhanced_metadata?.citations) {
            // Current format: citations in enhanced_metadata
            citations = metadata.enhanced_metadata.citations;
        } else if (metadata?.citations) {
            // Legacy format: citations directly in metadata
            citations = metadata.citations;
        }

        // PHASE 5: Handle messages without citation metadata gracefully
        if (!citations || !Array.isArray(citations) || citations.length === 0) {
            console.log('[MarkdownUnificationEngine] No citations found in metadata or not an array, skipping citation preprocessing');
            return text;
        }

        // Create lookup map for citations
        const citationLookup = {};
        citations.forEach(citation => {
            if (citation && typeof citation === 'object' && citation.uuid) {
                citationLookup[citation.uuid] = citation;
            }
        });

        // Replace [citation:uuid] with numbered markdown links
        const processed = text.replace(/\[citation:([^\]]+)\]/g, (match, citationId) => {
            this.citationCounter++;

            const citation = citationLookup[citationId];
            const displayText = citation ? `[${this.citationCounter}]` : `[${this.citationCounter}]`;

            // Create markdown link to citation viewer
            const workflow = window.globalState?.currentWorkflow;
            const viewUrl = workflow ? `/api/workflow/${workflow}/citations/${citationId}/view` : '#';

            return `[${displayText}](${viewUrl} "${citation?.title || 'View source document'}")`;
        });
        return processed;
    }

    /**
     * Post-process HTML for additional enhancements
     * @param {string} html - Processed HTML
     * @param {Object} metadata - Message metadata
     * @returns {string} Enhanced HTML
     */
    postProcessHTML(html, metadata) {
        // Add any additional processing here
        // For now, just return the HTML as-is
        return html;
    }

    /**
     * Fallback markdown processor when marked.js is not available
     * @param {string} markdown - Markdown text
     * @returns {string} Basic HTML
     */
    fallbackMarkdownProcessor(markdown) {
        console.log('[MarkdownUnificationEngine] Using fallback markdown processor');

        let html = markdown;

        // 1. Handle Code blocks FIRST to prevent them from being processed by other rules
        html = html.replace(/```(\w+)?\s*([\s\S]*?)```/g, (match, lang, code) => {
            const highlightedCode = this.highlightCode(code.trim(), lang || 'text');
            return `<div class="code-block-container">
                <pre class="code-block"><code>${highlightedCode}</code></pre>
                <button class="copy-button" onclick="this.copyCode()" title="Copy to clipboard">📋</button>
            </div>`;
        });

        // 2. Inline code
        html = html.replace(/`([^`\n]+)`/g, '<code class="inline-code">$1</code>');

        // 3. Bold and italic
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');

        // 4. Headers (multiline)
        html = html.replace(/^### (.*$)/gm, '<h3>$1</h3>');
        html = html.replace(/^## (.*$)/gm, '<h2>$1</h2>');
        html = html.replace(/^# (.*$)/gm, '<h1>$1</h1>');

        // 5. Images
        html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width: 100%; border-radius: 8px; margin: 10px 0;">');

        // 6. Links
        html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');

        // 7. Lists
        html = html.replace(/^\* (.*$)/gm, '<li>$1</li>');
        html = html.replace(/^\d+\. (.*$)/gm, '<li>$1</li>');

        // 8. Convert remaining newlines to <br> EXCEPT inside tags
        // This is a crude approximation
        html = html.replace(/\n/g, '<br>');

        return html;
    }

    /**
     * Basic syntax highlighting for code
     * @param {string} code - Code text
     * @param {string} language - Programming language
     * @returns {string} Highlighted HTML
     */
    highlightCode(code, language) {
        if (!language || language.toLowerCase() === 'text') {
            return this.escapeHtml(code);
        }

        // Use Prism.js if available
        if (window.Prism && window.Prism.highlight) {
            try {
                return window.Prism.highlight(code, window.Prism.languages[language] || window.Prism.languages.text, language);
            } catch (error) {
                console.warn('[MarkdownUnificationEngine] Prism.js highlighting failed:', error);
            }
        }

        // Fallback: Basic keyword highlighting
        let highlighted = this.escapeHtml(code);

        // Basic keyword highlighting for common languages
        const keywords = {
            'javascript': ['function', 'const', 'let', 'var', 'if', 'else', 'for', 'while', 'class', 'async', 'await', 'return'],
            'python': ['def', 'class', 'if', 'else', 'elif', 'for', 'while', 'try', 'except', 'import', 'from', 'return'],
            'java': ['public', 'private', 'class', 'if', 'else', 'for', 'while', 'try', 'catch', 'import', 'return'],
            'cpp': ['#include', 'int', 'void', 'class', 'if', 'else', 'for', 'while', 'try', 'catch', 'return']
        };

        const langKeywords = keywords[language.toLowerCase()] || [];
        if (langKeywords.length > 0) {
            const keywordRegex = new RegExp(`\\b(${langKeywords.join('|')})\\b`, 'g');
            highlighted = highlighted.replace(keywordRegex, '<span class="keyword">$1</span>');
        }

        // Basic string highlighting
        highlighted = highlighted.replace(/(["'`])(.*?)\1/g, '<span class="string">$&</span>');

        return highlighted;
    }

    /**
     * Escape HTML entities
     * @param {string} text - Text to escape
     * @returns {string} HTML-escaped text
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Get citation information for current message
     * @returns {Object} Citation counter and map
     */
    getCitationInfo() {
        return {
            counter: this.citationCounter,
            map: this.citationMap
        };
    }

    /**
     * Reset citation counter for new message
     */
    resetCitations() {
        this.citationCounter = 0;
        this.citationMap.clear();
    }
}

// Global instance
window.markdownUnificationEngine = new MarkdownUnificationEngine();

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', async () => {
    await window.markdownUnificationEngine.initialize();
});

