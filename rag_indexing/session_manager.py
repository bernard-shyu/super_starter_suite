"""
RAG Generation Session - Unified Architecture for Generate UI

This module provides a single cohesive object that encapsulates all generation-related
state and operations, eliminating global singleton violations and ensuring proper
per-session state management.

ARCHITECTURAL BENEFITS:
- Single responsibility: One object handles all RAG generation session needs
- No global state: Per-session instances eliminate state corruption
- Clean encapsulation: All generation logic within session boundary
- Proper lifecycle: Clear create/use/destroy lifecycle per Generate UI session

DESIGN PRINCIPLES:
- total_files is GET from cache metadata, not SET as parameter
- Session encapsulates all components (ProgressTracker, CacheManager, GenerateManager)
- Per-Generate-UI-session lifecycle (load cache on entry, save on exit)
"""

import logging
import copy
from typing import Dict, Any, Optional
from datetime import datetime

from super_starter_suite.shared.config_manager import UserConfig, UserRAGIndex, config_manager
from super_starter_suite.shared.dto import ProgressData, StatusData
from super_starter_suite.shared.session_utils import BasicUserSession

# Import encapsulated components (will be used internally)
from super_starter_suite.rag_indexing.generate_manager import GenerateManager

# Unified logging for session operations
session_logger = config_manager.get_logger("sess_manager")


