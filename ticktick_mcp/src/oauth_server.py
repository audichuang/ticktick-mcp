"""
OAuth 2.0 Authorization Server for TickTick MCP.

This module implements a simple OAuth 2.0 authorization server with a login page
for authenticating users before granting access to Claude.ai or other OAuth clients.
"""

import os
import json
import time
import secrets
import hashlib
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Optional, Tuple
from dotenv import load_dotenv
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# OAuth server configuration
OAUTH_USERNAME = os.getenv("OAUTH_USERNAME", "admin")
OAUTH_PASSWORD = os.getenv("OAUTH_PASSWORD", "password")
OAUTH_CLIENT_ID = os.getenv("TICKTICK_CLIENT_ID", "ticktick-mcp")
OAUTH_CLIENT_SECRET = os.getenv("TICKTICK_CLIENT_SECRET", "secret")

# In-memory storage for authorization codes and sessions
auth_codes = {}  # code -> {client_id, redirect_uri, expires_at, username}
sessions = {}    # session_id -> {username, expires_at}

# HTML template for the login page
LOGIN_PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TickTick MCP - Authorization</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #f5f5f5;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1), 0 1px 3px rgba(0, 0, 0, 0.08);
            max-width: 400px;
            width: 100%;
            padding: 40px;
        }
        
        .logo {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .logo h1 {
            color: #333;
            font-size: 24px;
            font-weight: 600;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }
        
        .logo .icon {
            width: 32px;
            height: 32px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
        }
        
        .auth-info {
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 24px;
        }
        
        .auth-info h2 {
            font-size: 16px;
            color: #333;
            margin-bottom: 8px;
            font-weight: 500;
        }
        
        .auth-info .client-name {
            font-weight: 600;
            color: #007bff;
        }
        
        .auth-info .redirect-url {
            font-size: 12px;
            color: #6c757d;
            word-break: break-all;
            margin-top: 4px;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        label {
            display: block;
            margin-bottom: 8px;
            color: #495057;
            font-size: 14px;
            font-weight: 500;
        }
        
        input[type="text"],
        input[type="password"] {
            width: 100%;
            padding: 10px 14px;
            border: 1px solid #ced4da;
            border-radius: 6px;
            font-size: 14px;
            transition: border-color 0.15s ease-in-out, box-shadow 0.15s ease-in-out;
        }
        
        input[type="text"]:focus,
        input[type="password"]:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        .button-group {
            display: flex;
            gap: 12px;
            margin-top: 24px;
        }
        
        button {
            flex: 1;
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s ease-in-out;
        }
        
        .btn-cancel {
            background-color: #e9ecef;
            color: #495057;
        }
        
        .btn-cancel:hover {
            background-color: #dee2e6;
        }
        
        .btn-approve {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .btn-approve:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
        }
        
        .error-message {
            background-color: #f8d7da;
            border: 1px solid #f5c6cb;
            color: #721c24;
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 20px;
            font-size: 14px;
        }
        
        .hidden {
            display: none;
        }
        
        @media (max-width: 480px) {
            .container {
                padding: 30px 20px;
            }
            
            .logo h1 {
                font-size: 20px;
            }
            
            .button-group {
                flex-direction: column;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">
            <h1>
                <span class="icon">T</span>
                TickTick MCP
            </h1>
        </div>
        
        <div class="auth-info">
            <h2><span class="client-name">{client_name}</span> is requesting access</h2>
            <div class="redirect-url">Redirect: {redirect_url}</div>
        </div>
        
        <div id="error-message" class="error-message {error_class}">
            {error_message}
        </div>
        
        <form method="POST" action="{form_action}">
            <div class="form-group">
                <label for="username">Username</label>
                <input type="text" id="username" name="username" required autofocus>
            </div>
            
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required>
            </div>
            
            <input type="hidden" name="client_id" value="{client_id}">
            <input type="hidden" name="redirect_uri" value="{redirect_uri}">
            <input type="hidden" name="response_type" value="{response_type}">
            <input type="hidden" name="state" value="{state}">
            <input type="hidden" name="scope" value="{scope}">
            
            <div class="button-group">
                <button type="button" class="btn-cancel" onclick="handleCancel()">Cancel</button>
                <button type="submit" class="btn-approve">Approve</button>
            </div>
        </form>
    </div>
    
    <script>
        function handleCancel() {
            // Redirect back with an error
            const params = new URLSearchParams(window.location.search);
            const redirectUri = params.get('redirect_uri');
            const state = params.get('state');
            
            if (redirectUri) {
                const separator = redirectUri.includes('?') ? '&' : '?';
                window.location.href = redirectUri + separator + 'error=access_denied' + (state ? '&state=' + state : '');
            }
        }
    </script>
</body>
</html>
"""


class OAuthServerHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the OAuth server."""
    
    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urllib.parse.urlparse(self.path)
        
        if parsed_path.path == '/oauth/authorize':
            self.handle_authorize_get(parsed_path)
        elif parsed_path.path == '/oauth/token':
            self.send_error(405, "Method Not Allowed")
        else:
            self.send_error(404, "Not Found")
    
    def do_POST(self):
        """Handle POST requests."""
        parsed_path = urllib.parse.urlparse(self.path)
        
        if parsed_path.path == '/oauth/authorize':
            self.handle_authorize_post()
        elif parsed_path.path == '/oauth/token':
            self.handle_token_request()
        else:
            self.send_error(404, "Not Found")
    
    def handle_authorize_get(self, parsed_path):
        """Handle GET requests to /oauth/authorize - show login page."""
        params = urllib.parse.parse_qs(parsed_path.query)
        
        # Extract parameters
        client_id = params.get('client_id', [''])[0]
        redirect_uri = params.get('redirect_uri', [''])[0]
        response_type = params.get('response_type', [''])[0]
        state = params.get('state', [''])[0]
        scope = params.get('scope', [''])[0]
        
        # Validate required parameters
        if not client_id or not redirect_uri or response_type != 'code':
            self.send_error(400, "Invalid request parameters")
            return
        
        # For demo purposes, we'll accept any client_id
        # In production, you'd validate against registered clients
        
        # Prepare template variables
        template_vars = {
            'client_name': 'claude.ai' if 'claude.ai' in redirect_uri else client_id,
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'redirect_url': redirect_uri,
            'response_type': response_type,
            'state': state,
            'scope': scope,
            'form_action': '/oauth/authorize',
            'error_message': '',
            'error_class': 'hidden'
        }
        
        # Render the login page
        html = LOGIN_PAGE_TEMPLATE.format(**template_vars)
        
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', str(len(html)))
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))
    
    def handle_authorize_post(self):
        """Handle POST requests to /oauth/authorize - process login."""
        # Parse form data
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        form_data = urllib.parse.parse_qs(post_data)
        
        # Extract form fields
        username = form_data.get('username', [''])[0]
        password = form_data.get('password', [''])[0]
        client_id = form_data.get('client_id', [''])[0]
        redirect_uri = form_data.get('redirect_uri', [''])[0]
        response_type = form_data.get('response_type', [''])[0]
        state = form_data.get('state', [''])[0]
        scope = form_data.get('scope', [''])[0]
        
        # Validate credentials
        if username == OAUTH_USERNAME and password == OAUTH_PASSWORD:
            # Generate authorization code
            auth_code = secrets.token_urlsafe(32)
            
            # Store auth code with metadata (expires in 10 minutes)
            auth_codes[auth_code] = {
                'client_id': client_id,
                'redirect_uri': redirect_uri,
                'expires_at': time.time() + 600,
                'username': username,
                'scope': scope
            }
            
            # Redirect back to client with auth code
            redirect_params = {'code': auth_code}
            if state:
                redirect_params['state'] = state
            
            redirect_url = redirect_uri + ('&' if '?' in redirect_uri else '?') + urllib.parse.urlencode(redirect_params)
            
            self.send_response(302)
            self.send_header('Location', redirect_url)
            self.end_headers()
        else:
            # Invalid credentials - show error
            template_vars = {
                'client_name': 'claude.ai' if 'claude.ai' in redirect_uri else client_id,
                'client_id': client_id,
                'redirect_uri': redirect_uri,
                'redirect_url': redirect_uri,
                'response_type': response_type,
                'state': state,
                'scope': scope,
                'form_action': '/oauth/authorize',
                'error_message': 'Invalid username or password',
                'error_class': ''
            }
            
            html = LOGIN_PAGE_TEMPLATE.format(**template_vars)
            
            self.send_response(401)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', str(len(html)))
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
    
    def handle_token_request(self):
        """Handle POST requests to /oauth/token - exchange code for token."""
        # Parse form data
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        form_data = urllib.parse.parse_qs(post_data)
        
        grant_type = form_data.get('grant_type', [''])[0]
        code = form_data.get('code', [''])[0]
        redirect_uri = form_data.get('redirect_uri', [''])[0]
        
        # Extract client credentials from Authorization header
        auth_header = self.headers.get('Authorization', '')
        client_id = None
        client_secret = None
        
        if auth_header.startswith('Basic '):
            try:
                import base64
                credentials = base64.b64decode(auth_header[6:]).decode('utf-8')
                client_id, client_secret = credentials.split(':', 1)
            except:
                pass
        
        # For demo purposes, accept any client credentials
        # In production, validate against registered clients
        
        if grant_type != 'authorization_code' or not code:
            self.send_json_response(400, {'error': 'invalid_request'})
            return
        
        # Validate authorization code
        auth_data = auth_codes.get(code)
        if not auth_data or auth_data['expires_at'] < time.time():
            self.send_json_response(400, {'error': 'invalid_grant'})
            return
        
        # Remove used auth code
        del auth_codes[code]
        
        # Generate access token
        access_token = secrets.token_urlsafe(64)
        
        # Create token response
        token_response = {
            'access_token': access_token,
            'token_type': 'Bearer',
            'expires_in': 3600,
            'scope': auth_data.get('scope', '')
        }
        
        self.send_json_response(200, token_response)
    
    def send_json_response(self, status_code: int, data: dict):
        """Send a JSON response."""
        response = json.dumps(data)
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(response)))
        self.end_headers()
        self.wfile.write(response.encode('utf-8'))
    
    def log_message(self, format, *args):
        """Override to customize logging."""
        logger.info(f"{self.address_string()} - {format % args}")


def cleanup_expired_codes():
    """Remove expired authorization codes."""
    current_time = time.time()
    expired_codes = [code for code, data in auth_codes.items() if data['expires_at'] < current_time]
    for code in expired_codes:
        del auth_codes[code]


def run_oauth_server(host: str = 'localhost', port: int = 8080):
    """Run the OAuth authorization server."""
    server_address = (host, port)
    httpd = HTTPServer(server_address, OAuthServerHandler)
    
    logger.info(f"OAuth server running on http://{host}:{port}")
    logger.info(f"Authorization endpoint: http://{host}:{port}/oauth/authorize")
    logger.info(f"Token endpoint: http://{host}:{port}/oauth/token")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("OAuth server shutting down...")
        httpd.shutdown()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='TickTick MCP OAuth Server')
    parser.add_argument('--host', default='localhost', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8080, help='Port to bind to')
    
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    run_oauth_server(args.host, args.port)