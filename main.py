from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi import status, APIRouter
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Dict, Any, Optional

import uvicorn
import toml
import ipaddress
import os
from pathlib import Path
import sys
import json
import hashlib
from datetime import datetime

# Add the current project's root directory to sys.path to enable local imports
# This ensures that imports like 'from super_starter_suite.shared.config_manager'
# correctly resolve to the 'super_starter_suite' package within this project.
# Assuming main.py is in super_starter_suite/main.py and project root is super_starter_suite/
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Ensure the project root is at the beginning of sys.path for local module priority
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now we can import from the super_starter_suite package
from super_starter_suite.shared.config_manager import config_manager, UserConfig
from super_starter_suite.shared.workflow_loader import get_all_workflow_configs, load_all_workflows
from super_starter_suite.shared.llama_utils import list_external_models

# Initialize event system for clean IPC architecture
from super_starter_suite.rag_indexing.event_system import initialize_event_system
_event_emitter = initialize_event_system(config_manager)

# Get logger for main application
main_logger = config_manager.get_logger("main")

from pathlib import Path

# --- FastAPI Application Setup ---
app = FastAPI()

# Mount static files for the frontend
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "frontend" / "static"), name="static")

# Templates for serving HTML
templates = Jinja2Templates(directory=Path(__file__).parent / "frontend" / "static")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(Path(__file__).parent / "frontend/static/favicon.ico")


