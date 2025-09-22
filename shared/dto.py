"""
Data Transfer Objects for MVC Pattern Implementation

This module contains encapsulated data objects that carry similar/same structure
data across MVC boundaries, with essential properties (always carried) and
meta-properties (internal control). Only essential changes are visible at control points.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union
from enum import Enum
import uuid
import json
import os
from pathlib import Path

# Import for filesystem operations
from super_starter_suite.shared.index_utils import calculate_storage_hash
from super_starter_suite.shared.config_manager import config_manager

# Get logger for StatusData operations
logger = config_manager.get_logger("dto")


class GenerationState(Enum):
    """Enumeration for generation states"""
    READY = "ST_READY"
    PARSER = "ST_PARSER"
    GENERATION = "ST_GENERATION"
    COMPLETED = "ST_COMPLETED"
    ERROR = "ST_ERROR"


@dataclass
class ProgressData:
    """
    Encapsulated progress data across MVC boundaries.

    Essential properties are always carried across boundaries.
    Meta-properties provide internal control and are not carried.
    """

    # Essential Properties (Always Carried Across Boundaries)
    type: str = "progress_update"
    state: GenerationState = GenerationState.READY
    progress: int = 0
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Essential Context Properties
    task_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    rag_type: str = "RAG"

    # Meta-Properties (Internal Control - Not Carried Across Boundaries)
    _source: str = "model"        # "model", "controller", "view"
    _validated: bool = False      # Has data been validated?
    _transformed: bool = False    # Has data been transformed by controller?
    _rendered: bool = False       # Has data been rendered by view?
    _from_cache: bool = False     # Was data loaded from cache?

    def validate(self) -> bool:
        """Control Point: Validate data before processing"""
        if 0 <= self.progress <= 100 and isinstance(self.state, GenerationState):
            self._validated = True
            return True
        return False

    def mark_transformed(self) -> None:
        """Control Point: Mark data as transformed by controller"""
        self._transformed = True
        self._source = "controller"

    def mark_rendered(self) -> None:
        """Control Point: Mark data as rendered by view"""
        self._rendered = True
        self._source = "view"

    def update_progress(self, new_progress: int, new_message: str) -> bool:
        """Control Point: Update progress (only if validated)"""
        if self._validated and 0 <= new_progress <= 100:
            self.progress = new_progress
            self.message = new_message
            self._rendered = False  # Mark for re-render
            self.timestamp = datetime.now()  # Update timestamp
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization (essential properties only)"""
        return {
            "type": self.type,
            "state": self.state.value,
            "progress": self.progress,
            "message": self.message,
            "metadata": self.metadata,
            "task_id": self.task_id,
            "timestamp": self.timestamp.isoformat(),
            "rag_type": self.rag_type,
            # Include meta-properties for debugging (but mark as internal)
            "_source": self._source,
            "_validated": self._validated,
            "_transformed": self._transformed,
            "_rendered": self._rendered
        }


