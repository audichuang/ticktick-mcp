#!/usr/bin/env python3
"""
Non-interactive authentication helper for Docker deployments.
This script allows setting up authentication without user interaction.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv, set_key

def setup_credentials_from_env():
    """
    Setup TickTick credentials from environment variables.
    This is useful for Docker deployments where interactive auth is not possible.
    
    Required environment variables:
    - TICKTICK_CLIENT_ID
    - TICKTICK_CLIENT_SECRET
    - TICKTICK_ACCESS_TOKEN (if you already have one)
    - TICKTICK_REFRESH_TOKEN (if you already have one)
    """
    # Check for required credentials
    client_id = os.getenv("TICKTICK_CLIENT_ID")
    client_secret = os.getenv("TICKTICK_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        print("ERROR: TICKTICK_CLIENT_ID and TICKTICK_CLIENT_SECRET must be set")
        return False
    
    # Check if we have tokens
    access_token = os.getenv("TICKTICK_ACCESS_TOKEN")
    refresh_token = os.getenv("TICKTICK_REFRESH_TOKEN")
    
    if not access_token:
        print("WARNING: No TICKTICK_ACCESS_TOKEN found.")
        print("You will need to run the interactive auth flow first to get tokens.")
        print("\nTo get tokens:")
        print("1. Run locally: uv run -m ticktick_mcp.cli auth")
        print("2. Copy the tokens from .env file")
        print("3. Set them as environment variables in Docker")
        return False
    
    # Create .env file with credentials
    env_path = Path(".env")
    
    # Write credentials to .env file
    with open(env_path, "w") as f:
        f.write(f"TICKTICK_CLIENT_ID={client_id}\n")
        f.write(f"TICKTICK_CLIENT_SECRET={client_secret}\n")
        f.write(f"TICKTICK_ACCESS_TOKEN={access_token}\n")
        if refresh_token:
            f.write(f"TICKTICK_REFRESH_TOKEN={refresh_token}\n")
    
    print("Credentials successfully written to .env file")
    return True

def main():
    """Main entry point."""
    if setup_credentials_from_env():
        print("Authentication setup complete!")
        return 0
    else:
        print("Authentication setup failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())