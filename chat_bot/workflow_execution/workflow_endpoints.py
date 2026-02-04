"""
Unified Workflow Execution API Endpoints

Consolidated single entry point for ALL workflow execution operations.
Merges executor_endpoint.py and websocket_endpoint.py into one coherent module.

Provides:
- ✅ POST /workflow/{workflow_id}/session/{session_id} (chat execution)
- ✅ WS   /workflow/{workflow_id}/session/{session_id}/stream (real-time events)
- ✅ GET  /workflow/{workflow_id}/sessions (list sessions)
- ✅ GET  /workflow/{workflow_id}/session/{session_id}/status (status check)
- ✅ GET  /workflow/{workflow_id}/citations/{citation_id}/view (document viewer)
- ✅ GET  /workflow/{workflow_id}/citations (citation overview)
"""

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio
import json
import logging
import time

from super_starter_suite.shared.config_manager import config_manager, UserConfig
from super_starter_suite.shared.workflow_loader import get_all_workflow_configs
from super_starter_suite.shared.decorators import bind_user_context, bind_workflow_session
from super_starter_suite.shared.index_utils import get_document_content_by_node_id

# Import HITL response handlers
from super_starter_suite.chat_bot.human_input.hitl_response_handlers import (
    handle_cli_response_via_workflow,
    handle_text_input_response,
    handle_feedback_response,
    handle_edit_resubmit_response,
    handle_confirmation_response
)

# Get logger for workflow endpoints
endpoints_logger = config_manager.get_logger("endpoints")

# Create consolidated router for ALL workflow endpoints
router = APIRouter()

# ============================================================================
# WORKFLOW WEBSOCKET CONNECTION MANAGEMENT (from websocket_endpoint.py)
# ============================================================================

