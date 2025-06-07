#!/usr/bin/env python3
"""
Example integration showing how to use the OAuth server with TickTick MCP.

This demonstrates how Claude.ai or other clients would integrate with the OAuth flow.
"""

import webbrowser
import urllib.parse
import requests
import base64
import http.server
import socketserver
from typing import Optional


class OAuthClient:
    """Example OAuth client implementation."""
    
    def __init__(self, auth_url: str, token_url: str, client_id: str, 
                 client_secret: str, redirect_uri: str):
        self.auth_url = auth_url
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.auth_code = None
        self.access_token = None
    
    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """Generate the authorization URL."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "tasks:read tasks:write"
        }
        
        if state:
            params["state"] = state
        
        return f"{self.auth_url}?" + urllib.parse.urlencode(params)
    
    def start_authorization_flow(self):
        """Start the OAuth authorization flow."""
        # Generate authorization URL
        auth_url = self.get_authorization_url(state="demo-state-123")
        
        print(f"Opening browser for authorization...")
        print(f"If the browser doesn't open, visit: {auth_url}")
        
        # Open browser
        webbrowser.open(auth_url)
        
        # Start local server to receive callback
        self._start_callback_server()
    
    def _start_callback_server(self):
        """Start a local server to receive the OAuth callback."""
        class CallbackHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(handler_self):
                # Parse query parameters
                query = urllib.parse.urlparse(handler_self.path).query
                params = urllib.parse.parse_qs(query)
                
                if 'code' in params:
                    self.auth_code = params['code'][0]
                    
                    # Send success response
                    handler_self.send_response(200)
                    handler_self.send_header('Content-type', 'text/html')
                    handler_self.end_headers()
                    
                    response = """
                    <html>
                    <body style="font-family: Arial; text-align: center; padding: 50px;">
                        <h1>Authorization Successful!</h1>
                        <p>You can close this window and return to the application.</p>
                    </body>
                    </html>
                    """
                    handler_self.wfile.write(response.encode())
                else:
                    handler_self.send_response(400)
                    handler_self.end_headers()
            
            def log_message(self, format, *args):
                pass  # Suppress logs
        
        # Extract port from redirect URI
        parsed_uri = urllib.parse.urlparse(self.redirect_uri)
        port = parsed_uri.port or 3000
        
        print(f"Waiting for authorization callback on port {port}...")
        
        with socketserver.TCPServer(("", port), CallbackHandler) as httpd:
            # Wait for one request
            httpd.handle_request()
    
    def exchange_code_for_token(self) -> bool:
        """Exchange authorization code for access token."""
        if not self.auth_code:
            print("No authorization code available")
            return False
        
        # Prepare request
        credentials = f"{self.client_id}:{self.client_secret}"
        auth_header = "Basic " + base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Authorization": auth_header,
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "grant_type": "authorization_code",
            "code": self.auth_code,
            "redirect_uri": self.redirect_uri
        }
        
        try:
            response = requests.post(self.token_url, headers=headers, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data.get("access_token")
            
            print(f"\nAccess token obtained successfully!")
            print(f"Token: {self.access_token[:20]}...")
            print(f"Type: {token_data.get('token_type')}")
            print(f"Expires in: {token_data.get('expires_in')} seconds")
            
            return True
            
        except Exception as e:
            print(f"Error exchanging code for token: {e}")
            return False
    
    def make_api_request(self, endpoint: str) -> Optional[dict]:
        """Make an authenticated API request."""
        if not self.access_token:
            print("No access token available")
            return None
        
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        
        try:
            response = requests.get(endpoint, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"API request failed: {e}")
            return None


def main():
    """Run the OAuth client example."""
    print("TickTick MCP OAuth Client Example")
    print("=" * 50)
    
    # Configure OAuth client
    client = OAuthClient(
        auth_url="http://localhost:8080/oauth/authorize",
        token_url="http://localhost:8080/oauth/token",
        client_id="demo-client",
        client_secret="demo-secret",
        redirect_uri="http://localhost:3000/callback"
    )
    
    print("\nStarting OAuth flow...")
    print("1. You'll be redirected to the login page")
    print("2. Enter your credentials (check .env file)")
    print("3. Click 'Approve' to grant access")
    print("4. You'll be redirected back here\n")
    
    # Start authorization flow
    client.start_authorization_flow()
    
    if client.auth_code:
        print(f"\nReceived authorization code: {client.auth_code[:10]}...")
        
        # Exchange code for token
        if client.exchange_code_for_token():
            print("\n✅ OAuth flow completed successfully!")
            
            # Example: Make an API request with the token
            print("\nExample API usage:")
            print("You can now use the access token to make authenticated requests")
            print("to the TickTick MCP server.")
        else:
            print("\n❌ Failed to exchange code for token")
    else:
        print("\n❌ No authorization code received")


if __name__ == "__main__":
    main()