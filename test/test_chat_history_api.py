#!/usr/bin/env python3
"""
Chat History API Tests
Tests for the chat history REST API endpoints
"""

import pytest
import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

# Import the main FastAPI app
from super_starter_suite.main import app
from super_starter_suite.chat_history.api import ChatHistoryAPI
from super_starter_suite.chat_history.chat_history_manager import ChatHistoryManager


class TestChatHistoryAPI:
    """Test suite for Chat History API endpoints"""

    def setup_method(self):
        """Setup test fixtures"""
        self.client = TestClient(app)
        self.api = ChatHistoryAPI()
        self.test_user_id = "test_user_123"
        self.test_session_id = str(uuid.uuid4())

        # Mock configuration
        self.mock_config = {
            'CHAT_HISTORY': {
                'ENABLED': True,
                'STORAGE_PATH': 'test_chat_history',
                'MAX_SESSIONS': 100,
                'MAX_MESSAGES_PER_SESSION': 50
            }
        }

    def teardown_method(self):
        """Cleanup after each test"""
        # Clean up any test files created
        pass

    @patch('super_starter_suite.chat_history.api.ChatHistoryManager')
    def test_get_sessions_success(self, mock_manager_class):
        """Test successful retrieval of chat sessions"""
        # Mock the manager and its methods
        mock_manager = MagicMock()
        mock_sessions = [
            {
                'session_id': self.test_session_id,
                'workflow_type': 'agentic_rag',
                'created_at': datetime.now().isoformat(),
                'messages': [
                    {
                        'role': 'user',
                        'content': 'Hello',
                        'timestamp': datetime.now().isoformat()
                    }
                ]
            }
        ]
        mock_manager.get_sessions.return_value = mock_sessions
        mock_manager_class.return_value = mock_manager

        # Make request
        response = self.client.get('/api/chat_history/sessions')

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert 'sessions' in data
        assert len(data['sessions']) == 1
        assert data['sessions'][0]['session_id'] == self.test_session_id

    @patch('super_starter_suite.chat_history.api.ChatHistoryManager')
    def test_get_sessions_empty(self, mock_manager_class):
        """Test retrieval when no sessions exist"""
        mock_manager = MagicMock()
        mock_manager.get_sessions.return_value = []
        mock_manager_class.return_value = mock_manager

        response = self.client.get('/api/chat_history/sessions')

        assert response.status_code == 200
        data = response.json()
        assert data['sessions'] == []

    @patch('super_starter_suite.chat_history.api.ChatHistoryManager')
    def test_get_session_success(self, mock_manager_class):
        """Test successful retrieval of a specific session"""
        mock_manager = MagicMock()
        mock_session = {
            'session_id': self.test_session_id,
            'workflow_type': 'code_generator',
            'created_at': datetime.now().isoformat(),
            'messages': []
        }
        mock_manager.get_session.return_value = mock_session
        mock_manager_class.return_value = mock_manager

        response = self.client.get(f'/api/chat_history/sessions/{self.test_session_id}')

        assert response.status_code == 200
        data = response.json()
        assert data['session_id'] == self.test_session_id
        assert data['workflow_type'] == 'code_generator'

    @patch('super_starter_suite.chat_history.api.ChatHistoryManager')
    def test_get_session_not_found(self, mock_manager_class):
        """Test retrieval of non-existent session"""
        mock_manager = MagicMock()
        mock_manager.get_session.return_value = None
        mock_manager_class.return_value = mock_manager

        response = self.client.get(f'/api/chat_history/sessions/{self.test_session_id}')

        assert response.status_code == 404
        data = response.json()
        assert 'detail' in data

    @patch('super_starter_suite.chat_history.api.ChatHistoryManager')
    def test_create_session_success(self, mock_manager_class):
        """Test successful session creation"""
        mock_manager = MagicMock()
        new_session = {
            'session_id': self.test_session_id,
            'workflow_type': 'deep_research',
            'created_at': datetime.now().isoformat(),
            'messages': []
        }
        mock_manager.create_session.return_value = new_session
        mock_manager_class.return_value = mock_manager

        request_data = {
            'workflow_type': 'deep_research',
            'user_id': self.test_user_id
        }

        response = self.client.post('/api/chat_history/sessions', json=request_data)

        assert response.status_code == 201
        data = response.json()
        assert data['session_id'] == self.test_session_id
        assert data['workflow_type'] == 'deep_research'

    def test_create_session_invalid_data(self):
        """Test session creation with invalid data"""
        # Missing workflow_type
        response = self.client.post('/api/chat_history/sessions', json={})
        assert response.status_code == 422

        # Invalid workflow_type
        response = self.client.post('/api/chat_history/sessions', json={
            'workflow_type': 'invalid_workflow'
        })
        assert response.status_code == 422

    @patch('super_starter_suite.chat_history.api.ChatHistoryManager')
    def test_add_message_success(self, mock_manager_class):
        """Test successful message addition to session"""
        mock_manager = MagicMock()
        mock_manager.add_message.return_value = True
        mock_manager_class.return_value = mock_manager

        message_data = {
            'role': 'user',
            'content': 'Test message',
            'timestamp': datetime.now().isoformat()
        }

        response = self.client.post(
            f'/api/chat_history/sessions/{self.test_session_id}/messages',
            json=message_data
        )

        assert response.status_code == 201
        mock_manager.add_message.assert_called_once()

    @patch('super_starter_suite.chat_history.api.ChatHistoryManager')
    def test_add_message_session_not_found(self, mock_manager_class):
        """Test message addition to non-existent session"""
        mock_manager = MagicMock()
        mock_manager.add_message.return_value = False
        mock_manager_class.return_value = mock_manager

        message_data = {
            'role': 'user',
            'content': 'Test message'
        }

        response = self.client.post(
            f'/api/chat_history/sessions/{self.test_session_id}/messages',
            json=message_data
        )

        assert response.status_code == 404

    @patch('super_starter_suite.chat_history.api.ChatHistoryManager')
    def test_delete_session_success(self, mock_manager_class):
        """Test successful session deletion"""
        mock_manager = MagicMock()
        mock_manager.delete_session.return_value = True
        mock_manager_class.return_value = mock_manager

        response = self.client.delete(f'/api/chat_history/sessions/{self.test_session_id}')

        assert response.status_code == 204
        mock_manager.delete_session.assert_called_once_with(self.test_session_id)

    @patch('super_starter_suite.chat_history.api.ChatHistoryManager')
    def test_delete_session_not_found(self, mock_manager_class):
        """Test deletion of non-existent session"""
        mock_manager = MagicMock()
        mock_manager.delete_session.return_value = False
        mock_manager_class.return_value = mock_manager

        response = self.client.delete(f'/api/chat_history/sessions/{self.test_session_id}')

        assert response.status_code == 404

    @patch('super_starter_suite.chat_history.api.ChatHistoryManager')
    def test_export_session_success(self, mock_manager_class):
        """Test successful session export"""
        mock_manager = MagicMock()
        export_data = {
            'session': {
                'session_id': self.test_session_id,
                'workflow_type': 'agentic_rag',
                'messages': []
            },
            'exported_at': datetime.now().isoformat()
        }
        mock_manager.export_session.return_value = export_data
        mock_manager_class.return_value = mock_manager

        response = self.client.get(f'/api/chat_history/sessions/{self.test_session_id}/export')

        assert response.status_code == 200
        data = response.json()
        assert 'session' in data
        assert 'exported_at' in data
        assert data['session']['session_id'] == self.test_session_id

    @patch('super_starter_suite.chat_history.api.ChatHistoryManager')
    def test_get_session_stats_success(self, mock_manager_class):
        """Test successful retrieval of session statistics"""
        mock_manager = MagicMock()
        stats = {
            'total_sessions': 5,
            'total_messages': 127,
            'oldest_session': (datetime.now() - timedelta(days=7)).isoformat(),
            'newest_session': datetime.now().isoformat()
        }
        mock_manager.get_stats.return_value = stats
        mock_manager_class.return_value = mock_manager

        response = self.client.get('/api/chat_history/stats')

        assert response.status_code == 200
        data = response.json()
        assert data['total_sessions'] == 5
        assert data['total_messages'] == 127
        assert 'oldest_session' in data
        assert 'newest_session' in data

    def test_api_disabled(self):
        """Test API behavior when chat history is disabled"""
        # This would require mocking the configuration to disable chat history
        # For now, this is a placeholder test
        pass

    @patch('super_starter_suite.chat_history.api.ChatHistoryManager')
    def test_concurrent_session_access(self, mock_manager_class):
        """Test concurrent access to the same session"""
        mock_manager = MagicMock()
        mock_manager.add_message.return_value = True
        mock_manager_class.return_value = mock_manager

        # Simulate concurrent requests
        message_data = {
            'role': 'user',
            'content': 'Concurrent message',
            'timestamp': datetime.now().isoformat()
        }

        responses = []
        for i in range(5):
            response = self.client.post(
                f'/api/chat_history/sessions/{self.test_session_id}/messages',
                json=message_data
            )
            responses.append(response)

        # All requests should succeed
        for response in responses:
            assert response.status_code == 201

        # Verify the method was called the correct number of times
        assert mock_manager.add_message.call_count == 5


if __name__ == '__main__':
    pytest.main([__file__])
