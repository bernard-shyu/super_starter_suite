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
        self.logger = config_manager.get_logger("chat_history")

        # Get chat history configuration
        if not self.user_config.chat_history_config:
            self.logger.warning(f"No chat history config found for user {user_config.user_id}")
            # Create default config
            from super_starter_suite.shared.dto import ChatHistoryConfig
            self.chat_history_config = ChatHistoryConfig()
        else:
            self.chat_history_config = self.user_config.chat_history_config

        # Set up storage directory
        self.storage_path = self._get_storage_path()

        # Ensure storage directory exists
        os.makedirs(self.storage_path, exist_ok=True)

        self.logger.debug(f"ChatHistoryManager initialized for user {user_config.user_id}")

    def _get_storage_path(self) -> Path:
        """Get the storage path for chat history files."""
        base_path = Path(self.user_config.get_user_setting(
            "USER_PREFERENCES.USER_RAG_ROOT",
            "default_rag_root"
        ))
        chat_history_path = base_path / self.chat_history_config.chat_history_storage_path
        return chat_history_path

    def _get_history_file_path(self, workflow_type: str, session_id: str) -> Path:
        """
        Generate the file path for a session's history.

        Args:
            workflow_type: The workflow type (e.g., "agentic_rag")
            session_id: Unique session identifier

        Returns:
            Path to the history file
        """
        filename = f"chat_history_{workflow_type}_{session_id}.json"
        return self.storage_path / filename

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
        workflow_dir = self.storage_path

        if not workflow_dir.exists():
            return sessions

        # Look for all chat history files for this workflow type
        pattern = f"chat_history_{workflow_type}_*.json"
        for file_path in workflow_dir.glob(pattern):
            try:
                # Extract session_id from filename
                filename = file_path.name
                session_id = filename.replace(f"chat_history_{workflow_type}_", "").replace(".json", "")

                # Load the session
                session = self.load_session(workflow_type, session_id)
                if session:
                    sessions.append(session)

            except Exception as e:
                self.logger.error(f"Error loading session from {file_path}: {e}")

        # Sort by updated_at (most recent first)
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions

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
                session_data = data.copy()
                session_data.setdefault("session_id", session_id)
                session_data.setdefault("user_id", self.user_config.user_id)
                session_data.setdefault("workflow_type", workflow_type)
                session_data.setdefault("title", "")
                session_data.setdefault("messages", [])
                session_data.setdefault("metadata", {})
            else:
                self.logger.error(f"Invalid session data format in {file_path}")
                return None

            # Convert to ChatSession object
            return ChatSession.from_dict(session_data)

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
        file_path = self._get_history_file_path(session.workflow_type, session.session_id)

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
                memory_size=self.chat_history_config.chat_history_max_size
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
