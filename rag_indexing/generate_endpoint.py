"""
Generate UI Endpoints - RAG Indexing Module

This module contains all Generate UI related endpoints and cache management.
Provides isolated RAG indexing functionality with proper request.state-based caching.
"""

from fastapi import APIRouter, Request, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse
from typing import Dict, Any, Optional

from super_starter_suite.shared.decorators import bind_user_context
from super_starter_suite.rag_indexing.generation import run_generation_with_progress, get_generation_status, get_generation_logs
from super_starter_suite.shared.config_manager import ConfigManager
from super_starter_suite.rag_indexing.generate_ui_cache import GenerateUICacheManager

# Create router for RAG indexing endpoints
router = APIRouter()

# ============================================================================
# GENERATE UI ENDPOINTS
# ============================================================================

@bind_user_context
@router.post("/api/generate")
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

    # Import MVC Controller for proper MVC architecture
    try:
        from .generate_websocket import get_mvc_controller
    except ImportError:
        from generate_websocket import get_mvc_controller

    # Get MVC Controller instance
    mvc_controller = get_mvc_controller()

    # Create progress callback function that sends raw messages to MVC Controller
    async def progress_callback(raw_message: str):
        """Callback to send raw log messages to MVC Controller for processing."""
        await mvc_controller.handle_generation_output(raw_message)

    async def status_callback(status: str, message: str):
        """Callback to broadcast status updates via WebSocket"""
        # Status updates can be handled here if needed
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

@bind_user_context
@router.get("/api/generate/status/{task_id}")
async def get_generation_status_endpoint(task_id: str):
    """Check the status of a RAG generation task."""
    status_info = get_generation_status(task_id)
    return status_info

@bind_user_context
@router.get("/api/generate/logs/{task_id}")
async def get_generation_logs_endpoint(task_id: str):
    """Get logs for a specific generation task."""
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

@bind_user_context
@router.get("/api/generate/rag_type_options")
async def get_rag_type_options(request: Request):
    """Return the list of available RAG types from the user's system configuration."""
    user_config = request.state.user_config
    rag_types = user_config.get_user_setting("USER_PREFERENCES.RAG_TYPES", [])
    return {"rag_types": rag_types}

# ============================================================================
# CACHE MANAGEMENT ENDPOINTS
# ============================================================================

@bind_user_context
@router.post("/api/generate/cache/load")
async def load_generate_cache(request: Request):
    """
    Load metadata cache for the Generate UI.

    This endpoint initializes the cache when entering the Generate UI.
    Uses persistent cache manager for proper state management across requests.
    """
    user_config = request.state.user_config

    try:
        # Get persistent cache manager for this user (maintains state between requests)
        from super_starter_suite.rag_indexing.generate_ui_cache import get_cache_manager
        cache_manager = get_cache_manager(user_config)
        success = cache_manager.load_metadata_cache()

        if success:
            return {"message": "Metadata cache loaded successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to load metadata cache")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading metadata cache: {str(e)}")

@bind_user_context
@router.post("/api/generate/cache/save")
async def save_generate_cache(request: Request):
    """
    Save metadata cache for the Generate UI.

    This endpoint persists the cache when leaving the Generate UI.
    Uses the same persistent cache manager instance that was loaded.
    """
    user_config = request.state.user_config

    try:
        # Get the SAME persistent cache manager instance that was loaded
        from super_starter_suite.rag_indexing.generate_ui_cache import get_cache_manager
        cache_manager = get_cache_manager(user_config)
        success = cache_manager.save_metadata_cache()

        if success:
            return {"message": "Metadata cache saved successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to save metadata cache")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving metadata cache: {str(e)}")

@bind_user_context
@router.get("/api/generate/cache/status")
async def get_generate_cache_status(request: Request):
    """
    Get cache status information for the Generate UI.

    Returns information about cache state, size, and loaded RAG types.
    """
    user_config = request.state.user_config

    try:
        # Get cache manager to check status
        from super_starter_suite.rag_indexing.generate_ui_cache import get_cache_manager
        cache_manager = get_cache_manager(user_config)

        # Get cache status information
        cache_status = {
            "cache_loaded": cache_manager.is_loaded,
            "cache_size": len(cache_manager.cache) if hasattr(cache_manager, 'cache') else 0,
            "cached_rag_types": list(cache_manager.cache.keys()) if hasattr(cache_manager, 'cache') else []
        }

        return {"cache_status": cache_status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting cache status: {str(e)}")

# ============================================================================
# RAG MANAGEMENT ENDPOINTS
# ============================================================================

@bind_user_context
@router.get("/api/data_status")
async def get_data_status(request: Request, rag_type: str = "RAG"):
    """Get simplified data status focused on change detection for RAG generation."""
    user_config = request.state.user_config

    # Set the RAG type for this request
    user_config.my_rag.set_rag_type(rag_type)

    try:
        # Get simplified data status with change detection
        from super_starter_suite.shared.index_utils import get_data_status_simple
        data_status = get_data_status_simple(user_config)

        return data_status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting data status: {str(e)}")

@bind_user_context
@router.get("/api/rag_status")
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

@bind_user_context
@router.post("/api/save_metadata")
async def save_metadata(request: Request):
    """Save current data status as metadata for the user's RAG type."""
    user_config = request.state.user_config

    try:
        # Scan current data
        from super_starter_suite.shared.index_utils import scan_data_directory, save_data_metadata
        current_data = scan_data_directory(user_config.my_rag.data_path)

        # Save metadata for this RAG type
        success = save_data_metadata(
            user_config.my_rag.rag_root,
            user_config.my_rag.rag_type,
            current_data
        )

        if success:
            return {"message": f"Metadata saved successfully for RAG type '{user_config.my_rag.rag_type}'"}
        else:
            raise HTTPException(status_code=500, detail="Failed to save metadata")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving metadata: {str(e)}")

# ============================================================================
# DETAILED STATUS ENDPOINTS
# ============================================================================

@bind_user_context
@router.get("/api/detailed_data_status")
async def get_detailed_data_status(request: Request, rag_type: str = "RAG"):
    """
    Get detailed data status with file-by-file information for the specified RAG type.

    This endpoint provides comprehensive file information including modification dates,
    file sizes, and change status for each file in the data directory.
    """
    user_config = request.state.user_config

    # Set the RAG type for this request
    user_config.my_rag.set_rag_type(rag_type)

    try:
        from super_starter_suite.shared.index_utils import get_detailed_data_status
        detailed_status = get_detailed_data_status(user_config)
        return detailed_status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting detailed data status: {str(e)}")
