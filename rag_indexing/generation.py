"""
Module for orchestrating the RAG index generation process with real-time progress tracking.
"""

import os
import sys
import uuid
import json
import asyncio
from typing import Dict, Any, List, Callable, Optional, Awaitable
import logging
import threading
import time

# Logger will be configured by config_manager

# Add the project root to sys.path to enable absolute imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the actual generation logic from RAG indexing module
from super_starter_suite.rag_indexing.generate_ocr_reader import perform_rag_generation
from super_starter_suite.shared.config_manager import UserConfig

# Import metadata management functions - DELEGATED to shared/index_utils.py
# External calls removed to maintain single responsibility principle

# MVC Controller removed - all MVC processing through session's GenerateManager
# No global state dependencies - clean session-based architecture

# Import centralized logging
from super_starter_suite.shared.config_manager import config_manager
# Get logger for generation component
gen_logger = config_manager.get_logger("generation")

# In-memory store for generation tasks
generation_tasks: Dict[str, Dict] = {}

# Import terminal output functionality from separated module
from .terminal_output import (
    RealTimeLogCaptureHandler,
    get_generation_logs,
    clear_generation_logs
)

async def run_generation_with_progress(
    user_config: UserConfig,
    task_id: str,
    progress_callback: Callable[[str], Awaitable[None]],
    status_callback: Optional[Callable[[str, str], Awaitable[None]]] = None
):
    """
    Run RAG generation with callback-based progress tracking.

    MVC processing is handled by the calling session's GenerateManager through callbacks.
    No global state dependencies - clean session-based architecture.

    Args:
        user_config: User configuration
        task_id: Unique task identifier
        progress_callback: Callback for processing raw log messages
        status_callback: Optional callback for status updates
    """
    generation_tasks[task_id] = {"status": "running", "user_id": user_config.user_id, "method": user_config.my_rag.generate_method}

    # MVC Controller removed - using session-based GenerateManager for MVC processing
    # Progress tracking handled by session's GenerateManager, not global controller

    # Get event loop for thread-safe communication
    loop = asyncio.get_event_loop()

    # Set up real-time log capture with callback for MVC processing
    log_capture_handler = RealTimeLogCaptureHandler(task_id, progress_callback, loop)
    log_capture_handler.setLevel(logging.DEBUG)  # Capture all levels for real-time streaming

    # Add handler to MVC_terminal logger (single source architecture)
    # Both generate_ocr_reader.py and terminal_output.py now use MVC_terminal
    import logging as builtin_logging
    builtin_logging.getLogger("MVC_terminal").addHandler(log_capture_handler)

    try:
        gen_logger.info("Starting RAG generation: task_id=%s, user=%s, method=%s, RAG_type=%s",
            task_id, user_config.user_id, user_config.my_rag.generate_method, user_config.my_rag.rag_type)

        # MVC messages handled by callback - no global controller dependency

        # Set environment variable for progress tracking
        original_debug_value = os.environ.get('RAG_GENERATE_DEBUG')
        os.environ['RAG_GENERATE_DEBUG'] = '2'

        try:
            # Execute generation in background thread to allow progress monitoring

            def run_generation():
                """Run generation in background thread"""
                try:
                    perform_rag_generation(
                        extractor=user_config.my_rag.generate_method,
                        user_rag_root=user_config.my_rag.rag_root,
                        model_config=user_config.my_rag.model_config,
                        data_path=user_config.my_rag.data_path,
                        storage_path=user_config.my_rag.storage_path
                    )
                except Exception as e:
                    raise e

            # Run generation in thread pool to allow concurrent progress monitoring
            await asyncio.get_event_loop().run_in_executor(None, run_generation)

            # MVC completion handled by callback - no global controller

            # Send task_completed message via WebSocket for proper UI completion handling
            try:
                # Import WebSocket cleanup function
                from super_starter_suite.rag_indexing.generate_websocket import cleanup_task_connections
                await cleanup_task_connections(task_id)
                gen_logger.info(f"WebSocket cleanup completed for task {task_id}")
            except Exception as ws_error:
                gen_logger.warning(f"Failed to cleanup WebSocket connections for task {task_id}: {ws_error}")

            # Update status if callback provided
            if status_callback:
                await status_callback("completed", "Generation finished successfully")

        except Exception as generation_error:
            error_msg = f"Generation failed: {str(generation_error)}"
            # MVC error handling via callback - no global controller
            if status_callback:
                await status_callback("failed", error_msg)
            raise generation_error

        finally:
            # Restore environment variable
            if original_debug_value is not None:
                os.environ['RAG_GENERATE_DEBUG'] = original_debug_value
            else:
                os.environ.pop('RAG_GENERATE_DEBUG', None)

        # Save metadata after successful generation
        try:
            # DELEGATE metadata operations to shared/index_utils.py
            # External calls removed to maintain single responsibility principle
            gen_logger.info(f"Metadata operations delegated to shared/index_utils.py for RAG type '{user_config.my_rag.rag_type}'")

        except Exception as metadata_error:
            gen_logger.warning(f"Metadata operation failed: {metadata_error}")

        generation_tasks[task_id]["status"] = "completed"
        gen_logger.info("Generation task %s completed successfully for user %s.", task_id, user_config.user_id)

    except Exception as generation_error:
        generation_tasks[task_id]["status"] = "failed"
        generation_tasks[task_id]["error"] = str(generation_error)
        gen_logger.error("Generation task %s failed for user %s: %s", task_id, user_config.user_id, generation_error)
        raise

    finally:
        # Remove the log capture handler from MVC_terminal logger
        builtin_logging.getLogger("MVC_terminal").removeHandler(log_capture_handler)

async def run_generation_script(
    user_config: UserConfig,
    task_id: str | None = None
):
    """
    Legacy function for backward compatibility.
    Use run_generation_with_progress for real-time updates.
    """
    # Use provided task_id or generate a UUID as fallback
    if task_id is None:
        task_id = str(uuid.uuid4())

    # Create dummy callbacks for backward compatibility
    async def dummy_progress_callback(raw_message: str):
        pass

    async def dummy_status_callback(status: str, message: str):
        pass

    # Run with dummy callbacks
    await run_generation_with_progress(
        user_config=user_config,
        task_id=task_id,
        progress_callback=dummy_progress_callback,
        status_callback=dummy_status_callback
    )

def get_generation_status(task_id: str) -> Dict:
    """
    Retrieve the status of a generation task.
    """
    return generation_tasks.get(task_id, {"status": "unknown"})

def get_generation_logs(task_id: str) -> List[str]:
    """
    Retrieve the logs for a generation task.
    DELEGATES TO: terminal_output module for log management.
    """
    from .terminal_output import generation_logs
    return generation_logs.get(task_id, [])
