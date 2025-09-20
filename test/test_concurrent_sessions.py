"""
Test concurrent session handling for unified RAG generation architecture.

This module tests the session-based architecture to ensure proper isolation
and concurrent request handling across multiple users and sessions.
"""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any
import unittest
from unittest.mock import Mock, patch, MagicMock

# Import the session components to test
from super_starter_suite.rag_indexing.rag_generation_session import (
    RAGGenerationSession,
    RAGSessionManager,
    get_rag_session,
    get_rag_session_by_user_id,
    cleanup_rag_session
)
from super_starter_suite.shared.config_manager import UserConfig, ConfigManager


class TestConcurrentSessions(unittest.TestCase):
    """Test concurrent session handling and isolation."""

    def setUp(self):
        """Set up test environment."""
        self.config_manager = ConfigManager()

        # Create mock user configurations
        self.user_configs = {}
        for i in range(5):
            user_id = f"test_user_{i}"
            user_config = Mock(spec=UserConfig)
            user_config.user_id = user_id
            user_config.my_rag = Mock()
            user_config.my_rag.rag_type = "TEST_RAG"
            user_config.my_rag.data_path = f"/test/data/{user_id}"
            user_config.my_rag.storage_path = f"/test/storage/{user_id}"
            user_config.get_user_setting = Mock(return_value=["TEST_RAG"])
            self.user_configs[user_id] = user_config

        # Clear any existing sessions
        self.session_manager = RAGSessionManager()
        self.session_manager._sessions.clear()
        self.session_manager._session_times.clear()

    def tearDown(self):
        """Clean up after tests."""
        # Clean up all sessions
        for user_id in list(self.session_manager._sessions.keys()):
            self.session_manager.cleanup_user_session(user_id)

    def test_concurrent_session_creation(self):
        """Test that concurrent session creation works properly."""
        results = []
        errors = []

        def create_session_worker(user_config: UserConfig):
            """Worker function to create a session."""
            try:
                session = self.session_manager.get_or_create_session(user_config)
                results.append((user_config.user_id, session.session_id))
                return session
            except Exception as e:
                errors.append((user_config.user_id, str(e)))
                return None

        # Create sessions concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for user_config in self.user_configs.values():
                future = executor.submit(create_session_worker, user_config)
                futures.append(future)

            # Wait for all to complete
            for future in as_completed(futures):
                future.result()

        # Verify results
        self.assertEqual(len(results), 5, "All sessions should be created successfully")
        self.assertEqual(len(errors), 0, "No errors should occur during session creation")

        # Verify session isolation - each user should have their own session
        session_ids = [result[1] for result in results]
        self.assertEqual(len(set(session_ids)), 5, "Each user should have a unique session")

        # Verify session manager state
        self.assertEqual(len(self.session_manager._sessions), 5, "Session manager should have 5 sessions")

    def test_session_isolation(self):
        """Test that sessions are properly isolated between users."""
        # Create sessions for all users
        sessions = {}
        for user_config in self.user_configs.values():
            session = self.session_manager.get_or_create_session(user_config)
            sessions[user_config.user_id] = session

        # Verify each user gets their own session
        user_ids = list(sessions.keys())
        session_ids = [sessions[user_id].session_id for user_id in user_ids]

        # All session IDs should be unique
        self.assertEqual(len(set(session_ids)), len(user_ids), "All sessions should be unique")

        # Each session should have the correct user configuration
        for user_id, session in sessions.items():
            self.assertEqual(session.user_config.user_id, user_id, f"Session for {user_id} should have correct user config")

        # Sessions should be properly isolated (different cache managers, etc.)
        cache_managers = [sessions[user_id]._cache_manager for user_id in user_ids]
        for i, cm1 in enumerate(cache_managers):
            for j, cm2 in enumerate(cache_managers):
                if i != j:
                    self.assertIsNot(cm1, cm2, f"Cache managers should be different for different users")

    def test_concurrent_cache_operations(self):
        """Test concurrent cache operations across multiple sessions."""
        # Create sessions
        sessions = {}
        for user_config in self.user_configs.values():
            session = self.session_manager.get_or_create_session(user_config)
            sessions[user_config.user_id] = session

        results = []
        errors = []

        def cache_operation_worker(user_id: str, operation: str):
            """Worker function to perform cache operations."""
            try:
                session = sessions[user_id]

                if operation == "load":
                    success = session.load_cache()
                    results.append((user_id, "load", success))
                elif operation == "save":
                    success = session.save_cache()
                    results.append((user_id, "save", success))
                elif operation == "status":
                    status = session.get_cache_status()
                    results.append((user_id, "status", status))

                return True
            except Exception as e:
                errors.append((user_id, operation, str(e)))
                return False

        # Perform concurrent cache operations
        operations = ["load", "save", "status"]
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []

            # Submit multiple operations per user
            for user_id in self.user_configs.keys():
                for operation in operations:
                    future = executor.submit(cache_operation_worker, user_id, operation)
                    futures.append(future)

            # Wait for all to complete
            for future in as_completed(futures):
                future.result()

        # Verify results
        expected_operations = len(self.user_configs) * len(operations)
        self.assertEqual(len(results), expected_operations, f"Should have {expected_operations} operation results")
        self.assertEqual(len(errors), 0, "No errors should occur during concurrent operations")

        # Verify cache isolation - operations on one user's cache shouldn't affect others
        status_results = [result for result in results if result[1] == "status"]
        for result in status_results:
            user_id, operation, status = result
            # Each user's cache status should be independent
            self.assertIsInstance(status, dict, f"Cache status should be a dict for {user_id}")

    def test_session_lifecycle_concurrency(self):
        """Test session lifecycle operations under concurrent load."""
        results = []
        errors = []

        def lifecycle_worker(user_config: UserConfig, iterations: int):
            """Worker function to test session lifecycle."""
            try:
                user_id = user_config.user_id

                for i in range(iterations):
                    # Create/get session
                    session = self.session_manager.get_or_create_session(user_config)
                    session_id = session.session_id

                    # Perform some operations
                    cache_status = session.get_cache_status()
                    current_progress = session.get_current_progress()

                    # Simulate some processing time
                    time.sleep(0.001)

                    results.append((user_id, i, session_id, "success"))

                return True
            except Exception as e:
                errors.append((user_config.user_id, str(e)))
                return False

        # Test concurrent lifecycle operations
        iterations_per_user = 3
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []

            for user_config in self.user_configs.values():
                future = executor.submit(lifecycle_worker, user_config, iterations_per_user)
                futures.append(future)

            # Wait for all to complete
            for future in as_completed(futures):
                future.result()

        # Verify results
        expected_results = len(self.user_configs) * iterations_per_user
        self.assertEqual(len(results), expected_results, f"Should have {expected_results} lifecycle results")
        self.assertEqual(len(errors), 0, "No errors should occur during lifecycle operations")

        # Verify session consistency - same user should get same session across iterations
        user_sessions = {}
        for user_id, iteration, session_id, status in results:
            if user_id not in user_sessions:
                user_sessions[user_id] = session_id
            else:
                self.assertEqual(user_sessions[user_id], session_id,
                               f"User {user_id} should get same session across iterations")

    def test_session_cleanup_concurrency(self):
        """Test concurrent session cleanup."""
        # First create sessions
        sessions = {}
        for user_config in self.user_configs.values():
            session = self.session_manager.get_or_create_session(user_config)
            sessions[user_config.user_id] = session

        results = []
        errors = []

        def cleanup_worker(user_id: str):
            """Worker function to clean up session."""
            try:
                self.session_manager.cleanup_user_session(user_id)
                results.append((user_id, "cleanup_success"))
                return True
            except Exception as e:
                errors.append((user_id, str(e)))
                return False

        # Clean up sessions concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []

            for user_id in list(sessions.keys()):
                future = executor.submit(cleanup_worker, user_id)
                futures.append(future)

            # Wait for all to complete
            for future in as_completed(futures):
                future.result()

        # Verify results
        self.assertEqual(len(results), len(self.user_configs), "All sessions should be cleaned up")
        self.assertEqual(len(errors), 0, "No errors should occur during cleanup")

        # Verify sessions are actually cleaned up
        self.assertEqual(len(self.session_manager._sessions), 0, "No sessions should remain after cleanup")
        self.assertEqual(len(self.session_manager._session_times), 0, "No session times should remain after cleanup")

        # Verify get_session returns None for cleaned up users
        for user_id in sessions.keys():
            session = self.session_manager.get_session(user_id)
            self.assertIsNone(session, f"Session for {user_id} should be None after cleanup")

    @patch('super_starter_suite.rag_indexing.rag_generation_session.datetime')
    def test_session_timeout_concurrency(self, mock_datetime):
        """Test session timeout handling under concurrent load."""
        # Mock datetime to control time
        fixed_time = time.time()
        mock_datetime.now.return_value = Mock()
        mock_datetime.now.return_value.timestamp.return_value = fixed_time

        # Create sessions
        sessions = {}
        for user_config in self.user_configs.values():
            session = self.session_manager.get_or_create_session(user_config)
            sessions[user_config.user_id] = session

        # Simulate time passing (beyond timeout)
        expired_time = fixed_time + self.session_manager._session_timeout + 1
        mock_datetime.now.return_value.timestamp.return_value = expired_time

        results = []
        errors = []

        def timeout_worker(user_config: UserConfig):
            """Worker function to test timeout handling."""
            try:
                user_id = user_config.user_id

                # Try to get session (should create new one since old is expired)
                new_session = self.session_manager.get_or_create_session(user_config)

                # Verify it's a different session
                old_session = sessions[user_id]
                is_different = new_session.session_id != old_session.session_id

                results.append((user_id, new_session.session_id, is_different))
                return True
            except Exception as e:
                errors.append((user_config.user_id, str(e)))
                return False

        # Test concurrent timeout handling
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []

            for user_config in self.user_configs.values():
                future = executor.submit(timeout_worker, user_config)
                futures.append(future)

            # Wait for all to complete
            for future in as_completed(futures):
                future.result()

        # Verify results
        self.assertEqual(len(results), len(self.user_configs), "All timeout operations should succeed")
        self.assertEqual(len(errors), 0, "No errors should occur during timeout handling")

        # Verify new sessions were created (different session IDs)
        for user_id, new_session_id, is_different in results:
            self.assertTrue(is_different, f"User {user_id} should get a new session after timeout")


