"""
Chat History API Endpoints

This module provides FastAPI endpoints for chat history management,
including session creation, loading, deletion, and message management.
"""

from fastapi import APIRouter, Request, HTTPException
from typing import Dict, Any, Optional
from datetime import datetime
from super_starter_suite.shared.config_manager import config_manager
from super_starter_suite.shared.decorators import bind_user_context
from super_starter_suite.chat_history.chat_history_manager import ChatHistoryManager
from super_starter_suite.shared.dto import ChatSession, ChatMessageDTO, MessageRole, create_chat_message

# Get logger for chat history API
chat_logger = config_manager.get_logger("history.api")

# Create router
router = APIRouter()

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
        # Get sessions for all workflow types
        all_sessions = []

        # List of all workflow types
        workflow_types = [
            "agentic_rag", "code_generator", "deep_research",
            "document_generator", "financial_report", "human_in_the_loop"
        ]

        for workflow_type in workflow_types:
            try:
                sessions = chat_manager.get_all_sessions(workflow_type)
                for session in sessions:
                    session_data = {
                        "session_id": session.session_id,
                        "workflow_type": session.workflow_type,  # Use ORIGINAL session workflow_type
                        "title": session.title or f"Chat {session.session_id[:8]}",
                        "created_at": session.created_at.isoformat(),
                        "updated_at": session.updated_at.isoformat(),
                        "message_count": len(session.messages)
                    }
                    all_sessions.append(session_data)

            except Exception as e:
                chat_logger.warning(f"Error loading sessions for {workflow_type}: {e}")
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
    Create a new chat session.

    Args:
        session_data: Session data including workflow_type and optional title

    Returns:
        New ChatSession object
    """
    user_config = request.state.user_config
    chat_manager = ChatHistoryManager(user_config)

    try:
        workflow_type = session_data.get("workflow_type", "agentic_rag")
        title = session_data.get("title", "")

        # Create new session
        session = chat_manager.create_new_session(workflow_type)

        if title:
            session.title = title

        # Save the session
        chat_manager.save_session(session)

        chat_logger.info(f"Created new chat session {session.session_id} for workflow {workflow_type}")
        return session.to_dict()

    except Exception as e:
        chat_logger.error(f"Error creating chat session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create chat session: {str(e)}")

@router.get("/chat_history/sessions/{session_id}")
@bind_user_context
async def get_session_by_id(request: Request, session_id: str):
    """
    Get a specific chat session by ID.

    Args:
        session_id: Unique session identifier

    Returns:
        Complete ChatSession object
    """
    user_config = request.state.user_config
    chat_manager = ChatHistoryManager(user_config)

    try:
        # Try to find session in all workflow types (and their variants)
        workflow_types = [
            "agentic_rag", "code_generator", "deep_research",
            "document_generator", "financial_report", "human_in_the_loop"
        ]

        # Also try dash variants for compatibility
        all_types_to_try = workflow_types + [wf.replace('_', '-') for wf in workflow_types]

        for workflow_type in all_types_to_try:
            try:
                session = chat_manager.load_session(workflow_type, session_id)
                if session:
                    return session.to_dict()
            except Exception:
                continue

        # Session not found
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
        # Try to delete session from all workflow types
        workflow_types = [
            "agentic_rag", "code_generator", "deep_research",
            "document_generator", "financial_report", "human_in_the_loop"
        ]

        deleted = False
        for workflow_type in workflow_types:
            try:
                chat_manager.delete_session(workflow_type, session_id)
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

        # Try to find and load session from all workflow types
        workflow_types = [
            "agentic_rag", "code_generator", "deep_research",
            "document_generator", "financial_report", "human_in_the_loop"
        ]

        session = None
        workflow_type = None

        for wf_type in workflow_types:
            try:
                session = chat_manager.load_session(wf_type, session_id)
                if session:
                    workflow_type = wf_type
                    break
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
        # Try to find session in all workflow types
        workflow_types = [
            "agentic_rag", "code_generator", "deep_research",
            "document_generator", "financial_report", "human_in_the_loop"
        ]

        for workflow_type in workflow_types:
            try:
                session = chat_manager.load_session(workflow_type, session_id)
                if session:
                    # Return export format
                    return {
                        "session_id": session.session_id,
                        "workflow_type": workflow_type,
                        "user_id": session.user_id,
                        "title": session.title,
                        "created_at": session.created_at.isoformat(),
                        "updated_at": session.updated_at.isoformat(),
                        "messages": [msg.to_dict() for msg in session.messages],
                        "exported_at": datetime.now().isoformat()
                    }
            except Exception:
                continue

        # Session not found
        raise HTTPException(status_code=404, detail=f"Chat session {session_id} not found")

    except HTTPException:
        raise
    except Exception as e:
        chat_logger.error(f"Error exporting chat session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to export chat session: {str(e)}")

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
        # Get stats for all workflow types
        workflow_types = [
            "agentic_rag", "code_generator", "deep_research",
            "document_generator", "financial_report", "human_in_the_loop"
        ]

        total_sessions = 0
        total_messages = 0
        workflow_stats = {}

        for workflow_type in workflow_types:
            try:
                stats = chat_manager.get_session_stats(workflow_type)
                workflow_stats[workflow_type] = stats
                total_sessions += stats.get("total_sessions", 0)
                total_messages += stats.get("total_messages", 0)
            except Exception as e:
                chat_logger.warning(f"Error getting stats for {workflow_type}: {e}")
                continue

        return {
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "workflows": workflow_stats
        }

    except Exception as e:
        chat_logger.error(f"Error retrieving chat history stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve stats: {str(e)}")

@router.post("/{workflow_type}/chat_history/new")
async def create_new_chat_session(request: Request, workflow_type: str, session_data: Optional[Dict[str, Any]] = None):
    """
    Create a new chat session for the specified workflow type.

    Args:
        workflow_type: The workflow type (e.g., "agentic_rag")
        session_data: Optional data for initializing the session

    Returns:
        ChatSession object with session details
    """
    user_config = request.state.user_config
    chat_manager = ChatHistoryManager(user_config)

    try:
        # Create initial message if provided
        initial_message = None
        if session_data and "initial_message" in session_data:
            msg_data = session_data["initial_message"]
            initial_message = create_chat_message(
                role=MessageRole(msg_data.get("role", "user")),
                content=msg_data.get("content", "")
            )

        # Create new session
        session = chat_manager.create_new_session(workflow_type, initial_message)

        chat_logger.info(f"Created new chat session {session.session_id} for workflow {workflow_type}")
        return session.to_dict()

    except Exception as e:
        chat_logger.error(f"Error creating chat session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create chat session: {str(e)}")

@router.get("/{workflow_type}/chat_history")
async def get_chat_sessions(request: Request, workflow_type: str):
    """
    Get all chat sessions for the specified workflow type.

    Args:
        workflow_type: The workflow type (e.g., "agentic_rag")

    Returns:
        List of chat sessions with basic info
    """
    user_config = request.state.user_config
    chat_manager = ChatHistoryManager(user_config)

    try:
        sessions = chat_manager.get_all_sessions(workflow_type)

        # Return simplified session info for listing
        session_list = []
        for session in sessions:
            session_list.append({
                "session_id": session.session_id,
                "title": session.title or f"Chat {session.session_id[:8]}",
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "message_count": len(session.messages)
            })

        return {"sessions": session_list}

    except Exception as e:
        chat_logger.error(f"Error retrieving chat sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve chat sessions: {str(e)}")

@router.get("/{workflow_type}/chat_history/{session_id}")
async def get_chat_session(request: Request, workflow_type: str, session_id: str):
    """
    Get a specific chat session with full message history.

    Args:
        workflow_type: The workflow type (e.g., "agentic_rag")
        session_id: Unique session identifier

    Returns:
        Complete ChatSession object
    """
    user_config = request.state.user_config
    chat_manager = ChatHistoryManager(user_config)

    try:
        session = chat_manager.load_session(workflow_type, session_id)

        if not session:
            raise HTTPException(status_code=404, detail=f"Chat session {session_id} not found")

        return session.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        chat_logger.error(f"Error retrieving chat session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve chat session: {str(e)}")

@router.delete("/{workflow_type}/chat_history/{session_id}")
async def delete_chat_session(request: Request, workflow_type: str, session_id: str):
    """
    Delete a specific chat session.

    Args:
        workflow_type: The workflow type (e.g., "agentic_rag")
        session_id: Unique session identifier

    Returns:
        Success message
    """
    user_config = request.state.user_config
    chat_manager = ChatHistoryManager(user_config)

    try:
        chat_manager.delete_session(workflow_type, session_id)

        chat_logger.info(f"Deleted chat session {session_id} for workflow {workflow_type}")
        return {"message": f"Chat session {session_id} deleted successfully"}

    except Exception as e:
        chat_logger.error(f"Error deleting chat session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete chat session: {str(e)}")

@router.post("/{workflow_type}/chat_history/{session_id}/message")
async def add_message_to_session(request: Request, workflow_type: str, session_id: str, message_data: Dict[str, Any]):
    """
    Add a message to an existing chat session.

    Args:
        workflow_type: The workflow type (e.g., "agentic_rag")
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
        session = chat_manager.load_session(workflow_type, session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Chat session {session_id} not found")

        # Create message
        message = create_chat_message(
            role=MessageRole(message_data.get("role", "user")),
            content=message_data["content"]
        )

        # Add message to session
        chat_manager.add_message_to_session(session, message)

        chat_logger.debug(f"Added message to chat session {session_id} for workflow {workflow_type}")
        return session.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        chat_logger.error(f"Error adding message to chat session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add message: {str(e)}")

@router.get("/{workflow_type}/chat_history/stats")
async def get_workflow_chat_history_stats(request: Request, workflow_type: str):
    """
    Get statistics about chat sessions for a workflow.

    Args:
        workflow_type: The workflow type (e.g., "agentic_rag")

    Returns:
        Session statistics
    """
    user_config = request.state.user_config
    chat_manager = ChatHistoryManager(user_config)

    try:
        stats = chat_manager.get_session_stats(workflow_type)
        return stats

    except Exception as e:
        chat_logger.error(f"Error retrieving chat history stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve stats: {str(e)}")
