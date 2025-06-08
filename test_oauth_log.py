#!/usr/bin/env python3
"""Test OAuth credential logging"""

import os
import logging
from ticktick_mcp.src.remote_server import run_remote_server

# Set up test environment
os.environ["OAUTH_USERNAME"] = "test-user"
os.environ["OAUTH_PASSWORD"] = "test-password-123"

# Test with custom credentials
print("Testing with custom credentials...")
print("Expected output should show:")
print("  Username: test-user")
print("  Password: test-password-123")
print("-" * 60)

# Note: This will start the server, you can Ctrl+C to stop
if __name__ == "__main__":
    # Just import to see the log messages
    from ticktick_mcp.src import remote_server
    print("\nCheck the logs above for OAuth credentials display")