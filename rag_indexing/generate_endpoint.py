"""
Generate UI Endpoints - RAG Indexing Module

This module contains all Generate UI related endpoints and cache management.
Provides isolated RAG indexing functionality with proper request.state-based caching.
"""

from fastapi import APIRouter, Request, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse
from typing import Dict, Any, Optional

from super_starter_suite.shared.decorators import bind_rag_session
from super_starter_suite.rag_indexing.generation import run_generation_with_progress, get_generation_status, get_generation_logs
from super_starter_suite.shared.config_manager import ConfigManager, config_manager

# Initialize logger
logger = config_manager.get_logger("main")

# Create router for RAG indexing endpoints
router = APIRouter()

# ============================================================================
# GENERATE UI ENDPOINTS
# ============================================================================

# ============================================================================
# PHASE 1: SINGLE DECORATOR PATTERN - CLEAN ARCHITECTURE
# ============================================================================
# Unified approach using single @bind_rag_session decorator
#
# DECORATOR ORDER: @router → @bind_rag_session
#
# Why this order?
# 1. @router.post() captures the decorated function for FastAPI routing
# 2. @bind_rag_session handles both user_config and RAG session initialization
#
# This eliminates complexity and ensures clean separation of concerns.
# ============================================================================

@router.post("/api/generate")
@bind_rag_session
async def generate_rag_index(request: Request, background_tasks: BackgroundTasks):
    """Generate RAG index for the specified RAG type with real-time progress updates."""
    user_id = request.state.user_id
    user_config = request.state.user_config

    from super_starter_suite.shared.config_manager import config_manager
    gen_logger = config_manager.get_logger("generation")
    gen_logger.info(f"Generate endpoint called for user: {user_id}")

    # Read rag_type from JSON body
    try:
        payload = await request.json()
        rag_type = payload.get('rag_type')
        # Payload received (no debug logging needed)
    except Exception as e:
        rag_type = None
        gen_logger.warning(f"Error reading payload: {e}")

    gen_logger.info(f"RAG type selected: {rag_type}")

    # Validate RAG type selection
    if not rag_type or rag_type.strip() == '':
        raise HTTPException(status_code=400, detail="Please select a rag_type before generating")

    # Use selected RAG type
    user_config.my_rag.set_rag_type(rag_type)

    # Create a temporary config for this generation with the selected RAG type
    from super_starter_suite.shared.config_manager import UserRAGIndex

    error_message = user_config.my_rag.sanity_check()
    if error_message:
        gen_logger.warning(f"Sanity check failed: {error_message}")
        raise HTTPException(status_code=400, detail=error_message)

    # Generate task_id for status checking
    task_id = f"{user_id}_{user_config.my_rag.generate_method}_{rag_type}"


    gen_logger.info("Starting background generation task with progress callbacks")

    # MVC processing handled by session's GenerateManager (no global state)
    session = request.state.rag_session

    # Create progress callback function for session's GenerateManager
    async def progress_callback(raw_message: str):
        """Send raw messages to session's GenerateManager for MVC processing and broadcast to WebSocket."""
        # Process through MVC pipeline: raw message → GenerateManager → ProgressData
        progress_data = session.process_console_output(raw_message, task_id, rag_type)

        # If GenerateManager returns structured progress data, broadcast to WebSocket
        if progress_data:
            # Import WebSocket broadcasting functions
            try:
                from super_starter_suite.rag_indexing.generate_websocket import broadcast_generation_progress

                # ProgressData.state.value is already in the correct format (e.g., 'ST_PARSER')
                # Broadcast progress directly to WebSocket-connected clients
                await broadcast_generation_progress(
                    task_id,
                    progress_data.state.value,
                    int(progress_data.progress),
                    progress_data.message
                )

                gen_logger.debug(f"Progress broadcast: {progress_data.state.value} {progress_data.progress}% - {progress_data.message}")

            except ImportError as e:
                gen_logger.warning(f"WebSocket broadcasting unavailable: {e}")
            except Exception as ws_error:
                gen_logger.warning(f"Failed to broadcast progress: {ws_error}")

    async def status_callback(status: str, message: str):
        """Status callback - handled by session if needed."""
        pass

    # Start a background generation task with progress callbacks
    background_tasks.add_task(
        run_generation_with_progress,
        user_config,
        task_id,
        progress_callback,
        status_callback
    )

    return {
        "message": f"RAG index generation started for user {user_id} with method {user_config.my_rag.generate_method} and RAG type {rag_type}.",
        "task_id": task_id
    }

@router.get("/api/generate/status/{task_id}")
@bind_rag_session
async def get_generation_status_endpoint(request: Request, task_id: str):
    """Check the status of a RAG generation task."""
    print(f"DEBUG ENDPOINT: get_generation_status_endpoint called with task_id={task_id}")
    status_info = get_generation_status(task_id)
    return status_info

