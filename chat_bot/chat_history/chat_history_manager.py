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
    ChatSessionData,
    ChatMessageDTO,
    MessageRole,
    create_chat_session_data,
    create_chat_message,
    WorkflowConfig
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

    def __init__(self, user_config: UserConfig, session_owner: Optional[Any] = None):
        """
        Initialize the ChatHistoryManager with user-specific configuration and session association.

        Args:
            user_config: UserConfig instance containing chat history settings
            session_owner: Associated ChatBotSession-derived instance (WorkflowSession or HistorySession)
                          for direct access to session state and lifecycle management
        """
        self.user_config = user_config
        self.session_owner = session_owner  # ESTABLISHED ASSOCIATION: Session owns ChatHistoryManager
        self.logger = config_manager.get_logger("history.storage")

        self.session_file_id = (getattr(self.session_owner, 'session_id', None) if self.session_owner else "unknown") or "unknown"

        # Initialize configuration and storage paths
        self._initialize_config_and_storage()

    @property
    def my_workflow_id(self) -> str:
        """Dynamic retrieval of workflow_id from session_owner to prevent state drift"""
        if not self.session_owner:
            return "unknown"
        return getattr(self.session_owner, 'active_workflow_id', None) or "unknown"

    @property
    def my_session_id(self) -> str:
        """Dynamic retrieval of infrastructure session_id from session_owner"""
        if not self.session_owner:
            return "unknown"
        return getattr(self.session_owner, 'session_id', None) or "unknown"

    def _initialize_config_and_storage(self):
        """Initialize chat history configuration and storage directories"""

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

        # RESTORED: SessionLifecycleManager functionality - Workflow-to-session mapping
        self.workflow_sessions = self._load_persisted_mappings()

        self.logger.debug(f"ChatHistoryManager initialized for user {self.user_config.user_id} with path {self.storage_path}")

    def _load_persisted_mappings(self) -> Dict[str, str]:
        """
        Load persisted workflow-to-session mappings from workflow_sessions.json.

        RESTORED from SessionLifecycleManager: Ensures workflow context persistence.

        Returns:
            Dict mapping workflow names to their active session IDs
        """
        mapping_file = self.storage_path / "workflow_sessions.json"
        if not mapping_file.exists():
            return {}

        try:
            with open(mapping_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.warning(f"Failed to load workflow session mappings: {e}")
            return {}

    def _save_mappings(self) -> None:
        """
        Persist workflow-to-session mappings to workflow_sessions.json.

        RESTORED from SessionLifecycleManager: Critical for workflow context persistence.
        """
        mapping_file = self.storage_path / "workflow_sessions.json"

        try:
            with open(mapping_file, 'w', encoding='utf-8') as f:
                json.dump(self.workflow_sessions, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save workflow session mappings: {e}")

    def _get_storage_path(self) -> Path:
        """Get the storage path for chat history files."""
        rag_root = getattr(self.user_config, 'my_rag_root', None)
        if not rag_root:
            raise ValueError("my_rag_root configuration is required but not set")

        base_path = Path(rag_root)
        chat_history_path = base_path / self.chat_history_config.chat_history_storage_path
        return chat_history_path

    def _get_history_file_path(self, workflow_id: str, session_id: str, session: Optional['ChatSessionData'] = None, create_dir: bool = False) -> Path:
        """
        Generate the file path for a session's history with TIMESTAMP PRESERVATION.

        SESSION FILE RESUMPTION LOGIC:
        1. FIRST: Look for existing files with this session_id (any timestamp)
        2. If found: Use the existing file (preserves original timestamp)
        3. If not found: Create new file with current timestamp

        This ensures session resumption saves to the original file with its creation timestamp.

        Args:
            workflow_id: The workflow ID (may be prefixed like A_agentic_rag)
            session_id: Unique session identifier
            session: Optional ChatSessionData object (for new file creation)
            create_dir: If True, create the workflow directory if it doesn't exist

        Returns:
            Path to the history file: chat_history/workflow_id/[TIMESTAMP.]session_id.json
        """
        workflow_dir = self.storage_path / workflow_id

        if create_dir:
            workflow_dir.mkdir(exist_ok=True)

        # SESSION RESUMPTION: FIRST, try to find existing file for this session_id
        for file_path in workflow_dir.glob(f"*.{session_id}.json"):
            if file_path.exists():
                # FOUND EXISTING FILE: Use it (preserves original timestamp)
                return file_path

        # NO EXISTING FILE: Create new file with timestamp (new session)
        if session and session.created_at:
            iso_timestamp = session.created_at.isoformat()
            timestamp_str = iso_timestamp.replace(':', '-').replace('+', 'P').replace('.', 'D')
            filename = f"{timestamp_str}.{session_id}.json"
            return workflow_dir / filename

        # FALLBACK: Should not happen in normal operation
        return workflow_dir / f"unknown.{session_id}.json"

    def _load_raw_history(self, workflow_id: str, session_id: str) -> List[Dict[str, Any]]:
        """
        Load raw message data from storage.

        Args:
            workflow_id: The workflow ID
            session_id: Unique session identifier

        Returns:
            List of raw message dictionaries
        """
        file_path = self._get_history_file_path(workflow_id, session_id)

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

    def _save_raw_history(self, workflow_id: str, session_id: str, messages: List[Dict[str, Any]]) -> None:
        """
        Save raw message data to storage using SESSION FILE ID DECOUPLING.

        Uses self.session_file_id for file naming instead of session_id parameter.
        This enables saving to existing active files instead of creating new ones.

        Args:
            workflow_id: The workflow ID
            session_id: Unique session identifier (for logging only)
            messages: List of raw message dictionaries
        """
        # SESSION FILE ID DECOUPLING: Use session_file_id for actual file operations
        file_path = self._get_history_file_path(workflow_id, self.session_file_id)
        self.logger.debug(f"Save session_data into path {file_path} for workflow {workflow_id} using file_id {self.session_file_id} (session_id: {session_id})")

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(messages, f, indent=2, ensure_ascii=False)
        except IOError as e:
            self.logger.error(f"Error saving chat history to {file_path}: {e}")
            raise

    def get_active_session_with_priority(self, workflow_name: str) -> Optional[ChatSessionData]:
        """
        Get the SINGLE ACTIVE session for a workflow with SESSION FILE ID DECOUPLING.

        SESSION FILE ID LOGIC:
        - Check for active session mapping from workflow_sessions.json
        - If found: SET session_file_id to active session's file ID (decouples from session manager ID)
        - If not found: Keep default session_file_id (same as session manager ID)

        This enables workflow execution to save to existing active files instead of creating new ones.

        Args:
            workflow_name: The workflow name to get active session for

        Returns:
            The ChatSessionData for active session, or None if no active session
        """
        try:
            # CHECK FOR ACTIVE SESSION MAPPING: Use workflow_sessions.json to find active session
            active_session_id = self._get_active_session_id(workflow_name)

            if active_session_id:
                # ACTIVE SESSION FOUND: Load the session and set session_file_id to its file ID
                active_session = self.load_session(workflow_name, active_session_id)
                if active_session:
                    # SESSION FILE ID DECOUPLING: Set file ID to active session's ID for saving
                    self.session_file_id = active_session.session_id
                    self.logger.debug(f"Active session found for {workflow_name}: file_id={self.session_file_id}")
                    return active_session

            # NO ACTIVE SESSION: Keep default session_file_id (same as session manager ID)
            self.logger.debug(f"No active session found for {workflow_name}, using default file_id={self.session_file_id}")
            return None

        except Exception as e:
            self.logger.error(f"Failed to get active session with priority for {workflow_name}: {e}")
            return None

    def set_active_session(self, workflow_name: str, session_id: str) -> None:
        """
        Set the active session for a workflow (PUBLIC API).

        Updates workflow_sessions.json to mark the specified session as active.
        Only one active session per workflow is maintained.

        Args:
            workflow_name: The workflow name
            session_id: The session ID to mark as active (must exist)
        """
        try:
            # Load current mappings
            mapping_file = self.storage_path / "workflow_sessions.json"
            mappings = {}

            if mapping_file.exists():
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    mappings = json.load(f)

            # Update the mapping for this workflow
            mappings[workflow_name] = session_id

            # Save updated mappings
            with open(mapping_file, 'w', encoding='utf-8') as f:
                json.dump(mappings, f, indent=2)

            self.logger.debug(f"Set active session for {workflow_name}: {session_id}")

        except Exception as e:
            self.logger.error(f"Failed to set active session for {workflow_name}: {e}")
            raise

    def get_all_sessions(self, workflow_name: str) -> List[ChatSessionData]:
        """
        Retrieve a list of all chat sessions for a given workflow.

        SRR (Single Responsibility Role): ChatHistoryManager owns chat_history session-files for workflows.

        ORDER (guaranteed by backend):
        1. ACTIVE SESSION (from workflow_sessions.json) - one per workflow, always first
        2. BOOKMARKED SESSIONS (TODO for future implementation)
        3. REMAINING SESSIONS (chronologically sorted, newest first)

        Args:
            workflow_name: The workflow name to get sessions for

        Returns:
            List of ChatSessionData objects with guaranteed ordering
        """
        sessions = []

        # Try primary workflow directory (underscore format)
        workflow_dir = self.storage_path / workflow_name
        if workflow_dir.exists():
            sessions.extend(self._load_sessions_from_directory(workflow_dir, workflow_name))

        # Also try dash variant for compatibility (frontend uses dashes)
        dash_workflow = workflow_name.replace('_', '-')
        dash_workflow_dir = self.storage_path / dash_workflow
        if dash_workflow_dir.exists():
            sessions.extend(self._load_sessions_from_directory(dash_workflow_dir, workflow_name))

        # Remove duplicates if any (same session loaded from multiple locations)
        seen_sessions = set()
        unique_sessions = []
        for session in sessions:
            session_key = (session.session_id, getattr(session, 'workflow_name', 'unknown'))
            if session_key not in seen_sessions:
                seen_sessions.add(session_key)
                unique_sessions.append(session)

        # IMPLEMENT PROPER ORDERING AS PER SRR REQUIREMENTS

        # 1. ACTIVE SESSION FIRST: Check for active session from workflow_sessions.json
        active_session_id = self._get_active_session_id(workflow_name)
        ordered_sessions = []
        remaining_sessions = []

        if active_session_id:
            # Find and move active session to front
            active_session = None
            for session in unique_sessions:
                if session.session_id == active_session_id:
                    active_session = session
                    break

            if active_session:
                ordered_sessions.append(active_session)
                # Remove active session from remaining list
                remaining_sessions = [s for s in unique_sessions if s.session_id != active_session_id]
            else:
                # Active session ID exists but session not found - clean up mapping
                self._cleanup_invalid_active_session(workflow_name, active_session_id)
                remaining_sessions = unique_sessions
        else:
            remaining_sessions = unique_sessions

        # 2. BOOKMARKED SESSIONS: Prioritize bookmarked sessions after active session
        bookmarked_sessions = []
        non_bookmarked_sessions = []

        for session in remaining_sessions:
            metadata = getattr(session, 'metadata', {})
            self.logger.debug(f"[get_all_sessions] Checking session {session.session_id}: metadata={metadata}, type={type(metadata)}")
            is_bookmarked = metadata.get('bookmarked', False) if metadata else False
            self.logger.debug(f"[get_all_sessions] Session {session.session_id} is_bookmarked={is_bookmarked}")
            if is_bookmarked:
                bookmarked_sessions.append(session)
                self.logger.debug(f"[get_all_sessions] Found bookmarked session: {session.session_id}")
            else:
                non_bookmarked_sessions.append(session)

        # Sort bookmarked sessions by recency (newest first)
        bookmarked_sessions.sort(key=lambda s: getattr(s, 'updated_at', datetime.min), reverse=True)

        # Add bookmarked sessions to ordered list
        ordered_sessions.extend(bookmarked_sessions)
        remaining_sessions = non_bookmarked_sessions

        # 3. REMAINING SESSIONS: Sort chronologically (newest first)
        remaining_sessions.sort(key=lambda s: getattr(s, 'updated_at', datetime.min), reverse=True)
        ordered_sessions.extend(remaining_sessions)

        self.logger.debug(f"[get_all_sessions] Returning {len(ordered_sessions)} total sessions for {workflow_name} (active: {active_session_id[:8] if active_session_id else 'none'})")
        return ordered_sessions

    def _get_active_session_id(self, workflow_name: str) -> Optional[str]:
        """
        Get the active session ID for a workflow from workflow_sessions.json.

        SRR: ChatHistoryManager owns the workflow_sessions.json file and active session mappings.

        Args:
            workflow_name: The workflow name

        Returns:
            Active session ID or None if not set
        """
        try:
            # Load workflow_sessions.json file
            mapping_file = self.storage_path / "workflow_sessions.json"

            if not mapping_file.exists():
                return None

            with open(mapping_file, 'r', encoding='utf-8') as f:
                mappings = json.load(f)

            # Return active session for this workflow
            return mappings.get(workflow_name)

        except (json.JSONDecodeError, IOError) as e:
            self.logger.warning(f"Error reading workflow_sessions.json: {e}")
            return None

    def _cleanup_invalid_active_session(self, workflow_name: str, invalid_session_id: str) -> None:
        """
        Remove invalid active session mapping from workflow_sessions.json.

        Args:
            workflow_name: The workflow name
            invalid_session_id: The session ID that no longer exists
        """
        try:
            mapping_file = self.storage_path / "workflow_sessions.json"

            if not mapping_file.exists():
                return

            with open(mapping_file, 'r', encoding='utf-8') as f:
                mappings = json.load(f)

            # Remove the invalid mapping
            if workflow_name in mappings and mappings[workflow_name] == invalid_session_id:
                del mappings[workflow_name]
                self.logger.info(f"Cleaned up invalid active session mapping for {workflow_name}: {invalid_session_id}")

                # Save updated mappings
                with open(mapping_file, 'w', encoding='utf-8') as f:
                    json.dump(mappings, f, indent=2)

        except (json.JSONDecodeError, IOError) as e:
            self.logger.warning(f"Error cleaning up invalid active session mapping: {e}")

    def _load_sessions_from_directory(self, workflow_dir: Path, workflow_id: str) -> List[ChatSessionData]:
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
                    session = self.load_session_from_file(workflow_id, session_id, file_path)
                    if session:
                        sessions.append(session)
                    else:
                        self.logger.warning(f"Could not load session {session_id} from {file_path}")

            except Exception as e:
                self.logger.error(f"Error loading session from {file_path}: {e}")

        return sessions

    def load_session_from_file(self, workflow_id: str, session_id: str, file_path: Path) -> Optional[ChatSessionData]:
        """
        Load a session directly from a known file path.

        Args:
            workflow_id: Expected workflow ID
            session_id: Expected session ID
            file_path: Exact path to the session file

        Returns:
            ChatSessionData object or None if not found/valid
        """
        if not file_path.exists():
            self.logger.debug(f"Session file does not exist: {file_path}")
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if isinstance(data, list):
                # Old format: convert to new format
                session_data = {
                    "session_id": session_id,
                    "user_id": self.user_config.user_id,
                    "workflow_name": workflow_id,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "title": "",
                    "messages": data,
                    "metadata": {}
                }
            elif isinstance(data, dict):
                # New format: ensure all required fields
                # CRITICAL: Use the WORKFLOW_NAME FROM THE FILE, NOT THE PARAMETER!
                # Files may contain "agentic-rag" while backend calls with "agentic_rag"
                session_data = data.copy()
                session_data.setdefault("session_id", session_id)
                # FORCE CURRENT USER ID: Ensures authenticated users take ownership of loaded sessions
                session_data["user_id"] = self.user_config.user_id
                # Use workflow_name from file, or fall back to parameter if missing
                session_data.setdefault("workflow_name", workflow_id)
                session_data.setdefault("title", "")
                session_data.setdefault("messages", [])
                session_data.setdefault("metadata", {})
            else:
                self.logger.error(f"Invalid session data format in {file_path}")
                return None

            # Convert to ChatSessionData object
            session = ChatSessionData.from_dict(session_data)
            return session

        except (json.JSONDecodeError, IOError, KeyError) as e:
            self.logger.error(f"Error loading session {session_id} from {file_path}: {e}")
            return None

    def load_session(self, workflow_id: str, session_id: str) -> Optional[ChatSessionData]:
        """
        Load a specific chat session.

        Args:
            workflow_id: The workflow ID
            session_id: Unique session identifier

        Returns:
            ChatSessionData object or None if not found
        """
        file_path = self._get_history_file_path(workflow_id, session_id)

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
                    "workflow_name": workflow_id,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "title": "",
                    "messages": data,
                    "metadata": {}
                }
            elif isinstance(data, dict):
                # New format: ensure all required fields
                # CRITICAL: Use the WORKFLOW_NAME FROM THE FILE, NOT THE PARAMETER!
                # Files may contain "agentic-rag" while backend calls with "agentic_rag"
                session_data = data.copy()
                session_data.setdefault("session_id", session_id)
                # FORCE CURRENT USER ID: Ensures authenticated users take ownership of loaded sessions
                session_data["user_id"] = self.user_config.user_id
                # Use workflow_name from file, or fall back to parameter if missing
                session_data.setdefault("workflow_name", workflow_id)
                session_data.setdefault("title", "")
                session_data.setdefault("messages", [])
                session_data.setdefault("metadata", {})
            else:
                self.logger.error(f"Invalid session data format in {file_path}")
                return None

            # Convert to ChatSessionData object
            session = ChatSessionData.from_dict(session_data)
            return session

        except (json.JSONDecodeError, IOError, KeyError) as e:
            self.logger.error(f"Error loading session {session_id}: {e}")
            return None

    def get_active_session_data(self) -> 'ChatSessionData':
        """
        Public API to retrieve the ChatSessionData for the current session context.
        Uses SESSION FILE ID DECOUPLING to ensure consistent session data.

        Returns:
            ChatSessionData: The active session data instance.
        """
        if self.my_workflow_id is None:
            raise ValueError("ChatHistoryManager missing workflow_id")
        
        return self._find_or_create_session_data(self.my_workflow_id, self.session_file_id)

    def save_session(self, session: ChatSessionData) -> None:
        """
        Save or update a chat session using SESSION FILE ID DECOUPLING.

        Uses self.session_file_id for file naming instead of session.session_id.
        This enables saving to existing active files instead of creating new ones.

        Args:
            session: ChatSessionData object to save
        """
        # Validate session belongs to current user
        if session.user_id != self.user_config.user_id:
            raise ValueError(f"Session user_id {session.user_id} does not match current user {self.user_config.user_id}")

        # Generate title from first message if not already set
        session.generate_title()

        # Convert to dictionary and save
        session_data = session.to_dict()

        # SESSION FILE ID DECOUPLING: Use session_file_id for file naming
        file_path = self._get_history_file_path(session.workflow_name, self.session_file_id, session, create_dir=True)
        self.logger.debug(f"Save session_data into path {file_path} for workflow {session.workflow_name} using file_id {self.session_file_id} (session_id: {session.session_id})")

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            self.logger.error(f"Error saving session {session.session_id}: {e}")
            raise

    # REMOVED create_new_session - NO LEGACY, NO BACKWARD COMPATIBILITY
    # Use _find_or_create_session_data() instead for internal unified operations

    def delete_session(self, workflow_id: str, session_id: str) -> None:
        """
        Delete a specific chat session with CUDA memory cleanup.

        Args:
            workflow_id: The workflow ID
            session_id: Unique session identifier
        """
        file_path = self._get_history_file_path(workflow_id, session_id)

        if file_path.exists():
            try:
                file_path.unlink()
                self.logger.info(f"Deleted chat session {session_id} for workflow {workflow_id}")

                # CLEANUP: CUDA memory cleanup would be done here if needed
                # Note: Session deletion now handles cleanup through unified WorkflowSession management
                self.logger.debug(f"Session cleanup completed for deleted session {session_id}")

            except IOError as e:
                self.logger.error(f"Error deleting session {session_id}: {e}")
                raise
        else:
            self.logger.warning(f"Session {session_id} not found for deletion")

    # ============================================================================
    # CORRECTED UNIFIED MESSAGE HANDLING APIS (Proper Architecture)
    # ============================================================================
    # - Use session_data for ChatSessionData DTO parameters
    # - Access session_id from self.session_owner (Single Truth principle)
    # - Properly separate ChatSessionData from active WorkflowSession concepts

    def add_message_to_session_data(
        self,
        message: ChatMessageDTO,
        auto_save: bool = True,
        workflow_id: Optional[str] = None
    ) -> None:
        """
        UNIFIED ADD MESSAGE API: Consolidates message addition to ChatSessionData DTO.

        Single entry point for adding any message to session data.
        Handles size limits, title generation, and persistence.
        Uses SESSION FILE ID DECOUPLING: Uses self.session_file_id for active session resumption.

        Args:
            message: Message to add
            auto_save: Whether to persist changes immediately
        """
        # SESSION FILE ID DECOUPLING: Use session_file_id for active session resumption
        target_workflow_id = workflow_id or self.my_workflow_id
        if target_workflow_id == "unknown":
             self.logger.warning("ChatHistoryManager: Saving message to 'unknown' workflow folder - session_owner may not be updated")

        session_data = self._find_or_create_session_data(target_workflow_id, self.session_file_id)

        # Relaxed deduplication: Only skip if the VERY LAST message is the same (role and content)
        # Allows repeated queries while preventing accidental double-submits
        if session_data.messages:
            last_msg = session_data.messages[-1]
            if last_msg.role == message.role and last_msg.content == message.content:
                self.logger.debug(f"Skipping identical back-to-back duplicate message: {message.role}")
                return

        # Apply message size limits
        if len(session_data.messages) >= self.chat_history_config.chat_history_max_size:
            remove_count = len(session_data.messages) - self.chat_history_config.chat_history_max_size + 1
            session_data.messages = session_data.messages[remove_count:]

        session_data.add_message(message)

        # Update title if first user message
        if not session_data.title and message.role == MessageRole.USER:
            session_data.generate_title()

        if auto_save:
            self.save_session(session_data)

    def add_artifacts_to_session_data(
        self,
        session_data: ChatSessionData,
        response_content: str = "",
        artifacts: Optional[List[Dict[str, Any]]] = None,
        workflow_config: Optional[Any] = None,
        enhanced_metadata: Optional[Dict[str, Any]] = None,
        auto_save: bool = True
    ) -> None:
        """
        UNIFIED ADD ARTIFACTS API: Add assistant message with artifacts to session data.

        Handles synthetic response generation for artifact-focused workflows.

        Args:
            session_data: ChatSessionData DTO to update
            response_content: Conversational response text
            artifacts: Generated artifacts
            workflow_config: For synthetic response templates
            enhanced_metadata: Rich metadata (citations, tool calls)
            auto_save: Whether to persist immediately
        """
        # Generate synthetic content if needed
        if not response_content and artifacts and workflow_config:
            response_content = self._generate_synthetic_response_for_artifacts(artifacts, workflow_config)

        if not response_content:
            response_content = f"Generated {len(artifacts or [])} artifacts"

        # FIX: Create assistant message with artifacts in metadata (ChatMessageDTO doesn't have artifacts parameter)
        if enhanced_metadata is None:
            enhanced_metadata = {}

        # Add artifacts to enhanced_metadata for proper storage
        if artifacts:
            enhanced_metadata['artifacts'] = artifacts

        assistant_msg = create_chat_message(
            role=MessageRole.ASSISTANT,
            content=response_content,
            enhanced_metadata=enhanced_metadata
        )

        session_data.add_message(assistant_msg)
        if auto_save:
            self.save_session(session_data)

    def save_workflow_conversation_turn(
        self,
        workflow_id: str,
        session_id: str,
        user_message: str,
        ai_response: str,
        artifacts: Optional[List[Dict[str, Any]]] = None,
        workflow_config: Optional[Any] = None,
        enhanced_metadata: Optional[Dict[str, Any]] = None
    ) -> ChatSessionData:
        """
        UNIFIED SAVE CONVERSATION API: Complete user-AI interaction (one conversation turn).

        Consolidates workflow message saving operations.
        Uses SESSION FILE ID DECOUPLING: Saves to self.session_file_id instead of session_id.

        Args:
            workflow_id: Workflow identifier
            session_id: Session identifier (for logging, file operations use self.session_file_id)
            user_message: User's input
            ai_response: AI response content
            artifacts: Generated artifacts
            workflow_config: Workflow configuration
            enhanced_metadata: Rich AI response metadata

        Returns:
            Updated ChatSessionData
        """
        # SESSION FILE ID DECOUPLING: Use session_file_id for file operations
        session_data = self._find_or_create_session_data(workflow_id, self.session_file_id)

        # Relaxed deduplication: Only skip if the VERY LAST message is the same user query
        # Allows repeated queries while preventing accidental double-submits
        is_duplicate = False
        if session_data.messages:
            last_msg = session_data.messages[-1]
            if last_msg.role == MessageRole.USER and last_msg.content == user_message:
                is_duplicate = True

        if not is_duplicate:
            self.logger.debug(f"[save_workflow_conversation_turn] Adding new user message")
            user_msg = create_chat_message(role=MessageRole.USER, content=user_message)
            session_data.add_message(user_msg)
        else:
            self.logger.debug(f"[save_workflow_conversation_turn] Skipping back-to-back duplicate user message")

        # Add AI response with artifacts (no auto-save)
        self.add_artifacts_to_session_data(
            session_data=session_data,
            response_content=ai_response,
            artifacts=artifacts,
            workflow_config=workflow_config,
            enhanced_metadata=enhanced_metadata,
            auto_save=False
        )

        # Single save operation
        self.save_session(session_data)

        artifact_count = len(artifacts) if artifacts else 0
        self.logger.info(f"Saved conversation turn to workflow {workflow_id} of session {session_id} ({artifact_count} artifacts)")

        return session_data

    # ============================================================================

    def _find_or_create_session_data(self, workflow_id: str, session_id: str) -> 'ChatSessionData':
        """
        SINGLE RESPONSIBILITY: ChatHistoryManager owns ChatSessionData lifecycle.

        Find existing session or create new one. This is the ONLY place
        where ChatSessionData instances should be created/retrieved.

        SESSION CONTENT PRESERVATION: Always try to load from file first to preserve existing content,
        especially critical for active session resumption.

        Args:
            workflow_id: Workflow identifier
            session_id: Session identifier

        Returns:
            ChatSessionData: Always returns a valid ChatSessionData instance
        """
        # SESSION CONTENT PRESERVATION: ALWAYS try to load from file first
        # For session resumption, we need to look for files with session_file_id, not session_id
        search_session_id = self.session_file_id if session_id == self.session_file_id else session_id
        file_path = self._get_history_file_path(workflow_id, search_session_id)

        if file_path.exists():
            existing_session = self.load_session_from_file(workflow_id, search_session_id, file_path)
            if existing_session:
                # FORCE WORKFLOW CONSISTENCY: Ensure loaded session matches the folder tree it came from
                # This prevents "workflow drift" if a file was previously saved with a wrong internal name
                if existing_session.workflow_name != workflow_id:
                    self.logger.debug(f"Correcting workflow_name in loaded session: {existing_session.workflow_name} -> {workflow_id}")
                    existing_session.workflow_name = workflow_id
                return existing_session
            else:
                self.logger.warning(f"FILE EXISTS but failed to load session {search_session_id} from {file_path}")

        # FALLBACK: Check if session exists in loaded sessions (for edge cases)
        all_sessions = self.get_all_sessions(workflow_id)
        existing_session = next((s for s in all_sessions if s.session_id == session_id), None)

        if existing_session:
            return existing_session  # Found existing

        # Create new session - ChatHistoryManager RESPONSIBLE for this
        new_session = create_chat_session_data(
            user_id=self.user_config.user_id,
            workflow_name=workflow_id,
            session_id=session_id
        )
        return new_session

    def _generate_synthetic_response_for_artifacts(
        self,
        artifacts: List[Dict[str, Any]],
        workflow_config: Optional['WorkflowConfig'] = None
    ) -> str:
        """
        Generate synthetic response text for artifact-focused workflows.

        Uses configured templates from WorkflowConfig for personalized responses.
        Falls back to generic artifact-based responses.

        Args:
            artifacts: List of artifacts generated by the workflow
            workflow_config: Optional WorkflowConfig with synthetic_response template

        Returns:
            Synthetic response text describing the artifacts
        """
        if not artifacts:
            return "Processing complete."

        artifact_count = len(artifacts)

        # Use configured synthetic response template if available
        if workflow_config and workflow_config.synthetic_response:
            try:
                # Template substitution {count} -> artifact count
                template = workflow_config.synthetic_response
                return template.format(count=artifact_count)
            except (KeyError, ValueError) as e:
                self.logger.warning(f"Failed to use synthetic response template '{workflow_config.synthetic_response}': {e}")
                # Fall through to generic generation

        # Generic generation based on artifact types
        artifact_types = [art.get('type', 'item') for art in artifacts]
        unique_types = list(set(artifact_types))

        # Map common artifact types to user-friendly descriptions
        type_descriptions = {
            'code': 'code files',
            'document': 'documents',
            'report': 'reports',
            'data': 'data outputs',
            'analysis': 'analysis results',
            'summary': 'summaries',
            'chart': 'charts',
            'graph': 'graphs',
            'table': 'tables',
            'file': 'files'
        }

        # Convert artifact types to descriptions, fallback to type name
        descriptions = [type_descriptions.get(t.lower(), f"{t}s") for t in unique_types]

        # Handle single vs multiple artifacts
        if artifact_count == 1:
            description = descriptions[0].rstrip('s')  # Remove plural for single
            return f"Generated {description}"
        else:
            if len(descriptions) == 1:
                return f"Generated {artifact_count} {descriptions[0]}"
            else:
                return f"Generated {artifact_count} outputs: {', '.join(descriptions)}"

    def get_llama_index_memory(self, session: ChatSessionData) -> Optional[Any]:
        """
        Convert ChatSessionData messages into a LlamaIndex ChatMemoryBuffer.

        Args:
            session: ChatSessionData object to convert

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

    def get_session_stats(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get statistics about chat sessions for a workflow.

        Args:
            workflow_id: The workflow ID to get stats for

        Returns:
            Dictionary with session statistics
        """
        sessions = self.get_all_sessions(workflow_id)

        if not sessions:
            return {
                "total_sessions": 0,
                "total_messages": 0,
                "oldest_session": None,
                "newest_session": None
            }

        total_messages = sum(len(session.messages) for session in sessions)

        # Handle datetime objects and strings safely
        def get_created_at(session):
            created_at = getattr(session, 'created_at', None)
            if isinstance(created_at, str):
                try:
                    return datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                except:
                    return datetime.min
            elif isinstance(created_at, datetime):
                return created_at
            else:
                return datetime.min

        def get_updated_at(session):
            updated_at = getattr(session, 'updated_at', None)
            if isinstance(updated_at, str):
                try:
                    return datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                except:
                    return datetime.min
            elif isinstance(updated_at, datetime):
                return updated_at
            else:
                return datetime.min

        oldest_session = min(sessions, key=get_created_at)
        newest_session = max(sessions, key=get_updated_at)

        # Safely format dates for JSON response
        def format_datetime(dt):
            if isinstance(dt, datetime):
                return dt.isoformat()
            elif isinstance(dt, str):
                return dt
            else:
                return None

        return {
            "total_sessions": len(sessions),
            "total_messages": total_messages,
            "oldest_session": format_datetime(getattr(oldest_session, 'created_at', None)),
            "newest_session": format_datetime(getattr(newest_session, 'updated_at', None))
        }

    # ============================================================================
    # UNIFIED UTILITY METHODS FOR ENDPOINT CONSISTENCY
    # ============================================================================

    def get_sessions_for_ui_listing(self, workflow_id: str) -> Dict[str, Any]:
        """
        UNIFIED: Get session METADATA for UI listing (Stage 1: session list view).

        Returns ONLY session metadata - NO message content.
        Used by History UI to display session list when workflow tab is clicked.

        Args:
            workflow_id: Workflow identifier

        Returns:
            Session metadata list: session_id, title, timestamps, message_count, etc.
        """
        all_sessions = self.get_all_sessions(workflow_id)

        sessions_data = []

        for session in all_sessions:
            # Format consistent with endpoint requirements
            updated_at_datetime = session.updated_at if hasattr(session, 'updated_at') and session.updated_at else session.created_at

            # SESSION METADATA ONLY - No messages, no previews
            # session.title is now the user-editable friendly name
            session_dict = {
                "session_id": session.session_id,
                "title": session.title or f"Chat {session.session_id[:8]}",  # ✅ TITLE IS NOW THE FRIENDLY NAME
                "created_at": session.created_at.isoformat() if hasattr(session.created_at, 'isoformat') else str(session.created_at),
                "updated_at": updated_at_datetime.isoformat() if hasattr(updated_at_datetime, 'isoformat') else str(updated_at_datetime),
                "message_count": len(session.messages) if session.messages else 0,
                "workflow_name": session.workflow_name,
                "metadata": getattr(session, 'metadata', {})  # ✅ INCLUDE METADATA
                # NOTE: No message previews - History UI generates these client-side
            }
            sessions_data.append(session_dict)

        # Sessions are already ordered by priority in get_all_sessions()
        # ACTIVE FIRST → BOOKMARKED → REGULAR, each group sorted by recency
        # No additional sorting needed here

        return {
            "workflow": workflow_id,
            "sessions": sessions_data
        }

    def get_messages_for_ui_listing(self, workflow_id: str, chat_sess_id: str) -> Optional[Dict[str, Any]]:
        """
        Get messages for specific chat session (Stage 2: individual session view).

        Called when user clicks on session item to view messages.
        Returns complete session data with messages and artifacts for that chat session.

        Args:
            workflow_id: Workflow identifier (for consistency with other methods)
            chat_sess_id: Specific chat session ID to load messages for

        Returns:
            Complete chat session data with messages and artifacts, or None if not found
        """
        chat_session = self.load_session(workflow_id, chat_sess_id)
        if not chat_session:
            return None

        # Return complete session data with messages and artifacts
        return self.format_session_with_artifacts(chat_session, include_artifacts=True)

    def format_session_with_artifacts(self, session: ChatSessionData, include_artifacts: bool = True) -> Dict[str, Any]:
        """
        UNIFIED: Format complete session data with artifacts for detail views.

        Ensures consistent artifact loading and session formatting across endpoints.
        Used by both workflow and history endpoints for session detail views.

        Args:
            session: ChatSessionData object to format
            include_artifacts: Whether to load and include artifacts

        Returns:
            Complete session data dictionary
        """
        # Base session data
        session_data = session.to_dict()

        if include_artifacts:
            # Use existing artifact loading utility (consistent across endpoints)
            from super_starter_suite.chat_bot.chat_history.data_crud_endpoint import load_artifacts_for_session
            artifacts = load_artifacts_for_session(session.session_id, self, session.workflow_name)

            # Filter artifacts by message_id for proper association
            # This ensures artifacts are correctly linked to their source messages
            session_data["artifacts"] = artifacts
        else:
            session_data["artifacts"] = []

        return session_data
