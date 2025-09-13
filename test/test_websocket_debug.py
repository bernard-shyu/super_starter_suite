#!/usr/bin/env python3
"""
WebSocket Debug Test Script

This script tests the WebSocket functionality for the Generate UI.
Run this script to verify WebSocket connections are working.
"""

import asyncio
import websockets
import json
import sys
import time

async def test_websocket_connection():
    """Test WebSocket connection to the generate endpoint"""
    # Test the same IP that browser is using
    uri = "ws://192.168.10.161:8000/ws/generate"  # Same as browser
    print(f"Testing WebSocket connection to: {uri}")
    print("This should reproduce the exact same issue as the browser")

    print(f"[TEST] Attempting to connect to: {uri}")

    try:
        async with websockets.connect(uri) as websocket:
            print("[TEST] WebSocket connection established!")

            # Send a test ping message
            ping_msg = "ping"
            await websocket.send(ping_msg)
            print(f"[TEST] Sent ping message: {ping_msg}")

            # Wait for pong response
            response = await websocket.recv()
            print(f"[TEST] Received response: {response}")

            # Test sending a mock progress message
            test_progress = {
                "type": "progress",
                "stage": "parser",
                "percentage": 50,
                "message": "Test progress message",
                "color": "green",
                "timestamp": "2025-09-05T11:14:30.000Z"
            }

            await websocket.send(json.dumps(test_progress))
            print(f"[TEST] Sent test progress message: {test_progress}")

            # Wait a bit for any additional messages
            try:
                await asyncio.wait_for(websocket.recv(), timeout=2.0)
                print("[TEST] Received additional message")
            except asyncio.TimeoutError:
                print("[TEST] No additional messages received (expected)")

            print("[TEST] WebSocket test completed successfully!")

    except Exception as e:
        print(f"[TEST] WebSocket test failed: {str(e)}")
        return False

    return True

async def test_http_endpoints():
    """Test HTTP endpoints related to generation"""
    import aiohttp

    print("[TEST] Testing HTTP endpoints...")

    async with aiohttp.ClientSession() as session:
        try:
            # Test generate endpoint with mock data
            payload = {"rag_type": "test_rag"}
            headers = {'Content-Type': 'application/json'}

            async with session.post('http://localhost:8000/api/generate', json=payload, headers=headers) as response:
                print(f"[TEST] Generate endpoint status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print(f"[TEST] Generate response: {data}")
                else:
                    error_text = await response.text()
                    print(f"[TEST] Generate error: {error_text}")

        except Exception as e:
            print(f"[TEST] HTTP test failed: {str(e)}")
            return False

    return True

async def main():
    """Run all tests"""
    print("=" * 50)
    print("WebSocket Debug Test Starting")
    print("=" * 50)

    # Test WebSocket connection
    print("\n--- Testing WebSocket Connection ---")
    ws_success = await test_websocket_connection()

    # Test HTTP endpoints
    print("\n--- Testing HTTP Endpoints ---")
    http_success = await test_http_endpoints()

    print("\n" + "=" * 50)
    print("Test Results:")
    print(f"WebSocket Test: {'PASS' if ws_success else 'FAIL'}")
    print(f"HTTP Test: {'PASS' if http_success else 'FAIL'}")

    if ws_success and http_success:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed. Check server logs for details.")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n[Test interrupted by user]")
        sys.exit(1)
    except Exception as e:
        print(f"\n[Test failed with error: {e}]")
        sys.exit(1)