@router.get("/api/generate/logs/{task_id}")
@bind_rag_session
async def get_generation_logs_endpoint(request: Request, task_id: str):
    """Get logs for a specific generation task."""
    print(f"DEBUG ENDPOINT: get_generation_logs_endpoint called with task_id={task_id}")
    # Get the captured logs from the generation process
    logs = get_generation_logs(task_id)

    # If no logs are captured yet, provide basic status-based messages
    if not logs:
        status_info = get_generation_status(task_id)
        if status_info.get("status") == "running":
            logs = [
                f"[INFO] Generation task {task_id} is running...",
                f"[INFO] Method: {status_info.get('method', 'unknown')}",
                f"[INFO] Please wait for completion..."
            ]
        elif status_info.get("status") == "completed":
            logs = [
                f"[SUCCESS] Generation task {task_id} completed successfully!",
                f"[INFO] Method: {status_info.get('method', 'unknown')}",
                f"[INFO] RAG index has been generated and is ready for use."
            ]
        elif status_info.get("status") == "failed":
            logs = [
                f"[ERROR] Generation task {task_id} failed!",
                f"[ERROR] Error: {status_info.get('error', 'Unknown error')}",
                f"[INFO] Please check your configuration and try again."
            ]
        else:
            logs = [
                f"[INFO] Task {task_id} status: {status_info.get('status', 'unknown')}"
            ]

    return {"logs": logs}

@router.get("/api/generate/rag_type_options")
@bind_rag_session
async def get_rag_type_options(request: Request):
    """Return the list of available RAG types from the user's system configuration."""
    user_config = request.state.user_config
    rag_types = user_config.get_user_setting("USER_PREFERENCES.RAG_TYPES", [])
    return {"rag_types": rag_types}

# ============================================================================
# CACHE MANAGEMENT ENDPOINTS
# ============================================================================

@router.post("/api/generate/cache/load")
@bind_rag_session
async def load_generate_cache(request: Request):
    """
    Load metadata cache for the Generate UI.

    This endpoint initializes the cache when entering the Generate UI.
    Uses session-based cache management for proper Generate UI session lifecycle.
    """
    try:
        # Decorators should have set up user_config and rag_session
        # If they're missing, the decorators didn't execute properly
        if not hasattr(request.state, 'user_config'):
            raise HTTPException(status_code=500, detail="User context not available - decorator binding failed")

        if not hasattr(request.state, 'rag_session'):
            raise HTTPException(status_code=500, detail="RAG session not available - decorator binding failed")

        session = request.state.rag_session

        # Check if session is properly initialized
        if not session.is_initialized:
            # Try to initialize session if not already done
            if not session.initialize_session():
                raise HTTPException(status_code=500, detail="Failed to initialize session for cache loading")

        # Load cache within session context
        success = session.load_cache()

        if success:
            return {"message": "Metadata cache loaded successfully"}
        else:
            # Provide more specific error information
            cache_error = "Cache loading failed - check file permissions and directory structure"
            raise HTTPException(status_code=500, detail=cache_error)

    except Exception as e:
        logger.error(f"Exception in load_generate_cache: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Cache load error: {str(e)}")

@router.post("/api/generate/cache/save")
@bind_rag_session
async def save_generate_cache(request: Request):
    """
    Save metadata cache for the Generate UI.

    This endpoint persists the cache when leaving the Generate UI.
    Uses session-based cache management for proper Generate UI session lifecycle.
    """
    try:
        # Decorators should have set up user_config and rag_session
        # If they're missing, the decorators didn't execute properly
        if not hasattr(request.state, 'user_config'):
            raise HTTPException(status_code=500, detail="User context not available - decorator binding failed")

        if not hasattr(request.state, 'rag_session'):
            raise HTTPException(status_code=500, detail="RAG session not available - decorator binding failed")

        session = request.state.rag_session

        # Check if session is properly initialized
        if not session.is_initialized:
            raise HTTPException(status_code=500, detail="Session not initialized - cannot save cache")

        # Save cache within session context
        success = session.save_cache()

        if success:
            return {"message": "Metadata cache saved successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to save metadata cache - check file permissions")

    except Exception as e:
        logger.error(f"Exception in save_generate_cache: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Cache save error: {str(e)}")

