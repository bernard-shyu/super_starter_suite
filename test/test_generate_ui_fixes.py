#!/usr/bin/env python3
"""
Automated testing script for Generate UI fixes - Phase 3.6 Verification
Tests the 3 remaining issues:
1. Generate UI not displaying generation method/model info
2. RAG Type selection not being applied
3. Terminal logging not showing real-time output
"""

import requests
import json
import time
import sys
from pathlib import Path

BASE_URL = "http://localhost:8000"

def test_generation_method_info():
    """Test Issue 1: Generate UI displaying generation method/model info"""
    print("🧪 Testing Issue 1: Generation method/model info display")
    print("=" * 60)

    try:
        # Test settings endpoint
        response = requests.get(f"{BASE_URL}/api/settings")
        if response.status_code != 200:
            print(f"❌ Settings endpoint failed: {response.status_code}")
            return False

        settings = response.json()
        print(f"✅ Settings endpoint response: {response.status_code}")

        # Check GENERATE section
        if 'GENERATE' in settings:
            method = settings['GENERATE'].get('METHOD', 'Not set')
            print(f"✅ Found GENERATE.METHOD: {method}")

            # Check model for AI methods
            if method in ['NvidiaAI', 'GeminiAI', 'AzureAI']:
                model_key = f"{method}_SELECTED_MODEL"
                if model_key in settings:
                    model = settings[model_key]
                    print(f"✅ Found model for {method}: {model}")
                else:
                    print(f"❌ Model not found for {method} with key {model_key}")
                    return False
        else:
            print("❌ GENERATE section not found in settings")
            return False

        return True

    except Exception as e:
        print(f"❌ Error testing generation method info: {e}")
        return False

def test_rag_type_options():
    """Test Issue 2: RAG Type options loading"""
    print("\n🧪 Testing Issue 2: RAG Type options loading")
    print("=" * 60)

    try:
        response = requests.get(f"{BASE_URL}/api/generate/rag_type_options")
        if response.status_code != 200:
            print(f"❌ RAG type options endpoint failed: {response.status_code}")
            return False

        data = response.json()
        print(f"✅ RAG type options endpoint response: {response.status_code}")

        if 'rag_types' in data and isinstance(data['rag_types'], list):
            print(f"✅ Found RAG types: {data['rag_types']}")
            return True
        else:
            print("❌ RAG types not found in response")
            return False

    except Exception as e:
        print(f"❌ Error testing RAG type options: {e}")
        return False

def test_generation_without_rag_type():
    """Test Issue 2: Generation fails without RAG type selection"""
    print("\n🧪 Testing Issue 2: Generation validation without RAG type")
    print("=" * 60)

    try:
        # Try to generate without RAG type
        payload = {}  # Empty payload
        response = requests.post(f"{BASE_URL}/api/generate", json=payload)

        if response.status_code == 400:
            data = response.json()
            if "rag_type" in str(data).lower() or "select" in str(data).lower():
                print(f"✅ Validation works - got expected error: {data}")
                return True
            else:
                print(f"❌ Got 400 error but wrong message: {data}")
                return False
        else:
            print(f"❌ Expected 400 error, got {response.status_code}: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Error testing generation validation: {e}")
        return False

