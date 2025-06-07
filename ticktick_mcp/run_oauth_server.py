#!/usr/bin/env python3
"""
Run the OAuth server for TickTick MCP.

This script starts the OAuth authorization server that handles the login flow
for clients like Claude.ai to authenticate and obtain access tokens.
"""

import sys
import os

# Add the parent directory to the path so we can import from ticktick_mcp
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ticktick_mcp.src.oauth_server import run_oauth_server

if __name__ == "__main__":
    import argparse
    import logging
    
    parser = argparse.ArgumentParser(description='TickTick MCP OAuth Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8080, help='Port to bind to (default: 8080)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Set up logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print(f"Starting TickTick MCP OAuth Server...")
    print(f"Server will be available at: http://{args.host}:{args.port}")
    print(f"Authorization endpoint: http://{args.host}:{args.port}/oauth/authorize")
    print(f"Token endpoint: http://{args.host}:{args.port}/oauth/token")
    print()
    print("Press Ctrl+C to stop the server")
    print()
    
    try:
        run_oauth_server(args.host, args.port)
    except KeyboardInterrupt:
        print("\nServer stopped.")