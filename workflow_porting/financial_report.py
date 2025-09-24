from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import HTMLResponse
from typing import Dict, Any
from super_starter_suite.shared.decorators import bind_workflow_session_porting
from super_starter_suite.shared.workflow_utils import validate_workflow_payload, create_error_response, log_workflow_execution
from super_starter_suite.STARTER_TOOLS.financial_report.app.workflow import create_workflow
from llama_index.core.agent.workflow.workflow_events import AgentWorkflowStartEvent
from llama_index.server.models.chat import ChatAPIMessage, ChatRequest
from super_starter_suite.shared.dto import MessageRole, create_chat_message
from llama_index.core.base.llms.types import MessageRole as LlamaMessageRole
import time
from super_starter_suite.shared.config_manager import config_manager

# UNIFIED LOGGING SYSTEM - Replace global logging
porting_logger = config_manager.get_logger("workflow")
router = APIRouter()

@router.post("/chat")
@bind_workflow_session_porting("financial-report")  # Provides complete chat session management for porting workflows
async def chat_endpoint(request: Request, payload: Dict[str, Any]) -> HTMLResponse:
    """
    Endpoint to handle chat requests for the ported Financial Report workflow.
    Uses direct LlamaIndex workflow execution with proper AgentWorkflowStartEvent pattern.
    Integrated with chat history system for persistent conversations.
    """
    start_time = time.time()

    try:
        # Validate request payload using shared utility
        is_valid, error_msg = validate_workflow_payload(payload)
        if not is_valid:
            error_html, status_code = create_error_response(error_msg, "Financial Report", 400)
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

        # Instantiate and run the workflow with the start event
        workflow = create_workflow(chat_request=chat_request)
        result = await workflow.run(start_event=start_event)
        porting_logger.debug(f"Workflow completed successfully: {result}")

        # Handle AgentOutput result properly
        if hasattr(result, 'response') and result.response:
            response_content = str(result.response.content)
        else:
            response_content = str(result) if result else "Financial report completed successfully"

        # Save assistant response to session (decorator-prepared chat_manager handles persistence)
        assistant_msg = create_chat_message(role=MessageRole.ASSISTANT, content=response_content)
        chat_manager.add_message_to_session(session, assistant_msg)
        porting_logger.debug(f"Saved assistant response to session {session.session_id}")

        # Format as HTML response
        response_html = f"<p>{response_content}</p>"

        # Log execution with elapsed duration
        log_workflow_execution("Financial Report", user_message, True, (time.time() - start_time))

        return HTMLResponse(content=response_html, status_code=status.HTTP_200_OK)

    except HTTPException:
        raise
    except Exception as e:
        # Calculate duration even for exceptions
        duration = time.time() - start_time

        # Log unexpected error
        log_workflow_execution("Financial Report", payload.get("question", "unknown"), False, duration)
        porting_logger.error(f"Financial Report workflow error: {str(e)}", exc_info=True)

        # Return formatted error response
        error_html, status_code = create_error_response(f"Unexpected error: {str(e)}", "Financial Report")
        return HTMLResponse(content=error_html, status_code=status_code)
