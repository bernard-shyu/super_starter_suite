from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import HTMLResponse
from typing import Dict, Any
from super_starter_suite.shared.decorators import bind_workflow_session_porting
from super_starter_suite.shared.workflow_utils import validate_workflow_payload, create_error_response, log_workflow_execution
from super_starter_suite.shared.dto import MessageRole, create_chat_message
from super_starter_suite.STARTER_TOOLS.agentic_rag.app.workflow import create_workflow
from llama_index.core.agent.workflow.workflow_events import AgentWorkflowStartEvent
from llama_index.server.models.chat import ChatAPIMessage, ChatRequest
from llama_index.core.base.llms.types import MessageRole as LlamaMessageRole
import time
from super_starter_suite.shared.config_manager import config_manager

# UNIFIED LOGGING SYSTEM
porting_logger = config_manager.get_logger("workflow")
router = APIRouter()

@router.post("/chat")
@bind_workflow_session_porting("agentic-rag")  # CRITICAL: Must come AFTER @router.post()
# Provides complete chat session management for porting workflows
# Handles user context + persistent sessions + message management
async def chat_endpoint(request: Request, payload: Dict[str, Any]) -> HTMLResponse:
    """
    Endpoint to handle chat requests for the ported Agentic RAG workflow.

    The @bind_workflow_session_porting("agentic-rag") decorator provides:
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
            error_html, status_code = create_error_response(error_msg, "Agentic RAG", 400)
            return HTMLResponse(content=error_html, status_code=status_code)

        # Extract user message (already added to session by decorator)
        user_message = payload["question"]

        # Get session and context prepared by decorator
        user_config = request.state.user_config
        chat_manager = request.state.chat_manager
        session = request.state.chat_session
        chat_memory = request.state.chat_memory

        porting_logger.debug(f"Workflow endpoint ready: Session {session.session_id} with {len(session.messages)} messages")

        # Create ChatRequest object for user context
        chat_request = ChatRequest(
            id=request.state.user_id,
            messages=[ChatAPIMessage(role=LlamaMessageRole.USER, content=user_message)],
        )

        # Create workflow start event with chat memory
        start_event = AgentWorkflowStartEvent(
            user_msg=user_message,
            chat_history=None,
            memory=chat_memory,
            max_iterations=None
        )

        # Execute workflow
        workflow = create_workflow(chat_request=chat_request)
        result = await workflow.run(start_event=start_event)
        porting_logger.debug(f"Workflow completed successfully: {result}")

        # Extract response content (porting-specific result handling)
        if hasattr(result, 'response') and result.response:
            response_content = str(result.response.content)
        else:
            response_content = str(result) if result else "Agentic RAG workflow completed successfully"

        # Save assistant response to session (decorator-prepared chat_manager handles persistence)
        assistant_msg = create_chat_message(role=MessageRole.ASSISTANT, content=response_content)
        chat_manager.add_message_to_session(session, assistant_msg)
        porting_logger.debug(f"Saved assistant response to session {session.session_id}")

        # Format response (porting uses plain paragraph format)
        response_html = f"<p>{response_content}</p>"

        # Log successful execution
        log_workflow_execution("Agentic RAG", user_message, True, (time.time() - start_time))
        return HTMLResponse(content=response_html, status_code=status.HTTP_200_OK)

    except HTTPException:
        raise
    except Exception as e:
        # Log error and return formatted response
        duration = time.time() - start_time
        log_workflow_execution("Agentic RAG", payload.get("question", "unknown"), False, duration)
        porting_logger.error(f"Agentic RAG workflow error: {str(e)}", exc_info=True)

        error_html, status_code = create_error_response(f"Unexpected error: {str(e)}", "Agentic RAG")
        return HTMLResponse(content=error_html, status_code=status_code)
