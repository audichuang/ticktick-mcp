#!/usr/bin/env python3
"""Test script to verify the OAuth discovery endpoint uses the correct host."""

import requests
import json

def test_oauth_discovery():
    """Test the OAuth discovery endpoint with different host headers."""
    
    # Test 1: Local testing
    print("Test 1: Local request without custom host header")
    try:
        response = requests.get('http://localhost:8000/.well-known/oauth-authorization-server')
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n" + "-"*50 + "\n")
    
    # Test 2: With custom host header (simulating Claude.ai access)
    print("Test 2: Request with custom host header (simulating Claude.ai)")
    try:
        headers = {
            'Host': 'ticktickmcp.audichuang.app',
            'X-Forwarded-Proto': 'https'
        }
        response = requests.get(
            'http://localhost:8000/.well-known/oauth-authorization-server',
            headers=headers
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n" + "-"*50 + "\n")
    
    # Test 3: Without X-Forwarded-Proto (should detect based on port)
    print("Test 3: Request with host header but no X-Forwarded-Proto")
    try:
        headers = {
            'Host': 'example.com:443'
        }
        response = requests.get(
            'http://localhost:8000/.well-known/oauth-authorization-server',
            headers=headers
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("OAuth Discovery Endpoint Test")
    print("Make sure the server is running on localhost:8000")
    print("="*50 + "\n")
    test_oauth_discovery()