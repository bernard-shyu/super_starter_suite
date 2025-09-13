# CLINE TASK PLAN: WebGUI, ChatBot, Config, and Status Improvements

## General Notes on Verification

*   **Server and Browser Separation**: I acknowledge that the server and browser are separate machines. For verification, I will prioritize `curl` for initial checks of API responses and HTML output, followed by `browser_action` for comprehensive UI rendering and interaction testing.

## Stage 1: Status Bar UI Improvements

**Goal**: Transform the single-line status display into a two-line, dynamic, and stateful status bar.

*   **Phase 1.1: Analyze existing HTML, CSS, JS for status bar**
    *   **Status**: Completed. I have reviewed `index.html` for the `status-bar` div, `style.css` for its styling, and `script.js` for `statusBarStruct`, `renderStatusBar`, `updateStatus`, and `setStatusBar` functions.
*   **Phase 1.2: Modify HTML to support 2-line status display**
    *   **Description**: Update `index.html` to include two distinct `div` elements within the `top-panel` for static and dynamic status information. The static information will be presented in a structured JSON-like format.
    *   **Implementation**:
        *   Add two `div` elements inside the `top-panel` with IDs:
            *   `status-static-info`: This will display a JSON-formatted string containing `current_workflow`, `current_model_provider`, and `current_model_id`.
            *   `status-dynamic-message`: This will display the dynamic status message.
        *   **Naming Convention**:
            *   HTML IDs: `status-static-info`, `status-dynamic-message`
            *   JavaScript variables: `staticStatusInfoElement`, `dynamicStatusMessageElement`
            *   JSON keys for static info: `current_workflow`, `current_model_provider`, `current_model_id`
            *   Python API parameters/keys: `current_workflow`, `current_model_provider`, `current_model_id`
*   **Phase 1.3: Update CSS for new status bar layout and styling**
    *   **Description**: Adjust `style.css` to accommodate the two-line layout and introduce styles for colorful and stateful status indications.
    *   **Implementation**:
        *   Modify `.top-panel` to use `flex-direction: column` or similar to stack the two lines.
        *   Add CSS classes (e.g., `.status-success`, `.status-error`, `.status-in-progress`, `.status-info`) with distinct colors and possibly animations for stateful updates.
        *   Ensure proper spacing and alignment for both lines.
*   **Phase 1.4: Enhance JavaScript `updateStatus` function for dynamic, colorful, and stateful updates**
    *   **Description**: Refactor `script.js` to populate the two status lines separately and to apply dynamic styling based on the status state. Ensure that static status information can be updated from both initial page load (via middleware headers) and after configuration changes (via a new API endpoint).
    *   **Implementation**:
        *   Update `statusBarStruct` to separate static and dynamic fields, using the new naming conventions (e.g., `current_workflow`, `current_model_provider`, `current_model_id`, `status_message`).
        *   Modify `renderStatusBar` to update `status-static-info` and `status-dynamic-message` independently. The `status-static-info` will display a formatted JSON string.
        *   Enhance `updateStatus` to accept a status message and an optional status type (e.g., 'success', 'error', 'info', 'in-progress').
        *   Dynamically add/remove CSS classes to `status-dynamic-message` based on the status type.
        *   Implement a new JavaScript function `fetchAndUpdateStaticStatus()` that makes an API call to `GET /api/user_state` to retrieve the current user's workflow and model information from the backend. This function will be called:
            *   On initial page load (in addition to reading headers, as headers might not always be present or up-to-date after client-side navigation).
            *   After a user saves changes in the Configuration Manager UI (Stage 2).
        *   **Backend Implementation (`main.py`)**: Add a new `GET /api/user_state` endpoint that returns the current `current_workflow`, `current_model_provider`, `current_model_id` based on the user's session. This endpoint will leverage `request.state.user_config` to retrieve the necessary information.
