/**
 * Citation Processor - Unified Citation System (Single Source of Truth)
 *
 * Handles ALL citation rendering for both live responses and chat history.
 * Processes CitationInfo arrays into HTML anchors and citation panels.
 * Consolidates citation logic from rich-text-renderer.js and citation-processor.js
 */

class CitationProcessor {
    /**
     * 🎯 UNIFIED CITATION RENDERING - Main entry point for all citation rendering
     * @param {CitationInfo[]|string[]} citations - Citation data (objects or strings)
     * @param {string} displayMode - "Short" or "Full"
     * @param {Object} options - Additional rendering options
     * @returns {Promise<string>} HTML citation section
     */
    static async renderCitationsUnified(citations, displayMode = "Short", options = {}) {
        if (!citations || citations.length === 0) return '';

        // Handle both CitationInfo objects and string arrays (backward compatibility)
        const citationObjects = this.normalizeCitations(citations, options.enhancedMetadata);

        switch (displayMode) {
            case 'Full':
                return this.renderFullMode(citationObjects, options);
            case 'Short':
            default:
                return this.renderShortMode(citationObjects, options);
        }
    }

    /**
     * 🎯 SHORT MODE: Grouped citation panels (compact display)
     * @param {CitationInfo[]} citations - Normalized citation objects
     * @param {Object} options - Rendering options
     * @returns {string} HTML for short mode display
     */
    static renderShortMode(citations, options = {}) {
        if (!citations || citations.length === 0) return '';

        // Group citations by source document filename
        const fileGroups = {};
        let globalCounter = 1;

        citations.forEach(citation => {
            // Extract filename from citation title (format: "filename.pdf | page X | chunk Y")
            const filename = citation.title.split(' | ')[0] || 'Unknown';
            const fileType = this.getFileType(filename);
            const icon = this.getFileIcon(fileType);


            if (!fileGroups[filename]) {
                fileGroups[filename] = {
                    icon: icon,
                    type: fileType,
                    citations: []
                };
            }

            // Add citation to this file group
            fileGroups[filename].citations.push({
                id: citation.uuid,
                number: globalCounter++
            });
        });

        // Generate grouped citation panels
        const panels = Object.entries(fileGroups).map(([filename, data]) => {
            const citationLinks = data.citations.map(c =>
                `<a href="#" class="citation-link" data-citation-id="${c.id}">[${c.number}]</a>`
            ).join(' ');

            return `
                <div class="citation-panel-item">
                    <div class="citation-panel-left">
                        <span class="citation-file-icon">${data.icon}</span>
                        <span class="citation-filename">${this.escapeHtml(filename)}</span>
                        <span class="citation-filetype">(${data.type.toUpperCase()})</span>
                    </div>
                    <div class="citation-panel-right">
                        <span class="citation-links">${citationLinks}</span>
                    </div>
                </div>
            `;
        }).join('');

        const result = `<div class="citations-section citation-panels">
            <h4 class="section-title">📚 Sources</h4>
            <div class="citation-panels-container">${panels}</div>
        </div>`;

        return result;
    }

    /**
     * 🎯 FULL MODE: Detailed citation information with previews
     * @param {CitationInfo[]} citations - Normalized citation objects
     * @param {Object} options - Rendering options
     * @returns {string} HTML for full mode display
     */
    static renderFullMode(citations, options = {}) {
        const sourceItems = citations.map((citation, index) => {
            const citationId = citation.uuid;
            const displayNumber = index + 1;

            // Extract metadata for display
            const metadata = citation.metadata || {};
            const page = metadata.page_num || metadata.page || 'N/A';
            const size = metadata.size ? this.formatSize(metadata.size) : 'Unknown';
            const preview = citation.content_preview ?
                `"${citation.content_preview.substring(0, 50)}..."` :
                'No preview available';

            // Get file info
            const filename = citation.title.split(' | ')[0] || 'Unknown';
            const fileType = this.getFileType(filename);
            const icon = this.getFileIcon(fileType);

            return `
                <div class="source-item-full">
                    <div class="source-header">
                        ${icon} ${this.escapeHtml(filename)} (${fileType.toUpperCase()})
                    </div>
                    <div class="source-details">
                        Page: ${page}, Size: ${size}<br>
                        Preview: ${this.escapeHtml(preview)}<br>
                        <a href="#" class="citation-link" data-citation-id="${citationId}">🔗 [${displayNumber}]</a>
                    </div>
                </div>
            `;
        }).join('');

        return `<div class="citations-section citations-full">
            <h4 class="section-title">📚 Detailed Sources</h4>
            ${sourceItems}
        </div>`;
    }

