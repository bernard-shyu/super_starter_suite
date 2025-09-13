"""
Data Transfer Objects for MVC Pattern Implementation

This module contains encapsulated data objects that carry similar/same structure
data across MVC boundaries, with essential properties (always carried) and
meta-properties (internal control). Only essential changes are visible at control points.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from enum import Enum


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
    data_file_newest: Optional[str] = None
    total_files: int = 0
    total_size: int = 0
    files: List[Dict[str, Any]] = field(default_factory=list)
    has_newer_files: bool = False

    # Essential Context Properties
    rag_type: str = "RAG"
    last_updated: datetime = field(default_factory=datetime.now)

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
        return datetime.now() - self.last_updated > self._stale_threshold

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

        self.last_updated = datetime.now()
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization (essential properties only)"""
        return {
            "data_file_newest": self.data_file_newest,
            "total_files": self.total_files,
            "total_size": self.total_size,
            "files": self.files,
            "has_newer_files": self.has_newer_files,
            "rag_type": self.rag_type,
            "last_updated": self.last_updated.isoformat(),
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
    data_file_newest: Optional[str] = None,
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
        data_file_newest=data_file_newest,
        total_files=total_files,
        total_size=total_size,
        **kwargs
    )

    # Control Point: Always validate on creation
    if not data.validate():
        raise ValueError(f"Invalid status data: total_files={total_files}, total_size={total_size}")

    return data