@router.get("/api/generate/cache/status")
@bind_rag_session
async def get_generate_cache_status(request: Request):
    """
    Get cache status information for the Generate UI.

    Returns information about cache state, size, and loaded RAG types.
    Uses session-based cache access for proper per-request state isolation.
    """
    try:
        # Decorators should have set up user_config and rag_session
        # If they're missing, the decorators didn't execute properly
        if not hasattr(request.state, 'user_config'):
            raise HTTPException(status_code=500, detail="User context not available - decorator binding failed")

        if not hasattr(request.state, 'rag_session'):
            raise HTTPException(status_code=500, detail="RAG session not available - decorator binding failed")

        session = request.state.rag_session

        # Check if session is properly initialized
        if not session.is_initialized:
            return {"cache_status": {"error": "Session not initialized"}}

        # Get cache status through session (unified access point)
        cache_status = session.get_cache_status()

        return {"cache_status": cache_status}

    except Exception as e:
        logger.error(f"Exception in get_generate_cache_status: {str(e)}", exc_info=True)
        return {"cache_status": {"error": f"Cache status error: {str(e)}"}}

# ============================================================================
# RAG MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/api/data_status")
@bind_rag_session
async def get_data_status(request: Request, rag_type: str = "RAG"):
    """
    Get cached data status from MVC session to avoid redundant scanning.

    This endpoint uses session-cached StatusData instead of triggering new scans.
    Returns complete data structure - frontend decides presentation format.
    """
    try:
        user_config = request.state.user_config
        session = request.state.rag_session
        logger.debug(f"get_data_status: rag_type={rag_type}")

        # Set the RAG type for this request
        user_config.my_rag.set_rag_type(rag_type)

        # Get cached StatusData from session (MVC Model layer)
        # Pass rag_type to trigger automatic switching if needed
        status_data = session.get_status_data_info(rag_type)

        if status_data.get("error"):
            raise HTTPException(status_code=500, detail=f"No cached data available: {status_data['error']}")

        # MVC COMPLIANT: Return RAW StatusData - Frontend handles ALL display formatting
        # Backend provides raw data only, frontend (MVC View layer) determines presentation format
        # This ensures proper separation of concerns and allows frontend to adapt display logic
        response = {
            # Raw data fields - no pre-formatted display logic
            "data_newest_time": status_data.get("data_newest_time"),
            "data_newest_file": status_data.get("data_newest_file"),
            "total_files": status_data.get("total_files", 0),
            "total_size": status_data.get("total_size", 0),
            "data_files": status_data.get("data_files", []),
            "storage_creation": status_data.get("storage_creation"),
            "storage_status": status_data.get("storage_status", "empty"),
            "meta_last_update": status_data.get("meta_last_update"),
            "rag_type": status_data.get("rag_type"),

            # Cache metadata for frontend awareness
            "from_cache": True,

            # Raw comparison data - frontend decides how to interpret and display
            "comparison_data": status_data.get("comparison", {})
        }

        # DEBUG: Log final response
        logger.debug(f"get_data_status: Final response rag_type={response.get('rag_type')}")

        return response

    except Exception as e:
        logger.error(f"Exception in get_data_status: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting cached data status: {str(e)}")

@router.get("/api/rag_status")
@bind_rag_session
async def get_rag_status(request: Request, rag_type: str = "RAG"):
    """Get the current status of RAG storage and compare with data metadata."""
    user_config = request.state.user_config

    # Set the RAG type for this request
    user_config.my_rag.set_rag_type(rag_type)

    try:
        # Get comprehensive status summary
        from super_starter_suite.shared.index_utils import get_rag_status_summary
        status_summary = get_rag_status_summary(user_config)

        return status_summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking RAG status: {str(e)}")


# ============================================================================
# DETAILED STATUS ENDPOINTS
# ============================================================================
@router.get("/api/detailed_data_status")
@bind_rag_session
async def get_detailed_data_status(request: Request, rag_type: str = "RAG"):
    """
    Get detailed cached data status with file-by-file information.

    This endpoint uses session-cached StatusData to avoid redundant scanning.
    Returns the same data structure as before but from MVC cache.
    """
    try:
        user_config = request.state.user_config
        session = request.state.rag_session

        # Set the RAG type for this request
        user_config.my_rag.set_rag_type(rag_type)

        # Get cached StatusData from session (MVC Model layer)
        # Pass rag_type to trigger automatic switching if needed
        status_data = session.get_status_data_info(rag_type)

        if status_data.get("error"):
            raise HTTPException(status_code=500, detail=f"No cached data available: {status_data['error']}")

        # Convert cached StatusData to detailed response format
        response = {
            "rag_type": status_data.get("rag_type"),
            "total_files": status_data.get("total_files", 0),
            "total_size": status_data.get("total_size", 0),
            "data_files": status_data.get("data_files", []),
            "last_scan": status_data.get("meta_last_update"),
            "from_cache": True
        }

        return response

    except Exception as e:
        logger.error(f"Exception in get_detailed_data_status: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting cached detailed data status: {str(e)}")