class WorkflowWebSocketManager:
    """Manages WebSocket connections for workflow event streaming"""

    def __init__(self, max_connections_per_workflow: int = 3):
        self.active_connections: Dict[str, List[WebSocket]] = {}  # workflow_id -> [websockets]
        self.workflow_sessions: Dict[str, str] = {}  # workflow_id -> session_id
        self.max_connections_per_workflow = max_connections_per_workflow
        self.connection_counts: Dict[str, int] = {}

    async def connect(self, workflow_id: str, session_id: str, websocket: WebSocket) -> bool:
        """Connect a WebSocket for a specific workflow session"""
        current_count = self.connection_counts.get(workflow_id, 0)

        if current_count >= self.max_connections_per_workflow:
            endpoints_logger.warning(f"Connection limit reached for workflow {workflow_id}")
            return False

        await websocket.accept()
        endpoints_logger.info(f"WebSocket accepted for workflow {workflow_id}, session {session_id}")

        if workflow_id not in self.active_connections:
            self.active_connections[workflow_id] = []
            self.connection_counts[workflow_id] = 0

        self.active_connections[workflow_id].append(websocket)
        self.connection_counts[workflow_id] += 1
        self.workflow_sessions[workflow_id] = session_id

        return True

    def disconnect(self, workflow_id: str, websocket: WebSocket):
        """Disconnect a WebSocket for a specific workflow"""
        if workflow_id in self.active_connections:
            if websocket in self.active_connections[workflow_id]:
                self.active_connections[workflow_id].remove(websocket)
                self.connection_counts[workflow_id] -= 1

            if not self.active_connections[workflow_id]:
                del self.active_connections[workflow_id]
                del self.connection_counts[workflow_id]
                if workflow_id in self.workflow_sessions:
                    del self.workflow_sessions[workflow_id]

    async def broadcast_to_workflow(self, workflow_id: str, message: Dict[str, Any]):
        """Broadcast message to all connections for a specific workflow"""
        if workflow_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[workflow_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    endpoints_logger.warning(f"Failed to send message to workflow {workflow_id}: {e}")
                    disconnected.append(connection)

            # Clean up disconnected connections
            for connection in disconnected:
                self.disconnect(workflow_id, connection)

    def get_connection_count(self, workflow_id: str) -> int:
        """Get current connection count for a workflow"""
        return self.connection_counts.get(workflow_id, 0)

    def get_active_workflows(self) -> List[str]:
        """Get list of workflows with active connections"""
        return list(self.active_connections.keys())

# Global workflow WebSocket manager instance
workflow_websocket_manager = WorkflowWebSocketManager()

# WebSocket-specific exception class
class WebSocketException(Exception):
    """Exception raised for WebSocket validation errors"""
    pass

# ============================================================================
# WORKFLOW IMPORT PATH MANAGEMENT (from executor_endpoint.py)
# ============================================================================

def get_workflow_import_paths() -> Dict[str, str]:
    """
    Build workflow import path mappings from system configuration.
    """
    workflow_configs = get_all_workflow_configs()

    import_paths = {}
    for workflow_id, config in workflow_configs.items():
        full_path = f"super_starter_suite.{config.code_path}"
        import_paths[workflow_id] = full_path

    return import_paths

# Build import path mapping at module load time
WORKFLOW_IMPORT_PATHS = get_workflow_import_paths()

# ============================================================================
# SHARED SESSION BINDING UTILITY (replaces problematic decorators)
# ============================================================================

def _extract_validate_session_context(session_id: str) -> tuple[str, str, Any, Any, Any]:
    """
    COMMON INTERNAL FUNCTION: Extract and validate all session context from session_id

    Core logic shared between HTTP and WebSocket endpoints.
    Performs comprehensive validation of session infrastructure.

    Args:
        session_id: Session ID to extract context from

    Returns:
        tuple: (workflow_id, user_id, user_config, session_handler, chat_manager)

    Raises:
        HTTPException: For HTTP endpoints
        WebSocketException: For WebSocket endpoints (defined below)
    """
    from super_starter_suite.chat_bot.session_manager import WorkflowSession
    from super_starter_suite.shared.session_utils import SESSION_REGISTRY

    # Get session handler from global registry
    session_handler = SESSION_REGISTRY.get(session_id)
    if not session_handler:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    # Validate WorkflowSession type
    if not isinstance(session_handler, WorkflowSession):
        raise HTTPException(status_code=400, detail=f"Invalid session type for {session_id}: expected WorkflowSession, got {type(session_handler)}")

    # Extract workflow_id from session
    workflow_id = getattr(session_handler, 'active_workflow_id', None)
    if not workflow_id:
        raise HTTPException(status_code=400, detail=f"No workflow_id in session {session_id}")

    # Validate workflow exists
    if workflow_id not in WORKFLOW_IMPORT_PATHS:
        raise HTTPException(status_code=400, detail=f"Unsupported workflow: {workflow_id}. Supported: {', '.join(WORKFLOW_IMPORT_PATHS.keys())}")

    # Get user context from session
    user_id = getattr(session_handler, 'user_id', 'unknown')
    user_config = getattr(session_handler, 'user_config', None) or config_manager.get_user_config(user_id)

    # Get chat_manager - type checker doesn't know this is WorkflowSession, so use getattr
    chat_manager = getattr(session_handler, 'chat_manager', None)  # type: ignore[attr]
    if not chat_manager:
        raise HTTPException(status_code=500, detail=f"No chat_manager in session {session_id}")

    return workflow_id, user_id, user_config, session_handler, chat_manager

def extract_workflow_context_variables(request: Request) -> tuple[str, str, Any, Any, Any]:
    """
    SHIM FUNCTION: Extract session context from HTTP request

    Delegates to common internal function after extracting session_id from request.
    Used by HTTP endpoints with @bind_workflow_session decorator.

    Returns:
        tuple: (workflow_id, user_id, user_config, session_handler, chat_manager)
    """
    # Extract session_id from request (already validated by @bind_workflow_session)
    session_handler = request.state.session_handler
    session_id = getattr(session_handler, 'session_id', None)

    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID not found in request context")

    # Delegate to common function
    return _extract_validate_session_context(session_id)

def extract_websocket_session_context(session_id: str) -> tuple[str, str, Any, Any, Any]:
    """
    SHIM FUNCTION: Extract session context for WebSocket endpoints

    Delegates to common internal function with session_id.
    Used by WebSocket endpoints that can't use @bind_workflow_session decorator.

    Returns:
        tuple: (workflow_id, user_id, user_config, session_handler, chat_manager)
    """
    try:
        # Delegate to common function
        return _extract_validate_session_context(session_id)
    except HTTPException as e:
        # Convert HTTP exceptions to WebSocket exceptions for WebSocket endpoints
        raise WebSocketException(str(e.detail))

# REMOVED: ensure_workflow_session() function replaced by @bind_workflow_session decorator
# All session binding now handled consistently by decorators

# ============================================================================
# CITATION HELPER FUNCTIONS (from executor_endpoint.py)
# ============================================================================

def _get_citation_metadata_from_sessions(workflow: str, citation_id: str, user_config: UserConfig, session_handler=None) -> Optional[Dict[str, Any]]:
    """
    Retrieve citation metadata from recent session history.
    """
    try:
        # Use injected WorkflowSession to access chat_manager
        if session_handler and hasattr(session_handler, 'chat_manager'):
            chat_manager = session_handler.chat_manager
            endpoints_logger.debug("Using WorkflowSession chat_manager for citation search")
        else:
            # Create scoped ChatHistoryManager with session_owner
            from super_starter_suite.chat_bot.chat_history.chat_history_manager import ChatHistoryManager
            from super_starter_suite.shared.session_utils import SessionBinder

            # Create a proper session for this operation
            bound_session = SessionBinder.bind_session(user_config, "workflow_session", {"workflow_id": workflow})
            chat_manager = bound_session.session_handler.chat_manager
            endpoints_logger.debug("Using newly bound WorkflowSession chat_manager for citation search")

        # Try multiple workflow name variations
        workflow_variations = [
            workflow,
            workflow.lstrip('P_').lstrip('A_'),
            workflow.replace('P_', '').replace('A_', ''),
        ]
        workflow_variations = list(set(workflow_variations))  # Remove duplicates

        endpoints_logger.debug(f"Searching for citation {citation_id} across workflow variations: {workflow_variations}")

        # Try each workflow variation
        for wf_name in workflow_variations:
            try:
                sessions = chat_manager.get_all_sessions(wf_name)
                if not sessions:
                    continue

                endpoints_logger.debug(f"Found {len(sessions)} sessions for workflow {wf_name}")

                # Search through recent messages (limit to last 5 sessions for performance)
                for session in sessions[:5]:
                    for message in reversed(session.messages):
                        if (hasattr(message, 'enhanced_metadata') and message.enhanced_metadata and
                            isinstance(message.enhanced_metadata, dict) and
                            'citation_metadata' in message.enhanced_metadata):

                            citation_meta = message.enhanced_metadata['citation_metadata']
                            if isinstance(citation_meta, dict) and citation_id in citation_meta:
                                endpoints_logger.debug(f"Found citation metadata for {citation_id} in session {session.session_id} (workflow: {wf_name})")
                                return citation_meta[citation_id]

            except Exception as e:
                endpoints_logger.debug(f"Error searching workflow {wf_name}: {e}")
                continue

        endpoints_logger.debug(f"No citation metadata found for {citation_id} in any workflow variation")
        return None

    except Exception as e:
        endpoints_logger.warning(f"Error retrieving citation metadata from sessions: {e}")
        return None

# ============================================================================
# WORKFLOW SESSION MANAGEMENT ENDPOINTS
# ============================================================================

@router.post("/workflow/create")
async def create_workflow_session(request: Request, workflow_data: Optional[Dict[str, Any]] = None):
    """
    UNIFIED WORKFLOW SESSION CREATION ENDPOINT
    Creates WorkflowSession infrastructure for workflow access.

    Can optionally bind to existing chat_session_id for session continuation.
    This enables seamless workflow transitions and session resumption.

    Parameters in workflow_data:
    - workflow_id: Required - The workflow identifier
    - include_sessions: Optional - Return chat sessions list
    - chat_session_id: Optional - Bind infrastructure to existing chat session

    When chat_session_id is provided:
    - Creates workflow infrastructure as usual
    - Binds the infrastructure's chat_manager to save to the specified chat session
    - Updates active session mapping to mark the chat session as active

    This is called when user clicks workflow to create session infrastructure.
    """
    try:
        # Extract parameters from request body
        workflow_id = None
        include_sessions = False
        chat_session_id = None

        if workflow_data and isinstance(workflow_data, dict):
            workflow_id = workflow_data.get('workflow_id')
            include_sessions = workflow_data.get('include_sessions', False)
            chat_session_id = workflow_data.get('chat_session_id')  # NEW: Optional chat session binding

        if not workflow_id:
            raise HTTPException(status_code=400, detail="workflow_id is required in request body")

        # Validate workflow exists
        if workflow_id not in WORKFLOW_IMPORT_PATHS:
            raise HTTPException(status_code=400, detail=f"Unsupported workflow: {workflow_id}")

        # Get user context
        from super_starter_suite.shared.session_utils import RequestValidator, SessionBinder
        validation = RequestValidator.validate_user_context(request)
        if not validation.is_valid:
            raise HTTPException(validation.error_code, f"User context validation failed: {validation.message}")

        # Create new WorkflowSession with workflow context
        # PASS chat_session_id into the context so bind_context handles unbinding if it's None
        bind_params = {"workflow_id": workflow_id}
        if workflow_data and "chat_session_id" in workflow_data:
            bind_params["chat_session_id"] = chat_session_id

        bound_session = SessionBinder.bind_session(request, "workflow_session", bind_params)
        bound_session.apply_to_request_state(request)

        # Validate proper session infrastructure creation
        session_handler = request.state.session_handler
        chat_manager = getattr(session_handler, 'chat_manager', None) if session_handler else None

        if not chat_manager:
            endpoints_logger.error(f"Session creation failed - chat_manager not initialized")
            raise HTTPException(status_code=500, detail="Chat manager infrastructure not available")

        # BIND TO EXISTING CHAT SESSION (if specified) - NO ACTIVE STATUS CHANGE
        # Check for key existence to handle explicit None (New Session)
        if workflow_data and "chat_session_id" in workflow_data:
            # Use bind_chat_session_id which now handles None correctly
            session_handler.bind_chat_session_id(chat_session_id)
            endpoints_logger.info(f"✅ Bound infrastructure session {session_handler.session_id} to chat session {chat_session_id}")
            
            # REMOVED: No longer automatically set as ACTIVE - ACTIVE status changes only on user messages
            # ACTIVE status is now managed by frontend based on user interactions
            endpoints_logger.debug(f"📖 Session {chat_session_id} bound for access (not marked ACTIVE)")

        endpoints_logger.debug(f"✅ Session infrastructure created for {workflow_id}: session_id={session_handler.session_id}")

        # Base response
        response_data = {
            "session_id": session_handler.session_id,
            "ready": True,
            "workflow_id": workflow_id
        }

        # Add chat session binding info if applicable
        if chat_session_id:
            response_data["bound_chat_session_id"] = chat_session_id

        # Optionally include sessions if requested (consolidated endpoint behavior)
        if include_sessions:
            sessions = session_handler.chat_manager.get_sessions_for_ui_listing(workflow_id)
            sessions_count = len(sessions.get('sessions', []))
            endpoints_logger.debug(f"✅ Retrieved {sessions_count} chat sessions for workflow {workflow_id}")

            response_data.update({
                "infrastructure_session_id": session_handler.session_id,  # Alias for compatibility
                "sessions": sessions.get('sessions', [])
            })

        return JSONResponse(content=response_data)

    except HTTPException:
        raise
    except Exception as e:
        endpoints_logger.error(f"Unexpected error in session creation: {e}")
        raise HTTPException(status_code=500, detail=f"Session creation failed: {str(e)}")


@router.delete("/workflow/{session_id}")
@bind_workflow_session()
async def destroy_workflow_session(request: Request, session_id: str):
    """
    DESTROY WORKFLOW INFRASTRUCTURE SESSION
    Following path convention: DELETE /workflow/{session_id}

    Part of generalized session lifecycle management.
    Called when leaving workflow context to clean up infrastructure.
    Uses inheritance-based dispose() method for proper cleanup.
    """
    try:
        # Extract workflow context (authorized by @bind_workflow_session decorator)
        workflow_id, user_id, user_config, session_handler, chat_manager = extract_workflow_context_variables(request)

        endpoints_logger.info(f"🗑️ Destroying workflow infrastructure session: {session_id} for workflow {workflow_id}")

        # Use inheritance-based cleanup through dispose() method
        from super_starter_suite.shared.session_utils import terminate_session_handler
        terminate_session_handler(session_id)  # Calls handler.dispose() and removes from registry

        return JSONResponse(content={
            "message": f"Workflow session {session_id} disposed via inheritance",
            "workflow_id": workflow_id
        })

    except HTTPException:
        raise
    except Exception as e:
        endpoints_logger.error(f"Error destroying workflow session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to destroy workflow session: {str(e)}")

# ============================================================================
# WORKFLOW EXECUTION ENDPOINTS (from executor_endpoint.py)
# ============================================================================

@router.post("/workflow/{session_id}/execute")
@bind_workflow_session()
async def execute_chat_with_session(
    request: Request,
    session_id: str,
    chat_request: Dict[str, Any]
) -> JSONResponse:
    """
    🎯 UNIFIED WORKFLOW EXECUTION ENDPOINT
    Execute workflows using WorkflowExecutor with consistent session handling.
    """
    try:
        # Extract all commonly used context variables
        workflow_id, user_id, user_config, session_handler, chat_manager = extract_workflow_context_variables(request)

        # Use WorkflowExecutor for unified execution
        from super_starter_suite.chat_bot.workflow_execution.workflow_executor import WorkflowExecutor

        # Extract user message from chat_request, with fallback for different formats
        user_message = ""
        if isinstance(chat_request, dict):
            user_message = chat_request.get("question", chat_request.get("message", ""))
        elif isinstance(chat_request, str):
            user_message = chat_request
        else:
            user_message = str(chat_request)

        if not user_message or not user_message.strip():
            raise HTTPException(status_code=400, detail="Request must contain a non-empty question or message field")

        result = await WorkflowExecutor.execute_workflow_request(
            workflow_id=workflow_id,
            user_message=user_message,
            request_state=request.state,
            session_id=session_id,
            logger_instance=endpoints_logger
        )

        return JSONResponse(content=result, status_code=200)

    except Exception as e:
        from super_starter_suite.chat_bot.workflow_execution.workflow_executor import WorkflowExecutionError

        if isinstance(e, WorkflowExecutionError):
            endpoints_logger.error(f"Workflow execution error: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        else:
            endpoints_logger.error(f"Unexpected error in workflow execution: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Workflow execution failed: {str(e)}")

@router.get("/workflow/{session_id}/sessions")
@bind_workflow_session()
async def list_workflow_sessions(request: Request, session_id: str):
    """
    Unified session listing with priority ordering:

    Returns:
    {
        "workflow": workflow_id,
        "sessions": [ordered_session_list],
    }
    """
    try:
        # Extract all commonly used context variables
        workflow_id, user_id, user_config, session_handler, chat_manager = extract_workflow_context_variables(request)

        # Use unified ChatHistoryManager method - session_handler is guaranteed to be WorkflowSession
        result = session_handler.chat_manager.get_sessions_for_ui_listing(workflow_id)  # type: ignore
        sessions_count = len(result.get('sessions', []))
        endpoints_logger.debug(f"✅ Successfully listed {sessions_count} sessions for workflow {workflow_id}")

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        endpoints_logger.error(f"Unexpected error in list_workflow_sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Session listing failed: {str(e)}")

# REMOVED: get_workflow_active_session endpoint functionality merged into list_workflow_sessions

@router.get("/workflow/{session_id}/status")
@bind_workflow_session()
async def get_session_status(request: Request, session_id: str):
    """
    Get status information for a specific workflow session.
    """
    workflow_id = "unknown"
    try:
        # Extract all commonly used context variables
        workflow_id, user_id, user_config, session_handler, chat_manager = extract_workflow_context_variables(request)

        # Get session status using SessionAuthority
        # Session status now handled through HistorySession
        session_status = {"status": "unknown", "message": "Session status via unified session management"}

        if not session_status:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        return JSONResponse(content=session_status)

    except HTTPException:
        raise
    except Exception as e:
        endpoints_logger.error(f"Error getting session status for {workflow_id}:{session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get session status: {str(e)}")

@router.get("/workflow/{session_id}/citations/{citation_id}/view")
@bind_workflow_session()
async def view_source_document(
    request: Request,
    session_id: str,
    citation_id: str
) -> JSONResponse:
    """
    Display source document content for a citation.
    """
    try:
        # Extract all commonly used context variables
        workflow_id, user_id, user_config, session_handler, chat_manager = extract_workflow_context_variables(request)

        endpoints_logger.debug(f"Viewing source document {citation_id} for workflow {workflow_id}")

        # Try to retrieve actual source document content
        document_data = get_document_content_by_node_id(citation_id, user_config)
        document_content = ""
        document_title = f"Source Document"
        doc_type = "RAG"
        relevance_score = "0.92"

        citation_metadata = None

        if document_data:
            document_content = document_data.get('content', "")
            document_title = document_data.get('source_file', document_title)
            doc_type = document_data.get('mimetype', 'text/plain').split('/')[1].upper()
            relevance_score = str(document_data.get('score', 0.92))
        else:
            # Fallback with citation metadata
            citation_metadata = _get_citation_metadata_from_sessions(workflow_id, citation_id, user_config, session_handler)
            if citation_metadata:
                document_content = citation_metadata.get('content_preview', '')
                document_title = citation_metadata.get('file_name', document_title)
                doc_type = "Citation"
                relevance_score = "N/A"
            else:
                # Fallback content when nothing found
                document_content = f"""# Citation Document Not Available

**Citation ID:** {citation_id}

**Workflow:** {workflow_id}

This citation could not be retrieved. Please try again or contact support."""

        # Create HTML document viewer
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Source Document - {citation_id}</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.6; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                .document-container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .citation-header {{ border-bottom: 2px solid #007acc; padding-bottom: 15px; margin-bottom: 20px; }}
                .citation-id {{ font-size: 14px; color: #666; font-weight: bold; }}
                .document-title {{ font-size: 24px; margin: 10px 0; color: #333; }}
                .document-meta {{ font-size: 14px; color: #888; margin-bottom: 20px; }}
                .document-content {{ font-size: 16px; color: #333; line-height: 1.8; border: 1px solid #e0e0e0; padding: 20px; background-color: #fafafa; border-radius: 4px; white-space: pre-wrap; }}
                .close-button {{ display: inline-block; padding: 8px 16px; background: #007acc; color: white; text-decoration: none; border-radius: 4px; margin-top: 20px; float: right; }}
                .close-button:hover {{ background: #005a9e; }}
            </style>
        </head>
        <body>
            <div class="document-container">
                <div class="citation-header">
                    <div class="citation-id">Citation: {citation_id[:8]}...</div>
                    <h1 class="document-title">{document_title}</h1>
                    <div class="document-meta">Workflow: {workflow_id.upper()} | Type: {doc_type} | Relevance Score: {relevance_score}</div>
                </div>
                <div class="document-content">{document_content}</div>
                <a href="javascript:window.close()" class="close-button">Close</a>
            </div>
            <script>document.addEventListener('keydown', function(event) {{ if (event.key === 'Escape') {{ window.close(); }} }});</script>
        </body>
        </html>
        """

        return JSONResponse(content={"html": html_content}, status_code=200)

    except HTTPException:
        raise
    except Exception as e:
        endpoints_logger.error(f"Error viewing source document {citation_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to view source document: {str(e)}")

@router.get("/workflow/{session_id}/citations")
@bind_workflow_session()
async def get_sources_overview(
    request: Request,
    session_id: str
) -> JSONResponse:
    """
    Get all available citations for a workflow.
    """
    try:
        # Extract all commonly used context variables
        workflow_id, user_id, user_config, session_handler, chat_manager = extract_workflow_context_variables(request)

        # Return empty list for now - to be integrated with source listing
        sources_info = []
        return JSONResponse(content=sources_info, status_code=200)

    except HTTPException:
        raise
    except Exception as e:
        endpoints_logger.error(f"Error getting citations for workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get workflow citations: {str(e)}")


@router.get("/workflow/{session_id}/chat_session/{chat_session_id}")
@bind_workflow_session()
async def get_workflow_chat_session_details(
    request: Request,
    session_id: str,
    chat_session_id: str
) -> JSONResponse:
    """
    Get chat session details within authorized workflow context.

    Following history API pattern: /api/workflow/{session_id}/chat_session/{chat_session_id}

    Args:
        session_id: Workflow infrastructure session ID (for authorization)
        chat_session_id: Chat session ID to load

    Returns:
        Complete ChatSessionData object with messages and artifacts
    """
    try:
        # Extract workflow context (authorized by @bind_workflow_session decorator)
        workflow_id, user_id, user_config, session_handler, chat_manager = extract_workflow_context_variables(request)

        endpoints_logger.debug(f"Loading chat session {chat_session_id} for workflow {workflow_id} (authorized via workflow session {session_id})")

        # Load the specific chat session within the authorized workflow context
        session = chat_manager.load_session(workflow_id, chat_session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Chat session {chat_session_id} not found for workflow {workflow_id}")

        # Use unified formatting method with consistent artifact loading
        session_data = chat_manager.format_session_with_artifacts(session, include_artifacts=True)

        endpoints_logger.debug(f"Loaded chat session {chat_session_id} with {len(session_data.get('messages', []))} messages and {len(session_data.get('artifacts', []))} artifacts")
        return JSONResponse(content=session_data)

    except HTTPException:
        raise
    except Exception as e:
        endpoints_logger.error(f"Error retrieving chat session {chat_session_id} for workflow session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve chat session: {str(e)}")

# ============================================================================
# HUMAN-IN-THE-LOOP (HITL) ENDPOINTS - REFACTORED TO FOLLOW SESSION MANAGER PATTERN
# ============================================================================

@router.post("/workflow/{session_id}/response")
@bind_workflow_session()
async def handle_workflow_response(request: Request, session_id: str, response_data: Dict[str, Any]):
    """
    Handle human-in-the-loop responses and route through proper workflow system.

    SESSION-CENTRIC PATTERN: Uses existing session_id from path for context.
    All HITL responses go through WorkflowExecutor with proper session validation.
    """
    try:
        # Extract all commonly used context variables
        workflow_id, user_id, user_config, session_handler, chat_manager = extract_workflow_context_variables(request)

        event_type = response_data.get("event_type")
        request_session_id = response_data.get("session_id")

        endpoints_logger.info(f"[HITL] Processing {event_type} for session {request_session_id} workflow {workflow_id}")

        # Handle different types of HITL responses
        if event_type == "CLIHumanResponseEvent":
            return await handle_cli_response_via_workflow(request, response_data)
        elif event_type == "TextInputResponseEvent":
            return await handle_text_input_response(response_data, request)
        elif event_type == "FeedbackResponseEvent":
            return await handle_feedback_response(response_data, request)
        elif event_type == "EditAndResubmitEvent":
            return await handle_edit_resubmit_response(response_data, request)
        elif event_type == "ConfirmationResponseEvent":
            return await handle_confirmation_response(response_data, request)
        else:
            endpoints_logger.warning(f"[HITL] Unknown event type: {event_type}")
            return JSONResponse(content={
                "status": "ignored",
                "message": f"Unknown event type: {event_type}"
            })

    except HTTPException:
        raise
    except Exception as e:
        endpoints_logger.error(f"[HITL] Error handling workflow response: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Workflow response error: {str(e)}")

@router.post("/workflow/{session_id}/recovery")
@bind_workflow_session()
async def recover_hie_session(request: Request, session_id: str, recovery_data: Optional[Dict[str, Any]] = None):
    """
    Recover workflow session after HIE completion to prevent session state corruption.

    SESSION-CENTRIC RECOVERY: Uses existing session_id from path to identify and recover session.
    Validates session ownership and recreates session infrastructure if corrupted.

    Args:
        session_id: The session ID to recover (from URL path)
        recovery_data: Optional recovery metadata (reason, etc.)
    """
    try:
        # Extract recovery reason
        recovery_reason = "unknown"
        if recovery_data and isinstance(recovery_data, dict):
            recovery_reason = recovery_data.get('recovery_reason', 'unknown')

        # Get existing session context (decorator already validated session exists and is accessible)
        workflow_id, user_id, user_config, session_handler, chat_manager = extract_workflow_context_variables(request)

        endpoints_logger.info(f"[HITL] Session recovery requested for session {session_id}, workflow {workflow_id}, reason '{recovery_reason}'")

        # Check if current session is corrupted (missing critical components)
        session_corrupted = False

        # Validate WorkflowSession type
        from super_starter_suite.chat_bot.session_manager import WorkflowSession
        if not isinstance(session_handler, WorkflowSession):
            session_corrupted = True
            endpoints_logger.warning(f"Session {session_id}: invalid session type {type(session_handler)}")

        # Validate chat_manager availability
        if not chat_manager:
            session_corrupted = True
            endpoints_logger.warning(f"Session {session_id}: missing chat_manager")

        # Validate workflow_config_data
        if not hasattr(session_handler, 'workflow_config_data') or session_handler.workflow_config_data is None:
            session_corrupted = True
            endpoints_logger.warning(f"Session {session_id}: missing workflow_config_data")

        if session_corrupted:
            endpoints_logger.info(f"Session {session_id} corrupted, creating fresh session for workflow {workflow_id}")

            # Create fresh WorkflowSession with same workflow_id
            from super_starter_suite.shared.session_utils import SessionBinder
            try:
                bound_session = SessionBinder.bind_session(user_config, "workflow_session", {"workflow_id": workflow_id})

                # Extract new session information
                new_session_id = bound_session.session_id
                new_session_handler = bound_session.session_handler

                # Validate new session
                if not isinstance(new_session_handler, WorkflowSession):
                    raise HTTPException(500, "Failed to create valid WorkflowSession during recovery")

                endpoints_logger.info(f"[HITL] Session recovery created new session {new_session_id} for corrupted session {session_id}")

                return JSONResponse(content={
                    "success": True,
                    "session_id": new_session_id,  # Return NEW session_id
                    "workflow_id": workflow_id,
                    "message": f"HIE session recovered with new session {new_session_id}",
                    "recovery_reason": recovery_reason,
                    "session_replaced": True,
                    "original_session_id": session_id
                })

            except Exception as session_error:
                endpoints_logger.error(f"Failed to create recovery session: {session_error}")
                raise HTTPException(status_code=500, detail="Session recovery failed: unable to create new session")
        else:
            # Session is healthy, return existing session_id
            endpoints_logger.info(f"[HITL] Session {session_id} validated as healthy, no recovery needed")

            return JSONResponse(content={
                "success": True,
                "session_id": session_id,  # Return SAME session_id
                "workflow_id": workflow_id,
                "message": f"HIE session validated as healthy - session {session_id}",
                "recovery_reason": recovery_reason,
                "session_replaced": False
            })

    except HTTPException:
        raise
    except Exception as e:
        endpoints_logger.error(f"[HITL] Session recovery failed for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Session recovery failed: {str(e)}")

# ============================================================================
# WORKFLOW WEBSOCKET ENDPOINTS (from websocket_endpoint.py + executor_endpoint.py)
# ============================================================================

@router.websocket("/workflow/{session_id}/stream")
async def chat_websocket_stream_endpoint(websocket: WebSocket, session_id: str):
    """
    🎯 SRR WEBSOCKET ENDPOINT FOR WORKFLOW EXECUTION

    SRR PATTERN: Uses session_id to extract ALL context (workflow_id, user_id, etc.)
    Does NOT create sessions - validates existing infrastructure only.
    """
    await websocket.accept()

    workflow_id = "unknown"  # Initialize for error handling

    try:
        # SRR: Extract ALL context from session_id (same validation as HTTP endpoints)
        workflow_id, user_id, user_config, session_handler, chat_manager = extract_websocket_session_context(session_id)

        endpoints_logger.info(f"🌐 WebSocket connected: session={session_id}, workflow={workflow_id}")

        # Step 1: Wait for initial chat request
        try:
            initial_message = await websocket.receive_json()
        except WebSocketDisconnect:
            endpoints_logger.info(f"WebSocket client disconnected before sending request")
            return

        if initial_message.get('type') != 'chat_request':
            await websocket.send_json({
                'type': 'error_event',
                'data': {'message': 'Expected chat_request message type'}
            })
            return

        chat_request = initial_message.get('data', {})
        user_question = chat_request.get('question', '').strip()
        requested_session_id = chat_request.get('session_id', session_id)

        # Allow empty questions for HITL workflow continuation or internal workflow requests
        allow_empty_question = False
        if not user_question:
            # Check if this is a HITL workflow continuation request
            if chat_request.get("event_type"):
                allow_empty_question = True
            # Check if this is an internal workflow request
            elif any(key in chat_request for key in ['workflow_id', 'session_id', 'command', 'execute']):
                allow_empty_question = True
            # Check if this is a system/metadata-only request
            elif not chat_request.get('question') and not chat_request.get('message'):
                allow_empty_question = True

        if not user_question and not allow_empty_question:
            await websocket.send_json({
                'type': 'error_event',
                'data': {'message': 'Request must contain a non-empty question field'}
            })
            return

        if not requested_session_id:
            await websocket.send_json({
                'type': 'error_event',
                'data': {'message': 'session_id required for WebSocket execution'}
            })
            return

        endpoints_logger.info(f"🌐 WebSocket chat request: session={session_id}, question={user_question[:100]}...")

        # Step 2: SRR VALIDATION COMPLETE - All context extracted above
        # No session creation - only validation of existing infrastructure

        # Handle session resumption if requested (within same workflow)
        if requested_session_id and requested_session_id != session_id:
            endpoints_logger.info(f"Resuming chat session: {requested_session_id} within workflow session {session_id}")
            # For WebSocket, we keep the infrastructure session but use requested chat session
            # The WorkflowExecutor will handle chat session switching within the infrastructure

        # Create mock request state for WorkflowExecutor (using validated context)
        class MockRequestState:
            def __init__(self):
                self.user_config = user_config
                self.user_id = user_id
                self.session_handler = session_handler
                self.session_id = requested_session_id or session_id

        mock_request_state = MockRequestState()

        # Step 3: Execute workflow with UI event streaming
        async def stream_ui_event(event_type: str, event_data: dict):
            """Stream UI events to WebSocket client"""
            try:
                await websocket.send_json({
                    'type': event_type,
                    'data': event_data,
                    'workflow_id': workflow_id,
                    'timestamp': datetime.now().isoformat()
                })
                endpoints_logger.debug(f"🌐 Streamed UI event via WebSocket: {event_type}")
            except Exception as e:
                endpoints_logger.warning(f"Failed to stream UI event to WebSocket: {e}")

        from super_starter_suite.chat_bot.workflow_execution.workflow_executor import WorkflowExecutor

        result = await WorkflowExecutor.execute_workflow_request(
            workflow_id=workflow_id,
            user_message=user_question,
            request_state=mock_request_state,
            session_id=requested_session_id,
            logger_instance=endpoints_logger,
            ui_event_callback=stream_ui_event
        )

        # Step 4: Send final response using standardized event naming
        await websocket.send_json({
            'type': 'chat_response_event',
            'data': result
        })

        endpoints_logger.info(f"🌐 WebSocket execution completed for workflow {workflow_id}")

    except WebSocketException as e:
        endpoints_logger.error(f"🌐 WebSocket SRR validation failed: {e}")
        try:
            await websocket.send_json({
                'type': 'error',
                'data': {'message': str(e)}
            })
        except Exception as send_error:
            endpoints_logger.error(f"❌ Failed to send WebSocket error: {send_error}")
    except WebSocketDisconnect:
        endpoints_logger.info(f"WebSocket client disconnected: session {session_id}")
    except Exception as e:
        endpoints_logger.error(f"🌐 WebSocket workflow execution failed: {e}")
        try:
            await websocket.send_json({
                'type': 'error',
                'data': {'message': f'Workflow execution failed: {str(e)}'}
            })
        except Exception as send_error:
            endpoints_logger.error(f"❌ Failed to send error message over WebSocket: {send_error}")


# ============================================================================

def get_workflow_connection_count(workflow_id: str) -> int:
    """Get current WebSocket connection count for a workflow"""
    return workflow_websocket_manager.get_connection_count(workflow_id)

def get_active_workflow_connections() -> List[str]:
    """Get list of workflows with active WebSocket connections"""
    return workflow_websocket_manager.get_active_workflows()

async def cleanup_workflow_connections(workflow_id: str):
    """Clean up all WebSocket connections for a completed workflow"""
    if workflow_id in workflow_websocket_manager.active_connections:
        await workflow_websocket_manager.broadcast_to_workflow(workflow_id, {
            "type": "workflow_cleanup",
            "workflow_id": workflow_id,
            "message": "Workflow completed, closing connections",
            "timestamp": datetime.now().isoformat()
        })

        await asyncio.sleep(0.5)

        for connection in workflow_websocket_manager.active_connections[workflow_id][:]:
            try:
                await connection.close(code=1000, reason="Workflow completed")
            except Exception:
                pass

        if workflow_id in workflow_websocket_manager.active_connections:
            del workflow_websocket_manager.active_connections[workflow_id]
        if workflow_id in workflow_websocket_manager.connection_counts:
            del workflow_websocket_manager.connection_counts[workflow_id]
        if workflow_id in workflow_websocket_manager.workflow_sessions:
            del workflow_websocket_manager.workflow_sessions[workflow_id]

def get_workflow_websocket_stats() -> Dict[str, Any]:
    """Get workflow WebSocket connection statistics"""
    total_connections = sum(workflow_websocket_manager.connection_counts.values())
    active_workflows = len(workflow_websocket_manager.connection_counts)

    return {
        "total_connections": total_connections,
        "active_workflows": active_workflows,
        "connections_per_workflow": dict(workflow_websocket_manager.connection_counts),
        "max_connections_per_workflow": workflow_websocket_manager.max_connections_per_workflow,
        "workflow_sessions": dict(workflow_websocket_manager.workflow_sessions)
    }

# ============================================================================
# EXPORT
# ============================================================================

__all__ = [
    "router",
    "get_workflow_connection_count",
    "get_active_workflow_connections",
    "cleanup_workflow_connections",
    "get_workflow_websocket_stats"
]
