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
from super_starter_suite.shared.config_manager import config_manager
from super_starter_suite.shared.workflow_session_bridge import WorkflowSessionBridge

# Get logger for chat executor
executor_logger = config_manager.get_logger("chat_executor")

# Create router for unified chat endpoints
router = APIRouter()

# Workflow name to adapter module mapping
WORKFLOW_ADAPTERS = {
    "agentic_rag": "super_starter_suite.workflow_adapters.agentic_rag",
    "code_generator": "super_starter_suite.workflow_adapters.code_generator",
    "deep_research": "super_starter_suite.workflow_adapters.deep_research",
    "document_generator": "super_starter_suite.workflow_adapters.document_generator",
    "financial_report": "super_starter_suite.workflow_adapters.financial_report",
    "human_in_the_loop": "super_starter_suite.workflow_adapters.human_in_the_loop",
}

# Workflow name to porting module mapping (fallback)
WORKFLOW_PORTING = {
    "agentic_rag": "super_starter_suite.workflow_porting.agentic_rag",
    "code_generator": "super_starter_suite.workflow_porting.code_generator",
    "deep_research": "super_starter_suite.workflow_porting.deep_research",
    "document_generator": "super_starter_suite.workflow_porting.document_generator",
    "financial_report": "super_starter_suite.workflow_porting.financial_report",
    "human_in_the_loop": "super_starter_suite.workflow_porting.human_in_the_loop",
}

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
        "response": "AI response content",
        "workflow": "workflow_name",
        "timestamp": "2025-09-22T21:56:34Z",
        "usage": { ... optional usage stats ... },
        "status": "success"
    }
    """
    start_time = datetime.now()

    try:
        # Validate workflow name
        if workflow not in WORKFLOW_ADAPTERS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported workflow: {workflow}. Supported: {', '.join(WORKFLOW_ADAPTERS.keys())}"
            )

        # Validate request payload
        if "question" not in chat_request or not chat_request["question"].strip():
            raise HTTPException(status_code=400, detail="Request must contain a non-empty 'question' field")

        user_config = request.state.user_config
        user_question = chat_request["question"]

        executor_logger.info(f"Chat request: workflow={workflow}, session={session_id}, user_question={user_question[:100]}...")

        # 1. Setup unified chat session using bridge
        session_data = WorkflowSessionBridge.ensure_chat_session(workflow, user_config, session_id)
        session = session_data['session']
        memory = session_data['memory']

        # 2. Route to appropriate workflow adapter
        workflow_response = await _execute_workflow_adapter(
            workflow, user_config, user_question, session.session_id, memory, chat_request
        )

        # 3. Save the AI response using unified session bridge
        WorkflowSessionBridge.add_message_and_save_response(
            workflow, user_config, session, user_question, workflow_response
        )

        # 4. Prepare standardized response
        execution_time = (datetime.now() - start_time).total_seconds()
        response_data = {
            "session_id": session.session_id,
            "response": workflow_response,
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
) -> str:
    """
    Route execution to the appropriate workflow adapter.

    Returns the workflow response as a string.
    """
    # Prepare payload for workflow adapter (maintain compatibility)
    workflow_payload = {
        "question": user_question,
        "session_id": session_id,
        **chat_request.get("parameters", {})
    }

    # Try primary adapter first, then fallback to porting version
    for workflow_map in [WORKFLOW_ADAPTERS, WORKFLOW_PORTING]:
        try:
            module_path = workflow_map.get(workflow)
            if not module_path:
                continue

            # Import the workflow module
            module = importlib.import_module(module_path)
            router = getattr(module, 'router', None)

            if not router:
                executor_logger.warning(f"No router found in {module_path}")
                continue

            # Get the chat endpoint handler
            chat_endpoint = None
            for route in router.routes:
                if hasattr(route, 'path') and route.path.endswith('/chat'):
                    chat_endpoint = route.endpoint
                    break

            if not chat_endpoint:
                executor_logger.warning(f"No /chat endpoint found in {module_path}")
                continue

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

            # Extract response content (adapt for different response types)
            if hasattr(response, 'body'):
                # FastAPI response with body
                response_content = response.body.decode('utf-8') if isinstance(response.body, bytes) else str(response.body)
            elif hasattr(response, 'content'):
                # HTMLResponse or similar
                response_content = str(response.content)
            else:
                response_content = str(response)

            # Clean up HTML tags if present (workflow adapters return HTML)
            import re
            clean_response = re.sub(r'<[^>]+>', '', response_content).strip()

            return clean_response

        except Exception as e:
            executor_logger.warning(f"Failed to execute {module_path}: {e}")
            continue

    # If we reach here, no adapter worked
    raise HTTPException(
        status_code=500,
        detail=f"No compatible adapter found for workflow '{workflow}'"
    )


@router.get("/chat/{workflow}/sessions")
async def list_workflow_sessions(request: Request, workflow: str):
    """
    List all sessions for a specific workflow.

    Returns session metadata for the specified workflow type.
    """
    if workflow not in WORKFLOW_ADAPTERS:
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
    if workflow not in WORKFLOW_ADAPTERS:
        raise HTTPException(status_code=400, detail=f"Unsupported workflow: {workflow}")

    user_config = request.state.user_config

    try:
        # Get session info using bridge
        session_info = WorkflowSessionBridge.get_session_info(workflow, user_config, session_id)

        if not session_info:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        return JSONResponse(content=session_info)

    except HTTPException:
        raise
    except Exception as e:
        executor_logger.error(f"Error getting session status for {workflow}:{session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get session status: {str(e)}")


# Export the router for inclusion in main FastAPI app
__all__ = ['router']
