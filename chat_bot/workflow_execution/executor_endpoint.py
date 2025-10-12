"""
Chat Executor - Unified Workflow Execution API

This module provides unified chat endpoints that execute workflows with
consistent Chat History session management across all workflow types.

Provides:
- Standardized chat execution API: /api/chat/{workflow}/session/{session_id}
- Unified session handling using WorkflowSessionBridge
- Workflow routing to appropriate adapters
- Consistent request/response formats across all workflows
- Integration with chat_history session management
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
from datetime import datetime
import importlib
import logging
import json
from super_starter_suite.shared.config_manager import config_manager
from super_starter_suite.shared.workflow_loader import get_all_workflow_configs
from super_starter_suite.chat_bot.session_authority import session_authority as _session_authority

# Get logger for chat executor
executor_logger = config_manager.get_logger("history.executor")

# Create router for unified chat endpoints
router = APIRouter()

def get_workflow_import_paths():
    """
    Build workflow import path mappings from system configuration.
    Uses the code_path field from workflow configs to construct full import paths.
    """
    workflow_configs = get_all_workflow_configs()

    import_paths = {}
    for workflow_id, config in workflow_configs.items():
        code_path = config.code_path  # e.g., "workflow_adapters.agentic_rag"
        full_path = f"super_starter_suite.{code_path}"
        import_paths[workflow_id] = full_path

    return import_paths

# Build import path mapping at module load time
WORKFLOW_IMPORT_PATHS = get_workflow_import_paths()

@router.post("/chat/{workflow}/session/{session_id}")
async def execute_chat_with_session(
    request: Request,
    workflow: str,
    session_id: Optional[str],
    chat_request: Dict[str, Any]
) -> JSONResponse:
    """
    Unified chat execution endpoint for any workflow with session management.

    URL Pattern: POST /api/chat/{workflow}/session/{session_id}
    - {workflow}: Workflow name (agentic_rag, code_generator, etc.)
    - {session_id}: Session ID for Chat History (optional - will create new if None)

    Request Body:
    {
        "question": "user message",
        "parameters": { ... workflow-specific parameters ... }
    }

    Response:
    {
        "session_id": "session-uuid",
        "message_id": "ai-message-uuidv4",  # ID of AI response for artifact association
        "response": "AI response content",
        "artifacts": [...],
        "workflow": "workflow_name",
        "timestamp": "2025-09-22T21:56:34Z",
        "execution_time": 1.23,
        "status": "success"
    }
    """
    start_time = datetime.now()

    try:
        # Validate workflow name
        if workflow not in WORKFLOW_IMPORT_PATHS:
            executor_logger.error(f"❌ Unsupported workflow '{workflow}'. Supported: {list(WORKFLOW_IMPORT_PATHS.keys())}")
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported workflow: {workflow}. Supported: {', '.join(WORKFLOW_IMPORT_PATHS.keys())}"
            )

        # Validate request payload
        if "question" not in chat_request or not chat_request["question"].strip():
            executor_logger.warning(f"❌ BAD REQUEST: Missing or empty question in request. session_id={session_id}, workflow={workflow}")
            raise HTTPException(status_code=400, detail="Request must contain a non-empty 'question' field")

        user_config = request.state.user_config
        user_question = chat_request["question"]

        executor_logger.info(f"Chat request: workflow={workflow}, session={session_id}, user_question={user_question[:100]}...")

        # Log request details for debugging resume chat issues
        executor_logger.info(f"📝 Chat details: workflow='{workflow}' ({workflow in WORKFLOW_IMPORT_PATHS}), session='{session_id}', is_new={'true' if session_id == 'new' else 'false'}")
        executor_logger.debug(f"Request payload: {chat_request}")

        # 1. Setup unified chat session using WorkflowSessionBridge (maintains compatibility)
        # For "new" sessions, use Bridge to create new session; for existing sessions, use Bridge to load
        from super_starter_suite.shared.workflow_session_bridge import WorkflowSessionBridge

        normalized_session_id = session_id if session_id and session_id != "new" else None

        session_data = WorkflowSessionBridge.ensure_chat_session(
            workflow_name=workflow,
            user_config=user_config,
            session_id=normalized_session_id
        )
        session = session_data['session']
        memory = session_data['memory']
        is_new_session = session_data.get('is_new', False)

        if is_new_session:
            executor_logger.debug(f"WorkflowSessionBridge created new session {session.session_id[:8]}... for {workflow}")
        else:
            executor_logger.debug(f"WorkflowSessionBridge loaded existing session {session.session_id[:8]}... for {workflow}")

        # 2. Route to appropriate workflow adapter
        workflow_result = await _execute_workflow_adapter(
            workflow, user_config, user_question, session.session_id, memory, chat_request
        )

        # Extract artifacts and conversational response separately (now properly populated by workflow adapter)
        workflow_response = workflow_result.get('response', '')
        artifacts = workflow_result.get('artifacts', [])

        # 3. Save the AI response using unified session bridge
        # Workflow adapter now provides proper conversational responses from planning step
        # Only generate synthetic response if still empty (fallback for edge cases)
        if not workflow_response.strip():
            # Generate synthetic response for artifact-focused workflows
            num_artifacts = len(artifacts) if artifacts else 0
            if num_artifacts > 0:
                workflow_response = f"Generated {num_artifacts} artifact{'s' if num_artifacts > 1 else ''} (see panel for details)"
            else:
                workflow_response = "Request processed successfully"

        # 3. Save messages using ChatHistoryManager directly (since SessionAuthority established the active session)
        # CRITICAL: Capture ONLY AI message_id for artifact association - simplifies API and avoids confusion
        # Message ID is UUIDv4 format string like "3a9697f4-3353-44e3-ad6b-d63c3a4b1f88"
        # Frontend uses this ID to match artifacts to the AI response message in chat interface
        from super_starter_suite.chat_bot.chat_history.chat_history_manager import ChatHistoryManager
        from super_starter_suite.shared.dto import MessageRole, create_chat_message

        chat_manager = ChatHistoryManager(user_config)

        # SET ACTIVE SESSION: Currently worked-on session becomes the active working session (SINGLE RESPONSIBILITY)
        # NEW sessions: Auto-set as active when created
        # EXISTING sessions: Set as active when resumed and used
        try:
            # Ask ChatHistoryManager to set this session (new or resumed) as the active session for the workflow
            chat_manager.set_active_session(workflow, session.session_id)
            session_type = "new" if is_new_session else "resumed"
            executor_logger.info(f"✅ Set {session_type} session {session.session_id[:8]}... as ACTIVE for {workflow}")
        except Exception as e:
            executor_logger.error(f"❌ FAILED to set active session {session.session_id[:8]}... for {workflow}: {e}")
            # This is critical - if we can't set the active session, at least log it
            raise

        # Save user message (if not already saved by workflow adapter) - no need to capture ID
        try:
            # Add user message to session if not already present
            user_messages = [msg for msg in session.messages if msg.role == MessageRole.USER and msg.content == user_question]
            if not user_messages:
                user_msg = create_chat_message(role=MessageRole.USER, content=user_question)
                chat_manager.add_message_to_session(session, user_msg)
        except Exception as e:
            executor_logger.warning(f"User message saving failed (likely already saved by workflow): {e}")

        # Save AI response to session - PRIMARY MESSAGE FOR ARTIFACTS
        # message_id: UUIDv4 of the AI response message where artifacts are linked
        # Frontend artifact buttons use this ID to load/generate artifact UIs
        message_id = None
        ai_msg = create_chat_message(role=MessageRole.ASSISTANT, content=workflow_response)
        if artifacts:
            saved_ai_msg = chat_manager.add_message_with_artifacts(session, workflow_response, artifacts)
            message_id = saved_ai_msg.message_id if saved_ai_msg else None
        else:
            saved_ai_msg = chat_manager.add_message_to_session(session, ai_msg)
            message_id = saved_ai_msg.message_id if saved_ai_msg else None

        if message_id:
            executor_logger.debug(f"Saved AI message with ID: {message_id} (artifacts: {len(artifacts) if artifacts else 0})")

        executor_logger.debug(f"✅ Messages saved to session {session.session_id[:8]}... for {workflow}")

        # 4. Prepare standardized response with artifacts as top-level field
        execution_time = (datetime.now() - start_time).total_seconds()
        response_data = {
            "session_id": session.session_id,
            "message_id": message_id,  # ONLY AI message ID - artifacts are always linked to AI responses
            "response": workflow_response,
            "artifacts": artifacts if artifacts else None,  # Add artifacts as top-level field
            "workflow": workflow,
            "timestamp": datetime.now().isoformat() + "Z",
            "execution_time": round(execution_time, 2),
            "status": "success"
        }

        executor_logger.info(".2f")

        return JSONResponse(content=response_data, status_code=200)

    except HTTPException:
        raise
    except Exception as e:
        execution_time = (datetime.now() - start_time).total_seconds()
        error_msg = f"Chat execution failed for workflow '{workflow}': {str(e)}"
        executor_logger.error(f"{error_msg} (execution_time: {execution_time:.2f}s)")
        raise HTTPException(status_code=500, detail=error_msg)


async def _execute_workflow_adapter(
    workflow: str,
    user_config,
    user_question: str,
    session_id: str,
    memory,
    chat_request: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Route execution to the appropriate workflow adapter.

    Returns the workflow response as a structured dict containing 'response' and 'artifacts' fields.
    """
    # Prepare payload for workflow adapter (maintain compatibility)
    workflow_payload = {
        "question": user_question,
        "session_id": session_id,
        **chat_request.get("parameters", {})
    }

    # Get the import path for this workflow
    try:
        module_path = WORKFLOW_IMPORT_PATHS[workflow]
    except KeyError:
        raise HTTPException(
            status_code=500,
            detail=f"No import path configured for workflow '{workflow}'"
        )

    try:
        # Import the workflow module
        module = importlib.import_module(module_path)
        router = getattr(module, 'router', None)

        if not router:
            executor_logger.warning(f"No router found in {module_path}")
            raise HTTPException(
                status_code=500,
                detail=f"No router found for workflow '{workflow}'"
            )

        # Get the chat endpoint handler
        chat_endpoint = None
        for route in router.routes:
            if hasattr(route, 'path') and route.path.endswith('/chat'):
                chat_endpoint = route.endpoint
                break

        if not chat_endpoint:
            executor_logger.warning(f"No /chat endpoint found in {module_path}")
            raise HTTPException(
                status_code=500,
                detail=f"No /chat endpoint found for workflow '{workflow}'"
            )

        # Create mock request for workflow execution
        from fastapi import Request
        from unittest.mock import Mock
        import asyncio

        # Create mock request object
        mock_request = Mock(spec=Request)
        mock_request.url = f"http://localhost:8000/api/chat/{workflow}/session/{session_id}"
        mock_request.method = "POST"
        mock_request.state.user_id = getattr(user_config, 'user_id', 'default')
        mock_request.state.user_config = user_config

        # Execute the workflow adapter
        executor_logger.debug(f"Routing to workflow adapter: {module_path}")

        # Call the async endpoint
        response = await chat_endpoint(mock_request, workflow_payload)

        # Extract and parse response content from workflow adapters
        # Workflow adapters return JSONResponse with structured {"response": "", "artifacts": [...]}
        try:
            if hasattr(response, 'body'):
                # FastAPI response with body (JSONResponse typically)
                response_content = response.body.decode('utf-8') if isinstance(response.body, bytes) else str(response.body)

                # Try to parse as JSON first (workflow adapters return structured JSON)
                try:
                    parsed_response = json.loads(response_content)
                    executor_logger.debug(f"Parsed JSON response from {workflow}: keys={list(parsed_response.keys())}")
                    return parsed_response
                except json.JSONDecodeError:
                    executor_logger.warning(f"Could not parse as JSON, treating as plain text: {response_content[:100]}...")

            # Fallback handling for other response types or non-JSON responses
            elif hasattr(response, 'content') and hasattr(response, 'media_type') and 'json' in response.media_type:
                # JSON HTMLResponse
                try:
                    parsed_response = json.loads(response.content)
                    return parsed_response
                except json.JSONDecodeError:
                    pass

        except Exception as parse_error:
            executor_logger.warning(f"Error parsing workflow response: {parse_error}")

        # Fall back to string handling if JSON parsing fails
        if hasattr(response, 'body'):
            response_content = response.body.decode('utf-8') if isinstance(response.body, bytes) else str(response.body)
        elif hasattr(response, 'content'):
            response_content = str(response.content)
        else:
            response_content = str(response)

        # Clean up HTML tags if present
        import re
        clean_response = re.sub(r'<[^>]+>', '', response_content).strip()

        # Return as structured response (without artifacts if JSON parsing failed)
        return {"response": clean_response, "artifacts": None}

    except Exception as e:
        error_msg = f"Failed to execute workflow {module_path}: {e}"
        executor_logger.warning(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


@router.get("/chat/{workflow}/sessions")
async def list_workflow_sessions(request: Request, workflow: str):
    """
    List all sessions for a specific workflow.

    Returns session metadata for the specified workflow type.
    """
    if workflow not in WORKFLOW_IMPORT_PATHS:
        raise HTTPException(status_code=400, detail=f"Unsupported workflow: {workflow}")

    user_config = request.state.user_config

    try:
        # Use bridge to get session info (this could be extended in the bridge)
        # For now, return basic placeholder structure - more implementation needed
        sessions_info = {
            "workflow": workflow,
            "sessions": [],
            "note": "Session listing integration in progress - use individual workflow endpoints"
        }

        return JSONResponse(content=sessions_info)

    except Exception as e:
        executor_logger.error(f"Error listing sessions for {workflow}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")


@router.get("/chat/{workflow}/session/{session_id}/status")
async def get_session_status(request: Request, workflow: str, session_id: str):
    """
    Get status information for a specific workflow session.
    """
    if workflow not in WORKFLOW_IMPORT_PATHS:
        raise HTTPException(status_code=400, detail=f"Unsupported workflow: {workflow}")

    user_config = request.state.user_config

    try:
        # Get session status using SessionAuthority (SINGLE SOURCE OF TRUTH)
        session_status = _session_authority.get_session_status(workflow, user_config)

        if not session_status:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        return JSONResponse(content=session_status)

    except HTTPException:
        raise
    except Exception as e:
        executor_logger.error(f"Error getting session status for {workflow}:{session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get session status: {str(e)}")


# Export the router for inclusion in main FastAPI app
__all__ = ['router']