*   **Phase 1.5: Verification (curl/browser_action)**
    *   **Description**: Test the new status bar functionality by interacting with the UI and observing the display.
    *   **Implementation**:
        *   Use `curl` to check the `GET /api/user_state` endpoint and verify the JSON output.
        *   Use `browser_action` to launch the application and verify the two-line layout.
        *   Trigger different actions (e.g., loading a workflow, initiating generation) to check if static and dynamic statuses update correctly with appropriate colors and states.
        *   Inspect element styles in the browser to confirm CSS classes are applied as expected.

## Stage 2: Configuration Management UI

**Goal**: Develop a full-fledged configuration management UI for `settings.<USER-ID>.toml` and `system_config.toml` with editable fields and select options.

*   **Phase 2.1: Analyze existing HTML, CSS, JS for settings/config display**
    *   **Status**: Completed. I have reviewed how `settings-btn` and `config-btn` currently fetch and display JSON in a `<pre>` tag.
*   **Phase 2.2: Design and implement UI components (edit boxes, select lists) for `settings.<USER-ID>.toml` and `system_config.toml`**
    *   **Description**: Create dynamic HTML forms to represent the TOML structure, allowing users to edit values.
    *   **Implementation**:
        *   Develop a JavaScript function (e.g., `renderConfigForm(configData, isSystemConfig)`) that takes a configuration object and generates an editable HTML form.
        *   For string/number values, use `<input type="text">` or `<input type="number">`.
        *   For boolean values, use `<input type="checkbox">`.
        *   For array values (like `RAG_TYPES`, `GENERATE_METHODS`), use a combination of `<select>` for predefined options or dynamic input fields for adding/removing items.
        *   For nested objects (like `AI_MODELS_AVAILABLE`, `GENERATE.NvidiaAI`), create nested sections or collapsible elements.
        *   Implement a "Save" button that collects all form data.
*   **Phase 2.3: Implement frontend logic to fetch and display configuration data**
    *   **Description**: Modify the click handlers for `settings-btn` and `config-btn` to use the new `renderConfigForm` function.
    *   **Implementation**:
        *   When `settings-btn` or `config-btn` is clicked, fetch the respective TOML data from the backend (`/api/settings`, `/api/config`).
        *   Parse the JSON response and pass it to `renderConfigForm` to display the editable UI in the `chat-area`.
*   **Phase 2.4: Implement frontend logic to send updated configuration data to backend**
    *   **Description**: Develop a JavaScript function to serialize the form data back into a JSON object and send it to the backend.
    *   **Implementation**:
        *   Attach an event listener to the "Save" button within the generated form.
        *   When clicked, collect all input values from the form.
        *   Construct a JSON object that mirrors the TOML structure.
        *   Send a `POST` request to `/api/settings` or `/api/config` with the updated JSON data.
        *   Handle success/error responses and update the status bar.
        *   Crucially, after a successful save, call `fetchAndUpdateStaticStatus()` to refresh the static status bar information, as model or workflow choices might have changed.
*   **Phase 2.5: Verification (curl/browser_action)**
    *   **Description**: Verify that configurations can be fetched, edited, and saved correctly.
    *   **Implementation**:
        *   Use `curl` to fetch and post configuration data to the backend, verifying the TOML file updates.
        *   Use `browser_action` to navigate to the settings/config pages.
        *   Modify various fields (text, numbers, booleans, array selections).
        *   Save changes and then re-open the settings/config to confirm persistence.

## Stage 3: ChatBOT Interface (WebGUI Focus, Non-Persistent History)

**Goal**: Develop a functional chatbot interface with conversation history and continuous interaction, without requiring history persistence across browsing sessions.

*   **Phase 3.1: Analyze existing HTML, CSS, JS for workflow integration**
    *   **Status**: Completed. I have reviewed how workflow buttons trigger a `POST` request and inject the HTML response directly into the `chat-area`.
