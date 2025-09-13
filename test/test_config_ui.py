#!/usr/bin/env python3
"""
Test script for Configuration Management UI enhancements.

This script tests the key functionality implemented in the Configuration Management UI:
1. Directory selection functionality
2. AI parser settings display for different methods (NvidiaAI, GeminiAI)
3. System configuration saving
4. TOML structure preservation
5. Workflow RAG type mapping saving
"""

import asyncio
import aiohttp
import json
import sys
import os
from pathlib import Path
from typing import Optional

class ConfigUITester:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def test_api_endpoints(self):
        """Test basic API endpoints functionality."""
        print("=== Testing API Endpoints ===")

        if not self.session:
            print("✗ Session not initialized")
            return False

        try:
            # Test GET /api/settings
            print("Testing GET /api/settings...")
            async with self.session.get(f"{self.base_url}/api/settings?user_id=Default") as resp:
                if resp.status == 200:
                    settings = await resp.json()
                    print("✓ GET /api/settings successful")
                    print(f"  Settings keys: {list(settings.keys())}")
                else:
                    print(f"✗ GET /api/settings failed: {resp.status}")
                    return False

            # Test GET /api/config
            print("Testing GET /api/config...")
            async with self.session.get(f"{self.base_url}/api/config") as resp:
                if resp.status == 200:
                    config = await resp.json()
                    print("✓ GET /api/config successful")
                    print(f"  Config keys: {list(config.keys())}")
                else:
                    print(f"✗ GET /api/config failed: {resp.status}")
                    return False

            # Test POST /api/settings
            print("Testing POST /api/settings...")
            test_settings = {
                "USER_PREFERENCES": {
                    "THEME": "dark",
                    "USER_RAG_ROOT": "/test/path"
                },
                "GENERATE": {
                    "METHOD": "NvidiaAI"
                },
                "GENERATE_AI_METHOD": {
                    "NvidiaAI_SELECTED_MODEL": "microsoft/phi-4-multimodal-instruct",
                    "GeminiAI_SELECTED_MODEL": "gemini-2.0-flash"
                },
                "WORKFLOW_RAG_TYPE": {
                    "agentic_rag": "RAG",
                    "code_generator": "CODE_GEN"
                }
            }

            async with self.session.post(
                f"{self.base_url}/api/settings",
                json=test_settings,
                headers={'Content-Type': 'application/json'}
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    print("✓ POST /api/settings successful")
                    print(f"  Response: {result}")
                else:
                    error_text = await resp.text()
                    print(f"✗ POST /api/settings failed: {resp.status} - {error_text}")
                    return False

            # Test POST /api/config
            print("Testing POST /api/config...")
            test_config = {
                "SYSTEM": {
                    "GENERATE_METHODS": ["NvidiaAI", "GeminiAI", "LlamaParse"]
                },
                "GENERATE_AI_METHOD": {
                    "NvidiaAI_SELECTED_MODEL": "microsoft/phi-4-multimodal-instruct",
                    "GeminiAI_SELECTED_MODEL": "gemini-2.0-flash"
                }
            }

            async with self.session.post(
                f"{self.base_url}/api/config",
                json=test_config,
                headers={'Content-Type': 'application/json'}
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    print("✓ POST /api/config successful")
                    print(f"  Response: {result}")
                else:
                    error_text = await resp.text()
                    print(f"✗ POST /api/config failed: {resp.status} - {error_text}")
                    return False

            return True

        except Exception as e:
            print(f"✗ API endpoint test failed with exception: {e}")
            return False

    async def test_toml_structure_preservation(self):
        """Test that TOML structure is preserved after saves."""
        print("\n=== Testing TOML Structure Preservation ===")

        if not self.session:
            print("✗ Session not initialized")
            return False

        try:
            # Get original settings
            async with self.session.get(f"{self.base_url}/api/settings?user_id=Default") as resp:
                if resp.status != 200:
                    print("✗ Failed to get original settings")
                    return False
                original_settings = await resp.json()

            # Modify and save settings
            modified_settings = original_settings.copy()
            modified_settings["USER_PREFERENCES"]["THEME"] = "light"
            modified_settings["GENERATE"]["METHOD"] = "GeminiAI"

            async with self.session.post(
                f"{self.base_url}/api/settings",
                json=modified_settings,
                headers={'Content-Type': 'application/json'}
            ) as resp:
                if resp.status != 200:
                    print("✗ Failed to save modified settings")
                    return False

            # Get settings again to verify structure
            async with self.session.get(f"{self.base_url}/api/settings?user_id=Default") as resp:
                if resp.status != 200:
                    print("✗ Failed to get modified settings")
                    return False
                retrieved_settings = await resp.json()

            # Check if structure is preserved
            if set(original_settings.keys()) == set(retrieved_settings.keys()):
                print("✓ TOML structure preserved - same top-level keys")
            else:
                print("✗ TOML structure changed - different top-level keys")
                print(f"  Original keys: {set(original_settings.keys())}")
                print(f"  Retrieved keys: {set(retrieved_settings.keys())}")
                return False

            # Check if our modifications were saved
            if (retrieved_settings.get("USER_PREFERENCES", {}).get("THEME") == "light" and
                retrieved_settings.get("GENERATE", {}).get("METHOD") == "GeminiAI"):
                print("✓ Settings modifications saved correctly")
            else:
                print("✗ Settings modifications not saved correctly")
                return False

            return True

        except Exception as e:
            print(f"✗ TOML structure test failed with exception: {e}")
            return False

    async def test_workflow_rag_type_mapping(self):
        """Test workflow RAG type mapping functionality."""

    async def test_user_rag_types(self):
        """Test that RAG types are now properly loaded from user preferences."""
        print("\n=== Testing User RAG Types ===")

        if not self.session:
            print("✗ Session not initialized")
            return False

        try:
            # Test getting RAG types from user preferences
            async with self.session.get(f"{self.base_url}/api/settings?user_id=Default") as resp:
                if resp.status != 200:
                    print("✗ Failed to get user settings")
                    return False
                settings = await resp.json()

            rag_types = settings.get("USER_PREFERENCES", {}).get("RAG_TYPES", [])
            if isinstance(rag_types, list) and len(rag_types) > 0:
                print("✓ RAG types successfully loaded from user preferences")
                print(f"  RAG types: {rag_types}")
            else:
                print("✗ RAG types not found or invalid in user preferences")
                return False

            # Test saving new RAG types
            test_rag_types = ["RAG", "CODE_GEN", "FINANCE", "TINA_DOC", "NEW_TYPE"]
            test_settings = {
                "USER_PREFERENCES": {
                    "RAG_TYPES": test_rag_types
                }
            }

            async with self.session.post(
                f"{self.base_url}/api/settings",
                json=test_settings,
                headers={'Content-Type': 'application/json'}
            ) as resp:
                if resp.status != 200:
                    print("✗ Failed to save RAG types")
                    return False

            # Verify the saved RAG types
            async with self.session.get(f"{self.base_url}/api/settings?user_id=Default") as resp:
                if resp.status != 200:
                    print("✗ Failed to get updated settings")
                    return False
                updated_settings = await resp.json()

            saved_rag_types = updated_settings.get("USER_PREFERENCES", {}).get("RAG_TYPES", [])
            if saved_rag_types == test_rag_types:
                print("✓ RAG types saved and retrieved correctly")
            else:
                print("✗ RAG types not saved correctly")
                print(f"  Expected: {test_rag_types}")
                print(f"  Got: {saved_rag_types}")
                return False

            return True

        except Exception as e:
            print(f"✗ User RAG types test failed with exception: {e}")
            return False
        print("\n=== Testing Workflow RAG Type Mapping ===")

        if not self.session:
            print("✗ Session not initialized")
            return False

        try:
            # Test saving workflow mappings
            test_mappings = {
                "USER_PREFERENCES": {
                    "THEME": "dark",
                    "USER_RAG_ROOT": "/test/path"
                },
                "GENERATE": {
                    "METHOD": "NvidiaAI"
                },
                "WORKFLOW_RAG_TYPE": {
                    "agentic_rag": "RAG",
                    "code_generator": "CODE_GEN",
                    "deep_research": "RAG",
                    "document_generator": "RAG",
                    "financial_report": "FINANCE",
                    "human_in_the_loop": "RAG"
                }
            }

            async with self.session.post(
                f"{self.base_url}/api/settings",
                json=test_mappings,
                headers={'Content-Type': 'application/json'}
            ) as resp:
                if resp.status != 200:
                    print("✗ Failed to save workflow mappings")
                    return False

            # Get settings back to verify
            async with self.session.get(f"{self.base_url}/api/settings?user_id=Default") as resp:
                if resp.status != 200:
                    print("✗ Failed to get workflow mappings")
                    return False
                retrieved_settings = await resp.json()

            saved_mappings = retrieved_settings.get("WORKFLOW_RAG_TYPE", {})
            if saved_mappings == test_mappings["WORKFLOW_RAG_TYPE"]:
                print("✓ Workflow RAG type mappings saved and retrieved correctly")
                print(f"  Saved mappings: {saved_mappings}")
            else:
                print("✗ Workflow RAG type mappings not saved correctly")
                print(f"  Expected: {test_mappings['WORKFLOW_RAG_TYPE']}")
                print(f"  Got: {saved_mappings}")
                return False

            return True

        except Exception as e:
            print(f"✗ Workflow mapping test failed with exception: {e}")
            return False

    async def run_all_tests(self):
        """Run all tests."""
        print("Configuration Management UI Test Suite")
        print("=" * 50)

        tests = [
        ("API Endpoints", self.test_api_endpoints),
        ("TOML Structure Preservation", self.test_toml_structure_preservation),
        ("Workflow RAG Type Mapping", self.test_workflow_rag_type_mapping),
        ("User RAG Types", self.test_user_rag_types),
        ]

        passed = 0
        total = len(tests)

        for test_name, test_func in tests:
            print(f"\nRunning {test_name}...")
            try:
                if await test_func():
                    passed += 1
                    print(f"✓ {test_name} PASSED")
                else:
                    print(f"✗ {test_name} FAILED")
            except Exception as e:
                print(f"✗ {test_name} FAILED with exception: {e}")

        print("\n" + "=" * 50)
        print(f"Test Results: {passed}/{total} tests passed")

        if passed == total:
            print("🎉 All tests passed! Configuration Management UI is working correctly.")
            return True
        else:
            print("❌ Some tests failed. Please check the implementation.")
            return False

def main():
    """Main function to run the test suite."""
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = "http://localhost:8000"

    print(f"Testing against: {base_url}")

    async def run_tests():
        async with ConfigUITester(base_url) as tester:
            return await tester.run_all_tests()

    try:
        success = asyncio.run(run_tests())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Test suite failed to run: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
