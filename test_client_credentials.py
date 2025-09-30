#!/usr/bin/env python3
"""
Test script for Client Credentials Grant functionality.
This script tests the new OAuth Client Credentials flow for direct authentication.
"""

import requests
import json
import sys
import time

def test_client_credentials():
    """Test the Client Credentials Grant flow."""
    print("🔐 Testing Client Credentials Grant Flow\n")
    
    base_url = "http://localhost:8080"
    client_id = "ticktick-mcp-client"
    client_secret = "TMC_2024_SecureSecret_ForDirectAuth_NoRedirect"
    
    # Test 1: OAuth Discovery
    print("1. Testing OAuth Discovery endpoint...")
    try:
        response = requests.get(f"{base_url}/.well-known/oauth-authorization-server")
        response.raise_for_status()
        discovery = response.json()
        
        if "client_credentials" in discovery.get("grant_types_supported", []):
            print("✅ Client Credentials Grant is supported in OAuth discovery")
        else:
            print("❌ Client Credentials Grant not found in supported grant types")
            print(f"   Supported: {discovery.get('grant_types_supported', [])}")
            return False
            
    except Exception as e:
        print(f"❌ OAuth discovery failed: {e}")
        return False
    
    print()
    
    # Test 2: Client Credentials Token Request
    print("2. Testing Client Credentials token request...")
    try:
        token_data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret
        }
        
        response = requests.post(
            f"{base_url}/oauth/token",
            data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        response.raise_for_status()
        token_response = response.json()
        
        access_token = token_response.get("access_token")
        if access_token:
            print("✅ Successfully obtained access token")
            print(f"   Token Type: {token_response.get('token_type')}")
            print(f"   Expires In: {token_response.get('expires_in')} seconds")
            print(f"   Scope: {token_response.get('scope')}")
            print(f"   Token (first 20 chars): {access_token[:20]}...")
        else:
            print("❌ No access token received")
            print(f"   Response: {token_response}")
            return False
            
    except Exception as e:
        print(f"❌ Token request failed: {e}")
        return False
    
    print()
    
    # Test 3: SSE Endpoint Access
    print("3. Testing SSE endpoint access with token...")
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(f"{base_url}/sse", headers=headers, timeout=3, stream=True)
        
        if response.status_code == 200:
            print("✅ SSE endpoint accessible with Client Credentials token")
            
            # Read first few lines to verify SSE format
            first_line = next(response.iter_lines(decode_unicode=True))
            if first_line.startswith("event:"):
                print(f"   First SSE event: {first_line}")
            
        else:
            print(f"❌ SSE endpoint returned status: {response.status_code}")
            return False
            
    except requests.exceptions.ReadTimeout:
        # Timeout is expected for SSE connections
        print("✅ SSE connection established (timeout expected)")
    except Exception as e:
        print(f"❌ SSE endpoint test failed: {e}")
        return False
    
    print()
    
    # Test 4: Invalid Credentials
    print("4. Testing invalid credentials...")
    try:
        invalid_data = {
            "grant_type": "client_credentials",
            "client_id": "invalid-client",
            "client_secret": "invalid-secret"
        }
        
        response = requests.post(
            f"{base_url}/oauth/token",
            data=invalid_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code == 401:
            error_response = response.json()
            print("✅ Invalid credentials properly rejected")
            print(f"   Error: {error_response.get('error')}")
        else:
            print(f"❌ Expected 401, got {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Invalid credentials test failed: {e}")
        return False
    
    print()
    
    # Summary
    print("📊 Test Results Summary:")
    print("   ✅ OAuth Discovery supports client_credentials")
    print("   ✅ Client Credentials Grant working")
    print("   ✅ Access token generation successful")
    print("   ✅ SSE endpoint authentication working")
    print("   ✅ Invalid credentials properly rejected")
    
    print("\n🎉 All Client Credentials tests passed!")
    print("\n💡 Claude.ai Integration Instructions:")
    print("   1. In Claude.ai settings, add new connector:")
    print("   2. Remote MCP server URL: https://your-domain.com/sse")
    print(f"   3. OAuth Client ID: {client_id}")
    print(f"   4. OAuth Client Secret: {client_secret}")
    print("   5. Claude.ai will automatically use Client Credentials flow!")
    
    return True

if __name__ == "__main__":
    success = test_client_credentials()
    sys.exit(0 if success else 1)