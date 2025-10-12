"""
Chat History API Endpoints

This module provides FastAPI endpoints for chat history management,
including session creation, loading, deletion, and message management.
"""

from fastapi import APIRouter, Request, HTTPException
from typing import Dict, Any, Optional, List
from datetime import datetime
import os
import json
from pathlib import Path
from super_starter_suite.shared.config_manager import config_manager
from super_starter_suite.shared.decorators import bind_user_context
from super_starter_suite.chat_bot.chat_history.chat_history_manager import ChatHistoryManager
from super_starter_suite.shared.dto import ChatSession, ChatMessageDTO, MessageRole, create_chat_message
from super_starter_suite.shared.workflow_loader import get_all_workflow_configs


# Get logger for chat history API
chat_logger = config_manager.get_logger("history.api")

# Create router
router = APIRouter()

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

def _is_workflow_compatible(session_workflow, requested_workflow):
    """
    Check if two workflow specifications are compatible.

    Defines compatible workflows to prevent cross-contamination while allowing
    reasonable naming flexibility.
    """
    # Direct match
    if session_workflow == requested_workflow:
        return True

    # Allow base workflow matching (ignore prefixes)
    # "agentic-rag" is compatible with "A_agentic_rag", "P_agentic_rag", etc.
    def get_workflow_base(name):
        # Use workflow name as defined in config - no prefix stripping needed
        return name  # Keep the full name as-is since workflow names are defined consistently

    return session_workflow == requested_workflow  # For now, require exact match

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
                            if ('metadata' in message and
                                isinstance(message['metadata'], dict) and
                                'artifacts' in message['metadata']):

                                message_artifacts = message['metadata']['artifacts']
                                message_id = message.get('message_id')
                                if isinstance(message_artifacts, list) and message_id:
                                    for artifact_data in message_artifacts:
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

@router.get("/chat_history/sessions")
@bind_user_context
async def get_all_sessions(request: Request):
    """
    Get all chat sessions across all workflow types for the current user.

    Returns:
        List of all chat sessions with basic info
    """
    user_config = request.state.user_config
    chat_manager = ChatHistoryManager(user_config)

    try:
        # Get sessions for all workflow types dynamically
        all_sessions = []

        # Get all configured workflow types

        workflow_configs = get_all_workflow_configs()

        # Use raw workflow IDs from config - ChatHistoryManager handles normalization internally
        workflow_ids = list(workflow_configs.keys())

        for workflow_id in workflow_ids:
            try:
                sessions = chat_manager.get_all_sessions(workflow_id)
                for session in sessions:
                    session_data = {
                        "session_id": session.session_id,
                        "workflow_name": session.workflow_name,  # Use session workflow_name field
                        "title": session.title or f"Chat {session.session_id[:8]}",
                        "created_at": session.created_at.isoformat(),
                        "updated_at": session.updated_at.isoformat(),
                        "message_count": len(session.messages)
                    }
                    all_sessions.append(session_data)

            except Exception as e:
                chat_logger.warning(f"Error loading sessions for {workflow_id}: {e}")
                continue

        # Sort by updated_at descending (most recent first)
        all_sessions.sort(key=lambda x: x["updated_at"], reverse=True)

        return {"sessions": all_sessions}

    except Exception as e:
        chat_logger.error(f"Error retrieving all chat sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve chat sessions: {str(e)}")

