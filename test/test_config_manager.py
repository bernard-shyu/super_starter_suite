import pytest
from fastapi.testclient import TestClient
from main import app, config_manager
import os
from pathlib import Path
import toml

# Create a test client
client = TestClient(app)

# Test configuration files
TEST_CONFIG_DIR = Path(__file__).parent.parent / "config"
TEST_USER_STATE_FILE = TEST_CONFIG_DIR / "user_state.toml"
TEST_SYSTEM_CONFIG_FILE = TEST_CONFIG_DIR / "system_config.toml"
TEST_USER_CONFIG_FILE = TEST_CONFIG_DIR / "settings.TestUser.toml"

@pytest.fixture
def setup_test_config():
    # Backup original files
    if TEST_USER_STATE_FILE.exists():
        os.rename(TEST_USER_STATE_FILE, TEST_USER_STATE_FILE.with_suffix(".bak"))
    if TEST_USER_CONFIG_FILE.exists():
        os.rename(TEST_USER_CONFIG_FILE, TEST_USER_CONFIG_FILE.with_suffix(".bak"))

    # Create test user state file
    test_user_state = {
        "USER_MAPPING": {
            "127.0.0.1": "TestUser",
            "testclient": "TestUser"
        },
        "CURR_WORKFLOW": {
            "TestUser": "agentic_rag"
        }
    }
    with open(TEST_USER_STATE_FILE, "w") as f:
        toml.dump(test_user_state, f)

    # Create test user config file
    test_user_config = {
        "USER_PREFERENCES": {
            "USER_RAG_ROOT": "/test/rag/root",
            "THEME": "dark"
        },
        "GENERATE": {
            "METHOD": "TestMethod"
        }
    }
    with open(TEST_USER_CONFIG_FILE, "w") as f:
        toml.dump(test_user_config, f)

    # Reload the config manager to ensure it picks up the test files
    config_manager.reload_user_state()

    yield

    # Restore original files
    if TEST_USER_STATE_FILE.with_suffix(".bak").exists():
        os.rename(TEST_USER_STATE_FILE.with_suffix(".bak"), TEST_USER_STATE_FILE)
    if TEST_USER_CONFIG_FILE.with_suffix(".bak").exists():
        os.rename(TEST_USER_CONFIG_FILE.with_suffix(".bak"), TEST_USER_CONFIG_FILE)

def test_user_identification(setup_test_config):
    # Test user identification from IP
    response = client.post("/api/associate_user", json={"user_id": "TestUser"})
    assert response.status_code == 200
    assert "User TestUser associated with IP" in response.json()["message"]

    # Test getting user settings
    headers = {"X-Forwarded-For": "127.0.0.1"}
    response = client.get("/api/settings", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"USER_RAG_ROOT": "/test/rag/root", "THEME": "dark"}

    # Also test with the actual test client IP
    response = client.get("/api/settings")
    assert response.status_code == 200
    assert "USER_RAG_ROOT" in response.json()

def test_config_management():
    # Test config manager initialization
    assert config_manager is not None
    assert isinstance(config_manager.system_config, dict)
    assert isinstance(config_manager.user_state, dict)

    # Test getting user settings
    test_user_settings = config_manager.get_user_settings("TestUser")
    assert isinstance(test_user_settings, dict)

    # Test getting merged config
    merged_config = config_manager.get_merged_config("TestUser")
    assert isinstance(merged_config, dict)
    assert "USER_PREFERENCES" in merged_config
    assert "GENERATE" in merged_config

def test_user_mapping():
    # Test user ID mapping
    user_id = config_manager.get_user_id("127.0.0.1")
    assert user_id == "TestUser"

    # Test unknown IP
    user_id = config_manager.get_user_id("192.168.1.1")
    assert user_id == "Default"

    # Test with the actual test client IP
    user_id = config_manager.get_user_id("testclient")
    assert user_id == "TestUser"

def test_config_merging():
    # Test config merging functionality
    merged_config = config_manager.get_merged_config("TestUser")
    assert merged_config["USER_PREFERENCES"]["USER_RAG_ROOT"] == "/test/rag/root"
    assert merged_config["GENERATE"]["METHOD"] == "TestMethod"
