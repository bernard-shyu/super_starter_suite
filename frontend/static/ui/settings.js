/**
 * Configuration Management UI for Super Starter Suite
 *
 * This file contains the JavaScript code for the configuration management UI.
 * It handles loading, displaying, and saving configuration settings.
 */

// Utility functions for better code organization
function getRequiredElement(selector, context = document) {
    const element = context.querySelector(selector);
    if (!element) {
        throw new Error(`Required element not found: ${selector}`);
    }
    return element;
}

function getOptionalElement(selector, context = document) {
    return context.querySelector(selector);
}

function getInputValue(input) {
    return input && input.value ? input.value.trim() : null;
}

function isValidInput(value) {
    return value && value.length > 0;
}

function createSelectOptions(items, selectedValue = null) {
    return items.map(item =>
        `<option value="${item}" ${selectedValue === item ? 'selected' : ''}>${item}</option>`
    ).join('');
}

async function apiRequest(endpoint, options = {}) {
    try {
        const response = await fetch(endpoint, options);
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`API request failed: ${response.status} - ${errorText}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`API request to ${endpoint} failed:`, error);
        throw error;
    }
}

function updateNestedConfig(baseConfig, path, value) {
    const keys = path.split('.');
    const result = { ...baseConfig };
    let current = result;

    for (let i = 0; i < keys.length - 1; i++) {
        current[keys[i]] = { ...current[keys[i]] };
        current = current[keys[i]];
    }

    current[keys[keys.length - 1]] = value;
    return result;
}

// Global variables
let currentConfig = {};
let currentSettings = {};
let currentUserId = 'anonymous';

// DOM elements - these will be set during initialization
let configContainer;
let settingsContainer;
let saveConfigBtn;
let saveSettingsBtn;
let userSelect;

// Initialize the UI
async function initConfigUI(containerElement) {

    // Ensure configContainer is defined to avoid errors in updateUI
    configContainer = document.createElement('div');
    configContainer.id = 'dummy-config-container';

    // Use the provided container element
    settingsContainer = containerElement;

    // Mark as initialized (specific to settings UI)
    settingsContainer.setAttribute('data-config-ui-initialized', 'true');

    // Create the complete DOM structure directly in the provided container
    const htmlContent = `
        <div id="settings-panel" class="config-panel"></div>
        <div class="save-button-container">
            <button id="save-settings-btn" class="config-button">Save Settings</button>
        </div>
    `;
    settingsContainer.innerHTML = htmlContent;

    // Get DOM elements from the container with error checking
    const settingsPanel = getRequiredElement('#settings-panel', settingsContainer);
    saveSettingsBtn = getRequiredElement('#save-settings-btn', settingsContainer);
    userSelect = getOptionalElement('#user-select', settingsContainer);

    // Assign settingsPanel to settingsContainer for consistency
    settingsContainer = settingsPanel;

    try {
        // Load current user state
        const userState = await apiRequest('/api/user_state');
        currentUserId = userState.current_user || 'anonymous';

        // Load configurations
        await loadConfigurations();

        // Set up event listeners
        setupEventListeners();

        // Update UI
        updateUI();
        return true;
    } catch (error) {
        console.error('[DEBUG:initConfigUI] Error initializing config UI:', error);
        console.error('[DEBUG:initConfigUI] Full error details:', error.stack);
        showError(`Failed to initialize configuration UI: ${error.message}`);
        return false;
    }
}

// Load configurations from server
async function loadConfigurations() {
    try {
        // Load system config
        currentConfig = await apiRequest('/api/system/config');

        // Load user settings
        currentSettings = await apiRequest(`/api/system/settings`);
    } catch (error) {
        console.error('Error loading configurations:', error);
        throw error;
    }
}

// Set up event listeners
function setupEventListeners() {
    // Save Settings Button
    if (saveSettingsBtn) {
        saveSettingsBtn.addEventListener('click', saveSettings);
    }
}

// Update UI with current configurations
function updateUI() {
    // Additional verification with more detailed error message
    if (!configContainer || !settingsContainer || !saveSettingsBtn) {
        console.error('Required DOM elements not found during UI update:',
            {
                configContainer: !!configContainer,
                settingsContainer: !!settingsContainer,
                saveSettingsBtn: !!saveSettingsBtn
            });

        // Additional debugging information
        console.log('Container innerHTML:', configContainer?.parentElement?.innerHTML);
        console.log('All child elements:', configContainer?.parentElement?.children);
        console.log('All elements with IDs:', configContainer?.parentElement?.querySelectorAll('[id]'));

        throw new Error('Required DOM elements not found during UI update');
    }

    // Clear system config container for user settings mode
    if (configContainer) {
        configContainer.innerHTML = '';
        configContainer.style.display = 'none';
    }

    // Render user settings only
    renderUserSettings();

    // Initialize AI parser section visibility after rendering
    setTimeout(() => {
        toggleAIParserSection();
        // Initialize directory selector after rendering
        addDirectorySelector();
    }, 100);
}



// Render system configuration
function renderSystemConfig() {
    if (!configContainer) {
        console.error('Config container not found');
        throw new Error('Config container not found');
    }



    // Create Generation Methods section with read-only list display
    let generateMethodsList = '<div>Loading generation methods...</div>';
    if (currentConfig.SYSTEM?.GENERATE_METHODS && currentConfig.SYSTEM.GENERATE_METHODS.length > 0) {
        const generateMethodsOptions = currentConfig.SYSTEM.GENERATE_METHODS.map(method =>
            `<option value="${method}">${method}</option>`
        ).join('');

        generateMethodsList = `
            <select class="config-select" size="4" disabled style="width: 100%; height: 100px;">
                ${generateMethodsOptions}
            </select>
        `;
    } else {
        console.error('No generation methods available in system config');
    }



    // Create Chatbot Models section with single list box (read-only)
    let chatbotModelsList = '<div>Loading chatbot models...</div>';
    if (currentConfig.AI_MODELS_AVAILABLE?.CHATBOT && currentConfig.AI_MODELS_AVAILABLE.CHATBOT.length > 0) {
        const chatbotModelOptions = currentConfig.AI_MODELS_AVAILABLE.CHATBOT.map(model =>
            `<option value="${model.ID}">${model.PROVIDER}: ${model.ID}</option>`
        ).join('');

        chatbotModelsList = `
            <select class="config-select" size="10" disabled style="width: 100%; height: 200px;">
                ${chatbotModelOptions}
            </select>
        `;
    } else {
        console.error('No chatbot models available in system config');
    }

    // Create GENERATE_AI_METHOD section with editable controls
    let generateAIMethodEditor = '<div>Loading AI method configurations...</div>';
    if (currentConfig.GENERATE_AI_METHOD) {
        const nvidiaModel = currentConfig.GENERATE_AI_METHOD.NvidiaAI_SELECTED_MODEL || '';
        const geminiModel = currentConfig.GENERATE_AI_METHOD.GeminiAI_SELECTED_MODEL || '';

        generateAIMethodEditor = `
            <div class="config-item">
                <h3>GeminiAI Parser Model Selection</h3>
                <input type="text" value="${geminiModel}" class="config-input" data-method="GeminiAI" data-field="SELECTED_MODEL" placeholder="Enter GeminiAI model ID">
            </div>

            <div class="config-item">
                <h3>NvidiaAI Parser Model Selection</h3>
                <input type="text" value="${nvidiaModel}" class="config-input" data-method="NvidiaAI" data-field="SELECTED_MODEL" placeholder="Enter NvidiaAI model ID">
            </div>
        `;

    } else {
        console.error('No GENERATE_AI_METHOD configurations in system config');
    }

    configContainer.innerHTML = `
        <h1>System Configuration</h1>

        <div class="config-section">
            <h2>Generation Methods</h2>
            <div class="config-item">
                <h3>Available Methods</h3>
                ${generateMethodsList}
            </div>

            <div class="config-item">
                <h3>GeminiAI Parser Model Selection</h3>
                <select class="config-select" data-method="GeminiAI" data-field="SELECTED_MODEL">
                    <option value="">Select GeminiAI model...</option>
                    ${currentConfig.AI_MODELS_AVAILABLE?.AI_PARSERS?.filter(model => model.GEN_METHOD === 'GeminiAI').map(model => {
        const isSelected = currentConfig.GENERATE_AI_METHOD?.GeminiAI_SELECTED_MODEL === model.ID;
        return `<option value="${model.ID}" ${isSelected ? 'selected' : ''}>${model.ID}</option>`;
    }).join('') || '<option value="">No GeminiAI models available</option>'}
                </select>
            </div>

            <div class="config-item">
                <h3>NvidiaAI Parser Model Selection</h3>
                <select class="config-select" data-method="NvidiaAI" data-field="SELECTED_MODEL">
                    <option value="">Select NvidiaAI model...</option>
                    ${currentConfig.AI_MODELS_AVAILABLE?.AI_PARSERS?.filter(model => model.GEN_METHOD === 'NvidiaAI').map(model => {
        const isSelected = currentConfig.GENERATE_AI_METHOD?.NvidiaAI_SELECTED_MODEL === model.ID;
        return `<option value="${model.ID}" ${isSelected ? 'selected' : ''}>${model.ID}</option>`;
    }).join('') || '<option value="">No NvidiaAI models available</option>'}
                </select>
            </div>
        </div>

        <div class="config-section">
            <h2>Model Parameters</h2>
            <div class="config-item">
                <h3>AI Parser Parameters</h3>
                <div class="params-container">
                    <div class="param-input">
                        <label>temperature:</label>
                        <input type="text" value="${currentConfig.MODEL_PARAMETERS?.AI_PARSER_PARAMS?.temperature || '0.1'}" class="param-value">
                    </div>
                    <div class="param-input">
                        <label>top_p:</label>
                        <input type="text" value="${currentConfig.MODEL_PARAMETERS?.AI_PARSER_PARAMS?.top_p || '1.0'}" class="param-value">
                    </div>
                </div>
            </div>

            <div class="config-item">
                <h3>Chatbot LLM Parameters</h3>
                <div class="params-container">
                    <div class="param-input">
                        <label>temperature:</label>
                        <input type="text" value="${currentConfig.MODEL_PARAMETERS?.CHATBOT_LLM_PARAMS?.temperature || '0.2'}" class="param-value">
                    </div>
                    <div class="param-input">
                        <label>top_k:</label>
                        <input type="text" value="${currentConfig.MODEL_PARAMETERS?.CHATBOT_LLM_PARAMS?.top_k || '40'}" class="param-value">
                    </div>
                </div>
            </div>
        </div>

        <div class="config-section">
            <h2>Available AI Models List</h2>

            <div class="config-item">
                <h3>GeminiAI Generate Parser Models List</h3>
                <select class="config-select" size="6" disabled style="width: 100%; height: 150px;">
                    ${currentConfig.AI_MODELS_AVAILABLE?.AI_PARSERS?.filter(model => model.GEN_METHOD === 'GeminiAI').map(model => `<option value="${model.ID}">${model.ID}</option>`).join('') || '<option>No GeminiAI models available</option>'}
                </select>
            </div>

            <div class="config-item">
                <h3>NvidiaAI Generate Parser Models List</h3>
                <select class="config-select" size="6" disabled style="width: 100%; height: 150px;">
                    ${currentConfig.AI_MODELS_AVAILABLE?.AI_PARSERS?.filter(model => model.GEN_METHOD === 'NvidiaAI').map(model => `<option value="${model.ID}">${model.ID}</option>`).join('') || '<option>No NvidiaAI models available</option>'}
                </select>
            </div>

            <div class="config-item">
                <h3>Chatbot LLM Models List</h3>
                ${chatbotModelsList}
            </div>
        </div>
    `;
}

// Add directory selection functionality
function addDirectorySelector() {
    const selectBtn = document.getElementById('select-rag-root-btn');
    if (!selectBtn) return;

    selectBtn.addEventListener('click', () => {
        // Get the input field for setting the selected path
        const ragRootInput = document.getElementById('rag-root-input');

        // Create a file input element for directory selection
        const input = document.createElement('input');
        input.type = 'file';
        input.webkitdirectory = true;
        input.directory = true;
        input.multiple = false;

        input.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                const firstFile = e.target.files[0];
                let directoryPath = '';

                // Try different methods to get directory path
                if (firstFile.path) {
                    // Direct path (available in some browsers like Electron)
                    directoryPath = firstFile.path;
                } else if (firstFile.webkitRelativePath) {
                    // WebKit relative path
                    const fullPath = firstFile.webkitRelativePath;
                    directoryPath = fullPath.substring(0, fullPath.lastIndexOf('/'));
                } else {
                    // Fallback: just use the directory name
                    directoryPath = firstFile.name;
                }

                // Set the input value to the selected directory path
                if (ragRootInput && directoryPath) {
                    ragRootInput.value = directoryPath;
                }
            }
        });

        // Open the directory selection dialog
        input.click();
    });
}

// Render user settings
function renderUserSettings() {
    if (!settingsContainer) {
        console.error('Settings container not found');
        throw new Error('Settings container not found');
    }

    // Create theme select with available themes from API
    let themeOptions = '<option value="">Loading theme options...</option>';

    // Load theme options asynchronously
    function loadThemeOptions() {
        const currentTheme = currentSettings.USER_PREFERENCES?.THEME || 'light_classic';
        const availableThemes = ["light_classic", "dark_classic", "green_classic", "blue_classic", "purple_classic",
            "light_modern", "dark_modern", "green_modern", "blue_modern", "purple_modern"];

        themeOptions = availableThemes.map(theme => {
            const isSelected = theme === currentTheme;
            // Format theme name for display (e.g., "light_classic" -> "Light Classic")
            const displayName = theme.split('_').map(word =>
                word.charAt(0).toUpperCase() + word.slice(1)
            ).join(' ');
            return `<option value="${theme}" ${isSelected ? 'selected' : ''}>${displayName}</option>`;
        }).join('');

        // Update theme select if it exists
        const themeSelect = document.getElementById('theme-select');
        if (themeSelect) {
            themeSelect.innerHTML = themeOptions;
        }
    }

    // Initialize theme options when settings are loaded
    setTimeout(() => {
        loadThemeOptions();

        // Add theme change listener
        const themeSelect = document.getElementById('theme-select');
        if (themeSelect) {
            themeSelect.addEventListener('change', async (event) => {
                const selectedTheme = event.target.value;
                if (selectedTheme && window.mainUIManager && window.mainUIManager.switchTheme) {
                    const success = await window.mainUIManager.switchTheme(selectedTheme);
                    if (success) {
                        // Update current theme variable
                        if (window.getCurrentTheme) {
                            window.getCurrentTheme = () => selectedTheme;
                        }
                    } else {
                        console.error('Failed to switch theme to:', selectedTheme);
                        // Reset dropdown to current theme
                        const currentTheme = window.getCurrentTheme ? window.getCurrentTheme() : 'light_classic';
                        event.target.value = currentTheme;
                    }
                }
            });
        }
    }, 100);

    // Create RAG Types section with dynamic input
    let ragTypesEditor = '<div>Loading RAG types...</div>';
    if (currentSettings.USER_PREFERENCES?.RAG_TYPES && currentSettings.USER_PREFERENCES.RAG_TYPES.length > 0) {
        const ragTypesItems = currentSettings.USER_PREFERENCES.RAG_TYPES.map((type, index) =>
            `<div class="array-item" data-index="${index}">
                <input type="text" value="${type}" class="array-input" data-section="RAG_TYPES" data-index="${index}">
                <button type="button" class="array-remove-btn" onclick="removeArrayItem('RAG_TYPES', ${index})">-</button>
            </div>`
        ).join('');

        ragTypesEditor = `
            <div class="array-editor">
                <div class="array-items" id="rag-types-items">
                    ${ragTypesItems}
                </div>
                <button type="button" class="array-add-btn" onclick="addArrayItem('RAG_TYPES')">+ Add RAG Type</button>
            </div>
        `;
    } else {
        console.error('No RAG types available in user preferences');
    }

    // Create RAG root input with enhanced debugging
    let ragRootValue = 'Loading RAG root...';
    try {
        if (currentSettings && currentSettings.USER_PREFERENCES) {
            if (currentSettings.USER_PREFERENCES.USER_RAG_ROOT) {
                ragRootValue = currentSettings.USER_PREFERENCES.USER_RAG_ROOT;
            } else {
                console.warn('USER_RAG_ROOT not found in USER_PREFERENCES');
                ragRootValue = '';
            }
        } else {
            console.error('USER_PREFERENCES not found in currentSettings', Object.keys(currentSettings || {}));
            ragRootValue = 'Error loading RAG root';
        }
    } catch (error) {
        console.error('Error processing RAG root value:', error);
        ragRootValue = `Error: ${error.message}`;
    }

    // Create generation method select with enhanced debugging
    let generateMethodOptions = '<option value="">Loading generation methods...</option>';
    try {
        // Check for the correct structure in config for available methods
        // The API returns raw system config, so we need to access it directly
        if (currentConfig && currentConfig.SYSTEM && Array.isArray(currentConfig.SYSTEM.GENERATE_METHODS)) {
            if (currentConfig.SYSTEM.GENERATE_METHODS.length > 0) {
                generateMethodOptions = currentConfig.SYSTEM.GENERATE_METHODS.map(method => {
                    // Check current selection from user settings
                    let isSelected = false;
                    let currentMethod = '';

                    if (currentSettings && typeof currentSettings === 'object') {
                        if (currentSettings.GENERATE && currentSettings.GENERATE.METHOD) {
                            currentMethod = currentSettings.GENERATE.METHOD;
                            isSelected = currentMethod === method;
                        }
                    }

                    return `<option value="${method}" ${isSelected ? 'selected' : ''}>${method}</option>`;
                }).join('');
            } else {
                generateMethodOptions = '<option value="">No generation methods available</option>';
            }
        } else {
            console.error('SYSTEM.GENERATE_METHODS not found or not an array');
            generateMethodOptions = '<option value="">Error: Config structure issue</option>';
        }
    } catch (error) {
        console.error('Error loading generation methods:', error);
        generateMethodOptions = `<option value="">Error: ${error.message}</option>`;
    }

    // Dynamic AI parser settings - Display actual selected models and parameters from system config
    let aiParserSections = '<div class="config-info">Loading AI configuration...</div>';

    try {
        // Build dynamic configuration display from system config
        let configDetails = '<div class="config-info">';
        configDetails += '<p><strong>Note:</strong> AI method configurations (NvidiaAI, GeminiAI) are managed at the system level.</p>';
        configDetails += '<p>Current configuration from system_config.toml:</p>';

        if (currentConfig && currentConfig.GENERATE_AI_METHOD) {
            configDetails += '<ul style="text-align: left; margin: 10px 0;">';

            // Display NvidiaAI selected model
            const nvidiaModel = currentConfig.GENERATE_AI_METHOD.NvidiaAI_SELECTED_MODEL;
            if (nvidiaModel) {
                configDetails += `<li><strong>NvidiaAI Model:</strong> ${nvidiaModel}</li>`;
            }

            // Display GeminiAI selected model
            const geminiModel = currentConfig.GENERATE_AI_METHOD.GeminiAI_SELECTED_MODEL;
            if (geminiModel) {
                configDetails += `<li><strong>GeminiAI Model:</strong> ${geminiModel}</li>`;
            }

            configDetails += '</ul>';
        }

        if (currentConfig && currentConfig.MODEL_PARAMETERS && currentConfig.MODEL_PARAMETERS.AI_PARSER_PARAMS) {
            configDetails += '<p><strong>AI Parser Parameters:</strong></p>';
            configDetails += '<ul style="text-align: left; margin: 10px 0;">';

            const params = currentConfig.MODEL_PARAMETERS.AI_PARSER_PARAMS;
            if (params.temperature !== undefined) {
                configDetails += `<li><strong>Temperature:</strong> ${params.temperature}</li>`;
            }
            if (params.top_p !== undefined) {
                configDetails += `<li><strong>Top P:</strong> ${params.top_p}</li>`;
            }

            configDetails += '</ul>';
        }

        configDetails += '<p>Model selection and parameters are configured in system_config.toml and handled by administrators.</p>';
        configDetails += '</div>';

        aiParserSections = configDetails;
    } catch (error) {
        console.error('Error building AI configuration display:', error);
        aiParserSections = `
            <div class="config-info">
                <p><strong>Note:</strong> AI method configurations (NvidiaAI, GeminiAI) are managed at the system level.</p>
                <p>Model selection and parameters are configured in system_config.toml and handled by administrators.</p>
                <p><em>Error loading current configuration details.</em></p>
            </div>
        `;
    }

    // Create 2-level chatbot model selection
    let chatbotModelSelectionUI = `
        <div class="model-selection-container">
            <div class="model-selection-row">
                <label>Model Source:</label>
                <select id="model-source-select" class="config-input">
                    <option value="system">SystemConfig models</option>
                    <option value="nvidia">NVIDIA models</option>
                    <option value="OpenRouter">OpenRouter models</option>
                    <option value="azureAI">Azure models</option>
                </select>
            </div>
            <div class="model-selection-row" style="margin-top: 10px;">
                <label>Selected Model:</label>
                <select id="model-id-select" class="config-input">
                    <option value="">Loading models...</option>
                </select>
            </div>
        </div>
    `;

    // Function to populate model ID dropdown
    const populateModelIDs = async (source, selectedID = null) => {
        const idSelect = document.getElementById('model-id-select');
        if (!idSelect) return;

        idSelect.innerHTML = '<option value="">Loading models...</option>';
        try {
            const data = await apiRequest(`/api/system/models/list?source=${source}`);
            const models = data.models || [];

            if (models.length === 0) {
                idSelect.innerHTML = `<option value="">No models found for ${source}</option>`;
                if (data.warning) console.warn(data.warning);
                return;
            }

            idSelect.innerHTML = models.map(m => {
                let text = m.id;
                if (source === 'system') text = `${m.PROVIDER}: ${m.ID}`;
                else if (source === 'OpenRouter' || source === 'azureAI') text = m.name || m.id;

                const val = (source === 'system') ? `${m.PROVIDER}:${m.ID}` : `${source}:${m.id}`;
                const isSel = (selectedID === val || selectedID === m.id);
                return `<option value="${val}" ${isSel ? 'selected' : ''}>${text}</option>`;
            }).join('');
        } catch (err) {
            idSelect.innerHTML = '<option value="">Error fetching models</option>';
        }
    };

    // Initialize 2-level lookup after rendering
    setTimeout(() => {
        const sourceSelect = document.getElementById('model-source-select');
        const idSelect = document.getElementById('model-id-select');

        if (sourceSelect) {
            // Determine initial source from current settings
            let initialSource = 'system';
            let initialID = null;
            if (currentSettings.CHATBOT_AI_MODEL?.SELECTED) {
                const sel = currentSettings.CHATBOT_AI_MODEL.SELECTED;
                initialID = sel.ID;
                const prov = sel.PROVIDER?.toLowerCase();
                if (prov === 'nvidia') initialSource = 'nvidia';
                else if (prov === 'openrouter') initialSource = 'OpenRouter';
                else if (prov === 'azureai' || prov === 'azure') initialSource = 'azureAI';
            }

            sourceSelect.value = initialSource;
            populateModelIDs(initialSource, initialID);

            sourceSelect.onchange = (e) => populateModelIDs(e.target.value);
        }
    }, 100);

    // Create workflow RAG type mapping with tabular layout
    let workflowRagTypeOptions = '<div>Loading workflow RAG type mappings...</div>';
    try {
        if (currentSettings && currentSettings.WORKFLOW_RAG_TYPE) {
            if (Object.keys(currentSettings.WORKFLOW_RAG_TYPE).length > 0) {
                // Create table header
                let tableHeader = `
                    <div class="config-table-header">
                        <div class="config-table-cell workflow-label">Workflow</div>
                        <div class="config-table-cell rag-type-select">RAG Type</div>
                    </div>
                `;

                // Create table rows
                let tableRows = Object.entries(currentSettings.WORKFLOW_RAG_TYPE).map(([workflow, ragType]) => {
                    let selectOrWarning = '<div class="rag-type-select">Loading RAG types...</div>';

                    // Check for the correct structure in user preferences (RAG_TYPES moved from system config to user preferences)
                    if (currentSettings && currentSettings.USER_PREFERENCES && currentSettings.USER_PREFERENCES.RAG_TYPES) {
                        const availableRagTypes = currentSettings.USER_PREFERENCES.RAG_TYPES;

                        // Check if current workflow ragType is still valid
                        if (ragType && !availableRagTypes.includes(ragType)) {
                            // Show red warning text for removed RAG type
                            selectOrWarning = `
                                <div class="config-table-cell rag-type-select">
                                    <span class="text-error" style="font-weight: 600;">${ragType} is removed</span>
                                </div>
                            `;
                        } else {
                            // Show normal select dropdown for valid RAG types
                            let typeOptions = '<option value="">Select RAG type...</option>';

                            if (availableRagTypes.length > 0) {
                                typeOptions = availableRagTypes.map(type => {
                                    const isSelected = ragType === type;
                                    return `<option value="${type}" ${isSelected ? 'selected' : ''}>${type}</option>`;
                                }).join('');
                            } else {
                                typeOptions = '<option value="">No RAG types available</option>';
                            }

                            selectOrWarning = `
                                <select class="config-select" data-workflow="${workflow}">
                                    ${typeOptions}
                                </select>
                            `;
                        }
                    } else {
                        console.error('RAG_TYPES not found in user preferences');
                        selectOrWarning = '<span class="text-error">Error loading RAG types</span>';
                    }

                    return `
                        <div class="config-table-row">
                            <div class="config-table-cell workflow-label">${workflow}:</div>
                            <div class="config-table-cell rag-type-select">
                                ${selectOrWarning}
                            </div>
                        </div>
                    `;
                }).join('');

                workflowRagTypeOptions = `
                    <div class="config-table">
                        ${tableHeader}
                        ${tableRows}
                    </div>
                `;
            } else {
                workflowRagTypeOptions = '<div>No workflow RAG type mappings available</div>';
            }
        } else {
            workflowRagTypeOptions = '<div>Error loading workflow RAG type mappings</div>';
        }
    } catch (error) {
        console.error('Error loading workflow RAG type mappings:', error);
        workflowRagTypeOptions = `<div>Error: ${error.message}</div>`;
    }

    settingsContainer.innerHTML = `
            <h1>Settings for user (${currentUserId})</h1>
            <div class="config-section">
                <h2>User Preferences</h2>
                <div class="config-item">
                    <h3>Theme</h3>
                    <select id="theme-select" class="config-input">
                        ${themeOptions}
                    </select>
                </div>
                <div class="config-item">
                    <h3>RAG Types:</h3>
                    ${ragTypesEditor}
                </div>
                <div class="config-item">
                    <h3>User RAG Root:</h3>
                    <div style="display: flex; align-items: center;">
                        <input type="text" id="rag-root-input" class="config-input"
                            value="${ragRootValue}" style="flex-grow: 1;">
                        <button type="button" id="select-rag-root-btn" class="config-button" style="margin-left: 10px;" title="Select Directory">
                            <img src="/static/assets/icons/config.png" alt="Select Directory" style="width: 16px; height: 16px;">
                        </button>
                    </div>
                </div>
            </div>
            <div class="config-section">
                <h2>Generation Settings</h2>
                <div class="config-item">
                    <h3>Method</h3>
                    <select id="generate-method-select" class="config-input" onchange="toggleAIParserSection()">
                        ${generateMethodOptions}
                    </select>
                </div>
                <div id="ai-parser-section" style="display: none;">
                    ${aiParserSections}
                </div>
            </div>
            <div class="config-section">
                <h2>Chatbot AI Model</h2>
                <div class="config-item">
                    <h3>Selected Model</h3>
                    ${chatbotModelSelectionUI}
                </div>
            </div>
            <div class="config-section">
                <h2>Workflow RAG Type Mapping</h2>
                ${workflowRagTypeOptions}
            </div>
        `;
}

// Save configuration changes
async function saveConfiguration() {
    console.log('Saving system configuration changes');

    // Add confirmation prompt
    if (window.showConfirm) {
        const confirmed = await window.showConfirm(
            'Save Configuration',
            'Are you sure you want to save these system configuration changes? This will affect all users.',
            { type: 'acceptReject', confirmText: 'Accept', cancelText: 'Reject' }
        );
        if (!confirmed) return;
    }

    try {
        // Collect all the system configuration changes
        const updatedConfig = { ...currentConfig };

        // Update GENERATE_AI_METHOD section with new flat structure
        if (!updatedConfig.GENERATE_AI_METHOD) {
            updatedConfig.GENERATE_AI_METHOD = {};
        }

        // Get NvidiaAI model selection
        const nvidiaInput = document.querySelector('input[data-method="NvidiaAI"][data-field="SELECTED_MODEL"]');
        if (nvidiaInput && nvidiaInput.value.trim()) {
            updatedConfig.GENERATE_AI_METHOD.NvidiaAI_SELECTED_MODEL = nvidiaInput.value.trim();
        }

        // Get GeminiAI model selection
        const geminiInput = document.querySelector('input[data-method="GeminiAI"][data-field="SELECTED_MODEL"]');
        if (geminiInput && geminiInput.value.trim()) {
            updatedConfig.GENERATE_AI_METHOD.GeminiAI_SELECTED_MODEL = geminiInput.value.trim();
        }

        // Update MODEL_PARAMETERS section
        if (!updatedConfig.MODEL_PARAMETERS) {
            updatedConfig.MODEL_PARAMETERS = {};
        }

        // Get AI Parser parameters
        const aiParserTempInput = document.querySelector('input[data-method="NvidiaAI"][data-param="temperature"]');
        const aiParserTopPInput = document.querySelector('input[data-method="NvidiaAI"][data-param="top_p"]');

        if (aiParserTempInput?.value.trim() || aiParserTopPInput?.value.trim()) {
            const aiParserParams = {};
            if (aiParserTempInput?.value.trim()) {
                aiParserParams.temperature = parseFloat(aiParserTempInput.value.trim());
            }
            if (aiParserTopPInput?.value.trim()) {
                aiParserParams.top_p = parseFloat(aiParserTopPInput.value.trim());
            }
            if (Object.keys(aiParserParams).length > 0) {
                updatedConfig.MODEL_PARAMETERS.AI_PARSER_PARAMS = aiParserParams;
            }
        }

        // Get Chatbot LLM parameters
        const chatbotTempInput = document.querySelector('input[data-method="GeminiAI"][data-param="temperature"]');
        const chatbotTopKInput = document.querySelector('input[data-method="GeminiAI"][data-param="top_k"]');

        if (chatbotTempInput?.value.trim() || chatbotTopKInput?.value.trim()) {
            const chatbotParams = {};
            if (chatbotTempInput?.value.trim()) {
                chatbotParams.temperature = parseFloat(chatbotTempInput.value.trim());
            }
            if (chatbotTopKInput?.value.trim()) {
                chatbotParams.top_k = parseFloat(chatbotTopKInput.value.trim());
            }
            if (Object.keys(chatbotParams).length > 0) {
                updatedConfig.MODEL_PARAMETERS.CHATBOT_LLM_PARAMS = chatbotParams;
            }
        }

        // Update AI parser settings for all AI methods
        const aiMethods = document.querySelectorAll('.ai-method-section');
        aiMethods.forEach(section => {
            const method = section.getAttribute('id').replace('ai-method-', '');
            const modelSelect = section.querySelector('.ai-model-select');
            const selectedModelId = modelSelect.value;

            if (!updatedConfig.GENERATE) {
                updatedConfig.GENERATE = {};
            }
            if (!updatedConfig.GENERATE[method]) {
                updatedConfig.GENERATE[method] = {};
            }
            updatedConfig.GENERATE[method].SELECTED_MODEL = selectedModelId;

            const paramInputs = section.querySelectorAll('.param-value');
            if (paramInputs.length > 0) {
                // Note: User settings still use GENERATE structure for parameters
                if (!updatedConfig.GENERATE[method].PARAMS) {
                    updatedConfig.GENERATE[method].PARAMS = {};
                }
                paramInputs.forEach(input => {
                    const paramKey = input.getAttribute('data-param');
                    updatedConfig.GENERATE[method].PARAMS[paramKey] = input.value;
                });
            }
        });

        console.log('Updated system configuration to save:', JSON.stringify(updatedConfig, null, 2));

        // Send to server
        const response = await fetch('/api/system/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(updatedConfig)
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error('Save system config response error:', errorText);
            throw new Error(`Failed to save system configuration: ${errorText}`);
        }

        const responseData = await response.json();
        console.log('Save system config response:', responseData);

        // Update current config
        currentConfig = updatedConfig;
        showSuccess('System configuration saved successfully');
    } catch (error) {
        console.error('Error saving system configuration:', error);
        showError(`Failed to save system configuration: ${error.message}`);
    }
}

// Save settings changes
async function saveSettings() {
    console.log('Saving settings changes');

    // Add confirmation prompt
    if (window.showConfirm) {
        const confirmed = await window.showConfirm(
            'Save Settings',
            'Do you want to apply these user settings changes?',
            { type: 'acceptReject', confirmText: 'Accept', cancelText: 'Reject' }
        );
        if (!confirmed) return;
    }

    try {
        // Start with current settings to preserve all existing data
        const updatedSettings = { ...currentSettings };

        // Update only the fields that can be changed from UI
        updatedSettings.USER_PREFERENCES = {
            ...updatedSettings.USER_PREFERENCES,
            THEME: document.getElementById('theme-select').value,
            USER_RAG_ROOT: document.getElementById('rag-root-input').value
        };

        updatedSettings.GENERATE = {
            ...updatedSettings.GENERATE,
            METHOD: document.getElementById('generate-method-select').value
        };

        // Update chatbot model selection
        const modelIdSelect = document.getElementById('model-id-select');
        if (modelIdSelect && modelIdSelect.value) {
            const [provider, ...idParts] = modelIdSelect.value.split(':');
            const id = idParts.join(':'); // Handle IDs that might contain colons
            updatedSettings.CHATBOT_AI_MODEL = {
                ...updatedSettings.CHATBOT_AI_MODEL,
                SELECTED: {
                    PROVIDER: provider,
                    ID: id
                }
            };
        }

        // Update WORKFLOW_RAG_TYPE mappings from the UI
        const workflowSelects = document.querySelectorAll('select[data-workflow]');
        if (workflowSelects.length > 0) {
            updatedSettings.WORKFLOW_RAG_TYPE = { ...updatedSettings.WORKFLOW_RAG_TYPE };
            workflowSelects.forEach(select => {
                const workflow = select.getAttribute('data-workflow');
                const ragType = select.value;
                updatedSettings.WORKFLOW_RAG_TYPE[workflow] = ragType;
            });
        }

        console.log('Updated settings to save:', JSON.stringify(updatedSettings, null, 2));

        // Send to server - just the settings object, not wrapped in another object
        const response = await fetch('/api/system/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(updatedSettings)
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error('Save response error:', errorText);
            throw new Error(`Failed to save settings: ${errorText}`);
        }

        const responseData = await response.json();
        console.log('Save response:', responseData);

        // Update current settings
        currentSettings = updatedSettings;

        // Refresh top-panel status to reflect new model values
        if (window.fetchAndUpdateStaticStatus) {
            window.fetchAndUpdateStaticStatus();
        }

        showSuccess('Settings saved successfully');
    } catch (error) {
        console.error('Error saving settings:', error);
        showError(`Failed to save settings: ${error.message}`);
    }
}

// Fetch user state
async function fetchUserState() {
    console.log('Fetching user state from API...');
    const response = await fetch('/api/user_state', {
        headers: {
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Expires': '0'
        }
    });
    console.log('User state API response status:', response.status);
    if (!response.ok) {
        const errorText = await response.text();
        console.error('Failed to fetch user state. Status:', response.status, 'Response:', errorText);
        throw new Error(`Failed to fetch user state: ${response.status} - ${errorText}`);
    }
    return await response.json();
}

// Helper functions for UI feedback
function showSuccess(message) {
    console.log('Success:', message);
    if (window.updateStatus) {
        window.updateStatus(message, 'success');
    }
}

function showError(message) {
    console.error('Error:', message);
    if (window.showAlert) window.showAlert('Error', message, { type: 'danger' });
    else alert(`Error: ${message}`);
}

// Initialize system configuration UI (for Configuration button)
// Initialize system configuration UI (for Configuration button)
async function initSystemConfigUI(containerElement) {
    // Use the provided container element
    configContainer = containerElement;

    // Check if config UI is already initialized
    if (configContainer.getAttribute('data-config-ui-initialized')) {
        return false;
    }

    // Mark as initialized
    configContainer.setAttribute('data-config-ui-initialized', 'true');

    // Create the complete DOM structure directly in the provided container
    const htmlContent = `
        <div id="config-panel" class="config-panel"></div>
        <div class="save-button-container">
            <button id="save-config-btn" class="config-button">Save System Configuration</button>
        </div>
    `;
    configContainer.innerHTML = htmlContent;

    // Use more robust element selection with error checking
    const configPanel = configContainer.querySelector('#config-panel');
    saveConfigBtn = configContainer.querySelector('#save-config-btn');

    // Verify all elements were found
    if (!configPanel || !saveConfigBtn) {
        console.error('Critical DOM elements missing for system config UI');
        showError('Critical DOM elements missing for system config UI');
        return false;
    }

    // Assign configPanel to configContainer for consistency with existing logic
    configContainer = configPanel;

    // Set UI mode to system configuration
    currentSettings = {}; // Clear user settings for system config mode
    currentUserId = 'SYSTEM';

    try {
        // Load system config
        const systemConfigResponse = await fetch('/api/system/config');
        if (!systemConfigResponse.ok) {
            const errorText = await systemConfigResponse.text();
            throw new Error(`Failed to load system config: ${systemConfigResponse.status} - ${errorText}`);
        }
        currentConfig = await systemConfigResponse.json();

        // Set up event listeners for system config
        if (!saveConfigBtn) {
            throw new Error('Save config button not found');
        }
        saveConfigBtn.addEventListener('click', saveConfiguration);

        // Update UI with system config
        updateSystemConfigUI();
        return true;
    } catch (error) {
        console.error('Error initializing system config UI:', error);
        showError(`Failed to initialize system configuration UI: ${error.message}`);
        return false;
    }
}

// Update UI with system configuration
function updateSystemConfigUI() {
    // More detailed verification for event listeners
    if (!configContainer || !saveConfigBtn) {
        console.error('Required DOM elements not found for event listeners:',
            {
                configContainer: !!configContainer,
                saveConfigBtn: !!saveConfigBtn
            });

        // Additional debugging information
        console.log('Container innerHTML:', configContainer?.parentElement?.innerHTML);
        console.log('All buttons in container:', configContainer?.parentElement?.querySelectorAll('button'));
        console.log('All elements with id starting with save:', configContainer?.parentElement?.querySelectorAll('[id^="save"]'));

        throw new Error('Required DOM elements not found for event listeners');
    }

    // Hide settings container for system config mode
    if (settingsContainer) {
        settingsContainer.innerHTML = '';
        settingsContainer.style.display = 'none';
    }

    // Show config container
    if (configContainer) {
        configContainer.style.display = 'block';
    }

    // More detailed verification for system config
    if (!configContainer || !saveConfigBtn) {
        console.error('Required DOM elements not found for system config:',
            {
                configContainer: !!configContainer,
                saveConfigBtn: !!saveConfigBtn
            });

        // Additional debugging information
        console.log('Container innerHTML:', configContainer?.parentElement?.innerHTML);
        console.log('All buttons in container:', configContainer?.parentElement?.querySelectorAll('button'));
        console.log('Save config button element:', configContainer?.parentElement?.querySelector('#save-config-btn'));
        console.log('Save config button by attribute:', configContainer?.parentElement?.querySelector('[id="save-config-btn"]'));

        throw new Error('Required DOM elements not found for system config');
    }

    // Render system config
    renderSystemConfig();
}

// Toggle AI Parser Section based on selected generation method
function toggleAIParserSection() {
    const methodSelect = document.getElementById('generate-method-select');
    if (!methodSelect) {
        return;
    }

    const selectedMethod = methodSelect.value;

    // Get the AI parser section container
    const aiParserSection = document.getElementById('ai-parser-section');
    if (!aiParserSection) {
        console.log('AI parser section not found');
        return;
    }

    // Check if selected method is an AI method
    const isAIMethod = selectedMethod.includes('AI');

    if (isAIMethod) {
        // Show the AI parser section
        aiParserSection.style.display = 'block';

        // Get all AI method sections within the AI parser section
        const aiMethodSections = aiParserSection.querySelectorAll('[id^="ai-method-"]');

        // Hide all AI method sections first
        aiMethodSections.forEach(section => {
            section.style.display = 'none';
        });

        // Show the selected AI method section if it exists
        const selectedSection = document.getElementById(`ai-method-${selectedMethod}`);
        if (selectedSection) {
            selectedSection.style.display = 'block';
        } else {
            console.log(`No settings section found for method: ${selectedMethod}`);
        }
    } else {
        // Hide the entire AI parser section for non-AI methods
        aiParserSection.style.display = 'none';
    }
}

// Refresh workflow RAG type mapping section when RAG types change
function refreshWorkflowRagTypeMapping() {
    // Find the workflow RAG type mapping container
    const workflowSection = document.querySelector('.config-section h2');
    let workflowContainer = null;

    // Find the workflow section by checking h2 text content
    const allSections = document.querySelectorAll('.config-section h2');

    allSections.forEach(h2 => {
        if (h2.textContent.includes('Workflow RAG Type Mapping')) {
            workflowContainer = h2.parentElement;
        }
    });

    if (!workflowContainer) {
        console.error('❌ Workflow RAG type mapping section not found');
        return;
    }

    // Get the current available RAG types from user preferences
    const availableRagTypes = currentSettings.USER_PREFERENCES?.RAG_TYPES || [];

    // Re-render the workflow RAG type mapping
    let workflowRagTypeOptions = '<div>Loading workflow RAG type mappings...</div>';
    try {
        if (currentSettings && currentSettings.WORKFLOW_RAG_TYPE) {
            if (Object.keys(currentSettings.WORKFLOW_RAG_TYPE).length > 0) {
                // Create table header
                let tableHeader = `
                    <div class="config-table-header">
                        <div class="config-table-cell workflow-label">Workflow</div>
                        <div class="config-table-cell rag-type-select">RAG Type</div>
                    </div>
                `;

                // Create table rows
                let tableRows = Object.entries(currentSettings.WORKFLOW_RAG_TYPE).map(([workflow, ragType]) => {
                    let selectOrWarning = '<div class="rag-type-select">Loading RAG types...</div>';

                    // Check if current workflow ragType is still valid (available in the RAG types list)
                    const isValidRagType = ragType && availableRagTypes.includes(ragType);

                    if (ragType && !availableRagTypes.includes(ragType)) {
                        // Show red warning text AND select dropdown for removed RAG type

                        // Create select dropdown with remaining RAG types
                        let warningSelectOptions = '<option value="" selected disabled>Select replacement...</option>';
                        if (availableRagTypes.length > 0) {
                            warningSelectOptions += availableRagTypes.map(type =>
                                `<option value="${type}">${type}</option>`
                            ).join('');
                        }

                        selectOrWarning = `
                            <div class="config-table-cell rag-type-select">
                                <select class="config-select" data-workflow="${workflow}" style="border: 2px solid #ef4444;">
                                    ${warningSelectOptions}
                                </select>
                                <div style="margin-bottom: 5px; margin-left: 20px;">
                                    <span class="text-error" style="font-weight: 600; color: #ef4444 !important;">${ragType} is removed</span>
                                </div>
                            </div>
                        `;
                    } else if (ragType && availableRagTypes.includes(ragType)) {
                        // Show normal select dropdown for valid RAG types
                        let typeOptions = availableRagTypes.map(type => {
                            const isSelected = ragType === type;
                            return `<option value="${type}" ${isSelected ? 'selected' : ''}>${type}</option>`;
                        }).join('');

                        selectOrWarning = `
                            <select class="config-select" data-workflow="${workflow}">
                                ${typeOptions}
                            </select>
                        `;
                    } else {
                        // No RAG type assigned - show empty select
                        let typeOptions = '<option value="" selected>Select RAG type...</option>';
                        if (availableRagTypes.length > 0) {
                            typeOptions += availableRagTypes.map(type =>
                                `<option value="${type}">${type}</option>`
                            ).join('');
                        }

                        selectOrWarning = `
                            <select class="config-select" data-workflow="${workflow}">
                                ${typeOptions}
                            </select>
                        `;
                    }

                    return `
                        <div class="config-table-row">
                            <div class="config-table-cell workflow-label">${workflow}:</div>
                            <div class="config-table-cell rag-type-select">
                                ${selectOrWarning}
                            </div>
                        </div>
                    `;
                }).join('');

                workflowRagTypeOptions = `
                    <div class="config-table">
                        ${tableHeader}
                        ${tableRows}
                    </div>
                `;
            } else {
                workflowRagTypeOptions = '<div>No workflow RAG type mappings available</div>';
            }
        } else {
            workflowRagTypeOptions = '<div>Error loading workflow RAG type mappings</div>';
        }
    } catch (error) {
        console.error('❌ Error re-rendering workflow RAG type mappings:', error);
        workflowRagTypeOptions = `<div>Error: ${error.message}</div>`;
    }

    // Update the workflow section content (skip the h2 header)
    const existingTable = workflowContainer.querySelector('.config-table');

    if (existingTable) {
        existingTable.outerHTML = workflowRagTypeOptions;
    } else {
        // If no table exists, replace all content after the h2
        const h2 = workflowContainer.querySelector('h2');
        if (h2) {
            // Clear everything after h2
            while (h2.nextSibling) {
                h2.parentElement.removeChild(h2.nextSibling);
            }
            // Add new content
            h2.insertAdjacentHTML('afterend', workflowRagTypeOptions);
        }
    }

}

// Array editor functions for user settings
function addArrayItem(section) {
    // Find the array items container
    const container = document.getElementById('rag-types-items');
    if (!container) {
        console.error('Array items container not found');
        return;
    }

    // Get current items count
    const currentItems = container.querySelectorAll('.array-item');
    const newIndex = currentItems.length;

    // Create new item
    const newItem = document.createElement('div');
    newItem.className = 'array-item';
    newItem.setAttribute('data-index', newIndex);
    newItem.innerHTML = `
        <input type="text" value="" class="array-input" data-section="${section}" data-index="${newIndex}">
        <button type="button" class="array-remove-btn" onclick="removeArrayItem('${section}', ${newIndex})">-</button>
    `;

    // Add to container
    container.appendChild(newItem);
    console.log(`Added new item at index ${newIndex}`);

    // Refresh workflow mapping section after adding
    if (section === 'RAG_TYPES') {
        setTimeout(() => refreshWorkflowRagTypeMapping(), 100);
    }
}

function removeArrayItem(section, index) {
    console.log(`Removing item from section: ${section}, index: ${index}`);

    // Find the item to remove
    const container = document.getElementById('rag-types-items');
    if (!container) {
        console.error('Array items container not found');
        return;
    }

    const itemToRemove = container.querySelector(`.array-item[data-index="${index}"]`);
    if (itemToRemove) {
        // Get the value before removing
        const input = itemToRemove.querySelector('.array-input');
        const removedValue = input ? input.value : null;
        console.log(`Removing item with value: ${removedValue}`);

        container.removeChild(itemToRemove);
        console.log(`Removed item at index ${index}`);

        // Update the underlying data structure for RAG_TYPES
        if (section === 'RAG_TYPES' && currentSettings.USER_PREFERENCES?.RAG_TYPES) {
            // Remove the item from the currentSettings array
            if (removedValue) {
                const originalArray = [...currentSettings.USER_PREFERENCES.RAG_TYPES];
                currentSettings.USER_PREFERENCES.RAG_TYPES = originalArray.filter(type => type !== removedValue);
                console.log(`Updated currentSettings RAG_TYPES:`, currentSettings.USER_PREFERENCES.RAG_TYPES);
            }
        }

        // Re-index remaining items
        const remainingItems = container.querySelectorAll('.array-item');
        remainingItems.forEach((item, newIndex) => {
            item.setAttribute('data-index', newIndex);
            const input = item.querySelector('.array-input');
            const button = item.querySelector('.array-remove-btn');

            if (input) {
                input.setAttribute('data-index', newIndex);
            }
            if (button) {
                button.setAttribute('onclick', `removeArrayItem('${section}', ${newIndex})`);
            }
        });

        // Refresh workflow mapping section after removing
        if (section === 'RAG_TYPES') {
            setTimeout(() => refreshWorkflowRagTypeMapping(), 100);
        }
    } else {
        console.error(`Item at index ${index} not found`);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
});

// Test function for notification system (can be called from browser console)
function testRagTypeNotification() {
    console.log('🧪 Testing RAG type notification system...');

    if (currentSettings.USER_PREFERENCES && currentSettings.USER_PREFERENCES.RAG_TYPES) {
        const originalRagTypes = [...currentSettings.USER_PREFERENCES.RAG_TYPES];
        console.log('📊 Original RAG types:', originalRagTypes);
        console.log('🔗 Current workflow mappings:', currentSettings.WORKFLOW_RAG_TYPE);

        // Find a RAG type that is actually being used by workflows
        let ragTypeToRemove = null;
        for (const ragType of originalRagTypes) {
            const workflowsUsingType = Object.entries(currentSettings.WORKFLOW_RAG_TYPE)
                .filter(([workflow, mappedType]) => mappedType === ragType)
                .map(([workflow]) => workflow);

            if (workflowsUsingType.length > 0) {
                ragTypeToRemove = ragType;
                console.log(`🎯 Found RAG type "${ragType}" used by workflows: ${workflowsUsingType.join(', ')}`);
                break;
            }
        }

        if (ragTypeToRemove) {
            // Remove the RAG type from user preferences
            const newRagTypes = originalRagTypes.filter(type => type !== ragTypeToRemove);
            currentSettings.USER_PREFERENCES.RAG_TYPES = newRagTypes;

            console.log(`🗑️  Removed RAG type: ${ragTypeToRemove}`);
            console.log('📋 Remaining RAG types:', newRagTypes);

            // Trigger the refresh function
            refreshWorkflowRagTypeMapping();

            console.log('✅ Test completed. You should now see red warning text for workflows that were using the removed RAG type.');
            console.log('🔍 Look for: <div class="config-table-cell rag-type-select"> containing <span class="text-error">');
        } else {
            console.log('⚠️  No RAG types are currently being used by workflows. To test:');
            console.log('   1. First set a workflow to use a specific RAG type');
            console.log('   2. Then remove that RAG type from User Preferences');
            console.log('   3. The workflow should show red warning text');
        }
    } else {
        console.log('❌ No RAG types found in user preferences');
    }
}

// Helper function to inspect the DOM structure
function inspectWorkflowSection() {
    console.log('🔍 Inspecting Workflow RAG Type Mapping section...');

    const allSections = document.querySelectorAll('.config-section h2');
    let workflowSection = null;

    allSections.forEach(h2 => {
        if (h2.textContent.includes('Workflow RAG Type Mapping')) {
            workflowSection = h2.parentElement;
        }
    });

    if (workflowSection) {
        console.log('📋 Workflow section found:', workflowSection);
        console.log('🔍 Section HTML:', workflowSection.innerHTML);

        const errorElements = workflowSection.querySelectorAll('.text-error');
        console.log(`🚨 Found ${errorElements.length} error elements:`, errorElements);

        errorElements.forEach((el, index) => {
            console.log(`   Error element ${index + 1}:`, el);
            console.log(`   Text content: "${el.textContent}"`);
            console.log(`   Parent element:`, el.parentElement);
        });
    } else {
        console.log('❌ Workflow section not found');
    }
}