    /**
     * 🎯 NORMALIZE CITATIONS: Convert string arrays to CitationInfo objects using available metadata
     * @param {CitationInfo[]|string[]} citations - Raw citation data
     * @param {Object} enhancedMetadata - Enhanced metadata containing citation metadata
     * @returns {CitationInfo[]} Normalized citation objects
     */
    static normalizeCitations(citations, enhancedMetadata = {}) {
        if (!citations?.length) {
            return [];
        }

        // If already CitationInfo objects, return as-is
        if (typeof citations[0] === 'object' && citations[0]?.uuid) {
            return citations;
        }

        // Convert string strings to objects
        const normalized = citations.map((citationStr, index) => {
            const match = citationStr.match(/\[citation:([^\]]+)\]/);
            const uuid = match ? match[1] : citationStr;

            // Try to find metadata for this UUID in the enhanced metadata
            let metadata = {};
            let title = `Source ${index + 1}`;
            let content_preview = '';

            // Check if citation_metadata field contains metadata for this UUID (preferred approach)
            if (enhancedMetadata.citation_metadata && typeof enhancedMetadata.citation_metadata === 'object' && enhancedMetadata.citation_metadata[uuid]) {
                const citationMeta = enhancedMetadata.citation_metadata[uuid];
                metadata = citationMeta;
                title = citationMeta.file_name || citationMeta.filename || `Source ${index + 1}`;
                content_preview = citationMeta.content_preview || citationMeta.content || citationMeta.text || '';
            } else {
                // Fallback: Check if citations array contains objects with metadata (legacy support)
                if (enhancedMetadata.citations && Array.isArray(enhancedMetadata.citations) &&
                    enhancedMetadata.citations.length > 0 && typeof enhancedMetadata.citations[0] === 'object') {
                    const citationMeta = enhancedMetadata.citations.find(citation =>
                        (citation.uuid === uuid || citation.id === uuid) && citation.metadata
                    );
                    if (citationMeta) {
                        metadata = citationMeta.metadata;
                        title = metadata.file_name || metadata.source || citationMeta.title || `Source ${index + 1}`;
                        content_preview = citationMeta.content_preview || citationMeta.text || '';
                    }
                }
            }

            return {
                uuid: uuid,
                title: title,
                content_preview: content_preview,
                metadata: metadata,
                number: index + 1
            };
        });

