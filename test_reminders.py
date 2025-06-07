#!/usr/bin/env python3
"""
Test script for TickTick MCP Reminders functionality.
This script tests creating and updating tasks with reminders.
"""

import asyncio
import sys
from datetime import datetime, timedelta
from ticktick_mcp.src.ticktick_client import TickTickClient

async def test_reminders():
    """Test the reminders functionality."""
    print("🔔 Testing TickTick MCP Reminders Functionality\n")
    
    # Initialize client
    print("1. Initializing TickTick client...")
    try:
        client = TickTickClient()
        print("✅ Client initialized successfully\n")
    except Exception as e:
        print(f"❌ Failed to initialize client: {e}")
        return
    
    # Get projects
    print("2. Getting projects...")
    projects = client.get_projects()
    if 'error' in projects:
        print(f"❌ Failed to get projects: {projects['error']}")
        return
    
    if not projects:
        print("❌ No projects found. Please create a project first.")
        return
    
    # Use the first project
    project = projects[0]
    project_id = project['id']
    print(f"✅ Using project: {project['name']} (ID: {project_id})\n")
    
    # Calculate dates
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    tomorrow_iso = tomorrow.strftime("%Y-%m-%dT%H:%M:%S+0000")
    
    # Test 1: Create task with single reminder
    print("3. Creating task with single reminder (15 minutes before)...")
    task1 = client.create_task(
        title="Test Task with 15min Reminder",
        project_id=project_id,
        content="This task has a reminder 15 minutes before the due date",
        due_date=tomorrow_iso,
        priority=3,
        reminders=["TRIGGER:PT15M"]
    )
    
    if 'error' in task1:
        print(f"❌ Failed to create task: {task1['error']}")
        return
    
    print(f"✅ Task created: {task1['title']}")
    print(f"   ID: {task1['id']}")
    if 'reminders' in task1:
        print(f"   Reminders: {task1['reminders']}")
    print()
    
    # Test 2: Create task with multiple reminders
    print("4. Creating task with multiple reminders...")
    task2 = client.create_task(
        title="Test Task with Multiple Reminders",
        project_id=project_id,
        content="This task has multiple reminders",
        due_date=tomorrow_iso,
        priority=5,
        reminders=[
            "TRIGGER:P1DT0H0M0S",  # 1 day before
            "TRIGGER:P0DT1H0M0S",  # 1 hour before
            "TRIGGER:PT0S"         # At time of event
        ]
    )
    
    if 'error' in task2:
        print(f"❌ Failed to create task: {task2['error']}")
    else:
        print(f"✅ Task created: {task2['title']}")
        print(f"   ID: {task2['id']}")
        if 'reminders' in task2:
            print(f"   Reminders: {task2['reminders']}")
        print()
    
    # Test 3: Update task to add reminders
    print("5. Updating first task to add another reminder...")
    updated_task = client.update_task(
        task_id=task1['id'],
        project_id=project_id,
        reminders=["TRIGGER:PT15M", "TRIGGER:P0DT1H0M0S"]  # 15 min and 1 hour before
    )
    
    if 'error' in updated_task:
        print(f"❌ Failed to update task: {updated_task['error']}")
    else:
        print(f"✅ Task updated: {updated_task['title']}")
        if 'reminders' in updated_task:
            print(f"   Updated reminders: {updated_task['reminders']}")
        print()
    
    # Test 4: Remove all reminders
    print("6. Removing all reminders from a task...")
    no_reminder_task = client.update_task(
        task_id=task2['id'],
        project_id=project_id,
        reminders=[]  # Empty list removes all reminders
    )
    
    if 'error' in no_reminder_task:
        print(f"❌ Failed to update task: {no_reminder_task['error']}")
    else:
        print(f"✅ Task updated: {no_reminder_task['title']}")
        print(f"   Reminders removed: {no_reminder_task.get('reminders', [])}")
        print()
    
    # Cleanup
    print("7. Cleaning up test tasks...")
    for task in [task1, task2]:
        if 'id' in task:
            result = client.delete_task(project_id, task['id'])
            if 'error' not in result:
                print(f"✅ Deleted task: {task['title']}")
            else:
                print(f"❌ Failed to delete task: {result['error']}")
    
    print("\n✨ Reminder functionality test completed!")

if __name__ == "__main__":
    asyncio.run(test_reminders())