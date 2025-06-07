#\!/usr/bin/env python3
"""
Test MCP server reminder functionality through the MCP protocol.
"""

import asyncio
import json
from datetime import datetime, timedelta
from mcp.client import ClientSession, stdio_client
from contextlib import AsyncExitStack

async def test_mcp_reminders():
    """Test reminder functionality through MCP."""
    print("🔔 Testing MCP Server Reminder Functionality\n")
    
    async with AsyncExitStack() as stack:
        # Start MCP client
        print("1. Connecting to MCP server...")
        read, write = await stack.enter_async_context(stdio_client())
        session = await stack.enter_async_context(ClientSession(read, write))
        
        # Initialize the connection
        result = await session.initialize()
        print(f"✅ Connected to: {result.server_info.name}\n")
        
        # List available tools
        print("2. Available tools:")
        tools = await session.list_tools()
        reminder_tools = [t.name for t in tools.tools if t.name in ['create_task', 'update_task']]
        print(f"   Found reminder-capable tools: {reminder_tools}\n")
        
        # Get projects
        print("3. Getting projects...")
        projects_result = await session.call_tool("get_projects", arguments={})
        print(projects_result.content[0].text[:200] + "...\n")
        
        # Extract first project ID from the response
        # This is a simple extraction - in real use you'd parse more carefully
        project_id = None
        for line in projects_result.content[0].text.split('\n'):
            if line.strip().startswith('ID:'):
                project_id = line.split('ID:')[1].strip()
                break
        
        if not project_id:
            print("❌ Could not find a project ID")
            return
            
        print(f"   Using project ID: {project_id}\n")
        
        # Calculate tomorrow's date
        tomorrow = datetime.now() + timedelta(days=1)
        tomorrow_iso = tomorrow.strftime("%Y-%m-%dT%H:%M:%S+0000")
        
        # Test creating task with reminders
        print("4. Creating task with reminders...")
        create_result = await session.call_tool(
            "create_task",
            arguments={
                "title": "MCP Test Task with Reminders",
                "project_id": project_id,
                "content": "Testing reminder functionality through MCP",
                "due_date": tomorrow_iso,
                "priority": 3,
                "reminders": ["TRIGGER:PT30M", "TRIGGER:P0DT2H0M0S"]
            }
        )
        print(create_result.content[0].text[:300] + "...\n")
        
        # Extract task ID
        task_id = None
        for line in create_result.content[0].text.split('\n'):
            if line.strip().startswith('ID:'):
                task_id = line.split('ID:')[1].strip()
                break
                
        if task_id:
            print(f"   Created task ID: {task_id}\n")
            
            # Test updating reminders
            print("5. Updating task reminders...")
            update_result = await session.call_tool(
                "update_task",
                arguments={
                    "task_id": task_id,
                    "project_id": project_id,
                    "reminders": ["TRIGGER:PT15M", "TRIGGER:PT0S"]
                }
            )
            print(update_result.content[0].text[:300] + "...\n")
            
            # Clean up
            print("6. Cleaning up...")
            delete_result = await session.call_tool(
                "delete_task",
                arguments={
                    "project_id": project_id,
                    "task_id": task_id
                }
            )
            print(f"   {delete_result.content[0].text}\n")
        
        print("✨ MCP reminder functionality test completed\!")

if __name__ == "__main__":
    asyncio.run(test_mcp_reminders())
EOF < /dev/null