*   **Phase 3.2: Analyze existing workflow-specific UI components in `STARTER_TOOLS/`**
    *   **Description**: Investigate the `components` directories within `STARTER_TOOLS/` to identify any existing UI components (e.g., `.jsx`, `.tsx` files) that need to be integrated or rewritten for the unified frontend.
    *   **Implementation**:
        *   I have already executed `find super_starter_suite/STARTER_TOOLS/ -name components` and found `ui_event.jsx` in `code_generator/components` and `cli_human_input.tsx` in `human_in_the_loop/components`. `agentic_rag` and `deep_research` do not have specific UI components in their `components` directories.
        *   For `ui_event.jsx` and `cli_human_input.tsx`, I will need to determine if these are simple enough to be rewritten in plain JavaScript/HTML or if a frontend framework (like React) is necessary for their integration. Given the "modern Single-Page Application (SPA) frontend" requirement, it's likely a framework will be needed. This will be addressed in the next sub-phase.
*   **Phase 3.3: Design and implement chat interface with conversation history and input field**
    *   **Description**: Modify the `chat-area` to include a scrollable message display area and a persistent input field for user queries. This phase will also address how to integrate or rewrite the identified workflow-specific UI components.
    *   **Implementation**:
        *   Update `index.html` or dynamically generate HTML in `script.js` to create:
            *   A `div` for `chat-history` (scrollable).
            *   An `input` field for `user-message-input`.
            *   A "Send" button.
        *   Add CSS to `style.css` for styling chat bubbles (user/AI), scrollable history, and the input area.
        *   **Integration of Workflow-Specific UI**:
            *   If the existing `.jsx`/`.tsx` components are simple, they will be rewritten in plain JavaScript and integrated directly into the `chat-area` when their respective workflows are selected.
            *   If they are complex, a decision will be made to either:
                *   Integrate a lightweight frontend framework (e.g., React) into the `super_starter_suite`'s `frontend/static` directory to render these components. This would involve setting up a build process (e.g., Webpack, Vite).
                *   Completely rewrite the functionality of these components using standard HTML/CSS/JavaScript, avoiding external frameworks for simplicity if feasible.
            *   The choice will depend on the complexity of `ui_event.jsx` and `cli_human_input.tsx` which will be further analyzed during implementation. For now, the plan assumes a rewrite into plain JS/HTML if possible, otherwise, a framework integration will be considered.
*   **Phase 3.4: Implement frontend logic to send user messages and display responses**
    *   **Description**: Connect the input field and send button to the workflow API, displaying both user input and AI responses.
    *   **Implementation**:
        *   Modify the workflow button click handlers to initialize the chat interface instead of directly fetching a single HTML response.
        *   Add an event listener to the "Send" button (or `Enter` key press on the input field).
        *   When a message is sent:
            *   Add the user's message to `chat-history`.
            *   Send a `POST` request to the appropriate workflow API endpoint (e.g., `/api/adapted/agentic-rag/chat`) with the user's question.
            *   Display a "typing" or "loading" indicator while waiting for the AI response.
            *   Upon receiving the AI response (which should be plain text or markdown, not full HTML), render it in `chat-history`.
            *   Clear the input field.
*   **Phase 3.5: Verification (curl/browser_action)**
    *   **Description**: Test the full chat interaction flow for all workflows.
    *   **Implementation**:
        *   Use `curl` to interact with the backend chat endpoints and verify the responses.
        *   Use `browser_action` to select different workflows and engage in multi-turn conversations.
        *   Verify that messages are displayed correctly, history is maintained within the current session, and responses are received.
        *   Check for proper loading indicators and error handling.

## Stage 4: ChatBOT User History (Persistent History)

**Goal**: Implement persistent chat history across separate browsing lifecycles, per user, with a dedicated UI for management.

