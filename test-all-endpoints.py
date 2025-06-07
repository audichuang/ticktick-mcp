#!/usr/bin/env python3
"""Complete test for TickTick MCP Remote Server endpoints"""

import requests
import json
from urllib.parse import parse_qs

def test_all_endpoints():
    base_url = "http://localhost:8000"
    password = "test-password-123"
    
    print("Testing ALL TickTick MCP Remote Server Endpoints")
    print("===============================================")
    
    # Test 1: Root endpoint without password (should fail)
    print("\n1. Root endpoint without password (should fail)...")
    try:
        response = requests.get(f"{base_url}/")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   ERROR: {e}")
    
    # Test 2: Root endpoint with wrong password (should fail)
    print("\n2. Root endpoint with wrong password (should fail)...")
    try:
        response = requests.get(f"{base_url}/wrong-password/")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   ERROR: {e}")
    
    # Test 3: Root endpoint with correct password (should succeed)
    print("\n3. Root endpoint with correct password (should succeed)...")
    try:
        response = requests.get(f"{base_url}/{password}/")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"   ERROR: {e}")
    
    # Test 4: SSE endpoint with correct password
    print(f"\n4. SSE endpoint with correct password...")
    try:
        response = requests.get(f"{base_url}/{password}/sse", stream=True, timeout=2)
        print(f"   Status: {response.status_code}")
        
        # Read first few lines to get session ID
        session_id = None
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                print(f"   {line_str}")
                if "session_id=" in line_str:
                    # Extract session ID
                    parts = line_str.split('session_id=')
                    if len(parts) > 1:
                        session_id = parts[1].split('&')[0]
                        break
        
        if session_id:
            print(f"\n   Got session ID: {session_id}")
            
            # Test 5: Messages endpoint with session ID
            print(f"\n5. Testing messages endpoint...")
            response = requests.post(
                f"{base_url}/{password}/messages/?session_id={session_id}",
                json={
                    "jsonrpc": "2.0",
                    "id": "1",
                    "method": "tools/list"
                }
            )
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text}")
        
    except requests.Timeout:
        print("   Timeout (normal for SSE)")
    except Exception as e:
        print(f"   ERROR: {e}")
    
    print("\n" + "="*50)
    print("Summary:")
    print("- Root endpoint (/) requires password and returns server info")
    print("- SSE endpoint (/sse) requires password and returns session")
    print("- Messages endpoint (/messages) requires password and session")
    print(f"\nFor Claude.ai Integration, use:")
    print(f"  URL: https://your-domain.com/{password}/sse")

if __name__ == "__main__":
    test_all_endpoints()