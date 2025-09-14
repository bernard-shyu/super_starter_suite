# super_starter_suite - Bernard Integrated Starter Tools 

## Architecture

### Key components

1. __Agentic RAG__: Focuses on creating a query tool with citations enabled and defining a system prompt for the agent.
2. __Code Generator__: Handles code generation based on user requirements, with steps for planning, generating artifacts, and synthesizing answers.
3. __Deep Research__: Involves retrieving information, analyzing it, and generating a comprehensive report based on the research results.
4. __Document Generator__: Generates or updates documents (Markdown or HTML) based on user requirements.
5. __Financial Report__: Generates financial reports using indexed documents, with steps for research, analysis, and report generation.
6. __Human in the Loop__: Executes CLI commands with human confirmation, using a prompt to generate the command based on the user's request.

### Dual-Mode Integration

1. __Adaptive Integration__: In the `workflow_adapters/`, integrates with lightweight wrapper files that import the logic from the corresponding `STARTER_TOOLS` and expose it to the main application via FastAPI `APIRouter`.
2. __Ported Integration__: In the `workflow_porting/`, integrates by porting the business logic to follow the `llama_index` core framework without adhering to the `STARTER_TOOLS/` framework.

## The design

### Multi-Use Scenario and Session management

Key technical concepts include:
- LLM service context management
- System Configuration
- User Settings and Context
- Request session context

1. __Multi-User Scenario__:
   - Multiple users (A, B, C) access the server simultaneously from different devices
   - Each user has their own browser session with the server
   - Requests from different users are interleaved on the server

2. __Middleware Lifecycle__:
   - When User A opens the browser, the middleware identifies them (via IP or auth token)
   - The middleware loads User A's settings and binds them to the request state
   - Each subsequent request from User A maintains this context
   - When User B makes a request, the middleware loads User B's settings separately
   - The server maintains complete isolation between users' settings and sessions

3. __Request Flow__:
   - User A Request → Middleware (loads User A settings) → Endpoint (uses User A settings)
   - User B Request → Middleware (loads User B settings) → Endpoint (uses User B settings)
   - User A Request → Middleware (already has User A settings) → Endpoint (uses User A settings)

### Context of User Setting and Web Request Session

1. __Session Context Propagation__: 
    - This pattern `request.state.user_setting = _user_setting` serves an important purpose in the application's architecture:
        - Session-aware configuration management
        - FastAPI request state handling
    - It makes the user settings available throughout the request lifecycle by storing them in the FastAPI request state object.

2. __Middleware Access__:
    - This allows middleware components to access the user settings without having to reload them for each request.

3. __Dependency Injection__:
    - It enables other parts of the application (like services, utilities, or other middleware) to access the user settings through the request object.

4. __Performance Optimization__:
    - By loading the settings once per request and storing them in the request state, we avoid repeatedly loading the settings from disk.

5. __Consistency__: Ensures all components in the request pipeline are working with the same user settings.

### Config Data Flow from backend to frontend

1. __Backend (Python)__:

   - The backend is responsible for loading and saving user settings. The relevant functions in `config_manager.py` are `load_user_settings` and `save_user_settings`.
   - The `load_user_settings` function loads user settings from a TOML file and returns them as a dictionary.
   - The `save_user_settings` function saves user settings to a TOML file.

2. __Frontend (JavaScript)__:

   - The frontend is responsible for displaying user settings and handling user interactions. The relevant functions in `config_ui.js` are `loadConfigurations`, `updateUI`, and `saveSettings`.
   - The `loadConfigurations` function loads system configuration and user settings from the backend and stores them in global variables.
   - The `updateUI` function updates the UI with the current configurations.
   - The `saveSettings` function handles saving user settings to the backend.

3. __HTML Rendering__:

   - The HTML rendering is responsible for displaying the user settings to the user. The relevant part of the HTML is the `settings-panel` div, which is populated by the `updateUI` function in `config_ui.js`.

## Theme System

### Overview
The WebGUI supports a comprehensive multi-theme system with 10 theme combinations (5 colors × 2 styles):

- **Colors**: light, dark, blue, green, purple
- **Styles**: classic, modern
- **Total Combinations**: 10 (light_classic, light_modern, dark_classic, dark_modern, blue_classic, blue_modern, green_classic, green_modern, purple_classic, purple_modern)

### Theme Architecture

#### 1. Configuration Layer
- **System Configuration**: `system_config.toml` contains `AVAILABLE_THEMES` array with all supported theme combinations
- **User Preferences**: Each `settings.<USER>.toml` file contains `THEME` preference in `{color}_{style}` format
- **Validation**: Backend validates theme selections against the `AVAILABLE_THEMES` array

