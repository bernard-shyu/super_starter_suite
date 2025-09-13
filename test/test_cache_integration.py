"""
Cache Integration Test

Tests the cache design pattern implementation including:
- Cache persistence across requests
- User isolation
- Cache lifecycle (load/save)
- Error handling and recovery
"""

import pytest
import asyncio
from unittest.mock import Mock, patch
from super_starter_suite.shared.config_manager import UserConfig
from super_starter_suite.rag_indexing.generate_ui_cache import (
    GenerateUICacheManager,
    get_cache_manager,
    _cache_managers
)


class TestCacheIntegration:
    """Test cache integration functionality"""

    def setup_method(self):
        """Setup test environment"""
        # Clear global cache managers before each test
        _cache_managers.clear()

        # Create mock user config
        self.mock_config = Mock(spec=UserConfig)
        self.mock_config.user_id = "test_user"
        self.mock_config.my_rag.rag_root = "/tmp/test_rag"
        self.mock_config.my_rag.rag_type = "TEST_RAG"
        self.mock_config.my_rag.data_path = "/tmp/test_rag/data.TEST_RAG"
        self.mock_config.my_rag.storage_path = "/tmp/test_rag/storage.TEST_RAG"

    def teardown_method(self):
        """Cleanup after each test"""
        _cache_managers.clear()

    def test_cache_manager_creation(self):
        """Test cache manager is created correctly"""
        cache_manager = get_cache_manager(self.mock_config)

        assert isinstance(cache_manager, GenerateUICacheManager)
        assert cache_manager.user_config == self.mock_config
        assert not cache_manager.is_loaded
        assert cache_manager.cache == {}
        assert cache_manager.last_updated is None

    def test_cache_manager_singleton_per_user(self):
        """Test that same user gets same cache manager instance"""
        cache_manager1 = get_cache_manager(self.mock_config)
        cache_manager2 = get_cache_manager(self.mock_config)

        assert cache_manager1 is cache_manager2

    def test_cache_manager_isolation_between_users(self):
        """Test that different users get different cache managers"""
        # Create second user config
        mock_config2 = Mock(spec=UserConfig)
        mock_config2.user_id = "test_user_2"
        mock_config2.my_rag.rag_root = "/tmp/test_rag_2"

        cache_manager1 = get_cache_manager(self.mock_config)
        cache_manager2 = get_cache_manager(mock_config2)

        assert cache_manager1 is not cache_manager2
        assert cache_manager1.user_config.user_id == "test_user"
        assert cache_manager2.user_config.user_id == "test_user_2"

    def test_cache_data_operations(self):
        """Test basic cache data operations"""
        cache_manager = get_cache_manager(self.mock_config)

        # Test cache data storage
        test_data = {"test_key": "test_value", "timestamp": "2025-01-01T00:00:00"}
        cache_manager.cache["TEST_RAG"] = test_data

        assert cache_manager.cache["TEST_RAG"] == test_data

        # Test cache data retrieval
        retrieved_data = cache_manager.get_cached_metadata("TEST_RAG")
        assert retrieved_data == test_data

        # Test non-existent data
        non_existent = cache_manager.get_cached_metadata("NON_EXISTENT")
        assert non_existent is None

    def test_cache_update_operations(self):
        """Test cache update operations"""
        cache_manager = get_cache_manager(self.mock_config)

        # Test update cached metadata
        test_data = {"files": [], "total_files": 0}
        success = cache_manager.update_cached_metadata("TEST_RAG", test_data)

        assert success
        assert cache_manager.cache["TEST_RAG"] == test_data
        assert cache_manager.last_updated is not None

        # Test update when cache not loaded (should fail gracefully)
        cache_manager.is_loaded = False
        success = cache_manager.update_cached_metadata("TEST_RAG_2", test_data)
        assert not success  # Should fail when cache not loaded

    @patch('super_starter_suite.rag_indexing.generate_ui_cache.get_metadata_file_path')
    @patch('pathlib.Path.exists')
    @patch('builtins.open')
    @patch('json.load')
    def test_cache_load_success(self, mock_json_load, mock_open, mock_exists, mock_get_path):
        """Test successful cache loading"""
        # Setup mocks
        mock_path = Mock()
        mock_get_path.return_value = mock_path
        mock_exists.return_value = True
        mock_json_load.return_value = {"TEST_RAG": {"files": []}}

        cache_manager = get_cache_manager(self.mock_config)
        success = cache_manager.load_metadata_cache()

        assert success
        assert cache_manager.is_loaded
        assert cache_manager.cache == {"TEST_RAG": {"files": []}}
        assert cache_manager.last_updated is not None

    @patch('super_starter_suite.rag_indexing.generate_ui_cache.get_metadata_file_path')
    @patch('pathlib.Path.exists')
    def test_cache_load_no_file(self, mock_exists, mock_get_path):
        """Test cache loading when no file exists"""
        # Setup mocks
        mock_path = Mock()
        mock_get_path.return_value = mock_path
        mock_exists.return_value = False

        cache_manager = get_cache_manager(self.mock_config)
        success = cache_manager.load_metadata_cache()

        assert success
        assert cache_manager.is_loaded
        assert cache_manager.cache == {}  # Empty cache
        assert cache_manager.last_updated is not None

    @patch('super_starter_suite.rag_indexing.generate_ui_cache.get_metadata_file_path')
    @patch('pathlib.Path.exists')
    @patch('builtins.open')
    @patch('json.load')
    def test_cache_load_error_handling(self, mock_json_load, mock_open, mock_exists, mock_get_path):
        """Test cache loading error handling"""
        # Setup mocks to cause JSON error
        mock_path = Mock()
        mock_get_path.return_value = mock_path
        mock_exists.return_value = True
        mock_json_load.side_effect = ValueError("Invalid JSON")

        cache_manager = get_cache_manager(self.mock_config)
        success = cache_manager.load_metadata_cache()

        assert not success
        assert not cache_manager.is_loaded
        assert cache_manager.cache == {}

    @patch('super_starter_suite.rag_indexing.generate_ui_cache.save_data_metadata')
    def test_cache_save_success(self, mock_save_data):
        """Test successful cache saving"""
        # Setup mock
        mock_save_data.return_value = True

        cache_manager = get_cache_manager(self.mock_config)
        cache_manager.is_loaded = True
        cache_manager.cache = {"TEST_RAG": {"files": []}}

        success = cache_manager.save_metadata_cache()

        assert success
        mock_save_data.assert_called_once()

    @patch('super_starter_suite.rag_indexing.generate_ui_cache.save_data_metadata')
    def test_cache_save_not_loaded(self, mock_save_data):
        """Test cache save when cache not loaded"""
        cache_manager = get_cache_manager(self.mock_config)
        cache_manager.is_loaded = False

        success = cache_manager.save_metadata_cache()

        assert not success
        mock_save_data.assert_not_called()

    def test_cache_cleanup(self):
        """Test cache cleanup functionality"""
        from super_starter_suite.rag_indexing.generate_ui_cache import cleanup_cache_manager

        # Create cache manager
        cache_manager = get_cache_manager(self.mock_config)
        assert "test_user" in _cache_managers

        # Cleanup
        cleanup_cache_manager("test_user")

        assert "test_user" not in _cache_managers

    def test_cache_cleanup_nonexistent_user(self):
        """Test cleanup of non-existent user"""
        from super_starter_suite.rag_indexing.generate_ui_cache import cleanup_cache_manager

        # Should not raise error
        cleanup_cache_manager("non_existent_user")


if __name__ == "__main__":
    # Run basic tests
    test = TestCacheIntegration()

    try:
        print("Running cache integration tests...")

        test.setup_method()
        test.test_cache_manager_creation()
        print("✅ Cache manager creation test passed")

        test.test_cache_manager_singleton_per_user()
        print("✅ Cache manager singleton test passed")

        test.test_cache_manager_isolation_between_users()
        print("✅ Cache manager isolation test passed")

        test.test_cache_data_operations()
        print("✅ Cache data operations test passed")

        test.test_cache_update_operations()
        print("✅ Cache update operations test passed")

        test.test_cache_cleanup()
        print("✅ Cache cleanup test passed")

        print("\n🎉 All cache integration tests passed!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise
