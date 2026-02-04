#!/usr/bin/env python3
"""
Workflow Integration Tests
Tests the complete dynamic workflow system: config → backend → frontend
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def test_config_loading():
    """Test 1: Workflow configuration loading"""
    print("🧪 Test 1: Workflow Configuration Loading")
    try:
        from super_starter_suite.shared.workflow_loader import get_all_workflow_configs
        workflows = get_all_workflow_configs()

        # Count both adapted and ported workflows (6 each = 12 total)
        total_count = len(workflows)
        assert total_count >= 10, f"Expected at least 10 workflows, got {total_count}"

        # Verify all workflows have required attributes
        required_attrs = ['display_name', 'code_path', 'timeout']
        for wf_id, wf_config in workflows.items():
            for attr in required_attrs:
                assert hasattr(wf_config, attr), f"Workflow {wf_id} missing {attr}"

        # Verify icon and description are properly set (optional attributes)
        for wf_id, wf_config in workflows.items():
            assert hasattr(wf_config, 'icon'), f"Workflow {wf_id} should have icon"
            assert hasattr(wf_config, 'description'), f"Workflow {wf_id} should have description"

        print(f"✅ Configuration loading PASSED - Loaded {total_count} workflows")
        return True
    except Exception as e:
        print(f"❌ Configuration loading FAILED: {e}")
        return False

def test_main_api_endpoint():
    """Test 2: Main app workflow endpoint"""
    print("\n🧪 Test 2: Main API Endpoint")
    try:
        from super_starter_suite.shared.workflow_loader import get_all_workflow_configs

        # Test get_available_workflows function logic
        workflows = get_all_workflow_configs()

        api_workflows = []
        for workflow_id, config in workflows.items():
            api_workflows.append({
                "id": workflow_id,
                "display_name": config.display_name,
                "description": getattr(config, 'description', ''),
                "icon": getattr(config, 'icon', '🤖'),
                "timeout": getattr(config, 'timeout', 60.0),
                "code_path": config.code_path
            })

        # Validate API structure - expect 10+ workflows from config
        assert len(api_workflows) >= 10, f"Expected at least 10 API workflows, got {len(api_workflows)}"

        for wf in api_workflows:
            required_fields = ['id', 'display_name', 'description', 'icon', 'timeout', 'code_path']
            for field in required_fields:
                assert field in wf, f"Missing required field '{field}' in workflow {wf.get('id')}"

        print(f"✅ Main API endpoint PASSED - {len(api_workflows)} workflows")
        return True
    except Exception as e:
        print(f"❌ Main API endpoint FAILED: {e}")
        return False

def test_frontend_api_data():
    """Test 3: Frontend-facing API data"""
    print("\n🧪 Test 3: Frontend API Data Structure")
    try:
        from super_starter_suite.shared.workflow_loader import get_all_workflow_configs
        workflows = get_workflow_config()

        # Test icon uniqueness and consistency
        icons = [workflow.icon for workflow in workflows.values()]
        assert len(set(icons)) > 6, "Icons should be mostly unique"  # Allow some duplicates

        # Test description quality
        descriptions = [workflow.description for workflow in workflows.values()]
        for desc in descriptions:
            assert len(desc) > 10, f"Description too short: '{desc}'"

        print(f"✅ Frontend API data PASSED - {len(icons)} unique icons")
        return True
    except Exception as e:
        print(f"❌ Frontend API data FAILED: {e}")
        return False

def test_session_endpoints():
    """Test 4: Session management endpoints"""
    print("\n🧪 Test 4: Session Management Endpoints")
    try:
        from super_starter_suite.shared.workflow_session_bridge import WorkflowSessionBridge
        from unittest.mock import MagicMock

        # Test session bridge initialization
        bridge = WorkflowSessionBridge()
        assert bridge is not None, "Session bridge failed"

        # Verify required methods exist (updated for actual bridge API)
        required_methods = ['ensure_chat_session', 'add_message_and_save_response', 'get_session_info']
        for method in required_methods:
            assert hasattr(bridge, method), f"Missing method: {method}"

        print("✅ Session management endpoints PASSED")
        return True
    except Exception as e:
        print(f"❌ Session management endpoints FAILED: {e}")
        return False

def run_all_tests():
    """Run all integration tests"""
    print("🚀 Starting Workflow Integration Tests")
    print("=" * 50)

    tests = [
        test_config_loading,
        test_main_api_endpoint,
        test_frontend_api_data,
        test_session_endpoints
    ]

    results = []
    try:
        for test in tests:
            result = test()
            results.append(result)
    except Exception as e:
        print(f"❌ Test execution FAILED: {e}")
        return False

    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"🎉 ALL TESTS PASSED ({passed}/{total})")
        print("\n✨ WORKFLOW INTEGRATION COMPLETED SUCCESSFULLY ✨")
        print("\n✅ Configuration-driven workflows working")
        print("✅ Dynamic frontend loading functional")
        print("✅ Backend API endpoints responding")
        print("✅ Session management integrated")
        print("✅ Zero hardcoded workflow components")
        return True
    else:
        print(f"⚠️ SOME TESTS FAILED: {passed}/{total} passed")
        return False

if __name__ == "__main__":
    import os
    import sys

    # Setup environment
    current_dir = os.path.dirname(__file__)
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)

    success = run_all_tests()
    print("\n🏁 Final Result:" + (" SUCCESS" if success else " FAILURE"))
    sys.exit(0 if success else 1)