class RAGGenerationSession:
    """
    Unified session object for RAG generation operations.

    This single object encapsulates all generation-related state and operations:
    - Progress tracking (file processing, state transitions, percentages)
    - Cache management (metadata loading/saving, user isolation, lifecycle)
    - Generation management (business logic, state synchronization, event handling)
    - Session state (per-Generate-UI-session state, proper cleanup, no global persistence)

    Eliminates global singleton patterns and ensures proper web statelessness.
    """

    def __init__(self, user_config: UserConfig):
        """
        Initialize a fresh RAG generation session for a Generate UI session.

        PHASE 1: Establish clear ownership - RAGGenerationSession owns StatusData,
        GenerateManager owns ProgressTracker.

        Args:
            user_config: User's configuration (contains RAG paths, settings, etc.)
        """
        self.user_config = user_config
        self.session_id = f"{user_config.user_id}_{datetime.now().isoformat()}"

        # PHASE 1: Session owns UserRAGIndex copy (no external changes during session)
        self.my_rag = copy.deepcopy(user_config.my_rag)

        # PHASE 1: StatusData cache for lazy loading multiple RAG types (SESSION owns this)
        self._status_data_cache: Dict[str, StatusData] = {}

        # PHASE 1: Current tracking for active RAG type (SESSION owns this)
        self._current_rag_type: Optional[str] = None
        self._current_status_data: Optional[StatusData] = None

        # PHASE 1: GenerateManager owns ProgressTracker, Session owns GenerateManager
        self._generate_manager = None

        # Session state
        self.is_initialized = False
        self.created_at = datetime.now()

        session_logger.info(f"RAGGenerationSession created: {self.session_id} for user {user_config.user_id}")

    def initialize_session(self) -> bool:
        """
        Initialize the session by loading StatusData from file and creating components.

        Uses existing save_data_metadata() from shared/index_utils.py for proper
        RAG type initialization and standalone application compatibility.
        No redundant StatusData.save_to_file() logic needed.

        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            # DELEGATE StatusData loading to shared/index_utils.py through StatusData.load_from_file()
            # External calls removed to maintain single responsibility principle
            self._status_data = StatusData.load_from_file(
                self.user_config,
                self.user_config.my_rag.rag_type
            )
            session_logger.debug(f"initialize_session: StatusData loaded: {self._status_data}, session {self.session_id}")

            # If StatusData loading fails, session initialization cannot proceed
            if self._status_data is None:
                session_logger.error(f"Failed to load StatusData for RAG type {self.user_config.my_rag.rag_type}")
                return False

            # Load initial StatusData into cache and set as current
            self._status_data_cache[self.user_config.my_rag.rag_type] = self._status_data
            self._current_rag_type = self.user_config.my_rag.rag_type
            self._current_status_data = self._status_data

            # DEBUG: Log StatusData details before creating components
            session_logger.debug(f"initialize_session: About to create components with StatusData: total_files={self._current_status_data.total_files if self._current_status_data else 'None'}")

            # Create GenerateManager with StatusData and user_config reference
            # GenerateManager owns ProgressTracker, Session owns GenerateManager
            self._generate_manager = GenerateManager(self._current_status_data, self.user_config)

            # DEBUG: Verify GenerateManager got the correct StatusData
            if self._generate_manager and hasattr(self._generate_manager, 'status_data'):
                session_logger.debug(f"initialize_session: GenerateManager status_data total_files={self._generate_manager.status_data.total_files if self._generate_manager.status_data else 'None'}")

            self.is_initialized = True
            session_logger.info(f"Session {self.session_id} initialized with RAG type {self._current_rag_type}, total_files={self.get_total_files()}")
            return True

        except Exception as e:
            session_logger.error(f"Failed to initialize session {self.session_id}: {e}")
            self.is_initialized = False
            return False



    def cleanup_session(self) -> bool:
        """
        Clean up session resources and save persistent state.

        Uses StatusData's own save functionality for persistence.

        Returns:
            bool: True if cleanup successful, False otherwise
        """
        try:
            # Save StatusData to file using its own save method
            if self._status_data:
                save_result = self._status_data.save_to_file(self.user_config)
                if not save_result:
                    session_logger.warning(f"Failed to save StatusData to file for session {self.session_id}")

            # Log session completion
            duration = datetime.now() - self.created_at
            session_logger.info(f"Session {self.session_id} cleaned up after {duration.total_seconds():.2f}s")

            self.is_initialized = False
            return True

        except Exception as e:
            session_logger.error(f"Error during session cleanup {self.session_id}: {e}")
            return False

    def process_console_output(self, raw_line: str, task_id: Optional[str] = None, rag_type: str = "RAG") -> Optional[ProgressData]:
        """
        Process console output through Session Manager before/after MVC cycle.

        Session Manager owns this function and can handle output processing,
        validation, and coordination before delegating to MVC components.
        Main usage comes from MVC during Generation Progress handling.

        Args:
            raw_line: Raw console output line from generation process
            task_id: Optional task identifier for tracking
            rag_type: RAG type for context validation

        Returns:
            ProgressData object from MVC processing, or None if no progress update
        """
        if not self.is_initialized or self._generate_manager is None:
            session_logger.warning("Session not initialized, cannot process console output")
            return None

        # Session-level validation and coordination
        if rag_type != self._current_rag_type:
            session_logger.warning(f"RAG type mismatch: {rag_type} != {self._current_rag_type}")
            # Use session's current RAG type for consistency
            rag_type = self._current_rag_type

        # Delegate to GenerateManager for MVC processing
        return self._generate_manager.process_console_output(raw_line, task_id, rag_type)

    # ============================================================================
    # CACHE MANAGEMENT INTERFACE - DELEGATES TO STATUSDATA
    # ============================================================================

    def load_cache(self) -> bool:
        """
        Load metadata cache using StatusData's cache functionality.

        Delegates to StatusData.load_from_file() for unified cache access.

        Returns:
            bool: True if cache loaded successfully, False otherwise
        """
        if not self.is_initialized or not self._status_data:
            session_logger.warning("Session not initialized, cannot load cache")
            return False

        try:
            # StatusData.load_from_file() handles all cache loading logic
            self._status_data = StatusData.load_from_file(self.user_config, self.user_config.my_rag.rag_type)
            if self._status_data is None:
                session_logger.warning("Failed to load StatusData from cache")
                return False

            # Update session state from loaded StatusData
            session_logger.info(f"Cache loaded successfully, total_files={self._status_data.total_files}")
            return True

        except Exception as e:
            session_logger.error(f"Error loading cache: {e}")
            return False

    def save_cache(self) -> bool:
        """
        Save metadata cache using StatusData's cache functionality.

        Delegates to StatusData.save_to_file() for unified cache persistence.

        Returns:
            bool: True if cache saved successfully, False otherwise
        """
        if not self.is_initialized or not self._status_data:
            session_logger.warning("Session not initialized, cannot save cache")
            return False

        try:
            # StatusData.save_to_file() handles all cache saving logic
            return self._status_data.save_to_file(self.user_config)

        except Exception as e:
            session_logger.error(f"Error saving cache: {e}")
            return False

    def get_cache_status(self) -> Dict[str, Any]:
        """
        Get cache status information.

        Returns comprehensive status information about the cache state.

        Returns:
            dict: Cache status information
        """
        if not self.is_initialized or not self._status_data:
            return {"error": "Session not initialized or StatusData not available"}

        try:
            # Handle meta_last_update - could be datetime or string
            meta_last_update = self._status_data.meta_last_update
            if meta_last_update:
                # If it's a datetime object, format it
                if hasattr(meta_last_update, 'isoformat'):
                    meta_last_update = meta_last_update.isoformat()
                # If it's already a string, use it as-is
                elif isinstance(meta_last_update, str):
                    pass  # already in correct format
                else:
                    meta_last_update = str(meta_last_update)  # fallback

            return {
                "cache_loaded": self._status_data._from_cache,
                "rag_type": self._status_data.rag_type,
                "total_files": self._status_data.total_files,
                "total_size": self._status_data.total_size,
                "meta_last_update": meta_last_update,
                "data_newest_time": self._status_data.data_newest_time,
                "storage_status": self._status_data.storage_status
            }

        except Exception as e:
            session_logger.error(f"Error getting cache status: {e}")
            return {"error": f"Failed to get cache status: {str(e)}"}

    # ============================================================================
    # STATUS DATA MANAGEMENT INTERFACE
    # ============================================================================

    def get_status_data_info(self, rag_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Get comprehensive StatusData information.

        Detects and handles RAG type switches automatically.

        Args:
            rag_type: Optional RAG type to switch to (detects switch if different from current)

        Returns:
            dict: StatusData information including loaded state and metadata
        """
        if not self.is_initialized:
            return {"error": "Session not initialized"}

        try:
            # Handle RAG type switching if requested
            if rag_type and rag_type != self._current_rag_type:
                session_logger.debug(f"RAG type switch detected: {self._current_rag_type} -> {rag_type}")
                self._refresh_data_cache(rag_type)

            # Use current StatusData (after potential switch)
            current_data = self._current_status_data or self._status_data
            if not current_data:
                return {"error": "No StatusData available"}

            # Handle meta_last_update - could be datetime or string
            meta_last_update = current_data.meta_last_update
            if meta_last_update:
                # If it's a datetime object, format it
                if hasattr(meta_last_update, 'isoformat'):
                    meta_last_update = meta_last_update.isoformat()
                # If it's already a string, use it as-is
                elif isinstance(meta_last_update, str):
                    pass  # already in correct format
                else:
                    meta_last_update = str(meta_last_update)  # fallback

            return {
                "status_loaded": self.is_initialized,
                "rag_type": current_data.rag_type,
                "total_files": current_data.total_files,
                "total_size": current_data.total_size,
                "data_newest_time": current_data.data_newest_time,
                "data_newest_file": current_data.data_newest_file,
                "storage_status": current_data.storage_status,
                "storage_creation": current_data.storage_creation,
                "meta_last_update": meta_last_update,
                "from_cache": current_data._from_cache,
                "data_files": current_data.data_files  # Include files list for Sample File extraction
            }

        except Exception as e:
            session_logger.error(f"Error getting StatusData info: {e}")
            return {"error": f"Failed to get StatusData info: {str(e)}"}

    def _refresh_data_cache(self, rag_type: str) -> None:
        """
        Switch to a different RAG type, loading StatusData lazily if needed.

        Args:
            rag_type: The RAG type to switch to
        """
        # Check if StatusData for this RAG type is already cached
        if rag_type not in self._status_data_cache:
            session_logger.debug(f"Lazy loading StatusData for RAG type: {rag_type}")

            # Load StatusData directly from metadata file using shared/index_utils.py
            # StatusData.load_from_file is now guaranteed to return a StatusData instance,
            # so no None check is needed here.
            status_data: StatusData = StatusData.load_from_file(self.user_config, rag_type)

            # Cache the StatusData instance
            self._status_data_cache[rag_type] = status_data

        # Update current tracking
        self._current_rag_type = rag_type
        self._current_status_data = self._status_data_cache[rag_type]

        # PHASE 1: Update GenerateManager with new StatusData
        # GenerateManager will handle ProgressTracker recreation internally
        if self._current_status_data and self._generate_manager:
            session_logger.debug(f"_refresh_data_cache: Updating GenerateManager with StatusData total_files={self._current_status_data.total_files}")
            # GenerateManager owns ProgressTracker, so it handles recreation
            self._generate_manager.set_status_data(self._current_status_data)
            session_logger.debug(f"_refresh_data_cache: GenerateManager updated successfully")
        else:
            session_logger.error(f"_refresh_data_cache: No StatusData or GenerateManager available for RAG type {rag_type}")

        session_logger.debug(f"Switched to RAG type {rag_type}, total_files={self.get_total_files()}")

    def switch_rag_type(self, rag_type: str) -> bool:
        """
        Clean method to change RAG type within session.

        Single point of truth for RAG type changes. Session owns current_rag_type
        and manages StatusData accordingly. No external rag_type parameters needed.

        Args:
            rag_type: The RAG type to switch to

        Returns:
            bool: True if switch successful, False otherwise
        """
        try:
            session_logger.info(f"Session {self.session_id} switching RAG type: {self._current_rag_type} -> {rag_type}")

            # Update session's UserRAGIndex copy
            self.my_rag.set_rag_type(rag_type)

            # Switch StatusData and update components
            self._refresh_data_cache(rag_type)

            session_logger.info(f"Session {self.session_id} successfully switched to RAG type {rag_type}")
            return True

        except Exception as e:
            session_logger.error(f"Failed to switch RAG type to {rag_type}: {e}")
            return False



    def get_total_files(self) -> int:
        """
        Get total files count from current StatusData.

        Returns:
            int: Total files count, or 0 if not available
        """
        if self._current_status_data:
            return self._current_status_data.total_files
        elif self._status_data:
            return self._status_data.total_files
        else:
            session_logger.warning(f"get_total_files called but no StatusData available for session {self.session_id}")
            return 0

    def get_current_progress(self) -> Dict[str, Any]:
        """
        Get current progress information.

        PHASE 1: Delegates to GenerateManager since ProgressTracker is owned by GenerateManager.

        Returns:
            dict: Current progress state
        """
        if not self.is_initialized or self._generate_manager is None:
            return {"error": "Session not initialized"}

        # Delegate to GenerateManager's ProgressTracker
        return self._generate_manager.get_current_status()

    def get_session_status(self) -> Dict[str, Any]:
        """
        Get comprehensive session status for debugging.

        PHASE 1: Delegates to GenerateManager for ProgressTracker status.

        Returns:
            dict: Complete session state information
        """
        return {
            "session_id": self.session_id,
            "user_id": self.user_config.user_id,
            "is_initialized": self.is_initialized,
            "total_files": self.get_total_files(),
            "created_at": self.created_at.isoformat(),
            "progress_tracker": self._generate_manager.get_current_status() if self.is_initialized and self._generate_manager else None,
            "status_data_loaded": self.is_initialized and self._status_data is not None,
            "generation_state": self._generate_manager.get_current_status() if self.is_initialized and self._generate_manager else None
        }

    def __repr__(self) -> str:
        """String representation of the session."""
        return f"RAGGenerationSession({self.session_id}, user={self.user_config.user_id}, initialized={self.is_initialized})"