@dataclass
class StatusData:
    """
    Encapsulated status data with caching metadata.

    Essential properties are always carried across boundaries.
    Meta-properties provide internal control and cache awareness.
    """

    # Essential Properties (Always Carried Across Boundaries)
    data_newest_time: Optional[str] = None
    data_newest_file: Optional[str] = None
    total_files: int = 0
    total_size: int = 0
    data_files: List[Dict[str, Any]] = field(default_factory=list)
    has_newer_files: bool = False

    # Essential Context Properties
    rag_type: str = "RAG"
    meta_last_update: datetime = field(default_factory=datetime.now)

    # Storage Status Properties
    storage_creation: Optional[str] = None
    storage_files_count: int = 0
    storage_hash: Optional[str] = None
    storage_status: str = "empty"  # "healthy", "empty", "corrupted"

    # Meta-Properties (Internal Control - Not Carried Across Boundaries)
    _from_cache: bool = False
    _cache_key: Optional[str] = None
    _stale_threshold: timedelta = field(default_factory=lambda: timedelta(minutes=5))
    _source: str = "model"
    _validated: bool = False

    def is_stale(self) -> bool:
        """Control Point: Check if data is stale"""
        return datetime.now() - self.meta_last_update > self._stale_threshold

    def should_refresh(self) -> bool:
        """Control Point: Determine if data needs refresh"""
        return self.is_stale() or not self._from_cache

    def mark_from_cache(self, cache_key: str) -> None:
        """Control Point: Mark data as loaded from cache"""
        self._from_cache = True
        self._cache_key = cache_key
        self._source = "cache"

    def validate(self) -> bool:
        """Control Point: Validate data integrity"""
        if self.total_files >= 0 and self.total_size >= 0:
            self._validated = True
            return True
        return False

    def update_storage_status(self, storage_info: Dict[str, Any]) -> bool:
        """Control Point: Update storage status information"""
        if not self._validated:
            return False

        self.storage_creation = storage_info.get("last_modified")
        self.storage_files_count = len(storage_info.get("storage_files", []))
        self.storage_hash = storage_info.get("hash")

        # Determine storage status
        if self.storage_files_count == 0:
            self.storage_status = "empty"
        elif storage_info.get("is_corrupted", False):
            self.storage_status = "corrupted"
        else:
            self.storage_status = "healthy"

        self.meta_last_update = datetime.now()
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization (essential properties only)"""
        return {
            "data_newest_time": self.data_newest_time,
            "data_newest_file": self.data_newest_file,
            "total_files": self.total_files,
            "total_size": self.total_size,
            "data_files": self.data_files,
            "has_newer_files": self.has_newer_files,
            "rag_type": self.rag_type,
            "meta_last_update": self.meta_last_update.isoformat(),
            "storage_creation": self.storage_creation,
            "storage_files_count": self.storage_files_count,
            "storage_hash": self.storage_hash,
            "storage_status": self.storage_status,
            # Include meta-properties for debugging (but mark as internal)
            "_from_cache": self._from_cache,
            "_cache_key": self._cache_key,
            "_source": self._source,
            "_validated": self._validated
        }

    @classmethod
    def load_from_file(cls, user_config, rag_type: str) -> 'StatusData': # Changed return type to always be StatusData
        """
        BRIDGE METHOD: Load StatusData by delegating to shared/index_utils.py

        Following architectural guidelines:
        - shared/index_utils.py: Single responsibility for METADATA file operations
        - shared/dto.py: Bridge role, data format conversion, NO direct file operations
        - shared/dto.py: Responsible for data format conversion (Dict ↔ List, timestamp formats)

        Args:
            user_config: User's configuration containing RAG paths
            rag_type: The RAG type to load metadata for

        Returns:
            StatusData: Validated StatusData object. Returns an empty StatusData
                        if loading fails or data is inconsistent.
        """
        metadata_dict: Optional[Dict[str, Any]] = None
        try:
            # BRIDGE: Delegate to shared/index_utils.py for file operations and consistency validation
            from super_starter_suite.shared.index_utils import load_data_metadata

            logger.debug(f"load_from_file:: Delegating to load_data_metadata() for RAG type '{rag_type}'")

            # Call shared/index_utils.py with filesystem consistency validation
            metadata_dict = load_data_metadata(user_config, rag_type=rag_type)

            # If None returned, metadata is inconsistent and auto-regeneration failed
            if metadata_dict is None:
                logger.warning(f"load_from_file:: Metadata inconsistency detected for RAG type '{rag_type}' - auto-regeneration failed or not possible. Returning empty StatusData.")
                # Fallback to an empty StatusData instance
                return cls(rag_type=rag_type, meta_last_update=datetime.now(), storage_status="empty")

            # DATA FORMAT CONVERSION: Convert from index_utils format to StatusData format
            # shared/index_utils.py returns files as dict (for existing compatibility)
            # StatusData expects files as list (for frontend consumption)

            # Convert data_files dict to list format
            files_list = []
            files_dict = metadata_dict.get('data_files', {})

            if isinstance(files_dict, dict):
                # Convert dict format {"filename": {"size": X, "modified": Y, "hash": Z}}
                # to list format [{"name": "filename", "size": X, "modified": Y, "hash": Z}]
                for filename, file_info in files_dict.items():
                    if isinstance(file_info, dict):
                        files_list.append({
                            "name": filename,
                            "size": file_info.get("size", 0),
                            "modified": file_info.get("modified", ""),
                            "hash": file_info.get("hash", "")
                        })
            elif isinstance(files_dict, list):
                # Already in list format, use as-is
                files_list = files_dict

            # Convert timestamp strings to datetime objects where appropriate
            meta_last_update = metadata_dict.get('meta_last_update')
            if isinstance(meta_last_update, str):
                try:
                    meta_last_update = datetime.fromisoformat(meta_last_update)
                except (ValueError, TypeError):
                    # Invalid timestamp, will use current time
                    meta_last_update = datetime.now()
            elif meta_last_update is None:
                # No timestamp provided, use current time
                meta_last_update = datetime.now()
            # If it's already a datetime object, use it as-is

            # Create StatusData with converted data formats
            status_data = cls(
                # Essential data properties
                data_newest_time=metadata_dict.get('data_newest_time'),
                data_newest_file=metadata_dict.get('data_newest_file'),
                total_files=metadata_dict.get('total_files', 0),
                total_size=metadata_dict.get('total_size', 0),
                data_files=files_list,  # Converted to list format
                has_newer_files=metadata_dict.get('has_newer_files', False),

                # Context properties
                rag_type=metadata_dict.get('rag_type', rag_type),
                meta_last_update=meta_last_update,

                # Storage properties
                storage_creation=metadata_dict.get('rag_storage_creation'),
                storage_files_count=metadata_dict.get('rag_storage_files_count', 0),
                storage_hash=metadata_dict.get('rag_storage_hash'),
                storage_status=metadata_dict.get('rag_storage_status', 'empty')
            )

            # Validate the created StatusData
            if not status_data.validate():
                logger.warning(f"load_from_file:: StatusData validation failed after format conversion for RAG type '{rag_type}'. Returning empty StatusData.")
                # Fallback to an empty StatusData instance
                return cls(rag_type=rag_type, meta_last_update=datetime.now(), storage_status="empty")

            # Mark as loaded from cache/file
            status_data._from_cache = True
            status_data._cache_key = f"{rag_type}_cache"
            status_data._source = "cache"

            logger.debug(f"load_from_file:: Successfully loaded and converted StatusData for RAG type '{rag_type}' with {len(files_list)} files")
            return status_data

        except Exception as e:
            # Log error but don't crash - return an empty StatusData for graceful degradation
            logger.error(f"load_from_file:: Unexpected error in bridge method for RAG type '{rag_type}': {e}. Returning empty StatusData.")
            return cls(rag_type=rag_type, meta_last_update=datetime.now(), storage_status="empty")

    def save_to_file(self, user_config) -> bool:
        """
        BRIDGE METHOD: Save StatusData by delegating to shared/index_utils.py

        Following architectural guidelines:
        - shared/index_utils.py: Single responsibility for METADATA file operations
        - shared/dto.py: Bridge role, data format conversion, NO direct file operations
        - shared/dto.py: Responsible for data format conversion (List ↔ Dict for files)

        Args:
            user_config: User's configuration containing RAG paths

        Returns:
            bool: True if save successful, False otherwise
        """
        try:
            # DATA FORMAT CONVERSION: Convert from StatusData format to index_utils format
            # StatusData stores files as list (for frontend consumption)
            # shared/index_utils.py expects files as dict (for existing compatibility)

            # Convert data_files list to dict format for index_utils compatibility
            files_dict = {}
            for file_info in self.data_files:
                if isinstance(file_info, dict) and "name" in file_info:
                    filename = file_info["name"]
                    files_dict[filename] = {
                        "size": file_info.get("size", 0),
                        "modified": file_info.get("modified", ""),
                        "hash": file_info.get("hash", "")
                    }

            # Create data_info dict in the format expected by save_data_metadata()
            data_info = {
                "total_files": self.total_files,
                "total_size": self.total_size,
                "data_files": [
                    {
                        "name": file_info.get("name", ""),
                        "size": file_info.get("size", 0),
                        "modified": file_info.get("modified", ""),
                        "hash": file_info.get("hash", "")
                    }
                    for file_info in self.data_files
                ]
            }

            # BRIDGE: Delegate to shared/index_utils.py for file operations
            from super_starter_suite.shared.index_utils import save_data_metadata

            logger.debug(f"save_to_file:: Delegating to save_data_metadata() for RAG type '{self.rag_type}'")

            # Call shared/index_utils.py to handle file operations
            success = save_data_metadata(
                user_config=user_config,
                rag_type=self.rag_type,
                data_info=data_info
            )

            if success:
                # Mark as cached after successful save
                self._from_cache = True
                self._cache_key = f"{self.rag_type}_cache"
                self._source = "cache"
                logger.debug(f"save_to_file:: Successfully saved StatusData for RAG type '{self.rag_type}'")
            else:
                logger.error(f"save_to_file:: Failed to save StatusData for RAG type '{self.rag_type}'")

            return success

        except Exception as e:
            logger.error(f"save_to_file:: Unexpected error in bridge method for RAG type '{self.rag_type}': {e}")
            return False

# Global instances for type checking and validation
PROGRESS_DATA_TEMPLATE = ProgressData()
STATUS_DATA_TEMPLATE = StatusData()


def create_progress_data(
    state: GenerationState = GenerationState.READY,
    progress: int = 0,
    message: str = "",
    task_id: Optional[str] = None,
    rag_type: str = "RAG",
    **kwargs
) -> ProgressData:
    """
    Factory function to create validated ProgressData instances.

    Control Point: Ensures all created instances are validated.
    """
    data = ProgressData(
        state=state,
        progress=progress,
        message=message,
        task_id=task_id,
        rag_type=rag_type,
        **kwargs
    )

    # Control Point: Always validate on creation
    if not data.validate():
        raise ValueError(f"Invalid progress data: progress={progress}, state={state}")

    return data


def create_status_data(
    rag_type: str = "RAG",
    data_newest_time: Optional[str] = None,
    total_files: int = 0,
    total_size: int = 0,
    **kwargs
) -> StatusData:
    """
    Factory function to create validated StatusData instances.

    Control Point: Ensures all created instances are validated.
    """
    data = StatusData(
        rag_type=rag_type,
        data_newest_time=data_newest_time,
        total_files=total_files,
        total_size=total_size,
        **kwargs
    )

    # Control Point: Always validate on creation
    if not data.validate():
        raise ValueError(f"Invalid status data: total_files={total_files}, total_size={total_size}")

    return data


# ------------------------------------------------------------------
# Chat History DTOs
# ------------------------------------------------------------------

class MessageRole(Enum):
    """Enumeration for chat message roles"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class ChatMessageDTO:
    """
    Data Transfer Object for individual chat messages.

    This DTO represents a single message in a chat session, designed to work
    across MVC boundaries and support JSON serialization for API responses.
    """
    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "message_id": self.message_id,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChatMessageDTO':
        """Create instance from dictionary"""
        return cls(
            role=MessageRole(data["role"]),
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            message_id=data["message_id"],
            metadata=data.get("metadata", {})
        )