@router.post("/chat_history/sessions")
@bind_user_context
async def create_chat_session(request: Request, session_data: Dict[str, Any]):
    """
    Create a new chat session through SessionAuthority (SINGLE SOURCE OF TRUTH).

    Guarantees proper session isolation - only one active session per workflow.

    Args:
        session_data: Session data including workflow_name and optional title

    Returns:
        New ChatSession object
    """
    user_config = request.state.user_config

    try:
        from super_starter_suite.chat_bot.session_authority import session_authority as _session_authority

        workflow_name = session_data.get("workflow_name", "agentic_rag")
        title = session_data.get("title", "")

        # ENSURE SESSION ISOLATION through SessionAuthority (SINGLE SOURCE)
        # This enforces exactly one active session per workflow
        session_data_result = _session_authority.get_or_create_session(
            workflow_name=workflow_name,
            user_config=user_config,
            existing_session_id=None  # Create new session
        )

        session = session_data_result['session']

        if title:
            session.title = title

        # Save any title updates
        chat_manager = ChatHistoryManager(user_config)
        chat_manager.save_session(session)

        chat_logger.info(f"Created new chat session {session.session_id} for workflow {workflow_name} via SessionAuthority")
        return session.to_dict()

    except Exception as e:
        chat_logger.error(f"Error creating chat session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create chat session: {str(e)}")

@router.get("/chat_history/sessions/{session_id}")
@bind_user_context
async def get_session_by_id(request: Request, session_id: str):
    """
    Get a specific chat session by ID across ALL workflow directories.

    FRONTEND RESUMPTION ISSUE: showChatInterface() calls this endpoint,
    and if it fails (404), the frontend generates a new session ID instead.
    This function must find sessions NO MATTER which workflow they belong to.

    Args:
        session_id: Unique session identifier

    Returns:
        Complete ChatSession object
    """
    user_config = request.state.user_config
    chat_manager = ChatHistoryManager(user_config)

    try:
        # SEARCH ACROSS ALL WORKFLOW DIRECTORIES - frontend resumption depends on this!
        # The session might be from any workflow type
        base_path = chat_manager.storage_path

        # Search ALL workflow subdirectories for this session
        for workflow_dir in base_path.iterdir():
            if not workflow_dir.is_dir():
                continue

            workflow_name = workflow_dir.name
            chat_logger.debug(f"Searching for session {session_id} in workflow directory: {workflow_name}")

            # Try loading session from this workflow directory (ChatHistoryManager knows how to find files)
            try:
                chat_logger.debug(f"Attempting to load session {session_id} from workflow {workflow_name}")
                session = chat_manager.load_session(workflow_name, session_id)
                if session:
                    # Verify session belongs to current user (security)
                    if session.user_id != user_config.user_id:
                        chat_logger.warning(f"Session {session_id} belongs to different user")
                        continue

                    chat_logger.info(f"✅ Session {session_id} found in workflow {workflow_name}")
                    return session.to_dict()
                else:
                    chat_logger.debug(f"load_session returned None for {workflow_name}/{session_id}")
            except Exception as e:
                chat_logger.debug(f"load_session exception in {workflow_name}: {e}")
                continue

        # Session not found in any workflow directory
        chat_logger.error(f"❌ Session {session_id} not found in any workflow directory")
        raise HTTPException(status_code=404, detail=f"Chat session {session_id} not found")

    except HTTPException:
        raise
    except Exception as e:
        chat_logger.error(f"Error retrieving chat session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve chat session: {str(e)}")

