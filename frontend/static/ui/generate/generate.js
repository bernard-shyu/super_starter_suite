// generate_ui.js

document.addEventListener('DOMContentLoaded', () => {
    // Global variables
    let isGenerating = false;
    let generationTaskId = null;
    let statusPollingInterval = null;
    let logPollingInterval = null;
    let terminalOutput = document.getElementById('main-terminal-output');
    let liveTerminalOutput = document.getElementById('live-terminal-output');
    let progressTracker = null;
    let terminalManager = null;
    let websocket = null;

    // Cache management - use the global cache manager
    let cacheManager = null;
    let currentRAGType = 'RAG';

    // RAG Session management
    let currentRAGSessionId = null;

    // Detail view states
    let dataDetailView = false;

    // Constants for UI adjustments
    const DETAIL_VIEW_HEIGHT = 200; // Adjustable height for detail views in pixels

    // Terminal state tracking - now purely reactive to backend broadcasts
    let generationStartTime = null;
    let currentState = 'ST_READY';  // Updated by backend broadcasts only
    let lastStateChangeTime = null;
    let stateMessages = [];
    let allTerminalMessages = [];

    // ============================================================================
    // MVC VIEW LAYER - CATEGORY-BASED DISPLAY LOGIC
    // ============================================================================

    /**
     * MVC VIEW: Map MODEL categories to VIEW display destinations
     *
     * MODEL sends category-based messages (important, stateful, progress, debugging, error, info)
     * VIEW decides which display destination to use based on its own display logic
     */
    const VIEW_DISPLAY_MAPPINGS = {
        // MODEL Categories → VIEW Display Destinations
        'important': 'main_terminal',     // Critical state changes, completions, errors → Main panel
        'stateful': 'main_terminal',      // State transitions, status updates → Main panel
        'error': 'main_terminal',         // Error messages → Main panel
        'progress': 'live_terminal',      // Progress bars, incremental updates → Live panel
        'debugging': 'live_terminal',     // Debug info, tracing, verbose output → Live panel
        'info': 'live_terminal'           // General information → Live panel
    };

    /**
     * MVC VIEW: Get display destination for a MODEL category
     */
    function getDisplayDestinationForCategory(category) {
        return VIEW_DISPLAY_MAPPINGS[category] || 'live_terminal'; // Default to live terminal
    }

    // Initialize the page
    initializePage();

    async function initializePage() {
        logToTerminal('info', 'Initializing RAG Generation UI...');

        try {
            // Create RAG session for this page session
            await createRAGSession();

            // Load metadata cache on page entry (Cache-Phase-3)
            await loadMetadataCache();

            // Initialize cache manager for client-side caching
            cacheManager = getCacheManager();
            await cacheManager.initialize();

            // Load initial status from cache
            await loadDataStatus();
            await loadRAGStatus();

            // Load RAG type options for the selector
            await loadRAGTypes();

            // Load and display current generation method and model
            loadGenerateMethod();

            // Set up event listeners
            document.getElementById('generate-btn').addEventListener('click', handleGenerateClick);
            document.getElementById('test-ws-btn').addEventListener('click', handleTestWebSocket);
            document.getElementById('rag-type-select').addEventListener('change', handleRAGTypeChange);
            document.getElementById('data-detail-toggle').addEventListener('click', toggleDataDetailView);

            // Display cache status for debugging
            await displayCacheStatus();

            logToTerminal('success', 'RAG Generation UI initialized successfully');
        } catch (error) {
            logToTerminal('error', `Failed to initialize RAG Generation UI: ${error.message}`);
        }
    }

    // Create RAG session for this page session
    async function createRAGSession() {
        try {
            logToTerminal('info', 'Creating RAG session...');

            // This will create a session that doesn't exist yet - the backend will handle it
            // For now, we'll use a placeholder session ID since the UI doesn't need to track specific sessions
            currentRAGSessionId = 'default-rag-session';

            logToTerminal('info', `RAG session ready: ${currentRAGSessionId}`);
        } catch (error) {
            logToTerminal('error', `Failed to create RAG session: ${error.message}`);
            throw error;
        }
    }

    // Load data status (check cache first unless forceFresh=true)
    async function loadDataStatus(forceFresh = false) {
        const cacheKey = `data_status_${currentRAGType}`;

        if (!forceFresh && cacheManager.has(cacheKey)) {
            const cachedData = cacheManager.get(cacheKey);
            displayDataStatus(cachedData);
            return;
        }

        try {
            const data = await window.apiUtils.getRAGDataStatus(currentRAGSessionId, currentRAGType);

            cacheManager.set(cacheKey, data);
            displayDataStatus(data);
            if (forceFresh) {
                logToTerminal('info', '✅ Fresh data status loaded');
            }
        } catch (error) {
            logToTerminal('error', `Failed to load data status: ${error.message}`);
            displayDataStatusError(error.message);
        }
    }

    // Load RAG storage status (check cache first unless forceFresh=true)
    async function loadRAGStatus(forceFresh = false) {
        const cacheKey = `rag_status_${currentRAGType}`;

        if (!forceFresh && cacheManager.has(cacheKey)) {
            const cachedData = cacheManager.get(cacheKey);
            displayRAGStatus(cachedData);
            return;
        }

        try {
            const data = await window.apiUtils.getRAGStatus(currentRAGSessionId, currentRAGType);

            cacheManager.set(cacheKey, data);
            displayRAGStatus(data);
            if (forceFresh) {
                logToTerminal('info', '✅ Fresh RAG status loaded');
            }
        } catch (error) {
            logToTerminal('error', `Failed to load RAG status: ${error.message}`);
            displayRAGStatusError(error.message);
        }
    }

    // Load RAG type options from backend
    async function loadRAGTypes() {
        try {
            const data = await window.apiUtils.getRAGTypeOptions(currentRAGSessionId);

            if (Array.isArray(data.rag_types)) {
                const select = document.getElementById('rag-type-select');
                if (select) {
                    // Clear any existing options
                    select.innerHTML = '';
                    // Populate options and sync with currentRAGType
                    data.rag_types.forEach(type => {
                        const option = document.createElement('option');
                        option.value = type;
                        option.textContent = type;
                        // Sync with currentRAGType variable
                        if (type === currentRAGType) {
                            option.selected = true;
                        }
                        select.appendChild(option);
                    });
                }
            } else {
                throw new Error(data.detail || 'Failed to load RAG types');
            }
        } catch (error) {
            logToTerminal('error', `Failed to load RAG types: ${error.message}`);
        }
    }

    // Load and display current generation method and model info
    async function loadGenerateMethod() {
        try {
            const response = await fetch('/api/system/settings');
            const settings = await response.json();

            if (response.ok && settings) {
                const generationInfoDiv = document.getElementById('generation-info');
                const methodInfoDiv = document.getElementById('generation-method-info');
                const modelInfoDiv = document.getElementById('generation-model-info');

                if (generationInfoDiv && methodInfoDiv && modelInfoDiv) {
                    // Get current generation method - handle both nested and flat structures
                    let currentMethod = 'Not set';
                    if (settings.GENERATE && settings.GENERATE.METHOD) {
                        currentMethod = settings.GENERATE.METHOD;
                    } else if (settings['GENERATE.METHOD']) {
                        currentMethod = settings['GENERATE.METHOD'];
                    }

                    // Get selected model for the current method if it's an AI method
                    let selectedModel = 'N/A';
                    if (currentMethod.includes('AI')) {
                        // Get model from the appropriate AI method section
                        if (currentMethod === 'NvidiaAI' && settings.GENERATE_AI_METHOD && settings.GENERATE_AI_METHOD.NvidiaAI_SELECTED_MODEL) {
                            selectedModel = settings.GENERATE_AI_METHOD.NvidiaAI_SELECTED_MODEL;
                        } else if (currentMethod === 'GeminiAI' && settings.GENERATE_AI_METHOD && settings.GENERATE_AI_METHOD.GeminiAI_SELECTED_MODEL) {
                            selectedModel = settings.GENERATE_AI_METHOD.GeminiAI_SELECTED_MODEL;
                        } else {
                            // Fallback to CHATBOT_AI_MODEL for other cases
                            if (settings.CHATBOT_AI_MODEL && settings.CHATBOT_AI_MODEL.SELECTED) {
                                selectedModel = settings.CHATBOT_AI_MODEL.SELECTED.ID || 'N/A';
                            }
                        }
                    }

                    // Display the information
                    methodInfoDiv.textContent = `Method: ${currentMethod}`;
                    modelInfoDiv.textContent = currentMethod.includes('AI') ? ` Model: ${selectedModel}` : '';

                    // Show the generation info section
                    generationInfoDiv.style.display = 'block';

                    logToTerminal('info', `Loaded generation method: ${currentMethod}${currentMethod.includes('AI') ? `, Model: ${selectedModel}` : ''}`);
                }
            } else {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
        } catch (error) {
            logToTerminal('error', `Failed to load generation method info: ${error.message}`);
            console.error('Settings response:', error);
        }
    }

    // ============================================================================
    // MVC VIEW LAYER: Enhanced Frontend Status Formatting Functions
    // ============================================================================
    // All display formatting logic moved from backend to frontend (MVC View layer)

    /**
     * MVC VIEW: Format data status display based on raw backend data
     * Backend provides raw data, frontend determines presentation format
     */
    function formatDataStatusDisplay(data) {
        // MVC COMPLIANT: Frontend analyzes raw data to determine status
        // Backend no longer provides pre-formatted status - frontend decides

        const totalFiles = data.total_files || 0;
        const storageStatus = data.storage_status || 'empty';
        const dataNewestTime = data.data_newest_time;
        const storageCreation = data.storage_creation;
        const comparisonData = data.comparison_data || {};

        // Analyze raw data to determine status (frontend business logic)
        let statusType = 'uptodate';
        let statusText = 'Up to date';
        let statusColor = '#4CAF50'; // GREEN

        if (totalFiles === 0) {
            // No data files found
            statusType = 'no_data';
            statusText = 'No Data Files';
            statusColor = '#9E9E9E'; // GRAY
        } else if (storageStatus === 'empty') {
            // Data exists but no storage created yet
            statusType = 'need_generate';
            statusText = 'Need Generate';
            statusColor = '#f44336'; // RED
        } else if (dataNewestTime && storageCreation) {
            // Compare timestamps (frontend handles comparison logic)
            try {
                const dataTime = new Date(dataNewestTime);
                const storageTime = new Date(storageCreation);

                if (dataTime > storageTime) {
                    // Data is newer than storage
                    statusType = 'obsolete_data';
                    statusText = 'Obsolete Data';
                    statusColor = '#FF9800'; // ORANGE
                }
            } catch (e) {
                // Timestamp comparison failed
                statusType = 'unknown';
                statusText = 'Status Unknown';
                statusColor = '#9E9E9E'; // GRAY
            }
        }

        // Use comparison data if available (more detailed status)
        if (comparisonData.is_up_to_date === false) {
            statusType = 'changes_detected';
            statusText = 'Changes Detected';
            statusColor = '#FF9800'; // ORANGE
        }

        return {
            statusType: statusType,
            text: statusText,
            color: statusColor,
            totalFiles: totalFiles,
            storageStatus: storageStatus,
            fromCache: data.from_cache || false
        };
    }

    /**
     * MVC VIEW: Format file size for human-readable display
     */
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    /**
     * MVC VIEW: Format date for display
     */
    function formatDate(dateString) {
        if (!dateString) return 'N/A';
        try {
            const date = new Date(dateString);
            return date.toLocaleString();
        } catch (e) {
            return dateString;
        }
    }

    /**
     * MVC VIEW: Generate summary text based on raw data
     */
    function generateDataSummary(data) {
        const totalFiles = data.total_files || 0;
        const totalSize = data.total_size || 0;
        const storageStatus = data.storage_status || 'empty';
        const statusInfo = formatDataStatusDisplay(data);

        let summary = '';

        if (totalFiles === 0) {
            summary = 'No data files found';
        } else if (storageStatus === 'empty') {
            summary = `Found ${totalFiles} files (${formatFileSize(totalSize)}) - generation required`;
        } else {
            summary = `Data contains ${totalFiles} files (${formatFileSize(totalSize)})`;
        }

        // Add cache indicator
        if (data.from_cache) {
            summary += ' (cached)';
        }

        return summary;
    }

    // Display data status - switches between Summary and Detail modes
    function displayDataStatus(data) {
        const dataStatusDiv = document.getElementById('data-status');
        if (!dataStatusDiv) {
            console.log('[DEBUG] ERROR: data-status element not found!');
            return;
        }

        dataStatusDiv.innerHTML = '';

        if (dataDetailView) {
            // Detail Status mode - show detailed file list with small font
            displayDetailedDataStatus(data);
        } else {
            // Summary Status mode - show 4-row tabular layout with normal font (reordered fields)
            const summaryTable = document.createElement('table');
            summaryTable.style.width = '100%';
            summaryTable.style.borderCollapse = 'collapse';
            summaryTable.style.fontSize = '14px'; // Normal font size

            // Row 1: Newest File Time (data_newest_time)
            const row1 = summaryTable.insertRow();
            row1.insertCell(0).textContent = 'Newest File Time:';
            row1.cells[0].style.fontWeight = 'bold';
            row1.cells[0].style.padding = '4px 8px';
            const fileTimeCell = row1.insertCell(1);
            fileTimeCell.textContent = formatDate(data.data_newest_time);
            fileTimeCell.style.padding = '4px 8px';
            fileTimeCell.style.textAlign = 'left';

            // Row 2: Newest File Name (data_newest_file)
            const row2 = summaryTable.insertRow();
            row2.insertCell(0).textContent = 'Newest File Name:';
            row2.cells[0].style.fontWeight = 'bold';
            row2.cells[0].style.padding = '4px 8px';
            const fileNameCell = row2.insertCell(1);
            const newestFilename = data.data_newest_file || 'N/A';
            const filenameValue = newestFilename.length > 35 ? newestFilename.substring(0, 35) + '...' : newestFilename;
            fileNameCell.textContent = filenameValue;
            fileNameCell.style.padding = '4px 8px';
            fileNameCell.style.textAlign = 'left';
            fileNameCell.style.fontFamily = 'monospace';
            fileNameCell.title = newestFilename; // Show full filename on hover

            // Row 3: total_files + total_size
            const row3 = summaryTable.insertRow();
            row3.insertCell(0).textContent = 'Files / Size:';
            row3.cells[0].style.fontWeight = 'bold';
            row3.cells[0].style.padding = '4px 8px';
            const filesSizeCell = row3.insertCell(1);
            const filesSizeValue = `${data.total_files || 0} files / ${formatFileSize(data.total_size || 0)}`;
            filesSizeCell.textContent = filesSizeValue;
            filesSizeCell.style.padding = '4px 8px';
            filesSizeCell.style.textAlign = 'left';

            // Row 4: summary status
            const row4 = summaryTable.insertRow();
            row4.insertCell(0).textContent = 'Status:';
            row4.cells[0].style.fontWeight = 'bold';
            row4.cells[0].style.padding = '4px 8px';
            const statusCell = row4.insertCell(1);

            // MVC VIEW LAYER: Frontend determines display format from backend data
            const statusInfo = formatDataStatusDisplay(data);
            statusCell.textContent = statusInfo.text;
            statusCell.style.padding = '4px 8px';
            statusCell.style.textAlign = 'left';
            statusCell.style.fontWeight = 'bold';
            statusCell.style.color = statusInfo.color;

            dataStatusDiv.appendChild(summaryTable);
        }
    }

    // Display RAG storage status in exact 3-row tabular layout as specified
    function displayRAGStatus(data) {
        const ragStatusDiv = document.getElementById('rag-status');
        if (!ragStatusDiv) {
            console.log('[DEBUG] ERROR: rag-status element not found!');
            return;
        }

        ragStatusDiv.innerHTML = '';

        // Create table for storage status (3 specific rows as specified)
        const storageTable = document.createElement('table');
        storageTable.style.width = '100%';
        storageTable.style.borderCollapse = 'collapse';
        storageTable.style.fontSize = '14px';

        // Row 1: rag_storage_creation
        const row1 = storageTable.insertRow();
        row1.insertCell(0).textContent = 'Creation Time:';
        row1.cells[0].style.fontWeight = 'bold';
        row1.cells[0].style.padding = '4px 8px';
        const creationCell = row1.insertCell(1);
        // Fix: Use correct field from backend
        const storageInfo = data.storage_info || {};
        const creationValue = storageInfo.last_modified ? formatDate(storageInfo.last_modified) : 'N/A';
        creationCell.textContent = creationValue;
        creationCell.style.padding = '4px 8px';
        creationCell.style.textAlign = 'left'; // Left-aligned as requested

        // Row 2: rag_storage_hash (no hash available from backend)
        const row2 = storageTable.insertRow();
        row2.insertCell(0).textContent = 'Storage Files:';
        row2.cells[0].style.fontWeight = 'bold';
        row2.cells[0].style.padding = '4px 8px';
        const fileCountCell = row2.insertCell(1);
        const storageFiles = storageInfo.storage_files || [];
        const fileCountValue = `${storageFiles.length} files`;
        fileCountCell.textContent = fileCountValue;
        fileCountCell.style.padding = '4px 8px';
        fileCountCell.style.textAlign = 'left'; // Left-aligned as requested

        // Row 3: summary status
        const row3 = storageTable.insertRow();
        row3.insertCell(0).textContent = 'Status:';
        row3.cells[0].style.fontWeight = 'bold';
        row3.cells[0].style.padding = '4px 8px';
        const statusCell = row3.insertCell(1);

        // Fix: Use correct field from backend for status determination
        let statusText = 'empty';
        let statusColor = '#f44336'; // RED for empty

        if (storageFiles.length > 0) {
            // Check if storage is up to date (from comparison result)
            if (data.is_up_to_date === false) {
                statusText = 'corrupted';
                statusColor = '#f44336'; // RED for corrupted
            } else {
                statusText = 'healthy';
                statusColor = '#4CAF50'; // GREEN for healthy
            }
        }

        statusCell.textContent = statusText;
        statusCell.style.padding = '4px 8px';
        statusCell.style.textAlign = 'left'; // Left-aligned as requested
        statusCell.style.fontWeight = 'bold';
        statusCell.style.color = statusColor;

        ragStatusDiv.appendChild(storageTable);
    }

    // Handle generate button click
    async function handleGenerateClick() {
        if (isGenerating) return;

        const generateBtn = document.getElementById('generate-btn');
        const progressSection = document.querySelector('.progress-section');
        const ragSelect = document.getElementById('rag-type-select');

        try {
            logToTerminal('info', 'Starting RAG generation process...');

            const selectedItem = ragSelect ? ragSelect.value : null;

            // Validate RAG type selection
            if (!selectedItem || selectedItem.trim() === '') {
                throw new Error('Please select a RAG type before generating');
            }

            const payload = { rag_type: selectedItem };
            logToTerminal('info', `Selected RAG type: ${selectedItem}`);

            const data = await window.apiUtils.startRAGGeneration(currentRAGSessionId, payload);

            if (data.task_id) {
                generationTaskId = data.task_id;
                isGenerating = true;

                // DISABLE RAG TYPE SELECTOR DURING GENERATION
                const ragSelect = document.getElementById('rag-type-select');
                if (ragSelect) {
                    ragSelect.disabled = true;
                    ragSelect.style.opacity = '0.6';
                    ragSelect.style.cursor = 'not-allowed';
                    ragSelect.style.pointerEvents = 'none'; // Additional disabling
                    ragSelect.style.backgroundColor = '#f5f5f5'; // Visual feedback
                    ragSelect.title = 'RAG type cannot be changed during generation'; // Tooltip
                    logToTerminal('info', 'RAG type selector disabled during generation');
                } else {
                    logToTerminal('warning', 'Could not find RAG type selector element');
                }

                generateBtn.disabled = true;
                generateBtn.textContent = '🔄 Generating...';
                if (progressSection) {
                    progressSection.classList.remove('hidden');
                }
                updateProgress(0, 'Initializing generation...');

                logToTerminal('success', `Generation started with task ID: ${data.task_id} for RAG type: ${selectedItem}`);

                // Connect to WebSocket for real-time updates (STATE-BASED) - include task_id for proper routing
                connectTerminalWebSocket(data.task_id);

                // Initialize frontend state sync with backend (no polling)
                initializeFrontendStateSync();
            } else {
                throw new Error('No task ID received from server');
            }
        } catch (error) {
            logToTerminal('error', `Failed to start generation: ${error.message}`);
            updateProgress(0, `Error: ${error.message}`);
        }
    }

    // REMOVED: Polling-based status checking (replaced with event-driven WebSocket)

    // STATE-BASED: Initialize frontend state sync with backend
    function initializeFrontendStateSync() {
        // Frontend MODEL syncs with backend state via WebSocket events
        // No polling - purely reactive to backend state changes
        generationStartTime = new Date();
        currentState = 'ST_READY';  // Initial state until backend syncs
        stateMessages = [];

        // Add initial ready message
        if (terminalOutput) {
            const separator = document.createElement('div');
            separator.className = 'log-entry log-info';
            separator.innerHTML = `<span class="log-timestamp">[${new Date().toLocaleTimeString()}]</span> === WAITING FOR BACKEND STATE SYNC ===`;
            terminalOutput.appendChild(separator);
        }

        if (liveTerminalOutput) {
            const separator = document.createElement('div');
            separator.className = 'log-entry log-info';
            separator.innerHTML = `<span class="log-timestamp">[${new Date().toLocaleTimeString()}]</span> === WAITING FOR BACKEND STATE SYNC ===`;
            liveTerminalOutput.appendChild(separator);
            liveTerminalOutput.scrollTop = liveTerminalOutput.scrollHeight;
        }

        // Apply initial UI state (will be updated by backend events)
        applyMVCStateStyling('ST_READY');
        updateTerminalHeader('ST_READY', 0);
        updateProgressBar(0);
        updateRotatingIcon('ST_READY');
    }

    // MVC COMPLIANT: Removed obsolete functions after category-based refactoring
    // - addStateMessage(): Messages now come categorized from backend
    // - updateMainTerminalState(): State comes directly from backend Controller
    // - updateMainTerminalDisplay(): Messages routed by category in renderTerminalMessage()

    // Format elapsed time as human-readable string
    function formatElapsedTime(seconds) {
        if (seconds < 60) return `${seconds}s`;
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        if (minutes < 60) return `${minutes}m ${remainingSeconds}s`;
        const hours = Math.floor(minutes / 60);
        const remainingMinutes = minutes % 60;
        return `${hours}h ${remainingMinutes}m ${remainingSeconds}s`;
    }

    // Handle successful generation completion (STATE-BASED: sync with backend state)
    async function handleGenerationComplete() {
        // Clear polling intervals (remove polling-based mechanism)
        if (statusPollingInterval) {
            clearTimeout(statusPollingInterval);
            statusPollingInterval = null;
        }
        if (logPollingInterval) {
            clearInterval(logPollingInterval);
            logPollingInterval = null;
        }

        // Set local generation flag (frontend state sync)
        isGenerating = false;

        // RE-ENABLE RAG TYPE SELECTOR AFTER GENERATION
        const ragSelect = document.getElementById('rag-type-select');
        if (ragSelect) {
            ragSelect.disabled = false;
            ragSelect.style.opacity = '1';
            ragSelect.style.cursor = 'pointer';
            ragSelect.style.pointerEvents = 'auto';
            ragSelect.style.backgroundColor = '';
            ragSelect.removeAttribute('title');
            logToTerminal('info', 'RAG type selector re-enabled after generation completion');
        }

        // IMMEDIATE button re-enabling (prevent race conditions)
        const generateBtn = document.getElementById('generate-btn');
        if (generateBtn) {
            generateBtn.disabled = false;
            generateBtn.removeAttribute('disabled');
            generateBtn.textContent = '✅ Generation Complete - Generate Again';
        }

        // Close WebSocket connection
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.close(1000, 'Generation completed');
            websocket = null;
            logToTerminal('info', 'WebSocket connection closed after completion');
        }

        // Update UI to COMPLETED state (sync with backend state)
        applyMVCStateStyling('ST_COMPLETED');
        updateTerminalHeader('ST_COMPLETED', 100);
        updateProgressBar(100);

        // AUTO-REFRESH STATUS AFTER GENERATION COMPLETES
        logToTerminal('info', 'Auto-refreshing status after generation completion...');
        try {
            // FORCE fresh data load by bypassing cache completely
            await loadDataStatus(true);  // forceFresh=true
            await loadRAGStatus(true);   // forceFresh=true
            logToTerminal('success', '✅ Status updated automatically after generation');
        } catch (error) {
            logToTerminal('warning', `⚠️ Auto-refresh failed: ${error.message}`);
        }

        // NON-POLLING: Let backend push status updates via WebSocket events
        // No setTimeout polling - wait for backend to send status updates
        // Frontend MODEL will sync when backend sends new status data
    }

    // Handle generation failure (MVC View - simple state updates)
    function handleGenerationFailed(error) {
        // FIX: Properly clear ALL polling intervals to prevent endless polling
        if (statusPollingInterval) {
            clearTimeout(statusPollingInterval);
            statusPollingInterval = null;
        }
        if (logPollingInterval) {
            clearInterval(logPollingInterval);
            logPollingInterval = null;
        }

        isGenerating = false;

        // RE-ENABLE RAG TYPE SELECTOR AFTER GENERATION FAILURE
        const ragSelect = document.getElementById('rag-type-select');
        if (ragSelect) {
            ragSelect.disabled = false;
            ragSelect.style.opacity = '1';
            ragSelect.style.cursor = 'pointer';
            ragSelect.style.pointerEvents = 'auto';
            ragSelect.style.backgroundColor = '';
            ragSelect.title = '';
            logToTerminal('info', 'RAG type selector re-enabled after generation failure');
        }

        const generateBtn = document.getElementById('generate-btn');
        generateBtn.disabled = false;
        generateBtn.textContent = '❌ Retry Generation';

        // FIX: Update terminal to error state
        applyMVCStateStyling('ST_ERROR');
        updateTerminalHeader('ST_ERROR', 0);
        updateProgressBar(0);

        // Check if RAG generation actually succeeded despite connection issues
        const cacheKey = `rag_status_${currentRAGType}`;
        let generationStatus = 'unknown';

        if (cacheManager && cacheManager.has(cacheKey)) {
            const ragStatus = cacheManager.get(cacheKey);
            const storageInfo = ragStatus.storage_info || {};
            const storageFiles = storageInfo.storage_files || [];

            if (storageFiles.length > 0) {
                generationStatus = 'succeeded';
                // Override error state if files were actually generated
                generateBtn.textContent = '✅ Generation Complete - Generate Again';
                applyMVCStateStyling('ST_READY');
                updateTerminalHeader('ST_READY', 100);
                updateProgressBar(100);
                logToTerminal('success', `RAG Index Storage files successfully generated (${storageFiles.length} files)`);
            } else {
                generationStatus = 'failed';
            }
        }

        // Provide clear error information
        const errorMessage = error || 'Unknown error occurred';
        if (generationStatus === 'succeeded') {
            logToTerminal('warning', `Connection error but RAG generation succeeded: ${errorMessage}`);
        } else {
            logToTerminal('error', `Generation failed: ${errorMessage}`);
        }

        // Close WebSocket connection properly
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.close(1000, generationStatus === 'succeeded' ? 'Generation completed with connection issue' : 'Generation failed');
            websocket = null;
            if (generationStatus === 'succeeded') {
                logToTerminal('info', 'WebSocket connection closed after successful generation');
            } else {
                logToTerminal('error', 'WebSocket connection closed after failure');
            }
        }
    }



    // Connect to WebSocket for real-time terminal updates
    function connectTerminalWebSocket(taskId = null) {
        if (websocket) {
            websocket.close();
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        // Include task_id in WebSocket URL to ensure proper message routing
        const wsUrl = taskId
            ? `${protocol}//${window.location.host}/ws/generate?task_id=${encodeURIComponent(taskId)}`
            : `${protocol}//${window.location.host}/ws/generate`;

        websocket = new WebSocket(wsUrl);

        // Add connection timeout
        websocket.connectionTimeout = setTimeout(() => {
            if (websocket.readyState === WebSocket.CONNECTING) {
                websocket.close();
                logToTerminal('error', 'WebSocket connection timeout');
            }
        }, 5000); // 5 second timeout

        websocket.onopen = function (event) {
            // WebSocket connection success - send to Live Terminal
            logToTerminal('info', '✅ Connected to terminal streaming');
        };

        websocket.onmessage = function (event) {
            try {
                const data = JSON.parse(event.data);

                // Route through EventDispatcher instead of direct handling
                document.dispatchEvent(new CustomEvent('websocket-message', {
                    detail: data
                }));
            } catch (e) {
                console.error('[WS] CRITICAL ERROR - Message parse failed:', event.data, 'Error:', e.message);
                // CRITICAL: Show parse errors in Main Terminal for debugging
                logToTerminal('error', `❌ CRITICAL: WebSocket message parse error - ${e.message}`);
                logToTerminal('error', `❌ Raw message: ${event.data.substring(0, 200)}...`);
            }
        };

        websocket.onclose = function (event) {
            // WebSocket closure details - keep in console for debugging
            console.log('[WS] Connection closed - code:', event.code, 'reason:', event.reason);

            // CRITICAL: Show WebSocket closure details in Main Terminal
            if (event.code === 1000) {
                logToTerminal('info', 'ℹ️ WebSocket connection closed normally');
            } else if (event.code === 1006) {
                logToTerminal('warning', '⚠️ WebSocket connection closed unexpectedly (code 1006)');
            } else {
                logToTerminal('warning', `⚠️ WebSocket connection closed (code: ${event.code}, reason: ${event.reason})`);
            }
        };

        websocket.onerror = function (error) {
            console.error('[WS] CRITICAL ERROR - WebSocket connection error:', error);

            // CRITICAL: Show WebSocket errors prominently in Main Terminal
            logToTerminal('error', '❌ CRITICAL: WebSocket connection error occurred');
            logToTerminal('error', '❌ This may indicate backend connectivity issues');

            // Check if generation is still running despite WebSocket error
            if (isGenerating) {
                logToTerminal('warning', '⚠️ Generation may still be running despite WebSocket error');
                logToTerminal('warning', '⚠️ Check backend logs for generation status');
            }
        };
    }



    // Handle encapsulated progress data with control points (MVC View)
    function handleEncapsulatedProgress(data) {
        try {
            // For plain JSON data from WebSocket, use directly without DTO validation
            const normalizedData = { ...data };

            // Ensure we have valid progress data
            if (normalizedData.progress === undefined || normalizedData.progress === null ||
                normalizedData.state === undefined || !normalizedData.state) {
                console.warn('[MVC] Invalid progress data received:', data);
                return;
            }

            // Always update UI with progress data
            // Progress updates go to Live Terminal
            if (liveTerminalOutput) {
                const liveEntry = document.createElement('div');
                liveEntry.className = 'log-entry log-info';
                liveEntry.innerHTML = `<span class="log-timestamp">[${new Date().toLocaleTimeString()}]</span> [${normalizedData.state.replace('ST_', '')}] ${normalizedData.message || ''}`;
                liveTerminalOutput.appendChild(liveEntry);
                liveTerminalOutput.scrollTop = liveTerminalOutput.scrollHeight;
            }

            // Update UI with progress data
            applyMVCStateStyling(normalizedData.state);
            updateTerminalHeader(normalizedData.state, normalizedData.progress);
            updateProgressBar(normalizedData.progress);
            updateRotatingIcon(normalizedData.state);

            // Handle state-specific completion logic
            if ((normalizedData.state === 'ST_READY' || normalizedData.state === 'ST_COMPLETED') &&
                normalizedData.message && normalizedData.message.includes('completed successfully')) {
                // Send completion to Main Terminal as 'important' event
                logToTerminal('success', '✅ Generation completed successfully');
                handleGenerationComplete();
            } else if (normalizedData.state === 'ST_ERROR') {
                console.warn('[GENERATION ERROR]', normalizedData.message);
                logToTerminal('error', `Generation failed: ${normalizedData.message}`);
                handleGenerationFailed(normalizedData.message);
            } else if (normalizedData.state === 'ST_COMPLETED') {
                // Send completion to Main Terminal as 'important' event
                logToTerminal('success', '✅ Generation completed successfully');
                handleGenerationComplete();
            }

        } catch (error) {
            console.error('[MVC] Error processing progress data:', error, data);
            logToTerminal('error', `Failed to process progress data: ${error.message}`);
        }
    }

    // MVC COMPLIANT: Message filtering now handled by category-based routing in VIEW_DISPLAY_MAPPINGS
    // No need for manual filtering function - VIEW decides destination based on MODEL categories

    // Handle encapsulated status data with control points (MVC View)
    function handleEncapsulatedStatus(data) {
        try {
            // Handle data status
            if (data.data_status) {
                // Create StatusData DTO from incoming data
                const statusData = new StatusData(data.data_status);

                // Control Point: Only render validated data
                if (statusData._validated) {
                    // Control Point: Check if refresh needed
                    if (statusData.shouldRefresh()) {
                        // Note: Frontend doesn't initiate refresh, just logs
                        logToTerminal('info', 'Status data refresh recommended');
                    }

                    displayDataStatus(statusData.toDict());

                    // CRITICAL FIX: Check if markRendered method exists before calling it
                    // This prevents "statusData.markRendered is not a function" error
                    if (typeof statusData.markRendered === 'function') {
                        statusData.markRendered();
                    } else {
                        console.warn('[MVC] StatusData object missing markRendered method - this is expected for plain JSON objects from backend');
                    }
                } else {
                    console.warn('[MVC] Received unvalidated status data');
                    console.warn('[MVC] StatusData validation details:', {
                        totalFiles: statusData.totalFiles,
                        totalSize: statusData.totalSize,
                        totalFilesValid: statusData.totalFiles >= 0,
                        totalSizeValid: statusData.totalSize >= 0
                    });
                }
            }

            // Handle RAG status (using existing format for now)
            if (data.rag_status) {
                displayRAGStatus(data.rag_status);
            }
        } catch (error) {
            console.error('[MVC] Error processing encapsulated status data:', error);
            console.error('[MVC] Error details:', error);
            logToTerminal('error', `Failed to process status data: ${error.message}`);
        }
    }

    // MVC COMPLIANT: Legacy functions removed - all progress handling now uses handleEncapsulatedProgress()

    // Apply state-dependent styling based on MVC state constants (WHITE/GREEN/ORANGE/RED)
    function applyMVCStateStyling(state) {
        const terminalHeader = document.getElementById('terminal-header');
        const terminalStatus = document.getElementById('terminal-status');
        const progressFill = document.getElementById('progress-fill');
        const rotatingIcon = document.getElementById('rotating-icon');

        if (!terminalHeader || !terminalStatus || !progressFill) return;

        // Remove all state classes
        terminalHeader.classList.remove('ready', 'parser', 'generation', 'error');
        terminalStatus.classList.remove('ready', 'parser', 'generation', 'error');
        progressFill.classList.remove('parser', 'generation');

        // State-based styling configuration - 5 states with compact text
        const stateConfig = {
            'ST_READY': {
                color: '#ffffff',  // WHITE
                backgroundColor: '#ffffff20',
                text: 'Terminal Output: Ready',
                showIcon: false,
                headerClass: 'ready'
            },
            'ST_PARSER': {
                color: '#4CAF50',  // GREEN
                backgroundColor: '#4CAF5020',
                text: 'Terminal Output: Parser',
                showIcon: true,
                headerClass: 'parser'
            },
            'ST_GENERATION': {
                color: '#FF9800',  // ORANGE
                backgroundColor: '#FF980020',
                text: 'Terminal Output: Generate',
                showIcon: true,
                headerClass: 'generation'
            },
            'ST_COMPLETED': {
                color: '#4CAF50',  // GREEN (same as parser for success)
                backgroundColor: '#4CAF5020',
                text: 'Terminal Output: Completed',
                showIcon: false,
                headerClass: 'completed'
            },
            'ST_ERROR': {
                color: '#f44336',  // RED
                backgroundColor: '#f4433620',
                text: 'Terminal Output: Error',
                showIcon: false,
                headerClass: 'error'
            }
        };

        const config = stateConfig[state] || stateConfig['ST_READY'];

        // Apply state class to elements
        terminalHeader.classList.add(config.headerClass);
        terminalStatus.classList.add(config.headerClass);

        // Apply colors and styling
        terminalHeader.style.backgroundColor = config.backgroundColor;
        terminalHeader.style.borderLeft = `4px solid ${config.color}`;
        terminalStatus.style.color = config.color;
        terminalStatus.textContent = config.text;

        // Set progress bar color based on state
        if (state === 'ST_PARSER') {
            progressFill.classList.add('parser');
            progressFill.style.backgroundColor = config.color;
        } else if (state === 'ST_GENERATION') {
            progressFill.classList.add('generation');
            progressFill.style.backgroundColor = config.color;
        }

        // Show/hide rotating icon
        if (rotatingIcon) {
            rotatingIcon.style.display = config.showIcon ? 'inline' : 'none';
        }
    }

    // Update terminal header with state and progress (MVC View)
    function updateTerminalHeader(state, progress) {
        const terminalHeader = document.getElementById('terminal-header');
        const terminalStatus = document.getElementById('terminal-status');
        const terminalProgressBar = document.getElementById('terminal-progress-bar');
        const terminalPercentage = document.getElementById('terminal-percentage');
        const rotatingIcon = document.getElementById('rotating-icon');

        if (!terminalHeader || !terminalStatus || !terminalProgressBar || !terminalPercentage) return;

        // State-based text and colors - 5 states with compact text
        const stateConfig = {
            'ST_READY': {
                text: 'Terminal Output: Ready',
                color: '#ffffff',
                showIcon: false
            },
            'ST_PARSER': {
                text: 'Terminal Output: Parser',
                color: '#4CAF50',
                showIcon: true
            },
            'ST_GENERATION': {
                text: 'Terminal Output: Generate',
                color: '#FF9800',
                showIcon: true
            },
            'ST_COMPLETED': {
                text: 'Terminal Output: Completed',
                color: '#4CAF50',
                showIcon: false
            },
            'ST_ERROR': {
                text: 'Terminal Output: Error',
                color: '#f44336',
                showIcon: false
            }
        };

        const config = stateConfig[state] || stateConfig['ST_READY'];

        // Update status text and colors
        terminalStatus.textContent = config.text;
        terminalStatus.style.color = config.color;

        // Update progress bar
        terminalProgressBar.style.width = `${progress}%`;
        terminalProgressBar.style.backgroundColor = config.color;

        // Update percentage text
        terminalPercentage.textContent = `${progress}%`;
        terminalPercentage.style.color = config.color;

        // Show/hide rotating icon
        if (rotatingIcon) {
            rotatingIcon.style.display = config.showIcon ? 'inline' : 'none';
        }

        // Apply header background based on state
        terminalHeader.style.backgroundColor = config.color + '20'; // 20 = 12% opacity
        terminalHeader.style.borderLeft = `4px solid ${config.color}`;
    }

    // MVC COMPLIANT: Legacy state mapping removed - backend now sends correct state names

    // Update progress bar with Model-calculated percentage (MVC View)
    function updateProgressBar(percentage) {
        const progressFill = document.getElementById('progress-fill');
        const progressText = document.getElementById('progress-text');
        const terminalProgressBar = document.getElementById('terminal-progress-bar');
        const terminalPercentage = document.getElementById('terminal-percentage');

        if (progressFill && progressText) {
            progressFill.style.width = `${percentage}%`;
            progressText.textContent = `${percentage}%`;
        }

        // Also update terminal progress bar
        if (terminalProgressBar && terminalPercentage) {
            terminalProgressBar.style.width = `${percentage}%`;
            terminalPercentage.textContent = `${percentage}%`;
        }
    }

    // Update rotating icon visibility based on state
    function updateRotatingIcon(state) {
        const rotatingIcon = document.getElementById('rotating-icon');
        if (!rotatingIcon) return;

        // Show icon for active states (parser/generation), hide for ready/error
        const showIcon = state === 'ST_PARSER' || state === 'ST_GENERATION';
        rotatingIcon.style.display = showIcon ? 'inline' : 'none';

        // Add/remove rotating animation class
        if (showIcon) {
            rotatingIcon.classList.add('rotating');
        } else {
            rotatingIcon.classList.remove('rotating');
        }
    }

    // Legacy updateProgress function for backward compatibility
    function updateProgress(percentage, message = "") {
        // Update progress bar
        updateProgressBar(percentage);

        // Update progress text if message provided
        if (message) {
            logToTerminal('info', message);
        }
    }

    // MVC VIEW: Render terminal message from Model/Controller with category-based routing
    function renderTerminalMessage(data) {
        // MVC: MODEL sends category-based messages, VIEW decides display destinations
        const category = data.category || 'info';  // MODEL-centric category
        const displayDestination = getDisplayDestinationForCategory(category);  // VIEW decision

        // Route message to appropriate VIEW display destination
        if (displayDestination === 'main_terminal') {
            // Main Terminal: important + stateful + error messages
            logToTerminal(data.level || 'info', data.message);
        } else if (displayDestination === 'live_terminal') {
            // Live Terminal: progress + debugging + info messages
            if (liveTerminalOutput) {
                const liveEntry = document.createElement('div');
                liveEntry.className = `log-entry log-${data.level || 'info'}`;
                liveEntry.innerHTML = `<span class="log-timestamp">[${new Date().toLocaleTimeString()}]</span> [${category}] ${data.message}`;
                liveTerminalOutput.appendChild(liveEntry);
                liveTerminalOutput.scrollTop = liveTerminalOutput.scrollHeight;
            }
        }

        // Special handling for error messages - show in both terminals
        if (category === 'error') {
            // Ensure error messages are visible in Live Terminal too
            if (liveTerminalOutput) {
                const errorEntry = document.createElement('div');
                errorEntry.className = 'log-entry log-error';
                errorEntry.innerHTML = `<span class="log-timestamp">[${new Date().toLocaleTimeString()}]</span> [ERROR] ${data.message}`;
                liveTerminalOutput.appendChild(errorEntry);
                liveTerminalOutput.scrollTop = liveTerminalOutput.scrollHeight;
            }
        }
    }

    // Log messages to terminal output
    function logToTerminal(level, message) {
        if (!terminalOutput) return;

        const logEntry = document.createElement('div');
        logEntry.className = `log-entry log-${level}`;
        logEntry.innerHTML = `<span class="log-timestamp">[${new Date().toLocaleTimeString()}]</span> ${message}`;

        terminalOutput.appendChild(logEntry);
        terminalOutput.scrollTop = terminalOutput.scrollHeight;
    }

    // Error displayDataStatusError
    function displayDataStatusError(error) {
        const dataStatusDiv = document.getElementById('data-status');
        dataStatusDiv.innerHTML = `
            <div class="status-item">
                <span style="color: #f44336;">Error loading data status</span>
                <span class="status-value">${error}</span>
            </div>
        `;
    }

    // Error displayRAGStatusError
    function displayRAGStatusError(error) {
        const ragStatusDiv = document.getElementById('rag-status');
        ragStatusDiv.innerHTML = `
            <div class="status-item">
                <span style="color: #f44336;">Error loading RAG status</span>
                <span class="status-value">${error}</span>
            </div>
        `;
    }

    // Utility functions
    function formatDate(dateString) {
        try {
            const date = new Date(dateString);
            return date.toLocaleString();
        } catch (e) {
            return dateString;
        }
    }

    // ============================================================================
    // CACHE MANAGEMENT FUNCTIONS (Cache-Phase-3 Integration)
    // ============================================================================

    // Load metadata cache on page entry (calls backend cache endpoint)
    async function loadMetadataCache() {
        try {
            logToTerminal('info', 'Loading metadata cache from backend...');

            // Use cache manager directly with sessionId
            const result = await cacheManager.initialize(currentRAGSessionId);

            logToTerminal('info', 'Metadata cache loaded successfully from backend');
            return true;
        } catch (error) {
            logToTerminal('error', `Failed to load metadata cache: ${error.message}`);
            return false;
        }
    }

    // Save metadata cache on page exit (calls backend cache endpoint)
    async function saveMetadataCache() {
        try {
            logToTerminal('info', 'Saving metadata cache to backend...');

            // Use cache manager directly with sessionId
            const result = await cacheManager.save(currentRAGSessionId);

            logToTerminal('info', 'Metadata cache saved successfully to backend');
            return true;
        } catch (error) {
            logToTerminal('error', `Failed to save metadata cache: ${error.message}`);
            return false;
        }
    }

    // Get cache status from backend
    async function getCacheStatus() {
        try {
            const status = await window.apiUtils.getGenerateCacheStatus(currentRAGSessionId);
            return status.cache_status;
        } catch (error) {
            logToTerminal('error', `Failed to get cache status: ${error.message}`);
            return null;
        }
    }

    // Display cache status in UI (for debugging)
    async function displayCacheStatus() {
        const status = await getCacheStatus();
        if (status) {
            const cachedTypes = status.cached_rag_types || [];
            const typesStr = Array.isArray(cachedTypes) ? cachedTypes.join(', ') : 'None';
            logToTerminal('info', `Cache Status - Loaded: ${status.cache_loaded}, Size: ${status.cache_size}, Types: ${typesStr}`);
        }
    }

    // ============================================================================
    // RAG TYPE CHANGE HANDLER
    // ============================================================================

    // Handle RAG type selection change
    async function handleRAGTypeChange(event) {
        const newRAGType = event.target.value;

        if (newRAGType && newRAGType !== currentRAGType) {

            // Invalidate cache for old RAG type
            cacheManager.remove(`data_status_${currentRAGType}`);
            cacheManager.remove(`rag_status_${currentRAGType}`);
            cacheManager.remove(`detailed_data_status_${currentRAGType}`);

            currentRAGType = newRAGType;
            cacheManager.setCurrentRAGType(newRAGType);

            logToTerminal('info', `RAG type changed to: ${newRAGType}`);

            // Force refresh status displays for new RAG type to ensure immediate update
            await loadDataStatus(true);  // forceFresh=true

            await loadRAGStatus(true);   // forceFresh=true


            // CRITICAL FIX: Check if new RAG type needs generation and update UI state accordingly
            // This ensures proper state transition from Completed to Ready when switching to "Need Generate" status
            const dataStatusCacheKey = `data_status_${currentRAGType}`;
            if (cacheManager.has(dataStatusCacheKey)) {
                const dataStatus = cacheManager.get(dataStatusCacheKey);

                // Check if data status indicates generation is needed by analyzing backend data
                const totalFiles = dataStatus.total_files || 0;
                const storageStatus = dataStatus.storage_status || 'empty';
                const comparisonData = dataStatus.comparison_data || {};
                const isUpToDate = comparisonData.is_up_to_date;

                // Determine if generation is needed based on backend logic
                let needsGeneration = false;
                if (totalFiles === 0) {
                    // No data files - no generation possible
                    needsGeneration = false;
                } else if (storageStatus === 'empty') {
                    // Data exists but no storage - generation needed
                    needsGeneration = true;
                } else if (isUpToDate === false) {
                    // Storage exists but data has changed - regeneration needed
                    needsGeneration = true;
                } else {
                    // Storage exists and is up to date
                    needsGeneration = false;
                }

                if (needsGeneration && !isGenerating) {
                    // Transition to Ready state when generation is needed
                    logToTerminal('info', `RAG type "${newRAGType}" needs generation - transitioning to Ready state`);
                    applyMVCStateStyling('ST_READY');
                    updateTerminalHeader('ST_READY', 0);
                    updateProgressBar(0);
                    updateRotatingIcon('ST_READY');

                    // CRITICAL FIX: Update button text to "Start RAG Generation" when generation is needed
                    updateGenerateButtonText('start');
                } else if (!needsGeneration && !isGenerating) {
                    // Data is up-to-date, maintain Completion state (don't change to Ready)
                    logToTerminal('info', `RAG type "${newRAGType}" is up-to-date - maintaining Completion state`);
                    applyMVCStateStyling('ST_COMPLETED');
                    updateTerminalHeader('ST_COMPLETED', 100);
                    updateProgressBar(100);
                    updateRotatingIcon('ST_COMPLETED');

                    // Keep completed button text
                    updateGenerateButtonText('completed');
                } else if (!isGenerating) {
                    // Default case: assume ready state for any other scenario
                    logToTerminal('info', `RAG type "${newRAGType}" - defaulting to Ready state`);
                    applyMVCStateStyling('ST_READY');
                    updateTerminalHeader('ST_READY', 0);
                    updateProgressBar(0);
                    updateRotatingIcon('ST_READY');
                    updateGenerateButtonText('start');
                }
            } else {
                // No cached data available - default to ready state
                logToTerminal('info', `RAG type "${newRAGType}" - no cached data, defaulting to Ready state`);
                applyMVCStateStyling('ST_READY');
                updateTerminalHeader('ST_READY', 0);
                updateProgressBar(0);
                updateRotatingIcon('ST_READY');
                updateGenerateButtonText('start');
            }

            // Reset detail views
            if (dataDetailView) {
                toggleDataDetailView();
            }
        }
    }

    // ============================================================================
    // BUTTON TEXT SYNCHRONIZATION FUNCTION
    // ============================================================================

    // Update generate button text based on data status
    function updateGenerateButtonText(mode) {
        const generateBtn = document.getElementById('generate-btn');
        if (!generateBtn) return;

        if (mode === 'start') {
            generateBtn.textContent = '🚀 Start RAG Generation';
        } else if (mode === 'completed') {
            generateBtn.textContent = '✅ Generation Complete - Generate Again';
        } else if (mode === 'retry') {
            generateBtn.textContent = '❌ Retry Generation';
        } else if (mode === 'generating') {
            generateBtn.textContent = '🔄 Generating...';
        }
    }

    // ============================================================================
    // DETAIL VIEW TOGGLE FUNCTIONS
    // ============================================================================

    // Toggle data detail view - switches between Summary and Detail modes
    function toggleDataDetailView() {
        const toggleBtn = document.getElementById('data-detail-toggle');

        dataDetailView = !dataDetailView;

        if (dataDetailView) {
            // Switch to Detail mode
            toggleBtn.classList.add('active');
            toggleBtn.textContent = '�'; // Different icon for detail mode

            // Load and display detailed data in the same div
            loadDetailedDataStatus();
        } else {
            // Switch to Summary mode
            toggleBtn.classList.remove('active');
            toggleBtn.textContent = '🔍';

            // Reload summary data in the same div
            loadDataStatus();
        }
    }

    // Storage Status has no detail toggle - only shows summary status

    // ============================================================================
    // DETAILED STATUS LOADING FUNCTIONS
    // ============================================================================

    // Load detailed data status (check cache first)
    async function loadDetailedDataStatus() {
        const cacheKey = `detailed_data_status_${currentRAGType}`;

        if (cacheManager.has(cacheKey)) {
            displayDetailedDataStatus(cacheManager.get(cacheKey));
            return;
        }

        try {
            const data = await window.apiUtils.getDetailedRAGDataStatus(currentRAGSessionId, currentRAGType);

            cacheManager.set(cacheKey, data);
            displayDetailedDataStatus(data);
        } catch (error) {
            logToTerminal('error', `Failed to load detailed data status: ${error.message}`);
            displayDetailedDataStatusError(error.message);
        }
    }



    // ============================================================================
    // DETAILED STATUS DISPLAY FUNCTIONS
    // ============================================================================

    // Display detailed data status in the same div as summary - switching mode
    function displayDetailedDataStatus(data) {
        const dataStatusDiv = document.getElementById('data-status');
        dataStatusDiv.innerHTML = '';

        // Add a header showing we're in detail mode
        const detailHeader = document.createElement('div');
        detailHeader.style.fontSize = '12px';
        detailHeader.style.fontWeight = 'bold';
        detailHeader.style.marginBottom = '8px';
        detailHeader.style.color = '#666';
        // FIX: Use correct backend field names
        detailHeader.textContent = `Detail View: ${data.total_files || 0} files`;
        dataStatusDiv.appendChild(detailHeader);

        // Create table for detail view (no header row as specified)
        const detailTable = document.createElement('table');
        detailTable.style.width = '100%';
        detailTable.style.borderCollapse = 'collapse';
        detailTable.style.fontSize = '12px'; // Small font size as specified
        detailTable.style.maxHeight = '300px'; // Add scroll capability
        detailTable.style.overflowY = 'auto';
        detailTable.style.display = 'block';

        // FIX: Use correct backend field names for files array
        if (data.data_files && data.data_files.length > 0) {
            data.data_files.forEach(file => {
                const row = detailTable.insertRow();

                // Column 1: filename (truncated to fit)
                const filenameCell = row.insertCell(0);
                // FIX: Use correct backend field name for filename
                const fullFilename = file.name || 'Unknown';
                const truncatedFilename = fullFilename.length > 30 ? fullFilename.substring(0, 30) + '...' : fullFilename;
                filenameCell.textContent = truncatedFilename;
                filenameCell.style.padding = '2px 4px';
                filenameCell.style.fontFamily = 'monospace';
                filenameCell.title = fullFilename; // Show full name on hover
                filenameCell.style.borderBottom = '1px solid #eee';

                // Column 2: file modified date (no time) + file size
                const detailsCell = row.insertCell(1);
                // FIX: Use correct backend field names
                const modifiedDate = formatDateNoTime(file.modified || '');
                const fileSize = formatFileSize(file.size || 0);
                detailsCell.textContent = `${modifiedDate} + ${fileSize}`;
                detailsCell.style.padding = '2px 4px';
                detailsCell.style.textAlign = 'right';
                detailsCell.style.fontFamily = 'monospace';
                detailsCell.style.borderBottom = '1px solid #eee';
            });
        } else {
            const row = detailTable.insertRow();
            const cell = row.insertCell(0);
            cell.colSpan = 2;
            cell.textContent = 'No files found';
            cell.style.padding = '2px 4px';
            cell.style.textAlign = 'center';
            cell.style.color = '#888';
        }

        dataStatusDiv.appendChild(detailTable);
    }



    // ============================================================================
    // ERROR HANDLING FOR DETAILED VIEWS
    // ============================================================================

    // Error display for detailed data status - works with switching logic
    function displayDetailedDataStatusError(error) {
        const dataStatusDiv = document.getElementById('data-status');
        dataStatusDiv.innerHTML = `
            <div style="color: #f44336; font-size: 12px; padding: 8px;">
                Error loading detailed data status: ${error}
            </div>
        `;
    }



    // ============================================================================
    // UTILITY FUNCTIONS FOR DETAILED VIEWS
    // ============================================================================

    // Format file size for display
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    // Format date for detail view (shorter format)
    function formatDateForDetail(dateString) {
        try {
            const date = new Date(dateString);
            return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } catch (e) {
            return dateString;
        }
    }

    // Format date without time (for detail status as specified)
    function formatDateNoTime(dateString) {
        try {
            const date = new Date(dateString);
            return date.toLocaleDateString(); // Only date, no time
        } catch (e) {
            return dateString;
        }
    }

    // ============================================================================
    // TEST WEBSOCKET FUNCTION
    // ============================================================================

    // Handle test WebSocket button click
    function handleTestWebSocket() {
        // Check if WebSocket is already connected
        if (websocket && websocket.readyState === WebSocket.OPEN) {
            // Send a test progress message
            const testMessage = {
                type: 'progress',
                state: 'ST_PARSER',
                progress: 25,
                message: 'Test WebSocket message - Parser Progress',
                timestamp: new Date().toISOString()
            };
            websocket.send(JSON.stringify(testMessage));
            logToTerminal('info', 'Sent test WebSocket message');
        } else {
            logToTerminal('info', 'Connecting to WebSocket for test...');
            connectTerminalWebSocket();

            // Wait a bit for connection, then send test message
            setTimeout(() => {
                if (websocket && websocket.readyState === WebSocket.OPEN) {
                    const testMessage = {
                        type: 'progress',
                        state: 'ST_PARSER',
                        progress: 25,
                        message: 'Test WebSocket message after connection',
                        timestamp: new Date().toISOString()
                    };
                    websocket.send(JSON.stringify(testMessage));
                    logToTerminal('info', 'Sent test WebSocket message after connection');
                } else {
                    logToTerminal('error', 'Failed to connect WebSocket for test');
                }
            }, 2000);
        }
    }

    // ============================================================================
    // CLEANUP ON PAGE UNLOAD
    // ============================================================================

    // Cleanup on page unload
    window.addEventListener('beforeunload', async () => {
        // Save metadata cache before leaving (Cache-Phase-3)
        await saveMetadataCache();

        if (statusPollingInterval) {
            clearTimeout(statusPollingInterval);
        }
        if (logPollingInterval) {
            clearInterval(logPollingInterval);
        }
    });
});
