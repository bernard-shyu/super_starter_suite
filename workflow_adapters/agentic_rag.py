from fastapi import APIRouter, Request, BackgroundTasks, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Dict, Any
import time
from super_starter_suite.shared.config_manager import config_manager
from super_starter_suite.shared.decorators import bind_workflow_session
from super_starter_suite.shared.workflow_utils import (
    validate_workflow_payload,
    create_error_response,
    log_workflow_execution,
    execute_agentic_workflow
)
from super_starter_suite.shared.workflow_loader import get_workflow_config
from super_starter_suite.shared.dto import MessageRole, create_chat_message
from llama_index.core.agent.workflow.workflow_events import AgentWorkflowStartEvent
from llama_index.server.models.chat import ChatAPIMessage, ChatRequest
from llama_index.core.base.llms.types import MessageRole as LlamaMessageRole

# UNIFIED LOGGING SYSTEM
logger = config_manager.get_logger("workflow.bzlogic")
router = APIRouter()

# SINGLE HARD-CODED ID FOR CONFIG LOOKUP - All other naming comes from DTO
workflow_ID = "A_agentic_rag"

# Load config for derived naming (no hard-coded text beyond workflow_ID)
workflow_config = get_workflow_config(workflow_ID)
# Validation happens in workflow_loader.py - assume config is correct

@router.post("/chat")
@bind_workflow_session(workflow_config)  # Single param decorator # CRITICAL: Must come AFTER @router.post()
# Unified decorator with configuration-driven behavior flags
async def chat_endpoint(request: Request, payload: Dict[str, Any]) -> JSONResponse:
    """
    Endpoint to handle chat requests for the Agentic RAG workflow.

    The @bind_workflow_session("agentic-rag") decorator provides:
    - User context initialization and LLM setup
    - Persistent chat session management (one session per workflow)
    - Automatic user message addition to session
    - Chat memory preparation for workflow context

    This endpoint focuses solely on workflow execution and response handling.
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

        # Get workflow context (decorator provides session, chat memory, etc.)
        from super_starter_suite.STARTER_TOOLS.agentic_rag.app.workflow import create_workflow

        # Execute AgentWorkflow using shared utilities (replaces inline AgentWorkflowStartEvent handling)
        response_data = await execute_agentic_workflow(
            workflow_factory=create_workflow,
            workflow_config=workflow_config,
            user_message=user_message,
            user_config=user_config,
            chat_manager=chat_manager,
            session=session,
            chat_memory=chat_memory,
            logger=logger
        )

        # Log successful execution
        log_workflow_execution("Agentic RAG", user_message, True, (time.time() - start_time))
        return JSONResponse(content=response_data, status_code=status.HTTP_200_OK)

    except HTTPException:
        raise
    except Exception as e:
        # Log error and return formatted response
        duration = time.time() - start_time
        log_workflow_execution("Agentic RAG", payload.get("question", "unknown"), False, duration)
        logger.error(f"Agentic RAG workflow error: {str(e)}", exc_info=True)

        error_data = {"error": f"Unexpected error: {str(e)}", "artifacts": None}
        return JSONResponse(content=error_data, status_code=500)