@router.delete("/chat_history/sessions/{session_id}")
@bind_user_context
async def delete_session_by_id(request: Request, session_id: str):
    """
    Delete a specific chat session by ID.

    Args:
        session_id: Unique session identifier

    Returns:
        Success message
    """
    user_config = request.state.user_config
    chat_manager = ChatHistoryManager(user_config)

    try:
        # Try to delete session from all configured workflow types
        workflow_configs = get_all_workflow_configs()
        workflow_ids = list(workflow_configs.keys())

        deleted = False
        for workflow_id in workflow_ids:
            try:
                chat_manager.delete_session(workflow_id, session_id)
                deleted = True
                break
            except Exception:
                continue

        if not deleted:
            raise HTTPException(status_code=404, detail=f"Chat session {session_id} not found")

        chat_logger.info(f"Deleted chat session {session_id}")
        return {"message": f"Chat session {session_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        chat_logger.error(f"Error deleting chat session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete chat session: {str(e)}")

@router.post("/chat_history/sessions/{session_id}/messages")
@bind_user_context
async def add_message_to_session_by_id(request: Request, session_id: str, message_data: Dict[str, Any]):
    """
    Add a message to a specific chat session.

    Args:
        session_id: Unique session identifier
        message_data: Message data with 'role' and 'content' fields

    Returns:
        Updated session data
    """
    user_config = request.state.user_config
    chat_manager = ChatHistoryManager(user_config)

    try:
        # Validate message data
        if not message_data.get("content"):
            raise HTTPException(status_code=400, detail="Message content is required")

        # Try to find and load session from all configured workflow types
        workflow_configs = get_all_workflow_configs()
        workflow_ids = list(workflow_configs.keys())

        session = None
        workflow_id = None

        # Use safe session loading to handle workflow-specific sessions
        for workflow_id in workflow_ids:
            try:
                loaded_session = safe_load_session(chat_manager, workflow_id, session_id)
                if loaded_session:
                    session = loaded_session
                    break
            except HTTPException as he:
                # safe_load_session raises 404 with recovery message, continue searching
                if he.status_code != 404:
                    raise he
                continue
            except Exception:
                continue

        if not session:
            raise HTTPException(status_code=404, detail=f"Chat session {session_id} not found")

        # Create message
        message = create_chat_message(
            role=MessageRole(message_data.get("role", "user")),
            content=message_data["content"]
        )

        # Add message to session
        chat_manager.add_message_to_session(session, message)

        chat_logger.debug(f"Added message to chat session {session_id}")
        return session.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        chat_logger.error(f"Error adding message to chat session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add message: {str(e)}")

@router.get("/chat_history/sessions/{session_id}/export")
@bind_user_context
async def export_session_by_id(request: Request, session_id: str):
    """
    Export a specific chat session as JSON.

    Args:
        session_id: Unique session identifier

    Returns:
        Complete session data for export
    """
    user_config = request.state.user_config
    chat_manager = ChatHistoryManager(user_config)

    try:
        # Try to find session in all configured workflow types
        workflow_configs = get_all_workflow_configs()
        workflow_ids = list(workflow_configs.keys())

        # Use safe session loading to handle workflow-specific sessions
        for workflow_id in workflow_ids:
            try:
                session = safe_load_session(chat_manager, workflow_id, session_id)
                if session:
                    # Return export format
                    return {
                        "session_id": session.session_id,
                        "workflow_id": workflow_id,
                        "user_id": session.user_id,
                        "title": session.title,
                        "created_at": session.created_at.isoformat(),
                        "updated_at": session.updated_at.isoformat(),
                        "messages": [msg.to_dict() for msg in session.messages],
                        "exported_at": datetime.now().isoformat()
                    }
            except HTTPException as he:
                # safe_load_session raises 404s with recovery messages, continue searching
                if he.status_code != 404:
                    raise he
                continue
            except Exception:
                continue

        # Session not found
        raise HTTPException(status_code=404, detail=f"Chat session {session_id} not found")

    except HTTPException:
        raise
    except Exception as e:
        chat_logger.error(f"Error exporting chat session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to export chat session: {str(e)}")

@router.get("/workflows")
async def get_available_workflows():
    """
    Get all available workflows with their configurations.

    Returns:
        List of available workflows with metadata
    """
    try:
        workflow_configs = get_all_workflow_configs()

        workflows = []
        for workflow_name, config in workflow_configs.items():
            workflow_data = {
                "id": workflow_name,
                "display_name": config.display_name,
                "description": config.description or f"{config.display_name} workflow",
                "icon": config.icon or "🤖",  # Default robot icon
                "code_path": config.code_path,
                "timeout": config.timeout,
                "category": "adapted" if workflow_name.startswith("A_") else "ported"
            }
            workflows.append(workflow_data)

        chat_logger.debug(f"Returning {len(workflows)} workflows to frontend")
        return {"workflows": workflows}

    except Exception as e:
        chat_logger.error(f"Error retrieving workflows: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve workflows: {str(e)}")

@router.get("/chat_history/stats")
@bind_user_context
async def get_chat_history_stats(request: Request):
    """
    Get statistics about all chat sessions for the current user.

    Returns:
        Overall chat history statistics
    """
    user_config = request.state.user_config
    chat_manager = ChatHistoryManager(user_config)

    try:
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

    except Exception as e:
        chat_logger.error(f"Error retrieving chat history stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve stats: {str(e)}")

@router.post("/{workflow_id}/chat_history/new")
async def create_new_chat_session(request: Request, workflow_id: str, session_data: Optional[Dict[str, Any]] = None):
    """
    Create a new chat session for the specified workflow through SessionAuthority.

    ENFORCES SESSION ISOLATION: Only one active session per workflow.

    Args:
        workflow_id: The workflow identifier (e.g., "A_agentic_rag")
        session_data: Optional data for initializing the session

    Returns:
        ChatSession object with session details
    """
    user_config = request.state.user_config

    try:
        from super_starter_suite.chat_bot.session_authority import session_authority as _session_authority

        # Create initial message if provided
        initial_message = None
        if session_data and "initial_message" in session_data:
            msg_data = session_data["initial_message"]
            initial_message = create_chat_message(
                role=MessageRole(msg_data.get("role", "user")),
                content=msg_data.get("content", "")
            )

        # ROUTE THROUGH SessionAuthority (SINGLE SOURCE OF TRUTH)
        # This enforces exactly one active session per workflow
        session_data_result = _session_authority.get_or_create_session(
            workflow_name=workflow_id,
            user_config=user_config,
            existing_session_id=None  # Always create new for this endpoint
        )

        session = session_data_result['session']

        # Add initial message if provided
        if initial_message:
            chat_manager = ChatHistoryManager(user_config)
            chat_manager.add_message_to_session(session, initial_message)

        chat_logger.info(f"Created new chat session {session.session_id} for workflow {workflow_id} via SessionAuthority")
        return session.to_dict()

    except Exception as e:
        chat_logger.error(f"Error creating chat session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create chat session: {str(e)}")

@router.get("/{workflow_id}/chat_history")
async def get_chat_sessions(request: Request, workflow_id: str):
    """
    Get ALL SESSIONS for the specified workflow (PRESERVE USER DATA).

    NO LONGER ENFORCES "ONE SESSION PER WORKFLOW" - Chat history is valuable user data.
    SessionAuthority handles session isolation - auto-cleanup was a mistaken workaround.

    Args:
        workflow_id: The workflow instance ID (e.g., "A_agentic_rag")

    Returns:
        All sessions for this workflow (most recent first)
    """
    user_config = request.state.user_config
    chat_manager = ChatHistoryManager(user_config)

    try:
        # PRESERVE ALL USER CHAT HISTORY - get all sessions without auto-cleanup
        all_sessions = chat_manager.get_all_sessions(workflow_id)

        # Convert to frontend format
        sessions_data = []
        for session in all_sessions:
            session_data = {
                "session_id": session.session_id,
                "title": session.title or f"Chat {session.session_id[:8]}",
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "message_count": len(session.messages),
                "is_active": False  # UI can determine based on global state/lifecycle
            }
            sessions_data.append(session_data)

        chat_logger.debug(f"Returning {len(sessions_data)} sessions for {workflow_id} (no auto-cleanup)")
        return {"sessions": sessions_data}

    except Exception as e:
        chat_logger.error(f"Error retrieving chat sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve chat sessions: {str(e)}")

@router.get("/{workflow_id}/chat_history/{session_id}")
async def get_chat_session(request: Request, workflow_id: str, session_id: str, message_id: Optional[str] = None):
    """
    Get a specific chat session with full message history and artifacts.

    Args:
        workflow_id: The workflow identifier (e.g., "A_agentic_rag")
        session_id: Unique session identifier
        message_id: Optional - filter artifacts to only this message's artifacts

    Returns:
        Complete ChatSession object with artifacts filtered by message_id if specified
    """
    user_config = request.state.user_config
    chat_manager = ChatHistoryManager(user_config)

    try:
        session = chat_manager.load_session(workflow_id, session_id)

        if not session:
            raise HTTPException(status_code=404, detail=f"Chat session {session_id} not found")

        # Get session data
        session_data = session.to_dict()

        # Load artifacts for this session (restrict to this workflow to prevent cross-workflow duplication)
        artifacts = load_artifacts_for_session(session_id, chat_manager, workflow_id)

        # Filter artifacts by message_id if specified
        if message_id:
            artifacts = [art for art in artifacts if art.get('message_id') == message_id]
            chat_logger.debug(f"Filtered to {len(artifacts)} artifacts for message {message_id}")

        session_data["artifacts"] = artifacts

        chat_logger.debug(f"Loaded session {session_id} with {len(artifacts)} artifacts")
        return session_data

    except HTTPException:
        raise
    except Exception as e:
        chat_logger.error(f"Error retrieving chat session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve chat session: {str(e)}")

@router.delete("/{workflow_id}/chat_history/{session_id}")
async def delete_chat_session(request: Request, workflow_id: str, session_id: str):
    """
    Delete a specific chat session.

    Args:
        workflow_id: The workflow identifier (e.g., "A_agentic_rag")
        session_id: Unique session identifier

    Returns:
        Success message
    """
    user_config = request.state.user_config
    chat_manager = ChatHistoryManager(user_config)

    try:
        chat_manager.delete_session(workflow_id, session_id)

        chat_logger.info(f"Deleted chat session {session_id} for workflow {workflow_id}")
        return {"message": f"Chat session {session_id} deleted successfully"}

    except Exception as e:
        chat_logger.error(f"Error deleting chat session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete chat session: {str(e)}")

@router.post("/{workflow_id}/chat_history/{session_id}/message")
async def add_message_to_session(request: Request, workflow_id: str, session_id: str, message_data: Dict[str, Any]):
    """
    Add a message to an existing chat session.

    Args:
        workflow_id: The workflow identifier (e.g., "A_agentic_rag")
        session_id: Unique session identifier
        message_data: Message data with 'role' and 'content' fields

    Returns:
        Updated session data
    """
    user_config = request.state.user_config
    chat_manager = ChatHistoryManager(user_config)

    try:
        # Validate message data
        if not message_data.get("content"):
            raise HTTPException(status_code=400, detail="Message content is required")

        # Load existing session
        session = chat_manager.load_session(workflow_id, session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Chat session {session_id} not found")

        # Create message
        message = create_chat_message(
            role=MessageRole(message_data.get("role", "user")),
            content=message_data["content"]
        )

        # Add message to session
        chat_manager.add_message_to_session(session, message)

        chat_logger.debug(f"Added message to chat session {session_id} for workflow {workflow_id}")
        return session.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        chat_logger.error(f"Error adding message to chat session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add message: {str(e)}")

@router.get("/{workflow_id}/chat_history/stats")
async def get_workflow_chat_history_stats(request: Request, workflow_id: str):
    """
    Get statistics about chat sessions for a workflow.

    Args:
        workflow_id: The workflow identifier (e.g., "A_agentic_rag")

    Returns:
        Session statistics
    """
    user_config = request.state.user_config
    chat_manager = ChatHistoryManager(user_config)

    try:
        stats = chat_manager.get_session_stats(workflow_id)
        return stats

    except Exception as e:
        chat_logger.error(f"Error retrieving chat history stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve stats: {str(e)}")