#### 2. CSS Architecture
- **Separation of Concerns**: Colors and styles are separated for maximum flexibility
- **CSS Custom Properties**: Uses `--theme-*` variables for dynamic theming with fallbacks
- **File Structure**:
  - **Style CSS**: `config_ui.classic.css`, `config_ui.modern.css` for Configuration/Settings UI
  - **Main CSS**: `main_style.classic.css`, `main_style.modern.css` for main WebGUI/ChatBot
  - **Color CSS**: `themes/{color}.css` files containing color-specific CSS variables

#### 3. API Endpoints
- `GET /api/themes` - Returns list of available themes from system configuration
- `GET /api/themes/current` - Returns user's current theme preference
- `POST /api/themes/current` - Updates user's theme preference with validation

#### 4. Frontend Integration
- **Dynamic Loading**: Theme CSS files are loaded dynamically without page refresh
- **Real-time Switching**: Immediate visual feedback when switching themes
- **Persistence**: Theme preferences persist across browser sessions
- **Fallback Support**: CSS variables include sensible fallbacks for robustness

### Theme Switching Flow

1. **User Selection**: User selects theme from dropdown in Settings UI
2. **Validation**: Frontend validates selection against available themes
3. **API Request**: POST request sent to `/api/themes/current` with selected theme
4. **Backend Processing**: Server validates theme and updates user settings file
5. **Response**: Success response returned with updated theme information
6. **CSS Application**: Frontend dynamically loads appropriate CSS files
7. **Visual Update**: Page styling updates immediately without refresh
8. **Persistence**: Theme preference saved to user settings for future sessions

### Technical Implementation Details

#### CSS Variable Structure
```css
/* Color theme files (themes/*.css) */
:root {
  --theme-primary-color: #your-color;
  --theme-secondary-color: #your-secondary;
  --theme-neutral-color: #your-neutral;
}

/* Style files with fallbacks */
.your-element {
  color: var(--theme-primary-color, #default-fallback);
  background: var(--theme-secondary-color, #default-fallback);
}
```

#### Configuration Example
```toml
# system_config.toml
[SYSTEM]
AVAILABLE_THEMES = [
    "light_classic",  "light_modern",
    "dark_classic",   "dark_modern",
    "green_classic",  "green_modern",
    "blue_classic",   "blue_modern",
    "purple_classic", "purple_modern"
]

# settings.Bernard.toml
[USER_PREFERENCES]
THEME = "dark_modern"
```

### Files Involved
- **Configuration**: `config/system_config.toml`, `config/settings.*.toml`
- **Backend Logic**: `shared/config_manager.py` (theme management methods)
- **API Endpoints**: `main.py` (theme API routes)
- **Frontend Logic**: `frontend/static/script.js` (theme loading/switching)
- **UI Components**: `frontend/static/config_ui.js` (theme selection)
- **CSS Files**:
  - Color themes: `frontend/static/themes/*.css`
  - Style themes: `frontend/static/*_style.*.css`
  - Config themes: `frontend/static/config_ui.*.css`

### Testing and Validation
- **Server Testing**: All theme API endpoints return 200 OK responses
- **Theme Switching**: All 5 colors work correctly with both classic and modern styles
- **Persistence**: Theme preferences maintained across page refreshes
- **Fallback Handling**: System gracefully handles missing theme files
- **Performance**: CSS loading optimized for minimal impact


## NextJS based GUI engine (*OBSOLETE*)

### Cleaning the Project

1. **Clean the frontend dependencies**: `cd super_starter_suite/frontend && npm run clean ;`
2. **Clean the backend dependencies**:  `cd super_starter_suite && hatch clean ;`

### Installing the Project

1. **Install the frontend dependencies**:  `cd super_starter_suite/frontend && npm install ;`
2. **Install the backend dependencies**:   `cd super_starter_suite && hatch build ;`

### Building the Project

1. **Build the frontend**: `cd super_starter_suite/frontend && npm run build ;`
2. **Build the backend**:  `cd super_starter_suite && hatch build ;`

### Running the Project

1. **Start the frontend development server**: `cd super_starter_suite/frontend && npm start ;`
2. **Start the backend development server**:  `uvicorn super_starter_suite.main:app --port 8000 --reload --host 0.0.0.0 ;`

___________________________________________________________________________________________________________________________________________________________
# cheat sheet
___________________________________________________________________________________________________________________________________________________________

```
bvenv ai8;  cd llama_index/bernard.campus/super_starter_suite;               uvicorn main:app --host 0.0.0.0 --port 8000 
#---------------------------------------------------------------------------------------------------------------------------
kvenv ai8;  cd llama_index/bernard.campus/super_starter_suite/rag_indexing;  source gen_ocr_reader.sh
```
