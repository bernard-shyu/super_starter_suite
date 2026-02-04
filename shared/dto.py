"""
Data Transfer Objects for MVC Pattern Implementation

This module contains encapsulated data objects that carry similar/same structure
data across MVC boundaries, with essential properties (always carried) and
meta-properties (internal control). Only essential changes are visible at control points.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union, Callable
from enum import Enum
import uuid
import json
import os
from pathlib import Path

from super_starter_suite.shared.config_manager import config_manager

# Get logger for StatusData operations
logger = config_manager.get_logger("dto")

# Import LlamaIndex types for ExecutionContext
from llama_index.server.api.models import ChatRequest


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
        from super_starter_suite.shared.index_utils import calculate_storage_hash

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

# ------------------------------------------------------------------
# CLEAN CITATION SYSTEM DTOs - Structured Data Flow
# ------------------------------------------------------------------

@dataclass
class MessageMetadata:
    """
    Clean metadata container for human-readable content separation.

    Defines clean boundaries between human-visible content and machine metadata.
    """
    citations: List[str] = field(default_factory=list)            # Clean citation markers: ["[citation:uuid]"]
    citation_metadata: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # Metadata for each citation UUID
    tool_calls: List[str] = field(default_factory=list)         # Tool names: ["query_index"]
    followup_questions: List[str] = field(default_factory=list) # Follow-up questions: ["What are trends?"]
    model_provider: str = ""                                    # Model provider
    model_id: str = ""                                          # Model ID

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "citations": self.citations,
            "citation_metadata": self.citation_metadata,
            "tool_calls": self.tool_calls,
            "followup_questions": self.followup_questions,
            "model_provider": self.model_provider,
            "model_id": self.model_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MessageMetadata':
        """Create from dictionary"""
        return cls(
            citations=data.get("citations", []),
            citation_metadata=data.get("citation_metadata", {}),
            tool_calls=data.get("tool_calls", []),
            followup_questions=data.get("followup_questions", []),
            model_provider=data.get("model_provider", ""),
            model_id=data.get("model_id", "")
        )


@dataclass
class StructuredMessage:
    """
    CLEAN DATA FLOW: Structured message with separation of concerns.

    Following clean architecture:
    - Raw Data Stage: Pure LlamaIndex response (separate concerns)
    - Structured Data Stage: This object with clean human content + metadata
    - Human Rendering Stage: Standard markdown processing of content field
    - History Persistence Stage: This object preserved for re-rendering

    Fields clearly define the stage boundaries:
    - content: Ready for human rendering (markdown-ready text)
    - metadata: Machine-friendly structure for enhanced UI
    """
    content: str                    # Human-readable text (ready for standard markdown processing)
    metadata: MessageMetadata      # Clean metadata (citations, tools, questions)
    workflow_name: str             # Context for rendering

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "content": self.content,
            "metadata": self.metadata.to_dict(),
            "workflow_name": self.workflow_name
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StructuredMessage':
        """Create from dictionary"""
        return cls(
            content=data["content"],
            metadata=MessageMetadata.from_dict(data.get("metadata", {})),
            workflow_name=data.get("workflow_name", "")
        )

    def has_enhanced_data(self) -> bool:
        """Check if message has any enhanced UI elements"""
        return (
            len(self.metadata.citations) > 0 or
            len(self.metadata.tool_calls) > 0 or
            len(self.metadata.followup_questions) > 0
        )


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

    ENHANCED: Separate rich text metadata from main content for clean UI separation.

    This DTO represents a single message in a chat session, designed to work
    across MVC boundaries and support JSON serialization for API responses.

    PHASE 5.8+: Enhanced with separate metadata to support rich text rendering
    where tool calls, citations, and questions are rendered in separate UI panels.
    """
    role: MessageRole
    content: str  # MAIN CONTENT ONLY - no embedded metadata
    timestamp: datetime = field(default_factory=datetime.now)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # ENHANCED for rich text rendering (separate from main content)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # PHASE 5.8+: Dedicated fields for workflow-enhanced metadata
    enhanced_metadata: Dict[str, Any] = field(default_factory=dict)  # {
    #     "tool_calls": ["query_index", "search_tool"],
    #     "citations": ["[citation:1]", "[source.pdf]"],
    #     "followup_questions": ["What are the trends?", "How do metrics compare?"]
    # }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "role": self.role.value,
            "content": self.content,  # Main content stays clean
            "timestamp": self.timestamp.isoformat(),
            "message_id": self.message_id,
            "metadata": self.metadata,  # Existing workflows use this
            "enhanced_metadata": self.enhanced_metadata  # Rich text workflows use this
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChatMessageDTO':
        """Create instance from dictionary"""
        return cls(
            role=MessageRole(data["role"]),
            content=data["content"],  # Main content stays clean
            timestamp=datetime.fromisoformat(data["timestamp"]),
            message_id=data["message_id"],
            metadata=data.get("metadata", {}),  # Existing workflows
            enhanced_metadata=data.get("enhanced_metadata", {})  # Rich text workflows
        )

    def has_enhanced_data(self) -> bool:
        """Check if message contains enhanced rich text metadata"""
        enhanced = self.enhanced_metadata
        return (
            enhanced.get("tool_calls", 0) > 0 or
            enhanced.get("citations", 0) > 0 or
            enhanced.get("followup_questions", 0) > 0
        )


