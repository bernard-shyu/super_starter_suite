/**
 * Rich Text Renderer - Phase 5.8 Chat Enhancement
 * Converts plain text chat messages to styled HTML with markdown support
 * Provides basic syntax highlighting for code blocks
 */

/**
 * RichTextRenderer - Converts markdown-style text to styled HTML
 */
class RichTextRenderer {
    constructor() {
        this.codeBlockRegex = /```(\w+)?\s*([\s\S]*?)```/g;
        this.inlineCodeRegex = /`([^`\n]+)`/g;
        this.boldRegex = /\*\*([^*\n]+)\*\*/g;
        this.italicRegex = /\*([^*\n]+)\*/g;
        this.markdownLinkRegex = /\[([^\]]+)\]\(([^)]+)\)/g;  // [text](url) pattern
        this.tableRegex = /^\|.*\|\s*$/gm;  // Markdown table detection
        this.urlRegex = /(https?:\/\/[^\s]+)/g;
        this.citationCounter = 0;  // Global citation counter
    }

    /**
     * 🎯 INTEGRATED RENDER MESSAGE - Uses Markdown Unification Engine
     * @param {string} content - Raw message text from ExecutionResult.response_content
     * @param {Object} metadata - Message metadata containing ExecutionResult.rendering_instructions
     * @returns {string} HTML-formatted content
     */
    async renderMessage(content, metadata = {}) {
        try {
            // IMMEDIATE SAFETY CHECKS
            if (!content || typeof content !== 'string') {
                return '';
            }

            // SAFETY: Limit content size to prevent memory exhaustion
            if (content.length > 50000) {
                console.warn('⚠️ RichTextRenderer: Content too large, truncating');
                content = content.substring(0, 50000) + '\n\n[Content truncated due to size]...';
            }

            // 🎯 USE MARKDOWN UNIFICATION ENGINE FOR ALL TEXT PROCESSING
            let html = '';

            if (window.markdownUnificationEngine) {
                // Use the unified markdown processing engine
                html = await window.markdownUnificationEngine.processMarkdown(content, metadata);
            } else {
                // Fallback if engine not available
                console.warn('⚠️ RichTextRenderer: Markdown unification engine not available, using fallback');
                html = this.fallbackRenderMessage(content, metadata);
            }

            // 🎯 APPENDIX CITATIONS: Show citations section based on show_citation configuration
            const enhancedMetadata = metadata?.enhanced_metadata;
            if (enhancedMetadata?.citations?.length > 0) {
                // Use stored configuration from message history, fallback to current workflow config
                const showCitation = enhancedMetadata.show_citation ||
                    (window.workflowUIConfigs?.[window.globalState?.currentWorkflow]?.show_citation) ||
                    "Short";

                if (showCitation !== "None") {
                    // Check if citations field contains CitationInfo objects
                    let citationObjects = enhancedMetadata.citations;
                    if (enhancedMetadata.citations && Array.isArray(enhancedMetadata.citations) &&
                        enhancedMetadata.citations.length > 0 && typeof enhancedMetadata.citations[0] === 'object') {
                        citationObjects = enhancedMetadata.citations;
                    }

                    // 🎯 USE UNIFIED CITATION PROCESSOR - Single Source of Truth
                    const citationsHtml = await window.CitationProcessor.renderCitationsUnified(citationObjects, showCitation, { enhancedMetadata });
                    html += '<br>' + citationsHtml;
                }
            }

            // 🎯 TOOL CALLS: Show tool calls section based on show_tool_calls configuration
            const showToolCalls = enhancedMetadata?.show_tool_calls ??
                (window.workflowUIConfigs?.[window.globalState?.currentWorkflow]?.show_tool_calls) ??
                true;
            if (enhancedMetadata?.tool_calls?.length > 0 && showToolCalls !== false) {
                const toolCallsHtml = this.renderUnifiedToolCalls(enhancedMetadata.tool_calls);
                html += '<br>' + toolCallsHtml;
            }

            // 🎯 FOLLOW-UP QUESTIONS: Show questions section based on show_followup_questions configuration
            const showFollowupQuestions = enhancedMetadata?.show_followup_questions ??
                (window.workflowUIConfigs?.[window.globalState?.currentWorkflow]?.show_followup_questions) ??
                true;
            if (enhancedMetadata?.followup_questions?.length > 0 && showFollowupQuestions !== false) {
                const questionsHtml = this.renderUnifiedFollowUpQuestions(enhancedMetadata.followup_questions);
                html += '<br>' + questionsHtml;
            }

            // 🎯 WORKFLOW STATES: Show progress states based on show_workflow_states configuration
            const showWorkflowStates = enhancedMetadata?.show_workflow_states ??
                (window.workflowUIConfigs?.[window.globalState?.currentWorkflow]?.show_workflow_states) ??
                true;
            if (enhancedMetadata?.progress_states?.length > 0 && showWorkflowStates !== false) {
                const progressHtml = this.renderUnifiedProgressStates(enhancedMetadata.progress_states);
                html += '<br>' + progressHtml;
            }

            // 🎯 ARTIFACT PROCESSING: Handle artifacts via ArtifactDisplayManager (controlled by artifacts_enabled)
            const artifactsEnabled = enhancedMetadata?.artifacts_enabled ??
                (window.workflowUIConfigs?.[window.globalState?.currentWorkflow]?.artifacts_enabled) ??
                true;
            if (enhancedMetadata?.artifacts?.length > 0 && artifactsEnabled !== false) {
                this.renderUnifiedArtifacts(enhancedMetadata.artifacts);
            }

            return html;

        } catch (error) {
            console.error('❌ RichTextRenderer CRASH:', error);
            return content || '[Rendering failed]';
        }
    }

    /**
     * Fallback rendering when markdown unification engine is not available
     * @param {string} content - Raw content
     * @param {Object} metadata - Metadata
     * @returns {string} HTML
     */
    fallbackRenderMessage(content, metadata = {}) {
        let html = content;

        // Basic processing without unified engine
        // 1. Headers
        html = html.replace(/^### (.*$)/gm, '<h3>$1</h3>');
        html = html.replace(/^## (.*$)/gm, '<h2>$1</h2>');
        html = html.replace(/^# (.*$)/gm, '<h1>$1</h1>');

        // 2. Bold and italic
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');

        // 3. Images and links
        html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width: 100%; border-radius: 8px;">');
        html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');

        // 4. Inline code
        html = html.replace(/`([^`\n]+)`/g, '<code class="inline-code">$1</code>');

        // 5. Newlines
        html = html.replace(/\n/g, '<br>');

        return html;
    }

    /**
     * Render code blocks with syntax highlighting
     * @param {string} text - Text containing code blocks
     * @returns {string} HTML with highlighted code blocks
     */
    renderCodeBlocks(text) {
        return text.replace(this.codeBlockRegex, (match, language, code) => {
            const highlightedCode = this.highlightCode(code.trim(), language);
            const langClass = language ? ` class="language-${language}"` : '';
            return `<div class="code-block-container">
                <pre class="code-block${langClass}"><code>${highlightedCode}</code></pre>
                <button class="copy-button" onclick="this.copyCode()" title="Copy to clipboard">📋</button>
            </div>`;
        });
    }

    /**
     * Render inline markdown elements
     * @param {string} text - Text containing inline markdown
     * @returns {string} HTML with inline styling
     */
    renderInlineElements(text) {
        // Bold text
        text = text.replace(this.boldRegex, '<strong>$1</strong>');

        // Italic text
        text = text.replace(this.italicRegex, '<em>$1</em>');

        // Inline code
        text = text.replace(this.inlineCodeRegex, '<code class="inline-code">$1</code>');

        return text;
    }

    /**
     * Render markdown links [text](url) as HTML anchor tags
     * @param {string} text - Text containing markdown links
     * @returns {string} HTML with markdown links converted to anchor tags
     */
    renderMarkdownLinks(text) {
        return text.replace(this.markdownLinkRegex, (match, text, url) => {
            // Escape the text content to prevent HTML injection
            const escapedText = text;

            // Special handling for citation links - use popup windows instead of new tabs
            if (url.includes('/citations/') && url.includes('/view')) {
                // Citation links: Use data-citation-id for global listener (removes onclick duplication)
                const citationId = url.split('/citations/')[1].split('/view')[0];
                return `<a href="${url}" data-citation-id="${citationId}" class="citation-link">${escapedText}</a>`;
            } else {
                // Regular markdown links: Open in new tab
                return `<a href="${url}" class="markdown-link" target="_blank" rel="noopener noreferrer">${escapedText}</a>`;
            }
        });
    }

    /**
     * Auto-link URLs in text
     * @param {string} text - Text containing URLs
     * @returns {string} HTML with linked URLs
     */
    autoLinkUrls(text) {
        return text.replace(this.urlRegex, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');
    }

    /**
     * Apply enhanced rendering based on workflow metadata from backend
     * @param {string} originalHtml - Current HTML content
     * @param {string} originalContent - Original text content
     * @param {Object} metadata - Message metadata with enhanced_metadata
     * @returns {string} Enhanced HTML
     */
    applyEnhancedRendering(originalHtml, originalContent, metadata) {
        let enhancedHtml = originalHtml;
        const features = [];

        // DIRECTLY USE BACKEND-PROVIDED METADATA INSTEAD OF EXTRACTION
        const enhancedMeta = metadata.enhanced_metadata || {};

        // 🎯 TOOL CALLS: Use backend-provided tool_calls array
        if (enhancedMeta.tool_calls && enhancedMeta.tool_calls.length > 0) {
            features.push(this.renderToolCalls(enhancedMeta.tool_calls));
        }

        // 📚 SOURCES: Use backend-provided citations array
        if (enhancedMeta.citations && enhancedMeta.citations.length > 0) {
            features.push(this.renderSources(enhancedMeta.citations));
        }

        // 💭 FOLLOW-UP QUESTIONS: Use backend-provided questions array
        if (enhancedMeta.followup_questions && enhancedMeta.followup_questions.length > 0) {
            features.push(this.renderFollowUpQuestions(enhancedMeta.followup_questions));
        }

        // Combine main content with enhanced features
        if (features.length > 0) {
            enhancedHtml += '<br>' + features.join('<br>');
        }

        return enhancedHtml;
    }

    /**
     * 🎯 DIRECT NUMBERED LINKS: Convert citations to direct numbered links [1], [2]
     * @param {string} content - Text content to process
     * @param {Array} citations - Citation data from backend
     * @returns {string} Content with citations as direct numbered links
     */
    applyUnifiedCitationProcessing(content, citations) {
        if (!content) return content;

        let processedContent = content;
        // Process citation markers: [citation:uuid] → <a href="/citations/uuid">[1]</a>
        const citationRegex = /\[citation:([^\]]+)\]/g;
        let counter = 0;

        processedContent = processedContent.replace(citationRegex, (match, citationId) => {
            counter++;
            const workflow = window.globalState?.currentWorkflow;
            const viewUrl = workflow ? `/api/workflow/${workflow}/citations/${citationId}/view` : '#';
            const numberedLink = `<a href="${viewUrl}" class="citation-link" data-citation-id="${citationId}" title="View source document">[${counter}]</a>`;
            return numberedLink;
        });

        return processedContent;
    }

    /**
     * 🎯 UNIFIED ENHANCED RENDERING: Use rendering_instructions from ExecutionResult
     * @param {string} originalHtml - Current HTML content
     * @param {string} originalContent - Original text content
     * @param {Object} renderingInstructions - From ExecutionResult.rendering_instructions
     * @returns {string} Enhanced HTML using backend rendering instructions
     */
    applyUnifiedEnhancedRendering(originalHtml, originalContent, renderingInstructions) {
        let enhancedHtml = originalHtml;
        const features = [];

        // 🎯 TOOL CALLS: Use rendering_instructions to decide what to show
        if (renderingInstructions.show_tool_calls && renderingInstructions.tool_calls?.length > 0) {
            features.push(this.renderUnifiedToolCalls(renderingInstructions.tool_calls));
        }

        // 📚 CITATIONS: Use unified CitationProcessor for citation rendering
        if (renderingInstructions.show_citation && renderingInstructions.show_citation !== "None" && renderingInstructions.citations?.length > 0) {
            const citationsHtml = window.CitationProcessor.renderCitationsUnified(renderingInstructions.citations, renderingInstructions.show_citation);
            features.push(citationsHtml);
        }

        // 💭 FOLLOW-UP QUESTIONS: Use rendering_instructions
        if (renderingInstructions.show_followup_questions && renderingInstructions.followup_questions?.length > 0) {
            features.push(this.renderUnifiedFollowUpQuestions(renderingInstructions.followup_questions));
        }

        // WORKFLOW PROGRESS STATES: Use rendering_instructions
        if (renderingInstructions.show_workflow_states && renderingInstructions.progress_states?.length > 0) {
            features.push(this.renderUnifiedProgressStates(renderingInstructions.progress_states));
        }

        // ARTIFACT RENDERING: Use rendering_instructions for artifact display
        if (renderingInstructions.artifacts?.length > 0) {
            features.push(this.renderUnifiedArtifacts(renderingInstructions.artifacts));
        }

        // Combine main content with enhanced features
        if (features.length > 0) {
            enhancedHtml += '<br>' + features.join('<br>');
        }

        return enhancedHtml;
    }

    /**
     * 🎯 Render tool calls from rendering_instructions
     * @param {Array} toolCalls - Tool call data from backend
     * @returns {string} HTML representation
     */
    renderUnifiedToolCalls(toolCalls) {
        if (!toolCalls?.length) return '';

        const toolItems = toolCalls.map(call =>
            `<li class="tool-call-item">${this.escapeHtml(call)}</li>`
        ).join('');
        return `<div class="tool-calls-section">
            <h4 class="section-title">🔧 Tool Calls</h4>
            <ul class="tool-calls-list">${toolItems}</ul>
        </div>`;
    }



    /**
     * 🎯 Render follow-up questions using unified rendering_instructions
     * @param {Array} questions - Question data from backend
     * @returns {string} HTML representation
     */
    renderUnifiedFollowUpQuestions(questions) {
        if (!questions?.length) return '';

        const questionItems = questions.map(q =>
            `<li class="followup-question">${this.escapeHtml(q)}</li>`
        ).join('');
        return `<div class="followup-questions-section">
            <h4 class="section-title">💭 Suggested Follow-up Questions</h4>
            <ul class="followup-questions-list">${questionItems}</ul>
        </div>`;
    }

    /**
     * 🎯 Render workflow progress states using rendering_instructions
     * @param {Array} progressStates - Progress state data from backend
     * @returns {string} HTML representation
     */
    renderUnifiedProgressStates(progressStates) {
        if (!progressStates?.length) return '';

        const progressItems = progressStates.map(state =>
            `<div class="progress-state-item">${this.escapeHtml(state || 'Processing...')}</div>`
        ).join('');

        return `<div class="progress-states-section">
            <h4 class="section-title">⚡ Progress</h4>
            <div class="progress-states-list">${progressItems}</div>
        </div>`;
    }

    /**
     * 🎯 Render artifacts using rendering_instructions - REMOVED INLINE DISPLAY
     * Artifacts are now handled exclusively by ArtifactDisplayManager for dedicated viewing
     * @param {Array} artifacts - Artifact data from backend
     * @returns {string} Empty string (artifacts displayed separately)
     */
    renderUnifiedArtifacts(artifacts) {
        // Notify ArtifactDisplayManager about available artifacts (if global instance exists)
        if (window.artifactDisplayManager && artifacts?.length > 0) {
            // Clean up artifacts for proper display
            const cleanedArtifacts = artifacts.map(artifact => ({
                type: artifact.type || 'code',
                language: artifact.language || 'text',
                code: artifact.code || artifact.content || '',
                filename: artifact.filename || artifact.file_name,
                title: artifact.title || artifact.name || `Generated ${artifact.type || 'code'}`,
                data: artifact.data || artifact.content || ''
            }));
            window.artifactDisplayManager.displayArtifacts(cleanedArtifacts);
        }

        return ''; // No inline display - artifacts shown separately
    }

    /**
     * ⚠️ LEGACY METHOD: Keep for backward compatibility
     * Apply citation processing to content before other markdown processing
     * Replaces [citation:uuid] with superscripted numbers [¹] in the text
     * @param {string} content - Text content to process
     * @param {Object} metadata - Message metadata containing citations
     * @returns {string} Content with citations converted to numbered references
     */
    applyCitationProcessing(content) {
        return this.applyUnifiedCitationProcessing(content, []); // Empty citations for backward compatibility
    }

    /**
     * Convert number to superscript
     * @param {number} num - Number to convert
     * @returns {string} Superscript representation
     */
    toSuperscript(num) {
        const superscriptMap = {
            '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
            '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹'
        };
        return '[' + num.toString().split('').map(digit => superscriptMap[digit]).join('') + ']';
    }

    /**
     * Render markdown tables - BASIC APPROACH
     * @param {string} text - Text containing potential markdown tables
     * @returns {string} HTML with markdown tables converted
     */
    renderMarkdownTables(text) {
        try {
            // Simple replacement of | separator notation with basic table structure
            // Look for consecutive lines that start and end with |
            const lines = text.split('\n');
            let result = [];
            let tableBuffer = [];
            let inTable = false;

            for (let i = 0; i < lines.length; i++) {
                const line = lines[i].trim();

                // Check if this is a table line (starts and ends with |)
                if (line.startsWith('|') && line.endsWith('|') && line.split('|').length >= 3) {
                    if (!inTable) {
                        // Start of a new table - add accumulated text
                        if (result.length > 0 && result.length > 0 && result[result.length - 1] !== '') {
                            result.pop(); // Remove any empty lines before table
                        }
                        inTable = true;
                    }
                    tableBuffer.push(line);
                } else {
                    // End of table sequence or regular line
                    if (inTable && tableBuffer.length >= 2) {
                        // Convert accumulated table lines to HTML
                        const tableHtml = this.parseTableLinesToHtml(tableBuffer);
                        result.push(tableHtml);
                        tableBuffer = [];
                        inTable = false;
                    } else if (tableBuffer.length > 0) {
                        // Single table line or malformed - output as regular text
                        result.push(...tableBuffer);
                        tableBuffer = [];
                        inTable = false;
                    }

                    result.push(line);
                }
            }

            // Handle table at end of text
            if (inTable && tableBuffer.length >= 2) {
                const tableHtml = this.parseTableLinesToHtml(tableBuffer);
                result.push(tableHtml);
            } else if (tableBuffer.length > 0) {
                result.push(...tableBuffer);
            }

            return result.join('\n');

        } catch (error) {
            console.error('🪑 TABLE: Error processing tables:', error);
            return text; // Return original if processing fails
        }
    }

    /**
     * Parse table lines into HTML table
     * @param {string[]} tableLines - Lines of markdown table
     * @returns {string} HTML table
     */
    parseTableLinesToHtml(tableLines) {
        if (tableLines.length < 2) return tableLines.join('\n');

        // Split into cells and clean up
        const rows = tableLines.map(line =>
            line.split('|')
                .slice(1, -1) // Remove first and last empty parts
                .map(cell => cell.trim())
                .filter(cell => cell !== '') // Remove empty cells
        );

        // Check for header separator line
        let hasHeader = false;
        if (tableLines.length >= 3) {
            const secondRow = tableLines[1].trim();
            hasHeader = secondRow.startsWith('|') && secondRow.endsWith('|') &&
                tableLines[1].split('|').slice(1, -1).some(cell =>
                    /^[-:\s]*-[-:\s]*$/.test(cell.trim())
                );
        }

        // Build HTML table
        let html = '<div class="markdown-table-container"><table class="markdown-table">';

        const startRow = hasHeader ? 1 : 0; // Skip second row if it's the separator

        for (let i = startRow; i < tableLines.length; i++) {
            if (hasHeader && i === 1) continue; // Skip separator line

            const cells = tableLines[i].split('|').slice(1, -1).map(cell => cell.trim());
            const tag = (hasHeader && i === startRow) ? 'th' : 'td';
            const cellHtml = cells.map(cell => `<${tag}>${this.escapeHtml(cell)}</${tag}>`).join('');

            if (hasHeader && i === startRow) {
                html += `<thead><tr>${cellHtml}</tr></thead>`;
            } else {
                html += `<tr>${cellHtml}</tr>`;
            }
        }


        html += '</table></div>';
        return html;
    }

    /**
     * Convert table lines to HTML table - NEW METHOD FOR MARKDOWN TABLES
     * @param {string[]} tableLines - Array of table lines (markdown format)
     * @returns {string} HTML table
     */
    convertMarkdownTableToHtml(tableLines) {
        // This method is kept for backwards compatibility but not used in simplified approach
        return this.parseTableLinesToHtml(tableLines);
    }

    /**
     * Convert table lines directly to HTML
     * @param {string[]} tableLines - Raw table lines
     * @returns {string} HTML table
     */
    convertLinesToTable(tableLines) {
        if (tableLines.length === 0) return '';

        let hasHeader = false;
        const headerRow = tableLines[0].split('|').slice(1, -1).map(cell => cell.trim());
        let bodyRows = [];

        // Check if second line is a separator
        if (tableLines.length > 1) {
            const secondRow = tableLines[1].split('|').slice(1, -1).map(cell => cell.trim());
            if (secondRow.every(cell => /^[-]+$/.test(cell))) {
                // Remove separator line
                tableLines.splice(1, 1);
                hasHeader = true;
            }
        }

        if (hasHeader && tableLines.length > 1) {
            bodyRows = tableLines.slice(1);
        } else {
            bodyRows = tableLines;
        }

        let tableHtml = '<div class="markdown-table-container"><table class="markdown-table">';

        // Add header if present
        if (hasHeader) {
            const headerCells = headerRow.map(cell => this.escapeHtml(cell)).join('');
            tableHtml += `<thead><tr><th>${headerCells}</th></tr></thead>`;
        }

        // Add body rows
        if (bodyRows.length > 0) {
            const rowsHtml = bodyRows.map(row => {
                const cells = row.split('|').slice(1, -1).map(cell => cell.trim());
                const cellHtml = cells.map(cell => this.escapeHtml(cell)).join('');
                return `<tr><td>${cellHtml}</td></tr>`;
            }).join('');
            tableHtml += `<tbody>${rowsHtml}</tbody>`;
        }

        tableHtml += '</table></div>';
        return tableHtml;
    }

    /**
     * Replace table lines in text with HTML
     * @param {string} originalText - Original markdown text
     * @param {string[]} htmlBlocks - HTML blocks to insert
     * @returns {string} Text with tables replaced
     */
    replaceTablesInText(originalText, htmlBlocks) {
        let result = originalText;
        let blockIndex = 0;

        // Simple approach: replace first occurrence of table pattern
        const tableLineRegex = /^[\s]*\|.*\|[\s]*$/gm;
        result = result.replace(tableLineRegex, (match, offset, string) => {
            if (blockIndex < htmlBlocks.length && htmlBlocks[blockIndex].includes('<table')) {
                const replacement = htmlBlocks[blockIndex++];
                return replacement;
            }
            return match;
        });

        // Clean up any remaining table lines if multiple tables
        while (blockIndex < htmlBlocks.length) {
            result = result.replace(tableLineRegex, (match) => {
                if (blockIndex < htmlBlocks.length && htmlBlocks[blockIndex].includes('<table')) {
                    return htmlBlocks[blockIndex++];
                }
                return match;
            });
        }

        return result;
    }

    /**
     * Check if line is a table separator (---|---|---)
     * @param {string} line - Line to check
     * @returns {boolean} True if table separator
     */
    isTableSeparator(line) {
        return /^\|[\s]*[-\s:]*[\s]*\|/.test(line) &&
            (!/\|[\s]*[^\-\s:].*[^\-\s:]/.test(line));
    }

    /**
     * Convert table lines to HTML table
     * @param {string[]} tableLines - Array of table lines
     * @returns {string} HTML table
     */
    convertTableToHtml(tableLines) {
        if (tableLines.length === 0) return '';

        const rows = [];
        let hasHeader = tableLines.length > 1 && this.isTableSeparator(tableLines[1]);

        for (let i = 0; i < tableLines.length; i++) {
            if (hasHeader && i === 1) continue; // Skip separator line

            const line = tableLines[i];
            const cells = line.split('|')
                .slice(1, -1) // Remove first and last empty elements
                .map(cell => cell.trim());

            const tag = (hasHeader && i === 0) ? 'th' : 'td';
            const cellHtml = cells.map(cell => `<${tag}>${this.escapeHtml(cell)}</${tag}>`).join('');

            if (i === 0 && hasHeader) {
                rows.push(`<thead><tr>${cellHtml}</tr></thead>`);
            } else {
                rows.push(`<tr>${cellHtml}</tr>`);
            }
        }

        const tbodyRows = rows.slice(hasHeader ? 1 : 0);
        const tbody = tbodyRows.length > 0 ? `<tbody>${tbodyRows.join('')}</tbody>` : '';

        return `<div class="markdown-table-container"><table class="markdown-table">${rows[0] || ''}${tbody}</table></div>`;
    }

    /**
     * Basic syntax highlighting for code
     * @param {string} code - Raw code text
     * @param {string} language - Programming language
     * @returns {string} Highlighted HTML code
     */
    highlightCode(code, language) {
        if (!language || language.toLowerCase() === 'text') {
            return this.escapeHtml(code);
        }

        // Basic highlighting for common languages
        const lowerLang = language.toLowerCase();
        let highlighted = this.escapeHtml(code);

        switch (lowerLang) {
            case 'javascript':
            case 'js':
                highlighted = this.highlightJavaScript(highlighted);
                break;
            case 'python':
            case 'py':
                highlighted = this.highlightPython(highlighted);
                break;
            case 'typescript':
            case 'ts':
                highlighted = this.highlightTypeScript(highlighted);
                break;
            case 'json':
                highlighted = this.highlightJSON(highlighted);
                break;
            default:
                // Default highlighting for keywords
                highlighted = this.highlightKeywords(highlighted, ['function', 'const', 'let', 'var', 'if', 'else', 'for', 'while', 'class', 'def', 'import', 'from']);
        }

        return highlighted;
    }

    /**
     * Highlight JavaScript/TypeScript code
     */
    highlightJavaScript(code) {
        let highlighted = code;

        // Keywords
        const jsKeywords = ['function', 'const', 'let', 'var', 'if', 'else', 'for', 'while', 'class', 'async', 'await', 'return', 'import', 'export', 'from', 'try', 'catch', 'finally'];
        highlighted = this.highlightKeywords(highlighted, jsKeywords);

        // Strings
        highlighted = highlighted.replace(/(["'`])(.*?)\1/g, '<span class="string">$&</span>');

        // Numbers
        highlighted = highlighted.replace(/\b(\d+(\.\d+)?)\b/g, '<span class="number">$1</span>');

        // Comments
        highlighted = highlighted.replace(/(\/\/.*$)/gm, '<span class="comment">$1</span>');
        highlighted = highlighted.replace(/(\/\*[\s\S]*?\*\/)/g, '<span class="comment">$1</span>');

        return highlighted;
    }

    /**
     * Highlight Python code
     */
    highlightPython(code) {
        let highlighted = code;

        // Keywords
        const pyKeywords = ['def', 'class', 'if', 'else', 'elif', 'for', 'while', 'try', 'except', 'finally', 'import', 'from', 'return', 'yield', 'async', 'await'];
        highlighted = this.highlightKeywords(highlighted, pyKeywords);

        // Strings
        highlighted = highlighted.replace(/(["'`])(.*?)\1/g, '<span class="string">$&</span>');

        // Numbers
        highlighted = highlighted.replace(/\b(\d+(\.\d+)?)\b/g, '<span class="number">$1</span>');

        // Comments
        highlighted = highlighted.replace(/(#.*$)/gm, '<span class="comment">$1</span>');

        return highlighted;
    }

    /**
     * Highlight TypeScript code (extends JS highlighting)
     */
    highlightTypeScript(code) {
        let highlighted = this.highlightJavaScript(code);

        // TypeScript-specific keywords
        const tsKeywords = ['interface', 'type', 'enum', 'private', 'public', 'protected', 'readonly', 'implements', 'extends'];
        highlighted = this.highlightKeywords(highlighted, tsKeywords);

        // Type annotations
        highlighted = highlighted.replace(/(: \w+(?:\[\])?)/g, '<span class="type">$1</span>');

        return highlighted;
    }

    /**
     * Highlight JSON
     */
    highlightJSON(code) {
        let highlighted = code;

        // Keys
        highlighted = highlighted.replace(/"([^"]+)":/g, '<span class="json-key">"$1"</span>:');

        // Strings
        highlighted = highlighted.replace(/: "([^"]+)"/g, ': <span class="string">"$1"</span>');

        // Numbers, booleans, null
        highlighted = highlighted.replace(/\b(true|false|null|\d+(\.\d+)?)\b/g, '<span class="json-value">$1</span>');

        return highlighted;
    }

    /**
     * Highlight keywords in code
     * @param {string} code - Code text
     * @param {string[]} keywords - Array of keywords to highlight
     * @returns {string} Highlighted code
     */
    highlightKeywords(code, keywords) {
        const keywordRegex = new RegExp(`\\b(${keywords.join('|')})\\b`, 'g');
        return code.replace(keywordRegex, '<span class="keyword">$1</span>');
    }

    /**
     * Extract tool calls from content
     * @param {string} content - Message content
     * @returns {string[]} Array of tool call strings
     */
    extractToolCalls(content) {
        const toolCalls = [];
        const lines = content.split('\n');

        for (const line of lines) {
            if (line.includes('Calling tool:')) {
                toolCalls.push(line.trim());
            }
        }

        return toolCalls;
    }



    /**
     * Extract follow-up questions from content
     * @param {string} content - Message content
     * @returns {string[]} Array of follow-up question strings
     */
    extractFollowUpQuestions(content) {
        const questions = [];
        const lines = content.split('\n');

        for (const line of lines) {
            if (line.trim().startsWith('-> ') || line.includes('?')) {
                questions.push(line.trim());
            }
        }

        return questions;
    }

    /**
     * Render tool calls as HTML
     * @param {string[]} toolCalls - Array of tool call strings
     * @returns {string} HTML representation
     */
    renderToolCalls(toolCalls) {
        if (!toolCalls.length) return '';

        const toolItems = toolCalls.map(call => `<li class="tool-call-item">${this.escapeHtml(call)}</li>`).join('');
        return `<div class="tool-calls-section">
            <h4 class="section-title">🔧 Tool Calls</h4>
            <ul class="tool-calls-list">${toolItems}</ul>
        </div>`;
    }

    /**
     * Render citations as HTML with clickable citations
     * @param {string[]} citations - Array of citations strings
     * @returns {string} HTML representation
     */
    renderSources(citations) {
        if (!citations.length) return '';

        // FIXED: Use global counter across all source items for sequential numbering
        let globalCounter = 1;  // Global counter, not reset per source item

        const sourceItems = citations.map(citation => {
            // Handle simple citation markers: just convert to markdown link
            let processedSource = citation;

            // For the new unified approach, citations are just citation markers
            const citationRegex = /\[citation:([^\]]+)\]/g;
            processedSource = processedSource.replace(citationRegex, (match, citationId) => {
                const displayNumber = globalCounter++;  // Sequential numbering across all citations
                const workflow = window.globalState?.currentWorkflow;
                const viewUrl = workflow ? `/api/workflow/${workflow}/citations/${citationId}/view` : '#';
                return `[${displayNumber}](${viewUrl})`;  // Markdown link format
            });

            // Convert markdown links to HTML
            processedSource = this.renderMarkdownLinks(processedSource);

            return `<li class="source-item">${processedSource}</li>`;
        }).join('');

        return `<div class="citations-section">
            <h4 class="section-title">📚 Sources</h4>
            <ol class="citations-list">${sourceItems}</ol>
        </div>`;
    }

    /**
     * Render follow-up questions as HTML
     * @param {string[]} questions - Array of question strings
     * @returns {string} HTML representation
     */
    renderFollowUpQuestions(questions) {
        if (!questions.length) return '';

        const questionItems = questions.map(q => `<li class="followup-question">${this.escapeHtml(q)}</li>`).join('');
        return `<div class="followup-questions-section">
            <h4 class="section-title">💭 Suggested Follow-up Questions</h4>
            <ul class="followup-questions-list">${questionItems}</ul>
        </div>`;
    }



    /**
     * Open citation document in popup window (like STARTER_TOOLS)
     * @param {string} citationId - The citation ID to open
     */
    openCitationPopup(citationId) {
        try {
            // 🎯 Get workflow from multiple sources (fixes history viewing)
            let workflow = window.globalState?.currentWorkflow;

            // If no workflow in global state (e.g., when viewing history),
            // try to get it from the history session
            if (!workflow && window.historyUI?.currentWorkflowId) {
                workflow = window.historyUI.currentWorkflowId;
            }

            if (!workflow) {
                console.error('❌ No current workflow available for citation popup');
                alert(`Cannot open citation: please ensure you're in an active chat or history session.`);
                return;
            }

            // Fetch the actual document content from the /view endpoint
            fetch(`/api/workflow/${workflow}/citations/${citationId}/view`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`API request failed: ${response.status}`);
                    }
                    return response.json();
                })
                .then(viewerResponse => {
                    // Open popup window with document viewer (like STARTER_TOOLS does)
                    const viewerWindow = window.open('', '_blank', 'width=900,height=700,scrollbars=yes,resizable=yes');

                    if (!viewerWindow) {
                        alert('Please allow popups for this site to view source documents.');
                        return;
                    }

                    // Write the HTML document viewer to the new window
                    viewerWindow.document.write(viewerResponse.html);
                    viewerWindow.document.title = `Source Document - ${citationId}`;
                    viewerWindow.document.close();
                })
                .catch(error => {
                    console.error('❌ Error loading source document:', error);
                    alert(`Error loading source document for citation ${citationId}: ${error.message}`);
                });

        } catch (error) {
            console.error('❌ Error in citation popup:', error);
            alert(`Error opening popup for citation ${citationId}: ${error.message}`);
        }
    }

    /**
     * Convert table lines to HTML table - NEW METHOD FOR MARKDOWN TABLES
     * @param {string[]} tableLines - Array of table lines (markdown format)
     * @returns {string} HTML table
     */
    convertMarkdownTableToHtml(tableLines) {
        if (!tableLines || tableLines.length === 0) return '';

        let hasHeader = false;
        let headerRow = [];
        let bodyRows = [];

        // Process first row (potential header)
        if (tableLines.length > 0) {
            headerRow = tableLines[0].split('|').slice(1, -1).map(cell => cell.trim());
        }

        // Check if second line is a table separator
        if (tableLines.length > 1) {
            const secondRow = tableLines[1].split('|').slice(1, -1).map(cell => cell.trim());
            const isSeparator = secondRow.every(cell => /^[-:\s]*-[-:\s]*$/.test(cell));
            if (isSeparator) {
                hasHeader = true;
                // Skip separator line
                bodyRows = tableLines.slice(2);
            } else {
                // No header, all rows are body rows
                bodyRows = tableLines;
            }
        } else {
            // Only one row
            bodyRows = [];
        }

        let tableHtml = '<div class="markdown-table-container"><table class="markdown-table">';

        // Add header if present
        if (hasHeader && headerRow.length > 0) {
            const headerCells = headerRow.map(cell => `<th>${this.escapeHtml(cell)}</th>`).join('');
            tableHtml += `<thead><tr>${headerCells}</tr></thead>`;
        }

        // Add body rows
        if (bodyRows.length > 0) {
            const tbodyContent = bodyRows.map(row => {
                const cells = row.split('|').slice(1, -1).map(cell => cell.trim());
                const cellHtml = cells.map(cell => `<td>${this.escapeHtml(cell)}</td>`).join('');
                return `<tr>${cellHtml}</tr>`;
            }).join('');
            tableHtml += `<tbody>${tbodyContent}</tbody>`;
        }

        tableHtml += '</table></div>';
        return tableHtml;
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
}

// CSS styles for rich text rendering
const richTextStyles = `
    /* Rich Text Renderer Styles */
    .message-content {
        line-height: 1.6;
        word-wrap: break-word;
    }

    .message-content strong {
        font-weight: 600;
        color: #1f2937;
    }

    .message-content em {
        font-style: italic;
        color: #4b5563;
    }

    .message-content .inline-code {
        background: #f3f4f6;
        color: #dc2626;
        padding: 0.125rem 0.25rem;
        border-radius: 0.25rem;
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
        font-size: 0.85em;
        border: 1px solid #e5e7eb;
    }

    .message-content a {
        color: #2563eb;
        text-decoration: underline;
    }

    .message-content a:hover {
        color: #1d4ed8;
    }

    /* Code Block Styles */
    .code-block-container {
        position: relative;
        margin: 1rem 0;
        border-radius: 0.5rem;
        overflow: hidden;
        border: 1px solid #e5e7eb;
    }

    .code-block {
        background: #1f2937 !important;
        color: #f3f4f6 !important;
        padding: 1rem !important;
        margin: 0 !important;
        overflow-x: auto;
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
        font-size: 0.875rem;
        line-height: 1.5;
        white-space: pre;
    }

    .code-block language-python,
    .code-block.language-js,
    .code-block.language-javascript,
    .code-block.language-typescript,
    .code-block.language-ts {
        background: #0f172a !important;
    }

    .copy-button {
        position: absolute;
        top: 0.5rem;
        right: 0.5rem;
        background: rgba(0, 0, 0, 0.7);
        color: white;
        border: none;
        border-radius: 0.25rem;
        padding: 0.25rem 0.5rem;
        font-size: 0.75rem;
        cursor: pointer;
        opacity: 0;
        transition: opacity 0.2s;
    }

    .code-block-container:hover .copy-button {
        opacity: 1;
    }

    .copy-button:hover {
        background: rgba(0, 0, 0, 0.9);
    }

    /* Syntax Highlighting */
    .code-block .keyword {
        color: #60a5fa;
        font-weight: 500;
    }

    .code-block .string {
        color: #34d399;
    }

    .code-block .number {
        color: #fbbf24;
    }

    .code-block .comment {
        color: #6b7280;
        font-style: italic;
    }

    .code-block .type {
        color: #a78bfa;
    }

    .code-block .json-key {
        color: #60a5fa;
        font-weight: 500;
    }

    .code-block .json-value {
        color: #34d399;
    }

    /* TypeScript specific */
    .code-block.language-typescript .type {
        color: #fbbf24;
    }

    /* Enhanced Rendering Styles */
    .tool-calls-section,
    .citations-section,
    .followup-questions-section {
        margin: 1rem 0;
        padding: 1rem;
        border-radius: 0.5rem;
        background: #f9fafb;
        border: 1px solid #e5e7eb;
    }

    .section-title {
        margin: 0 0 0.5rem 0;
        font-size: 0.875rem;
        font-weight: 600;
        color: #374151;
        text-transform: uppercase;
        letter-spacing: 0.025em;
    }

    .tool-calls-list,
    .citations-list,
    .followup-questions-list {
        margin: 0;
        padding-left: 1.25rem;
    }

    .tool-call-item,
    .source-item,
    .followup-question {
        margin: 0.25rem 0;
        font-size: 0.875rem;
        line-height: 1.4;
        color: #4b5563;
    }

    .tool-call-item {
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
        background: #f3f4f6;
        padding: 0.125rem 0.25rem;
        border-radius: 0.25rem;
        border-left: 3px solid #2563eb;
        padding-left: 0.5rem;
    }

    .source-item {
        color: #2563eb;
        text-decoration: none;
        border-left: 3px solid #10b981;
        padding-left: 0.5rem;
        transition: color 0.2s;
    }

    .source-item:hover {
        color: #1d4ed8;
    }

    .followup-question::before {
        content: "💡 ";
        display: inline-block;
        margin-left: -1.25rem;
        margin-right: 0.25rem;
    }

    /* Markdown Table Styles */
    .markdown-table-container {
        margin: 1rem 0;
        overflow-x: auto;
        border-radius: 0.5rem;
        border: 1px solid #e5e7eb;
    }

    .markdown-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.875rem;
        line-height: 1.4;
    }

    .markdown-table th {
        background: #f9fafb;
        font-weight: 600;
        color: #374151;
        padding: 0.75rem;
        text-align: left;
        border-bottom: 2px solid #e5e7eb;
    }

    .markdown-table td {
        padding: 0.75rem;
        border-bottom: 1px solid #e5e7eb;
        color: #4b5563;
    }

    .markdown-table tr:nth-child(even) {
        background: #f9fafb;
    }

    .markdown-table tr:hover {
        background: #f3f4f6;
    }

    /* Clickable Citation Styles */
    .citation-link {
        color: #2563eb !important;
        text-decoration: underline !important;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s ease;
        background: rgba(37, 99, 235, 0.05);
        padding: 0.125rem 0.25rem;
        border-radius: 0.25rem;
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
        font-size: 0.85em;
    }

    .citation-link:hover {
        color: #1d4ed8 !important;
        background: rgba(37, 99, 235, 0.1);
        text-decoration: underline !important;
    }

    .citation-link:active {
        color: #1e40af !important;
        background: rgba(37, 99, 235, 0.15);
    }

    /* Superscript Citation Numbers */
    .message-content sup {
        font-size: 0.75em;
        color: #2563eb;
        font-weight: 500;
        margin-left: 0.125rem;
    }

    /* Full Citation Rendering Styles */
    .citations-full {
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
        border: 2px solid #e2e8f0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }

    .citations-full .section-title {
        color: #1e293b;
        font-size: 1rem;
        font-weight: 700;
        text-transform: none;
        letter-spacing: normal;
        border-bottom: 2px solid #3b82f6;
        padding-bottom: 0.5rem;
        margin-bottom: 1rem;
    }

    .citations-summary {
        background: #dbeafe;
        color: #1e40af;
        padding: 0.75rem 1rem;
        border-radius: 0.5rem;
        font-weight: 600;
        margin-bottom: 1rem;
        border-left: 4px solid #3b82f6;
    }

    .citations-list-full {
        padding-left: 0;
        list-style: none;
    }

    .source-item-full {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 0.75rem;
        padding: 1rem;
        margin-bottom: 0.75rem;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
        transition: all 0.2s ease;
    }

    .source-item-full:hover {
        box-shadow: 0 4px 12px 0 rgba(0, 0, 0, 0.15);
        transform: translateY(-1px);
    }

    .source-header {
        font-weight: 600;
        color: #1e293b;
        margin-bottom: 0.5rem;
        font-size: 0.95rem;
    }

    .source-description {
        color: #64748b;
        font-size: 0.875rem;
        line-height: 1.5;
        margin-bottom: 0.5rem;
        font-style: italic;
    }

    .source-relevance {
        background: #dcfce7;
        color: #166534;
        padding: 0.25rem 0.5rem;
        border-radius: 0.375rem;
        font-size: 0.75rem;
        font-weight: 600;
        display: inline-block;
        border: 1px solid #bbf7d0;
    }
`;

// Add citation click handlers
if (typeof document !== 'undefined') {
    // Citation link click handler for both inline and citations citations
    document.addEventListener('click', function (event) {
        let target = event.target;

        // Find parent anchor if nested content clicked
        if (target.tagName !== 'A') {
            target = target.closest('a');
        }

        if (!target) return;

        // Handle different citation link classes
        if (target.classList.contains('citation-link') || target.classList.contains('inline-citation-link')) {
            event.preventDefault();
            // Extract citation ID from data attribute or construct from link
            let citationId = target.dataset.citationId;
            if (!citationId && target.tagName === 'A') {
                // For inline citation links, extract from href/id pattern
                const href = target.getAttribute('href');
                if (href) {
                    if (href.startsWith('#citation-')) {
                        citationId = href.replace('#citation-', '');
                    } else if (href.includes('/citations/')) {
                        // Extract from full URL
                        citationId = href.split('/citations/')[1].split('/view')[0];
                    }
                }
            }
            if (citationId) {
                // Use the class method for consistency and robustness
                if (window.richTextRenderer && window.richTextRenderer.openCitationPopup) {
                    window.richTextRenderer.openCitationPopup(citationId);
                }
            }
        }
    });

    // Removed legacy handleCitationClick - now using RichTextRenderer.prototype.openCitationPopup
}

// Add styles to document
if (typeof document !== 'undefined') {
    const styleSheet = document.createElement('style');
    styleSheet.textContent = richTextStyles;
    document.head.appendChild(styleSheet);
}

// Copy code functionality
if (typeof HTMLElement !== 'undefined') {
    HTMLElement.prototype.copyCode = function () {
        const codeElement = this.parentElement.querySelector('code');
        if (codeElement && navigator.clipboard) {
            navigator.clipboard.writeText(codeElement.textContent).then(() => {
                // Flash feedback
                this.textContent = '✅';
                this.style.background = '#10b981';
                setTimeout(() => {
                    this.textContent = '📋';
                    this.style.background = 'rgba(0, 0, 0, 0.7)';
                }, 1000);
            }).catch(() => {
                // Fallback for older browsers
                const textArea = document.createElement('textarea');
                textArea.value = codeElement.textContent;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);

                this.textContent = '✅';
                this.style.background = '#10b981';
                setTimeout(() => {
                    this.textContent = '📋';
                    this.style.background = 'rgba(0, 0, 0, 0.7)';
                }, 1000);
            });
        }
    };
}

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = RichTextRenderer;
}

// Global instance for easy access
window.richTextRenderer = new RichTextRenderer();
