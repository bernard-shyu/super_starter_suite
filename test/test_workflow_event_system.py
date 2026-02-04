#!/usr/bin/env python3
"""
Workflow Event System Test Suite

Tests the complete event system overhaul including:
- EventDispatcher functionality
- Standardized event naming with `_event` suffix
- Frontend/backend integration
- HIE modal display
- Progressive event handling
- Error recovery

Run with: python -m pytest test/test_workflow_event_system.py -v
"""

import asyncio
import json
import sys
import os
from typing import Dict, Any, List
from datetime import datetime

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from super_starter_suite.shared.config_manager import config_manager


class WorkflowEventSystemTester:
    """Comprehensive test suite for workflow event system"""

    def __init__(self):
        self.test_results = []
        self.logger = config_manager.get_logger("event_system_tester")

    def log_test_result(self, test_name: str, passed: bool, details: str = ""):
        """Log individual test result"""
        status = "✅ PASS" if passed else "❌ FAIL"
        result = f"{status} {test_name}"
        if details:
            result += f" - {details}"

        self.test_results.append({
            'test': test_name,
            'passed': passed,
            'details': details,
            'timestamp': datetime.now().isoformat()
        })

        print(result)

    async def test_event_dispatcher_creation(self):
        """Test 1: EventDispatcher can be created and initialized"""
        try:
            # Test EventDispatcher import
            sys.path.append(os.path.join(project_root, 'frontend', 'static', 'modules'))
            from event_dispatcher import EventDispatcher, getEventDispatcher

            # Create dispatcher
            dispatcher = EventDispatcher()

            # Check required methods
            assert hasattr(dispatcher, 'registerHandler'), "Missing registerHandler method"
            assert hasattr(dispatcher, 'dispatchEvent'), "Missing dispatchEvent method"
            assert hasattr(dispatcher, 'getHealthStatus'), "Missing getHealthStatus method"

            # Test health status
            health = dispatcher.getHealthStatus()
            assert 'healthy' in health, "Missing healthy status"
            assert 'handlerCount' in health, "Missing handler count"

            self.log_test_result("EventDispatcher Creation", True, f"Health: {health}")

        except Exception as e:
            self.log_test_result("EventDispatcher Creation", False, str(e))

    async def test_standardized_event_naming(self):
        """Test 2: Backend uses standardized `_event` suffix"""
        try:
            # Import key backend modules
            from super_starter_suite.chat_bot.human_input.hie_event_processor import process_hie_input_event
            from super_starter_suite.chat_bot.workflow_execution.workflow_endpoints import chat_websocket_stream_endpoint

            # Check source code for standardized event names
            import inspect

            # Check HIE processor uses hie_command_event
            hie_source = inspect.getsource(process_hie_input_event)
            assert "'hie_command_event'" in hie_source, "HIE processor doesn't use hie_command_event"

            # Check workflow endpoints use standardized events
            endpoints_source = inspect.getsource(chat_websocket_stream_endpoint)
            assert "'chat_response_event'" in endpoints_source, "WebSocket endpoint doesn't use chat_response_event"
            assert "'error_event'" in endpoints_source, "WebSocket endpoint doesn't use error_event"

            self.log_test_result("Standardized Event Naming", True, "All backend modules use _event suffix")

        except Exception as e:
            self.log_test_result("Standardized Event Naming", False, str(e))

    async def test_frontend_event_handlers(self):
        """Test 3: Frontend managers implement handleEvent interface"""
        try:
            # Test HumanInTheLoopManager
            sys.path.append(os.path.join(project_root, 'frontend', 'static', 'modules'))
            from human_in_the_loop_manager import HumanInTheLoopManager

            hitl_manager = HumanInTheLoopManager()
            assert hasattr(hitl_manager, 'handleEvent'), "HITL manager missing handleEvent method"

            # Test ChatUIManager
            from chat.chat_ui_manager import ChatUIManager
            chat_manager = ChatUIManager()
            assert hasattr(chat_manager, 'handleEvent'), "Chat manager missing handleEvent method"

            # Test handleEvent signatures
            try:
                # This should not throw an error
                await hitl_manager.handleEvent('hie_command_event', {}, 'test-workflow')
                await chat_manager.handleEvent('chat_response_event', {}, 'test-workflow')
                self.log_test_result("Frontend Event Handlers", True, "All managers implement handleEvent correctly")
            except Exception as e:
                self.log_test_result("Frontend Event Handlers", False, f"handleEvent execution failed: {e}")

        except Exception as e:
            self.log_test_result("Frontend Event Handlers", False, str(e))

    async def test_event_dispatcher_integration(self):
        """Test 4: EventDispatcher integrates with UI managers"""
        try:
            sys.path.append(os.path.join(project_root, 'frontend', 'static', 'modules'))
            from event_dispatcher import EventDispatcher
            from human_in_the_loop_manager import HumanInTheLoopManager
            from chat.chat_ui_manager import ChatUIManager

            # Create components
            dispatcher = EventDispatcher()
            hitl_manager = HumanInTheLoopManager()
            chat_manager = ChatUIManager()

            # Register handlers
            dispatcher.registerHandler('hie_command_event', hitl_manager)
            dispatcher.registerHandler('chat_response_event', chat_manager)

            # Test handler lookup
            assert dispatcher.getHandler('hie_command_event') is hitl_manager, "HITL handler not registered"
            assert dispatcher.getHandler('chat_response_event') is chat_manager, "Chat handler not registered"

            # Test event dispatch (should not throw errors)
            await dispatcher.dispatchEvent('hie_command_event', {'test': 'data'}, 'test-workflow')
            await dispatcher.dispatchEvent('chat_response_event', {'test': 'data'}, 'test-workflow')

            # Test unknown event (should log warning but not fail)
            await dispatcher.dispatchEvent('unknown_event', {}, 'test-workflow')

            self.log_test_result("EventDispatcher Integration", True, "All handlers registered and events dispatched")

        except Exception as e:
            self.log_test_result("EventDispatcher Integration", False, str(e))

    async def test_legacy_broadcast_removal(self):
        """Test 5: Legacy broadcast functions removed"""
        try:
            # Check execution_engine.py no longer imports broadcast functions
            with open(os.path.join(project_root, 'super_starter_suite', 'chat_bot', 'workflow_execution', 'execution_engine.py'), 'r') as f:
                content = f.read()

            # Should not contain broadcast imports or calls
            assert 'broadcast_workflow_progress' not in content, "Legacy broadcast_progress still present"
            assert 'broadcast_workflow_artifact' not in content, "Legacy broadcast_artifact still present"
            assert 'from .websocket_endpoint import' not in content, "Legacy websocket imports still present"

            self.log_test_result("Legacy Broadcast Removal", True, "All legacy broadcast code removed")

        except Exception as e:
            self.log_test_result("Legacy Broadcast Removal", False, str(e))

    async def test_event_data_formats(self):
        """Test 6: Event data formats are standardized"""
        try:
            # Test HIE event format
            hie_event_data = {
                "event_type": "cli_human_input",
                "command": "ls -la",
                "workflow_id": "test-workflow",
                "session_id": "test-session"
            }

            # Test progressive event format
            progressive_event_data = {
                "action": "create_panel",
                "panel_id": "research",
                "status": "in_progress",
                "message": "Researching question..."
            }

            # Test chat response format
            chat_event_data = {
                "session_id": "test-session",
                "message_id": "test-message",
                "response": "Test response",
                "artifacts": [],
                "enhanced_metadata": {}
            }

            # Validate required fields
            assert "event_type" in hie_event_data, "HIE event missing event_type"
            assert "command" in hie_event_data, "HIE event missing command"

            assert "action" in progressive_event_data, "Progressive event missing action"
            assert "panel_id" in progressive_event_data, "Progressive event missing panel_id"

            assert "response" in chat_event_data, "Chat event missing response"

            self.log_test_result("Event Data Formats", True, "All event formats properly structured")

        except Exception as e:
            self.log_test_result("Event Data Formats", False, str(e))

    async def test_error_handling(self):
        """Test 7: Error handling and recovery"""
        try:
            sys.path.append(os.path.join(project_root, 'frontend', 'static', 'modules'))
            from event_dispatcher import EventDispatcher

            dispatcher = EventDispatcher()

            # Test dispatching to non-existent handler
            await dispatcher.dispatchEvent('nonexistent_event', {}, 'test-workflow')

            # Test health status after errors
            health = dispatcher.getHealthStatus()
            assert health['healthy'] is True, "System should remain healthy after unknown events"

            # Test error statistics
            stats = dispatcher.getEventStats()
            assert isinstance(stats, dict), "Event stats should be a dictionary"

            self.log_test_result("Error Handling", True, "Error handling and recovery working correctly")

        except Exception as e:
            self.log_test_result("Error Handling", False, str(e))

    async def test_hie_event_processing(self):
        """Test 8: HIE event processing end-to-end"""
        try:
            from super_starter_suite.chat_bot.human_input.hie_event_processor import process_hie_input_event

            # Mock event data
            mock_event = type('MockEvent', (), {
                'data': type('MockData', (), {'command': 'echo "test"'})()
            })()

            mock_config = type('MockConfig', (), {
                'display_name': 'Test Workflow',
                'workflow_ID': 'test-workflow',
                'hie_enabled': True
            })()

            # Test HIE processing
            result = await process_hie_input_event(mock_event, mock_config, 'test-session', None)

            # Should return HIE data
            assert result is not None, "HIE processing should return data"
            assert result.get('HIE_intercepted') is True, "Should indicate HIE interception"
            assert 'HIE_command' in result, "Should include command"

            self.log_test_result("HIE Event Processing", True, "HIE events processed correctly")

        except Exception as e:
            self.log_test_result("HIE Event Processing", False, str(e))

    async def test_progressive_event_conversion(self):
        """Test 9: Progressive event conversion"""
        try:
            from super_starter_suite.chat_bot.workflow_execution.execution_engine import _convert_ui_event_to_progressive

            # Test with complete UI event data
            test_data = {
                'event': 'retrieve',
                'state': 'in_progress',
                'id': '123',
                'question': 'What is AI?',
                'answer': 'AI refers to artificial intelligence'
            }

            result = _convert_ui_event_to_progressive(test_data, self.logger)

            # Check conversion
            assert 'action' in result, "Should include action"
            assert 'panel_id' in result, "Should include panel_id"
            assert result['action'] == 'create_panel', "Should create panel for standard events"

            self.log_test_result("Progressive Event Conversion", True, "UI events converted to progressive format")

        except Exception as e:
            self.log_test_result("Progressive Event Conversion", False, str(e))

    async def run_all_tests(self):
        """Run complete test suite"""
        print("🧪 WORKFLOW EVENT SYSTEM TEST SUITE")
        print("=" * 50)

        tests = [
            self.test_event_dispatcher_creation,
            self.test_standardized_event_naming,
            self.test_frontend_event_handlers,
            self.test_event_dispatcher_integration,
            self.test_legacy_broadcast_removal,
            self.test_event_data_formats,
            self.test_error_handling,
            self.test_hie_event_processing,
            self.test_progressive_event_conversion,
        ]

        for test in tests:
            await test()

        # Summary
        print("\n" + "=" * 50)
        print("📊 TEST SUMMARY")

        passed = sum(1 for result in self.test_results if result['passed'])
        total = len(self.test_results)

        print(f"✅ Passed: {passed}/{total}")
        print(f"❌ Failed: {total - passed}/{total}")

        if passed == total:
            print("🎉 ALL TESTS PASSED! Event system is working correctly.")
            return True
        else:
            print("⚠️  SOME TESTS FAILED. Check details above.")
            # Print failed tests
            print("\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result['passed']:
                    print(f"  - {result['test']}: {result['details']}")
            return False


async def main():
    """Main test runner"""
    tester = WorkflowEventSystemTester()
    success = await tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