        return normalized;
    }

    /**
     * 🎯 LEGACY METHODS: Keep for backward compatibility
     * Render citations in text content (converts [1], [2] markers to HTML anchors)
     * @param {string} text - Text content with citation markers
     * @param {CitationInfo[]} citations - Citation data array
     * @returns {string} HTML with rendered citation links
     */
    static renderCitations(text, citations) {
        if (!text || !citations?.length) return text;

        // If text already contains HTML anchors, return as-is
        if (text.includes('<a href="javascript:window.richTextRenderer.openCitationPopup')) {
            return text;
        }

        // Convert [1], [2] markers to HTML anchors
        return text.replace(/\[(\d+)\]/g, (match, num) => {
            const citation = citations.find(c => c.number === parseInt(num));
            if (!citation) return match;

            const workflow = window.globalState?.currentWorkflow;
            const url = `javascript:window.richTextRenderer.openCitationPopup('${citation.uuid}');`;

            return `<a href="${url}" class="citation-link" data-citation-id="${citation.uuid}" title="${citation.title}">[${num}]</a>`;
        });
    }

    /**
     * LEGACY: Render citation panel based on display mode
     * @param {CitationInfo[]} citations - Citation data array
     * @param {string} displayMode - "None", "Short", or "Full"
     * @returns {string} HTML citation panel
     */
    static renderCitationPanel(citations, displayMode) {
        if (!citations?.length || displayMode === 'None') return '';

        switch (displayMode) {
            case 'Short':
                return this.renderShortForm(citations);
            case 'Full':
                return this.renderFullForm(citations);
            default:
                return this.renderShortForm(citations);
        }
    }

    /**
     * LEGACY: Render short form citation panel
     * @param {CitationInfo[]} citations - Citation data
     * @returns {string} Short form HTML
     */
    static renderShortForm(citations) {
        // Group citations by source file
        const fileGroups = {};

        citations.forEach(citation => {
            const source = citation.metadata?.source || 'Unknown';
            const fileType = this.getFileType(source);
            const icon = this.getFileIcon(fileType);

            if (!fileGroups[source]) {
                fileGroups[source] = {
                    icon: icon,
                    type: fileType,
                    citations: []
                };
            }
            fileGroups[source].citations.push(citation.number);
        });

        const panels = Object.entries(fileGroups).map(([filename, data]) => {
            const anchors = data.citations.map(num => `[${num}]`).join(' ');
            return `${data.icon} ${filename} (${data.type.toUpperCase()}) | 🔗 ${anchors}`;
        });

        return `<div class="citation-panel short-form">${panels.join('<br>')}</div>`;
    }

    /**
     * LEGACY: Render full form citation panel
     * @param {CitationInfo[]} citations - Citation data
     * @returns {string} Full form HTML
     */
    static renderFullForm(citations) {
        const panels = citations.map(citation => {
            const source = citation.metadata?.source || 'Unknown';
            const fileType = this.getFileType(source);
            const icon = this.getFileIcon(fileType);
            const size = citation.metadata?.size ? this.formatSize(citation.metadata.size) : 'Unknown';

            return `
                <div class="citation-item full-form">
                    <div class="citation-header">
                        ${icon} ${source} (${fileType.toUpperCase()})
                    </div>
                    <div class="citation-details">
                        Page: ${citation.metadata?.page || 'N/A'},
                        Size: ${size}
                    </div>
                    <div class="citation-preview">
                        ${citation.content_preview}
                    </div>
                    <div class="citation-link">
                        🔗 [${citation.number}]
                    </div>
                </div>
            `;
        });

        return `<div class="citation-panel full-form">${panels.join('')}</div>`;
    }

    /**
     * Get file type from filename
     * @param {string} filename - Source filename
     * @returns {string} File type (pdf, doc, txt, etc.)
     */
    static getFileType(filename) {
        if (!filename || typeof filename !== 'string') return 'unknown';

        const ext = filename.split('.').pop().toLowerCase();
        const typeMap = {
            'pdf': 'pdf',
            'doc': 'word',
            'docx': 'word',
            'txt': 'text',
            'md': 'markdown',
            'html': 'html',
            'htm': 'html',
            'json': 'json',
            'xml': 'xml'
        };

        return typeMap[ext] || 'unknown';
    }

    /**
     * Get file icon emoji for file type
     * @param {string} fileType - File type from getFileType()
     * @returns {string} Emoji icon
     */
    static getFileIcon(fileType) {
        const iconMap = {
            'pdf': '📄',
            'word': '📝',
            'text': '📄',
            'markdown': '📝',
            'html': '🌐',
            'json': '📋',
            'xml': '📋',
            'unknown': '📄'
        };

        return iconMap[fileType] || '📄';
    }

    /**
     * Format file size in human-readable format
     * @param {number} bytes - File size in bytes
     * @returns {string} Formatted size (e.g., "1.2KB")
     */
    static formatSize(bytes) {
        if (!bytes || bytes === 0) return '0B';

        const units = ['B', 'KB', 'MB', 'GB'];
        const k = 1024;
        const i = Math.floor(Math.log(bytes) / Math.log(k));

        return `${(bytes / Math.pow(k, i)).toFixed(1)}${units[i]}`;
    }

    /**
     * Escape HTML entities for safe rendering
     * @param {string} text - Text to escape
     * @returns {string} HTML-escaped text
     */
    static escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CitationProcessor;
}

// Global instance for easy access
window.CitationProcessor = CitationProcessor;