class TestSessionStressTest(unittest.TestCase):
    """Stress test for session handling under high concurrency."""

    def setUp(self):
        """Set up stress test environment."""
        self.session_manager = RAGSessionManager()
        self.session_manager._sessions.clear()
        self.session_manager._session_times.clear()

        # Create many mock user configurations
        self.user_configs = {}
        for i in range(20):  # More users for stress test
            user_id = f"stress_user_{i}"
            user_config = Mock(spec=UserConfig)
            user_config.user_id = user_id
            user_config.my_rag = Mock()
            user_config.my_rag.rag_type = "TEST_RAG"
            user_config.get_user_setting = Mock(return_value=["TEST_RAG"])
            self.user_configs[user_id] = user_config

    def tearDown(self):
        """Clean up after stress tests."""
        for user_id in list(self.session_manager._sessions.keys()):
            self.session_manager.cleanup_user_session(user_id)

    def test_high_concurrency_session_operations(self):
        """Test session operations under high concurrency."""
        num_operations = 100
        results = []
        errors = []

        def stress_worker(user_config: UserConfig, operation_id: int):
            """Worker function for stress testing."""
            try:
                user_id = user_config.user_id

                # Perform multiple session operations
                for i in range(5):  # Multiple operations per worker
                    session = self.session_manager.get_or_create_session(user_config)
                    status = session.get_cache_status()
                    progress = session.get_current_progress()

                    results.append((user_id, operation_id, i, "success"))

                return True
            except Exception as e:
                errors.append((user_config.user_id, operation_id, str(e)))
                return False

        # Run stress test with high concurrency
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = []

            # Submit many operations
            operation_id = 0
            for _ in range(num_operations):
                for user_config in list(self.user_configs.values())[:10]:  # Use subset for manageability
                    future = executor.submit(stress_worker, user_config, operation_id)
                    futures.append(future)
                    operation_id += 1

            # Wait for completion (with timeout)
            completed = 0
            for future in as_completed(futures, timeout=30):
                try:
                    future.result(timeout=10)
                    completed += 1
                except Exception as e:
                    errors.append(("timeout", str(e)))

        # Verify results
        self.assertGreater(completed, 0, "Some operations should complete successfully")
        self.assertLess(len(errors), num_operations * 0.1, "Error rate should be less than 10%")

        # Verify session manager integrity
        self.assertLessEqual(len(self.session_manager._sessions), len(self.user_configs),
                           "Should not have more sessions than users")


if __name__ == '__main__':
    unittest.main()
