#!/usr/bin/env python3
"""Test OAuth client for TickTick MCP Remote Server with OAuth authentication"""

import requests
import json
import sys
import base64
from urllib.parse import urlparse, parse_qs, urlencode

def test_oauth_flow():
    base_url = "http://localhost:8000"
    client_id = "test-client"
    client_secret = "test-secret"
    redirect_uri = "http://localhost:8080/callback"
    
    print("Testing TickTick MCP Remote Server with OAuth Authentication")
    print("===========================================================")
    
    # Test 1: OAuth Discovery
    print("\n1. Testing OAuth discovery endpoint...")
    try:
        response = requests.get(f"{base_url}/.well-known/oauth-authorization-server")
        print(f"   Response: {response.status_code}")
        if response.status_code == 200:
            discovery = response.json()
            print(f"   Authorization endpoint: {discovery.get('authorization_endpoint')}")
            print(f"   Token endpoint: {discovery.get('token_endpoint')}")
    except Exception as e:
        print(f"   ERROR: {e}")
    
    # Test 2: Try accessing SSE without token (should fail)
    print("\n2. Testing SSE access without token (should fail)...")
    try:
        response = requests.get(f"{base_url}/sse", timeout=1)
        print(f"   Response: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"   ERROR: {e}")
    
    # Test 3: Get authorization page
    print("\n3. Getting authorization page...")
    auth_params = {
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': 'full_access',
        'state': 'test-state-123'
    }
    auth_url = f"{base_url}/oauth/authorize?" + urlencode(auth_params)
    print(f"   Authorization URL: {auth_url}")
    
    try:
        response = requests.get(auth_url)
        print(f"   Response: {response.status_code}")
        if response.status_code == 200:
            print("   Login page received successfully")
    except Exception as e:
        print(f"   ERROR: {e}")
    
    # Test 4: Simulate login (this would normally be done through browser)
    print("\n4. Simulating login with credentials...")
    login_data = {
        'username': 'admin',  # Use OAUTH_USERNAME from .env
        'password': 'password',  # Use OAUTH_PASSWORD from .env
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'full_access',
        'state': 'test-state-123'
    }
    
    try:
        response = requests.post(f"{base_url}/oauth/authorize", data=login_data, allow_redirects=False)
        print(f"   Response: {response.status_code}")
        
        if response.status_code == 302:
            location = response.headers.get('Location', '')
            print(f"   Redirect to: {location}")
            
            # Extract authorization code
            if 'code=' in location:
                parsed = urlparse(location)
                params = parse_qs(parsed.query)
                auth_code = params.get('code', [''])[0]
                print(f"   Authorization code: {auth_code}")
                
                # Test 5: Exchange code for token
                print("\n5. Exchanging authorization code for access token...")
                
                # Create Basic auth header
                credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
                
                token_data = {
                    'grant_type': 'authorization_code',
                    'code': auth_code,
                    'redirect_uri': redirect_uri
                }
                
                headers = {
                    'Authorization': f'Basic {credentials}',
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
                
                response = requests.post(f"{base_url}/oauth/token", data=token_data, headers=headers)
                print(f"   Response: {response.status_code}")
                
                if response.status_code == 200:
                    token_info = response.json()
                    access_token = token_info.get('access_token')
                    print(f"   Access token: {access_token[:20]}...")
                    print(f"   Token type: {token_info.get('token_type')}")
                    print(f"   Expires in: {token_info.get('expires_in')} seconds")
                    
                    # Test 6: Access SSE with token
                    print("\n6. Accessing SSE endpoint with Bearer token...")
                    headers = {
                        'Authorization': f'Bearer {access_token}'
                    }
                    
                    try:
                        response = requests.get(f"{base_url}/sse", headers=headers, stream=True, timeout=2)
                        print(f"   Response: {response.status_code}")
                        
                        if response.status_code == 200:
                            # Read first few lines
                            session_id = None
                            for line in response.iter_lines():
                                if line:
                                    line_str = line.decode('utf-8')
                                    print(f"   {line_str}")
                                    if line_str.startswith("data: ") and "/messages/" in line_str:
                                        break
                            print("   SSE connection successful with OAuth!")
                    except requests.Timeout:
                        print("   Timeout (normal for SSE)")
                else:
                    print(f"   Token exchange failed: {response.text}")
        elif response.status_code == 401:
            print("   Login failed (check credentials)")
    except Exception as e:
        print(f"   ERROR: {e}")
    
    print("\nOAuth flow test completed!")
    print("\nFor Claude.ai Integration:")
    print(f"  1. Provide the SSE URL: https://your-domain.com/sse")
    print(f"  2. Claude.ai will detect OAuth is required and redirect to login")
    print(f"  3. Enter your OAUTH_USERNAME and OAUTH_PASSWORD")
    print(f"  4. Claude.ai will receive the token and connect automatically")

if __name__ == "__main__":
    test_oauth_flow()