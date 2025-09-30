#!/usr/bin/env python3
"""
Test script for the web authentication flow
"""

import json
import requests
import time

def test_web_login():
    """Test the web login endpoint"""
    print("🔐 Testing Web Authentication Flow...")
    
    # Test login endpoint
    login_url = "http://localhost:8000/api/login"
    login_data = {
        "username": "admin",
        "password": "test123"
    }
    
    try:
        print(f"📡 POST {login_url}")
        print(f"📝 Data: {login_data}")
        
        response = requests.post(
            login_url,
            json=login_data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"📊 Status: {response.status_code}")
        print(f"📄 Response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and data.get('token'):
                print("✅ Login successful!")
                token = data['token']
                
                # Test authenticated API call
                print("\n🔧 Testing authenticated API call...")
                api_url = "http://localhost:8000/tools/call"
                api_data = {
                    "name": "get_ics_sync_status",
                    "arguments": {}
                }
                
                api_response = requests.post(
                    api_url,
                    json=api_data,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {token}"
                    }
                )
                
                print(f"📊 API Status: {api_response.status_code}")
                print(f"📄 API Response: {api_response.text}")
                
                if api_response.status_code == 200:
                    print("✅ Authenticated API call successful!")
                    return True
                else:
                    print("❌ Authenticated API call failed")
                    return False
            else:
                print("❌ Login response missing token")
                return False
        else:
            print("❌ Login failed")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed - is the server running?")
        print("💡 Start the server with: python -m ticktick_mcp.src.remote_server")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_invalid_login():
    """Test login with invalid credentials"""
    print("\n🚫 Testing Invalid Credentials...")
    
    login_url = "http://localhost:8000/api/login"
    login_data = {
        "username": "wrong",
        "password": "wrong"
    }
    
    try:
        response = requests.post(
            login_url,
            json=login_data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"📊 Status: {response.status_code}")
        print(f"📄 Response: {response.text}")
        
        if response.status_code == 401:
            data = response.json()
            if not data.get('success') and data.get('error'):
                print("✅ Invalid credentials correctly rejected!")
                return True
        
        print("❌ Invalid credentials should be rejected")
        return False
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Web Authentication Test Suite\n")
    
    # Test valid login
    valid_result = test_web_login()
    
    # Test invalid login
    invalid_result = test_invalid_login()
    
    print(f"\n📊 Test Results:")
    print(f"✅ Valid login: {'PASS' if valid_result else 'FAIL'}")
    print(f"✅ Invalid login rejection: {'PASS' if invalid_result else 'FAIL'}")
    
    if valid_result and invalid_result:
        print("\n🎉 All tests passed! Web authentication is working correctly.")
        print("\n📝 You can now:")
        print("1. Open http://localhost:3000 for development server")
        print("2. Or access http://localhost:8000 for production build")
        print("3. Login with: admin / test123")
    else:
        print("\n❌ Some tests failed. Please check the server logs.")