# --- Startup and Shutdown Events ---
@app.on_event("startup")
async def startup_event():
    """Initialize and start the event system on application startup."""
    try:
        await _event_emitter.start()
        main_logger.info("[STARTUP] Event system started successfully")
    except Exception as e:
        main_logger.error(f"[STARTUP] Failed to start event system: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown of the event system."""
    try:
        await _event_emitter.stop()
        main_logger.info("[SHUTDOWN] Event system stopped successfully")
    except Exception as e:
        main_logger.error(f"[SHUTDOWN] Error stopping event system: {e}")

# --- Middleware for User Identification ---
@app.middleware("http")
async def user_session_middleware(request: Request, call_next):
    client_ip   = request.client.host if request.client and request.client.host else "unknown"
    user_id     = config_manager.get_user_id(client_ip)
    user_config = UserConfig(user_id=user_id)
    request.state.user_id = user_id
    request.state.user_config = user_config

    # WebSocket connection detected (no debug logging needed)

    # -------------------------------------------------
    response = await call_next(request)   # Continue to routing

    # -------------------------------------------------
    # Inject model provider and model ID into response
    # -------------------------------------------------
    # Get model information from the CHATBOT_AI_MODEL section
    chatbot_model  = user_config.get_user_setting("CHATBOT_AI_MODEL.SELECTED", {})
    model_provider = chatbot_model.get("PROVIDER", "bernard-provider")
    model_id       = chatbot_model.get("ID", "bernard-ID")
    main_logger.debug(f"middleware/http:: USER={user_id}  IP={client_ip}  MODEL={model_provider}--{model_id}")

    # The model information is now handled through the /api/user_state endpoint
    # which returns a JSON object with all the necessary information
    # This is more flexible and doesn't require custom headers

    return response

# Generate UI endpoints are now handled by the rag_indexing module

# --- API Endpoints ---
from super_starter_suite.shared.decorators import bind_user_context

# Bootstrap endpoint - CANNOT set domain here, called before user_config exists
# Decorators handle domain classification after association establishes user_config
@bind_user_context
@app.post("/api/user_state/associate_user")
async def associate_user(request: Request, user_data: Dict[str, str]):
    """BOOTSTRAP ENDPOINT: User association - domain set by decorators"""
    user_id = user_data.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID is required")
    client_ip = request.client.host if request.client and request.client.host else "unknown"
    config_manager.associate_user_ip(client_ip, user_id)
    return {"message": f"User {user_id} associated with IP {client_ip}"}

@app.get("/api/system/known_users")
async def get_known_users():
    """Returns a list of unique user IDs based on config/settings.<USER_ID>.toml files"""
    config_dir = Path(__file__).parent / "config"
    users = set()
    if config_dir.exists():
        for toml_file in config_dir.glob("settings.*.toml"):
            # Extract USER_ID from settings.USER_ID.toml
            parts = toml_file.name.split('.')
            if len(parts) >= 3:
                user_id = parts[1]
                users.add(user_id)
    
    # Ensure Default is always there or at least accounted for if it exists
    return {"users": sorted(list(users))}

@app.get("/api/system/models/list")
async def list_models(request: Request, source: str):
    """Fetches model list from specified source: 'system', 'nvidia', 'openrouter', 'azure'"""
    result = list_external_models(source)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

# Entry points now derive domains from path (no manual setting needed)
@app.get("/api/system/settings")
async def get_settings(request: Request):
    """SYSTEM ENDPOINT: Domain automatically derived from path"""
    user_id = request.state.user_id
    return config_manager.get_merged_config(user_id)

@app.post("/api/system/settings")
async def update_settings(request: Request, settings_data: Dict[str, Any]):
    """SYSTEM ENDPOINT: Domain automatically derived from path"""
    user_id = request.state.user_id
    config_manager.save_user_settings(user_id, settings_data)
    # Reload config for current request state to ensure middleware uses updated settings
    request.state.user_config = config_manager.get_user_config(user_id)
    return {"message": "Settings updated successfully"}

@bind_user_context
@app.get("/api/system/config")
async def get_config(request: Request):
    # Return system configuration only, not user-specific merged config
    return config_manager.load_system_config()

@bind_user_context
@app.post("/api/system/config")
async def update_config(request: Request, config_data: Dict[str, Any]):
    user_id = request.state.user_id
    # Save system configuration using ConfigManager only
    config_manager.save_system_config(config_data)
    # Note: We don't reload user_config here as system config changes affect all users
    return {"message": "System configuration updated successfully"}

@bind_user_context
@app.get("/api/user_state")
async def get_user_state(request: Request):
    user_config = request.state.user_config

    # Get model information from the CHATBOT_AI_MODEL section
    chatbot_model = user_config.get_user_setting("CHATBOT_AI_MODEL.SELECTED", {})
    model_provider = chatbot_model.get("PROVIDER", "")
    model_id = chatbot_model.get("ID", "")

    # Get current workflow from user_state.toml [CURR_WORKFLOW] section
    current_workflow = user_config.my_workflow
    main_logger.debug(f"get_user_state:: USER={user_config.user_id}  WORKFLOW={current_workflow}  MODEL_PROVIDER={model_provider}  MODEL_ID={model_id}")

    return {
        "current_user": user_config.user_id,
        "current_workflow": current_workflow,
        "current_model_provider": model_provider,
        "current_model_id": model_id
    }

@bind_user_context
@app.post("/api/user_state/workflow")
async def update_user_workflow(request: Request, workflow_data: Dict[str, str]):
    """Update the current workflow for the user in user_state.toml"""
    user_config = request.state.user_config
    workflow = workflow_data.get("workflow")

    if not workflow:
        raise HTTPException(status_code=400, detail="Workflow is required")

    try:
        # Update the workflow in user_state.toml
        config_manager.update_user_workflow(user_config.user_id, workflow)

        # Reload user config to reflect the change
        request.state.user_config = config_manager.get_user_config(user_config.user_id)

        main_logger.debug(f"update_user_workflow:: USER={user_config.user_id}  WORKFLOW={workflow}")
        return {"message": f"Workflow updated to {workflow}", "workflow": workflow}
    except Exception as e:
        main_logger.error(f"Failed to update workflow for user {user_config.user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update workflow")

# RAG management endpoints are now handled by the rag_indexing module
# Import RAG Indexing router and WebSocket router
try:
    from super_starter_suite.rag_indexing.generate_websocket import router as websocket_router
except Exception as e:
    main_logger.warning(f"[STARTUP] ERROR: Failed to import WebSocket router: {e}")
    import traceback
    traceback.print_exc()
    websocket_router = None

# --- RAG Indexing Endpoints ---
from super_starter_suite.rag_indexing.generate_endpoint import router as rag_indexing_router
app.include_router(rag_indexing_router, tags=["RAG Indexing"])

if websocket_router is not None:
    app.include_router(websocket_router, tags=["WebSocket"])
else:
    main_logger.warning("[STARTUP] WARNING: WebSocket router not available - skipping inclusion")


# --- Workflow Endpoints (mounted via APIRouter) ---
# Import and include consolidated workflow endpoints FIRST (higher precedence)
try:
    from super_starter_suite.chat_bot.workflow_execution.workflow_endpoints import router as workflow_router
except Exception as e:
    main_logger.warning(f"[STARTUP] ERROR: Failed to import consolidated workflow endpoints router: {e}")
    import traceback
    traceback.print_exc()
    workflow_router = None

if workflow_router is not None:
    # Mount it at the root /api for cleaner paths (e.g. /api/workflow/execute)
    app.include_router(workflow_router, prefix="/api")
else:
    main_logger.warning("[STARTUP] WARNING: Consolidated workflow endpoints router not available - skipping inclusion")

# Dynamically load and include workflow routers AFTER (lower precedence)
workflow_configs = get_all_workflow_configs()
loaded_workflows = load_all_workflows()

for workflow_id, (router, _, _, _) in loaded_workflows.items():
    workflow_config = workflow_configs.get(workflow_id)
    if workflow_config:
        prefix = f"/api/workflow/{workflow_id}/business_logic"
        # Ensure tags is a list of strings, as expected by FastAPI
        tags = [workflow_config.display_name]

        app.include_router(router, prefix=prefix, tags=tags)
        app.include_router(router, prefix=prefix, tags=tags)
    else:
        main_logger.warning(f"Workflow configuration not found for '{workflow_id}'. Skipping router inclusion.")

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# --- Theme Management Endpoints ---

@bind_user_context
@app.get("/api/system/themes")
async def get_available_themes(request: Request):
    """
    Get the list of available themes from system configuration.
    """
    themes = config_manager.get_available_themes()
    return {"themes": themes}

@bind_user_context
@app.get("/api/system/themes/current")
async def get_current_theme(request: Request):
    """
    Get the current theme preference for the authenticated user.
    """
    user_id = request.state.user_id
    theme = config_manager.get_user_theme(user_id)
    return {"theme": theme}

@bind_user_context
@app.post("/api/system/themes/current")
async def update_current_theme(request: Request, theme_data: Dict[str, str]):
    """
    Update the theme preference for the authenticated user.
    """
    user_id = request.state.user_id
    theme = theme_data.get("theme")

    if not theme:
        raise HTTPException(status_code=400, detail="Theme is required")

    try:
        config_manager.update_user_theme(user_id, theme)
        return {"message": f"Theme updated to {theme}", "theme": theme}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- RAG-ROOT File Serving ---
@app.get("/api/files/chat_history/{workflow_id}/output/{filename}")
async def serve_rag_root_file(request: Request, workflow_id: str, filename: str):
    """
    Serve files (charts, images) from the user's RAG-ROOT directory.
    Usage: /api/files/chat_history/P_financial_report/output/e2b_file_....png
    """
    user_id = request.state.user_id
    user_config = config_manager.get_user_config(user_id)
    rag_root = user_config.my_rag_root
    
    file_path = os.path.join(rag_root, "chat_history", workflow_id, "output", filename)
    
    if not os.path.exists(file_path):
        main_logger.warning(f"RAG-ROOT file not found: {file_path}")
        raise HTTPException(status_code=404, detail="File not found")
        
    return FileResponse(file_path)

# --- Chat History API Endpoints ---
# Import and include chat history data CRUD endpoints
try:
    from super_starter_suite.chat_bot.chat_history.data_crud_endpoint import router as data_crud_router
except Exception as e:
    main_logger.warning(f"[STARTUP] ERROR: Failed to import chat history data CRUD router: {e}")
    import traceback
    traceback.print_exc()
    data_crud_router = None

if data_crud_router is not None:
    app.include_router(data_crud_router)
else:
    main_logger.warning("[STARTUP] WARNING: Chat history data CRUD router not available - skipping inclusion")


# Session lifecycle management endpoint
@bind_user_context
@app.get("/api/system/workflows")
async def get_available_workflows(request: Request):
    """Get list of available workflows with their metadata."""
    try:
        workflow_configs = get_all_workflow_configs()

        workflows = []
        for workflow_id, config in workflow_configs.items():
            workflows.append({
                "id": workflow_id,
                "display_name": config.display_name,
                "description": getattr(config, 'description', ''),
                "icon": getattr(config, 'icon', '🤖'),
                "timeout": getattr(config, 'timeout', 60.0),
                "code_path": config.code_path,
                "ui_pattern": getattr(config, 'ui_pattern', None),
                "enhanced_rendering": getattr(config, 'enhanced_rendering', None),
                # 🎯 UI CONFIGURATION: Include rendering flags for frontend citation processing
                "ui_config": {
                    "show_citation": getattr(config, 'show_citation', "Short"),
                    "show_tool_calls": getattr(config, 'show_tool_calls', False),
                    "show_followup_questions": getattr(config, 'show_followup_questions', False),
                    "show_workflow_states": getattr(config, 'show_workflow_states', False),
                    "artifacts_enabled": getattr(config, 'artifacts_enabled', False)
                }
            })

        return {"workflows": workflows}
    except Exception as e:
        main_logger.error(f"Error retrieving workflow configurations: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve workflows")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