def test_generation_with_rag_type():
    """Test Issue 2: Generation succeeds with RAG type selection"""
    print("\n🧪 Testing Issue 2: Generation with RAG type selection")
    print("=" * 60)

    try:
        # Get available RAG types first
        response = requests.get(f"{BASE_URL}/api/generate/rag_type_options")
        if response.status_code != 200:
            print("❌ Cannot get RAG types for testing")
            return False

        rag_types = response.json()['rag_types']
        if not rag_types:
            print("❌ No RAG types available")
            return False

        selected_rag_type = rag_types[0]  # Use first available type
        print(f"📝 Testing with RAG type: {selected_rag_type}")

        # Try to generate with RAG type
        payload = {"rag_type": selected_rag_type}
        response = requests.post(f"{BASE_URL}/api/generate", json=payload)

        if response.status_code == 200:
            data = response.json()
            if 'task_id' in data:
                print(f"✅ Generation started successfully with task_id: {data['task_id']}")
                return data['task_id']
            else:
                print(f"❌ Generation response missing task_id: {data}")
                return False
        else:
            print(f"❌ Generation failed: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        print(f"❌ Error testing generation with RAG type: {e}")
        return False

def test_terminal_logging(task_id):
    """Test Issue 3: Terminal logging functionality"""
    print("\n🧪 Testing Issue 3: Terminal logging functionality")
    print("=" * 60)

    try:
        print(f"📝 Testing logs for task_id: {task_id}")

        # Test logs endpoint
        max_attempts = 10
        for attempt in range(max_attempts):
            response = requests.get(f"{BASE_URL}/api/generate/logs/{task_id}")

            if response.status_code != 200:
                print(f"❌ Logs endpoint failed: {response.status_code}")
                return False

            data = response.json()
            if 'logs' in data and isinstance(data['logs'], list):
                logs = data['logs']
                print(f"✅ Got {len(logs)} log entries on attempt {attempt + 1}")

                if logs:  # If we have logs
                    print("📋 Sample logs:")
                    for i, log in enumerate(logs[:3]):  # Show first 3 logs
                        print(f"   {i+1}. {log}")

                    # Check if we have real-time logs (not just status messages)
                    real_logs = [log for log in logs if not log.startswith("[INFO] Task") and not log.startswith("[SUCCESS] Generation task") and not log.startswith("[ERROR] Generation task")]
                    if real_logs:
                        print(f"✅ Found {len(real_logs)} real-time logs (not just status messages)")
                        return True
                    else:
                        print("⚠️  Only status messages found, waiting for real logs...")

            time.sleep(2)  # Wait 2 seconds between attempts

        print("⚠️  No real-time logs captured within timeout")
        return False

    except Exception as e:
        print(f"❌ Error testing terminal logging: {e}")
        return False

def test_generation_status(task_id):
    """Test generation status polling"""
    print("\n🧪 Testing generation status polling")
    print("=" * 60)

    try:
        response = requests.get(f"{BASE_URL}/api/generate/status/{task_id}")

        if response.status_code != 200:
            print(f"❌ Status endpoint failed: {response.status_code}")
            return False

        data = response.json()
        if 'status' in data:
            print(f"✅ Generation status: {data['status']}")
            return True
        else:
            print(f"❌ Status response missing status field: {data}")
            return False

    except Exception as e:
        print(f"❌ Error testing generation status: {e}")
        return False

def run_all_tests():
    """Run all tests and report results"""
    print("🚀 Starting Phase 3.6 Verification - Generate UI Fixes Testing")
    print("=" * 70)

    test_results = {
        "generation_method_info": test_generation_method_info(),
        "rag_type_options": test_rag_type_options(),
        "generation_validation": test_generation_without_rag_type(),
    }

    # Test generation with RAG type and get task_id
    task_id = test_generation_with_rag_type()
    if task_id:
        test_results["generation_with_rag"] = True

        # Wait a bit for generation to start
        print("\n⏳ Waiting for generation to process...")
        time.sleep(3)

        # Test terminal logging
        test_results["terminal_logging"] = test_terminal_logging(task_id)

        # Test status polling
        test_results["generation_status"] = test_generation_status(task_id)
    else:
        test_results["generation_with_rag"] = False
        test_results["terminal_logging"] = False
        test_results["generation_status"] = False

    # Summary
    print("\n" + "=" * 70)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 70)

    all_passed = True
    for test_name, result in test_results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:<25} {status}")
        if not result:
            all_passed = False

    print("=" * 70)
    if all_passed:
        print("🎉 ALL TESTS PASSED! Generate UI fixes are working correctly.")
    else:
        print("⚠️  Some tests failed. Issues may still exist.")

    return all_passed

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
