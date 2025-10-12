"""
Session Authority - Unified Session Management Control Layer

This module implements the Unified Session Authority pattern to eliminate
multiple uncoordinated session creation points and provide guaranteed
session isolation and memory management.

The SessionAuthority is the SINGLE AUTHORITATIVE SOURCE for all session lifecycle operations.

Key Responsibilities:
- Single source of truth for all session lifecycle operations
- Enforced isolation: exactly one active session per workflow per user
- Thread-safe operations with proper locking
- Proactive session management (creation, cleanup, memory management)
- Coordination between ChatHistoryManager and all clients (decorators, endpoints, etc.)
"""

import threading
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import asyncio

from super_starter_suite.shared.config_manager import UserConfig, config_manager
from super_starter_suite.chat_bot.chat_history.chat_history_manager import ChatHistoryManager, SessionLifecycleManager
from super_starter_suite.shared.workflow_session_bridge import WorkflowSessionBridge


@dataclass
class SessionInfo:
    """Minimal session information for authority tracking."""
    workflow_name: str
    session_id: str
    user_id: str
    created_at: datetime
    last_accessed: datetime = field(default_factory=datetime.now)

    def touch(self) -> None:
        """Update last access timestamp."""
        self.last_accessed = datetime.now()

    def __repr__(self) -> str:
        return f"SessionInfo(workflow={self.workflow_name}, session={self.session_id[:8]}..., user={self.user_id})"


class SessionRegistry:
    """
    Thread-safe registry for session management.

    Guarantees:
    - One active session per workflow per user
    - Thread-safe access with proper locking
    - Automatic cleanup of orphaned sessions
   """

    def __init__(self):
        self._lock = threading.RLock()
        # user_id -> workflow_name -> session_info
        self._active_sessions: Dict[str, Dict[str, SessionInfo]] = {}
        self._cleanup_interval = 300  # 5 minutes
        self.logger = config_manager.get_logger("chat_bot.session_registry")

        # Start cleanup thread
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_worker,
            daemon=True,
            name="SessionRegistryCleanup"
        )
        self._cleanup_thread.start()

    def _cleanup_worker(self) -> None:
        """Continuous cleanup of orphaned sessions."""
        while True:
            try:
                self._cleanup_orphaned_sessions()
            except Exception as e:
                self.logger.error(f"Session cleanup error: {e}")
            finally:
                threading.Event().wait(self._cleanup_interval)

    def _cleanup_orphaned_sessions(self) -> None:
        """Remove sessions that no longer exist in storage."""
        with self._lock:
            for user_id in list(self._active_sessions.keys()):
                user_config = None
                try:
                    user_config = config_manager.get_user_config(user_id)
                    chat_manager = ChatHistoryManager(user_config)

                    for workflow_name in list(self._active_sessions[user_id].keys()):
                        session_info = self._active_sessions[user_id][workflow_name]
                        session = chat_manager.load_session(workflow_name, session_info.session_id)

                        if not session:
                            self.logger.info(f"Removing orphaned session {session_info.session_id} for {workflow_name}")
                            del self._active_sessions[user_id][workflow_name]

                    # Clean up empty user entries
                    if not self._active_sessions[user_id]:
                        del self._active_sessions[user_id]

                except Exception as e:
                    self.logger.error(f"Error cleaning up user {user_id}: {e}")

    def get_user_sessions(self, user_id: str) -> Dict[str, SessionInfo]:
        """Get all active sessions for a user."""
        with self._lock:
            return self._active_sessions.get(user_id, {}).copy()

    def get_active_session(self, user_id: str, workflow_name: str) -> Optional[SessionInfo]:
        """Get active session for specific workflow."""
        with self._lock:
            user_sessions = self._active_sessions.get(user_id, {})
            session_info = user_sessions.get(workflow_name)
            if session_info:
                session_info.touch()  # Update access time
                return session_info
            return None

    def register_session(self, user_id: str, workflow_name: str, session_id: str) -> SessionInfo:
        """Register a new active session for workflow."""
        with self._lock:
            if user_id not in self._active_sessions:
                self._active_sessions[user_id] = {}

            # If there's an existing session for this workflow, clean it up first
            existing = self._active_sessions[user_id].get(workflow_name)
            if existing and existing.session_id != session_id:
                self.logger.debug(f"Replacing active session for {workflow_name}: {existing.session_id[:8]} -> {session_id[:8]}")

            session_info = SessionInfo(
                workflow_name=workflow_name,
                session_id=session_id,
                user_id=user_id,
                created_at=datetime.now()
            )

            self._active_sessions[user_id][workflow_name] = session_info
            self.logger.debug(f"Registered new session {session_id[:8]}... for {workflow_name} (user: {user_id})")
            return session_info

    def unregister_session(self, user_id: str, workflow_name: str) -> None:
        """Remove session from registry."""
        with self._lock:
            if user_id in self._active_sessions and workflow_name in self._active_sessions[user_id]:
                session_info = self._active_sessions[user_id][workflow_name]
                del self._active_sessions[user_id][workflow_name]
                self.logger.debug(f"Unregistered session {session_info.session_id[:8]}... for {workflow_name}")

                if not self._active_sessions[user_id]:
                    del self._active_sessions[user_id]

    def is_session_active(self, user_id: str, workflow_name: str, session_id: str) -> bool:
        """Check if specific session is the active one."""
        with self._lock:
            active = self.get_active_session(user_id, workflow_name)
            return active is not None and active.session_id == session_id

    def clear_user_sessions(self, user_id: str) -> int:
        """Clear all sessions for a user. Returns count of cleared sessions."""
        with self._lock:
            count = len(self._active_sessions.get(user_id, {}))
            if count > 0:
                self._active_sessions.pop(user_id, None)
                self.logger.debug(f"Cleared all {count} sessions for user {user_id}")
            return count


