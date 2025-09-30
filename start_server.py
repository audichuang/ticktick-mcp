#!/usr/bin/env python3
"""
Start the TickTick MCP server with ICS sync support
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the project to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from ticktick_mcp.src.remote_server import run_remote_server

async def main():
    """Start the server"""
    print("🚀 Starting TickTick MCP Server with ICS Sync...")
    print(f"📁 Project root: {project_root}")
    print(f"🌐 Web interface: http://localhost:8000")
    print(f"🔐 Login credentials: admin / test123")
    print("=" * 50)
    
    # Start the server
    await run_remote_server(host="0.0.0.0", port=8000)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"❌ Server error: {e}")
        sys.exit(1)