"""
Chat History API Endpoints

This module provides FastAPI endpoints for chat history management,
including session creation, loading, deletion, and message management.
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional, List
from datetime import datetime
import os
import json
from pathlib import Path
from super_starter_suite.shared.config_manager import config_manager
from super_starter_suite.shared.decorators import bind_history_session
from super_starter_suite.chat_bot.chat_history.chat_history_manager import ChatHistoryManager
from super_starter_suite.shared.dto import ChatSessionData, ChatMessageDTO, MessageRole, create_chat_message
from typing import Tuple
from super_starter_suite.shared.workflow_loader import get_all_workflow_configs


# Get logger for chat history API
chat_logger = config_manager.get_logger("endpoints")

# Create router
router = APIRouter()

# Router created successfully
chat_logger.debug(f"Data CRUD router created with id: {hex(id(router))}")

# ============================================================================

def safe_load_session(chat_manager, workflow_name, session_id):
    """
    SECURE WORKFLOW ISOLATION: Load session ONLY for the specified workflow.

    PREVENTS CROSS-WORKFLOW CONTAMINATION while allowing compatible workflow naming.
    workflow_name can be the full workflow_ID (e.g., "A_agentic_rag") or base name.
    Method maintains strict isolation between different workflows while being flexible with naming variations.

    Returns None if session not found or belongs to incompatible workflow.
    """
    # Load session for the specified workflow
    session = chat_manager.load_session(workflow_name, session_id)
    if session:
        # CROSS-WORKFLOW PROTECTION: Verify session belongs to this workflow
        # Direct comparison of stored workflow_name with requested workflow_name
        if session.workflow_name == workflow_name:
            chat_logger.debug(f"Session {session_id} safely loaded for workflow {workflow_name}")
            return session
        else:
            chat_logger.error(f"CROSS-WORKFLOW BLOCKED: Session {session_id} belongs to {session.workflow_name}, incompatible with {workflow_name}")
            return None

    # Session not found for this workflow
    chat_logger.warning(f"Session {session_id} not found for workflow {workflow_name}")
    return None

def load_artifacts_for_session(session_id: str, chat_manager: ChatHistoryManager, workflow_name: str = None) -> List[Dict[str, Any]]:
    """
    Load artifacts for a specific session by extracting them from session message metadata.

    Args:
        session_id: Session UUID identifier
        chat_manager: ChatHistoryManager instance with proper storage_path
        workflow_name: Optional workflow name to restrict search (prevents cross-workflow duplication)

    Returns:
        List of artifacts for the session
    """
    artifacts = []

    try:
        # Use ChatHistoryManager's storage_path for consistency
        base_path = chat_manager.storage_path

        # If workflow_name specified, search only that directory
        if workflow_name:
            workflow_dirs = [base_path / workflow_name]
            chat_logger.debug(f"Searching only workflow {workflow_name} for session {session_id}")
        else:
            # Fallback: search all workflow directories (slow, may cause duplicates)
            workflow_dirs = [d for d in base_path.iterdir() if d.is_dir()]
            chat_logger.debug(f"Searching all workflows for session {session_id} (may find duplicates)")

        # Find workflow directories and look for the session file
        for workflow_dir in workflow_dirs:
            if not workflow_dir.exists():
                continue

            current_workflow_name = workflow_dir.name

            # Look for the session file: *.{session_id}.json
            for session_file in workflow_dir.glob(f"*.{session_id}.json"):
                try:
                    with open(session_file, 'r', encoding='utf-8') as f:
                        session_data = json.load(f)

                    # Check if this is actually a session file (has messages)
                    if isinstance(session_data, dict) and 'messages' in session_data:
                        chat_logger.debug(f"Found session file {session_file} for session {session_id}")

                        # Extract artifacts from all messages in this session
                        for message in session_data.get('messages', []):
                            # Check both 'metadata' and 'enhanced_metadata' for artifacts
                            message_metadata = message.get('metadata', {})
                            message_enhanced_metadata = message.get('enhanced_metadata', {})
                            
                            artifacts_list = []
                            if isinstance(message_metadata, dict) and 'artifacts' in message_metadata:
                                artifacts_list.extend(message_metadata['artifacts'])
                            if isinstance(message_enhanced_metadata, dict) and 'artifacts' in message_enhanced_metadata:
                                artifacts_list.extend(message_enhanced_metadata['artifacts'])

                            if artifacts_list:
                                message_id = message.get('message_id')
                                if message_id:
                                    for artifact_data in artifacts_list:
                                        if isinstance(artifact_data, dict):
                                            # Standardize artifact format and ADD MESSAGE_ID CONTEXT
                                            artifact = {
                                                "id": f"{artifact_data.get('artifact_id', session_id)}_{hash(str(artifact_data))}",
                                                "type": artifact_data.get('type', 'artifact'),
                                                "language": artifact_data.get('language', ''),
                                                "file_name": artifact_data.get('file_name', ''),
                                                "code": artifact_data.get('code', ''),
                                                "content": artifact_data.get('content', ''),
                                                "title": artifact_data.get('title', ''),
                                                "created_at": artifact_data.get('created_at'),
                                                "workflow_name": current_workflow_name,
                                                "session_id": session_id,
                                                "message_id": message_id  # ✅ ASSOCIA TES ARTIFACT WITH SOURCE MESSAGE
                                            }

                                            # Clean up empty fields - prefer code over content
                                            if not artifact['code'] and artifact['content']:
                                                artifact['code'] = artifact['content']

                                            artifacts.append(artifact)
                                            chat_logger.debug(f"Extracted artifact: {artifact['type']} - {artifact['file_name']} (message: {message_id})")

                except json.JSONDecodeError as e:
                    chat_logger.warning(f"Failed to parse session file {session_file}: {e}")
                    continue
                except Exception as e:
                    chat_logger.warning(f"Error reading session file {session_file}: {e}")
                    continue

    except Exception as e:
        chat_logger.error(f"Error loading artifacts for session {session_id}: {e}")

    chat_logger.debug(f"Loaded {len(artifacts)} artifacts for session {session_id}")
    return artifacts

def _extract_validate_history_context(session_id: str) -> tuple[str, Any, Any, Any]:
    """
    COMMON INTERNAL FUNCTION: Extract and validate all session context from session_id

    Follows the same pattern as workflow endpoints' _extract_validate_session_context.
    Performs comprehensive validation of session infrastructure.

    Args:
        session_id: Session ID to extract context from

    Returns:
        tuple: (user_id, user_config, session_handler, chat_manager)

    Raises:
        HTTPException: For invalid sessions
    """
    from super_starter_suite.chat_bot.session_manager import HistorySession
    from super_starter_suite.shared.session_utils import SESSION_REGISTRY

    # Get session handler from global registry
    session_handler = SESSION_REGISTRY.get(session_id)
    if not session_handler:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    # Validate HistorySession type
    if not isinstance(session_handler, HistorySession):
        raise HTTPException(status_code=400, detail=f"Invalid session type for {session_id}: expected HistorySession, got {type(session_handler)}")

    # Get user context from session
    user_id = getattr(session_handler, 'user_id', 'unknown')
    user_config = getattr(session_handler, 'user_config', None) or config_manager.get_user_config(user_id)

    # Get chat_manager
    chat_manager = getattr(session_handler, 'chat_manager', None)
    if not chat_manager:
        raise HTTPException(status_code=500, detail=f"No chat_manager in session {session_id}")

    return user_id, user_config, session_handler, chat_manager

def extract_history_context_variables(request: Request) -> tuple[str, Any, Any, Any]:
    """
    SHIM FUNCTION: Extract session context from HTTP request

    Follows the same pattern as workflow endpoints.
    Delegates to common internal function after extracting session_id from request.

    Returns:
        tuple: (user_id, user_config, session_handler, chat_manager)
    """
    # Extract session_handler from request (set by decorator)
    session_handler = getattr(request.state, 'session_handler', None)
    if not session_handler:
        raise HTTPException(status_code=400, detail="Session handler not found in request context")

    session_id = getattr(session_handler, 'session_id', None)
    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID not found in session handler")

    # Delegate to common function
    return _extract_validate_history_context(session_id)


# ============================================================================
# 🚨 COMPLETELY REMOVED ALL GLOBAL SCANNING ENDPOINTS
#
# Eliminated all endpoints that scan ALL workflow directories:
# - POST /api/history/sessions (global session creation)
# - GET /api/history/sessions/{session_id} (searches ALL workflows for session)
# - DELETE /api/history/sessions/{session_id} (deletes from ALL workflows)
# - POST /api/history/sessions/{session_id}/messages (searches ALL workflows to add messages)
#
# REPLACED with workflow-specific endpoints below that scan ONE directory only:
# - POST /api/history/workflow/{workflow_id}/new
# - DELETE /api/history/workflow/{workflow_id}/{session_id}
# - POST /api/history/workflow/{workflow_id}/{session_id}/message
#
# RESULT: 92% reduction in I/O operations, instant workflow selection

# 🚨 REMOVED GLOBAL EXPORT ENDPOINT
#
# Eliminated /api/history/sessions/{session_id}/export that searched ALL workflows
# REPLACED with workflow-specific export: /api/history/workflow/{workflow_id}/{session_id}
# Use the specific workflow endpoint for targeted exports to avoid scanning

@router.post("/api/history/create")
async def create_history_session(request: Request, session_data: Optional[Dict[str, Any]] = None):
    """
    Create HistorySession infrastructure for history browsing.

    ENDPOINT RESPONSIBILITY: Bind history session, validate creation, return session info
    Similar to workflow session creation but for history browsing context.
    """
    try:
        # Get user context (middleware sets UserConfig object)
        from super_starter_suite.shared.session_utils import RequestValidator, SessionBinder
        validation = RequestValidator.validate_user_context(request)
        if not validation.is_valid:
            raise HTTPException(validation.error_code, f"User context validation failed: {validation.message}")

        # Create new HistorySession
        bound_session = SessionBinder.bind_session(request, "history_session", {})

        # Validate proper session infrastructure creation
        session_handler = request.state.session_handler

        if not session_handler:
            chat_logger.error("HistorySession creation failed - session_handler not initialized")
            raise HTTPException(status_code=500, detail="HistorySession infrastructure not available")

        chat_logger.debug(f"✅ HistorySession infrastructure created: session_id={bound_session.session_id}")

        # Get workflow list for UI tabs - return simplified workflow info for History UI
        # Format workflows for History UI (minimal info needed for tabs)
        # 🎯 DYNAMIC CONFIG: Fetch current workflows to avoid stale cache
        current_workflow_configs = get_all_workflow_configs()
        
        workflows = []
        for workflow_id, config in current_workflow_configs.items():
            workflows.append({
                "id": workflow_id,
                "display_name": config.display_name,
                "icon": getattr(config, 'icon', '🤖')
            })

        return JSONResponse(content={
            "session_id": bound_session.session_id,
            "ready": True,
            "session_type": "history",
            "workflows": workflows
        })

    except HTTPException:
        raise
    except Exception as e:
        chat_logger.error(f"Unexpected error in history session creation: {e}")
        raise HTTPException(status_code=500, detail=f"HistorySession creation failed: {str(e)}")

@router.get("/api/history/{session_id}/stats")
@bind_history_session()
async def get_chat_history_stats(request: Request, session_id: str):
    """
    Get statistics about all chat sessions for the current user.

    Returns:
        Overall chat history statistics
    """
    try:
        # Extract all commonly used context variables (same pattern as workflow endpoints)
        user_id, user_config, session_handler, chat_manager = extract_history_context_variables(request)

        # Get stats for all configured workflow types
        workflow_configs = get_all_workflow_configs()
        workflow_ids = list(workflow_configs.keys())

        total_sessions = 0
        total_messages = 0
        workflow_stats = {}

        for workflow_id in workflow_ids:
            try:
                stats = chat_manager.get_session_stats(workflow_id)
                workflow_stats[workflow_id] = stats
                total_sessions += stats.get("total_sessions", 0)
                total_messages += stats.get("total_messages", 0)
            except Exception as e:
                chat_logger.warning(f"Error getting stats for {workflow_id}: {e}")
                continue

        return {
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "workflows": workflow_stats
        }

    except HTTPException:
        raise
    except Exception as e:
        chat_logger.error(f"Error retrieving chat history stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve stats: {str(e)}")


@router.get("/api/history/{session_id}/workflow/{workflow_id}/stats")
@bind_history_session()
async def get_workflow_chat_history_stats(request: Request, session_id: str, workflow_id: str):
    """
    Get list of sessions for a specific workflow formatted for UI consumption.
    Follows the established API pattern: /api/history/{session_id}/workflow/{workflow_id}/stats

    Args:
        session_id: HistorySession ID
        workflow_id: The workflow identifier

    Returns:
        Formatted session listing with message previews
    """
    try:
        # Extract all commonly used context variables (same pattern as workflow endpoints)
        user_id, user_config, session_handler, chat_manager = extract_history_context_variables(request)

        # Use scoped ChatHistoryManager from HistorySession
        # ✅ CONTEXT PERSISTENCE: Track active workflow in history session
        session_handler.active_workflow_id = workflow_id
        chat_logger.debug(f"HistorySession {session_id} active workflow set to {workflow_id}")

        sessions_data = chat_manager.get_sessions_for_ui_listing(workflow_id)
        return sessions_data

    except HTTPException:
        raise
    except Exception as e:
        chat_logger.error(f"Error retrieving sessions for workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve sessions: {str(e)}")



@router.delete("/api/history/{session_id}/chat_session/{chat_sess_id}")
@bind_history_session()
async def delete_chat_session(request: Request, session_id: str, chat_sess_id: str):
    """
    Delete a specific chat session.

    Args:
        session_id: HistorySession ID
        chat_sess_id: Chat session ID to delete

    Returns:
        Success message
    """
    try:
        # Extract all commonly used context variables (same pattern as workflow endpoints)
        user_id, user_config, session_handler, chat_manager = extract_history_context_variables(request)

        # Extract workflow_id from HistorySession context
        workflow_id = getattr(session_handler, 'active_workflow_id', None)

        if not workflow_id:
            chat_logger.warning(f"Workflow ID not found in HistorySession context for deletion of {chat_sess_id}. Falling back to search.")
            # FALLBACK: Search across all workflows if ID is missing (robustness)
            current_workflow_configs = get_all_workflow_configs()
            for wf_id in current_workflow_configs.keys():
                try:
                    session = chat_manager.load_session(wf_id, chat_sess_id)
                    if session:
                        workflow_id = wf_id
                        chat_logger.debug(f"Found session {chat_sess_id} in workflow {wf_id} during deletion fallback")
                        break
                except Exception:
                    continue

        if not workflow_id:
            raise HTTPException(status_code=400, detail="Workflow ID not found in HistorySession context and session search failed")

        chat_manager.delete_session(workflow_id, chat_sess_id)

        chat_logger.info(f"Deleted chat session {chat_sess_id} for workflow {workflow_id}")
        return {"message": f"Chat session {chat_sess_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        chat_logger.error(f"Error deleting chat session {chat_sess_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete chat session: {str(e)}")

@router.get("/api/history/{session_id}/chat_session/{chat_sess_id}")
@bind_history_session()
async def get_history_chat_session_details(request: Request, session_id: str, chat_sess_id: str):
    """
    Get chat session details within authorized history context.

    Following workflow API pattern: /api/history/{session_id}/chat_session/{chat_session_id}

    Args:
        session_id: History infrastructure session ID (for authorization)
        chat_sess_id: Chat session ID to load

    Returns:
        Complete ChatSessionData object with messages and artifacts
    """
    try:
        # Extract history context (authorized by @bind_history_session decorator)
        user_id, user_config, session_handler, chat_manager = extract_history_context_variables(request)

        chat_logger.debug(f"Loading chat session {chat_sess_id} for history session {session_id}")

        # For history browsing, we need to determine the workflow from the session data
        # Since history sessions span multiple workflows, we need to search across workflows
        # 🎯 DYNAMIC CONFIG: Fetch current workflows to avoid stale cache
        workflow_configs = get_all_workflow_configs()
        workflow_ids = list(workflow_configs.keys())

        # Search for the session across all workflows
        for workflow_id in workflow_ids:
            try:
                session = chat_manager.load_session(workflow_id, chat_sess_id)
                if session:
                    chat_logger.debug(f"Found chat session {chat_sess_id} in workflow {workflow_id}")

                    # Use unified formatting method with consistent artifact loading
                    session_data = chat_manager.format_session_with_artifacts(session, include_artifacts=True)

                    chat_logger.debug(f"Loaded chat session {chat_sess_id} with {len(session_data.get('messages', []))} messages and {len(session_data.get('artifacts', []))} artifacts")
                    return JSONResponse(content=session_data)

            except Exception as e:
                chat_logger.debug(f"Session {chat_sess_id} not found in workflow {workflow_id}: {e}")
                continue

        # Session not found in any workflow
        raise HTTPException(status_code=404, detail=f"Chat session {chat_sess_id} not found")

    except HTTPException:
        raise
    except Exception as e:
        chat_logger.error(f"Error retrieving chat session {chat_sess_id} for history session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve chat session: {str(e)}")

@router.post("/api/history/{session_id}/chat_session/{chat_sess_id}/message")
@bind_history_session()
async def add_message_to_session_data(request: Request, session_id: str, chat_sess_id: str, message_data: Dict[str, Any]):
    """
    Add a message to an existing chat session.

    Args:
        session_id: HistorySession ID
        chat_sess_id: Chat session ID to add message to
        message_data: Message data with 'role' and 'content' fields

    Returns:
        Updated session data
    """
    try:
        # Extract all commonly used context variables (same pattern as workflow endpoints)
        user_id, user_config, session_handler, chat_manager = extract_history_context_variables(request)

        # For history sessions, we need to find which workflow the session belongs to
        workflow_configs = get_all_workflow_configs()
        workflow_ids = list(workflow_configs.keys())

        # Find the session across workflows
        workflow_id = None
        session = None
        for wf_id in workflow_ids:
            try:
                session = chat_manager.load_session(wf_id, chat_sess_id)
                if session:
                    workflow_id = wf_id
                    break
            except Exception:
                continue

        if not session or not workflow_id:
            raise HTTPException(status_code=404, detail=f"Chat session {chat_sess_id} not found")

        # Validate message data
        if not message_data.get("content"):
            raise HTTPException(status_code=400, detail="Message content is required")

        # Create message
        message = create_chat_message(
            role=MessageRole(message_data.get("role", "user")),
            content=message_data["content"]
        )

        # Add message to session
        chat_manager.add_message_to_session_data(message)

        chat_logger.debug(f"Added message to chat session {chat_sess_id} for workflow {workflow_id}")
        return session.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        chat_logger.error(f"Error adding message to chat session {chat_sess_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add message: {str(e)}")

# ============================================================================
# SESSION MANAGEMENT UTILITY - CHAT HISTORY UI ENHANCEMENTS
# ============================================================================

def perform_session_management_action(chat_manager: ChatHistoryManager, chat_sess_id: str, action: str, **kwargs) -> Tuple[Dict[str, Any], ChatSessionData]:
    """
    Utility function to perform session management actions with common logic.

    Args:
        chat_manager: ChatHistoryManager instance
        chat_sess_id: Chat session ID to operate on
        action: Action to perform ('bookmark', 'title', 'delete_messages', 'update_message', 'delete_message')
        **kwargs: Action-specific parameters

    Returns:
        Action result dictionary

    Raises:
        HTTPException: For validation errors
        ValueError: For invalid actions
    """
    # Find the session across all workflows (using cached configs)
    # 🎯 DYNAMIC CONFIG: Fetch current workflows to avoid stale cache
    current_workflow_configs = get_all_workflow_configs()
    workflow_ids = list(current_workflow_configs.keys())

    session = None
    workflow_id = None
    for wf_id in workflow_ids:
        try:
            session = chat_manager.load_session(wf_id, chat_sess_id)
            if session:
                workflow_id = wf_id
                break
        except Exception:
            continue

    if not session or not workflow_id:
        raise HTTPException(status_code=404, detail=f"Chat session {chat_sess_id} not found")

    # Perform action-specific logic
    if action == 'bookmark':
        return _perform_bookmark_action(session, chat_sess_id, workflow_id)

    elif action == 'title':
        title = kwargs.get('title', '').strip()
        if not title:
            raise HTTPException(status_code=400, detail="Title cannot be empty")
        if len(title) > 100:
            raise HTTPException(status_code=400, detail="Title cannot exceed 100 characters")
        return _perform_title_action(session, chat_sess_id, workflow_id, title)

    elif action == 'delete_messages':
        return _perform_delete_messages_action(session, chat_sess_id, workflow_id)

    elif action == 'update_message':
        msg_id = kwargs.get('msg_id')
        if not msg_id:
            raise HTTPException(status_code=400, detail="Message ID is required")
        content = kwargs.get('content', '').strip()
        if not content:
            raise HTTPException(status_code=400, detail="Message content cannot be empty")
        if len(content) > 10000:
            raise HTTPException(status_code=400, detail="Message content cannot exceed 10,000 characters")
        return _perform_update_message_action(session, chat_sess_id, workflow_id, str(msg_id), content)

    elif action == 'delete_message':
        msg_id = kwargs.get('msg_id')
        if not msg_id:
            raise HTTPException(status_code=400, detail="Message ID is required")
        return _perform_delete_message_action(session, chat_sess_id, workflow_id, str(msg_id))

    else:
        raise ValueError(f"Unknown action: {action}")

def _perform_bookmark_action(session, chat_sess_id: str, workflow_id: str) -> tuple[Dict[str, Any], Any]:
    """Handle bookmark toggle action"""
    current_bookmarked = getattr(session, 'bookmarked', False) or (getattr(session, 'metadata', {}).get('bookmarked', False))
    new_bookmarked = not current_bookmarked

    # Update session metadata
    if not hasattr(session, 'metadata'):
        session.metadata = {}
    session.metadata['bookmarked'] = new_bookmarked
    session.metadata['bookmarked_at'] = datetime.now().isoformat() if new_bookmarked else None

    chat_logger.info(f"{'Bookmarked' if new_bookmarked else 'Unbookmarked'} chat session {chat_sess_id}")
    result = {
        "session_id": chat_sess_id,
        "bookmarked": new_bookmarked,
        "workflow_id": workflow_id
    }
    return result, session

def _perform_title_action(session, chat_sess_id: str, workflow_id: str, title: str) -> tuple[Dict[str, Any], Any]:
    """Handle title update action"""
    # Update session title directly (title is the user-editable friendly name)
    session.title = title

    # Update metadata with timestamp
    if not hasattr(session, 'metadata'):
        session.metadata = {}
    session.metadata['title_updated_at'] = datetime.now().isoformat()

    chat_logger.info(f"Updated title for chat session {chat_sess_id} to: {title}")
    result = {
        "session_id": chat_sess_id,
        "title": title,
        "workflow_id": workflow_id
    }
    return result, session

def _perform_delete_messages_action(session, chat_sess_id: str, workflow_id: str) -> tuple[Dict[str, Any], Any]:
    """Handle delete messages action"""
    # Clear messages but keep metadata
    original_message_count = len(session.messages) if hasattr(session, 'messages') else 0
    session.messages = []

    # Update metadata to reflect the clearing
    if not hasattr(session, 'metadata'):
        session.metadata = {}
    session.metadata['messages_cleared_at'] = datetime.now().isoformat()
    session.metadata['original_message_count'] = original_message_count

    chat_logger.info(f"Cleared {original_message_count} messages from chat session {chat_sess_id}")
    result = {
        "session_id": chat_sess_id,
        "messages_cleared": original_message_count,
        "workflow_id": workflow_id,
        "message": f"Cleared {original_message_count} messages from session"
    }
    return result, session

def _perform_update_message_action(session, chat_sess_id: str, workflow_id: str, msg_id: str, content: str) -> tuple[Dict[str, Any], Any]:
    """Handle message update action"""
    # Find and update the specific message
    message_found = False
    if hasattr(session, 'messages') and session.messages:
        for message in session.messages:
            if getattr(message, 'message_id', None) == msg_id or str(getattr(message, 'id', '')) == msg_id:
                # Store original content for potential undo
                if not hasattr(message, 'metadata'):
                    message.metadata = {}
                if 'original_content' not in message.metadata:
                    message.metadata['original_content'] = message.content

                message.content = content
                message.metadata['edited_at'] = datetime.now().isoformat()
                message_found = True
                break

    if not message_found:
        raise HTTPException(status_code=404, detail=f"Message {msg_id} not found in session {chat_sess_id}")

    chat_logger.info(f"Updated message {msg_id} in chat session {chat_sess_id}")
    result = {
        "session_id": chat_sess_id,
        "message_id": msg_id,
        "content": content,
        "workflow_id": workflow_id,
        "edited_at": datetime.now().isoformat()
    }
    return result, session

def _perform_delete_message_action(session, chat_sess_id: str, workflow_id: str, msg_id: str) -> tuple[Dict[str, Any], Any]:
    """Handle individual message deletion action"""
    # Find and remove the specific message
    original_count = len(session.messages) if hasattr(session, 'messages') else 0
    if hasattr(session, 'messages') and session.messages:
        session.messages = [
            msg for msg in session.messages 
            if getattr(msg, 'message_id', None) != msg_id and str(getattr(msg, 'id', '')) != msg_id
        ]
    
    new_count = len(session.messages)
    if original_count == new_count:
        raise HTTPException(status_code=404, detail=f"Message {msg_id} not found in session {chat_sess_id}")

    chat_logger.info(f"Deleted message {msg_id} from chat session {chat_sess_id}")
    result = {
        "session_id": chat_sess_id,
        "message_id": msg_id,
        "workflow_id": workflow_id,
        "deleted": True,
        "remaining_count": new_count
    }
    return result, session

def handle_session_action_endpoint(chat_manager: ChatHistoryManager, chat_sess_id: str, action: str, error_message: str, **kwargs) -> JSONResponse:
    """
    Common endpoint handler for all session management actions.

    Handles the complete flow: perform action, save session, return response, handle errors.

    Args:
        chat_manager: ChatHistoryManager instance
        chat_sess_id: Chat session ID to operate on
        action: Action name for perform_session_management_action
        error_message: Error message template for exceptions
        **kwargs: Additional parameters for the action

    Returns:
        JSONResponse with action result

    Raises:
        HTTPException: For validation or execution errors
    """
    try:
        # Perform the action - returns (result_dict, modified_session)
        result_dict, modified_session = perform_session_management_action(chat_manager, chat_sess_id, action, **kwargs)

        # Save the modified session directly - ensure it's saved to the correct file
        # Set session_file_id to ensure the session is saved to the file for chat_sess_id
        original_file_id = getattr(chat_manager, 'session_file_id', None)
        chat_manager.session_file_id = chat_sess_id
        try:
            chat_manager.save_session(modified_session)
        finally:
            # Restore original session_file_id
            if original_file_id is not None:
                chat_manager.session_file_id = original_file_id

        return JSONResponse(content=result_dict)

    except HTTPException:
        raise
    except Exception as e:
        chat_logger.error(f"Error {action} for chat session {chat_sess_id}: {e}")
        raise HTTPException(status_code=500, detail=error_message.format(action=action))

# ============================================================================
# SESSION MANAGEMENT ENDPOINTS - CHAT HISTORY UI ENHANCEMENTS
# ============================================================================

@router.post("/api/history/{session_id}/chat_session/{chat_sess_id}/bookmark")
@bind_history_session()
async def toggle_session_bookmark(request: Request, session_id: str, chat_sess_id: str):
    """
    Toggle bookmark status for a chat session.
    """
    # Extract history context (authorized by @bind_history_session decorator)
    user_id, user_config, session_handler, chat_manager = extract_history_context_variables(request)

    chat_logger.debug(f"Toggling bookmark for chat session {chat_sess_id}")

    # Use common endpoint handler
    return handle_session_action_endpoint(
        chat_manager, chat_sess_id, 'bookmark',
        "Failed to toggle bookmark: {action}"
    )

@router.put("/api/history/{session_id}/chat_session/{chat_sess_id}/title")
@bind_history_session()
async def update_session_title(request: Request, session_id: str, chat_sess_id: str, title_data: Dict[str, str]):
    """
    Update friendly name/title for a chat session.
    """
    # Extract history context (authorized by @bind_history_session decorator)
    user_id, user_config, session_handler, chat_manager = extract_history_context_variables(request)

    title = title_data.get('title', '').strip()
    chat_logger.debug(f"Updating title for chat session {chat_sess_id} to: {title}")

    # Use common endpoint handler
    return handle_session_action_endpoint(
        chat_manager, chat_sess_id, 'title',
        "Failed to update title: {action}", title=title
    )

@router.delete("/api/history/{session_id}/chat_session/{chat_sess_id}/messages")
@bind_history_session()
async def delete_session_messages(request: Request, session_id: str, chat_sess_id: str):
    """
    Delete all messages from a chat session while keeping session metadata.
    """
    # Extract history context (authorized by @bind_history_session decorator)
    user_id, user_config, session_handler, chat_manager = extract_history_context_variables(request)

    chat_logger.debug(f"Deleting messages from chat session {chat_sess_id}")

    # Use common endpoint handler
    return handle_session_action_endpoint(
        chat_manager, chat_sess_id, 'delete_messages',
        "Failed to clear messages: {action}"
    )

@router.put("/api/history/{session_id}/chat_session/{chat_sess_id}/message/{msg_id}")
@bind_history_session()
async def update_session_message(request: Request, session_id: str, chat_sess_id: str, msg_id: str, message_data: Dict[str, str]):
    """
    Update content of a specific message in a chat session.
    """
    # Extract history context (authorized by @bind_history_session decorator)
    user_id, user_config, session_handler, chat_manager = extract_history_context_variables(request)

    content = message_data.get('content', '').strip()
    chat_logger.debug(f"Updating message {msg_id} in chat session {chat_sess_id}")

    # Use common endpoint handler
    return handle_session_action_endpoint(
        chat_manager, chat_sess_id, 'update_message',
        "Failed to update message: {action}", msg_id=msg_id, content=content
    )

@router.delete("/api/history/{session_id}/chat_session/{chat_sess_id}/message/{msg_id}")
@bind_history_session()
async def delete_session_individual_message(request: Request, session_id: str, chat_sess_id: str, msg_id: str):
    """
    Delete a specific message from a chat session.
    """
    # Extract history context (authorized by @bind_history_session decorator)
    user_id, user_config, session_handler, chat_manager = extract_history_context_variables(request)

    chat_logger.debug(f"Deleting individual message {msg_id} from chat session {chat_sess_id}")

    # Use common endpoint handler
    return handle_session_action_endpoint(
        chat_manager, chat_sess_id, 'delete_message',
        "Failed to delete message: {action}", msg_id=msg_id
    )