*   **Phase 4.0: Investigate LlamaIndex Framework for Chat History and Memory**
    *   **Description**: Research LlamaIndex's capabilities for managing chat history and memory to determine the best approach for persistence.
    *   **Implementation**:
        *   Use `web_fetch` to read the provided documentation: `https://docs.llamaindex.ai/en/stable/module_guides/deploying/agents/memory/`.
        *   Analyze different memory modules (e.g., `ChatMemoryBuffer`, `VectorContextRetrieverMemory`) and their suitability for a multi-user FastAPI application.
        *   Identify how to integrate these memory modules with existing LlamaIndex query engines or agents within the workflow adapters/porting.
*   **Phase 4.1: Backend API for Chat History Management**
    *   **Description**: Create backend endpoints to save and load chat history for a given user and workflow, leveraging LlamaIndex memory solutions.
    *   **Implementation**:
        *   Add new API endpoints in `main.py` (e.g., `POST /api/chat_history/{workflow_name}`, `GET /api/chat_history/{workflow_name}`, `DELETE /api/chat_history/{workflow_name}`).
        *   These endpoints will interact with the chosen LlamaIndex memory module to store/retrieve chat messages in a user-specific and workflow-specific manner.
        *   **Configuration**: Introduce new settings in `settings.<USER-ID>.toml` (and `settings.Default.toml`) for chat history, such as `CHAT_HISTORY_MAX_SIZE` or `CHAT_HISTORY_STORAGE_TYPE`. These settings will be exposed in the Configuration Management UI (Stage 2).
*   **Phase 4.2: Chat History WebGUI**
    *   **Description**: Design and implement a dedicated UI for managing chat history, allowing users to view, select, clear, and start new chat sessions for a given workflow.
    *   **Implementation**:
        *   Create a new section in the `chat-area` (or a modal/sidebar) that displays a list of available chat histories for the current user and selected workflow.
        *   Provide buttons for:
            *   "New Chat": Clears the current chat history and starts a fresh conversation.
            *   "Load History": Selects an existing chat history from the list and loads it into the chat interface.
            *   "Clear History": Deletes the selected chat history.
        *   This UI will interact with the new backend API endpoints for chat history management.
*   **Phase 4.3: Frontend Integration for Persistent History**
    *   **Description**: Modify the frontend to load history when a workflow is selected and save history after each interaction.
    *   **Implementation**:
        *   When a workflow button is clicked, before initializing the chat interface, make a `GET` request to `/api/chat_history/{workflow_name}` to load previous messages.
        *   After each user message is sent and an AI response is received, make a `POST` request to `/api/chat_history/{workflow_name}` to save the updated conversation history.
        *   Implement client-side logic to handle potential conflicts or synchronization issues (e.g., if multiple tabs are open).
*   **Phase 4.4: Verification (curl/browser_action)**
    *   **Description**: Verify that chat history persists across browser sessions for individual users and that the history management UI functions correctly.
    *   **Implementation**:
        *   Use `browser_action` to start a conversation with a specific user, close the browser, and then re-open it to verify that the history is loaded.
        *   Use the new Chat History WebGUI to create new chats, load existing ones, and clear them, verifying the functionality.
        *   Use `curl` to directly inspect the stored chat history on the backend to confirm persistence and deletion.

## Appendix: Configuration Management Details

### Summary

Configuration data is essential for the proper functioning of the WebGUI. It is crucial to handle configuration data consistently across the codebase. The following principles should be adhered to:

1. **TOML Handling**: All TOML handling should be consistent and adhere to the TOML specification. The `config_ui.js` file is the only place where TOML data fields are handled directly.
2. **Translated Keys**: Other parts of the codebase should access configuration data through translated keys using the `get_user_setting` function. This ensures that the codebase remains consistent and easy to maintain.
3. **Consistency**: Ensure that all configuration-related operations are consistent and follow the outlined principles. This includes loading, saving, and accessing configuration data.

For more detailed information, refer to the [WebGUI ChatBot Config Status](CLINE.TASK-PLAN.WebGUI-ChatBot-Config-Status.md) document.