from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi import status, APIRouter
from fastapi.responses import HTMLResponse
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

# Add the project root directory to sys.path to enable imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now we can import from the super_starter_suite package
from super_starter_suite.shared.config_manager import config_manager, UserConfig

# Initialize event system for clean IPC architecture
from super_starter_suite.rag_indexing.event_system import initialize_event_system
_event_emitter = initialize_event_system(config_manager)

# Get logger for main application
main_logger = config_manager.get_logger("main")

# Import metadata management functions
from super_starter_suite.shared.index_utils import (
    scan_data_directory,
    scan_storage_directory,
    save_data_metadata,
    load_data_metadata,
    compare_data_with_metadata,
    get_data_status_simple,
    get_rag_status_summary
)

# Import workflow routers
from super_starter_suite.workflow_adapters.agentic_rag import router as agentic_rag_adapter_router
from super_starter_suite.workflow_adapters.code_generator import router as code_generator_adapter_router
from super_starter_suite.workflow_adapters.deep_research import router as deep_research_adapter_router
from super_starter_suite.workflow_adapters.document_generator import router as document_generator_adapter_router
from super_starter_suite.workflow_adapters.financial_report import router as financial_report_adapter_router
from super_starter_suite.workflow_adapters.human_in_the_loop import router as human_in_the_loop_adapter_router

from super_starter_suite.workflow_porting.agentic_rag import router as agentic_rag_porting_router
from super_starter_suite.workflow_porting.code_generator import router as code_generator_porting_router
from super_starter_suite.workflow_porting.deep_research import router as deep_research_porting_router
from super_starter_suite.workflow_porting.document_generator import router as document_generator_porting_router
from super_starter_suite.workflow_porting.financial_report import router as financial_report_porting_router
from super_starter_suite.workflow_porting.human_in_the_loop import router as human_in_the_loop_porting_router

from pathlib import Path

# --- FastAPI Application Setup ---
app = FastAPI()

# Mount static files for the frontend
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "frontend" / "static"), name="static")

# Templates for serving HTML
templates = Jinja2Templates(directory=Path(__file__).parent / "frontend" / "static")

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
    response = await call_next(request)

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
@bind_user_context
@app.post("/api/associate_user")
async def associate_user(request: Request, user_data: Dict[str, str]):
    user_id = user_data.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID is required")
    client_ip = request.client.host if request.client and request.client.host else "unknown"
    config_manager.associate_user_ip(client_ip, user_id)
    return {"message": f"User {user_id} associated with IP {client_ip}"}

@bind_user_context
@app.get("/api/settings")
async def get_settings(request: Request):
    user_id = request.state.user_id
    return config_manager.load_user_settings(user_id)

@bind_user_context
@app.post("/api/settings")
async def update_settings(request: Request, settings_data: Dict[str, Any]):
    user_id = request.state.user_id
    config_manager.save_user_settings(user_id, settings_data)
    # Reload config for current request state
    request.state.user_config = config_manager.get_user_config(user_id)
    return {"message": "Settings updated successfully"}

@bind_user_context
@app.get("/api/config")
async def get_config(request: Request):
    # Return system configuration only, not user-specific merged config
    return config_manager.load_system_config()

@bind_user_context
@app.post("/api/config")
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

    # Get current workflow from user state (this would need to be stored somewhere)
    # For now, return default or empty
    current_workflow = user_config.get_user_setting("USER_PREFERENCES", {}).get("current_workflow", "")

    return {
        "current_workflow": current_workflow,
        "current_model_provider": model_provider,
        "current_model_id": model_id
    }

# RAG management endpoints are now handled by the rag_indexing module
# Import RAG Indexing router and WebSocket router
try:
    from super_starter_suite.rag_indexing.generate_websocket import router as websocket_router
    main_logger.debug("STARTUP] WebSocket router imported successfully")
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
    main_logger.debug(f"[STARTUP] WebSocket router included successfully")
else:
    main_logger.warning("[STARTUP] WARNING: WebSocket router not available - skipping inclusion")

# --- Workflow Endpoints (mounted via APIRouter) ---
app.include_router(agentic_rag_adapter_router,        prefix="/api/adapted/agentic-rag",        tags=["Agentic RAG"])
app.include_router(code_generator_adapter_router,     prefix="/api/adapted/code-generator",     tags=["Code Generator"])
app.include_router(deep_research_adapter_router,      prefix="/api/adapted/deep-research",      tags=["Deep Research"])
app.include_router(document_generator_adapter_router, prefix="/api/adapted/document-generator", tags=["Document Generator"])
app.include_router(financial_report_adapter_router,   prefix="/api/adapted/financial-report",   tags=["Financial Report"])
app.include_router(human_in_the_loop_adapter_router,  prefix="/api/adapted/human-in-the-loop",  tags=["Human in the Loop"])

app.include_router(agentic_rag_porting_router,        prefix="/api/ported/agentic-rag",        tags=["Agentic RAG Porting"])
app.include_router(code_generator_porting_router,     prefix="/api/ported/code-generator",     tags=["Code Generator Porting"])
app.include_router(deep_research_porting_router,      prefix="/api/ported/deep-research",      tags=["Deep Research Porting"])
app.include_router(document_generator_porting_router, prefix="/api/ported/document-generator", tags=["Document Generator Porting"])
app.include_router(financial_report_porting_router,   prefix="/api/ported/financial-report",   tags=["Financial Report Porting"])
app.include_router(human_in_the_loop_porting_router,  prefix="/api/ported/human-in-the-loop",  tags=["Human in the Loop Porting"])

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Remaining endpoints are now handled by the rag_indexing module



# Cache management endpoints are now handled by the rag_indexing module

# --- Theme Management Endpoints ---

@bind_user_context
@app.get("/api/themes")
async def get_available_themes(request: Request):
    """
    Get the list of available themes from system configuration.
    """
    themes = config_manager.get_available_themes()
    return {"themes": themes}

@bind_user_context
@app.get("/api/themes/current")
async def get_current_theme(request: Request):
    """
    Get the current theme preference for the authenticated user.
    """
    user_id = request.state.user_id
    theme = config_manager.get_user_theme(user_id)
    return {"theme": theme}

@bind_user_context
@app.post("/api/themes/current")
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