# ============================================================================
# NEW SESSION HANDLER FOR UNIFIED ARCHITECTURE
# ============================================================================

class RagGenSession(BasicUserSession):
    """RAG generation session implementing new BasicUserSession"""

    def __init__(self, user_config: Dict[str, Any], session_type: str, session_id: str):
        super().__init__(user_config, session_type, session_id)

        # RAG-specific properties
        self.generation_context: Dict[str, Any] = {}
        self.processing_status: str = "idle"
        self.rag_session: Optional[RAGGenerationSession] = None

    @property
    def is_initialized(self) -> bool:
        """Delegate is_initialized to underlying RAGGenerationSession"""
        return self.rag_session.is_initialized if self.rag_session else False

    def load_cache(self) -> bool:
        """Delegate load_cache to underlying RAGGenerationSession"""
        return self.rag_session.load_cache() if self.rag_session else False

    def save_cache(self) -> bool:
        """Delegate save_cache to underlying RAGGenerationSession"""
        return self.rag_session.save_cache() if self.rag_session else False

    def get_cache_status(self) -> Dict[str, Any]:
        """Delegate get_cache_status to underlying RAGGenerationSession"""
        return self.rag_session.get_cache_status() if self.rag_session else {"error": "No RAG session available"}

    def get_status_data_info(self, rag_type: Optional[str] = None) -> Dict[str, Any]:
        """Delegate get_status_data_info to underlying RAGGenerationSession"""
        return self.rag_session.get_status_data_info(rag_type) if self.rag_session else {"error": "No RAG session available"}

    def switch_rag_type(self, rag_type: str) -> bool:
        """Delegate switch_rag_type to underlying RAGGenerationSession"""
        return self.rag_session.switch_rag_type(rag_type) if self.rag_session else False

    def get_total_files(self) -> int:
        """Delegate get_total_files to underlying RAGGenerationSession"""
        return self.rag_session.get_total_files() if self.rag_session else 0

    def get_current_progress(self) -> Dict[str, Any]:
        """Delegate get_current_progress to underlying RAGGenerationSession"""
        return self.rag_session.get_current_progress() if self.rag_session else {"error": "No RAG session available"}

    def process_console_output(self, raw_line: str, task_id: Optional[str] = None, rag_type: str = "RAG") -> Optional[ProgressData]:
        """Delegate process_console_output to underlying RAGGenerationSession"""
        return self.rag_session.process_console_output(raw_line, task_id, rag_type) if self.rag_session else None

    def initialize_session_resources(self):
        """Initialize RAG generation resources"""
        # Create underlying RAGGenerationSession if this is a RAG session
        if self.session_type == "rag_session":
            # Get the full UserConfig object and make a deep copy for RAG generation
            # This allows the RAG session to switch RAG types without affecting the user's original config
            # user_id is already set by BasicUserSession parent class
            original_user_config = config_manager.get_user_config(self.user_id)

            # Deep copy UserConfig to prevent RAG type switches from affecting user's config
            user_config_copy = copy.deepcopy(original_user_config)

            self.rag_session = RAGGenerationSession(user_config_copy)
            self.rag_session.initialize_session()

            self.generation_context = {
                "initialized": True,
                "current_rag_type": user_config_copy.my_rag.rag_type,
                "session_id": self.rag_session.session_id if self.rag_session else None
            }

        session_logger.info(f"RagGenSession {self.session_id} resources initialized for user {self.user_id}")

    def dispose(self):
        """Clean up RAG generation resources and CUDA memory"""
        from super_starter_suite.shared.workflow_utils import cleanup_workflow_cuda_resources

        # Cleanup CUDA memory for RAG generation session
        cleanup_workflow_cuda_resources(self.session_id, {
            "session_type": "rag_generation",
            "session_id": self.rag_session.session_id if self.rag_session else None
        })

        # Cleanup underlying RAG session
        if self.rag_session:
            try:
                self.rag_session.cleanup_session()
            except Exception as e:
                session_logger.error(f"Error cleaning up RAG session: {e}")

        # Clear session-specific resources
        self.generation_context.clear()
        self.processing_status = "terminated"

        session_logger.info(f"RagGenSession {self.session_id} disposed")

    def get_session_health_status(self) -> dict:
        """Return health metrics for monitoring"""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "session_type": self.session_type,
            "rag_session_active": self.rag_session is not None,
            "processing_status": self.processing_status,
            "generation_context_valid": bool(self.generation_context),
            "rag_session_id": self.rag_session.session_id if self.rag_session else None,
            "healthy": True
        }

    def persist_session_data(self) -> bool:
        """Preserve session data by delegating to existing save_cache() method"""
        if self.rag_session:
            return self.rag_session.save_cache()
        return True

    def perform_session_health_check(self) -> bool:
        """Perform actual health validation"""
        try:
            # Validate session ID
            import uuid
            uuid.UUID(self.session_id)
            # Validate user config
            assert self.user_config and self.user_id
            # Validate session type
            assert isinstance(self.session_type, str) and self.session_type == "rag_session"
            # Validate RAG session if this is a RAG session
            if self.rag_session:
                assert self.rag_session.is_initialized
            return True
        except (ValueError, AssertionError):
            session_logger.warning(f"Health check failed for RAG session {self.session_id}")
            return False