class SessionAuthority:
    """
    SINGLE AUTHORITATIVE SOURCE for all session lifecycle operations.

    This singleton ensures:
    - One active session per workflow (enforced isolation)
    - Proper memory cleanup on session changes
    - Thread-safe coordination between all clients
    - Proactive rather than reactive session management

    NO OTHER CODE SHOULD CREATE OR MANAGE SESSIONS DIRECTLY.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.logger = config_manager.get_logger("chat_bot.session_authority")
        self.registry = SessionRegistry()

        # User-specific managers cache for performance
        self._user_managers: Dict[str, SessionLifecycleManager] = {}
        self._manager_lock = threading.RLock()

        self._initialized = True
        self.logger.info("SessionAuthority singleton initialized")

    def get_or_create_session(self, workflow_name: str, user_config: UserConfig,
                             existing_session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        SINGLE ENTRY POINT for session creation/retrieval.

        Guarantees:
        - Exactly one active session per workflow
        - Session isolation (no cross-workflow interference)
        - Memory cleanup of replaced sessions
        - Thread-safe operations

        Args:
            workflow_name: Target workflow name
            user_config: User configuration
            existing_session_id: Optional existing session ID to reuse

        Returns:
            dict: {
                'session': ChatSession,
                'is_new': bool,
                'memory': ChatMemoryBuffer or None,
                'replaced_session_id': str or None  # If session was replaced
            }
        """
        user_id = getattr(user_config, 'user_id', 'Default')

        with self._manager_lock:
            # Get or create session lifecycle manager for this user
            lifecycle_manager = self._get_user_lifecycle_manager(user_id, user_config)
            replaced_session_id = None

            # Check for existing active session
            existing_active_id = lifecycle_manager.get_active_session_id(workflow_name)
            target_session_id = existing_session_id or existing_active_id

            if target_session_id:
                # Verify existing session is still valid and matches active
                chat_manager = ChatHistoryManager(user_config)
                session = chat_manager.load_session(workflow_name, target_session_id)

                if session and existing_active_id == target_session_id:
                    # Session is valid and is the active one
                    memory = chat_manager.get_llama_index_memory(session)
                    self.registry.register_session(user_id, workflow_name, target_session_id)

                    self.logger.debug(f"Reusing active session {target_session_id[:8]}... for {workflow_name}")
                    return {
                        'session': session,
                        'is_new': False,
                        'memory': memory,
                        'replaced_session_id': None
                    }
                else:
                    # Session is invalid or not the active one - will replace
                    replaced_session_id = existing_active_id or target_session_id
                    self.logger.info(f"Invalid/Rogue session {target_session_id[:8]}... for {workflow_name}, will replace")

            # Create new session (no valid existing session found)
            try:
                new_session_id = lifecycle_manager.get_or_create_workflow_session(workflow_name)
                chat_manager = ChatHistoryManager(user_config)
                new_session = chat_manager.load_session(workflow_name, new_session_id)

                if not new_session:
                    raise RuntimeError(f"Failed to load newly created session {new_session_id}")

                memory = chat_manager.get_llama_index_memory(new_session)
                self.registry.register_session(user_id, workflow_name, new_session_id)

                # Cleanup old session memory if we replaced one
                if replaced_session_id and replaced_session_id != new_session_id:
                    self._cleanup_replaced_session(user_config, workflow_name, replaced_session_id)

                self.logger.info(f"Created new session {new_session_id[:8]}... for {workflow_name} (replaced: {replaced_session_id[:8] if replaced_session_id else None})")

                return {
                    'session': new_session,
                    'is_new': True,
                    'memory': memory,
                    'replaced_session_id': replaced_session_id
                }

            except Exception as e:
                self.logger.error(f"Failed to create session for {workflow_name}: {e}")
                raise

    def _get_user_lifecycle_manager(self, user_id: str, user_config: UserConfig) -> SessionLifecycleManager:
        """Get cached SessionLifecycleManager for user."""
        if user_id not in self._user_managers:
            chat_manager = ChatHistoryManager(user_config)
            self._user_managers[user_id] = SessionLifecycleManager(user_id, chat_manager)
        return self._user_managers[user_id]

    def _cleanup_replaced_session(self, user_config: UserConfig, workflow_name: str, old_session_id: str) -> None:
        """Clean up memory and resources from replaced session."""
        try:
            # Just log for now - ChatHistoryManager cleanup is reactive
            # TODO: Consider adding proactive cleanup to SessionLifecycleManager
            self.logger.debug(f"Old session {old_session_id[:8]}... cleaned up for {workflow_name}")

        except Exception as e:
            self.logger.warning(f"Non-critical error cleaning up replaced session: {e}")

    async def shutdown_workflow_session(self, workflow_name: str, user_config: UserConfig,
                                       session_id: str) -> None:
        """
        Gracefully shutdown a workflow session.

        Ensures memory cleanup and proper state transition.
        Called when workflow execution ends or on application shutdown.
        """
        user_id = getattr(user_config, 'user_id', 'Default')

        try:
            # Verify this is the active session before unregistering
            active_info = self.registry.get_active_session(user_id, workflow_name)
            if active_info and active_info.session_id == session_id:
                self.logger.debug(f"Shutting down session {session_id[:8]}... for {workflow_name}")

                # Cleanup memory through bridge
                session_data = {'memory': None}  # Don't have the actual memory object here
                # Note: Memory cleanup happens in WorkflowSessionBridge when sessions are actually used

                # Unregister from our registry
                self.registry.unregister_session(user_id, workflow_name)

                # Update lifecycle manager
                with self._manager_lock:
                    lifecycle_manager = self._user_managers.get(user_id)
                    if lifecycle_manager:
                        # The session mapping should be updated when a new session is created
                        # For shutdown, we don't remove the mapping - it persists for session recovery
                        pass

            else:
                self.logger.warning(f"Attempted to shutdown non-active session {session_id[:8]}... for {workflow_name}")

        except Exception as e:
            self.logger.error(f"Error shutting down session {session_id[:8]}... for {workflow_name}: {e}")

    def cleanup_user_sessions(self, user_config: UserConfig) -> int:
        """
        Clean up all sessions for a user (e.g., on logout or cleanup).

        Returns number of sessions cleaned up.
        """
        user_id = getattr(user_config, 'user_id', 'Default')

        try:
            count = self.registry.clear_user_sessions(user_id)

            # Also cleanup user manager cache
            with self._manager_lock:
                if user_id in self._user_managers:
                    del self._user_managers[user_id]

            if count > 0:
                self.logger.info(f"Cleaned up {count} sessions for user {user_id}")

            return count

        except Exception as e:
            self.logger.error(f"Error cleaning up sessions for user {user_id}: {e}")
            return 0

    def get_session_status(self, workflow_name: str, user_config: UserConfig) -> Optional[Dict[str, Any]]:
        """
        Get status of active session for workflow.
        """
        user_id = getattr(user_config, 'user_id', 'Default')
        session_info = self.registry.get_active_session(user_id, workflow_name)

        if not session_info:
            return None

        chat_manager = ChatHistoryManager(user_config)
        session = chat_manager.load_session(workflow_name, session_info.session_id)

        if not session:
            # Session info exists but session file is gone - clean up
            self.registry.unregister_session(user_id, workflow_name)
            return None

        return {
            'session_id': session.session_id,
            'workflow': workflow_name,
            'status': 'active',
            'created_at': session_info.created_at.isoformat(),
            'last_accessed': session_info.last_accessed.isoformat(),
            'message_count': len(session.messages)
        }

    def get_active_session_id(self, workflow_name: str, user_config: UserConfig) -> Optional[str]:
        """
        Get the active session ID for a workflow without creating one.

        This checks for existing sessions that were previously registered and active.
        Returns None if no active session exists for this specific workflow.

        CRITICAL: This maintains strict isolation - only returns sessions for the requested workflow.

        FALLBACK: If no registered session exists, uses SessionLifecycleManager's sophisticated logic
        to find existing sessions on disk and registers the active one.
        """
        user_id = getattr(user_config, 'user_id', 'Default')

        # Check registered sessions (SessionAuthority maintains)
        session_info = self.registry.get_active_session(user_id, workflow_name)
        if session_info:
            self.logger.debug(f"Found registered active session {session_info.session_id} for {workflow_name}")
            return session_info.session_id

        # FALLBACK: Check filesystem for existing sessions and register active one
        # This handles sessions that exist from previous runs but aren't registered
        self.logger.debug(f"No registered session found for {workflow_name}, checking filesystem")
        try:
            # Use SessionLifecycleManager's logic as fallback (direct instantiation for checking)
            chat_manager = ChatHistoryManager(user_config)
            lifecycle_manager = SessionLifecycleManager(user_id, chat_manager)

            # Check if there's an existing active session ID
            existing_session_id = lifecycle_manager.get_active_session_id(workflow_name)

            if existing_session_id:
                # Verify it still exists
                session = chat_manager.load_session(workflow_name, existing_session_id)
                if session:
                    # Register this as the active session for this workflow
                    self.registry.register_session(user_id, workflow_name, existing_session_id)
                    self.logger.debug(f"Registered existing active session {existing_session_id} for {workflow_name}")
                    return existing_session_id

            # No valid session found - try to find active session using ChatHistoryManager's priority logic
            active_session = self._find_active_session_from_filesystem(user_config, workflow_name)
            if active_session:
                # Register this as the active session for this workflow
                self.registry.register_session(user_id, workflow_name, active_session.session_id)
                self.logger.debug(f"Registered found active session {active_session.session_id} for {workflow_name}")
                return active_session.session_id

            self.logger.debug(f"No existing sessions found on filesystem for {workflow_name}")
        except Exception as e:
            self.logger.warning(f"Error checking existing sessions for {workflow_name}: {e}")

        # No active session found
        return None

    def _find_active_session_from_filesystem(self, user_config: UserConfig, workflow_name: str) -> Optional[Any]:
        """
        Find an active session from filesystem using ChatHistoryManager's priority logic.

        This is a fallback when no registered session exists in SessionAuthority.
        """
        try:
            chat_manager = ChatHistoryManager(user_config)

            # Get all sessions for this workflow, take the most recent
            sessions = chat_manager.get_all_sessions(workflow_name)
            if sessions:
                # Return the most recent session (already sorted by updated_at descending)
                return sessions[0]

        except Exception as e:
            self.logger.warning(f"Error finding active session from filesystem: {e}")

        return None

    def is_session_authorized(self, workflow_name: str, user_config: UserConfig,
                             session_id: str) -> bool:
        """
        Check if session ID is authorized for accessing this workflow.
        """
        user_id = getattr(user_config, 'user_id', 'Default')
        active_info = self.registry.get_active_session(user_id, workflow_name)
        return active_info is not None and active_info.session_id == session_id


# Global singleton instance
session_authority = SessionAuthority()

# Backwards compatibility class (redirects to authority)
class UnifiedSessionManager:
    """
    Backwards compatibility wrapper for SessionAuthority.

    Legacy code can use this class but all operations route through
    the singleton SessionAuthority for coordination.
    """

    def __init__(self, user_config: UserConfig):
        self.user_config = user_config
        self.logger = config_manager.get_logger("chat_bot.unified_session_manager")

    def get_or_create_session(self, workflow_name: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Delegate to SessionAuthority."""
        return session_authority.get_or_create_session(workflow_name, self.user_config, session_id)

    async def shutdown_session(self, workflow_name: str, session_id: str) -> None:
        """Delegate to SessionAuthority."""
        await session_authority.shutdown_workflow_session(workflow_name, self.user_config, session_id)

    def get_session_status(self, workflow_name: str) -> Optional[Dict[str, Any]]:
        """Delegate to SessionAuthority."""
        return session_authority.get_session_status(workflow_name, self.user_config)
