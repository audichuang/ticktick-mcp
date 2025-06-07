#!/usr/bin/env python3
"""Test SSE client for TickTick MCP Remote Server"""

import requests
import json
import sys
from urllib.parse import urlparse, parse_qs

def test_mcp_server():
    base_url = "http://localhost:8000"
    
    print("Testing TickTick MCP Remote Server")
    print("==================================")
    
    # 1. Connect to SSE endpoint to get session ID
    print("\n1. Connecting to SSE endpoint...")
    try:
        # Connect with streaming
        response = requests.get(f"{base_url}/sse", stream=True, timeout=2)
        
        # Read first few lines to get session ID
        session_id = None
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                print(f"   {line_str}")
                if line_str.startswith("data: /messages/"):
                    # Extract session ID from URL
                    url_part = line_str.replace("data: ", "")
                    parsed = urlparse(url_part)
                    params = parse_qs(parsed.query)
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
    
    # 2. Test tools/list
    print("\n2. Testing tools/list...")
    try:
        response = requests.post(
            f"{base_url}/messages/?session_id={session_id}",
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "tools/list"
            }
        )
        print(f"   Response: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"ERROR: {e}")
    
    # 3. Test get_projects tool
    print("\n3. Testing get_projects tool...")
    try:
        response = requests.post(
            f"{base_url}/messages/?session_id={session_id}",
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

if __name__ == "__main__":
    test_mcp_server()