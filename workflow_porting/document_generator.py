from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import HTMLResponse
from typing import Dict, Any
from super_starter_suite.shared.decorators import bind_user_context
from super_starter_suite.shared.workflow_utils import validate_workflow_payload, create_error_response, log_workflow_execution
from super_starter_suite.STARTER_TOOLS.document_generator.app.workflow import create_workflow
from llama_index.core.agent.workflow.workflow_events import AgentWorkflowStartEvent
from llama_index.server.models.chat import ChatAPIMessage, ChatRequest
from super_starter_suite.shared.dto import MessageRole, create_chat_message
from llama_index.core.base.llms.types import MessageRole as LlamaMessageRole
import time
from super_starter_suite.shared.config_manager import config_manager

# UNIFIED LOGGING SYSTEM - Replace global logging
porting_logger = config_manager.get_logger("porting")
router = APIRouter()

@router.post("/chat")
@bind_user_context
async def chat_endpoint(request: Request, payload: Dict[str, Any]) -> HTMLResponse:
    """
    Endpoint to handle chat requests for the ported Document Generator workflow.
    Uses direct LlamaIndex workflow execution with proper AgentWorkflowStartEvent pattern.
    Integrated with chat history system for persistent conversations.
    """
    start_time = time.time()

    try:
        # Validate request payload using shared utility
        is_valid, error_msg = validate_workflow_payload(payload)
        if not is_valid:
            error_html, status_code = create_error_response(error_msg, "Document Generator", 400)
            return HTMLResponse(content=error_html, status_code=status_code)

        # Extract parameters from payload
        user_message = payload["question"]
        session_id = payload.get("session_id")  # Optional session ID for chat history

        # Get user context from request state
        user_id = request.state.user_id
        user_config = request.state.user_config
        porting_logger.debug(f"Document Generator workflow request: URL={request.url}  USER={user_id}  SESSION={session_id}  MSG={user_message[:100]}...")

        # Use ChatHistoryManager for persistent chat sessions
        chat_memory = None
        if session_id:
            from super_starter_suite.chat_history.chat_history_manager import ChatHistoryManager
            chat_manager = ChatHistoryManager(user_config)

            # Load or create session
            session = chat_manager.load_session("document_generator", session_id)
            if not session:
                # Create new session if it doesn't exist
                session = chat_manager.create_new_session("document_generator")

            # Add user message to session
            from super_starter_suite.shared.dto import MessageRole, create_chat_message
            user_msg = create_chat_message(role=MessageRole.USER, content=user_message)
            chat_manager.add_message_to_session(session, user_msg)

            # Get LlamaIndex memory for conversation context
            chat_memory = chat_manager.get_llama_index_memory(session)

            porting_logger.debug(f"Loaded chat session {session_id} with {len(session.messages)} messages")

        # Create ChatRequest object for user context
        chat_request = ChatRequest(
            id=user_id,
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
            response_content = str(result) if result else "Document generation completed successfully"

        # Save assistant response to chat session
        if session_id and chat_memory:
            from super_starter_suite.chat_history.chat_history_manager import ChatHistoryManager
            chat_manager = ChatHistoryManager(user_config)
            session = chat_manager.load_session("document_generator", session_id)
            if session:
                # Add assistant response to session
                assistant_msg = create_chat_message(role=MessageRole.ASSISTANT, content=response_content)
                chat_manager.add_message_to_session(session, assistant_msg)
                porting_logger.debug(f"Saved assistant response to session {session_id}")

        # Format as HTML response
        response_html = f"<p>{response_content}</p>"

        # Log execution with elapsed duration
        log_workflow_execution("Document Generator", user_message, True, (time.time() - start_time))

        return HTMLResponse(content=response_html, status_code=status.HTTP_200_OK)

    except HTTPException:
        raise
    except Exception as e:
        # Calculate duration even for exceptions
        duration = time.time() - start_time

        # Log unexpected error
        log_workflow_execution("Document Generator", payload.get("question", "unknown"), False, duration)
        porting_logger.error(f"Document Generator workflow error: {str(e)}", exc_info=True)

        # Return formatted error response
        error_html, status_code = create_error_response(f"Unexpected error: {str(e)}", "Document Generator")
        return HTMLResponse(content=error_html, status_code=status_code)
