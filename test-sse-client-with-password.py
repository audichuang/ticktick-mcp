#!/usr/bin/env python3
"""Test SSE client for TickTick MCP Remote Server with password protection"""

import requests
import json
import sys
from urllib.parse import urlparse, parse_qs

def test_mcp_server():
    base_url = "http://localhost:8000"
    password = "test-password-123"  # This should match MCP_PASSWORD in .env
    
    print("Testing TickTick MCP Remote Server with Password Protection")
    print("=========================================================")
    
    # Test 1: Try without password (should fail)
    print("\n1. Testing without password (should fail)...")
    try:
        response = requests.get(f"{base_url}/sse", timeout=1)
        print(f"   Response: {response.status_code} - {response.text}")
    except requests.Timeout:
        print("   Timeout (unexpected)")
    except Exception as e:
        print(f"   ERROR: {e}")
    
    # Test 2: Try with wrong password (should fail)
    print("\n2. Testing with wrong password (should fail)...")
    try:
        response = requests.get(f"{base_url}/wrong-password/sse", timeout=1)
        print(f"   Response: {response.status_code} - {response.text}")
    except requests.Timeout:
        print("   Timeout (unexpected)")
    except Exception as e:
        print(f"   ERROR: {e}")
    
    # Test 3: Connect with correct password
    print(f"\n3. Connecting to SSE endpoint with correct password...")
    try:
        # Connect with streaming
        response = requests.get(f"{base_url}/{password}/sse", stream=True, timeout=2)
        
        # Read first few lines to get session ID
        session_id = None
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                print(f"   {line_str}")
                if line_str.startswith("data: ") and "/messages/" in line_str:
                    # Extract session ID from URL
                    url_part = line_str.replace("data: ", "")
                    # Parse the URL to get query parameters
                    if '?' in url_part:
                        query_string = url_part.split('?')[1]
                        params = parse_qs(query_string)
                        if 'session_id' in params:
                            session_id = params['session_id'][0]
                            break
        
        if not session_id:
            print("ERROR: Could not get session ID")
            return
            
        print(f"\n   Got session ID: {session_id}")
        
    except requests.Timeout:
        print("   Timeout connecting to SSE (this is normal)")
    except Exception as e:
        print(f"ERROR: {e}")
        return
    
    # Test 4: Test tools/list with password
    print(f"\n4. Testing tools/list...")
    try:
        response = requests.post(
            f"{base_url}/{password}/messages/?session_id={session_id}",
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "tools/list"
            }
        )
        print(f"   Response: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"ERROR: {e}")
    
    # Test 5: Test get_projects tool with password
    print(f"\n5. Testing get_projects tool...")
    try:
        response = requests.post(
            f"{base_url}/{password}/messages/?session_id={session_id}",
            json={
                "jsonrpc": "2.0",
                "id": "2",
                "method": "tools/call",
                "params": {
                    "name": "get_projects",
                    "arguments": {}
                }
            }
        )
        print(f"   Response: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"ERROR: {e}")
    
    print("\nTest completed!")
    print("\nNote: The actual responses are sent through the SSE connection.")
    print("In a real client, you would keep the SSE connection open to receive responses.")
    print(f"\nFor Claude.ai Integration, use: https://your-domain.com/{password}/sse")

if __name__ == "__main__":
    test_mcp_server()