@dataclass
class ChatSessionData:
    """
    Data Transfer Object for chat session data structures.

    Pure DTO containing chat message data structures and metadata.
    Used for persistent chat history storage and serialization.
    Separated from session management logic (ChatBotSession, WorkflowSession).
    """
    session_id: str
    user_id: str
    workflow_name: str  # Workflow identifier (e.g., "A_agentic_rag")
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
        if (self.session_id and self.user_id and self.workflow_name and
            len(self.session_id) > 0 and len(self.user_id) > 0 and len(self.workflow_name) > 0):
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
            "workflow_name": self.workflow_name,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "title": self.title,
            "messages": [msg.to_dict() for msg in self.messages],
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChatSessionData':
        """Create instance from dictionary"""
        return cls(
            session_id=data["session_id"],
            user_id=data["user_id"],
            workflow_name=data["workflow_name"],  # Must use correct field name
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
def create_chat_session_data(
    user_id: str,
    workflow_name: str,
    session_id: Optional[str] = None,
    title: str = "",
    **kwargs
) -> ChatSessionData:
    """
    Factory function to create validated ChatSessionData instances.
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    session = ChatSessionData(
        session_id=session_id,
        user_id=user_id,
        workflow_name=workflow_name,
        title=title,
        **kwargs
    )

    # Control Point: Always validate on creation
    if not session.validate():
        raise ValueError(f"Invalid chat session data: user_id={user_id}, workflow_name={workflow_name}")

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
CHAT_SESSION_TEMPLATE = ChatSessionData(
    session_id="template",
    user_id="template",
    workflow_name="template"
)
CHAT_MESSAGE_TEMPLATE = ChatMessageDTO(
    role=MessageRole.USER,
    content="template message"
)

# ------------------------------------------------------------------
# Workflow Management DTOs
# ------------------------------------------------------------------

@dataclass
class WorkflowConfig:
    """
    🎯 UNIFIED WORKFLOW CONFIGURATION - All properties inlined, no reference sections.

    Eliminates fragmented config architecture:
    - [WF_UI_PATTERN], [WF_ENHANCED_RENDERING], [WF_PROGRESSIVE_STATES] consolidated
    - Direct property access without reference lookups
    - Complete workflow config object from get_workflow_config()

    Encapsulates the complete metadata and settings required for a pluggable workflow,
    supporting dynamic loading and registration across the system.

    Derived Properties (computed from code_path):
    - workflow_code: "code_generator" from "workflow_adapters.code_generator"
    - workflow_hyphenated: "code-generator" from workflow_code
    - workflow_ID: Expected workflow ID pattern (must be defined in workflow files)
    """
    # 🎯 CORE WORKFLOW PROPERTIES
    code_path: str          # Python import path (e.g., "workflow_adapters.agentic_rag")
    timeout: float         # Execution timeout in seconds
    display_name: str      # User-friendly name for UI display
    description: Optional[str] = None  # Optional description for the workflow
    icon: Optional[str] = None  # Optional emoji or icon for UI display

    # 🎯 INTEGRATION TYPE PROPERTIES
    integrate_type: Optional[str] = "adapted"      # "adapted", "ported", "meta"
    response_format: Optional[str] = "json"        # "json", "html"

    # 🎯 ARTIFACT CONFIGURATION
    artifact_enabled: Optional[bool] = False       # True to enable artifact extraction
    artifacts_enabled: Optional[bool] = False      # Unified flag for artifacts rendering
    synthetic_response: Optional[str] = None       # Template for synthetic responses from artifacts

    # 🎯 SESSION MANAGEMENT
    chat_history_context: Optional[bool] = True    # True to maintain conversation history

    # 🎯 WORKFLOW IDENTIFICATION (from config key)
    workflow_ID: Optional[str] = None  # Raw workflow ID key from TOML config (e.g., "A_agentic_rag")

    # 🎯 UNIFIED UI CONFIGURATION (formerly separate sections)
    ui_component: Optional[str] = None            # "SimpleWorkflowProgress" or "MultiStageWorkflowProgress"

    # 🎯 UNIFIED RENDERING FLAGS (formerly enhanced_rendering section)
    show_tool_calls: Optional[bool] = False       # Show tool calls in UI
    show_citation: Optional[str] = "None"         # Show citation sources: "Full", "Short", "None"
    show_followup_questions: Optional[bool] = False  # Show AI follow-up questions
    show_workflow_states: Optional[bool] = False  # Show workflow state progression

    # 🎯 LLM BEHAVIOR FLAGS
    force_text_structured_predict: Optional[bool] = False # Force text-based structured prediction (Solution F)

    # 🎯 CLI WORKFLOW FEATURES
    hie_enabled: Optional[bool] = False           # Enable CLI command execution with human oversight

    # 🎯 USER DATA DIRECTORY - Workflow-specific working directory
    user_data_path: Optional[str] = None          # Calculated user data path from USER_RAG_ROOT/workflow_data

    # 🎯 DYNAMIC WORKFLOW MODULE LOADING - Lazy-loaded properties
    _workflow_module: Optional[Any] = None  # Cache for imported workflow module
    _workflow_factory: Optional[Callable[[], Any]] = None  # Cache for workflow factory function

    @property
    def workflow_code(self) -> str:
        """Derived: Get workflow code from code_path (e.g., 'code_generator' from 'workflow_adapters.code_generator')"""
        # Extract the last part after the last dot
        return self.code_path.split('.')[-1] if '.' in self.code_path else self.code_path

    def set_user_data_path(self, user_config) -> None:
        """
        Initialize user_data_path using user configuration.
        Must be called when user context is available.

        Args:
            user_config: User configuration with RAG root paths
        """
        if self.user_data_path is not None:
            return  # Already initialized

        # Calculate workflow data path from USER_RAG_ROOT + workflow_data
        user_rag_root = user_config.my_rag_root
        workflow_data_path = os.path.join(user_rag_root, "workflow_data")

        # Ensure directory exists
        os.makedirs(workflow_data_path, exist_ok=True)
        logger.debug(f"WorkflowConfig: Initialized user_data_path to {workflow_data_path}")

        self.user_data_path = workflow_data_path

    @property
    def workflow_factory(self) -> Optional[Callable[[], Any]]:
        """
        🎯 DYNAMIC WORKFLOW FACTORY: Lazy-loaded property that unifies all workflow module imports.

        Unifies the scattered workflow module import patterns across the codebase:
        - STARTER_TOOLS integrated workflows (adapted)
        - Ported workflow implementations
        - Future meta-workflow orchestrations

        Lazy-loading pattern ensures modules are imported only when needed,
        and cached for subsequent accesses.

        Returns:
            Factory function () -> workflow_instance

        Raises:
            ImportError: If module cannot be imported
            AttributeError: If required function not found
        """
        # 🚀 CHECK CACHE: Return cached factory if already loaded
        if self._workflow_factory is not None:
            return self._workflow_factory

        # 🎯 LAZY IMPORT: Import workflow module based on integration type
        try:
            if self.integrate_type == "adapted":
                # ⭐ ADAPTED: Import from STARTER_TOOLS.{workflow_code}.app.workflow
                import importlib
                starer_tools_path = f"STARTER_TOOLS.{self.workflow_code}.app.workflow"
                self._workflow_module = importlib.import_module(starer_tools_path)
                create_func = getattr(self._workflow_module, 'create_workflow')

            elif self.integrate_type == "ported":
                # 🔄 PORTED: Import from workflow_porting.{workflow_code}
                import importlib
                porting_path = f"super_starter_suite.workflow_porting.{self.workflow_code}"
                self._workflow_module = importlib.import_module(porting_path)
                # Direct approach: use create_workflow function directly
                create_func = getattr(self._workflow_module, 'create_workflow')

            elif self.integrate_type == "meta":
                # 🎭 META: Multi-agent orchestration workflows from workflow_meta
                import importlib
                # Use code_path which points to 'workflow_meta.multi_agent'
                meta_path = f"super_starter_suite.{self.code_path}"
                self._workflow_module = importlib.import_module(meta_path)
                # Look for create_workflow function
                if hasattr(self._workflow_module, 'create_workflow'):
                    create_func = getattr(self._workflow_module, 'create_workflow')
                else:
                    # Fallback for meta workflows that might use a different pattern
                    # But for now, we expect create_workflow to follow the pattern
                    raise NotImplementedError(f"Meta workflow {self.workflow_ID} does not implement create_workflow")

            else:
                raise ValueError(f"Unknown integrate_type: {self.integrate_type}")

            # 🏭 CREATE CACHED FACTORY: Direct create_workflow function (no wrapper needed)
            self._workflow_factory = create_func
            return self._workflow_factory

        except Exception as e:
            logger.error(f"❌ Failed to load workflow factory for {self.workflow_ID} ({self.integrate_type}): {e}")
            raise ImportError(f"Cannot load workflow factory for {self.workflow_ID}: {e}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "code_path": self.code_path,
            "timeout": self.timeout,
            "display_name": self.display_name,
            "description": self.description,
            "icon": self.icon,
            "integrate_type": self.integrate_type,
            "response_format": self.response_format,
            "artifact_enabled": self.artifact_enabled,
            "artifacts_enabled": self.artifacts_enabled,
            "synthetic_response": self.synthetic_response,
            "chat_history_context": self.chat_history_context,
            "workflow_ID": self.workflow_ID,
            "ui_component": self.ui_component,
            "show_tool_calls": self.show_tool_calls,
            "show_citation": self.show_citation,
            "show_followup_questions": self.show_followup_questions,
            "show_workflow_states": self.show_workflow_states,
            "force_text_structured_predict": self.force_text_structured_predict
        }

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'WorkflowConfig':
        """Create instance from dictionary, handling optional fields and defaults."""
        return cls(
            code_path=config_dict["code_path"],
            timeout=config_dict.get("timeout", 60.0),
            display_name=config_dict["display_name"],
            description=config_dict.get("description"),
            icon=config_dict.get("icon"),
            integrate_type=config_dict.get("integrate_type", "adapted"),
            response_format=config_dict.get("response_format", "json"),
            artifact_enabled=config_dict.get("artifact_enabled", False),
            artifacts_enabled=config_dict.get("artifacts_enabled", False),
            synthetic_response=config_dict.get("synthetic_response"),
            chat_history_context=config_dict.get("chat_history_context", True),
            workflow_ID=config_dict.get("workflow_ID"),
            ui_component=config_dict.get("ui_component"),
            show_tool_calls=config_dict.get("show_tool_calls", False),
            show_citation=config_dict.get("show_citation", "None"),
            show_followup_questions=config_dict.get("show_followup_questions", False),
            show_workflow_states=config_dict.get("show_workflow_states", False),

            # 🎯 LLM BEHAVIOR FLAGS
            force_text_structured_predict=config_dict.get("force_text_structured_predict", False),

            hie_enabled=config_dict.get("hie_enabled", False),
            user_data_path=config_dict.get("user_data_path")
        )

# ------------------------------------------------------------------
# EXECUTION ENGINE DTOs - Unified Workflow Execution Context
# ------------------------------------------------------------------

@dataclass
class ExecutionContext:
    """
    🎯 STREAMLINED EXECUTION CONTEXT: Dynamic data only - static data from WorkflowSession.

    NEW ARCHITECTURE: WorkflowSession becomes master container holding static + dynamic data.
    ExecutionContext contains ONLY per-request dynamic data for workflow execution.

    DYNAMIC DATA (per-request, changes frequently):
    - user_message: Current user input
    - chat_memory: Current conversation context
    - logger: Current execution logger

    STATIC DATA (bound once, accessed from WorkflowSession):
    - workflow_config: ← WorkflowSession.workflow_config_data
    - workflow_factory: ← WorkflowSession.workflow_factory_func
    - user_config: ← WorkflowSession.user_config
    - session/chat_manager: ← WorkflowSession properties
    """
    # DYNAMIC PARAMETERS ONLY (per-request execution)
    user_message: str                    # The current user's input message
    chat_memory: Optional[Any] = None    # Current conversation memory context

    # Logger (comes last to have default value)
    logger: Optional[Any] = None         # Logger for current execution

    # MARKED FOR REMOVAL: Static data now comes from WorkflowSession
    # These fields remain for backward compatibility during migration
    # TODO: Phase 4 - Remove these legacy fields
    user_config: Optional[Dict[str, Any]] = None    # LEGACY: ← WorkflowSession.user_config
    workflow_config: Optional[Any] = None           # LEGACY: ← WorkflowSession.workflow_config_data
    workflow_factory: Optional[Callable[[], Any]] = None  # LEGACY: ← WorkflowSession.workflow_factory_func
    session: Optional[Any] = None                   # LEGACY: ← WorkflowSession.session
    chat_manager: Optional[Any] = None             # LEGACY: ← WorkflowSession.chat_manager

    # EXECUTION CONTEXT METHODS - LEGACY COMPATIBILITY METHODS
    # Ensure workflows can still call these on ExecutionContext (delegated to session)

    def create_chat_request(self) -> Any:
        """
        Create standardized ChatRequest for workflow execution.
        Delegated to the session's create_chat_request method.

        Returns:
            ChatRequest: LlamaIndex ChatRequest object
        """
        if self.session and hasattr(self.session, 'create_chat_request'):
            return self.session.create_chat_request()

        # Fallback for workflows that don't have session with create_chat_request
        from llama_index.server.api.models import ChatRequest, ChatAPIMessage
        from llama_index.core.base.llms.types import MessageRole

        user_id = getattr(self.user_config, 'user_id', 'default_user') if self.user_config else 'default_user'

        return ChatRequest(
            messages=[ChatAPIMessage(
                role=MessageRole.USER,
                content=self.user_message
            )],
            id=user_id
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization (excluding complex objects)"""
        return {
            "user_message": self.user_message,
            # Note: Other fields contain complex objects not suitable for JSON
        }


# ------------------------------------------------------------------
# CLEAN EXECUTION ENGINE DTOs - Structured Workflow Results
# ------------------------------------------------------------------

@dataclass
class ExecutionResult:
    """
    🎯 EXECUTION RESULT: Structured results from Clean Workflow Execution Engine

    Represents the complete output from workflow execution using observation-only streaming.
    Provides clean separation between execution logic and result structure.

    Rendering Instructions Structure:
    {
        "show_tool_calls": boolean,
        "show_citation": boolean,
        "show_followup_questions": boolean,
        "show_workflow_states": boolean,
        "show_artifacts": boolean,

        "tool_calls": ["query_index", "search_results"],
        "citations": ["f4bdb632-d171-4e38-a14b-1c7f1f3780f5", "uuid2"],
        "followup_questions": ["What are trends?", "How do metrics compare?"],
        "progress_states": ["Analyzing", "Generating"],
        "artifacts": [{"type": "document", "name": "report.pdf"}]
    }
    """
    # 🎯 PRIMARY EXECUTION RESULTS
    response_content: str                        # Main response text (ready for rendering)
    artifacts_collected: List[Dict[str, Any]]   # Artifacts from ArtifactEvents

    # 🎯 CLEAN RENDERING INSTRUCTIONS (backend controls frontend rendering)
    rendering_instructions: Dict[str, Any] = field(default_factory=dict)

    # 🎯 EXECUTION METADATA
    execution_time: Optional[float] = None       # Time taken in seconds
    error_message: Optional[str] = None          # Error if execution failed
    workflow_config: Optional[WorkflowConfig] = None  # Used workflow config

    def __post_init__(self):
        """Validate and normalize after creation"""
        # Ensure response_content is always a string
        if not isinstance(self.response_content, str):
            self.response_content = str(self.response_content)

        # Ensure artifacts_collected is always a list
        if not isinstance(self.artifacts_collected, list):
            self.artifacts_collected = []

        # Initialize rendering_instructions with defaults
        if not self.rendering_instructions:
            self.rendering_instructions = {
                "show_tool_calls": False,
                "show_citation": "None",
                "show_followup_questions": False,
                "show_workflow_states": False,
                "show_artifacts": False,

                "tool_calls": [],
                "citations": [],
                "followup_questions": [],
                "progress_states": [],
                "artifacts": []
            }

    def is_successful(self) -> bool:
        """Check if execution was successful"""
        return self.error_message is None

    def has_artifacts(self) -> bool:
        """Check if execution produced artifacts"""
        return len(self.artifacts_collected) > 0

    def has_enhanced_rendering(self) -> bool:
        """Check if result requires enhanced rendering features"""
        instructions = self.rendering_instructions
        return any([
            instructions.get("show_tool_calls", False),
            instructions.get("show_citation", False),
            instructions.get("show_followup_questions", False),
            instructions.get("show_workflow_states", False),
            len(instructions.get("artifacts", [])) > 0
        ])

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON transport"""
        return {
            "response_content": self.response_content,
            "artifacts_collected": self.artifacts_collected,
            "rendering_instructions": self.rendering_instructions,
            "execution_time": self.execution_time,
            "error_message": self.error_message,
            "workflow_config": self.workflow_config.to_dict() if self.workflow_config else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutionResult':
        """Create from dictionary"""
        return cls(
            response_content=data.get("response_content", ""),
            artifacts_collected=data.get("artifacts_collected", []),
            rendering_instructions=data.get("rendering_instructions", {}),
            execution_time=data.get("execution_time"),
            error_message=data.get("error_message"),
            workflow_config=WorkflowConfig(**data.get("workflow_config", {})) if data.get("workflow_config") else None
        )


@dataclass
class WorkflowDefinition:
    """
    Definition of a workflow instance.

    Combines the workflow identifier with its configuration for system-wide
    workflow management and dynamic loading.
    """
    id: str                     # Workflow identifier (e.g., "A_agentic_rag")
    config: WorkflowConfig     # Associated configuration
