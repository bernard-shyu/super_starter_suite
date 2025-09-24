"""
Chat History Manager

This module provides the core functionality for managing persistent chat history,
including session creation, loading, saving, and LlamaIndex memory integration.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from super_starter_suite.shared.config_manager import UserConfig, config_manager
from super_starter_suite.shared.dto import (
    ChatSession,
    ChatMessageDTO,
    MessageRole,
    create_chat_session,
    create_chat_message
)

try:
    from llama_index.core.llms import ChatMessage as LlamaChatMessage
    from llama_index.core.memory import ChatMemoryBuffer
    LLAMA_INDEX_AVAILABLE = True
except ImportError:
    LLAMA_INDEX_AVAILABLE = False
    # Use Any for type checking when LlamaIndex is not available
    from typing import Any
    LlamaChatMessage = Any  # type: ignore
    ChatMemoryBuffer = Any  # type: ignore


class SessionLifecycleManager:
    """
    Manages ONE ACTIVE SESSION per workflow with persistent mappings.

    Ensures each workflow maintains exactly one active session, handling:
    - Workflow-to-session mapping persistence
    - Session validation and cleanup
    - Multi-user access isolation
    - Concurrent access protection (future: file locking)
    """

    def __init__(self, user_id: str, chat_manager: 'ChatHistoryManager'):
        self.user_id = user_id
        self.chat_manager = chat_manager
        self.mapping_file = self._get_mapping_file_path()
        self.workflow_sessions = self._load_persisted_mappings()
        self.logger = config_manager.get_logger("history.lifecycle")

    def _get_mapping_file_path(self) -> Path:
        """Get path for workflow-to-session mapping file"""
        return self.chat_manager.storage_path / "workflow_sessions.json"

    def _load_persisted_mappings(self) -> Dict[str, str]:
        """Load persisted workflow-to-session mappings"""
        if not self.mapping_file.exists():
            return {}

        try:
            with open(self.mapping_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.warning(f"Failed to load session mappings: {e}")
            return {}

    def _save_mappings(self) -> None:
        """Persist workflow-to-session mappings"""
        try:
            with open(self.mapping_file, 'w', encoding='utf-8') as f:
                json.dump(self.workflow_sessions, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save session mappings: {e}")

    def get_or_create_workflow_session(self, workflow_type: str) -> str:
        """
        Get ACTIVE session for workflow, create if none exists.

        Guarantees: ONE session per workflow, persisted across server restarts.
        """
        if workflow_type in self.workflow_sessions:
            # Verify existing session still exists and is valid
            session_id = self.workflow_sessions[workflow_type]
            session = self.chat_manager.load_session(workflow_type, session_id)
            if session:
                self.logger.debug(f"Reusing active session {session_id} for {workflow_type}")
                return session_id
            else:
                # Session is invalid, clean it up
                self.logger.info(f"Cleaning up invalid session {session_id} for {workflow_type}")
                del self.workflow_sessions[workflow_type]

        # Create new session and map it to workflow
        session = self.chat_manager.create_new_session(workflow_type)
        self.workflow_sessions[workflow_type] = session.session_id
        self._save_mappings()
        self.logger.info(f"Created new session {session.session_id} for {workflow_type}")

        return session.session_id

    def cleanup_invalid_sessions(self) -> int:
        """Clean up workflow mappings for sessions that no longer exist"""
        cleaned = 0
        for workflow_type, session_id in list(self.workflow_sessions.items()):
            session = self.chat_manager.load_session(workflow_type, session_id)
            if not session:
                self.logger.warning(f"Removing invalid mapping {workflow_type} -> {session_id}")
                del self.workflow_sessions[workflow_type]
                cleaned += 1

        if cleaned > 0:
            self._save_mappings()
        return cleaned


class ChatHistoryManager:
    """
    Core component for managing chat history persistence and LlamaIndex memory integration.

    This class handles the lifecycle of chat sessions, including creation, loading,
    saving, and conversion to/from LlamaIndex memory buffers for conversational context.
    """

    def __init__(self, user_config: UserConfig):
        """
        Initialize the ChatHistoryManager with user-specific configuration.

        Args:
            user_config: UserConfig instance containing chat history settings
        """
        self.user_config = user_config
        self.logger = config_manager.get_logger("history.storage")

        # Get chat history configuration
        if not self.user_config.chat_history_config:
            self.logger.warning(f"No chat history config found for user {user_config.user_id}")
            # Create default config
            from super_starter_suite.shared.dto import ChatHistoryConfig
            self.chat_history_config = ChatHistoryConfig()
        else:
            self.chat_history_config = self.user_config.chat_history_config

        # Set up storage directory (user-specific)
        self.storage_path = self._get_storage_path()

        # Ensure user-specific storage directory exists
        os.makedirs(self.storage_path, exist_ok=True)

        self.logger.debug(f"ChatHistoryManager initialized for user {user_config.user_id} with path {self.storage_path}")

    def _get_storage_path(self) -> Path:
        """Get the storage path for chat history files."""
        base_path = Path(self.user_config.get_user_setting(
            "USER_PREFERENCES.USER_RAG_ROOT",
            "default_rag_root"
        ))
        chat_history_path = base_path / self.chat_history_config.chat_history_storage_path
        return chat_history_path

    def _get_history_file_path(self, workflow_type: str, session_id: str, session: Optional['ChatSession'] = None, create_dir: bool = False) -> Path:
        """
        Generate the file path for a session's history.
        For new sessions, use session.created_at timestamp for consistent naming.

        Supports migration from previous USER_RAG_ROOT locations.

        Args:
            workflow_type: The workflow type (e.g., "agentic-rag")
            session_id: Unique session identifier
            session: Optional ChatSession object (required for creating new filenames)
            create_dir: If True, create the workflow directory if it doesn't exist

        Returns:
            Path to the history file: chat_history/workflow_type/DATE-TIME.session_id.json
        """
        # Get primary workflow directory path
        workflow_dir = self.storage_path / workflow_type

        if create_dir:
            # Create directory only when explicitly requested (e.g., for saving)
            workflow_dir.mkdir(exist_ok=True)

        if session and session.created_at:
            # New session being saved - use its created_at timestamp directly
            iso_timestamp = session.created_at.isoformat()
            timestamp_str = iso_timestamp.replace(':', '-').replace('+', 'P').replace('.', 'D')
            filename = f"{timestamp_str}.{session_id}.json"
        else:
            # For loading existing sessions, search multiple potential locations

            # 1. Try new format first (in workflow subdirectory of current USER_RAG_ROOT)
            for file_path in workflow_dir.glob(f"*.{session_id}.json"):
                if file_path.exists():
                    return file_path

            # 2. Try legacy directories within current USER_RAG_ROOT path
            potential_paths = [
                self.storage_path / f"chat_history_{workflow_type}_{session_id}.json",  # Old format in root
                self.storage_path.parent / "Super-RAG.Bernard" / "chat_history" / workflow_type,  # Alternative Bernard root
                self.storage_path.parent / "Super-RAG.Default" / "chat_history" / workflow_type,  # Old Default root
            ]

            for potential_path in potential_paths:
                if potential_path.is_file() and potential_path.exists():
                    return potential_path
                # Also check as directory for new format files
                if potential_path.is_dir():
                    for file_path in potential_path.glob(f"*.{session_id}.json"):
                        if file_path.exists():
                            return file_path

            # File not found - this will cause the operation to fail gracefully
            return workflow_dir / f"notfound.{session_id}.json"

        return workflow_dir / filename

    def _load_raw_history(self, workflow_type: str, session_id: str) -> List[Dict[str, Any]]:
        """
        Load raw message data from storage.

        Args:
            workflow_type: The workflow type
            session_id: Unique session identifier

        Returns:
            List of raw message dictionaries
        """
        file_path = self._get_history_file_path(workflow_type, session_id)

        if not file_path.exists():
            return []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Handle both old format (just messages) and new format (full session)
            if isinstance(data, list):
                # Old format: just messages
                return data
            elif isinstance(data, dict) and "messages" in data:
                # New format: full session data
                return data["messages"]
            else:
                self.logger.warning(f"Invalid chat history format in {file_path}")
                return []

        except (json.JSONDecodeError, IOError) as e:
            self.logger.error(f"Error loading chat history from {file_path}: {e}")
            return []

    def _save_raw_history(self, workflow_type: str, session_id: str, messages: List[Dict[str, Any]]) -> None:
        """
        Save raw message data to storage.

        Args:
            workflow_type: The workflow type
            session_id: Unique session identifier
            messages: List of raw message dictionaries
        """
        file_path = self._get_history_file_path(workflow_type, session_id)

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(messages, f, indent=2, ensure_ascii=False)
        except IOError as e:
            self.logger.error(f"Error saving chat history to {file_path}: {e}")
            raise

    def get_all_sessions(self, workflow_type: str) -> List[ChatSession]:
        """
        Retrieve a list of all chat sessions for a given workflow.

        Args:
            workflow_type: The workflow type to get sessions for

        Returns:
            List of ChatSession objects
        """
        sessions = []

        # Try primary workflow directory (underscore format)
        workflow_dir = self.storage_path / workflow_type
        if workflow_dir.exists():
            sessions.extend(self._load_sessions_from_directory(workflow_dir, workflow_type))

        # Also try dash variant for compatibility (frontend uses dashes)
        dash_workflow = workflow_type.replace('_', '-')
        dash_workflow_dir = self.storage_path / dash_workflow
        if dash_workflow_dir.exists():
            sessions.extend(self._load_sessions_from_directory(dash_workflow_dir, workflow_type))

        # Remove duplicates if any (same session loaded from multiple locations)
        seen_sessions = set()
        unique_sessions = []
        for session in sessions:
            session_key = (session.session_id, session.workflow_type)
            if session_key not in seen_sessions:
                seen_sessions.add(session_key)
                unique_sessions.append(session)

        # Sort by updated_at (most recent first)
        unique_sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return unique_sessions

    def _load_sessions_from_directory(self, workflow_dir: Path, workflow_type: str) -> List[ChatSession]:
        """
        Load all sessions from a specific workflow directory.
        """
        sessions = []

        # Look for all session files in workflow subdirectory (new format: DATE-TIME.session_id.json)
        for file_path in workflow_dir.glob("*.json"):
            try:
                # Extract session_id from filename (format: DATE-TIME.session_id.json)
                filename = file_path.name
                if filename.endswith('.json') and '.' in filename.rsplit('.json', 1)[0]:
                    # Split on last dot to get timestamp.session_id
                    timestamp_and_session = filename.rsplit('.json', 1)[0]
                    session_id = timestamp_and_session.split('.', 1)[1]  # After timestamp dot

                    # Load the session directly from known file path
                    session = self.load_session_from_file(workflow_type, session_id, file_path)
                    if session:
                        sessions.append(session)
                    else:
                        self.logger.warning(f"Could not load session {session_id} from {file_path}")

            except Exception as e:
                self.logger.error(f"Error loading session from {file_path}: {e}")

        return sessions

    def load_session_from_file(self, workflow_type: str, session_id: str, file_path: Path) -> Optional[ChatSession]:
        """
        Load a session directly from a known file path.

        Args:
            workflow_type: Expected workflow type
            session_id: Expected session ID
            file_path: Exact path to the session file

        Returns:
            ChatSession object or None if not found/valid
        """
        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if isinstance(data, list):
                # Old format: convert to new format
                session_data = {
                    "session_id": session_id,
                    "user_id": self.user_config.user_id,
                    "workflow_type": workflow_type,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "title": "",
                    "messages": data,
                    "metadata": {}
                }
            elif isinstance(data, dict):
                # New format: ensure all required fields
                # CRITICAL: Use the WORKFLOW_TYPE FROM THE FILE, NOT THE PARAMETER!
                # Files may contain "agentic-rag" while backend calls with "agentic_rag"
                session_data = data.copy()
                session_data.setdefault("session_id", session_id)
                session_data.setdefault("user_id", self.user_config.user_id)
                # Use workflow_type from file, or fall back to parameter if missing
                session_data.setdefault("workflow_type", workflow_type)
                session_data.setdefault("title", "")
                session_data.setdefault("messages", [])
                session_data.setdefault("metadata", {})
            else:
                self.logger.error(f"Invalid session data format in {file_path}")
                return None

            # Convert to ChatSession object
            session = ChatSession.from_dict(session_data)
            return session

        except (json.JSONDecodeError, IOError, KeyError) as e:
            self.logger.error(f"Error loading session {session_id} from {file_path}: {e}")
            return None

    def load_session(self, workflow_type: str, session_id: str) -> Optional[ChatSession]:
        """
        Load a specific chat session.

        Args:
            workflow_type: The workflow type
            session_id: Unique session identifier

        Returns:
            ChatSession object or None if not found
        """
        file_path = self._get_history_file_path(workflow_type, session_id)

        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if isinstance(data, list):
                # Old format: convert to new format
                session_data = {
                    "session_id": session_id,
                    "user_id": self.user_config.user_id,
                    "workflow_type": workflow_type,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "title": "",
                    "messages": data,
                    "metadata": {}
                }
            elif isinstance(data, dict):
                # New format: ensure all required fields
                # CRITICAL: Use the WORKFLOW_TYPE FROM THE FILE, NOT THE PARAMETER!
                # Files may contain "agentic-rag" while backend calls with "agentic_rag"
                session_data = data.copy()
                session_data.setdefault("session_id", session_id)
                session_data.setdefault("user_id", self.user_config.user_id)
                # Use workflow_type from file, or fall back to parameter if missing
                session_data.setdefault("workflow_type", workflow_type)
                session_data.setdefault("title", "")
                session_data.setdefault("messages", [])
                session_data.setdefault("metadata", {})
            else:
                self.logger.error(f"Invalid session data format in {file_path}")
                return None

            # Convert to ChatSession object
            session = ChatSession.from_dict(session_data)
            return session

        except (json.JSONDecodeError, IOError, KeyError) as e:
            self.logger.error(f"Error loading session {session_id}: {e}")
            return None

    def save_session(self, session: ChatSession) -> None:
        """
        Save or update a chat session.

        Args:
            session: ChatSession object to save
        """
        # Validate session belongs to current user
        if session.user_id != self.user_config.user_id:
            raise ValueError(f"Session user_id {session.user_id} does not match current user {self.user_config.user_id}")

        # Convert to dictionary and save
        session_data = session.to_dict()
        file_path = self._get_history_file_path(session.workflow_type, session.session_id, session, create_dir=True)

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            self.logger.error(f"Error saving session {session.session_id}: {e}")
            raise

    def create_new_session(self, workflow_type: str, initial_message: Optional[ChatMessageDTO] = None) -> ChatSession:
        """
        Create and initialize a new chat session.

        Args:
            workflow_type: The workflow type for the session
            initial_message: Optional initial message to add

        Returns:
            Newly created ChatSession object
        """
        session = create_chat_session(
            user_id=self.user_config.user_id,
            workflow_type=workflow_type
        )

        # Add initial message if provided
        if initial_message:
            session.add_message(initial_message)
            session.generate_title()

        # Save the session
        self.save_session(session)

        self.logger.info(f"Created new chat session {session.session_id} for workflow {workflow_type}")
        return session

    def delete_session(self, workflow_type: str, session_id: str) -> None:
        """
        Delete a specific chat session.

        Args:
            workflow_type: The workflow type
            session_id: Unique session identifier
        """
        file_path = self._get_history_file_path(workflow_type, session_id)

        if file_path.exists():
            try:
                file_path.unlink()
                self.logger.info(f"Deleted chat session {session_id} for workflow {workflow_type}")
            except IOError as e:
                self.logger.error(f"Error deleting session {session_id}: {e}")
                raise
        else:
            self.logger.warning(f"Session {session_id} not found for deletion")

    def add_message_to_session(self, session: ChatSession, message: ChatMessageDTO) -> None:
        """
        Add a new message to a session's history.

        Args:
            session: ChatSession object to update
            message: ChatMessageDTO to add
        """
        # Apply message size limit
        if len(session.messages) >= self.chat_history_config.chat_history_max_size:
            # Remove oldest messages to make room
            remove_count = len(session.messages) - self.chat_history_config.chat_history_max_size + 1
            session.messages = session.messages[remove_count:]

        session.add_message(message)

        # Update title if it's the first user message
        if not session.title and message.role == MessageRole.USER:
            session.generate_title()

        # Save the updated session
        self.save_session(session)

    def get_llama_index_memory(self, session: ChatSession) -> Optional[Any]:
        """
        Convert ChatSession messages into a LlamaIndex ChatMemoryBuffer.

        Args:
            session: ChatSession object to convert

        Returns:
            ChatMemoryBuffer instance or None if LlamaIndex not available
        """
        if not LLAMA_INDEX_AVAILABLE:
            self.logger.warning("LlamaIndex not available, cannot create ChatMemoryBuffer")
            return None

        try:
            # Convert our messages to LlamaIndex format
            llama_messages = []
            for msg in session.messages:
                llama_msg = LlamaChatMessage(
                    role=msg.role.value,
                    content=msg.content,
                    additional_kwargs=msg.metadata
                )
                llama_messages.append(llama_msg)

            # Create ChatMemoryBuffer
            memory = ChatMemoryBuffer.from_defaults(
                chat_history=llama_messages,
                token_limit=self.chat_history_config.chat_history_max_size
            )

            return memory

        except Exception as e:
            self.logger.error(f"Error creating LlamaIndex memory buffer: {e}")
            return None

    def get_session_stats(self, workflow_type: str) -> Dict[str, Any]:
        """
        Get statistics about chat sessions for a workflow.

        Args:
            workflow_type: The workflow type to get stats for

        Returns:
            Dictionary with session statistics
        """
        sessions = self.get_all_sessions(workflow_type)

        if not sessions:
            return {
                "total_sessions": 0,
                "total_messages": 0,
                "oldest_session": None,
                "newest_session": None
            }

        total_messages = sum(len(session.messages) for session in sessions)
        oldest_session = min(sessions, key=lambda s: s.created_at)
        newest_session = max(sessions, key=lambda s: s.updated_at)

        return {
            "total_sessions": len(sessions),
            "total_messages": total_messages,
            "oldest_session": oldest_session.created_at.isoformat(),
            "newest_session": newest_session.updated_at.isoformat()
        }
