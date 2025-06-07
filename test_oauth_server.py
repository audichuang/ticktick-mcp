#!/usr/bin/env python3
"""
Test script for the OAuth server.

This script tests the OAuth authorization flow to ensure everything works correctly.
"""

import requests
import urllib.parse
import base64
import time
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Configuration
OAUTH_SERVER_URL = "http://localhost:8080"
OAUTH_USERNAME = os.getenv("OAUTH_USERNAME", "admin")
OAUTH_PASSWORD = os.getenv("OAUTH_PASSWORD", "password")
CLIENT_ID = "test-client"
CLIENT_SECRET = "test-secret"
REDIRECT_URI = "http://localhost:3000/callback"


def test_authorization_page():
    """Test that the authorization page loads correctly."""
    print("1. Testing authorization page...")
    
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "state": "test-state-123"
    }
    
    url = f"{OAUTH_SERVER_URL}/oauth/authorize?" + urllib.parse.urlencode(params)
    response = requests.get(url)
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert "TickTick MCP" in response.text, "Login page should contain TickTick MCP"
    assert "is requesting access" in response.text, "Login page should show client request"
    
    print("   ✓ Authorization page loads successfully")
    return True


def test_login_flow():
    """Test the complete login and authorization flow."""
    print("\n2. Testing login flow...")
    
    # Start a session to maintain cookies
    session = requests.Session()
    
    # Step 1: Get the login page
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "state": "test-state-456"
    }
    
    auth_url = f"{OAUTH_SERVER_URL}/oauth/authorize"
    
    # Step 2: Submit login form
    form_data = {
        "username": OAUTH_USERNAME,
        "password": OAUTH_PASSWORD,
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "state": "test-state-456",
        "scope": "tasks:read tasks:write"
    }
    
    response = session.post(auth_url, data=form_data, allow_redirects=False)
    
    # Check for redirect with authorization code
    assert response.status_code == 302, f"Expected 302 redirect, got {response.status_code}"
    location = response.headers.get("Location", "")
    assert location.startswith(REDIRECT_URI), f"Should redirect to {REDIRECT_URI}"
    
    # Parse the authorization code
    parsed_url = urllib.parse.urlparse(location)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    auth_code = query_params.get("code", [None])[0]
    state = query_params.get("state", [None])[0]
    
    assert auth_code is not None, "Authorization code should be present"
    assert state == "test-state-456", "State should match"
    
    print("   ✓ Login successful, received authorization code")
    return auth_code


def test_invalid_login():
    """Test login with invalid credentials."""
    print("\n3. Testing invalid login...")
    
    form_data = {
        "username": "wrong-user",
        "password": "wrong-password",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "state": "test-state-789"
    }
    
    response = requests.post(f"{OAUTH_SERVER_URL}/oauth/authorize", data=form_data)
    
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    assert "Invalid username or password" in response.text, "Should show error message"
    
    print("   ✓ Invalid login correctly rejected")
    return True


def test_token_exchange(auth_code):
    """Test exchanging authorization code for access token."""
    print("\n4. Testing token exchange...")
    
    # Prepare Basic Auth header
    credentials = f"{CLIENT_ID}:{CLIENT_SECRET}"
    auth_header = "Basic " + base64.b64encode(credentials.encode()).decode()
    
    headers = {
        "Authorization": auth_header,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": REDIRECT_URI
    }
    
    response = requests.post(f"{OAUTH_SERVER_URL}/oauth/token", headers=headers, data=data)
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    token_data = response.json()
    assert "access_token" in token_data, "Response should contain access_token"
    assert token_data["token_type"] == "Bearer", "Token type should be Bearer"
    
    print("   ✓ Successfully exchanged code for access token")
    print(f"   Access token: {token_data['access_token'][:20]}...")
    
    return token_data


def test_expired_code():
    """Test using an expired or invalid authorization code."""
    print("\n5. Testing expired/invalid code...")
    
    credentials = f"{CLIENT_ID}:{CLIENT_SECRET}"
    auth_header = "Basic " + base64.b64encode(credentials.encode()).decode()
    
    headers = {
        "Authorization": auth_header,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "grant_type": "authorization_code",
        "code": "invalid-code-12345",
        "redirect_uri": REDIRECT_URI
    }
    
    response = requests.post(f"{OAUTH_SERVER_URL}/oauth/token", headers=headers, data=data)
    
    assert response.status_code == 400, f"Expected 400, got {response.status_code}"
    error_data = response.json()
    assert error_data.get("error") == "invalid_grant", "Should return invalid_grant error"
    
    print("   ✓ Invalid code correctly rejected")
    return True


def main():
    """Run all tests."""
    print("Starting OAuth Server Tests")
    print("=" * 50)
    print(f"Server URL: {OAUTH_SERVER_URL}")
    print(f"Username: {OAUTH_USERNAME}")
    print(f"Client ID: {CLIENT_ID}")
    print("=" * 50)
    
    # Wait a moment for server to be ready
    print("\nWaiting for server to be ready...")
    time.sleep(1)
    
    try:
        # Run tests
        test_authorization_page()
        auth_code = test_login_flow()
        test_invalid_login()
        test_token_exchange(auth_code)
        test_expired_code()
        
        print("\n" + "=" * 50)
        print("✅ All tests passed!")
        print("=" * 50)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except requests.exceptions.ConnectionError:
        print("\n❌ Could not connect to OAuth server.")
        print("   Please make sure the server is running:")
        print("   python ticktick_mcp/run_oauth_server.py")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())