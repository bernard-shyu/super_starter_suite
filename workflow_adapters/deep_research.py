from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Dict, Any, Optional
from super_starter_suite.shared.decorators import bind_workflow_session
from super_starter_suite.shared.workflow_loader import get_workflow_config
from super_starter_suite.shared.workflow_utils import (
    validate_workflow_payload,
    create_error_response,
    log_workflow_execution,
    execute_adapter_workflow
)
from super_starter_suite.shared.dto import MessageRole, create_chat_message
from llama_index.core.workflow import StartEvent
from llama_index.server.api.models import ChatAPIMessage, ChatRequest, Artifact, ArtifactEvent
from llama_index.core.base.llms.types import MessageRole as LlamaMessageRole
from super_starter_suite.shared.artifact_utils import extract_artifact_metadata
import time
from super_starter_suite.shared.config_manager import config_manager

# UNIFIED LOGGING SYSTEM - Replace global logging
logger = config_manager.get_logger("workflow.bzlogic")
router = APIRouter()

# SINGLE HARD-CODED ID FOR CONFIG LOOKUP - All other naming comes from DTO
workflow_ID = "A_deep_research"

# Load config for derived naming (no hard-coded text beyond workflow_ID)
workflow_config = get_workflow_config(workflow_ID)
# Validation happens in workflow_loader.py - assume config is correct

@router.post("/chat")
@bind_workflow_session(workflow_config)  # Single param decorator # CRITICAL: Must come AFTER @router.post()
# Unified decorator with configuration-driven behavior flags for artifact-enabled workflow
async def chat_endpoint(request: Request, payload: Dict[str, Any]) -> JSONResponse:
    """
    Endpoint to handle chat requests for the Deep Research workflow.
    Uses direct LlamaIndex workflow execution with proper artifact extraction pattern (APPROACH E).
    Integrated with chat history system for persistent conversations.
    """
    start_time = time.time()

    try:
        # Validate request payload using shared utility
        is_valid, error_msg = validate_workflow_payload(payload)
        if not is_valid:
            error_data = {"error": error_msg, "artifacts": None}
            return JSONResponse(content=error_data, status_code=400)

        # Extract user message (already added to session by decorator)
        user_message = payload["question"]

        # Get session and context prepared by decorator
        user_config = request.state.user_config
        chat_manager = request.state.chat_manager
        session = request.state.chat_session
        chat_memory = request.state.chat_memory

        # Import workflow factory (avoid circular dependency)
        from super_starter_suite.STARTER_TOOLS.deep_research.app.workflow import create_workflow

        # Execute workflow using shared utilities (replaces 150+ lines of inline code)
        response_data = await execute_adapter_workflow(
            workflow_factory=create_workflow,
            workflow_config=workflow_config,
            user_message=user_message,
            user_config=user_config,
            chat_manager=chat_manager,
            session=session,
            chat_memory=chat_memory,
            logger=logger
        )

        # Log execution with elapsed duration
        log_workflow_execution("Deep Research", user_message, True, (time.time() - start_time))

        return JSONResponse(content=response_data, status_code=status.HTTP_200_OK)

    except HTTPException:
        raise
    except Exception as e:
        # Calculate duration even for exceptions
        duration = time.time() - start_time

        # Log unexpected error
        log_workflow_execution("Deep Research", payload.get("question", "unknown"), False, duration)
        logger.error(f"Deep Research workflow error: {str(e)}", exc_info=True)

        # Return formatted error response
        error_data = {"error": f"Unexpected error: {str(e)}", "artifacts": None}
        return JSONResponse(content=error_data, status_code=500)