@dataclass
class ChatSession:
    """
    Data Transfer Object for chat sessions.

    Represents a complete chat session with persistent history, supporting
    MVC pattern boundaries and JSON serialization for frontend integration.
    """
    session_id: str
    user_id: str
    workflow_type: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    title: str = ""
    messages: List[ChatMessageDTO] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Meta-properties for internal control
    _validated: bool = False
    _from_cache: bool = False

    def validate(self) -> bool:
        """Control Point: Validate session data"""
        if (self.session_id and self.user_id and self.workflow_type and
            len(self.session_id) > 0 and len(self.user_id) > 0 and len(self.workflow_type) > 0):
            self._validated = True
            return True
        return False

    def add_message(self, message: ChatMessageDTO) -> None:
        """Add a message to the session and update timestamp"""
        self.messages.append(message)
        self.updated_at = datetime.now()

    def get_message_count(self) -> int:
        """Get the number of messages in the session"""
        return len(self.messages)

    def generate_title(self) -> str:
        """Generate a title from the first user message"""
        if not self.title and self.messages:
            # Find the first user message
            for msg in self.messages:
                if msg.role == MessageRole.USER:
                    # Take first 50 characters as title
                    content = msg.content.strip()
                    self.title = content[:50] + "..." if len(content) > 50 else content
                    break
        return self.title

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "workflow_type": self.workflow_type,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "title": self.title,
            "messages": [msg.to_dict() for msg in self.messages],
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChatSession':
        """Create instance from dictionary"""
        return cls(
            session_id=data["session_id"],
            user_id=data["user_id"],
            workflow_type=data["workflow_type"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            title=data.get("title", ""),
            messages=[ChatMessageDTO.from_dict(msg) for msg in data.get("messages", [])],
            metadata=data.get("metadata", {})
        )


@dataclass
class ChatHistoryConfig:
    """
    Configuration for chat history management.

    This Pydantic-style configuration class defines settings for
    chat history persistence and management.
    """
    chat_history_max_size: int = 100  # Maximum messages per session
    chat_history_storage_type: str = "json_file"  # Storage backend type
    chat_history_storage_path: str = "chat_history"  # Relative path for history files

    def validate(self) -> bool:
        """Validate configuration values"""
        return (self.chat_history_max_size > 0 and
                self.chat_history_storage_type in ["json_file", "database", "vector_store"] and
                len(self.chat_history_storage_path) > 0)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "CHAT_HISTORY_MAX_SIZE": self.chat_history_max_size,
            "CHAT_HISTORY_STORAGE_TYPE": self.chat_history_storage_type,
            "CHAT_HISTORY_STORAGE_PATH": self.chat_history_storage_path
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChatHistoryConfig':
        """Create instance from dictionary"""
        return cls(
            chat_history_max_size=data.get("CHAT_HISTORY_MAX_SIZE", 100),
            chat_history_storage_type=data.get("CHAT_HISTORY_STORAGE_TYPE", "json_file"),
            chat_history_storage_path=data.get("CHAT_HISTORY_STORAGE_PATH", "chat_history")
        )


# Factory functions for chat history DTOs
def create_chat_session(
    user_id: str,
    workflow_type: str,
    session_id: Optional[str] = None,
    title: str = "",
    **kwargs
) -> ChatSession:
    """
    Factory function to create validated ChatSession instances.
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    session = ChatSession(
        session_id=session_id,
        user_id=user_id,
        workflow_type=workflow_type,
        title=title,
        **kwargs
    )

    # Control Point: Always validate on creation
    if not session.validate():
        raise ValueError(f"Invalid chat session: user_id={user_id}, workflow_type={workflow_type}")

    return session


def create_chat_message(
    role: MessageRole,
    content: str,
    **kwargs
) -> ChatMessageDTO:
    """
    Factory function to create validated ChatMessageDTO instances.
    """
    message = ChatMessageDTO(
        role=role,
        content=content,
        **kwargs
    )

    # Basic validation
    if not content.strip():
        raise ValueError("Message content cannot be empty")

    return message


# Global instances for type checking
CHAT_SESSION_TEMPLATE = ChatSession(
    session_id="template",
    user_id="template",
    workflow_type="template"
)
CHAT_MESSAGE_TEMPLATE = ChatMessageDTO(
    role=MessageRole.USER,
    content="template message"
)
