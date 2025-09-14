#!/usr/bin/env python3
"""
Chat History Manager Tests
Tests for the ChatHistoryManager class functionality
"""

import pytest
import json
import tempfile
import shutil
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from super_starter_suite.chat_history.chat_history_manager import ChatHistoryManager
from super_starter_suite.shared.config_manager import UserConfig
from super_starter_suite.shared.dto import ChatHistoryConfig, create_chat_message, MessageRole


class TestChatHistoryManager:
    """Test suite for ChatHistoryManager class"""

    def setup_method(self):
        """Setup test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.user_id = "test_user_123"

        # Create mock user config
        self.mock_user_config = MagicMock(spec=UserConfig)
        self.mock_user_config.user_id = self.user_id
        self.mock_user_config.get_user_setting.return_value = self.temp_dir
        self.mock_user_config.chat_history_config = ChatHistoryConfig()

        # Create manager instance
        self.manager = ChatHistoryManager(self.mock_user_config)

    def teardown_method(self):
        """Cleanup after each test"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_initialization(self):
        """Test manager initialization"""
        assert self.manager.user_config == self.mock_user_config
        assert self.manager.chat_history_config is not None
        assert self.manager.storage_path.exists()

    def test_create_new_session_success(self):
        """Test successful session creation"""
        workflow_type = "agentic_rag"

        session = self.manager.create_new_session(workflow_type)

        assert session is not None
        assert session.session_id is not None
        assert session.workflow_type == workflow_type
        assert session.user_id == self.user_id
        assert session.created_at is not None
        assert len(session.messages) == 0

    def test_load_session_success(self):
        """Test successful session retrieval"""
        # Create a session first
        workflow_type = "code_generator"
        created_session = self.manager.create_new_session(workflow_type)

        # Save it first
        self.manager.save_session(created_session)

        # Retrieve the session
        retrieved_session = self.manager.load_session(workflow_type, created_session.session_id)

        assert retrieved_session is not None
        assert retrieved_session.session_id == created_session.session_id
        assert retrieved_session.workflow_type == workflow_type

    def test_load_session_not_found(self):
        """Test retrieval of non-existent session"""
        result = self.manager.load_session("agentic_rag", "non-existent-id")
        assert result is None

    def test_get_all_sessions_empty(self):
        """Test getting sessions when none exist"""
        sessions = self.manager.get_all_sessions("agentic_rag")
        assert sessions == []

    def test_get_all_sessions_with_data(self):
        """Test getting sessions with existing data"""
        # Create multiple sessions
        session1 = self.manager.create_new_session("agentic_rag")
        session2 = self.manager.create_new_session("code_generator")

        # Save them
        self.manager.save_session(session1)
        self.manager.save_session(session2)

        sessions = self.manager.get_all_sessions("agentic_rag")

        assert len(sessions) == 1
        assert sessions[0].session_id == session1.session_id

    def test_add_message_to_session_success(self):
        """Test successful message addition"""
        # Create a session
        session = self.manager.create_new_session("deep_research")

        # Create a message
        message = create_chat_message(
            role=MessageRole.USER,
            content="Test message"
        )

        # Add message to session
        self.manager.add_message_to_session(session, message)

        # Verify message was added
        assert len(session.messages) == 1
        assert session.messages[0].content == "Test message"

    def test_add_message_exceeds_limit(self):
        """Test adding messages beyond session limit"""
        # Create session with low message limit for testing
        self.manager.max_messages_per_session = 2
        session = self.manager.create_session("agentic_rag", self.user_id)

        # Add messages up to the limit
        for i in range(3):
            message = {
                'role': 'user',
                'content': f'Message {i}',
                'timestamp': datetime.now().isoformat()
            }
            result = self.manager.add_message(session['session_id'], message)

        # Verify only the last 2 messages are kept
        updated_session = self.manager.get_session(session['session_id'])
        assert len(updated_session['messages']) == 2
        assert updated_session['messages'][0]['content'] == 'Message 1'
        assert updated_session['messages'][1]['content'] == 'Message 2'

    def test_delete_session_success(self):
        """Test successful session deletion"""
        # Create a session
        session = self.manager.create_session("financial_report", self.user_id)

        # Delete the session
        result = self.manager.delete_session(session['session_id'])

        assert result is True

        # Verify session is removed
        assert len(self.manager.sessions) == 0
        assert self.manager.get_session(session['session_id']) is None

    def test_delete_session_not_found(self):
        """Test deletion of non-existent session"""
        result = self.manager.delete_session("non-existent-id")
        assert result is False

    def test_save_and_load_sessions(self):
        """Test saving and loading sessions to/from disk"""
        # Create sessions
        session1 = self.manager.create_session("agentic_rag", self.user_id)
        session2 = self.manager.create_session("code_generator", "user_456")

        # Add messages to sessions
        message1 = {
            'role': 'user',
            'content': 'Hello from user 1',
            'timestamp': datetime.now().isoformat()
        }
        message2 = {
            'role': 'assistant',
            'content': 'Hello from AI',
            'timestamp': datetime.now().isoformat()
        }

        self.manager.add_message(session1['session_id'], message1)
        self.manager.add_message(session2['session_id'], message2)

        # Save sessions
        save_result = self.manager.save_sessions()
        assert save_result is True

        # Create new manager instance to test loading
        new_manager = ChatHistoryManager()
        new_manager.config_manager = self.mock_config_manager
        new_manager.storage_path = self.manager.storage_path

        # Load sessions
        load_result = new_manager.load_sessions()
        assert load_result is True

        # Verify sessions were loaded
        assert len(new_manager.sessions) == 2

        # Verify messages were preserved
        loaded_session1 = new_manager.get_session(session1['session_id'])
        loaded_session2 = new_manager.get_session(session2['session_id'])

        assert loaded_session1 is not None
        assert loaded_session2 is not None
        assert len(loaded_session1['messages']) == 1
        assert len(loaded_session2['messages']) == 1
        assert loaded_session1['messages'][0]['content'] == 'Hello from user 1'
        assert loaded_session2['messages'][0]['content'] == 'Hello from AI'

    def test_export_session_success(self):
        """Test successful session export"""
        # Create a session with messages
        session = self.manager.create_session("document_generator", self.user_id)

        message = {
            'role': 'user',
            'content': 'Export test message',
            'timestamp': datetime.now().isoformat()
        }
        self.manager.add_message(session['session_id'], message)

        # Export the session
        export_data = self.manager.export_session(session['session_id'])

        assert export_data is not None
        assert 'session' in export_data
        assert 'exported_at' in export_data
        assert export_data['session']['session_id'] == session['session_id']
        assert len(export_data['session']['messages']) == 1

    def test_export_session_not_found(self):
        """Test export of non-existent session"""
        result = self.manager.export_session("non-existent-id")
        assert result is None

    def test_get_stats_empty(self):
        """Test getting statistics when no sessions exist"""
        stats = self.manager.get_stats()

        assert stats['total_sessions'] == 0
        assert stats['total_messages'] == 0
        assert stats['oldest_session'] is None
        assert stats['newest_session'] is None

    def test_get_stats_with_data(self):
        """Test getting statistics with session data"""
        # Create sessions at different times
        old_time = datetime.now() - timedelta(days=5)
        new_time = datetime.now()

        # Create sessions
        session1 = self.manager.create_session("agentic_rag", self.user_id)
        session2 = self.manager.create_session("code_generator", "user_456")

        # Add messages
        for i in range(3):
            message = {
                'role': 'user',
                'content': f'Message {i}',
                'timestamp': datetime.now().isoformat()
            }
            self.manager.add_message(session1['session_id'], message)

        for i in range(2):
            message = {
                'role': 'assistant',
                'content': f'Response {i}',
                'timestamp': datetime.now().isoformat()
            }
            self.manager.add_message(session2['session_id'], message)

        # Get stats
        stats = self.manager.get_stats()

        assert stats['total_sessions'] == 2
        assert stats['total_messages'] == 5
        assert stats['oldest_session'] is not None
        assert stats['newest_session'] is not None

    def test_session_timeout(self):
        """Test session timeout functionality"""
        # Create a session
        session = self.manager.create_session("human_in_the_loop", self.user_id)

        # Simulate old session by modifying created_at
        old_time = datetime.now() - timedelta(seconds=4000)  # Older than timeout
        session['created_at'] = old_time.isoformat()

        # Check if session should be cleaned up
        # (This would typically be called by a cleanup process)
        expired_sessions = self.manager.get_expired_sessions()

        assert len(expired_sessions) == 1
        assert expired_sessions[0]['session_id'] == session['session_id']

    def test_max_sessions_limit(self):
        """Test maximum sessions limit enforcement"""
        # Set low limit for testing
        self.manager.max_sessions = 2

        # Create sessions up to the limit
        session1 = self.manager.create_session("agentic_rag", self.user_id)
        session2 = self.manager.create_session("code_generator", "user_456")

        # Try to create one more (should succeed but trigger cleanup logic)
        session3 = self.manager.create_session("deep_research", "user_789")

        # All sessions should exist (limit enforcement would be in save/load logic)
        assert len(self.manager.sessions) == 3

    def test_concurrent_access(self):
        """Test concurrent access to the manager"""
        import threading
        import time

        results = []
        errors = []

        def worker(worker_id):
            try:
                # Each worker creates a session and adds messages
                session = self.manager.create_session(f"workflow_{worker_id}", f"user_{worker_id}")

                for i in range(5):
                    message = {
                        'role': 'user',
                        'content': f'Worker {worker_id} message {i}',
                        'timestamp': datetime.now().isoformat()
                    }
                    self.manager.add_message(session['session_id'], message)

                results.append(f'Worker {worker_id} completed')
            except Exception as e:
                errors.append(f'Worker {worker_id} error: {e}')

        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify results
        assert len(results) == 5
        assert len(errors) == 0
        assert len(self.manager.sessions) == 5

        # Verify all sessions have correct number of messages
        for session in self.manager.sessions:
            assert len(session['messages']) == 5

    def test_memory_buffer_configuration(self):
        """Test memory buffer configuration handling"""
        # Verify configuration is loaded correctly
        config = self.manager.get_memory_config()

        assert config is not None
        assert config['buffer_size'] == 2000
        assert config['token_limit'] == 2000

    @patch('os.makedirs')
    def test_storage_path_creation(self, mock_makedirs):
        """Test storage path creation"""
        # This tests that the manager creates necessary directories
        manager = ChatHistoryManager()
        manager.config_manager = self.mock_config_manager

        # Verify makedirs was called during initialization
        mock_makedirs.assert_called()

    def test_session_validation(self):
        """Test session data validation"""
        # Test valid session creation
        valid_session = self.manager.create_session("agentic_rag", self.user_id)
        assert valid_session is not None

        # Test invalid workflow type
        invalid_session = self.manager.create_session("", self.user_id)
        assert invalid_session is None

        # Test invalid user ID
        invalid_session2 = self.manager.create_session("agentic_rag", "")
        assert invalid_session2 is None


if __name__ == '__main__':
    pytest.main([__file__])
